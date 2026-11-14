import FridayUICore
import SwiftUI

/// Fenêtre principale : barre latérale (navigation + système), hub central, widgets.
struct DashboardView: View {
    @Bindable var model: AppModel
    @State private var section = "Accueil"
    @Environment(\.openWindow) private var openWindow

    private let sections: [(String, String)] = [
        ("Accueil", "house"), ("Conversations", "bubble.left.and.bubble.right"), ("Agents", "person.2"),
        ("Mémoire", "brain"), ("Domotique", "lightbulb"), ("Système", "cpu"),
    ]

    var body: some View {
        NavigationSplitView {
            List(selection: $section) {
                Section {
                    ForEach(sections, id: \.0) { name, icon in
                        Label(name, systemImage: icon).font(.fCallout).tag(name)
                    }
                }
                Section("Système") { StatsView(stats: model.stats) }
            }
            .navigationSplitViewColumnWidth(min: 200, ideal: 240, max: 280)
        } detail: {
            HStack(spacing: 0) {
                HubView(model: model).frame(maxWidth: .infinity, maxHeight: .infinity)
                WidgetsColumn().frame(width: 300)
            }
            .background(Theme.surface0)
        }
        .toolbar {
            ToolbarItem(placement: .principal) {
                TimelineView(.periodic(from: .now, by: 1)) { tl in
                    Text(tl.date, format: .dateTime.hour().minute())
                        .font(.fMono).foregroundStyle(Theme.textSecondary)
                        .accessibilityLabel("Heure")
                }
            }
            ToolbarItemGroup(placement: .primaryAction) {
                Button { model.toggleListening() } label: {
                    Label(model.avatar == .listening ? "Arrêter l'écoute" : "Écouter",
                          systemImage: model.avatar == .listening ? "mic.fill" : "mic")
                }
                .help("Écouter (⌘⇧F)")
                Button { openWindow(id: "expressions") } label: { Label("Expressions", systemImage: "face.smiling") }
                    .help("Grille des 18 expressions")
            }
        }
        .navigationTitle("")
        .frame(minWidth: 960, minHeight: 640)
        .preferredColorScheme(.dark)
    }
}

/// Barres système : piste surface 3, remplissage secondaire, valeur en mono. Au-delà de 90 % : icône + couleur.
struct StatsView: View {
    let stats: SystemStats

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            bar("CPU", stats.cpu)
            bar("Mémoire", stats.memory)
            bar("Disque", stats.disk)
        }
        .padding(.vertical, 4)
    }

    private func bar(_ label: String, _ value: Double) -> some View {
        let high = value >= 0.9
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label).font(.fCaption).tertiaryText()
                Spacer()
                if high { Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.warning).font(.fCaption) }
                Text(value, format: .percent.precision(.fractionLength(0))).font(.fMono).foregroundStyle(Theme.textSecondary)
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.surface3)
                    Capsule().fill(high ? Theme.warning : Theme.textSecondary).frame(width: g.size.width * min(max(value, 0), 1))
                }
            }
            .frame(height: 4)
            .animation(.easeOut(duration: 0.3), value: value)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label)
        .accessibilityValue(Text(value, format: .percent.precision(.fractionLength(0))) + Text(high ? ", élevé" : ""))
    }
}

/// Centre : l'avatar est la seule lumière de l'écran.
struct HubView: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            AvatarView(state: model.avatar, size: 180, audioLevel: model.audioLevel)
            StateLabel(state: model.avatar)
            Text("Bonjour, Thaïne.").font(.fTitle1).foregroundStyle(Theme.textPrimary)
            InputBar(model: model).frame(maxWidth: 500)
            HStack(spacing: 8) {
                quick("Routines", "bolt", "Lance la routine ")
                quick("Fichiers", "folder", "Ouvre le fichier ")
                quick("Rechercher", "magnifyingglass", "Cherche ")
                SettingsLink { Label("Réglages", systemImage: "gearshape") }.buttonStyle(SurfaceButtonStyle())
            }
            Spacer()
        }
        .padding(32)
    }

    private func quick(_ title: String, _ icon: String, _ prefix: String) -> some View {
        Button { model.draft = prefix } label: { Label(title, systemImage: icon) }
            .buttonStyle(SurfaceButtonStyle())
    }
}

/// État écrit sous l'avatar et annoncé à VoiceOver (jamais l'animation seule).
struct StateLabel: View {
    let state: AvatarState
    var body: some View {
        Text(state.label)
            .font(.fCaption).foregroundStyle(Theme.textSecondary)
            .accessibilityAddTraits(.updatesFrequently)
            .onChange(of: state) { _, new in AccessibilityNotification.Announcement(new.label).post() }
    }
}

/// Barre de saisie en verre (un des trois éléments autorisés à porter le Liquid Glass).
struct InputBar: View {
    @Bindable var model: AppModel
    var compact = false

    var body: some View {
        HStack(spacing: 8) {
            TextField("Parle-moi…", text: $model.draft)
                .textFieldStyle(.plain)
                .font(.fBody)
                .foregroundStyle(Theme.textPrimary)
                .onSubmit { model.send() }
                .accessibilityLabel("Message à Friday")
            Button { model.toggleListening() } label: {
                Image(systemName: model.avatar == .listening ? "mic.fill" : "mic")
                    .font(.system(size: 16, weight: .medium))
                    .frame(width: 28, height: 28)
                    .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.textPrimary)
            .accessibilityLabel(model.avatar == .listening ? "Arrêter l'écoute" : "Écouter")
            .help("Écouter")
        }
        .padding(.leading, 16).padding(.trailing, 8)
        .frame(height: compact ? 40 : 44)
        .glassSurface(radius: 20)
    }
}

struct WidgetsColumn: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                card("Météo") {
                    HStack(spacing: 12) {
                        Image(systemName: "cloud.sun").font(.system(size: 28)).foregroundStyle(Theme.textPrimary)
                        VStack(alignment: .leading) {
                            Text("12°").font(.fTitle2).foregroundStyle(Theme.textPrimary)
                            Text("Paris · nuageux").font(.fBody).foregroundStyle(Theme.textSecondary)
                        }
                    }
                }
                card("Agenda") {
                    VStack(alignment: .leading, spacing: 8) {
                        event("09:30", "Point projet Friday")
                        event("14:00", "Dentiste")
                    }
                }
                card("Activité") { ActivityChart(values: [3, 5, 2, 6, 4, 7], days: ["L", "M", "M", "J", "V", "S"]) }
                Text("Données de démonstration").font(.fCaption).tertiaryText()
            }
            .padding(16)
        }
        .background(Theme.surface1)
    }

    private func card<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.fHeadline).foregroundStyle(Theme.textPrimary)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Theme.surface2, in: .rect(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
    }

    private func event(_ time: String, _ title: String) -> some View {
        HStack(spacing: 12) {
            Text(time).font(.fMono).foregroundStyle(Theme.textSecondary)
            Text(title).font(.fBody).foregroundStyle(Theme.textPrimary)
        }
    }
}

struct ActivityChart: View {
    let values: [Double]
    let days: [String]
    var body: some View {
        let peak = values.max() ?? 1
        HStack(alignment: .bottom, spacing: 10) {
            ForEach(values.indices, id: \.self) { i in
                VStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 2).fill(Theme.textSecondary)
                        .frame(width: 20, height: 60 * values[i] / peak)
                    Text(days[i]).font(.fCaption).tertiaryText()
                }
                .help("\(Int(values[i])) interactions")
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(days[i]) : \(Int(values[i])) interactions")
            }
        }
        .frame(height: 84, alignment: .bottom)
    }
}
