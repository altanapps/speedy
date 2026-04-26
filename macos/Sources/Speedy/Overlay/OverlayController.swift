import AppKit
import SwiftUI

/// Owns the floating overlay panel: lifecycle, placement, dismissal, and the
/// in-flight search.
///
/// One panel is reused across hotkey fires. A fresh fire cancels any
/// previous search-in-flight before kicking off a new one — otherwise a slow
/// /search response from a previous selection could land on top of the
/// current selection's panel and confuse the user.
@MainActor
final class OverlayController {
    private static let initialSize = CGSize(width: 340, height: 140)
    private static let idleTimeout: TimeInterval = 8.0

    private let searchClient: SearchClient

    private var panel: OverlayPanel?
    private var hostingView: NSHostingView<OverlayView>?

    private var searchTask: Task<Void, Never>?
    private var keyMonitor: Any?
    private var clickMonitor: Any?
    private var idleTimer: Timer?

    init(searchClient: SearchClient) {
        self.searchClient = searchClient
    }

    func show(_ selection: Selection) {
        searchTask?.cancel()
        render(selection: selection, status: .searching)
        installDismissMonitors()
        restartIdleTimer()

        searchTask = Task { [weak self, searchClient] in
            do {
                let outcome = try await searchClient.search(selection)
                guard !Task.isCancelled else { return }
                let status: OverlayStatus = {
                    switch outcome {
                    case let .matched(market, score, _):
                        return .matched(market, score: score)
                    case let .noMatch(_, threshold):
                        return .noMatch(threshold: threshold)
                    }
                }()
                self?.render(selection: selection, status: status)
            } catch let error as SearchError {
                guard !Task.isCancelled else { return }
                self?.render(selection: selection, status: .error(Self.describe(error)))
            } catch {
                guard !Task.isCancelled else { return }
                self?.render(selection: selection, status: .error(error.localizedDescription))
            }
        }
    }

    /// Render an arbitrary selection + status without hitting the backend.
    /// Used by the menu-bar "Preview overlay" debug menu so visuals can be
    /// checked without AX trust or a real search round-trip.
    func showPreview(selection: Selection, status: OverlayStatus) {
        searchTask?.cancel()
        render(selection: selection, status: status)
        installDismissMonitors()
        restartIdleTimer()
    }

    func dismiss() {
        searchTask?.cancel()
        searchTask = nil
        idleTimer?.invalidate()
        idleTimer = nil
        removeDismissMonitors()
        panel?.orderOut(nil)
    }

    // MARK: - Render

    private func render(selection: Selection, status: OverlayStatus) {
        let panel = panel ?? makePanel()
        self.panel = panel

        let view = OverlayView(selection: selection, status: status)
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
        let origin = computeOrigin(panelSize: panel.frame.size)
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

    // MARK: - Dismissal

    private func installDismissMonitors() {
        removeDismissMonitors()

        let keyHandler: (NSEvent) -> Void = { [weak self] event in
            // 53 = kVK_Escape
            if event.keyCode == 53 {
                Task { @MainActor in self?.dismiss() }
            }
        }
        keyMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.keyDown], handler: keyHandler
        )

        let clickHandler: (NSEvent) -> Void = { [weak self] _ in
            guard let self, let panel = self.panel else { return }
            let clickLocation = NSEvent.mouseLocation
            if !panel.frame.contains(clickLocation) {
                Task { @MainActor in self.dismiss() }
            }
        }
        clickMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.leftMouseDown, .rightMouseDown, .otherMouseDown],
            handler: clickHandler
        )
    }

    private func removeDismissMonitors() {
        if let m = keyMonitor {
            NSEvent.removeMonitor(m)
            keyMonitor = nil
        }
        if let m = clickMonitor {
            NSEvent.removeMonitor(m)
            clickMonitor = nil
        }
    }

    private func restartIdleTimer() {
        idleTimer?.invalidate()
        idleTimer = Timer.scheduledTimer(
            withTimeInterval: Self.idleTimeout, repeats: false
        ) { [weak self] _ in
            Task { @MainActor in self?.dismiss() }
        }
    }
}
