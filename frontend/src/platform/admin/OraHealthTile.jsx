import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const API = process.env.REACT_APP_BACKEND_URL;

// iter 331c Sprint 6 — ORA Health Tile
// Reads /api/admin/ora/health (7-day rolling window) + the Vanguard
// Security score from /api/admin/ora/vanguard-status. Single
// green/yellow/red dot at the top, supporting numbers below.

const STATUS_COLORS = {
  green:  { bg: "bg-emerald-500/15", text: "text-emerald-300", dot: "bg-emerald-400" },
  yellow: { bg: "bg-amber-500/15",   text: "text-amber-300",   dot: "bg-amber-400" },
  red:    { bg: "bg-rose-500/15",    text: "text-rose-300",    dot: "bg-rose-400" },
  gray:   { bg: "bg-slate-500/15",   text: "text-slate-300",   dot: "bg-slate-400" },
};

function StatusDot({ status }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.gray;
  return (
    <span
      data-testid={`ora-health-dot-${status}`}
      className={`inline-block h-2.5 w-2.5 rounded-full ${c.dot}`}
    />
  );
}

export default function OraHealthTile() {
  const [health, setHealth]     = useState(null);
  const [vanguard, setVanguard] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("admin_token");
      const h = {
        Authorization: token ? `Bearer ${token}` : "",
        "Content-Type": "application/json",
      };
      const [hr, vr] = await Promise.all([
        fetch(`${API}/api/admin/ora/health?days=7`,    { headers: h }),
        fetch(`${API}/api/admin/ora/vanguard-status`,  { headers: h }),
      ]);
      if (hr.ok)  setHealth(await hr.json());
      if (vr.ok)  setVanguard(await vr.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => clearInterval(id);
  }, []);

  const healthStatus = health?.status || "gray";
  const vanguardStatus = vanguard?.status || "gray";
  const overall = (() => {
    if (healthStatus === "red" || vanguardStatus === "red") return "red";
    if (healthStatus === "yellow" || vanguardStatus === "yellow") return "yellow";
    if (healthStatus === "green" && vanguardStatus === "green") return "green";
    return "gray";
  })();
  const overallColor = STATUS_COLORS[overall];

  return (
    <Card data-testid="ora-health-tile" className={`border-slate-700 ${overallColor.bg}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <StatusDot status={overall} />
            ORA Health (7d rolling)
          </span>
          <button
            data-testid="ora-health-refresh-btn"
            onClick={refresh}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            {loading ? "…" : "refresh"}
          </button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {error && (
          <div data-testid="ora-health-error" className="text-rose-400 text-xs">
            {error}
          </div>
        )}

        {/* Session quality */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-slate-400">
            <span>Session quality</span>
            <span data-testid="ora-health-status" className={overallColor.text}>
              {healthStatus}
            </span>
          </div>
          {health?.ok && (
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-300">
              <span>Sessions</span>
              <span data-testid="ora-health-sessions" className="text-right">
                {health.sessions_count} ({health.sessions_succeeded} ok)
              </span>
              <span>Success rate</span>
              <span data-testid="ora-health-success-rate" className="text-right">
                {(health.success_rate * 100).toFixed(0)}%
              </span>
              <span>Tool calls</span>
              <span data-testid="ora-health-tool-calls" className="text-right">
                {health.tool_calls_total}
              </span>
              <span>Tool failure rate</span>
              <span data-testid="ora-health-tool-fail-rate" className="text-right">
                {(health.failure_rate * 100).toFixed(1)}%
              </span>
              <span>Rule Zero scrubs</span>
              <span data-testid="ora-health-scrubs" className="text-right">
                {health.prose_filter_scrubs}
              </span>
              <span>Loops detected</span>
              <span data-testid="ora-health-loops" className="text-right">
                {health.loops_detected}
              </span>
              {health.avg_usd_per_session !== null && (
                <>
                  <span>Avg cost/session</span>
                  <span data-testid="ora-health-cost" className="text-right">
                    ${health.avg_usd_per_session?.toFixed?.(3) || "—"}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Vanguard Security */}
        <div className="border-t border-slate-700/50 pt-3 space-y-1">
          <div className="flex justify-between text-xs text-slate-400">
            <span>Vanguard Security</span>
            <Badge
              data-testid="ora-vanguard-status"
              className={`${STATUS_COLORS[vanguardStatus].bg} ${STATUS_COLORS[vanguardStatus].text} text-xs`}
            >
              {vanguardStatus}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-300">
            <span>Score</span>
            <span data-testid="ora-vanguard-score" className="text-right">
              {vanguard?.score ?? "—"}{vanguard?.score ? "/100" : ""}
            </span>
            {vanguard?.last_ts && (
              <>
                <span>Last scan</span>
                <span className="text-right text-slate-400 truncate">
                  {new Date(vanguard.last_ts).toLocaleString()}
                </span>
              </>
            )}
            {vanguard?.message && (
              <span className="col-span-2 text-amber-300 text-xs italic">
                {vanguard.message}
              </span>
            )}
          </div>
        </div>

        {/* Status reasons (only if not green) */}
        {health?.reasons?.length > 0 && healthStatus !== "green" && (
          <div className="border-t border-slate-700/50 pt-2 text-xs text-slate-400">
            <div className="font-medium mb-1">Why {healthStatus}:</div>
            <ul className="list-disc list-inside space-y-0.5">
              {health.reasons.map((r, i) => (
                <li key={i} data-testid={`ora-health-reason-${i}`}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
