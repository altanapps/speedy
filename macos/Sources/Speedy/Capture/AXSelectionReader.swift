import ApplicationServices
import Foundation

/// Reads selected text from whatever has keyboard focus, via the macOS
/// Accessibility API.
///
/// This is the *primary* capture path: cleaner than pasteboard hijacking, no
/// race against the user's own clipboard usage, and it can also pull
/// surrounding context from the focused element. The AX implementation is
/// patchy in some apps though — Electron in particular often returns nil for
/// `kAXSelectedTextAttribute`. That's why `SelectionCapture` falls through to
/// the pasteboard reader on nil/empty.
enum AXSelectionReader {
    private static let contextChars = 200

    /// Returns nil if the AX query fails *or* if the resulting highlight is
    /// empty — empty selection isn't a real signal, even if AX answered
    /// "successfully."
    static func read() -> Selection? {
        let systemWide = AXUIElementCreateSystemWide()

        var focusedRef: CFTypeRef?
        let focusedStatus = AXUIElementCopyAttributeValue(
            systemWide, kAXFocusedUIElementAttribute as CFString, &focusedRef
        )
        guard focusedStatus == .success, let focusedRef else { return nil }
        let focused = focusedRef as! AXUIElement

        guard let highlight = selectedText(of: focused), !highlight.isEmpty else {
            return nil
        }

        let context = surroundingContext(of: focused)
        let title = WindowInfo.frontmostTitle()
        return Selection(
            highlight: highlight,
            surroundingContext: context,
            pageTitle: title,
            source: .accessibility
        )
    }

    private static func selectedText(of element: AXUIElement) -> String? {
        var ref: CFTypeRef?
        let status = AXUIElementCopyAttributeValue(
            element, kAXSelectedTextAttribute as CFString, &ref
        )
        guard status == .success else { return nil }
        return ref as? String
    }

    /// Best-effort: read the selected range, expand it by `contextChars` on
    /// either side (clamped to the document), and ask AX for the resulting
    /// substring. Returns nil if any of those steps don't pan out — which is
    /// fine, the server treats context as optional.
    private static func surroundingContext(of element: AXUIElement) -> String? {
        var rangeRef: CFTypeRef?
        let rangeStatus = AXUIElementCopyAttributeValue(
            element, kAXSelectedTextRangeAttribute as CFString, &rangeRef
        )
        guard rangeStatus == .success, let rangeRef else { return nil }

        var selectionRange = CFRange()
        guard AXValueGetValue(rangeRef as! AXValue, .cfRange, &selectionRange) else {
            return nil
        }

        // Document length, if AX exposes it. If not, we'll clamp lazily by
        // letting AX itself reject an over-long range.
        let totalLength: Int? = {
            var lengthRef: CFTypeRef?
            let s = AXUIElementCopyAttributeValue(
                element, kAXNumberOfCharactersAttribute as CFString, &lengthRef
            )
            guard s == .success, let n = lengthRef as? Int else { return nil }
            return n
        }()

        var expanded = expand(
            selectionRange, by: contextChars, totalLength: totalLength
        )
        var paramValue: AXValue?
        withUnsafePointer(to: &expanded) { ptr in
            paramValue = AXValueCreate(.cfRange, ptr)
        }
        guard let paramValue else { return nil }

        var stringRef: CFTypeRef?
        let stringStatus = AXUIElementCopyParameterizedAttributeValue(
            element,
            kAXStringForRangeParameterizedAttribute as CFString,
            paramValue,
            &stringRef
        )
        guard stringStatus == .success else { return nil }
        return stringRef as? String
    }

    /// Pure helper, exposed at file scope for clarity (the math is the only
    /// part of this file worth glancing at).
    static func expand(_ range: CFRange, by amount: Int, totalLength: Int?) -> CFRange {
        let start = max(0, range.location - amount)
        let proposedEnd = range.location + range.length + amount
        let end = totalLength.map { min($0, proposedEnd) } ?? proposedEnd
        return CFRange(location: start, length: max(0, end - start))
    }
}
