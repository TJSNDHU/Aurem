/**
 * Free SEO Audit → Paid Auto-Fix funnel
 * ======================================
 * Public revenue page: aurem.live/free-seo-audit
 *
 * Single-page flow:
 *   1. URL input → scan via /api/public/seo-funnel/scan
 *   2. Show overall score + 3–5 real issues (no fluff)
 *   3. CTA → Email capture → /api/public/seo-funnel/checkout → Stripe
 *
 * Stays deliberately minimal: one column, one button, one outcome.
 * Conversion math: every extra field reduces conversion ~10%. So we
 * collect only URL upfront and email at the checkout moment.
 */
import React, { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { Loader2, CheckCircle, AlertCircle, ShieldAlert, ArrowRight, Sparkles } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const SEV_STYLE = {
  high:   { color: '#ef4444', bg: 'rgba(239,68,68,0.10)',  label: 'Critical' },
  medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', label: 'High' },
  low:    { color: '#8B7355', bg: 'rgba(139,115,85,0.10)', label: 'Medium' },
};

export default function FreeSeoAudit() {
  // Stage: 'idle' | 'scanning' | 'results' | 'checkout' | 'error'
  const [stage, setStage] = useState('idle');
  const [url, setUrl] = useState('');
  const [email, setEmail] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const runScan = async (e) => {
    e?.preventDefault();
    if (!url.trim()) return;
    setStage('scanning');
    setError('');
    try {
      const r = await fetch(`${API}/api/public/seo-funnel/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || `Scan failed (${r.status})`);
      setResult(data);
      setStage('results');
    } catch (err) {
      setError(err.message || 'Scan failed');
      setStage('error');
    }
  };

  const startCheckout = async (e) => {
    e?.preventDefault();
    if (!email.trim() || !result?.scan_id) return;
    setStage('checkout');
    setError('');
    try {
      const r = await fetch(`${API}/api/public/seo-funnel/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          scan_id: result.scan_id,
          business_name: result.url,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || `Checkout failed (${r.status})`);
      // Stripe expects a full redirect.
      window.location.href = data.checkout_url;
    } catch (err) {
      setError(err.message || 'Could not start checkout');
      setStage('results');
    }
  };

  return (
    <div data-testid="free-seo-audit-page" style={pageWrap}>
      <Helmet>
        <title>Free SEO Audit · AUREM</title>
        <meta name="description" content="Get a free AUREM SEO audit of your website in under 30 seconds. Find the real issues costing you traffic and conversions, then fix them automatically for $49/month." />
        <link rel="canonical" href="https://aurem.live/free-seo-audit" />
      </Helmet>

      <div style={inner}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 56 }}>
          <div style={badge} data-testid="page-badge">
            <Sparkles size={12} style={{ color: '#D4AF37' }} />
            <span>Free · No signup · 30 seconds</span>
          </div>
          <h1 style={h1} data-testid="page-headline">
            Find what's silently killing<br />your website's traffic.
          </h1>
          <p style={subhead} data-testid="page-subhead">
            AUREM ORA runs a real 8-point audit on your site, no fluff, no
            generic checklist. You see the actual issues. Then we fix them
            automatically.
          </p>
        </div>

        {/* Stage: idle / scanning */}
        {(stage === 'idle' || stage === 'scanning' || stage === 'error') && (
          <form onSubmit={runScan} style={card} data-testid="scan-form">
            <label style={label} htmlFor="seo-funnel-url">Your website URL</label>
            <div style={inputRow}>
              <input
                id="seo-funnel-url"
                data-testid="scan-url-input"
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="yourbusiness.com"
                disabled={stage === 'scanning'}
                autoFocus
                style={input}
              />
              <button
                type="submit"
                data-testid="scan-submit-btn"
                disabled={stage === 'scanning' || !url.trim()}
                style={btnPrimary}
              >
                {stage === 'scanning' ? (
                  <><Loader2 size={14} className="animate-spin" /> Scanning…</>
                ) : (
                  <>Run free audit <ArrowRight size={14} /></>
                )}
              </button>
            </div>
            {stage === 'error' && error && (
              <div style={errBox} data-testid="scan-error">
                <AlertCircle size={14} /> {error}
              </div>
            )}
            <p style={muted}>
              We crawl your site once and email you a copy of the report. No
              account required, no card on file.
            </p>
          </form>
        )}

        {/* Stage: results */}
        {stage === 'results' && result && (
          <div data-testid="scan-results">
            {/* Score banner */}
            <div style={{ ...card, padding: 32, textAlign: 'center', marginBottom: 24 }}>
              <p style={{ ...muted, marginBottom: 8 }}>Audit complete for</p>
              <p style={{ fontSize: 14, color: '#1A1A2E', marginBottom: 24, fontFamily: 'monospace' }} data-testid="result-url">
                {result.url}
              </p>
              <div style={scoreRing(result.overall_score)} data-testid="result-score">
                <span style={{ fontSize: 44, fontWeight: 600, color: '#1A1A2E' }}>
                  {result.overall_score}
                </span>
                <span style={{ fontSize: 14, color: '#5a5a72' }}>/ 100</span>
              </div>
              <p style={{ ...subhead, fontSize: 14, marginTop: 16 }} data-testid="result-summary">
                {result.summary}
              </p>
            </div>

            {/* Issues */}
            <div style={card} data-testid="result-issues">
              <h2 style={{ fontSize: 18, fontWeight: 500, color: '#1A1A2E', margin: '0 0 4px' }}>
                What we found
              </h2>
              <p style={{ ...muted, marginBottom: 24 }}>
                {result.issues.length} prioritised issue{result.issues.length === 1 ? '' : 's'},
                ordered by impact.
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {result.issues.map((iss, i) => {
                  const sev = SEV_STYLE[iss.severity] || SEV_STYLE.medium;
                  return (
                    <li
                      key={`${iss.title}-${i}`}
                      data-testid={`issue-${i}`}
                      style={issueRow}
                    >
                      <div style={{ ...sevPill, color: sev.color, background: sev.bg }}>
                        <ShieldAlert size={12} />
                        <span>{sev.label}</span>
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontSize: 14, fontWeight: 500, color: '#1A1A2E', margin: '0 0 4px' }}>
                          {iss.title}
                        </p>
                        {iss.detail && (
                          <p style={{ fontSize: 12, color: '#5a5a72', margin: 0, lineHeight: 1.5 }}>
                            {iss.detail}
                          </p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* CTA */}
            <div style={{ ...card, padding: 32, marginTop: 24, background: 'linear-gradient(135deg, rgba(212,175,55,0.06), rgba(139,115,85,0.04))' }}>
              <h2 style={{ fontSize: 22, fontWeight: 500, color: '#1A1A2E', margin: '0 0 12px' }}>
                Fix all of this. Automatically.
              </h2>
              <p style={{ fontSize: 14, color: '#5a5a72', margin: '0 0 24px', lineHeight: 1.55 }}>
                AUREM ORA repairs each issue, monitors the site every hour, and
                writes the fixes back to your stack. Cancel anytime.
              </p>
              <form onSubmit={startCheckout} style={inputRow}>
                <input
                  type="email"
                  data-testid="checkout-email-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@yourbusiness.com"
                  required
                  disabled={stage === 'checkout'}
                  style={input}
                />
                <button
                  type="submit"
                  data-testid="checkout-cta-btn"
                  disabled={stage === 'checkout' || !email.trim()}
                  style={{ ...btnPrimary, padding: '12px 22px' }}
                >
                  {stage === 'checkout' ? (
                    <><Loader2 size={14} className="animate-spin" /> Redirecting…</>
                  ) : (
                    <>{result.plan?.cta || 'Fix These Issues Automatically'} <ArrowRight size={14} /></>
                  )}
                </button>
              </form>
              {error && (
                <div style={errBox} data-testid="checkout-error">
                  <AlertCircle size={14} /> {error}
                </div>
              )}
              <div style={{ display: 'flex', gap: 18, marginTop: 18, flexWrap: 'wrap' }} data-testid="trust-row">
                {['Cancel anytime', '14-day money back', 'No setup fees', 'Stripe checkout'].map((t) => (
                  <span key={t} style={trustChip}>
                    <CheckCircle size={11} style={{ color: '#22c55e' }} /> {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        <footer style={{ textAlign: 'center', marginTop: 56, paddingBottom: 32 }}>
          <p style={{ fontSize: 11, color: '#5a5a72' }}>
            © {new Date().getFullYear()} AUREM ·{' '}
            <a href="/terms" style={ftLink}>Terms</a> ·{' '}
            <a href="/privacy" style={ftLink}>Privacy</a> ·{' '}
            <a href="/refund" style={ftLink}>Refund Policy</a>
          </p>
        </footer>
      </div>
    </div>
  );
}

/* ----------------------------- styles ----------------------------- */
const pageWrap = {
  minHeight: '100vh',
  background: 'linear-gradient(180deg, #FAF8F1 0%, #F5F0E5 100%)',
  padding: '64px 20px',
  fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
};
const inner = { maxWidth: 720, margin: '0 auto' };
const badge = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '6px 12px', borderRadius: 999,
  background: 'rgba(212,175,55,0.10)',
  border: '1px solid rgba(212,175,55,0.25)',
  color: '#8B7355', fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase',
  marginBottom: 20,
};
const h1 = {
  fontSize: 'clamp(32px, 5vw, 48px)',
  fontWeight: 500, color: '#1A1A2E', margin: '0 0 16px',
  letterSpacing: '-0.02em', lineHeight: 1.15,
};
const subhead = {
  fontSize: 16, color: '#5a5a72', margin: 0, lineHeight: 1.55,
  maxWidth: 540, marginInline: 'auto',
};
const card = {
  background: 'rgba(255,255,255,0.85)',
  backdropFilter: 'blur(12px)',
  border: '1px solid rgba(212,175,55,0.18)',
  borderRadius: 16, padding: 28,
};
const label = {
  display: 'block', fontSize: 11, color: '#8B7355',
  letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 10,
};
const inputRow = { display: 'flex', gap: 10, flexWrap: 'wrap' };
const input = {
  flex: '1 1 240px', minWidth: 0, padding: '12px 14px',
  borderRadius: 10, border: '1px solid rgba(212,175,55,0.30)',
  background: '#fff', fontSize: 14, color: '#1A1A2E', outline: 'none',
};
const btnPrimary = {
  display: 'inline-flex', alignItems: 'center', gap: 8,
  padding: '12px 18px', borderRadius: 10, border: 'none',
  background: 'linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)',
  color: '#0a0a0a', fontSize: 13, fontWeight: 600,
  cursor: 'pointer', whiteSpace: 'nowrap',
};
const muted = { fontSize: 12, color: '#5a5a72', marginTop: 14, marginBottom: 0 };
const errBox = {
  display: 'flex', alignItems: 'center', gap: 8,
  marginTop: 14, padding: '10px 12px', borderRadius: 8,
  background: 'rgba(239,68,68,0.08)', color: '#b91c1c', fontSize: 12,
  border: '1px solid rgba(239,68,68,0.20)',
};
const scoreRing = (score) => ({
  display: 'inline-flex', alignItems: 'baseline', gap: 6,
  padding: '20px 36px', borderRadius: 999,
  background: 'rgba(212,175,55,0.06)',
  border: `2px solid ${score >= 70 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444'}`,
});
const issueRow = {
  display: 'flex', gap: 16, alignItems: 'flex-start',
  padding: '14px 0', borderBottom: '1px solid rgba(212,175,55,0.12)',
};
const sevPill = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '4px 8px', borderRadius: 6,
  fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
  textTransform: 'uppercase', whiteSpace: 'nowrap',
};
const trustChip = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  fontSize: 11, color: '#5a5a72',
};
const ftLink = { color: '#8B7355', textDecoration: 'none' };
