// friday-voice : pipeline vocal natif de Friday, piloté par Python (`python -m friday --voice`).
//   friday-voice            → écoute (protocole JSON Lines sur stdin/stdout)
//   friday-voice --check    → état de la langue, du modèle et des voix, sans micro
//   friday-voice --say "…"  → test du TTS seul
import AVFoundation
import Foundation
import FridayVoiceCore
import FridayVoiceKit
import Speech

let args = CommandLine.arguments
func option(_ name: String) -> String? {
    args.firstIndex(of: name).flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
}
let language = option("--locale") ?? "fr-FR"

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
    guard let pipeline = await VoicePipeline(language: language, emit: IO.emit) else {
        IO.emit(OutMessage(type: "error", message: "langue non supportée : \(language)"))
        exit(2)
    }
    try await pipeline.start()
    IO.emit(OutMessage(type: "ready"))
    IO.emit(OutMessage(type: "state", state: VoiceState.idle.rawValue))
    let controller = pipeline.controller
    do {
        for try await line in FileHandle.standardInput.bytes.lines {
            switch InMessage.parse(line) {
            case .say(let text): await controller.say(text)
            case .stop: await controller.stop()
            case .shutdown: await pipeline.stop(); exit(0)
            case nil: IO.log("message ignoré : \(line)")
            }
        }
    } catch {
        IO.log("stdin : \(error.localizedDescription)")
    }
    await pipeline.stop()                           // stdin fermé : le cœur Python s'est arrêté
}

do {
    if args.contains("--check") { await runCheck() }
    else if let text = option("--say") { try await runSay(text) }
    else { try await runListen() }
} catch {
    IO.emit(OutMessage(type: "error", message: error.localizedDescription))
    exit(1)
}
