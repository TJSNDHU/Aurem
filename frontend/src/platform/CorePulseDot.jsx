/**
 * CorePulseDot — live pulse indicator for AUREM Pillars health.
 * iter 279: polls /api/admin/pillars-map/overview every 25s and renders a
 * red/amber/green dot on the /dashboard sidebar so the operator sees
 * the system's vital signs at a glance — no drill-in required.
 *
 * States:
 *   🟢 green  — all pillars healthy (all collections written in window)
 *   🟡 amber  — one or more pillars degraded (stale writes < threshold)
 *   🔴 red    — at least one pillar down (hard fail or no data)
 *   ⚪ gray   — data not yet loaded (first few seconds after mount)
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL || "";

function readToken() {
  return (
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    ""
  );
}

export default function CorePulseDot() {
  const [status, setStatus] = useState("loading");
  const [counts, setCounts] = useState({ healthy: 0, degraded: 0, down: 0 });
  const navigate = useNavigate();

  useEffect(() => {
    let cancel = false;

    const poll = async () => {
      try {
        const token = readToken();
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const r = await fetch(`${API}/api/admin/pillars-map/overview`, {
          headers,
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        const pillars = d.pillars || [];
        let healthy = 0, degraded = 0, down = 0;
        for (const p of pillars) {
          const s = String(p.status || p.overall || "").toLowerCase();
          if (s.includes("healthy") || s.includes("ok") || s === "green") healthy++;
          else if (s.includes("degrad") || s.includes("warn") || s === "amber") degraded++;
          else down++;
        }
        if (cancel) return;
        setCounts({ healthy, degraded, down });
        if (down > 0) setStatus("down");
        else if (degraded > 0) setStatus("degraded");
        else if (healthy > 0) setStatus("healthy");
        else setStatus("unknown");
      } catch {
        if (!cancel) setStatus("down");
      }
    };

    poll();
    const id = setInterval(poll, 25_000);
    return () => {
      cancel = true;
      clearInterval(id);
    };
  }, []);

  const COLORS = {
    healthy:  { bg: "#22C55E", glow: "0 0 8px #22C55E", label: "All pillars green" },
    degraded: { bg: "#F59E0B", glow: "0 0 8px #F59E0B", label: "Some pillars degraded" },
    down:     { bg: "#EF4444", glow: "0 0 10px #EF4444", label: "At least one pillar down" },
    loading:  { bg: "#6B7280", glow: "none", label: "Loading…" },
    unknown:  { bg: "#6B7280", glow: "none", label: "No data" },
  };

  const meta = COLORS[status] || COLORS.loading;
  const tooltip = `${meta.label}  ·  ${counts.healthy}✓ ${counts.degraded}⚠ ${counts.down}✗  ·  Click to open Pillars Map`;

  return (
    <button
      type="button"
      data-testid="core-pulse-dot"
      title={tooltip}
      onClick={(e) => {
        e.stopPropagation();
        navigate("/admin/pillars-map");
      }}
      style={{
        width: 8,
        height: 8,
        borderRadius: 50,
        background: meta.bg,
        boxShadow: meta.glow,
        animation:
          status === "down"
            ? "corePulsePing 1.2s ease-in-out infinite"
            : status === "degraded"
              ? "corePulsePing 2.2s ease-in-out infinite"
              : "none",
        border: "none",
        padding: 0,
        cursor: "pointer",
        flexShrink: 0,
      }}
    >
      <span className="sr-only">{tooltip}</span>
      <style>{`
        @keyframes corePulsePing {
          0%,100% { transform: scale(1);   opacity: 1; }
          50%     { transform: scale(1.3); opacity: 0.7; }
        }
      `}</style>
    </button>
  );
}
