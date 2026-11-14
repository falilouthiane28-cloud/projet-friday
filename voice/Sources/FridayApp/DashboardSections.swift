import AppKit
import FridayVoiceCore
import SwiftUI

/// Colonne de contenu centrée et lisible (largeur max 760), avec en-tête de section.
struct SectionPage<Content: View>: View {
    let title: String
    var subtitle: String? = nil
    var scrolls = true
    @ViewBuilder var content: Content

    var body: some View {
        let page = VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 6) {
                Text(title).font(.fTitle1).foregroundStyle(Theme.textPrimary).accessibilityAddTraits(.isHeader)
                if let subtitle {
                    Text(subtitle).font(.fBody).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
                }
            }
            content
        }
        .frame(maxWidth: 760, alignment: .leading)
        .padding(32)
        .frame(maxWidth: .infinity)
        if scrolls { ScrollView { page } } else { page.frame(maxHeight: .infinity, alignment: .top) }
    }
}

// MARK: - Conversations

/// Le fil complet de la conversation, avec la même saisie que la bulle.
struct ConversationsSection: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(spacing: 16) {
            ChatThread(messages: model.messages, thinking: model.isThinking) { model.answerConfirm($0, ok: $1) }
            InputBar(model: model)
        }
        .frame(maxWidth: 760)
        .padding(.horizontal, 32).padding(.vertical, 24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Agents

/// Les agents spécialisés auxquels Friday délègue, avec leurs outils (registre réel du cœur).
struct AgentsSection: View {
    let model: AppModel
    var scrolls = true

    var body: some View {
        SectionPage(title: "Agents",
                    subtitle: "Friday répond elle-même aux demandes simples et délègue le reste à des agents spécialisés. Chacun ne voit que ses outils ; toute action sensible vous est soumise.",
                    scrolls: scrolls) {
            if let warning { StatusLine(icon: "exclamationmark.circle", text: warning) }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 300), spacing: 12)], spacing: 12) {
                ConductorCard(model: model)
                ForEach(agents) { AgentCard(agent: $0, note: note(for: $0)) }
            }
        }
    }

    private var agents: [DashboardInfo.Agent] {
        let real = model.dashboard?.agents ?? []
        return real.isEmpty ? Self.fallback : real
    }

    private var warning: String? {
        if model.needsLogin { return "Claude Code n'est pas connecté : les agents ne peuvent pas travailler. Réglages › Connecter Claude Code." }
        if model.brainName == "local" { return "Cœur en réponses locales : les agents demandent Claude Code." }
        return nil
    }

    private func note(for agent: DashboardInfo.Agent) -> String? {
        agent.name == "home_controller" && model.dashboard?.homeConfigured != true ? "Home Assistant non configuré" : nil
    }

    /// Avant la réponse du cœur : même liste que `agents/registry.py`.
    static let fallback: [DashboardInfo.Agent] = [
        .init(name: "researcher", title: "Chercheur", role: "Recherche sur le web et synthèse sourcée.", tools: ["web_search", "web_read"]),
        .init(name: "scheduler", title: "Planificateur", role: "Agenda, rappels et événements du Mac.",
              tools: ["calendar_read", "calendar_create_event", "reminder_create"]),
        .init(name: "coder", title: "Codeur", role: "Exécute du Python dans un bac à sable sans réseau.", tools: ["code_run"]),
        .init(name: "home_controller", title: "Contrôleur domotique", role: "Lumières, prises et scènes via Home Assistant.",
              model: "haiku", tools: ["home_states", "home_light", "home_switch", "home_scene", "home_secure"]),
        .init(name: "communicator", title: "Communicateur", role: "Lit vos e-mails et messages, prépare des brouillons.",
              tools: ["mail_read", "mail_draft", "mail_send", "message_read", "message_send", "notification_send"]),
        .init(name: "system_monitor", title: "Moniteur système", role: "Surveille CPU, mémoire, disque et batterie.",
              model: "haiku", tools: ["system_read"]),
    ]
}

/// Icône SF Symbol d'un agent.
func agentSymbol(_ name: String) -> String {
    switch name {
    case "researcher": "magnifyingglass"
    case "scheduler": "calendar"
    case "coder": "chevron.left.forwardslash.chevron.right"
    case "home_controller": "house"
    case "communicator": "envelope"
    case "system_monitor": "gauge.with.dots.needle.33percent"
    default: "person"
    }
}

struct ConductorCard: View {
    let model: AppModel
    var body: some View {
        AgentTile(icon: "wand.and.stars", title: "Friday", subtitle: "Chef d'orchestre",
                  role: "Comprend la demande, répond directement ou choisit l'agent. Lit la météo sans délégation.",
                  model: model.brainName ?? "en démarrage", tools: ["weather_read", "delegate_*"], note: nil)
    }
}

struct AgentCard: View {
    let agent: DashboardInfo.Agent
    var note: String?
    var body: some View {
        AgentTile(icon: agentSymbol(agent.name), title: agent.title, subtitle: nil, role: agent.role,
                  model: agent.model, tools: agent.tools, note: note)
    }
}

struct AgentTile: View {
    let icon: String
    let title: String
    let subtitle: String?
    let role: String
    let model: String
    let tools: [String]
    let note: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 16, weight: .medium)).foregroundStyle(Theme.textPrimary)
                    .frame(width: 36, height: 36)
                    .background(Theme.surface3, in: .rect(cornerRadius: 8))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.fHeadline).foregroundStyle(Theme.textPrimary)
                    Text(subtitle ?? model.capitalizedFirst).font(.fCaption).foregroundStyle(Theme.textSecondary)
                }
                Spacer()
            }
            Text(role).font(.fCallout).foregroundStyle(Theme.textSecondary)
                .lineLimit(3).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            if let note { StatusLine(icon: "lightbulb.slash", text: note) }
            Text(tools.joined(separator: " · ")).font(.system(size: 11, weight: .medium, design: .monospaced))
                .tertiaryText().lineLimit(2)
                .accessibilityLabel("Outils : \(tools.joined(separator: ", "))")
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 176, alignment: .topLeading)
        .background(Theme.surface2, in: .rect(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Mémoire

struct MemorySection: View {
    let model: AppModel
    var scrolls = true

    var body: some View {
        SectionPage(title: "Mémoire", subtitle: subtitle, scrolls: false) {
            MemoryPanel(model: model, scrolls: scrolls, embedded: true)
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { model.requestMemory() } label: { Label("Actualiser", systemImage: "arrow.clockwise") }
                    .help("Actualiser la liste")
            }
        }
        .onAppear { model.requestMemory() }
        .onDisappear { model.cancelForget() }
    }

    private var subtitle: String {
        let n = model.memory.facts.count
        return n == 0 ? "Ce que Friday retient de vos échanges, pour mieux vous aider."
                      : "\(n) souvenir\(n > 1 ? "s" : "") retenu\(n > 1 ? "s" : "") de vos échanges. Vous pouvez en oublier un à tout moment."
    }
}

// MARK: - Domotique

struct HomeAutomationSection: View {
    let model: AppModel
    var scrolls = true
    @State private var copied = false

    private static let command = "security add-generic-password -U -s friday-home-assistant -a friday -w"

    var body: some View {
        SectionPage(title: "Domotique", scrolls: scrolls) {
            if model.dashboard?.homeConfigured == true {
                Card(title: "Home Assistant est configuré", icon: "lightbulb.fill") {
                    Text("Demandez par exemple « allume la lumière du salon » ou « quelles lumières sont allumées ? ». Serrures, alarme et volets demandent toujours votre accord.")
                        .font(.fBody).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
                }
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "lightbulb.slash").font(.system(size: 40, weight: .light)).foregroundStyle(Theme.textSecondary)
                        .accessibilityHidden(true)
                    Text("Home Assistant n'est pas configuré").font(.fTitle2).foregroundStyle(Theme.textPrimary)
                    Text("Friday peut piloter lumières, prises et scènes via Home Assistant. Serrures, alarme et volets demanderont toujours votre accord.")
                        .font(.fBody).foregroundStyle(Theme.textSecondary).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true).frame(maxWidth: 480)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 24)
                Card(title: "Pour l'activer", icon: "list.number") {
                    VStack(alignment: .leading, spacing: 12) {
                        step(1, "Indiquez l'adresse de votre serveur dans config/friday.yaml, clé home_assistant.url.")
                        step(2, "Enregistrez un jeton d'accès longue durée dans le trousseau (jamais dans la configuration) :")
                        HStack(spacing: 8) {
                            Text(Self.command).font(.system(size: 12, weight: .medium, design: .monospaced))
                                .foregroundStyle(Theme.textPrimary).textSelection(.enabled).lineLimit(2)
                                .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                                .background(Theme.surface1, in: .rect(cornerRadius: 8))
                            Button(copied ? "Copiée" : "Copier") {
                                NSPasteboard.general.clearContents()
                                NSPasteboard.general.setString(Self.command, forType: .string)
                                copied = true
                            }
                            .buttonStyle(SurfaceButtonStyle()).fixedSize()
                            .accessibilityLabel("Copier la commande")
                        }
                        step(3, "Relancez Friday.")
                        if let root = CoreClient.repoRoot() {
                            Button { NSWorkspace.shared.open(root.appendingPathComponent("config/friday.yaml")) } label: {
                                Label("Ouvrir friday.yaml", systemImage: "doc.text")
                            }
                            .buttonStyle(SurfaceButtonStyle())
                        }
                    }
                }
            }
        }
    }

    private func step(_ n: Int, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text("\(n)").font(.fMono).foregroundStyle(Theme.textSecondary)
            Text(text).font(.fCallout).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - Système

struct SystemSection: View {
    let model: AppModel
    var scrolls = true

    var body: some View {
        let s = model.stats
        SectionPage(title: "Système", subtitle: "Mesures en direct du Mac, rafraîchies toutes les 2 secondes.", scrolls: scrolls) {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                MetricTile(title: "Processeur", value: s.cpu, detail: "\(s.cores) cœurs", history: s.cpuHistory)
                MetricTile(title: "Mémoire", value: s.memory,
                           detail: "\(Self.gb(s.memoryUsedBytes, binary: true)) sur \(Self.gb(s.memoryTotalBytes, binary: true))")
                MetricTile(title: "Disque", value: s.disk, detail: "\(Self.gb(s.diskFreeBytes)) libres")
                if let b = s.battery {
                    MetricTile(title: "Batterie", value: b, detail: s.charging ? "En charge" : "Sur batterie", lowIsBad: true)
                }
            }
            Card(title: "Friday", icon: "eye") {
                VStack(alignment: .leading, spacing: 8) {
                    StatusLine(icon: "brain.fill", text: model.needsLogin ? "Claude Code à connecter" : "Cerveau : \(model.brainName ?? "cœur en démarrage")")
                    StatusLine(icon: model.voiceAvailable ? "mic.fill" : "mic.slash", text: model.voiceAvailable ? "Micro et transcription prêts (fr-FR)" : "Micro indisponible")
                    StatusLine(icon: "clock", text: "Mac allumé depuis \(Self.duration(s.uptime))")
                    StatusLine(icon: "desktopcomputer", text: ProcessInfo.processInfo.operatingSystemVersionString
                        .replacingOccurrences(of: "Version", with: "macOS"))
                }
            }
        }
    }

    /// Mémoire en Gio (comme « À propos de ce Mac »), disque en Go décimaux (comme le Finder).
    static func gb(_ bytes: Double, binary: Bool = false) -> String {
        String(format: "%.0f Go", bytes / (binary ? 1_073_741_824 : 1_000_000_000))
    }

    static func duration(_ t: TimeInterval) -> String {
        let d = Int(t) / 86_400, h = Int(t) % 86_400 / 3600, m = Int(t) % 3600 / 60
        return d > 0 ? "\(d) j \(h) h" : (h > 0 ? "\(h) h \(m) min" : "\(m) min")
    }
}

/// Tuile de mesure : anneau monochrome + valeur mono ; au-delà du seuil, couleur de statut + icône.
struct MetricTile: View {
    let title: String
    let value: Double
    let detail: String
    var history: [Double] = []
    var lowIsBad = false

    private var alert: Bool { lowIsBad ? value <= 0.1 : value >= 0.9 }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title).font(.fHeadline).foregroundStyle(Theme.textPrimary)
                Spacer()
                if alert { Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.warning).accessibilityHidden(true) }
            }
            HStack(spacing: 16) {
                ZStack {
                    Circle().stroke(Theme.surface3, lineWidth: 6)
                    Circle().trim(from: 0, to: min(max(value, 0), 1))
                        .stroke(alert ? Theme.warning : Theme.textPrimary, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                        .animation(.easeOut(duration: 0.3), value: value)
                    Text(value, format: .percent.precision(.fractionLength(0))).font(.fMono).foregroundStyle(Theme.textPrimary)
                        .monospacedDigit()
                }
                .frame(width: 72, height: 72)
                VStack(alignment: .leading, spacing: 6) {
                    Text(detail).font(.fCallout).foregroundStyle(Theme.textSecondary)
                    if history.count > 1 { Sparkline(values: history).frame(height: 28) }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface2, in: .rect(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.border, lineWidth: 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(title)
        .accessibilityValue(Text(value, format: .percent.precision(.fractionLength(0))) + Text(", \(detail)") + Text(alert ? ", alerte" : ""))
    }
}

/// Courbe des dernières mesures (0…1).
struct Sparkline: View {
    let values: [Double]
    var body: some View {
        GeometryReader { g in
            Path { p in
                guard values.count > 1 else { return }
                let step = g.size.width / CGFloat(values.count - 1)
                for (i, v) in values.enumerated() {
                    let pt = CGPoint(x: CGFloat(i) * step, y: g.size.height * (1 - CGFloat(min(max(v, 0), 1))))
                    if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
                }
            }
            .stroke(Theme.textSecondary, style: StrokeStyle(lineWidth: 1.5, lineJoin: .round))
        }
        .accessibilityHidden(true)
    }
}
