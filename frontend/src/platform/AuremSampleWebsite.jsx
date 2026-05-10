/**
 * AUREM Sample Website — industry-themed, 6-section, mobile-first
 * Route: /sample/:slug
 */
import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Phone, MessageCircle, Star, Home, MapPin, Clock, ChevronDown,
  Droplet, Disc, Circle, Cpu, Settings, Wrench, Scissors, Palette,
  Brush, Hand, Sun, Utensils, Package, Truck, Gift, Heart, Activity,
  Shield, Beaker, Video, Smile, AlertCircle, AlignJustify, Zap, Users,
  Dumbbell, Apple, Smartphone, TrendingUp, Key, BarChart, DollarSign,
  Calendar, Check,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const ICONS = {
  droplet: Droplet, disc: Disc, circle: Circle, cpu: Cpu, settings: Settings,
  wrench: Wrench, scissors: Scissors, palette: Palette, brush: Brush, hand: Hand,
  sun: Sun, utensils: Utensils, package: Package, truck: Truck, gift: Gift,
  heart: Heart, activity: Activity, shield: Shield, beaker: Beaker, video: Video,
  smile: Smile, 'alert-circle': AlertCircle, 'align-justify': AlignJustify,
  zap: Zap, users: Users, dumbbell: Dumbbell, apple: Apple, smartphone: Smartphone,
  home: Home, 'trending-up': TrendingUp, key: Key, 'bar-chart': BarChart,
  'dollar-sign': DollarSign, calendar: Calendar, 'map-pin': MapPin,
  star: Star, check: Check, map: MapPin,
};

// ─────────────────────────────────────────────────────────────
// Industry-specific hero animation (canvas 2D — lightweight)
// ─────────────────────────────────────────────────────────────
const HeroAnimation = ({ kind, accent }) => {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w = canvas.width = canvas.offsetWidth;
    let h = canvas.height = canvas.offsetHeight;
    let raf;

    const particles = [];
    const accentRGB = hexToRgb(accent);

    if (kind === 'gears') {
      // Rotating gear teeth rings
      const rings = [
        { x: w * 0.25, y: h * 0.5, r: 120, teeth: 14, speed: 0.004 },
        { x: w * 0.7,  y: h * 0.35, r: 80,  teeth: 10, speed: -0.006 },
        { x: w * 0.65, y: h * 0.7,  r: 50,  teeth: 8,  speed: 0.008 },
      ];
      const loop = (t) => {
        ctx.clearRect(0, 0, w, h);
        rings.forEach(r => {
          ctx.save();
          ctx.translate(r.x, r.y);
          ctx.rotate(t * r.speed);
          ctx.strokeStyle = `rgba(${accentRGB},0.32)`;
          ctx.lineWidth = 2;
          for (let i = 0; i < r.teeth; i++) {
            const a = (i / r.teeth) * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(Math.cos(a) * r.r, Math.sin(a) * r.r);
            ctx.lineTo(Math.cos(a) * (r.r + 18), Math.sin(a) * (r.r + 18));
            ctx.stroke();
          }
          ctx.beginPath();
          ctx.arc(0, 0, r.r, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        });
        raf = requestAnimationFrame(loop);
      };
      loop(0);
    } else if (kind === 'petals' || kind === 'foodwave') {
      // Floating petals
      for (let i = 0; i < 40; i++) {
        particles.push({
          x: Math.random() * w, y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.3, vy: Math.random() * 0.4 + 0.2,
          r: Math.random() * 4 + 2, a: Math.random() * 0.4 + 0.2,
          rot: Math.random() * Math.PI,
        });
      }
      const loop = () => {
        ctx.clearRect(0, 0, w, h);
        particles.forEach(p => {
          p.x += p.vx; p.y += p.vy; p.rot += 0.01;
          if (p.y > h + 10) { p.y = -10; p.x = Math.random() * w; }
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          ctx.fillStyle = `rgba(${accentRGB},${p.a})`;
          ctx.beginPath();
          ctx.ellipse(0, 0, p.r * 1.8, p.r * 0.8, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        });
        raf = requestAnimationFrame(loop);
      };
      loop();
    } else if (kind === 'rings') {
      // Expanding rings (fitness)
      const rings = Array.from({ length: 5 }, (_, i) => ({ r: i * 60 + 20 }));
      let t0 = performance.now();
      const loop = (t) => {
        ctx.clearRect(0, 0, w, h);
        const cx = w * 0.5, cy = h * 0.5;
        rings.forEach((r, i) => {
          const rad = r.r + ((t - t0) / 20 + i * 40) % 300;
          const alpha = Math.max(0, 0.5 - rad / 600);
          ctx.strokeStyle = `rgba(${accentRGB},${alpha})`;
          ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.stroke();
        });
        raf = requestAnimationFrame(loop);
      };
      loop(t0);
    } else if (kind === 'pulse') {
      // Medical heartbeat pulse line
      let offset = 0;
      const loop = () => {
        ctx.clearRect(0, 0, w, h);
        ctx.strokeStyle = `rgba(${accentRGB},0.55)`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        const baseY = h * 0.5;
        for (let x = 0; x < w; x += 2) {
          const phase = ((x + offset) % 200) / 200;
          let y = baseY;
          if (phase > 0.4 && phase < 0.55) {
            const p = (phase - 0.4) / 0.15;
            y = baseY - Math.sin(p * Math.PI) * 60;
          } else if (phase > 0.55 && phase < 0.65) {
            const p = (phase - 0.55) / 0.1;
            y = baseY + Math.sin(p * Math.PI) * 40;
          }
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
        offset += 1.5;
        raf = requestAnimationFrame(loop);
      };
      loop();
    } else {
      // Default: orbital gold particles
      for (let i = 0; i < 50; i++) {
        particles.push({
          x: Math.random() * w, y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.2, vy: (Math.random() - 0.5) * 0.2,
          r: Math.random() * 1.5 + 0.5, a: Math.random() * 0.5 + 0.2,
        });
      }
      const loop = () => {
        ctx.clearRect(0, 0, w, h);
        particles.forEach(p => {
          p.x += p.vx; p.y += p.vy;
          if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
          if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${accentRGB},${p.a})`;
          ctx.fill();
        });
        raf = requestAnimationFrame(loop);
      };
      loop();
    }

    const onResize = () => { w = canvas.width = canvas.offsetWidth; h = canvas.height = canvas.offsetHeight; };
    window.addEventListener('resize', onResize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); };
  }, [kind, accent]);
  return <canvas ref={ref} className="absolute inset-0 w-full h-full pointer-events-none" />;
};

const hexToRgb = (hex) => {
  const m = hex.replace('#', '').match(/.{1,2}/g);
  return m ? m.map((x) => parseInt(x, 16)).join(',') : '255,255,255';
};

// ─────────────────────────────────────────────────────────────
// Subtle dismissible demo ribbon — thin, bottom-right, auto-fades
// ─────────────────────────────────────────────────────────────
const DismissibleDemoBanner = ({ theme }) => {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;
  const isDark = theme.bg && parseInt(theme.bg.replace('#',''), 16) < 0x888888;
  return (
    <div data-testid="demo-banner"
      className="fixed z-50 flex items-center gap-2 px-3 py-1.5 rounded-full shadow-lg text-[10px] tracking-wider font-semibold backdrop-blur-sm"
      style={{
        bottom: 16, right: 16,
        background: isDark ? 'rgba(0,0,0,0.75)' : 'rgba(255,255,255,0.92)',
        color: theme.accent,
        border: `1px solid ${theme.accent}55`,
      }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: theme.accent }} />
      <span>PREVIEW</span>
      <button
        onClick={() => setVisible(false)}
        data-testid="demo-banner-dismiss"
        className="ml-1 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss preview banner"
      >
        ×
      </button>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────
const AuremSampleWebsite = () => {
  const { slug } = useParams();
  const [site, setSite] = useState(null);
  const [error, setError] = useState(null);
  const sessionRef = useRef(null);
  const engagedFiredRef = useRef(false);

  // iter 322ab — if site is still being generated, auto-refresh every 5s
  // until it's ready. Visitors land here right after the homepage form
  // submit, so we want the page to come alive automatically.
  useEffect(() => {
    let cancelled = false;
    let pollTimer = null;
    const fetchSite = () => {
      fetch(`${API}/api/website-builder/${slug}`)
        .then((r) => r.ok ? r.json() : Promise.reject(r.status === 404 ? 'Website not found' : 'Failed to load'))
        .then((d) => {
          if (cancelled) return;
          setSite(d);
          // Keep polling while still building (5s cadence).
          if (d?.generation_state && d.generation_state !== 'ready') {
            pollTimer = setTimeout(fetchSite, 5000);
          }
        })
        .catch((e) => !cancelled && setError(String(e)));
    };
    fetchSite();
    return () => { cancelled = true; if (pollTimer) clearTimeout(pollTimer); };
  }, [slug]);

  // Live viewer tracking: visit → heartbeat every 15s → engaged at 30s
  useEffect(() => {
    if (!site) return;

    // 1. POST visit (triggers admin hot-lead alert)
    fetch(`${API}/api/website-builder/sample/${slug}/visit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        referrer: document.referrer || '',
        user_agent: navigator.userAgent || '',
      }),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.session_id) sessionRef.current = d.session_id; })
      .catch(() => {});

    // 2. Heartbeat every 15s
    const heartbeat = setInterval(() => {
      if (!sessionRef.current) return;
      fetch(`${API}/api/website-builder/sample/${slug}/heartbeat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionRef.current }),
      }).catch(() => {});
    }, 15000);

    // 3. Engagement nudge at 30s (idempotent on backend)
    const engageTimer = setTimeout(() => {
      if (engagedFiredRef.current || !sessionRef.current) return;
      engagedFiredRef.current = true;
      fetch(`${API}/api/website-builder/sample/${slug}/engaged`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionRef.current }),
      }).catch(() => {});
    }, 30000);

    return () => { clearInterval(heartbeat); clearTimeout(engageTimer); };
  }, [site, slug]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center text-white" style={{ background: '#0A0A0A' }} data-testid="sample-error">
        <div className="text-center p-8">
          <div className="text-sm tracking-[0.4em] text-[#C9A227] mb-3">AUREM</div>
          <h1 className="text-xl font-bold mb-2">Website not yet generated</h1>
          <p className="text-sm text-white/60">The sample for <code>{slug}</code> hasn't been built yet.</p>
        </div>
      </div>
    );
  }
  // iter 322ab — site exists but still generating → friendly building state
  if (site && site.generation_state && site.generation_state !== 'ready') {
    const isFailed = site.generation_state === 'failed';
    return (
      <div
        data-testid="sample-building"
        className="min-h-screen flex items-center justify-center text-white"
        style={{ background: '#0A0A0A' }}
      >
        <div className="text-center p-8 max-w-md">
          <div className="text-sm tracking-[0.4em] text-[#C9A227] mb-3">AUREM</div>
          {isFailed ? (
            <>
              <h1 className="text-xl font-bold mb-2">Generation hiccup</h1>
              <p className="text-sm text-white/60 mb-4">
                We hit a snag building <code>{slug}</code>. Our team is on it —
                check back in a few minutes or email{' '}
                <a className="text-[#C9A227] underline" href="mailto:ora@aurem.live">ora@aurem.live</a>.
              </p>
            </>
          ) : (
            <>
              <h1 className="text-xl font-bold mb-2">Building your site…</h1>
              <p className="text-sm text-white/60 mb-4">
                Hand-crafting <strong>{site?.business?.name || slug}</strong>. This takes 30–60 seconds.
              </p>
              <div className="w-10 h-10 mx-auto rounded-full border-2 border-[#C9A227]/20 border-t-[#C9A227] animate-spin" />
              <p className="text-xs text-white/40 mt-6">Auto-refreshing every 5s.</p>
            </>
          )}
        </div>
      </div>
    );
  }

  if (!site) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0A0A0A', color: '#fff' }} data-testid="sample-loading">
        <div className="w-10 h-10 rounded-full border-2 border-[#C9A227]/20 border-t-[#C9A227] animate-spin" />
      </div>
    );
  }

  const { theme, business, tagline, services, why_points, reviews, legal, industry } = site;
  const phoneClean = (business.phone || '').replace(/[^0-9+]/g, '');
  const isDark = isDarkHex(theme.bg);
  const bodyText = theme.text;
  const muted = isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.55)';
  const borderCol = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
  const cardBg = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)';

  const mapsQuery = encodeURIComponent(business.location || `${business.name} ${business.city || ''}`);
  const mapsEmbed = `https://www.google.com/maps?q=${mapsQuery}&output=embed`;

  return (
    <div style={{
      background: theme.bg, color: bodyText,
      fontFamily: `'${theme.font}', -apple-system, BlinkMacSystemFont, sans-serif`,
      minHeight: '100vh',
    }} data-testid="sample-website">

      {/* Scope-specific CSS: hide any global accessibility/skip links on sample route */}
      <style>{`
        body > .skip-nav-link, a.skip-nav-link { display: none !important; }
        [data-testid="sample-website"] ~ * { display: none !important; }
      `}</style>

      <link rel="stylesheet" href={`https://fonts.googleapis.com/css2?family=${encodeURIComponent(theme.font)}:wght@400;600;700;800&display=swap`} />

      {/* Demo banner — subtle thin ribbon (dismissible) */}
      <DismissibleDemoBanner theme={theme} />

      {/* HERO */}
      <section data-testid="sample-hero" className="relative overflow-hidden" style={{ minHeight: '92vh' }}>
        <HeroAnimation kind={theme.hero_anim} accent={theme.accent} />
        <div className="absolute inset-0" style={{ background: `radial-gradient(ellipse at 50% 30%, ${theme.accent}18, transparent 60%)` }} />
        <div className="relative z-10 max-w-5xl mx-auto px-6 md:px-10 pt-20 pb-16 md:pt-28 text-center">
          <div className="inline-flex items-center gap-2 text-[11px] tracking-[0.3em] font-semibold mb-6"
            style={{ color: theme.accent, border: `1px solid ${theme.accent}55`, borderRadius: 999, padding: '6px 16px' }}>
            <Star className="w-3 h-3 fill-current" />
            {business.rating}★ ({business.reviews_count || 'Many'} Reviews)
          </div>
          <h1 className="font-bold mb-5" style={{ fontSize: 'clamp(2.4rem, 7vw, 5rem)', lineHeight: 1.08 }}>
            {business.name}
          </h1>
          <p className="text-base md:text-xl mb-10 max-w-2xl mx-auto" style={{ color: muted }}>
            {tagline}
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {phoneClean && (
              <a href={`tel:${phoneClean}`} data-testid="hero-cta-call"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-bold text-sm tracking-wider transition-all hover:scale-[1.03]"
                style={{ background: theme.accent, color: isDarkHex(theme.accent) ? '#fff' : '#000' }}>
                <Phone className="w-4 h-4" /> CALL NOW
              </a>
            )}
            {phoneClean && (
              <a href={`https://wa.me/${phoneClean.replace('+','')}`} target="_blank" rel="noopener noreferrer" data-testid="hero-cta-whatsapp"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-bold text-sm tracking-wider border transition-all hover:scale-[1.03]"
                style={{ borderColor: theme.accent, color: theme.accent }}>
                <MessageCircle className="w-4 h-4" /> WHATSAPP US
              </a>
            )}
          </div>
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce opacity-60">
            <ChevronDown className="w-6 h-6" style={{ color: theme.accent }} />
          </div>
        </div>
      </section>

      {/* SERVICES */}
      <section data-testid="sample-services" className="py-20 md:py-28 px-6 md:px-10">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <div className="text-[11px] tracking-[0.4em] font-semibold mb-3" style={{ color: theme.accent }}>SERVICES</div>
            <h2 className="font-bold" style={{ fontSize: 'clamp(1.8rem, 5vw, 3rem)' }}>What We Do</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {services.map((s, i) => {
              const Icon = ICONS[s.icon] || Star;
              return (
                <div key={i} data-testid={`service-${i}`}
                  className="group p-6 rounded-xl border transition-all duration-300 hover:-translate-y-1"
                  style={{
                    background: cardBg, borderColor: borderCol,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = theme.accent; e.currentTarget.style.boxShadow = `0 12px 32px ${theme.accent}26`; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = borderCol; e.currentTarget.style.boxShadow = 'none'; }}>
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center mb-4" style={{ background: `${theme.accent}22` }}>
                    <Icon className="w-6 h-6" style={{ color: theme.accent }} />
                  </div>
                  <h3 className="font-bold text-lg mb-2">{s.name}</h3>
                  <p className="text-sm" style={{ color: muted }}>{s.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* WHY CHOOSE US */}
      <section data-testid="sample-why" className="py-20 md:py-24 px-6 md:px-10" style={{ background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.03)' }}>
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <div className="text-[11px] tracking-[0.4em] font-semibold mb-3" style={{ color: theme.accent }}>WHY CHOOSE US</div>
            <h2 className="font-bold" style={{ fontSize: 'clamp(1.8rem, 5vw, 3rem)' }}>Built on Trust</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {why_points.map((w, i) => {
              const Icon = ICONS[w.icon] || Check;
              return (
                <div key={i} data-testid={`why-${i}`} className="text-center p-5 rounded-xl border"
                  style={{ background: cardBg, borderColor: borderCol }}>
                  <div className="w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-3"
                    style={{ background: `${theme.accent}22` }}>
                    <Icon className="w-5 h-5" style={{ color: theme.accent }} />
                  </div>
                  <div className="text-sm font-semibold">{w.text}</div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* REVIEWS */}
      <section data-testid="sample-reviews" className="py-20 md:py-24 px-6 md:px-10">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <div className="text-[11px] tracking-[0.4em] font-semibold mb-3" style={{ color: theme.accent }}>REVIEWS</div>
            <h2 className="font-bold" style={{ fontSize: 'clamp(1.8rem, 5vw, 3rem)' }}>What Our Customers Say</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {reviews.slice(0, 6).map((r, i) => (
              <div key={i} data-testid={`review-${i}`} className="p-6 rounded-xl border"
                style={{ background: cardBg, borderColor: borderCol }}>
                <div className="flex gap-0.5 mb-3">
                  {Array.from({ length: r.rating || 5 }).map((_, k) => (
                    <Star key={k} className="w-4 h-4 fill-current" style={{ color: theme.accent }} />
                  ))}
                </div>
                <p className="text-sm mb-3 italic" style={{ color: muted }}>"{r.text}"</p>
                <div className="text-[11px] tracking-wider" style={{ color: theme.accent }}>
                  — {r.author}{r.source === 'google' ? ' · Google' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CONTACT + MAP */}
      <section data-testid="sample-contact" className="py-20 md:py-24 px-6 md:px-10" style={{ background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.03)' }}>
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-10">
            <div className="text-[11px] tracking-[0.4em] font-semibold mb-3" style={{ color: theme.accent }}>CONTACT</div>
            <h2 className="font-bold" style={{ fontSize: 'clamp(1.8rem, 5vw, 3rem)' }}>Visit Us</h2>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-4">
              {business.location && (
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 mt-1 shrink-0" style={{ color: theme.accent }} />
                  <div>
                    <div className="text-[10px] tracking-widest font-semibold mb-1" style={{ color: theme.accent }}>ADDRESS</div>
                    <div>{business.location}</div>
                  </div>
                </div>
              )}
              {business.phone && (
                <a href={`tel:${phoneClean}`} className="flex items-start gap-3 hover:opacity-80" data-testid="contact-phone">
                  <Phone className="w-5 h-5 mt-1 shrink-0" style={{ color: theme.accent }} />
                  <div>
                    <div className="text-[10px] tracking-widest font-semibold mb-1" style={{ color: theme.accent }}>PHONE</div>
                    <div>{business.phone}</div>
                  </div>
                </a>
              )}
              <div className="flex items-start gap-3">
                <Clock className="w-5 h-5 mt-1 shrink-0" style={{ color: theme.accent }} />
                <div>
                  <div className="text-[10px] tracking-widest font-semibold mb-1" style={{ color: theme.accent }}>HOURS</div>
                  <div style={{ color: muted }}>Mon–Fri · 8am – 6pm<br />Sat · 9am – 4pm<br />Sun · Closed</div>
                </div>
              </div>
              {phoneClean && (
                <a href={`https://wa.me/${phoneClean.replace('+','')}`} target="_blank" rel="noopener noreferrer"
                  data-testid="contact-whatsapp"
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-xs tracking-wider transition-all hover:scale-[1.03] mt-3"
                  style={{ background: theme.accent, color: isDarkHex(theme.accent) ? '#fff' : '#000' }}>
                  <MessageCircle className="w-4 h-4" /> MESSAGE US ON WHATSAPP
                </a>
              )}
            </div>
            <div className="rounded-xl overflow-hidden border" style={{ borderColor: borderCol, minHeight: 300 }}>
              <iframe title="map" src={mapsEmbed} width="100%" height="100%" style={{ border: 0, minHeight: 300 }} loading="lazy" allowFullScreen />
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER — minimal, CASL-compliant */}
      <footer data-testid="sample-footer" className="py-10 px-6 md:px-10 border-t text-xs"
        style={{ borderColor: borderCol, color: muted }}>
        <div className="max-w-5xl mx-auto text-center space-y-3">
          <div className="flex justify-center gap-4 flex-wrap text-[11px]">
            <a href={`/legal/privacy/${slug}`} className="hover:underline" data-testid="footer-privacy">Privacy Policy</a>
            <span className="opacity-40">·</span>
            <a href={`/legal/terms/${slug}`} className="hover:underline" data-testid="footer-terms">Terms of Service</a>
            <span className="opacity-40">·</span>
            <a href={`mailto:opt-out@aurem.live?subject=Unsubscribe&body=${encodeURIComponent('Slug: ' + slug)}`} className="hover:underline" data-testid="footer-unsubscribe">Unsubscribe</a>
          </div>
          <div className="text-[12px] font-medium" style={{ color: bodyText }}>
            © 2026 {business.name}
          </div>
          <div className="text-[10px] opacity-60 max-w-xl mx-auto">
            {legal.disclaimer} · This is a free website preview — <a href="https://aurem.live" className="underline" style={{ color: theme.accent }}>aurem.live</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

const isDarkHex = (hex) => {
  const rgb = hexToRgb(hex).split(',').map(Number);
  const lum = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255;
  return lum < 0.5;
};

export default AuremSampleWebsite;
