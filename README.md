# Speedy

> Trade where you read.

![Speedy demo](docs/demo.gif)

A native macOS hotkey-driven trade interface for Polymarket. Highlight any text — in a browser, Slack, a PDF — tap a hotkey, and Speedy retrieves the most relevant market and surfaces a one-click trade overlay at your cursor.

The product thesis: the bottleneck on retail prediction-market trading isn't decision quality, it's the 90 seconds between forming a thesis and getting a position on. Speedy collapses that to ~3 seconds — and Polymarket's poor in-app search means **discovery**, not just speed, is the real wedge.

## How it works

```
Highlight text          ⌃⌃               Embedding + LLM rerank        py-clob-client
in any app   ────────────▶  Speedy capture  ────▶  matched market   ──▶  signed trade
             (double-Ctrl)   (AX or pasteboard)    (Polymarket index)    on Polymarket
```

End-to-end loop:

1. Speedy keeps a refreshed index of every active Polymarket market (Postgres + pgvector).
2. On hotkey, it grabs your selection via the macOS Accessibility API (with pasteboard fallback for Electron apps).
3. Embeds the selection with `text-embedding-3-small`, takes top-K from pgvector, reranks with `claude-haiku-4-5`.
4. Surfaces the match in a floating overlay at your cursor with current Yes/No prices.
5. ⌘↵ to submit. The backend signs the order with your Polymarket EOA via `py-clob-client` and posts it to the CLOB.

## Status

**Self-hosted MVP.** Every user runs their own backend on `localhost:8000`. Hosted backend with Privy onboarding is tracked in [issue #14](https://github.com/altanapps/speedy/issues/14).

## What you need

| | Requirement | Where | Notes |
|---|---|---|---|
| 1 | macOS 13+ | — | Apple Silicon recommended |
| 2 | Xcode | Mac App Store | Full Xcode, not just CLT. Required for the `.app` build + signing |
| 3 | Homebrew | https://brew.sh | One-line install |
| 4 | OpenAI API key | https://platform.openai.com/api-keys | ~$0.10 first index build, fractions of a cent per search |
| 5 | Anthropic API key (recommended) | https://console.anthropic.com | ~$0.001/search; big quality win |
| 6 | MetaMask wallet | https://metamask.io | The same wallet you use on polymarket.com |
| 7 | Polymarket account | https://polymarket.com | Funded with USDC + a bit of MATIC for gas |

**About the keys:**

- **OpenAI** is required. Speedy embeds ~46k Polymarket markets with `text-embedding-3-small` so it can match your highlighted text. One-time index build is ~$0.10; per-search is fractions of a cent.
- **Anthropic** is optional but strongly recommended. When set, `/search` reranks the top-10 pgvector candidates with `claude-haiku-4-5`. Big win on ambiguous queries (*"Powell"* — which Powell?). Without it, falls back to embedding-only top-1 with a cosine similarity threshold.
- **Polymarket** isn't an "API key." You export the **private key** of your MetaMask wallet from polymarket.com (Wallet menu → Export private key). You also need your **funder address** — the deposit address polymarket.com shows you, which is your proxy wallet, not your EOA.

All secrets live in a single gitignored `backend/.env` file. Speedy never sends keys anywhere except the corresponding service.

## Install

### 1. Backend

```bash
git clone https://github.com/altanapps/speedy.git
cd speedy/backend

make setup
# Installs postgres@17 + pgvector via brew, creates the speedy db,
# runs migrations, creates an .env from .env.example.
```

Edit `backend/.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...                    # optional but recommended
POLYMARKET_PRIVATE_KEY=0x...                    # export from polymarket.com
POLYMARKET_FUNDER_ADDRESS=0x...                 # your polymarket.com deposit address
POLYMARKET_SIGNATURE_TYPE=2                     # 2 for newer Safe wallets (most accounts);
                                                # 1 for older proxies; 0 for raw EOA
SPEEDY_SEARCH_THRESHOLD=0.4                     # optional: lower = more matches, more noise
```

Then:

```bash
make refresh                     # ~5–15 min, ~$0.10 in OpenAI charges
make serve                       # uvicorn on :8000 — leave running
```

If anything goes sideways: `make doctor` prints a one-screen diagnostic.

### 2. macOS app

```bash
cd ../macos
brew install xcodegen            # one-time
xcodegen generate
open Speedy.xcodeproj
```

In Xcode:

1. Select the **Speedy** target → **Signing & Capabilities** → tick **Automatically manage signing** → pick your **Personal Team** (free; just your Apple ID, no Developer Program needed). Required so macOS Accessibility trust persists across rebuilds.
2. ⌘R to run.
3. macOS prompts for Accessibility — grant via System Settings → Privacy & Security → Accessibility, toggle Speedy on.
4. Highlight text anywhere, double-tap **Control**.

A floating panel appears at your cursor with the matched Polymarket market, current Yes/No prices, and a Buy button. Click Yes/No, set size, hit ⌘↵ to submit. **Esc** dismisses.

### 3. Smoke test

In the menu bar (top of screen), click the bolt icon → **Preview overlay → Matched**. You should see a sample card with prices, Yes/No, and a Buy button. This confirms visuals + IPC without needing a real selection.

For an actual trade test: ⌃⌃ on a Fed-related sentence → set size to **1** → click Buy. Order should land in seconds. Verify on polymarket.com.

## Troubleshooting

### Hotkey doesn't fire

By far the most common issue. macOS Accessibility trust pins to the binary's code signature; every Xcode rebuild changes the signature, so the trust entry from a previous build silently doesn't apply.

Recovery:

```bash
tccutil reset Accessibility tech.nuff.speedy
```

Then **⌘.** → **⌘R** in Xcode. Grant the fresh AX prompt.

If Xcode is connected as a debugger, sometimes TCC silently blocks trust. Workaround: launch standalone:

```bash
open ~/Library/Developer/Xcode/DerivedData/Speedy-*/Build/Products/Debug/Speedy.app
```

Permanent fix: ensure your Personal Team is selected in Signing & Capabilities. xcodegen wipes this on regenerate, so re-set after every `xcodegen generate`.

### Build fails after pulling new code

Stale xcodeproj — new Swift files exist on disk but the project file doesn't reference them:

```bash
cd macos
rm -rf Speedy.xcodeproj
xcodegen generate
open Speedy.xcodeproj
# Re-set Personal Team in Signing & Capabilities
```

### Order fails with "POLYMARKET_FUNDER_ADDRESS is required"

Your `signature_type` is 1 or 2 but the funder address is missing. Find your deposit address on polymarket.com → Wallet → Deposit. That's the proxy address; put it in `.env` as `POLYMARKET_FUNDER_ADDRESS`.

If your wallet is a raw self-custody EOA (USDC sits at your MetaMask address directly, not at a proxy), set `POLYMARKET_SIGNATURE_TYPE=0` and skip the funder address.

### Order fails with "ModuleNotFoundError: py_clob_client"

Your venv doesn't have the trading deps yet:

```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
```

Then ⌃C uvicorn and `make serve` again.

### Order fails with gas / allowance error

Two most common:

- **No MATIC.** Your wallet needs ~$1 worth of MATIC on Polygon for gas. Bridge or buy a tiny amount.
- **USDC not approved.** If your wallet has never traded on Polymarket directly through the website, the CLOB exchange contract may not have spend allowance. Place one $1 trade through polymarket.com itself — that auto-grants the approval.

### `/search` returns "No tradeable market" for everything

Two possibilities:

- **Index isn't populated.** Run `make refresh` and watch for a `RefreshStats(fetched=N, embedded=M, ...)` line at the end. If `M == 0`, your `OPENAI_API_KEY` is missing or invalid.
- **Threshold is too tight.** Default `SPEEDY_SEARCH_THRESHOLD` is `0.55`. With LLM rerank disabled, this is strict. Lower to `0.4` in `.env` and restart uvicorn.

### Backend logs show "Multiple head revisions"

Two migrations with the same revision number (rare, only if you edit migrations manually). Check `backend/alembic/versions/` for two files starting with the same digit; the higher one should have its `revision` and `down_revision` bumped.

## Layout

- [`macos/`](./macos/) — native macOS app (Swift + SwiftUI). XcodeGen project, design system, hotkey monitor, AX selection capture, overlay, trade controls.
- [`backend/`](./backend/) — Python + FastAPI service. Polymarket Gamma index, embeddings refresh, `/search` (with rerank), `/order` (via py-clob-client).
- [`eval/`](./eval/) — labeled selection→market evaluation corpus (issue #10 for the harness).
- [`PRD.md`](./PRD.md) — full product spec.
- [`claude-design/`](./claude-design/) — canonical design system + interactive prototype.
- [`DESIGN.md`](./DESIGN.md) — SwiftUI translation guide for the design system.

## Not what Speedy is

- Not a Polymarket replacement. Speedy doesn't replicate Polymarket's UI; it just collapses the path *to* a Polymarket trade.
- Not investment advice. Speedy doesn't tell you what to bet on. It finds the market that matches what you highlighted.
- Not a hosted service. Every user runs their own backend at v0.1.

## Contributing

Issues and PRs welcome. The high-leverage open questions are tracked as issues — [#10 (eval harness)](https://github.com/altanapps/speedy/issues/10) and [#14 (Privy onboarding)](https://github.com/altanapps/speedy/issues/14) are the most useful places to plug in if you want to help.

## License

[AGPL-3.0](./LICENSE). Free for self-hosting, forking, and modification. If you run a modified version as a network service, you must publish your modifications under the same license.

## Disclaimer

Speedy uses your own private key to sign trades on Polymarket. Trades are final. You are responsible for your own funds and your own jurisdiction's rules around prediction markets. Polymarket is geo-blocked from US IPs; Speedy does not change that.
