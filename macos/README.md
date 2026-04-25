# macOS — Speedy native app

Native macOS app, Swift + SwiftUI, targeting macOS 13+.

The shippable artifact is a real `.app` bundle generated from `project.yml` via [XcodeGen](https://github.com/yonaskolb/XcodeGen). A parallel `Package.swift` is kept so `swift build` works as a fast compile-time smoke test in CI and during quick iteration on pure-Swift logic.

## Run (dev)

Two paths:

**Fast smoke test (no `.app`, no entitlements):**

```bash
cd macos
swift build
swift run
```

**Real app bundle (menu-bar item, login-item registration, entitlements):**

```bash
cd macos
brew install xcodegen     # one-time
xcodegen generate
open Speedy.xcodeproj     # then ⌘R, or:
xcodebuild -project Speedy.xcodeproj -scheme Speedy -configuration Debug build
open build/Build/Products/Debug/Speedy.app   # if -derivedDataPath was set to build/
```

`Speedy.xcodeproj/` is generated and gitignored — regenerate with `xcodegen generate` whenever `project.yml` or the source layout changes.

## Layout

- `project.yml` — XcodeGen spec. Source of truth for bundle id, entitlements, deployment target, signing.
- `Resources/Info.plist` — bundle metadata. `LSUIElement` is `false` (Speedy has both a Dock icon and a menu-bar item).
- `Resources/Speedy.entitlements` — non-sandboxed (Accessibility API needs full process trust); `com.apple.security.network.client` for backend calls. Hardened runtime is on.
- `Sources/Speedy/SpeedyApp.swift` — `@main` entry point. Hosts the SwiftUI window scene and installs `AppDelegate`.
- `Sources/Speedy/AppDelegate.swift` — owns the `MenuBarController`; suppresses quit-on-last-window-close so the app stays alive in the menu bar.
- `Sources/Speedy/MenuBarController.swift` — `NSStatusItem` with Open / Launch-at-Login / Quit. Menu rebuilds on open so the login-item state stays in sync with system reality.
- `Sources/Speedy/LoginItemController.swift` — wraps `SMAppService.mainApp` (modern macOS 13+ login-item API; replaces the old `~/Library/LaunchAgents` plist approach).

## What's in this PR vs. later

This PR ships the bundle scaffolding only. It does **not** yet:

- Register a global hotkey (PR 6).
- Read the system pasteboard or Accessibility tree (PR 7).
- Show the cursor-anchored overlay (PR 8).

What it does ship: a real `.app` you can launch, a persistent menu-bar icon, and a working **Launch at Login** toggle that survives reboots (when run from a signed-and-installed bundle — `swift run` and unsigned dev builds will silently no-op the registration).

## Status

Subsequent PRs add:

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
