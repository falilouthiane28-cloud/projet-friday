import SwiftUI

/// Œil paramétrique : rectangle arrondi dont le bord supérieur peut s'incliner (colère, tristesse).
struct ParamEye: Shape {
    var width: CGFloat
    var height: CGFloat
    var corner: CGFloat
    var slant: CGFloat          // -1…1 : >0 bord intérieur abaissé (colère), <0 bord extérieur abaissé (tristesse)
    var mirrored: Bool          // œil droit

    var animatableData: AnimatablePair<AnimatablePair<CGFloat, CGFloat>, AnimatablePair<CGFloat, CGFloat>> {
        get { .init(.init(width, height), .init(corner, slant)) }
        set { width = newValue.first.first; height = newValue.first.second
              corner = newValue.second.first; slant = newValue.second.second }
    }

    func path(in rect: CGRect) -> Path {
        let r = CGRect(x: rect.midX - width / 2, y: rect.midY - height / 2, width: width, height: height)
        let c = min(corner, width / 2, height / 2)
        let drop = slant * height * 0.6                 // abaissement du coin intérieur
        let innerIsRight = !mirrored                    // œil gauche : coin intérieur à droite
        let topLeftY = r.minY + (innerIsRight ? max(-drop, 0) : max(drop, 0))
        let topRightY = r.minY + (innerIsRight ? max(drop, 0) : max(-drop, 0))
        var p = Path()
        p.move(to: CGPoint(x: r.minX + c, y: topLeftY))
        p.addLine(to: CGPoint(x: r.maxX - c, y: topRightY))
        p.addQuadCurve(to: CGPoint(x: r.maxX, y: topRightY + c), control: CGPoint(x: r.maxX, y: topRightY))
        p.addLine(to: CGPoint(x: r.maxX, y: r.maxY - c))
        p.addQuadCurve(to: CGPoint(x: r.maxX - c, y: r.maxY), control: CGPoint(x: r.maxX, y: r.maxY))
        p.addLine(to: CGPoint(x: r.minX + c, y: r.maxY))
        p.addQuadCurve(to: CGPoint(x: r.minX, y: r.maxY - c), control: CGPoint(x: r.minX, y: r.maxY))
        p.addLine(to: CGPoint(x: r.minX, y: topLeftY + c))
        p.addQuadCurve(to: CGPoint(x: r.minX + c, y: topLeftY), control: CGPoint(x: r.minX, y: topLeftY))
        p.closeSubpath()
        return p
    }
}

/// Symboles qui remplacent l'œil (couche 2), dessinés dans un carré unité centré.
enum Glyph: String {
    case arcUp, arcDown, heart, star, cross, spiral, alert, circle

    func path(in rect: CGRect) -> Path {
        let s = min(rect.width, rect.height)
        let r = CGRect(x: rect.midX - s / 2, y: rect.midY - s / 2, width: s, height: s)
        func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: r.minX + x * s, y: r.minY + y * s) }
        var p = Path()
        switch self {
        case .arcUp:
            p.move(to: pt(0.1, 0.7)); p.addQuadCurve(to: pt(0.9, 0.7), control: pt(0.5, 0.05))
        case .arcDown:
            p.move(to: pt(0.1, 0.35)); p.addQuadCurve(to: pt(0.9, 0.35), control: pt(0.5, 0.95))
        case .heart:
            p.move(to: pt(0.5, 0.92))
            p.addCurve(to: pt(0.05, 0.35), control1: pt(0.3, 0.75), control2: pt(0.05, 0.6))
            p.addArc(center: pt(0.275, 0.32), radius: 0.225 * s, startAngle: .degrees(180), endAngle: .degrees(0), clockwise: false)
            p.addArc(center: pt(0.725, 0.32), radius: 0.225 * s, startAngle: .degrees(180), endAngle: .degrees(0), clockwise: false)
            p.addCurve(to: pt(0.5, 0.92), control1: pt(0.95, 0.6), control2: pt(0.7, 0.75))
        case .star:
            for i in 0..<10 {
                let a = Double(i) * .pi / 5 - .pi / 2
                let rad = (i % 2 == 0 ? 0.5 : 0.2) * s
                let q = CGPoint(x: r.midX + rad * cos(a), y: r.midY + rad * sin(a))
                i == 0 ? p.move(to: q) : p.addLine(to: q)
            }
            p.closeSubpath()
        case .cross:
            p.move(to: pt(0.15, 0.15)); p.addLine(to: pt(0.85, 0.85))
            p.move(to: pt(0.85, 0.15)); p.addLine(to: pt(0.15, 0.85))
        case .spiral:
            let turns = 2.5
            for i in 0...60 {
                let t = Double(i) / 60
                let a = t * turns * 2 * .pi
                let q = CGPoint(x: r.midX + 0.45 * s * t * cos(a), y: r.midY + 0.45 * s * t * sin(a))
                i == 0 ? p.move(to: q) : p.addLine(to: q)
            }
        case .alert:
            p.move(to: pt(0.5, 0.05)); p.addLine(to: pt(0.97, 0.9)); p.addLine(to: pt(0.03, 0.9)); p.closeSubpath()
        case .circle:
            p.addEllipse(in: r.insetBy(dx: s * 0.05, dy: s * 0.05))
        }
        return p
    }

    var stroked: Bool { [.arcUp, .arcDown, .cross, .spiral].contains(self) }
}

struct GlyphView: View {
    let glyph: Glyph
    var body: some View {
        Canvas { ctx, size in
            let rect = CGRect(origin: .zero, size: size)
            let path = glyph.path(in: rect)
            if glyph.stroked {
                ctx.stroke(path, with: .color(Theme.eye),
                           style: StrokeStyle(lineWidth: size.width * 0.16, lineCap: .round, lineJoin: .round))
            } else {
                ctx.fill(path, with: .color(Theme.eye))
                if glyph == .alert {        // point d'exclamation découpé dans le triangle
                    let s = min(size.width, size.height)
                    var bang = Path()
                    bang.addRoundedRect(in: CGRect(x: size.width / 2 - s * 0.05, y: s * 0.32, width: s * 0.1, height: s * 0.32), cornerSize: CGSize(width: s * 0.05, height: s * 0.05))
                    bang.addEllipse(in: CGRect(x: size.width / 2 - s * 0.055, y: s * 0.7, width: s * 0.11, height: s * 0.11))
                    ctx.blendMode = .destinationOut
                    ctx.fill(bang, with: .color(.black))
                }
            }
        }
    }
}
