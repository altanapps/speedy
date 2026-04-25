# Speedy

> Trade where you read.

A native macOS hotkey-driven trade interface for Polymarket. Highlight any text — in a browser, Slack, a PDF — tap a hotkey, and Speedy retrieves the most relevant market and surfaces a one-click trade overlay at your cursor.

The product thesis: the bottleneck on retail prediction-market trading isn't decision quality, it's the 90 seconds between forming a thesis and getting a position on. Speedy collapses that to ~3 seconds — and Polymarket's poor in-app search means **discovery**, not just speed, is the real wedge.

## Status

Pre-MVP. PRD locked, design system + working web prototype shipped, native build not yet started.

## Layout

- [`macos/`](./macos/) — native macOS app (Swift + SwiftUI).
- [`backend/`](./backend/) — Python + FastAPI retrieval service (Polymarket index + `/search`).
- [`eval/`](./eval/) — labeled selection→market evaluation corpus.
- [`PRD.md`](./PRD.md) — full product spec (overview, architecture, MVP scope, risks).
- [`claude-design/`](./claude-design/) — canonical design system + interactive prototype.
  - [`Speedy Design System.html`](./claude-design/Speedy%20Design%20System.html) — tokens, typography, components, motion, voice. The source of truth for visual design.
  - [`Trading Cursor.html`](./claude-design/Trading%20Cursor.html) — interactive prototype (open in browser, loads `app.jsx`).
- [`DESIGN.md`](./DESIGN.md) — SwiftUI translation guide; maps the canonical web tokens to native macOS implementation.
- [`mock/index.html`](./mock/index.html) — early concept mock (superseded by `claude-design/`, kept for history).

## Locked decisions (engineering)

From the build interview:

- **Substrate:** Native macOS, Swift + SwiftUI.
- **Trigger:** Hotkey only (double-tap ⌃, customizable). Press once toggles overlay open; press again, Esc, or click-outside dismiss.
- **Selection capture:** Accessibility API first; pasteboard hijack fallback for Electron apps (Slack, Notion, Discord, VS Code).
- **Venue:** Polymarket only at MVP. Kalshi / Alpaca / Hyperliquid in v0.2+.
- **Wallet:** Privy embedded wallet as the EOA owner; Polymarket proxy wallet on top with session-key delegation so users sign once, not per trade.
- **Retrieval:** Server-hosted index of all active Polymarket markets, refreshed every ~5 min. `text-embedding-3-small` for embeddings, pgvector for search. Embedding-only at v1; LLM rerank is a one-day flag flip later if accuracy is bad.
- **Query input:** Highlight + surrounding text + window title from the Accessibility tree (no per-page LLM summarization in the hot path).
- **Backend:** Python + FastAPI + Postgres+pgvector on Fly.io.
- **Live prices:** Polymarket WebSocket subscription per visible market.
- **App shape:** Dock icon + menu-bar resident, auto-launch on login via `SMAppService.loginItem`.

## Open decisions

See `PRD.md` §10. Top:

1. Distribution at v0.1 (TestFlight closed beta → notarized DMG default).
2. Default order size, confirmation thresholds for large trades.
3. "No match" UX (silent vs. inline message vs. learn-from-failure prompt).
4. Telemetry & monetization (deferred from Round 1).
