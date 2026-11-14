import Foundation

public enum VoiceState: String, Codable, Sendable {
    case idle, listening, processing, speaking
}

/// Effets que l'exécutable doit appliquer (le cœur ne touche jamais à l'audio).
public enum VoiceEffect: Equatable, Sendable {
    case state(VoiceState)
    case utterance(String)
    case speak(String)
    case stopSpeaking
    case bargeIn
    case resetTranscript
}

public struct VoiceTimings: Sendable {
    public var endOfSpeech: TimeInterval = 0.7      // texte stable depuis ce délai → fin d'énoncé
    public var listenTimeout: TimeInterval = 6      // rien dit après le wake word → retour au repos
    public var processingTimeout: TimeInterval = 60  // Claude Code peut prendre plusieurs secondes
    public var idleResetAfter: TimeInterval = 2     // vide le tampon de transcription au repos
    public var bargeInMinWords = 2
    public init() {}
}

/// Machine à états Idle → Listening → Processing → Speaking → Idle, avec barge-in.
///
/// Entrée : la transcription courante (tout le texte entendu depuis le dernier
/// `resetTranscript`) et l'horloge. Sortie : une liste d'effets.
public struct VoiceSession: Sendable {
    public private(set) var state: VoiceState = .idle
    public private(set) var command = ""
    public let timings: VoiceTimings
    let spotter: WakeWordSpotter

    private var stateSince: TimeInterval = 0
    private var lastChange: TimeInterval = 0
    private var lastText = ""
    private var speakingText = ""

    public init(timings: VoiceTimings = VoiceTimings(), spotter: WakeWordSpotter = WakeWordSpotter()) {
        self.timings = timings
        self.spotter = spotter
    }

    private mutating func enter(_ s: VoiceState, at now: TimeInterval) -> VoiceEffect {
        state = s
        stateSince = now
        lastChange = now
        return .state(s)
    }

    public mutating func onTranscript(_ text: String, now: TimeInterval) -> [VoiceEffect] {
        if text != lastText { lastText = text; lastChange = now }
        switch state {
        case .idle:
            guard let rest = spotter.commandAfterWakeWord(in: text) else { return [] }
            command = rest
            return [enter(.listening, at: now)]
        case .listening:
            command = spotter.commandAfterWakeWord(in: text) ?? normalizeSpeech(text)
            return []
        case .processing:
            return []
        case .speaking:
            let heard = words(text)
            guard heard.count >= timings.bargeInMinWords,
                  !EchoGuard.isLikelyEcho(heard: text, speaking: speakingText) else { return [] }
            command = spotter.commandAfterWakeWord(in: text) ?? normalizeSpeech(text)
            return [.stopSpeaking, .bargeIn, enter(.listening, at: now)]
        }
    }

    public mutating func onTick(now: TimeInterval) -> [VoiceEffect] {
        switch state {
        case .idle:
            if !lastText.isEmpty, now - lastChange >= timings.idleResetAfter { return reset() }
        case .listening:
            if !command.isEmpty, now - lastChange >= timings.endOfSpeech {
                let utterance = command
                return [.utterance(utterance), enter(.processing, at: now)] + reset()
            }
            if command.isEmpty, now - stateSince >= timings.listenTimeout {
                return [enter(.idle, at: now)] + reset()
            }
        case .processing:
            if now - stateSince >= timings.processingTimeout { return [enter(.idle, at: now)] + reset() }
        case .speaking:
            break
        }
        return []
    }

    /// Réponse du cerveau (ou message proactif).
    public mutating func onSay(_ text: String, now: TimeInterval) -> [VoiceEffect] {
        speakingText = text
        let stop: [VoiceEffect] = state == .speaking ? [.stopSpeaking] : []
        return stop + [enter(.speaking, at: now), .speak(text)] + reset()
    }

    public mutating func onSpeechFinished(now: TimeInterval) -> [VoiceEffect] {
        guard state == .speaking else { return [] }
        speakingText = ""
        return [enter(.idle, at: now)] + reset()
    }

    /// Écoute demandée sans mot d'activation (bouton micro, raccourci global). Coupe la parole si besoin.
    public mutating func onListen(now: TimeInterval) -> [VoiceEffect] {
        guard state != .listening else { return [] }
        let stop: [VoiceEffect] = state == .speaking ? [.stopSpeaking] : []
        speakingText = ""
        return stop + [enter(.listening, at: now)] + reset()
    }

    public mutating func onStop(now: TimeInterval) -> [VoiceEffect] {
        let stop: [VoiceEffect] = state == .speaking ? [.stopSpeaking] : []
        return stop + [enter(.idle, at: now)] + reset()
    }

    private mutating func reset() -> [VoiceEffect] {
        command = ""
        lastText = ""
        return [.resetTranscript]
    }
}
