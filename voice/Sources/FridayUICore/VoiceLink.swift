import FridayVoiceCore

/// Lien entre l'état vocal et l'avatar : quel état demander, quel libellé afficher.
public enum VoiceLink {
    /// nil = fin d'activité, l'avatar revient à Neutre.
    public static func avatar(for voice: VoiceState) -> AvatarState? {
        switch voice {
        case .idle: nil
        case .listening: .listening
        case .processing: .thinking
        case .speaking: .happy
        }
    }

    /// Libellé sous l'avatar : la parole a son propre libellé, sinon celui de l'expression.
    public static func label(voice: VoiceState, avatar: AvatarState) -> String {
        voice == .speaking && avatar == .happy ? "Je parle" : avatar.label
    }

    /// Raccourci global : ouvre la fenêtre et lance l'écoute ; fenêtre déjà ouverte et à l'écoute → arrête.
    public enum HotkeyAction: Equatable, Sendable { case expandAndListen, listen, stopListening }

    public static func hotkey(expanded: Bool, voice: VoiceState) -> HotkeyAction {
        guard expanded else { return .expandAndListen }
        return voice == .listening ? .stopListening : .listen
    }
}
