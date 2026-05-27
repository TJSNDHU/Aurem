/**
 * AdminIntegrations.jsx — iter D-38
 *
 * Read-only admin dashboard for every 3rd-party API in AUREM's CRM /
 * outreach / chat / payments stack. Pills (green/yellow/red/unset),
 * key-tail redacted, last-failure timestamp, "needs recharge" badge,
 * one-click "Recharge" link to the provider's billing page.
 *
 * Auto-polls every 60 s. No write paths — pure observability.
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  AlertTriangle, ShieldCheck, Loader2, RefreshCcw,
  ExternalLink, KeyRound, MessageSquare, Mail, MessageCircle,
  CreditCard, Bot, Database, Server, Github,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

// ── visual mappings ──────────────────────────────────────────────────
const GROUP_META = {
  llm:     { label: "LLM / AI",      icon: Bot,           color: "#A78BFA" },
  comms:   { label: "Comms / CRM",   icon: MessageSquare, color: "#FF8C35" },
  payment: { label: "Payments",      icon: CreditCard,    color: "#50C878" },
  data:    { label: "Data / Search", icon: Database,      color: "#60A5FA" },
  infra:   { label: "Infrastructure",icon: Server,        color: "#9CA3AF" },
};

const STATUS_META = {
  green:  { color: "#50C878", bg: "rgba(80,200,120,0.10)",
            bd: "rgba(80,200,120,0.45)", label: "Healthy" },
  yellow: { color: "#F5C150", bg: "rgba(245,193,80,0.10)",
            bd: "rgba(245,193,80,0.45)", label: "Warnings" },
  red:    { color: "#FF6060", bg: "rgba(255,96,96,0.10)",
            bd: "rgba(255,96,96,0.45)", label: "Needs recharge" },
  unset:  { color: "#6A7080", bg: "rgba(106,112,128,0.10)",
            bd: "rgba(106,112,128,0.35)", label: "Key missing" },
};

function authHeaders() {
  const t = localStorage.getItem("aurem_admin_token")
            || localStorage.getItem("dev_jwt")
            || "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function AdminIntegrations() {
  const [data, setData] = useState(null);
  const [err, setErr]   = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/admin/integrations/health`,
                              { headers: authHeaders() });
      if (r.status === 401) throw new Error("Sign in as admin to view this page.");
      if (r.status === 403) throw new Error("Admin access required.");
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail?.msg || j.detail || "load_failed");
      setData(j); setErr("");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  if (loading) {
    return (
      <div data-testid="admin-integrations-loading"
           style={{ padding: 40, textAlign: "center",
                    color: "var(--dash-text-muted)" }}>
        <Loader2 size={20} className="onb-spin" /> Loading integration health…
      </div>
    );
  }

  if (err) {
    return (
      <div data-testid="admin-integrations-error"
           style={{ padding: 24, borderRadius: 6,
                     background: "rgba(255,96,96,0.08)",
                     border: "1px solid rgba(255,96,96,0.30)",
                     color: "#FF8C8C", fontSize: 13 }}>
        <AlertTriangle size={14} style={{ verticalAlign: "middle",
                                            marginRight: 6 }} />
        {err}
      </div>
    );
  }

  const { summary, integrations } = data;
  const groups = ["llm", "comms", "payment", "data", "infra"];

  return (
    <div data-testid="admin-integrations-page"
         style={{ display: "grid", gap: 18 }}>
      {/* Summary strip */}
      <div className="av2-card">
        <div style={{ display: "flex", alignItems: "center",
                       justifyContent: "space-between", flexWrap: "wrap",
                       gap: 12 }}>
          <div>
            <div className="av2-section-label">Integration Health</div>
            <div style={{ fontSize: 12, color: "var(--dash-text-muted)",
                           marginTop: 4 }}>
              Live view of every 3rd-party API powering AUREM. Updated
              every 60 s. Reads `api_key_health_log` for the last 7 days.
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <SummaryPill label="Total"  value={summary.total}
                          color="var(--dash-text)" />
            <SummaryPill label="Healthy" value={summary.green}
                          color={STATUS_META.green.color} />
            <SummaryPill label="Warnings" value={summary.yellow}
                          color={STATUS_META.yellow.color} />
            <SummaryPill label="Recharge" value={summary.red}
                          color={STATUS_META.red.color} />
            <SummaryPill label="Unset"   value={summary.unset}
                          color={STATUS_META.unset.color} />
            <button data-testid="admin-integrations-refresh"
                    onClick={load}
                    style={{ background: "transparent",
                              border: "1px solid var(--dash-border)",
                              color: "var(--dash-text)",
                              padding: "6px 12px", fontSize: 12,
                              borderRadius: 4, cursor: "pointer",
                              display: "inline-flex", alignItems: "center",
                              gap: 6 }}>
              <RefreshCcw size={12} /> Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Groups */}
      {groups.map(g => {
        const rows = integrations.filter(i => i.group === g);
        if (rows.length === 0) return null;
        const meta = GROUP_META[g];
        const Icon = meta.icon;
        return (
          <div key={g} className="av2-card"
                data-testid={`admin-integrations-group-${g}`}>
            <div style={{ display: "flex", alignItems: "center", gap: 8,
                           marginBottom: 12,
                           paddingBottom: 10,
                           borderBottom: "1px solid var(--dash-divider)" }}>
              <Icon size={14} style={{ color: meta.color }} />
              <span style={{ fontSize: 11, letterSpacing: "0.18em",
                              textTransform: "uppercase",
                              color: "var(--dash-text-muted)" }}>
                {meta.label}
              </span>
              <span style={{ marginLeft: "auto", fontSize: 11,
                              color: "var(--dash-text-muted)" }}>
                {rows.length} {rows.length === 1 ? "integration" : "integrations"}
              </span>
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {rows.map(row => <IntegrationRow key={row.provider} row={row} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SummaryPill({ label, value, color }) {
  return (
    <div data-testid={`admin-int-summary-${label.toLowerCase()}`}
         style={{ display: "inline-flex", alignItems: "center", gap: 6,
                   padding: "6px 10px",
                   background: "rgba(255,255,255,0.04)",
                   border: "1px solid var(--dash-border)",
                   borderRadius: 4, fontSize: 12 }}>
      <span style={{ color: "var(--dash-text-muted)" }}>{label}</span>
      <span style={{ color, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function IntegrationRow({ row }) {
  const s = STATUS_META[row.status] || STATUS_META.unset;
  return (
    <div data-testid={`admin-int-row-${row.provider}`}
         style={{ display: "grid",
                   gridTemplateColumns: "1fr auto",
                   gap: 12, padding: 12,
                   borderRadius: 4,
                   border: `1px solid ${s.bd}`,
                   background: s.bg }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8,
                       flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, fontWeight: 600,
                          color: "var(--dash-text)" }}>
            {row.provider}
          </span>
          <span style={{ display: "inline-flex", alignItems: "center",
                          gap: 4, fontSize: 10,
                          padding: "2px 8px", borderRadius: 999,
                          color: s.color,
                          background: "rgba(0,0,0,0.25)",
                          border: `1px solid ${s.bd}`,
                          textTransform: "uppercase",
                          letterSpacing: "0.10em" }}>
            {row.status === "green" && <ShieldCheck size={10} />}
            {(row.status === "red" || row.status === "unset")
              && <AlertTriangle size={10} />}
            {s.label}
          </span>
          <span style={{ fontSize: 10, color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace" }}>
            {row.env_var}: <span style={{ color: row.key_present
                                            ? "var(--dash-text)"
                                            : "var(--dash-text-faint)" }}>
              {row.key_tail}
            </span>
          </span>
        </div>
        <div style={{ fontSize: 12, color: "var(--dash-text-muted)",
                       marginTop: 4 }}>
          {row.role}
        </div>
        {(row.failures_7d > 0 || row.failures_24h > 0) && (
          <div style={{ fontSize: 11, color: s.color, marginTop: 6,
                          fontFamily: "'JetBrains Mono', monospace" }}>
            {row.failures_24h} fail(s) in last 24h · {row.failures_7d} in last 7d
            {row.last_failure_at && (
              <> · last: {new Date(row.last_failure_at).toLocaleString()}</>
            )}
          </div>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {row.recharge_url && (
          <a data-testid={`admin-int-recharge-${row.provider}`}
             href={row.recharge_url} target="_blank" rel="noreferrer"
             title={row.needs_recharge
               ? "Recharge / rotate this key"
               : "Open billing console"}
             style={{ display: "inline-flex", alignItems: "center",
                       gap: 6, padding: "6px 12px",
                       fontSize: 12, fontWeight: 500,
                       background: row.needs_recharge
                         ? "rgba(255,96,96,0.12)"
                         : "rgba(255,255,255,0.04)",
                       border: `1px solid ${row.needs_recharge
                         ? "rgba(255,96,96,0.45)"
                         : "var(--dash-border)"}`,
                       color: row.needs_recharge
                         ? "#FF8C8C"
                         : "var(--dash-text)",
                       borderRadius: 4, textDecoration: "none" }}>
            <KeyRound size={12} />
            {row.needs_recharge ? "Recharge" : "Billing"}
            <ExternalLink size={10} />
          </a>
        )}
      </div>
    </div>
  );
}
