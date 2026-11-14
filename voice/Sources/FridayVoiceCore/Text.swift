import Foundation

/// Minuscules, sans accents ni ponctuation, espaces simples.
public func normalizeSpeech(_ text: String) -> String {
    let folded = text.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "fr_FR"))
    let cleaned = folded.unicodeScalars.map { CharacterSet.alphanumerics.contains($0) || $0 == "'" ? Character($0) : " " }
    return String(cleaned).split(separator: " ").joined(separator: " ")
}

public func words(_ text: String) -> [String] {
    normalizeSpeech(text).split(separator: " ").map(String.init)
}

/// Détecte le mot d'activation dans une transcription et renvoie ce qui suit.
public struct WakeWordSpotter: Sendable {
    public let keywords: Set<String>

    public init(keywords: Set<String> = ["friday", "fridays", "fraidai", "fraide"]) {
        self.keywords = keywords
    }

    /// nil si absent ; sinon le texte après la première occurrence (éventuellement vide).
    public func commandAfterWakeWord(in text: String) -> String? {
        let w = words(text)
        guard let i = w.firstIndex(where: keywords.contains) else { return nil }
        return w[(i + 1)...].joined(separator: " ")
    }
}

/// Évite qu'un barge-in soit déclenché par la propre voix de Friday captée par le micro.
public enum EchoGuard {
    public static func isLikelyEcho(heard: String, speaking: String, threshold: Double = 0.8) -> Bool {
        let h = words(heard)
        guard !h.isEmpty else { return true }
        let spoken = Set(words(speaking))
        let overlap = h.filter(spoken.contains).count
        return Double(overlap) / Double(h.count) >= threshold
    }
}
