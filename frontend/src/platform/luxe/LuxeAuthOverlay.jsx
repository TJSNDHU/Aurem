/**
 * LuxeAuthOverlay — gated welcome screen rendered on top of a blurred
 * customer dashboard until the user signs in or signs up.
 */
import React, { useState } from 'react';
import { Loader2, User as UserIcon, Mail, KeyRound, Building2 } from 'lucide-react';
import { useLuxeAuth } from './LuxeAuthContext';
import {
  GOLD, GOLD_HI, INK, STROKE, TEXT_HI, TEXT_MD, TEXT_LO,
  fontDisplay, fontBody, fontMono,
  labelStyle, fieldStyle, buttonGold,
} from './tokens';

export const LuxeAuthOverlay = () => {
  const { login, signup, error: ctxError, loading: ctxLoading } = useLuxeAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [company, setCompany] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState(null);

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (submitting) return;
    setLocalError(null);
    setSubmitting(true);
    if (mode === 'login') {
      const r = await login({ identifier: identifier.trim(), password });
      if (!r.ok) setLocalError(r.error);
    } else {
      if (!identifier.includes('@')) {
        setLocalError('Please enter a valid email');
        setSubmitting(false);
        return;
      }
      const r = await signup({
        email: identifier.trim(), password,
        full_name: fullName.trim() || identifier.trim().split('@')[0],
        company_name: company.trim() || 'My Company',
      });
      if (!r.ok) setLocalError(r.error);
    }
    setSubmitting(false);
  };

  const errMsg = localError || ctxError;

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
            {mode === 'login' ? 'WELCOME BACK' : 'JOIN AUREM'}
          </div>
          <h1 style={{
            margin: '14px 0 4px', color: TEXT_HI, fontFamily: fontDisplay,
            fontSize: 26, fontWeight: 700, letterSpacing: '0.08em',
          }}>
            {mode === 'login' ? 'Customer Access' : 'Create Account'}
          </h1>
          <div style={{ color: TEXT_LO, fontFamily: fontBody, fontSize: 12 }}>
            {mode === 'login'
              ? 'Sign in to continue to your AUREM dashboard.'
              : 'Start your 14-day trial — no card required.'}
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

        <label style={labelStyle}>{mode === 'login' ? 'Email or BIN' : 'Email'}</label>
        <input data-testid="auth-email" style={fieldStyle}
          autoComplete="email"
          value={identifier} onChange={(e) => setIdentifier(e.target.value)}
          placeholder={mode === 'login' ? 'you@company.com or AURE-FNDR-001' : 'you@company.com'} />

        <div style={{ height: 12 }} />
        <label style={labelStyle}>Password</label>
        <input data-testid="auth-password" style={fieldStyle}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          type="password"
          value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••" />

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

        <div style={{ marginTop: 18 }}>
          <button data-testid="auth-submit" type="submit" disabled={submitting || ctxLoading}
            style={{ ...buttonGold, width: '100%',
              opacity: (submitting || ctxLoading) ? 0.7 : 1,
              cursor: (submitting || ctxLoading) ? 'wait' : 'pointer',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
            {submitting && <Loader2 size={14} className="luxe-spin" />}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </div>

        <div style={{ marginTop: 16, textAlign: 'center', fontFamily: fontMono, fontSize: 10, color: TEXT_LO }}>
          {mode === 'login' ? "New to AUREM?" : 'Already have an account?'}{' '}
          <button type="button" data-testid="auth-switch" onClick={() => {
            setMode(mode === 'login' ? 'signup' : 'login'); setLocalError(null);
          }} style={{
            background: 'none', border: 'none', color: GOLD_HI, cursor: 'pointer',
            fontFamily: fontMono, letterSpacing: '0.18em', textTransform: 'uppercase',
            fontSize: 10, padding: 0,
          }}>
            {mode === 'login' ? 'Sign up' : 'Sign in'}
          </button>
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
