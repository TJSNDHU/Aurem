/**
 * CampaignCommandDashboard.jsx — iter D-78
 *
 * Real funnel metrics for every campaign on the platform.
 * NO MOCK DATA: every byte comes straight from
 * /api/admin/campaigns/funnel which aggregates live Mongo
 * collections (campaign_leads, outreach_history, inbound_replies,
 * platform_users).
 *
 * Hero strip: grand totals across all campaigns
 * Per-campaign cards: touches → opens → replies → conversions
 *                     with channel breakdown + sparkline timeline
 * Source lineage: every metric shows its source collection so
 *                 the founder can audit any number on demand.
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Send, Eye, MessageSquare, Trophy, RefreshCw, AlertTriangle,
  TrendingUp, ChevronDown, ChevronRight,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

function authHeaders() {
  const t =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") || "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function fmt(n) {
  if (n === null || n === undefined) return "—";
  if (typeof n !== "number") return String(n);
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 10_000) return (n / 1_000).toFixed(1) + "k";
  return n.toLocaleString();
}

function pct(p) {
  if (p === null || p === undefined) return "—";
  return `${p.toFixed(p < 10 ? 2 : 1)}%`;
}

// ── Hero metric tile (top strip) ────────────────────────────────────
function HeroTile({ icon: Icon, label, value, sub, accent }) {
  return (
    <div
      data-testid={`funnel-hero-${label.toLowerCase().replace(/\s+/g, "-")}`}
      className="flex-1 min-w-[160px] bg-zinc-950/70 border border-zinc-800 rounded-xl p-4 relative overflow-hidden"
    >
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{ background: accent }}
      />
      <div className="flex items-center justify-between mb-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: `${accent}1A`, color: accent }}
        >
          <Icon size={16} />
        </div>
        <span className="text-[9px] uppercase tracking-[2px] text-zinc-500 font-semibold">
          {label}
        </span>
      </div>
      <div className="font-mono text-2xl font-bold text-zinc-50 tracking-tight">
        {fmt(value)}
      </div>
      {sub && <div className="text-[10px] text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

// ── Channel breakdown bar (per campaign card) ──────────────────────
function ChannelBar({ label, count, max, color }) {
  const w = max > 0 ? Math.max(2, Math.round((count / max) * 100)) : 0;
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-16 text-zinc-500 uppercase tracking-wider">{label}</span>
      <div className="flex-1 bg-zinc-900 rounded h-2 overflow-hidden">
        <div
          className="h-full"
          style={{ width: `${w}%`, background: color }}
        />
      </div>
      <span className="w-12 text-right font-mono text-zinc-200">
        {fmt(count)}
      </span>
    </div>
  );
}

// ── Sparkline (touches per day) ────────────────────────────────────
function Sparkline({ series }) {
  if (!series || series.length === 0) {
    return <div className="text-[10px] text-zinc-600 italic">no timeline</div>;
  }
  const max = Math.max(1, ...series.map((d) => d.total));
  const W = 240, H = 36;
  const step = W / Math.max(1, series.length - 1);
  const pts = series
    .map((d, i) => `${(i * step).toFixed(1)},${(H - (d.total / max) * H).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={W} height={H} className="block">
      <polyline
        fill="none"
        stroke="#F97316"
        strokeWidth="1.5"
        points={pts}
      />
      {series.map((d, i) => (
        <circle
          key={i}
          cx={(i * step).toFixed(1)}
          cy={(H - (d.total / max) * H).toFixed(1)}
          r={d.total > 0 ? 1.5 : 0.5}
          fill={d.total > 0 ? "#F97316" : "#52525B"}
        />
      ))}
    </svg>
  );
}

// ── Per-campaign card ──────────────────────────────────────────────
function CampaignCard({ camp, expanded, onToggle }) {
  const [series, setSeries] = useState(null);
  const t = camp.touches || {};
  const o = camp.opens || {};
  const r = camp.replies || {};
  const c = camp.conversions || {};
  const rates = camp.rates_pct || {};
  const maxCh = Math.max(1, ...Object.values(t.by_channel || { x: 1 }));

  useEffect(() => {
    if (!expanded || series !== null) return;
    let ok = true;
    (async () => {
      try {
        const cid = camp.is_unattributed ? "__unattributed__" : camp.campaign_id;
        const res = await fetch(
          `${API}/api/admin/campaigns/funnel/${encodeURIComponent(cid)}/timeline?days=14`,
          { headers: { ...authHeaders() } },
        );
        const j = await res.json();
        if (ok) setSeries(j.series || []);
      } catch (_e) {
        if (ok) setSeries([]);
      }
    })();
    return () => { ok = false; };
  }, [expanded, series, camp.campaign_id, camp.is_unattributed]);

  return (
    <div
      data-testid={`funnel-card-${camp.campaign_id}`}
      className="bg-zinc-950/70 border border-zinc-800 rounded-xl overflow-hidden"
    >
      <button
        onClick={onToggle}
        data-testid={`funnel-toggle-${camp.campaign_id}`}
        className="w-full px-5 py-4 flex items-center gap-3 hover:bg-zinc-900/40 text-left"
      >
        <span className="text-zinc-400">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-mono font-semibold text-zinc-100 truncate">
            {camp.campaign_id}
            {camp.is_unattributed && (
              <span className="ml-2 text-[10px] uppercase tracking-wider text-amber-400 border border-amber-700/40 bg-amber-900/20 px-1.5 py-0.5 rounded">
                unattributed
              </span>
            )}
          </div>
          <div className="text-[10px] uppercase tracking-[2px] text-zinc-500 mt-1">
            {fmt(camp.leads_total)} leads &middot; {fmt(t.total || 0)} touches &middot; {fmt(o.total || 0)} opens &middot; {fmt(r.total || 0)} replies &middot; {fmt(c.total || 0)} conv.
          </div>
        </div>
        <div className="hidden md:flex items-center gap-6 text-right shrink-0">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-500">Open</div>
            <div className="font-mono text-sm text-blue-300">{pct(rates.open_rate)}</div>
          </div>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-500">Reply</div>
            <div className="font-mono text-sm text-emerald-300">{pct(rates.reply_rate)}</div>
          </div>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-zinc-500">Conv.</div>
            <div className="font-mono text-sm text-amber-300">{pct(rates.conversion_rate)}</div>
          </div>
        </div>
      </button>

      {expanded && (
        <div
          data-testid={`funnel-detail-${camp.campaign_id}`}
          className="border-t border-zinc-800 px-5 py-4 grid md:grid-cols-2 gap-6 text-xs"
        >
          {/* Channel breakdown */}
          <div>
            <div className="text-[9px] uppercase tracking-[3px] text-zinc-500 font-semibold mb-3">
              Touches by channel
            </div>
            <div className="space-y-2">
              <ChannelBar label="Email"    count={t.by_channel?.email || 0}    max={maxCh} color="#F97316" />
              <ChannelBar label="WhatsApp" count={t.by_channel?.whatsapp || 0} max={maxCh} color="#22c55e" />
              <ChannelBar label="SMS"      count={t.by_channel?.sms || 0}      max={maxCh} color="#3b82f6" />
              <ChannelBar label="Call"     count={t.by_channel?.call || 0}     max={maxCh} color="#a855f7" />
            </div>
            <div className="text-[10px] text-zinc-500 mt-4 font-mono">
              source: {t.source_collection}
            </div>
          </div>

          {/* Opens / Replies / Conversions */}
          <div>
            <div className="text-[9px] uppercase tracking-[3px] text-zinc-500 font-semibold mb-3">
              Engagement &amp; conversion
            </div>
            <div className="space-y-2 mb-3">
              <div className="flex justify-between">
                <span className="text-zinc-400">report_view (pixel)</span>
                <span className="font-mono text-zinc-100">{fmt(o.by_channel?.report_view || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">sample_view (pixel)</span>
                <span className="font-mono text-zinc-100">{fmt(o.by_channel?.sample_view || 0)}</span>
              </div>
              <div className="flex justify-between border-t border-zinc-800 pt-2">
                <span className="text-zinc-400">replies (inbound)</span>
                <span className="font-mono text-emerald-300">{fmt(r.total || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">conv. via status</span>
                <span className="font-mono text-amber-300">{fmt(c.by_lead_status || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">conv. via signup</span>
                <span className="font-mono text-amber-300">{fmt(c.by_platform_signup || 0)}</span>
              </div>
            </div>
            {r.source_missing && (
              <div className="text-[10px] text-amber-400 flex items-center gap-1">
                <AlertTriangle size={11} />
                inbound_replies collection missing — replies = 0
              </div>
            )}
            <div className="text-[10px] text-zinc-500 mt-2 font-mono">
              source: campaign_leads.status + platform_users.email
            </div>
          </div>

          {/* Timeline */}
          <div className="md:col-span-2 border-t border-zinc-800 pt-4">
            <div className="text-[9px] uppercase tracking-[3px] text-zinc-500 font-semibold mb-2">
              Touches (last 14 days)
            </div>
            <Sparkline series={series} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Top-level dashboard ───────────────────────────────────────────
export default function CampaignCommandDashboard() {
  const [body, setBody] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(
        `${API}/api/admin/campaigns/funnel?limit=50`,
        { headers: { ...authHeaders() } },
      );
      if (!r.ok) {
        const t = await r.text().catch(() => "");
        throw new Error(`${r.status} ${t.slice(0, 200)}`);
      }
      setBody(await r.json());
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const grand = body?.grand || {};
  const camps = body?.campaigns || [];

  return (
    <div
      data-testid="campaign-command-dashboard"
      className="bg-black min-h-screen text-zinc-100 px-6 py-8"
    >
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6 flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1
            data-testid="campaign-dashboard-title"
            className="font-serif text-2xl text-orange-300 tracking-wide"
          >
            Campaign Command
          </h1>
          <p className="text-xs text-zinc-500 mt-1 max-w-2xl">
            Real funnel metrics aggregated live from <span className="font-mono text-zinc-300">campaign_leads.outreach_history</span>,
            {" "}<span className="font-mono text-zinc-300">inbound_replies</span>, and{" "}
            <span className="font-mono text-zinc-300">platform_users</span>. Zero mocks &mdash; every number is auditable.
          </p>
        </div>
        <button
          data-testid="campaign-dashboard-refresh"
          onClick={load}
          disabled={loading}
          className="text-xs text-zinc-300 border border-zinc-700 hover:border-orange-500 hover:text-orange-300 px-3 py-1.5 rounded inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          {loading ? "loading…" : "refresh"}
        </button>
      </div>

      {err && (
        <div
          data-testid="campaign-dashboard-error"
          className="max-w-7xl mx-auto mb-4 text-xs text-red-300 bg-red-950/40 border border-red-900/50 rounded px-3 py-2"
        >
          {err}
        </div>
      )}

      {/* Hero strip */}
      <div className="max-w-7xl mx-auto mb-8 flex flex-wrap gap-3">
        <HeroTile icon={Send} label="Touches Sent" value={grand.touches_total} sub={`across ${body?.campaign_count ?? 0} campaigns`} accent="#F97316" />
        <HeroTile icon={Eye} label="Opens" value={grand.opens_total} sub="pixel + sample views" accent="#3b82f6" />
        <HeroTile icon={MessageSquare} label="Replies" value={grand.replies_total} sub="inbound matched" accent="#22c55e" />
        <HeroTile icon={Trophy} label="Conversions" value={grand.conversions_total} sub="status + signup" accent="#eab308" />
        <HeroTile icon={TrendingUp} label="Leads" value={grand.leads_total} sub="total in funnel" accent="#a855f7" />
      </div>

      {/* Per-campaign cards */}
      <div className="max-w-7xl mx-auto space-y-3">
        {(!body && loading) && (
          <div className="text-xs text-zinc-500 italic">loading…</div>
        )}
        {body && camps.length === 0 && (
          <div
            data-testid="campaign-dashboard-empty"
            className="text-xs text-zinc-500 italic border border-dashed border-zinc-800 rounded-lg p-8 text-center"
          >
            No campaigns yet. Once your daily scrape runs and writes to{" "}
            <span className="font-mono text-zinc-300">campaign_leads</span>,
            the funnel will appear here automatically.
          </div>
        )}
        {camps.map((c) => (
          <CampaignCard
            key={c.campaign_id}
            camp={c}
            expanded={openId === c.campaign_id}
            onToggle={() => setOpenId(openId === c.campaign_id ? null : c.campaign_id)}
          />
        ))}
      </div>

      {body && (
        <div className="max-w-7xl mx-auto mt-6 text-[10px] text-zinc-600 font-mono">
          fetched_at: {body.fetched_at}
        </div>
      )}
    </div>
  );
}
