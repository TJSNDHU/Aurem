/* SystemPulseHUD.jsx — Pillar Neural Map (iter 274, upgrade from legacy)
 * =========================================================================
 * Legacy "System Pulse" screen replaced with a Pillar-Centric Neural Map.
 *
 * Kachra replaced:
 *   ✗  Static 5-card status (Active/TestMode/NoKey/Mock/Offline)
 *   ✗  Empty "Dependency Constellation" scatter
 *   ✗  Jhoota "All systems clear" forensic panel
 *   ✗  Static DB/Tier distribution numbers
 *
 * Naya:
 *   ✓  4 Pillar Power Gauges with live Triple-Pulse dots (DB · BE · FE)
 *   ✓  Neural Wiring Map — 6 inter-pillar wires with animated status lines
 *   ✓  Sentient Diagnosis sentence (auto-generated from red/yellow flows+wires)
 *   ✓  Live DB/Coll count from cached pillar snapshot
 *
 * Single data source: /api/admin/pillars-map/heartbeat (cached, <50 ms).
 * Poll interval 10 s. No independent checks — pure projection.
 *
 * Props: { token } (optional, reads from storage if not passed)
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, Database, Zap, ShieldCheck, AlertTriangle, Crosshair,
  CheckCircle, Clock, XCircle, TrendingUp, Server,
} from "lucide-react";

import "./system-pulse.css";

const API_URL = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 10_000;

function readToken(passed) {
  if (passed) return passed;
  return (
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    ""
  );
}

const STATUS_COLOR = {
  green:  "#22C55E",
  yellow: "#F59E0B",
  red:    "#EF4444",
  idle:   "#4B5563",
};

function Dot({ status, size = 8, pulse = false }) {
  const c = STATUS_COLOR[status] || "#6B7280";
  return (
    <span
      className={pulse ? "aurem-pulse-dot" : ""}
      style={{
        display: "inline-block",
        width: size, height: size, borderRadius: "50%",
        background: c,
        boxShadow: pulse ? `0 0 10px ${c}` : "none",
      }}
    />
  );
}

/* ──────────────────────────────────────────────────────────────
 *  1. Pillar Power Gauge — replaces the old 5 status cards
 * ────────────────────────────────────────────────────────────── */
function PillarGauge({ pillar }) {
  if (!pillar) return null;
  const statusColor = STATUS_COLOR[pillar.status] || "#6B7280";

  // Aggregate per-pillar Triple-Pulse = worst among its collections
  const dbs = [], bes = [], fes = [];
  for (const row of pillar.collections?.rows || []) {
    const tp = row.triple_pulse || {};
    if (tp.db)       dbs.push(tp.db.status);
    if (tp.backend)  bes.push(tp.backend.status);
    if (tp.frontend) fes.push(tp.frontend.status);
  }
  const worst = (arr) => arr.includes("red") ? "red" : arr.includes("yellow") ? "yellow" : "green";
  const db = dbs.length ? worst(dbs) : "green";
  const be = bes.length ? worst(bes) : "green";
  const fe = fes.length ? worst(fes) : "green";

  return (
    <div
      data-testid={`pillar-gauge-${pillar.key}`}
      className="relative rounded-xl border border-white/10 p-4 backdrop-blur-xl transition-all"
      style={{
        background: `linear-gradient(135deg, ${statusColor}14 0%, rgba(10,12,16,0.85) 100%)`,
        borderColor: `${statusColor}55`,
        boxShadow: pillar.status === "red" ? `0 0 30px ${statusColor}33` : "none",
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] font-bold" style={{ color: statusColor }}>
            {pillar.key.replace("_", " · ").toUpperCase()}
          </div>
          <div className="text-sm font-semibold text-gray-100 mt-0.5">{pillar.label}</div>
        </div>
        <Dot status={pillar.status} size={14} pulse={pillar.status !== "green"} />
      </div>

      {/* Triple-Pulse mini-row */}
      <div className="flex items-center justify-center gap-4 my-3 py-2 rounded bg-black/30 border border-white/5">
        {[
          { label: "DB", status: db },
          { label: "BE", status: be },
          { label: "FE", status: fe },
        ].map((p) => (
          <div
            key={p.label}
            data-testid={`pillar-pulse-${pillar.key}-${p.label.toLowerCase()}`}
            className="flex items-center gap-1.5"
          >
            <Dot status={p.status} size={7} pulse={p.status === "red"} />
            <span className="text-[9px] font-bold tracking-widest text-gray-400">{p.label}</span>
          </div>
        ))}
      </div>

      {/* Footer counts */}
      <div className="flex items-center justify-between text-[10px]">
        <span className="text-gray-500">
          workers <span className="text-gray-200 font-mono font-semibold">{pillar.workers?.live ?? 0}</span>
        </span>
        <span className="text-gray-500">
          colls <span className="text-gray-200 font-mono font-semibold">{pillar.collections?.total ?? 0}</span>
        </span>
        {pillar.collections?.silent_failures > 0 && (
          <span className="text-red-400 font-bold" title="Silent failures">
            ⚠ {pillar.collections.silent_failures}
          </span>
        )}
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
 *  2. Neural Wiring Map — replaces "Dependency Constellation"
 * ────────────────────────────────────────────────────────────── */
function NeuralWiringMap({ wires }) {
  return (
    <div
      data-testid="neural-wiring-map"
      className="rounded-xl border border-white/10 p-4 backdrop-blur-xl"
      style={{
        background: "linear-gradient(180deg, rgba(10,14,20,0.8), rgba(8,10,14,0.9))",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="size-4 text-amber-400" />
          <span className="text-[10px] tracking-[0.2em] font-bold text-white uppercase">
            Neural Wiring Map
          </span>
        </div>
        <span className="text-[10px] text-gray-500">
          {wires.length} wires · {wires.filter((w) => w.status === "red").length} broken
        </span>
      </div>

      <div className="space-y-1.5">
        {wires.length === 0 && (
          <div className="text-xs text-gray-500 py-8 text-center">No wires to display</div>
        )}
        {wires.map((w) => {
          const color = STATUS_COLOR[w.status] || "#4B5563";
          const animate = w.status === "red" || w.status === "yellow";
          return (
            <div
              key={w.id}
              data-testid={`wire-${w.id}`}
              className="flex items-center gap-3 px-3 py-1.5 rounded"
              style={{ borderLeft: `3px solid ${color}` }}
            >
              <span className="text-[9px] font-mono font-bold text-gray-400 bg-black/30 px-1.5 py-0.5 rounded">
                {w.source_pillar?.replace("_", "").slice(0, 2).toUpperCase()}
              </span>
              <div className="relative flex-1 min-w-[60px]">
                <div
                  className="h-0.5"
                  style={{
                    background: color,
                    boxShadow: animate ? `0 0 8px ${color}` : "none",
                    animation: animate ? "auremWireFlow 1.2s linear infinite" : "none",
                  }}
                />
                <div
                  className="absolute left-1/2 -translate-x-1/2 -top-0.5 size-1.5 rounded-full"
                  style={{ background: color, boxShadow: `0 0 6px ${color}` }}
                />
              </div>
              <span className="text-[9px] font-mono font-bold text-gray-400 bg-black/30 px-1.5 py-0.5 rounded">
                {w.target_pillar?.replace("_", "").slice(0, 2).toUpperCase()}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-200 font-semibold truncate">{w.label}</div>
                <div className="text-[10px] text-gray-500 truncate">{w.reason}</div>
              </div>
              <Dot status={w.status === "idle" ? "green" : w.status} size={8} pulse={w.status === "red"} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
 *  3. Sentient Diagnosis — replaces "Forensic Root-Cause"
 * ────────────────────────────────────────────────────────────── */
function SentientDiagnosis({ snapshot }) {
  const lines = useMemo(() => {
    if (!snapshot) return [];
    const out = [];

    // Silent failures
    for (const p of snapshot.pillars || []) {
      for (const row of p.collections?.rows || []) {
        if (row.silent_failure) {
          const m = /stale (\d+)m/.exec(row.triple_pulse?.db?.reason || "");
          out.push({
            severity: "red",
            text: `Pillar ${p.key.replace("_", " · ")} stale${m ? ` for ${m[1]} min` : ""}. Reason: ${row.collection} no writes within threshold.`,
          });
        }
      }
    }
    // Broken wires
    for (const w of snapshot.wires || []) {
      if (w.status === "red") {
        out.push({
          severity: "red",
          text: `Bridge broken: ${w.source_pillar} → ${w.target_pillar} (${w.label}). ${w.reason}.`,
        });
      } else if (w.status === "yellow") {
        out.push({
          severity: "yellow",
          text: `Bridge slow: ${w.label}. Lag ${w.lag_seconds}s > ${w.lag_seconds}s tolerance.`,
        });
      }
    }
    // Broken flows
    for (const f of snapshot.flows || []) {
      if (f.status === "red") {
        const tp = f.triple_pulse || {};
        const culprit = [
          tp.db?.status === "red" && `DB (${tp.db.reason})`,
          tp.backend?.status === "red" && `Backend (${tp.backend.reason})`,
          tp.frontend?.status === "red" && `Frontend (${tp.frontend.reason})`,
        ].filter(Boolean).join(" · ");
        out.push({
          severity: "red",
          text: `Interface ${f.surface}:${f.label} is RED. ${culprit || "Unknown axis"}.`,
        });
      }
    }

    return out.length === 0
      ? [{ severity: "green", text: "Every pillar healthy · every wire green · no stale collections · no flow red. System is genuinely clear." }]
      : out.slice(0, 8);
  }, [snapshot]);

  const anyRed = lines.some((l) => l.severity === "red");

  return (
    <div
      data-testid="sentient-diagnosis"
      className="rounded-xl border p-4 backdrop-blur-xl"
      style={{
        background: anyRed
          ? "linear-gradient(135deg, rgba(239,68,68,0.08), rgba(8,10,14,0.9))"
          : "linear-gradient(135deg, rgba(34,197,94,0.06), rgba(8,10,14,0.9))",
        borderColor: anyRed ? "rgba(239,68,68,0.35)" : "rgba(34,197,94,0.25)",
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        {anyRed
          ? <AlertTriangle className="size-4 text-red-400" />
          : <ShieldCheck className="size-4 text-emerald-400" />}
        <span className="text-[10px] tracking-[0.2em] font-bold text-white uppercase">
          Sentient Diagnosis
        </span>
      </div>
      <div className="space-y-2">
        {lines.map((l, i) => (
          <div
            key={i}
            data-testid={`diag-${i}`}
            className="flex items-start gap-2 text-xs text-gray-200 leading-relaxed"
          >
            <Dot status={l.severity} size={7} pulse={l.severity === "red"} />
            <span>{l.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
 *  4. Live System Vitals — replaces static DB/Tier panel
 * ────────────────────────────────────────────────────────────── */
function SystemVitals({ snapshot }) {
  const totals = snapshot?.totals || {};
  const items = [
    { label: "Collections",       value: totals.collections ?? "—",     Icon: Database },
    { label: "Silent failures",   value: totals.silent_failures ?? 0,    Icon: AlertTriangle,
      warn: (totals.silent_failures ?? 0) > 0 },
    { label: "Broken wires",      value: `${totals.wires_red ?? 0} / ${totals.wires_total ?? 0}`, Icon: Zap,
      warn: (totals.wires_red ?? 0) > 0 },
    { label: "Flows red/yellow",  value: `${totals.flows_red ?? 0} / ${totals.flows_yellow ?? 0}`, Icon: Activity,
      warn: ((totals.flows_red ?? 0) + (totals.flows_yellow ?? 0)) > 0 },
    { label: "Backend red",       value: totals.backend_red ?? 0,         Icon: Server,
      warn: (totals.backend_red ?? 0) > 0 },
  ];
  return (
    <div
      data-testid="system-vitals"
      className="rounded-xl border border-white/10 p-4 backdrop-blur-xl"
      style={{ background: "linear-gradient(180deg, rgba(10,14,20,0.8), rgba(8,10,14,0.9))" }}
    >
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="size-4 text-blue-400" />
        <span className="text-[10px] tracking-[0.2em] font-bold text-white uppercase">
          Live System Vitals
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2">
        {items.map((it) => (
          <div
            key={it.label}
            className="flex items-center justify-between px-2 py-1.5 rounded bg-black/30 border border-white/5"
          >
            <div className="flex items-center gap-1.5">
              <it.Icon className="size-3 text-gray-500" />
              <span className="text-[10px] text-gray-400">{it.label}</span>
            </div>
            <span
              className="font-mono font-bold text-sm"
              style={{ color: it.warn ? "#EF4444" : "#E5E7EB" }}
            >
              {it.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
 *  Root component (preserves legacy export signature)
 * ══════════════════════════════════════════════════════════════ */
export default function SystemPulseHUD({ token: passedToken } = {}) {
  const [snap, setSnap] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const token = readToken(passedToken);
      const r = await fetch(`${API_URL}/api/admin/pillars-map/heartbeat`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSnap(await r.json());
      setErr("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [passedToken]);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const overall = snap?.overall_status || "green";
  const overallColor = STATUS_COLOR[overall] || "#6B7280";

  return (
    <div data-testid="system-pulse-hud" className="min-h-screen bg-[#05070B] text-gray-100 pb-12">
      <style>{`
        .aurem-pulse-dot { animation: auremPulse 1.4s ease-in-out infinite; }
        @keyframes auremPulse {
          0%,100% { transform: scale(1); opacity: 1; }
          50%     { transform: scale(1.45); opacity: 0.55; }
        }
        @keyframes auremWireFlow {
          0%   { background-position: 0 0; }
          100% { background-position: 20px 0; }
        }
      `}</style>

      {/* Hero header */}
      <div
        className="border-b border-white/5 backdrop-blur-xl sticky top-0 z-30"
        style={{
          background: "linear-gradient(90deg, rgba(10,14,20,0.92), rgba(14,18,26,0.85), rgba(10,14,20,0.92))",
          boxShadow: `0 1px 0 ${overallColor}33, 0 0 22px ${overallColor}14`,
        }}
      >
        <div className="max-w-[1500px] mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Crosshair className="size-4 text-amber-400" />
              <span className="text-[10px] tracking-[0.2em] font-bold text-amber-400 uppercase">AUREM · Mission Control</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-100 mt-1">System Pulse</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              Pillar-Centric Neural Map · single-source projection · polled every {POLL_MS / 1000}s
            </p>
          </div>
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-md border"
            style={{
              background: `${overallColor}14`,
              borderColor: `${overallColor}55`,
              color: overallColor,
            }}
            data-testid="pulse-overall-status"
          >
            <Dot status={overall} size={10} pulse={overall !== "green"} />
            <span className="text-xs font-bold tracking-widest">{overall.toUpperCase()}</span>
          </div>
        </div>
      </div>

      {loading && !snap && (
        <div className="flex items-center justify-center py-20 text-gray-400 text-sm">
          Loading pillar telemetry…
        </div>
      )}

      {err && !snap && (
        <div className="max-w-4xl mx-auto mt-10 p-4 rounded-lg border border-red-900 bg-red-950/40 text-red-300 text-sm">
          {err}
        </div>
      )}

      {snap && (
        <div className="max-w-[1500px] mx-auto px-6 pt-6 space-y-6">
          {/* 4 Pillar Power Gauges */}
          <div
            data-testid="pillar-gauges-grid"
            className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
          >
            {(snap.pillars || []).map((p) => <PillarGauge key={p.key} pillar={p} />)}
          </div>

          {/* 2-column: Neural Wiring (left) · Vitals + Diagnosis (right) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <NeuralWiringMap wires={snap.wires || []} />
            </div>
            <div className="space-y-4">
              <SystemVitals snapshot={snap} />
              <SentientDiagnosis snapshot={snap} />
            </div>
          </div>

          <div className="text-[10px] text-gray-600 flex items-center gap-2 pt-2">
            <Clock className="size-3" />
            snapshot {snap.cached ? "cached" : "live"} · generated {snap.generated_at}
          </div>
        </div>
      )}
    </div>
  );
}
