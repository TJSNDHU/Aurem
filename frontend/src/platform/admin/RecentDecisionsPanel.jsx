/**
 * RecentDecisionsPanel.jsx — iter 326cc (Phase 3 P2.4)
 *
 * Sidebar panel showing the last N ORA decisions (approved / rejected /
 * auto-executed). Useful during overnight 30-second auto-execute runs —
 * founder wakes up, glances at this panel, sees exactly what ORA did
 * while they slept. Safety feature, not a nice-to-have.
 *
 * Data: GET /api/admin/ora/decisions?days=7&limit=50
 *
 * Drop-in: <RecentDecisionsPanel /> — no props required.
 */
import React, { useCallback, useEffect, useState } from "react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const _getAdminToken = () =>
  localStorage.getItem("aurem_admin_token") ||
  sessionStorage.getItem("aurem_admin_token") ||
  "";

const _outcomeBadge = (outcome) => {
  const base =
    "inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide";
  if (outcome === "approved")
    return `${base} bg-emerald-500/15 text-emerald-300 border border-emerald-500/30`;
  if (outcome === "auto_executed")
    return `${base} bg-sky-500/15 text-sky-300 border border-sky-500/30`;
  if (outcome === "rejected")
    return `${base} bg-rose-500/15 text-rose-300 border border-rose-500/30`;
  if (outcome && outcome.endsWith("_failed"))
    return `${base} bg-amber-500/15 text-amber-300 border border-amber-500/30`;
  return `${base} bg-zinc-700/40 text-zinc-300 border border-zinc-600/40`;
};

const _fmtTs = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffSec = Math.max(0, (now - d) / 1000);
    if (diffSec < 60) return `${Math.floor(diffSec)}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  } catch (_e) {
    return iso;
  }
};

const _OUTCOMES = ["all", "approved", "auto_executed", "rejected"];

export default function RecentDecisionsPanel() {
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({});
  const [outcome, setOutcome] = useState("all");
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams({ days: String(days), limit: "50" });
      if (outcome !== "all") qs.set("outcome", outcome);
      const r = await fetch(`${API}/api/admin/ora/decisions?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${_getAdminToken()}` },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setRows(Array.isArray(data?.decisions) ? data.decisions : []);
      setCounts(data?.outcome_counts || {});
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [days, outcome]);

  useEffect(() => {
    load();
    // Light auto-refresh every 30 s so overnight runs surface fresh
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div
      className="flex flex-col h-full bg-zinc-950 border-l border-zinc-800 text-zinc-100"
      data-testid="recent-decisions-panel"
    >
      <div className="px-4 pt-4 pb-3 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-2">
          <h3
            className="text-sm font-semibold tracking-wide text-zinc-200"
            data-testid="recent-decisions-title"
          >
            Recent ORA Decisions
          </h3>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="text-[11px] text-zinc-400 hover:text-zinc-100 disabled:opacity-40 transition"
            data-testid="recent-decisions-refresh"
          >
            {loading ? "…" : "refresh"}
          </button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {_OUTCOMES.map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => setOutcome(o)}
              data-testid={`recent-decisions-filter-${o}`}
              className={
                "text-[10px] uppercase tracking-wider px-2 py-1 rounded border transition " +
                (outcome === o
                  ? "bg-zinc-100 text-zinc-900 border-zinc-100"
                  : "bg-transparent text-zinc-400 border-zinc-700 hover:border-zinc-500")
              }
            >
              {o.replace("_", " ")}
              {counts[o] != null && o !== "all" ? ` (${counts[o]})` : ""}
            </button>
          ))}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            data-testid="recent-decisions-days-select"
            className="ml-auto bg-zinc-900 text-zinc-300 text-[11px] border border-zinc-700 rounded px-1.5 py-0.5"
          >
            <option value={1}>1d</option>
            <option value={7}>7d</option>
            <option value={30}>30d</option>
            <option value={90}>90d</option>
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {error ? (
          <div
            className="text-xs text-rose-300"
            data-testid="recent-decisions-error"
          >
            Couldn't load decisions: {error}
          </div>
        ) : rows.length === 0 && !loading ? (
          <div
            className="text-xs text-zinc-500 italic"
            data-testid="recent-decisions-empty"
          >
            No decisions in the selected window. Once ORA approves or rejects
            something, it'll show up here.
          </div>
        ) : (
          rows.map((r) => (
            <div
              key={r.id}
              data-testid={`recent-decisions-row-${r.id}`}
              className="rounded border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 p-3 transition"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={_outcomeBadge(r.outcome)}>
                    {(r.outcome || "?").replace("_", " ")}
                  </span>
                  <span className="text-[11px] font-mono text-zinc-400 truncate">
                    {r.tool}
                  </span>
                </div>
                <span className="text-[10px] text-zinc-500 whitespace-nowrap">
                  {_fmtTs(r.ts)}
                </span>
              </div>
              {r.summary ? (
                <div className="text-[12px] text-zinc-200 mt-2 leading-snug line-clamp-3">
                  {r.summary}
                </div>
              ) : null}
              {r.tags && r.tags.length ? (
                <div className="flex items-center gap-1 mt-2 flex-wrap">
                  {r.tags.slice(0, 6).map((t) => (
                    <span
                      key={t}
                      className="text-[9px] uppercase tracking-wider text-zinc-400 border border-zinc-700 rounded px-1 py-[1px]"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
