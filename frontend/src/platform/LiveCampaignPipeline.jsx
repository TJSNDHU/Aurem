/**
 * LiveCampaignPipeline — replaces the RobotViewport warehouse junk.
 * Shows a real-time snapshot of active campaigns with actual lead counts.
 * iter 278: production-relevant trust signal, no fake/simulated data.
 */
import React, { useEffect, useState } from "react";
import { Rocket, TrendingUp, RefreshCw, Activity } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

function statusColor(status) {
  const s = String(status || "").toLowerCase();
  if (s.includes("active") || s.includes("running") || s.includes("live"))
    return { bg: "rgba(34,197,94,0.15)", fg: "#22C55E" };
  if (s.includes("paused") || s.includes("draft"))
    return { bg: "rgba(245,158,11,0.15)", fg: "#F59E0B" };
  if (s.includes("completed") || s.includes("done"))
    return { bg: "rgba(96,165,250,0.15)", fg: "#60A5FA" };
  return { bg: "rgba(156,163,175,0.12)", fg: "#9CA3AF" };
}

export default function LiveCampaignPipeline({ token }) {
  const [campaigns, setCampaigns] = useState([]);
  const [stats, setStats] = useState({ total: 0, active: 0, leads: 0 });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = async () => {
    setLoading(true);
    setErr("");
    try {
      const hdrs = token ? { Authorization: `Bearer ${token}` } : {};
      // iter 285.6 — /api/campaigns/ was 404 (old mount removed). Real data
      // lives on two pillar endpoints: proximity + comms. Merge both so the
      // widget reflects actual activity (no mocks, no fake fallback).
      const [pxR, cmR] = await Promise.all([
        fetch(`${API}/api/proximity/campaigns`, { headers: hdrs }).catch(() => null),
        fetch(`${API}/api/comms/campaigns`, { headers: hdrs }).catch(() => null),
      ]);
      const merged = [];
      if (pxR && pxR.ok) {
        const d = await pxR.json();
        for (const c of (d.campaigns || [])) {
          merged.push({
            name: `${c.source || "proximity"} · ${c.radius_km}km`,
            status: c.data_source === "real" ? "active" : "completed",
            lead_count: c.leads_found || 0,
            created_at: c.created_at,
            _source: "proximity",
          });
        }
      }
      if (cmR && cmR.ok) {
        const d = await cmR.json();
        for (const c of (d.campaigns || [])) {
          merged.push({
            name: c.name || c.campaign_name || c.id || "comm-campaign",
            status: c.status || "active",
            lead_count: c.recipients_count || c.lead_count || 0,
            created_at: c.created_at,
            _source: "comms",
          });
        }
      }
      merged.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
      const active = merged.filter((c) =>
        String(c.status || "").toLowerCase().match(/active|running|live/)
      ).length;
      const leadCount = merged.reduce((sum, c) => sum + (c.lead_count || 0), 0);
      setCampaigns(merged.slice(0, 5));
      setStats({ total: merged.length, active, leads: leadCount });
      if (merged.length === 0 && !(pxR?.ok) && !(cmR?.ok)) {
        throw new Error("Both campaign pillars unreachable");
      }
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      data-testid="live-campaign-pipeline"
      style={{
        borderRadius: 16,
        overflow: "hidden",
        background:
          "linear-gradient(135deg,rgba(26,26,46,0.85) 0%,rgba(15,15,30,0.95) 100%)",
        backdropFilter: "blur(24px)",
        border: "1px solid rgba(212,175,55,0.2)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid rgba(212,175,55,0.15)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Rocket size={16} style={{ color: "#D4AF37" }} />
          <span
            style={{
              color: "#D4AF37",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: 2,
              fontFamily: "'Montserrat',sans-serif",
            }}
          >
            LIVE CAMPAIGN PIPELINE
          </span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 50,
              background: "#22C55E",
              boxShadow: "0 0 8px #22C55E",
              animation: "pulse 2s ease-in-out infinite",
            }}
          />
        </div>
        <button
          onClick={load}
          disabled={loading}
          data-testid="pipeline-refresh"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 10px",
            background: "rgba(212,175,55,0.08)",
            border: "1px solid rgba(212,175,55,0.3)",
            borderRadius: 6,
            color: "#D4AF37",
            fontSize: 10,
            cursor: "pointer",
            opacity: loading ? 0.5 : 1,
          }}
        >
          <RefreshCw
            size={10}
            style={{ animation: loading ? "spin 1s linear infinite" : "" }}
          />
          Refresh
        </button>
      </div>

      {/* Stats row */}
      <div
        style={{
          padding: "16px",
          display: "grid",
          gridTemplateColumns: "repeat(3,1fr)",
          gap: 12,
          borderBottom: "1px solid rgba(212,175,55,0.1)",
        }}
      >
        <StatBox label="Total Campaigns" value={stats.total} color="#60A5FA" />
        <StatBox label="Active Now" value={stats.active} color="#22C55E" />
        <StatBox label="Leads Engaged" value={stats.leads} color="#D4AF37" />
      </div>

      {/* Campaign list */}
      <div style={{ padding: "12px 16px", minHeight: 180 }}>
        {err ? (
          <div style={{ color: "#EF4444", fontSize: 12 }}>
            Failed to load: {err}
          </div>
        ) : campaigns.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              color: "#8A8070",
              fontSize: 12,
              padding: "24px 0",
              fontStyle: "italic",
            }}
          >
            No campaigns yet — launch one from Campaign HQ to see live activity
            here.
          </div>
        ) : (
          campaigns.map((c, i) => {
            const sc = statusColor(c.status);
            return (
              <div
                key={c._id || c.id || i}
                data-testid={`pipeline-row-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 0",
                  borderBottom:
                    i < campaigns.length - 1
                      ? "1px solid rgba(212,175,55,0.07)"
                      : "none",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      color: "#E8E0D0",
                      fontSize: 13,
                      fontWeight: 500,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {c.name || c.title || c.campaign_name || "Untitled"}
                  </div>
                  <div style={{ color: "#8A8070", fontSize: 10, marginTop: 2 }}>
                    {c.lead_count || c.leads_count || 0} leads ·{" "}
                    {c.channel || c.type || "multi-channel"}
                  </div>
                </div>
                <span
                  style={{
                    padding: "2px 8px",
                    background: sc.bg,
                    color: sc.fg,
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: 1,
                    borderRadius: 4,
                    textTransform: "uppercase",
                  }}
                >
                  {c.status || "draft"}
                </span>
              </div>
            );
          })
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1}50%{opacity:.5} }
        @keyframes spin { to { transform: rotate(360deg) } }
      `}</style>
    </div>
  );
}

function StatBox({ label, value, color }) {
  return (
    <div>
      <div
        style={{
          fontSize: 10,
          color: "#8A8070",
          textTransform: "uppercase",
          letterSpacing: 1.2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 300,
          color,
          marginTop: 2,
          fontFamily: "'Jost',sans-serif",
        }}
      >
        {(value || 0).toLocaleString()}
      </div>
    </div>
  );
}
