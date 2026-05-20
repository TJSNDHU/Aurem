/**
 * AUREM Command Hub — Unified Admin Control Center
 * ==================================================
 * Single-window admin experience replacing scattered sidebar entries.
 * Tabs: Overview · Pricing Studio · Voice Agent · Pipeline · Campaigns
 *
 * Lives at /dashboard with activeItem='command-hub' (wire in AuremDashboard.jsx).
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard, DollarSign, Phone, Users, Megaphone,
  TrendingUp, Activity, Package, RefreshCw, Loader2,
} from 'lucide-react';
import PricingStudio from './admin/PricingStudio';
import VoiceAgentStudio from './admin/VoiceAgentStudio';

const API = process.env.REACT_APP_BACKEND_URL || '';

const TABS = [
  { id: 'overview',        label: 'Overview',        icon: LayoutDashboard },
  { id: 'pricing-studio',  label: 'Pricing Studio',  icon: DollarSign },
  { id: 'voice-agent',     label: 'Voice Agent',     icon: Phone },
  { id: 'pipeline',        label: 'Pipeline',        icon: TrendingUp },
  { id: 'campaigns',       label: 'Campaigns',       icon: Megaphone },
];

const STYLES = {
  wrap: {
    padding: 28,
    minHeight: '100vh',
    background: 'linear-gradient(180deg, rgba(8,8,15,0.6) 0%, rgba(15,18,28,0.6) 100%)',
    fontFamily: "'Jost',sans-serif",
    color: '#F4F4F4',
  },
  tabBar: {
    display: 'flex',
    gap: 6,
    padding: 6,
    borderRadius: 14,
    background: 'rgba(15,18,28,0.55)',
    border: '1px solid rgba(212,175,55,0.14)',
    backdropFilter: 'blur(20px)',
    marginBottom: 22,
    flexWrap: 'wrap',
  },
  tab: (active) => ({
    display: 'inline-flex', alignItems: 'center', gap: 8,
    padding: '10px 16px', borderRadius: 10,
    background: active
      ? 'linear-gradient(135deg, rgba(212,175,55,0.22) 0%, rgba(255,138,61,0.14) 100%)'
      : 'transparent',
    border: active ? '1px solid rgba(212,175,55,0.35)' : '1px solid transparent',
    color: active ? '#D4AF37' : '#8A8070',
    fontSize: 12, fontWeight: 700,
    letterSpacing: '0.08em', textTransform: 'uppercase',
    cursor: 'pointer',
    transition: 'all 0.18s',
  }),
  card: {
    padding: 22, borderRadius: 16,
    background: 'rgba(15,18,28,0.55)',
    border: '1px solid rgba(212,175,55,0.14)',
    backdropFilter: 'blur(22px) saturate(140%)',
    marginBottom: 18,
  },
  statGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    gap: 14,
    marginBottom: 18,
  },
  stat: (color) => ({
    padding: 18, borderRadius: 14,
    background: 'rgba(255,255,255,0.03)',
    border: `1px solid ${color || 'rgba(212,175,55,0.14)'}`,
  }),
};

export default function AdminCommandHub({ token }) {
  const [tab, setTab] = useState('overview');

  return (
    <div data-testid="admin-command-hub" style={STYLES.wrap}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontFamily: "'Cinzel',serif", fontSize: 28, fontWeight: 700, margin: 0, color: '#FFF', letterSpacing: '0.03em' }}>
            AUREM Command Hub
          </h1>
          <p style={{ fontSize: 12, color: '#8A8070', marginTop: 4 }}>
            Unified platform control. Services, voice, pipeline, campaigns, one window.
          </p>
        </div>
        {/* iter 285 — canonical cockpit link (merge duplicate surfaces) */}
        <a
          href="/admin/pillars-map"
          data-testid="command-hub-open-cockpit"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '10px 16px', borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(212,175,55,0.20) 0%, rgba(34,197,94,0.12) 100%)',
            border: '1px solid rgba(212,175,55,0.40)',
            color: '#D4AF37', textDecoration: 'none',
            fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          }}
          title="Open Live Cockpit — Pillars Map, Sentinel, Truth Ledger, Deploy Drift, Autonomous Repair"
        >
          <Activity size={13} />
          Open Live Cockpit
        </a>
      </div>

      <div style={STYLES.tabBar} data-testid="hub-tabs">
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`hub-tab-${t.id}`}
              style={STYLES.tab(tab === t.id)}
            >
              <Icon size={13} />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === 'overview' && <OverviewTab token={token} />}
      {tab === 'pricing-studio' && <PricingStudio token={token} />}
      {tab === 'voice-agent' && <VoiceAgentStudio token={token} />}
      {tab === 'pipeline' && <PipelineTab token={token} />}
      {tab === 'campaigns' && <CampaignsTab token={token} />}
    </div>
  );
}

// ───────────────────── OVERVIEW TAB ─────────────────────

function OverviewTab({ token }) {
  const [data, setData] = useState(null);
  const [voiceOv, setVoiceOv] = useState(null);
  const [sentinel, setSentinel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastSynced, setLastSynced] = useState(null);

  const load = useCallback(async () => {
    try {
      const [catR, voR, snR] = await Promise.all([
        fetch(`${API}/api/admin/catalog`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/admin/voice-agent/overview`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/admin/sentinel/overview`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (catR.ok) setData(await catR.json());
      if (voR.ok) setVoiceOv(await voR.json());
      if (snR.ok) setSentinel(await snR.json());
      setLastSynced(new Date());
    } catch (e) {} finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, [load]);

  if (loading) return <div style={STYLES.card}><Loader2 className="animate-spin" size={28} style={{ color: '#D4AF37', display: 'block', margin: '20px auto' }} /></div>;
  if (!data) return <div style={STYLES.card}>Unable to load overview</div>;

  const errs1h = sentinel?.errors_1h ?? 0;
  const errs24h = sentinel?.errors_24h ?? 0;
  const sentinelColor = errs1h > 0 ? '#EF4444' : errs24h > 0 ? '#F59E0B' : '#22C55E';

  const stats = [
    { label: 'Total MRR', value: `$${(data.total_mrr || 0).toFixed(2)}`, color: '#D4AF37' },
    { label: 'Active Subscriptions', value: data.total_active_subs || 0, color: '#22C55E' },
    { label: 'Services in Catalog', value: data.total_services || 0, color: '#3b82f6' },
    { label: 'Voice Calls (7d)', value: voiceOv?.calls_7d ?? 0, color: '#FF8A3D' },
    { label: 'Sentinel · Errors 1h / 24h', value: `${errs1h} / ${errs24h}`, color: sentinelColor, testid: 'sentinel-kpi', href: '/admin/sentinel' },
  ];

  return (
    <>
      <div data-testid="overview-stats" style={STYLES.statGrid}>
        {stats.map((s, i) => (
          <div
            key={i}
            style={{ ...STYLES.stat(`${s.color}33`), cursor: s.href ? 'pointer' : 'default' }}
            data-testid={s.testid || `overview-stat-${i}`}
            onClick={s.href ? () => { window.location.href = s.href; } : undefined}
          >
            <div style={{ fontSize: 10, color: '#8A8070', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: s.color, fontFamily: "'Cinzel',serif", marginTop: 6 }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <div style={STYLES.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ fontSize: 12, color: '#D4AF37', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: 0 }}>
            Top-Selling Services
          </h3>
          <div style={{ fontSize: 10, color: '#8A8070', display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={11} style={{ animation: 'spin 4s linear infinite' }} />
            Live · {lastSynced && lastSynced.toLocaleTimeString()}
          </div>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: '#8A8070', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              <th style={{ textAlign: 'left', padding: '8px 6px' }}>Service</th>
              <th style={{ textAlign: 'left', padding: '8px 6px' }}>Cluster</th>
              <th style={{ textAlign: 'right', padding: '8px 6px' }}>Active Subs</th>
              <th style={{ textAlign: 'right', padding: '8px 6px' }}>Revenue</th>
            </tr>
          </thead>
          <tbody>
            {(data.services || []).slice().sort((a,b)=>(b.monthly_revenue||0)-(a.monthly_revenue||0)).slice(0, 10).map((s, i) => (
              <tr key={i} style={{ borderTop: '1px solid rgba(212,175,55,0.08)' }} data-testid={`top-svc-${i}`}>
                <td style={{ padding: '10px 6px', fontSize: 12, color: '#E8E0D0' }}>{s.name}</td>
                <td style={{ padding: '10px 6px', fontSize: 10, color: '#8A8070', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{s.cluster}</td>
                <td style={{ padding: '10px 6px', fontSize: 12, color: '#FFF', textAlign: 'right', fontFamily: "'JetBrains Mono',monospace" }}>{s.active_subscribers || 0}</td>
                <td style={{ padding: '10px 6px', fontSize: 12, color: '#D4AF37', textAlign: 'right', fontFamily: "'JetBrains Mono',monospace", fontWeight: 700 }}>${(s.monthly_revenue || 0).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={STYLES.card}>
        <h3 style={{ fontSize: 12, color: '#D4AF37', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 12px 0' }}>
          Voice Agent Platform
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          <MiniStat label="Retell Connection" value={voiceOv?.retell_connected ? 'Connected ✓' : 'Not Connected'} color={voiceOv?.retell_connected ? '#22C55E' : '#EF4444'} />
          <MiniStat label="Customers Configured" value={voiceOv?.total_customers_configured ?? 0} />
          <MiniStat label="Total Minutes" value={voiceOv?.total_minutes_all_time ?? 0} />
        </div>
      </div>
    </>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{ padding: 12, borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(212,175,55,0.1)' }}>
      <div style={{ fontSize: 9, color: '#8A8070', letterSpacing: '0.16em', textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color: color || '#FFF', marginTop: 4 }}>{value}</div>
    </div>
  );
}

// ─── Placeholder tabs (link to legacy screens for now) ───

function PipelineTab({ token }) {
  return (
    <div style={STYLES.card}>
      <h3 style={{ color: '#D4AF37' }}>Lead Pipeline</h3>
      <p style={{ color: '#8A8070', fontSize: 13 }}>
        Unified view consolidating LeadsDashboard, LeadEnrichmentDashboard, PipelineDashboard, SalesPipelineDashboard.
      </p>
      <div style={{ padding: 24, marginTop: 12, background: 'rgba(255,255,255,0.02)', borderRadius: 12, border: '1px dashed rgba(212,175,55,0.2)' }}>
        <a href="/dashboard#sales-pipeline" style={{ color: '#D4AF37' }}>→ Open legacy Sales Pipeline view</a>
      </div>
    </div>
  );
}

function CampaignsTab({ token }) {
  return (
    <div style={STYLES.card}>
      <h3 style={{ color: '#D4AF37' }}>Campaigns</h3>
      <p style={{ color: '#8A8070', fontSize: 13 }}>
        Drip, outreach, hot-lead campaigns, consolidated.
      </p>
      <div style={{ padding: 24, marginTop: 12, background: 'rgba(255,255,255,0.02)', borderRadius: 12, border: '1px dashed rgba(212,175,55,0.2)' }}>
        <a href="/dashboard#campaign-dashboard" style={{ color: '#D4AF37' }}>→ Open legacy Campaign Dashboard</a>
      </div>
    </div>
  );
}
