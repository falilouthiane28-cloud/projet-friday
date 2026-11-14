// friday-app : interface SwiftUI de Friday.
//   friday-app                       → app de barre de menus
//   friday-app --snapshot <dossier>  → rend la grille et l'avatar en PNG (vérification sans écran)
//   friday-app --selftest            → app ↔ cœur Python de bout en bout, sans écran ni micro
import AppKit
import FridayUICore
import KeyboardShortcuts
import SwiftUI

extension KeyboardShortcuts.Name {
    /// Ouvre la bulle et lance l'écoute. Depuis Sequoia, un raccourci global doit contenir Cmd ou Ctrl.
    static let summonFriday = Self("summonFriday", default: .init(.space, modifiers: [.control, .option]))
}

struct FridayApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel.shared

    var body: some Scene {
        MenuBarExtra {
            MenuContent(model: model)
        } label: {
            MenuBarLabel(model: model)
        }
        Window("Friday", id: "dashboard") { DashboardView(model: model) }
            .defaultSize(width: 1440, height: 900)
        Window("Expressions", id: "expressions") { ExpressionsGridView(model: model) }
            .windowResizability(.contentSize)
        Settings {
            SettingsView(model: model)
        }
    }
}

struct MenuContent: View {
    let model: AppModel
    var body: some View {
        Button("Afficher ou masquer la bulle") { OverlayController.shared.toggle(model: model) }
            .keyboardShortcut("o", modifiers: [.command, .shift])
        Divider()
        FridayMenuItems(model: model)
    }
}

/// Réglages : raccourci global, lecture des réponses, cerveau.
struct SettingsView: View {
    @Bindable var model: AppModel
    var body: some View {
        Form {
            Section("Raccourci") {
                KeyboardShortcuts.Recorder("Appeler Friday :", name: .summonFriday)
                Text("Ouvre la conversation et lance l'écoute ; une seconde pression arrête l'écoute.")
                    .font(.fCaption).foregroundStyle(.secondary)
            }
            Section("Voix") {
                Toggle("Lire aussi les réponses aux messages tapés", isOn: $model.speakAllReplies)
                Text("Par défaut, Friday ne parle que lorsque vous lui parlez.")
                    .font(.fCaption).foregroundStyle(.secondary)
            }
            Section("Cerveau") {
                LabeledContent("Moteur", value: model.brainName ?? "cœur non démarré")
                if model.needsLogin && model.claudeBinary != nil {
                    Button("Connecter Claude Code…") { model.connectClaude() }
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 460)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)           // pas d'icône dans le Dock
        MainActor.assumeIsolated {
            OverlayController.shared.show(model: AppModel.shared)      // bulle dès le lancement
            AppModel.shared.start()                                     // cœur Python + pipeline vocal
        }
        KeyboardShortcuts.onKeyUp(for: .summonFriday) {
            MainActor.assumeIsolated { AppModel.shared.hotkey() }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { AppModel.shared.shutdown() }
    }
}

@MainActor
func snapshot(to dir: String) {
    let url = URL(fileURLWithPath: dir)
    try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    func render(_ view: some View, _ name: String) {
        let r = ImageRenderer(content: view.environment(\.colorScheme, .dark))
        r.scale = 2
        guard let img = r.nsImage, let tiff = img.tiffRepresentation,
              let png = NSBitmapImageRep(data: tiff)?.representation(using: .png, properties: [:]) else {
            print("échec : \(name)"); return
        }
        try? png.write(to: url.appendingPathComponent(name))
        print("écrit : \(name)")
    }
    render(ExpressionsGridView(), "expressions.png")
    render(AvatarView(state: .neutral, size: 360, animated: false).padding(20).background(Color.black), "avatar-neutre.png")
    let model = AppModel.shared
    model.messages += [ChatMessage(fromFriday: false, text: "Qu'est-ce que tu peux faire ?"),
                       ChatMessage(fromFriday: true, text: "Je réponds à vos questions avec **Claude Code**, et je donne l'heure et la date en local.")]
    render(OverlayView(model: model).background(Color(white: 0.25)), "fenetre.png")
}

let args = CommandLine.arguments
if args.contains("--selftest") {
    Task { @MainActor in exit(await runSelfTest() ? 0 : 1) }
    dispatchMain()
} else if let i = args.firstIndex(of: "--snapshot") {
    MainActor.assumeIsolated { snapshot(to: i + 1 < args.count ? args[i + 1] : "snapshots") }
} else {
    FridayApp.main()
}
