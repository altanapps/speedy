import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var menuBar: MenuBarController?
    private var hotkey: HotkeyMonitor?
    private var overlay: OverlayController?
    private var permissionPollTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menuBar = MenuBarController()
        self.menuBar = menuBar

        let overlay = OverlayController(searchClient: HTTPSearchClient())
        self.overlay = overlay

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
            guard AccessibilityPermission.isTrusted else { return }
            timer.invalidate()
            self?.permissionPollTimer = nil
            hotkey.start()
            NSLog("Speedy: Accessibility granted; hotkey monitor started")
        }
    }
}
