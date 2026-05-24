/**
 * /developers/dashboard — Main developer hub (Auth-gated)
 * LuxeDashboardV2 av2-card primitives, edge-to-edge.
 */
import React, { useEffect, useState } from "react";
import { Coins, Github, Gauge, Activity } from "lucide-react";
import DeveloperShell, { devAuthHeaders, useDevMe } from "./DeveloperShell";
import DevCtoChatPanel from "./DevCtoChatPanel";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevDashboard() {
  const { me } = useDevMe();
  const [sessions, setSessions] = useState({ active: [], limit: 2 });
  const [purchases, setPurchases] = useState([]);
  const [liveTokens, setLiveTokens] = useState(null);
  const [activity] = useState([
    { ts: new Date().toISOString(),
      text: "Account ready. Type your first task in the AUREM CTO chat to begin." },
  ]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/developers/sessions`, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j && !cancelled) setSessions(j); })
      .catch(() => {});
    fetch(`${API}/api/developers/me/purchases`, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j && !cancelled) setPurchases(j.rows || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const remaining = liveTokens ?? me?.tokens_remaining ?? 0;
  const used      = me?.tokens_total_used ?? 0;
  const total     = remaining + used;
  const pct       = total > 0 ? (remaining / total) * 100 : 100;
  const balanceColor =
    pct < 20 ? "var(--dash-red)"
    : pct < 50 ? "var(--dash-amber)"
    : "var(--dash-green)";

  return (
    <DeveloperShell requireAuth>
      <PageHeader
        eyebrow="DASHBOARD"
        title={me ? `Welcome back, ${(me.name || "").split(" ")[0] || "builder"}.` : "Welcome"}
        sub="Live counters from your account. Refreshed each visit." />

      <div className="av2-grid-4">
        <MetricTile testid="dashboard-token-counter" icon={Coins}
                    label="Tokens remaining"
                    value={remaining.toLocaleString()}
                    valueColor={balanceColor} />
        <MetricTile testid="active-project-card" icon={Github}
                    label="GitHub linked"
                    value={me?.github_username ? `@${me.github_username}` : "Not connected"}
                    sub={me?.github_username ? "read-only" : "Connect to start"} />
        <MetricTile testid="rate-limit-status" icon={Gauge}
                    label="Active sessions"
                    value={`${sessions.active?.length || 0} / ${sessions.limit ?? 2}`} />
        <MetricTile testid="dashboard-tokens-used" icon={Activity}
                    label="Lifetime usage"
                    value={used.toLocaleString()} />
      </div>

      {/* iter 332b D-10 — AUREM CTO chat panel (the founder's #1 ask) */}
      <DevCtoChatPanel onTokensUpdate={setLiveTokens} />

      {/* Recent purchases strip — iter 331g */}
      {purchases.length > 0 && (
        <div className="av2-card" data-testid="recent-purchases-strip">
          <SectionTitle title="Recent purchases" />
          <ul style={{ listStyle: "none", padding: 0, margin: 0,
                       fontFamily: "'JetBrains Mono', monospace",
                       fontSize: 12 }}>
            {purchases.map((p, i) => (
              <li key={p.session_id || i}
                  data-testid="purchase-row"
                  style={{ display: "flex", alignItems: "center",
                            gap: 12, padding: "8px 0",
                            borderBottom: i < purchases.length - 1
                              ? "1px solid var(--dash-divider)" : "none",
                            color: "var(--dash-text)" }}>
                <span style={{ color: "var(--dash-text-muted)",
                                minWidth: 92 }}>
                  {(p.created_at || "").slice(0, 10)}
                </span>
                <span style={{ minWidth: 70,
                                textTransform: "uppercase",
                                color: "var(--dash-gold-bright)",
                                fontWeight: 500 }}>
                  {p.tier}
                </span>
                <span style={{ minWidth: 60 }}>
                  ${Number(p.amount_usd || 0).toFixed(2)}
                </span>
                <span style={{ color: p.credited ? "var(--dash-green)"
                                                  : "var(--dash-text-muted)" }}>
                  {p.credited ? "✓ credited" : p.payment_status || "pending"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recent activity feed */}
      <div className="av2-card" data-testid="recent-activity-feed">
        <SectionTitle title="Recent activity" pill="live" />
        <ul style={{ listStyle: "none", padding: 0, margin: 0,
                     fontFamily: "'JetBrains Mono', monospace",
                     fontSize: 13 }}>
          {activity.length === 0 ? (
            <li data-testid="activity-empty"
                style={{ color: "var(--dash-text-muted)" }}>
              No activity yet.
            </li>
          ) : activity.map((a, i) => (
            <li key={i} data-testid="activity-item"
                style={{ display: "flex", gap: 14, padding: "8px 0",
                          borderBottom: i < activity.length - 1
                            ? "1px solid var(--dash-divider)" : "none",
                          color: "var(--dash-text)" }}>
              <span style={{ color: "var(--dash-text-muted)",
                              minWidth: 90 }}>
                {new Date(a.ts).toLocaleTimeString()}
              </span>
              <span>{a.text}</span>
            </li>
          ))}
        </ul>
      </div>
    </DeveloperShell>
  );
}

// ─── Shared primitives (used by every dashboard-mode page) ───────────

export function PageHeader({ eyebrow, title, sub }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.2em",
        textTransform: "uppercase",
        color: "var(--dash-orange)",
      }}>{eyebrow}</span>
      <h1 style={{
        fontFamily: "'Cinzel', serif",
        fontSize: 26, fontWeight: 600, letterSpacing: "0.01em",
        color: "var(--dash-text)", margin: "8px 0 6px",
      }}>{title}</h1>
      {sub && (
        <p style={{ fontSize: 13, color: "var(--dash-text-muted)" }}>
          {sub}
        </p>
      )}
    </div>
  );
}

export function MetricTile({ testid, icon: Icon, label, value, sub,
                              valueColor = "var(--dash-text)" }) {
  return (
    <div data-testid={testid} className="av2-card">
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10, letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "var(--dash-text-muted)", marginBottom: 10,
      }}>
        <Icon size={11} /> {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em",
                     color: valueColor }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: "var(--dash-text-faint)",
                       marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

export function SectionTitle({ title, pill }) {
  return (
    <div style={{ display: "flex", alignItems: "center",
                   justifyContent: "space-between", marginBottom: 12 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600,
                    color: "var(--dash-text)" }}>{title}</h3>
      {pill && <span className="av2-pill av2-pill-live">{pill}</span>}
    </div>
  );
}
