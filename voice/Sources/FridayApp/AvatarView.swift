import FridayUICore
import SwiftUI

/// Apparence d'un œil : paramétrique (couche 1) ou symbole (couche 2).
enum EyeLook: Equatable {
    case param(w: CGFloat, h: CGFloat, corner: CGFloat = 4, slant: CGFloat = 0)
    case glyph(Glyph, size: CGFloat)
    case loading
}

enum Motion { case blink, pulse, heartbeat, shake, scan, tilt, breathe, tremble, dim, fill, glow, spin, shine, audio, still }

struct Pose {
    var left: EyeLook
    var right: EyeLook
    var offset = CGSize.zero
    var glasses = false
    var motion: Motion = .blink
}

extension AvatarState {
    var pose: Pose {
        switch self {
        case .neutral: Pose(left: .param(w: 22, h: 18), right: .param(w: 22, h: 18))
        case .happy: Pose(left: .glyph(.arcUp, size: 24), right: .glyph(.arcUp, size: 24), motion: .pulse)
        case .love: Pose(left: .glyph(.heart, size: 24), right: .glyph(.heart, size: 24), motion: .heartbeat)
        case .excited: Pose(left: .glyph(.star, size: 26), right: .glyph(.star, size: 26), motion: .shake)
        case .thinking: Pose(left: .param(w: 18, h: 12), right: .param(w: 18, h: 12), offset: CGSize(width: 6, height: -3), motion: .scan)
        case .confused: Pose(left: .param(w: 24, h: 20), right: .param(w: 14, h: 11), motion: .tilt)
        case .sleeping: Pose(left: .param(w: 22, h: 3, corner: 1.5), right: .param(w: 22, h: 3, corner: 1.5), offset: CGSize(width: 0, height: 4), motion: .breathe)
        case .angry: Pose(left: .param(w: 22, h: 15, corner: 3, slant: 0.8), right: .param(w: 22, h: 15, corner: 3, slant: 0.8), motion: .tremble)
        case .sad: Pose(left: .param(w: 20, h: 14, corner: 3, slant: -0.8), right: .param(w: 20, h: 14, corner: 3, slant: -0.8), offset: CGSize(width: 0, height: 4), motion: .dim)
        case .loading: Pose(left: .loading, right: .loading, motion: .fill)
        case .alert: Pose(left: .glyph(.alert, size: 24), right: .glyph(.alert, size: 24), motion: .glow)
        case .wink: Pose(left: .param(w: 22, h: 18), right: .param(w: 22, h: 3, corner: 1.5), motion: .still)
        case .surprised: Pose(left: .glyph(.circle, size: 26), right: .glyph(.circle, size: 26))
        case .dizzy: Pose(left: .glyph(.spiral, size: 24), right: .glyph(.spiral, size: 24), motion: .spin)
        case .shy: Pose(left: .param(w: 16, h: 10, corner: 3), right: .param(w: 16, h: 10, corner: 3), offset: CGSize(width: 0, height: 7))
        case .cool: Pose(left: .param(w: 32, h: 14, corner: 3), right: .param(w: 32, h: 14, corner: 3), glasses: true, motion: .shine)
        case .error: Pose(left: .glyph(.cross, size: 20), right: .glyph(.cross, size: 20), motion: .glow)
        case .listening: Pose(left: .param(w: 26, h: 22, corner: 6), right: .param(w: 26, h: 22, corner: 6), motion: .audio)
        }
    }
}

/// Avatar de Friday : casque, visière, deux yeux LED blancs. Seuls les yeux brillent.
struct AvatarView: View {
    let state: AvatarState
    var size: CGFloat = 180
    var audioLevel: Double = 0                     // 0…1, état « À l'écoute »
    var animated = true                            // false : pose statique (grille au repos)

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let pose = state.pose
        let live = animated && !reduceMotion && pose.motion != .still
        TimelineView(.animation(minimumInterval: 1 / 30, paused: !live)) { tl in
            let t = live ? tl.date.timeIntervalSinceReferenceDate : 0
            let m = MotionFrame(motion: live ? pose.motion : .still, t: t, audio: audioLevel)
            face(pose: pose, m: m)
        }
        .frame(width: 200, height: 200)
        .scaleEffect(size / 200)
        .frame(width: size, height: size)
        .animation(reduceMotion ? .easeInOut(duration: 0.15) : Theme.spring, value: state)
        .accessibilityElement()
        .accessibilityLabel("Friday, \(state.label)")
    }

    private func face(pose: Pose, m: MotionFrame) -> some View {
        ZStack {
            HeadShape().fill(Theme.helmet)
                .overlay(HeadShape().stroke(Color.white.opacity(0.08), lineWidth: 0.5))
            RoundedRectangle(cornerRadius: 12).fill(Color.black)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.06), lineWidth: 0.5))
                .frame(width: 90, height: 45)
                .position(x: 100, y: 92.5)
            Group {
                eye(pose.left, mirrored: false, m: m).position(x: 79, y: 91)
                eye(pose.right, mirrored: true, m: m).position(x: 121, y: 91)
                if pose.glasses { glassesBridge(m: m) }
            }
            .offset(x: pose.offset.width + m.dx, y: pose.offset.height + m.dy)
            .scaleEffect(m.scale, anchor: UnitPoint(x: 0.5, y: 0.455))
            .rotationEffect(.degrees(m.rotation), anchor: UnitPoint(x: 0.5, y: 0.455))
            .opacity(m.opacity)
            .shadow(color: .white.opacity(0.35), radius: 3)
            .mask(RoundedRectangle(cornerRadius: 12).frame(width: 90, height: 45).position(x: 100, y: 92.5))
        }
    }

    @ViewBuilder
    private func eye(_ look: EyeLook, mirrored: Bool, m: MotionFrame) -> some View {
        ZStack {
            switch look {
            case let .param(w, h, corner, slant):
                ParamEye(width: w, height: h * m.blink, corner: corner, slant: slant, mirrored: mirrored)
                    .fill(Theme.eye)
                    .transition(.scale(scale: 0.6).combined(with: .opacity))
            case let .glyph(g, s):
                GlyphView(glyph: g)
                    .frame(width: s, height: s)
                    .rotationEffect(.degrees(m.spin))
                    .id(g)
                    .transition(.scale(scale: 0.4).combined(with: .opacity))
            case .loading:
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3).stroke(Theme.eye, lineWidth: 1.5)
                    RoundedRectangle(cornerRadius: 2).fill(Theme.eye)
                        .frame(width: max(2, 19 * m.progress)).padding(1.5)
                }
                .frame(width: 24, height: 10)
                .transition(.opacity)
            }
        }
        .frame(width: 40, height: 40)
    }

    private func glassesBridge(m: MotionFrame) -> some View {
        ZStack {
            Rectangle().fill(Theme.eye).frame(width: 12, height: 2.5).position(x: 100, y: 88)
            // reflet qui balaie les verres
            LinearGradient(colors: [.clear, .black.opacity(0.55), .clear], startPoint: .leading, endPoint: .trailing)
                .frame(width: 10, height: 18)
                .rotationEffect(.degrees(20))
                .position(x: 60 + 80 * m.shine, y: 91)
                .blendMode(.multiply)
        }
    }
}

/// Valeurs d'animation dérivées du temps (aucun état mutable : rendu déterministe).
struct MotionFrame {
    var dx: CGFloat = 0, dy: CGFloat = 0, scale: CGFloat = 1, rotation: Double = 0
    var opacity: Double = 1, blink: CGFloat = 1, spin: Double = 0, progress: CGFloat = 0.6, shine: CGFloat = 0.3

    init(motion: Motion, t: Double, audio: Double) {
        let s = { (period: Double) in sin(2 * .pi * t / period) }
        switch motion {
        case .blink: blink = MotionFrame.blink(t)
        case .pulse: opacity = 0.88 + 0.12 * s(1.6)
        case .heartbeat: scale = 1 + 0.05 * (1 + s(1.0))
        case .shake: dx = 2 * s(1 / 6)
        case .scan: dx = 4 * s(3); blink = MotionFrame.blink(t)
        case .tilt: rotation = 5 * s(2.5); blink = MotionFrame.blink(t)
        case .breathe: scale = 1 + 0.01 * (1 + s(6))
        case .tremble: dx = 0.8 * s(1 / 12)
        case .dim: opacity = 0.75 + 0.08 * s(3); blink = MotionFrame.blink(t)
        case .fill: progress = CGFloat(t.truncatingRemainder(dividingBy: 1.6) / 1.6)
        case .glow: opacity = 0.65 + 0.35 * (0.5 + 0.5 * s(1.4))   // < 1 Hz, sans flash (WCAG 2.3.1)
        case .spin: spin = (t / 2).truncatingRemainder(dividingBy: 1) * 360
        case .shine: shine = CGFloat((t / 3).truncatingRemainder(dividingBy: 1))
        case .audio: scale = 1 + 0.25 * pow(max(0, min(1, audio)), 0.6); blink = MotionFrame.blink(t)
        case .still: break
        }
    }

    /// Clignement toutes les 4 s ± 1,5 s, durée 150 ms.
    static func blink(_ t: Double) -> CGFloat {
        let k = floor(t / 4)
        let jitter = (sin(k * 12.9898) * 43758.5453).truncatingRemainder(dividingBy: 1) * 1.5
        let at = k * 4 + 2 + jitter
        let d = abs(t - at)
        return d < 0.075 ? CGFloat(max(0.1, d / 0.075)) : 1
    }
}

struct HeadShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: 40, y: 120))
        p.addQuadCurve(to: CGPoint(x: 100, y: 30), control: CGPoint(x: 40, y: 30))
        p.addQuadCurve(to: CGPoint(x: 160, y: 120), control: CGPoint(x: 160, y: 30))
        p.addQuadCurve(to: CGPoint(x: 140, y: 170), control: CGPoint(x: 160, y: 160))
        p.addLine(to: CGPoint(x: 60, y: 170))
        p.addQuadCurve(to: CGPoint(x: 40, y: 120), control: CGPoint(x: 40, y: 160))
        p.closeSubpath()
        return p
    }
}
