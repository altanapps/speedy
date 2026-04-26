import AppKit

final class MenuBarController: NSObject {
    private let statusItem: NSStatusItem
    private let menu = NSMenu()
    private let idleSymbol = "bolt"
    private let activeSymbol = "bolt.fill"
    private var flashWorkItem: DispatchWorkItem?

    /// Optional debug hook — when set, the menu shows "Preview overlay…"
    /// items that fire each OverlayStatus state with sample data. AppDelegate
    /// wires this in DEBUG builds so the visual can be checked without AX
    /// trust or the hotkey path.
    var previewOverlay: ((Selection, OverlayStatus) -> Void)?

    override init() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        super.init()

        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: idleSymbol, accessibilityDescription: "Speedy")
            button.toolTip = "Speedy — Trade where you read"
        }

        statusItem.menu = menu
        menu.delegate = self
        rebuild()
    }

    /// Visual feedback when the hotkey fires. Until the overlay lands (PR 8),
    /// this is the only signal the user gets that selection-capture happened.
    func flash() {
        guard let button = statusItem.button else { return }
        flashWorkItem?.cancel()
        button.image = NSImage(
            systemSymbolName: activeSymbol, accessibilityDescription: "Speedy active"
        )
        let restore = DispatchWorkItem { [weak self, weak button] in
            guard let self, let button else { return }
            button.image = NSImage(
                systemSymbolName: self.idleSymbol, accessibilityDescription: "Speedy"
            )
        }
        flashWorkItem = restore
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25, execute: restore)
    }

    private func rebuild() {
        menu.removeAllItems()

        let openItem = NSMenuItem(title: "Open Speedy", action: #selector(openMain), keyEquivalent: "")
        openItem.target = self
        menu.addItem(openItem)

        menu.addItem(.separator())

        if previewOverlay != nil {
            let previewMenu = NSMenu(title: "Preview overlay")
            for (title, selector) in [
                ("Searching", #selector(previewSearching)),
                ("Matched", #selector(previewMatched)),
                ("No match", #selector(previewNoMatch)),
                ("Error", #selector(previewError)),
            ] {
                let item = NSMenuItem(title: title, action: selector, keyEquivalent: "")
                item.target = self
                previewMenu.addItem(item)
            }
            let parent = NSMenuItem(title: "Preview overlay", action: nil, keyEquivalent: "")
            parent.submenu = previewMenu
            menu.addItem(parent)
            menu.addItem(.separator())
        }

        let loginItem = NSMenuItem(
            title: "Launch at Login",
            action: #selector(toggleLoginItem),
            keyEquivalent: ""
        )
        loginItem.target = self
        loginItem.state = LoginItemController.isEnabled ? .on : .off
        menu.addItem(loginItem)

        menu.addItem(.separator())

        let quitItem = NSMenuItem(title: "Quit Speedy", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)
    }

    // MARK: - Sample-data hooks

    private static let sampleSelection = Selection(
        highlight: "Powell signaled patience on rate cuts at the March FOMC meeting",
        surroundingContext: nil,
        pageTitle: "FT — Fed Minutes",
        source: .accessibility
    )

    private static let sampleMarket = MatchedMarket(
        id: "fed-may-2026",
        slug: "will-the-fed-cut-rates-in-may-2026",
        question: "Will the Fed cut rates at the May 2026 FOMC meeting?",
        description: nil,
        endDate: Date(timeIntervalSinceNow: 86_400 * 14),
        category: "Macro",
        tags: ["fed", "rates"],
        yesPrice: 0.62,
        noPrice: 0.38,
        volume24h: 1_245_000,
        pricesUpdatedAt: Date()
    )

    @objc private func previewSearching() {
        previewOverlay?(Self.sampleSelection, .searching)
    }

    @objc private func previewMatched() {
        previewOverlay?(Self.sampleSelection, .matched(Self.sampleMarket, score: 0.71))
    }

    @objc private func previewNoMatch() {
        previewOverlay?(Self.sampleSelection, .noMatch(threshold: 0.55))
    }

    @objc private func previewError() {
        previewOverlay?(
            Self.sampleSelection,
            .error("Couldn't reach Speedy backend (Connection refused)")
        )
    }

    @objc private func openMain() {
        NSApp.activate(ignoringOtherApps: true)
        for window in NSApp.windows where window.canBecomeMain {
            window.makeKeyAndOrderFront(nil)
            return
        }
    }

    @objc private func toggleLoginItem() {
        LoginItemController.toggle()
        rebuild()
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

extension MenuBarController: NSMenuDelegate {
    func menuWillOpen(_ menu: NSMenu) {
        rebuild()
    }
}
