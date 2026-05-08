/* AdminRootCommand.jsx — Unified Error Intelligence Hub (iter 266)
 * ==================================================================
 * Single "Root Cause" dashboard that replaces the two dead dashboards
 * (SentinelDashboard.jsx, SentinelOverwatch.jsx) and aggregates all 6
 * error-finder data sources in a single network round-trip.
 *
 *   GET /api/admin/root-command/overview  → {
 *     verdict, total_action_items,
 *     sources: { auto_fixer, sentinel_errors, shannon, system_audit,
 *                infra, migrations }
 *   }
 *
 * The page is a **navigator**, not a patch console — each tile shows the
 * headline count + file:line of the top 3 items, and a "Drill" button
 * that jumps to the existing dashboard where the operator acts on it.
 * This is the "Root Cause, not Patch Cosmetics" principle.
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Loader2, Activity, ShieldCheck, AlertTriangle, CheckCircle, Server,
  FileCode, Zap, Database, TrendingDown, ExternalLink, RefreshCw,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import MissionControlRibbon from "./MissionControlRibbon";

const API = process.env.REACT_APP_BACKEND_URL || "";

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

function Card({ title, icon: Icon, color = "#3b82f6", children, onDrill, drillLabel, testId }) {
  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-gray-800 bg-gray-900/60 p-5 hover:bg-gray-900/80 transition-colors"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="w-5 h-5" style={{ color }} />
          <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
        </div>
        {onDrill && (
          <button
            onClick={onDrill}
            data-testid={`${testId}-drill`}
            className="text-xs flex items-center gap-1 text-blue-400 hover:text-blue-300"
          >
            {drillLabel || "Open"} <ExternalLink className="w-3 h-3" />
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, highlight = false }) {
  return (
    <div className="flex items-center justify-between text-sm py-1">
      <span className="text-gray-400">{label}</span>
      <span className={highlight ? "font-bold text-amber-300" : "text-gray-100"}>
        {value}
      </span>
    </div>
  );
}

function Badge({ status }) {
  const map = {
    ok:        { color: "#22C55E", bg: "rgba(34,197,94,0.15)", label: "OK" },
    degraded:  { color: "#F59E0B", bg: "rgba(245,158,11,0.15)", label: "Degraded" },
    error:     { color: "#EF4444", bg: "rgba(239,68,68,0.15)", label: "Error" },
    healthy:   { color: "#22C55E", bg: "rgba(34,197,94,0.15)", label: "Healthy" },
    fallback_memory: { color: "#F59E0B", bg: "rgba(245,158,11,0.15)", label: "Fallback" },
  };
  const meta = map[status] || { color: "#9CA3AF", bg: "rgba(156,163,175,0.15)", label: status };
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-semibold"
      style={{ color: meta.color, backgroundColor: meta.bg }}
    >
      {meta.label}
    </span>
  );
}

export default function AdminRootCommand() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [busyError, setBusyError] = useState(null);

  const triggerStemFix = useCallback(async (errorItem) => {
    if (!errorItem) return;
    setBusyError(errorItem.id);
    try {
      const res = await fetch(`${API}/api/admin/stem-fix/generate`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          error_id: errorItem.id,
          target_file: errorItem.source_file,
          target_line: errorItem.source_line,
          error_message: errorItem.message,
          traceback: errorItem.stack || errorItem.traceback || "",
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(`Stem-Fix generation failed: ${body.detail || body.reason || res.status}`);
      } else {
        alert(`Stem-Fix generated: ${body.fix_id}. Redirecting to queue…`);
        navigate("/admin/stem-fix");
      }
    } catch (e) {
      alert(`Network error: ${e.message || e}`);
    } finally {
      setBusyError(null);
    }
  }, [navigate]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/root-command/overview`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j = await res.json();
      setData(j);
      setLastRefresh(new Date());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, [load]);

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center" data-testid="root-command-loading">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-gray-950 p-8" data-testid="root-command-error">
        <div className="max-w-2xl mx-auto rounded-lg border border-red-700 bg-red-900/30 p-6">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <h2 className="text-lg font-bold text-red-300">Failed to load Root Command</h2>
          </div>
          <p className="text-sm text-red-200/80">{error}</p>
          <button onClick={load} className="mt-4 px-3 py-1.5 bg-red-800 text-red-100 rounded hover:bg-red-700 text-sm">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const sources = data?.sources || {};
  const actionItems = data?.total_action_items || 0;
  const verdict = data?.verdict || "unknown";
  const auto = sources.auto_fixer || {};
  const errs = sources.sentinel_errors || {};
  const shannon = sources.shannon || {};
  const audit = sources.system_audit || {};
  const infra = sources.infra || {};
  const migrations = sources.migrations || {};

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100" data-testid="root-command-page">
      <MissionControlRibbon />
      <div className="max-w-7xl mx-auto p-6">
        {/* Hero */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-50 mb-1">Root Command</h1>
            <p className="text-gray-400 text-sm">
              Unified Error Intelligence — Root Causes, not Symptoms
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge status={verdict} />
            <button
              onClick={() => window.location.assign("/admin/pillars-map")}
              data-testid="root-command-go-pillars-map"
              className="flex items-center gap-2 px-3 py-1.5 bg-amber-900/30 border border-amber-700/40 text-amber-200 rounded text-sm hover:bg-amber-800/40"
              title="Open Pillars Map (Deep-Drill Diagnostic)"
            >
              <Database className="w-4 h-4" /> Pillars Map
            </button>
            <button
              onClick={load}
              data-testid="root-command-refresh"
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded text-sm hover:bg-gray-700"
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        {/* Top-line KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6" data-testid="root-command-kpis">
          <div className="rounded-lg border border-amber-700/40 bg-amber-900/20 p-4">
            <div className="text-xs text-amber-300/70 uppercase tracking-wide mb-1">Action Items</div>
            <div className="text-3xl font-bold text-amber-200" data-testid="kpi-action-items">{actionItems}</div>
          </div>
          <div className="rounded-lg border border-blue-700/40 bg-blue-900/20 p-4">
            <div className="text-xs text-blue-300/70 uppercase tracking-wide mb-1">Pending Fixes</div>
            <div className="text-3xl font-bold text-blue-200" data-testid="kpi-pending-fixes">
              {auto.by_status?.pending || 0}
            </div>
          </div>
          <div className="rounded-lg border border-red-700/40 bg-red-900/20 p-4">
            <div className="text-xs text-red-300/70 uppercase tracking-wide mb-1">Errors (24h)</div>
            <div className="text-3xl font-bold text-red-200" data-testid="kpi-errors-24h">
              {errs.errors_24h || 0}
            </div>
          </div>
          <div className="rounded-lg border border-green-700/40 bg-green-900/20 p-4">
            <div className="text-xs text-green-300/70 uppercase tracking-wide mb-1">Shannon Score</div>
            <div className="text-3xl font-bold text-green-200" data-testid="kpi-shannon-score">
              {shannon.score ?? "—"}
            </div>
          </div>
        </div>

        {/* Source cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Auto-Fixer */}
          <Card
            title="Auto-Fix Queue (Pillar 3)"
            icon={Zap}
            color="#3b82f6"
            onDrill={() => navigate("/admin/auto-fixer")}
            drillLabel="Approve Fixes"
            testId="card-auto-fixer"
          >
            <Row label="Total Fixes" value={auto.total ?? 0} />
            <Row label="Pending Review" value={auto.by_status?.pending ?? 0} highlight={!!auto.by_status?.pending} />
            <Row label="Approved" value={auto.by_status?.approved ?? 0} />
            <Row label="Deployed" value={auto.by_status?.deployed ?? 0} />
            {auto.latest_pending?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <div className="text-xs text-gray-500 mb-2">Latest Roots</div>
                {auto.latest_pending.map((f) => (
                  <div key={f.id} className="text-xs text-gray-300 flex items-center gap-2 mb-1">
                    <FileCode className="w-3 h-3 text-gray-500" />
                    <span className="truncate">{f.title || f.category}</span>
                    {f.file && (
                      <span className="text-gray-500 font-mono text-[10px] flex-shrink-0">
                        {f.file.split("/").slice(-2).join("/")}{f.line ? `:${f.line}` : ""}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Sentinel Errors */}
          <Card
            title="Client Error Stream (Sentinel)"
            icon={AlertTriangle}
            color="#EF4444"
            onDrill={() => navigate("/admin/stem-fix")}
            drillLabel="Stem-Fix Queue"
            testId="card-sentinel-errors"
          >
            <Row label="Errors (1h)" value={errs.errors_1h ?? 0} highlight={!!errs.errors_1h} />
            <Row label="Errors (24h)" value={errs.errors_24h ?? 0} />
            <Row label="AI Suggestions Pending" value={errs.suggestions_pending ?? 0} highlight={!!errs.suggestions_pending} />
            {errs.top_errors?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <div className="text-xs text-gray-500 mb-2">Top Roots by Frequency</div>
                {errs.top_errors.map((e) => (
                  <div key={e.id} className="text-xs text-gray-300 mb-2 flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <span className="text-red-300 font-semibold">×{e.count || 1}</span>{" "}
                      <span className="truncate">{e.error_type}: {(e.message || "").substring(0, 40)}</span>
                    </div>
                    <button
                      onClick={() => triggerStemFix(e)}
                      data-testid={`gen-stem-fix-${e.id}`}
                      disabled={busyError === e.id}
                      className="flex-shrink-0 px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-[10px] hover:bg-blue-800/70 disabled:opacity-50"
                    >
                      {busyError === e.id ? "…" : "Stem-Fix"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Shannon Security */}
          <Card
            title="Security Posture (Shannon)"
            icon={ShieldCheck}
            color="#22C55E"
            testId="card-shannon"
          >
            {shannon.score != null ? (
              <>
                <Row label="Score" value={`${shannon.score}/100`} />
                <Row label="Critical" value={shannon.critical_count ?? 0} highlight={!!shannon.critical_count} />
                <Row label="High" value={shannon.high_count ?? 0} />
                <Row label="Medium" value={shannon.medium_count ?? 0} />
                <Row label="Low" value={shannon.low_count ?? 0} />
              </>
            ) : (
              <p className="text-xs text-gray-500">No Shannon audit has run yet.</p>
            )}
          </Card>

          {/* System Audit */}
          <Card
            title="System Heartbeat (Monthly)"
            icon={Activity}
            color="#F59E0B"
            onDrill={() => navigate("/admin/system-audit")}
            drillLabel="Full Audit"
            testId="card-system-audit"
          >
            <Row label="Verdict" value={audit.verdict || "—"} />
            <Row label="Red Flags" value={(audit.red_flags?.length) || 0} highlight={(audit.red_flags?.length || 0) > 0} />
            {audit.red_flags?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                {audit.red_flags.slice(0, 3).map((f, i) => (
                  <div key={i} className="text-xs text-amber-200 mb-1 flex gap-2">
                    <TrendingDown className="w-3 h-3 flex-shrink-0 mt-0.5" />
                    <span>{typeof f === "string" ? f : JSON.stringify(f).substring(0, 80)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Infra */}
          <Card
            title="Infrastructure Roots"
            icon={Server}
            color="#9333EA"
            testId="card-infra"
          >
            <div className="flex items-center justify-between text-sm py-1">
              <span className="text-gray-400">MongoDB</span>
              <Badge status={infra.mongodb} />
            </div>
            <div className="flex items-center justify-between text-sm py-1">
              <span className="text-gray-400">Redis</span>
              <Badge status={infra.redis} />
            </div>
            <div className="mt-3 pt-3 border-t border-gray-800">
              <div className="text-xs text-gray-500 mb-2">Pillar Workers (total: {infra.total_schedulers ?? 0})</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {["p1_sales", "p2_billing", "p3_monitor", "p4_command_hub"].map((p) => (
                  <div key={p} className="flex justify-between">
                    <span className="text-gray-500">{p.replace(/_/g, " ")}</span>
                    <span className="text-green-400 font-mono">{infra.pillars?.[p] ?? "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Migrations */}
          <Card
            title="Migration Trail"
            icon={Database}
            color="#0EA5E9"
            testId="card-migrations"
          >
            <Row label="Recent Migrations" value={migrations.count ?? 0} />
            {migrations.recent?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                {migrations.recent.map((m, i) => (
                  <div key={i} className="text-xs text-gray-300 mb-2">
                    <CheckCircle className="w-3 h-3 text-green-400 inline-block mr-1" />
                    <span className="font-mono text-[10px]">{m._id}</span>
                    <div className="text-gray-500 text-[10px]">
                      {m.ran_at ? new Date(m.ran_at).toLocaleString() : "—"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {lastRefresh && (
          <div className="mt-6 text-xs text-gray-500 text-center" data-testid="root-command-last-refresh">
            Last refresh: {lastRefresh.toLocaleTimeString()} · auto-refresh every 20s
          </div>
        )}
      </div>
    </div>
  );
}
