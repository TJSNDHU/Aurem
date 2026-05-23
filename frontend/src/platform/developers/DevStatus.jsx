/**
 * /developers/status — Live system status (Auth-gated)
 */
import React, { useEffect, useState, useCallback } from "react";
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from "lucide-react";
import DeveloperShell from "./DeveloperShell";
import { PageHeader } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 30000;

const DOT  = { green: "#50C878", yellow: "#FFB36B",
                red: "#FF6060",  gray: "#7A7590" };
const ICON = { green: CheckCircle2, yellow: AlertTriangle,
                red: XCircle, gray: AlertTriangle };

export default function DevStatus() {
  const [data, setData]       = useState(null);
  const [error, setError]     = useState(null);
  const [updated, setUpdated] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/public/status`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setUpdated(new Date());
      setError(null);
    } catch (e) {
      setError(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const components = buildRows(data);
  const overall = components.some(c => c.status === "red") ? "red"
                : components.some(c => c.status === "yellow") ? "yellow"
                : components.length === 0 ? "gray" : "green";
  const OverallIcon = ICON[overall];

  return (
    <DeveloperShell requireAuth>
      <div style={{ display: "flex", alignItems: "flex-end",
                     justifyContent: "space-between", flexWrap: "wrap",
                     gap: 12, marginBottom: 4 }}>
        <PageHeader eyebrow="STATUS"
                    title={
                      overall === "green" ? "All systems normal"
                      : overall === "yellow" ? "Minor degradation"
                      : overall === "red" ? "Incident in progress"
                      : "Loading…"
                    }
                    sub="Updated every 30 seconds." />
        <button onClick={load} data-testid="status-refresh-btn"
                 className="av2-icon-btn"
                 style={{ display: "inline-flex", alignItems: "center",
                           gap: 6, width: "auto", padding: "0 14px" }}>
          <RefreshCw size={13} />
          <span style={{ fontSize: 12 }}>Refresh</span>
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12,
                     marginBottom: 16 }}>
        <OverallIcon size={26} style={{ color: DOT[overall] }} />
        <span data-testid="status-overall-label"
               style={{ fontSize: 14, color: "var(--dash-text-muted)" }}>
          {components.length} components monitored
        </span>
      </div>

      {error && (
        <div data-testid="status-error" className="av2-card"
              style={{ borderColor: "rgba(255,96,96,0.30)",
                        background: "rgba(255,96,96,0.05)",
                        color: "var(--dash-red)", fontSize: 13 }}>
          Couldn't reach status endpoint: {error}
        </div>
      )}

      <div data-testid="status-component-list" className="av2-card"
            style={{ padding: 0 }}>
        {components.length === 0 && !error && (
          <p style={{ padding: 24, fontSize: 13,
                       color: "var(--dash-text-muted)" }}>
            Loading status…
          </p>
        )}
        {components.map((c, i) => {
          const StatusIcon = ICON[c.status];
          return (
            <div key={c.id}
                  style={{
                    display: "flex", alignItems: "center",
                    justifyContent: "space-between",
                    padding: "14px 20px",
                    borderTop: i > 0 ? "1px solid var(--dash-divider)" : "none",
                  }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span data-testid="status-indicator"
                       style={{
                         width: 8, height: 8, borderRadius: "50%",
                         background: DOT[c.status],
                         boxShadow: `0 0 10px ${DOT[c.status]}`,
                       }} />
                <span style={{ fontSize: 14, color: "var(--dash-text)" }}>
                  {c.name}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8,
                             fontSize: 12,
                             color: "var(--dash-text-muted)" }}>
                <StatusIcon size={14} style={{ color: DOT[c.status] }} />
                <span data-testid={`status-state-${c.id}`}>{c.label}</span>
              </div>
            </div>
          );
        })}
      </div>

      <p data-testid="status-last-updated"
         style={{ fontFamily: "'JetBrains Mono', monospace",
                   fontSize: 11, color: "var(--dash-text-faint)",
                   textAlign: "right", marginTop: 6 }}>
        Last updated: {updated ? updated.toLocaleTimeString() : "—"}
      </p>
    </DeveloperShell>
  );
}

function buildRows(data) {
  if (!data) return [];
  const out = [];
  const sla = data.sla;
  if (sla) {
    out.push({ id: "uptime", name: "Platform uptime (30 days)",
      status: (sla.uptime_30d_pct ?? 0) >= 99.5 ? "green"
            : (sla.uptime_30d_pct ?? 0) >= 99   ? "yellow" : "red",
      label: `${(sla.uptime_30d_pct ?? 0).toFixed(2)}%` });
    out.push({ id: "ora_p95", name: "AUREM CTO p95 reply time",
      status: (sla.ora_p95_seconds ?? 0) <= 3 ? "green"
            : (sla.ora_p95_seconds ?? 0) <= 6 ? "yellow" : "red",
      label: `${(sla.ora_p95_seconds ?? 0).toFixed(2)}s` });
    out.push({ id: "email_delivery", name: "Email delivery (24h)",
      status: (sla.email_delivery_pct ?? 100) >= 95 ? "green"
            : (sla.email_delivery_pct ?? 100) >= 90 ? "yellow" : "red",
      label: `${(sla.email_delivery_pct ?? 100).toFixed(1)}%` });
    out.push({ id: "campaign_completion", name: "Campaign completion (24h)",
      status: (sla.campaign_completion_pct ?? 100) >= 98 ? "green"
            : (sla.campaign_completion_pct ?? 100) >= 95 ? "yellow" : "red",
      label: `${(sla.campaign_completion_pct ?? 100).toFixed(1)}%` });
  }
  if (out.length === 0) {
    out.push({ id: "api", name: "API",
      status: data.ok ? "green" : "yellow",
      label: data.ok ? "Operational" : "Unknown" });
  }
  return out;
}
