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

        guard let monoIn = MicConverter.monoFormat(for: inFormat),
              let target = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber], considering: monoIn),
              let converter = MicConverter(input: inFormat, target: target) else {
            throw NSError(domain: "friday-voice", code: 1, userInfo: [NSLocalizedDescriptionKey: "format audio incompatible"])
        }
        try await analyzer.prepareToAnalyze(in: target)
        let debug = ProcessInfo.processInfo.environment["FRIDAY_DEBUG_AUDIO"] == "1"
        if debug { VoiceLog.log("formats : micro \(inFormat) → analyseur \(target)") }
        let stats = ConversionStats()

        let (stream, continuation) = AsyncStream<AnalyzerInput>.makeStream()
        self.continuation = continuation

        input.installTap(onBus: 0, bufferSize: 1024, format: inFormat) { [weak self] buffer, _ in
            if let level = self?.onLevel { level(Listener.rms(buffer)) }
            let (out, error) = converter.convert(buffer)
            if let out { continuation.yield(AnalyzerInput(buffer: out)) }
            if debug, let line = stats.record(inFrames: buffer.frameLength, outFrames: out?.frameLength ?? 0, error: error) {
                VoiceLog.log(line)
            }
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

    /// Diagnostic : tampons convertis et erreurs, résumé toutes les 5 s.
    final class ConversionStats: @unchecked Sendable {
        private var buffers = 0, empty = 0, errors = 0, inFrames = 0, outFrames = 0
        private var lastError = ""
        private var since = Date()
        func record(inFrames i: AVAudioFrameCount, outFrames o: AVAudioFrameCount, error: NSError?) -> String? {
            buffers += 1; inFrames += Int(i); outFrames += Int(o)
            if o == 0 { empty += 1 }
            if let error { errors += 1; lastError = error.localizedDescription }
            guard Date().timeIntervalSince(since) >= 5 else { return nil }
            defer { buffers = 0; empty = 0; errors = 0; inFrames = 0; outFrames = 0; since = Date() }
            return "conversion : \(buffers) tampons, \(inFrames) → \(outFrames) trames, \(empty) vides, \(errors) erreurs \(lastError)"
        }
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
