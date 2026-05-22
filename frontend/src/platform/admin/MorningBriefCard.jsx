/**
 * MorningBriefCard.jsx — iter 326gg-UI (Phase 3 P3.2 — desktop)
 *
 * Compact desktop card surface for the morning brief. Same backend as
 * the mobile route, just a tighter rendering for the cockpit grid.
 * Backed by GET /api/admin/ora/morning-brief.
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const _severityBadge = (sev) => {
  const base =
    "text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded border";
  if (sev === "critical")
    return `${base} bg-rose-500/15 text-rose-300 border-rose-500/30`;
  if (sev === "warning")
    return `${base} bg-amber-500/15 text-amber-300 border-amber-500/30`;
  return `${base} bg-zinc-700/40 text-zinc-300 border-zinc-600/40`;
};

export default function MorningBriefCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`${API}/api/admin/ora/morning-brief`, {
        headers: { Authorization: `Bearer ${_getAdminToken()}` },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5 * 60_000);
    return () => clearInterval(t);
  }, [load]);

  const camp = data?.campaigns || {};
  const focusLeads = Array.isArray(data?.focus_leads) ? data.focus_leads : [];
  const alerts = Array.isArray(data?.alerts) ? data.alerts : [];

  return (
    <div
      className="rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-100 p-4 shadow-sm"
      data-testid="morning-brief-card"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold tracking-wide text-zinc-200">
          Morning Brief
        </h3>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          data-testid="morning-brief-refresh"
          className="text-[11px] text-zinc-400 hover:text-zinc-100 disabled:opacity-40"
        >
          {loading ? "…" : "refresh"}
        </button>
      </div>

      {error ? (
        <div className="text-xs text-rose-300" data-testid="morning-brief-error">
          Couldn't load brief: {error}
        </div>
      ) : (
        <>
          <div
            className="grid grid-cols-3 gap-3 mb-3"
            data-testid="morning-brief-kpis"
          >
            <div>
              <div className="text-xl font-semibold tabular-nums">
                {(camp.sent || 0).toLocaleString()}
              </div>
              <div className="text-[11px] text-zinc-500">outreach sent</div>
            </div>
            <div>
              <div className="text-xl font-semibold tabular-nums text-emerald-300">
                {(camp.replies || 0).toLocaleString()}
              </div>
              <div className="text-[11px] text-zinc-500">replies</div>
            </div>
            <div>
              <div className="text-xl font-semibold tabular-nums">
                {(camp.leads_blasted || 0).toLocaleString()}
              </div>
              <div className="text-[11px] text-zinc-500">leads worked</div>
            </div>
          </div>

          {alerts.length > 0 ? (
            <div
              className="border-t border-zinc-800 pt-2 mb-2"
              data-testid="morning-brief-alerts"
            >
              <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                Alerts ({alerts.length})
              </div>
              <div className="space-y-1">
                {alerts.slice(0, 3).map((a, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-[12px]"
                  >
                    <span className={_severityBadge(a.severity)}>
                      {a.severity}
                    </span>
                    <span className="text-zinc-300 truncate">{a.title}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {focusLeads.length > 0 ? (
            <div
              className="border-t border-zinc-800 pt-2"
              data-testid="morning-brief-focus"
            >
              <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                Today's focus leads ({focusLeads.length})
              </div>
              <div className="space-y-1">
                {focusLeads.slice(0, 5).map((l) => (
                  <div
                    key={l.lead_id}
                    className="text-[12px] flex items-center justify-between"
                  >
                    <span className="text-zinc-200 truncate">
                      {l.business_name || l.lead_id}
                    </span>
                    <span className="text-zinc-500 text-[10px]">
                      {l.city || ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {!data && !loading ? (
            <div className="text-xs text-zinc-500 italic">no data yet…</div>
          ) : null}
        </>
      )}
    </div>
  );
}
