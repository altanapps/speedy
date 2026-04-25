import AppKit
import SwiftUI

/// Owns the floating overlay panel: lifecycle, placement, and dismissal.
///
/// One panel is reused across hotkey fires — cheaper than recreating, and the
/// reuse path also handles "user double-taps Control while the overlay is
/// already up" correctly (we just reposition with the new selection).
@MainActor
final class OverlayController {
    /// Initial panel size before SwiftUI tells us its real intrinsic size.
    /// Just needs to be non-zero so NSHostingView has a valid contentRect to
    /// lay out in; it gets resized on every show().
    private static let initialSize = CGSize(width: 320, height: 140)
    private static let idleTimeout: TimeInterval = 8.0

    private var panel: OverlayPanel?
    private var hostingView: NSHostingView<OverlayView>?

    private var keyMonitor: Any?
    private var clickMonitor: Any?
    private var idleTimer: Timer?

    func show(_ selection: Selection) {
        let panel = panel ?? makePanel()
        self.panel = panel

        let view = OverlayView(selection: selection)
        let hosting: NSHostingView<OverlayView>
        if let hostingView {
            hostingView.rootView = view
            hosting = hostingView
        } else {
            hosting = NSHostingView(rootView: view)
            panel.contentView = hosting
            hostingView = hosting
        }

        // Let SwiftUI dictate the content size — fixed `.frame(width: 320)` in
        // OverlayView and intrinsic height from the text. Forcing a hardcoded
        // size here disagreed with SwiftUI's intrinsic height and caused
        // layout recursion (-layoutSubtreeIfNeeded inside layout).
        let size = hosting.fittingSize
        panel.setContentSize(size)
        let origin = computeOrigin(panelSize: panel.frame.size)
        panel.setFrameOrigin(origin)
        panel.orderFrontRegardless()

        installDismissMonitors()
        restartIdleTimer()
    }

    func dismiss() {
        idleTimer?.invalidate()
        idleTimer = nil
        removeDismissMonitors()
        panel?.orderOut(nil)
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

        // Esc dismisses. Local first so the panel-key path works; global so we
        // catch Esc when focus stayed in the source app (which it does, since
        // the panel is non-activating).
        let keyHandler: (NSEvent) -> Void = { [weak self] event in
            // 53 = kVK_Escape
            if event.keyCode == 53 {
                Task { @MainActor in self?.dismiss() }
            }
        }
        keyMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: [.keyDown], handler: keyHandler
        )

        // Click outside the panel dismisses. Local clicks (i.e. on the panel
        // itself) are explicitly allowed through.
        let clickHandler: (NSEvent) -> Void = { [weak self] event in
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
