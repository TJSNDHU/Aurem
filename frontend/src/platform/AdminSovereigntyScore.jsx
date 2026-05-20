/**
 * AdminSovereigntyScore.jsx — iter 323j
 *
 * North-Star metric page for the Full Sovereignty mission.
 * Shows a live ring score (0–100) computed from 6 weighted components:
 *   Mongo (25)  Ingress (25)  Legion LLM (20)
 *   Redis (15)  LLM Fallbacks (8)  SaaS Deps (7)
 *
 * Data source: GET /api/admin/sovereignty/score
 * Refresh: every 30 s (manual button + interval).
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, ShieldCheck, AlertTriangle, Cloud, Server } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const STATUS_STYLE = {
  sovereign: { label: "SOVEREIGN", color: "#22C55E", icon: ShieldCheck },
  hybrid:    { label: "HYBRID",    color: "#F59E0B", icon: AlertTriangle },
  degraded:  { label: "DEGRADED",  color: "#F59E0B", icon: AlertTriangle },
  cloud:     { label: "CLOUD-DEP", color: "#EF4444", icon: Cloud },
  down:      { label: "DOWN",      color: "#EF4444", icon: AlertTriangle },
  missing:   { label: "MISSING",   color: "#6B7280", icon: AlertTriangle },
  unknown:   { label: "UNKNOWN",   color: "#6B7280", icon: AlertTriangle },
  info:      { label: "INFO",      color: "#3B82F6", icon: Server },
};

const COMPONENT_LABEL = {
  mongo:         "MongoDB",
  ingress:       "Ingress / Hosting",
  legion:        "Legion LLM (Ollama)",
  redis:         "Redis",
  llm_fallbacks: "LLM Cloud Fallbacks",
  saas_deps:     "External SaaS",
};

function ScoreRing({ score, tier }) {
  const tierStyle = STATUS_STYLE[tier] || STATUS_STYLE.unknown;
  const size = 240;
  const stroke = 18;
  const radius = (size - stroke) / 2;
  const circ = 2 * Math.PI * radius;
  const dash = (Math.max(0, Math.min(100, score)) / 100) * circ;

  return (
    <div className="relative" style={{ width: size, height: size }} data-testid="sovereignty-ring">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tierStyle.color}
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={circ / 4}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 600ms ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-5xl font-light tracking-tight" style={{ color: tierStyle.color }}>
          {score}
          <span className="text-xl text-gray-500">%</span>
        </div>
        <div
          className="mt-1 text-xs uppercase tracking-[0.2em]"
          style={{ color: tierStyle.color }}
        >
          {tierStyle.label}
        </div>
      </div>
    </div>
  );
}

function ComponentCard({ id, comp, weight }) {
  const status = comp?.status || "unknown";
  const style = STATUS_STYLE[status] || STATUS_STYLE.unknown;
  const Icon = style.icon;
  const score = Number(comp?.score ?? 0);
  return (
    <div
      className="rounded-lg border bg-gray-900/40 p-4"
      style={{ borderColor: "rgba(255,255,255,0.08)" }}
      data-testid={`sovereignty-component-${id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon size={16} style={{ color: style.color }} />
          <div className="text-sm font-medium text-gray-200">
            {COMPONENT_LABEL[id] || id}
          </div>
        </div>
        <div
          className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider"
          style={{ color: style.color, border: `1px solid ${style.color}40` }}
        >
          {style.label}
        </div>
      </div>
      <div className="mt-3 flex items-baseline justify-between">
        <div className="text-2xl font-light" style={{ color: style.color }}>
          {score}
          <span className="text-xs text-gray-500">/100</span>
        </div>
        <div className="text-[11px] text-gray-500">weight {weight}</div>
      </div>
      <div className="mt-2 text-xs text-gray-400 leading-snug">
        {comp?.detail || "—"}
      </div>
      <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-gray-800/60">
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.min(100, score)}%`, backgroundColor: style.color }}
        />
      </div>
    </div>
  );
}

export default function AdminSovereigntyScore() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [lastFetched, setLastFetched] = useState(null);
  const [pulse, setPulse] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch(`${API}/api/admin/sovereignty/score`, {
        headers: { ...authHeaders() },
      });
      if (!r.ok) {
        const body = await r.text();
        throw new Error(`HTTP ${r.status} — ${body.slice(0, 200)}`);
      }
      const j = await r.json();
      setData(j);
      setLastFetched(new Date());
      // (e) visual pulse on every successful refresh
      setPulse(true);
      setTimeout(() => setPulse(false), 900);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  // (c) auto-pause when tab hidden + (f) instant refresh on focus return
  useEffect(() => {
    load();
    let id = null;
    const start = () => {
      if (id == null) id = setInterval(load, 30000);
    };
    const stop = () => {
      if (id != null) { clearInterval(id); id = null; }
    };
    const onVis = () => {
      if (document.hidden) {
        stop();
      } else {
        load();   // (f) refresh immediately when tab regains focus
        start();
      }
    };
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("focus", onVis);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("focus", onVis);
    };
  }, [load]);

  const componentEntries = useMemo(() => {
    if (!data?.components) return [];
    const order = ["mongo", "ingress", "legion", "redis", "llm_fallbacks", "saas_deps"];
    return order
      .filter((k) => data.components[k])
      .map((k) => [k, data.components[k], data.weights?.[k] || 0]);
  }, [data]);

  return (
    <div className="min-h-screen px-6 py-8 text-gray-200" data-testid="sovereignty-page">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-gray-500">
              North-Star Metric
            </div>
            <h1 className="mt-2 text-3xl font-light tracking-tight text-white">
              Full Sovereignty Score
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-gray-400">
              Live measurement of AUREM's independence from cloud SaaS. Goal:
              100 % via Hetzner VPS, local MongoDB, and Legion LLM (Ollama).
            </p>
          </div>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md border border-gray-700 bg-gray-900/60 px-3 py-2 text-xs text-gray-300 hover:border-gray-500 disabled:opacity-50"
            data-testid="sovereignty-refresh-button"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            {loading ? "Probing…" : "Refresh"}
          </button>
        </div>

        {err && (
          <div
            className="mb-6 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
            data-testid="sovereignty-error"
          >
            Failed to load: {err}
          </div>
        )}

        {/* Score + mission */}
        <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div
            className="flex items-center justify-center rounded-xl border bg-black/30 p-6 lg:col-span-1"
            style={{ borderColor: "rgba(255,255,255,0.08)" }}
          >
            <ScoreRing score={Number(data?.score ?? 0)} tier={data?.tier || "unknown"} />
          </div>
          <div
            className="rounded-xl border bg-black/30 p-6 lg:col-span-2"
            style={{ borderColor: "rgba(255,255,255,0.08)" }}
          >
            <div className="text-xs uppercase tracking-[0.2em] text-gray-500">
              Mission
            </div>
            <div className="mt-2 text-lg text-gray-200">
              {data?.mission || "Full Sovereignty — Hetzner + local Mongo + Legion LLM"}
            </div>
            <div className="mt-6 grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-light text-emerald-400">
                  {componentEntries.filter(([, c]) => c.status === "sovereign").length}
                </div>
                <div className="text-[11px] uppercase tracking-wider text-gray-500">
                  Sovereign
                </div>
              </div>
              <div>
                <div className="text-2xl font-light text-amber-400">
                  {
                    componentEntries.filter(([, c]) =>
                      ["hybrid", "degraded", "unknown"].includes(c.status),
                    ).length
                  }
                </div>
                <div className="text-[11px] uppercase tracking-wider text-gray-500">
                  Hybrid
                </div>
              </div>
              <div>
                <div className="text-2xl font-light text-red-400">
                  {
                    componentEntries.filter(([, c]) =>
                      ["cloud", "down", "missing"].includes(c.status),
                    ).length
                  }
                </div>
                <div className="text-[11px] uppercase tracking-wider text-gray-500">
                  Cloud-Dep
                </div>
              </div>
            </div>
            <div className="mt-6 flex items-center gap-2 text-[11px] text-gray-500" data-testid="sovereignty-last-probed">
              <span
                className="inline-block size-2 rounded-full"
                style={{
                  backgroundColor: pulse ? "#22C55E" : "rgba(34,197,94,0.35)",
                  boxShadow: pulse ? "0 0 8px #22C55E" : "none",
                  transition: "background-color 240ms ease, box-shadow 240ms ease",
                }}
                data-testid="sovereignty-live-pulse"
              />
              {lastFetched
                ? `Last probed ${lastFetched.toLocaleTimeString()} — auto-refresh every 30 s (pauses when tab hidden).`
                : "Probing…"}
            </div>
          </div>
        </div>

        {/* Components grid */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {componentEntries.map(([id, comp, weight]) => (
            <ComponentCard key={id} id={id} comp={comp} weight={weight} />
          ))}
        </div>
      </div>
    </div>
  );
}
