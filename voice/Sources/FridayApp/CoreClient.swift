import Foundation
import FridayVoiceCore

/// Cœur Python (`python -m friday --serve`) en sous-processus, JSON Lines sur stdin/stdout.
final class CoreClient: @unchecked Sendable {
    private let process = Process()
    private let input = Pipe()
    private let output = Pipe()
    private let lock = NSLock()
    private var nextID = 1
    var onEvent: (@Sendable (CoreEvent) -> Void)?
    var onExit: (@Sendable (Int32) -> Void)?

    /// Racine du dépôt : `FRIDAY_ROOT`, sinon en remontant depuis l'exécutable (voice/.build/…/friday-app).
    static func repoRoot() -> URL? {
        if let env = ProcessInfo.processInfo.environment["FRIDAY_ROOT"] { return URL(fileURLWithPath: env) }
        let exe = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath().deletingLastPathComponent()
        return findRepoRoot(from: exe) { FileManager.default.fileExists(atPath: $0.path) }
    }

    init?(root: URL) {
        let python = root.appendingPathComponent(".venv/bin/python")
        guard FileManager.default.isExecutableFile(atPath: python.path) else { return nil }
        process.executableURL = python
        process.arguments = ["-m", "friday", "--serve"]
        process.currentDirectoryURL = root
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = root.appendingPathComponent("src").path
        env["PYTHONUNBUFFERED"] = "1"
        process.environment = env
        process.standardInput = input
        process.standardOutput = output
        process.standardError = FileHandle.standardError       // journaux structlog
    }

    func start() throws {
        process.terminationHandler = { [weak self] p in self?.onExit?(p.terminationStatus) }
        try process.run()
        let handle = output.fileHandleForReading
        Task.detached { [weak self] in
            do {
                for try await line in handle.bytes.lines {
                    guard let event = CoreEvent.parse(line) else { continue }
                    self?.onEvent?(event)
                }
            } catch {}
        }
    }

    /// Envoie une question ; retourne son identifiant (repris dans la réponse).
    @discardableResult
    func ask(_ text: String, source: String) -> Int {
        lock.lock()
        let id = nextID
        nextID += 1
        lock.unlock()
        send(.ask(id: id, text: text, source: source))
        return id
    }

    func send(_ request: CoreRequest) {
        guard process.isRunning else { return }
        lock.lock(); defer { lock.unlock() }
        try? input.fileHandleForWriting.write(contentsOf: Data((request.jsonLine() + "\n").utf8))
    }

    func stop() {
        send(.shutdown)
        try? input.fileHandleForWriting.close()
    }
}
