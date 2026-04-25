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
- `Sources/Speedy/AppDelegate.swift` — owns the `MenuBarController` and `HotkeyMonitor`; suppresses quit-on-last-window-close so the app stays alive in the menu bar; polls Accessibility-trust until the user grants it, then starts hotkey monitoring.
- `Sources/Speedy/MenuBarController.swift` — `NSStatusItem` with Open / Launch-at-Login / Quit. Menu rebuilds on open so the login-item state stays in sync with system reality. Exposes `flash()` so the hotkey has visible feedback before the overlay lands.
- `Sources/Speedy/LoginItemController.swift` — wraps `SMAppService.mainApp` (modern macOS 13+ login-item API; replaces the old `~/Library/LaunchAgents` plist approach).
- `Sources/Speedy/HotkeyMonitor.swift` — `NSEvent` global+local monitor on `.flagsChanged`. Detects double-tap of Control (300ms window) and fires a callback. No `RegisterEventHotKey` because Carbon hotkeys don't trigger on bare modifiers.
- `Sources/Speedy/AccessibilityPermission.swift` — `AXIsProcessTrusted` check + system prompt + a deep-link to System Settings → Privacy & Security → Accessibility for the "permission missing" flow.

## Trying the hotkey

After installing full Xcode (the SwiftPM build produces a binary, but Accessibility prompts and reliable global event monitoring need a proper `.app`):

```bash
cd macos
xcodegen generate
open Speedy.xcodeproj            # ⌘R in Xcode
```

On first launch macOS will prompt for Accessibility — grant it via System Settings → Privacy & Security → Accessibility. Once granted, double-tap **Control** anywhere on the system; the menu-bar bolt icon should briefly fill, then return to its outline state. That's the trigger that PR 7 will use to capture selected text.

If the prompt was dismissed without granting, toggle the Speedy entry off and on in System Settings; the app polls trust state once a second and starts the monitor as soon as it flips.

## What's in this PR vs. later

Hotkey detection only — no selection capture, no overlay. The flash is throwaway feedback so PR 6 is independently demoable; it's replaced by the cursor-anchored overlay in PR 8.

## Status

Subsequent PRs add:

- Accessibility-API selection capture with pasteboard fallback (PR 7)
- Cursor-anchored `NSPanel` overlay (PR 8)
- Full design-system port — Inter, JetBrains Mono, materials (PR 9)
- Privy onboarding via `WKWebView` (PR 10)
- Polymarket proxy wallet + session-key auth (PR 11)
- Order placement (PR 12)
- Backend wire-up (PR 13)
- Positions popover (PR 14)
- TestFlight build, signing, notarization, app icon (PR 15)
