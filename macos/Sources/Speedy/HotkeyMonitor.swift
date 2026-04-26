import AppKit
import Foundation

/// Detects a double-tap of the Control key — Speedy's primary trigger.
///
/// Why `flagsChanged` and not `RegisterEventHotKey`: Carbon hotkeys don't fire
/// on bare modifier presses (no character key). We watch modifier transitions
/// at the OS level and run a small state machine.
///
/// The window is 300ms between the *first release* and the *second press* —
/// long enough to feel intentional, short enough that ordinary Control usage
/// (Ctrl-click, Ctrl-key combos) never accidentally fires.
final class HotkeyMonitor {
    private let onFire: () -> Void
    private let doubleTapWindow: TimeInterval
    private var globalMonitor: Any?
    private var localMonitor: Any?

    /// Timestamp of the most recent release of Control-only. `nil` between
    /// resets. A second Control press while this is set & within the window
    /// fires the hotkey.
    private var lastControlUp: Date?

    init(doubleTapWindow: TimeInterval = 0.3, onFire: @escaping () -> Void) {
        self.doubleTapWindow = doubleTapWindow
        self.onFire = onFire
    }

    deinit { stop() }

    func start() {
        stop()
        let handler: (NSEvent) -> Void = { [weak self] event in
            self?.handle(event)
        }
        // Global = events delivered to other apps (i.e. when Speedy is not focused).
        // Local = events delivered to Speedy itself; we still need them so the
        // hotkey works when the user is interacting with Speedy's own window.
        globalMonitor = NSEvent.addGlobalMonitorForEvents(
            matching: .flagsChanged, handler: handler
        )
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .flagsChanged) { event in
            handler(event)
            return event
        }
        NSLog(
            "Speedy: HotkeyMonitor.start() — global=%@ local=%@",
            globalMonitor != nil ? "yes" : "no",
            localMonitor != nil ? "yes" : "no"
        )
    }

    func stop() {
        if let m = globalMonitor {
            NSEvent.removeMonitor(m)
            globalMonitor = nil
        }
        if let m = localMonitor {
            NSEvent.removeMonitor(m)
            localMonitor = nil
        }
        lastControlUp = nil
    }

    private func handle(_ event: NSEvent) {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)

        if flags == .control {
            // Control-only is now held. If we just saw a Control release within
            // the window, this is the second tap — fire and reset.
            let now = Date()
            if let lastUp = lastControlUp, now.timeIntervalSince(lastUp) <= doubleTapWindow {
                lastControlUp = nil
                DispatchQueue.main.async { [weak self] in self?.onFire() }
                return
            }
            // First press of a potential pair — wait for the release.
            lastControlUp = nil
        } else if flags.isEmpty {
            // All modifiers released. Mark Control's release time so the next
            // press (if soon enough and Control-only) completes the double-tap.
            lastControlUp = Date()
        } else {
            // Some other modifier joined (Cmd, Shift, Option) — abort the
            // sequence; the user is doing a real chord, not double-tap-Control.
            lastControlUp = nil
        }
    }
}
