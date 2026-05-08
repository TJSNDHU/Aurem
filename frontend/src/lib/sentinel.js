/**
 * AUREM Sentinel — Frontend Error Observability + Auto-Heal
 * ═══════════════════════════════════════════════════════════════════
 *
 * Captures client-side errors automatically (no F12 needed) and ships them
 * to the backend for admin review + optional AI diagnosis.
 *
 * TRUST-BUT-VERIFY MODEL:
 *  ▸ Tier 1 — Auto-heal KNOWN patterns silently (no AI)
 *  ▸ Tier 2 — All errors captured + POSTed to /api/sentinel/client-error
 *  ▸ Tier 3 — Admin may trigger Claude diagnosis per-error in dashboard
 *  ▸ AI NEVER modifies code or deploys. Human is always in the loop.
 *
 * Captures:
 *  ▸ window.onerror           — JS runtime exceptions
 *  ▸ unhandledrejection       — failed Promises
 *  ▸ console.error (wrapped)  — React errors + 3rd-party SDK failures
 *  ▸ fetch responses          — 4xx/5xx + network failures
 *
 * Safety:
 *  ▸ Dedup by signature hash — max 3 sends per signature per 5 min
 *  ▸ Max 40 sends per session per 5 min
 *  ▸ Never captures: login bodies, tokens, passwords
 *  ▸ Disabled on localhost/127.0.0.1 (dev noise)
 */

const SENTINEL_VERSION = "1.1.0";
const INGEST_PATH = "/api/sentinel/client-error";
// iter 264 — aggressive dampening to prevent prod log floods.
// Each unique error signature is reported AT MOST ONCE per window.
// Session-wide cap is halved to 10/window. Most errors are transient
// and already visible in backend logs — Sentinel is for novel issues.
const MAX_SENDS_PER_SIGNATURE = 1;
const SIG_WINDOW_MS = 5 * 60 * 1000;
const MAX_SESSION_SENDS = 10;

// Known-404 / optional endpoints — never capture. These are polled by
// features that gracefully handle a 404, so reporting them is noise.
const IGNORED_URL_FRAGMENTS = [
  "/api/sentinel/client-error",
  "/api/sentinel/heartbeat",
  "/api/voice-agent/health",
  "/api/ora/health",
  "/api/leads/health",
  "/api/system/overview/public",
  "/api/service-catalog",
  "/api/services/catalog",
  "/robots.txt",
  "/sitemap.xml",
  "/llms.txt",
  "/llms-full.txt",
  "/favicon.ico",
  // 3rd-party / browser-extension telemetry (not our problem)
  "chrome-extension://",
  "moz-extension://",
  "googleads",
  "doubleclick",
  "google-analytics",
];

function _isIgnoredUrl(url) {
  if (!url) return true;
  const u = String(url).toLowerCase();
  return IGNORED_URL_FRAGMENTS.some((frag) => u.includes(frag));
}

// Routes that handle sensitive bodies — never capture bodies for these
const SENSITIVE_URL_FRAGMENTS = [
  "/api/auth/login",
  "/api/auth/admin/login",
  "/api/auth/google/callback",
  "/api/platform/auth/login",
  "/api/platform/auth/register",
  "/api/bin-auth/",
  "/api/password",
  "/api/reset-password",
];

function _isSensitive(url) {
  if (!url) return false;
  const u = String(url).toLowerCase();
  return SENSITIVE_URL_FRAGMENTS.some((frag) => u.includes(frag));
}

function _hostname() {
  try { return window.location.hostname; } catch { return ""; }
}

function _sessionId() {
  try {
    let s = sessionStorage.getItem("aurem_sentinel_session");
    if (!s) {
      s = "s_" + Math.random().toString(36).slice(2, 10) + "_" + Date.now().toString(36);
      sessionStorage.setItem("aurem_sentinel_session", s);
    }
    return s;
  } catch { return "s_anon"; }
}

function _userEmail() {
  try {
    const raw = localStorage.getItem("aurem_user") ||
                localStorage.getItem("platform_user") ||
                sessionStorage.getItem("aurem_platform_user") ||
                "";
    if (!raw) return null;
    const u = JSON.parse(raw);
    return (u && (u.email || u.user?.email)) || null;
  } catch { return null; }
}

function _tenantBin() {
  try {
    const raw = localStorage.getItem("aurem_user") ||
                localStorage.getItem("platform_user") || "";
    if (!raw) return null;
    const u = JSON.parse(raw);
    return (u && (u.bin || u.business_id || u.user?.bin)) || null;
  } catch { return null; }
}

// Simple FNV-1a-ish hash for signature dedup (fast, non-crypto)
function _hash(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return ("00000000" + h.toString(16)).slice(-8);
}

function _signature(evt) {
  return _hash(
    (evt.type || "") + "|" +
    (evt.message || "").slice(0, 200) + "|" +
    (evt.status_code || "") + "|" +
    (evt.url || "").split("?")[0].slice(0, 160)
  );
}

// Network-failure suppression rules (iter 320.3) — eliminates ~95% of
// false-positive "🌐 Network Failure" entries that flooded the Sentinel
// console. None of the suppressed events are actionable bugs:
//   - Polling endpoints that fire every 30-60s catch every transient blip
//   - Hidden tabs (laptop sleep, background tab) emit "Failed to fetch"
//     when the OS suspends the network stack
//   - Single-shot fetch failures with no repeat are almost always
//     transient connectivity, not a real outage
const POLLING_URL_FRAGMENTS = [
  "/api/public/aurem-stats",
  "/api/public/config",
  "/api/health",
  "/api/admin/sentinel/overview",
  "/api/admin/pillars-map/overview",
  "/api/admin/pillars-map/heartbeat",
  "/api/pillars/health",
  "/api/agents/board/rollup",
  "/api/agents/board/pulse",
  "/api/admin/system-pulse-live",
  "/api/admin/truth-ledger",
  "/api/admin/transparency/wall",
  "/api/admin/autopilot/status",
  "/api/admin/autopilot/live-log",
  "/api/admin/autonomous-repair",
  "/api/admin/deploy-drift",
  "/api/admin/cache/stats",
  "/api/admin/builder/stats",
  "/api/admin/evolver/status",
  "/api/admin/legion/health",
  "/api/admin/wiring-audit",
  "/api/admin/system-audit",
  "/api/admin/db-indexes/status",
  "/api/admin/breakers/status",
  "/api/admin/mission-control/",
  "/api/empire-hud/nodes",
  "/api/customer/pixel/status",
];

// Endpoints that legitimately take >20s — single fetch failure on these
// is far more likely to be a browser timeout / nav-away than a real
// backend outage. Tracked separately so we can require multiple repeats
// before reporting.
const SLOW_LEGITIMATE_FRAGMENTS = [
  "/api/qa/pulse/run-now",
  "/api/seo-audit/scan",
];

function _isPollingUrl(url) {
  if (!url) return false;
  const u = String(url).toLowerCase();
  return POLLING_URL_FRAGMENTS.some((frag) => u.includes(frag.toLowerCase()));
}

function _isSlowLegitimateUrl(url) {
  if (!url) return false;
  const u = String(url).toLowerCase();
  return SLOW_LEGITIMATE_FRAGMENTS.some((frag) => u.includes(frag.toLowerCase()));
}

// Network-failure repeat counter (signature → first-seen ts + count).
// Used to require ≥2 failures in 5 min before reporting transient blips.
const _netFailHistory = new Map();
function _shouldReportNetworkFailure(signature, url) {
  // Always report failures on critical user-action endpoints (auth/billing).
  // For polling + slow-legit URLs, require repeat behaviour.
  const requireRepeat = _isPollingUrl(url) || _isSlowLegitimateUrl(url);
  if (!requireRepeat) return true;

  const now = Date.now();
  const entry = _netFailHistory.get(signature);
  if (!entry || (now - entry.first_ts) > 5 * 60 * 1000) {
    _netFailHistory.set(signature, { first_ts: now, count: 1 });
    return false; // first occurrence — likely transient, suppress
  }
  entry.count += 1;
  return entry.count >= 2; // repeat within 5 min — real signal
}

// iter 271 — hard global cooldown. No matter what, Sentinel will not POST
// more than ONE event per N seconds. Prevents floods during pod restart
// windows when every polled endpoint briefly 5xxs.
const GLOBAL_COOLDOWN_MS = 10 * 1000;
let _lastShipAt = 0;

// iter 281.5 — module-level state declarations (were referenced but
// never declared causing ReferenceError on first _allowSend call).
// SIG_WINDOW_MS + MAX_SESSION_SENDS are declared at the top of the file.
let _sessionSends = 0;
let _sessionSendsWindowStart = Date.now();
const _sigHistory = new Map();

function _allowSend(signature) {
  const now = Date.now();

  // Hard global cooldown — if we shipped anything in the last 10s, skip.
  if (now - _lastShipAt < GLOBAL_COOLDOWN_MS) {
    return false;
  }

  // Reset session window every 5 min
  if (now - _sessionSendsWindowStart > SIG_WINDOW_MS) {
    _sessionSends = 0;
    _sessionSendsWindowStart = now;
    _sigHistory.clear();
  }
  if (_sessionSends >= MAX_SESSION_SENDS) return false;
  const s = _sigHistory.get(signature);
  if (!s) {
    _sigHistory.set(signature, { count: 1, first_ts: now });
    _sessionSends += 1;
    _lastShipAt = now;
    return true;
  }
  if (s.count >= MAX_SENDS_PER_SIGNATURE) return false;
  s.count += 1;
  _sessionSends += 1;
  _lastShipAt = now;
  return true;
}

function _apiBase() {
  // Reuse the smart resolver logic from lib/api.js (but standalone to avoid
  // an import cycle). On aurem.live / custom hosts → same-origin. On preview
  // → env var. On localhost → localhost:8001.
  try {
    const host = window.location.hostname || "";
    if (host.includes("localhost") || host.includes("127.0.0.1")) {
      return "http://localhost:8001";
    }
    if (!host.includes("preview.emergentagent.com") && !host.includes("emergent.host")) {
      return window.location.origin;
    }
    return (typeof process !== "undefined" && process.env && process.env.REACT_APP_BACKEND_URL) ||
           window.location.origin;
  } catch {
    return "";
  }
}

async function _shipEvent(evt) {
  const sig = _signature(evt);
  if (!_allowSend(sig)) return;

  const payload = {
    type: evt.type,
    message: evt.message,
    stack: evt.stack,
    url: evt.url,
    method: evt.method,
    status_code: evt.status_code,
    user_agent: (navigator && navigator.userAgent) ? navigator.userAgent.slice(0, 400) : "",
    session_id: _sessionId(),
    release_hash: (typeof process !== "undefined" && process.env && process.env.REACT_APP_RELEASE) || "",
    hostname: _hostname(),
    page_url: (window.location && window.location.href) ? window.location.href.slice(0, 500) : "",
    user_email: _userEmail(),
    tenant_bin: _tenantBin(),
    extra: evt.extra || null,
  };

  try {
    const base = _apiBase();
    // Use keepalive so events survive page unload
    await fetch(base + INGEST_PATH, {
      method: "POST",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch {
    /* never let the sentinel itself throw */
  }
}

// ═════════════════════════════════════════════════════════════
// Layer 1 — Console Listener (wrap, don't replace)
// ═════════════════════════════════════════════════════════════
function _installConsoleWrap() {
  const orig = window.console.error;
  window.console.error = function patchedConsoleError(...args) {
    try {
      const msg = args
        .map((a) => (a instanceof Error ? (a.stack || a.message) : (typeof a === "string" ? a : JSON.stringify(a))))
        .join(" ");
      // Skip internal sentinel + common framework noise
      if (!msg.includes("[AUREM Sentinel]")) {
        _shipEvent({
          type: "console_error",
          message: msg.slice(0, 2000),
          stack: null,
          url: window.location?.href || "",
        });
      }
    } catch { /* swallow */ }
    return orig.apply(this, args);
  };
}

function _installErrorHandlers() {
  window.addEventListener("error", (event) => {
    try {
      const err = event.error;
      _shipEvent({
        type: "js_exception",
        message: (err && err.message) || event.message || String(event) || "unknown",
        stack: (err && err.stack) || null,
        url: event.filename || "",
        extra: { lineno: event.lineno, colno: event.colno },
      });
    } catch { /* swallow */ }
  });

  window.addEventListener("unhandledrejection", (event) => {
    try {
      const r = event.reason;
      _shipEvent({
        type: "unhandled_rejection",
        message: (r && (r.message || r.toString())) || "Unhandled promise rejection",
        stack: (r && r.stack) || null,
        url: window.location?.href || "",
      });
    } catch { /* swallow */ }
  });

  // Resource load failures (img/script/link)
  window.addEventListener("error", (event) => {
    try {
      const tgt = event.target;
      if (tgt && (tgt.tagName === "IMG" || tgt.tagName === "SCRIPT" || tgt.tagName === "LINK")) {
        _shipEvent({
          type: "resource_load_failure",
          message: `${tgt.tagName} failed to load`,
          url: tgt.src || tgt.href || "",
        });
      }
    } catch { /* swallow */ }
  }, true); // capture phase to catch resource errors
}

// ═════════════════════════════════════════════════════════════
// Layer 2 — Network Sniffer (fetch wrapper only — XHR skipped
// because Stripe/Twilio SDKs break if we patch XHR.prototype).
// ═════════════════════════════════════════════════════════════
function _installFetchSniffer() {
  if (!window.fetch) return;
  const orig = window.fetch.bind(window);
  window.fetch = async function patchedSentinelFetch(input, init) {
    const startedAt = Date.now();
    let method = "GET";
    let url = "";
    try {
      if (typeof input === "string") {
        url = input;
      } else if (input && input.url) {
        url = input.url;
        method = (input.method || "GET").toUpperCase();
      }
      if (init && init.method) method = String(init.method).toUpperCase();
    } catch { /* swallow */ }

    let response;
    try {
      response = await orig(input, init);
    } catch (e) {
      // iter 285.7 — AbortError is NOT a real failure. It fires when:
      //   (a) user navigates away mid-fetch (component unmount cleanup)
      //   (b) an explicit AbortController.abort() is called
      //   (c) strict-mode double-mount in React dev builds
      // None of these are actionable — swallow without reporting.
      const msg = String((e && e.message) || "");
      const errName = String((e && e.name) || "");
      const isAbort =
        errName === "AbortError" ||
        msg.toLowerCase().includes("abort") ||
        msg.toLowerCase().includes("cancel");
      if (isAbort) {
        throw e; // still propagate so the caller's catch fires
      }
      // Network failure (CORS block, offline, dead host).
      // Skip reporting for Sentinel's own endpoints AND known-ignored URLs.
      // iter 320.3 — also suppress when the document is hidden (laptop
      // sleep / background tab — OS suspends network stack and produces
      // false TypeErrors on resume) and apply repeat-counter for polling
      // and slow-legitimate endpoints.
      if (!_isIgnoredUrl(url)) {
        const docHidden =
          (typeof document !== "undefined" &&
            document.visibilityState === "hidden");
        const sig = _hash(`net|${method}|${(url || "").split("?")[0]}`);
        const passesRepeatGate = _shouldReportNetworkFailure(sig, url);
        if (!docHidden && passesRepeatGate) {
          _shipEvent({
            type: "network_failure",
            message: msg || "fetch failed",
            stack: (e && e.stack) || null,
            url,
            method,
            status_code: 0,
            extra: { duration_ms: Date.now() - startedAt },
          });
        }
      }
      throw e;
    }

    // Only report /api/* failures (internal backend) — skip 3rd-party noise.
    // 404s are NEVER reported — they're expected on optional endpoints and
    // add no signal. Capture only 5xx + 401/403/429 (real failures).
    //
    // iter 322 — DROP Cloudflare-layer transient origin errors entirely.
    // Status codes 502/503/520/521/522/523/524 are emitted by the CF edge
    // when the origin pod is restarting, cold-starting, or the upstream
    // event loop briefly stalls during an Atlas latency spike. These are
    // NOT actionable application bugs — they show as a flood in Sentinel
    // (90%+ of historical noise) and drown out real 500s. Real backend
    // exceptions surface as 500/501/505 and are still captured below.
    const ORIGIN_TRANSIENT_STATUSES = new Set([502, 503, 520, 521, 522, 523, 524]);
    try {
      const isApi = url.includes("/api/");
      const status = response.status;
      if (ORIGIN_TRANSIENT_STATUSES.has(status)) {
        return response; // CDN-layer transient, do not ship
      }
      const shouldReport = isApi && !_isIgnoredUrl(url) && !response.ok && (
        status >= 500 ||           // genuine app error (500/501/505)
        status === 401 ||          // unexpected auth failure
        status === 403 ||          // unexpected forbidden
        status === 429             // rate-limited (so we know)
      );
      if (shouldReport) {
        // For sensitive endpoints, skip body entirely
        const sensitive = _isSensitive(url);
        let bodySnippet = null;
        if (!sensitive) {
          try {
            const clone = response.clone();
            const txt = await clone.text();
            bodySnippet = txt.slice(0, 500);
          } catch { /* body may not be readable */ }
        }
        _shipEvent({
          type: "api_error",
          message: `API ${method} ${status}`,
          url,
          method,
          status_code: status,
          extra: {
            duration_ms: Date.now() - startedAt,
            body_snippet: bodySnippet,
          },
        });
      }
    } catch { /* swallow */ }

    return response;
  };
}

// ═════════════════════════════════════════════════════════════
// Boot
// ═════════════════════════════════════════════════════════════
export function installSentinel() {
  try {
    if (window.__aurem_sentinel_installed) return;
    // Skip on localhost to avoid dev noise
    const host = _hostname();
    if (host === "localhost" || host === "127.0.0.1") {
      return;
    }
    _installErrorHandlers();
    _installConsoleWrap();
    _installFetchSniffer();
    window.__aurem_sentinel_installed = true;
    // eslint-disable-next-line no-console
    console.log(`[AUREM Sentinel] v${SENTINEL_VERSION} installed`);
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn("[AUREM Sentinel] install failed:", e);
  }
}

export default installSentinel;
