/**
 * ORA Command Console
 * One window for: Hunt config · Hunt Now · Agents · Live Feed.
 *
 * Route : /admin/command-console   (replaces Agent Command Center slot)
 * Auth  : reads `aurem_jwt` from localStorage (same as the rest of admin)
 * SSE   : /api/admin/events/:clientId  (push_sse_event broadcasts agent_event)
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import HuntProgressPanel from "./HuntProgressPanel";
import useAuthFetch from "../hooks/useAuthFetch";
import { BACKEND_URL } from "../lib/api";

// Smart resolver: on aurem.live falls back to window.location.origin so a
// stale baked-in preview-pod URL never bricks production. On preview, uses
// REACT_APP_BACKEND_URL as before.
const API = BACKEND_URL;

// Backend agent IDs (must match services/agents/*.AGENT_ID)
const AGENTS = [
  { id: "hunter_ora",   label: "Hunter",    role: "Finds new leads",     icon: "⬡", accent: "#C9A227" },
  { id: "followup_ora", label: "Follow-up", role: "Nurture sequences",   icon: "◈", accent: "#7B9FD4" },
  { id: "closer_ora",   label: "Closer",    role: "Converts to clients", icon: "◆", accent: "#7EC8A0" },
  { id: "referral_ora", label: "Referral",  role: "Generates referrals", icon: "◇", accent: "#C47888" },
];

const INDUSTRY_GROUPS = {
  "Beauty & Wellness": ["salons", "barber shops", "nail salons", "med spas", "spas", "yoga studios", "gyms"],
  "Health":            ["dental clinics", "chiropractors", "optometrists", "physiotherapy", "massage therapy", "pharmacies"],
  "Food & Drink":      ["restaurants", "cafes", "food trucks", "bakeries", "bars", "catering"],
  "Auto":              ["auto shops", "car detailing", "tire shops", "auto glass", "towing"],
  "Professional":      ["lawyers", "accountants", "insurance brokers", "mortgage brokers", "real estate agents"],
  "Trades":            ["hvac", "plumbers", "electricians", "contractors", "painters", "landscapers", "cleaners"],
  "Retail":            ["boutiques", "pet grooming", "florists", "gift shops", "hardware stores"],
};
const ALL_INDUSTRIES = Object.values(INDUSTRY_GROUPS).flat();

const PROVINCES = [
  { key: "ontario",       label: "Ontario" },
  { key: "bc",            label: "British Columbia" },
  { key: "alberta",       label: "Alberta" },
  { key: "quebec",        label: "Quebec" },
  { key: "manitoba",      label: "Manitoba" },
  { key: "saskatchewan",  label: "Saskatchewan" },
  { key: "nova_scotia",   label: "Nova Scotia" },
  { key: "new_brunswick", label: "New Brunswick" },
];

const STATUS_META = {
  running: { color: "#C9A227", label: "Running", pulse: true },
  idle:    { color: "#7EC8A0", label: "Idle",    pulse: false },
  paused:  { color: "#7B9FD4", label: "Paused",  pulse: false },
  queued:  { color: "#C9A227", label: "Queued",  pulse: true },
  stopped: { color: "#3a3a3a", label: "Off",     pulse: false },
};

// ───────────────── helpers ─────────────────

// NOTE: getToken() + apiCall() are kept for backwards compat with helpers
// defined at module scope. The primary path now routes through useAuthFetch()
// inside the component (see `af` hook below). Module-scope helpers use the
// same resolver logic so FormData uploads outside the hook still carry the
// Bearer token.
import { resolveAuthToken } from "../hooks/useAuthFetch";

function getToken() {
  return resolveAuthToken();
}

async function apiCall(path, opts = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers || {}),
  };
  // We use Bearer token auth (Authorization header), not cookies, so
  // `credentials` must be "omit" — otherwise browser CORS spec rejects the
  // backend's `Access-Control-Allow-Origin: *` preflight and the UI silently
  // fails on cross-origin prod deploys (aurem.live → *.emergent.host).
  const r = await fetch(`${API}${path}`, { credentials: "omit", ...opts, headers });
  if (!r.ok) {
    let msg = `${r.status}`;
    try { const d = await r.json(); msg = d.detail || d.error || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

function useToast() {
  const [toasts, setToasts] = useState([]);
  const n = useRef(0);
  const push = useCallback((msg, type = "info", dur = 3500) => {
    const id = ++n.current;
    setToasts((p) => [...p, { id, msg, type }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), dur);
  }, []);
  return { toasts, push };
}

function useSSE(clientId) {
  const [feed, setFeed] = useState([]);
  const esRef = useRef(null);
  const iid = useRef(0);
  useEffect(() => {
    if (!clientId) return;
    const go = () => {
      const es = new EventSource(`${API}/api/admin/events/${clientId}`);
      esRef.current = es;
      es.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (!msg || msg.type === "ping" || msg.type === "connected") return;
          // server_misc_routes wraps as {type, data, timestamp}. Unwrap if so.
          const d = msg.data ? { ...msg.data, timestamp: msg.timestamp } : msg;
          setFeed((p) => [...p.slice(-80), { ...d, _k: ++iid.current }]);
        } catch {}
      };
      es.onerror = () => { es.close(); setTimeout(go, 5000); };
    };
    go();
    return () => esRef.current?.close();
  }, [clientId]);
  return { feed, clear: () => setFeed([]) };
}

// ───────────────── UI primitives ─────────────────

function ToastStack({ toasts }) {
  return (
    <div style={{ position: "fixed", top: 14, right: 14, zIndex: 9999, display: "flex", flexDirection: "column", gap: 5, pointerEvents: "none" }}>
      {toasts.map((t) => (
        <div key={t.id} data-testid={`toast-${t.type}`} style={{
          background: t.type === "error" ? "#1a0808" : t.type === "success" ? "#081508" : "#10101a",
          border: `1px solid ${t.type === "error" ? "#7a2020" : t.type === "success" ? "#2a5a2a" : "#C9A22755"}`,
          color: "#e4ddd3", padding: "9px 13px", borderRadius: 5,
          fontSize: 12, fontFamily: "'Jost',sans-serif",
          boxShadow: "0 6px 24px rgba(0,0,0,.55)", maxWidth: 300, lineHeight: 1.4,
        }}>
          <span style={{ opacity: .7, marginRight: 6 }}>
            {t.type === "success" ? "✓" : t.type === "error" ? "✗" : "◆"}
          </span>
          {t.msg}
        </div>
      ))}
    </div>
  );
}

function Toggle({ on, set, color = "#C9A227", sm }) {
  const w = sm ? 28 : 36, h = sm ? 16 : 20, k = sm ? 10 : 14;
  return (
    <div onClick={() => set(!on)} data-testid="ora-toggle" style={{
      position: "relative", width: w, height: h,
      background: on ? color : "#252525", borderRadius: h / 2,
      cursor: "pointer", transition: "background .18s", flexShrink: 0,
    }}>
      <div style={{
        position: "absolute", top: (h - k) / 2,
        left: on ? w - k - (h - k) / 2 : (h - k) / 2,
        width: k, height: k, background: "#fff",
        borderRadius: "50%", transition: "left .18s",
      }} />
    </div>
  );
}

function Chip({ label, active, onClick, testid }) {
  return (
    <button onClick={onClick} data-testid={testid} style={{
      padding: "4px 9px", fontSize: 10.5, borderRadius: 3, cursor: "pointer",
      border: `1px solid ${active ? "#C9A227" : "#222"}`,
      background: active ? "#C9A22715" : "#0f0f0f",
      color: active ? "#C9A227" : "#555",
      fontFamily: "'Jost',sans-serif", letterSpacing: ".04em",
      transition: "all .1s", whiteSpace: "nowrap",
    }}>
      {label}
    </button>
  );
}

// ─── Right-slide drawer shell ───
function Drawer({ open, onClose, title, subtitle, accentColor = "#C9A227", children }) {
  useEffect(() => {
    if (!open) return;
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.55)",
        opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
        transition: "opacity .22s ease",
      }} />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 400, zIndex: 1001,
        background: "#0f0f11", borderLeft: `1px solid ${accentColor}28`,
        boxShadow: "-12px 0 60px rgba(0,0,0,.7)",
        transform: open ? "translateX(0)" : "translateX(100%)",
        transition: "transform .24s cubic-bezier(.4,0,.2,1)",
        display: "flex", flexDirection: "column", fontFamily: "'Jost',sans-serif",
      }}>
        <div style={{ padding: "18px 20px 14px", borderBottom: "1px solid #1a1a1a", background: "#0d0d0f", flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: accentColor, fontFamily: "'Cinzel',serif", letterSpacing: ".1em", textTransform: "uppercase" }}>{title}</div>
              {subtitle && <div style={{ fontSize: 10, color: "#444", marginTop: 3 }}>{subtitle}</div>}
            </div>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#444", cursor: "pointer", fontSize: 16 }} data-testid="drawer-close">✕</button>
          </div>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>{children}</div>
      </div>
    </>
  );
}

// ─── Morning Brief drawer body ───
const MorningBriefDrawerBody = React.memo(function ({ brief, loading, onRegenerate }) {
  const G = "#C9A227";
  const greet = () => {
    const h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  };
  if (loading) {
    return <div style={{ textAlign: "center", padding: 48, color: "#444" }}>
      <div style={{ fontSize: 22, marginBottom: 10 }}>⬡</div>
      <div style={{ fontSize: 12 }}>Generating brief…</div>
    </div>;
  }
  if (!brief) {
    return <div style={{ textAlign: "center", padding: 40, color: "#444", fontSize: 12 }}>
      No brief yet. Click Regenerate to build one.
      <br /><br />
      <button onClick={onRegenerate} style={{ background: G, color: "#0d0d0d", border: "none", padding: "8px 18px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase" }}>Generate Brief</button>
    </div>;
  }
  const over = brief.overnight || {};
  const actions = brief.pending_tasks || brief.actions || [];
  return (
    <div data-testid="brief-body">
      <div style={{ fontSize: 14, color: "#e4ddd3", fontWeight: 600, marginBottom: 4 }}>{greet()}</div>
      <div style={{ fontSize: 11, color: "#555", marginBottom: 20, lineHeight: 1.5 }}>
        {brief.narration || brief.summary || "Here's what happened while you were away."}
      </div>
      <div style={{ fontSize: 9.5, color: G, letterSpacing: ".14em", textTransform: "uppercase", fontWeight: 700, marginBottom: 10 }}>Overnight Activity</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 20 }}>
        {[
          ["Leads Found", over.leads_found ?? brief.leads_today ?? "—", G],
          ["Messages Sent", over.messages_sent ?? brief.messages_sent ?? "—", "#7B9FD4"],
          ["Replies In", over.replies ?? brief.replies ?? "—", "#7EC8A0"],
          ["Deals Moved", over.deals_moved ?? brief.deals_moved ?? "—", "#C47888"],
        ].map(([label, value, color]) => (
          <div key={label} style={{ background: "#0d0d0f", border: "1px solid #1e1e1e", borderRadius: 5, padding: "10px 12px" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
            <div style={{ fontSize: 9, color: "#444", marginTop: 3, textTransform: "uppercase", letterSpacing: ".06em" }}>{label}</div>
          </div>
        ))}
      </div>
      {actions.length > 0 && (
        <>
          <div style={{ fontSize: 9.5, color: G, letterSpacing: ".14em", textTransform: "uppercase", fontWeight: 700, marginBottom: 10 }}>Today's Actions</div>
          {actions.slice(0, 5).map((a, i) => {
            const pri = a.priority || "low";
            const color = pri === "high" || pri === "critical" ? "#d44" : pri === "medium" ? "#C9A227" : "#7EC8A0";
            const icon = pri === "high" || pri === "critical" ? "🔴" : pri === "medium" ? "🟡" : "🟢";
            return (
              <div key={i} style={{ background: "#0d0d0f", border: "1px solid #1a1a1a", borderRadius: 4, padding: "10px 12px", marginBottom: 6, borderLeft: `3px solid ${color}` }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <span style={{ fontSize: 11 }}>{icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: "#e4ddd3", fontWeight: 500 }}>{a.title || a.action || a.text || a.description}</div>
                    {a.reason && <div style={{ fontSize: 10, color: "#555", marginTop: 3 }}>{a.reason}</div>}
                  </div>
                </div>
              </div>
            );
          })}
        </>
      )}
      <button onClick={onRegenerate} data-testid="brief-regenerate" style={{ background: "transparent", color: "#555", border: "1px solid #222", borderRadius: 4, padding: "7px 14px", cursor: "pointer", fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase", width: "100%", marginTop: 14 }}>↻ Regenerate Brief</button>
    </div>
  );
});

// ─── Approvals drawer body ───
const ApprovalsDrawerBody = React.memo(function ({ approvals, loading, onApprove, onReject, actingId }) {
  const typeColor = (t) => (t === "outreach" || t === "message") ? "#7B9FD4" : (t === "payment" || t === "financial") ? "#C9A227" : (t === "campaign" || t === "hunt") ? "#C47888" : "#7EC8A0";
  if (loading) {
    return <div style={{ textAlign: "center", padding: 48, color: "#444" }}>
      <div style={{ fontSize: 22, marginBottom: 10 }}>◈</div>
      <div style={{ fontSize: 12 }}>Loading…</div>
    </div>;
  }
  if (!approvals?.length) {
    return <div style={{ textAlign: "center", padding: 48 }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>✓</div>
      <div style={{ fontSize: 13, color: "#7EC8A0", fontWeight: 600, marginBottom: 6 }}>All clear</div>
      <div style={{ fontSize: 11, color: "#444" }}>No pending approvals right now.</div>
    </div>;
  }
  return (
    <div data-testid="approvals-body">
      <div style={{ fontSize: 11, color: "#555", marginBottom: 16 }}>Review each item — approve or reject. Actions execute immediately.</div>
      {approvals.map((a) => {
        const id = a.id || a._id || a.approval_id;
        const isActing = actingId === id;
        const t = a.type || a.action_type || "other";
        return (
          <div key={id} style={{ background: "#0d0d0f", border: `1px solid ${typeColor(t)}22`, borderRadius: 6, padding: "13px 14px", marginBottom: 10, opacity: isActing ? 0.6 : 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 9.5, padding: "2px 7px", borderRadius: 2, border: `1px solid ${typeColor(t)}40`, color: typeColor(t), letterSpacing: ".07em", textTransform: "uppercase" }}>{t}</span>
              <span style={{ fontSize: 9.5, color: "#333" }}>{a.created_at ? new Date(a.created_at).toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" }) : ""}</span>
            </div>
            <div style={{ fontSize: 12.5, color: "#e4ddd3", fontWeight: 600, marginBottom: 5 }}>
              {a.title || a.action_title || a.description || "Pending action"}
            </div>
            {(a.context || a.preview || a.details || a.message) && (
              <div style={{ fontSize: 11, color: "#666", marginBottom: 10, padding: "8px 10px", background: "#111", borderRadius: 3, borderLeft: `2px solid ${typeColor(t)}40` }}>
                {a.context || a.preview || a.details || a.message}
              </div>
            )}
            {a.target && <div style={{ fontSize: 10, color: "#555", marginBottom: 10 }}>→ {a.target}</div>}
            <div style={{ display: "flex", gap: 7 }}>
              <button disabled={isActing} onClick={() => onApprove(id)} data-testid={`approve-${id}`} style={{ flex: 1, background: "#0a1a0a", color: "#7EC8A0", border: "1px solid #2a5a2a", borderRadius: 4, padding: "8px 0", cursor: "pointer", fontSize: 11, fontWeight: 600, letterSpacing: ".07em" }}>{isActing ? "⟳ Processing…" : "✓ Approve"}</button>
              <button disabled={isActing} onClick={() => onReject(id)} data-testid={`reject-${id}`} style={{ flex: 1, background: "transparent", color: "#d44", border: "1px solid #7a222260", borderRadius: 4, padding: "8px 0", cursor: "pointer", fontSize: 11, letterSpacing: ".07em" }}>✕ Reject</button>
            </div>
          </div>
        );
      })}
    </div>
  );
});

// ─── Scout drawer body ───
const ScoutDrawerBody = React.memo(function ({ query, setQuery, depth, setDepth, loading, result, onRun }) {
  const G = "#C9A227";
  const surface = result?.surface;
  const osint = result?.osint;

  return (
    <div data-testid="scout-body">
      <div style={{ fontSize: 11, color: "#555", marginBottom: 14, lineHeight: 1.55 }}>
        Deep research a business, person, or topic. Surface = open web. OSINT = deeper intel sweep.
      </div>

      {/* Depth toggle */}
      <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
        {[
          ["surface", "🌐 Surface"],
          ["osint", "🕵 OSINT"],
          ["both", "◆ Both"],
        ].map(([k, l]) => (
          <button
            key={k}
            onClick={() => setDepth(k)}
            data-testid={`scout-depth-${k}`}
            style={{
              flex: 1, padding: "6px 10px", fontSize: 10.5, borderRadius: 3, cursor: "pointer",
              border: `1px solid ${depth === k ? G : "#1e1e1e"}`,
              background: depth === k ? `${G}15` : "transparent",
              color: depth === k ? G : "#555",
              fontFamily: "'Jost',sans-serif", letterSpacing: ".06em", textTransform: "uppercase",
              fontWeight: 600,
            }}
          >{l}</button>
        ))}
      </div>

      {/* Query input */}
      <input
        data-testid="scout-query-input"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onRun()}
        placeholder="e.g. Glow Beauty Salon Toronto · Acme Inc revenue · CEO name company"
        style={{
          width: "100%", background: "#0c0c0d", border: "1px solid #222",
          borderRadius: 4, padding: "9px 12px", color: "#e4ddd3", fontSize: 12,
          fontFamily: "'Jost',sans-serif", outline: "none", marginBottom: 10,
        }}
      />

      <button
        data-testid="scout-run-btn"
        onClick={onRun}
        disabled={loading || !query.trim()}
        style={{
          width: "100%", background: G, color: "#0d0d0d", border: "none",
          padding: "9px 14px", borderRadius: 4, cursor: loading ? "wait" : "pointer",
          fontSize: 11, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase",
          fontFamily: "'Jost',sans-serif", opacity: loading || !query.trim() ? 0.5 : 1, marginBottom: 16,
        }}
      >{loading ? "⟳ Investigating…" : "🔍 Investigate"}</button>

      {/* Results */}
      {result && (
        <div>
          <div style={{ fontSize: 9.5, color: G, letterSpacing: ".14em", textTransform: "uppercase", fontWeight: 700, marginBottom: 10 }}>
            Results · {result.query}
          </div>

          {/* Surface */}
          {surface && (
            <div style={{ background: "#0d0d0f", border: "1px solid #1e1e1e", borderRadius: 5, padding: "12px 14px", marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: "#7B9FD4", letterSpacing: ".08em", textTransform: "uppercase", fontWeight: 700, marginBottom: 7 }}>🌐 Surface Web</div>
              {surface.summary ? (
                <div style={{ fontSize: 11.5, color: "#e4ddd3", lineHeight: 1.55, marginBottom: 8 }}>
                  {String(surface.summary).slice(0, 600)}
                </div>
              ) : null}
              {Array.isArray(surface.sources) && surface.sources.length > 0 && (
                <div>
                  <div style={{ fontSize: 9, color: "#444", textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4 }}>Sources</div>
                  {surface.sources.slice(0, 5).map((s, i) => (
                    <div key={i} style={{ fontSize: 10.5, color: "#7B9FD4", marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.url || s.link || s.title || String(s)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {result.surface_error && (
            <div style={{ padding: "8px 10px", borderRadius: 4, background: "#1a0808", border: "1px solid #7a2020", color: "#d44", fontSize: 10.5, marginBottom: 10 }}>
              Surface failed: {result.surface_error}
            </div>
          )}

          {/* OSINT */}
          {osint && (
            <div style={{ background: "#0d0d0f", border: "1px solid #1e1e1e", borderRadius: 5, padding: "12px 14px", marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 7 }}>
                <div style={{ fontSize: 10, color: "#C47888", letterSpacing: ".08em", textTransform: "uppercase", fontWeight: 700 }}>🕵 OSINT</div>
                {osint.risk_level && (
                  <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 2, border: "1px solid #C4788840", color: "#C47888", textTransform: "uppercase" }}>
                    Risk: {osint.risk_level}
                  </span>
                )}
              </div>
              {osint.analysis_preview && (
                <div style={{ fontSize: 11.5, color: "#e4ddd3", lineHeight: 1.55, marginBottom: 8 }}>
                  {osint.analysis_preview}
                </div>
              )}
              {osint.search_results != null && (
                <div style={{ fontSize: 10, color: "#555" }}>
                  {osint.search_results} sources scanned · {osint.filtered_results ?? 0} after filter
                </div>
              )}
            </div>
          )}
          {result.osint_error && (
            <div style={{ padding: "8px 10px", borderRadius: 4, background: "#1a0808", border: "1px solid #7a2020", color: "#d44", fontSize: 10.5 }}>
              OSINT failed: {result.osint_error}
            </div>
          )}
        </div>
      )}
    </div>
  );
});

// ───────────────── MAIN ─────────────────

export default function ORACommandConsole() {
  const { toasts, push: toast } = useToast();
  const clientId = useMemo(() => `ora_${Date.now()}`, []);
  const { feed, clear: clearFeed } = useSSE(clientId);
  const feedEnd = useRef(null);

  // #1 — Memoize progress events slice so HuntProgressPanel re-renders ONLY
  // when a hunt_progress event arrives, not on every unrelated feed update.
  const progressEvents = useMemo(
    () => feed.filter((e) => e && e.step && e.status),
    [feed]
  );

  // Global — Dry Run system removed (iter 263); agents always run LIVE.
  const [allPaused, setAllPaused] = useState(false);
  const [agentStatus, setAgentStatus] = useState({});
  const [busy, setBusy] = useState({});
  const [stats, setStats] = useState({ total_leads: "—", contacted_today: "—", deals_open: "—", response_rate: "—" });
  const [compliance, setCompliance] = useState(null);  // CASL snapshot
  const [dncCount, setDncCount] = useState(null);      // Do Not Contact list size

  // Hunt target
  const [mode, setMode] = useState("industry"); // industry | radius | csv
  const [industries, setInds] = useState(["salons", "dental clinics"]);
  const [customInd, setCustomInd] = useState("");
  const [province, setProv] = useState("ontario");
  const [scoreMin, setScoreMin] = useState(70);
  const [limit, setLimit] = useState(20);
  const [address, setAddress] = useState("");
  const [radiusKm, setRadiusKm] = useState(5);
  const [radInd, setRadInd] = useState("salons");
  const [csvFile, setCsvFile] = useState(null);   // #7 CSV mode file

  // #9 Smart Presets — persisted in localStorage
  const [presets, setPresets] = useState(() => {
    try { return JSON.parse(localStorage.getItem("ora_hunt_presets") || "[]"); }
    catch { return []; }
  });

  // Persisted hunt command history (survives refresh) — backend: db.hunt_commands
  const [commandHistory, setCommandHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);

  // ── Drawers: Morning Brief + Smart Approvals ──
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefActions, setBriefActions] = useState(0);
  const [approvalsOpen, setApprovalsOpen] = useState(false);
  const [approvals, setApprovals] = useState([]);
  const [approvalsCount, setApprovalsCount] = useState(0);
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const [actingApprovalId, setActingApprovalId] = useState(null);

  // ── Scout drawer (unified Deep + Dark Scout) ──
  const [scoutOpen, setScoutOpen] = useState(false);
  const [scoutQuery, setScoutQuery] = useState("");
  const [scoutDepth, setScoutDepth] = useState("surface");
  const [scoutLoading, setScoutLoading] = useState(false);
  const [scoutResult, setScoutResult] = useState(null);

  const [previewing, setPrev] = useState(false);
  const [previewData, setPrevData] = useState(null);
  const [hunting, setHunting] = useState(false);

  const [rightTab, setRightTab] = useState("agents"); // agents | config
  const [config, setConfig] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load on mount + poll
  useEffect(() => {
    // Reset scroll to top whenever Console mounts — fixes "opens scrolled to bottom"
    // when switching in from another view whose scroll position carried over.
    try {
      window.scrollTo(0, 0);
      const area = document.querySelector('[data-content-area]');
      if (area) area.scrollTop = 0;
      // Also reset any scrollable ancestor (main content wrapper in AuremDashboard)
      let el = document.querySelector('[data-testid="ora-command-console"]');
      while (el && el.parentElement) {
        el = el.parentElement;
        if (el.scrollHeight > el.clientHeight) el.scrollTop = 0;
      }
    } catch {}
    loadStatus(); loadConfig(); loadStats(); loadCompliance(); loadDnc(); loadCommandHistory();
    loadBriefBadge(); loadApprovalBadge();
    const t = setInterval(() => { loadStatus(); loadCompliance(); loadApprovalBadge(); }, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll the feed to the latest entry — but only when feed has items AND
  // only scrolls WITHIN the live-feed div (block:"nearest" + restrict to nearest
  // ancestor). Previously this ran on mount with empty feed and forced the whole
  // dashboard scroll container down by ~1455px — opening Console scrolled to bottom.
  useEffect(() => {
    if (!feed.length) return;
    const el = feedEnd.current;
    if (!el) return;
    const parent = el.parentElement;
    if (parent) parent.scrollTop = parent.scrollHeight;
  }, [feed]);

  // #8 — Chime + haptic on HIGH lead (approved feature)
  const lastHighRef = useRef(0);
  useEffect(() => {
    if (!feed.length) return;
    const latest = feed[feed.length - 1];
    if (latest._k <= lastHighRef.current) return;
    const score = latest.score ?? latest.ora_score;
    const isHigh = (score && score >= 80) || latest.type === "high_lead";
    if (!isHigh) return;
    lastHighRef.current = latest._k;
    // 300ms ding via Web Audio
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) {
        const ctx = new Ctx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = 880;
        osc.connect(gain); gain.connect(ctx.destination);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.start(); osc.stop(ctx.currentTime + 0.3);
      }
    } catch {}
    try { navigator.vibrate?.(100); } catch {}
  }, [feed]);

  async function loadStatus() {
    try {
      const d = await apiCall("/api/agents/status");
      // Our backend returns { agents: [{agent_id, status, today_stats, ...}], ... }
      const map = {};
      (d.agents || []).forEach((a) => {
        map[a.agent_id] = {
          status: a.paused ? "paused" : (a.status || "idle"),
          last_run: a.last_run_at,
          leads_today: (a.today_stats && (a.today_stats.scouted || a.today_stats.drip_sent || a.today_stats.closer_attempts || a.today_stats.referrals_contacted)) || 0,
          queued: 0,
        };
      });
      setAgentStatus(map);
    } catch (e) {
      // silent — status endpoint may need admin token
    }
  }

  async function loadConfig() {
    try {
      const d = await apiCall("/api/auto-hunt/settings");
      setConfig(d);
      if (d.industries_enabled?.length) setInds(d.industries_enabled);
    } catch {}
  }

  async function loadStats() {
    try {
      const d = await apiCall("/api/agents/stats");
      setStats({
        total_leads: d.total_leads ?? 0,
        contacted_today: d.contacted_today ?? 0,
        deals_open: d.deals_open ?? 0,
        response_rate: d.response_rate != null ? `${d.response_rate}%` : "—",
      });
    } catch {}
  }

  async function loadCompliance() {
    try {
      const d = await apiCall("/api/compliance/status");
      setCompliance(d);
    } catch {}
  }

  async function loadDnc() {
    try {
      const d = await apiCall("/api/campaign/do-not-contact?limit=1");
      setDncCount(d.total ?? 0);
    } catch {}
  }

  // ── Morning Brief ──
  async function loadBriefBadge() {
    try {
      const d = await apiCall("/api/aurem/morning-brief?task_limit=20");
      const count = (d.pending_tasks || []).length || (d.actions || []).length || 0;
      setBriefActions(count);
      setBrief(d);
    } catch {}
  }
  async function openBrief() {
    setBriefOpen(true);
    if (brief) return;
    setBriefLoading(true);
    try {
      const d = await apiCall("/api/aurem/morning-brief?task_limit=20");
      setBrief(d);
      setBriefActions((d.pending_tasks || d.actions || []).length);
    } catch {}
    setBriefLoading(false);
  }
  async function regenerateBrief() {
    setBriefLoading(true);
    setBrief(null);
    try {
      const d = await apiCall("/api/aurem/morning-brief?task_limit=20");
      setBrief(d);
      setBriefActions((d.pending_tasks || d.actions || []).length);
      toast("Brief refreshed", "success");
    } catch { toast("Brief generation failed", "error"); }
    setBriefLoading(false);
  }

  // ── Smart Approvals ──
  async function loadApprovalBadge() {
    try {
      const d = await apiCall("/api/approvals/pending");
      setApprovalsCount(d.count ?? (d.approvals || []).length);
      if (approvalsOpen) setApprovals(d.approvals || []);
    } catch {}
  }
  async function openApprovals() {
    setApprovalsOpen(true);
    setApprovalsLoading(true);
    try {
      const d = await apiCall("/api/approvals/pending");
      setApprovals(d.approvals || []);
      setApprovalsCount(d.count ?? (d.approvals || []).length);
    } catch {}
    setApprovalsLoading(false);
  }
  async function handleApprove(id) {
    setActingApprovalId(id);
    try {
      await apiCall(`/api/approvals/${id}/approve`, { method: "POST" });
      setApprovals((p) => p.filter((a) => (a.id || a._id) !== id));
      setApprovalsCount((c) => Math.max(0, c - 1));
      toast("Approved ✓", "success");
    } catch (e) { toast(`Approve failed: ${e.message}`, "error"); }
    setActingApprovalId(null);
  }
  async function handleReject(id) {
    setActingApprovalId(id);
    try {
      await apiCall(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason: "" }) });
      setApprovals((p) => p.filter((a) => (a.id || a._id) !== id));
      setApprovalsCount((c) => Math.max(0, c - 1));
      toast("Rejected", "info");
    } catch (e) { toast(`Reject failed: ${e.message}`, "error"); }
    setActingApprovalId(null);
  }

  // ── Scout handler ──
  async function runScout() {
    const q = scoutQuery.trim();
    if (!q) return;
    setScoutLoading(true); setScoutResult(null);
    try {
      const d = await apiCall("/api/scout/unified", {
        method: "POST",
        body: JSON.stringify({ query: q, depth: scoutDepth, max_results: 15 }),
      });
      setScoutResult(d);
      toast(`Scout complete · ${scoutDepth}`, "success");
    } catch (e) { toast(`Scout failed: ${e.message}`, "error"); }
    setScoutLoading(false);
  }

  // Agent actions — fire-and-forget, instant UI feedback
  async function agentAct(id, action) {
    if (busy[id]) return;
    setBusy((p) => ({ ...p, [id]: action }));
    try {
      await apiCall(`/api/agents/${id}/${action === "run" ? "run-now" : action}`, { method: "POST" });
      const lbl = AGENTS.find((a) => a.id === id)?.label || id;
      const actionLabel = action === "run" ? "queued" : action === "pause" ? "paused" : "resumed";
      toast(`${lbl} ${actionLabel}`, "success");
      setTimeout(loadStatus, 1200);
    } catch (e) {
      toast(`${action} failed: ${e.message}`, "error");
    }
    setTimeout(() => setBusy((p) => ({ ...p, [id]: null })), 1500);
  }

  async function toggleAll() {
    try {
      await apiCall(`/api/agents/${allPaused ? "resume" : "pause"}-all`, { method: "POST" });
      setAllPaused(!allPaused);
      toast(allPaused ? "All agents resumed" : "All agents paused", "info");
      setTimeout(loadStatus, 1000);
    } catch (e) { toast(`Failed: ${e.message}`, "error"); }
  }

  function huntPayload(lim) {
    if (mode === "radius") {
      return { mode: "radius", address: address.trim(), radius_km: radiusKm, industry: radInd, limit: lim };
    }
    return { mode: "industry", industry: industries, province, score_filter: scoreMin, limit: lim };
  }

  async function preview() {
    if (mode === "radius" && !address.trim()) { toast("Enter an address first", "error"); return; }
    if (mode === "industry" && !industries.length) { toast("Select at least one industry", "error"); return; }
    setPrev(true); setPrevData(null);
    try {
      const d = await apiCall("/api/agents/hunter/hunt-now", {
        method: "POST",
        body: JSON.stringify(huntPayload(5)),
      });
      const res = d.results || d.leads || [];
      setPrevData(res);
      toast(res.length ? `Preview: ${res.length} found` : "No matches — try broader filters", res.length ? "success" : "info");
    } catch (e) { toast(`Preview failed: ${e.message}`, "error"); }
    setPrev(false);
  }

  async function hunt() {
    // CSV mode branch (#7)
    if (mode === "csv") {
      if (!csvFile) { toast("Choose a CSV file first", "error"); return; }
      setHunting(true); setPrevData(null);
      try {
        const form = new FormData();
        form.append("file", csvFile);
        form.append("limit", String(limit));
        const token = getToken();
        const r = await fetch(`${API}/api/agents/hunter/csv-hunt`, {
          method: "POST",
          credentials: "omit",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
        });
        if (!r.ok) {
          let msg = `${r.status}`;
          try { const d = await r.json(); msg = d.detail || msg; } catch {}
          throw new Error(msg);
        }
        const d = await r.json();
        toast(`CSV hunt queued: ${d.queued || 0} rows · LIVE`, "success", 5000);
        savePreset({ mode: "csv", filename: csvFile.name, limit });
        setCsvFile(null);
        setTimeout(loadCommandHistory, 500);
      } catch (e) { toast(`CSV hunt failed: ${e.message}`, "error"); }
      setHunting(false);
      return;
    }

    if (mode === "radius" && !address.trim()) { toast("Enter an address first", "error"); return; }
    if (mode === "industry" && !industries.length) { toast("Select at least one industry", "error"); return; }
    setHunting(true); setPrevData(null);
    try {
      const d = await apiCall("/api/agents/hunter/hunt-now", {
        method: "POST",
        body: JSON.stringify(huntPayload(limit)),
      });
      toast(`Hunt queued — ${d.queued || limit} targets · LIVE`, "success", 5000);
      savePreset({ mode, industries, province, scoreMin, address, radiusKm, radInd, limit });
      setTimeout(loadStatus, 1500);
      setTimeout(loadCommandHistory, 500);   // pull freshly persisted command
    } catch (e) { toast(`Hunt failed: ${e.message}`, "error"); }
    setHunting(false);
  }

  async function loadCommandHistory() {
    try {
      const d = await apiCall("/api/agents/hunter/commands?limit=30");
      setCommandHistory(d?.commands || []);
    } catch { /* history is optional */ }
  }

  // #9 Save config as preset (last 3 kept, newest first)
  function savePreset(cfg) {
    const label = cfg.mode === "csv"
      ? `CSV · ${cfg.filename}`
      : cfg.mode === "radius"
        ? `${cfg.radInd || "all"} · ${cfg.address}`
        : `${(cfg.industries || []).slice(0, 2).join(", ")} · ${cfg.province}`;
    const next = [
      { id: Date.now(), label, cfg },
      ...presets.filter((p) => p.label !== label),
    ].slice(0, 3);
    setPresets(next);
    try { localStorage.setItem("ora_hunt_presets", JSON.stringify(next)); } catch {}
  }

  function applyPreset(p) {
    const c = p.cfg || {};
    setMode(c.mode || "industry");
    if (c.mode === "csv") {
      toast("CSV preset — re-upload the file, rest of settings restored.", "info");
    } else if (c.mode === "radius") {
      setAddress(c.address || "");
      setRadiusKm(c.radiusKm || 5);
      setRadInd(c.radInd || "");
    } else {
      setInds(c.industries || []);
      setProv(c.province || "ontario");
      setScoreMin(c.scoreMin || 70);
    }
    setLimit(c.limit || 20);
    toast(`Preset loaded: ${p.label}`, "success");
  }

  async function saveConfig() {
    setSaving(true);
    try {
      await apiCall("/api/auto-hunt/settings", {
        method: "POST",
        body: JSON.stringify({ ...config, industries_enabled: industries }),
      });
      toast("Schedule saved", "success"); setDirty(false);
    } catch (e) { toast(`Save failed: ${e.message}`, "error"); }
    setSaving(false);
  }

  function toggleInd(v) {
    setInds((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]));
    setDirty(true);
  }
  function addCustom() {
    const v = customInd.trim().toLowerCase();
    if (v && !industries.includes(v)) { setInds((p) => [...p, v]); setDirty(true); }
    setCustomInd("");
  }
  function ago(ts) {
    if (!ts) return "—";
    const s = Math.floor((Date.now() - new Date(ts)) / 1000);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    return `${Math.floor(s / 3600)}h`;
  }
  function feedColor(e) {
    if (e.type === "error") return "#c44";
    if (e.type === "success") return "#7EC8A0";
    const m = { hunter_ora: "#C9A227", followup_ora: "#7B9FD4", closer_ora: "#7EC8A0", referral_ora: "#C47888" };
    return m[e.agent] || "#7B7B7B";
  }
  function feedIcon(e) {
    if (e.type === "error") return "✗";
    if (e.type === "success") return "✓";
    const m = { hunter_ora: "⬡", followup_ora: "◈", closer_ora: "◆", referral_ora: "◇" };
    return m[e.agent] || "·";
  }

  // ─── styles ───
  const G = "#C9A227";
  const GLASS = "rgba(15, 18, 28, 0.42)";
  const GLASS_DEEP = "rgba(12, 14, 22, 0.58)";
  const GLASS_CARD = "rgba(16, 18, 26, 0.48)";
  const BLUR = "blur(22px) saturate(160%)";
  const GOLD_RIM = "rgba(201, 162, 39, 0.22)";
  const s = {
    root: { minHeight: "100vh", background: "transparent", color: "#E4DDD3", fontFamily: "'Jost',sans-serif", display: "flex", flexDirection: "column" },
    topbar: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "13px 20px", borderBottom: `1px solid ${GOLD_RIM}`, background: GLASS_DEEP, backdropFilter: BLUR, WebkitBackdropFilter: BLUR, flexShrink: 0, flexWrap: "wrap", gap: 12 },
    title: { fontFamily: "'Cinzel',serif", fontSize: 15, color: G, letterSpacing: ".12em" },
    sub: { fontSize: 9, color: "#7a7a7a", letterSpacing: ".1em", textTransform: "uppercase", marginTop: 2 },
    // Desktop default: 2-column grid with right agents rail.
    // Mobile (<768px) override comes from the injected <style> block below — it
    // flips to a single-column flow so Hunt Target isn't crushed into a 90px
    // squished strip on phones (the old "content showing at bottom" bug).
    body: { flex: 1, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 300px", overflow: "hidden" },
    left: { display: "flex", flexDirection: "column", overflowY: "auto", borderRight: `1px solid ${GOLD_RIM}` },
    right: { display: "flex", flexDirection: "column", overflowY: "auto", background: GLASS, backdropFilter: BLUR, WebkitBackdropFilter: BLUR },
    sec: { padding: "15px 17px", borderBottom: `1px solid ${GOLD_RIM}`, background: GLASS, backdropFilter: BLUR, WebkitBackdropFilter: BLUR, margin: "10px 10px 0", borderRadius: 12, boxShadow: "0 8px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)" },
    secHead: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 11 },
    secLabel: { fontSize: 9.5, color: G, letterSpacing: ".14em", textTransform: "uppercase", fontWeight: 700 },
    tabs: { display: "flex", gap: 3, marginBottom: 13 },
    tab: (a) => ({ padding: "5px 13px", fontSize: 10.5, borderRadius: 3, cursor: "pointer", border: `1px solid ${a ? G : "#1e1e1e"}`, background: a ? `${G}12` : "transparent", color: a ? G : "#7a7a7a", fontFamily: "'Jost',sans-serif", letterSpacing: ".05em" }),
    grpLabel: { fontSize: 9, color: "#5e5e5e", letterSpacing: ".12em", textTransform: "uppercase", marginBottom: 4, fontWeight: 700 },
    chipGrid: { display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 9 },
    row: { display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 10 },
    col: { display: "flex", flexDirection: "column" },
    lbl: { fontSize: 9.5, color: "#8e8272", letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 3 },
    input: { background: "rgba(10, 12, 18, 0.55)", border: "1px solid rgba(201,162,39,0.18)", borderRadius: 4, padding: "7px 10px", color: "#e4ddd3", fontSize: 12, fontFamily: "'Jost',sans-serif", outline: "none", width: "100%", backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)" },
    select: { background: "rgba(10, 12, 18, 0.55)", border: "1px solid rgba(201,162,39,0.18)", borderRadius: 4, padding: "7px 10px", color: "#e4ddd3", fontSize: 12, fontFamily: "'Jost',sans-serif", outline: "none", cursor: "pointer", backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)" },
    slider: { width: "100%", accentColor: G, cursor: "pointer" },
    sliderHead: { display: "flex", justifyContent: "space-between", marginBottom: 3 },
    divider: { height: 1, background: GOLD_RIM, margin: "11px 0" },
    btnGold: { background: G, color: "#0c0c0d", border: "none", padding: "8px 17px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontFamily: "'Jost',sans-serif", fontWeight: 700, letterSpacing: ".09em", textTransform: "uppercase", boxShadow: "0 4px 14px rgba(201,162,39,0.35)" },
    btnOut: (c = G) => ({ background: "transparent", color: c, border: `1px solid ${c}`, padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontFamily: "'Jost',sans-serif", letterSpacing: ".07em", textTransform: "uppercase" }),
    btnGhost: (c = "#8a8272") => ({ background: "transparent", border: `1px solid ${c}38`, color: c, padding: "5px 10px", borderRadius: 3, cursor: "pointer", fontSize: 10, fontFamily: "'Jost',sans-serif", letterSpacing: ".05em" }),
    btnRed: { background: "transparent", color: "#ff6b6b", border: "1px solid rgba(212,66,42,0.6)", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontFamily: "'Jost',sans-serif", letterSpacing: ".07em", textTransform: "uppercase" },
    agentCard: (accent) => ({ background: GLASS_CARD, border: `1px solid ${accent}35`, borderRadius: 8, padding: "10px 12px", marginBottom: 7, backdropFilter: "blur(18px) saturate(150%)", WebkitBackdropFilter: "blur(18px) saturate(150%)", boxShadow: `0 6px 18px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05), 0 0 0 1px ${accent}10` }),
    dot: (c, p) => ({ width: 6, height: 6, borderRadius: "50%", background: c, flexShrink: 0, boxShadow: p ? `0 0 4px ${c}` : "none", animation: p ? "oraGlow 1.6s ease-in-out infinite" : "none" }),
    feedRow: { display: "flex", gap: 7, padding: "4px 0", borderBottom: "1px solid rgba(201,162,39,0.08)", fontSize: 11.5, alignItems: "flex-start", lineHeight: 1.4 },
    preCard: { background: GLASS_CARD, border: `1px solid ${GOLD_RIM}`, borderRadius: 6, padding: "8px 10px", marginBottom: 5, backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)" },
    badge: (c = G) => ({ fontSize: 9, padding: "2px 6px", borderRadius: 2, border: `1px solid ${c}38`, color: c, letterSpacing: ".07em", textTransform: "uppercase" }),
  };

  return (
    <div style={s.root} data-testid="ora-command-console">
      <style>{`
        @keyframes oraGlow{0%,100%{opacity:1}50%{opacity:.25}}
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-track{background:#0c0c0d}
        ::-webkit-scrollbar-thumb{background:#222;border-radius:2px}
        select option{background:#111}
        input:focus,select:focus{border-color:#C9A22755!important}
        /* ─ Mobile layout: stack columns, let parent handle scroll ─ */
        @media (max-width: 767px){
          [data-testid="ora-command-console"]{ min-height:auto !important; }
          [data-testid="ora-command-console"] .ora-body{
            display:flex !important; flex-direction:column !important;
            grid-template-columns:none !important; overflow:visible !important;
          }
          [data-testid="ora-command-console"] .ora-left,
          [data-testid="ora-command-console"] .ora-right{
            overflow-y:visible !important; border-right:none !important;
            width:100% !important;
          }
          [data-testid="ora-command-console"] .ora-right{
            border-top:1px solid #1c1c1c;
          }
          [data-testid="ora-command-console"] .ora-topbar{
            padding:10px 12px !important; gap:8px !important;
          }
          /* Hide the "title + sub" block's sub line on tiny screens to save height */
          [data-testid="ora-command-console"] .ora-topbar-sub{ display:none; }
        }
      `}</style>

      <ToastStack toasts={toasts} />

      {/* TOPBAR */}
      <div style={s.topbar} className="ora-topbar">
        <div>
          <div style={s.title}>⬡ ORA Command Console</div>
          <div style={s.sub} className="ora-topbar-sub">AUREM AI · {new Date().toLocaleDateString("en-CA", { weekday: "short", year: "numeric", month: "short", day: "numeric" })}</div>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          {[["Leads", stats.total_leads], ["Today", stats.contacted_today], ["Open", stats.deals_open], ["Reply", stats.response_rate]].map(([l, v]) => (
            <div key={l} style={{ textAlign: "center", minWidth: 38 }} data-testid={`topbar-stat-${l.toLowerCase()}`}>
              <div style={{ fontSize: 15, fontWeight: 700, color: G, lineHeight: 1 }}>{v}</div>
              <div style={{ fontSize: 8.5, color: "#333", textTransform: "uppercase", letterSpacing: ".08em" }}>{l}</div>
            </div>
          ))}
          <div style={{ width: 1, height: 28, background: "#1c1c1c" }} />
          {/* Hunt History badge — persisted commands (survives refresh) */}
          <button
            onClick={() => { loadCommandHistory(); setHistoryOpen(true); }}
            data-testid="history-badge"
            style={{
              position: "relative", background: commandHistory.length > 0 ? "#101818" : "transparent",
              border: `1px solid ${commandHistory.length > 0 ? "#4ADE8060" : "#1e1e1e"}`,
              borderRadius: 4, padding: "5px 10px", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6, transition: "all .15s",
            }}
            title="Locked hunt command history — persists across refresh"
          >
            <span style={{ fontSize: 13 }}>🔒</span>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: 9.5, color: commandHistory.length > 0 ? "#4ADE80" : "#555", letterSpacing: ".06em", textTransform: "uppercase", fontWeight: 600, lineHeight: 1 }}>History</div>
              <div style={{ fontSize: 9, color: commandHistory.length > 0 ? "#4ADE8090" : "#333", marginTop: 1 }}>
                {commandHistory.length > 0 ? `${commandHistory.length} locked` : "No commands yet"}
              </div>
            </div>
          </button>
          {/* Morning Brief badge */}
          <button
            onClick={openBrief}
            data-testid="brief-badge"
            style={{
              position: "relative", background: briefActions > 0 ? "#1a1500" : "transparent",
              border: `1px solid ${briefActions > 0 ? "#C9A22760" : "#1e1e1e"}`,
              borderRadius: 4, padding: "5px 10px", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6, transition: "all .15s",
            }}
          >
            <span style={{ fontSize: 13 }}>📋</span>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: 9.5, color: briefActions > 0 ? "#C9A227" : "#555", letterSpacing: ".06em", textTransform: "uppercase", fontWeight: 600, lineHeight: 1 }}>Brief</div>
              <div style={{ fontSize: 9, color: briefActions > 0 ? "#C9A22290" : "#333", marginTop: 1 }}>
                {briefActions > 0 ? `${briefActions} action${briefActions !== 1 ? "s" : ""}` : "Up to date"}
              </div>
            </div>
            {briefActions > 0 && (
              <div style={{
                position: "absolute", top: -5, right: -5, background: "#C9A227", color: "#0c0c0d",
                width: 16, height: 16, borderRadius: "50%", fontSize: 9.5, fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: "0 0 8px #C9A22780",
              }}>{briefActions > 9 ? "9+" : briefActions}</div>
            )}
          </button>
          {/* Smart Approvals badge */}
          <button
            onClick={openApprovals}
            data-testid="approvals-badge"
            style={{
              position: "relative", background: approvalsCount > 0 ? "#0e101a" : "transparent",
              border: `1px solid ${approvalsCount > 0 ? "#7B9FD460" : "#1e1e1e"}`,
              borderRadius: 4, padding: "5px 10px", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6, transition: "all .15s",
            }}
          >
            <span style={{ fontSize: 13 }}>⚡</span>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: 9.5, color: approvalsCount > 0 ? "#7B9FD4" : "#555", letterSpacing: ".06em", textTransform: "uppercase", fontWeight: 600, lineHeight: 1 }}>Approvals</div>
              <div style={{ fontSize: 9, color: approvalsCount > 0 ? "#7B9FD490" : "#333", marginTop: 1 }}>
                {approvalsCount > 0 ? `${approvalsCount} pending` : "None pending"}
              </div>
            </div>
            {approvalsCount > 0 && (
              <div style={{
                position: "absolute", top: -5, right: -5, background: "#7B9FD4", color: "#0c0c0d",
                width: 16, height: 16, borderRadius: "50%", fontSize: 9.5, fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
                animation: "oraGlow 2s ease-in-out infinite", boxShadow: "0 0 8px #7B9FD480",
              }}>{approvalsCount > 9 ? "9+" : approvalsCount}</div>
            )}
          </button>
          {/* ORA Scout badge (🔍 deep research + OSINT) */}
          <button
            onClick={() => setScoutOpen(true)}
            data-testid="scout-badge"
            style={{
              background: "transparent",
              border: "1px solid #7B9FD428",
              borderRadius: 4, padding: "5px 10px", cursor: "pointer",
              display: "flex", alignItems: "center", gap: 6, transition: "all .15s",
            }}
          >
            <span style={{ fontSize: 13 }}>🔍</span>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontSize: 9.5, color: "#7B9FD4", letterSpacing: ".06em", textTransform: "uppercase", fontWeight: 600, lineHeight: 1 }}>Scout</div>
              <div style={{ fontSize: 9, color: "#7B9FD490", marginTop: 1 }}>Deep research</div>
            </div>
          </button>
          {/* #2 CASL Compliance badge */}
          {compliance && (
            <div
              data-testid="casl-badge"
              title={compliance.compliant ? "CASL compliant — safe to send" : "CASL issues detected — review before going live"}
              style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "3px 8px", borderRadius: 3,
                background: compliance.compliant ? "#08150810" : "#1a080810",
                border: `1px solid ${compliance.compliant ? "#2a5a2a" : "#7a2020"}`,
                fontSize: 9.5, color: compliance.compliant ? "#7EC8A0" : "#d44",
                letterSpacing: ".08em", textTransform: "uppercase",
              }}
            >
              {compliance.compliant ? "CASL ✓" : "CASL ✗"}
            </div>
          )}
          {/* #3 DNC count */}
          {dncCount != null && (
            <div
              data-testid="dnc-badge"
              title="Do Not Contact list — these are skipped automatically"
              style={{
                fontSize: 9.5, color: "#888", letterSpacing: ".06em",
                padding: "3px 8px", borderRadius: 3,
                background: "#0e0e10", border: "1px solid #222",
              }}
            >
              ⛔ {dncCount} DNC
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 9.5, color: "#d44", letterSpacing: ".08em", textTransform: "uppercase" }}>
              ⚠ LIVE
            </span>
          </div>
          <button
            style={allPaused ? s.btnOut() : s.btnRed}
            onClick={toggleAll}
            data-testid="pause-all-btn"
          >
            {allPaused ? "▶ Resume All" : "⏸ Pause All"}
          </button>
        </div>
      </div>

      {/* BODY */}
      <div style={s.body} className="ora-body">
        {/* LEFT */}
        <div style={s.left} className="ora-left">
          {/* HUNT TARGET */}
          <div style={s.sec}>
            <div style={s.secHead}>
              <span style={s.secLabel}>Hunt Target</span>
            </div>

            <div style={s.tabs}>
              {[["industry", "🏷 Industry"], ["radius", "📍 Radius"], ["csv", "📋 CSV"]].map(([k, l]) => (
                <button key={k} style={s.tab(mode === k)} onClick={() => { setMode(k); setPrevData(null); }} data-testid={`mode-${k}`}>
                  {l}
                </button>
              ))}
            </div>

            {/* #9 Smart Presets — chips row, only shown if any saved */}
            {presets.length > 0 && (
              <div style={{ display: "flex", gap: 5, marginBottom: 11, flexWrap: "wrap" }}>
                <span style={{ fontSize: 9, color: "#2e2e2e", letterSpacing: ".1em", textTransform: "uppercase", alignSelf: "center", marginRight: 4 }}>
                  Recent:
                </span>
                {presets.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => applyPreset(p)}
                    data-testid={`preset-${p.id}`}
                    title={p.label}
                    style={{
                      padding: "3px 9px", fontSize: 10.5, borderRadius: 3, cursor: "pointer",
                      border: "1px solid #7B9FD428", background: "#7B9FD410",
                      color: "#7B9FD4", fontFamily: "'Jost',sans-serif", letterSpacing: ".04em",
                      whiteSpace: "nowrap", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis",
                    }}
                  >
                    ★ {p.label}
                  </button>
                ))}
              </div>
            )}

            {mode === "industry" && (
              <>
                {Object.entries(INDUSTRY_GROUPS).map(([grp, items]) => (
                  <div key={grp} style={{ marginBottom: 11 }}>
                    <div style={s.grpLabel}>{grp}</div>
                    <div style={s.chipGrid}>
                      {items.map((ind) => (
                        <Chip key={ind} label={ind} active={industries.includes(ind)}
                              onClick={() => toggleInd(ind)} testid={`chip-${ind.replace(/\s+/g, "-")}`} />
                      ))}
                    </div>
                  </div>
                ))}
                <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                  <input style={{ ...s.input, flex: 1 }} placeholder="+ Custom industry…"
                    value={customInd} onChange={(e) => setCustomInd(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addCustom()}
                    data-testid="custom-industry-input" />
                  <button style={s.btnGhost(G)} onClick={addCustom} data-testid="custom-industry-add">Add</button>
                </div>
                {industries.length > 0 && (
                  <div style={{ fontSize: 9.5, color: "#C9A22790", marginBottom: 10 }}>
                    {industries.length} selected · {industries.join(", ")}
                  </div>
                )}
                <div style={s.divider} />
                <div style={s.row}>
                  <div style={{ flex: 1, ...s.col }}>
                    <div style={s.lbl}>Province</div>
                    <select style={{ ...s.select, width: "100%" }} value={province}
                      onChange={(e) => setProv(e.target.value)} data-testid="province-select">
                      {PROVINCES.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
                    </select>
                  </div>
                  <div style={{ flex: 1, ...s.col }}>
                    <div style={s.lbl}>Min Score</div>
                    <select style={{ ...s.select, width: "100%" }} value={scoreMin}
                      onChange={(e) => setScoreMin(+e.target.value)} data-testid="min-score-select">
                      {[50, 60, 65, 70, 75, 80, 85, 90].map((v) => <option key={v} value={v}>{v}+ ORA</option>)}
                    </select>
                  </div>
                </div>
              </>
            )}

            {mode === "radius" && (
              <>
                <div style={{ ...s.col, marginBottom: 10 }}>
                  <div style={s.lbl}>Address / City / Postal Code</div>
                  <input style={s.input} placeholder="e.g. Mississauga, ON or King & Bay, Toronto"
                    value={address} onChange={(e) => setAddress(e.target.value)} data-testid="radius-address-input" />
                </div>
                <div style={{ marginBottom: 11 }}>
                  <div style={s.sliderHead}>
                    <span style={s.lbl}>Radius</span>
                    <span style={{ fontSize: 13, color: G, fontWeight: 700 }}>{radiusKm} km</span>
                  </div>
                  <input type="range" min={1} max={50} value={radiusKm}
                    onChange={(e) => setRadiusKm(+e.target.value)} style={s.slider} data-testid="radius-slider" />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "#2a2a2a" }}>
                    <span>1 km</span><span>25 km</span><span>50 km</span>
                  </div>
                </div>
                <div style={{ ...s.col, marginBottom: 10 }}>
                  <div style={s.lbl}>Industry Focus</div>
                  <select style={{ ...s.select, width: "100%" }} value={radInd}
                    onChange={(e) => setRadInd(e.target.value)} data-testid="radius-industry-select">
                    <option value="">All businesses</option>
                    {ALL_INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
                  </select>
                </div>
              </>
            )}

            {/* CSV mode (#7) — LIVE hunt via uploaded contact list */}
            {mode === "csv" && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ border: "2px dashed #1e1e1e", borderRadius: 6, padding: "20px 14px", textAlign: "center" }}>
                  <div style={{ fontSize: 22, marginBottom: 7 }}>📋</div>
                  <div style={{ color: "#444", fontSize: 11, lineHeight: 1.6, marginBottom: 12 }}>
                    Upload a CSV with columns: <span style={{ color: "#666" }}>name, phone, email, address</span>
                  </div>
                  <input
                    type="file"
                    accept=".csv,.txt"
                    id="oraCsvFile"
                    data-testid="csv-file-input"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      setCsvFile(f || null);
                      if (f) toast(`${f.name} · ${(f.size / 1024).toFixed(1)}KB`, "success");
                    }}
                  />
                  <label htmlFor="oraCsvFile" style={{ ...s.btnOut(), display: "inline-block", cursor: "pointer" }}>
                    Choose File
                  </label>
                  {csvFile && (
                    <div style={{ marginTop: 10, color: G, fontSize: 11 }}>
                      ✓ {csvFile.name}
                      <span style={{ color: "#555", cursor: "pointer", marginLeft: 7 }} onClick={() => setCsvFile(null)}>✕</span>
                    </div>
                  )}
                </div>
                {/* SAFETY BANNER — CSV is the #1 accidental-live-send surface */}
                <div
                  data-testid="csv-safety-banner"
                  style={{
                    marginTop: 9, padding: "8px 10px", borderRadius: 4,
                    background: "#1a0808",
                    border: "1px solid #7a2020",
                    fontSize: 10.5, color: "#d44",
                    lineHeight: 1.5,
                  }}
                >
                  ⚠ LIVE MODE — real WhatsApp / SMS will go to every contact on this list. DNC auto-skipped.
                </div>
              </div>
            )}

            {/* Limit slider */}
            <div style={{ marginBottom: 11 }}>
              <div style={s.sliderHead}>
                <span style={s.lbl}>Hunt Limit</span>
                <span style={{ fontSize: 13, color: G, fontWeight: 700 }}>{limit}</span>
              </div>
              <input type="range" min={1} max={150} step={1} value={limit}
                onChange={(e) => setLimit(+e.target.value)} style={s.slider} data-testid="limit-slider" />
            </div>

            <div style={{ display: "flex", gap: 7 }}>
              <button style={{ ...s.btnOut(), opacity: previewing ? .5 : 1 }}
                onClick={preview} disabled={previewing} data-testid="preview-btn">
                {previewing ? "Scanning…" : "👁 Preview 5"}
              </button>
              <button style={{ ...s.btnGold, flex: 1, opacity: hunting ? .5 : 1 }}
                onClick={hunt} disabled={hunting} data-testid="hunt-btn">
                {hunting ? "Queuing…" : `🚀 Hunt ${limit} · LIVE`}
              </button>
            </div>
          </div>

          {/* PREVIEW RESULTS */}
          {previewData !== null && (
            <div style={s.sec}>
              <div style={s.secHead}>
                <span style={s.secLabel}>Preview · {previewData.length} found</span>
                <button style={s.btnGhost()} onClick={() => setPrevData(null)}>Clear</button>
              </div>
              {previewData.length === 0 ? (
                <div style={{ color: "#333", fontSize: 12 }}>No results — try broader industry or location.</div>
              ) : (
                previewData.map((b, i) => (
                  <div key={i} style={s.preCard} data-testid={`preview-row-${i}`}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#e4ddd3" }}>{b.name || "—"}</div>
                        <div style={{ fontSize: 10, color: "#555", marginTop: 1 }}>{b.address || ""}</div>
                      </div>
                      {b.score != null && <span style={s.badge("#7EC8A0")}>{b.score}</span>}
                    </div>
                    <div style={{ display: "flex", gap: 10, marginTop: 5 }}>
                      {b.phone && <span style={{ fontSize: 10, color: G }}>{b.phone}</span>}
                      {b.email && <span style={{ fontSize: 10, color: "#7B9FD4" }}>{b.email}</span>}
                    </div>
                  </div>
                ))
              )}
              {previewData.length > 0 && (
                <button style={{ ...s.btnGold, width: "100%", marginTop: 5 }}
                  onClick={hunt} disabled={hunting} data-testid="confirm-hunt-btn">
                  {hunting ? "Queuing…" : `✓ Go — Hunt ${limit}`}
                </button>
              )}
            </div>
          )}

          {/* HUNT PROGRESS PANEL (#1 + #4) — memoized, renders only on hunt_progress events */}
          <HuntProgressPanel progressEvents={progressEvents} active={hunting} />

          {/* LIVE FEED */}
          <div style={{ ...s.sec, flex: 1, display: "flex", flexDirection: "column", minHeight: 220 }}>
            <div style={s.secHead}>
              <span style={s.secLabel}>📡 Live Feed</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span style={{ fontSize: 8.5, color: "#2a5a2a", background: "#081508", border: "1px solid #1a3a1a", borderRadius: 2, padding: "1px 5px" }}>● SSE</span>
                <button style={s.btnGhost()} onClick={clearFeed}>Clear</button>
              </div>
            </div>
            <div style={{ flex: 1, overflowY: "auto", minHeight: 150 }} data-testid="live-feed">
              {feed.length === 0 ? (
                <div style={{ color: "#222", fontSize: 11.5, padding: "16px 0", textAlign: "center" }}>
                  Waiting for activity…
                </div>
              ) : (
                feed.map((e, i) => (
                  <div key={e._k || i} style={s.feedRow}>
                    <span style={{ color: feedColor(e), fontSize: 10.5, flexShrink: 0, marginTop: 1 }}>{feedIcon(e)}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ color: "#999", fontSize: 11 }}>
                        {e.message || e.msg || e.text || "—"}
                      </span>
                      {e.business_name && <div style={{ fontSize: 10, color: G, marginTop: 1 }}>{e.business_name}</div>}
                    </div>
                    <span style={{ fontSize: 9, color: "#222", flexShrink: 0 }}>
                      {ago(e.timestamp)}
                    </span>
                  </div>
                ))
              )}
              <div ref={feedEnd} />
            </div>
            {/* #6 — Jump to leads in Campaign HQ */}
            <button
              data-testid="jump-campaign-hq-btn"
              onClick={() => {
                try {
                  window.parent?.postMessage?.({ type: "aurem:navigate", to: "campaign-dashboard" }, "*");
                } catch {}
                const url = new URL(window.location.href);
                url.searchParams.set("activeItem", "campaign-dashboard");
                window.location.href = `${url.pathname}?activeItem=campaign-dashboard`;
              }}
              style={{
                marginTop: 8, padding: "6px 10px", fontSize: 10,
                background: "transparent", color: G, border: `1px solid ${G}28`,
                borderRadius: 3, cursor: "pointer", letterSpacing: ".06em",
                fontFamily: "'Jost',sans-serif",
              }}
            >
              → View contacted leads in Campaign HQ
            </button>
          </div>
        </div>

        {/* RIGHT */}
        <div style={s.right} className="ora-right">
          <div style={{ display: "flex", borderBottom: "1px solid #1c1c1c", background: "#0e0e10", flexShrink: 0 }}>
            {[["agents", "⬡ Agents"], ["config", "⚙ Schedule"]].map(([k, l]) => (
              <button key={k} onClick={() => setRightTab(k)} data-testid={`right-tab-${k}`} style={{
                flex: 1, padding: "10px 0", fontSize: 9.5, cursor: "pointer",
                background: "transparent", border: "none",
                borderBottom: rightTab === k ? `2px solid ${G}` : "2px solid transparent",
                color: rightTab === k ? G : "#3a3a3a",
                letterSpacing: ".1em", textTransform: "uppercase",
                fontFamily: "'Jost',sans-serif", fontWeight: 600,
              }}>
                {l}
              </button>
            ))}
          </div>

          {rightTab === "agents" && (
            <div style={{ padding: 13, overflowY: "auto" }}>
              {AGENTS.map((agent) => {
                const st = agentStatus[agent.id] || {};
                const sm = STATUS_META[st.status] || STATUS_META.idle;
                const bsy = busy[agent.id];
                const isPaused = st.status === "paused";
                return (
                  <div key={agent.id} style={s.agentCard(agent.accent)} data-testid={`agent-card-${agent.id}`}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <div style={s.dot(sm.color, sm.pulse)} />
                        <div>
                          <div style={{ fontSize: 11.5, fontWeight: 600, color: "#e4ddd3" }}>{agent.label}</div>
                          <div style={{ fontSize: 9, color: "#3a3a3a" }}>{agent.role}</div>
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 9.5, color: sm.color, textTransform: "uppercase", letterSpacing: ".06em" }}>
                          {bsy ? `${bsy}…` : sm.label}
                        </div>
                        {st.last_run && <div style={{ fontSize: 8.5, color: "#2a2a2a" }}>{ago(st.last_run)} ago</div>}
                      </div>
                    </div>
                    {(st.leads_today > 0) && (
                      <div style={{ display: "flex", gap: 9, marginBottom: 7, paddingBottom: 7, borderBottom: "1px solid #141414" }}>
                        <div style={{ fontSize: 10, color: "#555" }}>
                          <span style={{ color: G, fontWeight: 600 }}>{st.leads_today}</span> today
                        </div>
                      </div>
                    )}
                    <div style={{ display: "flex", gap: 5 }}>
                      <button
                        style={{ ...s.btnGhost(isPaused ? "#7EC8A0" : "#7B9FD4"), flex: 1, opacity: bsy ? .4 : 1 }}
                        disabled={!!bsy}
                        onClick={() => agentAct(agent.id, isPaused ? "resume" : "pause")}
                        data-testid={`agent-${agent.id}-toggle`}
                      >
                        {isPaused ? "▶ Resume" : "⏸ Pause"}
                      </button>
                      <button
                        style={{ ...s.btnGhost(agent.accent), flex: 1, opacity: bsy ? .4 : 1, background: bsy === "run" ? `${agent.accent}0e` : "transparent" }}
                        disabled={!!bsy}
                        onClick={() => agentAct(agent.id, "run")}
                        data-testid={`agent-${agent.id}-run`}
                      >
                        {bsy === "run" ? "⟳ Running" : "▷ Run Now"}
                      </button>
                    </div>
                  </div>
                );
              })}
              <button style={{ ...s.btnGold, width: "100%", marginTop: 5 }}
                onClick={() => {
                  ["hunter_ora", "followup_ora", "closer_ora"].forEach((id, i) =>
                    setTimeout(() => agentAct(id, "run"), i * 400));
                  toast("Chain queued: Hunter → Follow-up → Closer", "success", 5000);
                }}
                data-testid="run-chain-btn">
                ⬡ Run Full Chain
              </button>
            </div>
          )}

          {rightTab === "config" && (
            <div style={{ padding: 13, overflowY: "auto" }}>
              <div style={{ fontSize: 11, color: "#444", marginBottom: 13, lineHeight: 1.7 }}>
                Auto-scheduled background cycles. "Hunt Now" overrides for one-off runs.
              </div>
              <div style={{ ...s.col, marginBottom: 10 }}>
                <div style={s.lbl}>Ramp Mode</div>
                <select style={{ ...s.select, width: "100%" }} value={config?.ramp_mode || "safe"}
                  onChange={(e) => { setConfig((p) => ({ ...p, ramp_mode: e.target.value })); setDirty(true); }}
                  data-testid="ramp-mode-select">
                  <option value="safe">Safe (dry-run first)</option>
                  <option value="aggressive">Aggressive</option>
                </select>
              </div>
              <div style={s.row}>
                <div style={{ flex: 1, ...s.col }}>
                  <div style={s.lbl}>Morning Brief</div>
                  <input type="time" style={s.input} value={config?.morning_brief_time || "07:00"}
                    onChange={(e) => { setConfig((p) => ({ ...p, morning_brief_time: e.target.value })); setDirty(true); }} />
                </div>
                <div style={{ flex: 1, ...s.col }}>
                  <div style={s.lbl}>Evening Brief</div>
                  <input type="time" style={s.input} value={config?.evening_brief_time || "19:00"}
                    onChange={(e) => { setConfig((p) => ({ ...p, evening_brief_time: e.target.value })); setDirty(true); }} />
                </div>
              </div>
              {/* #5 — Active outreach hours (CASL: 9-5 EST, no Sundays) */}
              <div style={s.row}>
                <div style={{ flex: 1, ...s.col }}>
                  <div style={s.lbl}>Active Hours From</div>
                  <input
                    type="time"
                    style={s.input}
                    value={config?.active_hours_start || "09:00"}
                    onChange={(e) => { setConfig((p) => ({ ...p, active_hours_start: e.target.value })); setDirty(true); }}
                    data-testid="active-hours-start"
                  />
                </div>
                <div style={{ flex: 1, ...s.col }}>
                  <div style={s.lbl}>Active Hours To</div>
                  <input
                    type="time"
                    style={s.input}
                    value={config?.active_hours_end || "17:00"}
                    onChange={(e) => { setConfig((p) => ({ ...p, active_hours_end: e.target.value })); setDirty(true); }}
                    data-testid="active-hours-end"
                  />
                </div>
              </div>
              <div style={{ fontSize: 10, color: "#444", marginTop: -4, marginBottom: 10 }}>
                Outreach runs only inside this window. Sundays are auto-skipped for CASL.
              </div>
              <div style={s.divider} />
              <div style={s.lbl}>Province Schedule</div>
              {PROVINCES.map((p) => {
                const pc = config?.province_config?.[p.label] || config?.province_config?.[p.key] || {};
                const active = pc.active ?? (p.key === "ontario");
                const lim = pc.limit ?? 30;
                return (
                  <div key={p.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid #111" }}>
                    <Toggle sm on={active} color={G} set={(val) => {
                      setConfig((prev) => ({
                        ...prev,
                        province_config: {
                          ...(prev?.province_config || {}),
                          [p.label]: { ...(prev?.province_config?.[p.label] || {}), active: val, limit: lim },
                        },
                      }));
                      setDirty(true);
                    }} />
                    <span style={{ fontSize: 11, color: active ? "#e4ddd3" : "#3a3a3a", flex: 1 }}>{p.label}</span>
                    <input type="number" min={1} max={200} value={lim}
                      onChange={(e) => {
                        setConfig((prev) => ({
                          ...prev,
                          province_config: {
                            ...(prev?.province_config || {}),
                            [p.label]: { ...(prev?.province_config?.[p.label] || {}), active, limit: +e.target.value },
                          },
                        }));
                        setDirty(true);
                      }}
                      style={{ ...s.input, width: 50, padding: "3px 5px", fontSize: 11, textAlign: "center", opacity: active ? 1 : .3 }} />
                  </div>
                );
              })}
              <button style={{ ...s.btnGold, width: "100%", marginTop: 13, opacity: saving ? .5 : 1 }}
                onClick={saveConfig} disabled={saving} data-testid="save-config-btn">
                {saving ? "Saving…" : `💾 Save${dirty ? " ·" : ""}`}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Drawers — Morning Brief + Smart Approvals */}
      <Drawer
        open={briefOpen}
        onClose={() => setBriefOpen(false)}
        title="Morning Brief"
        subtitle={new Date().toLocaleDateString("en-CA", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
        accentColor="#C9A227"
      >
        <MorningBriefDrawerBody brief={brief} loading={briefLoading} onRegenerate={regenerateBrief} />
      </Drawer>
      <Drawer
        open={approvalsOpen}
        onClose={() => setApprovalsOpen(false)}
        title="Smart Approvals"
        subtitle={`${approvalsCount} pending decision${approvalsCount !== 1 ? "s" : ""}`}
        accentColor="#7B9FD4"
      >
        <ApprovalsDrawerBody
          approvals={approvals}
          loading={approvalsLoading}
          onApprove={handleApprove}
          onReject={handleReject}
          actingId={actingApprovalId}
        />
      </Drawer>
      <Drawer
        open={scoutOpen}
        onClose={() => setScoutOpen(false)}
        title="ORA Scout"
        subtitle="Deep research · Surface + OSINT"
        accentColor="#7B9FD4"
      >
        <ScoutDrawerBody
          query={scoutQuery}
          setQuery={setScoutQuery}
          depth={scoutDepth}
          setDepth={setScoutDepth}
          loading={scoutLoading}
          result={scoutResult}
          onRun={runScout}
        />
      </Drawer>
      <Drawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title="🔒 Hunt Command History"
        subtitle={`${commandHistory.length} locked command${commandHistory.length !== 1 ? "s" : ""} · persists across refresh`}
        accentColor="#4ADE80"
      >
        <div data-testid="history-body">
          {commandHistory.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 12px", color: "#555", fontSize: 12 }}>
              No hunt commands locked yet.<br />
              <span style={{ fontSize: 10, color: "#333" }}>Fire a Hunt, CSV upload, or Radius Search from the left panel — it'll appear here with timestamp and outcome.</span>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <button
                onClick={loadCommandHistory}
                data-testid="history-refresh"
                style={{ alignSelf: "flex-end", background: "transparent", border: "1px solid #333", color: "#888", fontSize: 10, padding: "4px 10px", borderRadius: 4, cursor: "pointer", letterSpacing: ".08em", textTransform: "uppercase" }}
              >
                ↻ Refresh
              </button>
              {commandHistory.map((c) => {
                const statusColor = c.status === "completed" ? "#4ADE80"
                                  : c.status === "failed"    ? "#ef4444"
                                  : c.status === "running"   ? "#C9A227"
                                  :                            "#7B9FD4";
                const ind = (c.industry || []).join(", ") || "—";
                const target = c.mode === "radius" ? (c.address || "—")
                             : c.mode === "csv"    ? "CSV upload"
                             :                       (c.province || "—");
                const when = c.fired_at ? new Date(c.fired_at).toLocaleString("en-CA",
                  { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
                return (
                  <div
                    key={c.command_id}
                    data-testid={`history-cmd-${c.command_id}`}
                    style={{
                      background: "#0b0b0c", border: `1px solid #1a1a1a`, borderLeft: `3px solid ${statusColor}`,
                      borderRadius: 4, padding: "10px 12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 11, color: "#e4ddd3", fontWeight: 600 }}>
                          {c.mode === "radius" ? "◎" : c.mode === "csv" ? "▤" : "⌖"} {c.mode.toUpperCase()} · {ind}
                        </div>
                        <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>
                          Target: <span style={{ color: "#C9A227" }}>{target}</span>
                          {c.radius_km ? ` · ${c.radius_km} km` : ""}
                          {" · limit "}<span style={{ color: "#e4ddd3" }}>{c.limit}</span>
                        </div>
                        <div style={{ fontSize: 9.5, color: "#555", marginTop: 3 }}>
                          {when} · by {c.fired_by || "admin"} · <span style={{ color: "#444" }}>{c.command_id}</span>
                        </div>
                      </div>
                      <div style={{ textAlign: "right", minWidth: 72 }}>
                        <div style={{
                          display: "inline-block", padding: "2px 6px", borderRadius: 3,
                          fontSize: 9, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase",
                          background: `${statusColor}15`, color: statusColor, border: `1px solid ${statusColor}40`,
                        }}>
                          {c.status}
                        </div>
                        {typeof c.result_count === "number" && (
                          <div style={{ fontSize: 10, color: "#888", marginTop: 4 }}>
                            {c.result_count} result{c.result_count !== 1 ? "s" : ""}
                          </div>
                        )}
                      </div>
                    </div>
                    {c.error && (
                      <div style={{ marginTop: 6, fontSize: 10, color: "#ef4444", background: "rgba(239,68,68,0.06)", padding: "4px 8px", borderRadius: 3 }}>
                        {c.error}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Drawer>
    </div>
  );
}
