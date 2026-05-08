/**
 * TransparencyWall.jsx — iter 285.4
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Live trust metrics strip shown on AUREM SYSTEM OVERVIEW + AdminPillarsMap.
 * Projects real data from `/api/admin/transparency/wall` — no mocks.
 *
 *   • Widgets registered (audit count)
 *   • A2A pipelines green/total
 *   • Auto-heals in last 24h
 *   • Open critical alerts
 *   • Errors in last 1h
 *   • Verdict pill (green / amber / red)
 *   • Last truth-ledger failure (if any)
 */
import React, { useCallback, useEffect, useState } from "react";
import { ShieldCheck, AlertTriangle, Activity, Zap, Eye, RefreshCw } from "lucide-react";
import { emitWidgetSignal } from "../lib/emitWidgetSignal";

const API = process.env.REACT_APP_BACKEND_URL || "";

const VERDICT_COLOR = {
  green: "#22C55E",
  amber: "#F59E0B",
  red: "#EF4444",
};

const VERDICT_LABEL = {
  green: "ALL SYSTEMS TRUE-LIVE",
  amber: "DEGRADED · SELF-HEALING",
  red: "INCIDENT · LIVE-REPAIR ACTIVE",
};

export default function TransparencyWall() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const token = (typeof window !== "undefined" && (
    sessionStorage.getItem("platform_token") ||
    sessionStorage.getItem("aurem_platform_token") ||
    localStorage.getItem("aurem_token") ||
    localStorage.getItem("token")
  )) || "";

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/transparency/wall`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const j = await r.json();
        setData(j);
        setErr("");
        // Fire-and-forget A2A emit so ORA learns widget-usage patterns
        emitWidgetSignal("system_overview", "transparency_viewed", { verdict: j.verdict });
      } else {
        setErr(`HTTP ${r.status}`);
      }
    } catch (e) {
      setErr(String(e).slice(0, 120));
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, [load]);

  const verdict = data?.verdict || "green";
  const color = VERDICT_COLOR[verdict] || "#8A8070";
  const label = VERDICT_LABEL[verdict] || verdict.toUpperCase();

  const widgets = data?.widgets?.registered ?? 0;
  const a2aGreen = data?.a2a?.green ?? 0;
  const a2aTotal = data?.a2a?.total ?? 7;
  const autoHeals = data?.auto_heals_24h ?? 0;
  const openCrit = data?.open_criticals_24h ?? 0;
  const errs1h = data?.errors_1h ?? 0;
  const lastFail = data?.last_truth_failure;

  return (
    <div
      data-testid="transparency-wall"
      style={{
        padding: 22,
        borderRadius: 16,
        background: "rgba(10,12,20,0.72)",
        border: `1px solid ${color}44`,
        boxShadow: `0 0 24px ${color}22`,
        backdropFilter: "blur(22px) saturate(140%)",
        marginBottom: 18,
        color: "#F4F4F4",
        fontFamily: "'Jost',sans-serif",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Eye size={18} style={{ color }} />
          <h3 style={{
            fontFamily: "'Cinzel',serif", fontSize: 20, margin: 0, letterSpacing: "0.04em",
            background: `linear-gradient(135deg, ${color}, #FFF)`, WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent", backgroundClip: "text",
          }}>
            Transparency Wall · Truth-Sync Live
          </h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            data-testid="transparency-verdict"
            style={{
              padding: "6px 14px", borderRadius: 20, fontSize: 11, fontWeight: 800,
              letterSpacing: "0.1em", textTransform: "uppercase",
              background: `${color}22`, color, border: `1px solid ${color}66`,
            }}
          >
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: color, marginRight: 7, animation: "aurem-pulse 2s infinite" }} />
            {label}
          </span>
          <button
            data-testid="transparency-refresh"
            onClick={load}
            disabled={busy}
            style={{
              padding: 7, borderRadius: 8,
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
              color: "#C8C8C8", cursor: busy ? "not-allowed" : "pointer",
              display: "inline-flex", alignItems: "center",
            }}
            title="Refresh"
          >
            <RefreshCw size={12} className={busy ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {err && (
        <div style={{ padding: 8, borderRadius: 6, background: "rgba(239,68,68,0.14)", border: "1px solid rgba(239,68,68,0.3)", color: "#FCA5A5", fontSize: 11, marginBottom: 10 }}>
          {err}
        </div>
      )}

      {/* Live counters */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(155px,1fr))", gap: 10 }}>
        <Metric icon={<ShieldCheck size={14} />} label="Widgets Wired" value={widgets} color="#D4AF37" testid="tw-widgets" />
        <Metric icon={<Activity size={14} />} label="A2A Pipelines" value={`${a2aGreen}/${a2aTotal}`} color={a2aGreen === a2aTotal ? "#22C55E" : "#F59E0B"} testid="tw-a2a" />
        <Metric icon={<Zap size={14} />} label="Auto-Heals · 24h" value={autoHeals} color="#86EFAC" testid="tw-heals" />
        <Metric icon={<AlertTriangle size={14} />} label="Open Criticals · 24h" value={openCrit} color={openCrit > 0 ? "#EF4444" : "#6B7280"} testid="tw-criticals" />
        <Metric icon={<Activity size={14} />} label="Errors · 1h" value={errs1h} color={errs1h >= 20 ? "#EF4444" : errs1h >= 5 ? "#F59E0B" : "#6B7280"} testid="tw-errors" />
      </div>

      {lastFail && (
        <div
          data-testid="tw-last-failure"
          style={{
            marginTop: 12, padding: 10, borderRadius: 8,
            background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.20)",
            fontSize: 11, color: "#FCA5A5", fontFamily: "monospace",
          }}
        >
          <span style={{ color: "#6B7280", fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase" }}>Last Truth-Ledger Failure · </span>
          {(lastFail.ts_iso || "").slice(0, 19).replace("T", " ")} · {lastFail.actor || "?"} · {(lastFail.description || "").slice(0, 120)}
        </div>
      )}

      <div style={{ marginTop: 10, fontSize: 10, color: "#6B7280", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        Zabaan ka pakka · Zero mocks · Live data only · Updated every 20s
      </div>
    </div>
  );
}

function Metric({ icon, label, value, color, testid }) {
  return (
    <div
      data-testid={testid}
      style={{
        padding: 12, borderRadius: 10,
        background: "rgba(255,255,255,0.03)",
        border: `1px solid ${color}33`,
        display: "flex", flexDirection: "column", gap: 4,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#8A8070", fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase" }}>
        <span style={{ color }}>{icon}</span>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: "'Jost',sans-serif" }}>{value}</div>
    </div>
  );
}
