# Speedy

> Trade where you read.

A native macOS hotkey-driven trade interface for Polymarket. Highlight any text — in a browser, Slack, a PDF — tap a hotkey, and Speedy retrieves the most relevant market and surfaces a one-click trade overlay at your cursor.

The product thesis: the bottleneck on retail prediction-market trading isn't decision quality, it's the 90 seconds between forming a thesis and getting a position on. Speedy collapses that to ~3 seconds — and Polymarket's poor in-app search means **discovery**, not just speed, is the real wedge.

## Status

Self-hosted MVP. End-to-end loop works: highlight → match → click Yes/No → trade lands on Polymarket. No hosted backend yet — every user runs their own on `localhost`.

## What you need

| | What | Where to get it | Cost |
|---|---|---|---|
| 1 | macOS 13+ | — | — |
| 2 | Xcode (full, not just CLT) | Mac App Store | free |
| 3 | Homebrew | https://brew.sh | free |
| 4 | OpenAI API key | https://platform.openai.com/api-keys | ~$0.10 first index build, pennies/month after |
| 5 | Anthropic API key (optional, recommended) | https://console.anthropic.com | ~$0.001/search |
| 6 | MetaMask wallet on Polygon | https://metamask.io | free |
| 7 | Polymarket account funded with USDC | https://polymarket.com | $10–20 USDC + a bit of MATIC for gas |

**About the keys:**

- **OpenAI** is required. Speedy embeds ~46k Polymarket markets with `text-embedding-3-small` so it can match your highlighted text against them. One-time index build runs you ~$0.10; per-search cost is fractions of a cent.
- **Anthropic** is optional but recommended. When set, `/search` runs LLM rerank with `claude-haiku-4-5` over the top-10 pgvector candidates. Big quality win on ambiguous queries ("Powell" → which Powell?). Without it, `/search` falls back to embedding-only top-1.
- **Polymarket** isn't an "API key" — it's the private key of the MetaMask wallet you trade with, exported from polymarket.com → wallet → Export private key. You also need the proxy/funder address (your deposit address on polymarket.com).

All secrets live in a single gitignored `backend/.env` file. Speedy never sends your keys anywhere except the corresponding service.

## Install

```bash
git clone https://github.com/altanapps/speedy.git
cd speedy
```

### Backend

```bash
cd backend
make setup
# brew installs postgres@17 + pgvector, creates the speedy db, runs migrations, creates .env

# Edit backend/.env and fill in:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...           (optional)
#   POLYMARKET_PRIVATE_KEY=0x...           (export from polymarket.com)
#   POLYMARKET_FUNDER_ADDRESS=0x...        (your polymarket.com deposit address)
#   POLYMARKET_SIGNATURE_TYPE=2            (1 for older proxies, 0 for raw EOA)

make refresh                     # ~5–15 min, ~$0.10 in OpenAI charges
make serve                       # uvicorn on :8000 — leave running
```

If anything goes sideways: `make doctor` prints a one-screen diagnostic.

### macOS app

```bash
cd macos
brew install xcodegen            # one-time
xcodegen generate
open Speedy.xcodeproj
```

In Xcode:

1. Select the **Speedy** target → **Signing & Capabilities** → tick **Automatically manage signing** → pick your **Personal Team** (free, just your Apple ID — no Developer Program needed). Required so macOS Accessibility trust persists across rebuilds.
2. ⌘R to run.
3. macOS prompts for Accessibility — grant via System Settings → Privacy & Security → Accessibility, toggle Speedy on.
4. Highlight text anywhere, double-tap **Control**.

A floating panel appears at your cursor with the matched Polymarket market, current Yes/No prices, and a Buy button. Click Yes/No, set size, hit ⌘↵ to submit.

If the hotkey doesn't fire after granting Accessibility, see `macos/README.md` § "AX is on, but the hotkey doesn't fire."

## Layout

- [`macos/`](./macos/) — native macOS app (Swift + SwiftUI).
- [`backend/`](./backend/) — Python + FastAPI retrieval service (Polymarket index + `/search` + `/order`).
- [`eval/`](./eval/) — labeled selection→market evaluation corpus.
- [`PRD.md`](./PRD.md) — full product spec.
- [`claude-design/`](./claude-design/) — canonical design system + interactive prototype.
- [`DESIGN.md`](./DESIGN.md) — SwiftUI translation guide.

## Locked decisions

- **Substrate:** Native macOS, Swift + SwiftUI.
- **Trigger:** Double-tap Control (customizable later).
- **Selection capture:** Accessibility API first; pasteboard fallback for Electron (Slack, Notion, Discord, VS Code).
- **Venue:** Polymarket only at MVP. Kalshi / Alpaca / Hyperliquid in v0.2+.
- **Wallet:** Self-custody EOA private key in env at v0.1. Privy embedded wallet + session-key delegation in v0.2 (issue #14).
- **Retrieval:** Server-hosted index of all active Polymarket markets, refreshed every ~5 min. `text-embedding-3-small` + pgvector + `claude-haiku-4-5` rerank.
- **Backend:** Python + FastAPI + Postgres+pgvector. Self-hosted in v0.1.

## License

AGPL-3.0. See [`LICENSE`](./LICENSE).
