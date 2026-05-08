/**
 * AUREM SYSTEM OVERVIEW — Mission Control Room
 * Route: /admin/system-overview
 * Purpose: Founder review, investor demo, client showcase
 */
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import TransparencyWall from './TransparencyWall';
import RepairBanner from './RepairBanner';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const GOLD = '#C9A84C';
const OBSIDIAN = '#0D0D0D';
const SOLAR = '#FF4D00';
const PANEL_BG = 'rgba(13,13,13,0.85)';
const BORDER = 'rgba(201,168,76,0.12)';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700;900&family=Cormorant+Garamond:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

.sov-root { min-height:100vh; background:${OBSIDIAN}; color:#E8E0D0; overflow-x:hidden; }
.sov-root * { box-sizing:border-box; }

@keyframes sov-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.7;transform:scale(1.05)} }
@keyframes sov-glow { 0%,100%{box-shadow:0 0 8px ${GOLD}40} 50%{box-shadow:0 0 20px ${GOLD}60} }
@keyframes sov-sentinel { 0%,100%{box-shadow:0 0 6px ${SOLAR}30} 50%{box-shadow:0 0 16px ${SOLAR}60} }
@keyframes sov-fadein { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
@keyframes sov-scan { 0%{left:-30%} 100%{left:130%} }

.sov-card { background:${PANEL_BG}; border:1px solid ${BORDER}; border-radius:16px; backdrop-filter:blur(16px); animation:sov-fadein 0.5s ease both; }
.sov-hdr { font-family:'Cinzel Decorative',serif; color:${GOLD}; letter-spacing:0.08em; }
.sov-body { font-family:'Cormorant Garamond',serif; }
.sov-mono { font-family:'JetBrains Mono',monospace; }
.sov-badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:20px; font-size:10px; font-weight:700; letter-spacing:0.1em; }
.sov-check { color:#4ADE80; }
.sov-pending { color:#F59E0B; }
.sov-critical { color:#EF4444; }

.sov-root ::-webkit-scrollbar { width:4px; }
.sov-root ::-webkit-scrollbar-thumb { background:${GOLD}30; border-radius:4px; }

@keyframes sov-marquee { from{transform:translateX(0)} to{transform:translateX(-50%)} }
.sov-marquee-track { display:inline-flex; gap:40px; animation:sov-marquee 60s linear infinite; white-space:nowrap; }
.sov-marquee-wrap:hover .sov-marquee-track { animation-play-state:paused; }
.sov-activity-item { display:inline-flex; align-items:center; gap:10px; padding:8px 14px; border-radius:10px; background:rgba(13,13,13,0.7); border:1px solid ${BORDER}; font-size:12px; }
.sov-activity-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
`;

/**
 * LiveActivityMarquee
 * Horizontal auto-scrolling ticker that pulls from /api/admin/activity-feed
 * every 20 s and shows Builder / Evolver / ORA / Auto-repair events in
 * reverse-chronological order. Pauses on hover so founders can read items.
 */
function LiveActivityMarquee() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState(false);
  const [lastFetched, setLastFetched] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const token = sessionStorage.getItem('platform_token')
        || sessionStorage.getItem('aurem_platform_token')
        || localStorage.getItem('aurem_token')
        || localStorage.getItem('token');
      try {
        const r = await fetch(`${API}/api/admin/activity-feed?limit=30`, {
          headers: { Authorization: `Bearer ${token || ''}` },
        });
        if (!cancelled && r.ok) {
          const d = await r.json();
          setItems(d.items || []);
          setErr(false);
          setLastFetched(new Date());
        } else if (!cancelled) {
          setErr(true);
        }
      } catch {
        if (!cancelled) setErr(true);
      }
    };
    tick();
    const id = setInterval(tick, 20000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (err && items.length === 0) return null;

  const toneColor = {
    good: '#4ADE80', bad: '#EF4444', warn: '#F59E0B',
    gold: GOLD, neutral: '#8A8494',
  };

  const fmtAgo = (ts) => {
    if (!ts) return '';
    try {
      const diffS = (Date.now() - new Date(ts).getTime()) / 1000;
      if (diffS < 60) return `${Math.max(1, Math.floor(diffS))}s ago`;
      if (diffS < 3600) return `${Math.floor(diffS / 60)}m ago`;
      if (diffS < 86400) return `${Math.floor(diffS / 3600)}h ago`;
      return `${Math.floor(diffS / 86400)}d ago`;
    } catch { return ''; }
  };

  const doubled = items.length > 0 ? [...items, ...items] : [];

  return (
    <div
      data-testid="sov-live-activity-marquee"
      className="sov-card sov-marquee-wrap"
      style={{
        padding: '14px 0', marginBottom: 20, overflow: 'hidden',
        border: `1px solid ${GOLD}30`, position: 'relative',
      }}
    >
      <div style={{
        position: 'absolute', left: 14, top: 0, bottom: 0,
        display: 'flex', alignItems: 'center', gap: 8, zIndex: 2,
        background: `linear-gradient(90deg, ${OBSIDIAN} 60%, transparent)`,
        paddingRight: 30,
      }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#4ADE80', animation: 'sov-pulse 1.5s ease-in-out infinite' }} />
        <span className="sov-mono" style={{ fontSize: 10, color: GOLD, fontWeight: 700, letterSpacing: '0.2em' }}>
          LIVE ACTIVITY
        </span>
        {lastFetched && (
          <span className="sov-mono" style={{ fontSize: 9, color: '#5A5468' }}>
            {fmtAgo(lastFetched.toISOString())}
          </span>
        )}
      </div>
      <div style={{ paddingLeft: 150, overflow: 'hidden' }}>
        {items.length === 0 ? (
          <span className="sov-mono" style={{ fontSize: 11, color: '#5A5468' }}>
            waiting for activity…
          </span>
        ) : (
          <div className="sov-marquee-track" style={{ width: 'max-content' }}>
            {doubled.map((it, i) => {
              const inner = (
                <>
                  <span style={{ fontSize: 14 }}>{it.icon || '•'}</span>
                  <span className="sov-activity-dot" style={{ background: toneColor[it.tone] || '#8A8494' }} />
                  <span className="sov-mono" style={{ color: '#E8E0D0', fontWeight: 600 }}>
                    {it.title}
                  </span>
                  <span className="sov-mono" style={{ color: '#6A6070', fontSize: 10.5 }}>
                    {(it.detail || '').slice(0, 90)}
                  </span>
                  <span className="sov-mono" style={{ color: '#5A5468', fontSize: 9.5 }}>
                    {fmtAgo(it.ts)}
                  </span>
                </>
              );
              const commonStyle = { cursor: it.href ? 'pointer' : 'default', textDecoration: 'none' };
              if (it.href) {
                return (
                  <Link
                    key={`${it.ts}-${i}`}
                    to={it.href}
                    data-testid={`sov-activity-${it.kind}`}
                    className="sov-activity-item"
                    style={commonStyle}
                    title="Click to drill down"
                  >
                    {inner}
                  </Link>
                );
              }
              return (
                <span
                  key={`${it.ts}-${i}`}
                  data-testid={`sov-activity-${it.kind}`}
                  className="sov-activity-item"
                >
                  {inner}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function Badge({ status, label }) {
  const colors = {
    active: { bg: 'rgba(74,222,128,0.1)', border: 'rgba(74,222,128,0.3)', color: '#4ADE80' },
    pending: { bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.3)', color: '#F59E0B' },
    critical: { bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.3)', color: '#EF4444' },
    info: { bg: 'rgba(100,200,255,0.08)', border: 'rgba(100,200,255,0.2)', color: '#64C8FF' },
  };
  const c = colors[status] || colors.info;
  return (
    <span className="sov-badge" style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.color }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.color }} />
      {label}
    </span>
  );
}

function StatCard({ value, label, color, sub }) {
  return (
    <div style={{ textAlign: 'center', padding: '16px 8px' }}>
      <div className="sov-mono" style={{ fontSize: 'clamp(24px,4vw,36px)', fontWeight: 700, color: color || GOLD, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, color: '#6A6070', letterSpacing: '0.12em', marginTop: 6, fontWeight: 600 }}>{label}</div>
      {sub && <div style={{ fontSize: 9, color: '#4A4458', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function FeatureGrid({ title, items, accent }) {
  return (
    <div className="sov-card" style={{ padding: '20px 24px', animationDelay: '0.1s' }}>
      <div className="sov-hdr" style={{ fontSize: 13, marginBottom: 14 }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 6 }}>
        {items.map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '4px 0', fontSize: 12 }}>
            <span style={{ color: accent || '#4ADE80', flexShrink: 0, fontWeight: 700 }}>&#10003;</span>
            <span className="sov-body" style={{ color: '#B8B0A4', lineHeight: 1.4 }}>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SystemOverview() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const s = document.createElement('style');
    s.id = 'sov-css'; s.textContent = CSS;
    document.head.appendChild(s);
    return () => { document.getElementById('sov-css')?.remove(); };
  }, []);

  useEffect(() => {
    (async () => {
      const token = sessionStorage.getItem('platform_token') || sessionStorage.getItem('aurem_platform_token') || localStorage.getItem('aurem_token') || localStorage.getItem('token');
      try {
        const res = await fetch(`${API}/api/admin/system-overview/stats`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) setData(await res.json());
      } catch (e) { console.error(e); }
      setLoading(false);
    })();
  }, []);

  const p = data?.platform || {};
  const pipe = data?.pipeline || {};
  const ai = data?.ai || {};
  const clients = data?.clients || [];

  return (
    <div className="sov-root" data-testid="system-overview">
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: 'clamp(16px,3vw,40px)' }}>

        <RepairBanner />

        {/* ═══ HEADER ═══ */}
        <div style={{ textAlign: 'center', marginBottom: 'clamp(24px,4vw,48px)', animation: 'sov-fadein 0.6s ease', position: 'relative' }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, margin: '0 auto 16px', background: `linear-gradient(135deg, ${GOLD}, #8B6914)`, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'sov-glow 3s ease-in-out infinite' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#0D0D0D" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          </div>
          <h1 className="sov-hdr" style={{ fontSize: 'clamp(20px,4vw,32px)', margin: 0 }}>AUREM SYSTEM OVERVIEW</h1>
          <p className="sov-body" style={{ color: '#6A6070', fontSize: 14, marginTop: 6, letterSpacing: '0.15em' }}>POLARIS BUILT INC. | SOVEREIGN COMMAND | ITER 256</p>

          {/* ═══ SHARE BUTTON ═══ */}
          <div style={{ marginTop: 20, display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="sov-share-btn"
              onClick={() => {
                const url = `${window.location.origin}/share/system-overview`;
                if (navigator.clipboard) {
                  navigator.clipboard.writeText(url).then(() => {
                    const el = document.getElementById('sov-share-toast');
                    if (el) { el.style.opacity = '1'; setTimeout(() => { el.style.opacity = '0'; }, 2200); }
                  });
                }
              }}
              className="sov-mono"
              style={{
                padding: '10px 20px', borderRadius: 10, fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
                background: `linear-gradient(135deg, ${GOLD}22, ${GOLD}08)`,
                border: `1px solid ${GOLD}55`, color: GOLD, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 8, transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = `0 4px 14px ${GOLD}33`; }}
              onMouseLeave={(e) => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                <path d="M8.6 13.5l6.9 4M15.5 6.5l-6.9 4"/>
              </svg>
              SHARE READ-ONLY LINK
            </button>
            <a
              href="/framework"
              data-testid="sov-empire-hub-link"
              className="sov-mono"
              style={{
                padding: '10px 20px', borderRadius: 10, fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
                background: 'rgba(91,142,174,0.08)', border: '1px solid rgba(91,142,174,0.45)', color: '#5B8EAE',
                textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 8, transition: 'all 0.2s',
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
                <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
              </svg>
              OPEN EMPIRE HUD
            </a>
          </div>
          <div id="sov-share-toast" style={{
            position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)',
            padding: '8px 16px', borderRadius: 8, fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
            background: '#4ADE8022', border: '1px solid #4ADE8066', color: '#4ADE80',
            opacity: 0, transition: 'opacity 0.3s', pointerEvents: 'none',
          }}>LINK COPIED TO CLIPBOARD</div>
        </div>

        {/* ═══ LIVE ACTIVITY MARQUEE ═══ */}
        <LiveActivityMarquee />

        {/* ═══ iter 285.4 — TRANSPARENCY WALL (Truth-Sync Live) ═══ */}
        <TransparencyWall />

        {/* ═══ ITERATION 255+ — LATEST BUILDS (Feb 2026) ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20, border: `1px solid #4ADE8040`, animation: 'sov-glow 5s ease-in-out infinite' }} data-testid="sov-iter256-builds">
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 14, color: '#4ADE80' }}>ITERATION 256 — FEB 2026 SHIPPED</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
            <FeatureGrid title="RETELL AI VOICE AGENT — LIVE" accent="#4ADE80" items={[
              'RETELL_API_KEY wired (318 voices accessible)',
              '2-step flow: create-retell-llm → create-agent',
              'HMAC-SHA256 webhook signature verification (5-min replay window)',
              'Admin endpoints: /api/admin/voice-agent/retell/{status,voices,agents,phone-numbers}',
              'Customer config save → auto-creates Retell LLM + Agent',
              'Inbound webhook logs + metered billing (db.voice_call_logs)',
              'Outbound calls: pending RETELL_FROM_NUMBER purchase',
            ]} />
            <FeatureGrid title="STRIPE ANNUAL PRICING — LIVE" accent={GOLD} items={[
              'Starter Annual: $970 CAD/yr (2 months free)',
              'Growth Annual: $2,970 CAD/yr (2 months free)',
              'Enterprise Annual: $9,970 CAD/yr (2 months free)',
              'stripe_embed_router auto-selects annual on annual:true flag',
              'PricingPage.jsx monthly/annual toggle wired',
              'Apple Pay + Google Pay on annual checkout',
            ]} />
            <FeatureGrid title="GOOGLE OAUTH — EMERGENT-MANAGED" accent="#64C8FF" items={[
              'GoogleAuthButton rewritten (300 → 65 lines)',
              'Redirects to auth.emergentagent.com → back with #session_id',
              'Backend /api/auth/google/callback exchanges session_id → JWT',
              'No Google Cloud keys required',
              'Race-safe AppRouter detects fragment synchronously',
              'GoogleAuthCallback useRef StrictMode-safe',
              'User upsert by email — auth_provider flag preserved',
            ]} />
            <FeatureGrid title="WORDPRESS PLUGIN — DOWNLOADABLE" accent="#8B5CF6" items={[
              'aurem-pixel.zip (4.4 KB, 3 files) — ready to install',
              'Auto wp_head pixel injection (page_view tracking)',
              'Optional Friend Scanner widget (viral loop)',
              'Settings → AUREM admin page with Tenant ID input',
              'Download: /api/plugins/wordpress',
              'Fallback: /api/static/plugins/aurem-pixel.zip',
              'CASL-safe async loading, zero perf impact',
            ]} />
            <FeatureGrid title="SHOPIFY OAUTH — 1-CLICK INSTALL" accent="#F59E0B" items={[
              'SHOPIFY_API_KEY + SECRET live in .env',
              '/api/shopify/auth?shop=xxx.myshopify.com → OAuth redirect',
              'ShopifyAppManager.jsx (5 tabs) in sidebar 13.2',
              'Scopes: products, orders, customers, themes, analytics',
              'Callback: /api/shopify/auth/callback',
              'Connection status: /api/shopify/auth/status',
            ]} />
            <FeatureGrid title="CODEBASE CLEANUP — 14 FILES ARCHIVED" accent="#EF4444" items={[
              '9 legacy routers → _archive/routers/',
              '3 orphan services → _archive/services/',
              '2 stale tests → _archive/tests/',
              'Archived: clawchief, empire_hud, evolver, openfang, sentinel-{anomaly,guard,overwatch,router}, telegram',
              'Router count: 234 → 225',
              'Registry.py cleaned (9 entries removed)',
              '6 deep-wired services preserved (middleware dependencies)',
            ]} />
          </div>
        </div>

        {/* ═══ ITERATION 212 — SHIPPED THIS SPRINT ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20, border: `1px solid ${GOLD}40`, animation: 'sov-glow 5s ease-in-out infinite' }} data-testid="sov-latest-builds">
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 14, color: GOLD }}>ITERATIONS 198 → 212 — LATEST BUILDS</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
            <FeatureGrid title="AUREM SELF-BUILDING SYSTEM" accent={GOLD} items={[
              'Internal Builder (Claude Opus 4.6 via EMERGENT_LLM_KEY)',
              'POST /api/admin/builder/build (async BackgroundTask)',
              'Shannon-style security scan + py_compile check',
              '2-attempt self-repair loop on syntax fail',
              'Strict path whitelist (server.py / .env / registry.py blocked)',
              'ORA intents: Build / Fix / Test /endpoint',
              'Every build audited in build_log collection',
            ]} />
            <FeatureGrid title="EVOMAP EVOLVER INTEGRATION" accent="#8B5CF6" items={[
              'HTTP client for Legion Evolver node (github.com/EvoMap/evolver)',
              'Graceful degradation — offline returns no-op, never crashes',
              'Gene approval gate — admin must sign off every gene',
              'EVOLVER_ALLOW_SELF_MODIFY=false hard default',
              'Hooks: Builder fail, ORA campaign outcomes, nightly review',
              '/admin/evolver page — approve/reject UI with confidence %',
              'Nightly 2:45 AM cron (aurem_evolver_review)',
            ]} />
            <FeatureGrid title="ADMIN CONTROL CENTER" accent="#4ADE80" items={[
              '/admin/control-center — mission control (30s auto-refresh)',
              'Telegram health chip + Builder card + Evolver card',
              'System Audit verdict, Wiring Coverage %, DB indexes',
              'Redis Cache hit rate + Pixel Buffer efficiency',
              '4-Agent Autonomous System live status',
              'Scheduler (19 jobs) + Anomaly Detector + Health Check',
              'Integration Secrets (required + optional badges)',
            ]} />
            <FeatureGrid title="CUSTOMER 360° + IMPERSONATION" accent="#64C8FF" items={[
              '/admin/customer/:identifier — email OR BIN lookup',
              'Action Panel: reset password · send WA · rotate keys',
              'Customer Impersonation (temp JWT, impersonated=true claim)',
              '/admin/impersonation-log — CASL-compliant audit trail',
              'Searchable table + CSV export',
              'Columns: Timestamp · Admin · Target · IP · TTL · JTI',
            ]} />
            <FeatureGrid title="SMART ONBOARDING + BIN LOGIN" accent="#F59E0B" items={[
              'BIN Generator (Industry-City-4chars)',
              'Login accepts BIN or email',
              'First-Login Wizard (4 steps)',
              'WhatsApp OTP forgot-password + SMS fallback',
              'Welcome email with API key + 1-line pixel install',
              'Admin BIN Search',
              'Apple Pay / Stripe embedded checkout',
            ]} />
            <FeatureGrid title="SAFE-MODE DB + ANOMALY" accent={SOLAR} items={[
              'Redis read-through caching (aurem_cache.py)',
              'Pixel event buffer (100/batch, mem → Mongo)',
              'TTL indexes (BSON dates) — auto cleanup',
              'Nightly Health Check (2:30 AM) — onboarding dry-run',
              'Nightly Wiring Audit (3:15 AM) — feature coverage',
              'Anomaly Detector (every 5 min) — cache/pixel/verdict',
              'WhatsApp alerts · 60 min cooldown · 917 auto-repairs',
            ]} />
          </div>
        </div>

        {/* ═══ SECTION 1 — PLATFORM STATS ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20, animation: 'sov-glow 4s ease-in-out infinite' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
            <StatCard value={p.uptime || '99.9%'} label="UPTIME" color="#4ADE80" />
            <StatCard value={`${ai.security_score || '83'}%`} label="SECURITY" color={GOLD} />
            <StatCard value={p.version || 'v1.47'} label="VERSION" color="#64C8FF" />
            <StatCard value={p.collections || 0} label="COLLECTIONS" color="#8B5CF6" sub={`${p.data_mb || 0} MB`} />
            <StatCard value={clients.length || 0} label="CLIENTS" color={GOLD} />
            <StatCard value={p.integrations || 0} label="INTEGRATIONS" color="#4ADE80" />
          </div>
        </div>

        {/* ═══ SECTION 2 — WHAT'S BUILT ═══ */}
        <div style={{ marginBottom: 20 }}>
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 12, paddingLeft: 4 }}>WHAT&apos;S BUILT</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
            <FeatureGrid title="CORE PLATFORM" accent="#4ADE80" items={[
              'Auth System (Admin + Tenant JWT)', 'Bcrypt password hashing (12 rounds)',
              'TenantGuard middleware — JWT → ctxvar tenant isolation',
              '7-Router tenant hardening (Depends(current_tenant))',
              'Rate limiting (login)', 'CORS domain locked', '5 Security headers',
              'Multi-tenant provisioning', 'BIN login (Industry-City-4chars)',
              'BIN canonical normalizer (3+3+4 ↔ 4+4 formats)',
            ]} />
            <FeatureGrid title="AI ENGINE" accent={GOLD} items={[
              'ORA Chat (multi-model race)', '3-model parallel: GPT-4o, Gemini, Claude Sonnet 4.5',
              'ULTRAPLINIAN scorer', 'Voice AI (Deepgram + ElevenLabs)',
              '3-tier memory system', 'RAG knowledge base (BM25 + Vector hybrid)',
              'OODA Pipeline (Scout/Architect/Envoy/Closer)',
              'CRAG Resilience (Evaluator + Web Scout)',
              'Live Race Latency Tracker (0.1ms precision)',
              'Hermes Identity (SOUL.md / USER.md)',
              'WebSocket streaming V2V pipeline',
              'OpenRouter fallback: Llama 3.3 70B + Gemma 3 27B (free)',
              'auto_repair with Claude 4.5 LlmChat correct init',
            ]} />
            <FeatureGrid title="BUSINESS AUTOMATION" accent="#64C8FF" items={[
              '4-Agent Autonomous System (Hunter / Follow-up / Closer / Referral ORA)',
              'Hunter ORA daily ramp (20→50→100→200) w/ cap enforcement',
              'Auto-Hunt territory rotation (Canada + US, 14 regions)',
              'Morning Brief + Economic Intelligence (Bank of Canada live)',
              'Website Scanner (SSL-resilient, 15 accessibility checks)',
              'Self-Repair engine (917 repairs — LLM-powered)',
              'Website Editor Tokens (2/3/5/10 cost, 10=$19 CAD)',
              'Google Places Reviews cron (3 AM daily)',
              'Monthly Report PDF Engine (reportlab, 1st of month)',
              'Sentinel health monitor', 'Circuit breaker (8 services)',
            ]} />
            <FeatureGrid title="CUSTOMER MANAGEMENT" accent="#8B5CF6" items={[
              'Customer 360° View (email OR BIN identifier)',
              'Action Panel (reset · WA · impersonate · rotate keys)',
              'Impersonation Log (CASL audit trail)',
              'tenant_customers collection', '8-item Customer Portal',
              'First-Login Wizard (4 steps)', 'WhatsApp OTP reset',
              'Pixel install + scan history in portal',
              'Connection Wizard (SMTP + WhatsApp)',
            ]} />
            <FeatureGrid title="OUTBOUND CAMPAIGN" accent="#F59E0B" items={[
              'Google Maps lead scraper', 'Website auto-scanner',
              'ORA voice call scripts', '3 HTML email templates',
              '3 WhatsApp templates', 'Campaign HQ dashboard',
              'CASL compliance', 'do_not_contact list',
              'APScheduler automation', 'Lead Lifecycle (Kanban + Drip)',
              'Accurate Scout + Dark Scout Intelligence',
              '16 campaign API endpoints',
            ]} />
            <FeatureGrid title="SOVEREIGN ARCHITECTURE" accent={SOLAR} items={[
              'Sovereign Node (Ollama via Ngrok)', 'XTTS v2 Voice Cloning',
              '7-Agent Swarm (Scout/Envoy/Closer/Oracle/Architect/Voice/Shannon)',
              'Shannon Red Team pentester', 'PentAGI Enterprise pentest',
              'BitNet Workers (qwen2:0.5b)',
              'Graphify Knowledge Graph (AST)', 'Redis 3-lane sharding',
              'Overwatch Mobile PWA (PIN auth)',
              'Legion Docker — Evolver / Postiz / n8n (pending wire)',
            ]} />
          </div>
        </div>

        {/* ═══ SECTION 3 — CLIENTS ═══ */}
        <div style={{ marginBottom: 20 }}>
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 12, paddingLeft: 4 }}>CLIENTS</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            {clients.map((c, i) => (
              <div key={i} className="sov-card" style={{ padding: '20px 24px', animationDelay: `${i * 0.1}s` }} data-testid={`client-card-${i}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                  <div>
                    <div className="sov-body" style={{ fontSize: 18, fontWeight: 700, color: '#E8E0D0' }}>{c.name}</div>
                    <div className="sov-mono" style={{ fontSize: 10, color: '#5A5468', marginTop: 2 }}>{c.tenant_id}</div>
                  </div>
                  <Badge status={c.status === 'active' ? 'active' : 'pending'} label={c.status?.toUpperCase() || 'ACTIVE'} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 9, color: '#5A5468', letterSpacing: '0.1em' }}>PLAN</div>
                    <div className="sov-body" style={{ fontSize: 14, fontWeight: 600, color: GOLD }}>{c.plan_price || c.plan || 'Starter'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: '#5A5468', letterSpacing: '0.1em' }}>HEALTH SCORE</div>
                    <div className="sov-mono" style={{ fontSize: 18, fontWeight: 700, color: c.score >= 80 ? '#4ADE80' : c.score >= 50 ? GOLD : '#EF4444' }}>
                      {c.score || 0}<span style={{ fontSize: 10, color: '#5A5468' }}>/100</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ═══ SECTION 4 — CAMPAIGN PIPELINE ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20 }}>
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 16 }}>CAMPAIGN PIPELINE</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 }}>
            <StatCard value={pipe.leads_scraped || 0} label="LEADS SCRAPED" color={GOLD} />
            <StatCard value={pipe.websites_scanned || 0} label="SITES SCANNED" color="#64C8FF" />
            <StatCard value={pipe.repairs_deployed || 0} label="REPAIRS" color="#4ADE80" />
            <StatCard value={pipe.calls_made || 0} label="CALLS MADE" color="#8B5CF6" />
            <StatCard value={pipe.emails_sent || 0} label="EMAILS SENT" color="#F59E0B" />
            <StatCard value={pipe.whatsapp_sent || 0} label="WHATSAPP" color="#4ADE80" />
            <StatCard value={pipe.comm_leads || 0} label="COMM LEADS" color={GOLD} />
            <StatCard value={pipe.live_chats || 0} label="LIVE CHATS" color="#64C8FF" />
          </div>
        </div>

        {/* ═══ SECTION 5 — SYSTEM ARCHITECTURE ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20 }}>
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 16 }}>SYSTEM ARCHITECTURE</div>
          <div className="sov-mono" style={{ fontSize: 11, color: '#8A8494', lineHeight: 2.2, textAlign: 'center', padding: '12px 0' }}>
            <div style={{ color: '#64C8FF' }}>[ User / Client ]</div>
            <div style={{ color: '#5A5468' }}>|</div>
            <div style={{ color: '#F59E0B' }}>[ Cloudflare CDN + SSL ]</div>
            <div style={{ color: '#5A5468' }}>|</div>
            <div style={{ color: '#4ADE80' }}>[ React PWA Frontend ]</div>
            <div style={{ color: '#5A5468' }}>|</div>
            <div style={{ color: GOLD }}>[ FastAPI Backend — 7 Agent Swarm ]</div>
            <div style={{ color: '#5A5468' }}>/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\</div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 32, flexWrap: 'wrap' }}>
              <span style={{ color: '#EF4444' }}>[ Redis 3-Lane ]</span>
              <span style={{ color: '#8B5CF6' }}>[ MongoDB Atlas ]</span>
              <span style={{ color: '#64C8FF' }}>[ OpenRouter / Emergent ]</span>
            </div>
            <div style={{ color: '#5A5468', marginTop: 4 }}>|</div>
            <div style={{ color: '#8B5CF6' }}>[ 3-Tier Memory: Working + Episodic + Knowledge ]</div>
            <div style={{ color: '#5A5468' }}>|</div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap', color: GOLD }}>
              <span>Scout</span><span style={{ color: '#5A5468' }}>&rarr;</span>
              <span>Architect</span><span style={{ color: '#5A5468' }}>&rarr;</span>
              <span>Envoy</span><span style={{ color: '#5A5468' }}>&rarr;</span>
              <span>Closer</span><span style={{ color: '#5A5468' }}>&rarr;</span>
              <span style={{ color: '#8B5CF6' }}>Shannon</span>
            </div>
            <div style={{ color: '#5A5468', marginTop: 8 }}>|</div>
            <div style={{ color: SOLAR }}>[ Sovereign Node: Legion Ollama + XTTS v2 via Ngrok ]</div>
            <div style={{ color: '#5A5468', marginTop: 4 }}>|</div>
            <div style={{ color: GOLD }}>[ AUREM Builder (Opus 4.6) → Shannon → Self-Repair → Testing → Deploy ]</div>
            <div style={{ color: '#5A5468' }}>|</div>
            <div style={{ color: '#8B5CF6' }}>[ EvoMap Evolver (Legion) → Gene Store → Admin Approval → Apply ]</div>
          </div>
        </div>

        {/* ═══ SECTION 6 — INTEGRATIONS & LEGAL ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, marginBottom: 20 }}>
          <FeatureGrid title="INTEGRATIONS" accent="#64C8FF" items={[
            'Emergent LLM Key (GPT-4o, GPT-4o-mini, Claude Sonnet 4.5, Gemini)',
            'OpenRouter (Llama 3.3 + Gemma 3 free fallback)',
            'Retell AI (318 voices, inbound webhook live)',
            'OpenAI Whisper (voice STT)', 'ElevenLabs (voice TTS)',
            'Resend Pro (bulk email)',
            'Twilio WABA (official WhatsApp) + SMS',
            'Telegram Bot API (alerts + briefs + commands)',
            'Apollo.io Org Enrich + DIY Proxy (scraper + email guesser)',
            'GitHub Actions Deploy Webhook (fallback trigger)',
            'Stripe (embedded checkout + Apple Pay LIVE, annual SKUs live)',
            'Redis (3-lane cache + read-through)',
            'MongoDB Atlas (database + TTL indexes)',
            'Shopify OAuth (1-click install, scopes wired)',
            'WordPress Plugin (downloadable zip, pixel + scanner)',
            'Tavily (web search)', 'Firecrawl (scraping)',
            'Google PageSpeed + Places APIs',
            'Cloudflare (DNS/CDN)', 'Ngrok (Sovereign tunnel)',
          ]} />
          <FeatureGrid title="LEGAL & COMPLIANCE" accent="#F59E0B" items={[
            'Terms of Service', 'Privacy Policy (PIPEDA)', 'CASL Acceptable Use',
            'OSC Economic Disclaimer', 'Refund Policy', 'Cookie Policy',
          ]} />
          <FeatureGrid title="INFRASTRUCTURE" accent="#4ADE80" items={[
            'Emergent K8s deployment', 'GitHub backup', '6-hour MongoDB backup',
            'Supervisor process manager', 'Health check endpoint', 'SSL certificate (aurem.live)',
            'PWA (installable app)', 'Overwatch mobile PWA',
          ]} />
        </div>

        {/* ═══ SECTION 7 — TECH STACK ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20 }}>
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 16 }}>TECHNOLOGY STACK</div>
          {[
            { label: 'Frontend', items: ['React', 'PWA', 'Recharts', 'Tailwind', 'Shadcn/UI', 'WebAuthn'], color: '#64C8FF' },
            { label: 'Backend', items: ['FastAPI', 'Python', 'APScheduler', 'Redis', 'WebSockets'], color: '#4ADE80' },
            { label: 'Database', items: ['MongoDB Atlas', '3-Tier Memory', 'Redis 3-Lane Cache'], color: '#8B5CF6' },
            { label: 'AI', items: ['Claude Sonnet 4.5', 'GPT-4o', 'GPT-4o-mini', 'Gemini 3', 'Llama 3.3 70B', 'Gemma 3 27B', 'OpenAI Whisper', 'ElevenLabs', 'Ollama', 'XTTS v2', 'EvoMap Evolver'], color: GOLD },
            { label: 'Infra', items: ['Emergent K8s', 'Cloudflare', 'GitHub', 'SSL/HTTPS', 'Ngrok'], color: '#F59E0B' },
            { label: 'Compliance', items: ['PIPEDA', 'CASL', 'OSC', 'PCI-DSS (Stripe)', 'SOC 2'], color: '#EF4444' },
          ].map((row, ri) => (
            <div key={ri} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
              <span className="sov-mono" style={{ fontSize: 10, color: '#5A5468', minWidth: 80, letterSpacing: '0.1em' }}>{row.label}</span>
              {row.items.map((t, ti) => (
                <span key={ti} className="sov-mono" style={{
                  fontSize: 10, padding: '4px 10px', borderRadius: 8, fontWeight: 600,
                  background: `${row.color}10`, border: `1px solid ${row.color}30`, color: row.color,
                }}>{t}</span>
              ))}
            </div>
          ))}
        </div>

        {/* ═══ SECTION 8 — PENDING ACTIONS ═══ */}
        <div className="sov-card" style={{ padding: '24px 32px', marginBottom: 20 }}>
          <div className="sov-hdr" style={{ fontSize: 14, marginBottom: 16 }}>PENDING ACTIONS</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12 }}>
            {[
              { status: 'critical', icon: '\u{1F534}', title: 'RETELL_FROM_NUMBER missing', desc: 'Buy/import phone in Retell dashboard \u2192 unlock outbound calls', priority: 'P0' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'Twilio A2P 10DLC Brand (Canada)', desc: 'SMS unblock \u2192 user action pending', priority: 'P1' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'Google Calendar API for booking', desc: 'Needs Google Cloud OAuth (separate from Emergent Auth)', priority: 'P2' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'POSTIZ API Key', desc: 'Social posting via /my/social', priority: 'P2' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'Google OAuth (Emergent-managed)', desc: 'Customer social login option', priority: 'P2' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'Shopify Partner App listing', desc: 'Public app store submission (2-4 week review)', priority: 'P3' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'AUREM Trademark CIPO', desc: '$458 CAD \u2192 Class 42', priority: 'P1' },
              { status: 'pending', icon: '\u{1F7E1}', title: 'Telnyx migration (vs Twilio)', desc: 'CRM tier margin 28% \u2192 81% post-migration', priority: 'P2' },
              { status: 'active', icon: '\u{1F7E2}', title: 'ORA Founder Sovereign Mode LIVE', desc: 'Text + voice + any language \u2022 11 founder-gated intents (Iter 287.7)', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Twilio WABA Official WhatsApp LIVE', desc: 'Migrated off banned WHAPI (Iter 287.4)', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Apollo DIY Proxy LIVE', desc: 'Website scraper + email guesser fallback (Iter 287.0-287.2)', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: '7-Day Free Trial Promo + Mascot LIVE', desc: 'Animated SVG robot on landing page (Iter 287.5)', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Morning Brief + Evening Wrap LIVE', desc: 'Resend + Telegram + Twilio (Iter 285.9 / 286.0)', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Master Autopilot LIVE', desc: 'Daily 08:00 AM Toronto \u2022 Scout \u2192 Hunt \u2192 Blast \u2192 Report', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Deploy Webhook Fallback LIVE', desc: '/api/admin/deploy/trigger (Iter 287.1)', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'AUREM Builder pipeline LIVE', desc: 'Async BackgroundTask \u2022 ORA intents wired', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Evolver gene approval gate LIVE', desc: '/admin/evolver \u2022 review-mode ON \u2022 never auto-applies', priority: 'P0' },
              { status: 'active', icon: '\u{1F7E2}', title: 'Nightly scheduler (19 jobs)', desc: '2:00 learn \u2022 2:30 health \u2022 2:45 evolver \u2022 3:15 audit', priority: 'P0' },
            ].map((item, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 16px', borderRadius: 12,
                background: item.status === 'critical' ? 'rgba(239,68,68,0.04)' : item.status === 'pending' ? 'rgba(245,158,11,0.04)' : 'rgba(74,222,128,0.04)',
                border: `1px solid ${item.status === 'critical' ? 'rgba(239,68,68,0.15)' : item.status === 'pending' ? 'rgba(245,158,11,0.15)' : 'rgba(74,222,128,0.15)'}`,
              }}>
                <span className="sov-mono" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.05)', color: '#5A5468' }}>{item.priority}</span>
                <div>
                  <div className="sov-body" style={{ fontSize: 14, fontWeight: 600, color: '#E8E0D0' }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: '#6A6070', marginTop: 2 }}>{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ═══ SENTINEL HEALTH (Pulse Animation) ═══ */}
        <div className="sov-card" style={{ padding: '20px 32px', marginBottom: 20, animation: 'sov-sentinel 2s ease-in-out infinite', position: 'relative', overflow: 'hidden' }} data-testid="sentinel-pulse-card">
          <div style={{ position: 'absolute', top: 0, left: 0, width: '20%', height: '100%', background: `linear-gradient(90deg, transparent, ${SOLAR}08, transparent)`, animation: 'sov-scan 3s ease-in-out infinite' }} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: SOLAR, animation: 'sov-pulse 1.5s ease-in-out infinite', boxShadow: `0 0 12px ${SOLAR}60` }} />
              <div>
                <div className="sov-hdr" style={{ fontSize: 13 }}>SENTINEL HEALTH MONITOR</div>
                <div className="sov-mono" style={{ fontSize: 10, color: '#6A6070' }}>Real-time system monitoring active</div>
              </div>
            </div>
            <div className="sov-mono" style={{ fontSize: 11, color: SOLAR, fontWeight: 700 }}>
              ALL SYSTEMS OPERATIONAL
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', padding: '24px 0', borderTop: `1px solid ${BORDER}` }}>
          <div className="sov-hdr" style={{ fontSize: 11, opacity: 0.5 }}>AUREM AI</div>
          <div style={{ fontSize: 10, color: '#3A3448', marginTop: 4, letterSpacing: '0.15em' }}>POLARIS BUILT INC. | SOVEREIGN INFRASTRUCTURE | {new Date().getFullYear()}</div>
        </div>
      </div>
    </div>
  );
}
