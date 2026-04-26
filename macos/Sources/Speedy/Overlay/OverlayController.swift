import AppKit
import SwiftUI

/// Owns the floating overlay panel: lifecycle, placement, dismissal, the
/// in-flight search, and (PR 10–12) order submission.
///
/// One panel is reused across hotkey fires. A fresh fire cancels any
/// previous search-in-flight before kicking off a new one — otherwise a slow
/// /search response from a previous selection could land on top of the
/// current selection's panel and confuse the user.
@MainActor
final class OverlayController {
    private static let initialSize = CGSize(width: 340, height: 140)
    private static let idleTimeout: TimeInterval = 8.0
    private static let defaultSizeUSDC = "5"

    private let searchClient: SearchClient
    private let orderClient: OrderClient

    private var panel: OverlayPanel?
    private var hostingView: NSHostingView<OverlayView>?

    private var searchTask: Task<Void, Never>?
    private var orderTask: Task<Void, Never>?
    private var keyMonitor: Any?
    private var localKeyMonitor: Any?
    private var clickMonitor: Any?
    private var idleTimer: Timer?

    // Per-show trade state. Reset on each `show(_:)` call.
    private var currentSelection: Selection?
    private var matchedMarket: MatchedMarket?
    private var outcome: OrderRequest.Outcome = .yes
    private var sizeText: String = OverlayController.defaultSizeUSDC

    /// Top-left anchor of the panel, pinned on first render of each
    /// `show()`. Subsequent re-renders reuse it so the panel doesn't chase
    /// the cursor *and* doesn't visually jump when its height reflows
    /// (typing in the size field, toggling Yes/No, status change). We pin
    /// top-left rather than bottom-left because macOS panels grow downward
    /// from a fixed top — pinning the bottom would make the top edge bob
    /// up/down as content height changes.
    private var pinnedTopLeft: CGPoint?

    init(searchClient: SearchClient, orderClient: OrderClient) {
        self.searchClient = searchClient
        self.orderClient = orderClient
    }

    func show(_ selection: Selection) {
        searchTask?.cancel()
        orderTask?.cancel()
        currentSelection = selection
        matchedMarket = nil
        outcome = .yes
        sizeText = Self.defaultSizeUSDC
        pinnedTopLeft = nil  // re-anchor on the first render of this show()

        render(status: .searching)
        installDismissMonitors()
        restartIdleTimer()

        searchTask = Task { [weak self, searchClient] in
            do {
                let outcome = try await searchClient.search(selection)
                guard !Task.isCancelled else { return }
                guard let self else { return }
                switch outcome {
                case let .matched(market, score, _):
                    self.matchedMarket = market
                    self.render(status: .matched(market, score: score))
                case let .noMatch(_, threshold):
                    self.render(status: .noMatch(threshold: threshold))
                }
            } catch let error as SearchError {
                guard !Task.isCancelled else { return }
                self?.render(status: .error(Self.describe(error)))
            } catch {
                guard !Task.isCancelled else { return }
                self?.render(status: .error(error.localizedDescription))
            }
        }
    }

    /// Render an arbitrary selection + status without hitting the backend.
    /// Used by the menu-bar "Preview overlay" debug menu so visuals can be
    /// checked without AX trust or a real search round-trip.
    func showPreview(selection: Selection, status: OverlayStatus) {
        searchTask?.cancel()
        currentSelection = selection
        pinnedTopLeft = nil  // re-anchor on the first render of this preview
        // Keep matchedMarket in sync if previewing a matched state, so
        // TradeControls bind correctly in preview mode too.
        if case let .matched(market, _) = status {
            matchedMarket = market
        } else {
            matchedMarket = nil
        }
        render(status: status)
        installDismissMonitors()
        restartIdleTimer()
    }

    func dismiss() {
        searchTask?.cancel()
        searchTask = nil
        orderTask?.cancel()
        orderTask = nil
        idleTimer?.invalidate()
        idleTimer = nil
        removeDismissMonitors()
        panel?.orderOut(nil)
        pinnedTopLeft = nil
    }

    // MARK: - Order submission

    /// Triggered by the Buy button or ⌘↵. No-ops unless we're in a matched
    /// state with a valid size and no order already in flight.
    func submitOrder() {
        guard orderTask == nil else { return }
        guard let market = matchedMarket else { return }
        guard let size = Self.parseSize(sizeText) else { return }

        // Cancelling search is fine — even if it's still running, we already
        // have the matched market. Keep the idle timer alive so a successful
        // place still auto-dismisses after the timeout.
        let request = OrderRequest(
            marketId: market.id,
            outcome: outcome,
            sizeUsdc: size,
            side: .buy
        )
        render(status: .placing)
        restartIdleTimer()

        orderTask = Task { [weak self, orderClient] in
            defer { Task { @MainActor in self?.orderTask = nil } }
            do {
                let response = try await orderClient.placeOrder(request)
                guard !Task.isCancelled else { return }
                let id = response.orderId ?? response.transactionHash ?? "?"
                self?.render(status: .placed(orderId: id))
            } catch let error as OrderError {
                guard !Task.isCancelled else { return }
                self?.render(status: .orderError(Self.describe(error)))
            } catch {
                guard !Task.isCancelled else { return }
                self?.render(status: .orderError(error.localizedDescription))
            }
        }
    }

    // MARK: - Render

    private func render(status: OverlayStatus) {
        guard let selection = currentSelection else { return }
        let panel = panel ?? makePanel()
        self.panel = panel

        // Build the TradeControlsConfig only when we're actually matched —
        // OverlayView won't render TradeControls otherwise. Bindings are
        // synthesised from this controller's state so toggling Yes/No or
        // editing the size flows back here without SwiftUI @State.
        let config: TradeControlsConfig?
        if case .matched = status {
            config = TradeControlsConfig(
                outcome: Binding(
                    get: { [weak self] in self?.outcome ?? .yes },
                    set: { [weak self] new in
                        self?.outcome = new
                        // Re-render so the segmented control reflects the new state.
                        self?.render(status: status)
                    }
                ),
                sizeText: Binding(
                    get: { [weak self] in self?.sizeText ?? Self.defaultSizeUSDC },
                    set: { [weak self] new in
                        self?.sizeText = new
                        self?.render(status: status)
                    }
                ),
                onSubmit: { [weak self] in self?.submitOrder() }
            )
        } else {
            config = nil
        }

        let view = OverlayView(selection: selection, status: status, tradeControls: config)
        let hosting: NSHostingView<OverlayView>
        if let hostingView {
            hostingView.rootView = view
            hosting = hostingView
        } else {
            hosting = NSHostingView(rootView: view)
            panel.contentView = hosting
            hostingView = hosting
        }

        // Let SwiftUI dictate size — `.frame(width: 340)` plus intrinsic
        // height. Hardcoding here disagreed with SwiftUI's intrinsic size
        // and caused -layoutSubtreeIfNeeded recursion.
        let size = hosting.fittingSize
        panel.setContentSize(size)
        // Pin the *top-left* of the panel. macOS frame origins are
        // bottom-left, so we convert: bottomLeft.y = topLeft.y - height.
        // First render establishes the top-left from the cursor; later
        // re-renders (size field typing, Yes/No toggle, status change)
        // reuse the same top-left, so the panel grows downward without the
        // visible top edge ever moving. Re-anchored on the next show().
        let topLeft: CGPoint
        if let pinned = pinnedTopLeft {
            topLeft = pinned
        } else {
            let bottomLeft = computeOrigin(panelSize: size)
            topLeft = CGPoint(x: bottomLeft.x, y: bottomLeft.y + size.height)
            pinnedTopLeft = topLeft
        }
        let origin = CGPoint(x: topLeft.x, y: topLeft.y - size.height)
        panel.setFrameOrigin(origin)
        panel.orderFrontRegardless()
    }

    private static func describe(_ error: SearchError) -> String {
        switch error {
        case let .transport(message):
            return "Couldn't reach Speedy backend (\(message))"
        case let .http(status):
            return "Backend error (HTTP \(status))"
        case let .decode(message):
            return "Couldn't read backend response (\(message))"
        }
    }

    private static func describe(_ error: OrderError) -> String {
        switch error {
        case let .transport(message):
            return "couldn't reach backend (\(message))"
        case let .http(status, message):
            if let m = message, !m.isEmpty { return "HTTP \(status): \(m)" }
            return "HTTP \(status)"
        case let .decode(message):
            return "bad response (\(message))"
        case let .rejected(message):
            return message
        case let .credentialsMissing(message):
            return message
        }
    }

    private static func parseSize(_ text: String) -> Double? {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard let value = Double(trimmed), value > 0 else { return nil }
        return value
    }

    // MARK: - Panel construction

    private func makePanel() -> OverlayPanel {
        let rect = NSRect(origin: .zero, size: Self.initialSize)
        return OverlayPanel(contentRect: rect)
    }

    // MARK: - Placement

    private func computeOrigin(panelSize: CGSize) -> CGPoint {
        let cursor = NSEvent.mouseLocation
        let screen =
            NSScreen.screens.first(where: { $0.frame.contains(cursor) })
            ?? NSScreen.main
            ?? NSScreen.screens.first
        let frame = screen?.visibleFrame ?? CGRect(x: 0, y: 0, width: 1440, height: 900)
        return OverlayPositioner.panelOrigin(
            cursor: cursor, panelSize: panelSize, in: frame
        )
    }

    // MARK: - Dismissal & key handling

    private func installDismissMonitors() {
        removeDismissMonitors()

        // Esc is the *only* way to dismiss the overlay. Click-outside +
        // idle-timeout were both removed — users were losing the panel
        // mid-edit when they clicked into another app to look something up.
        // ⌘↵ still submits a trade.
        //
        // We install both global and local monitors:
        //   - global catches Esc / ⌘↵ when focus is in Safari (most common)
        //   - local catches them when focus has hopped to Speedy itself
        //     (which happens transiently after an order completes — without
        //     a local monitor, Esc was getting eaten by SwiftUI internals
        //     and the .placed overlay stayed stuck on screen).
        let act: (NSEvent) -> Void = { [weak self] event in
            // 53 = kVK_Escape  → dismiss.
            // 36 = kVK_Return with ⌘ → submit (only meaningful when matched).
            if event.keyCode == 53 {
                Task { @MainActor in self?.dismiss() }
            } else if event.keyCode == 36, event.modifierFlags.contains(.command) {
                Task { @MainActor in self?.submitOrder() }
            }
        }
        keyMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.keyDown], handler: act
        )
        localKeyMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.keyDown]
        ) { event in
            act(event)
            return event
        }
    }

    private func removeDismissMonitors() {
        if let m = keyMonitor {
            NSEvent.removeMonitor(m)
            keyMonitor = nil
        }
        if let m = localKeyMonitor {
            NSEvent.removeMonitor(m)
            localKeyMonitor = nil
        }
        if let m = clickMonitor {
            NSEvent.removeMonitor(m)
            clickMonitor = nil
        }
    }

    /// No-op. The idle auto-dismiss was removed — the overlay only goes
    /// away when the user explicitly hits Esc (or after a successful order
    /// submission, if you wire that elsewhere). Kept the call sites + this
    /// stub so the next behavioral change (e.g. dismiss-on-success) only
    /// touches one place.
    private func restartIdleTimer() {
        idleTimer?.invalidate()
        idleTimer = nil
    }
}
