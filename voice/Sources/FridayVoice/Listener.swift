import AVFoundation
import CoreMedia
import Speech

/// Micro (annulation d'écho Apple) → SpeechAnalyzer + SpeechTranscriber, sur l'appareil.
final class Listener: @unchecked Sendable {
    let engine: AVAudioEngine
    private let locale: Locale
    private var analyzer: SpeechAnalyzer?
    private var continuation: AsyncStream<AnalyzerInput>.Continuation?

    /// texte, définitif ?, fin du segment audio (secondes)
    var onResult: (@Sendable (String, Bool, Double) -> Void)?

    init(engine: AVAudioEngine, locale: Locale) {
        self.engine = engine
        self.locale = locale
    }

    static func makeTranscriber(_ locale: Locale) -> SpeechTranscriber {
        SpeechTranscriber(locale: locale, transcriptionOptions: [],
                          reportingOptions: [.volatileResults, .fastResults],
                          attributeOptions: [.audioTimeRange])
    }

    /// Installe le modèle de la langue si besoin (asset système Apple).
    static func ensureModel(_ transcriber: SpeechTranscriber) async throws {
        if await AssetInventory.status(forModules: [transcriber]) == .installed { return }
        if let request = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
            IO.log("téléchargement du modèle de transcription…")
            try await request.downloadAndInstall()
        }
    }

    func start() async throws {
        let input = engine.inputNode
        try input.setVoiceProcessingEnabled(true)            // annulation d'écho + réduction de bruit
        let inFormat = input.outputFormat(forBus: 0)

        let transcriber = Listener.makeTranscriber(locale)
        try await Listener.ensureModel(transcriber)
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        self.analyzer = analyzer
        let context = AnalysisContext()
        context.contextualStrings[.general] = ["Friday", "Hey Friday"]
        try await analyzer.setContext(context)

        guard let target = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber], considering: inFormat),
              let converter = AVAudioConverter(from: inFormat, to: target) else {
            throw NSError(domain: "friday-voice", code: 1, userInfo: [NSLocalizedDescriptionKey: "format audio incompatible"])
        }
        try await analyzer.prepareToAnalyze(in: target)

        let (stream, continuation) = AsyncStream<AnalyzerInput>.makeStream()
        self.continuation = continuation

        input.installTap(onBus: 0, bufferSize: 1024, format: inFormat) { buffer, _ in
            let ratio = target.sampleRate / inFormat.sampleRate
            let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 512
            guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { return }
            var supplied = false
            var error: NSError?
            converter.convert(to: out, error: &error) { _, status in
                if supplied { status.pointee = .noDataNow; return nil }
                supplied = true
                status.pointee = .haveData
                return buffer
            }
            if error == nil, out.frameLength > 0 { continuation.yield(AnalyzerInput(buffer: out)) }
        }

        Task { [weak self] in
            do {
                for try await result in transcriber.results {
                    let end = CMTimeGetSeconds(CMTimeRangeGetEnd(result.range))
                    self?.onResult?(String(result.text.characters), result.isFinal, end.isFinite ? end : 0)
                }
            } catch {
                IO.log("transcription interrompue : \(error.localizedDescription)")
            }
        }
        try await analyzer.start(inputSequence: stream)
        engine.prepare()
        try engine.start()
    }

    func stop() async {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        continuation?.finish()
        await analyzer?.cancelAndFinishNow()
    }
}
