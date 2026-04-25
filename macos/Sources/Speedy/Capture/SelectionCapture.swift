import Foundation

/// Glue between the hotkey trigger and the two reader strategies.
///
/// Runs on the main actor: AX calls are happiest there, and so is reading the
/// frontmost window title via NSWorkspace. The pasteboard fallback hops to a
/// background task because it sleeps waiting for the synthetic ⌘C to land.
enum SelectionCapture {
    @MainActor
    static func capture() async -> Selection? {
        if let selection = AXSelectionReader.read() {
            return selection
        }

        let highlight = await Task.detached(priority: .userInitiated) {
            PasteboardSelectionReader.read()
        }.value
        guard let highlight, !highlight.isEmpty else { return nil }

        return Selection(
            highlight: highlight,
            surroundingContext: nil,
            pageTitle: WindowInfo.frontmostTitle(),
            source: .pasteboard
        )
    }
}
