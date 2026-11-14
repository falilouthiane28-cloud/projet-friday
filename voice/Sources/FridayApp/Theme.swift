import SwiftUI

/// Tokens de `design-system/friday-ai/MASTER.md` (v2 monochrome). Hex opaques, jamais d'opacité sur le texte.
enum Theme {
    static let surface0 = Color(hex: 0x000000)
    static let surface1 = Color(hex: 0x0A0A0A)
    static let surface2 = Color(hex: 0x141414)
    static let surface3 = Color(hex: 0x1C1C1E)
    static let surface4 = Color(hex: 0x2C2C2E)

    static let textPrimary = Color(hex: 0xFFFFFF)
    static let textSecondary = Color(hex: 0x999999)    // 7,4:1 sur #000
    static let textTertiary = Color(hex: 0x8C8C8C)     // 6,3:1 sur #000 — jamais sur surface 4

    static let divider = Color(hex: 0x1A1A1A)
    static let border = Color(hex: 0x262626)
    static let borderField = Color(hex: 0x4D4D4D)
    static let focusRing = Color(hex: 0xD9D9D9)
    static let handle = Color(hex: 0x7A7A7A)

    static let success = Color(hex: 0x34C759)
    static let warning = Color(hex: 0xFFD60A)
    static let error = Color(hex: 0xFF453A)

    static let eye = Color.white.opacity(0.95)
    static let helmet = Color(hex: 0x0A0A0A)

    static let spring = Animation.spring(response: 0.3, dampingFraction: 0.7)
}

/// Verre Liquid Glass, remplacé par une surface opaque quand « Réduire la transparence » est actif.
struct GlassSurface: ViewModifier {
    var radius: CGFloat
    var tint: Color? = nil
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.colorSchemeContrast) private var contrast

    func body(content: Content) -> some View {
        if reduceTransparency {
            content
                .background(Theme.surface3, in: .rect(cornerRadius: radius))
                .overlay(RoundedRectangle(cornerRadius: radius).strokeBorder(contrast == .increased ? Theme.borderField : Theme.border))
        } else {
            content.glassEffect(.regular.tint(tint), in: .rect(cornerRadius: radius))
        }
    }
}

/// Texte tertiaire : #8C8C8C, ou #B3B3B3 (10:1) avec « Augmenter le contraste ».
struct TertiaryStyle: ViewModifier {
    @Environment(\.colorSchemeContrast) private var contrast
    func body(content: Content) -> some View {
        content.foregroundStyle(contrast == .increased ? Color(hex: 0xB3B3B3) : Theme.textTertiary)
    }
}

extension View {
    func glassSurface(radius: CGFloat, tint: Color? = nil) -> some View { modifier(GlassSurface(radius: radius, tint: tint)) }
    func tertiaryText() -> some View { modifier(TertiaryStyle()) }
}

extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}

extension Font {
    static let fTitle1 = Font.system(size: 28, weight: .bold)
    static let fTitle2 = Font.system(size: 22, weight: .semibold)
    static let fHeadline = Font.system(size: 15, weight: .semibold)
    static let fBody = Font.system(size: 15)
    static let fCallout = Font.system(size: 14)
    static let fCaption = Font.system(size: 12, weight: .medium)
    static let fMono = Font.system(size: 13, weight: .medium, design: .monospaced)
}

/// Bouton plein (surface 3) : hover un niveau au-dessus, pressé = scale 0.98.
struct SurfaceButtonStyle: ButtonStyle {
    var radius: CGFloat = 8
    @State private var hover = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.fCaption)
            .foregroundStyle(Theme.textPrimary)
            .padding(.horizontal, 14)
            .frame(minHeight: 32)
            .background(hover ? Theme.surface4 : Theme.surface3, in: .rect(cornerRadius: radius))
            .overlay(RoundedRectangle(cornerRadius: radius).strokeBorder(Theme.border, lineWidth: 1))
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.1), value: configuration.isPressed)
            .onHover { hover = $0 }
            .contentShape(.rect(cornerRadius: radius))
    }
}
