import SwiftUI

/// Tiny trading affordance below the matched market card. Deliberately
/// minimal: Yes/No segmented control, USDC size field, Buy button.
///
/// Submission paths:
/// 1. The user clicks "Buy" inside this view.
/// 2. The user presses ⌘↵; `OverlayController`'s global key monitor sees
///    it and calls `submitOrder()` directly. We can't observe global
///    hotkeys from here, so the controller mediates.
struct TradeControls: View {
    @Binding var outcome: OrderRequest.Outcome
    @Binding var sizeText: String
    let onSubmit: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Picker("", selection: $outcome) {
                Text("Yes").tag(OrderRequest.Outcome.yes)
                Text("No").tag(OrderRequest.Outcome.no)
            }
            .pickerStyle(.segmented)
            .labelsHidden()

            HStack(spacing: 6) {
                Text("$")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.secondary)
                TextField("5", text: $sizeText)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 12))
                    .frame(width: 70)
                Text("USDC")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
                Spacer(minLength: 0)
                Button(action: onSubmit) {
                    Text("Buy  ⌘↵")
                        .font(.system(size: 11, weight: .semibold))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!Self.isValidSize(sizeText))
            }
        }
        .padding(.top, 4)
    }

    /// True if the text field parses to a positive number. Used to grey out
    /// the Buy button so we don't fire a guaranteed-422 request.
    static func isValidSize(_ text: String) -> Bool {
        guard let value = Double(text.trimmingCharacters(in: .whitespaces)) else {
            return false
        }
        return value > 0
    }
}
