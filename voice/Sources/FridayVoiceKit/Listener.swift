import AVFoundation
import CoreMedia
import Speech

/// Journal du pipeline (stderr par défaut ; l'app peut le rediriger).
public enum VoiceLog {
    nonisolated(unsafe) public static var log: @Sendable (String) -> Void = { text in
        FileHandle.standardError.write(Data("[friday-voice] \(text)\n".utf8))
    }
}

/// Micro (annulation d'écho Apple) → SpeechAnalyzer + SpeechTranscriber, sur l'appareil.
public final class Listener: @unchecked Sendable {
    public let engine: AVAudioEngine
    private let locale: Locale
    private var analyzer: SpeechAnalyzer?
    private var continuation: AsyncStream<AnalyzerInput>.Continuation?

    /// texte, définitif ?, fin du segment audio (secondes)
    public var onResult: (@Sendable (String, Bool, Double) -> Void)?
    /// RMS linéaire de chaque tampon micro (niveau pour l'avatar).
    public var onLevel: (@Sendable (Float) -> Void)?

    public init(engine: AVAudioEngine, locale: Locale) {
        self.engine = engine
        self.locale = locale
    }

    public static func makeTranscriber(_ locale: Locale) -> SpeechTranscriber {
        SpeechTranscriber(locale: locale, transcriptionOptions: [],
                          reportingOptions: [.volatileResults, .fastResults],
                          attributeOptions: [.audioTimeRange])
    }

    /// Installe le modèle de la langue si besoin (asset système Apple).
    public static func ensureModel(_ transcriber: SpeechTranscriber) async throws {
        if await AssetInventory.status(forModules: [transcriber]) == .installed { return }
        if let request = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
            VoiceLog.log("téléchargement du modèle de transcription…")
            try await request.downloadAndInstall()
        }
    }

    public func start() async throws {
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

        input.installTap(onBus: 0, bufferSize: 1024, format: inFormat) { [weak self] buffer, _ in
            if let level = self?.onLevel { level(Listener.rms(buffer)) }
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
                VoiceLog.log("transcription interrompue : \(error.localizedDescription)")
            }
        }
        try await analyzer.start(inputSequence: stream)
        engine.prepare()
        try engine.start()
    }

    static func rms(_ buffer: AVAudioPCMBuffer) -> Float {
        guard let data = buffer.floatChannelData, buffer.frameLength > 0 else { return 0 }
        let n = Int(buffer.frameLength)
        var sum: Float = 0
        for i in 0..<n { sum += data[0][i] * data[0][i] }
        return (sum / Float(n)).squareRoot()
    }

    public func stop() async {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        continuation?.finish()
        await analyzer?.cancelAndFinishNow()
    }
}
