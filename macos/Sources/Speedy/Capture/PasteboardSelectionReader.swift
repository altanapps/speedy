import AppKit
import CoreGraphics
import Foundation

/// Last-resort selection capture: synthesise ⌘C, read whatever lands on the
/// pasteboard, restore the user's prior clipboard contents.
///
/// Used when the AX path returns nil/empty — most commonly inside Electron
/// apps (Slack, Notion, Discord, VS Code) where AX doesn't expose
/// `kAXSelectedTextAttribute`. Fundamentally racy: if the user happens to be
/// pasting at the same moment, our restore can clobber their copy. The
/// changeCount-based wait below keeps the window short (typically <30ms in
/// practice).
enum PasteboardSelectionReader {
    private static let pollInterval: useconds_t = 5_000   // 5ms
    private static let pollAttempts = 20                  // ⇒ 100ms cap

    /// Synchronous on purpose — runs on a background queue from the
    /// orchestrator. Returns nil if the synthetic ⌘C didn't produce anything
    /// new, e.g. the user had nothing selected.
    static func read() -> String? {
        let pb = NSPasteboard.general
        let snapshot = takeSnapshot(of: pb)
        let priorChangeCount = pb.changeCount

        synthesiseCopy()

        var attempts = 0
        while pb.changeCount == priorChangeCount, attempts < pollAttempts {
            usleep(pollInterval)
            attempts += 1
        }

        let captured: String?
        if pb.changeCount != priorChangeCount {
            captured = pb.string(forType: .string)
        } else {
            captured = nil
        }

        restore(snapshot, to: pb)

        if let captured, !captured.isEmpty {
            return captured
        }
        return nil
    }

    // MARK: - Snapshot/restore

    private struct Snapshot {
        let items: [[NSPasteboard.PasteboardType: Data]]
    }

    private static func takeSnapshot(of pb: NSPasteboard) -> Snapshot {
        let items = pb.pasteboardItems ?? []
        let captured: [[NSPasteboard.PasteboardType: Data]] = items.map { item in
            var dict: [NSPasteboard.PasteboardType: Data] = [:]
            for type in item.types {
                if let data = item.data(forType: type) {
                    dict[type] = data
                }
            }
            return dict
        }
        return Snapshot(items: captured)
    }

    private static func restore(_ snapshot: Snapshot, to pb: NSPasteboard) {
        pb.clearContents()
        guard !snapshot.items.isEmpty else { return }
        let items: [NSPasteboardItem] = snapshot.items.map { dict in
            let item = NSPasteboardItem()
            for (type, data) in dict {
                item.setData(data, forType: type)
            }
            return item
        }
        pb.writeObjects(items)
    }

    // MARK: - Keystroke synthesis

    /// Posts ⌘C through the HID event tap so it reaches the focused app the
    /// same way a physical keypress would.
    private static func synthesiseCopy() {
        let source = CGEventSource(stateID: .combinedSessionState)
        let cKey: CGKeyCode = 0x08

        let down = CGEvent(keyboardEventSource: source, virtualKey: cKey, keyDown: true)
        down?.flags = .maskCommand
        let up = CGEvent(keyboardEventSource: source, virtualKey: cKey, keyDown: false)
        up?.flags = .maskCommand

        down?.post(tap: .cghidEventTap)
        up?.post(tap: .cghidEventTap)
    }
}
