import SwiftUI

/// Overlay state machine, driven by `OverlayController`. PR 13 ships the
/// loading/match/no-match/error transitions; the real market-card visuals
/// land in PR 9 (design-system port).
enum OverlayStatus: Equatable {
    case searching
    case matched(MatchedMarket, score: Double)
    case noMatch(threshold: Double)
    case error(String)
}

struct OverlayView: View {
    let selection: Selection
    let status: OverlayStatus

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            header

            Text(selection.highlight)
                .font(.system(size: 13, weight: .regular))
                .lineLimit(2)
                .truncationMode(.tail)
                .foregroundStyle(.secondary)

            statusRow

            if let title = selection.pageTitle, !title.isEmpty {
                Text(title)
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
        }
        .padding(14)
        .frame(width: 340, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(.regularMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(Color.primary.opacity(0.08), lineWidth: 0.5)
                )
        )
    }

    private var header: some View {
        HStack(spacing: 6) {
            Image(systemName: "bolt.fill")
                .foregroundStyle(.yellow)
            Text("Speedy")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.secondary)
            Spacer(minLength: 0)
            Text(selection.source.rawValue)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.tertiary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.secondary.opacity(0.12), in: Capsule())
        }
    }

    @ViewBuilder
    private var statusRow: some View {
        switch status {
        case .searching:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Searching markets…")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

        case let .matched(market, score):
            VStack(alignment: .leading, spacing: 4) {
                Text(market.question)
                    .font(.system(size: 14, weight: .semibold))
                    .lineLimit(2)
                    .truncationMode(.tail)
                HStack(spacing: 6) {
                    if let category = market.category, !category.isEmpty {
                        Text(category)
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.12), in: Capsule())
                    }
                    Text(String(format: "score %.2f", score))
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(.tertiary)
                }
            }

        case let .noMatch(threshold):
            Text(String(format: "No tradeable market (threshold %.2f).", threshold))
                .font(.system(size: 12))
                .foregroundStyle(.secondary)

        case let .error(message):
            Text(message)
                .font(.system(size: 11))
                .foregroundStyle(.red)
                .lineLimit(2)
        }
    }
}
