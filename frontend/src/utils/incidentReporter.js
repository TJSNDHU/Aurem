/**
 * incidentReporter.js — Frontend → AUREM incident bus (iter 322ff).
 *
 * Captures three classes of frontend failure:
 *   1. window.onerror          (synchronous JS errors)
 *   2. unhandledrejection      (promise rejections, e.g. fetch JSON parse)
 *   3. safeJson()._http_status (5xx / HTML-instead-of-JSON, already wired
 *                                in OraChat.jsx — we expose a helper)
 *
 * POSTs to /api/incident/report (open endpoint, rate-limited server-side).
 *
 * Wire-up: import this once at app entry (e.g. index.js):
 *   import "./utils/incidentReporter";
 */

const API = process.env.REACT_APP_BACKEND_URL || "";

// In-memory dedup so a tight loop of errors doesn't hammer the network.
const SEEN = new Map();           // signature → lastTs(ms)
const DEDUP_MS = 30_000;          // 30s client-side window
const MAX_DETAIL_LEN = 3500;

function _dedup(signature) {
  const now = Date.now();
  const last = SEEN.get(signature) || 0;
  if (now - last < DEDUP_MS) return true;
  SEEN.set(signature, now);
  // Prune old entries every 50 inserts
  if (SEEN.size > 200) {
    for (const [k, ts] of SEEN.entries()) {
      if (now - ts > DEDUP_MS * 4) SEEN.delete(k);
    }
  }
  return false;
}

function _safeStr(v, max = 240) {
  try {
    if (v == null) return "";
    const s = typeof v === "string" ? v : String(v);
    return s.length > max ? s.slice(0, max) + "…" : s;
  } catch { return ""; }
}

export async function reportIncident({
  category = "frontend_crash",
  signature = "",
  severity = "P2",
  title = "",
  detail = "",
  metadata = {},
} = {}) {
  if (!API) return false;
  const sig = _safeStr(signature, 220);
  if (!sig) return false;
  if (_dedup(`${category}|${sig}`)) return false;

  const payload = {
    category,
    signature: sig,
    severity,
    source: "frontend",
    title: _safeStr(title, 200),
    detail: _safeStr(detail, MAX_DETAIL_LEN),
    metadata: {
      url: typeof window !== "undefined" ? window.location?.href?.slice(0, 400) : "",
      ua: typeof navigator !== "undefined" ? navigator.userAgent?.slice(0, 240) : "",
      ts: new Date().toISOString(),
      ...metadata,
    },
  };

  try {
    // navigator.sendBeacon if available (fire-and-forget, survives unload)
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
      const ok = navigator.sendBeacon(`${API}/api/incident/report`, blob);
      if (ok) return true;
    }
    // Fallback: regular fetch with keepalive
    await fetch(`${API}/api/incident/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    return true;
  } catch {
    return false;
  }
}

// ── Auto-wire: only run in browser, only once ──────────────────────
if (typeof window !== "undefined" && !window.__AUREM_INCIDENT_REPORTER__) {
  window.__AUREM_INCIDENT_REPORTER__ = true;

  window.addEventListener("error", (e) => {
    const err = e?.error;
    const sig = `${err?.name || "Error"}:${(e?.message || "").slice(0, 120)}:${
      (e?.filename || "").split("/").pop() || ""
    }:${e?.lineno || 0}`;
    reportIncident({
      category: "frontend_crash",
      signature: sig,
      severity: "P2",
      title: e?.message || "Window error",
      detail: (err?.stack || e?.message || "(no stack)").slice(0, MAX_DETAIL_LEN),
      metadata: {
        filename: e?.filename, lineno: e?.lineno, colno: e?.colno,
      },
    });
  });

  window.addEventListener("unhandledrejection", (e) => {
    const reason = e?.reason;
    const msg = (reason && (reason.message || reason.toString && reason.toString())) || "(no reason)";
    const sig = `unhandledrejection:${(msg || "").slice(0, 200)}`;
    reportIncident({
      category: "frontend_unhandled_rejection",
      signature: sig,
      severity: "P2",
      title: msg.slice(0, 200),
      detail: (reason?.stack || msg).slice(0, MAX_DETAIL_LEN),
    });
  });
}

// Helper for safeJson() and other manual call sites
export function reportApiFailure({ endpoint, httpStatus, bodyPreview = "" }) {
  const category = httpStatus >= 500
    ? (httpStatus === 502 || httpStatus === 504 ? "transient_502" : "backend_5xx")
    : "tool_exception";
  return reportIncident({
    category,
    signature: `HTTP ${httpStatus}:${endpoint}`,
    severity: httpStatus >= 500 ? "P1" : "P2",
    title: `HTTP ${httpStatus} on ${endpoint}`,
    detail: bodyPreview,
    metadata: { endpoint, http_status: httpStatus },
  });
}

export default reportIncident;
