/**
 * CustomerPortal — 8-item dedicated Customer Experience
 * ======================================================
 * Strictly isolated from Admin's 14-item sidebar (/dashboard/*).
 * Routes: /my, /my/website, /my/reviews, /my/social, /my/ora, /my/report, /my/billing, /my/settings
 *
 * Triggers FirstLoginWizard modal when must_set_password OR !wizard_complete.
 */

import React, { useEffect, useState, Suspense, lazy } from 'react';
import ReactDOM from 'react-dom';
import { Routes, Route, NavLink, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Home as HomeIcon, Globe, Star, Share2, MessageSquare,
  FileText, CreditCard, Settings, LogOut, Menu, X, ChevronRight, Activity, Award, Plug
} from 'lucide-react';
import { getPlatformToken, clearPlatformAuth as clearPlatformToken } from '../utils/secureTokenStore';
import '../styles/portal-global.css';

const API = process.env.REACT_APP_BACKEND_URL || '';

const FirstLoginWizard = lazy(() => import('./FirstLoginWizard'));
const CustomerHome = lazy(() => import('./customer/CustomerHome'));
const CustomerWebsite = lazy(() => import('./customer/CustomerWebsite'));
const CustomerReviews = lazy(() => import('./customer/CustomerReviews'));
const CustomerSocial = lazy(() => import('./customer/CustomerSocial'));
const CustomerOra = lazy(() => import('./customer/CustomerOra'));
const CustomerReport = lazy(() => import('./customer/CustomerReport'));
const CustomerBilling = lazy(() => import('./customer/CustomerBilling'));
const CustomerSettings = lazy(() => import('./customer/CustomerSettings'));
const CustomerReferrals = lazy(() => import('./customer/CustomerReferrals'));
const CustomerOnboarding = lazy(() => import('./customer/CustomerOnboarding'));
const CustomerIntegrations = lazy(() => import('./customer/CustomerIntegrations'));
// Site Monitor + Board Report — formerly mounted as standalone routes outside
// CustomerPortal (which made every page look "blank" because the portal's
// auth context + sidebar chrome never wrapped them). Now lazy-loaded as
// proper portal children.
const CustomerSiteMonitor = lazy(() => import('./CustomerSiteMonitor'));
const CustomerBoardReport = lazy(() => import('./CustomerBoardReport'));

const NAV_ITEMS = [
  { to: '/my',           label: 'Home',           icon: HomeIcon },
  { to: '/my/website',   label: 'My Website',     icon: Globe },
  { to: '/my/monitor',   label: 'Site Monitor',   icon: Activity },
  { to: '/my/board-report', label: 'Board Report', icon: Award },
  { to: '/my/reviews',   label: 'Google Reviews', icon: Star },
  { to: '/my/social',    label: 'Social Media',   icon: Share2 },
  { to: '/my/ora',       label: 'ORA Chat',       icon: MessageSquare },
  { to: '/my/report',    label: 'Monthly Report', icon: FileText },
  { to: '/my/billing',   label: 'Billing',        icon: CreditCard },
  { to: '/my/integrations', label: 'Integrations', icon: Plug },
  { to: '/my/settings',  label: 'Settings',       icon: Settings },
];

const COLORS = {
  bg:     '#08080F',
  panel:  '#0D0D17',
  border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37',
  accent2:'#FF6B00',
  text:   '#E8E0D0',
  textD:  '#8A8070',
};
// Decode the JWT we already have so the portal still renders something
// useful when /api/bin-auth/customer-context fails (network blip, CF 520,
// transient backend restart). Returns minimal {role, business_id, email,
// name} or null if token can't be decoded.
function _ctxFromJwt(token) {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    const isAdmin = !!(payload.is_admin || payload.is_super_admin
                       || payload.role === 'admin' || payload.role === 'super_admin');
    return {
      email: payload.email || '',
      name: payload.name || (payload.email || '').split('@')[0] || 'You',
      bin: payload.business_id || '',
      role: isAdmin ? 'admin' : 'customer',
      plan: payload.plan || 'Trial',
      must_set_password: false,
      wizard_complete: true,
      smart_onboarding_complete: true,
    };
  } catch {
    return null;
  }
}


function PortalLoader({ label = 'Loading...', inline = false }) {
  if (inline) {
    return (
      <div
        data-testid="customer-portal-loader-inline"
        style={{
          minHeight: '60vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: 22,
          background: 'rgba(255,255,255,0.06)',
          backdropFilter: 'blur(26px) saturate(150%)',
          WebkitBackdropFilter: 'blur(26px) saturate(150%)',
          border: '1px solid rgba(212,175,55,0.18)',
          boxShadow: '0 24px 60px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)',
          color: '#F0EADC',
          fontFamily: "'Jost',sans-serif",
          fontSize: 12,
          letterSpacing: '0.2em',
          textTransform: 'uppercase',
        }}
      >
        <span style={{opacity:0.75}}>{label}</span>
      </div>
    );
  }
  return (
    <div data-testid="customer-portal-loader" style={{height:'100vh',display:'flex',alignItems:'center',justifyContent:'center',background:COLORS.bg,color:COLORS.textD,fontFamily:"'Jost',sans-serif",fontSize:13,letterSpacing:'0.15em',textTransform:'uppercase'}}>
      {label}
    </div>
  );
}

export default function CustomerPortal() {
  const navigate = useNavigate();
  const [ctx, setCtx] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true);

  const loadContext = React.useCallback(async () => {
    const tok = getPlatformToken();
    if (!tok) { navigate('/login'); return; }
    try {
      const res = await fetch(`${API}/api/bin-auth/customer-context`, {
        headers: { 'Authorization': `Bearer ${tok}` },
      });
      if (res.status === 401) { navigate('/login'); return; }
      if (!res.ok) {
        // Backend up but returned 4xx/5xx — fall back to JWT decode so the
        // portal still renders with whatever user data we have, and the
        // sidebar/dashboard appears instead of an empty background.
        console.warn(`[Customer] context endpoint ${res.status}, using JWT fallback`);
        const fallback = _ctxFromJwt(tok);
        if (fallback) {
          setCtx(fallback);
          return;
        }
        // No JWT either — kick to login
        navigate('/login');
        return;
      }
      const data = await res.json();
      setCtx(data);
      if (data.must_set_password || (!data.wizard_complete && data.role !== 'admin')) {
        setWizardOpen(true);
      } else if (
        data.role !== 'admin' &&
        data.wizard_complete &&
        !data.smart_onboarding_complete &&
        typeof window !== 'undefined' &&
        window.location.pathname === '/my'
      ) {
        // First-login done but smart onboarding pending → auto-redirect to smart form
        navigate('/my/onboarding', { replace: true });
      }
    } catch (e) {
      console.warn('[Customer] Context load failed:', e);
      // Network failure (e.g. Cloudflare 520, transient backend hiccup).
      // Decode the JWT to get at least name + role + business_id and
      // render the portal in degraded mode rather than showing just bg+ORA.
      const fallback = _ctxFromJwt(tok);
      if (fallback) {
        setCtx({ ...fallback, _degraded: true });
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => { loadContext(); }, [loadContext]);

  useEffect(() => {
    const onResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const handleLogout = () => {
    clearPlatformToken();
    navigate('/login');
  };

  if (loading) return <PortalLoader label="Initializing..." />;
  if (!ctx) {
    // Final fallback — should be very rare since loadContext now decodes
    // JWT on failure. Show actionable retry instead of a frozen label.
    return (
      <div data-testid="customer-portal-needs-auth"
           style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',
                   flexDirection:'column',gap:18,background:COLORS.bg,color:COLORS.text,
                   fontFamily:"'Jost',sans-serif",padding:28,textAlign:'center'}}>
        <div style={{fontSize:13,letterSpacing:'0.18em',textTransform:'uppercase',color:COLORS.textD}}>
          Couldn't verify your session
        </div>
        <div style={{fontSize:13,color:COLORS.textD,maxWidth:420,lineHeight:1.6}}>
          Your token is valid but the portal couldn't reach the customer-context API.
          This is usually a transient network issue.
        </div>
        <div style={{display:'flex',gap:10,marginTop:12}}>
          <button data-testid="portal-retry-btn"
            onClick={() => { setLoading(true); loadContext(); }}
            style={{padding:'10px 20px',background:COLORS.gold,color:'#0A0A00',
                    border:'none',borderRadius:8,fontWeight:600,cursor:'pointer'}}>
            Retry
          </button>
          <button data-testid="portal-relogin-btn"
            onClick={handleLogout}
            style={{padding:'10px 20px',background:'transparent',color:COLORS.text,
                    border:`1px solid ${COLORS.border}`,borderRadius:8,fontWeight:600,cursor:'pointer'}}>
            Sign in again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="customer-portal" className="customer-portal-bg portal-shell relative" style={{minHeight:'100vh',color:COLORS.text,fontFamily:"'Jost',sans-serif",display:'flex'}}>
      {/* Background video — full-screen, muted, looped (iter 322d) */}
      <video
        data-testid="portal-bg-video"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        className="fixed inset-0 w-full h-full object-cover"
        style={{ zIndex: 0, opacity: 0.45, pointerEvents: 'none' }}
      >
        <source src="/videos/login-bg.mp4" type="video/mp4" />
      </video>
      {/* Vignette overlay so cards stay readable */}
      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: 0,
          background:
            'radial-gradient(ellipse at center, rgba(5,5,10,0.55) 0%, rgba(5,5,10,0.82) 70%, rgba(5,5,10,0.93) 100%)',
        }}
      />
      {/* Layered background: circuit overlay + CSS-only robot mascot */}
      <div className="portal-circuit" aria-hidden="true" />
      <div className="portal-robot" aria-hidden="true" data-testid="portal-robot">
        <span className="antenna" />
        <span className="head" />
        <span className="visor" />
        <span className="jaw" />
      </div>
      {/* ── Floating Glass Sidebar ── */}
      {(isDesktop || sidebarOpen) && (
        <motion.aside data-testid="customer-sidebar"
          initial={{ x: -40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 180, damping: 22 }}
          className="spatial-glass-flat portal-sidebar-glass"
          style={{
            width: isDesktop ? 248 : 260,
            flexShrink:0,
            display:'flex',flexDirection:'column',padding:'22px 14px',
            position:isDesktop?'fixed':'fixed',
            top: isDesktop ? 20 : 0,
            left: isDesktop ? 20 : 0,
            bottom: isDesktop ? 20 : 0,
            height: isDesktop ? 'calc(100vh - 40px)' : '100vh',
            borderRadius: isDesktop ? 22 : 0,
            zIndex:50,
            background: 'rgba(13, 13, 23, 0.68)',
            backdropFilter: 'blur(28px) saturate(160%)',
            WebkitBackdropFilter: 'blur(28px) saturate(160%)',
            border: `1px solid ${COLORS.border}`,
            boxShadow: '0 24px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(212,175,55,0.18)',
          }}
        >
          {/* Logo + BIN */}
          <div style={{marginBottom:22,paddingBottom:18,borderBottom:`1px solid ${COLORS.border}`}}>
            <div style={{display:'flex',alignItems:'center',gap:10}}>
              <motion.div
                animate={{ y: [0, -3, 0] }}
                transition={{ duration: 3.6, repeat: Infinity, ease: 'easeInOut' }}
                style={{width:38,height:38,borderRadius:12,background:'linear-gradient(135deg,#F97316,#C9A227)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:16,fontWeight:900,color:'#0A0A00',boxShadow:'0 8px 24px rgba(249,115,22,0.45)'}}>
                A
              </motion.div>
              <div>
                <div style={{fontFamily:"'Cinzel',serif",fontSize:15,fontWeight:700,color:'#FFF',letterSpacing:'0.05em',textShadow:'0 0 16px rgba(249,115,22,0.35)'}}>AUREM</div>
                <div style={{fontSize:9,letterSpacing:'0.18em',color:COLORS.textD,textTransform:'uppercase',display:'flex',alignItems:'center',gap:4}}>
                  <span className="lightning-pulse inline-block w-1 h-1 rounded-full" style={{background:'#68DA8D'}}/>
                  Customer · Live
                </div>
              </div>
              {!isDesktop && (
                <button data-testid="customer-sidebar-close" onClick={()=>setSidebarOpen(false)} style={{marginLeft:'auto',background:'none',border:'none',color:COLORS.textD,cursor:'pointer'}}><X size={18}/></button>
              )}
            </div>
            <div style={{marginTop:14,padding:'10px 12px',borderRadius:10,background:'rgba(249,115,22,0.08)',border:'1px solid rgba(249,115,22,0.18)',position:'relative',overflow:'hidden'}}>
              <div style={{fontSize:9,letterSpacing:'0.18em',color:COLORS.textD,textTransform:'uppercase'}}>Your BIN</div>
              <div data-testid="customer-bin" className="portal-bin" style={{fontSize:13,fontWeight:700,marginTop:2}}>{ctx.bin || '—'}</div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{flex:1,display:'flex',flexDirection:'column',gap:3}}>
            {NAV_ITEMS.map(({to,label,icon:Icon}, i) => (
              <motion.div
                key={to}
                initial={{ x: -16, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: 0.08 + i * 0.04, type: 'spring', stiffness: 220, damping: 20 }}
              >
                <NavLink
                  to={to}
                  end={to==='/my'}
                  data-testid={`customer-nav-${label.toLowerCase().replace(/\s+/g,'-')}`}
                  onClick={()=>!isDesktop && setSidebarOpen(false)}
                  style={({isActive}) => ({
                    display:'flex',alignItems:'center',gap:12,padding:'11px 14px',borderRadius:11,
                    textDecoration:'none',fontSize:13.5,fontWeight:500,letterSpacing:'0.02em',
                    color:isActive?'#F97316':'rgba(255,255,255,0.55)',
                    background:isActive?'rgba(249,115,22,0.10)':'transparent',
                    borderLeft:`2px solid ${isActive?'#F97316':'transparent'}`,
                    boxShadow:isActive?'inset 4px 0 12px rgba(249,115,22,0.05)':'none',
                    transition:'all 0.25s cubic-bezier(.4,0,.2,1)',
                  })}
                >
                  {({isActive})=> (
                    <>
                      <Icon size={16} strokeWidth={isActive?2.4:2}/> {label}
                      {isActive && <ChevronRight size={13} style={{marginLeft:'auto'}}/>}
                    </>
                  )}
                </NavLink>
              </motion.div>
            ))}
          </nav>

          {/* Footer */}
          <div style={{marginTop:'auto',paddingTop:18,borderTop:`1px solid ${COLORS.border}`}}>
            {/* iter 322bg — 1-click ORA PWA SSO. Token already in localStorage,
                so /ora reads it and auto-skips the platform/login page. */}
            <a
              href="/ora"
              data-testid="customer-open-ora-pwa"
              style={{
                width:'100%',
                display:'flex',
                alignItems:'center',
                justifyContent:'center',
                gap:8,
                padding:'11px 12px',
                borderRadius:11,
                marginBottom:10,
                textDecoration:'none',
                color:'#0A0A00',
                fontWeight:700,
                fontSize:12.5,
                letterSpacing:'0.06em',
                textTransform:'uppercase',
                fontFamily:"'Jost',sans-serif",
                background:'linear-gradient(135deg,#F97316,#C9A227)',
                boxShadow:'0 8px 22px rgba(249,115,22,0.35)',
                transition:'transform 0.2s ease, box-shadow 0.2s ease',
              }}
              onMouseEnter={(e)=>{
                e.currentTarget.style.transform='translateY(-1px)';
                e.currentTarget.style.boxShadow='0 12px 28px rgba(249,115,22,0.5)';
              }}
              onMouseLeave={(e)=>{
                e.currentTarget.style.transform='translateY(0)';
                e.currentTarget.style.boxShadow='0 8px 22px rgba(249,115,22,0.35)';
              }}
            >
              <span style={{width:7,height:7,borderRadius:'50%',background:'#0A0A00',boxShadow:'0 0 8px rgba(0,0,0,0.4)'}}/>
              Open ORA AI
            </a>
            <div style={{fontSize:11,color:COLORS.textD,marginBottom:8,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
              {ctx.full_name || ctx.email}
            </div>
            <button
              data-testid="customer-logout"
              onClick={handleLogout}
              style={{width:'100%',display:'flex',alignItems:'center',gap:10,padding:'9px 10px',borderRadius:10,background:'transparent',border:`1px solid ${COLORS.border}`,color:COLORS.textD,cursor:'pointer',fontSize:12,fontFamily:"'Jost',sans-serif",transition:'all 0.25s'}}
              onMouseEnter={(e)=>{e.currentTarget.style.background='rgba(255,107,0,0.08)';e.currentTarget.style.color='#FF6B00';}}
              onMouseLeave={(e)=>{e.currentTarget.style.background='transparent';e.currentTarget.style.color=COLORS.textD;}}
            >
              <LogOut size={14}/> Logout
            </button>
          </div>
        </motion.aside>
      )}

      {/* ── Main content ── */}
      <main style={{flex:1,minWidth:0,display:'flex',flexDirection:'column',marginLeft: isDesktop ? 288 : 0, position:'relative', zIndex:1}}>
        {/* Top bar (mobile) */}
        {!isDesktop && (
          <header style={{padding:'12px 16px',borderBottom:`1px solid ${COLORS.border}`,background:'rgba(13,13,23,0.85)',backdropFilter:'blur(18px)',display:'flex',alignItems:'center',justifyContent:'space-between',position:'sticky',top:0,zIndex:20}}>
            <button data-testid="customer-sidebar-open" onClick={()=>setSidebarOpen(true)} style={{background:'none',border:'none',color:COLORS.text,cursor:'pointer'}}><Menu size={20}/></button>
            <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:12,color:COLORS.accent,fontWeight:700}}>{ctx.bin}</div>
          </header>
        )}

        {/* Routes with page transitions — max-width + right-biased to avoid
            clashing with the robot hero subject on the left of the viewport.
            Identity strip at top is shared across all /my/* pages. */}
        <div style={{flex:1, padding:isDesktop?'28px 40px 40px':'16px 14px', overflowY:'auto'}}>
          <div style={{maxWidth: 920, marginLeft:isDesktop?'auto':0, marginRight:0}}>
            <IdentityStrip ctx={ctx} />
            <Suspense fallback={<PortalLoader label="Loading section..." inline />}>
              <AnimatedRoutes ctx={ctx} reload={loadContext} />
            </Suspense>
          </div>
        </div>
      </main>

      {/* First-Login Wizard (modal) */}
      {wizardOpen && (
        <Suspense fallback={null}>
          <FirstLoginWizard
            ctx={ctx}
            onComplete={() => { setWizardOpen(false); loadContext(); }}
          />
        </Suspense>
      )}
    </div>
  );
}

function AnimatedRoutes({ ctx, reload }) {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -12 }}
        transition={{ duration: 0.32, ease: [0.25, 0.8, 0.25, 1] }}
      >
        <Routes location={location}>
          <Route index element={<CustomerHome ctx={ctx} />} />
          <Route path="website" element={<CustomerWebsite ctx={ctx} />} />
          <Route path="monitor" element={<CustomerSiteMonitor ctx={ctx} />} />
          <Route path="board-report" element={<CustomerBoardReport ctx={ctx} />} />
          <Route path="reviews" element={<CustomerReviews ctx={ctx} />} />
          <Route path="social" element={<CustomerSocial ctx={ctx} />} />
          <Route path="ora" element={<CustomerOra ctx={ctx} />} />
          <Route path="report" element={<CustomerReport ctx={ctx} />} />
          <Route path="billing" element={<CustomerBilling ctx={ctx} />} />
          <Route path="integrations" element={<CustomerIntegrations ctx={ctx} />} />
          <Route path="settings" element={<CustomerSettings ctx={ctx} reload={reload} />} />
          <Route path="referrals" element={<CustomerReferrals ctx={ctx} />} />
          <Route path="onboarding" element={<CustomerOnboarding ctx={ctx} />} />
          <Route path="*" element={<Navigate to="/my" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

// Shared helpers exposed to customer/* pages
export const CUSTOMER_COLORS = COLORS;
export { PortalLoader };

/**
 * IdentityStrip — top-banner showing BIN · Name · Email · Company.
 * Rendered once at the top of the customer portal main area so every
 * sub-page (Home, Website, Report, Billing, Social, Reviews, Referrals,
 * Settings, ORA) inherits a consistent identity header.
 */
function IdentityStrip({ ctx }) {
  const [pixel, setPixel] = React.useState({ status: 'loading' });
  const [pixelModalOpen, setPixelModalOpen] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const tok = (await import('../utils/secureTokenStore')).getPlatformToken();
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/customer/pixel/status`, {
          headers: { Authorization: `Bearer ${tok}` },
        });
        if (!alive) return;
        if (res.ok) {
          const j = await res.json();
          setPixel(j);
        } else {
          setPixel({ status: 'not_installed' });
        }
      } catch (e) {
        if (alive) setPixel({ status: 'not_installed' });
      }
    };
    load();
    const iv = setInterval(load, 30000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  if (!ctx) return null;

  const pixelInfo = (() => {
    if (pixel.status === 'online')
      return { dot: '#22C55E', label: 'PIXEL ACTIVE', sub: 'Online · monitoring live' };
    if (pixel.status === 'offline')
      return { dot: '#FF8A3D', label: 'PIXEL OFFLINE', sub: 'Last seen: ' + (pixel.last_event_at || '').slice(5, 16) };
    if (pixel.status === 'not_installed')
      return { dot: '#6B7280', label: 'PIXEL NOT INSTALLED', sub: 'Click to install on your site' };
    return { dot: '#6B7280', label: 'CHECKING…', sub: '' };
  })();

  const cells = [
    { label: 'BIN', value: ctx.bin, mono: true, accent: true },
    { label: 'Name', value: ctx.full_name || '—' },
    { label: 'Email', value: ctx.email },
    { label: 'Company', value: ctx.business_name || '—' },
  ];
  return (
    <div
      data-testid="portal-identity-strip"
      className="portal-identity-bar glass-card"
      style={{
        marginBottom: 22,
      }}
    >
      {cells.map((c, i) => (
        <div
          key={i}
          data-testid={`identity-${c.label.toLowerCase()}`}
          style={{
            flex: '1 1 160px',
            minWidth: 140,
            paddingRight: 14,
            borderRight: '1px solid rgba(212,175,55,0.10)',
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: '#8A8070',
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              marginBottom: 4,
              fontWeight: 600,
            }}
          >
            {c.label}
          </div>
          <div
            className={c.accent ? 'portal-bin' : ''}
            style={{
              fontSize: c.mono ? 14 : 13,
              color: c.accent ? 'var(--portal-orange)' : '#E8E0D0',
              fontFamily: c.accent ? "'Cinzel', serif" : (c.mono ? "'JetBrains Mono', monospace" : "'Jost', sans-serif"),
              fontWeight: c.mono ? 700 : 500,
              letterSpacing: c.accent ? '0.15em' : 'normal',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={c.value}
          >
            {c.value}
          </div>
        </div>
      ))}
      {/* Pixel status cell */}
      <div data-testid="identity-pixel-status" style={{ flex: '1 1 200px', minWidth: 180, paddingRight: 4 }}>
        <div style={{ fontSize: 10, color: '#8A8070', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 4, fontWeight: 600 }}>
          Status
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 10, height: 10, borderRadius: 999,
            background: pixelInfo.dot,
            boxShadow: `0 0 10px ${pixelInfo.dot}cc`,
            animation: pixel.status === 'online' ? 'pixelPulse 1.8s ease-in-out infinite' : 'none',
            flexShrink: 0,
          }} />
          <div style={{ overflow: 'hidden', flex: 1 }}>
            <div style={{
              fontSize: 12, color: pixelInfo.dot, fontFamily: "'Jost',sans-serif", fontWeight: 700,
              letterSpacing: '0.06em', whiteSpace: 'nowrap',
            }}>{pixelInfo.label}</div>
            <div style={{ fontSize: 10, color: '#8A8070', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {pixelInfo.sub}
            </div>
          </div>
          {(pixel.status === 'not_installed' || pixel.status === 'offline') && (
            <button
              data-testid="identity-add-pixel-btn"
              onClick={() => setPixelModalOpen(true)}
              title={pixel.status === 'offline' ? 'Reinstall pixel' : 'Install pixel on your site'}
              style={{
                padding: '6px 12px',
                borderRadius: 999,
                background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)',
                color: '#0A0A0F',
                border: 'none',
                cursor: 'pointer',
                fontSize: 10,
                fontWeight: 800,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                fontFamily: "'Jost',sans-serif",
                boxShadow: '0 6px 18px rgba(212,175,55,0.35)',
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
            >
              {pixel.status === 'offline' ? 'Reinstall' : '+ Add Pixel'}
            </button>
          )}
        </div>
      </div>
      {pixelModalOpen && (
        <PixelInstallModal
          onClose={() => setPixelModalOpen(false)}
          onInstalled={() => setPixel({ status: 'online', last_event_at: new Date().toISOString() })}
        />
      )}
    </div>
  );
}

/**
 * PixelInstallModal — focused modal that ONLY surfaces the pixel install
 * snippet + copy button. Replaces the previous flow which navigated to the
 * full /my/settings page and scrolled to a hash anchor (heavy, jarring).
 *
 * Reads from GET /api/customer/api-key (same source as the Settings page
 * section), so behaviour stays consistent.
 */
function PixelInstallModal({ onClose, onInstalled }) {
  const [info, setInfo] = React.useState(null);
  const [copied, setCopied] = React.useState(false);
  const [verifying, setVerifying] = React.useState(false);
  const [err, setErr] = React.useState('');

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const tok = (await import('../utils/secureTokenStore')).getPlatformToken();
        const r = await fetch(`${API}/api/customer/api-key`, {
          headers: { Authorization: `Bearer ${tok}` },
        });
        let j = r.ok ? await r.json() : { has_key: false };
        // Self-heal: if no key has ever been issued for this account, mint one
        // on demand so the user gets the snippet immediately instead of the
        // "come back later" message. Only triggers when has_key is genuinely
        // false (avoids touching existing keys).
        if (!j.has_key) {
          try {
            const reg = await fetch(`${API}/api/customer/api-key/regenerate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` },
              body: JSON.stringify({ confirm: true }),
            });
            if (reg.ok) {
              // Re-fetch the canonical record so all derived fields (preview,
              // events_total, etc.) are populated by the server.
              const r2 = await fetch(`${API}/api/customer/api-key`, {
                headers: { Authorization: `Bearer ${tok}` },
              });
              if (r2.ok) j = await r2.json();
            }
          } catch (_) { /* fall through with original j */ }
        }
        if (alive) setInfo(j);
      } catch (e) {
        if (alive) setErr('Could not load pixel snippet. Try again in a moment.');
      }
    })();
    return () => { alive = false; };
  }, []);

  // Close on ESC key
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const copySnippet = () => {
    if (!info?.snippet) return;
    navigator.clipboard.writeText(info.snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2200);
  };

  const verify = async () => {
    setVerifying(true);
    setErr('');
    try {
      const tok = (await import('../utils/secureTokenStore')).getPlatformToken();
      const r = await fetch(`${API}/api/customer/pixel/status`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      const j = r.ok ? await r.json() : { status: 'not_installed' };
      if (j.status === 'online') {
        onInstalled?.();
        onClose();
      } else {
        setErr('Pixel not detected yet. Make sure the snippet is published before </head> and reload your site once.');
      }
    } catch (e) {
      setErr('Verification failed — check connection and retry.');
    } finally {
      setVerifying(false);
    }
  };

  const modalNode = (
    <div
      data-testid="pixel-install-modal"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 99999,
        background: 'rgba(5,5,12,0.82)', backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
        // Prevent any transform/filter parent from creating a containing
        // block that traps position:fixed (handled via portal below; this
        // is belt-and-suspenders).
        transform: 'none', filter: 'none', willChange: 'auto',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(560px, 100%)',
          maxHeight: '90vh', overflowY: 'auto',
          borderRadius: 18, padding: 26,
          background: 'linear-gradient(180deg, rgba(15,18,28,0.96) 0%, rgba(8,8,15,0.96) 100%)',
          border: '1px solid rgba(212,175,55,0.22)',
          boxShadow: '0 30px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(212,175,55,0.12)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <div style={{ fontFamily: "'Cinzel',serif", fontSize: 20, fontWeight: 700, color: '#FFF', letterSpacing: '0.04em' }}>
              Install Your AUREM Pixel
            </div>
            <div style={{ fontSize: 12, color: '#8A8070', marginTop: 4 }}>
              One snippet · pasted before <code style={{ color: '#D4AF37', fontFamily: "'JetBrains Mono',monospace" }}>&lt;/head&gt;</code> on your site.
            </div>
          </div>
          <button
            data-testid="pixel-modal-close"
            onClick={onClose}
            aria-label="Close"
            style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              color: '#8A8070', cursor: 'pointer', fontSize: 16, lineHeight: '30px',
            }}
          >×</button>
        </div>

        {!info && !err && (
          <div data-testid="pixel-modal-loading" style={{ padding: 20, textAlign: 'center', color: '#8A8070', fontSize: 13 }}>
            Loading your snippet…
          </div>
        )}

        {err && (
          <div data-testid="pixel-modal-error" style={{ padding: 14, borderRadius: 10, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#FCA5A5', fontSize: 12 }}>
            {err}
          </div>
        )}

        {info && info.has_key && (
          <>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 10, letterSpacing: '0.18em', textTransform: 'uppercase', color: '#8A8070', fontWeight: 600, marginBottom: 6 }}>
                Install Snippet
              </div>
              <div
                data-testid="pixel-modal-snippet"
                style={{
                  padding: 14, borderRadius: 10,
                  background: 'rgba(0,0,0,0.45)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  fontFamily: "'JetBrains Mono',monospace",
                  fontSize: 11, color: '#D4D4D4', lineHeight: 1.55,
                  wordBreak: 'break-all',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {info.snippet}
              </div>
              <button
                data-testid="pixel-modal-copy"
                onClick={copySnippet}
                style={{
                  marginTop: 10, padding: '10px 16px', borderRadius: 9,
                  background: 'linear-gradient(135deg,#D4AF37,#B19A5E)',
                  border: 'none', color: '#0A0A00',
                  fontSize: 12, fontWeight: 700, letterSpacing: '0.1em',
                  textTransform: 'uppercase', cursor: 'pointer', fontFamily: "'Jost',sans-serif",
                }}
              >
                {copied ? 'Copied ✓' : 'Copy install code'}
              </button>
            </div>

            <ol style={{ paddingLeft: 20, color: '#B8B0A0', fontSize: 12, lineHeight: 1.7, margin: '0 0 16px' }}>
              <li>Open your site's HTML editor (or theme's <code>&lt;head&gt;</code> snippet area).</li>
              <li>Paste the code above immediately before <code>&lt;/head&gt;</code>.</li>
              <li>Save & publish, then click <strong>Verify Install</strong> below.</li>
            </ol>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                data-testid="pixel-modal-verify"
                onClick={verify}
                disabled={verifying}
                style={{
                  padding: '10px 18px', borderRadius: 9,
                  background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.4)',
                  color: '#86EFAC', fontSize: 12, fontWeight: 700, letterSpacing: '0.1em',
                  textTransform: 'uppercase', cursor: verifying ? 'wait' : 'pointer',
                  fontFamily: "'Jost',sans-serif",
                }}
              >
                {verifying ? 'Verifying…' : 'Verify Install'}
              </button>
              <a
                href="/my/settings#pixel-install"
                data-testid="pixel-modal-advanced"
                style={{ fontSize: 11, color: '#8A8070', textDecoration: 'none' }}
              >
                Advanced settings →
              </a>
            </div>
          </>
        )}

        {info && !info.has_key && (
          <div data-testid="pixel-modal-no-key" style={{ padding: 14, borderRadius: 10, background: 'rgba(212,175,55,0.05)', border: '1px solid rgba(212,175,55,0.15)', color: '#B8B0A0', fontSize: 12 }}>
            {info.message || 'Your pixel key has not been provisioned yet. Try again in a few seconds, or open Settings → API Key.'}
          </div>
        )}
      </div>
    </div>
  );

  // Render via portal so the modal escapes any framer-motion transform
  // parent (transforms create a containing block that traps position:fixed
  // children, which caused the modal to render mis-positioned/clipped
  // inside the page content area instead of centered over the viewport).
  return typeof document !== 'undefined' && document.body
    ? ReactDOM.createPortal(modalNode, document.body)
    : modalNode;
}
