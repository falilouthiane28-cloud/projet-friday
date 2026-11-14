import AVFoundation

/// TTS AVSpeechSynthesizer rendu dans le même AVAudioEngine que le micro :
/// la sortie passe par l'unité voice-processing, donc l'annulation d'écho la retire du micro.
public final class Speaker: @unchecked Sendable {
    private let synth = AVSpeechSynthesizer()
    private let player = AVAudioPlayerNode()
    private let format: AVAudioFormat
    private let voice: AVSpeechSynthesisVoice?
    private var converters: [String: AVAudioConverter] = [:]
    private var generation = 0
    private var pending = 0
    private var synthDone = false
    private var active = false                  // une phrase est en cours de synthèse ou de lecture
    private var upcoming: [String] = []         // phrases suivantes d'une réponse en flux
    private let queue = DispatchQueue(label: "friday.speaker")

    public var onFirstAudio: (@Sendable () -> Void)?
    public var onFinished: (@Sendable () -> Void)?

    public init(engine: AVAudioEngine, language: String) {
        format = AVAudioFormat(standardFormatWithSampleRate: 22_050, channels: 1)!
        voice = Speaker.bestVoice(language: language)
        engine.attach(player)
        engine.connect(player, to: engine.mainMixerNode, format: format)
    }

    public static func bestVoice(language: String) -> AVSpeechSynthesisVoice? {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language == language }
            .max { $0.quality.rawValue < $1.quality.rawValue } ?? AVSpeechSynthesisVoice(language: language)
    }

    /// Lit `text` après la phrase en cours (ou tout de suite si Friday ne parle pas).
    public func enqueue(_ text: String) {
        let waiting = queue.sync { () -> Bool in
            guard active else { return false }
            upcoming.append(text)
            return true
        }
        if !waiting { speak(text) }
    }

    public func speak(_ text: String) {
        queue.sync {
            generation += 1
            pending = 0
            synthDone = false
            active = true
        }
        let gen = queue.sync { generation }
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = voice
        var first = true
        if !player.isPlaying { player.play() }
        synth.write(utterance) { [weak self] buffer in
            guard let self, let pcm = buffer as? AVAudioPCMBuffer else { return }
            self.queue.async {
                guard gen == self.generation else { return }
                if pcm.frameLength == 0 {           // fin de la synthèse
                    self.synthDone = true
                    self.finishIfDone()
                    return
                }
                guard let out = self.convert(pcm) else { return }
                if first { first = false; self.onFirstAudio?() }
                self.pending += 1
                self.player.scheduleBuffer(out) { [weak self] in
                    guard let self else { return }
                    self.queue.async {
                        guard gen == self.generation else { return }
                        self.pending -= 1
                        self.finishIfDone()
                    }
                }
            }
        }
    }

    public func stop() {
        queue.sync { generation += 1; upcoming.removeAll(); active = false }
        synth.stopSpeaking(at: .immediate)
        player.stop()
    }

    private func finishIfDone() {
        if synthDone && pending == 0 {
            generation += 1
            if !upcoming.isEmpty {                  // phrase suivante, sans repasser par le repos
                let next = upcoming.removeFirst()
                DispatchQueue.global(qos: .userInitiated).async { self.speak(next) }
                return
            }
            active = false
            onFinished?()
        }
    }

    private func convert(_ buffer: AVAudioPCMBuffer) -> AVAudioPCMBuffer? {
        if buffer.format == format { return buffer }
        let key = buffer.format.description
        let converter = converters[key] ?? AVAudioConverter(from: buffer.format, to: format)
        converters[key] = converter
        guard let converter else { return nil }
        let ratio = format.sampleRate / buffer.format.sampleRate
        let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 1024
        guard let out = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: capacity) else { return nil }
        var supplied = false
        var error: NSError?
        converter.convert(to: out, error: &error) { _, status in
            if supplied { status.pointee = .noDataNow; return nil }
            supplied = true
            status.pointee = .haveData
            return buffer
        }
        return error == nil ? out : nil
    }
}
