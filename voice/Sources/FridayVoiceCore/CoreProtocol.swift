import Foundation

/// Protocole JSON Lines entre l'app Swift et le cœur Python (`python -m friday --serve`).
///
/// app → cœur : ask{id, text, source}, metrics{ttfa_ms}, reset, shutdown
/// cœur → app : ready{name, brain, claude_binary?}, reply{id, text, intent, agent, login_required?}, error{message}
public enum CoreRequest: Equatable, Sendable {
    case ask(id: Int, text: String, source: String)     // source : "voice" | "text"
    case metrics(ttfaMs: Int)
    case reset                                          // nouvelle conversation
    case shutdown

    public func jsonLine() -> String {
        var obj: [String: Any]
        switch self {
        case .ask(let id, let text, let source): obj = ["type": "ask", "id": id, "text": text, "source": source]
        case .metrics(let ms): obj = ["type": "metrics", "ttfa_ms": ms]
        case .reset: obj = ["type": "reset"]
        case .shutdown: obj = ["type": "shutdown"]
        }
        let data = (try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes])) ?? Data("{}".utf8)
        return String(decoding: data, as: UTF8.self)
    }
}

public enum CoreEvent: Equatable, Sendable {
    case ready(name: String, brain: String, claudeBinary: String?)
    case reply(id: Int, text: String, intent: String, agent: String, loginRequired: Bool)
    case error(String)

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
                          loginRequired: obj["login_required"] as? Bool ?? false)
        case "error": return .error(obj["message"] as? String ?? "erreur inconnue")
        default: return nil
        }
    }
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
