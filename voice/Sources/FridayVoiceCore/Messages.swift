import Foundation

/// Protocole JSON Lines entre friday-voice (stdout/stdin) et le cœur Python.
public struct OutMessage: Codable, Equatable, Sendable {
    public var type: String                 // ready | state | utterance | barge_in | metrics | error
    public var state: String?
    public var text: String?
    public var ttfaMs: Int?
    public var message: String?

    enum CodingKeys: String, CodingKey {
        case type, state, text, message
        case ttfaMs = "ttfa_ms"
    }

    public init(type: String, state: String? = nil, text: String? = nil, ttfaMs: Int? = nil, message: String? = nil) {
        self.type = type; self.state = state; self.text = text; self.ttfaMs = ttfaMs; self.message = message
    }

    public func jsonLine() -> String {
        let enc = JSONEncoder()
        enc.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return String(decoding: (try? enc.encode(self)) ?? Data("{}".utf8), as: UTF8.self)
    }
}

public enum InMessage: Equatable, Sendable {
    case say(String)
    case stop
    case shutdown

    public static func parse(_ line: String) -> InMessage? {
        guard let obj = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any],
              let type = obj["type"] as? String else { return nil }
        switch type {
        case "say": return (obj["text"] as? String).map { .say($0) }
        case "stop": return .stop
        case "shutdown": return .shutdown
        default: return nil
        }
    }
}
