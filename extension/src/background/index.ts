// MV3 service worker. Lives idle until a content script or popup posts a
// message, then handles backend HTTP (search, order, config). Phase 1 is
// just a stub that proves the worker loads — real wiring lands in step 3.

console.log('[speedy] background service worker loaded');

chrome.runtime.onInstalled.addListener((details) => {
  console.log('[speedy] installed:', details.reason);
});
