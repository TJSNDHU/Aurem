/**
 * AUREM Public Business Report
 * ============================
 * Sales funnel landing page for scouted leads.
 * Dark luxury theme, animated score, revenue calculator, Stripe instant-subscribe.
 * Route: /report/:slug  (e.g. /report/tj-auto-clinic-001)
 */
import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Globe, Star, Instagram, MapPin, RefreshCw, Search, Zap, Users,
  TrendingUp, MessageCircle, CheckCircle, AlertTriangle, ArrowRight,
  Phone, Mail, Calendar, Sparkles, Quote,
  Inbox, Film, Send, BarChart3, Eye, Sun, Shield, Wrench, FileText, ShoppingBag,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const GOLD = '#C9A227';
const BG = '#0A0A0A';

const ICON_MAP = {
  globe: Globe, star: Star, instagram: Instagram, 'map-pin': MapPin,
  refresh: RefreshCw, search: Search, zap: Zap, users: Users,
  message: MessageCircle, 'trending-up': TrendingUp,
  phone: Phone, inbox: Inbox, film: Film, send: Send,
  'bar-chart': BarChart3, eye: Eye, sun: Sun, shield: Shield,
  tool: Wrench, 'file-text': FileText, 'shopping-bag': ShoppingBag,
};

// Inline styles for card animations (injected once)
const AUREM_FIX_CSS = `
  @keyframes aurem-fix-fade-in {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .aurem-fix-card {
    opacity: 0;
    animation: aurem-fix-fade-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  .aurem-fix-card:hover {
    border-color: ${GOLD} !important;
    box-shadow: 0 0 0 1px ${GOLD}55, 0 12px 32px ${GOLD}26;
    background: linear-gradient(135deg, rgba(201,162,39,0.12), rgba(0,0,0,0.25)) !important;
  }
`;

// ─────────────────────────────────────────────────────────────
// Particle background — subtle gold dots
// ─────────────────────────────────────────────────────────────
const Particles = () => {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w = (canvas.width = window.innerWidth);
    let h = (canvas.height = window.innerHeight);
    const count = Math.min(60, Math.floor((w * h) / 36000));
    const particles = Array.from({ length: count }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      r: Math.random() * 1.3 + 0.3,
      a: Math.random() * 0.5 + 0.15,
    }));
    let raf;
    const loop = () => {
      ctx.clearRect(0, 0, w, h);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(201, 162, 39, ${p.a})`;
        ctx.fill();
      });
      raf = requestAnimationFrame(loop);
    };
    loop();
    const resize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; };
    window.addEventListener('resize', resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none" style={{ zIndex: 0 }} />;
};

// ─────────────────────────────────────────────────────────────
// Animated Score Meter
// ─────────────────────────────────────────────────────────────
const ScoreMeter = ({ target, severity }) => {
  const [displayed, setDisplayed] = useState(0);
  useEffect(() => {
    let raf;
    const start = performance.now();
    const duration = 1800;
    const step = (t) => {
      const progress = Math.min((t - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(target * eased));
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  const color = severity === 'critical' ? '#ef4444' : severity === 'warning' ? '#f59e0b' : '#4ADE80';
  const circumference = 2 * Math.PI * 110;
  const offset = circumference - (displayed / 100) * circumference;

  return (
    <div className="relative flex flex-col items-center" data-testid="score-meter">
      <svg width="260" height="260" viewBox="0 0 260 260" className="transform -rotate-90">
        <circle cx="130" cy="130" r="110" fill="none" stroke="rgba(201,162,39,0.1)" strokeWidth="12" />
        <circle
          cx="130" cy="130" r="110" fill="none"
          stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.1s linear', filter: `drop-shadow(0 0 18px ${color}66)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-bold tabular-nums" style={{ fontFamily: 'Cinzel, Georgia, serif', fontSize: '68px', color, lineHeight: 1 }}>
          {displayed}
        </div>
        <div className="mt-1 text-xs tracking-[0.4em]" style={{ color: 'rgba(255,255,255,0.5)' }}>/ 100</div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Urgency Bar — sticky top banner
// ─────────────────────────────────────────────────────────────
const UrgencyBar = ({ city }) => {
  const [signups, setSignups] = useState(3);
  const [countdown, setCountdown] = useState('');

  useEffect(() => {
    fetch(`${API}/api/onboarding/urgency/stats`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.signups_today) setSignups(d.signups_today); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const end = Date.now() + 24 * 60 * 60 * 1000;
    const tick = () => {
      const ms = end - Date.now();
      if (ms <= 0) { setCountdown('0h 0m'); return; }
      const h = Math.floor(ms / 3600000);
      const m = Math.floor((ms % 3600000) / 60000);
      setCountdown(`${h}h ${m}m`);
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div data-testid="urgency-bar"
      className="sticky top-0 z-40 border-b backdrop-blur-md"
      style={{ background: 'rgba(10,10,10,0.85)', borderColor: 'rgba(201,162,39,0.25)' }}>
      <div className="max-w-5xl mx-auto px-4 md:px-10 py-2.5 flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-[11px] md:text-xs font-medium">
        <span className="flex items-center gap-1.5" style={{ color: '#fca5a5' }}>
          <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
          <span>{signups} businesses in {city} signed up today</span>
        </span>
        <span className="hidden md:inline" style={{ color: 'rgba(255,255,255,0.55)' }}>·</span>
        <span className="flex items-center gap-1.5" style={{ color: GOLD }}>
          ⏰ Free trial expires in <strong className="tabular-nums">{countdown}</strong>
        </span>
        <span className="hidden md:inline" style={{ color: 'rgba(255,255,255,0.55)' }}>·</span>
        <span style={{ color: '#4ADE80' }}>✅ 7-day free trial, cancel anytime</span>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Section wrapper
// ─────────────────────────────────────────────────────────────
const Section = ({ label, title, children, testid }) => (
  <section className="relative max-w-5xl mx-auto px-6 md:px-10 py-12 md:py-20" data-testid={testid}>
    {label && (
      <div className="text-[11px] tracking-[0.4em] font-semibold mb-3" style={{ color: GOLD }}>
        {label}
      </div>
    )}
    {title && (
      <h2 className="text-3xl md:text-5xl font-bold mb-8 md:mb-12"
        style={{ fontFamily: 'Cinzel, Georgia, serif', color: '#fff', lineHeight: 1.15 }}>
        {title}
      </h2>
    )}
    {children}
  </section>
);

// ─────────────────────────────────────────────────────────────
// Revenue Calculator
// ─────────────────────────────────────────────────────────────
const RevenueCalculator = ({ revenue }) => {
  const [avgJob, setAvgJob] = useState(revenue.avg_job_value_cad);
  const additionalLeads = revenue.additional_leads;
  const monthly = additionalLeads * avgJob;
  const annual = monthly * 12;
  const fmt = (n) => '$' + n.toLocaleString('en-CA');

  return (
    <div className="rounded-2xl p-6 md:p-10 border relative overflow-hidden"
      style={{ background: 'linear-gradient(135deg, rgba(201,162,39,0.08), rgba(201,162,39,0.02))', borderColor: 'rgba(201,162,39,0.3)' }}
      data-testid="revenue-calculator">
      <div className="grid md:grid-cols-2 gap-8 items-center">
        <div>
          <div className="text-xs tracking-[0.3em] font-semibold mb-2" style={{ color: GOLD }}>
            📈 GROWTH PROJECTION
          </div>
          <div className="text-sm mb-6" style={{ color: 'rgba(255,255,255,0.65)' }}>
            Based on {revenue.monthly_searches.toLocaleString()} monthly searches in your city.
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span style={{ color: 'rgba(255,255,255,0.6)' }}>Current monthly leads</span><span className="font-mono font-bold">~{revenue.current_monthly_leads}</span></div>
            <div className="flex justify-between"><span style={{ color: 'rgba(255,255,255,0.6)' }}>With AUREM</span><span className="font-mono font-bold" style={{ color: '#4ADE80' }}>~{revenue.aurem_monthly_leads}+ /mo</span></div>
            <div className="h-px my-3" style={{ background: 'rgba(201,162,39,0.15)' }} />
            <label className="block">
              <div className="flex justify-between mb-2">
                <span style={{ color: 'rgba(255,255,255,0.65)' }} className="text-xs tracking-wide">Your avg job value</span>
                <span className="font-mono font-bold" style={{ color: GOLD }}>{fmt(avgJob)}</span>
              </div>
              <input
                type="range" min="25" max="2000" step="5" value={avgJob}
                onChange={(e) => setAvgJob(Number(e.target.value))}
                data-testid="revenue-job-slider"
                className="w-full accent-[#C9A227]"
                style={{ accentColor: GOLD }}
              />
              <div className="flex justify-between text-[10px] mt-1" style={{ color: 'rgba(255,255,255,0.65)' }}>
                <span>$25</span><span>$2,000</span>
              </div>
            </label>
          </div>
        </div>
        <div className="text-center p-6 rounded-xl"
          style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(201,162,39,0.2)' }}>
          <div className="text-[10px] tracking-[0.35em] mb-2" style={{ color: 'rgba(255,255,255,0.5)' }}>ADDITIONAL MONTHLY</div>
          <div className="font-bold tabular-nums" style={{ fontFamily: 'Cinzel, serif', color: '#4ADE80', fontSize: 'clamp(2rem, 6vw, 3.5rem)' }} data-testid="revenue-monthly">
            +{fmt(monthly)}
          </div>
          <div className="mt-4 text-[10px] tracking-[0.35em]" style={{ color: 'rgba(255,255,255,0.5)' }}>ANNUAL IMPACT</div>
          <div className="font-bold tabular-nums mt-1" style={{ fontFamily: 'Cinzel, serif', color: GOLD, fontSize: 'clamp(1.75rem, 5vw, 2.5rem)' }} data-testid="revenue-annual">
            +{fmt(annual)}
          </div>
          <div className="mt-4 text-[11px]" style={{ color: 'rgba(255,255,255,0.7)' }}>
            {additionalLeads} extra leads/mo × {fmt(avgJob)} × 12
          </div>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Pricing Tier Card — profit math + instant subscribe
// ─────────────────────────────────────────────────────────────
const PricingCard = ({ plan, onSubscribe, loading }) => {
  const isPopular = plan.popular;
  const fmt = (n) => '$' + Number(n).toLocaleString('en-CA');

  return (
    <div
      className="relative rounded-2xl p-6 md:p-7 border transition-all duration-300 hover:scale-[1.02] flex flex-col"
      style={{
        background: isPopular
          ? 'linear-gradient(160deg, rgba(201,162,39,0.14), rgba(201,162,39,0.03))'
          : 'rgba(255,255,255,0.02)',
        borderColor: isPopular ? GOLD : 'rgba(255,255,255,0.08)',
        boxShadow: isPopular ? `0 12px 48px ${GOLD}30` : 'none',
      }}
      data-testid={`pricing-card-${plan.tier}`}
    >
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[10px] font-bold tracking-widest flex items-center gap-1"
          style={{ background: GOLD, color: '#000' }}>
          ⭐ MOST POPULAR
        </div>
      )}

      <div className="text-[10px] tracking-[0.35em] font-semibold mb-1" style={{ color: GOLD }}>
        {plan.name.toUpperCase()}{plan.tier === 'enterprise' && ' 🔥'}
      </div>
      <div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.7)' }}>{plan.tag}</div>

      {/* Customer target */}
      <div className="mt-5 flex items-center gap-2">
        <span className="text-2xl">🎯</span>
        <div>
          <div className="text-base md:text-lg font-bold text-white">
            {plan.customers_low}-{plan.customers_high} New Customers
          </div>
          <div className="text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>per month</div>
        </div>
      </div>

      {/* Profit math rows */}
      <div className="mt-5 space-y-1.5 text-sm">
        <div className="flex justify-between" style={{ color: 'rgba(255,255,255,0.55)' }}>
          <span>You invest</span>
          <span className="font-mono font-bold text-white" data-testid={`invest-${plan.tier}`}>{fmt(plan.price_cad)}/mo</span>
        </div>
        <div className="flex justify-between" style={{ color: 'rgba(255,255,255,0.55)' }}>
          <span>You earn</span>
          <span className="font-mono font-bold" style={{ color: '#4ADE80' }} data-testid={`earn-${plan.tier}`}>
            {fmt(plan.earn_low_cad)}–{fmt(plan.earn_high_cad)}/mo
          </span>
        </div>
        <div className="flex justify-between pt-1.5 border-t" style={{ borderColor: 'rgba(201,162,39,0.15)' }}>
          <span className="font-semibold" style={{ color: GOLD }}>Pure profit</span>
          <span className="font-mono font-bold text-lg" style={{ color: GOLD }} data-testid={`profit-${plan.tier}`}>
            {fmt(plan.profit_cad)}/mo
          </span>
        </div>
      </div>

      <div className="mt-4 text-[11px] flex items-center gap-1.5" style={{ color: '#4ADE80' }}>
        <CheckCircle className="size-3.5" />
        <span>Pays for itself with <strong>{plan.payback_customers} customer{plan.payback_customers > 1 ? 's' : ''}</strong></span>
      </div>

      {/* Feature bullets */}
      <ul className="mt-4 space-y-1.5 flex-1">
        {plan.features.slice(0, 4).map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-[12px]" style={{ color: 'rgba(255,255,255,0.65)' }}>
            <CheckCircle className="size-3.5 mt-0.5 shrink-0" style={{ color: GOLD }} />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      {/* CTA */}
      <button
        onClick={() => onSubscribe(plan)}
        disabled={loading === plan.tier}
        data-testid={`subscribe-${plan.tier}`}
        className="mt-6 w-full py-3.5 rounded-xl font-bold text-sm tracking-wider transition-all hover:brightness-110 flex items-center justify-center gap-2"
        style={{
          background: isPopular ? GOLD : 'rgba(255,255,255,0.05)',
          color: isPopular ? '#000' : '#fff',
          border: `1px solid ${isPopular ? GOLD : 'rgba(201,162,39,0.35)'}`,
          opacity: loading === plan.tier ? 0.6 : 1,
        }}
      >
        <Zap className="size-4" />
        {loading === plan.tier ? 'REDIRECTING…' : `START NOW — $${plan.price_cad}/mo`}
      </button>
      <div className="mt-2.5 text-center text-[10px]" style={{ color: 'rgba(255,255,255,0.7)' }}>
        Apple Pay · Google Pay · Card · 7-day free trial
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────
const AuremReport = () => {
  const { slug } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [checkoutLoading, setCheckoutLoading] = useState(null);
  const startRef = useRef(Date.now());
  const engagedFiredRef = useRef(false);

  // Fetch report data
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/report/${slug}`);
        if (!r.ok) throw new Error(r.status === 404 ? 'Report not found' : 'Failed to load report');
        const data = await r.json();
        if (!cancelled) setReport(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [slug]);

  // Log visit + 30-second engagement nudge
  useEffect(() => {
    if (!report) return;
    // Log visit
    fetch(`${API}/api/report/${slug}/visit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        referrer: document.referrer || '',
        user_agent: navigator.userAgent || '',
      }),
    }).catch(() => {});

    // 30-second engagement trigger
    const timer = setTimeout(() => {
      if (engagedFiredRef.current) return;
      engagedFiredRef.current = true;
      fetch(`${API}/api/report/${slug}/engaged`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          duration_seconds: Math.round((Date.now() - startRef.current) / 1000),
        }),
      }).catch(() => {});
    }, 30000);
    return () => clearTimeout(timer);
  }, [report, slug]);

  const handleSubscribe = useCallback(async (plan) => {
    setCheckoutLoading(plan.tier);
    try {
      const res = await fetch(`${API}/api/payments/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          package_id: plan.tier,
          origin_url: window.location.origin,
          ref: slug,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.url) { window.location.href = data.url; return; }
      }
      // Fallback to AUREM pricing page with plan preselected
      window.location.href = `/pricing?plan=${plan.tier}&ref=${slug}`;
    } catch {
      window.location.href = `/pricing?plan=${plan.tier}&ref=${slug}`;
    } finally {
      setCheckoutLoading(null);
    }
  }, [slug]);

  const severityCopy = useMemo(() => {
    if (!report) return { label: '', color: GOLD };
    const s = report.score?.severity;
    if (s === 'critical') return { label: '⚠️ CRITICAL — Immediate action needed', color: '#ef4444' };
    if (s === 'warning') return { label: '⚡ ROOM TO GROW', color: '#f59e0b' };
    return { label: '✓ STRONG PRESENCE', color: '#4ADE80' };
  }, [report]);

  // Loading / error states
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: BG, color: '#fff' }} data-testid="report-error">
        <div className="text-center">
          <div className="text-sm tracking-[0.4em] mb-3" style={{ color: GOLD }}>AUREM</div>
          <h1 className="text-2xl font-bold mb-2" style={{ fontFamily: 'Cinzel, serif' }}>Report not found</h1>
          <p className="text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>The business slug <code className="text-[#C9A227]">{slug}</code> was not found in our scout database.</p>
          <a href="https://aurem.live" className="inline-block mt-6 px-5 py-2.5 rounded-lg text-xs font-bold tracking-wider" style={{ background: GOLD, color: '#000' }}>
            VISIT AUREM.LIVE
          </a>
        </div>
      </div>
    );
  }
  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: BG, color: '#fff' }} data-testid="report-loading">
        <div className="text-center">
          <div className="size-12 rounded-full border-2 border-[#C9A227]/20 border-t-[#C9A227] animate-spin mx-auto" />
          <div className="mt-4 text-xs tracking-[0.4em]" style={{ color: GOLD }}>GENERATING YOUR REPORT…</div>
        </div>
      </div>
    );
  }

  const { business, score, growth_gaps, aurem_fixes, revenue, pricing, social_proof, repair_offer } = report;

  return (
    <div className="min-h-screen relative" style={{ background: BG, color: '#fff', fontFamily: 'Jost, Manrope, -apple-system, sans-serif' }} data-testid="aurem-report">
      <style>{AUREM_FIX_CSS}</style>
      <Particles />
      <UrgencyBar city={business.city || 'your area'} />

      {/* Gold glow at top */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] pointer-events-none"
        style={{ background: `radial-gradient(ellipse, ${GOLD}1a 0%, transparent 70%)` }} />

      <div className="relative" style={{ zIndex: 1 }}>

        {/* ══════ SECTION 1: HERO ══════ */}
        <Section testid="report-hero">
          <div className="text-center">
            <div className="inline-flex items-center gap-2 mb-6">
              <div className="size-3 rounded-full animate-pulse" style={{ background: GOLD, boxShadow: `0 0 16px ${GOLD}` }} />
              <div className="text-xs tracking-[0.4em] font-semibold" style={{ color: GOLD }}>AUREM</div>
            </div>
            <div className="text-[10px] tracking-[0.5em] mb-4" style={{ color: 'rgba(255,255,255,0.5)' }}>
              FREE BUSINESS INTELLIGENCE REPORT
            </div>
            <div className="h-px w-32 mx-auto mb-8" style={{ background: `linear-gradient(90deg, transparent, ${GOLD}, transparent)` }} />
            <h1 className="text-4xl md:text-6xl font-bold mb-3" style={{ fontFamily: 'Cinzel, Georgia, serif', color: '#fff', lineHeight: 1.1 }}>
              {business.name}
            </h1>
            <div className="text-sm md:text-base" style={{ color: 'rgba(255,255,255,0.6)' }}>
              {business.city || business.location}
            </div>
            <div className="mt-8 inline-flex items-center gap-2 px-4 py-2 rounded-full border" style={{ borderColor: 'rgba(201,162,39,0.3)', background: 'rgba(201,162,39,0.05)' }}>
              <Sparkles className="size-3.5" style={{ color: GOLD }} />
              <span className="text-xs tracking-wider" style={{ color: 'rgba(255,255,255,0.75)' }}>
                Generated by <strong style={{ color: GOLD }}>ORA</strong>, World's First AI Business Intelligence
              </span>
            </div>
          </div>
        </Section>

        {/* ══════ SECTION 2: SCORE METER ══════ */}
        <Section testid="section-score">
          <div className="text-center">
            <div className="text-[10px] tracking-[0.5em] mb-6" style={{ color: 'rgba(255,255,255,0.5)' }}>
              YOUR GOOGLE PRESENCE SCORE
            </div>
            <div className="flex justify-center mb-8">
              <ScoreMeter target={score.score} severity={score.severity} />
            </div>
            <div className="text-base md:text-lg font-bold mb-6" style={{ color: severityCopy.color, letterSpacing: '0.1em' }} data-testid="score-severity">
              {severityCopy.label}
            </div>
            <div className="flex flex-wrap justify-center gap-6 text-xs md:text-sm" style={{ color: 'rgba(255,255,255,0.5)' }}>
              <div>Industry avg: <strong className="text-white">{score.industry_average}/100</strong></div>
              <div className="w-px" style={{ background: 'rgba(255,255,255,0.15)' }} />
              <div>Top competitors: <strong className="text-white">{score.top_competitors}/100</strong></div>
            </div>
          </div>
        </Section>

        {/* ══════ SECTION 3: GROWTH GAPS ══════ */}
        <Section label="PROBLEM" title="Growth Gaps Found" testid="section-gaps">
          <div className="grid md:grid-cols-2 gap-4">
            {growth_gaps.map((gap, i) => {
              const Icon = ICON_MAP[gap.icon] || AlertTriangle;
              return (
                <div key={i} data-testid={`gap-${i}`}
                  className="p-5 rounded-xl border flex gap-4"
                  style={{ background: 'linear-gradient(135deg, rgba(239,68,68,0.08), rgba(239,68,68,0.02))', borderColor: 'rgba(239,68,68,0.25)' }}>
                  <div className="size-10 shrink-0 rounded-lg flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.15)' }}>
                    <Icon className="size-5" style={{ color: '#ef4444' }} />
                  </div>
                  <div>
                    <div className="font-bold text-white mb-1">{gap.title}</div>
                    <div className="text-sm mb-1.5" style={{ color: 'rgba(255,255,255,0.65)' }}>{gap.detail}</div>
                    <div className="text-xs font-semibold" style={{ color: '#fca5a5' }}>{gap.impact}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </Section>

        {/* ══════ SECTION 4: AUREM FIXES ══════ */}
        <Section label="SOLUTION" title="AUREM Fixes Everything Automatically" testid="section-fixes">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 md:gap-4">
            {aurem_fixes.map((fix, i) => {
              const Icon = ICON_MAP[fix.icon] || CheckCircle;
              return (
                <div key={i} data-testid={`fix-${i}`}
                  className="aurem-fix-card group p-4 md:p-5 rounded-xl border flex flex-col gap-2.5 transition-all duration-300 hover:-translate-y-1"
                  style={{
                    background: 'linear-gradient(135deg, rgba(201,162,39,0.04), rgba(0,0,0,0.2))',
                    borderColor: 'rgba(201,162,39,0.15)',
                    animationDelay: `${i * 40}ms`,
                  }}>
                  <div className="size-10 shrink-0 rounded-lg flex items-center justify-center transition-all duration-300 group-hover:scale-110"
                    style={{ background: 'rgba(201,162,39,0.12)', boxShadow: `0 0 0 1px rgba(201,162,39,0.25) inset` }}>
                    <Icon className="size-5 transition-colors duration-300" style={{ color: GOLD }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-[13px] md:text-sm leading-tight mb-1" style={{ color: '#fff' }}>
                      {fix.title}
                    </div>
                    <div className="text-[11px] md:text-xs leading-snug" style={{ color: 'rgba(255,255,255,0.6)' }}>
                      {fix.detail}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="text-center mt-8 text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>
            All {aurem_fixes.length} capabilities — included in every plan. No add-ons, no upsells.
          </div>
        </Section>

        {/* ══════ SECTION 5: REVENUE CALCULATOR ══════ */}
        <Section label="OPPORTUNITY" title="Your Growth Potential" testid="section-revenue">
          <RevenueCalculator revenue={revenue} />
        </Section>

        {/* ══════ HYBRID REPAIR CTA — appears only when a repair scan exists for this lead ══════ */}
        {repair_offer?.available && (
          <Section label="QUICK FIX OPTION" title="Don't need everything? Just fix what's broken." testid="section-repair-offer">
            <div className="rounded-2xl border p-6 md:p-8" data-testid="repair-offer-card"
              style={{
                background: 'linear-gradient(160deg, rgba(220,38,38,0.10), rgba(201,162,39,0.04))',
                borderColor: 'rgba(201,162,39,0.4)',
              }}>
              <div className="flex flex-col md:flex-row md:items-center gap-6">
                <div className="flex-1">
                  <div className="text-[10px] tracking-[0.35em] font-semibold mb-2" style={{ color: '#EF4444' }}>
                    AUDIT SCORE: {repair_offer.score}/100 · {repair_offer.issues_total} ISSUES FOUND
                  </div>
                  <div className="text-xl md:text-2xl font-bold mb-2" style={{ fontFamily: 'Cinzel, Georgia, serif' }}>
                    Skip the subscription. Pay once, we fix it.
                  </div>
                  <div className="text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>
                    Already happy with your business? Just want the website
                    issues patched? Pay once, we deliver in 24-48h. No
                    monthly. No commitment.
                  </div>
                  <a href={`/api/repair-report/${repair_offer.public_slug}`}
                    target="_blank" rel="noreferrer"
                    data-testid="repair-offer-view-full-report"
                    className="inline-block mt-3 text-[11px] underline"
                    style={{ color: GOLD }}>
                    See the full audit ({repair_offer.issues_critical} critical) →
                  </a>
                </div>

                <div className="flex flex-col gap-3 md:min-w-[260px]">
                  {repair_offer.tiers.map((t) => (
                    <a key={t.tier} href={t.checkout_url}
                      data-testid={`repair-offer-buy-${t.tier}`}
                      className="block rounded-xl border px-5 py-4 transition hover:brightness-110"
                      style={{
                        background: t.tier === 'basic'
                          ? 'rgba(201,162,39,0.95)' : 'rgba(255,255,255,0.04)',
                        color: t.tier === 'basic' ? '#000' : '#fff',
                        borderColor: 'rgba(201,162,39,0.5)',
                        textDecoration: 'none',
                      }}>
                      <div className="flex justify-between items-baseline">
                        <span className="text-[11px] font-bold tracking-widest">
                          {t.label.toUpperCase()}
                        </span>
                        <span className="font-mono font-bold text-xl">${t.price_cad}</span>
                      </div>
                      <div className="text-[10px] mt-1"
                        style={{ opacity: 0.75 }}>
                        Delivered in {t.delivery_hours}h · One-time
                      </div>
                    </a>
                  ))}
                  <div className="text-center text-[10px]"
                    style={{ color: 'rgba(255,255,255,0.5)' }}>
                    Powered by Stripe · CAD
                  </div>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* ══════ SECTION 6: PRICING ══════ */}
        <Section label="START TODAY" title="Choose Your Plan" testid="section-pricing">
          <div className="grid md:grid-cols-3 gap-5">
            {pricing.map((plan) => (
              <PricingCard key={plan.tier} plan={plan} onSubscribe={handleSubscribe} loading={checkoutLoading} />
            ))}
          </div>
          <div className="text-center mt-8 text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>
            Instant activation · Powered by Stripe · Cancel anytime in 1 click
          </div>
        </Section>

        {/* ══════ SECTION 7: SOCIAL PROOF ══════ */}
        <Section label="PROOF" title="Trusted by Canadian Businesses" testid="section-proof">
          <div className="grid md:grid-cols-3 gap-4">
            {social_proof.map((p, i) => (
              <div key={i} data-testid={`proof-${i}`}
                className="p-6 rounded-xl border"
                style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(201,162,39,0.2)' }}>
                <Quote className="size-6 mb-3" style={{ color: GOLD }} />
                <div className="text-sm font-medium mb-3 italic" style={{ color: 'rgba(255,255,255,0.85)' }}>
                  "{p.quote}"
                </div>
                <div className="text-[11px] tracking-wider" style={{ color: 'rgba(255,255,255,0.5)' }}>
                  — {p.author}
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* ══════ SECTION 8: CTA FOOTER ══════ */}
        <Section testid="section-cta-footer">
          <div className="rounded-2xl p-8 md:p-12 text-center border"
            style={{ background: 'linear-gradient(135deg, rgba(201,162,39,0.08), rgba(0,0,0,0.6))', borderColor: 'rgba(201,162,39,0.3)' }}>
            <h2 className="text-3xl md:text-4xl font-bold mb-3" style={{ fontFamily: 'Cinzel, serif', color: '#fff' }}>
              Still have questions?
            </h2>
            <div className="text-sm mb-8" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Talk to ORA, our AI handles everything from questions to setup.
            </div>
            <div className="flex flex-wrap justify-center gap-3">
              <a href="tel:+14314500004" data-testid="cta-call"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs tracking-wider hover:brightness-110 transition-all"
                style={{ background: GOLD, color: '#000' }}>
                <Phone className="size-4" /> BOOK A DEMO CALL
              </a>
              <a href="https://aurem.live/ora" data-testid="cta-chat"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs tracking-wider border hover:bg-white/5 transition-all"
                style={{ borderColor: GOLD, color: GOLD }}>
                <MessageCircle className="size-4" /> CHAT WITH ORA
              </a>
              <a href="mailto:ora@aurem.live" data-testid="cta-email"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs tracking-wider border hover:bg-white/5 transition-all"
                style={{ borderColor: 'rgba(255,255,255,0.15)', color: '#fff' }}>
                <Mail className="size-4" /> EMAIL US
              </a>
            </div>
            <div className="mt-8 text-[11px] tracking-wider" style={{ color: 'rgba(255,255,255,0.65)' }}>
              7-day free trial · No credit card · Cancel anytime
            </div>
          </div>

          <div className="text-center mt-10 pb-10">
            <div className="text-xs tracking-[0.4em] font-semibold mb-1" style={{ color: GOLD }}>AUREM</div>
            <div className="text-[11px]" style={{ color: 'rgba(255,255,255,0.65)' }}>
              World's First AI Business Intelligence Platform
            </div>
            <a href="https://aurem.live" className="text-[11px] hover:underline" style={{ color: GOLD }}>
              aurem.live
            </a>
          </div>
        </Section>
      </div>
    </div>
  );
};

export default AuremReport;
