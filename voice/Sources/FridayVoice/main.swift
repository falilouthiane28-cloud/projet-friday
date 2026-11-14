// friday-voice : pipeline vocal natif de Friday, piloté par Python (`python -m friday --voice`).
//   friday-voice            → écoute (protocole JSON Lines sur stdin/stdout)
//   friday-voice --check    → état de la langue, du modèle et des voix, sans micro
//   friday-voice --say "…"  → test du TTS seul
//   friday-voice --transcribe <fichier>  → test de la transcription sur un fichier audio
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

func rms16(_ b: AVAudioPCMBuffer) -> Float {
    guard let d = b.int16ChannelData, b.frameLength > 0 else { return -1 }
    var sum: Float = 0
    for i in 0..<Int(b.frameLength) { let v = Float(d[0][i]) / 32768; sum += v * v }
    return (sum / Float(b.frameLength)).squareRoot()
}

/// Ancienne méthode : conversion directe 3 canaux → mono 16 kHz.
func legacyRMS(_ mic: AVAudioPCMBuffer, _ target: AVAudioFormat) -> Float {
    guard let conv = AVAudioConverter(from: mic.format, to: target),
          let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: 1024) else { return -1 }
    var supplied = false
    var error: NSError?
    conv.convert(to: out, error: &error) { _, status in
        if supplied { status.pointee = .noDataNow; return nil }
        supplied = true; status.pointee = .haveData; return mic
    }
    return rms16(out)
}

func runTranscribe(_ path: String, channels: AVAudioChannelCount) async throws {
    guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: language)) else { print("langue non supportée"); return }
    let transcriber = Listener.makeTranscriber(locale)
    try await Listener.ensureModel(transcriber)
    let file = try AVAudioFile(forReading: URL(fileURLWithPath: path))
    // Simule le micro : 48 kHz, `channels` canaux non entrelacés (le voice processing en donne 3).
    let layout = AVAudioChannelLayout(layoutTag: kAudioChannelLayoutTag_DiscreteInOrder | UInt32(channels))!
    let micFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 48_000, interleaved: false, channelLayout: layout)
    let analyzer = SpeechAnalyzer(modules: [transcriber])
    guard let monoIn = MicConverter.monoFormat(for: micFormat),
          let target = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber], considering: monoIn),
          let converter = MicConverter(input: micFormat, target: target) else { print("format incompatible"); return }
    try await analyzer.prepareToAnalyze(in: target)
    let (stream, continuation) = AsyncStream<AnalyzerInput>.makeStream()
    let reader = Task {
        for try await r in transcriber.results { print(r.isFinal ? "définitif :" : "volatile :", String(r.text.characters)) }
    }
    try await analyzer.start(inputSequence: stream)
    // fichier → format micro (copie du canal 0 sur tous les canaux) → format analyseur, par tampons de 1024
    // Le fichier doit déjà être en 48 kHz Float32 mono (say --data-format=LEF32@48000).
    let mono = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length))!
    try file.read(into: mono)
    print("fichier : \(file.processingFormat), \(mono.frameLength) trames")
    var offset: AVAudioFrameCount = 0
    while offset < mono.frameLength {
        let n = min(1024, mono.frameLength - offset)
        let mic = AVAudioPCMBuffer(pcmFormat: micFormat, frameCapacity: n)!
        mic.frameLength = n
        for c in 0..<Int(channels) { for i in 0..<Int(n) { mic.floatChannelData![c][i] = c == 0 ? mono.floatChannelData![0][Int(offset) + i] : 0 } }
        if let out = converter.convert(mic).0 {
            if offset == 48_128 { print("rms sortie (canal 0) :", rms16(out), "| ancienne conversion directe :", legacyRMS(mic, target)) }
            continuation.yield(AnalyzerInput(buffer: out))
        }
        offset += n
        try await Task.sleep(for: .milliseconds(5))
    }
    continuation.finish()
    try await analyzer.finalizeAndFinishThroughEndOfInput()
    _ = try await reader.value
    print("fin")
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
    else if let path = option("--transcribe") { try await runTranscribe(path, channels: AVAudioChannelCount(option("--channels") ?? "1") ?? 1) }
    else { try await runListen() }
} catch {
    IO.emit(OutMessage(type: "error", message: error.localizedDescription))
    exit(1)
}
