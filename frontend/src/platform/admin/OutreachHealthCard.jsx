/**
 * OutreachHealthCard.jsx — iter 330 FIX 5
 *
 * 7-channel outreach health at-a-glance.
 * Green / yellow / red badges + last-fire timestamp + 24h count.
 * Polls every 60 s. Quick-action buttons fire each cron manually.
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  Mail, MessageCircle, Smartphone, Phone, Compass, Sparkles, Share2,
  CheckCircle, AlertTriangle, XCircle, RefreshCw, Play,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const OK_GREEN = "#22c55e";
const WARN = "#F5C45E";
const ERR_RED = "#ef4444";
const PANEL_BG = "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))";

const ICONS = {
  "Email":                Mail,
  "WhatsApp":             MessageCircle,
  "SMS":                  Smartphone,
  "Voice (Retell)":       Phone,
  "Daily Hunt":           Compass,
  "Proactive Follow-up":  Sparkles,
  "Social (LinkedIn)":    Share2,
};

const ACTIONS = {
  "Voice (Retell)":      { path: "/api/admin/outreach/closer-day5/run", label: "Run Day-5 sweep" },
  "Social (LinkedIn)":   { path: "/api/admin/outreach/social/post-now", label: "Post now" },
  "Proactive Follow-up": { path: null,                                   label: null },
};
const REPLY_INBOX_ACTION = { path: "/api/admin/outreach/reply-inbox/run", label: "Process replies" };

function authHeaders() {
  const t = sessionStorage.getItem("platform_token")
    || localStorage.getItem("platform_token")
    || localStorage.getItem("aurem_admin_token")
    || sessionStorage.getItem("aurem_admin_token")
    || localStorage.getItem("token") || "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function statusColor(s) {
  if (s === "green")  return OK_GREEN;
  if (s === "yellow") return WARN;
  return ERR_RED;
}

function StatusIcon({ status, size = 14 }) {
  if (status === "green")  return <CheckCircle    size={size} color={OK_GREEN} />;
  if (status === "yellow") return <AlertTriangle size={size} color={WARN}    />;
  return <XCircle size={size} color={ERR_RED} />;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!t || Number.isNaN(t)) return "—";
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1)    return "just now";
  if (mins < 60)   return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

export default function OutreachHealthCard() {
  const [snap, setSnap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState(null);
  const [actionMsg, setActionMsg] = useState(null);
  const [unmatched, setUnmatched] = useState(null);
  const [showUnmatched, setShowUnmatched] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const r = await fetch(`${API}/api/admin/outreach/health`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSnap(await r.json());
      // iter 330b — also fetch unmatched-pixel summary (cheap).
      const r2 = await fetch(`${API}/api/admin/outreach/unmatched-pixels?limit=10`, {
        headers: authHeaders(),
      });
      if (r2.ok) setUnmatched(await r2.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  async function fireAction(path, key) {
    setBusyAction(key);
    setActionMsg(null);
    try {
      const r = await fetch(`${API}${path}`, { method: "POST", headers: authHeaders() });
      const j = await r.json().catch(() => ({}));
      setActionMsg(j?.ok ? `${key}: ✔ ran (${JSON.stringify(j).slice(0, 80)})` : `${key}: ✖ ${JSON.stringify(j).slice(0, 80)}`);
      await load();
    } catch (e) {
      setActionMsg(`${key}: ✖ ${e.message || e}`);
    } finally {
      setBusyAction(null);
      setTimeout(() => setActionMsg(null), 8000);
    }
  }

  return (
    <section
      data-testid="outreach-health-card"
      style={{
        padding: 18, borderRadius: 14,
        background: PANEL_BG, border: `1px solid ${BORDER}`,
        marginBottom: 18,
      }}
    >
      <header style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: TEXT }}>
          Outreach Health
        </span>
        <span
          data-testid="outreach-overall-status"
          style={{
            padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
            background: snap?.overall === "green" ? "rgba(34,197,94,0.18)"
                       : snap?.overall === "yellow" ? "rgba(245,196,94,0.18)"
                       : "rgba(239,68,68,0.18)",
            color: statusColor(snap?.overall),
          }}
        >
          {snap?.overall ? snap.overall.toUpperCase() : "—"}
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => fireAction(REPLY_INBOX_ACTION.path, "Reply inbox")}
          data-testid="outreach-run-reply-inbox"
          disabled={busyAction === "Reply inbox"}
          style={pillBtn(busyAction === "Reply inbox")}
        >
          <Play size={11} /> {REPLY_INBOX_ACTION.label}
        </button>
        <button
          onClick={load} aria-label="Refresh"
          data-testid="outreach-refresh"
          style={{
            width: 26, height: 26, marginLeft: 6, border: `1px solid ${BORDER}`,
            background: "transparent", borderRadius: 6, cursor: "pointer",
            color: TEXT_DIM, display: "inline-flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <RefreshCw size={12} />
        </button>
      </header>

      {actionMsg && (
        <div
          data-testid="outreach-action-msg"
          style={{
            marginBottom: 10, padding: "8px 12px", borderRadius: 8,
            background: "rgba(212,175,55,0.10)", border: `1px solid ${BORDER}`,
            color: TEXT, fontSize: 12,
          }}
        >
          {actionMsg}
        </div>
      )}

      {loading && !snap ? (
        <div style={{ color: TEXT_DIM, fontSize: 12 }}>Loading…</div>
      ) : error ? (
        <div data-testid="outreach-error" style={{ color: ERR_RED, fontSize: 12 }}>{error}</div>
      ) : snap?.channels ? (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 10,
        }}>
          {snap.channels.map((c) => {
            const Icon = ICONS[c.label] || Compass;
            const action = ACTIONS[c.label];
            const tid = `outreach-row-${c.label.toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "")}`;
            return (
              <div
                key={c.label}
                data-testid={tid}
                style={{
                  padding: "10px 12px", borderRadius: 8,
                  background: c.status === "green" ? "rgba(34,197,94,0.06)"
                             : c.status === "yellow" ? "rgba(245,196,94,0.06)"
                             : "rgba(239,68,68,0.06)",
                  border: `1px solid ${c.status === "green" ? "rgba(34,197,94,0.30)"
                                          : c.status === "yellow" ? "rgba(245,196,94,0.30)"
                                          : "rgba(239,68,68,0.30)"}`,
                  fontSize: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <Icon size={14} color={statusColor(c.status)} />
                  <span style={{ color: TEXT, fontWeight: 600 }}>{c.label}</span>
                  <StatusIcon status={c.status} />
                  <div style={{ flex: 1 }} />
                  <span style={{ color: TEXT_DIM, fontSize: 11 }}>{timeAgo(c.last_fire_at)}</span>
                </div>
                <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 4 }}>
                  {c.last_24h_count !== undefined ? `${c.last_24h_count} in 24h` : ""}
                  {c.success_pct !== null && c.success_pct !== undefined ?
                      ` · ${c.success_pct}% success` : ""}
                </div>
                {c.note && (
                  <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: action?.path ? 6 : 0 }}>
                    {c.note}
                  </div>
                )}
                {action?.path && (
                  <button
                    onClick={() => fireAction(action.path, c.label)}
                    data-testid={`outreach-run-${c.label.toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "")}`}
                    disabled={busyAction === c.label}
                    style={pillBtn(busyAction === c.label)}
                  >
                    <Play size={11} /> {action.label}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* iter 330b — Unmatched-pixel review row */}
      {unmatched && (unmatched.total ?? 0) > 0 && (
        <div
          data-testid="outreach-unmatched-pixels"
          style={{
            marginTop: 14, padding: "8px 12px", borderRadius: 8,
            background: "rgba(245,196,94,0.05)",
            border: `1px solid rgba(245,196,94,0.20)`,
            fontSize: 11, color: TEXT_DIM,
          }}
        >
          <div
            onClick={() => setShowUnmatched((v) => !v)}
            data-testid="outreach-unmatched-toggle"
            style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
          >
            <AlertTriangle size={11} color={WARN} />
            <span style={{ color: TEXT }}>Unmatched pixel hits</span>
            <span style={{ color: WARN, fontWeight: 600 }}>
              {unmatched.count_24h} in 24h
            </span>
            <span>· {unmatched.total} total</span>
            <div style={{ flex: 1 }} />
            <span style={{ color: TEXT_DIM, fontSize: 10 }}>
              {showUnmatched ? "hide ▾" : "show ▸"}
            </span>
          </div>
          {showUnmatched && (unmatched.entries || []).length > 0 && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
              {(unmatched.entries || []).map((e, i) => (
                <div
                  key={i}
                  data-testid={`unmatched-pixel-row-${i}`}
                  style={{
                    padding: "6px 8px", borderRadius: 6,
                    background: "rgba(0,0,0,0.18)",
                    fontSize: 11, lineHeight: 1.4,
                  }}
                >
                  <div style={{ color: TEXT }}>
                    {e.platform}/{e.event_type}
                    <span style={{ color: TEXT_DIM, marginLeft: 8 }}>
                      {timeAgo(e.ts)}
                    </span>
                    {e.remote_addr && (
                      <span style={{ color: TEXT_DIM, marginLeft: 8 }}>
                        from {e.remote_addr}
                      </span>
                    )}
                  </div>
                  {e.referer && (
                    <div style={{ color: TEXT_DIM, marginTop: 2, wordBreak: "break-all" }}>
                      ref: {e.referer.slice(0, 80)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

const pillBtn = (busy) => ({
  display: "inline-flex", alignItems: "center", gap: 5,
  padding: "5px 10px", borderRadius: 999,
  background: busy ? "rgba(212,175,55,0.25)" : "rgba(212,175,55,0.10)",
  border: `1px solid ${BORDER}`, color: "#D4AF37",
  fontSize: 11, fontWeight: 600,
  cursor: busy ? "not-allowed" : "pointer",
  opacity: busy ? 0.7 : 1,
});
