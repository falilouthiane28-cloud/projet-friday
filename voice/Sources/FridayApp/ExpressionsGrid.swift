import FridayUICore
import SwiftUI

/// Grille 6×3 des 18 expressions. Pose statique au repos, animée au survol, au focus ou avec « Tout animer ».
struct ExpressionsGridView: View {
    var model: AppModel?
    @State private var animateAll = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                Text("Expressions de Friday").font(.fTitle2).foregroundStyle(Theme.textPrimary)
                Spacer()
                Toggle("Tout animer", isOn: $animateAll).toggleStyle(.switch).foregroundStyle(Theme.textSecondary)
            }
            LazyVGrid(columns: Array(repeating: GridItem(.fixed(160), spacing: 20), count: 6), spacing: 20) {
                ForEach(AvatarState.allCases) { state in
                    ExpressionCell(state: state, animateAll: animateAll) { model?.show(state) }
                }
            }
        }
        .padding(40)
        .background(Theme.surface0)
        .preferredColorScheme(.dark)
    }
}

struct ExpressionCell: View {
    let state: AvatarState
    let animateAll: Bool
    let action: () -> Void
    @State private var hover = false
    @FocusState private var focused: Bool

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                AvatarView(state: state, size: 120, animated: animateAll || hover || focused)
                Text(state.label).font(.fCaption).foregroundStyle(Theme.textSecondary)
            }
            .frame(width: 160, height: 160)
            .background(hover ? Theme.surface3 : Theme.surface2, in: .rect(cornerRadius: 12))
            .contentShape(.rect(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .focused($focused)
        .onHover { hover = $0 }
        .accessibilityLabel(state.label)
        .accessibilityHint("Affiche cette expression sur l'avatar")
    }
}
