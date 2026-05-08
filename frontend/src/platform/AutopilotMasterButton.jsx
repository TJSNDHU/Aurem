/**
 * AutopilotMasterButton.jsx — iter 285.8
 * ═══════════════════════════════════════════════════════════════════════
 *
 * One-click "activate tomorrow 08:00 full-auto-blast" button with a live
 * status strip. Mounted on AdminPillarsMap cockpit.
 *
 * Projects real data from:
 *   GET  /api/admin/autopilot/status
 *   GET  /api/admin/autopilot/live-log
 *   POST /api/admin/autopilot/activate
 *   POST /api/admin/autopilot/pause
 *   POST /api/admin/autopilot/fire-now
 *
 * Zero mocks — every phase result is from the real cycle run.
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Rocket, Pause, Play, Clock, CheckCircle2, AlertTriangle,
  RefreshCw, Zap, Radar, Send, FileText,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const AGENT_ICONS = {
  scout:  Radar,
  hunt:   Zap,
  blast:  Send,
  report: FileText,
};

const AGENT_LABELS = {
  scout:  "Scout · Find Leads",
  hunt:   "Hunt · Verify",
  blast:  "Blast · 4-Channel Send",
  report: "Report · Morning Brief",
};

export default function AutopilotMasterButton() {
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [err, setErr] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [fireTime, setFireTime] = useState("08:00");

  const token = (typeof window !== "undefined" && (
    localStorage.getItem("token") ||
    localStorage.getItem("aurem_token") ||
    sessionStorage.getItem("platform_token") ||
    sessionStorage.getItem("aurem_platform_token")
  )) || "";

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [sr, lr] = await Promise.all([
        fetch(`${API}/api/admin/autopilot/status`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/admin/autopilot/live-log?limit=10`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (sr.ok) setStatus(await sr.json());
      if (lr.ok) setLog((await lr.json()).runs || []);
      setErr("");
    } catch (e) {
      setErr(String(e).slice(0, 140));
    }
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 15000);
    return () => clearInterval(iv);
  }, [load]);

  const post = async (path, body) => {
    const r = await fetch(`${API}/api/admin/autopilot/${path}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  };

  const activate = async () => {
    setBusy(true);
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Toronto";
      const r = await post("activate", { time: fireTime, tz });
      setToast(`🚀 Autopilot ARMED — next fire at ${String(r.next_fire_at).slice(0, 19).replace("T", " ")} UTC (${Math.round((r.seconds_until_fire || 0) / 3600)}h from now)`);
      setConfirming(false);
      await load();
    } catch (e) {
      setErr(String(e).slice(0, 160));
    } finally {
      setBusy(false);
      setTimeout(() => setToast(""), 7000);
    }
  };

  const pauseNow = async () => {
    setBusy(true);
    try {
      await post("pause");
      setToast("Autopilot paused. Per-tenant auto-blast settings preserved.");
      await load();
    } catch (e) {
      setErr(String(e).slice(0, 160));
    } finally {
      setBusy(false);
      setTimeout(() => setToast(""), 5000);
    }
  };

  const fireNow = async () => {
    setBusy(true);
    try {
      const r = await post("fire-now");
      const phases = r.run?.phases || [];
      const ok = phases.filter(p => p.ok).length;
      setToast(`🔥 Test fire complete — ${ok}/${phases.length} phases OK (${r.run?.duration_seconds}s)`);
      await load();
    } catch (e) {
      setErr(String(e).slice(0, 160));
    } finally {
      setBusy(false);
      setTimeout(() => setToast(""), 7000);
    }
  };

  const enabled = status?.enabled;
  const nextFire = status?.next_fire_at;
  const secUntil = status?.seconds_until_fire || 0;
  const nextFireHuman = secUntil > 0
    ? `${Math.floor(secUntil / 3600)}h ${Math.floor((secUntil % 3600) / 60)}m`
    : "—";
  const agents = status?.agents || ["scout", "hunt", "blast", "report"];
  const lastRun = log[0];
  const tenants = status?.auto_blast_tenants || { enabled: 0, total: 0 };

  const armColor = enabled ? "#22C55E" : "#D4AF37";

  return (
    <div
      data-testid="autopilot-master-button"
      style={{
        padding: 24,
        borderRadius: 18,
        background: enabled
          ? "linear-gradient(135deg, rgba(34,197,94,0.10) 0%, rgba(10,12,20,0.72) 60%)"
          : "linear-gradient(135deg, rgba(212,175,55,0.10) 0%, rgba(10,12,20,0.72) 60%)",
        border: `1px solid ${armColor}55`,
        boxShadow: `0 0 24px ${armColor}22`,
        backdropFilter: "blur(22px) saturate(140%)",
        marginBottom: 18,
        color: "#F4F4F4",
        fontFamily: "'Jost',sans-serif",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Rocket size={20} style={{ color: armColor }} />
            <h3 style={{
              fontFamily: "'Cinzel',serif", fontSize: 22, margin: 0, letterSpacing: "0.04em",
              background: `linear-gradient(135deg, ${armColor}, #FFF)`, WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}>
              Master Autopilot · Morning Blast
            </h3>
          </div>
          <p style={{ fontSize: 12, color: "#8A8070", marginTop: 4, marginLeft: 30, letterSpacing: "0.02em" }}>
            Scout → Hunt → Blast → Report · 4 agents · single-click arm · zero-touch daily run
          </p>
        </div>
        <button
          onClick={load}
          disabled={busy}
          data-testid="autopilot-refresh"
          style={{
            padding: 8, borderRadius: 8,
            background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
            color: "#C8C8C8", cursor: busy ? "not-allowed" : "pointer",
          }}
        >
          <RefreshCw size={12} className={busy ? "animate-spin" : ""} />
        </button>
      </div>

      {err && (
        <div style={{ padding: 10, borderRadius: 8, background: "rgba(239,68,68,0.14)", border: "1px solid rgba(239,68,68,0.3)", color: "#FCA5A5", fontSize: 12, marginBottom: 10 }}>
          <AlertTriangle size={12} style={{ marginRight: 6, display: "inline-block", verticalAlign: "middle" }} />
          {err}
        </div>
      )}
      {toast && (
        <div data-testid="autopilot-toast" style={{ padding: 10, borderRadius: 8, background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.3)", color: "#86EFAC", fontSize: 12, marginBottom: 10 }}>
          {toast}
        </div>
      )}

      {/* Main status bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10, marginBottom: 14 }}>
        <StatCard label="Status" testid="ap-status"
          value={enabled ? "ARMED" : "IDLE"}
          color={enabled ? "#22C55E" : "#6B7280"} />
        <StatCard label="Next Fire" testid="ap-next-fire"
          value={enabled ? nextFireHuman : "—"}
          sub={nextFire ? String(nextFire).slice(11, 16) + " UTC" : null}
          color="#D4AF37" />
        <StatCard label="Auto-Blast Tenants" testid="ap-tenants"
          value={`${tenants.enabled}/${tenants.total}`}
          color="#60A5FA" />
        <StatCard label="Last Run" testid="ap-last"
          value={lastRun ? (lastRun.success ? "SUCCESS" : "PARTIAL") : "—"}
          sub={lastRun ? String(lastRun.started_at).slice(11, 19) : null}
          color={lastRun?.success ? "#22C55E" : lastRun ? "#F59E0B" : "#6B7280"} />
      </div>

      {/* Agent chips */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "#8A8070", marginBottom: 8 }}>
          Agents on Duty
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {agents.map((a) => {
            const Icon = AGENT_ICONS[a] || Zap;
            return (
              <div key={a}
                data-testid={`ap-agent-${a}`}
                style={{
                  padding: "6px 12px", borderRadius: 20, fontSize: 11, fontWeight: 700,
                  background: enabled ? "rgba(34,197,94,0.12)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${enabled ? "rgba(34,197,94,0.35)" : "rgba(255,255,255,0.08)"}`,
                  color: enabled ? "#86EFAC" : "#C8C8C8",
                  display: "inline-flex", alignItems: "center", gap: 6,
                  letterSpacing: "0.05em",
                }}>
                <Icon size={11} /> {AGENT_LABELS[a] || a}
              </div>
            );
          })}
        </div>
      </div>

      {/* Primary CTA */}
      {!enabled ? (
        confirming ? (
          <div style={{
            padding: 14, borderRadius: 12,
            background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.25)",
            display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap",
          }}>
            <label style={{ fontSize: 11, color: "#8A8070", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Fire every day at
            </label>
            <input
              type="time"
              value={fireTime}
              onChange={(e) => setFireTime(e.target.value)}
              data-testid="ap-fire-time"
              style={{
                padding: "6px 10px", borderRadius: 6,
                background: "#0A0C14", border: "1px solid rgba(212,175,55,0.35)",
                color: "#F4F4F4", fontSize: 13, fontFamily: "monospace",
              }}
            />
            <span style={{ fontSize: 10, color: "#8A8070" }}>
              ({Intl.DateTimeFormat().resolvedOptions().timeZone || "local"})
            </span>
            <button
              onClick={activate}
              disabled={busy}
              data-testid="ap-arm-confirm"
              style={{
                marginLeft: "auto", padding: "10px 20px", borderRadius: 10, border: "none",
                background: "linear-gradient(135deg, #22C55E 0%, #15803D 100%)",
                color: "#FFF", fontWeight: 800, fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase",
                cursor: busy ? "not-allowed" : "pointer",
                boxShadow: "0 0 14px rgba(34,197,94,0.4)",
              }}
            >
              <Rocket size={12} style={{ verticalAlign: "middle", marginRight: 6 }} />
              Arm Autopilot
            </button>
            <button
              onClick={() => setConfirming(false)}
              disabled={busy}
              data-testid="ap-arm-cancel"
              style={{
                padding: "10px 16px", borderRadius: 10,
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.12)",
                color: "#C8C8C8", fontSize: 12, letterSpacing: "0.06em",
                cursor: busy ? "not-allowed" : "pointer",
              }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button
              onClick={() => setConfirming(true)}
              disabled={busy}
              data-testid="ap-arm-open"
              style={{
                padding: "14px 24px", borderRadius: 12, border: "none",
                background: "linear-gradient(135deg, #D4AF37 0%, #8B5E00 100%)",
                color: "#1A0F00", fontWeight: 800, fontSize: 13, letterSpacing: "0.1em", textTransform: "uppercase",
                cursor: busy ? "not-allowed" : "pointer",
                boxShadow: "0 0 18px rgba(212,175,55,0.45)",
                display: "inline-flex", alignItems: "center", gap: 8,
              }}
            >
              <Rocket size={14} />
              Arm Tomorrow Morning
            </button>
            <button
              onClick={fireNow}
              disabled={busy}
              data-testid="ap-fire-now"
              style={{
                padding: "14px 20px", borderRadius: 12,
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,55,0.35)",
                color: "#D4AF37", fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
                cursor: busy ? "not-allowed" : "pointer",
                display: "inline-flex", alignItems: "center", gap: 6,
              }}
            >
              <Zap size={12} /> Test Fire Now
            </button>
          </div>
        )
      ) : (
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            onClick={pauseNow}
            disabled={busy}
            data-testid="ap-pause"
            style={{
              padding: "12px 20px", borderRadius: 10,
              background: "rgba(239,68,68,0.10)", border: "1px solid rgba(239,68,68,0.35)",
              color: "#FCA5A5", fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
              cursor: busy ? "not-allowed" : "pointer",
              display: "inline-flex", alignItems: "center", gap: 6,
            }}
          >
            <Pause size={12} /> Pause Autopilot
          </button>
          <button
            onClick={fireNow}
            disabled={busy}
            data-testid="ap-fire-now"
            style={{
              padding: "12px 20px", borderRadius: 10,
              background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.35)",
              color: "#86EFAC", fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
              cursor: busy ? "not-allowed" : "pointer",
              display: "inline-flex", alignItems: "center", gap: 6,
            }}
          >
            <Play size={12} /> Test Fire Now
          </button>
        </div>
      )}

      {/* Run log (last 10) */}
      {log.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "#8A8070", marginBottom: 8 }}>
            Recent Runs
          </div>
          <div data-testid="ap-run-log" style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 220, overflowY: "auto" }}>
            {log.map((run) => (
              <RunRow key={run.run_id} run={run} />
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 10, color: "#6B7280", letterSpacing: "0.08em" }}>
        Zabaan ka pakka · Morning cron-less scheduler · {status?.activated_by ? `armed by ${status.activated_by}` : "unarmed"}
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color, testid }) {
  return (
    <div
      data-testid={testid}
      style={{
        padding: 10, borderRadius: 10,
        background: "rgba(255,255,255,0.03)",
        border: `1px solid ${color}33`,
      }}
    >
      <div style={{ fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase", color: "#8A8070" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color, marginTop: 3, fontFamily: "'Jost',sans-serif" }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#6B7280", marginTop: 1, fontFamily: "monospace" }}>{sub}</div>}
    </div>
  );
}

function RunRow({ run }) {
  const ok = run.success;
  const color = ok ? "#22C55E" : "#F59E0B";
  const phaseCount = (run.phases || []).length;
  const okCount = (run.phases || []).filter(p => p.ok).length;
  return (
    <div style={{
      padding: "8px 12px", borderRadius: 8,
      background: `rgba(255,255,255,0.02)`,
      border: `1px solid ${color}22`,
      display: "flex", alignItems: "center", gap: 10, fontSize: 11,
      fontFamily: "monospace",
    }}>
      {ok
        ? <CheckCircle2 size={12} style={{ color }} />
        : <AlertTriangle size={12} style={{ color }} />}
      <span style={{ color: "#C8C8C8" }}>{String(run.started_at).slice(0, 19).replace("T", " ")}</span>
      <span style={{ color: "#D4AF37" }}>{run.triggered_by?.split(":")[0] || "auto"}</span>
      <span style={{ color, fontWeight: 700 }}>{okCount}/{phaseCount} ok</span>
      <span style={{ marginLeft: "auto", color: "#8A8070" }}>
        <Clock size={10} style={{ marginRight: 3, verticalAlign: "middle" }} />
        {run.duration_seconds}s
      </span>
    </div>
  );
}
