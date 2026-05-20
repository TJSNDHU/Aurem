/**
 * OraOptimizer — iter 322ep
 * Admin UI for /api/admin/ora-optimize — LLM budget watchdog.
 * Surfaces cost rollups, cache health, and one-click cleanup actions.
 *
 * Route: /admin/ora-optimize
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2, Zap, AlertTriangle, RefreshCw, Trash2,
  TrendingUp, Database, CheckCircle, DollarSign,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 30000;

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

const SEV_COLOR = { high: "#FF7676", medium: "#FFB36B", low: "#67E8A0" };

export default function OraOptimizer() {
  const navigate = useNavigate();
  const [window, setWindow] = useState(24);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [purgeBusy, setPurgeBusy] = useState(false);
  const [purgeResult, setPurgeResult] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const r = await fetch(`${API}/api/admin/ora-optimize/scan?window_hours=${window}`,
                           { headers: authHeaders() });
      const j = await r.json();
      if (!j?.ok) {
        setError(j?.detail || "scan failed");
      } else {
        setData(j);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const purgeStale = async () => {
    if (!confirm("Drop all cache rows with 0 hits older than 24h?")) return;
    setPurgeBusy(true);
    setPurgeResult(null);
    try {
      const r = await fetch(`${API}/api/admin/ora-optimize/purge-stale`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ hits_max: 0, older_than_hours: 24 }),
      });
      const j = await r.json();
      setPurgeResult(j);
      load();
    } catch (e) {
      setPurgeResult({ ok: false, error: String(e) });
    } finally {
      setPurgeBusy(false);
    }
  };

  if (loading && !data) {
    return (
      <div style={{ minHeight: "100vh", background: "#0A0A12", display: "flex",
                    alignItems: "center", justifyContent: "center", color: TEXT_DIM }}>
        <Loader2 className="spin" size={36} color={GOLD} />
        <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const cache = data?.cache || {};
  const recs = data?.recommendations || [];
  const tasks = (data?.by_task || []).slice(0, 10);
  const prov = data?.provider_mix || [];

  return (
    <div data-testid="ora-optimizer" style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Zap size={26} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }}>ORA Optimizer</h1>
          </div>
          <p style={{ color: TEXT_DIM, fontSize: 13, marginTop: 6 }}>
            LLM budget watchdog, token spend, cache health & spend-cut recommendations.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select data-testid="window-select" value={window} onChange={(e) => setWindow(parseInt(e.target.value))}
                  style={{
                    background: "rgba(255,255,255,0.06)", color: TEXT,
                    border: `1px solid ${BORDER}`, borderRadius: 8, padding: "6px 10px",
                  }}>
            <option value={1}>last 1 h</option>
            <option value={6}>last 6 h</option>
            <option value={24}>last 24 h</option>
            <option value={72}>last 3 d</option>
            <option value={168}>last 7 d</option>
          </select>
          <button data-testid="refresh-btn" onClick={load} style={btn(false)}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button data-testid="back-btn" onClick={() => navigate("/admin/boardroom")} style={btn(false)}>← Back</button>
        </div>
      </div>

      {error && (
        <div style={{ ...GLASS, padding: 14, marginBottom: 18, color: "#FF7676" }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* KPI tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 18 }}>
        <Tile testid="kpi-calls" label="LLM calls" value={data?.total_calls ?? 0}
              sub={`window ${data?.window_hours ?? 24}h`} icon={Zap} />
        <Tile testid="kpi-cost" label="Cost" value={`$${(data?.total_cost_usd ?? 0).toFixed(4)}`}
              sub="est. via list price" icon={DollarSign} />
        <Tile testid="kpi-cache-rows" label="Cache rows" value={cache.rows ?? 0}
              sub={`${cache.hot_3plus_hits ?? 0} hot · ${cache.stale_zero_hits ?? 0} stale`} icon={Database} />
        <Tile testid="kpi-hit-ratio" label="Hit ratio" value={`${cache.approx_hit_ratio_pct ?? 0}%`}
              sub={`${cache.total_hits ?? 0} hits`} icon={TrendingUp} />
        <Tile testid="kpi-saved" label="Cache saved" value={`$${(cache.estimated_saved_usd ?? 0).toFixed(3)}`}
              sub={`${cache.avg_tokens_per_hit ?? 0} avg tok/hit`} icon={CheckCircle} />
      </div>

      {/* Recommendations */}
      <div style={{ ...GLASS, padding: 18, marginBottom: 18 }}>
        <SectionTitle icon={AlertTriangle} text={`Recommendations (${recs.length})`} />
        {recs.length === 0 ? (
          <div style={{ color: TEXT_DIM, fontSize: 13 }}>
            ✓ No optimization opportunities detected in this window.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {recs.map((r, i) => (
              <div data-testid={`rec-${r.id}`} key={i}
                   style={{ display: "flex", gap: 12, padding: 12,
                            border: `1px solid ${BORDER}`, borderRadius: 10,
                            background: "rgba(0,0,0,0.32)" }}>
                <div style={{
                  width: 6, borderRadius: 4,
                  background: SEV_COLOR[r.severity] || TEXT_DIM,
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{r.title}</div>
                  <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 2 }}>{r.action}</div>
                  <div style={{ color: GOLD, fontSize: 11, marginTop: 4 }}>Impact: {r.impact}</div>
                </div>
                {r.id === "purge_stale_cache" && (
                  <button data-testid="purge-stale-btn" disabled={purgeBusy} onClick={purgeStale} style={btn(true, purgeBusy)}>
                    {purgeBusy ? <Loader2 size={12} className="spin" /> : <Trash2 size={12} />} Purge
                  </button>
                )}
              </div>
            ))}
            {purgeResult && (
              <div style={{ marginTop: 4, color: purgeResult.ok ? "#67E8A0" : "#FF7676", fontSize: 12 }}>
                {purgeResult.ok
                  ? `✓ Deleted ${purgeResult.deleted} cache rows`
                  : `✗ ${purgeResult.error || "purge failed"}`}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Top task types */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
        <div style={{ ...GLASS, padding: 18 }}>
          <SectionTitle icon={TrendingUp} text="Top task types by tokens-out" />
          {tasks.length === 0 ? (
            <div style={{ color: TEXT_DIM, fontSize: 13 }}>No LLM calls in this window.</div>
          ) : (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "1.4fr 0.8fr 60px 80px 80px 60px 90px",
                            gap: 6, padding: "6px 0", color: TEXT_DIM, fontSize: 11,
                            textTransform: "uppercase", borderBottom: `1px solid ${BORDER}` }}>
                <div>Task</div><div>Provider</div><div>Calls</div><div>Tok in</div><div>Tok out</div><div>Fails</div><div>Est $</div>
              </div>
              {tasks.map((t, i) => (
                <div data-testid={`task-row-${i}`} key={i}
                     style={{ display: "grid", gridTemplateColumns: "1.4fr 0.8fr 60px 80px 80px 60px 90px",
                              gap: 6, padding: "8px 0", fontSize: 12.5,
                              borderBottom: `1px solid rgba(212,175,55,0.06)` }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.task_type}</div>
                  <div style={{ color: TEXT_DIM }}>{t.provider}</div>
                  <div>{t.calls}</div>
                  <div style={{ color: TEXT_DIM }}>{t.tokens_in}</div>
                  <div>{t.tokens_out}</div>
                  <div style={{ color: t.fails > 0 ? "#FF7676" : TEXT_DIM }}>{t.fails}</div>
                  <div style={{ color: GOLD }}>${(t.est_cost_usd ?? 0).toFixed(4)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ ...GLASS, padding: 18 }}>
          <SectionTitle icon={Database} text="Provider mix" />
          {prov.length === 0 ? (
            <div style={{ color: TEXT_DIM, fontSize: 13 }}>No data in this window.</div>
          ) : prov.map((p, i) => (
            <div data-testid={`prov-${p.provider}`} key={i}
                 style={{ padding: "8px 0", borderBottom: `1px solid rgba(212,175,55,0.06)` }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 600 }}>{p.provider || "?"}</span>
                <span style={{ color: GOLD, fontSize: 13 }}>${(p.est_cost_usd ?? 0).toFixed(4)}</span>
              </div>
              <div style={{ color: TEXT_DIM, fontSize: 11 }}>
                {p.calls} calls · {p.tokens_out} tok out
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "6px 12px", fontSize: 13,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}

function Tile({ testid, label, value, sub, icon: Icon }) {
  return (
    <div data-testid={testid} style={{ ...GLASS, padding: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase" }}>{label}</span>
        {Icon && <Icon size={14} color={GOLD} />}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6 }}>{value}</div>
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
