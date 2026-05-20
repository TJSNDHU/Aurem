import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { BACKEND_URL } from '../lib/api';

// Smart resolver: same-origin on aurem.live, env-var on preview. Prevents
// stale preview-pod URLs from breaking Google OAuth callback in production.
const API_URL = BACKEND_URL;

/**
 * GoogleAuthCallback - Processes the session_id from Emergent Google Auth.
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
 */
export default function GoogleAuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { hash } = location;
  const hasProcessed = useRef(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      setError('No session ID found. Please try logging in again.');
      return;
    }

    const sessionId = match[1];

    const exchangeSession = async () => {
      try {
        const res = await fetch(`${API_URL}/api/auth/google/callback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(data.detail || 'Authentication failed. Please try again.');
          return;
        }

        const data = await res.json();

        // ── STORE TOKEN under EVERY key downstream code may read ──
        // The codebase has ~5 different storage keys in different
        // components (legacy → modern). Writing once here covers ALL
        // consumers (CustomerPortal, AdminShell, AuremDashboard, ORA, etc.)
        // and fixes the "Authenticating with Google… infinite scroll" loop
        // + the blank `/my` page where CustomerPortal couldn't find the token.
        const writeAll = (key, val) => {
          try { localStorage.setItem(key, val); } catch {}
          try { sessionStorage.setItem(key, val); } catch {}
        };
        writeAll('platform_token', data.token);   // ← primary (CustomerPortal, AdminShell, AdminGuard)
        writeAll('aurem_admin_token', data.token); // ← admin panels (CustomerHealthPanel, OraDevConsole)
        writeAll('aurem_token', data.token);       // ← legacy
        writeAll('token', data.token);             // ← oldest fallback
        try {
          localStorage.setItem('platform_user', JSON.stringify(data.user));
          localStorage.setItem('aurem_user', JSON.stringify(data.user));
        } catch {}

        // iter 282h — single-hop: admin → /dashboard, customer → /my
        let target = '/my';
        try {
          const payload = JSON.parse(atob(data.token.split('.')[1]));
          if (payload.is_admin || payload.role === 'admin' || payload.role === 'super_admin') {
            target = '/admin/console';
          }
        } catch {}
        navigate(target, { replace: true, state: { user: data.user } });
      } catch (err) {
        setError('Network error. Please try again.');
      }
    };

    exchangeSession();
  }, [hash, navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--aurem-bg, #050505)' }}>
        <div className="text-center max-w-md px-6" data-testid="google-auth-error">
          <h1 className="text-xl font-bold mb-3 text-red-500">Authentication Error</h1>
          <p className="text-sm mb-4" style={{ color: 'var(--aurem-body-secondary, #888)' }}>{error}</p>
          <a href="/login" className="text-sm font-medium" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
            Return to Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--aurem-bg, #050505)' }}>
      <div className="text-center" data-testid="google-auth-loading">
        <Loader2 className="size-12 mx-auto mb-4 animate-spin" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
        <p className="text-sm" style={{ color: 'var(--aurem-body-secondary, #888)' }}>Authenticating with Google…</p>
      </div>
    </div>
  );
}
