/**
 * AUREM Site Monitor — Free Lead Magnet Landing Page
 * Route: /monitor-free (PUBLIC, no auth)
 * Purpose: capture email + URL, start 30-day free monitoring, drive signups
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import '../theme/aurem-floating.css';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const GOLD = '#C9A84C';
const OBSIDIAN = '#0D0D0D';
const GREEN = '#4ADE80';
const RED = '#EF4444';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700;900&family=Cormorant+Garamond:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
* { box-sizing:border-box; }
.mf-root { min-height:100vh; background:transparent; color:#E8E0D0; padding:0; overflow-x:hidden; }
.mf-nav { padding:20px 40px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(201,168,76,0.08); }
.mf-brand { font-family:'Cinzel Decorative',serif; color:${GOLD}; font-size:22px; letter-spacing:0.1em; }
.mf-hero { padding:80px 24px 40px; text-align:center; max-width:900px; margin:0 auto; }
.mf-h1 { font-family:'Cinzel Decorative',serif; font-size:56px; color:${GOLD}; letter-spacing:0.03em; margin:0 0 16px 0; line-height:1.1; }
.mf-h1 .amber { color:#fff; }
.mf-sub { font-family:'Cormorant Garamond',serif; font-size:22px; color:#ccc; line-height:1.5; margin-bottom:20px; }
.mf-form { max-width:560px; margin:32px auto 20px; display:grid; gap:12px; }
.mf-input { background:rgba(0,0,0,0.5); border:1px solid rgba(201,168,76,0.3); color:#fff; padding:16px 20px; border-radius:12px; font-family:'JetBrains Mono',monospace; font-size:14px; width:100%; }
.mf-input:focus { outline:none; border-color:${GOLD}; box-shadow:0 0 0 4px rgba(201,168,76,0.15); }
.mf-cta { background:${GOLD}; color:${OBSIDIAN}; border:none; padding:18px 40px; border-radius:12px; font-family:'Cinzel Decorative',serif; font-size:16px; letter-spacing:0.1em; cursor:pointer; font-weight:700; transition:all 0.2s; }
.mf-cta:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(201,168,76,0.4); }
.mf-cta:disabled { opacity:0.5; cursor:not-allowed; }
.mf-benefits { max-width:1000px; margin:0 auto; padding:60px 24px; }
.mf-grid3 { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:24px; }
.mf-card { background:rgba(13,13,13,0.6); border:1px solid rgba(201,168,76,0.1); border-radius:14px; padding:24px; backdrop-filter:blur(12px); }
.mf-card-icon { font-family:'JetBrains Mono',monospace; color:${GOLD}; font-size:20px; margin-bottom:10px; }
.mf-card-title { font-family:'Cinzel Decorative',serif; color:${GOLD}; font-size:14px; letter-spacing:0.1em; margin-bottom:8px; }
.mf-card-body { font-family:'Cormorant Garamond',serif; color:#ccc; font-size:16px; line-height:1.5; }
.mf-trust { font-size:11px; color:#888; letter-spacing:0.15em; text-transform:uppercase; margin-top:10px; }
.mf-compare { max-width:900px; margin:20px auto 60px; padding:0 24px; }
.mf-compare-title { font-family:'Cinzel Decorative',serif; color:${GOLD}; font-size:22px; text-align:center; margin-bottom:24px; letter-spacing:0.08em; }
.mf-compare-table { width:100%; border-collapse:collapse; font-family:'JetBrains Mono',monospace; font-size:13px; }
.mf-compare-table th { padding:12px; color:${GOLD}; font-weight:500; text-align:left; border-bottom:1px solid rgba(201,168,76,0.2); font-size:11px; letter-spacing:0.15em; text-transform:uppercase; }
.mf-compare-table td { padding:12px; border-bottom:1px solid rgba(255,255,255,0.04); color:#ccc; }
.mf-compare-table td.good { color:${GREEN}; }
.mf-compare-table td.bad { color:${RED}; }
.mf-footer { padding:40px 24px; text-align:center; border-top:1px solid rgba(201,168,76,0.08); color:#666; font-family:'JetBrains Mono',monospace; font-size:11px; letter-spacing:0.1em; }
@media (max-width:640px) { .mf-h1 { font-size:36px; } .mf-sub { font-size:17px; } }
`;

export default function MonitorFreeLanding() {
  const [email, setEmail] = useState('');
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    if (!email || !email.includes('@')) { setError('Please enter a valid email'); return; }
    if (!url || url.length < 4) { setError('Please enter a URL'); return; }
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/site-monitor/free/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), url: url.trim() }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setSuccess(j);
    } catch (e) {
      setError(e.message || 'Signup failed');
    }
    setLoading(false);
  };

  return (
    <>
      <Helmet>
        <title>Free Website Monitoring | AUREM, 7 Days, No Credit Card</title>
        <meta name="description" content="24×7 uptime monitoring for your website. Get email alerts when your site goes down. 7-day free trial, no credit card required." />
        <meta property="og:title" content="AUREM — Free Website Uptime Monitoring" />
        <meta property="og:description" content="24×7 monitoring with instant downtime alerts. Free 7-day trial." />
        <link rel="canonical" href="https://aurem.live/monitor-free" />
      </Helmet>
      <style>{CSS}</style>
      <div className="mf-root aurem-page-bg-circuit" data-testid="monitor-free-landing">
        <nav className="mf-nav">
          <Link to="/" style={{ textDecoration: 'none' }}><span className="mf-brand">AUREM</span></Link>
          <Link to="/platform/login" style={{ color: GOLD, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, textDecoration: 'none', letterSpacing: '0.1em' }}>SIGN IN →</Link>
        </nav>

        {/* Hero + form */}
        <section className="mf-hero">
          <h1 className="mf-h1">Is Your Website <span className="amber">Down Right Now?</span></h1>
          <p className="mf-sub">
            AUREM watches your site <b style={{ color: GOLD }}>24×7</b> and emails you the <b style={{ color: GOLD }}>second</b> it goes down.<br />
            <span style={{ fontSize: 18, color: '#999' }}>7-day free trial · 3 URLs · No credit card · Setup in 30 seconds</span>
          </p>

          {success ? (
            <div className="mf-card aurem-floating-card" data-testid="success-card" style={{ maxWidth: 560, margin: '0 auto', textAlign: 'left' }}>
              <div style={{ color: GREEN, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, letterSpacing: '0.15em', marginBottom: 8 }}>✓ YOU'RE IN</div>
              <div className="mf-card-title" style={{ fontSize: 22 }}>Monitoring active</div>
              <div className="mf-card-body" style={{ marginTop: 10 }}>
                We're now watching <b style={{ color: GOLD }}>{success.url}</b> every 15 minutes.<br />
                Check your email at <b>{success.email}</b> for your welcome message + dashboard link.
              </div>
              <div className="mf-trust">Trial ends {new Date(success.trial_ends_at).toLocaleDateString()}</div>
              <Link to="/platform/signup" style={{ display: 'inline-block', marginTop: 16, color: GOLD, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, letterSpacing: '0.1em' }}>CREATE YOUR DASHBOARD →</Link>
            </div>
          ) : (
            <div className="mf-form">
              <input className="mf-input" type="email" placeholder="your@email.com" value={email} onChange={e => setEmail(e.target.value)} data-testid="email-input" />
              <input className="mf-input" type="text" placeholder="https://yoursite.com" value={url} onChange={e => setUrl(e.target.value)} data-testid="url-input" />
              <button className="mf-cta" onClick={submit} disabled={loading} data-testid="submit-btn">
                {loading ? 'STARTING MONITOR…' : 'START MONITORING FREE'}
              </button>
              {error && <div style={{ color: RED, fontSize: 13 }} data-testid="error-msg">{error}</div>}
              <div className="mf-trust">⚡ Average setup: 30 seconds · First alert: within 15 min</div>
            </div>
          )}
        </section>

        {/* Benefits */}
        <section className="mf-benefits">
          <div className="mf-grid3">
            <div className="mf-card aurem-floating-card">
              <div className="mf-card-icon">⚡</div>
              <div className="mf-card-title">INSTANT ALERTS</div>
              <div className="mf-card-body">Email the moment your site returns 500, timeouts, or goes fully offline. Recovery notification when it's back.</div>
            </div>
            <div className="mf-card aurem-floating-card delay-1">
              <div className="mf-card-icon">🔄</div>
              <div className="mf-card-title">15-MIN HEARTBEAT</div>
              <div className="mf-card-body">We ping your URL every 15 minutes (free tier). Paid tiers scale to 1-minute checks for mission-critical endpoints.</div>
            </div>
            <div className="mf-card aurem-floating-card delay-2">
              <div className="mf-card-icon">📊</div>
              <div className="mf-card-title">LIVE DASHBOARD</div>
              <div className="mf-card-body">Real-time uptime %, latency graph, incident history. Know exactly when + why your site went down.</div>
            </div>
          </div>
        </section>

        {/* Comparison */}
        <section className="mf-compare">
          <div className="mf-compare-title">How AUREM stacks up</div>
          <table className="mf-compare-table">
            <thead>
              <tr><th>Feature</th><th>AUREM Free</th><th>UptimeRobot Free</th><th>Pingdom Free</th></tr>
            </thead>
            <tbody>
              <tr><td>URLs</td><td className="good">3</td><td>50</td><td className="bad">1</td></tr>
              <tr><td>Check frequency</td><td className="good">15 min</td><td>5 min</td><td>1 min</td></tr>
              <tr><td>Email alerts</td><td className="good">✓</td><td className="good">✓</td><td className="good">✓</td></tr>
              <tr><td>AI root-cause analysis</td><td className="good">✓ (paid)</td><td className="bad">✗</td><td className="bad">✗</td></tr>
              <tr><td>WhatsApp alerts</td><td className="good">✓ (paid)</td><td className="bad">✗</td><td className="bad">✗</td></tr>
              <tr><td>Integrated SEO + CRM</td><td className="good">✓</td><td className="bad">✗</td><td className="bad">✗</td></tr>
              <tr><td>Upgrade price (unlimited)</td><td className="good">$249/mo</td><td>$449/mo</td><td>$699/mo</td></tr>
            </tbody>
          </table>
        </section>

        <footer className="mf-footer">
          © 2026 POLARIS BUILT INC · AUREM LIVE · TORONTO, CANADA
          <div style={{ marginTop: 8 }}>
            <Link to="/legal/privacy" style={{ color: '#666', marginRight: 16 }}>PRIVACY</Link>
            <Link to="/legal/terms" style={{ color: '#666' }}>TERMS</Link>
          </div>
        </footer>
      </div>
    </>
  );
}
