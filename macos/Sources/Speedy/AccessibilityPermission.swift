import AppKit
import ApplicationServices

/// Wrapper around the macOS Accessibility-trust APIs.
///
/// Speedy needs Accessibility for two things: monitoring global key events
/// (the double-tap-Control hotkey) and reading selected text via the AX tree
/// in PR 7. Both are gated by the same per-app system permission.
enum AccessibilityPermission {
    /// True if the user has already granted Accessibility access to this app.
    /// Cheap to call; safe to poll from a periodic timer.
    static var isTrusted: Bool {
        AXIsProcessTrusted()
    }

    /// Like `isTrusted`, but also asks the system to surface its prompt if the
    /// app isn't trusted yet. Returns the *current* state — the prompt is async
    /// and the user may flip the toggle minutes later.
    @discardableResult
    static func requestIfNeeded() -> Bool {
        let key = "AXTrustedCheckOptionPrompt" as CFString
        let options = [key: true] as CFDictionary
        return AXIsProcessTrustedWithOptions(options)
    }

    /// Open the System Settings pane where the user toggles Accessibility.
    /// Useful from a "permission missing" alert action.
    static func openSettings() {
        if let url = URL(
            string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ) {
            NSWorkspace.shared.open(url)
        }
    }
}
