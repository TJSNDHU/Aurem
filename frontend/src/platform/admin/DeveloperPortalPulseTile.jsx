/**
 * DeveloperPortalPulseTile — iter 331f
 * Single Cockpit card showing live Developer Portal counters:
 *   active_sessions, tokens_remaining, sessions_refused_today,
 *   ssrf_blocks_today, abuse_blocks_today, emails_sent_today.
 *
 * Auto-polls every 30s. Auth-gated via the admin token bearer.
 */
import React, { useEffect, useState, useCallback } from "react";
import { Users, ShieldAlert, Coins, Activity } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const POLL_MS = 30000;

const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GREEN = "#67E8A0";
const AMBER = "#FFB36B";
const RED = "#FF7676";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("admin_token") ||
    localStorage.getItem("token") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function StatColumn({ icon: Icon, label, value, color }) {
  return (
    <div data-testid={`dev-pulse-stat-${label.replace(/\s+/g, "-").toLowerCase()}`}
         style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6,
                    color: TEXT_DIM, fontSize: 11, letterSpacing: 0.4,
                    textTransform: "uppercase" }}>
        <Icon size={12} /> {label}
      </div>
      <div style={{ color: color || TEXT, fontSize: 22, fontWeight: 600 }}>
        {value}
      </div>
    </div>
  );
}

export default function DeveloperPortalPulseTile() {
  const [data, setData] = useState(null);
  const [err, setErr]   = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/admin/developers/health`,
                             { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (j?.ok) {
        setData(j);
        setErr(null);
      }
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const status = data?.status || "gray";
  const statusColor = status === "green" ? GREEN
                    : status === "yellow" ? AMBER
                    : status === "red"   ? RED : TEXT_DIM;

  return (
    <div data-testid="developer-portal-pulse-tile" style={{ ...GLASS, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%",
                          background: statusColor, display: "inline-block",
                          boxShadow: `0 0 8px ${statusColor}` }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: TEXT }}>
            Developer Portal pulse
          </span>
        </div>
        <span style={{ color: TEXT_DIM, fontSize: 11 }}>
          {data?.developers?.verified ?? 0} verified · {data?.developers?.total ?? 0} total
        </span>
      </div>

      {err && (
        <div data-testid="dev-pulse-error" style={{ color: RED, fontSize: 12, marginBottom: 8 }}>
          {err}
        </div>
      )}

      <div style={{ display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                    gap: 14, marginBottom: 14 }}>
        <StatColumn icon={Users} label="Active sessions"
                    value={data?.sessions?.active_total ?? 0} />
        <StatColumn icon={Coins} label="Tokens remaining"
                    value={(data?.tokens?.remaining_total ?? 0).toLocaleString()} />
        <StatColumn icon={Activity} label="Calls 24h"
                    value={data?.tokens?.calls_today ?? 0} />
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between",
                      padding: "8px 12px", background: "rgba(255,118,118,0.06)",
                      border: "1px solid rgba(255,118,118,0.18)", borderRadius: 8 }}>
          <span style={{ color: TEXT_DIM, fontSize: 12,
                          display: "flex", alignItems: "center", gap: 6 }}>
            <ShieldAlert size={12} /> Blocks (24h)
          </span>
          <span style={{ color: TEXT, fontSize: 12 }}>
            <span data-testid="dev-pulse-ssrf">{data?.blocks_today?.ssrf ?? 0} SSRF</span>
            {" · "}
            <span data-testid="dev-pulse-abuse">{data?.blocks_today?.abuse ?? 0} abuse</span>
            {" · "}
            <span data-testid="dev-pulse-sessions-refused">
              {data?.blocks_today?.sessions ?? 0} session refused
            </span>
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between",
                      color: TEXT_DIM, fontSize: 11, paddingLeft: 4 }}>
          <span>Emails sent today</span>
          <span data-testid="dev-pulse-emails-sent">{data?.emails_sent_today ?? 0}</span>
        </div>
      </div>
    </div>
  );
}
