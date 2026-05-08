/**
 * DeployStatusPanel.jsx — iter 280.2
 *
 * A compact admin-dashboard panel that surfaces deploy drift:
 *   • Current prod SHA (aurem.live)
 *   • Current preview SHA (this pod)
 *   • Pending commits (git log prod..preview)
 *   • Oldest commit age
 *   • Scroll-list of recent commits awaiting deploy
 *
 * If pending > 0 AND oldest_drift > threshold, the panel pulses amber with
 * a "DEPLOY NEEDED" banner directing the operator to Emergent's Deploy flow.
 *
 * Data source: GET /api/admin/deploy-drift
 * Poll rate  : 60s (same as chip)
 */
import React, { useEffect, useState } from "react";
import { GitCommit, RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react";

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

function relAge(iso) {
  try {
    const d = new Date(iso);
    const sec = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.round(sec / 60)}m`;
    if (sec < 86400) return `${Math.round(sec / 3600)}h`;
    return `${Math.round(sec / 86400)}d`;
  } catch {
    return "?";
  }
}

export default function DeployStatusPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [invalidating, setInvalidating] = useState(false);

  const load = async () => {
    try {
      const r = await fetch(`${API}/api/admin/deploy-drift`, {
        headers: authHeaders(),
        cache: "no-store",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
    } catch (_e) {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const forceRefresh = async () => {
    setInvalidating(true);
    try {
      await fetch(`${API}/api/admin/deploy-drift/invalidate`, {
        method: "POST",
        headers: authHeaders(),
      });
      await load();
    } finally {
      setInvalidating(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  if (loading && !data) {
    return (
      <div
        className="rounded-lg border border-gray-800 bg-gray-900/40 p-4"
        data-testid="deploy-status-panel-loading"
      >
        <div className="text-xs uppercase tracking-wider text-gray-500">
          Deploy Status
        </div>
        <div className="mt-2 text-sm text-gray-500">Loading…</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div
        className="rounded-lg border border-gray-800 bg-gray-900/40 p-4"
        data-testid="deploy-status-panel-error"
      >
        <div className="text-xs uppercase tracking-wider text-gray-500">
          Deploy Status
        </div>
        <div className="mt-2 text-sm text-red-400">
          Unable to reach deploy-drift endpoint (admin auth required)
        </div>
      </div>
    );
  }

  const inSync = !!data.in_sync;
  const needsDeploy = !!data.needs_deploy;
  const pending = data.pending_commits || 0;
  const recent = data.recent_commits || [];
  const borderClass = needsDeploy
    ? "border-amber-600/60 bg-amber-900/10"
    : inSync
      ? "border-emerald-600/40 bg-emerald-900/10"
      : "border-gray-700 bg-gray-900/40";

  return (
    <div
      className={`rounded-lg border p-4 ${borderClass}`}
      data-testid="deploy-status-panel"
      data-needs-deploy={needsDeploy ? "true" : "false"}
      data-in-sync={inSync ? "true" : "false"}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {inSync ? (
            <CheckCircle2 size={16} className="text-emerald-400" />
          ) : needsDeploy ? (
            <AlertTriangle size={16} className="text-amber-400" />
          ) : (
            <GitCommit size={16} className="text-gray-400" />
          )}
          <div className="text-xs uppercase tracking-wider text-gray-400">
            Deploy Status
          </div>
        </div>
        <button
          type="button"
          onClick={forceRefresh}
          disabled={invalidating}
          className="inline-flex items-center gap-1 rounded border border-gray-700 bg-gray-800/60 px-2 py-0.5 text-[10px] uppercase tracking-wider text-gray-300 hover:bg-gray-800 disabled:opacity-50"
          data-testid="deploy-status-refresh"
        >
          <RefreshCw size={10} className={invalidating ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Primary status line */}
      <div className="mt-3 text-sm">
        {inSync ? (
          <span className="text-emerald-200">
            ✓ aurem.live is serving the latest commit
          </span>
        ) : needsDeploy ? (
          <span className="text-amber-200">
            ⚠ {pending} commit{pending === 1 ? "" : "s"} pending · oldest{" "}
            {Math.round((data.oldest_drift_seconds || 0) / 60)}m behind — hit
            Deploy
          </span>
        ) : pending > 0 ? (
          <span className="text-gray-300">
            {pending} commit{pending === 1 ? "" : "s"} staged (within threshold)
          </span>
        ) : data.prod_reachable ? (
          <span className="text-gray-400">
            Build matches prod · uptime check pending
          </span>
        ) : (
          <span className="text-gray-500">
            Prod unreachable: {data.prod_error || "no details"}
          </span>
        )}
      </div>

      {/* SHA strip */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded border border-gray-800 bg-gray-900/60 p-2">
          <div className="text-[10px] uppercase tracking-wider text-gray-500">
            Prod · aurem.live
          </div>
          <div className="font-mono text-xs text-gray-200" data-testid="deploy-prod-sha">
            {data.prod_sha || "—"}
          </div>
        </div>
        <div className="rounded border border-gray-800 bg-gray-900/60 p-2">
          <div className="text-[10px] uppercase tracking-wider text-gray-500">
            Preview · this pod
          </div>
          <div className="font-mono text-xs text-gray-200" data-testid="deploy-preview-sha">
            {data.preview_sha || "—"}
          </div>
        </div>
      </div>

      {/* Pending commits list */}
      {recent.length > 0 ? (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
            Pending Commits ({recent.length})
          </div>
          <div className="max-h-28 overflow-y-auto rounded border border-gray-800 bg-gray-900/40">
            {recent.map((c) => (
              <div
                key={c.sha}
                className="flex items-center gap-2 border-b border-gray-800 px-2 py-1 last:border-b-0"
                data-testid={`deploy-commit-${c.sha}`}
              >
                <span className="font-mono text-[10px] text-gray-500">
                  {c.sha}
                </span>
                <span className="flex-1 truncate text-xs text-gray-300">
                  {c.subject}
                </span>
                <span className="text-[10px] text-gray-500">
                  {relAge(c.timestamp)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {data.cached ? (
        <div className="mt-2 text-[10px] text-gray-500">
          Cached · computed {relAge(data.computed_at)} ago
        </div>
      ) : null}
    </div>
  );
}
