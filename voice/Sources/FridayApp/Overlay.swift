import AppKit
import FridayUICore
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
            .help("Friday — \(model.avatar.label). Cliquer pour ouvrir, glisser pour déplacer.")
            .accessibilityElement()
            .accessibilityLabel("Friday, \(model.avatar.label)")
            .accessibilityHint("Ouvre la conversation")
            .accessibilityAddTraits(.isButton)
            .accessibilityAction { OverlayController.shared.setExpanded(true) }
    }
}

struct OverlayView: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(spacing: 12) {
            ZStack {
                Capsule().fill(Theme.handle).frame(width: 40, height: 4).accessibilityHidden(true)
                HStack {
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
                StateLabel(state: model.avatar)
            }
            ChatThread(messages: model.messages)
            HStack(spacing: 8) {
                pill("Rappel", "bell", "Rappelle-moi de ")
                pill("Tâche", "checkmark.square", "Ajoute la tâche ")
                pill("Note", "note.text", "Note que ")
            }
            InputBar(model: model, compact: true)
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

struct ChatThread: View {
    let messages: [ChatMessage]
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(messages) { m in
                        HStack {
                            if !m.fromFriday { Spacer(minLength: 40) }
                            Text(m.text)
                                .font(.fBody)
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
                .padding(.vertical, 4)
            }
            .onChange(of: messages.count) { _, _ in
                withAnimation { proxy.scrollTo(messages.last?.id, anchor: .bottom) }
            }
        }
        .frame(maxHeight: .infinity)
    }
}
