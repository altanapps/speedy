import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var menuBar: MenuBarController?
    private var hotkey: HotkeyMonitor?
    private var overlay: OverlayController?
    private var permissionPollTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menuBar = MenuBarController()
        self.menuBar = menuBar

        let overlay = OverlayController(
            searchClient: HTTPSearchClient(),
            orderClient: HTTPOrderClient()
        )
        self.overlay = overlay

        // Wire the menu-bar's preview hook so users can see overlay visuals
        // without AX trust or a working hotkey path. Always on for now —
        // makes design QA cheap.
        menuBar.previewOverlay = { [weak overlay] selection, status in
            Task { @MainActor in
                overlay?.showPreview(selection: selection, status: status)
            }
        }

        let hotkey = HotkeyMonitor { [weak menuBar, weak overlay] in
            menuBar?.flash()
            Task { @MainActor in
                guard let selection = await SelectionCapture.capture() else {
                    NSLog("Speedy: hotkey fired — no selection")
                    return
                }
                NSLog(
                    "Speedy: captured via %@ — %@",
                    selection.source.rawValue,
                    selection.highlight.prefix(80) as NSString
                )
                overlay?.show(selection)
            }
        }
        self.hotkey = hotkey

        // Ask for Accessibility on first launch. The prompt is async; the user
        // may grant it later — poll until it flips, then start monitoring.
        let trusted = AccessibilityPermission.requestIfNeeded()
        NSLog("Speedy: launched. AX trusted=%@", trusted ? "yes" : "no")
        if trusted {
            hotkey.start()
        } else {
            startPermissionPoll(hotkey: hotkey)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    private func startPermissionPoll(hotkey: HotkeyMonitor) {
        permissionPollTimer?.invalidate()
        permissionPollTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) {
            [weak self] timer in
            let trusted = AccessibilityPermission.isTrusted
            NSLog("Speedy: AX poll tick — trusted=%@", trusted ? "yes" : "no")
            guard trusted else { return }
            timer.invalidate()
            self?.permissionPollTimer = nil
            hotkey.start()
            NSLog("Speedy: Accessibility granted; hotkey monitor started")
        }
    }
}
