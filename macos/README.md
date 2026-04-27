# macOS — Speedy native app

Native macOS app, Swift + SwiftUI, targeting macOS 13+.

The shippable artifact is a real `.app` bundle generated from `project.yml`
via [XcodeGen](https://github.com/yonaskolb/XcodeGen). A parallel
`Package.swift` is kept so `swift build` works as a fast compile-time smoke
test in CI and during quick iteration on pure-Swift logic.

## Build

```bash
cd macos
brew install xcodegen     # one-time
xcodegen generate
open Speedy.xcodeproj
```

In Xcode:

1. Select the **Speedy** target → **Signing & Capabilities** → tick
   **Automatically manage signing** → pick your **Personal Team** (free,
   just your Apple ID — no Developer Program needed). Required so
   Accessibility trust persists across rebuilds.
2. ⌘R to run.

`Speedy.xcodeproj/` is generated and gitignored — regenerate with
`xcodegen generate` whenever `project.yml` or the source layout changes.

A faster smoke-only path (no `.app` bundle, no entitlements, no
Accessibility) for iterating on pure-Swift logic:

```bash
swift build
swift run
```

## Layout

- `project.yml` — XcodeGen spec. Source of truth for bundle id,
  entitlements, deployment target, signing.
- `Resources/Info.plist` — bundle metadata. `LSUIElement` is `false`
  (Speedy has both a Dock icon and a menu-bar item).
- `Resources/Speedy.entitlements` — non-sandboxed (Accessibility API
  needs full process trust); `com.apple.security.network.client` for
  backend calls. Hardened runtime is on.
- `Resources/Fonts/` — bundled Inter + JetBrains Mono TTFs for the
  overlay's typography. Loaded via `ATSApplicationFontsPath` in
  `Info.plist`.
- `Sources/Speedy/SpeedyApp.swift` — `@main` entry point. Hosts the
  SwiftUI window scene and installs `AppDelegate`.
- `Sources/Speedy/AppDelegate.swift` — owns the `MenuBarController`,
  `HotkeyMonitor`, and `OverlayController`. Suppresses
  quit-on-last-window-close so the app stays alive in the menu bar;
  polls Accessibility-trust until the user grants it; fetches
  `/config` from the backend at launch for the user's Polymarket
  profile URL.
- `Sources/Speedy/MenuBarController.swift` — `NSStatusItem` with Open /
  Launch-at-Login / Quit (and a "Preview overlay" debug submenu). Menu
  rebuilds on open so login-item state stays in sync with system reality.
- `Sources/Speedy/LoginItemController.swift` — wraps `SMAppService.mainApp`
  (modern macOS 13+ login-item API; replaces the old
  `~/Library/LaunchAgents` plist approach).
- `Sources/Speedy/HotkeyMonitor.swift` — `NSEvent` global+local monitor
  on `.flagsChanged`. Detects double-tap of Control (300ms window) and
  fires a callback. No `RegisterEventHotKey` because Carbon hotkeys
  don't trigger on bare modifiers.
- `Sources/Speedy/AccessibilityPermission.swift` — `AXIsProcessTrusted`
  check + system prompt + a deep-link to System Settings → Privacy &
  Security → Accessibility for the "permission missing" flow.
- `Sources/Speedy/Capture/` — selection-capture pipeline:
  - `Selection.swift` — `{highlight, surroundingContext?, pageTitle?, source}`
  - `SelectionCapture.swift` — orchestrator, `@MainActor`, AX first
    then pasteboard.
  - `AXSelectionReader.swift` — `kAXSelectedTextAttribute` on the
    system-wide focused element, plus best-effort surrounding context
    via `kAXStringForRangeParameterizedAttribute`.
  - `PasteboardSelectionReader.swift` — fallback for Electron (Slack,
    Notion, Discord, VS Code) where AX doesn't expose the selection.
    Snapshots the pasteboard, synthesises ⌘C, polls `changeCount`
    (≤100ms), reads, restores.
  - `WindowInfo.swift` — frontmost app name + AX focused-window title
    for `pageTitle`.
- `Sources/Speedy/Overlay/` — cursor-anchored floating panel:
  - `OverlayPanel.swift` — borderless, non-activating `NSPanel`;
    floats across Spaces and into full-screen apps; transparent
    background so the SwiftUI content owns its own chrome.
  - `OverlayView.swift` — `OverlayStatus` state machine (searching /
    matched / noMatch / error / placing / placed / orderError),
    rendered with the Speedy design system (Inter, JetBrains Mono,
    dark-glass material).
  - `OverlayController.swift` — owns one reused panel; presents at
    cursor with top-left pinning so the panel doesn't move while the
    user edits; auto-dismisses noMatch (2s) and placed (3s); Esc-only
    explicit dismiss.
  - `OverlayPositioner.swift` — pure cursor → panel-origin math with
    screen-edge collision avoidance. Tested in `Tests/SpeedyTests/`.
  - `SpeedyTokens.swift` — design-system tokens (colors, typography,
    radii, spacing, motion).
  - `TradeControls.swift` — Yes/No segmented control + USDC size
    field + Buy button. Mounted into the matched-state body.
- `Sources/Speedy/Search/` — backend wire-up for retrieval:
  - `SearchResult.swift` — `MatchedMarket` + `SearchResponse` Codable
    models mirroring the backend's Pydantic; `SearchOutcome` collapses
    into `matched` / `noMatch`.
  - `SearchClient.swift` — `SearchClient` protocol + `HTTPSearchClient`
    (URLSession-backed). Backend URL: `SPEEDY_BACKEND_URL` env →
    `SpeedyBackendURL` Info.plist key → `http://localhost:8000`.
  - `ConfigClient.swift` — one-shot GET `/config` at launch, returns
    the user's Polymarket profile URL so the overlay's "View on
    Polymarket" link points to the right wallet.
- `Sources/Speedy/Trading/` — order-submission wire-up:
  - `Order.swift` — `OrderRequest` + `OrderResponse` Codable mirrors.
  - `OrderClient.swift` — POST `/order` to the backend.
- `Tests/SpeedyTests/` — XCTest target. Positioner math, search/order
  client request shapes via `URLProtocol` stubbing.

## Trying it end-to-end

You need the backend running first — see [`../backend/README.md`](../backend/README.md).

Once `make serve` is up at `localhost:8000`:

1. ⌘R the macOS app from Xcode.
2. macOS prompts for Accessibility on first launch — grant it.
3. Select text in any app, double-tap **Control**.
4. Bolt icon flashes; floating panel appears at cursor with the matched
   market and live Yes/No prices.
5. Click Yes/No, set size, **⌘↵** to submit. **Esc** dismisses.

To point the app at a different backend (e.g. a Railway deploy), set
`SPEEDY_BACKEND_URL` in the Xcode scheme's environment variables.

## Running tests

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer  # one-time
cd macos
swift test
```

CI runs `swift test` on `macos-15` so the test target is exercised on
every push.

## Troubleshooting

### "AX is on, but the hotkey doesn't fire"

macOS pins Accessibility trust to a binary's **code signature**, not its
bundle id. Every ad-hoc dev build (`CODE_SIGN_IDENTITY="-"`) produces a
new signature, so the "Speedy" entry you see toggled on may be for a
*previous* build. The current binary then has no matching trust entry
and `AXIsProcessTrusted()` returns `false` even though the entry looks
correct.

Reset it cleanly:

```bash
tccutil reset Accessibility tech.nuff.speedy
```

Then **⌘.** + **⌘R** in Xcode. A fresh prompt appears — grant it. The
new signature gets a fresh trust entry and the polling timer flips
within ~1s.

You'll hit this every time the binary signature changes meaningfully
(switching machines, signing-config changes, long pauses between
builds). The Personal Team signing setup above (Signing & Capabilities
→ Automatic) reduces but doesn't eliminate signature drift.

### Pasteboard fallback

If you trigger Speedy from an Electron app (Slack, Notion, Discord,
VS Code), the AX path returns nothing useful — those apps don't
expose `kAXSelectedTextAttribute`. Speedy falls back to synthesising
⌘C, reading the pasteboard, and restoring it. You'll see
`captured via pasteboard` in the console instead of
`via accessibility`. Same end behavior, but there's a short window
(~30ms typical, 100ms cap) where your real clipboard is briefly
unavailable.
