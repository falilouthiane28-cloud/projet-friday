import AVFoundation

/// Micro → format de l'analyseur. Avec l'annulation d'écho, le micro donne plusieurs canaux
/// (3 sur ce Mac) : seul le canal 0 porte la voix traitée. On l'extrait en mono avant le
/// rééchantillonnage, sinon SpeechAnalyzer ne renvoie aucun résultat.
public final class MicConverter: @unchecked Sendable {
    public let mono: AVAudioFormat
    private let converter: AVAudioConverter
    private let target: AVAudioFormat

    public init?(input: AVAudioFormat, target: AVAudioFormat) {
        guard let mono = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: input.sampleRate, channels: 1, interleaved: false),
              let converter = AVAudioConverter(from: mono, to: target) else { return nil }
        self.mono = mono
        self.converter = converter
        self.target = target
    }

    /// Format mono à proposer à `SpeechAnalyzer.bestAvailableAudioFormat`.
    public static func monoFormat(for input: AVAudioFormat) -> AVAudioFormat? {
        AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: input.sampleRate, channels: 1, interleaved: false)
    }

    public func convert(_ buffer: AVAudioPCMBuffer) -> (AVAudioPCMBuffer?, NSError?) {
        guard let src = buffer.floatChannelData,
              let monoBuf = AVAudioPCMBuffer(pcmFormat: mono, frameCapacity: buffer.frameLength) else { return (nil, nil) }
        monoBuf.frameLength = buffer.frameLength
        monoBuf.floatChannelData![0].update(from: src[0], count: Int(buffer.frameLength))
        let capacity = AVAudioFrameCount(Double(buffer.frameLength) * target.sampleRate / mono.sampleRate) + 512
        guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { return (nil, nil) }
        var supplied = false
        var error: NSError?
        converter.convert(to: out, error: &error) { _, status in
            if supplied { status.pointee = .noDataNow; return nil }
            supplied = true
            status.pointee = .haveData
            return monoBuf
        }
        return (error == nil && out.frameLength > 0 ? out : nil, error)
    }
}
