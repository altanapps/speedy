import SwiftUI

/// Overlay state machine, driven by `OverlayController`. The four states
/// each render a distinct Speedy visual:
///
/// - `.searching` — attribution bar + a hairline pulse and "scanning…"
/// - `.matched`   — full trading-cursor card (header / source row / question
///                  / price). Trade controls (Yes/No, size, confirm) are
///                  intentionally omitted; the trade-flow agent appends
///                  them in a follow-up PR.
/// - `.noMatch`   — honest empty state per voice spec ("No tradeable
///                  market found.")
/// - `.error`     — same chrome, a red one-liner.
///
/// Visual reference: `claude-design/Trading Cursor.html` + the hero
/// preview in `claude-design/Speedy Design System.html` §08.
enum OverlayStatus: Equatable {
    case searching
    case matched(MatchedMarket, score: Double)
    case noMatch(threshold: Double)
    case error(String)
}

struct OverlayView: View {
    let selection: Selection
    let status: OverlayStatus

    /// Trade overlay width per `DESIGN.md §8` and `app.jsx` (`width:300`,
    /// rounded up to the design system's documented 320pt). Height is
    /// intrinsic — the controller reads `hosting.fittingSize` and sizes
    /// the panel to whatever this view computes.
    private static let overlayWidth: CGFloat = 320

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            attributionBar

            Divider().background(Speedy.ColorToken.separator)

            switch status {
            case .searching:
                searchingBody
            case let .matched(market, score):
                matchedBody(market: market, score: score)
            case let .noMatch(threshold):
                noMatchBody(threshold: threshold)
            case let .error(message):
                errorBody(message: message)
            }
        }
        .frame(width: Self.overlayWidth, alignment: .leading)
        .background(panelBackground)
        .overlay(panelStroke)
        .clipShape(RoundedRectangle(cornerRadius: Speedy.Radius.lg, style: .continuous))
        // Layered shadow per DESIGN.md §7 — outer ambient + closer drop.
        .shadow(color: .black.opacity(0.45), radius: 30, x: 0, y: 24)
        .shadow(color: .black.opacity(0.25), radius: 10, x: 0, y: 8)
        // The panel itself is dark glass; force the dark scheme so SwiftUI
        // primitives (`Divider`, system materials) render their dark
        // variant even if the host app is light.
        .environment(\.colorScheme, .dark)
    }

    // MARK: - Chrome

    /// `.regularMaterial` supplies the blur; the `matTint` overlay nudges
    /// the result toward the design system's slightly darker glass. Reduce
    /// Transparency callers fall through to a solid `bgElevated`.
    private var panelBackground: some View {
        RoundedRectangle(cornerRadius: Speedy.Radius.lg, style: .continuous)
            .fill(.regularMaterial)
            .overlay(
                RoundedRectangle(cornerRadius: Speedy.Radius.lg, style: .continuous)
                    .fill(Speedy.ColorToken.matTint)
            )
    }

    private var panelStroke: some View {
        RoundedRectangle(cornerRadius: Speedy.Radius.lg, style: .continuous)
            .strokeBorder(Speedy.ColorToken.separatorStrong, lineWidth: 0.5)
    }

    // MARK: - Attribution bar (top of every state)

    /// Mirrors the React `TradePanel` attribution row: brand mark + SPEEDY
    /// wordmark on the left, hotkey hint on the right. JetBrains Mono.
    private var attributionBar: some View {
        HStack {
            HStack(spacing: 6) {
                SpeedyMark(size: 11)
                Text("SPEEDY")
                    .font(Speedy.Font.mono(10, weight: .medium))
                    .tracking(1.0) // ~0.04em at 10pt
                    .foregroundStyle(Speedy.ColorToken.labelTertiary)
            }
            Spacer(minLength: 0)
            // Right-side hint: just `esc` for now. The trade-flow agent
            // will add `⌘⏎ confirm · esc` once there's a confirm action.
            Text("esc")
                .font(Speedy.Font.mono(10))
                .foregroundStyle(Speedy.ColorToken.labelQuaternary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
    }

    // MARK: - States

    /// Searching: a thin pulse + the highlighted text the user actually
    /// selected, so they know which selection Speedy is working on.
    private var searchingBody: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                ScanningDot()
                Text("scanning markets…")
                    .font(Speedy.Font.mono(11))
                    .foregroundStyle(Speedy.ColorToken.labelSecondary)
                Spacer()
            }
            highlightExcerpt
            // Reserved breathing room — keeps the searching state visually
            // close to the height of the other states so the panel doesn't
            // jump after a fast match.
            Color.clear.frame(height: 4)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    /// Matched: the canonical card from `app.jsx` — source row, question,
    /// price row. NO trade controls (Yes/No / size / confirm) by design;
    /// the trade-flow agent appends them in a follow-up.
    private func matchedBody(market: MatchedMarket, score: Double) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sourceRow(market: market, score: score)

            Text(market.question)
                .font(Speedy.Font.inter(13.5, weight: .semibold))
                .tracking(-0.13) // ~-0.01em at 13.5pt
                .foregroundStyle(Speedy.ColorToken.label)
                .lineSpacing(2)
                .lineLimit(3)
                .truncationMode(.tail)
                .fixedSize(horizontal: false, vertical: true)

            // Reserved trade-controls slot. Empty today; trade-flow agent
            // fills it. Sized so the matched state has visible breathing
            // room, signalling that something belongs here.
            Color.clear.frame(height: 8)
        }
        .padding(.horizontal, 14)
        .padding(.top, 11)
        .padding(.bottom, 12)
    }

    private func noMatchBody(threshold: Double) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                NoMatchDot()
                Text("No tradeable market found.")
                    .font(Speedy.Font.inter(12, weight: .medium))
                    .foregroundStyle(Speedy.ColorToken.label)
                Spacer()
            }
            highlightExcerpt
            Text(String(format: "below match threshold (%.2f)", threshold))
                .font(Speedy.Font.mono(10))
                .foregroundStyle(Speedy.ColorToken.labelTertiary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private func errorBody(message: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Circle()
                    .fill(Speedy.ColorToken.red)
                    .frame(width: 6, height: 6)
                Text("Couldn't search.")
                    .font(Speedy.Font.inter(12, weight: .semibold))
                    .foregroundStyle(Speedy.ColorToken.label)
                Spacer()
            }
            Text(message)
                .font(Speedy.Font.inter(11))
                .foregroundStyle(Speedy.ColorToken.labelSecondary)
                .lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    // MARK: - Components

    /// PRED · POLYMARKET · "…excerpt…"  — the row directly under the
    /// attribution bar in the matched state.
    private func sourceRow(market: MatchedMarket, score: Double) -> some View {
        HStack(spacing: 6) {
            MarketBadge(kind: .prediction)
            Text("POLYMARKET")
                .font(Speedy.Font.mono(10, weight: .medium))
                .tracking(0.4)
                .foregroundStyle(Speedy.ColorToken.labelTertiary)

            Spacer(minLength: 6)

            // Score — tiny mono, right-aligned. Useful for debugging the
            // match quality without yelling. `.foregroundColor` (not
            // `.foregroundStyle`) because `Text + Text` concatenation
            // needs the macOS 13 API.
            (
                Text(String(format: "%.0f", score * 100))
                    .foregroundColor(Speedy.ColorToken.labelTertiary)
                + Text("%")
                    .foregroundColor(Speedy.ColorToken.labelQuaternary)
            )
            .font(Speedy.Font.mono(9.5, weight: .medium))
        }
    }

    /// The "…highlight…" excerpt pill — purple-tinted background, italic.
    private var highlightExcerpt: some View {
        HStack(spacing: 4) {
            Text("\u{201C}")
                .font(Speedy.Font.inter(11))
                .foregroundStyle(Speedy.ColorToken.labelTertiary)
            Text(selection.highlight)
                .font(Speedy.Font.inter(11))
                .italic()
                .foregroundStyle(Speedy.ColorToken.labelSecondary)
                .lineLimit(1)
                .truncationMode(.middle)
            Text("\u{201D}")
                .font(Speedy.Font.inter(11))
                .foregroundStyle(Speedy.ColorToken.labelTertiary)
        }
        .padding(.horizontal, 7)
        .padding(.vertical, 3)
        .background(
            RoundedRectangle(cornerRadius: 5, style: .continuous)
                .fill(Speedy.ColorToken.purpleSubtle)
                .overlay(
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .strokeBorder(Speedy.ColorToken.purpleTint, lineWidth: 0.5)
                )
        )
    }
}

// MARK: - Speedy mark

/// The 11px brand mark used in the attribution bar — a small purple
/// rounded square with a white lightning bolt. Mirrors the `<SpeedyMark>`
/// component in `app.jsx` (and the larger `.speedy-tile` from the design
/// system, scaled down).
private struct SpeedyMark: View {
    let size: CGFloat

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            Color(hex: 0x8E72FF),
                            Speedy.ColorToken.purple,
                            Color(hex: 0x5E3FE0)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
                        .strokeBorder(Color.black.opacity(0.4), lineWidth: 0.5)
                )

            BoltShape()
                .fill(Color.white)
                .frame(width: size * 0.62, height: size * 0.62)
        }
        .frame(width: size, height: size)
    }
}

/// The lightning-bolt path from the design system SVG, normalised to a
/// 24×24 box.
private struct BoltShape: Shape {
    func path(in rect: CGRect) -> Path {
        let s = min(rect.width, rect.height) / 24.0
        var p = Path()
        // M14 2 L4 14 H11 L10 22 L20 10 H13 L14 2 Z
        p.move(to:    CGPoint(x: 14*s, y: 2*s))
        p.addLine(to: CGPoint(x:  4*s, y: 14*s))
        p.addLine(to: CGPoint(x: 11*s, y: 14*s))
        p.addLine(to: CGPoint(x: 10*s, y: 22*s))
        p.addLine(to: CGPoint(x: 20*s, y: 10*s))
        p.addLine(to: CGPoint(x: 13*s, y: 10*s))
        p.addLine(to: CGPoint(x: 14*s, y:  2*s))
        p.closeSubpath()
        return p
    }
}

// MARK: - Market badge

/// PRED / STOCK / PERP / COMM badge — the small uppercase mono pill from
/// design system §07 (`.market-badge`). Today the overlay only ever shows
/// PRED (Polymarket-only backend), but the type is designed for the day
/// we add stocks/perps.
private struct MarketBadge: View {
    enum Kind {
        case prediction, stock, perp, commodity

        var label: String {
            switch self {
            case .prediction: return "PRED"
            case .stock:      return "STOCK"
            case .perp:       return "PERP"
            case .commodity:  return "COMM"
            }
        }

        var fill: Color {
            switch self {
            case .prediction: return Speedy.ColorToken.badgePred
            case .stock:      return Speedy.ColorToken.badgeStock
            case .perp:       return Speedy.ColorToken.badgePerp
            case .commodity:  return Speedy.ColorToken.badgeComm
            }
        }
    }

    let kind: Kind

    var body: some View {
        Text(kind.label)
            .font(Speedy.Font.mono(9.5, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(Color(hex: 0x0E0E10))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(
                RoundedRectangle(cornerRadius: 3, style: .continuous)
                    .fill(kind.fill)
            )
    }
}

// MARK: - Status indicators

/// Pulsing purple dot for the `.searching` state.
private struct ScanningDot: View {
    @State private var pulse = false

    var body: some View {
        Circle()
            .fill(Speedy.ColorToken.purple)
            .frame(width: 6, height: 6)
            .opacity(pulse ? 0.45 : 1.0)
            .scaleEffect(pulse ? 1.25 : 1.0)
            .onAppear {
                withAnimation(
                    .easeInOut(duration: 0.6).repeatForever(autoreverses: true)
                ) { pulse = true }
            }
    }
}

/// Static muted dot for the `.noMatch` state — same footprint as
/// `ScanningDot` so the layouts read as related.
private struct NoMatchDot: View {
    var body: some View {
        Circle()
            .strokeBorder(Speedy.ColorToken.labelTertiary, lineWidth: 1)
            .frame(width: 6, height: 6)
    }
}
