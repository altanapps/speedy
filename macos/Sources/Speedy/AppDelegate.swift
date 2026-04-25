import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var menuBar: MenuBarController?
    private var hotkey: HotkeyMonitor?
    private var permissionPollTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menuBar = MenuBarController()
        self.menuBar = menuBar

        let hotkey = HotkeyMonitor { [weak menuBar] in
            menuBar?.flash()
            NSLog("Speedy: hotkey fired")
        }
        self.hotkey = hotkey

        // Ask for Accessibility on first launch. The prompt is async; the user
        // may grant it later — poll until it flips, then start monitoring.
        let trusted = AccessibilityPermission.requestIfNeeded()
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
