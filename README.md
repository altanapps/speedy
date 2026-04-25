# Speedy

Turn any selected text — anywhere on your screen — into a tradeable position in two clicks.

Highlight a phrase in an article, hold a hotkey, and a transparent overlay appears at your cursor with the matched market (a Kalshi contract, an equity ticker, a perpetual). Pick side and size; `⌘↵` confirms; the order routes to whichever venue you've pre-linked.

## Status

Pre-MVP. PRD drafted, web mock built, no production code yet.

## Layout

- [`PRD.md`](./PRD.md) — full product spec (overview, architecture, MVP scope, risks).
- [`DESIGN.md`](./DESIGN.md) — visual + interaction design schema (tokens, components, motion).
- [`mock/index.html`](./mock/index.html) — interactive web mock of the cursor-attached overlay. Open in a browser, highlight any underlined phrase, or press `E` for a page-level market.

## Open decisions

See `PRD.md` §10. Top:

1. Substrate for v0 — native macOS vs Chrome extension.
2. Wallet UX — sign every trade vs session key.
3. Monetization — flat SaaS vs Polymarket referral / volume rebate.
