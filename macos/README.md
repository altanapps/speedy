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
- `Sources/Speedy/Capture/` — selection-capture pipeline:
  - `Selection.swift` — `{highlight, surroundingContext?, pageTitle?, source}`
  - `SelectionCapture.swift` — orchestrator, `@MainActor`, AX first then pasteboard.
  - `AXSelectionReader.swift` — `kAXSelectedTextAttribute` on the system-wide focused element, plus best-effort surrounding context via `kAXStringForRangeParameterizedAttribute`.
  - `PasteboardSelectionReader.swift` — fallback for Electron (Slack, Notion, Discord, VS Code) where AX doesn't expose the selection. Snapshots the pasteboard, synthesises ⌘C, polls `changeCount` (≤100ms), reads, restores.
  - `WindowInfo.swift` — frontmost app name + AX focused-window title for `pageTitle`.
- `Sources/Speedy/Overlay/` — cursor-anchored floating panel:
  - `OverlayPanel.swift` — borderless, non-activating `NSPanel`; floats across Spaces and into full-screen apps; transparent background so the SwiftUI content owns its own chrome.
  - `OverlayView.swift` — placeholder content (highlight + page title + source badge). Replaced by the real market card in PR 13 once `/search` is wired in.
  - `OverlayController.swift` — owns one reused panel; presents at cursor; installs Esc + click-outside dismiss monitors; 8s idle auto-dismiss timer.
  - `OverlayPositioner.swift` — pure cursor → panel-origin math with screen-edge collision avoidance. Tested in `Tests/SpeedyTests/`.

## Trying it

After installing full Xcode:

```bash
cd macos
xcodegen generate
open Speedy.xcodeproj            # ⌘R in Xcode
```

On first launch macOS will prompt for Accessibility — grant it via System Settings → Privacy & Security → Accessibility. Once granted:

1. Select some text in any app (Safari, Notes, Slack, a PDF).
2. Double-tap **Control** anywhere on the system.
3. The menu-bar bolt icon flashes for ~250ms, **and** a small floating panel appears next to the cursor showing the captured text.
4. The panel dismisses on **Esc**, on **click-outside**, or after **8 seconds** of idle.

In the Xcode console (⌘⇧Y) you'll also see:
```
Speedy: captured via accessibility — Powell signaled patience on rate cuts
```

## Running tests

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer  # one-time
cd macos
swift test
```

CI runs `swift test` on `macos-15` so the test target is exercised on every push.

If you tried it from an Electron app (Slack, Notion, Discord, VS Code), expect `via pasteboard` instead — the same text, just routed through a synthetic ⌘C with the clipboard restored within ~100ms.

If the Accessibility prompt was dismissed without granting, toggle the Speedy entry off and on in System Settings; the app polls trust state once a second and starts the monitor as soon as it flips.

### "AX is on, but the hotkey doesn't fire"

macOS pins Accessibility trust to a binary's **code signature**, not its bundle id. Every ad-hoc dev build (`CODE_SIGN_IDENTITY="-"`) produces a new signature, so the "Speedy" entry you see toggled on is for a *previous* build. The current binary has no matching trust entry and `AXIsProcessTrusted()` returns `false` even though the entry looks correct.

Reset it cleanly:

```bash
tccutil reset Accessibility tech.nuff.speedy
```

Then **⌘.** + **⌘R** in Xcode. A fresh prompt appears — grant it. The new signature gets a fresh trust entry and the polling timer flips within ~1s.

You'll need this every time the binary signature changes meaningfully (e.g. after long pauses between builds, switching machines, or signing-config changes). Once we have a real Developer ID signature in PR 15, this stops being an issue.

## What's in this PR vs. later

Capture only. Nothing is sent to the backend yet — the captured text is logged so you can verify the pipeline. Wiring the result into a `/search` request lands in PR 13; the cursor-anchored overlay in PR 8.

## Status

Subsequent PRs add:
- Cursor-anchored `NSPanel` overlay (PR 8)
- Full design-system port — Inter, JetBrains Mono, materials (PR 9)
- Privy onboarding via `WKWebView` (PR 10)
- Polymarket proxy wallet + session-key auth (PR 11)
- Order placement (PR 12)
- Backend wire-up (PR 13)
- Positions popover (PR 14)
- TestFlight build, signing, notarization, app icon (PR 15)
