import AppKit

/// Borderless, non-activating, transparent floating panel.
///
/// `nonactivatingPanel` keeps focus in whatever app the user was reading;
/// `canJoinAllSpaces` + `fullScreenAuxiliary` make it follow the user across
/// Spaces and into full-screen apps. `becomeKey` is overridden so the panel
/// can take keyboard input (Esc, arrow keys later) without stealing app focus.
final class OverlayPanel: NSPanel {
    init(contentRect: NSRect) {
        super.init(
            contentRect: contentRect,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        self.isFloatingPanel = true
        self.level = .floating
        self.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        self.isMovableByWindowBackground = false
        self.hidesOnDeactivate = false
        self.hasShadow = true
        self.isOpaque = false
        self.backgroundColor = .clear
        self.animationBehavior = .utilityWindow
    }

    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
