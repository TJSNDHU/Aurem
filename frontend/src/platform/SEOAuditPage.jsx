/**
 * AUREM SEO Audit — Public Lead Magnet + $49 Unlock
 * Route: /audit
 *
 * Flow:
 *  1. URL + email capture → free preview with 3 top issues + grade
 *  2. CTA "Unlock Full Report — $49" → Stripe embedded checkout
 *  3. Post-payment: reload with session_id → fetch full 20-issue report
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL;
const GOLD = '#C9A84C';

export default function SEOAuditPage() {
  const [searchParams] = useSearchParams();
  const preloadScanId = searchParams.get('scan');
  const [phase, setPhase] = useState('form');   // form | scanning | preview | unlocking | full
  const [form, setForm] = useState({ url: '', email: '', business_name: '', consent: false });
  const [err, setErr] = useState('');
  const [report, setReport] = useState(null);
  const [scanId, setScanId] = useState(preloadScanId || null);

  // If arriving from email link with ?scan=xxx, auto-fetch
  useEffect(() => {
    if (preloadScanId) {
      setScanId(preloadScanId);
      fetch(`${API}/api/seo-audit/report/${preloadScanId}`)
        .then((r) => r.json())
        .then((d) => {
          setReport(d);
          setPhase(d.locked ? 'preview' : 'full');
        })
        .catch(() => setErr('Could not load report'));
    }
  }, [preloadScanId]);

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    if (!form.url || !form.email) return setErr('URL and email are required');
    setPhase('scanning');
    try {
      const r = await fetch(`${API}/api/seo-audit/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: form.url,
          email: form.email,
          business_name: form.business_name || null,
          consent_marketing: form.consent,
        }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || 'Scan failed');
      const d = await r.json();
      setScanId(d.scan_id);
      setReport(d);
      setPhase('preview');
    } catch (e2) {
      setErr(String(e2.message || e2));
      setPhase('form');
    }
  };

  const unlock = async () => {
    setPhase('unlocking');
    try {
      const r = await fetch(`${API}/api/seo-audit/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_id: scanId, return_url: window.location.origin }),
      });
      const d = await r.json();
      if (d.already_paid) { setPhase('full'); return; }
      if (!d.client_secret) throw new Error('Checkout not available');
      // Redirect to Stripe-hosted checkout via embedded launcher
      window.location.href = `https://checkout.stripe.com/c/pay/${d.session_id}`;
    } catch (e2) {
      setErr(String(e2.message || e2));
      setPhase('preview');
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0D0D0D', color: '#FDF9F9', fontFamily: "'Inter', sans-serif", padding: 'clamp(20px,4vw,60px)' }} data-testid="seo-audit-page">
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ display: 'inline-block', padding: '4px 14px', borderRadius: 20, background: `${GOLD}15`, border: `1px solid ${GOLD}44`, color: GOLD, fontSize: 11, letterSpacing: '0.2em', marginBottom: 16 }}>
            AUREM · SEO AUDIT
          </div>
          <h1 style={{ fontSize: 'clamp(28px,5vw,48px)', fontWeight: 300, letterSpacing: '-0.02em', margin: '12px 0' }}>
            Your site, diagnosed in 60 seconds.
          </h1>
          <p style={{ color: '#888', fontSize: 15, maxWidth: 520, margin: '0 auto' }}>
            We audit performance, SEO, accessibility, and local presence. Free preview in your inbox. Full 20-issue teardown for <span style={{ color: GOLD }}>$49 CAD</span>.
          </p>
        </div>

        {/* FORM */}
        {phase === 'form' && (
          <form onSubmit={submit} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 32 }}>
            <label style={{ fontSize: 12, color: '#888', letterSpacing: '0.15em' }}>WEBSITE URL</label>
            <input
              data-testid="seo-url-input"
              type="text" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="yoursite.com"
              style={{ width: '100%', padding: 14, marginTop: 6, marginBottom: 18, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#FDF9F9', fontSize: 15 }}
              required
            />
            <label style={{ fontSize: 12, color: '#888', letterSpacing: '0.15em' }}>EMAIL</label>
            <input
              data-testid="seo-email-input"
              type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="you@company.com"
              style={{ width: '100%', padding: 14, marginTop: 6, marginBottom: 18, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#FDF9F9', fontSize: 15 }}
              required
            />
            <label style={{ fontSize: 12, color: '#888', letterSpacing: '0.15em' }}>BUSINESS NAME (optional · unlocks local SEO)</label>
            <input
              data-testid="seo-name-input"
              type="text" value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })}
              placeholder="Your Clinic / Store"
              style={{ width: '100%', padding: 14, marginTop: 6, marginBottom: 18, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#FDF9F9', fontSize: 15 }}
            />
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 13, color: '#888', marginBottom: 24 }}>
              <input
                data-testid="seo-consent-input"
                type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })}
                style={{ marginTop: 4 }}
              />
              <span>Send me the monthly AUREM intelligence digest (CASL-compliant, unsubscribe anytime).</span>
            </label>
            {err && <div style={{ color: '#ff6b6b', marginBottom: 16, fontSize: 13 }}>{err}</div>}
            <button
              data-testid="seo-scan-btn"
              type="submit"
              style={{ width: '100%', padding: 18, background: GOLD, color: '#0D0D0D', border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 700, letterSpacing: '0.1em', cursor: 'pointer' }}
            >
              RUN FREE AUDIT →
            </button>
          </form>
        )}

        {phase === 'scanning' && (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <div style={{ fontSize: 14, color: GOLD, letterSpacing: '0.2em', marginBottom: 12 }}>SCANNING…</div>
            <div style={{ color: '#666', fontSize: 13 }}>Running PageSpeed · Firecrawl · Local SEO checks</div>
          </div>
        )}

        {(phase === 'preview' || phase === 'full') && report && (
          <div>
            {/* Score card */}
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 32, marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                <div>
                  <div style={{ fontSize: 11, color: '#666', letterSpacing: '0.2em' }}>OVERALL GRADE</div>
                  <div style={{ fontSize: 64, fontWeight: 300, color: GOLD, lineHeight: 1 }} data-testid="seo-grade">
                    {report.summary?.grade || '-'}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 13, color: '#888', marginBottom: 4 }}>{report.summary?.overall_score || 0}/100</div>
                  <div style={{ fontSize: 11, color: '#666' }}>{report.url}</div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {['performance', 'seo', 'accessibility', 'best_practices'].map((k) => (
                  <div key={k} style={{ padding: 12, background: 'rgba(0,0,0,0.3)', borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: '#666', letterSpacing: '0.15em', marginBottom: 4 }}>{k.replace('_', ' ').toUpperCase()}</div>
                    <div style={{ fontSize: 22, fontWeight: 500, color: report.summary?.[k] >= 85 ? '#4ADE80' : report.summary?.[k] >= 60 ? GOLD : '#ff6b6b' }}>
                      {report.summary?.[k] || 0}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Issues */}
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 32, marginBottom: 24 }}>
              <div style={{ fontSize: 12, color: '#888', letterSpacing: '0.2em', marginBottom: 16 }}>
                {phase === 'full' ? 'ALL ISSUES' : 'TOP 3 ISSUES · PREVIEW'}
              </div>
              {(phase === 'full'
                ? (report.full_report?.all_opportunities || [])
                : (report.top_issues || [])
              ).map((issue, i) => (
                <div key={i} style={{ padding: '14px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }} data-testid={`seo-issue-${i}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, marginBottom: 4 }}>{issue.title}</div>
                      <div style={{ fontSize: 12, color: '#888', lineHeight: 1.5 }}>{issue.description}</div>
                    </div>
                    <div style={{ fontSize: 11, color: GOLD, whiteSpace: 'nowrap' }}>
                      {issue.savings_ms ? `-${(issue.savings_ms / 1000).toFixed(1)}s` : '-'}
                    </div>
                  </div>
                </div>
              ))}

              {phase === 'preview' && (
                <div style={{ marginTop: 24, padding: 20, background: `${GOLD}10`, border: `1px solid ${GOLD}44`, borderRadius: 10, textAlign: 'center' }}>
                  <div style={{ fontSize: 13, color: '#888', marginBottom: 12 }}>
                    Your full report has <strong style={{ color: GOLD }}>{(report.full_report?.all_opportunities?.length || 20)} more issues</strong> with fix instructions.
                  </div>
                  <button
                    data-testid="seo-unlock-btn"
                    onClick={unlock}
                    style={{ padding: '14px 32px', background: GOLD, color: '#0D0D0D', border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 700, letterSpacing: '0.1em', cursor: 'pointer' }}
                  >
                    UNLOCK FULL REPORT, $49 CAD
                  </button>
                  <div style={{ fontSize: 11, color: '#666', marginTop: 10 }}>One-time payment · Instant access · Apple Pay & Google Pay</div>
                </div>
              )}
            </div>
          </div>
        )}

        <div style={{ textAlign: 'center', marginTop: 40, fontSize: 11, color: '#444', letterSpacing: '0.15em' }}>
          POWERED BY AUREM · POLARIS BUILT INC.
        </div>
      </div>
    </div>
  );
}
