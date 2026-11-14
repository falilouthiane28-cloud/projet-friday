import Foundation

/// Protocole JSON Lines entre l'app Swift et le cœur Python (`python -m friday --serve`).
///
/// app → cœur : ask{id, text, source}, metrics{ttfa_ms}, reset, confirm_result{id, ok}, shutdown
/// cœur → app : ready{name, brain, claude_binary?}, chunk{id, text}, reply{id, text, intent, agent, login_required?},
///              error{message}, confirm{id, summary, action}, confirm_expired{id}, notice{text}
public enum CoreRequest: Equatable, Sendable {
    case ask(id: Int, text: String, source: String)     // source : "voice" | "text"
    case metrics(ttfaMs: Int)
    case reset                                          // nouvelle conversation
    case confirmResult(id: Int, ok: Bool)               // réponse à une demande Tier 1
    case shutdown

    public func jsonLine() -> String {
        var obj: [String: Any]
        switch self {
        case .ask(let id, let text, let source): obj = ["type": "ask", "id": id, "text": text, "source": source]
        case .metrics(let ms): obj = ["type": "metrics", "ttfa_ms": ms]
        case .reset: obj = ["type": "reset"]
        case .confirmResult(let id, let ok): obj = ["type": "confirm_result", "id": id, "ok": ok]
        case .shutdown: obj = ["type": "shutdown"]
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
        default: return nil
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
