/**
 * AUREM AdminShell — Phase 2
 * ───────────────────────────
 * Persistent left sidebar + top HUD that wraps every /admin/* route.
 * Renders <Outlet /> so existing pages need ZERO changes.
 *
 * Sections (6):  COCKPIT · OPERATIONS · ORA AGENTS · HEALTH · BUILD · SETTINGS
 * Items   (22): see SECTIONS below
 * Default landing: /admin → /admin/boardroom (handled in App.js)
 *
 * HUD: live gross_burn (60s poll) · agent online dot · system status · ⌘K hint
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Crown, Target, Compass, Brain, Activity, Wrench, Settings, ChevronLeft, Search,
  // Cockpit
  Trophy, Zap, Layers, Grid3x3,
  // Operations
  Radar, Phone, Globe, FlaskConical,
  // ORA Agents
  Network, Sword, Terminal, Camera, Pickaxe,
  // Health
  Map, Shield, GitBranch, RotateCcw,
  // Build
  Hammer, Sparkles, FileText,
  // Settings
  Lock, DollarSign, Hash, Eye,
  // HUD
  Flame, Dot, LogOut, MessageSquare,
} from 'lucide-react';
import { getPlatformToken, clearPlatformAuth } from '../utils/secureTokenStore';
import { BACKEND_URL } from '../lib/api';
import { PillarProvider, usePillarHealth } from './PillarHealthContext';
import PillarGate, { PillarDot } from './PillarGate';

const API = BACKEND_URL;

// ─────────────────────────────────────────────────────────────
// SIDEBAR TREE — 22 items, 6 sections
// ─────────────────────────────────────────────────────────────
const SECTIONS = [
  {
    id: 'cockpit', label: 'COCKPIT', icon: Crown, accent: '#4A8FD4', pillar: 'P1',
    blurb: 'Observe — P&L, burn, system pulse',
    items: [
      { to: '/admin/console',            label: 'Founders Console',    icon: Brain,   hint: 'g c' },
      { to: '/admin/awb-cockpit',        label: 'Auto Site Cockpit',   icon: Globe,   hint: 'g w' },
      { to: '/admin/boardroom',          label: 'Boardroom · P&L',     icon: Trophy,  hint: 'g b' },
      { to: '/admin/system-pulse-live',  label: 'System Pulse · Live', icon: Zap,     hint: 'g p' },
      { to: '/admin/system-overview',    label: 'System Overview',     icon: Layers,  hint: 'g s' },
      { to: '/admin/blocks',             label: 'Pillar Blocks',       icon: Grid3x3, hint: 'g B' },
    ],
  },
  {
    id: 'operations', label: 'OPERATIONS', icon: Compass, accent: '#C9A227', pillar: 'P3',
    blurb: 'Orient — leads, clients, outreach',
    items: [
      { to: '/admin/mission-control',    label: 'Mission Control',     icon: Radar,   hint: 'g m' },
      { to: '/admin/openfang',           label: 'OpenFang · Lead Hand',icon: Phone,   hint: 'g o' },
      { to: '/admin/site-monitor',       label: 'Site Monitor',        icon: Globe,   hint: '' },
      { to: '/admin/hunter-test',        label: 'Hunter · Live Test',  icon: FlaskConical, hint: 'g h' },
    ],
  },
  {
    id: 'ora', label: 'ORA AGENTS', icon: Brain, accent: '#9B6DD4', pillar: 'P2',
    blurb: 'AI workforce visibility',
    items: [
      { to: '/admin/brain-graph',        label: 'Brain Graph',         icon: Network, hint: '' },
      { to: '/admin/browser-agent',      label: 'Browser Agent',       icon: Camera,  hint: '' },
      { to: '/admin/avatar-manager',     label: 'Avatar Manager',      icon: Sparkles,hint: '' },
      { to: '/admin/leads-mining',       label: 'Leads Mining',        icon: Pickaxe, hint: '' },
      { to: '/admin/vanguard',           label: 'Vanguard',            icon: Sword,   hint: '' },
      { to: '/admin/root-command',       label: 'Root Command',        icon: Terminal,hint: 'g r' },
      { to: '/admin/skills-library',     label: 'Skills Library · 1.4k',icon: Sparkles,hint: 'g l' },
      { to: '/admin/memoir',             label: 'Memoir · Memory',     icon: GitBranch,hint: 'g M' },
    ],
  },
  {
    id: 'health', label: 'HEALTH', icon: Activity, accent: '#F0A030', pillar: null,
    blurb: 'System integrity · diagnostics',
    items: [
      { to: '/admin/pillars-map',        label: 'Pillars Map',         icon: Map,        hint: '' },
      { to: '/admin/sentinel',           label: 'Diagnostics',         icon: Shield,     hint: 'g x' },
      { to: '/admin/customer-health',    label: 'Customer Health',     icon: Activity,   hint: 'g h' },
      { to: '/admin/stem-fix',           label: 'Stem-Fix · Refactor', icon: GitBranch,  hint: '' },
      { to: '/admin/self-repair',        label: 'Self-Repair',         icon: RotateCcw,  hint: '' },
      { to: '/admin/ora-optimize',       label: 'ORA Optimizer · $',   icon: Zap,        hint: '' },
      { to: '/admin/ora-cto',            label: 'ORA CTO Cockpit',     icon: Crown,      hint: '' },
      { to: '/admin/git-gate',           label: 'Git Commit Gate',     icon: GitBranch,  hint: '' },
      { to: '/admin/ora-chat',           label: 'ORA Chat',            icon: MessageSquare, hint: '' },
      { to: '/admin/ora-settings',       label: 'ORA Settings',        icon: Settings,   hint: '' },
    ],
  },
  {
    id: 'build', label: 'BUILD', icon: Wrench, accent: '#4AD4A0', pillar: 'P1',
    blurb: 'Construction layer',
    items: [
      { to: '/admin/control-center',     label: 'Control Center',      icon: Hammer,     hint: 'g c' },
      { to: '/admin/evolver',            label: 'EvoMap Evolver',      icon: Sparkles,   hint: 'g e' },
      { to: '/admin/case-study',         label: 'Case Study Builder',  icon: FileText,   hint: 'g k' },
      { to: '/admin/design-extract',     label: 'Design Extract',      icon: Sparkles,   hint: '' },
    ],
  },
  {
    id: 'settings', label: 'SETTINGS', icon: Settings, accent: '#7A7468', pillar: 'P4',
    blurb: 'Config · access · plans',
    items: [
      { to: '/admin/2fa',                label: '2FA Enrolment',       icon: Lock,       hint: '' },
      { to: '/admin/ssot',               label: 'SSOT Console',        icon: DollarSign, hint: 'g s' },
      { to: '/admin/plans',              label: 'Plans · Pricing',     icon: DollarSign, hint: '' },
      { to: '/admin/business-ids',       label: 'Business IDs',        icon: Hash,       hint: 'g i' },
      { to: '/admin/impersonation-log',  label: 'Impersonation Log',   icon: Eye,        hint: 'g l' },
    ],
  },
];

// ─────────────────────────────────────────────────────────────
function useBoardroomTicker(token, enabled) {
  const [data, setData] = useState({ burn: null, realized: null, losers: 0, online: false, board: [] });
  useEffect(() => {
    if (!token || !enabled) return;
    let mounted = true;
    const tick = async () => {
      try {
        const r = await fetch(`${API}/api/agents/board/rollup?days=1`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) { if (mounted) setData((d) => ({ ...d, online: false })); return; }
        const d = await r.json();
        if (!mounted) return;
        setData({
          burn: d.gross_burn_usd ?? 0,
          realized: d.realized_revenue_usd ?? 0,
          losers: (d.firing_line || []).length,
          online: true,
          board: d.board || [],
        });
      } catch {
        if (mounted) setData((d) => ({ ...d, online: false }));
      }
    };
    tick();
    const id = setInterval(tick, 60_000);
    return () => { mounted = false; clearInterval(id); };
  }, [token, enabled]);
  return data;
}

// Phase 3 — A2A live rail (per-agent activity dots + founder timeline)
function usePulse(token, enabled) {
  const [pulse, setPulse] = useState({ agents: [], timeline: [] });
  useEffect(() => {
    if (!token || !enabled) return;
    let mounted = true;
    const tick = async () => {
      try {
        const r = await fetch(`${API}/api/agents/board/pulse?agents_window_min=15&timeline_limit=8`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return;
        const d = await r.json();
        if (mounted) setPulse({ agents: d.agents || [], timeline: d.timeline || [] });
      } catch { /* swallow */ }
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, [token, enabled]);
  return pulse;
}

const AGENT_DOT_META = {
  hunter_ora:   { label: 'HU', color: '#EF4444' },
  followup_ora: { label: 'FU', color: '#F59E0B' },
  closer_ora:   { label: 'CL', color: '#22C55E' },
  referral_ora: { label: 'RE', color: '#8B5CF6' },
  scout_ora:    { label: 'SC', color: '#06B6D4' },
  envoy_ora:    { label: 'EN', color: '#D4AF37' },
  ora_brain:    { label: 'OR', color: '#E8E6E1' },
};

const STATUS_COLOR = { live: '#22C55E', idle: '#F59E0B', dormant: '#3A3830' };

// Customer-health summary poll (30s — matches scheduler cadence)
function useCustomerHealthCounts(token, enabled) {
  const [counts, setCounts] = useState(null);
  useEffect(() => {
    if (!token || !enabled) return;
    let mounted = true;
    const tick = async () => {
      try {
        const r = await fetch(`${API}/api/admin/diagnostics/summary`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return;
        const d = await r.json();
        if (mounted && d?.counts) setCounts(d.counts);
      } catch { /* swallow */ }
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, [token, enabled]);
  return counts;
}

// Inline pill for the top ticker bar — visible on EVERY admin route.
function CustomerHealthPill({ counts, onClick }) {
  if (!counts) return null;
  const { healthy = 0, degraded = 0, critical = 0 } = counts;
  const hasCritical = critical > 0;
  const hasDegraded = degraded > 0;
  const dotColor = hasCritical ? '#EF4444' : (hasDegraded ? '#F59E0B' : '#22C55E');
  return (
    <button
      type="button"
      data-testid="hud-customer-health-pill"
      onClick={onClick}
      title={`${healthy} healthy · ${degraded} degraded · ${critical} critical · click for details`}
      style={{
        position: 'absolute', top: 3, right: 12, height: 18,
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '0 8px',
        background: hasCritical ? 'rgba(239,68,68,0.10)' : 'rgba(11,11,16,0.85)',
        border: hasCritical
          ? '1px solid rgba(239,68,68,0.45)'
          : '1px solid rgba(201,162,39,0.18)',
        borderRadius: 4,
        fontFamily: 'JetBrains Mono, monospace', fontSize: 9,
        cursor: 'pointer', color: '#EDE8DF',
        zIndex: 31,
        letterSpacing: '0.04em',
      }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: dotColor,
        display: 'inline-block',
        boxShadow: hasCritical ? '0 0 6px 1px rgba(239,68,68,0.85)' : 'none',
        animation: hasCritical
          ? 'aurem-customer-pulse 1.4s ease-in-out infinite' : 'none',
      }} />
      <span style={{ color: '#7A7468', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
        Customers
      </span>
      <span style={{ color: '#22C55E', fontWeight: 600 }}>{healthy}</span>
      <span style={{ color: '#3A3830' }}>·</span>
      <span style={{ color: hasDegraded ? '#F59E0B' : '#3A3830', fontWeight: 600 }}>{degraded}</span>
      <span style={{ color: '#3A3830' }}>·</span>
      <span style={{ color: hasCritical ? '#EF4444' : '#3A3830', fontWeight: 600 }}>{critical}</span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
// SHELL
// ─────────────────────────────────────────────────────────────
const COLLAPSED_PX = 64;
const EXPANDED_PX  = 248;
const STORAGE_KEY  = 'aurem_admin_sidebar_collapsed';

const AdminShell = () => {
  const token = getPlatformToken();
  return (
    <PillarProvider token={token}>
      <AdminShellInner />
    </PillarProvider>
  );
};

const AdminShellInner = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const token = getPlatformToken();
  const pillars = usePillarHealth();

  // Persist collapsed state
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0'); } catch { /* ignore */ }
  }, [collapsed]);

  // Auto-expand only the active section
  const activeSection = useMemo(() => {
    for (const s of SECTIONS) {
      if (s.items.some((it) => location.pathname.startsWith(it.to))) return s.id;
    }
    return SECTIONS[0].id;
  }, [location.pathname]);

  const ticker = useBoardroomTicker(token, true);
  const pulse  = usePulse(token, !collapsed);
  const customerCounts = useCustomerHealthCounts(token, true);

  const [oraQuery, setOraQuery] = useState('');
  const [oraSending, setOraSending] = useState(false);
  const [oraReply, setOraReply] = useState('');
  const sendOra = async (e) => {
    e?.preventDefault?.();
    const q = oraQuery.trim();
    if (!q || oraSending) return;
    setOraSending(true);
    try {
      const r = await fetch(`${API}/api/ora/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text: q, channel: 'shell' }),
      });
      const d = await r.json();
      setOraReply(d.reply || d.detail || 'OK');
      setOraQuery('');
    } catch {
      setOraReply('error');
    }
    setOraSending(false);
    setTimeout(() => setOraReply(''), 8000);
  };

  const openPalette = useCallback(() => {
    // AdminShortcuts.jsx subscribes to this custom event (added in same iter)
    window.dispatchEvent(new CustomEvent('aurem:open-palette'));
  }, []);

  const logout = () => { clearPlatformAuth(); navigate('/admin/login'); };

  const W = collapsed ? COLLAPSED_PX : EXPANDED_PX;

  // Ticker rows from board (filter agents that have any signal today)
  const tickerAgents = (ticker.board || []).map((r) => ({
    id: (r.agent_id || '').toUpperCase(),
    raw_id: r.agent_id,
    roi: Number(r.roi_potential || 0).toFixed(2),
    burn_per_day: Number(r.cost_usd || 0).toFixed(2),
  }));
  const onTickerClick = (rawId) => {
    if (!rawId) return;
    navigate(`/admin/boardroom#agent-${rawId}`);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#06060A', color: '#EDE8DF' }} data-testid="admin-shell">
      {/* ─────── TICKER (top, full-width, 24px) ─────── */}
      <div data-testid="admin-ticker" style={{
        height: 24,
        background: '#0B0B10',
        borderBottom: '0.5px solid rgba(201,162,39,0.10)',
        overflow: 'hidden',
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        zIndex: 30,
      }}>
        <CustomerHealthPill counts={customerCounts}
                              onClick={() => navigate('/admin/customer-health')} />
        {tickerAgents.length > 0 ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            height: '100%',
            whiteSpace: 'nowrap',
            animation: 'aurem-ticker 40s linear infinite',
            width: 'max-content',
          }}>
            {[0, 1].map((rep) => (
              <span key={rep} style={{ display: 'inline-flex' }} aria-hidden={rep === 1}>
                {tickerAgents.map((a, i) => (
                  <span key={`${rep}-${i}`}
                    onClick={() => rep === 0 && onTickerClick(a.raw_id)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '0 24px',
                      borderRight: '0.5px solid #3A3830',
                      cursor: rep === 0 ? 'pointer' : 'default',
                    }} data-testid={rep === 0 ? `ticker-row-${a.id.toLowerCase()}` : undefined}>
                    <span style={{
                      fontSize: 8, color: '#7A7468',
                      letterSpacing: 1.5, marginRight: 7,
                      fontFamily: 'JetBrains Mono, monospace',
                    }}>{a.id}</span>
                    <span style={{
                      fontSize: 9,
                      color: Number(a.roi) > 1 ? '#52C47A' : '#D94F5C',
                      fontFamily: 'JetBrains Mono, monospace', fontWeight: 600,
                    }}>{a.roi}×</span>
                    <span style={{
                      fontSize: 8, color: '#3A3830',
                      marginLeft: 6, fontFamily: 'JetBrains Mono, monospace',
                    }}>${a.burn_per_day}/d</span>
                  </span>
                ))}
              </span>
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', height: '100%', padding: '0 18px',
                        fontSize: 9, color: '#3A3830', letterSpacing: '0.2em', textTransform: 'uppercase',
                        fontFamily: 'JetBrains Mono, monospace' }}>
            ticker · awaiting workforce telemetry
          </div>
        )}
      </div>
      <style>{`
        @keyframes aurem-ticker {from{transform:translateX(0)}to{transform:translateX(-50%)}}
        @keyframes aurem-customer-pulse {
          0%, 100% { box-shadow: 0 0 4px 1px rgba(239,68,68,0.55); }
          50%      { box-shadow: 0 0 10px 3px rgba(239,68,68,0.95); }
        }
        [data-testid="admin-ticker"] > div:not([data-testid="hud-customer-health-pill"]):hover { animation-play-state: paused; }
        [data-testid="admin-ticker"] [data-testid^="ticker-row-"]:hover { background: rgba(212,175,55,0.06); }
        [data-testid="hud-customer-health-pill"]:hover { filter: brightness(1.2); }
      `}</style>

      {/* ─────── BODY (sidebar + outlet) ─────── */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
      {/* ─────── SIDEBAR ─────── */}
      <aside
        data-testid="admin-sidebar"
        style={{
          width: W,
          background: '#0B0B10',
          borderRight: '1px solid rgba(212,175,55,0.10)',
          transition: 'width 220ms cubic-bezier(.4,0,.2,1)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 24,
          height: 'calc(100vh - 24px)',
          flexShrink: 0,
          overflow: 'hidden',
        }}>
        {/* Brand */}
        <div style={{ padding: '20px 14px 16px', borderBottom: '1px solid rgba(212,175,55,0.06)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg,#D4AF37,#8B7355)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Target style={{ width: 16, height: 16, color: '#06060A' }} />
          </div>
          {!collapsed && (
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: "'Cinzel', serif", fontSize: 13, color: '#EDE8DF', letterSpacing: '0.18em', whiteSpace: 'nowrap' }}>AUREM</div>
              <div style={{ fontSize: 9, color: '#7A7468', letterSpacing: '0.2em', textTransform: 'uppercase' }}>Sovereign OS</div>
            </div>
          )}
        </div>

        {/* HUD strip — only when expanded */}
        {!collapsed && (
          <div data-testid="admin-hud" style={{ padding: '10px 14px 12px', borderBottom: '1px solid rgba(212,175,55,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <Dot style={{ width: 14, height: 14, color: ticker.online ? '#22C55E' : '#7A7468' }} className={ticker.online ? 'animate-pulse' : ''} />
              <span style={{ fontSize: 9, color: '#7A7468', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
                {ticker.online ? 'AI Workforce · Live' : 'Connecting…'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Flame style={{ width: 10, height: 10, color: '#EF4444' }} />
                  <span style={{ fontSize: 8, color: '#7A7468', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Burn 24h</span>
                </div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: '#EDE8DF', marginTop: 1 }}
                     data-testid="hud-burn">
                  ${(ticker.burn ?? 0).toFixed(2)}
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Trophy style={{ width: 10, height: 10, color: '#22C55E' }} />
                  <span style={{ fontSize: 8, color: '#7A7468', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Real $</span>
                </div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: '#EDE8DF', marginTop: 1 }}
                     data-testid="hud-realized">
                  ${(ticker.realized ?? 0).toFixed(0)}
                </div>
              </div>
            </div>
            {ticker.losers > 0 && (
              <div data-testid="hud-firing-line" style={{ marginTop: 6, fontSize: 9, color: '#EF4444' }}>
                ⚠ {ticker.losers} agent{ticker.losers === 1 ? '' : 's'} on firing line
              </div>
            )}
          </div>
        )}

        {/* A2A AGENT PULSE RIBBON — per-agent live dots */}
        {!collapsed && pulse.agents.length > 0 && (
          <div data-testid="a2a-rail" style={{ padding: '8px 14px', borderBottom: '1px solid rgba(212,175,55,0.06)' }}>
            <div style={{ fontSize: 8, color: '#7A7468', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 5 }}>
              AI Workforce · 15m
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {pulse.agents.map((a) => {
                const meta = AGENT_DOT_META[a.agent_id] || { label: a.agent_id.slice(0,2).toUpperCase(), color: '#888' };
                const ringColor = STATUS_COLOR[a.status] || STATUS_COLOR.dormant;
                return (
                  <div
                    key={a.agent_id}
                    title={`${a.agent_id} · ${a.status} · ${a.count} actions · $${(a.cost_usd||0).toFixed(4)}`}
                    data-testid={`a2a-dot-${a.agent_id}`}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      width: 22, height: 22, borderRadius: '50%',
                      background: `${meta.color}1A`,
                      border: `1.5px solid ${ringColor}`,
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 8, fontWeight: 700, color: meta.color,
                      animation: a.status === 'live' ? 'aurempulse 1.5s ease-in-out infinite' : 'none',
                    }}>
                    {meta.label}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* FOUNDER TIMELINE — last 5 events */}
        {!collapsed && pulse.timeline.length > 0 && (
          <div data-testid="founder-timeline" style={{ padding: '8px 14px', borderBottom: '1px solid rgba(212,175,55,0.06)', maxHeight: 130, overflowY: 'auto' }}>
            <div style={{ fontSize: 8, color: '#7A7468', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 5 }}>
              Founder Timeline
            </div>
            {pulse.timeline.slice(0, 5).map((ev, i) => {
              const c = ev.type === 'sentinel' ? '#F59E0B'
                      : ev.type === 'deploy' ? '#22C55E'
                      : ev.type === 'ora' ? '#06B6D4'
                      : '#9A9388';
              const sha = ev.meta?.commit_sha;
              const repo = ev.meta?.repo;
              const ghHref = ev.type === 'deploy' && sha && repo
                ? `https://github.com/${repo}/commit/${sha}`
                : null;
              return (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', padding: '3px 0', fontSize: 9, lineHeight: 1.4 }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <span style={{ color: c, flexShrink: 0, fontFamily: 'JetBrains Mono, monospace' }}>·</span>
                    <span style={{ color: '#9A9388', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {ev.msg}
                    </span>
                  </div>
                  {ghHref && (
                    <a
                      href={ghHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid={`timeline-commit-${(sha || '').slice(0,7)}`}
                      style={{ marginLeft: 12, fontSize: 9, color: '#22C55E', textDecoration: 'none', opacity: 0.85 }}>
                      View commit →
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <style>{`@keyframes aurempulse {0%,100%{box-shadow:0 0 0 0 rgba(34,197,94,0.55)}50%{box-shadow:0 0 0 6px rgba(34,197,94,0)}}`}</style>

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0', minHeight: 0 }}>
          {SECTIONS.map((sec) => {
            const isActive = activeSection === sec.id;
            const Icon = sec.icon;
            const pillarStatus = sec.pillar ? (pillars[sec.pillar] || 'loading') : null;
            return (
              <div key={sec.id} data-testid={`section-${sec.id}`} style={{ marginBottom: 6 }}>
                {/* Section header */}
                {!collapsed ? (
                  <div style={{ padding: '8px 14px 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Icon style={{ width: 11, height: 11, color: sec.accent }} />
                    <span style={{ fontSize: 9, color: sec.accent, letterSpacing: '0.25em', fontWeight: 600 }}>{sec.label}</span>
                    {pillarStatus && (
                      <PillarDot
                        status={pillarStatus}
                        size={6}
                        title={`${sec.pillar} ${pillarStatus}`}
                      />
                    )}
                  </div>
                ) : (
                  <div style={{ padding: '6px 0', display: 'flex', justifyContent: 'center', position: 'relative' }} title={`${sec.label}${pillarStatus ? ` · ${sec.pillar} ${pillarStatus}` : ''}`}>
                    <Icon style={{ width: 14, height: 14, color: sec.accent, opacity: isActive ? 1 : 0.5 }} />
                    {pillarStatus && pillarStatus !== 'green' && (
                      <span style={{ position: 'absolute', top: 4, right: 16 }}>
                        <PillarDot status={pillarStatus} size={5} />
                      </span>
                    )}
                  </div>
                )}
                {/* Items — show only if expanded OR section is active (so collapsed mode keeps active section visible too) */}
                {(!collapsed || isActive) && sec.items.map((it) => {
                  const ItIcon = it.icon;
                  return (
                    <NavLink
                      key={it.to}
                      to={it.to}
                      data-testid={`nav-${it.to.replace('/admin/', '').replace(/\W+/g, '-')}`}
                      style={({ isActive: linkActive }) => ({
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: collapsed ? '8px 12px' : '7px 14px 7px 30px',
                        marginInline: 6,
                        borderRadius: 8,
                        textDecoration: 'none',
                        background: linkActive ? `${sec.accent}1A` : 'transparent',
                        borderLeft: linkActive ? `2px solid ${sec.accent}` : '2px solid transparent',
                        color: linkActive ? '#EDE8DF' : '#9A9388',
                        fontSize: 12,
                        transition: 'background 100ms',
                      })}>
                      <ItIcon style={{ width: 13, height: 13, flexShrink: 0 }} />
                      {!collapsed && (
                        <>
                          <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.label}</span>
                          {it.hint && (
                            <code style={{ fontSize: 9, color: sec.accent, fontFamily: 'JetBrains Mono, monospace', opacity: 0.6 }}>
                              {it.hint}
                            </code>
                          )}
                        </>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Footer actions */}
        <div style={{ borderTop: '1px solid rgba(212,175,55,0.06)', padding: '10px 8px', flexShrink: 0 }}>
          {/* Mini ORA command */}
          {!collapsed && (
            <form onSubmit={sendOra} data-testid="ora-mini" style={{ marginBottom: 8 }}>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={oraQuery}
                  onChange={(e) => setOraQuery(e.target.value)}
                  placeholder="Ask ORA…"
                  disabled={oraSending}
                  data-testid="ora-mini-input"
                  style={{
                    width: '100%', padding: '7px 28px 7px 10px', borderRadius: 8,
                    background: 'rgba(6,182,212,0.06)',
                    border: '0.5px solid rgba(6,182,212,0.25)',
                    color: '#E8E6E1', fontSize: 11, outline: 'none',
                  }}
                />
                <Brain style={{ position: 'absolute', right: 8, top: 7, width: 12, height: 12, color: '#06B6D4' }} />
              </div>
              {oraReply && (
                <div data-testid="ora-mini-reply" style={{ marginTop: 4, fontSize: 9, color: '#06B6D4', lineHeight: 1.4, maxHeight: 40, overflow: 'hidden' }}>
                  {oraReply}
                </div>
              )}
            </form>
          )}

          <button
            onClick={openPalette}
            data-testid="admin-cmdk-trigger"
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'space-between',
              gap: 8, padding: '8px 10px', borderRadius: 8, background: 'rgba(212,175,55,0.06)',
              border: '0.5px solid rgba(212,175,55,0.18)', color: '#D4AF37', fontSize: 11, cursor: 'pointer',
            }}>
            <Search style={{ width: 12, height: 12 }} />
            {!collapsed && <><span style={{ flex: 1, textAlign: 'left' }}>Search…</span><code style={{ fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}>⌘K</code></>}
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            data-testid="admin-sidebar-toggle"
            style={{
              width: '100%', marginTop: 6, padding: '6px 10px', borderRadius: 8,
              background: 'transparent', border: '0.5px solid rgba(255,255,255,0.06)',
              color: '#7A7468', fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
            <ChevronLeft style={{ width: 11, height: 11, transform: collapsed ? 'rotate(180deg)' : 'none', transition: 'transform 200ms' }} />
            {!collapsed && <span>Collapse</span>}
          </button>
          <button
            onClick={logout}
            data-testid="admin-logout"
            style={{
              width: '100%', marginTop: 6, padding: '6px 10px', borderRadius: 8,
              background: 'transparent', border: '0.5px solid rgba(239,68,68,0.18)',
              color: '#EF4444', fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
            <LogOut style={{ width: 11, height: 11 }} />
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>

      {/* ─────── MAIN OUTLET ─────── */}
      <main style={{ flex: 1, minWidth: 0 }} data-testid="admin-outlet">
        {(() => {
          const activeSec = SECTIONS.find(s => s.id === activeSection);
          const pillarKey = activeSec?.pillar;
          if (!pillarKey) return <Outlet />;
          // Lazy-import to avoid circular: render gate inline
          const status = pillars[pillarKey] || 'loading';
          if (status === 'green' || status === 'yellow') return <Outlet />;
          // red or loading → render gate via dedicated component
          return <PillarGate pillar={pillarKey}><Outlet /></PillarGate>;
        })()}
      </main>
      </div>
    </div>
  );
};

export default AdminShell;
