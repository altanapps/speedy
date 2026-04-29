# Speedy — browser extension

Browser-extension version of [Speedy](../README.md). Talks to the same self-hosted backend at `http://localhost:8000` as the [macOS app](../macos/README.md) — no new backend wiring needed beyond CORS.

> **Status:** Phase 1 scaffold. Loads, surfaces a popup with backend health, runs a content-script and service-worker stub. Selection capture, hotkey, overlay, and trade flow land in subsequent commits.

## Develop

```bash
cd extension
npm install
npm run dev
```

Then in Chrome:

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right)
3. **Load unpacked** → select `extension/dist/`
4. Click the Speedy icon in the toolbar — popup should show backend health

The dev server keeps `dist/` updated; reload the extension from `chrome://extensions` after most changes (popup HMR works without a reload).

## Build

```bash
npm run build
```

Output is a packed extension in `extension/dist/`, ready to load unpacked or zip for the Web Store.

## Architecture

```
src/
├── background/      service worker — backend HTTP, message router
├── content/         injected on every page — hotkey, selection capture, overlay
├── popup/           toolbar popup — settings + backend status
└── lib/             (later) typed API client, chrome.storage helpers
```

The plan is to port the macOS overlay, trade controls, and design tokens 1:1 to React-in-Shadow-DOM. See `macos/Sources/Speedy/Overlay/` for the source of truth on layout and tokens.

## Hotkey

The macOS app uses a global double-Ctrl. Chrome's `commands` API can't bind same-modifier double-tap, so the eventual pattern will be a content-script `keydown` listener (matches the macOS UX on regular pages) plus an `Alt+Shift+S` fallback registered through `commands` (works system-wide but only opens the popup, not the overlay). The `Alt+Shift+S` binding is wired in this scaffold; the double-tap handler lands later.

## Permissions

- `storage` — settings (backend URL, default size, hotkey config)
- `activeTab` — needed when reading the selection from the active tab via the popup
- `host_permissions: http://localhost:8000/*` — only the local backend. Tightest possible scope until a hosted backend exists.

The extension does not have `<all_urls>` host permission. The content script is declared with `<all_urls>` *match* (so it injects everywhere) but does not get cross-origin fetch privileges to those origins — all backend traffic goes through the service worker, which is restricted to localhost.
