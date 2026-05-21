/**
 * LuxeDashboardV2 — Apple-style customer dashboard (iter 325n).
 * Edge-to-edge layout · auto dark/light · responsive desktop/tablet/mobile.
 *
 * Spec: dashboard-theme.css owns all colors via CSS vars.
 *       Components live in ./components/*.
 *       Existing internal pages (CRM/Settings/etc.) keep using LuxePages.jsx.
 */
import React, { useState, useMemo } from 'react';
import {
  Home as HomeIcon, Activity,
  Zap, Users,
  Sparkles, Bot, Settings as SettingsIcon,
  Bell, Sun, Moon, LogOut, Search,
} from 'lucide-react';
import { Toaster } from 'sonner';

import '../../styles/dashboard-theme.css';
import { LuxeAuthProvider, useLuxeAuth } from './LuxeAuthContext';
import { LuxeAuthOverlay } from './LuxeAuthOverlay';
import { useLuxeDashboardData } from './useLuxeDashboardData';
import { useViewport } from './useViewport';
import { useTheme } from './useTheme';
import {
  ProfilePage,
  IntegrationsPage,
} from './LuxePages';
import {
  LuxeLiveHealth, LuxeCRM, LuxeCampaign, LuxeORA, LuxeProfile, LuxeSettings,
} from './LuxeV2Pages';

import { PulseCard }            from './components/PulseCard';
import { MetricRow }            from './components/MetricRow';
import { BusinessGrowthChart }  from './components/BusinessGrowthChart';
import { AgentBars }            from './components/AgentBars';
import { VanguardRing }         from './components/VanguardRing';
import { WebsiteScanCard }      from './components/WebsiteScanCard';
import { PipelineCard }         from './components/PipelineCard';
import { InboxCard }            from './components/InboxCard';
import { BottomTabBar }         from './components/BottomTabBar';

// ────────────────────────────────────────────────────────────────
// Nav sections (desktop sidebar) — iter 325o: merged to 6 items
// No duplicates, every item maps to a real working page.
// ────────────────────────────────────────────────────────────────
const NAV_SECTIONS = [
  {
    title: 'Dashboard',
    items: [
      { k: 'home',         label: 'Home',         icon: HomeIcon },
      { k: 'live-health',  label: 'Live Health',  icon: Activity },
    ],
  },
  {
    title: 'Revenue',
    items: [
      { k: 'crm',          label: 'CRM',          icon: Users },
      { k: 'campaign',     label: 'Campaign',     icon: Zap },
    ],
  },
  {
    title: 'System',
    items: [
      { k: 'ora',          label: 'ORA',          icon: Sparkles },
      { k: 'profile',      label: 'Profile',      icon: SettingsIcon },
      { k: 'settings',     label: 'Settings',     icon: Bot },
    ],
  },
];

// Map nav key → page renderer.
const PAGE_RENDERERS = {
  'live-health': () => <LuxeLiveHealth />,
  'crm':         () => <LuxeCRM />,
  'campaign':    () => <LuxeCampaign />,
  'ora':         () => <LuxeORA />,
  'profile':     () => <LuxeProfile />,
  'settings':    () => <LuxeSettings />,
  // Legacy fallbacks (in case BottomTabBar still references these)
  'automation':  () => <LuxeCampaign />,
  'inbox':       () => <LuxeCRM />,
  'integrations':() => <IntegrationsPage />,
};

const Avatar = ({ user, size = 36 }) => {
  const initial = ((user?.company_name || user?.business_name || user?.full_name || 'A')[0] || 'A').toUpperCase();
  return (
    <div data-testid="user-avatar" style={{
      width: size, height: size, borderRadius: 10,
      background: 'linear-gradient(135deg, var(--dash-orange), var(--dash-gold-bright))',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#fff', fontWeight: 700, fontSize: size * 0.42, flexShrink: 0,
    }}>{initial}</div>
  );
};

// ────────────────────────────────────────────────────────────────
// Sidebar
// ────────────────────────────────────────────────────────────────
const Sidebar = ({ active, onNav, user, onLogout }) => (
  <aside data-testid="sidebar" className="av2-sidebar av2-scroll">
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 8px 18px' }}>
      <div style={{
        width: 28, height: 28, borderRadius: 8,
        background: 'linear-gradient(135deg, var(--dash-orange), var(--dash-gold-bright))',
      }} />
      <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: '0.04em' }}>AUREM</span>
    </div>

    {/* User block */}
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: 10, borderRadius: 10,
      background: 'var(--dash-card)', border: '1px solid var(--dash-border)',
      marginBottom: 18,
    }}>
      <Avatar user={user} />
      <div className="av2-user-meta" style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--dash-text)',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {user?.company_name || user?.business_name || user?.full_name || 'My Business'}
        </div>
        <div style={{ fontSize: 10, color: 'var(--dash-text-faint)', letterSpacing: '0.06em' }}>
          {(user?.role || 'customer').toUpperCase()}
        </div>
      </div>
    </div>

    {NAV_SECTIONS.map((section) => (
      <div key={section.title} style={{ marginBottom: 14 }}>
        <div className="av2-section-label" style={{
          fontSize: 10, color: 'var(--dash-text-faint)', letterSpacing: '0.10em',
          padding: '0 10px 6px', textTransform: 'uppercase',
        }}>
          {section.title}
        </div>
        {section.items.map(({ k, label, icon: Icon }) => {
          const isActive = active === k;
          return (
            <button
              key={k}
              type="button"
              data-testid={`nav-${k}`}
              onClick={() => onNav(k)}
              className="av2-nav-item"
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '9px 10px', marginBottom: 2,
                background: isActive ? 'var(--dash-nav-active-bg)' : 'transparent',
                color: isActive ? 'var(--dash-text)' : 'var(--dash-text-muted)',
                border: 0,
                borderLeft: isActive ? '2px solid var(--dash-nav-active-bar)' : '2px solid transparent',
                borderRadius: '0 8px 8px 0',
                fontSize: 13, fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                transition: 'background 140ms ease, color 140ms ease',
              }}
            >
              <Icon size={16} />
              <span className="av2-nav-label">{label}</span>
            </button>
          );
        })}
      </div>
    ))}

    <div className="av2-sidebar-footer" style={{
      marginTop: 'auto', paddingTop: 12, fontSize: 10,
      color: 'var(--dash-text-faint)', display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className="av2-pulse-dot" />
        <span>Production · v325n</span>
      </div>
      <button type="button"
              data-testid="sidebar-logout"
              onClick={onLogout}
              style={{ display: 'flex', alignItems: 'center', gap: 6,
                       background: 'none', border: 0, color: 'var(--dash-text-muted)',
                       fontSize: 11, cursor: 'pointer', padding: 0 }}>
        <LogOut size={12} /> Log out
      </button>
    </div>
  </aside>
);

// ────────────────────────────────────────────────────────────────
// Topbar
// ────────────────────────────────────────────────────────────────
const Topbar = ({ pageTitle, isMobile, theme, onToggleTheme, pulseActive }) => (
  <header className="av2-topbar" data-testid="topbar">
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
      {isMobile ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 22, height: 22, borderRadius: 6,
            background: 'linear-gradient(135deg, var(--dash-orange), var(--dash-gold-bright))',
          }} />
          <span style={{ fontSize: 14, fontWeight: 700 }}>AUREM</span>
        </div>
      ) : (
        <>
          <div style={{ fontSize: 12, color: 'var(--dash-text-faint)' }}>
            AUREM · Customer
          </div>
          <span style={{ color: 'var(--dash-text-faint)' }}>›</span>
          <h1 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--dash-text)' }}>
            {pageTitle}
          </h1>
        </>
      )}
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {!isMobile && (
        <>
          <span className="av2-pill av2-pill-live" data-testid="topbar-live">
            <span className="av2-pulse-dot" style={{ width: 6, height: 6 }} /> {pulseActive ? 'Live' : 'Idle'}
          </span>
          <span className="av2-pill av2-pill-ent">Enterprise · Active</span>
        </>
      )}
      <button type="button" className="av2-icon-btn" aria-label="Search" data-testid="topbar-search">
        <Search size={15} />
      </button>
      <button type="button" className="av2-icon-btn" aria-label="Notifications" data-testid="topbar-bell">
        <Bell size={15} />
      </button>
      <button type="button" className="av2-icon-btn" aria-label="Toggle theme"
              data-testid="theme-toggle" onClick={onToggleTheme}>
        {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
      </button>
    </div>
  </header>
);

// ────────────────────────────────────────────────────────────────
// Home view
// ────────────────────────────────────────────────────────────────
export const HomeView = ({ data }) => {
  const growthSeries = useMemo(() => {
    // Map either homeAgg multi-line series OR fallback to single-series growth.
    if (data?.growthMulti && data.growthMulti.length) {
      return data.growthMulti.map((d) => ({
        m: d.month || d.m, revenue: d.revenue, leads: d.leads, fixes: d.fixes ?? d.auto_fixes,
      }));
    }
    return (data?.growth || []).map((d) => ({
      m: d.m, revenue: d.a, leads: d.b, fixes: 0,
    }));
  }, [data]);

  const pipelineStages = data?.pipelineStages || data?.pipeline?.stages || [];
  const pipelineTotal  = data?.pipelineTotal   ?? data?.pipeline?.total   ?? 0;
  const resultsSummary = data?.resultsSummary || data?.results || {};
  const inboxThreads   = data?.inboxThreads || [];
  const inboxUnread    = data?.inboxUnread ?? 0;
  const runningAgents  = (data?.agents || []).filter((a) => (a?.v ?? 0) > 0).length;

  return (
    <>
      <PulseCard
        revenue={data?.totalRevenue}
        websiteHealth={data?.websiteHealth}
        autoFix={data?.autoFix}
        securityAlerts={data?.securityAlerts}
        oraRepair={data?.oraRepair}
        active={data?.pulse?.active}
        lastUpdated={data?.lastUpdated}
      />
      <MetricRow data={resultsSummary} />
      <div className="av2-grid-3-2">
        <BusinessGrowthChart series={growthSeries} />
        <AgentBars agents={data?.agents} running={runningAgents} uptime={data?.uptime || '99.9%'} />
        <VanguardRing
          score={data?.vanguard?.score}
          siteShield={data?.vanguard?.site}
          platform={data?.vanguard?.platform}
          backlinks={data?.vanguard?.backlinks}
          rateLimiter={data?.vanguard?.rateLimiter}
          rlsEnforced={data?.vanguard?.rlsEnforced}
        />
      </div>
      <div className="av2-grid-2">
        <WebsiteScanCard scan={data?.websiteScan} lastScan={data?.websiteScan?.lastScan} />
        <PipelineCard stages={pipelineStages} total={pipelineTotal} />
      </div>
      <InboxCard threads={inboxThreads} unread={inboxUnread} />
    </>
  );
};

// ────────────────────────────────────────────────────────────────
// Page title resolver
// ────────────────────────────────────────────────────────────────
const TITLES = {
  home: 'Home', 'live-health': 'Live Health',
  crm: 'CRM', campaign: 'Campaign',
  ora: 'ORA', profile: 'Profile', settings: 'Settings',
  inbox: 'Inbox', automation: 'Campaign', integrations: 'Automation',
};

// ────────────────────────────────────────────────────────────────
// Shell
// ────────────────────────────────────────────────────────────────
const Shell = () => {
  const { user, token, logout } = useLuxeAuth();
  const [active, setActive] = useState('home');
  const { isMobile } = useViewport();
  const { effective, toggle } = useTheme();
  const data = useLuxeDashboardData(token);
  const pageTitle = TITLES[active] || 'Home';

  const renderPage = () => {
    if (active === 'home') return <HomeView data={data} />;
    const fn = PAGE_RENDERERS[active];
    return fn ? fn() : <HomeView data={data} />;
  };

  if (!token) return <LuxeAuthOverlay />;

  return (
    <div className="aurem-v2-root" data-testid="aurem-v2-root">
      <Toaster position="top-right" theme={effective} />
      <div className="av2-shell">
        <Sidebar active={active} onNav={setActive} user={user} onLogout={logout} />
        <main className="av2-main">
          <Topbar
            pageTitle={pageTitle}
            isMobile={isMobile}
            theme={effective}
            onToggleTheme={toggle}
            pulseActive={data?.pulse?.active}
          />
          <div className="av2-content av2-scroll" data-testid="page-content">
            {renderPage()}
          </div>
          <BottomTabBar active={active} onNav={setActive} />
        </main>
      </div>
    </div>
  );
};

const LuxeDashboardV2 = () => (
  <LuxeAuthProvider>
    <Shell />
  </LuxeAuthProvider>
);

export default LuxeDashboardV2;
