// Content script. Runs in every tab's main frame at document_idle. Phase 1
// stub just confirms it loaded; selection capture, hotkey, and overlay
// mount land in steps 4–6.

console.log('[speedy] content script loaded on', location.host);
