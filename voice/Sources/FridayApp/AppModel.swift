import FridayUICore
import Foundation
import Observation

struct ChatMessage: Identifiable, Equatable {
    let id = UUID()
    let fromFriday: Bool
    let text: String
    let date = Date()
}

/// État partagé par la barre de menus, le dashboard et l'overlay.
@MainActor @Observable
final class AppModel {
    static let shared = AppModel()
    var overlayExpanded = false
    private(set) var avatar: AvatarState = .neutral
    var audioLevel: Double = 0
    var draft = ""
    var messages: [ChatMessage] = [
        ChatMessage(fromFriday: true, text: "Bonjour Thaïne. Je suis prête."),
    ]
    let stats = SystemStats()

    private var machine = AvatarMachine()
    private let started = Date()
    private var now: TimeInterval { Date().timeIntervalSince(started) }
    private var timer: Timer?

    init() {
        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.apply(self.machine.tick(now: self.now))
                if self.avatar == .listening {            // niveau audio de démonstration
                    self.audioLevel = 0.5 + 0.5 * sin(Date().timeIntervalSinceReferenceDate * 5)
                }
            }
        }
    }

    func show(_ state: AvatarState) {
        if state == .neutral { apply(machine.clear(now: now)) } else { apply(machine.request(state, now: now)) }
    }

    func toggleListening() {
        avatar == .listening ? show(.neutral) : show(.listening)
    }

    func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
        messages.append(ChatMessage(fromFriday: false, text: text))
        show(.thinking)
        // Le cœur Python (puis Claude Code) répondra ici ; en attendant, réponse locale.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { [weak self] in
            guard let self else { return }
            self.messages.append(ChatMessage(fromFriday: true, text: "Bien reçu. Le cerveau sera branché à la phase 3."))
            self.show(.happy)
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
