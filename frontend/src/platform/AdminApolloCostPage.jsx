/**
 * AdminApolloCostPage.jsx
 *
 * Daily Apollo spend, monthly forecast, rate-limit headroom.
 * Reads /api/admin/apollo-cost/{summary,forecast}.
 */
import React, { useEffect, useState, useCallback } from "react";
import { DollarSign, TrendingUp, RefreshCw, Zap } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

function adminHeaders() {
  let token = "";
  try {
    token = sessionStorage.getItem("platform_token") ||
            localStorage.getItem("platform_token") ||
            localStorage.getItem("aurem_admin_token") ||
            localStorage.getItem("token") || "";
  } catch { /* ignore */ }
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const C = {
  ink: "#F0EDE8", dim: "#a1958a", gold: "#E8C86A",
  amber: "#FF8C35", green: "#4ade80",
  panel: "rgba(255,255,255,0.04)", border: "rgba(255,255,255,0.10)",
};
const mono = "'JetBrains Mono', monospace";


function StatCard({ label, value, sublabel, icon: Icon, tint }) {
  return (
    <div style={{ padding: 16, background: C.panel,
                  border: `1px solid ${C.border}`, borderRadius: 6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                    color: tint || C.gold, fontSize: 11,
                    fontFamily: mono, marginBottom: 8 }}>
        <Icon size={13} /> {label}
      </div>
      <div style={{ color: C.ink, fontSize: 26, fontWeight: 600,
                    fontFamily: "'Cinzel', serif" }}>
        {value}
      </div>
      {sublabel && (
        <div style={{ color: C.dim, fontSize: 10,
                       fontFamily: mono, marginTop: 4 }}>
          {sublabel}
        </div>
      )}
    </div>
  );
}


export default function AdminApolloCostPage() {
  const [summary, setSummary]     = useState(null);
  const [forecast, setForecast]   = useState(null);
  const [error, setError]         = useState("");
  const [loading, setLoading]     = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [s, f] = await Promise.all([
        fetch(`${API}/api/admin/apollo-cost/summary`,
                { headers: adminHeaders() }),
        fetch(`${API}/api/admin/apollo-cost/forecast`,
                { headers: adminHeaders() }),
      ]);
      const js = await s.json();
      const jf = await f.json();
      if (!s.ok) throw new Error(js.detail || "summary failed");
      if (!f.ok) throw new Error(jf.detail || "forecast failed");
      setSummary(js); setForecast(jf);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const daily = summary?.daily || [];
  const maxCalls = Math.max(1, ...daily.map(d => d.calls));

  return (
    <div data-testid="admin-apollo-cost-page"
         style={{ padding: "24px 28px", maxWidth: 1100,
                  margin: "0 auto", color: C.ink }}>

      <div style={{ display: "flex", alignItems: "center",
                    gap: 12, marginBottom: 18 }}>
        <DollarSign size={18} style={{ color: C.amber }} />
        <h1 style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                     color: C.gold, margin: 0 }}>
          Apollo Cost · Dashboard
        </h1>
        <button onClick={load} disabled={loading}
                data-testid="apollo-cost-refresh"
                style={{ marginLeft: "auto", background: C.panel,
                         border: `1px solid ${C.border}`,
                         color: C.dim, padding: "6px 12px",
                         borderRadius: 4, fontSize: 11,
                         cursor: loading ? "wait" : "pointer",
                         display: "inline-flex", alignItems: "center", gap: 5 }}>
          <RefreshCw size={12}
                     className={loading ? "aurem-anim-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, color: "#FF6060",
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12 }}>
          {error}
        </div>
      )}

      {summary && (
        <div style={{ display: "grid",
                       gridTemplateColumns: "repeat(4, 1fr)",
                       gap: 10, marginBottom: 18 }}>
          <StatCard label="Last 30 days · calls"
                    value={summary.total_calls.toLocaleString()}
                    sublabel={`@ $${summary.per_call_usd}/call`}
                    icon={Zap} tint={C.amber} />
          <StatCard label="Last 30 days · spend"
                    value={`$${summary.total_usd.toFixed(2)}`}
                    sublabel="USD"
                    icon={DollarSign} tint={C.gold} />
          {forecast && (
            <>
              <StatCard label="7-day daily avg"
                        value={`$${forecast.avg_daily_usd.toFixed(2)}`}
                        sublabel={`${forecast.trailing_7d_calls} calls`}
                        icon={TrendingUp} tint={C.green} />
              <StatCard label="30-day projection"
                        value={`$${forecast.projected_30d_usd.toFixed(2)}`}
                        sublabel={`limit: ${forecast.rate_limit_per_hour}/hr`}
                        icon={TrendingUp} tint={C.green} />
            </>
          )}
        </div>
      )}

      {daily.length > 0 ? (
        <div style={{ padding: 14, background: C.panel,
                       border: `1px solid ${C.border}`, borderRadius: 6 }}>
          <h2 style={{ fontSize: 12, color: C.gold,
                        fontFamily: "'Cinzel', serif",
                        margin: "0 0 12px",
                        letterSpacing: "0.05em" }}>
            Daily calls · last 30 days
          </h2>
          <div style={{ display: "flex", alignItems: "flex-end",
                         gap: 4, height: 140 }}>
            {daily.map(d => {
              const h = Math.max(2, (d.calls / maxCalls) * 130);
              return (
                <div key={d.day}
                     title={`${d.day} · ${d.calls} calls · $${d.usd}`}
                     style={{ flex: 1, height: h,
                              background: "linear-gradient(180deg, #FF8C35, #FF6B00)",
                              borderRadius: "2px 2px 0 0",
                              minWidth: 6 }} />
              );
            })}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between",
                         marginTop: 6, color: C.dim, fontSize: 10,
                         fontFamily: mono }}>
            <span>{daily[0]?.day}</span>
            <span>today</span>
          </div>
        </div>
      ) : !loading && (
        <div style={{ padding: 24, color: C.dim, fontSize: 12,
                       fontFamily: mono,
                       border: `1px dashed ${C.border}`,
                       borderRadius: 6 }}>
          No Apollo calls logged yet. Once campaigns fire, real-time
          spend will appear here.
        </div>
      )}
    </div>
  );
}
