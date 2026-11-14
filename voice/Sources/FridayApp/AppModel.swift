import FridayUICore
import FridayVoiceCore
import FridayVoiceKit
import Foundation
import Observation

struct ChatMessage: Identifiable, Equatable {
    let id = UUID()
    let fromFriday: Bool
    let text: String
    let date = Date()
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

    private var machine = AvatarMachine()
    private let started = Date()
    private var now: TimeInterval { Date().timeIntervalSince(started) }
    private var timer: Timer?
    private let level = LevelBox()
    private var core: CoreClient?
    private var voice: VoicePipeline?
    private var pendingText: Set<Int> = []        // questions tapées en attente de réponse

    init() {
        timer = Timer.scheduledTimer(withTimeInterval: 1 / 20, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.apply(self.machine.tick(now: self.now))
                let target = self.voiceState == .listening ? AudioLevel.normalized(rms: self.level.get()) : 0
                let next = AudioLevel.smoothed(previous: self.audioLevel, target: target)
                if abs(next - self.audioLevel) > 0.01 || (next == 0) != (self.audioLevel == 0) { self.audioLevel = next }
            }
        }
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
        let pipeline = await VoicePipeline(
            language: "fr-FR",
            emit: { msg in Task { @MainActor in AppModel.shared.handle(msg) } },
            level: { box.set($0) }
        )
        guard let pipeline else { note("Transcription française indisponible sur ce Mac."); return }
        do {
            try await pipeline.start()
            voice = pipeline
            voiceAvailable = true
        } catch {
            note("Micro indisponible : \(error.localizedDescription). La saisie texte reste active.")
        }
    }

    // MARK: - Événements

    /// Pipeline vocal → interface et cœur.
    func handle(_ msg: OutMessage) {
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
        case .ready:
            break
        case .reply(let id, let text, _, _):
            pendingText.remove(id)
            messages.append(ChatMessage(fromFriday: true, text: text))
            if let voice { Task { await voice.controller.say(text) } } else { show(.happy) }
        case .error(let message):
            pendingText.removeAll()
            note("Le cœur a signalé une erreur : \(message)")
            show(.confused)
        }
    }

    private func coreExited(_ code: Int32) {
        core = nil
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
        switch VoiceLink.hotkey(expanded: overlayExpanded, voice: voiceState) {
        case .expandAndListen:
            OverlayController.shared.show(model: self)
            OverlayController.shared.setExpanded(true)
            if voiceState != .listening { toggleListening() }
        case .listen, .stopListening:
            toggleListening()
        }
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
        messages.append(ChatMessage(fromFriday: true, text: text))
    }

    private func apply(_ sequence: [AvatarState]) {
        for (i, s) in sequence.enumerated() {
            if i == 0 { avatar = s } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3 * Double(i)) { [weak self] in self?.avatar = s }
            }
        }
    }
}
