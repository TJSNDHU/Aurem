/**
 * MTTHCard.jsx — iter 285.4
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Mean Time To Heal card for AdminPillarsMap cockpit.
 * Projects real data from `/api/admin/mtth/summary` — computed from
 * `autonomous_repair_events` verify outcomes (cycle_start → verified_heal).
 *
 * Shows: 24h / 7d / 30d windows with count · median · p95 · longest.
 * Verdict pill: green (<10m) · amber (<30m) · red (≥30m) · idle (no heals).
 */
import React, { useCallback, useEffect, useState } from "react";
import { Gauge, Clock, TrendingDown, Activity, RefreshCw } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const VERDICT = {
  green: { color: "#22C55E", label: "FAST-HEAL" },
  amber: { color: "#F59E0B", label: "SLOW-HEAL" },
  red:   { color: "#EF4444", label: "LAG-HEAL" },
  idle:  { color: "#6B7280", label: "IDLE · NO INCIDENTS" },
};

export default function MTTHCard() {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [tiers, setTiers] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const token = (typeof window !== "undefined" && localStorage.getItem("token")) || "";

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    try {
      const [sr, hr, tr] = await Promise.all([
        fetch(`${API}/api/admin/mtth/summary`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/admin/mtth/history?limit=15`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/admin/mtth/by-tier`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (sr.ok) setData(await sr.json());
      if (hr.ok) setHistory((await hr.json()).heals || []);
      if (tr.ok) setTiers((await tr.json()).tiers?.["24h"] || null);
      setErr("");
    } catch (e) {
      setErr(String(e).slice(0, 120));
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 25000);
    return () => clearInterval(iv);
  }, [load]);

  const verdict = data?.verdict || "idle";
  const vdata = VERDICT[verdict] || VERDICT.idle;
  const windows = data?.windows || {};
  const w24 = windows["24h"] || {};
  const w7d = windows["7d"] || {};
  const w30d = windows["30d"] || {};

  return (
    <div
      data-testid="mtth-card"
      style={{
        padding: 22,
        borderRadius: 16,
        background: "rgba(15,18,28,0.55)",
        border: `1px solid ${vdata.color}44`,
        boxShadow: `0 0 18px ${vdata.color}22`,
        backdropFilter: "blur(22px) saturate(140%)",
        marginBottom: 18,
        color: "#F4F4F4",
        fontFamily: "'Jost',sans-serif",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Gauge size={16} style={{ color: vdata.color }} />
            <h3 style={{ fontFamily: "'Cinzel',serif", fontSize: 18, margin: 0, letterSpacing: "0.03em" }}>
              MTTH · Mean Time To Heal
            </h3>
          </div>
          <p style={{ fontSize: 11, color: "#8A8070", margin: "4px 0 0 24px" }}>
            Sentinel detect → auto-repair dispatch → verified recovery. Zero mocks · live from <code style={{ color: "#D4AF37" }}>autonomous_repair_events</code>.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <span
            data-testid="mtth-verdict"
            style={{
              padding: "6px 12px", borderRadius: 20, fontSize: 11, fontWeight: 800,
              letterSpacing: "0.1em", textTransform: "uppercase",
              background: `${vdata.color}22`, color: vdata.color, border: `1px solid ${vdata.color}55`,
            }}
          >
            {vdata.label}
          </span>
          <button
            data-testid="mtth-refresh"
            onClick={load}
            disabled={busy}
            style={{
              padding: 7, borderRadius: 8,
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
              color: "#C8C8C8", cursor: busy ? "not-allowed" : "pointer",
              display: "inline-flex", alignItems: "center",
            }}
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

      {/* 3-window grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 10, marginBottom: 12 }}>
        <WindowCard label="Last 24h" w={w24} color={vdata.color} testid="mtth-24h" />
        <WindowCard label="Last 7 days" w={w7d} color="#D4AF37" testid="mtth-7d" />
        <WindowCard label="Last 30 days" w={w30d} color="#8B5CF6" testid="mtth-30d" />
      </div>

      {/* iter 285.5 — Tier breakdown (24h window) */}
      {tiers && (
        <div data-testid="mtth-tier-breakdown" style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: "#8A8070", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
            By Tier · Last 24h
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 8 }}>
            <TierPill t={tiers.tier_1} color="#22C55E" testid="mtth-tier-1" />
            <TierPill t={tiers.tier_2} color="#F59E0B" testid="mtth-tier-2" />
            <TierPill t={tiers.tier_3} color="#EF4444" testid="mtth-tier-3" />
          </div>
        </div>
      )}

      {/* Recent heals timeline */}
      {history.length > 0 && (
        <div>
          <div style={{ fontSize: 10, color: "#8A8070", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            <Activity size={11} /> Recent Heals ({history.length})
          </div>
          <div data-testid="mtth-history" style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 180, overflowY: "auto" }}>
            {history.map((h, i) => (
              <div
                key={i}
                style={{
                  display: "flex", justifyContent: "space-between", gap: 10,
                  padding: "6px 10px", borderRadius: 6,
                  background: "rgba(34,197,94,0.04)", border: "1px solid rgba(34,197,94,0.10)",
                  fontSize: 11, fontFamily: "monospace",
                }}
              >
                <span style={{ color: "#8A8070" }}>{(h.ts || "").slice(0, 19).replace("T", " ")}</span>
                <span style={{ color: "#D4AF37", flex: 1, marginLeft: 8 }}>{h.classification || "unknown"}</span>
                <span style={{ color: "#86EFAC", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <Clock size={10} /> {h.duration_human || "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data?.last_heal_at && (
        <div style={{ marginTop: 10, fontSize: 10, color: "#6B7280", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Last heal @ {(data.last_heal_at || "").slice(0, 19).replace("T", " ")} UTC
        </div>
      )}
    </div>
  );
}

function WindowCard({ label, w, color, testid }) {
  const count = w.count || 0;
  return (
    <div
      data-testid={testid}
      style={{
        padding: 12, borderRadius: 10,
        background: "rgba(255,255,255,0.03)",
        border: `1px solid ${color}33`,
      }}
    >
      <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "#8A8070" }}>{label}</div>
      {count === 0 ? (
        <div style={{ fontSize: 14, color: "#6B7280", marginTop: 6, fontFamily: "monospace" }}>No heals recorded</div>
      ) : (
        <>
          <div style={{ fontSize: 20, fontWeight: 700, color, marginTop: 4, display: "flex", alignItems: "baseline", gap: 6 }}>
            {w.median_human || "—"}
            <span style={{ fontSize: 10, color: "#8A8070", fontWeight: 400, letterSpacing: "0.1em" }}>MEDIAN</span>
          </div>
          <div style={{ fontSize: 11, color: "#8A8070", marginTop: 4, fontFamily: "monospace", display: "flex", gap: 10, flexWrap: "wrap" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}><TrendingDown size={10} />p95 {w.p95_human || "—"}</span>
            <span>· {count} heal{count === 1 ? "" : "s"}</span>
          </div>
        </>
      )}
    </div>
  );
}

function TierPill({ t, color, testid }) {
  if (!t) return null;
  const count = t.count || 0;
  return (
    <div
      data-testid={testid}
      style={{
        padding: "8px 10px", borderRadius: 8,
        background: "rgba(255,255,255,0.02)",
        border: `1px solid ${color}33`,
      }}
    >
      <div style={{ fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase", color }}>{t.name}</div>
      <div style={{ fontSize: 13, fontWeight: 700, color: count > 0 ? color : "#6B7280", marginTop: 4, fontFamily: "'Jost',sans-serif" }}>
        {count > 0 ? t.median_human : "—"}
      </div>
      <div style={{ fontSize: 10, color: "#6B7280", marginTop: 2, fontFamily: "monospace" }}>
        {count} heal{count === 1 ? "" : "s"} · p95 {count > 0 ? t.p95_human : "—"}
      </div>
    </div>
  );
}
