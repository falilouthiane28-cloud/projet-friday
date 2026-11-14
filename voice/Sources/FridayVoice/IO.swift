import Foundation
import FridayVoiceCore

/// stdout = protocole JSON Lines uniquement ; les journaux vont sur stderr.
enum IO {
    private static let lock = NSLock()

    static func emit(_ message: OutMessage) {
        lock.lock(); defer { lock.unlock() }
        FileHandle.standardOutput.write(Data((message.jsonLine() + "\n").utf8))
    }

    static func log(_ text: String) {
        FileHandle.standardError.write(Data("[friday-voice] \(text)\n".utf8))
    }
}
