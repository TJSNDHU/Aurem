/**
 * LuxeDashboardPreview — the customer portal at /my.
 * Sidebar + Home dashboard (12 tiles, all real data) + page router.
 * Auth-gated by LuxeAuthOverlay. Re-uses Card primitive from LuxePages.
 */
import React, { useState, useMemo } from 'react';
import {
  Home as HomeIcon, Activity, Shield, Bot, Users, Sparkles, Cog,
  User as UserIcon, LogOut, Bell, Zap,
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
} from 'recharts';
import { Toaster } from 'sonner';
import { LuxeAuthProvider, useLuxeAuth } from '../luxe/LuxeAuthContext';
import { LuxeAuthOverlay } from '../luxe/LuxeAuthOverlay';
import { useLuxeDashboardData } from '../luxe/useLuxeDashboardData';
import {
  Card, StatusDot,
  ProfilePage, LiveHealthPage, SecurityPage,
  AutomationPage, CRMPage, ORAPage, SettingsPage,
} from '../luxe/LuxePages';
import {
  GOLD, GOLD_HI, INK, STROKE, TEXT_HI, TEXT_MD, TEXT_LO,
  fontDisplay, fontBody, fontMono,
} from '../luxe/tokens';

const NAV = [
  { k: 'home',        label: 'Home',        icon: HomeIcon },
  { k: 'profile',     label: 'Profile',     icon: UserIcon },
  { k: 'live-health', label: 'Live Health', icon: Activity },
  { k: 'security',    label: 'Security',    icon: Shield },
  { k: 'automation',  label: 'Automation',  icon: Bot },
  { k: 'crm',         label: 'CRM',         icon: Users },
  { k: 'ora',         label: 'ORA',         icon: Sparkles },
  { k: 'settings',    label: 'Settings',    icon: Cog },
];

// ── Sidebar ──────────────────────────────────────────────────────────
const Sidebar = ({ active, onNav, onLogout, user }) => (
  <aside style={{
    width: 200, padding: '20px 14px',
    display: 'flex', flexDirection: 'column', gap: 4,
    background: 'rgba(8,10,14,0.72)',
    borderRight: '1px solid rgba(212,163,115,0.10)',
    backdropFilter: 'blur(18px)',
    WebkitBackdropFilter: 'blur(18px)',
    height: '100vh', position: 'sticky', top: 0,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 22, paddingLeft: 4 }}>
      <span style={{
        width: 26, height: 26, borderRadius: 7,
        background: 'linear-gradient(135deg, #FFE4A8, #C9A84C)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: fontDisplay, color: INK, fontSize: 14, fontWeight: 700,
      }}>A</span>
      <span style={{ color: TEXT_HI, fontFamily: fontDisplay, letterSpacing: '0.30em', fontSize: 13, fontWeight: 700 }}>AUREM</span>
    </div>
    {NAV.map(({ k, label, icon: Icon }) => (
      <button key={k} data-testid={`nav-${k}`} onClick={() => onNav(k)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px', borderRadius: 10,
          background: active === k ? 'rgba(212,163,115,0.10)' : 'transparent',
          border: `1px solid ${active === k ? STROKE : 'transparent'}`,
          color: active === k ? GOLD_HI : TEXT_MD,
          fontFamily: fontMono, fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase',
          cursor: 'pointer', textAlign: 'left',
        }}>
        <Icon size={14} />
        {label}
      </button>
    ))}
    <div style={{ flex: 1 }} />
    <div style={{ padding: '10px 12px', fontFamily: fontMono, color: TEXT_LO, fontSize: 9 }}>
      {user?.email || 'Loading…'}
    </div>
    <button data-testid="nav-logout" onClick={onLogout} style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 12px', borderRadius: 10, background: 'transparent',
      border: '1px solid transparent', color: TEXT_MD,
      fontFamily: fontMono, fontSize: 11, letterSpacing: '0.16em', textTransform: 'uppercase',
      cursor: 'pointer', textAlign: 'left',
    }}>
      <LogOut size={14} />
      Sign Out
    </button>
  </aside>
);

// ── Header strip ─────────────────────────────────────────────────────
const HeaderStrip = ({ user }) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 18px', borderBottom: '1px solid rgba(212,163,115,0.08)',
  }}>
    <div style={{ fontFamily: fontMono, fontSize: 10, color: TEXT_LO, letterSpacing: '0.20em' }}>
      AUREM PLATFORM · CUSTOMER
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: fontMono, fontSize: 10, color: TEXT_MD }}>
      <Bell size={13} />
      <span>{(user?.tier || 'starter').toUpperCase()}</span>
      <span style={{ color: GOLD_HI }}>•</span>
      <span>{(user?.tier_status || 'trial').toUpperCase()}</span>
    </div>
  </div>
);

// ── Home tiles ───────────────────────────────────────────────────────
const KpiTile = ({ label, value, sub, color = TEXT_HI, testid }) => (
  <Card testid={testid}>
    <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 10 }}>
      {label}
    </div>
    <div style={{ fontFamily: fontDisplay, color, fontSize: 38, fontWeight: 700, lineHeight: 1 }}>{value}</div>
    {sub && <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, marginTop: 6 }}>{sub}</div>}
  </Card>
);

const PulseRing = ({ active }) => (
  <span style={{
    display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
    background: active ? '#bef264' : '#fbbf24',
    boxShadow: `0 0 12px ${active ? 'rgba(190,242,100,0.6)' : 'rgba(251,191,36,0.5)'}`,
    animation: 'luxe-pulse 1.5s ease-in-out infinite',
  }} />
);

const AgentsTile = ({ agents }) => (
  <Card testid="agents-tile" style={{ gridColumn: 'span 2' }}>
    <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 14 }}>
      Active Agents (Real-Time)
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 10, height: 110, alignItems: 'end' }}>
      {agents.map((a, i) => {
        const h = 16 + (a.v / 100) * 70;
        const isHi = a.v >= 70;
        const display = a.n >= 1000 ? `${(a.n / 1000).toFixed(1)}k` : String(a.n);
        return (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}
            title={`${a.k}: ${a.n} ${a.status || ''}`}
          >
            <span style={{ fontFamily: fontMono, color: isHi ? '#FFE4A8' : TEXT_HI, fontSize: 9, fontWeight: 700 }}>{display}</span>
            <div style={{
              width: 16, height: h, borderRadius: 4,
              background: isHi
                ? 'linear-gradient(180deg, #FFE4A8 0%, #C9A84C 100%)'
                : 'linear-gradient(180deg, #6A6560 0%, #3A3530 100%)',
              boxShadow: isHi ? '0 4px 14px rgba(212,163,115,0.45)' : 'none',
            }} />
            <span style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 8, letterSpacing: '0.06em' }}>{a.k.toUpperCase()}</span>
          </div>
        );
      })}
    </div>
  </Card>
);

const VanguardTile = ({ data }) => {
  const v = data?.vanguard || { score: 0, platform: 0, site: 0, backlinks: 0, brokenLinks: 0, insecureLinks: 0 };
  const score = Math.max(0, Math.min(100, Math.round(v.score || 0)));
  const ringColor = score >= 85 ? '#bef264' : (score >= 60 ? GOLD_HI : '#fdba74');
  const ringDeg = (score / 100) * 360;
  return (
    <Card testid="vanguard-security-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase' }}>
          Vanguard Security
        </div>
        <span style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO, letterSpacing: '0.18em' }}>
          {v.rateLimiter === 'redis' ? 'REDIS' : 'MEM'} · {v.rlsEnforced ? 'RLS✓' : 'RLS✗'}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: 14, alignItems: 'center' }}>
        <div style={{
          width: 92, height: 92, borderRadius: '50%',
          background: `conic-gradient(${ringColor} 0deg ${ringDeg}deg, rgba(255,255,255,0.07) ${ringDeg}deg 360deg)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: 70, height: 70, borderRadius: '50%', background: 'rgba(8,12,18,0.95)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 22, fontWeight: 700 }}>{score}</span>
            <span style={{ fontFamily: fontMono, color: TEXT_MD, fontSize: 8, letterSpacing: '0.14em' }}>VANGUARD</span>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7, fontFamily: fontMono, fontSize: 10 }}>
          <PillarRow label="Site shield" value={Math.round(v.site || 0)} hint="HTTPS/CSP/HSTS" />
          <PillarRow label="Platform"    value={Math.round(v.platform || 0)} hint="rate-limit · JWT · RLS" />
          <PillarRow label="Backlinks"   value={Math.round(v.backlinks || 0)}
            hint={`${v.brokenLinks || 0} broken · ${v.insecureLinks || 0} insecure`} />
        </div>
      </div>
    </Card>
  );
};

const PillarRow = ({ label, value, hint }) => {
  const c = value >= 85 ? '#bef264' : (value >= 60 ? '#FFE4A8' : '#fdba74');
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ color: TEXT_MD, letterSpacing: '0.14em', textTransform: 'uppercase', fontSize: 9 }}>{label}</span>
        <span style={{ color: c, fontWeight: 700 }}>{value}</span>
      </div>
      <div style={{ width: '100%', height: 4, borderRadius: 999, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(2, value)}%`, height: '100%', background: c, transition: 'width .6s ease' }} />
      </div>
      {hint && <div style={{ color: TEXT_LO, fontSize: 8, marginTop: 2, letterSpacing: '0.10em' }}>{hint}</div>}
    </div>
  );
};

const ScanTile = ({ data }) => {
  const s = data?.websiteScan || {};
  return (
    <Card testid="website-scan-card">
      <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 12 }}>
        Website Scan
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
        {[['GEO', s.geo], ['SEC', s.sec], ['ACC', s.acc], ['SEO', s.seo]].map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
            <span style={{ fontFamily: fontMono, color: TEXT_MD, fontSize: 10, letterSpacing: '0.14em' }}>{k}</span>
            <span style={{ fontFamily: fontMono, color: TEXT_HI, fontSize: 13, fontWeight: 700 }}>{v ?? 0}</span>
          </div>
        ))}
      </div>
    </Card>
  );
};

const RepairTile = ({ data }) => {
  const r = data?.oraRepair || {};
  return (
    <Card testid="ora-repair-card">
      <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 10 }}>
        ORA Repair
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontFamily: fontDisplay, color: '#22c55e', fontSize: 32, fontWeight: 700 }}>{r.successPct ?? 0}%</span>
        <span style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10 }}>success</span>
      </div>
      <div style={{ fontFamily: fontMono, color: TEXT_MD, fontSize: 10, marginTop: 6 }}>
        {r.healed ?? 0} healed · {r.attempts ?? 0} attempts
      </div>
    </Card>
  );
};

const AlertsTile = ({ data }) => {
  const a = data?.securityAlerts || { count: 0, items: [] };
  return (
    <Card testid="alerts-card">
      <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 10 }}>
        Security Alerts
      </div>
      <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 28, fontWeight: 700 }}>{a.count}</div>
      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {(a.items || []).slice(0, 3).map((it, i) => (
          <div key={i} style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_MD, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <span style={{ color: it.level === 'HIGH' ? '#fca5a5' : (it.level === 'MED' ? '#fdba74' : TEXT_LO), letterSpacing: '0.14em', marginRight: 6 }}>{it.level}</span>
            {it.msg}
          </div>
        ))}
      </div>
    </Card>
  );
};

// ── Home (12-tile grid) ──────────────────────────────────────────────
const HomePage = ({ data }) => (
  <div data-testid="page-home" style={{ padding: '4px 6px', display: 'flex', flexDirection: 'column', gap: 14 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <PulseRing active={!!data.pulse?.active} />
      <h1 style={{ margin: 0, color: TEXT_HI, fontFamily: fontDisplay, fontSize: 22, fontWeight: 700, letterSpacing: '0.10em' }}>AUREM PULSE</h1>
      <span style={{ fontFamily: fontMono, fontSize: 10, color: data.pulse?.active ? '#bef264' : '#fbbf24', letterSpacing: '0.20em' }}>
        ● {data.pulse?.active ? 'ACTIVE' : 'STANDBY'}
      </span>
    </div>
    {/* Row 1: 4 KPIs */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      <KpiTile testid="total-revenue" label="Total Revenue"
        value={`$${(data.totalRevenue?.value || 0).toLocaleString()}`}
        sub={`Δ ${data.totalRevenue?.deltaPct?.toFixed(1) ?? 0}%`} />
      <KpiTile testid="website-health-score" label="Website Health Score"
        value={`${data.websiteHealth?.value ?? 0}/${data.websiteHealth?.max ?? 100}`}
        sub="composite of GEO/SEC/ACC/SEO" />
      <KpiTile testid="auto-fix-live" label="Auto Fix Live"
        value={(data.autoFix?.value ?? 0).toLocaleString()}
        sub="ORA repairs cumulative" />
      <KpiTile testid="agents-active" label="Active Agents"
        value={(data.agents || []).filter(a => /ACTIVE|SCANNING|ENGAGING|HUNTING|NURTURING|AMPLIFYING|SPEAKING|WATCHING/i.test(a.status)).length + ' / 8'}
        sub="of 8 customer agents" />
    </div>
    {/* Row 2: agents (2 cols) + Vanguard (2 cols) */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      <AgentsTile agents={data.agents || []} />
      <div style={{ gridColumn: 'span 2' }}><VanguardTile data={data} /></div>
    </div>
    {/* Row 3: scan + repair + alerts (3 cols) */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
      <ScanTile data={data} />
      <RepairTile data={data} />
      <AlertsTile data={data} />
    </div>
    <style>{`
      @keyframes luxe-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.4); }
      }
    `}</style>
  </div>
);

// ── Inner shell (auth-gated) ─────────────────────────────────────────
const Inner = () => {
  const { token, user, loading, logout } = useLuxeAuth();
  const [active, setActive] = useState('home');
  const data = useLuxeDashboardData(token);

  const Page = useMemo(() => {
    switch (active) {
      case 'profile':     return <ProfilePage />;
      case 'live-health': return <LiveHealthPage />;
      case 'security':    return <SecurityPage />;
      case 'automation':  return <AutomationPage />;
      case 'crm':         return <CRMPage />;
      case 'ora':         return <ORAPage />;
      case 'settings':    return <SettingsPage />;
      default:            return <HomePage data={data} />;
    }
  }, [active, data]);

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      height: '100vh',
      background:
        'radial-gradient(80% 50% at 50% 0%, rgba(212,163,115,0.06) 0%, transparent 60%),' +
        'linear-gradient(180deg, #0E1014 0%, #0A0C10 100%)',
      color: TEXT_HI,
      overflow: 'hidden',
    }}>
      <Sidebar active={active} onNav={setActive} onLogout={logout} user={user} />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <HeaderStrip user={user} />
        <div style={{ flex: 1, padding: 18, overflowY: 'auto', minHeight: 0 }}>
          {Page}
        </div>
      </main>
      {(!loading && !token) && <LuxeAuthOverlay />}
      <Toaster position="top-right" theme="dark" />
    </div>
  );
};

// ── Default export ───────────────────────────────────────────────────
const LuxeDashboardPreview = () => (
  <LuxeAuthProvider>
    <Inner />
  </LuxeAuthProvider>
);

export default LuxeDashboardPreview;
