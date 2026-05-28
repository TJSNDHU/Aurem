/**
 * AdminSecurityKeys.jsx — iter D-46
 *
 * /admin/security-keys — admin overview of every customer's security
 * key status. Plaintext values are NEVER exposed; admins see only
 * `key_tail` (last 4 chars) and metadata. Admins can force-rotate.
 */
import React, { useEffect, useState } from "react";
import { ShieldAlert, RotateCcw, AlertTriangle, CheckCircle2,
         History as HistoryIcon, RefreshCw } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

function authHeaders() {
  const tok = localStorage.getItem("aurem.admin_jwt")
           || localStorage.getItem("aurem.dev_jwt")
           || localStorage.getItem("aurem.jwt") || "";
  return tok ? { Authorization: `Bearer ${tok}` } : {};
}

const ADMIN_BASE = `${API}/api/admin/security-keys`;

function StatusBadge({ status }) {
  const cfg = status === "active"
    ? { c: "var(--dash-green, #4ade80)",
        bg: "rgba(74,222,128,0.12)",
        label: "Active", Icon: CheckCircle2 }
    : status === "rotated"
      ? { c: "#FF8C35",
          bg: "rgba(255,140,53,0.12)",
          label: "Rotated", Icon: RotateCcw }
      : { c: "#FF6060",
          bg: "rgba(255,96,96,0.12)",
          label: "No keys", Icon: AlertTriangle };
  const Icon = cfg.Icon;
  return (
    <span data-testid={`security-status-${status || "none"}`}
          style={{ display: "inline-flex", alignItems: "center", gap: 4,
                   padding: "3px 8px", borderRadius: 999,
                   background: cfg.bg, color: cfg.c,
                   fontSize: 10, letterSpacing: 0.5,
                   textTransform: "uppercase" }}>
      <Icon size={10} /> {cfg.label}
    </span>
  );
}


export default function AdminSecurityKeys() {
  const [data, setData] = useState(null);
  const [err,  setErr]  = useState(null);
  const [busy, setBusy] = useState({});  // user_id → bool
  const [openHist, setOpenHist] = useState(null);
  const [history,  setHistory]  = useState(null);

  async function load() {
    setErr(null);
    try {
      const r = await fetch(ADMIN_BASE,
                              { headers: authHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "fetch_failed");
      setData(j);
    } catch (e) { setErr(String(e.message || e)); }
  }
  useEffect(() => { load(); }, []);

  async function forceRotate(user_id, email) {
    const reason = window.prompt(
      `Force-rotate keys for ${email || user_id}?\n\n` +
      "Reason (optional, logged in audit trail):");
    if (reason === null) return;
    setBusy(b => ({ ...b, [user_id]: true }));
    try {
      const r = await fetch(
        `${ADMIN_BASE}/${encodeURIComponent(user_id)}/rotate`,
        { method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ reason: reason || "" }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "rotate_failed");
      await load();
    } catch (e) { alert(String(e.message || e)); }
    finally   { setBusy(b => ({ ...b, [user_id]: false })); }
  }

  async function viewHistory(user_id) {
    setOpenHist(user_id);
    setHistory(null);
    try {
      const r = await fetch(
        `${ADMIN_BASE}/${encodeURIComponent(user_id)}/history`,
        { headers: authHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "history_failed");
      setHistory(j);
    } catch (e) { setHistory({ error: String(e.message || e), items: [] }); }
  }

  return (
    <div data-testid="admin-security-keys-page"
         style={{ padding: "24px 28px", maxWidth: 1100,
                  fontFamily: "'Inter', system-ui, sans-serif",
                  color: "#F0EDE8", background: "#0e0c0a",
                  minHeight: "100vh" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                     marginBottom: 6 }}>
        <ShieldAlert size={22} style={{ color: "#FF8C35" }} />
        <h1 style={{ fontFamily: "'Cinzel', serif",
                      fontSize: 22, margin: 0, color: "#E8C86A" }}>
          Customer security keys
        </h1>
        <button onClick={load}
                data-testid="security-admin-refresh"
                style={{ marginLeft: "auto",
                         background: "rgba(255,255,255,0.04)",
                         border: "1px solid rgba(255,255,255,0.10)",
                         color: "#FFB070",
                         padding: "6px 12px", borderRadius: 4,
                         cursor: "pointer", fontSize: 12,
                         display: "inline-flex", alignItems: "center", gap: 6 }}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      <p style={{ fontSize: 13, color: "#a1958a", marginBottom: 18 }}>
        Read-only view. Plaintext keys are never returned via the admin
        path — only masked tails. Force-rotate triggers a new active
        record; the customer must re-fetch their own plaintext next.
      </p>

      {/* Summary tiles */}
      {data && (
        <div style={{ display: "grid",
                       gridTemplateColumns: "repeat(3, 1fr)",
                       gap: 12, marginBottom: 18 }}>
          {[
            { k: "total",   l: "Total customers", c: "#E8C86A" },
            { k: "active",  l: "Active",          c: "#4ade80" },
            { k: "rotated", l: "Rotated",         c: "#FF8C35" },
          ].map(t => (
            <div key={t.k}
                 data-testid={`security-tile-${t.k}`}
                 style={{ padding: "12px 14px",
                          background: "rgba(255,255,255,0.03)",
                          border: "1px solid rgba(255,255,255,0.08)",
                          borderRadius: 6 }}>
              <div style={{ fontSize: 10, letterSpacing: 0.5,
                             color: "#a1958a",
                             textTransform: "uppercase" }}>{t.l}</div>
              <div style={{ fontSize: 22, fontWeight: 600,
                             color: t.c, marginTop: 4,
                             fontFamily: "'JetBrains Mono', monospace" }}>
                {data[t.k] ?? 0}
              </div>
            </div>
          ))}
        </div>
      )}

      {err && (
        <div data-testid="security-admin-error"
             style={{ padding: 12, marginBottom: 14,
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12, color: "#FF6060" }}>
          {err}
        </div>
      )}

      {/* Customer table */}
      <div style={{ background: "rgba(255,255,255,0.02)",
                     border: "1px solid rgba(255,255,255,0.08)",
                     borderRadius: 6, overflow: "hidden" }}>
        <div style={{ display: "grid",
                       gridTemplateColumns: "1.4fr 1.2fr 1.4fr auto 1.2fr auto",
                       gap: 10, padding: "10px 14px",
                       background: "rgba(255,107,0,0.04)",
                       fontSize: 10, letterSpacing: 0.6,
                       textTransform: "uppercase", color: "#FF8C35",
                       fontFamily: "'JetBrains Mono', monospace" }}>
          <span>Customer</span>
          <span>Tenant</span>
          <span>Generated at</span>
          <span>Status</span>
          <span>From IP</span>
          <span style={{ textAlign: "right" }}>Actions</span>
        </div>
        {(data?.items || []).length === 0 && (
          <div data-testid="security-admin-empty"
               style={{ padding: 24, textAlign: "center",
                        color: "#a1958a", fontSize: 13 }}>
            No customers have generated security keys yet.
          </div>
        )}
        {(data?.items || []).map(r => (
          <div key={r.user_id}
               data-testid={`security-admin-row-${r.user_id}`}
               style={{ display: "grid",
                        gridTemplateColumns: "1.4fr 1.2fr 1.4fr auto 1.2fr auto",
                        gap: 10, padding: "12px 14px",
                        borderTop: "1px solid rgba(255,255,255,0.06)",
                        fontSize: 12, alignItems: "center" }}>
            <span style={{ overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap" }}>
              {r.email || r.user_id}
            </span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace",
                            color: "#a1958a" }}>
              {r.tenant_id || "default"}
            </span>
            <span style={{ color: "#a1958a", fontSize: 11 }}>
              {r.generated_at
                ? new Date(r.generated_at).toLocaleString()
                : "—"}
            </span>
            <StatusBadge status={r.status} />
            <span style={{ fontFamily: "'JetBrains Mono', monospace",
                            color: "#a1958a", fontSize: 11 }}>
              {r.ip_address || "—"}
            </span>
            <span style={{ display: "flex", gap: 6,
                            justifyContent: "flex-end" }}>
              <button onClick={() => viewHistory(r.user_id)}
                      data-testid={`security-history-${r.user_id}`}
                      title="View rotation history"
                      style={{ background: "transparent",
                               border: "1px solid rgba(255,255,255,0.10)",
                               color: "#a1958a",
                               padding: "5px 8px", borderRadius: 4,
                               cursor: "pointer",
                               display: "inline-flex", alignItems: "center" }}>
                <HistoryIcon size={12} />
              </button>
              <button onClick={() => forceRotate(r.user_id, r.email)}
                      disabled={busy[r.user_id]}
                      data-testid={`security-rotate-${r.user_id}`}
                      style={{ background: "rgba(255,107,0,0.10)",
                               border: "1px solid rgba(255,107,0,0.30)",
                               color: "#FF8C35",
                               padding: "5px 10px", borderRadius: 4,
                               cursor: busy[r.user_id]
                                 ? "not-allowed" : "pointer",
                               opacity: busy[r.user_id] ? 0.5 : 1,
                               fontSize: 11,
                               display: "inline-flex", alignItems: "center", gap: 4 }}>
                <RotateCcw size={11} />
                {busy[r.user_id] ? "…" : "Rotate"}
              </button>
            </span>
          </div>
        ))}
      </div>

      {/* History drawer (inline panel — not a modal) */}
      {openHist && (
        <div data-testid="security-history-panel"
             style={{ marginTop: 16, padding: 14,
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8,
                         marginBottom: 10 }}>
            <HistoryIcon size={14} style={{ color: "#FF8C35" }} />
            <strong style={{ fontSize: 13, color: "#E8C86A" }}>
              Rotation history — {openHist}
            </strong>
            <button onClick={() => setOpenHist(null)}
                    style={{ marginLeft: "auto",
                             background: "transparent", border: "none",
                             color: "#a1958a", cursor: "pointer",
                             fontSize: 12 }}>Close</button>
          </div>
          {!history && (
            <div style={{ fontSize: 11, color: "#a1958a" }}>Loading…</div>
          )}
          {history?.items?.map((row, i) => (
            <div key={i}
                  data-testid={`security-history-row-${i}`}
                  style={{ display: "grid",
                           gridTemplateColumns: "1fr auto auto",
                           gap: 12, padding: "8px 0",
                           borderTop: i > 0
                             ? "1px solid rgba(255,255,255,0.06)" : "none",
                           fontSize: 11,
                           fontFamily: "'JetBrains Mono', monospace" }}>
              <span style={{ color: "#a1958a" }}>
                {row.generated_at
                  ? new Date(row.generated_at).toLocaleString()
                  : "—"}
              </span>
              <span style={{ color: "#a1958a" }}>
                {row.ip_address || "—"}
              </span>
              <StatusBadge status={row.status} />
            </div>
          ))}
          {history?.items?.length === 0 && (
            <div style={{ fontSize: 11, color: "#a1958a" }}>
              No history records.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
