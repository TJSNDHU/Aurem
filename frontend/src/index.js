import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { installSentinel } from "./lib/sentinel";

console.log('[AUREM] Autonomous AI Workforce Platform Starting...');

// ═══════════════════════════════════════════════════════════════
// AUREM SENTINEL — Client-side error observability + auto-heal
// Installs global error listeners + fetch sniffer that ship to
// /api/sentinel/client-error for admin review. AI diagnosis is
// triggered manually by an admin; code is never auto-modified.
// ═══════════════════════════════════════════════════════════════
installSentinel();

// ═══════════════════════════════════════════════════════════════
// STALE-PREVIEW-POD URL AUTO-HEAL (Apr 2026)
// ---------------------------------------------------------------
// Production bundles deployed to aurem.live can carry a baked-in
// REACT_APP_BACKEND_URL pointing to a now-dead preview pod
// (e.g. live-support-3.*.preview.emergentagent.com). When the pod
// is rotated every new fork, 205+ fetch() call-sites across the app
// blow up with 404/504 until a fresh deploy happens.
//
// This patch monkey-patches window.fetch so that when we're running
// on the production host (aurem.live), ANY request to a known stale
// preview-pod hostname is rewritten to same-origin before the network
// call leaves the browser. Rest of the fetch behavior stays untouched.
// ═══════════════════════════════════════════════════════════════
(function installApiUrlHealer() {
  try {
    if (typeof window === 'undefined' || !window.fetch) return;
    const host = window.location.hostname || '';
    const isProd =
      !host.includes('preview.emergentagent.com') &&
      !host.includes('emergent.host') &&
      !host.includes('localhost') &&
      !host.includes('127.0.0.1');
    if (!isProd) return; // only heal on real production hosts

    const STALE_MARKERS = [
      '.preview.emergentagent.com',
      '.emergent.host',
    ];
    const origFetch = window.fetch.bind(window);
    window.fetch = function patchedFetch(input, init) {
      try {
        let urlStr = typeof input === 'string' ? input : (input && input.url) || '';
        if (urlStr && /^https?:\/\//i.test(urlStr)) {
          const u = new URL(urlStr);
          const isStale =
            u.hostname !== window.location.hostname &&
            STALE_MARKERS.some((m) => u.hostname.endsWith(m));
          if (isStale) {
            const healed = window.location.origin + u.pathname + u.search + u.hash;
            if (typeof input === 'string') {
              input = healed;
            } else {
              input = new Request(healed, input);
            }
          }
        }
      } catch (_e) { /* swallow and fall through */ }
      return origFetch(input, init);
    };
    console.log('[AUREM] API URL auto-healer installed (production mode)');
  } catch (e) {
    console.warn('[AUREM] API URL healer install failed:', e);
  }
})();

// ═══════════════════════════════════════════════════════════════
// CHUNK LOAD ERROR AUTO-RECOVERY
// ---------------------------------------------------------------
// When a stale Service Worker / stale HTML references Webpack chunks
// that no longer exist (post-deploy), React throws `ChunkLoadError`
// or "Unexpected token '<'". We detect this and force a one-time
// hard reload after clearing the SW caches, so users don't get stuck
// on a blank / broken screen.
// ═══════════════════════════════════════════════════════════════
const RELOAD_FLAG = '__aurem_chunk_reload__';

async function nukeCachesAndReload() {
  try {
    if (sessionStorage.getItem(RELOAD_FLAG)) return; // already tried once in this session
    sessionStorage.setItem(RELOAD_FLAG, '1');

    if ('caches' in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    }
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
    }
  } catch (e) {
    console.warn('[AUREM] Cache nuke failed:', e);
  }
  // Hard reload, bypassing HTTP cache
  window.location.reload(true);
}

function isChunkError(err) {
  if (!err) return false;
  const msg = (err.message || err.toString() || '').toLowerCase();
  return (
    msg.includes('chunkloaderror') ||
    msg.includes('loading chunk') ||
    msg.includes('loading css chunk') ||
    msg.includes("unexpected token '<'") ||
    msg.includes('unexpected token <') ||
    err.name === 'ChunkLoadError'
  );
}

window.addEventListener('error', (event) => {
  if (isChunkError(event.error) || isChunkError(event)) {
    console.warn('[AUREM] ChunkLoadError detected, recovering...');
    nukeCachesAndReload();
  }
});

window.addEventListener('unhandledrejection', (event) => {
  if (isChunkError(event.reason)) {
    console.warn('[AUREM] ChunkLoadError (promise) detected, recovering...');
    nukeCachesAndReload();
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// REGISTER service worker for PWA offline support + push notifications
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then((reg) => {
        console.log('[AUREM] Service Worker registered:', reg.scope);
        // When a new SW is found, tell it to skip waiting immediately
        reg.addEventListener('updatefound', () => {
          const nw = reg.installing;
          if (nw) {
            nw.addEventListener('statechange', () => {
              if (nw.state === 'installed' && navigator.serviceWorker.controller) {
                // New version available — activate it now
                nw.postMessage({ type: 'SKIP_WAITING' });
              }
            });
          }
        });
      })
      .catch((err) => console.warn('[AUREM] Service Worker registration failed:', err));

    // When the controlling SW changes (new version activated), reload ONCE
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });
  });
}
