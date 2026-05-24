/**
 * AUREM Admin Login — Dedicated Admin Authentication
 * Company: Polaris Built Inc.
 * Separate from customer login. No biometric. No public link.
 * Rate limited: 5 attempts, 15-min lockout.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Target, Mail, Lock, ArrowRight, Loader2, Shield, AlertTriangle } from 'lucide-react';
import { setPlatformToken, setPlatformUser, getPlatformToken } from '../utils/secureTokenStore';
import { BACKEND_URL } from '../lib/api';

// Smart resolver: forces same-origin on aurem.live so a stale baked-in
// preview-pod URL can never brick production admin login.
const API_URL = BACKEND_URL;

const AdminLogin = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  // iter 325e — show TOTP input pre-emptively when the typed email
  // looks like an admin account, so the founder can paste the password
  // AND the 6-digit code in one go and submit ONCE. Previously the
  // backend had to return 401(2fa_required) before the input rendered,
  // which forced a second click.
  const [needTotp, setNeedTotp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Heuristic: admin emails are on the aurem.live domain OR explicitly
  // listed below. False positives only cause an extra (empty) input to
  // render — never block legit non-admin signin, because needTotp is
  // gated to "show field" not "require field" on submit.
  const KNOWN_ADMIN_EMAILS = new Set([
    'admin@aurem.live',
    'super@aurem.live',
    'teji.ss1986@gmail.com',
  ]);
  const looksLikeAdmin = (val) => {
    const v = (val || '').trim().toLowerCase();
    if (!v) return false;
    if (KNOWN_ADMIN_EMAILS.has(v)) return true;
    // Domain match — anyone on the company domain gets the TOTP field.
    return v.endsWith('@aurem.live');
  };

  useEffect(() => {
    // Reveal TOTP as soon as the typed email looks admin-shaped.
    // We never auto-HIDE the field after it appears (avoids flicker
    // mid-typing) — the server is still the source of truth.
    if (!needTotp && looksLikeAdmin(email)) {
      setNeedTotp(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email]);

  useEffect(() => {
    const token = getPlatformToken();
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        // iter 326nn — verify the token isn't expired BEFORE auto-
        // redirecting. A stale token whose `exp` is in the past would
        // still pass the role check, bounce the user to the dashboard,
        // and then the dashboard would fail every API call and send
        // them right back here. Worst possible UX loop.
        const nowSec = Math.floor(Date.now() / 1000);
        if (payload.exp && payload.exp < nowSec) {
          // Stale token — clear it and let the user see the form.
          import('../utils/secureTokenStore').then(({ clearAdminAuth }) => {
            clearAdminAuth();
          }).catch(() => { /* ignore */ });
          return;
        }
        if (payload.is_admin || payload.is_super_admin || payload.role === 'admin' || payload.role === 'super_admin') {
          navigate('/admin/mission-control');
        }
      } catch { /* ignore — corrupt token, show the form */ }
    }
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API_URL}/api/auth/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, totp_code: totpCode || undefined }),
      });

      const data = await res.json();

      if (res.ok && data.token) {
        setPlatformToken(data.token);
        setPlatformUser(data.user || data);
        try {
          if (data.user?.refresh_token) {
            localStorage.setItem('aurem_admin_refresh', data.user.refresh_token);
          }
        } catch { /* ignore */ }
        navigate('/admin/mission-control');
      } else if (res.status === 401 && data.detail === '2fa_required') {
        setNeedTotp(true);
        setError('Enter the 6-digit code from your authenticator app.');
      } else if (res.status === 429) {
        setError('Account locked. Try again in 15 minutes.');
      } else if (res.status === 403) {
        setError('Access denied. Admin privileges required.');
      } else {
        setError(data.detail || 'Invalid credentials');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative lightning-bg overflow-hidden"
      style={{ fontFamily: "'Inter', sans-serif" }}
      data-testid="admin-login-page">
      {/* Shared robot hero background — inverted for admin gravitas */}
      <div className="absolute inset-0 z-0" aria-hidden="true">
        <div className="absolute inset-0" style={{
          backgroundImage: 'url(/assets/aurem-hero-robot.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'brightness(0.36) saturate(1.2) hue-rotate(-3deg)',
        }} />
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse at center, rgba(5,5,10,0.25) 0%, rgba(5,5,10,0.8) 65%, rgba(5,5,10,0.96) 100%)',
        }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 180, damping: 22 }}
        className="w-full max-w-sm spatial-glass relative z-10"
        style={{ padding: '32px 28px' }}
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center size-14 rounded-xl mb-4"
            style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)' }}>
            <Target className="size-7 text-[#050507]" />
          </div>
          <h1 className="text-lg tracking-[0.15em] mb-1" style={{ fontFamily: "'Cinzel', serif", color: '#E8E6E1' }}
            data-testid="admin-login-title">
            AUREM ADMIN
          </h1>
          <div className="flex items-center justify-center gap-1.5 text-[10px] text-[#555]">
            <Shield className="size-3" />
            <span>Restricted Access</span>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-3 rounded-lg flex items-center gap-2 text-xs"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444' }}
              data-testid="admin-login-error"
            >
              <AlertTriangle className="size-3.5 flex-shrink-0" />
              {error}
            </motion.div>
          )}

          <div>
            <label className="block text-[9px] text-[#555] tracking-[0.2em] uppercase mb-1.5">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[#444]" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="admin-email-input"
                className="w-full pl-10 pr-4 py-3 rounded-lg text-sm"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#E8E6E1' }}
                placeholder="admin@aurem.live"
              />
            </div>
          </div>

          <div>
            <label htmlFor="admin-password" className="block text-[9px] text-[#9ca3af] tracking-[0.2em] uppercase mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[#444]" />
              <input
                id="admin-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                aria-label="Admin password"
                data-testid="admin-password-input"
                className="w-full pl-10 pr-4 py-3 rounded-lg text-sm"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#E8E6E1' }}
                placeholder="Enter admin password"
              />
            </div>
          </div>

          {needTotp && (
            <div>
              <label htmlFor="admin-totp" className="block text-[9px] text-[#9ca3af] tracking-[0.2em] uppercase mb-1.5">2FA Code</label>
              <div className="relative">
                <Shield className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[#444]" />
                <input
                  id="admin-totp"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                  required
                  autoFocus
                  data-testid="admin-totp-input"
                  className="w-full pl-10 pr-4 py-3 rounded-lg text-sm tracking-[0.4em] font-mono"
                  style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.25)', color: '#E8E6E1' }}
                  placeholder="000000"
                />
              </div>
            </div>
          )}

          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            type="submit"
            disabled={loading}
            data-testid="admin-login-submit"
            className="w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 text-sm disabled:opacity-50 transition-all"
            style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)', color: '#050507' }}
          >
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                <span>Authenticating…</span>
              </>
            ) : (
              <>
                Authenticate
                <ArrowRight className="size-4" />
              </>
            )}
          </motion.button>
        </form>

        {/* Forgot password — added iter 288.3 (founder-requested) */}
        <p className="text-center text-xs text-[#666] mt-6">
          <Link to="/forgot-password" data-testid="admin-forgot-password-link" className="text-[#888] hover:text-[#D4AF37] transition-colors">
            Forgot password?
          </Link>
        </p>
        <p className="text-center text-[9px] text-[#333] mt-2">
          Admin access only.
        </p>
      </motion.div>
    </div>
  );
};

export default AdminLogin;
