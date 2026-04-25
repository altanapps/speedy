import CoreGraphics
import Foundation

/// Pure positioning math: cursor → overlay-panel origin, with screen-edge
/// collision avoidance.
///
/// All inputs/outputs are in macOS screen coordinates: bottom-left origin,
/// Y increases upward. `screenFrame` should be the screen's `visibleFrame`
/// (excludes menu bar + Dock).
///
/// Strategy: prefer below-right of the cursor — that's where the user's eye
/// is already heading after the gesture. Flip horizontally if the panel
/// would clip the right edge; flip vertically if it would clip the bottom.
/// Finally clamp into the visible frame so we never produce an off-screen
/// origin even for cursors way outside the screen.
enum OverlayPositioner {
    static let cursorPadding: CGFloat = 12
    static let edgePadding: CGFloat = 8

    static func panelOrigin(
        cursor: CGPoint,
        panelSize: CGSize,
        in screenFrame: CGRect
    ) -> CGPoint {
        // Default: panel below-right of cursor (low-Y is "below" in macOS coords).
        var x = cursor.x + cursorPadding
        var y = cursor.y - panelSize.height - cursorPadding

        // Flip horizontally if the right edge would clip.
        if x + panelSize.width > screenFrame.maxX - edgePadding {
            x = cursor.x - panelSize.width - cursorPadding
        }

        // Flip vertically if the bottom would clip.
        if y < screenFrame.minY + edgePadding {
            y = cursor.y + cursorPadding
        }

        // Final clamp — covers the case where the cursor itself is near a
        // corner and even after flipping the panel would still spill out.
        let minX = screenFrame.minX + edgePadding
        let maxX = screenFrame.maxX - panelSize.width - edgePadding
        let minY = screenFrame.minY + edgePadding
        let maxY = screenFrame.maxY - panelSize.height - edgePadding
        x = min(max(x, minX), maxX)
        y = min(max(y, minY), maxY)

        return CGPoint(x: x, y: y)
    }
}
