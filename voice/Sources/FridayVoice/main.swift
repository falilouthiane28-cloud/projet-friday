// friday-voice : pipeline vocal natif de Friday.
//   friday-voice            → écoute (protocole JSON Lines sur stdin/stdout)
//   friday-voice --check    → état de la langue, du modèle et des voix, sans micro
//   friday-voice --say "…"  → test du TTS seul
import AVFoundation
import Foundation
import FridayVoiceCore
import Speech

let args = CommandLine.arguments
func option(_ name: String) -> String? {
    args.firstIndex(of: name).flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
}
let language = option("--locale") ?? "fr-FR"

/// Orchestration : applique les effets de VoiceSession (cœur testé) à l'audio réel.
actor Controller {
    private var session = VoiceSession()
    private let speaker: Speaker
    private let started = Date()
    private var finalized = ""
    private var volatile = ""
    private var cutoff = 0.0          // ignore les résultats antérieurs au dernier reset
    private var lastAudioEnd = 0.0
    private var utteranceAt: Date?

    init(speaker: Speaker) { self.speaker = speaker }

    private var now: TimeInterval { Date().timeIntervalSince(started) }

    func result(_ text: String, isFinal: Bool, end: Double) {
        lastAudioEnd = max(lastAudioEnd, end)
        guard end > cutoff else { return }
        if isFinal { finalized += " " + text; volatile = "" } else { volatile = text }
        apply(session.onTranscript(finalized + " " + volatile, now: now))
    }

    func tick() { apply(session.onTick(now: now)) }
    func say(_ text: String) { apply(session.onSay(text, now: now)) }
    func stop() { apply(session.onStop(now: now)) }
    func speechFinished() { apply(session.onSpeechFinished(now: now)) }

    func firstAudio() {
        guard let t = utteranceAt else { return }
        utteranceAt = nil
        IO.emit(OutMessage(type: "metrics", ttfaMs: Int(Date().timeIntervalSince(t) * 1000)))
    }

    private func apply(_ effects: [VoiceEffect]) {
        for effect in effects {
            switch effect {
            case .state(let s): IO.emit(OutMessage(type: "state", state: s.rawValue))
            case .utterance(let t): utteranceAt = Date(); IO.emit(OutMessage(type: "utterance", text: t))
            case .speak(let t): speaker.speak(t)
            case .stopSpeaking: speaker.stop()
            case .bargeIn: IO.emit(OutMessage(type: "barge_in"))
            case .resetTranscript: finalized = ""; volatile = ""; cutoff = lastAudioEnd
            }
        }
    }
}

func runCheck() async {
    let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: language))
    print("langue demandée : \(language)")
    print("transcription sur l'appareil : \(locale.map { "supportée (\($0.identifier))" } ?? "non supportée")")
    if let locale {
        let status = await AssetInventory.status(forModules: [Listener.makeTranscriber(locale)])
        print("modèle : \(status)")
    }
    let voices = AVSpeechSynthesisVoice.speechVoices().filter { $0.language == language }
    print("voix \(language) : \(voices.map { "\($0.name) (q\($0.quality.rawValue))" }.joined(separator: ", "))")
    print("voix choisie : \(Speaker.bestVoice(language: language)?.name ?? "aucune")")
}

func runSay(_ text: String) async throws {
    let engine = AVAudioEngine()
    let speaker = Speaker(engine: engine, language: language)
    let done = AsyncStream<Void>.makeStream()
    speaker.onFinished = { done.continuation.yield() }
    engine.prepare()
    try engine.start()
    speaker.speak(text)
    for await _ in done.stream { break }
}

func runListen() async throws {
    guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: language)) else {
        IO.emit(OutMessage(type: "error", message: "langue non supportée : \(language)"))
        exit(2)
    }
    let engine = AVAudioEngine()
    let listener = Listener(engine: engine, locale: locale)
    let speaker = Speaker(engine: engine, language: language)
    let controller = Controller(speaker: speaker)
    listener.onResult = { text, isFinal, end in Task { await controller.result(text, isFinal: isFinal, end: end) } }
    speaker.onFirstAudio = { Task { await controller.firstAudio() } }
    speaker.onFinished = { Task { await controller.speechFinished() } }

    try await listener.start()
    IO.emit(OutMessage(type: "ready"))
    IO.emit(OutMessage(type: "state", state: VoiceState.idle.rawValue))

    Task {                                          // horloge : fin d'énoncé, timeouts
        while true {
            try? await Task.sleep(for: .milliseconds(50))
            await controller.tick()
        }
    }
    do {
        for try await line in FileHandle.standardInput.bytes.lines {
            switch InMessage.parse(line) {
            case .say(let text): await controller.say(text)
            case .stop: await controller.stop()
            case .shutdown: await listener.stop(); exit(0)
            case nil: IO.log("message ignoré : \(line)")
            }
        }
    } catch {
        IO.log("stdin : \(error.localizedDescription)")
    }
    await listener.stop()                           // stdin fermé : le cœur Python s'est arrêté
}

do {
    if args.contains("--check") { await runCheck() }
    else if let text = option("--say") { try await runSay(text) }
    else { try await runListen() }
} catch {
    IO.emit(OutMessage(type: "error", message: error.localizedDescription))
    exit(1)
}
