import CoreGraphics
import XCTest

@testable import Speedy

/// All assertions are in screen coordinates: bottom-left origin, Y up.
/// `screen` here is the `visibleFrame`-equivalent rect.
final class OverlayPositionerTests: XCTestCase {
    private let panel = CGSize(width: 320, height: 140)
    private let screen = CGRect(x: 0, y: 0, width: 1440, height: 900)

    private var pad: CGFloat { OverlayPositioner.cursorPadding }
    private var edge: CGFloat { OverlayPositioner.edgePadding }

    func test_cursorInMiddle_placesPanelBelowAndRight() {
        let cursor = CGPoint(x: 700, y: 500)
        let origin = OverlayPositioner.panelOrigin(
            cursor: cursor, panelSize: panel, in: screen
        )
        XCTAssertEqual(origin.x, cursor.x + pad, accuracy: 0.001)
        XCTAssertEqual(origin.y, cursor.y - panel.height - pad, accuracy: 0.001)
    }

    func test_cursorNearRightEdge_flipsPanelToLeft() {
        let cursor = CGPoint(x: screen.maxX - 30, y: 500)
        let origin = OverlayPositioner.panelOrigin(
            cursor: cursor, panelSize: panel, in: screen
        )
        // Should be left of cursor, not spilling off the right edge.
        XCTAssertEqual(origin.x, cursor.x - panel.width - pad, accuracy: 0.001)
        XCTAssertLessThanOrEqual(origin.x + panel.width, screen.maxX - edge)
    }

    func test_cursorNearBottom_flipsPanelAbove() {
        // Low Y = "near bottom of screen" in macOS coords.
        let cursor = CGPoint(x: 700, y: screen.minY + 30)
        let origin = OverlayPositioner.panelOrigin(
            cursor: cursor, panelSize: panel, in: screen
        )
        XCTAssertEqual(origin.y, cursor.y + pad, accuracy: 0.001)
        XCTAssertGreaterThanOrEqual(origin.y, screen.minY + edge)
    }

    func test_cursorInBottomRightCorner_flipsBothAxes() {
        let cursor = CGPoint(x: screen.maxX - 20, y: screen.minY + 20)
        let origin = OverlayPositioner.panelOrigin(
            cursor: cursor, panelSize: panel, in: screen
        )
        // Panel goes left-of and above cursor.
        XCTAssertLessThanOrEqual(origin.x + panel.width, cursor.x)
        XCTAssertGreaterThanOrEqual(origin.y, cursor.y)
        // Still inside screen.
        XCTAssertGreaterThanOrEqual(origin.x, screen.minX + edge)
        XCTAssertLessThanOrEqual(origin.y + panel.height, screen.maxY - edge)
    }

    func test_cursorOutsideScreen_clampsIntoVisibleFrame() {
        // Hot-corner-ish: cursor past the right edge entirely.
        let cursor = CGPoint(x: screen.maxX + 200, y: 500)
        let origin = OverlayPositioner.panelOrigin(
            cursor: cursor, panelSize: panel, in: screen
        )
        XCTAssertGreaterThanOrEqual(origin.x, screen.minX + edge)
        XCTAssertLessThanOrEqual(origin.x + panel.width, screen.maxX - edge)
        XCTAssertGreaterThanOrEqual(origin.y, screen.minY + edge)
        XCTAssertLessThanOrEqual(origin.y + panel.height, screen.maxY - edge)
    }

    func test_panelLargerThanScreen_clampsToOriginCorner() {
        // Pathological — panel larger than its screen. We don't do anything
        // clever, just clamp to a sane corner so the user sees *something*.
        let huge = CGSize(width: screen.width + 100, height: screen.height + 100)
        let origin = OverlayPositioner.panelOrigin(
            cursor: CGPoint(x: 200, y: 200), panelSize: huge, in: screen
        )
        XCTAssertEqual(origin.x, screen.minX + edge, accuracy: 0.001)
        XCTAssertEqual(origin.y, screen.minY + edge, accuracy: 0.001)
    }
}
