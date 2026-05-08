/**
 * EmpireHUDMap.jsx — iter 285.6
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Empire HUD — visualizes sovereign nodes + integration endpoints as a
 * star-topology map. Every node shows live status (green/amber/red/grey)
 * from /api/empire-hud/nodes. No mocks.
 *
 *   • Legion (Sovereign Node) — edge/local server (heartbeat-driven)
 *   • Twilio — SMS & voice
 *   • WHAPI  — WhatsApp Business
 *   • Resend — transactional email
 *   • Stripe — billing
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Phone, MessageCircle, Mail, CreditCard, Smartphone,
  Server, RefreshCw, Radio, AlertCircle,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const VERDICT = {
  green: { color: "#22C55E", label: "LIVE",     glow: "0 0 14px rgba(34,197,94,0.45)" },
  amber: { color: "#F59E0B", label: "DEGRADED", glow: "0 0 14px rgba(245,158,11,0.45)" },
  red:   { color: "#EF4444", label: "DOWN",     glow: "0 0 14px rgba(239,68,68,0.45)" },
  grey:  { color: "#6B7280", label: "NOT CFG",  glow: "none" },
};

const ICONS = {
  "phone":         Phone,
  "message-circle": MessageCircle,
  "mail":          Mail,
  "credit-card":   CreditCard,
  "smartphone":    Smartphone,
  "server":        Server,
};

export default function EmpireHUDMap() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const token = (typeof window !== "undefined" && (
    localStorage.getItem("token") ||
    localStorage.getItem("aurem_token") ||
    sessionStorage.getItem("platform_token") ||
    sessionStorage.getItem("aurem_platform_token")
  )) || "";

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/empire-hud/nodes`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        setData(await r.json());
        setErr("");
      } else {
        setErr(`HTTP ${r.status}`);
      }
    } catch (e) {
      setErr(String(e).slice(0, 140));
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, [load]);

  const nodes = data?.nodes || [];
  const sovereigns = nodes.filter((n) => n.kind === "sovereign");
  const integrations = nodes.filter((n) => n.kind === "integration");

  return (
    <div
      data-testid="empire-hud-map"
      style={{
        padding: 22,
        borderRadius: 16,
        background: "rgba(10,12,20,0.72)",
        border: "1px solid rgba(212,175,55,0.25)",
        backdropFilter: "blur(22px) saturate(140%)",
        marginBottom: 18,
        color: "#F4F4F4",
        fontFamily: "'Jost',sans-serif",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Radio size={18} style={{ color: "#D4AF37" }} />
          <h3 style={{
            fontFamily: "'Cinzel',serif", fontSize: 20, margin: 0, letterSpacing: "0.04em",
            background: "linear-gradient(135deg, #D4AF37, #FFF)", WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent", backgroundClip: "text",
          }}>
            Empire HUD · Sovereign Map
          </h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 11 }}>
          {data && (
            <>
              <StatPill n={data.green} color="#22C55E" label="live" />
              <StatPill n={data.amber} color="#F59E0B" label="degraded" />
              <StatPill n={data.red} color="#EF4444" label="down" />
              <StatPill n={data.grey} color="#6B7280" label="not cfg" />
            </>
          )}
          <button
            data-testid="empire-hud-refresh"
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
          <AlertCircle size={12} style={{ marginRight: 6, display: "inline-block", verticalAlign: "middle" }} />
          {err}
        </div>
      )}

      {/* Star topology — AUREM core in center, nodes around */}
      <div style={{ position: "relative", padding: "10px 0" }}>
        {/* Center node: AUREM core */}
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
          <div
            data-testid="empire-hud-core"
            style={{
              padding: "14px 24px", borderRadius: 28,
              background: "linear-gradient(135deg, rgba(212,175,55,0.25), rgba(212,175,55,0.08))",
              border: "1px solid rgba(212,175,55,0.55)",
              boxShadow: "0 0 18px rgba(212,175,55,0.22)",
              display: "inline-flex", alignItems: "center", gap: 10,
              fontFamily: "'Cinzel',serif", letterSpacing: "0.08em", color: "#D4AF37",
              fontSize: 14, fontWeight: 700,
            }}
          >
            <Server size={16} />
            AUREM CORE
          </div>
        </div>

        {/* Sovereign nodes row */}
        {sovereigns.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <RowLabel>Sovereign Nodes</RowLabel>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
              {sovereigns.map((n) => <NodeCard key={n.id} node={n} />)}
            </div>
          </div>
        )}

        {/* Integrations row */}
        <div>
          <RowLabel>Integrations</RowLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
            {integrations.map((n) => <NodeCard key={n.id} node={n} />)}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 12, fontSize: 10, color: "#6B7280", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        Zabaan ka pakka · Status derived from env + heartbeat + circuit breakers · Updated every 20s
      </div>
    </div>
  );
}

function StatPill({ n, color, label }) {
  if (typeof n !== "number") return null;
  return (
    <span
      style={{
        padding: "3px 10px", borderRadius: 14,
        background: `${color}18`, border: `1px solid ${color}55`,
        color, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
        display: "inline-flex", alignItems: "center", gap: 4,
      }}
    >
      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: color }} />
      {n} {label}
    </span>
  );
}

function RowLabel({ children }) {
  return (
    <div style={{
      fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase",
      color: "#8A8070", marginBottom: 8, paddingLeft: 4,
    }}>
      {children}
    </div>
  );
}

function NodeCard({ node }) {
  const v = VERDICT[node.verdict] || VERDICT.grey;
  const IconCmp = ICONS[node.icon] || Server;
  const isSovereign = node.kind === "sovereign";

  return (
    <div
      data-testid={`empire-node-${node.id}`}
      style={{
        padding: 14, borderRadius: 12,
        background: "rgba(255,255,255,0.025)",
        border: `1px solid ${v.color}44`,
        boxShadow: v.glow,
        position: "relative",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{
          width: 38, height: 38, borderRadius: 10,
          background: `${v.color}18`, border: `1px solid ${v.color}55`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: v.color,
        }}>
          <IconCmp size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#F4F4F4", letterSpacing: "0.03em" }}>
            {node.name}
          </div>
          <div style={{ fontSize: 10, color: "#8A8070", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            {node.role}
          </div>
        </div>
        <span
          data-testid={`empire-node-verdict-${node.id}`}
          style={{
            padding: "3px 8px", borderRadius: 12, fontSize: 9, fontWeight: 800,
            letterSpacing: "0.1em", textTransform: "uppercase",
            background: `${v.color}22`, color: v.color, border: `1px solid ${v.color}66`,
            display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0,
          }}
        >
          <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: v.color,
            animation: node.verdict === "green" ? "aurem-pulse 2s infinite" : "none" }} />
          {v.label}
        </span>
      </div>

      {isSovereign ? (
        <div style={{ fontSize: 10, color: "#8A8070", fontFamily: "monospace", lineHeight: 1.6 }}>
          <div>ip: <span style={{ color: "#C8C8C8" }}>{node.ip || "—"}</span></div>
          <div>last: <span style={{ color: "#C8C8C8" }}>
            {node.last_seen ? String(node.last_seen).slice(0, 19).replace("T", " ") : "never"}
          </span></div>
          <div>queue: <span style={{ color: node.queue_count > 0 ? "#F59E0B" : "#C8C8C8" }}>
            {node.queue_count || 0} pending
          </span></div>
          <div>version: <span style={{ color: "#C8C8C8" }}>{node.version || "—"}</span></div>
        </div>
      ) : (
        <div style={{ fontSize: 10, color: "#8A8070", fontFamily: "monospace", lineHeight: 1.6 }}>
          <div>status: <span style={{ color: v.color }}>{node.status}</span></div>
          {node.missing_keys && node.missing_keys.length > 0 && (
            <div>missing: <span style={{ color: "#F59E0B" }}>{node.missing_keys.join(", ")}</span></div>
          )}
          {node.circuit_last_failure && (
            <div>last_cb_failure: <span style={{ color: "#FCA5A5" }}>
              {String(node.circuit_last_failure).slice(0, 19).replace("T", " ")}
            </span></div>
          )}
        </div>
      )}
    </div>
  );
}
