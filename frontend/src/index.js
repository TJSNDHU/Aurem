// regression test 2
// regression test 3
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { installSentinel } from "./lib/sentinel";
// iter 322ff — incident reporter auto-wires window.onerror +
// unhandledrejection → POST /api/incident/report. Side-effect import only.
import "./utils/incidentReporter";

console.log('[AUREM] Autonomous AI Workforce Platform Starting...');

// ════════════════════════════════════════════════════
// AUREM SENTINEL — Client-side error observability + auto-heal
// Installs global error listeners + fetch sniffer that ship to
// /api/sentinel/client-error for admin review. AI diagnosis is
// triggered manually by an admin; code is never auto-modified.
// ═══
installSentinel();

(function installApiUrlHealer() {
  try {
    if (typeof window === 'undefined' || !window.fetch) return;
    const host = window.location.hostname || '';
    const isProd =
      !host.includes('preview.emergentagent.com') &&
      !host.includes('emergent.host') &&
      !host.includes('localhost') &&
      !host.includes('127.0.0.1');
    if (!isProd) return;

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
            const healed = window.location.origin + u.pathname + u.search + u.hash;        if (typeof input === 'string') {          input = healed;     else { input = new Request(healed, input); }}}} catch (_e) { /* swallow and fall through */ }return origFetch(input, init);};console.log('[AUREM] API URL auto-healer installed (production mode)');} catch (e) { console.warn('[AUREM] API URL healer install failed:', e); }D})();