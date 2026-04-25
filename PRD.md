# Speedy — Product Requirements Document

## 1. Overview

Speedy is a native desktop app that turns any selected text — anywhere on your screen — into a tradeable position in two clicks. Highlight "Powell signaled patience" in an article, hold a hotkey, and a transparent overlay appears at your cursor with the matched market (a Polymarket contract on Fed action, etc.). One click picks side and size; ⌘↵ confirms; the order routes to whichever venue you've pre-linked.

The product thesis: the bottleneck on retail trading isn't decision quality, it's the 90 seconds between forming a thesis and getting a position on. Speedy collapses that to ~3 seconds.

## 2. Problem

Today, when a user reading research, news, or a Slack message sees something they want to bet on:
1. They switch apps to their broker / Polymarket / Hyperliquid.
2. They search the asset (often guessing the canonical name).
3. They navigate the order ticket.
4. By the time they're done, the conviction has either decayed or the price has moved.

Every step is friction the trader pays for in either missed entries or in not bothering at all.

## 3. Target users

- **Primary (MVP):** Prediction-market users on Polymarket. Currently struggle with discovery — Polymarket has thousands of markets and in-app search is poor. Speedy turns "I just read about X, is there a market on it?" from a 2-minute hunt into a 3-second overlay.
- **Secondary (post-MVP):** Active retail traders / "informed amateurs" who already hold accounts at Robinhood, IBKR, Alpaca, Kalshi, Hyperliquid. Read 2–10 hours/day across news, Twitter, and research.
- **Not a target:** First-time traders. Speedy assumes the user already understands position sizing, leverage, and the venues they've linked.

## 4. Goals & non-goals

### Goals
- **Time-to-position:** Median time from text-selection to confirmed order ≤ 5 seconds.
- **Match quality:** Top-1 entity-to-market match accuracy ≥ 85% on a held-out evaluation set.
- **Reliability:** Order placement success rate ≥ 99% (excluding venue-side rejections).
- **Privacy posture:** No selected text or order metadata leaves the device beyond what's strictly needed for entity resolution and order routing.

### Non-goals (v1)
- Becoming a broker-dealer or custodying funds.
- Portfolio analytics beyond a simple cross-venue P&L view.
- Charting, technical analysis, or research tooling.
- Mobile apps.
- Windows support (deferred to v2).

## 5. User experience

### Core flow
1. User selects text in any app (browser, PDF, Slack, Notes, terminal).
2. User holds the global hotkey (default: hold `⌃`).
3. A floating overlay appears next to the cursor showing the matched market, current price, and a side/size selector.
4. User picks side (defaults to the directionally implied side based on context if confidence is high), adjusts size if needed, and presses `⌘↵` to confirm — or `Esc` to dismiss.
5. Toast confirms fill. Position appears in the menu bar.

### Secondary flows
- **Match disambiguation:** If multiple markets are close in confidence, overlay shows a "swap" dropdown. Arrow keys cycle, `Tab` confirms.
- **Position view:** Click the menu bar icon to see open positions across all linked venues, with aggregate P&L.
- **Settings:** Manage linked accounts, default sizing rules, hotkey, and entity-resolution preferences.

### Failure states
- No match found → overlay shows "No tradeable market for this selection" and dismisses on click.
- Venue auth expired → overlay prompts re-auth inline; original selection preserved.
- Order rejected → toast shows venue-returned reason; one-click retry.

## 6. System architecture

```
[Selected text]
     │
     ▼
[OS capture layer]   ──  Accessibility API + synthetic ⌘C, global hotkey
     │
     ▼
[Entity resolver]    ──  NER + intent classification (local 1-3B model preferred)
     │
     ▼
[Market index]       ──  Unified semantic + symbol search across venues
     │
     ▼
[Overlay UI]         ──  Floating NSPanel; renders match, accepts side/size
     │
     ▼
[Execution router]   ──  Per-venue API clients; user's own credentials
     │
     ▼
[Position store]     ──  Local SQLite + websocket reconciliation
```

### 6.1 OS capture layer
- **macOS:** Global hotkey via `Carbon RegisterEventHotKey` or `NSEvent.addGlobalMonitor`. On trigger, synthesize `⌘C`, read `NSPasteboard.general`, restore prior pasteboard contents within 50ms. Falls back to Accessibility API (`AXUIElementCopyAttributeValue` with `kAXSelectedTextAttribute`) when pasteboard read fails.
- Requires Accessibility permission grant on first launch — onboarding must walk the user through System Settings → Privacy & Security → Accessibility.

### 6.2 Entity resolver
- **Input:** Raw selected text, surrounding context (up to 200 chars before/after if available via Accessibility tree).
- **Output:** Structured entities `{type, canonical_id, confidence, implied_direction?}`.
- **MVP:** Remote inference via a hosted LLM (Claude Haiku or similar) — single round-trip, ~$0.0002/call. No local model until cost crosses ~$5/MAU.
- **Post-MVP:** Fine-tuned small LM (target: 1–3B params, quantized, runs on Apple Silicon Neural Engine) for offline + privacy.
- **Categories:**
  - `event` — semantic match against Polymarket question index (MVP focus)
  - `ticker` — direct symbol matches (NVDA, BTC, SPY) — post-MVP
  - `asset_name` — canonical mapping (gold → GLD/XAUUSD, oil → CL=F) — post-MVP
  - `macro_phrase` — ranked candidate list (inflation → CPI prints, TIP, etc.) — post-MVP

### 6.3 Market index + retrieval

The core retrieval task: given a highlighted phrase and its page context, search across **all active Polymarket markets** and rank the most relevant.

**Index build (server-side, hosted):**
- Pull all active Polymarket markets every ~5 min via the Gamma / CLOB APIs.
- For each market, build a document combining: question + description + resolution criteria + tags + end-date.
- Embed with a small embedding model (e.g. `text-embedding-3-small` or `voyage-3-lite`).
- Store vectors + metadata in Postgres + pgvector. Active set is typically 5–20k markets.

**Retrieval (per highlight):**
1. Client sends `{highlight, surrounding_context, page_title}` to the server.
2. Server builds a query string (the highlight, augmented by a 1-line context summary if available) and embeds it.
3. pgvector returns top-50 by cosine similarity, with metadata.
4. **MVP path:** apply a confidence threshold to top-1; if below, return "no match" rather than show a weak result. Return top-1 to the client.
5. **v0.2 path:** rerank the top-50 with an LLM call (Haiku) prompted on highlight + context, returning top-3 with a short rationale per result.
6. Results are streamed back to the overlay; first market renders within ~200ms.

**Why this works for Polymarket specifically:**
- Market questions are short, well-formed sentences — clean embedding targets, far cleaner than typical RAG corpora.
- ~5–20k active markets fits in pgvector with sub-100ms p95 latency on a single small instance.
- Surrounding context is the disambiguator: "Powell" alone is ambiguous; "Powell signaled patience on rate cuts" is not. The pipeline must carry that context through, not just embed the highlight in isolation.

**Why client-side index doesn't work:**
- Active market set churns hourly; clients would need constant sync.
- Embedding model + vector ops on-device adds complexity for no privacy gain (we don't store queries).

Post-MVP: extend the index to Kalshi (similar question-corpus shape), equities/ETFs (Alpaca for breadth), perpetuals (Hyperliquid, Binance, dYdX), futures (CME via Polygon). Each venue gets its own document schema; retrieval merges across indexes with venue-aware ranking.

### 6.4 Execution router (the regulatory crux)

**Decision: ship as a UI client, not as a broker.** Speedy never touches funds. The user pre-links each venue and Speedy holds API tokens locally (Keychain on macOS) to submit orders on their behalf.

| Venue | Auth method | Order API | Phase |
|---|---|---|---|
| Polymarket | Wallet signature (EOA) | On-chain via CLOB | **MVP** |
| Kalshi | API key | REST | v0.2 |
| Alpaca | API key | REST | v0.2 |
| Hyperliquid | Wallet signature | REST + websocket | v0.3 |
| IBKR | OAuth + Client Portal | REST | v0.3 |
| Robinhood | Unofficial | — | deferred |

This avoids US broker-dealer registration, MiFID, and custody requirements — Speedy's legal posture is closer to a portfolio aggregator (Plaid-adjacent) than a broker. **Compliance review still required before launch** — see §10.

### 6.5 Overlay UI
- macOS: `NSPanel` with `.nonactivatingPanel`, `.canJoinAllSpaces`, `.fullScreenAuxiliary`.
- Position: anchored to cursor at `mouseUp`, with screen-edge collision avoidance.
- Dismissal: `Esc`, click outside, or 8-second idle timeout.
- Always-on-top, transparent background, ~320×140px default.

### 6.6 Position store
- Local SQLite database for orders + reconciled fills.
- Per-venue websocket clients maintain real-time position state.
- Optimistic UI on order submit; reconciles on fill confirmation.
- Menu bar item shows aggregate P&L; click opens detail window.

## 7. MVP scope (v0.1)

Ship the smallest end-to-end loop that proves the core hypothesis:

**Included:**
- macOS only (Apple Silicon).
- **One venue: Polymarket.** Wallet linking via WalletConnect or imported EOA.
- Entity resolver covers semantic match against the Polymarket question index. Remote LLM inference, no local model.
- Floating overlay with side (Yes/No) + size + confirm.
- Menu bar position view (Polymarket positions only).
- Basic onboarding for Accessibility permission + wallet linking.
- Geo-handling: explicit non-US positioning, IP check at install, clear ToS.

**Explicitly excluded from MVP:**
- Equities, perpetuals, futures (v0.2+).
- Kalshi, Alpaca, Hyperliquid, IBKR (v0.2+).
- Windows.
- Disambiguation dropdown (just show top-1 in MVP; if confidence < threshold, show "no match").
- Cross-venue P&L aggregation.
- Default-direction inference from context (require explicit Yes/No click in MVP).
- Local NER model (remote inference only).

## 8. Phases

| Phase | Scope | Approx. timeline |
|---|---|---|
| v0.1 — MVP | macOS, Polymarket only, top-1 match, remote NER | 6–8 weeks |
| v0.2 — Breadth | + Kalshi, Alpaca, disambiguation UI | +4 weeks |
| v0.3 — Depth | + Hyperliquid, IBKR, direction inference, P&L view | +4 weeks |
| v1.0 — Public launch | Hardened auth, compliance review complete, marketing site | +6 weeks |
| v2.0 — Windows | UI Automation port | post-launch |

## 9. Recommended stack

- **App shell:** Swift + SwiftUI for native macOS. Avoid Electron/Tauri — the floating overlay, system hotkey, and Accessibility API integration are fragile through web wrappers.
- **Core logic:** Swift, with Rust crate for any cross-platform pieces that need to port to Windows later (entity resolution client, market index client).
- **Entity resolution (MVP):** hosted LLM (Claude Haiku or similar) via FastAPI proxy — never call provider directly from client (key safety).
- **Local NER model (post-MVP):** CoreML-converted fine-tuned model, ~1B params quantized to int4. Llama.cpp + Metal as fallback runtime.
- **Backend services (market index, NER proxy):** Python (FastAPI) + Postgres + pgvector, hosted on Fly.io or Railway for v0.1.
- **Local storage:** SQLite via GRDB.swift. Credentials in Keychain.

## 10. Risks & open questions

### Legal / regulatory (highest priority)
- **Polymarket US restriction.** Polymarket geo-blocks US IPs. Speedy must (a) position explicitly as a non-US product, (b) IP-gate at install, (c) make geo posture clear in ToS. If Speedy is found to "facilitate" US access, regulatory exposure is non-trivial. Resolve before any public launch.
- Even as a "UI client," routing orders on a user's behalf may trigger investment advisor registration in some jurisdictions, especially if Speedy makes any directional recommendation. **Need legal review before any direction-inference feature ships.**
- Storing wallet signing keys / API tokens with order-placement scope creates a security/liability surface — needs threat model + key rotation policy.

### Technical
- Pasteboard hijacking on `⌘C` synthesis can race with the user's own clipboard usage. Need rigorous save/restore.
- Accessibility API behavior varies wildly across apps (Electron apps in particular). Need a per-app fallback strategy.
- Polymarket order placement requires wallet signing — UX of "sign every trade" vs "session key" needs design before MVP build.
- Polymarket markets resolve on-chain; fill confirmation latency is seconds-to-minutes, not milliseconds. Position-store optimism model must handle this.

### Product
- What's the right default size? Per-user fixed dollar amount? % of portfolio? Per-market rules?
- How aggressive should direction inference be? Showing "YES" by default when the article is bullish creates a UX advantage but also a "the app talked me into it" liability.
- Confirmation friction: is `⌘↵` enough, or do we need a secondary confirm for orders above some threshold?

### Decisions to confirm with stakeholders
1. ✅ MVP venue: Polymarket only (locked).
2. Lock MVP to macOS only?
3. Confirm "UI client, never custodial" as the v1 model?
4. Acceptable to ship without direction inference in MVP?

## 11. Success metrics

- **North star:** Median time from selection to confirmed order, measured per user per week.
- **Activation:** % of new users who place a trade within 7 days of install.
- **Retention:** D30 retention of users who place ≥ 1 trade in week 1.
- **Match quality:** Top-1 accuracy on a labeled eval set of 500 selections drawn from real user logs (with consent).
- **Reliability:** P95 overlay-render latency from hotkey to visible UI < 200ms.

## 12. Open files for the build

- `/eval/` — Labeled selection→market eval set. Build this first; it's the only honest measure of whether the entity resolver is working.
- `/docs/legal/` — Compliance memo from outside counsel covering UI-client model, Polymarket geo posture, and per-venue ToS review.
- `/threat-model.md` — Security model for wallet signing, token storage, and order-scoped API keys.
