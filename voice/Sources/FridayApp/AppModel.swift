import FridayUICore
import FridayVoiceCore
import FridayVoiceKit
import AppKit
import Foundation
import Observation

struct ChatMessage: Identifiable, Equatable {
    let id = UUID()
    let fromFriday: Bool
    var text: String
    let date = Date()
}

/// Diagnostic (`FRIDAY_DEBUG_AUDIO=1`) : texte entendu par la transcription, sur stderr.
@Sendable func traceTranscript(_ text: String, _ final: Bool) {
    FileHandle.standardError.write(Data("[friday-app] transcription\(final ? " (définitive)" : "") : « \(text) »\n".utf8))
}

/// Dernier niveau micro, écrit par le thread audio, lu par le minuteur de l'interface.
private final class LevelBox: @unchecked Sendable {
    private let lock = NSLock()
    private var rms: Float = 0
    func set(_ v: Float) { lock.lock(); rms = v; lock.unlock() }
    func get() -> Float { lock.lock(); defer { lock.unlock() }; return rms }
}

/// État partagé par la barre de menus, le dashboard et l'overlay.
/// Relie le pipeline vocal (même processus) et le cœur Python (sous-processus) à l'avatar et au fil.
@MainActor @Observable
final class AppModel {
    static let shared = AppModel()
    var overlayExpanded = false
    private(set) var avatar: AvatarState = .neutral
    private(set) var voiceState: VoiceState = .idle
    private(set) var voiceAvailable = false
    var audioLevel: Double = 0
    var draft = ""
    var messages: [ChatMessage] = [
        ChatMessage(fromFriday: true, text: "Bonjour Thaïne. Je suis prête."),
    ]
    let stats = SystemStats()

    var statusLabel: String { VoiceLink.label(voice: voiceState, avatar: avatar) }

    /// Cerveau annoncé par le cœur (« Claude Code », « local ») ; nil tant que le cœur n'est pas prêt.
    private(set) var brainName: String?
    private(set) var claudeBinary: String?
    private(set) var needsLogin = false
    /// Une réponse est attendue (saisie texte ou énoncé vocal).
    var isThinking: Bool { !pendingText.subtracting(streaming.keys).isEmpty || voiceState == .processing }
    /// Lire aussi les réponses aux messages tapés (par défaut : seulement en mode vocal).
    var speakAllReplies = UserDefaults.standard.bool(forKey: "speakAllReplies") {
        didSet { UserDefaults.standard.set(speakAllReplies, forKey: "speakAllReplies") }
    }
    /// Ouverture des fenêtres SwiftUI, capturée depuis la scène de barre de menus.
    var openWindowAction: ((String) -> Void)?
    var openSettingsAction: (() -> Void)?

    private var machine = AvatarMachine()
    private let started = Date()
    private var now: TimeInterval { Date().timeIntervalSince(started) }
    private var timer: Timer?
    private let level = LevelBox()
    private var core: CoreClient?
    private var voice: VoicePipeline?
    private var pendingText: Set<Int> = []        // questions tapées en attente de réponse
    private var streaming: [Int: UUID] = [:]      // réponse en flux → message du fil en cours de remplissage

    /// Les phrases d'une réponse doivent atteindre la voix dans l'ordre : chaque envoi attend le précédent.
    private var lastVoiceTask: Task<Void, Never>?
    private func inOrder(_ op: @escaping @Sendable () async -> Void) {
        let previous = lastVoiceTask
        lastVoiceTask = Task { await previous?.value; await op() }
    }

    /// Friday lit-elle la réponse à cette question ? (vocale, ou option « tout lire »)
    private func speaks(_ id: Int) -> Bool {
        VoiceLink.shouldSpeak(askedByVoice: !pendingText.contains(id), speakAll: speakAllReplies, voiceAvailable: voice != nil)
    }

    init() {
        timer = Timer.scheduledTimer(withTimeInterval: 1 / 20, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.apply(self.machine.tick(now: self.now))
                if self.debugAudio { self.traceAudio() }
                let target = self.voiceState == .listening ? AudioLevel.normalized(rms: self.level.get()) : 0
                let next = AudioLevel.smoothed(previous: self.audioLevel, target: target)
                if abs(next - self.audioLevel) > 0.01 || (next == 0) != (self.audioLevel == 0) { self.audioLevel = next }
            }
        }
    }

    /// `FRIDAY_DEBUG_AUDIO=1` : journalise le niveau micro maximal toutes les 3 s (diagnostic).
    private let debugAudio = ProcessInfo.processInfo.environment["FRIDAY_DEBUG_AUDIO"] == "1"
    private var peakRMS: Float = 0
    private var lastTrace = Date()

    private func traceAudio() {
        peakRMS = max(peakRMS, level.get())
        guard Date().timeIntervalSince(lastTrace) >= 3 else { return }
        let db = peakRMS > 0 ? 20 * log10(Double(peakRMS)) : -999
        log(String(format: "micro : crête %.0f dB (voix %@)", db, voiceAvailable ? "active" : "inactive"))
        peakRMS = 0
        lastTrace = Date()
    }

    // MARK: - Démarrage

    /// Lance le cœur Python puis le pipeline vocal. Chacun peut manquer sans bloquer l'autre.
    func start() {
        startCore()
        Task { await startVoice() }
    }

    func shutdown() {
        core?.stop()
        if let voice { Task { await voice.stop() } }
    }

    func startCore() {
        guard let root = CoreClient.repoRoot(), let client = CoreClient(root: root) else {
            note("Cœur Python introuvable (.venv/bin/python). Définissez FRIDAY_ROOT ou lancez depuis le dépôt.")
            return
        }
        client.onEvent = { event in Task { @MainActor in AppModel.shared.handle(event) } }
        client.onExit = { code in Task { @MainActor in AppModel.shared.coreExited(code) } }
        do {
            try client.start()
            core = client
        } catch {
            note("Cœur Python non lancé : \(error.localizedDescription)")
        }
    }

    private func startVoice() async {
        let box = level
        // Diagnostic seulement : le texte entendu n'est jamais journalisé hors FRIDAY_DEBUG_AUDIO.
        let trace: (@Sendable (String, Bool) -> Void)? = debugAudio ? traceTranscript : nil
        let pipeline = await VoicePipeline(
            language: "fr-FR",
            emit: { msg in Task { @MainActor in AppModel.shared.handle(msg) } },
            level: { box.set($0) },
            transcript: trace
        )
        guard let pipeline else { note("Transcription française indisponible sur ce Mac."); return }
        do {
            try await pipeline.start()
            voice = pipeline
            voiceAvailable = true
            log("voix prête (micro + transcription fr_FR)")
        } catch {
            note("Micro indisponible : \(error.localizedDescription). La saisie texte reste active.")
        }
    }

    // MARK: - Événements

    /// Pipeline vocal → interface et cœur.
    func handle(_ msg: OutMessage) {
        log(Self.describe(msg))
        switch msg.type {
        case "state":
            guard let s = msg.state.flatMap(VoiceState.init(rawValue:)) else { return }
            voiceState = s
            if let a = VoiceLink.avatar(for: s) { show(a) } else if pendingText.isEmpty { show(.neutral) }
        case "utterance":
            guard let text = msg.text, !text.isEmpty else { return }
            messages.append(ChatMessage(fromFriday: false, text: text))
            if let core { core.ask(text, source: "voice") } else { answerLocally() }
        case "metrics":
            if let ms = msg.ttfaMs { core?.send(.metrics(ttfaMs: ms)) }
        case "error":
            note(msg.message ?? "Erreur du pipeline vocal.")
        default:
            break
        }
    }

    /// Cœur Python → fil de conversation et voix.
    func handle(_ event: CoreEvent) {
        switch event {
        case .ready(let name, let brain, let binary):
            brainName = brain
            claudeBinary = binary
            log("cœur prêt (\(name), cerveau : \(brain))")
        case .chunk(let id, let text):
            // Réponse en flux : le fil se remplit phrase par phrase, la voix lit dès la première.
            if let mid = streaming[id], let i = messages.firstIndex(where: { $0.id == mid }) {
                messages[i].text += " " + text
            } else {
                let m = ChatMessage(fromFriday: true, text: text)
                streaming[id] = m.id
                messages.append(m)
            }
            if let voice, speaks(id) { inOrder { await voice.controller.sayMore(text) } }
        case .reply(let id, let text, _, _, let loginRequired, let streamed):
            let spoken = speaks(id)
            pendingText.remove(id)
            needsLogin = loginRequired
            if let mid = streaming.removeValue(forKey: id), let i = messages.firstIndex(where: { $0.id == mid }) {
                messages[i].text = text                      // texte final exact (markdown compris)
            } else {
                messages.append(ChatMessage(fromFriday: true, text: text))
            }
            if let voice, spoken, !streamed {
                inOrder { await voice.controller.say(text) }
            } else if voice == nil || !spoken {
                show(loginRequired ? .confused : .happy)
            }
        case .error(let message):
            pendingText.removeAll()
            note("Le cœur a signalé une erreur : \(message)")
            show(.confused)
        }
    }

    private func coreExited(_ code: Int32) {
        core = nil
        brainName = nil
        pendingText.removeAll()
        note("Le cœur Python s'est arrêté (code \(code)).")
        show(.error)
    }

    // MARK: - Actions

    func show(_ state: AvatarState) {
        if state == .neutral { apply(machine.clear(now: now)) } else { apply(machine.request(state, now: now)) }
    }

    func toggleListening() {
        guard let voice else { note("Le micro n'est pas disponible."); return }
        let listening = voiceState == .listening
        Task { listening ? await voice.controller.stop() : await voice.controller.listen() }
    }

    /// Raccourci global (⌃⌥Espace par défaut).
    func hotkey() {
        log("raccourci global pressé")
        switch VoiceLink.hotkey(expanded: overlayExpanded, voice: voiceState) {
        case .expandAndListen:
            OverlayController.shared.show(model: self)
            OverlayController.shared.setExpanded(true)
            if voiceState != .listening { toggleListening() }
        case .listen, .stopListening:
            toggleListening()
        }
    }

    /// Nouvelle conversation : vide le fil et oublie la session Claude Code.
    func newConversation() {
        messages = [ChatMessage(fromFriday: true, text: "Nouvelle conversation. Je vous écoute.")]
        pendingText.removeAll()
        streaming.removeAll()
        core?.send(.reset)
        if let voice { Task { await voice.controller.stop() } }
        show(.neutral)
    }

    /// Ouvre Terminal sur Claude Code pour la connexion (/login), une seule fois.
    func connectClaude() {
        guard let binary = claudeBinary else { note("Claude Code est introuvable sur ce Mac."); return }
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("Friday")
        let script = dir.appendingPathComponent("connecter-claude.command")
        let quoted = "'" + binary.replacingOccurrences(of: "'", with: "'\\''") + "'"
        let body = """
        #!/bin/zsh
        echo "Connexion de Friday à Claude Code."
        echo "Tapez /login, suivez les étapes, puis fermez cette fenêtre."
        echo
        exec \(quoted)
        """
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try body.write(to: script, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: script.path)
            NSWorkspace.shared.open(script)
            note("Terminal est ouvert : tapez /login puis reposez-moi votre question.")
        } catch {
            note("Impossible d'ouvrir Terminal : \(error.localizedDescription)")
        }
    }

    func openWindow(_ id: String) {
        openWindowAction?(id)
        NSApp.activate()
    }

    func openSettings() {
        openSettingsAction?()
        NSApp.activate()
    }

    func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
        messages.append(ChatMessage(fromFriday: false, text: text))
        show(.thinking)
        guard let core else { answerLocally(); return }
        pendingText.insert(core.ask(text, source: "text"))
    }

    private func answerLocally() {
        let text = "Mon cœur n'est pas joignable pour l'instant."
        messages.append(ChatMessage(fromFriday: true, text: text))
        if let voice { Task { await voice.controller.say(text) } } else { show(.sad) }
    }

    /// Message système de Friday dans le fil.
    private func note(_ text: String) {
        log("note : \(text)")
        messages.append(ChatMessage(fromFriday: true, text: text))
    }

    /// Journal sur stderr. Jamais le texte d'un énoncé (règle d'audit) : seulement sa longueur.
    func log(_ text: String) {
        let t = ISO8601DateFormatter().string(from: Date())
        FileHandle.standardError.write(Data("[friday-app] \(t) \(text)\n".utf8))
    }

    static func describe(_ msg: OutMessage) -> String {
        switch msg.type {
        case "state": "voix : état \(msg.state ?? "?")"
        case "utterance": "voix : énoncé (\(msg.text?.count ?? 0) caractères)"
        case "metrics": "voix : TTFA \(msg.ttfaMs ?? -1) ms"
        case "error": "voix : erreur \(msg.message ?? "?")"
        default: "voix : \(msg.type)"
        }
    }

    private func apply(_ sequence: [AvatarState]) {
        for (i, s) in sequence.enumerated() {
            if i == 0 { avatar = s } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3 * Double(i)) { [weak self] in self?.avatar = s }
            }
        }
    }
}
