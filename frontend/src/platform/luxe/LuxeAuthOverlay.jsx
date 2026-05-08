/**
 * LuxeAuthOverlay — gated welcome screen rendered on top of a blurred
 * customer dashboard until the user signs in or signs up.
 *
 * Modes:
 *  - 'login'        sign in with email/BIN + password (eye-toggle)
 *  - 'signup'       create new account
 *  - 'forgot'       request reset email (POST /api/auth/forgot-password)
 *  - 'reset'        set a new password via ?reset_token=… in the URL
 *                   (POST /api/auth/reset-password)
 */
import React, { useState, useEffect } from 'react';
import {
  Loader2, Mail, KeyRound, Eye, EyeOff, ArrowLeft, CheckCircle2,
} from 'lucide-react';
import { useLuxeAuth } from './LuxeAuthContext';
import { BACKEND_URL } from '../../lib/api';
import {
  GOLD_HI, TEXT_HI, TEXT_LO,
  fontDisplay, fontBody, fontMono,
  labelStyle, fieldStyle, buttonGold,
} from './tokens';

// ── Reusable password input with eye toggle ──────────────────────────
const PasswordField = ({
  value, onChange, testid, placeholder = '••••••••',
  autoComplete = 'current-password',
}) => {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input
        data-testid={testid}
        style={{ ...fieldStyle, paddingRight: 38 }}
        autoComplete={autoComplete}
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <button
        type="button"
        data-testid={`${testid}-toggle`}
        onClick={() => setShow((v) => !v)}
        aria-label={show ? 'Hide password' : 'Show password'}
        style={{
          position: 'absolute', right: 8, top: '50%',
          transform: 'translateY(-50%)',
          background: 'transparent', border: 'none',
          color: TEXT_LO, cursor: 'pointer',
          padding: 6, display: 'flex', alignItems: 'center',
        }}
      >
        {show ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  );
};

export const LuxeAuthOverlay = () => {
  const {
    login, signup, error: ctxError, loading: ctxLoading, rememberPreference,
  } = useLuxeAuth();

  // Detect ?reset_token=… on first render → switch to 'reset' mode automatically.
  const [mode, setMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      if (params.get('reset_token')) return 'reset';
    }
    return 'login';
  });

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [fullName, setFullName] = useState('');
  const [company, setCompany] = useState('');
  const [remember, setRemember] = useState(rememberPreference !== false);
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState(null);
  const [info, setInfo] = useState(null);

  // Reset token from URL (only used in 'reset' mode)
  const [resetToken] = useState(() => {
    if (typeof window === 'undefined') return null;
    return new URLSearchParams(window.location.search).get('reset_token');
  });

  // Clear local state when mode changes
  useEffect(() => {
    setLocalError(null);
    setInfo(null);
  }, [mode]);

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (submitting) return;
    setLocalError(null);
    setInfo(null);
    setSubmitting(true);

    try {
      if (mode === 'login') {
        const r = await login({ identifier: identifier.trim(), password, remember });
        if (!r.ok) setLocalError(r.error);
      } else if (mode === 'signup') {
        if (!identifier.includes('@')) {
          setLocalError('Please enter a valid email');
          return;
        }
        const r = await signup({
          email: identifier.trim(), password,
          full_name: fullName.trim() || identifier.trim().split('@')[0],
          company_name: company.trim() || 'My Company',
          remember,
        });
        if (!r.ok) setLocalError(r.error);
      } else if (mode === 'forgot') {
        if (!identifier.includes('@')) {
          setLocalError('Please enter a valid email');
          return;
        }
        const res = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: identifier.trim().toLowerCase() }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setLocalError(data.detail || 'Could not send reset email');
        } else {
          setInfo(
            data.message ||
              'If this email exists, you will receive reset instructions.'
          );
        }
      } else if (mode === 'reset') {
        if (!resetToken) {
          setLocalError('Reset link is missing or invalid');
          return;
        }
        if (password.length < 8) {
          setLocalError('Password must be at least 8 characters');
          return;
        }
        if (password !== confirmPwd) {
          setLocalError('Passwords do not match');
          return;
        }
        const res = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            token: resetToken,
            new_password: password,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          setLocalError(data.detail || 'Could not reset password');
        } else {
          setInfo('Password reset successful. You can sign in now.');
          // Strip the token from the URL so a refresh stays clean.
          if (typeof window !== 'undefined') {
            window.history.replaceState({}, '', window.location.pathname);
          }
          setPassword('');
          setConfirmPwd('');
          setTimeout(() => setMode('login'), 1500);
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const errMsg = localError || ctxError;

  // ─── Per-mode header copy
  const headerCopy = {
    login:  { tag: 'WELCOME BACK',    title: 'Customer Access',  sub: 'Sign in to continue to your AUREM dashboard.' },
    signup: { tag: 'JOIN AUREM',      title: 'Create Account',   sub: 'Start your 14-day trial — no card required.' },
    forgot: { tag: 'PASSWORD RESET',  title: 'Forgot password?', sub: "Enter your email — we'll send a reset link." },
    reset:  { tag: 'NEW PASSWORD',    title: 'Set new password', sub: 'Choose a strong password to secure your account.' },
  }[mode];

  const submitLabel = {
    login: 'Sign In',
    signup: 'Create Account',
    forgot: 'Send Reset Link',
    reset: 'Save New Password',
  }[mode];

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(8,10,14,0.55)',
      backdropFilter: 'blur(28px) saturate(140%)',
      WebkitBackdropFilter: 'blur(28px) saturate(140%)',
    }}>
      <form data-testid="luxe-auth-overlay" onSubmit={handleSubmit} style={{
        width: 380, maxWidth: 'calc(100vw - 32px)',
        padding: 28, borderRadius: 22,
        background:
          'radial-gradient(140% 80% at 30% 0%, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.03) 22%, transparent 55%),' +
          'linear-gradient(165deg, rgba(60,62,72,0.45) 0%, rgba(18,20,28,0.55) 60%, rgba(40,42,52,0.40) 100%)',
        border: '1px solid rgba(255,255,255,0.16)',
        boxShadow:
          '0 1px 0 rgba(255,255,255,0.20) inset,' +
          ' 0 -1px 0 rgba(0,0,0,0.40) inset,' +
          ' 0 28px 60px -18px rgba(0,0,0,0.7)',
        backdropFilter: 'blur(24px) saturate(160%)',
        WebkitBackdropFilter: 'blur(24px) saturate(160%)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 18 }}>
          <div style={{
            display: 'inline-block', padding: '4px 14px', borderRadius: 999,
            background: 'rgba(212,163,115,0.10)',
            border: '1px solid rgba(212,163,115,0.30)',
            fontFamily: fontMono, fontSize: 9, color: GOLD_HI,
            letterSpacing: '0.30em',
          }}>
            {headerCopy.tag}
          </div>
          <h1 style={{
            margin: '14px 0 4px', color: TEXT_HI, fontFamily: fontDisplay,
            fontSize: 'clamp(20px, 5vw, 26px)', fontWeight: 700, letterSpacing: '0.08em',
          }}>
            {headerCopy.title}
          </h1>
          <div style={{ color: TEXT_LO, fontFamily: fontBody, fontSize: 12 }}>
            {headerCopy.sub}
          </div>
        </div>

        {mode === 'signup' && (
          <>
            <label style={labelStyle}>Full name</label>
            <input data-testid="auth-fullname" style={fieldStyle}
              value={fullName} onChange={(e) => setFullName(e.target.value)}
              placeholder="Your name" />
            <div style={{ height: 12 }} />
            <label style={labelStyle}>Company</label>
            <input data-testid="auth-company" style={fieldStyle}
              value={company} onChange={(e) => setCompany(e.target.value)}
              placeholder="Acme Inc." />
            <div style={{ height: 12 }} />
          </>
        )}

        {(mode === 'login' || mode === 'signup' || mode === 'forgot') && (
          <>
            <label style={labelStyle}>
              {mode === 'login' ? 'Email or BIN' : 'Email'}
            </label>
            <input data-testid="auth-email" style={fieldStyle}
              autoComplete="email"
              value={identifier} onChange={(e) => setIdentifier(e.target.value)}
              placeholder={mode === 'login'
                ? 'you@company.com or AURE-FNDR-001'
                : 'you@company.com'} />
          </>
        )}

        {(mode === 'login' || mode === 'signup') && (
          <>
            <div style={{ height: 12 }} />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={labelStyle}>Password</label>
              {mode === 'login' && (
                <button
                  type="button"
                  data-testid="auth-forgot-link"
                  onClick={() => setMode('forgot')}
                  style={{
                    background: 'none', border: 'none', color: GOLD_HI,
                    cursor: 'pointer', fontFamily: fontMono, fontSize: 9,
                    letterSpacing: '0.18em', textTransform: 'uppercase',
                    padding: 0, marginBottom: 6,
                  }}
                >
                  Forgot?
                </button>
              )}
            </div>
            <PasswordField
              testid="auth-password"
              value={password}
              onChange={setPassword}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </>
        )}

        {/* "Remember me" — only relevant when actively signing in/up */}
        {(mode === 'login' || mode === 'signup') && (
          <label
            data-testid="auth-remember-label"
            htmlFor="auth-remember-checkbox"
            style={{
              marginTop: 12,
              display: 'inline-flex', alignItems: 'center', gap: 8,
              cursor: 'pointer', userSelect: 'none',
              fontFamily: fontMono, fontSize: 10, color: TEXT_LO,
              letterSpacing: '0.10em',
            }}
          >
            <input
              id="auth-remember-checkbox"
              data-testid="auth-remember"
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              style={{
                width: 14, height: 14, cursor: 'pointer',
                accentColor: GOLD_HI,
                margin: 0,
              }}
            />
            <span>Keep me signed in for 30 days</span>
          </label>
        )}

        {mode === 'reset' && (
          <>
            <label style={labelStyle}>New password</label>
            <PasswordField
              testid="auth-new-password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              placeholder="At least 8 chars, 1 upper, 1 lower, 1 number"
            />
            <div style={{ height: 12 }} />
            <label style={labelStyle}>Confirm new password</label>
            <PasswordField
              testid="auth-confirm-password"
              value={confirmPwd}
              onChange={setConfirmPwd}
              autoComplete="new-password"
              placeholder="Re-type new password"
            />
          </>
        )}

        {errMsg && (
          <div data-testid="auth-error" style={{
            marginTop: 12, padding: '8px 12px', borderRadius: 8,
            background: 'rgba(248,113,113,0.10)',
            border: '1px solid rgba(248,113,113,0.30)',
            color: '#fca5a5', fontFamily: fontMono, fontSize: 11,
          }}>
            {errMsg}
          </div>
        )}

        {info && (
          <div data-testid="auth-info" style={{
            marginTop: 12, padding: '10px 12px', borderRadius: 8,
            background: 'rgba(190,242,100,0.10)',
            border: '1px solid rgba(190,242,100,0.30)',
            color: '#bef264', fontFamily: fontMono, fontSize: 11,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <CheckCircle2 size={14} />
            <span>{info}</span>
          </div>
        )}

        <div style={{ marginTop: 18 }}>
          <button data-testid="auth-submit" type="submit"
            disabled={submitting || ctxLoading}
            style={{ ...buttonGold, width: '100%',
              opacity: (submitting || ctxLoading) ? 0.7 : 1,
              cursor: (submitting || ctxLoading) ? 'wait' : 'pointer',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
            {submitting && <Loader2 size={14} className="luxe-spin" />}
            {submitLabel}
          </button>
        </div>

        {/* Footer links — different per mode */}
        <div style={{
          marginTop: 16, textAlign: 'center',
          fontFamily: fontMono, fontSize: 10, color: TEXT_LO,
        }}>
          {mode === 'login' && (
            <>
              New to AUREM?{' '}
              <button type="button" data-testid="auth-switch"
                onClick={() => setMode('signup')}
                style={{
                  background: 'none', border: 'none', color: GOLD_HI, cursor: 'pointer',
                  fontFamily: fontMono, letterSpacing: '0.18em', textTransform: 'uppercase',
                  fontSize: 10, padding: 0,
                }}>Sign up</button>
            </>
          )}
          {mode === 'signup' && (
            <>
              Already have an account?{' '}
              <button type="button" data-testid="auth-switch"
                onClick={() => setMode('login')}
                style={{
                  background: 'none', border: 'none', color: GOLD_HI, cursor: 'pointer',
                  fontFamily: fontMono, letterSpacing: '0.18em', textTransform: 'uppercase',
                  fontSize: 10, padding: 0,
                }}>Sign in</button>
            </>
          )}
          {(mode === 'forgot' || mode === 'reset') && (
            <button type="button" data-testid="auth-back-to-login"
              onClick={() => setMode('login')}
              style={{
                background: 'none', border: 'none', color: GOLD_HI, cursor: 'pointer',
                fontFamily: fontMono, letterSpacing: '0.18em', textTransform: 'uppercase',
                fontSize: 10, padding: 0,
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>
              <ArrowLeft size={11} /> Back to sign in
            </button>
          )}
        </div>
      </form>
      <style>{`
        .luxe-spin { animation: luxe-spin 1s linear infinite; }
        @keyframes luxe-spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default LuxeAuthOverlay;
