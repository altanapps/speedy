# Speedy

> Trade where you read.

A native macOS hotkey-driven trade interface for Polymarket. Highlight any text — in a browser, Slack, a PDF — tap a hotkey, and Speedy retrieves the most relevant market and surfaces a one-click trade overlay at your cursor.

The product thesis: the bottleneck on retail prediction-market trading isn't decision quality, it's the 90 seconds between forming a thesis and getting a position on. Speedy collapses that to ~3 seconds — and Polymarket's poor in-app search means **discovery**, not just speed, is the real wedge.

## Status

Pre-MVP, runnable end-to-end on a developer machine. PRD locked, retrieval pipeline + macOS app + cursor-anchored overlay shipped. No trading path yet (PRs 10–12).

## Run it locally

You need: macOS 13+, Xcode, Homebrew, Python 3.11+, an OpenAI API key.

```bash
git clone https://github.com/altanapps/speedy.git
cd speedy
```

**Backend** (one-shot setup, then refresh + serve):

```bash
cd backend
make setup                       # brew installs postgres@17 + pgvector, creates the speedy db, runs migrations, creates .env

# put your OpenAI key in backend/.env (it's gitignored):
#   OPENAI_API_KEY=sk-...
# get one at https://platform.openai.com/api-keys

make refresh                     # pulls Polymarket markets + embeds them (~5–15 min, ~$0.10 in OpenAI charges)
make serve                       # runs uvicorn on :8000 — leave it running
```

If anything goes sideways: `make doctor` prints a one-screen diagnostic.

**macOS app** (separate terminal):

```bash
cd macos
brew install xcodegen            # one-time
xcodegen generate
open Speedy.xcodeproj
```

In Xcode:

1. Select the **Speedy** target → **Signing & Capabilities** → tick **Automatically manage signing** → pick your **Personal Team** (free, just your Apple ID — no Developer Program needed). This is required so macOS Accessibility trust persists across rebuilds.
2. ⌘R to run.
3. macOS prompts for Accessibility permission — grant via System Settings → Privacy & Security → Accessibility, toggle Speedy on.
4. Highlight text anywhere, double-tap **Control**.

A floating panel appears at your cursor with the matched Polymarket market. Esc / click-outside / 8s idle to dismiss.

If the hotkey doesn't fire after granting Accessibility, see `macos/README.md` § "AX is on, but the hotkey doesn't fire" — this can happen when the trust entry is bound to a previous build's signature.

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
