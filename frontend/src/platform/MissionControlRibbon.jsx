/* MissionControlRibbon.jsx — Persistent War-Room Top-Nav (iter 272)
 * ===================================================================
 * Mounts on all /admin/* command pages. Shows 3 live counters
 * (Wires Broken · Stale Badges · Silent Failures), 4 tab switches,
 * and a Sync Now button that force-refreshes the backend cache.
 *
 * Design: Scientific-Luxe · glassmorphism · amber/neutral palette.
 * Polls cached /heartbeat every 10s for counters. Sync Now hits
 * POST /sync for instant feedback.
 */
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Activity, AlertTriangle, Clock, Crosshair, Database, Loader2, RefreshCw,
  Wrench, Zap,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 10_000;

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

const TABS = [
  { to: "/admin/root-command",   label: "Root Command",   Icon: Crosshair },
  { to: "/admin/pillars-map",    label: "Pillars Map",    Icon: Database },
  { to: "/admin/command-blocks", label: "Command Blocks", Icon: Activity },
  { to: "/admin/stem-fix",       label: "Stem-Fix",       Icon: Wrench },
];

function CounterPill({ label, value, tone = "neutral", Icon, testId }) {
  const tones = {
    red:     "border-red-800/60 bg-red-950/40 text-red-300",
    yellow:  "border-amber-800/60 bg-amber-950/40 text-amber-300",
    green:   "border-emerald-800/60 bg-emerald-950/30 text-emerald-300",
    neutral: "border-gray-800 bg-gray-900/50 text-gray-300",
  };
  return (
    <div
      data-testid={testId}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-md border text-[11px] font-semibold ${tones[tone]}`}
    >
      {Icon && <Icon className="size-3" />}
      <span className="opacity-70">{label}</span>
      <span className="font-mono font-bold">{value}</span>
    </div>
  );
}

export default function MissionControlRibbon() {
  const navigate = useNavigate();
  const location = useLocation();
  const [totals, setTotals] = useState(null);
  const [overall, setOverall] = useState("green");
  const [syncing, setSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/admin/pillars-map/heartbeat`, { headers: authHeaders() });
      if (!r.ok) return;
      const d = await r.json();
      setTotals(d.totals || {});
      setOverall(d.overall_status || "green");
      setLastSynced(d.generated_at || null);
    } catch {
      /* ignore */
    }
  }, []);

  const sync = useCallback(async () => {
    setSyncing(true);
    try {
      const r = await fetch(`${API}/api/admin/pillars-map/sync`, {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
      });
      if (r.ok) {
        const d = await r.json();
        setTotals(d.totals || {});
        setOverall(d.overall_status || "green");
        setLastSynced(d.generated_at || new Date().toISOString());
      }
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const wiresBroken = totals?.wires_red ?? 0;
  const stale = totals?.silent_failures ?? 0;
  const flowsRed = (totals?.flows_red ?? 0) + (totals?.flows_yellow ?? 0);

  const overallColor = {
    red:    "#EF4444",
    yellow: "#F59E0B",
    green:  "#22C55E",
  }[overall] || "#22C55E";

  const agoText = () => {
    if (!lastSynced) return "—";
    const delta = Math.max(0, Date.now() - new Date(lastSynced).getTime());
    if (delta < 60_000)  return `${Math.round(delta / 1000)}s ago`;
    if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m ago`;
    return `${Math.round(delta / 3_600_000)}h ago`;
  };

  return (
    <div
      data-testid="mission-control-ribbon"
      className="sticky top-0 z-40 border-b border-white/5 backdrop-blur-xl"
      style={{
        background: "linear-gradient(90deg, rgba(10,12,16,0.85) 0%, rgba(14,16,22,0.75) 50%, rgba(10,12,16,0.85) 100%)",
        boxShadow: `0 1px 0 ${overallColor}33, 0 0 20px ${overallColor}14`,
      }}
    >
      <div className="max-w-[1600px] mx-auto px-5 py-2 flex items-center justify-between gap-4">
        {/* Left — Brand + overall pulse */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center gap-2">
            <span
              className="size-2 rounded-full"
              style={{ background: overallColor, boxShadow: `0 0 8px ${overallColor}` }}
            />
            <span className="text-xs uppercase tracking-[0.18em] font-bold text-gray-200">
              AUREM · Mission Control
            </span>
          </div>
          <span className="text-[10px] text-gray-500 font-mono hidden md:inline-block">
            sync {agoText()}
          </span>
        </div>

        {/* Middle — Tabs */}
        <nav
          data-testid="ribbon-tabs"
          className="hidden lg:flex items-center gap-1 px-1 py-1 rounded-md bg-black/30 border border-white/5"
        >
          {TABS.map((t) => {
            const active = location.pathname.startsWith(t.to.split("?")[0]) ||
                           (t.to === "/admin/pillars-map" && location.pathname === "/admin/pillars") ||
                           (t.to === "/admin/command-blocks" && location.pathname === "/admin/blocks");
            return (
              <button
                key={t.to}
                data-testid={`ribbon-tab-${t.to.split("/").pop()}`}
                onClick={() => navigate(t.to)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                  active
                    ? "bg-amber-600/15 text-amber-200 border border-amber-500/30"
                    : "text-gray-400 hover:text-gray-100 hover:bg-white/5 border border-transparent"
                }`}
              >
                <t.Icon className="size-3" /> {t.label}
              </button>
            );
          })}
        </nav>

        {/* Right — Counters + Sync */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <CounterPill
            label="Wires"    value={wiresBroken}
            tone={wiresBroken ? "red" : "green"}
            Icon={Zap}
            testId="ribbon-counter-wires"
          />
          <CounterPill
            label="Stale"    value={stale}
            tone={stale ? "yellow" : "green"}
            Icon={Clock}
            testId="ribbon-counter-stale"
          />
          <CounterPill
            label="Flows"    value={flowsRed}
            tone={flowsRed ? (totals?.flows_red ? "red" : "yellow") : "green"}
            Icon={AlertTriangle}
            testId="ribbon-counter-flows"
          />
          <button
            data-testid="ribbon-sync-now"
            onClick={sync}
            disabled={syncing}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md border border-white/10 bg-white/5 text-[11px] font-semibold text-gray-200 hover:bg-white/10 disabled:opacity-50 transition"
            title="Force-refresh the cached pillar snapshot"
          >
            {syncing
              ? <Loader2 className="size-3 animate-spin" />
              : <RefreshCw className="size-3" />
            }
            Sync
          </button>
        </div>
      </div>
    </div>
  );
}
