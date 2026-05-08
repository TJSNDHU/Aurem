/**
 * AUREM Demo + Setup Tutorial
 * /demo — public landing referenced from Retell SMS link
 *
 * Sections:
 *   1. Hero — pitch + CTA "Start Free Trial"
 *   2. Embedded demo video (YouTube/Vimeo or direct mp4 via env)
 *   3. 5-step setup tutorial
 *   4. What AUREM repairs (live capability list)
 *   5. Final CTA
 */
import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  Crown, Play, Wrench, Search, Globe, Zap, Shield,
  CheckCircle, ArrowRight, Sparkles,
  Loader2, AlertTriangle, Lock, Mail, Send, ScanLine,
} from 'lucide-react';
import { BACKEND_URL } from '../lib/api';

const API = BACKEND_URL;

const VIDEO_URL = process.env.REACT_APP_AUREM_DEMO_VIDEO || ''; // mp4/webm direct URL
const YOUTUBE_ID = process.env.REACT_APP_AUREM_DEMO_YT || '';   // YouTube video ID (preferred)

const STEPS = [
  {
    n: 1, title: 'Sign up — 30 seconds',
    body: 'Click "Start Free Trial". Email + password. No credit card. You get instant access to the AUREM platform.',
    icon: CheckCircle, accent: '#22C55E',
  },
  {
    n: 2, title: 'Connect your website',
    body: 'Paste your domain. AUREM begins crawling it within 60 seconds — finds broken links, slow images, missing meta tags, schema errors, and AI-search visibility gaps.',
    icon: Globe, accent: '#06B6D4',
  },
  {
    n: 3, title: 'Approve your repair guardrails',
    body: 'One-time setup: pick what AUREM is allowed to auto-deploy (e.g. SEO meta tags YES, layout changes ASK FIRST). Founder kill-switch always available.',
    icon: Shield, accent: '#D4AF37',
  },
  {
    n: 4, title: 'Watch repairs ship live',
    body: 'AUREM detects → patches → deploys to your live site within minutes. Every fix is logged, reviewed, and one-click reversible. You see the diff in real time on the dashboard.',
    icon: Wrench, accent: '#EF4444',
  },
  {
    n: 5, title: 'AI agents start hunting leads',
    body: 'Hunter, Scout, Closer, Envoy and ORA Brain run 24/7 — calling, texting, emailing local prospects, booking discovery calls into your calendar. Most clients see 8-15 new bookings per month.',
    icon: Sparkles, accent: '#8B5CF6',
  },
];

const REPAIRS = [
  { icon: Wrench,  label: 'Broken links auto-fixed',                 color: '#EF4444' },
  { icon: Search,  label: 'SEO meta tags rewritten weekly',          color: '#22C55E' },
  { icon: Globe,   label: 'GEO Optimization (ChatGPT, Perplexity)',  color: '#06B6D4' },
  { icon: Zap,     label: 'Speed patches (image compress, JS defer)',color: '#D4AF37' },
  { icon: Shield,  label: 'Schema + sitemap auto-generated',         color: '#8B5CF6' },
  { icon: Sparkles,label: 'Contact form failure detection',          color: '#F59E0B' },
];

const Demo = () => {
  useEffect(() => {
    document.title = 'AUREM Demo & Setup Tutorial — World\'s First Automation Intelligence';
  }, []);

  const ctaStyle = {
    background: 'linear-gradient(135deg,#D4AF37,#8B7355)',
    color: '#06060A',
    fontWeight: 600,
    fontSize: 14,
    padding: '14px 28px',
    borderRadius: 10,
    textDecoration: 'none',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
  };

  return (
    <div data-testid="demo-page"
      style={{ background: '#06060A', color: '#EDE8DF', minHeight: '100vh', fontFamily: "'Inter',sans-serif" }}>
      {/* HERO */}
      <section style={{ padding: '80px 24px 60px', textAlign: 'center', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999,
                      background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.25)', marginBottom: 24 }}>
          <Crown style={{ width: 12, height: 12, color: '#D4AF37' }} />
          <span style={{ fontSize: 10, color: '#D4AF37', letterSpacing: '0.25em', textTransform: 'uppercase' }}>
            World's First · Automation Intelligence
          </span>
        </div>
        <h1 style={{ fontFamily: "'Cinzel',serif", fontSize: 'clamp(36px,6vw,64px)', lineHeight: 1.1, margin: '0 0 18px',
                     letterSpacing: '0.02em' }}>
          See AUREM repair<br/>your website live.
        </h1>
        <p style={{ fontSize: 16, color: '#9A9388', maxWidth: 640, margin: '0 auto 32px', lineHeight: 1.6 }}>
          Watch the 2-minute demo, then start a free 7-day trial. AUREM scans your real website
          and ships SEO + speed + schema fixes automatically — no developer needed.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link to="/signup" data-testid="demo-cta-primary" style={ctaStyle}>
            Start Free 7-Day Trial <ArrowRight style={{ width: 14, height: 14 }} />
          </Link>
          <a href="#video" data-testid="demo-cta-watch" style={{
            ...ctaStyle, background: 'transparent', color: '#EDE8DF',
            border: '1px solid rgba(255,255,255,0.12)',
          }}>
            <Play style={{ width: 14, height: 14 }} /> Watch demo
          </a>
        </div>
        <div style={{ marginTop: 18, fontSize: 11, color: '#7A7468', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          No credit card · Cancel any time · One-click reversible
        </div>
      </section>

      {/* SCANNER WIDGET — viral lead capture */}
      <ScannerWidget />

      {/* VIDEO */}
      <section id="video" data-testid="demo-video-section"
        style={{ maxWidth: 980, margin: '0 auto 80px', padding: '0 24px' }}>
        <div style={{
          borderRadius: 16,
          overflow: 'hidden',
          border: '1px solid rgba(212,175,55,0.18)',
          boxShadow: '0 30px 80px rgba(0,0,0,0.55)',
          aspectRatio: '16/9',
          background: '#0B0B10',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {YOUTUBE_ID ? (
            <iframe
              data-testid="demo-video-yt"
              title="AUREM demo"
              src={`https://www.youtube.com/embed/${YOUTUBE_ID}?rel=0&modestbranding=1`}
              style={{ width: '100%', height: '100%', border: 0 }}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : VIDEO_URL ? (
            <video data-testid="demo-video-mp4" src={VIDEO_URL} controls
                   style={{ width: '100%', height: '100%' }}>
              <track kind="captions" />
            </video>
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: '#7A7468' }}>
              <Play style={{ width: 56, height: 56, color: '#D4AF37', marginBottom: 14, opacity: 0.4 }} />
              <div style={{ fontSize: 13, color: '#9A9388' }}>Demo video uploading shortly.</div>
              <div style={{ fontSize: 11, marginTop: 6, color: '#555' }}>
                Set <code style={{ color: '#D4AF37' }}>REACT_APP_AUREM_DEMO_YT</code> to embed YouTube,
                or <code style={{ color: '#D4AF37' }}>REACT_APP_AUREM_DEMO_VIDEO</code> for direct mp4.
              </div>
              <Link to="/signup" data-testid="demo-fallback-cta" style={{ ...ctaStyle, marginTop: 22, fontSize: 12 }}>
                Skip — start trial now <ArrowRight style={{ width: 12, height: 12 }} />
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* SETUP STEPS */}
      <section data-testid="demo-steps"
        style={{ maxWidth: 1100, margin: '0 auto 100px', padding: '0 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div style={{ fontSize: 9, color: '#D4AF37', letterSpacing: '0.3em', marginBottom: 8 }}>
            STEP-BY-STEP SETUP
          </div>
          <h2 style={{ fontFamily: "'Cinzel',serif", fontSize: 32, margin: 0, letterSpacing: '0.05em' }}>
            From signup to first auto-repair in 5 minutes.
          </h2>
        </div>
        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {STEPS.map((s) => {
            const I = s.icon;
            return (
              <div key={s.n} data-testid={`demo-step-${s.n}`}
                style={{
                  padding: 24, borderRadius: 14, position: 'relative', overflow: 'hidden',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: s.accent }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: `${s.accent}1A`, color: s.accent,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: 'JetBrains Mono, monospace', fontSize: 13, fontWeight: 700,
                  }}>{s.n}</div>
                  <I style={{ width: 16, height: 16, color: s.accent }} />
                </div>
                <h3 style={{ fontSize: 16, margin: '0 0 8px', color: '#EDE8DF', fontFamily: "'Cinzel',serif", letterSpacing: '0.04em' }}>
                  {s.title}
                </h3>
                <p style={{ fontSize: 12, color: '#9A9388', margin: 0, lineHeight: 1.6 }}>
                  {s.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CAPABILITIES */}
      <section data-testid="demo-capabilities"
        style={{ maxWidth: 1100, margin: '0 auto 100px', padding: '0 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ fontSize: 9, color: '#D4AF37', letterSpacing: '0.3em', marginBottom: 8 }}>
            WHAT AUREM REPAIRS — AUTOMATICALLY
          </div>
          <h2 style={{ fontFamily: "'Cinzel',serif", fontSize: 28, margin: 0 }}>
            No developer. No tickets. No waiting.
          </h2>
        </div>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
          {REPAIRS.map((r, i) => {
            const I = r.icon;
            return (
              <div key={i} data-testid={`demo-cap-${i}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: 16, borderRadius: 10,
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: `${r.color}1A`, color: r.color,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <I style={{ width: 16, height: 16 }} />
                </div>
                <div style={{ fontSize: 13, color: '#EDE8DF' }}>{r.label}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* FINAL CTA */}
      <section data-testid="demo-final-cta"
        style={{ maxWidth: 800, margin: '0 auto 120px', padding: '0 24px', textAlign: 'center' }}>
        <h2 style={{ fontFamily: "'Cinzel',serif", fontSize: 28, margin: '0 0 14px' }}>
          Ready to let AUREM run your business?
        </h2>
        <p style={{ fontSize: 14, color: '#9A9388', marginBottom: 24 }}>
          7 days free. No credit card. Full platform unlocked. Cancel any time in one click.
        </p>
        <Link to="/signup" data-testid="demo-cta-final" style={ctaStyle}>
          Activate my trial <ArrowRight style={{ width: 14, height: 14 }} />
        </Link>
      </section>
    </div>
  );
};

export default Demo;

// ─────────────────────────────────────────────────────────────
// ScannerWidget — live website scan + quota lock + email capture
// ─────────────────────────────────────────────────────────────

const SCAN_PHASES = [
  { from: 0,  to: 8,  label: 'Checking meta tags…' },
  { from: 8,  to: 16, label: 'Testing page speed…' },
  { from: 16, to: 24, label: 'Scanning for broken links…' },
  { from: 24, to: 30, label: 'Analyzing schema + AI search visibility…' },
];

const SEV_COLOR = {
  red:    { ring: '#EF4444', bg: 'rgba(239,68,68,0.08)', label: 'CRITICAL' },
  yellow: { ring: '#F59E0B', bg: 'rgba(245,158,11,0.08)', label: 'NEEDS WORK' },
  green:  { ring: '#22C55E', bg: 'rgba(34,197,94,0.08)', label: 'OK' },
};

function getDeviceId() {
  try {
    let id = localStorage.getItem('aurem_scan_device_id');
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) || `dev-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem('aurem_scan_device_id', id);
    }
    return id;
  } catch {
    return `dev-${Date.now()}`;
  }
}

const ScannerWidget = () => {
  const [domain, setDomain] = useState('');
  const [scanning, setScanning] = useState(false);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [quota, setQuota] = useState({ used: 0, remaining: 3, limit: 3 });
  const [locked, setLocked] = useState(false);

  const [reportEmail, setReportEmail] = useState('');
  const [reportSending, setReportSending] = useState(false);
  const [reportSent, setReportSent] = useState(false);

  const deviceId = useRef(getDeviceId());
  const phaseTimerRef = useRef(null);

  const refreshQuota = async () => {
    try {
      const r = await fetch(`${API}/api/scan/quick/quota?device_id=${encodeURIComponent(deviceId.current)}`);
      const d = await r.json();
      setQuota(d.quota || { used: 0, remaining: 3, limit: 3 });
      setLocked((d.quota?.remaining ?? 3) <= 0);
    } catch { /* ignore */ }
  };

  useEffect(() => { refreshQuota(); }, []);

  const startCountdown = () => {
    setPhaseIdx(0);
    setProgress(0);
    const start = Date.now();
    phaseTimerRef.current = setInterval(() => {
      const t = (Date.now() - start) / 1000;
      const pct = Math.min(100, (t / 30) * 100);
      setProgress(pct);
      const idx = SCAN_PHASES.findIndex((p) => t >= p.from && t < p.to);
      if (idx >= 0) setPhaseIdx(idx);
    }, 200);
  };

  const stopCountdown = () => {
    if (phaseTimerRef.current) clearInterval(phaseTimerRef.current);
    phaseTimerRef.current = null;
    setProgress(100);
  };

  const handleScan = async (e) => {
    e?.preventDefault?.();
    if (!domain.trim() || scanning || locked) return;
    setScanning(true);
    setResult(null);
    setError('');
    setReportSent(false);
    setReportEmail('');
    startCountdown();

    try {
      const r = await fetch(`${API}/api/scan/quick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: domain.trim(), device_id: deviceId.current }),
      });
      const d = await r.json();
      stopCountdown();

      if (d.rate_limited) {
        setLocked(true);
        setQuota(d.quota || quota);
      } else if (!d.ok) {
        setError(d.error || 'Scan failed. Try a different URL.');
        setQuota(d.quota || quota);
      } else {
        setResult(d);
        setQuota(d.quota || quota);
        setLocked((d.quota?.remaining ?? 0) <= 0);
      }
    } catch {
      stopCountdown();
      setError('Network error. Try again.');
    }
    setScanning(false);
  };

  const sendReport = async (e) => {
    e?.preventDefault?.();
    if (!reportEmail.trim() || reportSending || !result) return;
    setReportSending(true);
    try {
      const r = await fetch(`${API}/api/scan/quick/email-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: deviceId.current,
          email: reportEmail.trim(),
          domain: result.domain,
          score: result.score || 0,
          critical_issues: result.critical_issues || 0,
        }),
      });
      const d = await r.json();
      setReportSent(d.ok);
    } catch {
      setError('Could not send. Try again.');
    }
    setReportSending(false);
  };

  return (
    <section data-testid="scanner-widget"
      style={{ maxWidth: 920, margin: '0 auto 80px', padding: '0 24px' }}>
      <div style={{
        borderRadius: 18, padding: '36px 32px',
        background: 'linear-gradient(180deg, rgba(212,175,55,0.04), rgba(255,255,255,0.02))',
        border: '1px solid rgba(212,175,55,0.18)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 26 }}>
          <div style={{ fontSize: 9, color: '#D4AF37', letterSpacing: '0.3em', marginBottom: 8 }}>
            LIVE WEBSITE AUDIT — 30 SECONDS
          </div>
          <h2 style={{ fontFamily: "'Cinzel',serif", fontSize: 26, margin: '0 0 10px' }}>
            Scan your site. See what AUREM would fix.
          </h2>
          <div style={{ fontSize: 12, color: '#9A9388' }}>
            <span data-testid="scanner-quota" style={{ color: locked ? '#EF4444' : '#9A9388' }}>
              {quota.remaining > 0 ? `${quota.remaining} of ${quota.limit} free scans remaining` : 'Free scans exhausted'}
            </span>
            {' · '}No card needed
          </div>
        </div>

        {/* Input */}
        <form onSubmit={handleScan} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 240, position: 'relative' }}>
            <Globe style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', width: 14, height: 14, color: '#7A7468' }} />
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="yourwebsite.com"
              disabled={scanning || locked}
              data-testid="scanner-domain-input"
              style={{
                width: '100%', padding: '14px 14px 14px 38px', fontSize: 14,
                background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10, color: '#EDE8DF', outline: 'none',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={scanning || locked || !domain.trim()}
            data-testid="scanner-run-btn"
            style={{
              padding: '14px 26px', borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: 'pointer',
              background: locked ? '#3A3830' : 'linear-gradient(135deg,#D4AF37,#8B7355)',
              color: locked ? '#7A7468' : '#06060A',
              border: 'none', display: 'flex', alignItems: 'center', gap: 8,
              opacity: (scanning || !domain.trim() || locked) ? 0.65 : 1,
            }}>
            {scanning ? <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} /> : <ScanLine style={{ width: 14, height: 14 }} />}
            {scanning ? 'Scanning…' : locked ? 'Locked' : 'Scan now'}
          </button>
        </form>

        {/* Countdown / phase */}
        {scanning && (
          <div data-testid="scanner-progress" style={{ marginTop: 22 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#9A9388', marginBottom: 6 }}>
              <span>{SCAN_PHASES[phaseIdx]?.label || 'Working…'}</span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{Math.floor(progress)}%</span>
            </div>
            <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{
                width: `${progress}%`, height: '100%',
                background: 'linear-gradient(90deg,#D4AF37,#22C55E)',
                transition: 'width 200ms linear',
              }} />
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div data-testid="scanner-error" style={{ marginTop: 18, padding: 12, borderRadius: 10,
                       background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
                       color: '#EF4444', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle style={{ width: 14, height: 14 }} /> {error}
          </div>
        )}

        {/* LOCKED panel */}
        {locked && !scanning && (
          <div data-testid="scanner-locked" style={{ marginTop: 22, padding: 24, borderRadius: 12,
                       background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.25)',
                       textAlign: 'center' }}>
            <Lock style={{ width: 22, height: 22, color: '#D4AF37', marginBottom: 10 }} />
            <div style={{ fontFamily: "'Cinzel',serif", fontSize: 18, marginBottom: 6 }}>
              You've used your 3 free scans.
            </div>
            <p style={{ fontSize: 12, color: '#9A9388', marginBottom: 16, lineHeight: 1.6 }}>
              Start your free 7-day trial to unlock unlimited scans + automatic fixes.<br />
              No credit card required.
            </p>
            <Link to="/signup" data-testid="scanner-locked-cta" style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: '12px 24px',
              background: 'linear-gradient(135deg,#D4AF37,#8B7355)', color: '#06060A',
              borderRadius: 10, fontWeight: 600, fontSize: 13, textDecoration: 'none',
            }}>
              Start Free Trial <ArrowRight style={{ width: 13, height: 13 }} />
            </Link>
          </div>
        )}

        {/* RESULTS */}
        {result && !scanning && (
          <div data-testid="scanner-result" style={{ marginTop: 28 }}>
            {/* Score banner */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px 20px', borderRadius: 12, marginBottom: 18,
              background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)',
            }}>
              <div>
                <div style={{ fontSize: 9, color: '#7A7468', letterSpacing: '0.25em', textTransform: 'uppercase' }}>
                  Diagnostic Audit · {result.domain}
                </div>
                <div style={{ fontSize: 14, color: '#EDE8DF', marginTop: 2 }}>
                  {result.critical_issues > 0
                    ? <><span style={{ color: '#EF4444', fontWeight: 600 }}>{result.critical_issues}</span> critical issues found · activate AUREM to start fixing</>
                    : 'Site looks healthy. AUREM keeps it that way 24/7.'}
                </div>
                <div style={{ fontSize: 10, color: '#7A7468', marginTop: 4, fontStyle: 'italic' }}>
                  Read-only scan · no changes made to your website
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 28, lineHeight: 1,
                              color: result.score >= 80 ? '#22C55E' : result.score >= 60 ? '#F59E0B' : '#EF4444' }}>
                  {result.score}
                </div>
                <div style={{ fontSize: 9, color: '#7A7468', letterSpacing: '0.2em' }}>SCORE / 100</div>
              </div>
            </div>

            {/* Issue cards */}
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: '1fr' }}>
              {(result.cards || []).map((c) => {
                const sev = SEV_COLOR[c.severity] || SEV_COLOR.yellow;
                return (
                  <div key={c.id} data-testid={`scanner-card-${c.id}`}
                    style={{ padding: 16, borderRadius: 12, background: 'rgba(255,255,255,0.02)',
                             border: `1px solid ${sev.ring}33` }}>
                    {/* Title row */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#EDE8DF' }}>{c.title}</div>
                      <span style={{ fontSize: 8, fontWeight: 700, padding: '3px 8px', borderRadius: 999,
                                     background: sev.ring, color: '#06060A', letterSpacing: '0.1em' }}>
                        {sev.label}
                      </span>
                    </div>

                    {/* BEFORE | AFTER two-column layout */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      {/* YOUR SITE NOW */}
                      <div style={{ padding: 12, borderRadius: 10, background: sev.bg, border: `1px solid ${sev.ring}33` }}>
                        <div style={{ fontSize: 8, color: sev.ring, letterSpacing: '0.25em', marginBottom: 8, fontWeight: 700 }}>
                          YOUR SITE NOW
                        </div>
                        <ul style={{ margin: 0, paddingLeft: 14, color: '#9A9388', fontSize: 11, lineHeight: 1.6 }}>
                          {c.findings.map((f, i) => <li key={i}>{f}</li>)}
                        </ul>
                      </div>

                      {/* WITH AUREM — locked preview */}
                      <div style={{ padding: 12, borderRadius: 10, position: 'relative', overflow: 'hidden',
                                    background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.18)' }}>
                        <div style={{ fontSize: 8, color: '#22C55E', letterSpacing: '0.25em', marginBottom: 8, fontWeight: 700 }}>
                          WITH AUREM
                        </div>
                        <ul style={{ margin: 0, paddingLeft: 14, color: '#22C55E', fontSize: 11, lineHeight: 1.6,
                                     filter: 'blur(3.5px)', userSelect: 'none', pointerEvents: 'none' }}>
                          <li>{c.fix}</li>
                          <li>Auto-monitored every 6 hours</li>
                          <li>One-click reversible</li>
                        </ul>
                        {/* Lock overlay */}
                        <div style={{
                          position: 'absolute', inset: 0,
                          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                          background: 'linear-gradient(180deg, rgba(6,6,10,0.55), rgba(6,6,10,0.85))',
                        }}>
                          <Lock style={{ width: 14, height: 14, color: '#D4AF37', marginBottom: 6 }} />
                          <div style={{ fontSize: 10, color: '#D4AF37', textAlign: 'center', fontWeight: 600 }}>
                            Activate fixes →
                          </div>
                          <Link to="/signup" data-testid={`scanner-card-cta-${c.id}`}
                            style={{ marginTop: 4, fontSize: 9, color: '#22C55E', textDecoration: 'underline' }}>
                            Start Free Trial
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Email report capture */}
            {!reportSent ? (
              <form onSubmit={sendReport} data-testid="scanner-email-form" style={{ marginTop: 22, padding: 18, borderRadius: 12,
                                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: 11, color: '#9A9388', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Mail style={{ width: 13, height: 13, color: '#06B6D4' }} />
                  Email me the full report — get the breakdown anytime.
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <input type="email" required value={reportEmail}
                    onChange={(e) => setReportEmail(e.target.value)}
                    placeholder="you@business.com"
                    data-testid="scanner-email-input"
                    style={{ flex: 1, minWidth: 220, padding: '11px 14px', fontSize: 13,
                             background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)',
                             borderRadius: 10, color: '#EDE8DF', outline: 'none' }} />
                  <button type="submit" disabled={reportSending || !reportEmail.trim()}
                    data-testid="scanner-email-send"
                    style={{ padding: '11px 20px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                             background: 'rgba(6,182,212,0.18)', border: '1px solid rgba(6,182,212,0.4)',
                             color: '#06B6D4', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {reportSending ? <Loader2 className="animate-spin" style={{ width: 12, height: 12 }} /> : <Send style={{ width: 12, height: 12 }} />}
                    Send report
                  </button>
                </div>
              </form>
            ) : (
              <div data-testid="scanner-email-sent" style={{ marginTop: 22, padding: 14, borderRadius: 10,
                              background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)',
                              color: '#22C55E', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                <CheckCircle style={{ width: 14, height: 14 }} /> Report sent. Check your inbox in the next minute.
              </div>
            )}

            {/* Trial CTA */}
            <div style={{ marginTop: 22, textAlign: 'center', padding: '20px 16px',
                          borderRadius: 12, background: 'linear-gradient(135deg, rgba(212,175,55,0.10), rgba(212,175,55,0.04))',
                          border: '1px solid rgba(212,175,55,0.30)' }}>
              <div style={{ fontFamily: "'Cinzel',serif", fontSize: 16, marginBottom: 4 }}>
                Activate AUREM to start fixing all of this.
              </div>
              <div style={{ fontSize: 11, color: '#9A9388', marginBottom: 14 }}>
                Free 7-day trial — no credit card. Fixes activate after you sign up & install the AUREM tag.
              </div>
              <Link to="/signup" data-testid="scanner-result-cta" style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, padding: '11px 22px',
                background: 'linear-gradient(135deg,#D4AF37,#8B7355)', color: '#06060A',
                borderRadius: 10, fontWeight: 600, fontSize: 12, textDecoration: 'none',
              }}>
                Start Free Trial <ArrowRight style={{ width: 12, height: 12 }} />
              </Link>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
