# claude-design — design system + interactive prototypes

The canonical visual language for Speedy. Lives outside the macOS app so
the design can iterate independently of the SwiftUI port — the SwiftUI
implementation in `macos/Sources/Speedy/Overlay/` mirrors what's defined
here.

## Files

- **`Speedy Design System.html`** — the source of truth. Tokens
  (colors, typography, radii, spacing, motion), components, voice rules.
  Open in any browser.
- **`Trading Cursor.html`** — interactive prototype of the overlay.
  Loads `app.jsx`. Shows all four overlay states (searching, matched,
  no-match, error) with realistic data.
- **`Trading Cursor v1 (web).html`** — earlier iteration. Kept for
  diff-checking the design evolution.
- **`app.jsx`** — React component for the trading cursor. The 1:1
  reference for the SwiftUI port.
- **`macos-window.jsx`** — surrounding macOS window chrome (title bar,
  traffic lights) used by the prototype.
- **`tweaks-panel.jsx`** — interactive controls in the prototype that
  let you toggle states / adjust parameters. Not part of the final
  design — just a dev affordance.
- **[`marketing/`](./marketing/)** — rendered marketing assets (hero
  image, OG card, app icon, wordmark). See its own README.

## How this maps to SwiftUI

`DESIGN.md` (top-level) is the translation guide — it walks each token
in `Speedy Design System.html` and shows the SwiftUI equivalent. When
the design changes here, that file is what the SwiftUI port follows.

## Running the prototype

```bash
cd claude-design
python3 -m http.server 8080
# open http://localhost:8080/Trading%20Cursor.html
```

(JSX files load via [esm.sh](https://esm.sh) — no build step needed.)
