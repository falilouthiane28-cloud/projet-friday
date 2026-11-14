import Foundation

/// Protocole JSON Lines entre l'app Swift et le cœur Python (`python -m friday --serve`).
///
/// app → cœur : ask{id, text, source}, metrics{ttfa_ms}, reset, confirm_result{id, ok}, shutdown,
///              memory_list, memory_forget{id}
/// cœur → app : ready{name, brain, claude_binary?}, chunk{id, text}, reply{id, text, intent, agent, login_required?},
///              error{message}, confirm{id, summary, action}, confirm_expired{id}, notice{text},
///              memory{facts: [{id, text, category, created_at}], available, forgot?}
public enum CoreRequest: Equatable, Sendable {
    case ask(id: Int, text: String, source: String)     // source : "voice" | "text"
    case metrics(ttfaMs: Int)
    case reset                                          // nouvelle conversation
    case confirmResult(id: Int, ok: Bool)               // réponse à une demande Tier 1
    case shutdown
    case memoryList                                     // « Ce dont Friday se souvient… »
    case memoryForget(id: Int)                          // oublier un fait précis

    public func jsonLine() -> String {
        var obj: [String: Any]
        switch self {
        case .ask(let id, let text, let source): obj = ["type": "ask", "id": id, "text": text, "source": source]
        case .metrics(let ms): obj = ["type": "metrics", "ttfa_ms": ms]
        case .reset: obj = ["type": "reset"]
        case .confirmResult(let id, let ok): obj = ["type": "confirm_result", "id": id, "ok": ok]
        case .shutdown: obj = ["type": "shutdown"]
        case .memoryList: obj = ["type": "memory_list"]
        case .memoryForget(let id): obj = ["type": "memory_forget", "id": id]
        }
        let data = (try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes])) ?? Data("{}".utf8)
        return String(decoding: data, as: UTF8.self)
    }
}

public enum CoreEvent: Equatable, Sendable {
    case ready(name: String, brain: String, claudeBinary: String?)
    case chunk(id: Int, text: String)                   // une phrase de la réponse en cours
    case reply(id: Int, text: String, intent: String, agent: String, loginRequired: Bool, streamed: Bool)
    case error(String)
    case confirm(id: Int, summary: String, action: String)   // action Tier 1 : Autoriser / Refuser
    case confirmExpired(id: Int)                        // 60 s sans réponse : refusée par le cœur
    case notice(String)                                 // action Tier 2 exécutée
    case memory(facts: [MemoryFact], available: Bool, forgot: Bool?)   // faits mémorisés (plus récents d'abord)

    public static func parse(_ line: String) -> CoreEvent? {
        guard let obj = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any],
              let type = obj["type"] as? String else { return nil }
        switch type {
        case "ready":
            return .ready(name: obj["name"] as? String ?? "Friday", brain: obj["brain"] as? String ?? "local",
                          claudeBinary: obj["claude_binary"] as? String)
        case "reply":
            guard let id = obj["id"] as? Int, let text = obj["text"] as? String else { return nil }
            return .reply(id: id, text: text, intent: obj["intent"] as? String ?? "", agent: obj["agent"] as? String ?? "",
                          loginRequired: obj["login_required"] as? Bool ?? false, streamed: obj["streamed"] as? Bool ?? false)
        case "chunk":
            guard let id = obj["id"] as? Int, let text = obj["text"] as? String else { return nil }
            return .chunk(id: id, text: text)
        case "error": return .error(obj["message"] as? String ?? "erreur inconnue")
        case "confirm":
            guard let id = obj["id"] as? Int, let summary = obj["summary"] as? String, !summary.isEmpty else { return nil }
            return .confirm(id: id, summary: summary, action: obj["action"] as? String ?? "")
        case "confirm_expired":
            guard let id = obj["id"] as? Int else { return nil }
            return .confirmExpired(id: id)
        case "notice":
            guard let text = obj["text"] as? String, !text.isEmpty else { return nil }
            return .notice(text)
        case "memory":
            guard let raw = obj["facts"] as? [[String: Any]] else { return nil }
            let facts = raw.compactMap { f -> MemoryFact? in
                guard let id = f["id"] as? Int, let text = f["text"] as? String, !text.isEmpty else { return nil }
                return MemoryFact(id: id, text: text, category: f["category"] as? String ?? "general",
                                  createdAt: f["created_at"] as? String ?? "")
            }
            return .memory(facts: facts, available: obj["available"] as? Bool ?? true, forgot: obj["forgot"] as? Bool)
        default: return nil
        }
    }
}

/// Un fait que Friday a retenu sur l'utilisateur.
public struct MemoryFact: Equatable, Sendable, Identifiable {
    public let id: Int
    public let text: String
    public let category: String
    public let createdAt: String                        // ISO 8601 (UTC)

    public init(id: Int, text: String, category: String = "general", createdAt: String = "") {
        self.id = id
        self.text = text
        self.category = category
        self.createdAt = createdAt
    }

    public var categoryLabel: String {
        switch category {
        case "identite": "Identité"
        case "proches": "Proches"
        case "preference": "Préférence"
        case "habitude": "Habitude"
        case "projet": "Projet"
        case "travail": "Travail"
        case "sante": "Santé"
        default: "Divers"
        }
    }

    /// « 14/11/2026 », ou "" si la date est illisible.
    public var dayLabel: String {
        let parts = createdAt.prefix(10).split(separator: "-")
        guard parts.count == 3 else { return "" }
        return "\(parts[2])/\(parts[1])/\(parts[0])"
    }
}

/// « Ce dont Friday se souvient… » : liste des faits et oubli en deux temps (Oublier → Confirmer).
public struct MemoryBook: Equatable, Sendable {
    public enum Phase: Equatable, Sendable { case idle, loading, loaded, unavailable }
    public private(set) var facts: [MemoryFact] = []
    public private(set) var phase: Phase = .idle
    public private(set) var armed: Int? = nil           // fait dont l'oubli attend la confirmation
    public private(set) var forgetting: Int? = nil      // demande envoyée, réponse attendue
    public private(set) var lastMessage: String? = nil

    public init() {}

    /// Ouverture du panneau : la liste est redemandée au cœur.
    public mutating func open() -> CoreRequest {
        phase = .loading
        armed = nil
        lastMessage = nil
        return .memoryList
    }

    /// 1er appui : arme ; 2e appui sur le même fait : la demande d'oubli part (une seule fois).
    public mutating func tapForget(_ id: Int) -> CoreRequest? {
        guard forgetting == nil, facts.contains(where: { $0.id == id }) else { return nil }
        if armed == id {
            armed = nil
            forgetting = id
            return .memoryForget(id: id)
        }
        armed = id
        return nil
    }

    public mutating func cancel() { armed = nil }

    public mutating func apply(facts: [MemoryFact], available: Bool, forgot: Bool?) {
        self.facts = facts
        phase = available ? .loaded : .unavailable
        if let forgot { lastMessage = forgot ? "C'est oublié." : "Ce fait n'existait plus." }
        forgetting = nil
        if let a = armed, !facts.contains(where: { $0.id == a }) { armed = nil }
    }

    public var emptyText: String {
        switch phase {
        case .idle, .loading: "Chargement…"
        case .unavailable: "La mémoire n'est pas disponible (cœur en mode local)."
        case .loaded: "Friday ne se souvient encore de rien. Dites par exemple « ma sœur s'appelle Awa »."
        }
    }
}

/// Demande de confirmation d'une action Tier 1, affichée en carte Autoriser / Refuser dans le fil.
public struct ConfirmRequest: Equatable, Sendable {
    public enum State: Equatable, Sendable { case pending, allowed, denied, expired }
    public let id: Int
    public let summary: String
    public let action: String
    public private(set) var state: State = .pending

    public init(id: Int, summary: String, action: String) {
        self.id = id
        self.summary = summary
        self.action = action
    }

    /// Réponse du maître : le message à envoyer au cœur, une seule fois (nil si déjà tranchée).
    public mutating func answer(_ ok: Bool) -> CoreRequest? {
        guard state == .pending else { return nil }
        state = ok ? .allowed : .denied
        return .confirmResult(id: id, ok: ok)
    }

    /// Délai dépassé côté cœur : la carte se ferme, l'action est refusée.
    public mutating func expire() {
        if state == .pending { state = .expired }
    }

    public var statusText: String {
        switch state {
        case .pending: "En attente de votre accord"
        case .allowed: "Autorisé"
        case .denied: "Refusé"
        case .expired: "Refusé (sans réponse en 60 s)"
        }
    }

    /// Annonce vocale de la demande (la réponse se donne dans la bulle).
    public var spoken: String { "J'ai besoin de votre accord : \(summary). Autorisez ou refusez dans la bulle." }
}

/// Niveau du micro pour l'avatar : RMS linéaire → 0…1 sur une échelle en dB.
public enum AudioLevel {
    public static let floorDb = -50.0
    public static let ceilDb = -10.0

    public static func normalized(rms: Float) -> Double {
        guard rms > 0, rms.isFinite else { return 0 }
        let db = 20 * log10(Double(rms))
        return min(1, max(0, (db - floorDb) / (ceilDb - floorDb)))
    }

    /// Lissage : montée rapide, descente lente (l'avatar ne clignote pas).
    public static func smoothed(previous: Double, target: Double) -> Double {
        target > previous ? previous + (target - previous) * 0.6 : previous + (target - previous) * 0.15
    }
}

/// Racine du dépôt (là où se trouve `pyproject.toml`), en remontant depuis l'exécutable.
public func findRepoRoot(from start: URL, exists: (URL) -> Bool) -> URL? {
    var dir = start.standardizedFileURL
    for _ in 0..<8 {
        if exists(dir.appendingPathComponent("pyproject.toml")) { return dir }
        let parent = dir.deletingLastPathComponent()
        if parent.path == dir.path { return nil }
        dir = parent
    }
    return nil
}
