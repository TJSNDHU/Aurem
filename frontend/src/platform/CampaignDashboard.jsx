/**
 * AUREM Campaign Dashboard — Outbound Acquisition Command Center
 * Shows campaign pipeline stats, lead table, schedule, and controls
 */
import React, { useState, useEffect, useCallback } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import { 
  Rocket, Phone, Mail, MessageCircle, Search, Users, TrendingUp,
  Play, Pause, RefreshCw, Eye, ChevronDown, ChevronRight, Filter,
  Globe, Target, Clock, Zap, BarChart3, ArrowUpRight
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const STATUS_CONFIG = {
  new: { label: 'New', color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
  scanned: { label: 'Scanned', color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
  called: { label: 'Called', color: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
  emailed: { label: 'Emailed', color: '#D4AF37', bg: 'rgba(212,175,55,0.1)' },
  whatsapp_sent: { label: 'WhatsApp', color: '#22c55e', bg: 'rgba(34,197,94,0.1)' },
  interested: { label: 'Interested', color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  signed_up: { label: 'Signed Up', color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
  not_interested: { label: 'Not Interested', color: '#6b7280', bg: 'rgba(107,114,128,0.1)' },
};

const StatCard = ({ label, value, icon: Icon, color, suffix }) => (
  <div className="p-4 rounded-xl border" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
    <div className="flex items-center gap-2 mb-2">
      <Icon className="size-4" style={{ color: color || '#D4AF37' }} />
      <span className="text-[10px] tracking-widest uppercase" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</span>
    </div>
    <div className="text-2xl font-bold font-mono" style={{ color: color || '#D4AF37' }}>{value}{suffix || ''}</div>
  </div>
);

const ScheduleItem = ({ time, task, active }) => (
  <div className={`flex items-center gap-3 py-2.5 px-3 rounded-lg transition-colors ${active ? 'border' : ''}`} 
    style={active ? { borderColor: 'rgba(212,175,55,0.3)', background: 'rgba(212,175,55,0.05)' } : {}}>
    <div className="w-16 text-[11px] font-mono font-bold" style={{ color: active ? '#D4AF37' : 'var(--aurem-body-secondary)' }}>{time}</div>
    <div className="flex-1 text-xs" style={{ color: active ? 'var(--aurem-heading)' : 'var(--aurem-body-secondary)' }}>{task}</div>
    {active && <div className="size-2 rounded-full bg-[#D4AF37] animate-pulse" />}
  </div>
);

const WA_BADGE_CONFIG = {
  twilio:         { label: 'Active (Twilio)',    color: '#4ADE80', bg: 'rgba(74,222,128,0.1)',  icon: '✓' },
  meta_cloud:     { label: 'Permanent',          color: '#4ADE80', bg: 'rgba(74,222,128,0.1)',  icon: '✓' },
  whapi:          { label: 'Active (Session)',   color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  icon: '●' },
  expired:        { label: 'Reconnect Required', color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   icon: '!' },
  not_connected:  { label: 'Not Connected',      color: '#6b7280', bg: 'rgba(107,114,128,0.1)', icon: '○' },
};

const LiveViewersPanel = ({ token }) => {
  const [viewers, setViewers] = useState([]);
  const [stats, setStats] = useState({ unique_ips_24h: 0, total_views_24h: 0 });
  const [checkedAt, setCheckedAt] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const fetchViewers = async () => {
      try {
        const r = await fetch(`${API_URL}/api/website-builder/live-viewers`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (r.ok) {
          const d = await r.json();
          if (!cancelled) {
            setViewers(d.viewers || []);
            setStats({ unique_ips_24h: d.unique_ips_24h || 0, total_views_24h: d.total_views_24h || 0 });
            setCheckedAt(d.checked_at);
          }
        }
      } catch {
        // silent
      }
    };
    fetchViewers();
    const poll = setInterval(fetchViewers, 5000);
    const counter = setInterval(() => setTick((t) => t + 1), 1000);
    return () => { cancelled = true; clearInterval(poll); clearInterval(counter); };
  }, [token]);

  // Compute live duration client-side (tick dependency intentional via state)
  const fmtDuration = (startedAt) => {
    if (!startedAt) return '0s';
    try {
      const started = new Date(startedAt).getTime();
      const secs = Math.max(0, Math.round((Date.now() - started) / 1000));
      if (secs < 60) return `${secs}s`;
      return `${Math.floor(secs / 60)}m ${secs % 60}s`;
    } catch { return '0s'; }
  };

  if (!viewers.length) {
    return (
      <div data-testid="live-viewers-empty"
        className="rounded-xl border p-4 mb-3"
        style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'var(--aurem-border)' }}>
        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="size-2 rounded-full" style={{ background: '#6b7280' }} />
          <div className="text-[11px] tracking-widest uppercase font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>
            Live Viewers · 0
          </div>
          <div className="text-[10px] font-mono" style={{ color: 'var(--aurem-body-secondary)' }}>
            <span data-testid="unique-ips-24h">{stats.unique_ips_24h} unique IPs</span> · <span data-testid="total-views-24h">{stats.total_views_24h} views</span> · last 24h
          </div>
          <div className="text-xs ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>
            5s polling · {checkedAt ? new Date(checkedAt).toLocaleTimeString() : '—'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="live-viewers-panel"
      className="rounded-xl border p-4 mb-3 relative overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, rgba(239,68,68,0.08), rgba(245,158,11,0.04))',
        borderColor: 'rgba(239,68,68,0.35)',
      }}>
      <div className="flex items-center gap-2.5 mb-3 flex-wrap">
        <div className="size-2.5 rounded-full animate-pulse" style={{ background: '#ef4444', boxShadow: '0 0 12px #ef4444' }} />
        <div className="text-[11px] tracking-widest uppercase font-bold" style={{ color: '#ef4444' }}>
          🔥 {viewers.length} HOT LEAD{viewers.length !== 1 ? 'S' : ''} — viewing right now
        </div>
        <div className="text-[10px] font-mono" style={{ color: 'var(--aurem-body-secondary)' }}>
          <span data-testid="unique-ips-24h">{stats.unique_ips_24h} IPs</span> · <span data-testid="total-views-24h">{stats.total_views_24h} views</span> · 24h
        </div>
        <div className="text-xs ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>
          Updates every 5s
        </div>
      </div>
      <div className="space-y-2">
        {viewers.map((v) => {
          const duration = fmtDuration(v.started_at);
          const isEngaged = v.engagement_nudge_fired;
          return (
            <div
              key={v.session_id}
              data-testid={`live-viewer-${v.slug}`}
              className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg border"
              style={{
                background: 'rgba(0,0,0,0.25)',
                borderColor: isEngaged ? 'rgba(74,222,128,0.35)' : 'rgba(239,68,68,0.3)',
              }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="size-8 rounded-full flex items-center justify-center shrink-0"
                  style={{ background: '#ef444422' }}>
                  <span className="text-sm animate-pulse">👀</span>
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-bold truncate" style={{ color: 'var(--aurem-heading)' }}>
                    {v.business_name}
                  </div>
                  <div className="text-[10px] truncate" style={{ color: 'var(--aurem-body-secondary)' }}>
                    is viewing their sample site · <span className="font-mono font-bold tabular-nums" style={{ color: '#f59e0b' }}>{duration}</span>
                    {isEngaged && <span className="ml-2" style={{ color: '#4ADE80' }}>· ✓ 30s nudge sent</span>}
                  </div>
                </div>
              </div>
              <a
                href={v.slug_url}
                target="_blank"
                rel="noopener noreferrer"
                data-testid={`live-viewer-${v.slug}-open`}
                className="shrink-0 text-[10px] font-bold px-2.5 py-1.5 rounded-md transition-all hover:scale-[1.03] flex items-center gap-1"
                style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.4)' }}
              >
                VIEW PAGE
                <ArrowUpRight className="size-3" />
              </a>
            </div>
          );
        })}
      </div>
      {/* hidden tick counter to drive re-render */}
      <span className="hidden">{tick}</span>
    </div>
  );
};

const PendingOpsBanner = ({ opsStatus, onDismiss, onRefresh }) => {
  if (!opsStatus || opsStatus.all_green) return null;
  const { channels, links, pending_count } = opsStatus;
  const rows = [
    {
      key: 'twilio',
      label: 'Twilio WhatsApp Business',
      channel: channels?.twilio_whatsapp,
      action: { label: 'Approve in Twilio', url: links?.twilio_whatsapp_approval },
    },
    {
      key: 'places',
      label: 'Google Places API (New)',
      channel: channels?.google_places,
      action: { label: 'Enable in GCP', url: links?.google_places_enable },
    },
  ];
  return (
    <div
      data-testid="pending-ops-banner"
      className="rounded-xl border p-4 mb-2"
      style={{
        background: 'linear-gradient(135deg, rgba(245,158,11,0.08), rgba(239,68,68,0.04))',
        borderColor: 'rgba(245,158,11,0.35)',
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg flex items-center justify-center"
            style={{ background: 'rgba(245,158,11,0.15)' }}>
            <Clock className="size-5" style={{ color: '#f59e0b' }} />
          </div>
          <div>
            <div className="text-[10px] tracking-widest uppercase font-bold"
              style={{ color: '#f59e0b' }}>
              Pending Ops · {pending_count} blocker{pending_count !== 1 ? 's' : ''}
            </div>
            <div className="text-sm font-semibold mt-0.5"
              style={{ color: 'var(--aurem-heading)' }}>
              External integrations awaiting your console approval
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            data-testid="ops-banner-refresh"
            className="p-1.5 rounded-md border transition-all hover:scale-[1.03]"
            style={{ borderColor: 'rgba(245,158,11,0.3)', color: '#f59e0b' }}
            title="Re-check status"
          >
            <RefreshCw className="size-3.5" />
          </button>
          <button
            onClick={onDismiss}
            data-testid="ops-banner-dismiss"
            className="px-2 py-1 rounded-md text-[10px] font-bold transition-all hover:scale-[1.03]"
            style={{ color: 'var(--aurem-body-secondary)', border: '1px solid var(--aurem-border)' }}
          >
            Dismiss
          </button>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
        {rows.map((r) => {
          const ok = r.channel?.ok;
          return (
            <div
              key={r.key}
              data-testid={`pending-op-${r.key}`}
              className="flex items-center justify-between rounded-lg border p-2.5"
              style={{
                borderColor: ok ? 'rgba(74,222,128,0.25)' : 'rgba(239,68,68,0.25)',
                background: ok ? 'rgba(74,222,128,0.05)' : 'rgba(239,68,68,0.04)',
              }}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span
                  className="text-base leading-none"
                  style={{ color: ok ? '#4ADE80' : '#ef4444' }}
                >
                  {ok ? '✓' : '✕'}
                </span>
                <div className="min-w-0">
                  <div className="text-xs font-semibold truncate"
                    style={{ color: 'var(--aurem-heading)' }}>{r.label}</div>
                  <div className="text-[10px] truncate"
                    style={{ color: 'var(--aurem-body-secondary)' }}
                    title={r.channel?.detail}>
                    {r.channel?.detail || 'Status unknown'}
                  </div>
                </div>
              </div>
              {!ok && r.action?.url && (
                <a
                  href={r.action.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid={`pending-op-${r.key}-action`}
                  className="shrink-0 text-[10px] font-bold px-2.5 py-1.5 rounded-md transition-all hover:scale-[1.03] flex items-center gap-1"
                  style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.35)' }}
                >
                  {r.action.label}
                  <ArrowUpRight className="size-3" />
                </a>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const WhatsAppChannelBadge = ({ status }) => {
  let mode = 'not_connected';
  if (status?.connected && status?.mode === 'twilio') mode = 'twilio';
  else if (status?.connected && status?.mode === 'meta_cloud') mode = 'meta_cloud';
  else if (status?.connected && status?.mode === 'whapi') mode = 'whapi';
  else if (status?.mode === 'whapi' && !status?.connected) mode = 'expired';
  const cfg = WA_BADGE_CONFIG[mode] || WA_BADGE_CONFIG.not_connected;
  return (
    <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border" data-testid="wa-channel-badge"
      style={{ background: cfg.bg, borderColor: `${cfg.color}30` }}>
      <MessageCircle className="size-4" style={{ color: cfg.color }} />
      <div>
        <p className="text-[11px] font-bold" style={{ color: cfg.color }}>WhatsApp {cfg.icon}</p>
        <p className="text-[9px]" style={{ color: cfg.color, opacity: 0.8 }}>{cfg.label}</p>
      </div>
    </div>
  );
};

const VoiceChannelBadge = () => {
  const hasTwilio = true; // creds are in env — always configured
  const cfg = hasTwilio
    ? { label: 'Voice Active', color: '#4ADE80', bg: 'rgba(74,222,128,0.1)', icon: '✓' }
    : { label: 'Not Configured', color: '#6b7280', bg: 'rgba(107,114,128,0.1)', icon: '○' };
  return (
    <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border" data-testid="voice-channel-badge"
      style={{ background: cfg.bg, borderColor: `${cfg.color}30` }}>
      <Phone className="size-4" style={{ color: cfg.color }} />
      <div>
        <p className="text-[11px] font-bold" style={{ color: cfg.color }}>Voice {cfg.icon}</p>
        <p className="text-[9px]" style={{ color: cfg.color, opacity: 0.8 }}>{cfg.label}</p>
      </div>
    </div>
  );
};

/**
 * VerificationBadge — shows Accurate Scout confidence + channel gating per lead.
 * Clicking "Verify Now" on unverified leads triggers /api/scout/verify/lead.
 */
const CONF_COLORS = {
  HIGH:   { color: '#4ADE80', bg: 'rgba(74,222,128,0.15)',  dot: '🟢' },
  MEDIUM: { color: '#F59E0B', bg: 'rgba(245,158,11,0.15)',  dot: '🟡' },
  LOW:    { color: '#EF4444', bg: 'rgba(239,68,68,0.15)',   dot: '🔴' },
  NONE:   { color: '#6B7280', bg: 'rgba(107,114,128,0.1)',  dot: '⚪' },
};

const VerificationBadge = ({ lead, onVerify, verifying }) => {
  const v = lead.verification;
  if (!v) {
    return (
      <button
        onClick={onVerify}
        disabled={verifying}
        data-testid={`verify-btn-${lead.lead_id}`}
        className="px-2 py-0.5 rounded text-[10px] font-semibold hover:scale-[1.02] transition-all border"
        style={{
          background: verifying ? 'rgba(212,175,55,0.05)' : 'rgba(212,175,55,0.12)',
          borderColor: 'rgba(212,175,55,0.35)',
          color: '#D4AF37',
          opacity: verifying ? 0.55 : 1,
          cursor: verifying ? 'wait' : 'pointer',
        }}
        title="Run multi-source accuracy check before outreach"
      >
        {verifying ? '⏳ Verifying…' : '⚡ Verify Now'}
      </button>
    );
  }
  const phoneConf = (v.phone_confidence || 'NONE').toUpperCase();
  const emailConf = (v.email_confidence || 'NONE').toUpperCase();
  const pc = CONF_COLORS[phoneConf] || CONF_COLORS.NONE;
  const ec = CONF_COLORS[emailConf] || CONF_COLORS.NONE;
  const gate = v.channel_gating || {};
  const srcCount = v.source_count || 0;
  const tooltip = (
    `Phone: ${phoneConf} (${srcCount} sources)\n` +
    `Email: ${emailConf}\n` +
    `Channels: ${gate.call ? '📞' : '🛑'} call · ${gate.sms ? '💬' : '🛑'} sms · ` +
    `${gate.whatsapp ? '📱' : '🛑'} wa · ${gate.email ? '📧' : '🛑'} email`
  );
  return (
    <div className="flex flex-col gap-1" title={tooltip} data-testid={`verify-badge-${lead.lead_id}`}>
      <div className="flex items-center gap-1">
        <span
          className="px-1.5 py-0.5 rounded text-[9px] font-bold"
          style={{ background: pc.bg, color: pc.color, border: `1px solid ${pc.color}40` }}>
          {pc.dot} {phoneConf.charAt(0)}{phoneConf.slice(1).toLowerCase()} · {srcCount}
        </span>
      </div>
      <div className="flex items-center gap-0.5 text-[9px]">
        <span style={{ color: gate.call ? '#4ADE80' : '#6B7280' }} title={`Call ${gate.call ? 'OK' : 'blocked'}`}>📞{gate.call ? '✓' : '✕'}</span>
        <span style={{ color: gate.sms ? '#4ADE80' : '#6B7280' }} title={`SMS ${gate.sms ? 'OK' : 'blocked'}`}>💬{gate.sms ? '✓' : '✕'}</span>
        <span style={{ color: gate.whatsapp ? '#4ADE80' : '#6B7280' }} title={`WhatsApp ${gate.whatsapp ? 'OK' : 'blocked'}`}>📱{gate.whatsapp ? '✓' : '✕'}</span>
        <span style={{ color: gate.email ? '#4ADE80' : '#6B7280' }} title={`Email ${gate.email ? 'OK' : 'blocked'}`}>📧{gate.email ? '✓' : '✕'}</span>
      </div>
    </div>
  );
};

const CampaignDashboard = ({ token }) => {
  const [overview, setOverview] = useState(null);
  const [stats, setStats] = useState(null);
  const [leads, setLeads] = useState([]);
  const [leadsTotal, setLeadsTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [scraping, setScraping] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [waChannelStatus, setWaChannelStatus] = useState(null);
  const [opsStatus, setOpsStatus] = useState(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [blastingLead, setBlastingLead] = useState(null);
  const [blastResult, setBlastResult] = useState(null);
  const [verifyingLead, setVerifyingLead] = useState(null);
  const [verifiedMap, setVerifiedMap] = useState({}); // lead_id → verification sub-doc

  // Adaptive ORA mode (shadow / automation)
  const [oraMode, setOraMode] = useState('shadow');
  const [oraBuckets, setOraBuckets] = useState({});
  const [oraModeBusy, setOraModeBusy] = useState(false);
  const [oraActivity, setOraActivity] = useState(null);
  const [showActivity, setShowActivity] = useState(false);

  // ══════════════ Auto-Blast Engine ══════════════
  const [autoBlast, setAutoBlast] = useState(null);
  const [autoBlastBusy, setAutoBlastBusy] = useState(false);
  // 🔴🟢 DB-verified status (separate from UI optimistic state)
  const [autoBlastDbVerified, setAutoBlastDbVerified] = useState(null); // null | true | false
  const [autoBlastLastSync, setAutoBlastLastSync] = useState(null);
  const [autoBlastError, setAutoBlastError] = useState(null);

  const fetchAutoBlast = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${API_URL}/api/campaign/auto-blast/status`, { headers });
      if (!r.ok) {
        setAutoBlastError(`Status fetch HTTP ${r.status}`);
        setAutoBlastDbVerified(null);
        return;
      }
      const data = await r.json();
      setAutoBlast(data);
      setAutoBlastDbVerified(!!data.enabled); // truth from DB
      setAutoBlastLastSync(new Date());
      setAutoBlastError(null);
    } catch (e) {
      setAutoBlastError(`Network: ${e.message}`);
      setAutoBlastDbVerified(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const toggleAutoBlast = async () => {
    if (!autoBlast) return;
    const next = !autoBlast.enabled;
    const msg = next
      ? `⚡ Enable AUTO-BLAST Engine?\n\n• Every 5 min the engine will auto-verify + fire 4-channel outreach on new leads\n• ${autoBlast.queued_leads || 0} leads currently queued\n• Max ${autoBlast.max_per_cycle || 10} leads per cycle\n• Respects DNC list + channel gates\n\nProceed?`
      : 'Disable AUTO-BLAST? New leads will wait for manual "Blast All 4" clicks.';
    if (!window.confirm(msg)) return;
    setAutoBlastBusy(true);
    setAutoBlastError(null);
    try {
      const r = await fetch(`${API_URL}/api/campaign/auto-blast/toggle`, {
        method: 'POST', headers, body: JSON.stringify({ enabled: next }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok || !body.ok) {
        throw new Error(body.detail || body.error || `HTTP ${r.status}`);
      }
      // Force re-read from DB and confirm persistence
      await fetchAutoBlast();
      // Double-check: fetch again after 500ms to catch replication delay
      await new Promise((res) => setTimeout(res, 500));
      const r2 = await fetch(`${API_URL}/api/campaign/auto-blast/status`, { headers });
      const data2 = r2.ok ? await r2.json() : null;
      if (data2 && data2.enabled !== next) {
        setAutoBlastError(`⚠️ DB not persisted! Expected ${next ? 'ON' : 'OFF'}, got ${data2.enabled ? 'ON' : 'OFF'}`);
      } else if (data2) {
        setAutoBlast(data2);
        setAutoBlastDbVerified(!!data2.enabled);
      }
    } catch (e) {
      setAutoBlastError(`Toggle FAILED: ${e.message}`);
      window.alert(`Toggle failed: ${e.message}\n\nDB state NOT changed. Check console.`);
    }
    setAutoBlastBusy(false);
  };

  const runAutoBlastNow = async () => {
    if (!window.confirm('Fire ONE auto-blast cycle immediately? This will verify + blast up to 10 queued leads right now.')) return;
    setAutoBlastBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/campaign/auto-blast/run-now`, {
        method: 'POST', headers,
      });
      const d = await r.json();
      window.alert(d.ok
        ? `✓ Cycle complete\nProcessed: ${d.total_processed}\nChannels sent: ${d.total_sent}`
        : `Failed: ${d.error || 'unknown'}`);
      await fetchAutoBlast();
      await fetchLeads();
      await fetchData();
    } catch (e) {
      window.alert(`Network: ${e.message}`);
    }
    setAutoBlastBusy(false);
  };

  const fetchOraConfig = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${API_URL}/api/conviction/config`, { headers });
      if (!r.ok) return;
      const d = await r.json();
      setOraMode(d.mode || 'shadow');
      setOraBuckets(d.bucket_counts || {});
    } catch { /* silent */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const fetchOraActivity = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${API_URL}/api/conviction/activity?limit=30`, { headers });
      if (!r.ok) return;
      const d = await r.json();
      setOraActivity(d);
    } catch { /* silent */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const toggleOraMode = async () => {
    const next = oraMode === 'automation' ? 'shadow' : 'automation';
    const msg = next === 'automation'
      ? '⚠️ Enable Adaptive ORA AUTOMATION?\n\n• Hot leads (score ≥90) auto-handoff to Closer and wake the agent.\n• Cold leads (score <20) auto-halt (do_not_contact).\n\nFlip back to Shadow anytime.'
      : 'Switch back to SHADOW mode?\n\nScores keep updating but no agents auto-fire.';
    if (!window.confirm(msg)) return;
    setOraModeBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/conviction/config`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ mode: next }),
      });
      const d = await r.json();
      if (r.ok && d.mode) {
        setOraMode(d.mode);
        await fetchOraConfig();
      } else {
        window.alert(`Switch failed: ${d.detail || 'unknown'}`);
      }
    } catch (e) {
      window.alert(`Network: ${e.message}`);
    }
    setOraModeBusy(false);
  };

  // ══════════════════════════════════════════════
  // Active Hunt Banner — SSE subscription
  // ══════════════════════════════════════════════
  const [activeHunt, setActiveHunt] = useState(null);

  useEffect(() => {
    let clientId = sessionStorage.getItem('aurem_sse_client_id');
    if (!clientId) {
      clientId = `hq_${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem('aurem_sse_client_id', clientId);
    }
    const es = new EventSource(`${API_URL}/api/admin/events/${clientId}`);
    es.onmessage = (evt) => {
      let p; try { p = JSON.parse(evt.data); } catch { return; }
      if (p?.type !== 'hunt_progress') return;
      const d = p.data || {};
      if (!d.hunt_id) return;
      setActiveHunt((prev) => {
        const base = prev && prev.hunt_id === d.hunt_id ? prev : {
          hunt_id: d.hunt_id,
          city: d.data?.city || prev?.city,
          industry: d.data?.industry || prev?.industry,
          total: d.data?.count || d.data?.total || prev?.total || 0,
          done: 0,
          campaignsSent: 0,
          finished: false,
          startedAt: Date.now(),
        };
        let next = { ...base };
        if (d.step === 'hunt' && d.data?.done != null) next.done = d.data.done;
        if (d.step === 'hunt' && d.data?.total) next.total = d.data.total;
        if (d.step === 'hunt' && d.data?.city) next.city = d.data.city;
        if (d.step === 'hunt' && d.data?.industry) next.industry = d.data.industry;
        if ((d.step === 'email' || d.step === 'whatsapp' || d.step === 'sms' || d.step === 'call') && d.status === 'ok') {
          next.campaignsSent = (next.campaignsSent || 0) + 1;
        }
        if (d.step === 'hunt' && d.status === 'complete') next.finished = true;
        return next;
      });
    };
    es.onerror = () => { /* auto-reconnect */ };
    return () => { try { es.close(); } catch { /* noop */ } };
  }, []);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = useCallback(async () => {
    if (!token) return;
    try {
      const [ovRes, stRes, waRes, opsRes] = await Promise.all([
        fetch(`${API_URL}/api/campaign/overview`, { headers }),
        fetch(`${API_URL}/api/campaign/stats`, { headers }),
        fetch(`${API_URL}/api/integrations/polaris-built-001/whatsapp/status`, { headers }),
        fetch(`${API_URL}/api/campaign/ops-status`, { headers }),
      ]);
      if (ovRes.ok) setOverview(await ovRes.json());
      if (stRes.ok) setStats(await stRes.json());
      if (waRes.ok) setWaChannelStatus(await waRes.json());
      if (opsRes.ok) setOpsStatus(await opsRes.json());
    } catch (e) { console.error('Campaign fetch error:', e); }
    setLoading(false);
  }, [token]);

  const fetchLeads = useCallback(async () => {
    if (!token) return;
    const params = new URLSearchParams({ page, limit: 25 });
    if (statusFilter) params.set('status', statusFilter);
    if (searchQuery) params.set('search', searchQuery);
    try {
      const res = await fetch(`${API_URL}/api/campaign/leads?${params}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads || []);
        setLeadsTotal(data.total || 0);
      }
    } catch (e) { console.error('Leads fetch error:', e); }
  }, [token, page, statusFilter, searchQuery]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchLeads(); }, [fetchLeads]);
  useEffect(() => { fetchAutoBlast(); }, [fetchAutoBlast]);
  useEffect(() => {
    fetchOraConfig();
    fetchOraActivity();
    const p = setInterval(() => { fetchOraConfig(); fetchOraActivity(); }, 30000);
    return () => clearInterval(p);
  }, [fetchOraConfig, fetchOraActivity]);

  // iter 270 — keep Campaign Leads + overview auto-refreshing (10s)
  // Pauses when tab hidden, re-fetches on focus + reconnect.
  useLivePolling(fetchData, 10000);
  useLivePolling(fetchLeads, 10000);
  useLivePolling(fetchAutoBlast, 15000);

  const seedAurem = async () => {
    setSeeding(true);
    try {
      await fetch(`${API_URL}/api/campaign/seed-aurem`, { method: 'POST', headers });
      await fetchData();
    } catch (e) { console.error(e); }
    setSeeding(false);
  };

  const handleScrape = async () => {
    setScraping(true);
    try {
      await fetch(`${API_URL}/api/campaign/scrape`, {
        method: 'POST', headers,
        body: JSON.stringify({ location: 'Mississauga, Ontario', category: 'hair salon', limit: 10 }),
      });
      await fetchLeads();
      await fetchData();
    } catch (e) { console.error(e); }
    setScraping(false);
  };

  const toggleCampaign = async () => {
    const action = overview?.campaign?.status === 'active' ? 'pause' : 'resume';
    try {
      await fetch(`${API_URL}/api/campaign/${action}`, { method: 'POST', headers });
      await fetchData();
    } catch (e) { console.error(e); }
  };

  const blastAll = async (leadId, businessName) => {
    if (!window.confirm(`Send AUREM outreach across all 4 channels (Email, SMS, WhatsApp, Voice) to ${businessName}?`)) return;
    setBlastingLead(leadId);
    setBlastResult(null);
    try {
      const res = await fetch(`${API_URL}/api/campaign/leads/${leadId}/blast-all`, {
        method: 'POST', headers, body: JSON.stringify({}),
      });
      const data = await res.json();
      setBlastResult({ leadId, businessName, ...data });
      await fetchLeads();
    } catch (e) {
      setBlastResult({ leadId, businessName, error: String(e) });
    }
    setBlastingLead(null);
  };

  const verifyLead = async (leadId) => {
    setVerifyingLead(leadId);
    try {
      const res = await fetch(`${API_URL}/api/scout/verify/lead/${leadId}`, {
        method: 'POST', headers,
      });
      if (res.ok) {
        const data = await res.json();
        const c = data.consolidated || {};
        setVerifiedMap((prev) => ({
          ...prev,
          [leadId]: {
            phone_confidence: (c.phone || {}).confidence,
            email_confidence: (c.email || {}).confidence,
            phone_sources: ((c.phone || {}).sources) || [],
            channel_gating: data.channel_gating || {},
            source_count: (data.sources_used || []).length,
            verified_at: data.verified_at,
          },
        }));
        await fetchLeads();
      }
    } catch (_) { /* silent */ }
    setVerifyingLead(null);
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center" style={{ background: 'transparent' }}>
      <div className="size-8 border-2 border-[#D4AF37]/20 rounded-full border-t-[#D4AF37] animate-spin" />
    </div>
  );

  const campaign = overview?.campaign;
  const byStatus = overview?.leads_summary?.by_status || {};
  const schedule = overview?.today_schedule || [];
  const campaignStats = stats?.stats || {};
  const isActive = campaign?.status === 'active';

  // Determine current schedule item based on time
  const now = new Date();
  const hour = now.getHours();
  let activeScheduleIdx = -1;
  if (hour >= 9 && hour < 10) activeScheduleIdx = 0;
  else if (hour >= 10 && hour < 11) activeScheduleIdx = 1;
  else if (hour >= 11 && hour < 14) activeScheduleIdx = 2;
  else if (hour >= 14 && hour < 16) activeScheduleIdx = 3;
  else if (hour >= 16 && hour < 17) activeScheduleIdx = 4;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="campaign-dashboard">
      {/* ═══ Auto-Blast Engine Banner ═══ */}
      {autoBlast && (
        <div
          data-testid="auto-blast-banner"
          className={`rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
            autoBlast.enabled ? 'border border-[#D4AF37]/50' : 'border border-white/10'
          }`}
          style={{
            background: autoBlast.enabled
              ? 'linear-gradient(90deg, rgba(212,175,55,0.12), rgba(255,107,0,0.05))'
              : 'linear-gradient(90deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))',
            animation: 'auremFadeSlideIn 0.3s ease both',
          }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <Zap className="size-5" style={{ color: autoBlast.enabled ? '#D4AF37' : 'rgba(255,255,255,0.4)' }} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-bold tracking-[1.5px] uppercase" style={{ color: 'var(--aurem-heading)' }}>
                  Auto-Blast Engine
                </span>
                <span
                  className={`text-[9px] font-black px-2 py-0.5 rounded-full tracking-wider ${
                    autoBlast.enabled ? 'bg-[#D4AF37] text-black' : 'bg-white/15 text-white/85'
                  }`}
                  data-testid="auto-blast-mode-badge"
                >
                  {autoBlast.enabled ? 'AUTO FIRING' : 'MANUAL'}
                </span>
                {/* 🔴🟢 DB-verified status — shows ACTUAL MongoDB state, not optimistic UI */}
                <span
                  className="flex items-center gap-1 text-[9px] font-bold tracking-wider px-2 py-0.5 rounded-full"
                  data-testid="auto-blast-db-status"
                  title={autoBlastError || `DB last synced: ${autoBlastLastSync ? autoBlastLastSync.toLocaleTimeString() : 'never'}`}
                  style={{
                    background: autoBlastDbVerified === null
                      ? 'rgba(255,255,255,0.08)'
                      : autoBlastDbVerified
                        ? 'rgba(34,197,94,0.18)'
                        : 'rgba(239,68,68,0.15)',
                    border: `1px solid ${autoBlastDbVerified === null ? 'rgba(255,255,255,0.15)' : autoBlastDbVerified ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.35)'}`,
                    color: autoBlastDbVerified === null ? 'rgba(255,255,255,0.6)' : autoBlastDbVerified ? '#22c55e' : '#ef4444',
                  }}
                >
                  <span
                    className={`size-1.5 rounded-full ${autoBlastDbVerified ? 'animate-pulse' : ''}`}
                    style={{
                      background: autoBlastDbVerified === null
                        ? 'rgba(255,255,255,0.4)'
                        : autoBlastDbVerified ? '#22c55e' : '#ef4444',
                      boxShadow: autoBlastDbVerified
                        ? '0 0 6px #22c55e'
                        : autoBlastDbVerified === false ? '0 0 6px #ef4444' : 'none',
                    }}
                  />
                  DB {autoBlastDbVerified === null ? '…' : autoBlastDbVerified ? 'ON' : 'OFF'}
                </span>
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {autoBlast.queued_leads} queued · {autoBlast.blasted_leads} blasted · {autoBlast.max_per_cycle}/cycle
                </span>
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
                {autoBlastError ? (
                  <span style={{ color: '#f87171' }}>⚠ {autoBlastError}</span>
                ) : autoBlast.enabled
                  ? `ORA auto-verifies + blasts 4 channels every ${autoBlast.interval_minutes} min. Last run: ${autoBlast.last_run_at ? new Date(autoBlast.last_run_at).toLocaleTimeString() : 'pending'}`
                  : 'Manual mode — click "Blast All 4" per lead. Enable to let ORA fire automatically.'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={runAutoBlastNow}
              disabled={autoBlastBusy}
              data-testid="auto-blast-run-now-btn"
              className="text-[10px] px-3 py-1.5 rounded-md font-bold uppercase tracking-wider transition hover:scale-[1.03] disabled:opacity-40"
              style={{ background: 'rgba(255,107,0,0.15)', color: '#FF6B00', border: '1px solid rgba(255,107,0,0.3)' }}
            >
              Run Once
            </button>
            <button
              onClick={toggleAutoBlast}
              disabled={autoBlastBusy}
              data-testid="auto-blast-toggle-btn"
              className="text-[10px] px-3 py-1.5 rounded-md font-bold uppercase tracking-wider transition hover:scale-[1.03] disabled:opacity-40"
              style={{
                background: autoBlast.enabled ? 'linear-gradient(135deg,#D4AF37,#A08028)' : 'rgba(212,175,55,0.15)',
                color: autoBlast.enabled ? '#050507' : '#D4AF37',
                border: `1px solid ${autoBlast.enabled ? '#D4AF37' : 'rgba(212,175,55,0.3)'}`,
              }}
            >
              {autoBlastBusy ? '…' : autoBlast.enabled ? 'Disable Auto' : 'Enable Auto'}
            </button>
          </div>
        </div>
      )}

      {/* ═══ Adaptive ORA Mode Banner ═══ */}
      <div
        data-testid="adaptive-ora-banner"
        className={`rounded-xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
          oraMode === 'automation'
            ? 'border border-amber-500/40'
            : 'border border-white/10'
        }`}
        style={{
          background: oraMode === 'automation'
            ? 'linear-gradient(90deg, rgba(245,158,11,0.10), rgba(239,68,68,0.04))'
            : 'linear-gradient(90deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))',
          animation: 'auremFadeSlideIn 0.3s ease both',
        }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xl">{oraMode === 'automation' ? '🤖' : '👁'}</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold tracking-[1.5px] uppercase" style={{ color: 'var(--aurem-heading)' }}>
                Adaptive ORA
              </span>
              <span
                className={`text-[9px] font-black px-2 py-0.5 rounded-full tracking-wider ${
                  oraMode === 'automation' ? 'bg-amber-500 text-white' : 'bg-white/15 text-white/85'
                }`}
                data-testid="adaptive-ora-mode-badge"
              >
                {oraMode === 'automation' ? 'AUTO FIRING' : 'SHADOW'}
              </span>
            </div>
            <div className="text-[11px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
              {oraMode === 'automation'
                ? 'Hot leads auto-handoff to Closer, cold leads auto-halt.'
                : 'Scores computed silently — no agents auto-fire.'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* bucket counts */}
          <div className="flex items-center gap-2.5 flex-wrap text-[11px] font-mono">
            {[
              { k: 'CLOSER_NOW', e: '🔥' },
              { k: 'INTENSIFY',  e: '⚡' },
              { k: 'CONTINUE',   e: '✓' },
              { k: 'SLOW',       e: '⏳' },
              { k: 'HALT',       e: '○' },
            ].map((b) => (
              <span key={b.k} className="opacity-80" data-testid={`bucket-count-${b.k}`}>
                {b.e} {oraBuckets[b.k] || 0}
              </span>
            ))}
          </div>
          {/* 24h activity pills — only meaningful in automation mode */}
          {oraMode === 'automation' && oraActivity?.summary && (
            <div className="flex items-center gap-2 text-[10px] font-bold tracking-wider">
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" data-testid="ora-handoffs-24h">
                🔥 {oraActivity.summary.handoffs_24h} HANDOFFS/24h
              </span>
              <span className="px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/30" data-testid="ora-halts-24h">
                ○ {oraActivity.summary.halts_24h} HALTS/24h
              </span>
            </div>
          )}
          <button
            onClick={() => setShowActivity(!showActivity)}
            data-testid="toggle-ora-activity"
            className="text-[10px] font-bold tracking-wider px-2 py-1 rounded-md transition-all"
            style={{
              background: showActivity ? 'rgba(255,107,0,0.18)' : 'rgba(255,255,255,0.06)',
              border: `1px solid ${showActivity ? 'rgba(255,107,0,0.4)' : 'rgba(255,255,255,0.1)'}`,
              color: showActivity ? '#FF6B00' : 'var(--aurem-heading)',
            }}
            title="View recent auto-fire / auto-halt events"
          >
            {showActivity ? '▾ Hide Feed' : '▸ View Feed'}
          </button>
          <button
            onClick={toggleOraMode}
            disabled={oraModeBusy}
            data-testid="adaptive-ora-toggle-btn"
            className={`relative inline-flex h-7 w-14 shrink-0 rounded-full border-2 transition-colors duration-200 ${
              oraMode === 'automation'
                ? 'bg-amber-500 border-amber-500'
                : 'bg-white/10 border-white/25'
            } ${oraModeBusy ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
            aria-label="Toggle Adaptive ORA automation"
          >
            <span
              className={`pointer-events-none inline-block size-5 transform rounded-full bg-white shadow transition duration-200 ${
                oraMode === 'automation' ? 'translate-x-7' : 'translate-x-0.5'
              } mt-[1px]`}
            />
          </button>
        </div>
      </div>

      {/* ═══ Adaptive ORA Activity Feed ═══ */}
      {showActivity && (
        <div
          data-testid="ora-activity-feed"
          className="rounded-xl border border-white/10 p-3 sm:p-4"
          style={{
            background: 'linear-gradient(180deg, rgba(255,107,0,0.04), rgba(0,0,0,0.15))',
            animation: 'auremFadeSlideIn 0.25s ease both',
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-heading)' }}>
                Automation Activity
              </span>
              <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                last {oraActivity?.window_hours || 72}h · auto-refresh 30s
              </span>
            </div>
            <button
              onClick={fetchOraActivity}
              className="text-[10px] font-bold px-2 py-1 rounded-md hover:opacity-80"
              style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--aurem-heading)' }}
              data-testid="refresh-ora-activity"
            >
              ↻ Refresh
            </button>
          </div>

          {(!oraActivity || oraActivity.events?.length === 0) ? (
            <div className="text-center py-8 text-[11px]" style={{ color: 'var(--aurem-body-secondary)' }}>
              {oraMode === 'automation'
                ? 'No auto-fires or auto-halts yet in this window. Events will appear here as leads cross bucket thresholds.'
                : '(Shadow mode — enable automation to see auto-actions appear here.)'}
            </div>
          ) : (
            <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
              {oraActivity.events.map((ev, i) => {
                const isHot = ev.type === 'closer_handoff';
                const icon = isHot ? '🔥' : '○';
                const color = isHot ? '#22C55E' : '#EF4444';
                const label = isHot ? 'HANDED TO CLOSER' : 'AUTO-HALTED';
                const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '—';
                return (
                  <div
                    key={`${ev.lead_id}-${ev.timestamp}-${i}`}
                    className="flex items-center gap-3 p-2 rounded-lg"
                    style={{ background: 'rgba(255,255,255,0.03)' }}
                    data-testid={`activity-row-${i}`}
                  >
                    <span className="text-base flex-shrink-0">{icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-black tracking-wider" style={{ color }}>{label}</span>
                        <span className="text-xs font-semibold truncate" style={{ color: 'var(--aurem-heading)', maxWidth: '28ch' }}>
                          {ev.business_name || ev.lead_id}
                        </span>
                      </div>
                      <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        score {Math.round(ev.score || 0)} · {ev.reason} · {ts}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══ Active Hunt Banner — appears when a hunt is in flight ═══ */}
      {activeHunt && (
        <div
          data-testid="active-hunt-banner"
          className="rounded-xl p-4 flex items-center justify-between gap-4"
          style={{
            border: activeHunt.finished ? '1px solid rgba(27,94,58,0.35)' : '1px solid rgba(255,107,0,0.45)',
            background: activeHunt.finished
              ? 'linear-gradient(90deg, rgba(27,94,58,0.08), rgba(27,94,58,0.02))'
              : 'linear-gradient(90deg, rgba(255,107,0,0.12), rgba(255,107,0,0.02))',
            animation: 'auremFadeSlideIn 0.3s ease both',
          }}
        >
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span
              className="inline-flex size-2.5 rounded-full flex-shrink-0"
              style={{
                background: activeHunt.finished ? '#1B5E3A' : '#FF6B00',
                animation: activeHunt.finished ? 'none' : 'pulse 1s ease-in-out infinite',
                boxShadow: activeHunt.finished ? 'none' : '0 0 8px rgba(255,107,0,0.6)',
              }}
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold truncate" style={{ color: 'var(--aurem-heading)' }}>
                {activeHunt.finished ? '🏁 Hunt Complete' : '🔄 Hunt in progress'}: {activeHunt.industry} in {activeHunt.city}
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
                {activeHunt.done || 0}/{activeHunt.total || '?'} scouted · {activeHunt.campaignsSent || 0} campaigns sent
              </div>
            </div>
            {activeHunt.total > 0 && (
              <div className="w-40 h-1.5 rounded-full overflow-hidden flex-shrink-0" style={{ background: 'rgba(27,94,58,0.1)' }}>
                <div
                  className="h-full transition-all duration-500"
                  data-testid="active-hunt-progress-bar"
                  style={{
                    width: `${Math.round(((activeHunt.done || 0) / activeHunt.total) * 100)}%`,
                    background: 'linear-gradient(90deg, #FF6B00, #1B5E3A)',
                  }}
                />
              </div>
            )}
          </div>
          {activeHunt.finished && (
            <button
              onClick={() => setActiveHunt(null)}
              data-testid="active-hunt-dismiss-btn"
              className="text-xs opacity-60 hover:opacity-100 underline flex-shrink-0"
            >
              dismiss
            </button>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }} data-testid="campaign-title">
            AUREM Acquisition Campaign
          </h1>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            {campaign ? `Started: ${new Date(campaign.created_at).toLocaleDateString()} | Status: ` : 'Campaign not initialized | '}
            <span className={`font-bold ${isActive ? 'text-green-400' : 'text-yellow-500'}`}>
              {isActive ? 'Live' : campaign ? 'Paused' : 'Not Started'}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!campaign && (
            <button onClick={seedAurem} disabled={seeding} data-testid="seed-aurem-btn"
              className="px-4 py-2 rounded-lg text-xs font-bold tracking-wider transition-all hover:scale-[1.02]"
              style={{ background: 'linear-gradient(135deg, #D4AF37, #A08028)', color: '#050507' }}>
              {seeding ? 'Initializing...' : 'Initialize Campaign'}
            </button>
          )}
          {campaign && (
            <>
              <button onClick={handleScrape} disabled={scraping} data-testid="scrape-btn"
                className="px-3 py-2 rounded-lg text-[11px] font-bold border transition-all hover:scale-[1.02]"
                style={{ borderColor: 'rgba(212,175,55,0.3)', color: '#D4AF37' }}>
                <Search className="size-3 inline mr-1" />
                {scraping ? 'Scraping...' : 'Scout Now'}
              </button>
              <button onClick={toggleCampaign} data-testid="toggle-campaign-btn"
                className="px-3 py-2 rounded-lg text-[11px] font-bold transition-all hover:scale-[1.02]"
                style={{ background: isActive ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)', color: isActive ? '#ef4444' : '#22c55e', border: `1px solid ${isActive ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}` }}>
                {isActive ? <><Pause className="size-3 inline mr-1" />Pause</> : <><Play className="size-3 inline mr-1" />Resume</>}
              </button>
              <button onClick={() => { fetchData(); fetchLeads(); }} data-testid="refresh-campaign-btn"
                className="p-2 rounded-lg border transition-all hover:scale-[1.02]"
                style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>
                <RefreshCw className="size-3.5" />
              </button>
            </>
          )}
        </div>
      </div>

      {!bannerDismissed && (
        <PendingOpsBanner
          opsStatus={opsStatus}
          onDismiss={() => setBannerDismissed(true)}
          onRefresh={fetchData}
        />
      )}

      <LiveViewersPanel token={token} />

      {/* Channel Status Badges */}
      <div className="flex flex-wrap gap-3" data-testid="channel-badges">
        <WhatsAppChannelBadge status={waChannelStatus} />
        <VoiceChannelBadge />
      </div>

      {/* Pipeline Stats */}
      <div>
        <h2 className="text-sm font-bold tracking-widest uppercase mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>Leads Pipeline</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3" data-testid="pipeline-stats">
          <StatCard label="Scraped" value={campaignStats.leads_scraped || 0} icon={Search} color="#6366f1" />
          <StatCard label="Scanned" value={campaignStats.websites_scanned || 0} icon={Globe} color="#8b5cf6" />
          <StatCard label="Called" value={campaignStats.calls_made || 0} icon={Phone} color="#3b82f6" />
          <StatCard label="Emailed" value={campaignStats.emails_sent || 0} icon={Mail} color="#D4AF37" />
          <StatCard label="WhatsApp" value={campaignStats.whatsapp_sent || 0} icon={MessageCircle} color="#22c55e" />
          <StatCard label="Total Leads" value={overview?.leads_summary?.total || 0} icon={Users} color="#f59e0b" />
        </div>
      </div>

      {/* Results + Schedule Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Results */}
        <div className="lg:col-span-2 p-5 rounded-xl border" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="campaign-results">
          <h3 className="text-sm font-bold tracking-widest uppercase mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>Results</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Answered Calls</p>
              <p className="text-xl font-bold font-mono" style={{ color: 'var(--aurem-heading)' }}>{campaignStats.calls_answered || 0}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Email Opens</p>
              <p className="text-xl font-bold font-mono" style={{ color: 'var(--aurem-heading)' }}>
                {campaignStats.email_opens || 0} <span className="text-xs text-[#D4AF37]">({stats?.email_open_rate || 0}%)</span>
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Replies</p>
              <p className="text-xl font-bold font-mono" style={{ color: 'var(--aurem-heading)' }}>{campaignStats.replies_received || 0}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Reports Sent</p>
              <p className="text-xl font-bold font-mono" style={{ color: 'var(--aurem-heading)' }}>{campaignStats.reports_sent || 0}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Demo Requests</p>
              <p className="text-xl font-bold font-mono text-[#f59e0b]">{campaignStats.demo_requests || 0}</p>
            </div>
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Signups</p>
              <p className="text-xl font-bold font-mono text-[#10b981]">{campaignStats.signups || 0}</p>
            </div>
            <div className="space-y-1 md:col-span-3 pt-3 border-t" style={{ borderColor: 'var(--aurem-border)' }}>
              <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>Revenue</p>
              <p className="text-2xl font-bold font-mono text-[#D4AF37]">${(campaignStats.revenue_cad || 0).toLocaleString()} <span className="text-xs">CAD</span></p>
            </div>
          </div>
        </div>

        {/* Today's Schedule */}
        <div className="p-5 rounded-xl border" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="campaign-schedule">
          <h3 className="text-sm font-bold tracking-widest uppercase mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>
            <Clock className="size-3.5 inline mr-1" /> Today's Schedule
          </h3>
          <div className="space-y-1">
            {schedule.map((item, i) => (
              <ScheduleItem key={i} time={item.time} task={item.task} active={i === activeScheduleIdx} />
            ))}
          </div>
        </div>
      </div>

      {/* Status Breakdown */}
      <div className="flex flex-wrap gap-2" data-testid="status-breakdown">
        {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
          <button key={key} onClick={() => setStatusFilter(statusFilter === key ? '' : key)}
            className={`px-3 py-1.5 rounded-full text-[11px] font-bold transition-all ${statusFilter === key ? 'ring-2 ring-[#D4AF37]' : ''}`}
            style={{ background: cfg.bg, color: cfg.color }}
            data-testid={`filter-${key}`}>
            {cfg.label}: {byStatus[key] || 0}
          </button>
        ))}
      </div>

      {/* Leads Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="leads-table">
        <div className="p-4 flex items-center justify-between border-b" style={{ borderColor: 'var(--aurem-border)' }}>
          <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Campaign Leads ({leadsTotal})</h3>
          <div className="relative">
            <Search className="size-3.5 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--aurem-body-secondary)' }} />
            <input
              type="text" placeholder="Search leads..." value={searchQuery}
              onChange={e => { setSearchQuery(e.target.value); setPage(1); }}
              className="pl-9 pr-3 py-1.5 rounded-lg border text-xs w-56"
              style={{ background: 'transparent', borderColor: 'var(--aurem-border)', color: 'var(--aurem-heading)' }}
              data-testid="leads-search"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--aurem-border)' }}>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Business</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Verified</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Score</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Called</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Emailed</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>WhatsApp</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Status</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '10px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center" style={{ color: 'var(--aurem-body-secondary)' }}>
                    <Rocket className="size-8 mx-auto mb-3 opacity-30" />
                    <p className="text-sm font-medium mb-1">No leads yet</p>
                    <p className="text-[11px]">Click "Scout Now" to scrape businesses or "Initialize Campaign" to start.</p>
                  </td>
                </tr>
              ) : leads.map(lead => {
                const outreach = lead.outreach_history || [];
                const hasCalled = outreach.some(o => o.type === 'call');
                const hasEmailed = outreach.some(o => o.type === 'email');
                const hasWhatsApp = outreach.some(o => o.type === 'whatsapp');
                const statusCfg = STATUS_CONFIG[lead.status] || STATUS_CONFIG.new;
                return (
                  <tr key={lead.lead_id} className="border-b transition-colors hover:bg-white/5" style={{ borderColor: 'rgba(255,255,255,0.03)' }}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="font-medium" style={{ color: 'var(--aurem-heading)' }}>{lead.business_name}</div>
                        {/* Adaptive ORA conviction pill (shadow mode) */}
                        {typeof lead.conviction_score === 'number' && (
                          <span
                            data-testid={`conviction-pill-${lead.lead_id}`}
                            title={`Adaptive ORA · score ${Math.round(lead.conviction_score)} · last signal: ${lead.last_signal || 'none'} · SHADOW MODE (no auto-actions)`}
                            className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider"
                            style={{
                              background:
                                lead.conviction_bucket === 'CLOSER_NOW' ? 'rgba(239,68,68,0.15)' :
                                lead.conviction_bucket === 'INTENSIFY'  ? 'rgba(245,158,11,0.15)' :
                                lead.conviction_bucket === 'CONTINUE'   ? 'rgba(74,222,128,0.12)' :
                                lead.conviction_bucket === 'SLOW'       ? 'rgba(156,163,175,0.12)' :
                                                                          'rgba(107,114,128,0.10)',
                              color:
                                lead.conviction_bucket === 'CLOSER_NOW' ? '#ef4444' :
                                lead.conviction_bucket === 'INTENSIFY'  ? '#f59e0b' :
                                lead.conviction_bucket === 'CONTINUE'   ? '#16a34a' :
                                lead.conviction_bucket === 'SLOW'       ? '#9ca3af' :
                                                                          '#9ca3af',
                            }}
                          >
                            {lead.conviction_bucket === 'CLOSER_NOW' ? '🔥' :
                             lead.conviction_bucket === 'INTENSIFY'  ? '⚡' :
                             lead.conviction_bucket === 'CONTINUE'   ? '✓' :
                             lead.conviction_bucket === 'SLOW'       ? '⏳' : '○'} {Math.round(lead.conviction_score)}
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{lead.category} · {lead.location}</div>
                    </td>
                    <td className="px-4 py-3">
                      <VerificationBadge
                        lead={{ ...lead, verification: verifiedMap[lead.lead_id] || lead.verification }}
                        onVerify={() => verifyLead(lead.lead_id)}
                        verifying={verifyingLead === lead.lead_id}
                      />
                    </td>
                    <td className="px-4 py-3">
                      {lead.score !== null ? (
                        <span className={`font-bold font-mono ${lead.score < 50 ? 'text-red-400' : lead.score < 70 ? 'text-yellow-400' : 'text-green-400'}`}>
                          {lead.score}
                        </span>
                      ) : <span style={{ color: 'var(--aurem-body-secondary)' }}>—</span>}
                    </td>
                    <td className="px-4 py-3">{hasCalled ? <Phone className="size-3.5 text-blue-400" /> : <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>—</span>}</td>
                    <td className="px-4 py-3">{hasEmailed ? <Mail className="size-3.5 text-[#D4AF37]" /> : <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>—</span>}</td>
                    <td className="px-4 py-3">{hasWhatsApp ? <MessageCircle className="size-3.5 text-green-400" /> : <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>—</span>}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 rounded-full text-[10px] font-bold" style={{ background: statusCfg.bg, color: statusCfg.color }}>
                        {statusCfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {lead.website_url && (
                        <a href={lead.website_url} target="_blank" rel="noopener noreferrer" className="text-[#D4AF37] hover:underline text-[10px] flex items-center gap-1">
                          <Eye className="size-3" /> View
                        </a>
                      )}
                      <button
                        onClick={() => blastAll(lead.lead_id, lead.business_name)}
                        disabled={blastingLead === lead.lead_id}
                        data-testid={`blast-all-${lead.lead_id}`}
                        className="mt-1.5 px-2 py-1 rounded-md text-[10px] font-bold flex items-center gap-1 transition-all hover:scale-[1.03]"
                        style={{
                          background: blastingLead === lead.lead_id
                            ? 'rgba(212,175,55,0.1)'
                            : 'linear-gradient(135deg, #D4AF37, #A08028)',
                          color: blastingLead === lead.lead_id ? '#D4AF37' : '#050507',
                          opacity: blastingLead === lead.lead_id ? 0.6 : 1,
                        }}
                        title="Blast AUREM outreach on Email + SMS + WhatsApp + Voice"
                      >
                        <Zap className="size-3" />
                        {blastingLead === lead.lead_id ? 'Blasting…' : 'Blast All 4'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {leadsTotal > 25 && (
          <div className="p-3 flex items-center justify-between border-t" style={{ borderColor: 'var(--aurem-border)' }}>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
              className="text-xs px-3 py-1 rounded border" style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>
              Prev
            </button>
            <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Page {page} of {Math.ceil(leadsTotal / 25)}</span>
            <button onClick={() => setPage(page + 1)} disabled={page * 25 >= leadsTotal}
              className="text-xs px-3 py-1 rounded border" style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>
              Next
            </button>
          </div>
        )}
      </div>

      {/* CASL Compliance Footer */}
      <div className="text-center py-3 text-[9px] tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }} data-testid="casl-footer">
        CASL Compliant · B2B Implied Consent · Polaris Built Inc. · 7221 Sigsbee Dr, Mississauga, ON L4T 3L6 · All communications include unsubscribe
      </div>

      {blastResult && (
        <div
          data-testid="blast-result-toast"
          className="fixed bottom-6 right-6 z-50 rounded-xl border shadow-2xl p-4 min-w-[340px] max-w-[420px]"
          style={{
            background: 'var(--aurem-card-bg, #0b0b0f)',
            borderColor: blastResult.error ? 'rgba(239,68,68,0.4)' : 'rgba(74,222,128,0.4)',
            boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
          }}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-[10px] tracking-widest uppercase font-bold mb-1"
                style={{ color: blastResult.error ? '#ef4444' : '#4ADE80' }}>
                {blastResult.error ? 'Blast failed' : `Blast sent · ${blastResult.sent_count}/4 channels`}
              </div>
              <div className="text-sm font-semibold mb-2" style={{ color: 'var(--aurem-heading)' }}>
                {blastResult.businessName}
              </div>
              {blastResult.error ? (
                <div className="text-xs" style={{ color: '#ef4444' }}>{blastResult.error}</div>
              ) : (
                <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                  {['email', 'sms', 'whatsapp', 'voice'].map((ch) => {
                    const r = blastResult.results?.[ch];
                    const ok = r?.success;
                    const Icon = ch === 'email' ? Mail : ch === 'sms' ? MessageCircle : ch === 'whatsapp' ? MessageCircle : Phone;
                    return (
                      <div key={ch} data-testid={`blast-result-${ch}`}
                        className="flex items-center gap-2 px-2 py-1.5 rounded border"
                        style={{
                          borderColor: ok ? 'rgba(74,222,128,0.3)' : 'rgba(239,68,68,0.3)',
                          background: ok ? 'rgba(74,222,128,0.05)' : 'rgba(239,68,68,0.05)',
                        }}>
                        <Icon className="size-3" style={{ color: ok ? '#4ADE80' : '#ef4444' }} />
                        <span className="font-semibold capitalize" style={{ color: 'var(--aurem-heading)' }}>{ch}</span>
                        <span className="ml-auto text-[10px]" style={{ color: ok ? '#4ADE80' : '#ef4444' }}>
                          {ok ? '✓' : '✕'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <button
              onClick={() => setBlastResult(null)}
              data-testid="blast-result-close"
              className="text-xs px-2 py-1 rounded-md"
              style={{ color: 'var(--aurem-body-secondary)', border: '1px solid var(--aurem-border)' }}
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default CampaignDashboard;
