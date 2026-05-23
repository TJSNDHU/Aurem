/**
 * SlaCard.jsx — iter 328f SLA + Error Budget card.
 *
 * Plugs into ORA-CTO Cockpit. Shows the 4 SLA metrics at-a-glance with
 * pass/fail badges. Polls every 30 s.
 */
import React, { useEffect, useState, useCallback } from "react";
import { Gauge, CheckCircle, XCircle, RefreshCw } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const OK_GREEN = "#22c55e";
const ERR_RED = "#ef4444";
const PANEL_BG = "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))";

function authHeaders() {
  const t =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") || "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

const METRIC_LABELS = {
  uptime_pct:              { label: "Uptime",         unit: "%",  better: "higher" },
  ora_latency_p95_seconds: { label: "ORA p95",        unit: "s",  better: "lower"  },
  email_delivery_pct:      { label: "Email delivery", unit: "%",  better: "higher" },
  campaign_completion_pct: { label: "Campaign cycle", unit: "%",  better: "higher" },
};

export default function SlaCard() {
  const [snap, setSnap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const r = await fetch(`${API}/api/admin/sla/snapshot`, {
        headers: authHeaders(),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSnap(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <section
      data-testid="sla-card"
      style={{
        padding: 18, borderRadius: 14,
        background: PANEL_BG, border: `1px solid ${BORDER}`,
        marginBottom: 18,
      }}
    >
      <header style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <Gauge size={16} color={GOLD} />
        <span style={{ fontSize: 14, fontWeight: 700, color: TEXT }}>
          SLA & Error Budget
        </span>
        <span
          data-testid="sla-overall-status"
          style={{
            padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
            background: snap?.all_ok ? "rgba(34,197,94,0.18)" : "rgba(239,68,68,0.18)",
            color: snap?.all_ok ? OK_GREEN : ERR_RED,
            marginLeft: 6,
          }}
        >
          {snap?.all_ok ? "ALL GREEN" : snap ? "BREACH" : "—"}
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ color: TEXT_DIM, fontSize: 11 }}>
          {snap?.ts ? new Date(snap.ts).toLocaleTimeString() : "—"}
        </span>
        <button
          onClick={load}
          data-testid="sla-refresh"
          aria-label="Refresh SLA"
          style={{
            width: 26, height: 26, border: `1px solid ${BORDER}`,
            background: "transparent", borderRadius: 6, cursor: "pointer",
            color: TEXT_DIM, display: "inline-flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <RefreshCw size={12} />
        </button>
      </header>

      {loading && !snap ? (
        <div style={{ color: TEXT_DIM, fontSize: 12 }}>Loading…</div>
      ) : error ? (
        <div data-testid="sla-error" style={{ color: ERR_RED, fontSize: 12 }}>{error}</div>
      ) : snap?.metrics ? (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 10,
        }}>
          {Object.entries(snap.metrics).map(([key, m]) => {
            const meta = METRIC_LABELS[key] || { label: key, unit: "", better: "higher" };
            const ok = !!m.ok;
            return (
              <div
                key={key}
                data-testid={`sla-metric-${key}`}
                style={{
                  padding: "10px 12px", borderRadius: 8,
                  background: ok ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)",
                  border: `1px solid ${ok ? "rgba(34,197,94,0.30)" : "rgba(239,68,68,0.30)"}`,
                  fontSize: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  {ok ? <CheckCircle size={12} color={OK_GREEN} /> : <XCircle size={12} color={ERR_RED} />}
                  <span style={{ color: TEXT, fontWeight: 600 }}>{meta.label}</span>
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color: ok ? OK_GREEN : ERR_RED }}>
                  {(m.value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  <span style={{ fontSize: 12, color: TEXT_DIM, marginLeft: 4 }}>{meta.unit}</span>
                </div>
                <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 4 }}>
                  target: {(m.target ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}{meta.unit}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
