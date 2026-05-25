/**
 * /developers/dashboard — iter 332b D-19
 *
 * Founder redesign:
 *   - The 4 stat cards (tokens / GitHub / sessions / lifetime) move into
 *     a compact pill row in the top-right of the page header.
 *   - The AUREM CTO chat panel becomes the dashboard. Full height,
 *     fills the viewport (minus the developer shell + page header).
 *   - Recent activity & purchases drop to a thin strip below the chat
 *     so they don't crowd the build surface.
 */
import React, { useEffect, useState } from "react";
import { Coins, Github, Gauge, Activity } from "lucide-react";
import DeveloperShell, { devAuthHeaders, useDevMe } from "./DeveloperShell";
import DevCtoChatPanel from "./DevCtoChatPanel";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function DevDashboard() {
  const { me } = useDevMe();
  const [sessions, setSessions] = useState({ active: [], limit: 2 });
  const [liveTokens, setLiveTokens] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/developers/sessions`, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j && !cancelled) setSessions(j); })
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
      {/* Header row: title on the left, compact stat chips on the right. */}
      <div data-testid="dev-dashboard-header"
           style={{ display: "flex", alignItems: "flex-end",
                    justifyContent: "space-between", gap: 24,
                    flexWrap: "wrap", marginBottom: 14 }}>
        <div style={{ minWidth: 220 }}>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10, letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "var(--dash-orange)",
          }}>DASHBOARD</span>
          <h1 style={{
            fontFamily: "'Cinzel', serif",
            fontSize: 24, fontWeight: 600, letterSpacing: "0.01em",
            color: "var(--dash-text)", margin: "6px 0 0",
          }}>
            {me ? `Welcome back, ${(me.name || "").split(" ")[0] || "builder"}.` : "Welcome"}
          </h1>
        </div>

        {/* Compact stat chips — replaces the old 2x2 metric card grid. */}
        <div data-testid="dev-header-chips"
             style={{ display: "flex", gap: 8, flexWrap: "wrap",
                      alignItems: "center" }}>
          <StatChip testid="dashboard-token-counter" icon={Coins}
                     label="Tokens"
                     value={remaining.toLocaleString()}
                     valueColor={balanceColor} />
          <StatChip testid="active-project-card" icon={Github}
                     label="GitHub"
                     value={me?.github_username
                       ? `@${me.github_username}` : "—"} />
          <StatChip testid="rate-limit-status" icon={Gauge}
                     label="Sessions"
                     value={`${sessions.active?.length || 0}/${sessions.limit ?? 2}`} />
          <StatChip testid="dashboard-tokens-used" icon={Activity}
                     label="Lifetime"
                     value={used.toLocaleString()} />
        </div>
      </div>

      {/* Chat = the dashboard. Takes the rest of the viewport. */}
      <DevCtoChatPanel onTokensUpdate={setLiveTokens} fullScreen />
    </DeveloperShell>
  );
}

// ─── Small header chip (replaces MetricTile for the compact layout) ────
function StatChip({ testid, icon: Icon, label, value,
                    valueColor = "var(--dash-text)" }) {
  return (
    <div data-testid={testid}
         style={{ display: "inline-flex", alignItems: "center", gap: 8,
                  padding: "8px 12px",
                  border: "1px solid var(--dash-border)",
                  borderRadius: 999,
                  background: "rgba(255,255,255,0.02)",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11 }}>
      <Icon size={12} style={{ color: "var(--dash-text-muted)" }} />
      <span style={{
        letterSpacing: "0.14em", textTransform: "uppercase",
        color: "var(--dash-text-muted)", fontSize: 9,
      }}>{label}</span>
      <span style={{ color: valueColor, fontWeight: 600, fontSize: 12 }}>
        {value}
      </span>
    </div>
  );
}

// ─── Re-exports kept for backwards compat with other dev pages ────────
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
