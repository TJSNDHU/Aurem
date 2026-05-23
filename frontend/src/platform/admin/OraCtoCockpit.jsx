/**
 * OraCtoCockpit — iter 322eq
 * Read-only visibility into ORA's autonomous-CTO activity:
 *   • KPI tiles (calls 24h, success rate, override count, active tools)
 *   • Per-tool rollup (with cost overlay)
 *   • Council-override trail (loud red rows)
 *   • Live quota strip (per-tool used/cap)
 *   • Recent invocations feed (paginated)
 *
 * Route: /admin/ora-cto
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Crown, Activity, Shield, AlertTriangle, RefreshCw,
  Zap, FileWarning, Hammer, CheckCircle, Cpu,
} from "lucide-react";
import { safeFetchJson } from "../../lib/safeFetchJson";
import SlaCard from "./SlaCard";
import OutreachHealthCard from "./OutreachHealthCard";
// iter 331c Sprint 6.3 — ORA Health tile (metrics + Vanguard score)
import OraHealthTile from "./OraHealthTile";
// iter 331f — Developer Portal pulse tile
import DeveloperPortalPulseTile from "./DeveloperPortalPulseTile";
// iter 332a-2 — Specialist Cost Breakdown + Validated Solutions
import SpecialistCostBreakdownTile from "./SpecialistCostBreakdownTile";
import ValidatedSolutionsPanel from "./ValidatedSolutionsPanel";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 25000;

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const RED = "#FF7676";
const AMBER = "#FFB36B";
const GREEN = "#67E8A0";

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

export default function OraCtoCockpit() {
  const navigate = useNavigate();
  const [window, setWindow] = useState(24);
  const [summary, setSummary] = useState(null);
  const [byTool, setByTool] = useState([]);
  const [overrides, setOverrides] = useState([]);
  const [invocations, setInvocations] = useState([]);
  const [filterTool, setFilterTool] = useState("");
  const [onlyFails, setOnlyFails] = useState(false);
  const [error, setError] = useState(null);
  // iter 326c — live provider chain (DeepSeek / FreeLLMAPI / Claude / Ollama / Groq)
  const [providers, setProviders] = useState(null);
  const [providersAt, setProvidersAt] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const headers = authHeaders();
      const params = new URLSearchParams();
      if (filterTool) params.set("tool", filterTool);
      if (onlyFails) params.set("only_failures", "true");
      params.set("limit", "30");
      const [s, b, o, i] = await Promise.all([
        fetch(`${API}/api/admin/ora-cto/summary`, { headers }).then(r => r.json()),
        fetch(`${API}/api/admin/ora-cto/by-tool?window_hours=${window}`, { headers }).then(r => r.json()),
        fetch(`${API}/api/admin/ora-cto/overrides?limit=20`, { headers }).then(r => r.json()),
        fetch(`${API}/api/admin/ora-cto/invocations?${params.toString()}`, { headers }).then(r => r.json()),
      ]);
      if (s?.ok) setSummary(s);
      if (b?.ok) setByTool(b.rows || []);
      if (o?.ok) setOverrides(o.rows || []);
      if (i?.ok) setInvocations(i.rows || []);

      // iter 326c — provider chain health. Backend caches 15s so polling
      // every 25s never hammers upstreams. safeFetchJson swallows HTML/5xx
      // so a CDN wobble never crashes the panel.
      const pr = await safeFetchJson(
        `${API}/api/admin/ora/providers/health`,
        { headers },
      );
      if (pr.ok) {
        setProviders(pr.data);
        setProvidersAt(new Date());
      } else if (pr.isAuthError) {
        // silent — admin token might still be loading
      } else {
        // Keep last-known state, just timestamp the failure.
        setProvidersAt(new Date());
      }
    } catch (e) {
      setError(String(e));
    }
  }, [window, filterTool, onlyFails]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div data-testid="ora-cto-cockpit" style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Crown size={26} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, letterSpacing: 0.3 }}>
              ORA CTO Cockpit
            </h1>
          </div>
          <p style={{ color: TEXT_DIM, marginTop: 6, fontSize: 13 }}>
            Live audit trail · council overrides · per-tool cost · rolling-hour quotas
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select data-testid="window-select" value={window} onChange={(e) => setWindow(parseInt(e.target.value))}
                  style={selStyle}>
            <option value={1}>1 h</option>
            <option value={6}>6 h</option>
            <option value={24}>24 h</option>
            <option value={72}>3 d</option>
            <option value={168}>7 d</option>
          </select>
          <button data-testid="refresh-btn" onClick={load} style={btn(false)}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button data-testid="back-btn" onClick={() => navigate("/admin/boardroom")} style={btn(false)}>← Back</button>
        </div>
      </div>

      {error && (
        <div style={{ ...GLASS, padding: 12, marginBottom: 18, color: RED }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* KPI tiles */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 18 }}>
          <Tile testid="kpi-total"  icon={Activity}  label="Total invocations" value={summary.total_invocations} sub="lifetime" />
          <Tile testid="kpi-24h"    icon={Zap}       label="Last 24h"        value={summary.invocations_24h} sub={`${summary.invocations_1h} in last 1h`} />
          <Tile testid="kpi-okrate" icon={CheckCircle} label="Success rate"   value={`${summary.success_rate_24h ?? 0}%`} sub={`${summary.failures_24h} failures`}
                accent={summary.success_rate_24h < 90 ? "warn" : null} />
          <Tile testid="kpi-overrides" icon={Shield} label="Council overrides" value={summary.overrides_24h}
                sub={`${summary.overrides_total} lifetime`}
                accent={summary.overrides_24h > 0 ? "warn" : null} />
          <Tile testid="kpi-active" icon={Hammer}    label="Active tools 24h" value={summary.tools_active_24h} sub="distinct tools" />
        </div>
      )}

      {/* iter 328f — SLA + Error Budget card */}
      <SlaCard />

      {/* iter 330 — Outreach Health card (7 channels) */}
      <OutreachHealthCard />

      {/* iter 331c Sprint 6 — ORA Health + Vanguard Security tile */}
      <OraHealthTile />

      {/* iter 331f — Developer Portal pulse */}
      <div style={{ marginBottom: 18 }}>
        <DeveloperPortalPulseTile />
      </div>

      {/* iter 332a-2 — Specialist Cost + Validated Solutions */}
      <div style={{ display: "grid",
                     gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.4fr)",
                     gap: 18, marginBottom: 18 }}>
        <SpecialistCostBreakdownTile />
        <ValidatedSolutionsPanel />
      </div>

      {/* iter 326c — Provider chain health (DeepSeek → FreeLLMAPI → Claude → Ollama → Groq) */}
      <ProviderHealthPanel
        data={providers}
        checkedAt={providersAt}
        loading={!providers && !error}
      />

      {/* Quotas section intentionally removed (iter 322es). */}

      {/* By-tool grid */}
      <div style={{ ...GLASS, padding: 18, marginBottom: 18 }}>
        <SectionTitle icon={Activity} text={`Per-tool rollup · last ${window}h`} />
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 70px 70px 90px 130px",
                      gap: 6, padding: "4px 0", color: TEXT_DIM, fontSize: 11,
                      textTransform: "uppercase", borderBottom: `1px solid ${BORDER}` }}>
          <div>Tool</div><div>Calls</div><div>OK %</div><div>Avg ms</div><div>Last</div>
        </div>
        {byTool.length === 0 ? (
          <div style={{ padding: 10, color: TEXT_DIM, fontSize: 13 }}>No activity in this window.</div>
        ) : byTool.map((r, i) => (
          <div data-testid={`tool-row-${r.tool}`} key={r.tool}
               onClick={() => setFilterTool(r.tool === filterTool ? "" : r.tool)}
               style={{
                 display: "grid", gridTemplateColumns: "1.4fr 70px 70px 90px 130px",
                 gap: 6, padding: "8px 0", fontSize: 12.5, cursor: "pointer",
                 borderBottom: `1px solid rgba(212,175,55,0.06)`,
                 background: filterTool === r.tool ? "rgba(212,175,55,0.08)" : "transparent",
               }}>
            <div style={{ fontWeight: filterTool === r.tool ? 700 : 500 }}>{r.tool}</div>
            <div>{r.calls}</div>
            <div style={{ color: r.ok_pct < 90 ? RED : r.ok_pct < 99 ? AMBER : GREEN }}>
              {r.ok_pct}%
            </div>
            <div style={{ color: TEXT_DIM }}>{r.avg_latency_ms}</div>
            <div style={{ color: TEXT_DIM, fontSize: 11 }}>{(r.last_ts || "").slice(0, 19)}</div>
          </div>
        ))}
      </div>

      {/* Override trail */}
      {overrides.length > 0 && (
        <div style={{ ...GLASS, padding: 18, marginBottom: 18,
                      borderColor: "rgba(255,118,118,0.32)" }}>
          <SectionTitle icon={FileWarning} text={`Council overrides (${overrides.length}) · loud-logged`} />
          {overrides.map((o, i) => (
            <div data-testid={`override-row-${i}`} key={i}
                 style={{ padding: 12, marginBottom: 8, border: `1px solid rgba(255,118,118,0.28)`,
                          background: "rgba(255,118,118,0.06)", borderRadius: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontWeight: 600, color: RED }}>
                  {o.tool} · risk={o.risk_tier}
                </span>
                <span style={{ color: TEXT_DIM, fontSize: 11 }}>{(o.ts || "").slice(0, 19)}</span>
              </div>
              <div style={{ fontSize: 12, color: TEXT_DIM, marginBottom: 4 }}>
                {o.path && <>Path: <code style={{ color: TEXT }}>{o.path}</code></>}
                {o.command && <>Cmd: <code style={{ color: TEXT }}>{o.command} {(o.args || []).join(" ")}</code></>}
              </div>
              <div style={{ fontSize: 12.5, marginBottom: 4 }}>
                <strong style={{ color: AMBER }}>Rationale:</strong> {o.rationale}
              </div>
              <div style={{ fontSize: 12.5, marginBottom: 4 }}>
                <strong style={{ color: RED }}>Override reason:</strong> {o.override_reason}
              </div>
              <div style={{ fontSize: 11, color: TEXT_DIM, marginTop: 6 }}>
                Dissenters:{" "}
                {(o.dissenters || []).map((d, j) => (
                  <span key={j} style={{ marginRight: 8 }}>
                    <strong>{d.role}</strong> ({(d.signals || []).slice(0, 2).join(", ")})
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Invocations feed */}
      <div style={{ ...GLASS, padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <SectionTitle icon={Activity} text={`Recent invocations${filterTool ? ` · ${filterTool}` : ""}`} />
          <div style={{ display: "flex", gap: 8 }}>
            {filterTool && (
              <button data-testid="clear-filter-btn" onClick={() => setFilterTool("")} style={btn(false)}>
                clear tool filter
              </button>
            )}
            <label data-testid="only-failures-toggle"
                   style={{ display: "flex", alignItems: "center", gap: 6, color: TEXT_DIM, fontSize: 12, cursor: "pointer" }}>
              <input type="checkbox" checked={onlyFails} onChange={(e) => setOnlyFails(e.target.checked)} />
              only failures
            </label>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "140px 1fr 100px 80px 60px 70px",
                      gap: 6, padding: "4px 0", color: TEXT_DIM, fontSize: 11,
                      textTransform: "uppercase", borderBottom: `1px solid ${BORDER}` }}>
          <div>Time</div><div>Tool</div><div>Actor</div><div>Status</div><div>ms</div><div>Args</div>
        </div>
        {invocations.length === 0 ? (
          <div style={{ padding: 10, color: TEXT_DIM, fontSize: 13 }}>No invocations match this filter.</div>
        ) : invocations.map((row, i) => (
          <div data-testid={`inv-row-${i}`} key={i}
               style={{ display: "grid", gridTemplateColumns: "140px 1fr 100px 80px 60px 70px",
                        gap: 6, padding: "6px 0", fontSize: 12,
                        borderBottom: `1px solid rgba(212,175,55,0.06)` }}>
            <div style={{ color: TEXT_DIM, fontSize: 11 }}>{(row.ts || "").slice(0, 19)}</div>
            <div>{row.tool}</div>
            <div style={{ color: TEXT_DIM }}>{row.actor}</div>
            <div style={{ color: row.ok ? GREEN : RED }}>
              {row.ok ? "✓ ok" : "✗ fail"}
            </div>
            <div style={{ color: TEXT_DIM }}>{row.elapsed_ms ?? "?"}</div>
            <div style={{ color: TEXT_DIM, fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {Object.keys(row.args || {}).slice(0, 3).join(",")}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "6px 12px", fontSize: 12,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}
const selStyle = {
  background: "rgba(255,255,255,0.06)", color: TEXT,
  border: `1px solid ${BORDER}`, borderRadius: 8, padding: "6px 10px",
};

function Tile({ testid, icon: Icon, label, value, sub, accent }) {
  return (
    <div data-testid={testid} style={{ ...GLASS, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase" }}>{label}</span>
        {Icon && <Icon size={14} color={GOLD} />}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6,
                    color: accent === "warn" ? AMBER : TEXT }}>{value}</div>
      <div style={{ color: TEXT_DIM, fontSize: 11 }}>{sub}</div>
    </div>
  );
}

function SectionTitle({ icon: Icon, text }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <Icon size={14} color={GOLD} />
      <span style={{ fontWeight: 600, fontSize: 13 }}>{text}</span>
    </div>
  );
}

// iter 326c — ORA provider chain health panel.
// Renders live state of every provider in the fallback chain so the founder
// can see at a glance whether DeepSeek/FreeLLMAPI/Claude/Ollama/Groq are
// reachable, how many models each one routes, and per-provider latency.
// Backend caches the snapshot 15 s, so the 25 s panel poll never hammers
// upstreams.
const PROVIDER_LABELS = {
  deepseek:      { name: "DeepSeek V3.1",  sub: "OpenRouter · primary" },
  gemini:        { name: "Google Gemini",  sub: "AI Studio · 2.5 Flash · 1.5K req/day free" },
  nvidia:        { name: "NVIDIA NIM",     sub: "Llama 4 · 1K req/day free" },
  freellmapi:    { name: "FreeLLMAPI",     sub: "self-hosted proxy · 11-provider failover" },
  claude:        { name: "Claude",         sub: "Emergent Universal Key · fallback" },
  legion_ollama: { name: "Legion (Ollama)",sub: "sovereign · laptop · optional" },
  ollama:        { name: "Ollama",         sub: "sovereign · optional" },
  groq:          { name: "Groq",           sub: "safety net · rate-limited" },
};

function dotColor(p) {
  if (!p?.configured) return TEXT_DIM;
  if (p.ok)          return GREEN;
  return RED;
}

function statusLabel(p) {
  if (!p)              return "—";
  if (!p.configured)   return "Not configured";
  if (p.ok)            return "Online";
  return "Offline";
}

function ProviderHealthPanel({ data, checkedAt, loading }) {
  if (loading && !data) {
    return (
      <div style={{ ...GLASS, padding: 18, marginBottom: 18 }}>
        <SectionTitle icon={Cpu} text="LLM provider chain · loading…" />
      </div>
    );
  }
  if (!data) return null;

  const order = data.order || [];
  const providers = data.providers || {};
  const allOk = data.any_chat_provider_ok;
  const primaryOk = data.primary_ok;
  const cached = data.cached;

  const headerTint = allOk ? GREEN : RED;
  const headerStatus = !allOk
    ? "All chat providers offline — ORA will degrade"
    : primaryOk
      ? `Primary (${PROVIDER_LABELS[data.primary]?.name || data.primary}) online`
      : `Primary offline — fallback active`;

  return (
    <div
      data-testid="provider-health-panel"
      style={{
        ...GLASS,
        padding: 18,
        marginBottom: 18,
        borderColor: allOk ? BORDER : "rgba(255,118,118,0.32)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Cpu size={14} color={GOLD} />
          <span style={{ fontWeight: 600, fontSize: 13 }}>
            LLM provider chain · {order.length} configured
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10,
                      fontSize: 11, color: TEXT_DIM }}>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            color: headerTint, fontWeight: 600,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: 999, background: headerTint,
              boxShadow: `0 0 8px ${headerTint}`,
            }} />
            {headerStatus}
          </span>
          {checkedAt && (
            <span data-testid="provider-checked-at">
              checked {checkedAt.toLocaleTimeString()}
              {cached ? " · cached" : ""}
            </span>
          )}
        </div>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "20px 1.5fr 110px 80px 110px 1fr",
        gap: 6, padding: "4px 0", color: TEXT_DIM, fontSize: 11,
        textTransform: "uppercase", borderBottom: `1px solid ${BORDER}`,
      }}>
        <div></div><div>Provider</div><div>Status</div><div>Latency</div>
        <div>Models</div><div>Detail</div>
      </div>

      {order.map((key, i) => {
        const p = providers[key] || {};
        const label = PROVIDER_LABELS[key] || { name: key, sub: "" };
        const isPrimary = i === 0;
        return (
          <div
            key={key}
            data-testid={`provider-row-${key}`}
            style={{
              display: "grid",
              gridTemplateColumns: "20px 1.5fr 110px 80px 110px 1fr",
              gap: 6, padding: "10px 0", fontSize: 12.5,
              borderBottom: `1px solid rgba(212,175,55,0.06)`,
              background: isPrimary ? "rgba(212,175,55,0.04)" : "transparent",
            }}
          >
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{
                width: 8, height: 8, borderRadius: 999,
                background: dotColor(p),
                boxShadow: p.ok ? `0 0 8px ${dotColor(p)}` : "none",
              }} />
            </div>
            <div>
              <div style={{ fontWeight: isPrimary ? 700 : 500 }}>
                {label.name}
                {isPrimary && (
                  <span style={{
                    marginLeft: 6, fontSize: 10, fontWeight: 700,
                    color: GOLD, letterSpacing: 0.5,
                  }}>PRIMARY</span>
                )}
              </div>
              <div style={{ color: TEXT_DIM, fontSize: 11 }}>{label.sub}</div>
            </div>
            <div style={{ color: dotColor(p), fontWeight: 600 }}>
              {statusLabel(p)}
            </div>
            <div style={{ color: TEXT_DIM }}>
              {p.latency_ms != null ? `${p.latency_ms} ms` : "—"}
            </div>
            <div style={{ color: TEXT_DIM }}>
              {p.models_total != null ? p.models_total : "—"}
            </div>
            <div style={{ color: TEXT_DIM, fontSize: 11.5 }}>
              {p.reason || "—"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

