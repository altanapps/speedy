import AppKit

final class MenuBarController: NSObject {
    private let statusItem: NSStatusItem
    private let menu = NSMenu()
    private let idleSymbol = "bolt"
    private let activeSymbol = "bolt.fill"
    private var flashWorkItem: DispatchWorkItem?

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
