/**
 * LuxeDashboardPreview — the customer portal at /my.
 * Sidebar + Home dashboard (12 tiles, all real data) + page router.
 * Auth-gated by LuxeAuthOverlay. Re-uses Card primitive from LuxePages.
 */
import React, { useState, useMemo } from 'react';
import {
  Home as HomeIcon, Activity, Shield, Bot, Users, Sparkles, Cog,
  User as UserIcon, LogOut, Bell, Zap, Plug, Menu as MenuIcon, X as CloseIcon,
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  LineChart, Line,
} from 'recharts';
import { Toaster } from 'sonner';
import { LuxeAuthProvider, useLuxeAuth } from '../luxe/LuxeAuthContext';
import { LuxeAuthOverlay } from '../luxe/LuxeAuthOverlay';
import { useLuxeDashboardData } from '../luxe/useLuxeDashboardData';
import { useViewport } from '../luxe/useViewport';
import {
  Card, StatusDot,
  ProfilePage, LiveHealthPage, SecurityPage,
  AutomationPage, CRMPage, ORAPage, SettingsPage, IntegrationsPage,
} from '../luxe/LuxePages';
import { CustomerResultsRow } from '../luxe/CustomerResultsRow';
import {
  GOLD, GOLD_HI, INK, STROKE, TEXT_HI, TEXT_MD, TEXT_LO,
  fontDisplay, fontBody, fontMono,
} from '../luxe/tokens';

const NAV = [
  // iter 322bk — matches target screenshot exactly. Integrations dropped from
  // sidebar (still reachable via deep-link inside Automation). Profile moved
  // after ORA per the target ordering.
  { k: 'home',         label: 'Home',         icon: HomeIcon },
  { k: 'live-health',  label: 'Live Health',  icon: Activity },
  { k: 'security',     label: 'Security',     icon: Shield },
  { k: 'automation',   label: 'Automation',   icon: Bot },
  { k: 'crm',          label: 'CRM',          icon: Users },
  { k: 'ora',          label: 'ORA',          icon: Sparkles },
  { k: 'profile',      label: 'Profile',      icon: UserIcon },
  { k: 'settings',     label: 'Settings',     icon: Cog },
];

// ── Sidebar ──────────────────────────────────────────────────────────
// Desktop: full 200px rail. Tablet: 200px rail. Mobile: hidden (drawer).
const Sidebar = ({ active, onNav, onLogout, user, isMobile, isDesktop, mobileOpen, onMobileClose }) => {
  const visible = !isMobile || mobileOpen;
  const navClick = (k) => {
    onNav(k);
    if (isMobile) onMobileClose?.();
  };
  return (
    <>
      {/* Mobile backdrop */}
      {isMobile && mobileOpen && (
        <div
          onClick={onMobileClose}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
            zIndex: 90,
          }}
        />
      )}
      <aside
        data-testid="luxe-sidebar"
        style={{
          width: isDesktop ? 260 : 232, padding: '22px 16px',
          display: visible ? 'flex' : 'none',
          flexDirection: 'column', gap: 4,
          // iter 322bl — 3D glass/water-bubble shine layered look (target match).
          // Layer 1: deep ink base.
          // Layer 2: top-down vignette so the head of the rail glows softly.
          // Layer 3: subtle gold caustic curving across the upper third.
          // Layer 4: inner top highlight (the "shine line").
          background: `
            radial-gradient(ellipse 320px 200px at 50% -40px, rgba(255,228,168,0.10), transparent 70%),
            radial-gradient(ellipse 200px 460px at 10% 30%, rgba(255,228,168,0.04), transparent 70%),
            linear-gradient(180deg, rgba(20,18,28,0.95) 0%, rgba(8,8,14,0.98) 60%, rgba(4,4,8,1) 100%)
          `,
          borderRight: '1px solid rgba(212,163,115,0.14)',
          boxShadow: `
            inset 1px 0 0 rgba(255,255,255,0.04),
            inset -1px 0 0 rgba(0,0,0,0.4),
            4px 0 32px rgba(0,0,0,0.55)
          `,
          backdropFilter: 'blur(22px) saturate(160%)',
          WebkitBackdropFilter: 'blur(22px) saturate(160%)',
          height: '100vh',
          position: isMobile ? 'fixed' : 'sticky',
          top: 0, left: 0,
          zIndex: isMobile ? 100 : 1,
          transition: 'transform .25s ease',
          overflow: 'hidden',
        }}
      >
        {/* Glass top-edge shine — animated bubble that drifts subtly */}
        <div aria-hidden="true" style={{
          position: 'absolute', top: -120, left: -40, right: -40, height: 280,
          background: 'radial-gradient(ellipse at center, rgba(255,228,168,0.16) 0%, transparent 60%)',
          pointerEvents: 'none', filter: 'blur(10px)',
        }} />
        <div aria-hidden="true" style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 1,
          background: 'linear-gradient(90deg, transparent 0%, rgba(255,228,168,0.4) 30%, rgba(255,228,168,0.4) 70%, transparent 100%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 14, paddingLeft: 4,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 28, height: 28, borderRadius: 8,
              background: `
                radial-gradient(ellipse at 30% 25%, rgba(255,255,255,0.5) 0%, transparent 50%),
                linear-gradient(135deg, #FFE4A8 0%, #C9A84C 50%, #8B6A2E 100%)
              `,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: fontDisplay, color: INK, fontSize: 14, fontWeight: 700,
              boxShadow: `
                inset 0 1px 0 rgba(255,255,255,0.45),
                inset 0 -1px 0 rgba(0,0,0,0.25),
                0 2px 8px rgba(201,168,76,0.35)
              `,
            }}>A</span>
            <span style={{
              color: TEXT_HI, fontFamily: fontDisplay,
              letterSpacing: '0.30em', fontSize: 13, fontWeight: 700,
            }}>AUREM</span>
          </div>
          {isMobile && (
            <button
              data-testid="sidebar-close"
              onClick={onMobileClose}
              aria-label="Close menu"
              style={{
                background: 'transparent', border: 'none', color: TEXT_MD,
                cursor: 'pointer', padding: 4,
              }}
            >
              <CloseIcon size={18} />
            </button>
          )}
        </div>

        {/* iter 322bk/bl — business badge card with glass-bubble depth */}
        <div data-testid="sidebar-business-badge" style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '11px 11px', borderRadius: 14, marginBottom: 18,
          position: 'relative',
          background: `
            linear-gradient(180deg, rgba(255,228,168,0.10) 0%, rgba(255,228,168,0.02) 60%, transparent 100%),
            linear-gradient(180deg, rgba(20,16,10,0.6) 0%, rgba(8,7,4,0.7) 100%)
          `,
          border: '1px solid rgba(255,228,168,0.16)',
          boxShadow: `
            inset 0 1px 0 rgba(255,255,255,0.08),
            inset 0 -1px 0 rgba(0,0,0,0.3),
            0 4px 16px rgba(0,0,0,0.4)
          `,
        }}>
          <span style={{
            width: 36, height: 36, borderRadius: 9,
            background: `
              radial-gradient(ellipse at 30% 25%, rgba(255,255,255,0.45) 0%, transparent 50%),
              linear-gradient(135deg, #FFE4A8 0%, #C9A84C 50%, #8B6A2E 100%)
            `,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: fontDisplay, color: INK, fontSize: 18, fontWeight: 700,
            flexShrink: 0,
            boxShadow: `
              inset 0 1px 0 rgba(255,255,255,0.4),
              inset 0 -1px 0 rgba(0,0,0,0.25),
              0 2px 8px rgba(201,168,76,0.4)
            `,
          }}>{((user?.company_name || user?.business_name || user?.full_name || 'A')[0] || 'A').toUpperCase()}</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{
              fontFamily: fontDisplay, color: TEXT_HI, fontSize: 11.5, fontWeight: 600,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              letterSpacing: '0.02em',
            }}>{user?.company_name || user?.business_name || user?.full_name || 'My Business'}</div>
            <div style={{
              fontFamily: fontMono, color: GOLD_HI, fontSize: 9.5,
              letterSpacing: '0.14em', marginTop: 2,
            }}>{user?.business_id || user?.bin || (user?.email || '').split('@')[0].slice(0, 10).toUpperCase() || '—'}</div>
          </div>
        </div>
        {NAV.map(({ k, label, icon: Icon }) => {
          const isActive = active === k;
          return (
          <button key={k} data-testid={`nav-${k}`} onClick={() => navClick(k)}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '11px 14px', borderRadius: 12,
              position: 'relative',
              // iter 322bl — glass-bubble active state (3D shine)
              background: isActive
                ? `linear-gradient(180deg, rgba(255,228,168,0.14) 0%, rgba(255,228,168,0.04) 50%, rgba(255,228,168,0.02) 100%),
                   linear-gradient(180deg, rgba(20,16,10,0.4), rgba(8,7,4,0.5))`
                : 'transparent',
              border: `1px solid ${isActive ? 'rgba(255,228,168,0.20)' : 'transparent'}`,
              boxShadow: isActive
                ? `inset 0 1px 0 rgba(255,255,255,0.10),
                   inset 0 -1px 0 rgba(0,0,0,0.25),
                   0 4px 14px rgba(0,0,0,0.35)`
                : 'none',
              color: isActive ? TEXT_HI : TEXT_MD,
              fontFamily: fontBody, fontSize: 13.5, fontWeight: isActive ? 600 : 500,
              letterSpacing: '0',
              cursor: 'pointer', textAlign: 'left',
              transition: 'background 0.22s ease, color 0.22s ease, box-shadow 0.22s ease',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'linear-gradient(180deg, rgba(255,228,168,0.05), rgba(255,228,168,0.01))';
                e.currentTarget.style.color = TEXT_HI;
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = TEXT_MD;
              }
            }}>
            <Icon size={16} color={isActive ? GOLD_HI : TEXT_MD} />
            {label}
          </button>
          );
        })}
        <div style={{ flex: 1 }} />
        <button data-testid="nav-logout" onClick={onLogout} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '11px 14px', borderRadius: 12, background: 'transparent',
          border: '1px solid transparent', color: TEXT_MD,
          fontFamily: fontBody, fontSize: 13.5, fontWeight: 500,
          letterSpacing: '0',
          cursor: 'pointer', textAlign: 'left',
          transition: 'background 0.18s ease, color 0.18s ease',
        }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,228,168,0.035)';
            e.currentTarget.style.color = TEXT_HI;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = TEXT_MD;
          }}>
          <LogOut size={16} />
          Log out
        </button>
      </aside>
    </>
  );
};

// ── Header strip ─────────────────────────────────────────────────────
const HeaderStrip = ({ user, isMobile, onMenuOpen }) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 14px', borderBottom: '1px solid rgba(212,163,115,0.08)',
    gap: 8,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
      {isMobile && (
        <button
          data-testid="sidebar-open"
          onClick={onMenuOpen}
          aria-label="Open menu"
          style={{
            background: 'transparent', border: '1px solid rgba(212,163,115,0.18)',
            color: TEXT_MD, padding: '6px 8px', borderRadius: 8, cursor: 'pointer',
            display: 'flex', alignItems: 'center',
          }}
        >
          <MenuIcon size={16} />
        </button>
      )}
      <div style={{
        fontFamily: fontMono, fontSize: 10, color: TEXT_LO, letterSpacing: '0.20em',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {isMobile ? 'AUREM' : 'AUREM PLATFORM · CUSTOMER'}
      </div>
    </div>
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      fontFamily: fontMono, fontSize: 10, color: TEXT_MD,
      flexShrink: 0,
    }}>
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
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(38px, 1fr))',
      gap: 10, alignItems: 'end',
    }}>
      {agents.map((a, i) => {
        const h = 16 + (a.v / 100) * 70;
        const isHi = a.v >= 70;
        const display = a.n >= 1000 ? `${(a.n / 1000).toFixed(1)}k` : String(a.n);
        return (
          <div key={i} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
            minHeight: 110, justifyContent: 'flex-end',
          }}
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

// iter 322bk — Website Scan as FOUR individual bordered tiles (target screenshot).
const ScanRowFour = ({ data }) => {
  const s = data?.websiteScan || {};
  const tiles = [
    ['GEO', s.geo, '#FFE4A8', 'Geographic Reach', 'top-5 markets'],
    ['SEC', s.sec, '#bef264', 'Security', 'TLS / CSP'],
    ['ACC', s.acc, '#FFA552', 'Accessibility', 'WCAG / ARIA'],
    ['SEO', s.seo, '#60A5FA', 'SEO / Performance', 'LCP / meta'],
  ];
  return (
    <Card testid="website-scan-card" style={{ padding: 16 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: 12,
      }}>
        <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase' }}>
          Website Scan
        </div>
        <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 9, letterSpacing: '0.16em' }}>
          last · {s.lastScan || '—'}
        </div>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, minmax(0,1fr))',
        gap: 10,
      }}>
        {tiles.map(([k, v, c, name, hint]) => {
          const pct = Math.max(0, Math.min(100, Number(v) || 0));
          const r = 18, C = 2 * Math.PI * r, dash = C * (pct / 100);
          return (
            <div key={k} data-testid={`scan-tile-${k.toLowerCase()}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px', borderRadius: 12,
                background: 'rgba(255,228,168,0.025)',
                border: `1px solid ${STROKE}`,
              }}>
              <div style={{ position: 'relative', width: 50, height: 50, flexShrink: 0 }}>
                <svg width="50" height="50" viewBox="0 0 50 50">
                  <circle cx="25" cy="25" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
                  <circle cx="25" cy="25" r={r} fill="none" stroke={c} strokeWidth="4" strokeLinecap="round"
                    strokeDasharray={`${dash} ${C}`} transform="rotate(-90 25 25)"
                    style={{ filter: `drop-shadow(0 0 4px ${c})`, transition: 'stroke-dasharray .8s ease' }} />
                </svg>
                <div style={{
                  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: fontDisplay, fontSize: 13, fontWeight: 700, color: TEXT_HI,
                }}>{pct}</div>
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontFamily: fontMono, fontSize: 9, color: GOLD_HI,
                  letterSpacing: '0.18em', textTransform: 'uppercase',
                }}>{k}</div>
                <div style={{
                  fontFamily: fontDisplay, fontSize: 11, color: TEXT_HI,
                  marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{name}</div>
                <div style={{
                  fontFamily: fontMono, fontSize: 9, color: TEXT_LO, marginTop: 2,
                }}>{hint}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

const ScanTile = ({ data }) => {
  const s = data?.websiteScan || {};
  const dials = [
    ['GEO', s.geo, '#C9A227', 'Geographic'],
    ['SEC', s.sec, '#bef264', 'TLS · CSP'],
    ['ACC', s.acc, '#FFA552', 'WCAG · ARIA'],
    ['SEO', s.seo, '#60A5FA', 'LCP · meta'],
  ];
  return (
    <Card testid="website-scan-card">
      <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 14 }}>
        Website Scan
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 14 }}>
        {dials.map(([k, v, c, hint]) => {
          const pct = Math.max(0, Math.min(100, Number(v) || 0));
          const r = 22, C = 2 * Math.PI * r, dash = C * (pct / 100);
          return (
            <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 10 }} data-testid={`scan-dial-${k.toLowerCase()}`}>
              <div style={{ position: 'relative', width: 60, height: 60, flexShrink: 0 }}>
                <svg width="60" height="60" viewBox="0 0 60 60">
                  <circle cx="30" cy="30" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="5" />
                  <circle cx="30" cy="30" r={r} fill="none" stroke={c} strokeWidth="5" strokeLinecap="round"
                    strokeDasharray={`${dash} ${C}`} transform="rotate(-90 30 30)"
                    style={{ filter: `drop-shadow(0 0 5px ${c})`, transition: 'stroke-dasharray .8s ease' }} />
                </svg>
                <div style={{
                  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: fontDisplay, fontSize: 14, fontWeight: 700, color: TEXT_HI,
                }}>{pct}</div>
              </div>
              <div>
                <div style={{ fontFamily: fontMono, fontSize: 10, color: TEXT_MD, letterSpacing: '0.16em' }}>{k}</div>
                <div style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO, marginTop: 2 }}>{hint}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

const RepairTile = ({ data }) => {
  const r = data?.oraRepair || {};
  // iter 322bk — dual area (Healed + Applied) matching target screenshot.
  // The `Healed` series uses successful repairs; `Applied` is the broader
  // attempts series. We re-use the same sparkline buckets for both, but if
  // backend exposes a separate series later we'll swap it in.
  const sparkSrc = (r.sparkline && r.sparkline.length > 0)
    ? r.sparkline.map((y, i) => ({ x: i, healed: y, applied: Math.max(y, Math.round(y * 1.1)) }))
    : (r.series || []).map((s, i) => ({ x: i, healed: s.v ?? 0, applied: s.v ?? 0 }));
  const wow = (r.deltaPct ?? 0);
  return (
    <Card testid="ora-repair-card">
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8,
      }}>
        <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase' }}>
          ORA Repair Effect
        </div>
        <div style={{ fontFamily: fontMono, color: wow >= 0 ? '#bef264' : '#fca5a5', fontSize: 10 }}>
          {wow >= 0 ? '+' : ''}{wow.toFixed(1)}% {wow >= 0 ? '↑' : '↓'} <span style={{ color: TEXT_LO, letterSpacing: '0.12em' }}>WOW</span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontFamily: fontDisplay, color: '#FFFFFF', fontSize: 34, fontWeight: 700 }}>
          {r.successPct ?? 0}<span style={{ fontSize: 18, color: '#22c55e' }}>%</span>
        </span>
        <span style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10 }}>success</span>
      </div>
      <div style={{ fontFamily: fontMono, color: TEXT_MD, fontSize: 10, marginTop: 4, marginBottom: 8 }}>
        {(r.healed ?? 0).toLocaleString()} healed / {(r.attempts ?? 0).toLocaleString()} attempts
      </div>
      <div style={{ height: 90 }} data-testid="ora-repair-sparkline">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkSrc}>
            <defs>
              <linearGradient id="appliedOrange" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FFA552" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#FFA552" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="healedGreen" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.55} />
                <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="applied" stroke="#FFA552" strokeWidth={1.5} fill="url(#appliedOrange)" />
            <Area type="monotone" dataKey="healed"  stroke="#22c55e" strokeWidth={2}   fill="url(#healedGreen)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 14, marginTop: 4, fontFamily: fontMono, fontSize: 9, color: TEXT_MD }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 14, height: 2, background: '#22c55e', display: 'inline-block' }} /> Healed
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 14, height: 2, background: '#FFA552', display: 'inline-block' }} /> Applied
        </span>
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

// ── iter 322bj — AUREM PULSE hero + BUSINESS GROWTH chart ────────────
const fmtCurrency = (n) => {
  if (!n) return '$0';
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${Math.round(n)}`;
};

const ProgressMicro = ({ value, max, gradient }) => {
  const pct = Math.max(0, Math.min(100, (Number(value) / Math.max(1, Number(max))) * 100));
  return (
    <div style={{ width: '100%', height: 6, borderRadius: 99, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', background: gradient, transition: 'width .9s ease', borderRadius: 99 }} />
    </div>
  );
};

const AuremPulseHero = ({ data }) => {
  const rev = data?.totalRevenue || {};
  const hp = data?.websiteHealth || { value: 0, max: 100 };
  const af = data?.autoFix || { value: 0, target: 2000 };
  const bars = data?.pulseBars || [];
  const deltaUp = (rev.deltaPct ?? 0) >= 0;
  return (
    <Card testid="aurem-pulse-hero">
      <div style={{
        display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,220px)',
        gap: 22, alignItems: 'start',
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
            fontFamily: fontDisplay, fontSize: 11, letterSpacing: '0.24em',
            textTransform: 'uppercase', color: GOLD_HI,
          }}>
            AUREM PULSE
            {/* iter 322bk — heartbeat wave matching target screenshot */}
            <svg width="80" height="18" viewBox="0 0 80 18" data-testid="aurem-pulse-wave"
                 style={{ display: 'block' }}>
              <path d="M 0 9 L 16 9 L 22 4 L 28 14 L 34 2 L 40 14 L 46 9 L 80 9"
                    fill="none" stroke="#22c55e" strokeWidth="1.6" strokeLinecap="round"
                    style={{ filter: 'drop-shadow(0 0 5px rgba(34,197,94,0.6))' }} />
            </svg>
            <span style={{ color: data?.pulse?.active ? '#bef264' : '#fbbf24', fontFamily: fontMono, marginLeft: 'auto' }}>
              ● {data?.pulse?.active ? 'ACTIVE' : 'STANDBY'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
            <span data-testid="kpi-revenue-hero" style={{
              fontFamily: fontDisplay, fontSize: 'clamp(28px, 5vw, 40px)',
              color: TEXT_HI, fontWeight: 700, lineHeight: 1,
            }}>{fmtCurrency(rev.value)}</span>
            <span style={{ color: deltaUp ? '#bef264' : '#fca5a5', fontSize: 13, fontWeight: 600 }}>
              {(deltaUp ? '+' : '') + (rev.deltaPct ?? 0).toFixed(1)}% {deltaUp ? '↑' : '↓'}
            </span>
            <span style={{ color: deltaUp ? '#bef264' : '#fca5a5', fontSize: 13 }}>
              {(deltaUp ? '+' : '') + fmtCurrency(Math.abs(rev.deltaAbs || 0))}
            </span>
          </div>
          <div style={{ fontFamily: fontMono, color: TEXT_LO, fontSize: 10, letterSpacing: '0.14em',
                         textTransform: 'uppercase', marginTop: 6 }}>
            Total Revenue · last 30 days
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, marginTop: 22 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: TEXT_MD, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                  Website Health Score
                </span>
                <span data-testid="kpi-health-hero" style={{ fontFamily: fontDisplay, fontSize: 22, color: TEXT_HI, fontWeight: 700 }}>
                  {hp.value}<span style={{ color: TEXT_LO, fontSize: 12 }}>/{hp.max}</span>
                </span>
              </div>
              <ProgressMicro value={hp.value} max={hp.max}
                gradient="linear-gradient(90deg, #C9A227 0%, #F97316 100%)" />
              <div style={{ fontSize: 9, color: TEXT_LO, marginTop: 4, letterSpacing: '0.06em' }}>
                composite of GEO · SEC · ACC · SEO
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
                <span style={{ fontFamily: fontMono, fontSize: 10, color: TEXT_MD, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
                  Auto-Fix Live
                </span>
                <span data-testid="kpi-autofix-hero" style={{ fontFamily: fontDisplay, fontSize: 22, color: TEXT_HI, fontWeight: 700 }}>
                  {(af.value || 0).toLocaleString()}<span style={{ color: TEXT_LO, fontSize: 12 }}>/{(af.target || 2000).toLocaleString()}</span>
                </span>
              </div>
              <ProgressMicro value={af.value} max={af.target || 2000}
                gradient="linear-gradient(90deg, #2BB36C 0%, #bef264 100%)" />
              <div style={{ fontSize: 9, color: TEXT_LO, marginTop: 4, letterSpacing: '0.06em' }}>
                ORA patches applied today
              </div>
            </div>
          </div>
        </div>

        <div style={{ minWidth: 0 }}>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: TEXT_LO,
                        letterSpacing: '0.16em', textTransform: 'uppercase',
                        textAlign: 'right', marginBottom: 6 }}>
            Active · last 7 mo
          </div>
          <div style={{ height: 130 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bars} barCategoryGap="22%">
                <XAxis dataKey="month" tick={{ fontSize: 8, fill: TEXT_LO }}
                  axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: 'rgba(212,163,115,0.06)' }}
                  contentStyle={{ background: '#0F0F18', border: '1px solid rgba(212,163,115,0.18)', borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="value" fill="url(#pulseBarGold)" radius={[3, 3, 0, 0]} />
                <defs>
                  <linearGradient id="pulseBarGold" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FFE4A8" />
                    <stop offset="100%" stopColor="#8B7355" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </Card>
  );
};

const BusinessGrowthChart = ({ data }) => {
  const g = data?.growthMulti;
  const rows = (g?.leads || []).map((row, i) => ({
    x: row.x,
    Revenue: g.revenue?.[i]?.y || 0,
    Leads: g.leads?.[i]?.y || 0,
    Outreach: g.outreach?.[i]?.y || 0,
    'Pixel views': g.pixel_views?.[i]?.y || 0,
    'Auto-fixes': g.auto_fixes?.[i]?.y || 0,
  }));
  return (
    <Card testid="business-growth-card">
      <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 14 }}>
        Business Growth
      </div>
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 14, left: -14, bottom: 0 }}>
            <XAxis dataKey="x" tick={{ fontSize: 10, fill: TEXT_LO }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: TEXT_LO }} axisLine={false} tickLine={false} width={36} />
            <Tooltip contentStyle={{ background: '#0F0F18', border: '1px solid rgba(212,163,115,0.18)', borderRadius: 8, fontSize: 11 }} />
            <Line type="monotone" dataKey="Revenue"     stroke="#FFE4A8" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Leads"       stroke="#F97316" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Outreach"    stroke="#C9A227" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Pixel views" stroke="#9CA3AF" strokeWidth={1.5} strokeDasharray="3 3" dot={false} />
            <Line type="monotone" dataKey="Auto-fixes"  stroke="#bef264" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 10, fontSize: 10 }}>
        {[
          ['Revenue', '#FFE4A8'], ['Leads', '#F97316'], ['Outreach', '#C9A227'],
          ['Pixel views', '#9CA3AF'], ['Auto-fixes', '#bef264'],
        ].map(([k, c]) => (
          <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 5,
                                  color: TEXT_MD, letterSpacing: '0.08em', fontFamily: fontMono }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: c }} />{k}
          </span>
        ))}
      </div>
    </Card>
  );
};

// ── Home (target screenshot layout) ──────────────────────────────────
const HomePage = ({ data, isMobile, isTablet }) => (
  <div data-testid="page-home" style={{ padding: '4px 2px', display: 'flex', flexDirection: 'column', gap: 14 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <h1 style={{
        margin: 0, color: TEXT_HI, fontFamily: fontDisplay,
        fontSize: 'clamp(22px, 4vw, 30px)', fontWeight: 700, letterSpacing: '0.10em',
      }}>HOME</h1>
    </div>

    {/* Row 1 — AUREM PULSE hero (KPIs + mini bars) */}
    <AuremPulseHero data={data} />

    {/* Row 2 — Business Growth multi-line chart */}
    <BusinessGrowthChart data={data} />

    {/* Row 3 — Scan (4 individual dials) · Repair % + sparkline · Alerts */}
    <div style={{
      display: 'grid',
      gridTemplateColumns: isMobile ? '1fr' : isTablet ? '1fr 1fr' : 'minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr)',
      gap: 12,
    }}>
      <ScanRowFour data={data} />
      <RepairTile data={data} />
      <AlertsTile data={data} />
    </div>

    {/* ── iter 322bl — extra rows brought back below target layout ─── */}
    {/* Row 4 — Active Agents · Vanguard Security */}
    <div style={{
      display: 'grid',
      gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: 12,
    }}>
      <div style={{ minWidth: 0 }}><AgentsTileWrap agents={data.agents || []} /></div>
      <div style={{ minWidth: 0 }}><VanguardTile data={data} /></div>
    </div>

    {/* Row 5 — AUREM Working For You · Recent Activity · Pipeline This Month */}
    <CustomerResultsRow />

    <style>{`
      @keyframes luxe-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.4); }
      }
    `}</style>
  </div>
);

// AgentsTile already takes `gridColumn: span 2` for the original 4-col layout.
// In the new auto-fit grid we don't want that column-span; wrap to strip it.
const AgentsTileWrap = ({ agents }) => (
  <Card testid="agents-tile">
    <div style={{ fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', marginBottom: 14 }}>
      Active Agents (Real-Time)
    </div>
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(38px, 1fr))',
      gap: 10, alignItems: 'end',
    }}>
      {agents.map((a, i) => {
        const h = 16 + (a.v / 100) * 70;
        const isHi = a.v >= 70;
        const display = a.n >= 1000 ? `${(a.n / 1000).toFixed(1)}k` : String(a.n);
        return (
          <div key={i} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
            minHeight: 110, justifyContent: 'flex-end',
          }}
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

// ── Inner shell (auth-gated) ─────────────────────────────────────────
const Inner = () => {
  const { token, user, loading, logout } = useLuxeAuth();
  const { isMobile, isTablet, isDesktop } = useViewport();
  const [active, setActive] = useState('home');
  const [mobileOpen, setMobileOpen] = useState(false);
  const data = useLuxeDashboardData(token);

  const Page = useMemo(() => {
    switch (active) {
      case 'profile':       return <ProfilePage />;
      case 'live-health':   return <LiveHealthPage />;
      case 'security':      return <SecurityPage />;
      case 'automation':    return <AutomationPage />;
      case 'crm':           return <CRMPage />;
      case 'ora':           return <ORAPage />;
      case 'integrations':  return <IntegrationsPage />;
      case 'settings':      return <SettingsPage />;
      default:              return <HomePage data={data} isMobile={isMobile} isTablet={isTablet} />;
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
      <Sidebar
        active={active}
        onNav={setActive}
        onLogout={logout}
        user={user}
        isMobile={isMobile}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <HeaderStrip
          user={user}
          isMobile={isMobile}
          onMenuOpen={() => setMobileOpen(true)}
        />
        <div style={{
          flex: 1,
          padding: isMobile ? '12px 12px 24px' : isDesktop ? '24px 28px 32px' : 18,
          overflowY: 'auto',
          minHeight: 0,
          WebkitOverflowScrolling: 'touch',
        }}>
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
