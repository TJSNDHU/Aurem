/**
 * AUREM Onboarding — Pixel Install Gate (P0)
 * Route: /onboarding/pixel?tenant_id=XXX
 * Mandatory step. Dashboard does not unlock until pixel is verified.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Copy, Check, Loader2, ShieldAlert, ShieldCheck,
  Download, Globe, Zap, ArrowRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const GOLD = '#C9A227';

export default function OnboardingPixelStep() {
  const [params] = useSearchParams();
  const tenantId = params.get('tenant_id') || params.get('wid') || '';
  const [snippet, setSnippet] = useState('');
  const [wpUrl, setWpUrl] = useState('');
  const [domain, setDomain] = useState('');
  const [status, setStatus] = useState({ pixel_installed: false, last_seen_at: null });
  const [verifying, setVerifying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!tenantId) return;
    fetch(`${API}/api/onboarding/tenant/${tenantId}/pixel/snippet`)
      .then(r => r.json())
      .then(d => { setSnippet(d.snippet || ''); setWpUrl(d.wp_plugin_url || ''); })
      .catch(() => {});
    fetch(`${API}/api/onboarding/tenant/${tenantId}/pixel/status`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) { setStatus(d); if (d.domain) setDomain(d.domain); } })
      .catch(() => {});
  }, [tenantId]);

  const copy = () => {
    if (!snippet) return;
    navigator.clipboard?.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const verify = async () => {
    if (!domain.trim() || verifying) return;
    setVerifying(true); setErr('');
    try {
      const r = await fetch(`${API}/api/onboarding/tenant/${tenantId}/pixel/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: domain.trim() }),
      });
      const d = await r.json();
      if (d.detected) {
        setStatus({ pixel_installed: true, last_seen_at: new Date().toISOString() });
      } else {
        setErr(d.hint || d.fetch_error || 'Pixel not detected. Confirm snippet is in <head> and site is redeployed.');
      }
    } catch (e) {
      setErr(String(e));
    }
    setVerifying(false);
  };

  if (!tenantId) {
    return (
      <div data-testid="pixel-step-no-tenant" style={{ minHeight: '100vh', background: '#0A0A0A', color: '#fff', padding: 40 }}>
        <h1>Missing tenant_id</h1>
        <p>This page requires <code>?tenant_id=XXX</code> in the URL.</p>
      </div>
    );
  }

  return (
    <div data-testid="pixel-onboarding-page"
      style={{ minHeight: '100vh', background: '#0A0A0A', color: '#EDE8DF',
               padding: '48px 24px', fontFamily: 'system-ui' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <div style={{ fontSize: 11, color: GOLD, letterSpacing: '0.25em', fontWeight: 700 }}>
          STEP 2 OF 4 — REQUIRED
        </div>
        <h1 style={{ fontSize: 36, fontWeight: 700, margin: '8px 0 6px',
                     fontFamily: 'serif', letterSpacing: '-0.01em' }}>
          Install the AUREM pixel
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, marginBottom: 32 }}>
          One snippet. 30 seconds. After install, AUREM auto-fixes SEO, speed, schema and security on your site — forever.
        </p>

        {/* Status banner */}
        {status.pixel_installed ? (
          <div data-testid="pixel-verified-banner"
            style={{ padding: 16, borderRadius: 10, background: 'rgba(74,222,128,0.08)',
                     border: '1px solid rgba(74,222,128,0.4)', marginBottom: 24,
                     display: 'flex', alignItems: 'center', gap: 12 }}>
            <ShieldCheck style={{ width: 20, height: 20, color: '#4ADE80' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: '#4ADE80' }}>Pixel detected — dashboard unlocked</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>Last seen {status.last_seen_at ? new Date(status.last_seen_at).toLocaleString() : 'just now'}</div>
            </div>
            <Link to="/dashboard" data-testid="goto-dashboard"
              style={{ padding: '10px 18px', borderRadius: 8, background: GOLD, color: '#0A0A0A',
                       fontWeight: 700, fontSize: 13, textDecoration: 'none',
                       display: 'flex', alignItems: 'center', gap: 6 }}>
              Open Dashboard <ArrowRight style={{ width: 14, height: 14 }} />
            </Link>
          </div>
        ) : (
          <div data-testid="pixel-pending-banner"
            style={{ padding: 16, borderRadius: 10, background: 'rgba(245,158,11,0.08)',
                     border: '1px solid rgba(245,158,11,0.4)', marginBottom: 24,
                     display: 'flex', alignItems: 'center', gap: 12 }}>
            <ShieldAlert style={{ width: 20, height: 20, color: '#F59E0B' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#F59E0B' }}>Pixel not detected — fixes paused</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>Install + verify to unlock the dashboard.</div>
            </div>
          </div>
        )}

        {/* Snippet block */}
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(201,162,39,0.2)',
                      borderRadius: 12, padding: 24, marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: GOLD, letterSpacing: '0.2em', fontWeight: 700, marginBottom: 12 }}>
            1. PASTE INTO YOUR SITE'S &lt;head&gt; TAG
          </div>
          <pre data-testid="pixel-snippet-code"
            style={{ background: '#000', padding: 16, borderRadius: 8, overflow: 'auto',
                     fontSize: 12, color: '#EDE8DF', margin: 0,
                     border: '1px solid rgba(255,255,255,0.08)' }}>
{snippet || 'Loading snippet…'}
          </pre>
          <button onClick={copy} disabled={!snippet}
            data-testid="copy-snippet-btn"
            style={{ marginTop: 12, padding: '10px 18px', borderRadius: 8,
                     background: copied ? '#4ADE80' : 'rgba(201,162,39,0.2)',
                     color: copied ? '#0A0A0A' : GOLD, fontWeight: 600, fontSize: 12,
                     border: '1px solid rgba(201,162,39,0.35)', cursor: 'pointer',
                     display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {copied ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
            {copied ? 'Copied' : 'Copy snippet'}
          </button>
        </div>

        {/* WP plugin shortcut */}
        {wpUrl && (
          <div data-testid="wp-plugin-block"
            style={{ background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.25)',
                     borderRadius: 12, padding: 18, marginBottom: 16,
                     display: 'flex', alignItems: 'center', gap: 14 }}>
            <Zap style={{ width: 22, height: 22, color: '#60A5FA' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>WordPress site? Skip the snippet.</div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>Upload our plugin → Activate → Done. Auto-registers itself.</div>
            </div>
            <a href={wpUrl} download data-testid="wp-plugin-download"
              style={{ padding: '10px 16px', borderRadius: 8, background: 'rgba(59,130,246,0.2)',
                       border: '1px solid rgba(59,130,246,0.4)', color: '#60A5FA',
                       fontSize: 12, fontWeight: 600, textDecoration: 'none',
                       display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <Download style={{ width: 14, height: 14 }} /> Download plugin
            </a>
          </div>
        )}

        {/* Verify */}
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(201,162,39,0.2)',
                      borderRadius: 12, padding: 24 }}>
          <div style={{ fontSize: 11, color: GOLD, letterSpacing: '0.2em', fontWeight: 700, marginBottom: 12 }}>
            2. VERIFY INSTALL
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 240, position: 'relative' }}>
              <Globe style={{ width: 14, height: 14, position: 'absolute',
                              left: 12, top: '50%', transform: 'translateY(-50%)', color: GOLD }} />
              <input type="url" value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="https://yourdomain.com"
                data-testid="verify-domain-input"
                style={{ width: '100%', padding: '12px 14px 12px 36px', fontSize: 13,
                         background: '#000', border: '1px solid rgba(255,255,255,0.1)',
                         borderRadius: 8, color: '#EDE8DF', outline: 'none' }} />
            </div>
            <button onClick={verify} disabled={verifying || !domain.trim()}
              data-testid="verify-pixel-btn"
              style={{ padding: '12px 22px', borderRadius: 8, background: GOLD,
                       color: '#0A0A0A', fontWeight: 700, fontSize: 13, border: 'none',
                       cursor: (verifying || !domain.trim()) ? 'not-allowed' : 'pointer',
                       opacity: (verifying || !domain.trim()) ? 0.6 : 1,
                       display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {verifying && <Loader2 className="animate-spin" style={{ width: 14, height: 14 }} />}
              {verifying ? 'Verifying…' : 'Verify pixel'}
            </button>
          </div>
          {err && (
            <div data-testid="verify-error"
              style={{ marginTop: 10, fontSize: 12, color: '#F87171' }}>{err}</div>
          )}
        </div>

        <div style={{ marginTop: 24, fontSize: 11, opacity: 0.5, textAlign: 'center' }}>
          Need help? Reply YES to the SMS we sent — ORA will install it for you.
        </div>
      </div>
    </div>
  );
}
