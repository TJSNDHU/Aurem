/**
 * AuditLiveDashboard — Live admin widget (iter 322ed).
 *
 * Polls GET /api/customer/audit/admin/live every 15s and surfaces:
 *   • Counts: total / today / week / failed_today
 *   • 7-day rollup: total $ waste detected, avg performance + SEO
 *   • Top recurring issues across customers (product roadmap signal)
 *   • Intelligence coverage: bins with pixel firing, merged profiles
 *   • Latest 10 audits feed
 *
 * Renders as a stand-alone page at /admin/audit-live. Linkable from
 * AdminRootCommand and any admin shell.
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2, RefreshCw, AlertTriangle, TrendingDown, Activity,
  DollarSign, Database, ExternalLink, CheckCircle, XCircle,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 15000;

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AuditLiveDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/customer/audit/admin/live`, {
        headers: authHeaders(),
      });
      if (r.status === 401 || r.status === 403) {
        setErr("Admin access required — please sign in as admin.");
        setLoading(false);
        return;
      }
      if (!r.ok) {
        setErr(`HTTP ${r.status}`);
        setLoading(false);
        return;
      }
      const j = await r.json();
      setData(j);
      setErr("");
      setLastRefresh(new Date());
    } catch (e) {
      setErr(String(e?.message || e));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !data) {
    return (
      <div style={pageStyle} data-testid="audit-live-loading">
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: TEXT_DIM }}>
          <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
          Loading live audit dashboard…
        </div>
        <style>{spinKeyframes}</style>
      </div>
    );
  }

  if (err && !data) {
    return (
      <div style={pageStyle} data-testid="audit-live-error">
        <div style={{ ...GLASS, padding: 24, maxWidth: 540 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#EF4444", marginBottom: 8 }}>
            <XCircle size={18} /> <strong>Couldn’t load audit dashboard</strong>
          </div>
          <p style={{ color: TEXT_DIM, fontSize: 13, lineHeight: 1.55 }}>{err}</p>
          <button onClick={load} data-testid="audit-live-retry-btn" style={btnGhost}>
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      </div>
    );
  }

  const c = data.counts || {};
  const r7 = data.rollup_7d || {};
  const intel = data.intelligence || {};
  const issues = data.top_issues || [];
  const latest = data.latest_audits || [];

  return (
    <div style={pageStyle} data-testid="audit-live-dashboard">
      {/* Hero */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                     marginBottom: 22, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Activity size={20} style={{ color: GOLD }} />
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: TEXT }}>
              Audit Live Dashboard
            </h1>
          </div>
          <p style={{ margin: "6px 0 0 28px", fontSize: 12, color: TEXT_DIM }}>
            Live SEO/Ads + Intelligence rollup across all customers · auto-refresh 15s
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => navigate("/admin/root-command")}
                  data-testid="audit-live-back-btn" style={btnGhost}>
            ← Root Command
          </button>
          <button onClick={load} data-testid="audit-live-refresh-btn" style={btnGold}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                     gap: 12, marginBottom: 18 }} data-testid="audit-live-kpis">
        <Kpi label="Audits Today"  value={c.today ?? 0}     accent={GOLD}    testid="kpi-audits-today" />
        <Kpi label="Audits 7d"     value={c.week ?? 0}      accent="#5B9CFF" testid="kpi-audits-week" />
        <Kpi label="Total"         value={c.total ?? 0}     accent="#22C55E" testid="kpi-audits-total" />
        <Kpi label="Failed Today"  value={c.failed_today ?? 0}
              accent={(c.failed_today ?? 0) > 0 ? "#EF4444" : TEXT_DIM} testid="kpi-failed-today" />
        <Kpi label="$ Waste Detected (7d)"
              value={`$${(r7.total_waste_usd ?? 0).toLocaleString()}`}
              accent="#FF6B00" big testid="kpi-waste-7d" />
      </div>

      {/* Main grid */}
      <div style={{ display: "grid",
                     gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)",
                     gap: 14 }}>
        {/* Score averages */}
        <Card title="Score Averages (7d)" icon={TrendingDown} testid="card-scores">
          <ScoreBar label="Performance" value={r7.avg_performance ?? 0} />
          <ScoreBar label="SEO"          value={r7.avg_seo ?? 0} />
        </Card>

        {/* Intelligence coverage */}
        <Card title="Intelligence Coverage" icon={Database} testid="card-intel">
          <Row label="BINs with pixel"     value={intel.bins_with_pixel ?? 0} />
          <Row label="BINs with signals"   value={intel.bins_with_signals ?? 0} />
          <Row label="Merged profiles"     value={intel.merged_profiles ?? 0} accent={GOLD} />
          <Row label="Raw signals"         value={intel.raw_signals ?? 0} />
        </Card>

        {/* Top issues */}
        <Card title="Top Recurring Issues (7d)" icon={AlertTriangle}
              testid="card-top-issues" wide>
          {issues.length === 0 ? (
            <div style={{ fontSize: 12, color: TEXT_DIM }}>
              No completed audits in the past 7 days.
            </div>
          ) : (
            <ul data-testid="top-issues-list" style={{ margin: 0, padding: "0 0 0 16px",
                                                       fontSize: 12, color: TEXT, lineHeight: 1.75 }}>
              {issues.slice(0, 8).map((it, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span style={{ color: TEXT }}>{it.issue}</span>
                  <span style={{ color: TEXT_DIM, marginLeft: 8, fontFamily: "monospace",
                                  fontSize: 11 }}>×{it.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Latest audits feed */}
        <Card title="Latest Audits" icon={Activity} testid="card-latest-audits" wide>
          {latest.length === 0 ? (
            <div style={{ fontSize: 12, color: TEXT_DIM }}>No audits yet.</div>
          ) : (
            <div data-testid="latest-audits-feed" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {latest.map((a, i) => (
                <div key={a.id || i} style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto auto auto auto",
                  gap: 10, alignItems: "center",
                  padding: "8px 10px", borderRadius: 8,
                  background: "rgba(255,255,255,0.02)",
                  border: `1px solid ${BORDER}`, fontSize: 12,
                }}>
                  <a href={a.url} target="_blank" rel="noopener noreferrer"
                     style={{ color: GOLD, textDecoration: "none",
                              overflow: "hidden", textOverflow: "ellipsis",
                              whiteSpace: "nowrap" }}>
                    {(a.url || "").replace(/^https?:\/\//, "").slice(0, 36)}
                    <ExternalLink size={10} style={{ marginLeft: 4, verticalAlign: "middle" }} />
                  </a>
                  <span style={{ color: TEXT_DIM, fontFamily: "monospace", fontSize: 11 }}>
                    perf {a.scores?.performance ?? "—"} · seo {a.scores?.seo ?? "—"}
                  </span>
                  <span style={{ color: "#FF6B00", fontFamily: "monospace", fontSize: 11 }}>
                    ${a.ads?.estimated_monthly_waste_usd ?? 0}/mo
                  </span>
                  <span style={{ color: a.intelligence?.available ? "#22C55E" : TEXT_DIM,
                                  fontSize: 11 }}
                        title={a.intelligence?.available
                                 ? `${a.intelligence?.pixel_visitors_today ?? 0} visits today / ${a.intelligence?.pixel_matched_contacts ?? 0} matched`
                                 : "no intelligence data"}>
                    intel: {a.intelligence?.available
                              ? `${a.intelligence?.pixel_matched_contacts ?? 0}↔${a.intelligence?.pixel_visitors_today ?? 0}`
                              : "—"}
                  </span>
                  <span style={{
                    fontSize: 10, padding: "2px 8px", borderRadius: 4,
                    background: a.status === "completed" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                    color: a.status === "completed" ? "#22C55E" : "#EF4444",
                    textTransform: "uppercase", letterSpacing: 0.5,
                  }}>{a.status}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {lastRefresh && (
        <div style={{ marginTop: 18, fontSize: 11, color: TEXT_DIM, textAlign: "center" }}
             data-testid="audit-live-last-refresh">
          Last refresh: {lastRefresh.toLocaleTimeString()} · auto-refresh every {POLL_MS / 1000}s
        </div>
      )}

      <style>{spinKeyframes}</style>
    </div>
  );
}

function Kpi({ label, value, accent, big, testid }) {
  return (
    <div data-testid={testid} style={{
      ...GLASS, padding: 14,
      display: "flex", flexDirection: "column", gap: 6,
    }}>
      <div style={{ fontSize: 10, color: TEXT_DIM, textTransform: "uppercase",
                     letterSpacing: 1.2 }}>{label}</div>
      <div style={{ fontSize: big ? 28 : 26, fontWeight: 800, color: accent,
                     fontFamily: "monospace", lineHeight: 1.1 }}>{value}</div>
    </div>
  );
}

function Card({ title, icon: Icon, children, testid, wide }) {
  return (
    <div data-testid={testid} style={{
      ...GLASS, padding: 18,
      gridColumn: wide ? "span 2" : undefined,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        {Icon && <Icon size={14} style={{ color: GOLD }} />}
        <span style={{ fontSize: 11, color: TEXT, textTransform: "uppercase",
                        letterSpacing: 1.5, fontWeight: 600 }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, accent }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between",
                   padding: "6px 0", fontSize: 12 }}>
      <span style={{ color: TEXT_DIM }}>{label}</span>
      <span style={{ color: accent || TEXT, fontFamily: "monospace", fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}

function ScoreBar({ label, value }) {
  const v = Number(value) || 0;
  const color = v >= 90 ? "#22C55E" : v >= 60 ? "#F59E0B" : "#EF4444";
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11,
                     color: TEXT_DIM, marginBottom: 4 }}>
        <span>{label}</span>
        <span style={{ color, fontFamily: "monospace", fontWeight: 700 }}>{v}/100</span>
      </div>
      <div style={{ height: 6, background: "rgba(255,255,255,0.05)", borderRadius: 999,
                     overflow: "hidden" }}>
        <div style={{ width: `${Math.min(100, Math.max(0, v))}%`,
                       height: "100%", background: color,
                       transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

const pageStyle = {
  minHeight: "100vh",
  padding: "28px 24px",
  background: "linear-gradient(180deg, #08080F 0%, #0D0D18 100%)",
  color: TEXT,
  fontFamily: "system-ui, -apple-system, sans-serif",
};
const btnGhost = {
  display: "inline-flex", alignItems: "center", gap: 6,
  padding: "8px 14px", background: "rgba(255,255,255,0.04)",
  border: `1px solid ${BORDER}`, borderRadius: 10,
  color: TEXT, fontSize: 12, cursor: "pointer",
};
const btnGold = {
  ...btnGhost,
  background: `linear-gradient(135deg, ${GOLD}, #FF6B00)`,
  color: "#08080F", fontWeight: 700, border: "none",
};
const spinKeyframes = `@keyframes spin { to { transform: rotate(360deg) } }`;
