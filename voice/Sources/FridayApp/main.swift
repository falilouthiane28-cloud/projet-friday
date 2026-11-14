// friday-app : interface SwiftUI de Friday.
//   friday-app                       → app de barre de menus
//   friday-app --snapshot <dossier>  → rend la grille et l'avatar en PNG (vérification sans écran)
//   friday-app --selftest            → app ↔ cœur Python de bout en bout, sans écran ni micro
import AppKit
import FridayUICore
import FridayVoiceCore
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
    model.handle(.memory(facts: [
        MemoryFact(id: 3, text: "La sœur de l'utilisateur s'appelle Awa", category: "proches", createdAt: "2026-11-14T10:00:00+00:00"),
        MemoryFact(id: 2, text: "L'utilisateur boit son café sans sucre", category: "habitude", createdAt: "2026-11-14T09:00:00+00:00"),
        MemoryFact(id: 1, text: "L'utilisateur habite à Lyon", category: "identite", createdAt: "2026-11-13T09:00:00+00:00"),
    ], available: true, forgot: nil))
    model.showingMemory = true
    model.forgetFact(2)                               // 2e fait en attente de confirmation
    render(MemoryPanel(model: model, scrolls: false).padding(16).frame(width: 380, height: 520)
        .background(Color(white: 0.1)), "fenetre-memoire.png")

    // Dashboard : chaque section seule (ImageRenderer ne rend ni NavigationSplitView ni ScrollView).
    var info = DashboardInfo()
    info.city = "Dakar"
    info.weather = .init(city: "Dakar", temperature: 27.4, feelsLike: 29, code: 2, label: "partiellement nuageux",
                         wind: 18, isDay: false, min: 22, max: 30, rain: 5)
    info.agenda = [.init(start: "2026-11-14T00:00:00", end: "2026-11-15T00:00:00", title: "Anniversaire d'Awa", allDay: true),
                   .init(start: "2026-11-14T14:00:00", end: "2026-11-14T15:00:00", title: "Dentiste")]
    info.agents = AgentsSection.fallback
    model.handle(.dashboard(info))
    let detail = { (v: AnyView, name: String) in
        render(v.frame(width: 1200, height: 860).background(Theme.surface0), name)
    }
    detail(AnyView(HStack(spacing: 0) {
        HubView(model: model).frame(maxWidth: .infinity, maxHeight: .infinity)
        WidgetsColumn(model: model, scrolls: false).frame(width: 300).frame(maxHeight: .infinity, alignment: .top).background(Theme.surface1)
    }), "dash-accueil.png")
    detail(AnyView(AgentsSection(model: model, scrolls: false)), "dash-agents.png")
    detail(AnyView(MemorySection(model: model, scrolls: false)), "dash-memoire.png")
    detail(AnyView(HomeAutomationSection(model: model, scrolls: false)), "dash-domotique.png")
    detail(AnyView(SystemSection(model: model, scrolls: false)), "dash-systeme.png")
    render(StatsView(stats: model.stats).padding(16).frame(width: 220).background(Theme.surface1), "dash-sidebar-stats.png")

    // Rendu AppKit réel (NSHostingView dans une fenêtre hors écran) : ScrollView et List y sont dessinés.
    func renderLive(_ view: some View, _ size: NSSize, _ name: String, after: () -> Void = {}) {
        let host = NSHostingView(rootView: view.frame(width: size.width, height: size.height).environment(\.colorScheme, .dark))
        let window = NSWindow(contentRect: NSRect(origin: NSPoint(x: -10_000, y: -10_000), size: size),
                              styleMask: [.borderless], backing: .buffered, defer: false)
        window.contentView = host
        window.orderFrontRegardless()
        host.layoutSubtreeIfNeeded()
        RunLoop.main.run(until: Date().addingTimeInterval(0.3))
        after()                                       // ex. réponse du cœur simulée après onAppear
        RunLoop.main.run(until: Date().addingTimeInterval(0.3))
        guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { print("échec : \(name)"); return }
        host.cacheDisplay(in: host.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?.write(to: url.appendingPathComponent(name))
        window.orderOut(nil)
        print("écrit : \(name)")
    }
    let live = NSSize(width: 1200, height: 860)
    renderLive(MemorySection(model: model).background(Theme.surface0), live, "live-memoire.png") {
        model.handle(.memory(facts: [
            MemoryFact(id: 4, text: "L'utilisateur s'appelle Thaïne", category: "identite", createdAt: "2026-11-14T21:00:00+00:00"),
        ], available: true, forgot: nil))
    }
    renderLive(ConversationsSection(model: model).background(Theme.surface0), live, "live-conversations.png")
    for section in [DashSection.memoire, .agents, .systeme] {
        model.dashboardSection = section
        renderLive(DashboardView(model: model), NSSize(width: 1280, height: 800), "live-dashboard-\(section.rawValue).png") {
            if section == .memoire {
                model.handle(.memory(facts: [MemoryFact(id: 4, text: "L'utilisateur s'appelle Thaïne", category: "identite",
                                                        createdAt: "2026-11-14T21:00:00+00:00")], available: true, forgot: nil))
            }
        }
    }
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
