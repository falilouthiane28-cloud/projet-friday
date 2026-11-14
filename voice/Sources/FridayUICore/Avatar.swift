import Foundation

/// Les 18 états émotionnels de l'avatar (raw value = entrée `eyeState` 0–17).
public enum AvatarState: Int, CaseIterable, Sendable, Identifiable {
    case neutral, happy, love, excited, thinking, confused
    case sleeping, angry, sad, loading, alert, wink
    case surprised, dizzy, shy, cool, error, listening

    public var id: Int { rawValue }

    /// Libellé affiché sous l'avatar et annoncé à VoiceOver.
    public var label: String {
        switch self {
        case .neutral: "Neutre"
        case .happy: "Joyeux"
        case .love: "Amour"
        case .excited: "Excité"
        case .thinking: "Je réfléchis"
        case .confused: "Confus"
        case .sleeping: "En veille"
        case .angry: "En colère"
        case .sad: "Triste"
        case .loading: "Chargement"
        case .alert: "Alerte"
        case .wink: "Clin d'œil"
        case .surprised: "Surpris"
        case .dizzy: "Étourdi"
        case .shy: "Timide"
        case .cool: "Cool"
        case .error: "Erreur"
        case .listening: "À l'écoute"
        }
    }

    /// Priorité : plus haut = l'emporte. Erreur/alerte > écoute > activité > émotions > repos.
    public var priority: Int {
        switch self {
        case .error, .alert: 4
        case .listening: 3
        case .loading, .thinking: 2
        case .sleeping, .neutral: 0
        default: 1
        }
    }

    /// Les états d'activité durent tant que l'activité dure ; les autres expirent.
    public var expires: Bool { priority == 1 || priority == 4 }
}

/// Machine d'états de l'avatar (pure, testable).
public struct AvatarMachine: Sendable {
    public private(set) var state: AvatarState = .neutral
    public private(set) var since: TimeInterval = 0
    public let neutralAfter: TimeInterval

    /// Transitions directes interdites : on passe par Neutre.
    static let forbidden: Set<[AvatarState]> = [[.sleeping, .angry], [.sleeping, .excited], [.sleeping, .dizzy]]

    public init(neutralAfter: TimeInterval = 10) { self.neutralAfter = neutralAfter }

    /// Demande un état. Retourne la séquence d'états à jouer (vide si refusé).
    @discardableResult
    public mutating func request(_ next: AvatarState, now: TimeInterval) -> [AvatarState] {
        guard next != state else { since = now; return [] }
        // Alerte et erreur ne sont interrompues que par un état de même priorité ou par clear().
        if state.priority == 4, next.priority < 4 { return [] }
        let path: [AvatarState] = AvatarMachine.forbidden.contains([state, next]) ? [.neutral, next] : [next]
        state = next
        since = now
        return path
    }

    /// Fin d'une activité (écoute, chargement…) ou d'une alerte.
    public mutating func clear(now: TimeInterval) -> [AvatarState] {
        guard state != .neutral else { return [] }
        state = .neutral
        since = now
        return [.neutral]
    }

    /// Retour à Neutre après `neutralAfter` secondes sans stimulus.
    public mutating func tick(now: TimeInterval) -> [AvatarState] {
        guard state.expires, now - since >= neutralAfter else { return [] }
        return clear(now: now)
    }
}
