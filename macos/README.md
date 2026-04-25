# macOS — Speedy native app

Native macOS app, Swift + SwiftUI, targeting macOS 13+.

## Run

```bash
cd macos
swift build
swift run
```

## Status

Bare scaffold. Renders a window with the tagline. Subsequent PRs add:

- Menu-bar resident behavior + Dock icon (PR 3)
- Double-tap ⌃ hotkey listener (PR 6)
- Accessibility-API selection capture with pasteboard fallback (PR 7)
- Cursor-anchored `NSPanel` overlay (PR 8)
- Full design-system port — Inter, JetBrains Mono, materials (PR 9)
- Privy onboarding via `WKWebView` (PR 10)
- Polymarket proxy wallet + session-key auth (PR 11)
- Order placement (PR 12)
- Backend wire-up (PR 13)
- Positions popover (PR 14)
- TestFlight build, signing, notarization, app icon (PR 15)

The current `swift build` produces a plain executable, not a proper `.app` bundle. PR 3 introduces a generated Xcode project (XcodeGen) so we can ship a real app bundle with entitlements (Accessibility, Network) and a `LaunchAgent` for hotkey-on-login behavior.
