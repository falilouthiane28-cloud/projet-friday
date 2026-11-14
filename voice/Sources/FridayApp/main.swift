// friday-app : interface SwiftUI de Friday.
//   friday-app                       → app de barre de menus
//   friday-app --snapshot <dossier>  → rend la grille et l'avatar en PNG (vérification sans écran)
import AppKit
import FridayUICore
import SwiftUI

struct FridayApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel.shared

    var body: some Scene {
        MenuBarExtra("Friday", systemImage: "eye") {
            MenuContent(model: model)
        }
        Window("Friday", id: "dashboard") { DashboardView(model: model) }
            .defaultSize(width: 1440, height: 900)
        Window("Expressions", id: "expressions") { ExpressionsGridView(model: model) }
            .windowResizability(.contentSize)
        Settings {
            Text("Réglages à venir : raccourci global, mot d'activation, voix.")
                .font(.fBody).padding(32).frame(width: 420)
        }
    }
}

struct MenuContent: View {
    let model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button("Afficher le dashboard") { open("dashboard") }
        Button("Afficher ou masquer la bulle") { OverlayController.shared.toggle(model: model) }
            .keyboardShortcut("o", modifiers: [.command, .shift])
        Button(model.avatar == .listening ? "Arrêter l'écoute" : "Écouter") { model.toggleListening() }
            .keyboardShortcut("f", modifiers: [.command, .shift])
        Button("Expressions") { open("expressions") }
        Divider()
        SettingsLink { Text("Réglages…") }.keyboardShortcut(",")
        Button("Quitter Friday") { NSApp.terminate(nil) }.keyboardShortcut("q")
    }

    private func open(_ id: String) {
        openWindow(id: id)
        NSApp.activate()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)           // pas d'icône dans le Dock
        MainActor.assumeIsolated { OverlayController.shared.show(model: AppModel.shared) }   // bulle dès le lancement
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
}

let args = CommandLine.arguments
if let i = args.firstIndex(of: "--snapshot") {
    MainActor.assumeIsolated { snapshot(to: i + 1 < args.count ? args[i + 1] : "snapshots") }
} else {
    FridayApp.main()
}
