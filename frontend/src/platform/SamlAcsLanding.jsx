/**
 * AUREM SAML SSO callback receiver.
 *
 * The backend /api/saml/{org_id}/acs endpoint validates the IdP's
 * SAMLResponse, mints an AUREM JWT, then 303-redirects the browser
 * here with the token in the URL hash (`#t=...`). This page:
 *   1. Plucks the token from the hash
 *   2. Writes it to the admin token slot
 *   3. Strips the hash from the URL bar
 *   4. Navigates to /admin/mission-control
 *
 * Hash > query so the JWT NEVER lands in nginx / Cloudflare access logs.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { setPlatformToken } from '../utils/secureTokenStore';

export default function SamlAcsLanding() {
  const navigate = useNavigate();
  const [status, setStatus] = useState('verifying');

  useEffect(() => {
    try {
      const hash = (window.location.hash || '').replace(/^#/, '');
      const params = new URLSearchParams(hash);
      const token = params.get('t');
      if (!token) {
        setStatus('no_token');
        return;
      }
      setPlatformToken(token);
      // Wipe the hash so the token doesn't sit in the browser URL bar.
      window.history.replaceState({}, '',
        window.location.pathname + window.location.search);
      setStatus('ok');
      // Tiny delay so the React state machine commits before nav.
      setTimeout(() => navigate('/admin/mission-control', { replace: true }), 250);
    } catch (e) {
      setStatus('error');
    }
  }, [navigate]);

  return (
    <div
      data-testid="saml-acs-landing"
      style={{
        minHeight: '100vh',
        background: '#0a0a0a',
        color: '#f6f5f1',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <div style={{
          fontFamily: "'Cinzel', serif",
          fontSize: 28,
          letterSpacing: '0.05em',
          color: 'var(--dash-orange, #FF6B00)',
          marginBottom: 14,
      }}>
        AUREM
      </div>
      <div style={{ fontSize: 11, letterSpacing: '0.25em', textTransform: 'uppercase', color: '#777' }}>
        {status === 'verifying' && 'Verifying single sign-on…'}
        {status === 'ok'        && 'Signed in. Redirecting…'}
        {status === 'no_token'  && 'No token received. Please try again.'}
        {status === 'error'     && 'Something went wrong. Please try again.'}
      </div>
    </div>
  );
}
