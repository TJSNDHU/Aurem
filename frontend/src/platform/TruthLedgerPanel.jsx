/**
 * TruthLedgerPanel.jsx — iter 283 (Honesty DNA)
 *
 * Append-only truth feed. Shows real failures / glitches / insufficient
 * recoveries / persistent_reds. NO sanitization. NO success-washing.
 *
 * Data source: GET /api/admin/truth-ledger/recent?limit=20
 */
import React, { useCallback, useEffect, useState } from "react";
import { ShieldAlert, CheckCircle2, AlertOctagon, XCircle, Zap } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

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

function relTime(iso) {
  try {
    const sec = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.round(sec / 60)}m`;
    if (sec < 86400) return `${Math.round(sec / 3600)}h`;
    return `${Math.round(sec / 86400)}d`;
  } catch {
    return "?";
  }
}

const EVENT_META = {
  failure:               { color: "text-red-300",     icon: XCircle,      bg: "bg-red-950/30 border-red-800/40" },
  success:               { color: "text-emerald-300", icon: CheckCircle2, bg: "bg-emerald-950/20 border-emerald-800/30" },
  glitch:                { color: "text-amber-300",   icon: AlertOctagon, bg: "bg-amber-950/20 border-amber-800/30" },
  self_correction:       { color: "text-sky-300",     icon: Zap,          bg: "bg-sky-950/20 border-sky-800/30" },
  hallucination_caught:  { color: "text-fuchsia-300", icon: ShieldAlert,  bg: "bg-fuchsia-950/20 border-fuchsia-800/30" },
  insufficient_recovery: { color: "text-red-300",     icon: AlertOctagon, bg: "bg-red-950/30 border-red-800/40" },
  persistent_red:        { color: "text-red-300",     icon: AlertOctagon, bg: "bg-red-950/40 border-red-800/50" },
  manual_override:       { color: "text-violet-300",  icon: ShieldAlert,  bg: "bg-violet-950/20 border-violet-800/30" },
  learning_no_signal:    { color: "text-gray-400",    icon: AlertOctagon, bg: "bg-gray-900/40 border-gray-800" },
};

export default function TruthLedgerPanel() {
  const [entries, setEntries] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const q = filter === "all" ? "" : `&severity=${filter}`;
      const [r, s] = await Promise.all([
        fetch(`${API}/api/admin/truth-ledger/recent?limit=20${q}`, {
          headers: authHeaders(),
        }).then((x) => (x.ok ? x.json() : Promise.reject(x.status))),
        fetch(`${API}/api/admin/truth-ledger/stats`, {
          headers: authHeaders(),
        }).then((x) => (x.ok ? x.json() : Promise.reject(x.status))),
      ]);
      setEntries(r.entries || []);
      setStats(s);
      setErr("");
    } catch (e) {
      setErr(String(e));
    }
  }, [filter]);

  useEffect(() => {
    load();
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, [load]);

  const crit = stats?.by_severity?.critical || 0;
  const warn = stats?.by_severity?.warn || 0;

  return (
    <div
      className="rounded-lg border border-slate-700 bg-slate-950/40 p-4"
      data-testid="truth-ledger-panel"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ShieldAlert size={15} className="text-slate-300" />
          <div className="text-xs uppercase tracking-wider text-slate-200">
            Truth Ledger · Honesty DNA
          </div>
          <span
            className="rounded border border-slate-600 bg-slate-800/60 px-1.5 py-0.5 text-[9px] uppercase tracking-widest text-slate-300"
            title="Append-only. No deletions. Zabaan ka pakka."
          >
            Append-only
          </span>
        </div>
        <div className="flex gap-1" data-testid="truth-ledger-filters">
          {["all", "critical", "warn", "info"].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`px-2 py-0.5 text-[10px] uppercase tracking-widest rounded border ${
                filter === f
                  ? "bg-slate-700 border-slate-500 text-white"
                  : "bg-slate-900/60 border-slate-700 text-slate-400 hover:text-slate-200"
              }`}
              data-testid={`truth-filter-${f}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Stats strip */}
      {stats ? (
        <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
          <span>
            last {stats.window_days}d{" "}
            <span className="text-slate-200 font-mono">{stats.total}</span> entries
          </span>
          <span className="text-red-400">critical <span className="font-mono">{crit}</span></span>
          <span className="text-amber-400">warn <span className="font-mono">{warn}</span></span>
          <span className="text-slate-300">
            actors <span className="font-mono">{Object.keys(stats.by_actor || {}).length}</span>
          </span>
        </div>
      ) : null}

      {err ? (
        <div className="text-[11px] text-red-400 mb-2" data-testid="truth-ledger-error">
          {err}
        </div>
      ) : null}

      {/* Entries */}
      <div className="max-h-72 overflow-y-auto rounded border border-slate-800 bg-slate-900/30">
        {entries.length === 0 ? (
          <div
            className="p-3 text-xs text-slate-500"
            data-testid="truth-ledger-empty"
          >
            No entries match this filter yet.
          </div>
        ) : (
          entries.map((e) => {
            const m = EVENT_META[e.event_type] || EVENT_META.glitch;
            const Icon = m.icon;
            return (
              <div
                key={e.log_id}
                className={`border-b border-slate-800 px-2 py-1.5 last:border-b-0 ${m.bg}`}
                data-testid={`truth-entry-${e.log_id}`}
              >
                <div className="flex items-start gap-2">
                  <Icon size={12} className={`${m.color} mt-0.5 shrink-0`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className={`font-mono ${m.color}`}>{e.event_type}</span>
                      <span
                        className={`text-[9px] uppercase tracking-widest ${
                          e.severity === "critical"
                            ? "text-red-400"
                            : e.severity === "warn"
                              ? "text-amber-400"
                              : "text-slate-400"
                        }`}
                      >
                        {e.severity}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        · {e.actor}
                      </span>
                      <span className="ml-auto text-[10px] text-slate-500">
                        {relTime(e.ts_iso)} ago
                      </span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-slate-200 break-words">
                      {e.description}
                    </div>
                    {e.outcome ? (
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        outcome: <span className="text-slate-300">{e.outcome}</span>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
