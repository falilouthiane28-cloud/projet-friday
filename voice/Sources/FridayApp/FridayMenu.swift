import AppKit
import SwiftUI

/// Commandes de Friday, partagées par la barre de menus, le menu « … » de la fenêtre et le clic droit sur la bulle.
/// Le menu contextuel reste court, sans raccourcis affichés, et masque ce qui n'est pas disponible (HIG › Context menus).
struct FridayMenuItems: View {
    let model: AppModel
    var context = false                             // true : menu contextuel de la bulle

    var body: some View {
        Section {
            if context && !model.overlayExpanded {
                Button("Ouvrir la conversation", systemImage: "bubble.left") { OverlayController.shared.setExpanded(true) }
            }
            if model.voiceAvailable || !context {
                Button(model.voiceState == .listening ? "Arrêter l'écoute" : "Écouter",
                       systemImage: model.voiceState == .listening ? "mic.slash" : "mic") { model.toggleListening() }
                    .disabled(!model.voiceAvailable)
                    .shortcut(context ? nil : KeyEquivalent("l"))
            }
            Button("Nouvelle conversation", systemImage: "square.and.pencil") { model.newConversation() }
                .shortcut(context ? nil : KeyEquivalent("n"))
        }
        if model.needsLogin && model.claudeBinary != nil {
            Section { Button("Connecter Claude Code…", systemImage: "person.badge.key") { model.connectClaude() } }
        }
        Section {
            Button("Dashboard", systemImage: "rectangle.grid.2x2") { model.openWindow("dashboard") }
            if !context {
                Button("Expressions", systemImage: "face.smiling") { model.openWindow("expressions") }
                Toggle("Lire toutes les réponses", isOn: Binding(get: { model.speakAllReplies },
                                                                 set: { model.speakAllReplies = $0 }))
            }
            Button("Réglages…", systemImage: "gearshape") { model.openSettings() }
                .shortcut(context ? nil : KeyEquivalent(","))
        }
        Section {
            Button("Quitter Friday", systemImage: "power") { NSApp.terminate(nil) }
                .shortcut(context ? nil : KeyEquivalent("q"))
        }
    }
}

private extension View {
    @ViewBuilder func shortcut(_ key: KeyEquivalent?) -> some View {
        if let key { keyboardShortcut(key, modifiers: .command) } else { self }
    }
}

/// Capture les actions d'ouverture de fenêtre depuis une vue toujours présente dans la scène (l'icône de barre de menus),
/// pour que la bulle — hébergée hors des scènes SwiftUI — puisse ouvrir le dashboard et les réglages.
struct MenuBarLabel: View {
    let model: AppModel
    @Environment(\.openWindow) private var openWindow
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        Image(systemName: model.voiceState == .listening ? "eye.fill" : "eye")
            .accessibilityLabel("Friday")
            .onAppear {
                model.openWindowAction = { openWindow(id: $0) }
                model.openSettingsAction = { openSettings() }
                model.log("actions de fenêtre capturées (dashboard, réglages)")
            }
    }
}
