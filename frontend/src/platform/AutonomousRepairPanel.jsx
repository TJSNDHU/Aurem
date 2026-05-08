/**
 * AutonomousRepairPanel.jsx — iter 281
 *
 * Live feed for the autonomous repair engine:
 *   • Status header: enabled / paused + rate capacity + interval
 *   • Trigger Now + Pause/Resume buttons
 *   • Scrollable event log (last 20) with action → outcome pills
 *
 * Data sources:
 *   GET  /api/admin/autonomous-repair/status
 *   GET  /api/admin/autonomous-repair/events?limit=20
 *   POST /api/admin/autonomous-repair/trigger | /pause | /resume
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Activity, Pause, Play, Zap, AlertOctagon, CheckCircle2, XCircle,
} from "lucide-react";

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
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
    return `${Math.round(sec / 86400)}d ago`;
  } catch {
    return "?";
  }
}

function ActionPill({ a }) {
  const ok = !!a.ok;
  const cls = ok
    ? "bg-emerald-900/30 text-emerald-200 border-emerald-700/40"
    : "bg-red-900/30 text-red-200 border-red-700/40";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-mono ${cls}`}
      title={a.signature_hash || ""}
      data-testid={`ar-action-${a.action}`}
    >
      {ok ? <CheckCircle2 size={9} /> : <XCircle size={9} />}
      {a.classification}→{a.action}
    </span>
  );
}

export default function AutonomousRepairPanel() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, e] = await Promise.all([
        fetch(`${API}/api/admin/autonomous-repair/status`, {
          headers: authHeaders(),
        }).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
        fetch(`${API}/api/admin/autonomous-repair/events?limit=20`, {
          headers: authHeaders(),
        }).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
      ]);
      setStatus(s);
      setEvents(e.events || []);
      setErr("");
    } catch (e2) {
      setErr(String(e2));
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, [load]);

  const fire = useCallback(
    async (path) => {
      setBusy(true);
      try {
        const r = await fetch(`${API}/api/admin/autonomous-repair/${path}`, {
          method: "POST",
          headers: authHeaders(),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        await load();
      } catch (e2) {
        setErr(String(e2));
      } finally {
        setBusy(false);
      }
    },
    [load]
  );

  const enabled = !!status?.enabled;
  const cap = status?.rate_capacity_remaining ?? 0;
  const maxCap = status?.max_actions_per_hour ?? 0;

  return (
    <div
      className="rounded-lg border border-violet-800/50 bg-violet-950/20 p-4"
      data-testid="autonomous-repair-panel"
      data-enabled={enabled ? "true" : "false"}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity
            size={16}
            className={enabled ? "text-violet-300" : "text-gray-500"}
          />
          <div className="text-xs uppercase tracking-wider text-gray-300">
            Autonomous Repair Engine
          </div>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${
              enabled
                ? "bg-emerald-900/40 text-emerald-200 border border-emerald-700/50"
                : "bg-amber-900/40 text-amber-200 border border-amber-700/50"
            }`}
            data-testid="ar-enabled-pill"
          >
            {enabled ? "LIVE" : "PAUSED"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => fire("trigger")}
            className="inline-flex items-center gap-1 rounded border border-violet-600/50 bg-violet-600/20 px-2 py-1 text-[10px] uppercase tracking-wider text-violet-100 hover:bg-violet-600/30 disabled:opacity-50"
            data-testid="ar-trigger-btn"
            title="Force a repair cycle now (overrides cooldown only if green)"
          >
            <Zap size={10} />
            Trigger
          </button>
          {enabled ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => fire("pause")}
              className="inline-flex items-center gap-1 rounded border border-amber-600/50 bg-amber-600/20 px-2 py-1 text-[10px] uppercase tracking-wider text-amber-100 hover:bg-amber-600/30 disabled:opacity-50"
              data-testid="ar-pause-btn"
            >
              <Pause size={10} />
              Pause
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => fire("resume")}
              className="inline-flex items-center gap-1 rounded border border-emerald-600/50 bg-emerald-600/20 px-2 py-1 text-[10px] uppercase tracking-wider text-emerald-100 hover:bg-emerald-600/30 disabled:opacity-50"
              data-testid="ar-resume-btn"
            >
              <Play size={10} />
              Resume
            </button>
          )}
        </div>
      </div>

      {/* Status strip */}
      {status ? (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-400">
          <span>
            interval{" "}
            <span className="text-gray-200 font-mono">
              {status.interval_sec}s
            </span>
          </span>
          <span>
            min-gap{" "}
            <span className="text-gray-200 font-mono">{status.min_gap_sec}s</span>
          </span>
          <span data-testid="ar-rate-capacity">
            capacity{" "}
            <span
              className={`font-mono ${cap < 3 ? "text-amber-400" : "text-gray-200"}`}
            >
              {cap}/{maxCap}
            </span>{" "}
            per hour
          </span>
        </div>
      ) : null}

      {/* Error line */}
      {err ? (
        <div className="mt-2 text-[11px] text-red-400" data-testid="ar-error">
          {err}
        </div>
      ) : null}

      {/* Event feed */}
      <div className="mt-3">
        <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
          Recent Cycles ({events.length})
        </div>
        <div className="max-h-56 overflow-y-auto rounded border border-gray-800 bg-gray-900/40">
          {events.length === 0 ? (
            <div className="p-3 text-xs text-gray-500" data-testid="ar-events-empty">
              No cycles yet — engine will trigger on sentinel red.
            </div>
          ) : (
            events.map((e, i) => (
              <div
                key={`${e.ts_iso}_${i}`}
                className="border-b border-gray-800 px-2 py-1.5 last:border-b-0"
                data-testid="ar-event-row"
              >
                <div className="flex items-center gap-2 text-[11px]">
                  {e.event === "verify" ? (
                    e.recovered ? (
                      <CheckCircle2 size={11} className="text-emerald-400" />
                    ) : (
                      <AlertOctagon size={11} className="text-amber-400" />
                    )
                  ) : (
                    <Zap size={11} className="text-violet-300" />
                  )}
                  <span className="text-gray-300 font-mono">
                    {e.event}
                  </span>
                  {e.trigger_verdict ? (
                    <span
                      className={`text-[10px] font-mono uppercase ${
                        e.trigger_verdict === "red"
                          ? "text-red-400"
                          : e.trigger_verdict === "yellow"
                            ? "text-amber-400"
                            : "text-emerald-400"
                      }`}
                    >
                      · {e.trigger_verdict}
                    </span>
                  ) : null}
                  {typeof e.errors_1h_before === "number" ? (
                    <span className="text-[10px] text-gray-500">
                      errors_before={e.errors_1h_before}
                    </span>
                  ) : null}
                  {typeof e.recovered === "boolean" ? (
                    <span
                      className={`text-[10px] ${
                        e.recovered ? "text-emerald-400" : "text-amber-400"
                      }`}
                    >
                      recovered={String(e.recovered)} (before={e.errors_before}→
                      after={e.errors_after})
                    </span>
                  ) : null}
                  <span className="ml-auto text-[10px] text-gray-500">
                    {relTime(e.ts_iso)}
                  </span>
                </div>
                {Array.isArray(e.actions) && e.actions.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {e.actions.map((a, j) => (
                      <ActionPill key={j} a={a} />
                    ))}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
