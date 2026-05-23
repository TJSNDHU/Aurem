/**
 * SpecialistCostBreakdownTile — iter 332a-2
 * 7-day rollup of ORA vs Emergent vs validated-cache calls.
 * Pulls from GET /api/admin/ora/specialist-cost-breakdown (30s poll).
 */
import React, { useEffect, useState, useCallback } from "react";
import { Cpu, Sparkles, DatabaseZap, DollarSign } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 30000;

const TEXT      = "#F0EADC";
const TEXT_DIM  = "#A8A08F";
const BORDER    = "rgba(212,175,55,0.18)";
const GREEN     = "#67E8A0";
const ORANGE    = "#FF6B00";
const GOLD      = "#E8C86A";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55)",
  padding: 18,
};

function authHeaders() {
  const tok =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("admin_token") ||
    localStorage.getItem("token") ||
    "";
  return tok ? { Authorization: `Bearer ${tok}` } : {};
}

function Row({ icon: Icon, label, calls, value, color, testid }) {
  return (
    <div data-testid={testid}
         style={{ display: "flex", alignItems: "center",
                   justifyContent: "space-between", padding: "10px 12px",
                   borderRadius: 10,
                   background: "rgba(255,255,255,0.02)",
                   border: "1px solid rgba(255,255,255,0.04)" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 8,
                      color: TEXT_DIM, fontSize: 12 }}>
        <Icon size={13} style={{ color: color || TEXT_DIM }} />
        {label}
        <span style={{ fontFamily: "'JetBrains Mono', monospace",
                        color: TEXT, fontSize: 11 }}>
          · {calls} call{calls === 1 ? "" : "s"}
        </span>
      </span>
      <span style={{ color: color || TEXT, fontWeight: 600,
                      fontSize: 14 }}>
        {value}
      </span>
    </div>
  );
}

export default function SpecialistCostBreakdownTile() {
  const [data, setData] = useState(null);
  const [err, setErr]   = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/admin/ora/specialist-cost-breakdown`,
                             { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setErr(null);
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const ora       = data?.ora       || { calls: 0, usd: 0 };
  const emergent  = data?.emergent  || { calls: 0, usd: 0 };
  const validated = data?.validated || { calls: 0, usd_saved: 0 };
  const spent = data?.total_spent_usd ?? 0;
  const saved = data?.total_saved_usd ?? 0;

  return (
    <div data-testid="specialist-cost-tile" style={GLASS}>
      <div style={{ display: "flex", justifyContent: "space-between",
                     alignItems: "center", marginBottom: 14 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: TEXT,
                        display: "flex", alignItems: "center", gap: 8 }}>
          <DollarSign size={14} style={{ color: GOLD }} />
          Specialist cost — last 7 days
        </span>
        <span style={{ color: TEXT_DIM, fontSize: 11 }}>
          spent <span style={{ color: TEXT }}>${spent.toFixed(3)}</span> · saved{" "}
          <span style={{ color: GREEN }}>${saved.toFixed(2)}</span>
        </span>
      </div>

      {err && (
        <div data-testid="specialist-cost-error"
              style={{ color: "#FF6060", fontSize: 12, marginBottom: 8 }}>
          {err}
        </div>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        <Row testid="cost-row-ora" icon={Cpu} label="ORA local"
              calls={ora.calls} color={TEXT}
              value={`$${(ora.usd || 0).toFixed(3)}`} />
        <Row testid="cost-row-emergent" icon={Sparkles} label="Emergent"
              calls={emergent.calls} color={ORANGE}
              value={`$${(emergent.usd || 0).toFixed(3)}`} />
        <Row testid="cost-row-validated" icon={DatabaseZap}
              label="Validated cache hits"
              calls={validated.calls} color={GREEN}
              value={`$${(validated.usd_saved || 0).toFixed(2)} saved`} />
      </div>
    </div>
  );
}
