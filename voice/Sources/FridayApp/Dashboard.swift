import FridayUICore
import FridayVoiceCore
import SwiftUI

/// Sections de la barre latérale du dashboard.
enum DashSection: String, CaseIterable, Identifiable, Hashable {
    case accueil, conversations, agents, memoire, domotique, systeme
    var id: String { rawValue }

    var title: String {
        switch self {
        case .accueil: "Accueil"
        case .conversations: "Conversations"
        case .agents: "Agents"
        case .memoire: "Mémoire"
        case .domotique: "Domotique"
        case .systeme: "Système"
        }
    }

    var icon: String {
        switch self {
        case .accueil: "house"
        case .conversations: "bubble.left.and.bubble.right"
        case .agents: "person.2"
        case .memoire: "brain"
        case .domotique: "lightbulb"
        case .systeme: "cpu"
        }
    }

    /// ⌘1 à ⌘6.
    var shortcut: KeyEquivalent { KeyEquivalent(Character(String((Self.allCases.firstIndex(of: self) ?? 0) + 1))) }
}

/// Fenêtre principale : barre latérale (6 sections + jauges système), détail de la section choisie.
/// Quand cette fenêtre est au premier plan, la bulle flottante se retire (`OverlayController.updateVisibility`).
struct DashboardView: View {
    @Bindable var model: AppModel

    var body: some View {
        NavigationSplitView {
            List(selection: Binding<DashSection?>(get: { model.dashboardSection },
                                                  set: { if let s = $0 { model.dashboardSection = s } })) {
                ForEach(DashSection.allCases) { s in
                    Label(s.title, systemImage: s.icon).tag(s)
                        .help("\(s.title) (⌘\(String(s.shortcut.character)))")
                }
            }
            .safeAreaInset(edge: .bottom) {
                StatsView(stats: model.stats)
                    .padding(.horizontal, 16).padding(.vertical, 12)
            }
            .navigationSplitViewColumnWidth(min: 200, ideal: 220, max: 280)
        } detail: {
            detail
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Theme.surface0)
                .navigationTitle(model.dashboardSection.title)
        }
        .toolbar { toolbar }
        .background { shortcuts }
        .frame(minWidth: 960, minHeight: 640)
        .preferredColorScheme(.dark)
        .onAppear {
            model.refreshDashboard()
            OverlayController.shared.updateVisibility()
        }
    }

    @ViewBuilder private var detail: some View {
        switch model.dashboardSection {
        case .accueil: HomeSection(model: model)
        case .conversations: ConversationsSection(model: model)
        case .agents: AgentsSection(model: model)
        case .memoire: MemorySection(model: model)
        case .domotique: HomeAutomationSection(model: model)
        case .systeme: SystemSection(model: model)
        }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .primaryAction) {
            if model.dashboardSection == .conversations {
                Button { model.newConversation() } label: { Label("Nouvelle conversation", systemImage: "square.and.pencil") }
                    .help("Nouvelle conversation")
            }
            if model.dashboardSection == .accueil {
                Button { model.refreshDashboard(force: true) } label: { Label("Actualiser", systemImage: "arrow.clockwise") }
                    .help("Actualiser la météo et l'agenda")
                    .disabled(model.dashboardLoading)
            }
            Button { model.toggleListening() } label: {
                Label(model.voiceState == .listening ? "Arrêter l'écoute" : "Écouter",
                      systemImage: model.voiceState == .listening ? "mic.fill" : "mic")
            }
            .help(model.voiceState == .listening ? "Arrêter l'écoute" : "Écouter (⌃⌥Espace)")
            .disabled(!model.voiceAvailable)
            SettingsLink { Label("Réglages", systemImage: "gearshape") }
                .help("Réglages (⌘,)")
        }
    }

    /// Raccourcis ⌘1…⌘6 (l'app de barre de menus n'a pas de barre de menus propre).
    private var shortcuts: some View {
        ZStack {
            ForEach(DashSection.allCases) { s in
                Button("") { model.dashboardSection = s }.keyboardShortcut(s.shortcut, modifiers: .command)
            }
        }
        .opacity(0).accessibilityHidden(true).allowsHitTesting(false)
    }
}

// MARK: - Accueil

/// Accueil : l'avatar au centre (seule lumière de l'écran), widgets réels à droite.
struct HomeSection: View {
    @Bindable var model: AppModel

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 0) {
                HubView(model: model).frame(minWidth: 480, maxWidth: .infinity, maxHeight: .infinity)
                WidgetsColumn(model: model).frame(width: 300)
            }
            ScrollView {
                VStack(spacing: 0) {
                    HubView(model: model).frame(minHeight: 560)
                    WidgetsColumn(model: model, scrolls: false)
                }
            }
        }
    }
}

/// Centre : date et heure, avatar, état, salutation, saisie et suggestions qui mènent à une vraie réponse.
struct HubView: View {
    @Bindable var model: AppModel
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            TimelineView(.everyMinute) { tl in
                Text(Self.dateLine(tl.date))
                    .font(.fCaption).tertiaryText()
                    .accessibilityLabel(Text(tl.date, format: .dateTime.weekday(.wide).day().month(.wide).hour().minute()))
            }
            AvatarView(state: model.avatar, size: 180, audioLevel: model.audioLevel)
            StateLabel(state: model.avatar, text: model.statusLabel)
            TimelineView(.everyMinute) { tl in
                Text(Self.greeting(tl.date)).font(.fTitle1).foregroundStyle(Theme.textPrimary)
            }
            InputBar(model: model, focus: $focused, onSubmit: send).frame(maxWidth: 520)
            HStack(spacing: 8) {
                suggestion("Agenda du jour", "calendar", "Qu'est-ce que j'ai au programme aujourd'hui ?")
                suggestion("Météo", "cloud.sun", "Quel temps fait-il aujourd'hui ?")
                Button { model.draft = "Cherche "; focused = true } label: { Label("Rechercher", systemImage: "magnifyingglass") }
                    .buttonStyle(SurfaceButtonStyle())
                    .help("Demander une recherche sur le web")
                Button { model.dashboardSection = .memoire } label: { Label("Mémoire", systemImage: "brain") }
                    .buttonStyle(SurfaceButtonStyle())
                    .help("Ce dont Friday se souvient")
            }
            Spacer()
        }
        .padding(32)
    }

    /// Envoyer depuis l'accueil ouvre la conversation, où la réponse s'affiche.
    private func send() {
        guard !model.draft.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        model.send()
        model.dashboardSection = .conversations
    }

    private func suggestion(_ title: String, _ icon: String, _ prompt: String) -> some View {
        Button { model.draft = prompt; send() } label: { Label(title, systemImage: icon) }
            .buttonStyle(SurfaceButtonStyle())
            .help("Demander : « \(prompt) »")
    }

    static func greeting(_ date: Date) -> String {
        let h = Calendar.current.component(.hour, from: date)
        return (h >= 18 || h < 5 ? "Bonsoir" : "Bonjour") + ", Thaïne."
    }

    static func dateLine(_ date: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateFormat = "EEEE d MMMM · HH:mm"
        return f.string(from: date).capitalizedFirst
    }
}

extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
}

/// État écrit sous l'avatar et annoncé à VoiceOver (jamais l'animation seule).
struct StateLabel: View {
    let state: AvatarState
    var text: String? = nil                        // libellé imposé (ex. « Je parle »)
    var body: some View {
        Text(text ?? state.label)
            .font(.fCaption).foregroundStyle(Theme.textSecondary)
            .accessibilityAddTraits(.updatesFrequently)
            .onChange(of: state) { _, new in AccessibilityNotification.Announcement(new.label).post() }
    }
}

/// Barre de saisie en verre (un des trois éléments autorisés à porter le Liquid Glass).
struct InputBar: View {
    @Bindable var model: AppModel
    var compact = false
    var focus: FocusState<Bool>.Binding? = nil
    var onSubmit: (() -> Void)? = nil

    var body: some View {
        HStack(spacing: 8) {
            field
            Button { model.toggleListening() } label: {
                Image(systemName: model.voiceState == .listening ? "mic.fill" : "mic")
                    .font(.system(size: 16, weight: .medium))
                    .frame(width: 28, height: 28)
                    .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .foregroundStyle(model.voiceAvailable ? Theme.textPrimary : Theme.textSecondary)
            .disabled(!model.voiceAvailable)
            .accessibilityLabel(model.voiceState == .listening ? "Arrêter l'écoute" : "Écouter")
            .help(model.voiceAvailable ? "Écouter" : "Micro indisponible")
        }
        .padding(.leading, 16).padding(.trailing, 8)
        .frame(height: compact ? 40 : 44)
        .glassSurface(radius: 20)
    }

    @ViewBuilder private var field: some View {
        let f = TextField("Parle-moi…", text: $model.draft)
            .textFieldStyle(.plain)
            .font(.fBody)
            .foregroundStyle(Theme.textPrimary)
            .onSubmit { if let onSubmit { onSubmit() } else { model.send() } }
            .accessibilityLabel("Message à Friday")
        if let focus { f.focused(focus) } else { f }
    }
}

/// Jauges système de la barre latérale : piste surface 3, remplissage secondaire, valeur en mono. ≥ 90 % : icône + couleur.
struct StatsView: View {
    let stats: SystemStats

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            bar("CPU", stats.cpu)
            bar("Mémoire", stats.memory)
            bar("Disque", stats.disk)
        }
    }

    private func bar(_ label: String, _ value: Double) -> some View {
        let high = value >= 0.9
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label).font(.fCaption).tertiaryText()
                Spacer()
                if high { Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.warning).font(.fCaption) }
                Text(value, format: .percent.precision(.fractionLength(0))).font(.fMono).foregroundStyle(Theme.textSecondary)
                    .monospacedDigit()
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

// MARK: - Widgets de l'accueil (données réelles)

struct WidgetsColumn: View {
    let model: AppModel
    var scrolls = true

    var body: some View {
        Group {
            if scrolls { ScrollView { content } } else { content }
        }
        .background(Theme.surface1)
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 12) {
            WeatherCard(model: model)
            AgendaCard(model: model)
            FridayStatusCard(model: model)
            if let date = model.dashboardUpdated {
                Text("Mis à jour à \(date.formatted(.dateTime.hour().minute()))").font(.fCaption).tertiaryText()
                    .padding(.horizontal, 4)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Carte opaque (surface 2, bord 1 px, rayon 12) avec titre en headline.
struct Card<Content: View>: View {
    let title: String
    var icon: String? = nil
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                if let icon { Image(systemName: icon).font(.fCaption).foregroundStyle(Theme.textSecondary) }
                Text(title).font(.fHeadline).foregroundStyle(Theme.textPrimary)
            }
            .accessibilityAddTraits(.isHeader)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Theme.surface2, in: .rect(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
    }
}

/// Ligne d'attente ou d'erreur d'une carte.
struct CardPlaceholder: View {
    let loading: Bool
    let text: String
    var body: some View {
        HStack(spacing: 8) {
            if loading { ProgressView().controlSize(.small) }
            Text(text).font(.fCallout).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct WeatherCard: View {
    let model: AppModel

    var body: some View {
        Card(title: "Météo") {
            if let w = model.dashboard?.weather {
                HStack(spacing: 14) {
                    Image(systemName: w.symbol).font(.system(size: 30)).foregroundStyle(Theme.textPrimary)
                        .frame(width: 40).accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(Int(w.temperature.rounded()))°").font(.fTitle2).foregroundStyle(Theme.textPrimary)
                        Text("\(w.city) · \(w.label)").font(.fCallout).foregroundStyle(Theme.textSecondary).lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .accessibilityElement(children: .combine)
                Text(details(w)).font(.fCaption).tertiaryText()
            } else {
                CardPlaceholder(loading: model.dashboard == nil,
                                text: model.dashboard == nil ? "Chargement…" : (model.dashboard?.weatherError ?? "Météo indisponible."))
            }
        }
    }

    private func details(_ w: DashboardInfo.Weather) -> String {
        var parts: [String] = []
        if let min = w.min, let max = w.max { parts.append("\(Int(min.rounded()))° / \(Int(max.rounded()))°") }
        if let f = w.feelsLike { parts.append("ressenti \(Int(f.rounded()))°") }
        if let r = w.rain { parts.append("pluie \(r) %") }
        return parts.joined(separator: " · ")
    }
}

struct AgendaCard: View {
    let model: AppModel

    var body: some View {
        Card(title: "Aujourd'hui") {
            if let events = model.dashboard?.agenda {
                if events.isEmpty {
                    Text("Rien de prévu.").font(.fCallout).foregroundStyle(Theme.textSecondary)
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(events.prefix(6)) { e in
                            HStack(alignment: .firstTextBaseline, spacing: 12) {
                                Text(e.timeLabel).font(.fMono).foregroundStyle(Theme.textSecondary).frame(width: 64, alignment: .leading)
                                Text(e.title).font(.fCallout).foregroundStyle(Theme.textPrimary).lineLimit(2)
                            }
                            .accessibilityElement(children: .combine)
                        }
                        if events.count > 6 {
                            Text("et \(events.count - 6) autre(s)").font(.fCaption).tertiaryText()
                        }
                    }
                }
            } else {
                CardPlaceholder(loading: model.dashboard == nil,
                                text: model.dashboard == nil ? "Chargement…" : (model.dashboard?.agendaError ?? "Calendrier indisponible."))
            }
        }
    }
}

/// Ce qui marche, en clair (icône + texte, jamais la couleur seule).
struct FridayStatusCard: View {
    let model: AppModel

    var body: some View {
        Card(title: "Friday") {
            VStack(alignment: .leading, spacing: 8) {
                StatusLine(icon: model.brainName == nil ? "brain" : "brain.fill", text: brainText)
                StatusLine(icon: model.voiceAvailable ? "mic.fill" : "mic.slash", text: model.voiceAvailable ? "Micro actif" : "Micro indisponible")
                StatusLine(icon: "brain.head.profile", text: memoryText)
                StatusLine(icon: model.dashboard?.homeConfigured == true ? "lightbulb.fill" : "lightbulb.slash",
                           text: model.dashboard?.homeConfigured == true ? "Domotique configurée" : "Domotique non configurée")
            }
        }
    }

    private var brainText: String {
        if model.needsLogin { return "Claude Code à connecter" }
        guard let b = model.brainName else { return "Cœur en démarrage" }
        return b == "local" ? "Réponses locales" : "Cerveau : \(b)"
    }

    private var memoryText: String {
        switch model.memory.phase {
        case .loaded: model.memory.facts.isEmpty ? "Aucun souvenir" : "\(model.memory.facts.count) souvenir(s)"
        case .unavailable: "Mémoire indisponible"
        default: "Mémoire"
        }
    }
}

struct StatusLine: View {
    let icon: String
    let text: String
    var body: some View {
        Label { Text(text).foregroundStyle(Theme.textSecondary) } icon: {
            Image(systemName: icon).foregroundStyle(Theme.textPrimary).frame(width: 18)
        }
        .font(.fCallout)
    }
}
