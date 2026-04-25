import AppKit
import ApplicationServices

/// Title-of-the-thing-the-user-is-looking-at. Server-side retrieval treats
/// this as a weak signal that's free to include.
enum WindowInfo {
    /// Best-effort: focused window title via the AX tree, falling back to the
    /// frontmost app's localized name. Returns nil only if there's no
    /// frontmost app at all (rare — usually the loginwindow is "frontmost").
    static func frontmostTitle() -> String? {
        guard let app = NSWorkspace.shared.frontmostApplication else { return nil }
        let pid = app.processIdentifier
        if let axTitle = focusedWindowTitle(pid: pid), !axTitle.isEmpty {
            // App name is more useful than a bare window title that might just
            // say "Untitled" or be empty. Combine when we have both.
            if let appName = app.localizedName, !appName.isEmpty {
                return "\(appName) — \(axTitle)"
            }
            return axTitle
        }
        return app.localizedName
    }

    private static func focusedWindowTitle(pid: pid_t) -> String? {
        let appElement = AXUIElementCreateApplication(pid)
        var windowRef: CFTypeRef?
        let windowStatus = AXUIElementCopyAttributeValue(
            appElement, kAXFocusedWindowAttribute as CFString, &windowRef
        )
        guard windowStatus == .success, let windowRef else { return nil }
        let window = windowRef as! AXUIElement

        var titleRef: CFTypeRef?
        let titleStatus = AXUIElementCopyAttributeValue(
            window, kAXTitleAttribute as CFString, &titleRef
        )
        guard titleStatus == .success else { return nil }
        return titleRef as? String
    }
}
