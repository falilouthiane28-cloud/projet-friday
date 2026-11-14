import AVFoundation
import Foundation
import FridayVoiceCore
import Speech

/// Orchestration : applique les effets de VoiceSession (cœur testé) à l'audio réel.
/// Les événements sortent sous forme d'`OutMessage` (protocole voix) vers `emit`.
public actor VoiceController {
    private var session = VoiceSession()
    private let speaker: Speaker
    private let emit: @Sendable (OutMessage) -> Void
    private let started = Date()
    private var finalized = ""
    private var volatile = ""
    private var cutoff = 0.0          // ignore les résultats antérieurs au dernier reset
    private var lastAudioEnd = 0.0
    private var utteranceAt: Date?

    public init(speaker: Speaker, emit: @escaping @Sendable (OutMessage) -> Void) {
        self.speaker = speaker
        self.emit = emit
    }

    private var now: TimeInterval { Date().timeIntervalSince(started) }

    public func result(_ text: String, isFinal: Bool, end: Double) {
        lastAudioEnd = max(lastAudioEnd, end)
        guard end > cutoff else { return }
        if isFinal { finalized += " " + text; volatile = "" } else { volatile = text }
        apply(session.onTranscript(finalized + " " + volatile, now: now))
    }

    public func tick() { apply(session.onTick(now: now)) }
    public func say(_ text: String) { apply(session.onSay(text, now: now)) }
    public func sayMore(_ text: String) { apply(session.onSayMore(text, now: now)) }
    public func listen() { apply(session.onListen(now: now)) }
    public func stop() { apply(session.onStop(now: now)) }
    public func speechFinished() { apply(session.onSpeechFinished(now: now)) }

    public func firstAudio() {
        guard let t = utteranceAt else { return }
        utteranceAt = nil
        emit(OutMessage(type: "metrics", ttfaMs: Int(Date().timeIntervalSince(t) * 1000)))
    }

    private func apply(_ effects: [VoiceEffect]) {
        for effect in effects {
            switch effect {
            case .state(let s): emit(OutMessage(type: "state", state: s.rawValue))
            case .utterance(let t): utteranceAt = Date(); emit(OutMessage(type: "utterance", text: t))
            case .speak(let t): speaker.speak(t)
            case .enqueueSpeech(let t): speaker.enqueue(t)
            case .stopSpeaking: speaker.stop()
            case .bargeIn: emit(OutMessage(type: "barge_in"))
            case .resetTranscript: finalized = ""; volatile = ""; cutoff = lastAudioEnd
            }
        }
    }
}

/// Pipeline complet : micro + STT + TTS dans un seul AVAudioEngine, horloge de 50 ms.
public final class VoicePipeline: @unchecked Sendable {
    public let controller: VoiceController
    private let listener: Listener
    private var clock: Task<Void, Never>?

    /// nil si la langue n'est pas supportée par la transcription sur l'appareil.
    public init?(language: String, emit: @escaping @Sendable (OutMessage) -> Void,
                 level: (@Sendable (Float) -> Void)? = nil,
                 transcript: (@Sendable (String, Bool) -> Void)? = nil) async {
        guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: language)) else { return nil }
        let engine = AVAudioEngine()
        listener = Listener(engine: engine, locale: locale)
        let speaker = Speaker(engine: engine, language: language)
        let controller = VoiceController(speaker: speaker, emit: emit)
        self.controller = controller
        listener.onResult = { text, isFinal, end in
            transcript?(text, isFinal)
            Task { await controller.result(text, isFinal: isFinal, end: end) }
        }
        listener.onLevel = level
        speaker.onFirstAudio = { Task { await controller.firstAudio() } }
        speaker.onFinished = { Task { await controller.speechFinished() } }
    }

    public func start() async throws {
        try await listener.start()
        let controller = self.controller
        clock = Task {                                  // fin d'énoncé, timeouts
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(50))
                await controller.tick()
            }
        }
    }

    public func stop() async {
        clock?.cancel()
        await listener.stop()
    }
}
