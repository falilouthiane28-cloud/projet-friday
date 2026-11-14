import AppKit
import FridayUICore
import FridayVoiceCore
import SwiftUI

/// Panneau flottant non activant : visible sur tous les Spaces et au-dessus des apps plein écran.
final class FloatingPanel: NSPanel {
    init(content: some View) {
        super.init(contentRect: NSRect(origin: .zero, size: OverlayController.bubbleSize),
                   styleMask: [.nonactivatingPanel, .borderless, .fullSizeContentView],
                   backing: .buffered, defer: false)
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        isFloatingPanel = true
        hidesOnDeactivate = false
        isMovableByWindowBackground = true
        backgroundColor = .clear
        isOpaque = false
        hasShadow = true
        let host = NSHostingView(rootView: content)
        host.sizingOptions = []
        contentView = host
    }

    override var canBecomeKey: Bool { true }          // pour la saisie
    override var canBecomeMain: Bool { false }
    override func cancelOperation(_ sender: Any?) {   // Échap : la fenêtre redevient bulle
        MainActor.assumeIsolated { OverlayController.shared.setExpanded(false) }
    }
}

@MainActor
final class OverlayController {
    static let shared = OverlayController()
    static let bubbleSize = NSSize(width: 96, height: 96)
    static let expandedSize = NSSize(width: 380, height: 680)
    private var panel: FloatingPanel?
    private var model: AppModel?

    /// Affiche la bulle (en haut à droite au premier lancement).
    func show(model: AppModel) {
        self.model = model
        if panel == nil {
            let p = FloatingPanel(content: OverlayRoot(model: model))
            if let screen = NSScreen.main?.visibleFrame {
                p.setFrameOrigin(NSPoint(x: screen.maxX - Self.bubbleSize.width - 16, y: screen.maxY - Self.bubbleSize.height - 16))
            }
            panel = p
        }
        panel?.orderFrontRegardless()
    }

    func toggle(model: AppModel) {
        if let panel, panel.isVisible { panel.orderOut(nil) } else { show(model: model) }
    }

    /// Bulle ↔ fenêtre : le coin supérieur droit reste en place, le cadre reste dans l'écran.
    func setExpanded(_ expanded: Bool) {
        guard let panel, let model, model.overlayExpanded != expanded else { return }
        let size = expanded ? Self.expandedSize : Self.bubbleSize
        let old = panel.frame
        var frame = NSRect(x: old.maxX - size.width, y: old.maxY - size.height, width: size.width, height: size.height)
        if let screen = (panel.screen ?? NSScreen.main)?.visibleFrame {
            frame.origin.x = min(max(frame.minX, screen.minX + 8), screen.maxX - size.width - 8)
            frame.origin.y = min(max(frame.minY, screen.minY + 8), screen.maxY - size.height - 8)
        }
        model.overlayExpanded = expanded
        panel.setFrame(frame, display: true, animate: !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion)
        if expanded { panel.makeKey() }
    }
}

/// Racine du panneau : bulle permanente ou fenêtre de conversation.
struct OverlayRoot: View {
    @Bindable var model: AppModel
    var body: some View {
        Group {
            if model.overlayExpanded { OverlayView(model: model) } else { BubbleView(model: model) }
        }
        .preferredColorScheme(.dark)
    }
}

/// Bulle ronde toujours visible : le visage de Friday. Glisser pour déplacer, cliquer pour ouvrir.
struct BubbleView: View {
    @Bindable var model: AppModel
    @State private var hover = false

    var body: some View {
        AvatarView(state: model.avatar, size: 84, audioLevel: model.audioLevel)
            .frame(width: 88, height: 88)
            .glassSurface(radius: 44, tint: .black.opacity(0.6))
            .overlay(Circle().strokeBorder(hover ? Theme.focusRing : Theme.border, lineWidth: hover ? 1.5 : 1))
            .frame(width: 96, height: 96)
            .contentShape(Circle())
            .onHover { hover = $0 }
            .onTapGesture { OverlayController.shared.setExpanded(true) }
            .help("Friday — \(model.statusLabel). Cliquer pour ouvrir, clic droit pour les commandes, glisser pour déplacer.")
            .accessibilityElement()
            .accessibilityLabel("Friday, \(model.avatar.label)")
            .accessibilityHint("Ouvre la conversation")
            .accessibilityAddTraits(.isButton)
            .accessibilityAction { OverlayController.shared.setExpanded(true) }
            .contextMenu { FridayMenuItems(model: model, context: true) }   // clic droit : tout Friday depuis la bulle
    }
}

struct OverlayView: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(spacing: 12) {
            ZStack {
                Capsule().fill(Theme.handle).frame(width: 40, height: 4).accessibilityHidden(true)
                HStack {
                    Menu {
                        FridayMenuItems(model: model)
                    } label: {
                        Image(systemName: "ellipsis.circle").font(.system(size: 16)).frame(width: 28, height: 28).contentShape(.rect)
                    }
                    .menuStyle(.button).buttonStyle(.plain).menuIndicator(.hidden).fixedSize()
                    .foregroundStyle(Theme.textSecondary)
                    .help("Commandes de Friday").accessibilityLabel("Commandes de Friday")
                    Spacer()
                    Button { OverlayController.shared.setExpanded(false) } label: {
                        Image(systemName: "chevron.down.circle").font(.system(size: 16)).frame(width: 28, height: 28).contentShape(.rect)
                    }
                    .buttonStyle(.plain).foregroundStyle(Theme.textSecondary)
                    .help("Réduire en bulle (Échap)").accessibilityLabel("Réduire en bulle")
                }
            }
            .padding(.top, 8)
            AvatarView(state: model.avatar, size: 80, audioLevel: model.audioLevel)
            HStack(spacing: 6) {
                Text("Friday").font(.fHeadline).foregroundStyle(Theme.textPrimary)
                Text("·").foregroundStyle(Theme.textSecondary)
                Image(systemName: "circle.fill").font(.system(size: 6)).foregroundStyle(Theme.textPrimary)
                StateLabel(state: model.avatar, text: model.statusLabel)
            }
            StatusRow(model: model)
            if model.showingMemory {
                MemoryPanel(model: model)
            } else {
                ChatThread(messages: model.messages, thinking: model.isThinking) { model.answerConfirm($0, ok: $1) }
                HStack(spacing: 8) {
                    pill("Rappel", "bell", "Rappelle-moi de ")
                    pill("Tâche", "checkmark.square", "Ajoute la tâche ")
                    pill("Note", "note.text", "Note que ")
                }
                InputBar(model: model, compact: true)
            }
        }
        .padding(.horizontal, 16).padding(.bottom, 16)
        .frame(width: 380, height: 680)
        // Teinte sombre du verre : texte lisible même au-dessus d'une fenêtre claire.
        .glassSurface(radius: 20, tint: .black.opacity(0.6))
        .preferredColorScheme(.dark)
    }

    private func pill(_ title: String, _ icon: String, _ prefix: String) -> some View {
        Button { model.draft = prefix } label: { Label(title, systemImage: icon) }.buttonStyle(SurfaceButtonStyle())
    }
}

/// Ce qui marche, en clair : cerveau et micro (icône + texte, jamais la couleur seule).
struct StatusRow: View {
    let model: AppModel
    var body: some View {
        HStack(spacing: 12) {
            item(model.brainName == nil ? "brain" : "brain.fill",
                 model.needsLogin ? "Claude Code à connecter" : (model.brainName.map { $0 == "local" ? "Réponses locales" : $0 } ?? "Cœur en démarrage"))
            item(model.voiceAvailable ? "mic.fill" : "mic.slash", model.voiceAvailable ? "Micro actif" : "Micro indisponible")
        }
        .font(.fCaption)
        .foregroundStyle(Theme.textSecondary)
        .accessibilityElement(children: .combine)
    }

    private func item(_ icon: String, _ text: String) -> some View {
        Label(text, systemImage: icon).labelStyle(.titleAndIcon).lineLimit(1)
    }
}

struct ChatThread: View {
    let messages: [ChatMessage]
    var thinking = false
    var answer: (Int, Bool) -> Void = { _, _ in }
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(messages) { m in
                        if let c = m.confirm {
                            ConfirmCard(request: c, answer: answer).id(m.id)
                        } else if m.isNotice {
                            Label(m.text, systemImage: "checkmark.circle")
                                .font(.fCaption).foregroundStyle(Theme.textSecondary)
                                .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 12)
                                .id(m.id)
                        } else {
                        HStack {
                            if !m.fromFriday { Spacer(minLength: 40) }
                            Text(Self.render(m.text))
                                .font(.fBody)
                                .textSelection(.enabled)
                                .foregroundStyle(m.fromFriday ? Theme.textSecondary : Theme.textPrimary)
                                .padding(.horizontal, 12).padding(.vertical, 8)
                                .background(m.fromFriday ? Theme.surface2 : Theme.surface3,
                                            in: UnevenRoundedRectangle(topLeadingRadius: 16, bottomLeadingRadius: m.fromFriday ? 4 : 16,
                                                                        bottomTrailingRadius: m.fromFriday ? 16 : 4, topTrailingRadius: 16))
                                .accessibilityLabel((m.fromFriday ? "Friday : " : "Vous : ") + m.text)
                            if m.fromFriday { Spacer(minLength: 40) }
                        }
                        .id(m.id)
                        }
                    }
                    if thinking {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small)
                            Text("Friday réfléchit…").font(.fBody).foregroundStyle(Theme.textSecondary)
                            Spacer()
                        }
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .id("thinking")
                        .accessibilityElement(children: .combine)
                    }
                }
                .padding(.vertical, 4)
            }
            .onChange(of: messages.count) { _, _ in
                withAnimation { proxy.scrollTo(messages.last?.id, anchor: .bottom) }
            }
            .onChange(of: thinking) { _, now in
                if now { withAnimation { proxy.scrollTo("thinking", anchor: .bottom) } }
            }
        }
        .frame(maxHeight: .infinity)
    }

    /// Markdown en ligne des réponses de Claude (gras, italique, code, liens) ; texte brut sinon.
    static func render(_ text: String) -> AttributedString {
        (try? AttributedString(markdown: text, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(text)
    }
}

/// Action Tier 1 : Friday attend l'accord du maître (refus par défaut après 60 s).
struct ConfirmCard: View {
    let request: ConfirmRequest
    let answer: (Int, Bool) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Autorisation requise", systemImage: "lock.shield").font(.fCaption).foregroundStyle(Theme.textSecondary)
            Text(request.summary).font(.fBody).foregroundStyle(Theme.textPrimary).fixedSize(horizontal: false, vertical: true)
            if request.state == .pending {
                HStack(spacing: 8) {
                    Button("Refuser") { answer(request.id, false) }
                        .buttonStyle(SurfaceButtonStyle())
                    Button("Autoriser") { answer(request.id, true) }
                        .buttonStyle(SurfaceButtonStyle())   // pas de raccourci : Entrée ne doit jamais autoriser
                }
            } else {
                Label(request.statusText, systemImage: request.state == .allowed ? "checkmark.circle" : "xmark.circle")
                    .font(.fCaption).foregroundStyle(Theme.textSecondary)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface2, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.textSecondary.opacity(0.5), lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Autorisation requise : \(request.summary). \(request.statusText)")
    }
}

/// « Ce dont Friday se souvient… » : faits mémorisés, oubli en deux temps (Oublier → Oui, oublier).
struct MemoryPanel: View {
    let model: AppModel
    var scrolls = true                                // false : rendu --snapshot (ImageRenderer ignore les ScrollView)

    var body: some View {
        let book = model.memory
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Button { model.cancelForget(); model.showingMemory = false } label: {
                    Label("Conversation", systemImage: "chevron.left")
                }
                .buttonStyle(.plain).foregroundStyle(Theme.textSecondary)
                .help("Revenir à la conversation").accessibilityLabel("Revenir à la conversation")
                Spacer()
            }
            .font(.fCaption)
            Text("Ce dont Friday se souvient").font(.fHeadline).foregroundStyle(Theme.textPrimary)
            if let msg = book.lastMessage {
                Label(msg, systemImage: "checkmark.circle").font(.fCaption).foregroundStyle(Theme.textSecondary)
            }
            if book.facts.isEmpty {
                Text(book.emptyText).font(.fBody).foregroundStyle(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
            } else if scrolls {
                ScrollView { rows(book).padding(.vertical, 4) }.frame(maxHeight: .infinity)
            } else {
                rows(book)
                Spacer()
            }
            Text("Friday ne retient jamais de mot de passe ni de code. Oublier un fait efface aussi la conversation en cours.")
                .font(.fCaption).foregroundStyle(Theme.textSecondary).fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    private func rows(_ book: MemoryBook) -> some View {
        LazyVStack(spacing: 8) {
            ForEach(book.facts) { fact in row(fact, armed: book.armed == fact.id, busy: book.forgetting != nil) }
        }
    }

    private func row(_ fact: MemoryFact, armed: Bool, busy: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(fact.text).font(.fBody).foregroundStyle(Theme.textPrimary).textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) {
                Text([fact.categoryLabel, fact.dayLabel].filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(.fCaption).foregroundStyle(Theme.textSecondary)
                Spacer()
                if armed {
                    Button("Annuler") { model.cancelForget() }.buttonStyle(SurfaceButtonStyle()).fixedSize()
                    Button("Oui, oublier") { model.forgetFact(fact.id) }.buttonStyle(SurfaceButtonStyle()).fixedSize()
                } else {
                    Button { model.forgetFact(fact.id) } label: { Label("Oublier", systemImage: "trash") }
                        .buttonStyle(SurfaceButtonStyle()).disabled(busy)
                        .help("Oublier ce fait").accessibilityLabel("Oublier : \(fact.text)")
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface2, in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .contain)
    }
}
