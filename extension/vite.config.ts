import { crx, defineManifest } from '@crxjs/vite-plugin';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// MV3 manifest. Kept inline so changes ship with one diff (vs. a separate
// manifest.json that has to be hand-edited and easily drifts from the code
// it references). The crxjs plugin rewrites paths to the built bundles.
const manifest = defineManifest({
  manifest_version: 3,
  name: 'Speedy',
  version: '0.1.0',
  description:
    'Trade where you read. Highlight any text, hit the hotkey, get the matched Polymarket market at your cursor.',
  action: {
    default_popup: 'src/popup/index.html',
    default_title: 'Speedy',
  },
  background: {
    service_worker: 'src/background/index.ts',
    type: 'module',
  },
  content_scripts: [
    {
      matches: ['<all_urls>'],
      js: ['src/content/index.ts'],
      run_at: 'document_idle',
    },
  ],
  permissions: ['storage', 'activeTab'],
  // Phase 1 talks only to the self-hosted local backend, same as the macOS
  // app. Hosted backend domain gets added when issue #14 lands.
  host_permissions: ['http://localhost:8000/*'],
  commands: {
    'open-popup': {
      suggested_key: {
        default: 'Alt+Shift+S',
        mac: 'Alt+Shift+S',
      },
      description: 'Open Speedy popup',
    },
  },
});

export default defineConfig({
  plugins: [react(), crx({ manifest })],
  // crxjs needs a stable HMR port so the content-script HMR client can
  // reconnect across reloads. Without this, every `npm run dev` picks a
  // fresh port and the page-side WebSocket dies.
  server: {
    port: 5173,
    strictPort: true,
    hmr: { port: 5173 },
  },
});
