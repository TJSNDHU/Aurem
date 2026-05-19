/**
 * FaceID Authentication Wrapper
 * "Aurem Pulse" Login + Signup Sequence — Scientific-Luxe Entry
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Lock, Eye, EyeOff, Scan, UserPlus, ArrowRight, Loader2 } from 'lucide-react';
import AuremPulseLogin from './AuremPulseLogin';
import FastBiometricLogin from './FastBiometricLogin';
import FastBiometricSetup from './FastBiometricSetup';
import '../theme/aurem-green.css';
import { getPlatformToken, setPlatformToken, setPlatformUser } from '../utils/secureTokenStore';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─── Bulletproof JSON parser ───────────────────────────────────
// When the backend or any layer in front of it (Cloudflare, ingress,
// browser extension) returns HTML instead of JSON, `await res.json()`
// throws "Unexpected token '<', '<!DOCTYPE'..." which then leaks into
// the user-visible error toast. This helper:
//   1. Reads the body as TEXT first
//   2. Tries JSON.parse — if it fails, returns a structured error
//      object with the HTTP status + a friendly message
//   3. NEVER throws — caller can always do `if (!data.token) ...`
async function safeAuthFetch(url, opts) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    return { _ok: false, _network_error: true,
             detail: 'Network error — please check your connection and try again.' };
  }
  const ct = (res.headers.get('content-type') || '').toLowerCase();
  let body;
  try { body = await res.text(); }
  catch { body = ''; }

  if (ct.includes('application/json') || (body.trim().startsWith('{') || body.trim().startsWith('['))) {
    try {
      const json = JSON.parse(body);
      return { _ok: res.ok, _status: res.status, ...json };
    } catch {
      // Fall through to non-JSON branch
    }
  }
  // Non-JSON response (most likely an HTML error page from CF / ingress)
  let friendly = '';
  if (res.status === 502 || res.status === 503 || res.status === 520) {
    friendly = 'Our servers are warming up. Please try again in a few seconds.';
  } else if (res.status === 429) {
    friendly = 'Too many attempts. Please wait a minute and try again.';
  } else if (res.status === 404) {
    friendly = 'The login service is temporarily unavailable.';
  } else if (res.status >= 500) {
    friendly = `Server error (${res.status}). Please try again.`;
  } else {
    friendly = `Login service returned an unexpected response (${res.status}).`;
  }
  return { _ok: false, _status: res.status, _non_json: true, detail: friendly };
}

const FaceIDAuthWrapper = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState('checking');
  const [faceIDAvailable, setFaceIDAvailable] = useState(false);
  const [animDone, setAnimDone] = useState(false);

  const goHome = (token) => {
    // iter 282h — single-hop: admin → /dashboard, customer → /my
    let target = '/my';
    try {
      const tok = token || (typeof getPlatformToken === 'function' ? getPlatformToken() : null);
      if (tok) {
        const payload = JSON.parse(atob(tok.split('.')[1]));
        if (payload.is_admin || payload.role === 'admin') target = '/dashboard';
      }
    } catch {}
    navigate(target);
  };

  useEffect(() => {
    // Check if already logged in
    const token = getPlatformToken();
    if (token) {
      goHome(token);
      return;
    }

    const urlMode = searchParams.get('mode');
    const trained = localStorage.getItem('faceid_trained') === 'true';
    const descriptor = localStorage.getItem('faceid_descriptor');
    if (trained && descriptor) {
      setFaceIDAvailable(true);
      setMode('faceid');
    } else {
      setMode(urlMode === 'register' ? 'register' : 'password');
    }
  }, [searchParams, navigate]);

  const handleFaceIDSuccess = async (email) => {
    // iter 324g — SECURITY: was sending a hardcoded admin password from
    // frontend JS. Browser-extractable; the literal leaked the old
    // master password via every bundled `main.js`. Removed.
    //
    // Face ID is a UX hint only — the actual auth must happen via a
    // proper Face-ID-validated server endpoint OR the user typing
    // their password. Until a backend `/api/auth/face_id` exists,
    // fall through to password mode.
    setMode('password');
  };

  const handlePasswordLogin = async (email, password) => {
    const data = await safeAuthFetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (data._ok && data.token) {
      setPlatformToken(data.token);
      setPlatformUser(data);
      localStorage.setItem('faceid_email', email);
      // Admins/super-admins skip biometric enrollment prompt — they bounce
      // between many admin URLs in new tabs during dogfooding and the prompt
      // blocks that flow. Regular users still get the optional upsell.
      const isAdmin = !!(data.is_admin || data.is_super_admin || data.role === 'admin' || data.role === 'super_admin');
      if (!isAdmin && !faceIDAvailable && window.PublicKeyCredential) {
        setMode('biometric_prompt');
        return;
      }
      goHome(data.token);
    } else {
      throw new Error(data.detail || `Login failed (status ${data._status || 'unknown'})`);
    }
  };

  const handleRegister = async (firstName, lastName, email, phone, password) => {
    const data = await safeAuthFetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ first_name: firstName, last_name: lastName, email, phone, password })
    });
    if (data._ok && data.token) {
      setPlatformToken(data.token);
      setPlatformUser(data);
      goHome(data.token);
    } else {
      throw new Error(data.detail || `Registration failed (status ${data._status || 'unknown'})`);
    }
  };

  const handleTrainingComplete = () => goHome();

  if (mode === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center relative">
        <div className="aurem-bg-container"><div className="geometric-overlay"></div></div>
        <div className="relative z-10 w-16 h-16 border-3 border-[#D4A373] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden lightning-bg" data-testid="auth-wrapper">
      {/* Background video — full-screen, muted, looped (iter 322) */}
      <video
        data-testid="login-bg-video"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        poster="/assets/aurem-hero-robot.jpg"
        className="absolute inset-0 w-full h-full object-cover"
        style={{ zIndex: 0, opacity: 0.6 }}
      >
        <source src="/videos/login-bg.mp4" type="video/mp4" />
      </video>
      {/* Vignette overlay so the form stays readable */}
      <div className="absolute inset-0" aria-hidden="true" style={{ zIndex: 0 }}>
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse at center, rgba(5,5,10,0.35) 0%, rgba(5,5,10,0.82) 70%, rgba(5,5,10,0.95) 100%)',
        }} />
      </div>
      <AuremPulseLogin onAnimationComplete={() => setAnimDone(true)} />

      <div className="w-full max-w-lg relative z-10">
        {/* Logo */}
        <div className="text-center mb-8" style={{ animation: 'auremLogoEntry 0.5s cubic-bezier(0.16,1,0.3,1) forwards' }}>
          <div className="relative inline-block">
            <div className="absolute inset-0 flex items-center justify-center" style={{ animation: 'auremPulseDelay 2s ease-out 0.6s both' }}>
              <div className="login-logo-glow" />
            </div>
            <div className="w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center relative"
              style={{ background: 'linear-gradient(135deg, #D4A373, #B38659)', boxShadow: '0 0 30px rgba(212,163,115,0.4)' }}>
              <span className="text-2xl font-black text-[#1A3026]">A</span>
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-[4px] text-[#E8E4DE]" style={{ fontFamily: "'Montserrat', sans-serif" }}>AUREM</h1>
          <p className="text-[11px] text-[#9A9590] mt-1 tracking-[3px]" style={{ fontFamily: "'Montserrat', sans-serif" }}>BUSINESS ORA PLATFORM</p>
        </div>

        {/* Auth Card — iter 322p defensive: keep opacity 1 by default so the
            form is always visible even if the `glassEntry` animation never
            fires (slow network / CSS not loaded yet / cached bundle race). */}
        <div style={{ animation: 'glassEntry 0.6s cubic-bezier(0.16,1,0.3,1) backwards', animationDelay: '0.5s' }}>
          {mode === 'training' && (
            <div className="aurem-glass-card overflow-hidden">
              <FastBiometricSetup email={localStorage.getItem('faceid_email') || 'user@aurem.ai'} onComplete={handleTrainingComplete} onSkip={handleTrainingComplete} />
            </div>
          )}

          {mode === 'faceid' && (
            <div className="aurem-glass-card overflow-hidden">
              <FastBiometricLogin onSuccess={handleFaceIDSuccess} onFallbackToPassword={() => setMode('password')} />
            </div>
          )}

          {mode === 'password' && (
            <LoginForm
              onLogin={handlePasswordLogin}
              onSwitchToFaceID={() => setMode('faceid')}
              onSwitchToRegister={() => setMode('register')}
              faceIDAvailable={faceIDAvailable}
            />
          )}

          {mode === 'register' && (
            <RegisterForm
              onRegister={handleRegister}
              onSwitchToLogin={() => setMode('password')}
            />
          )}

          {mode === 'biometric_prompt' && (
            <div className="aurem-glass-card p-8 text-center" data-testid="biometric-prompt">
              <div className="mb-4">
                <div style={{ width: 64, height: 64, margin: '0 auto', borderRadius: '50%', background: 'linear-gradient(135deg, rgba(212,175,55,0.15), rgba(45,122,74,0.1))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Scan className="w-7 h-7" style={{ color: '#D4AF37' }} />
                </div>
              </div>
              <h3 className="text-base font-bold mb-1" style={{ color: '#D4AF37', fontFamily: "'Cinzel', serif", letterSpacing: '0.05em' }}>Enable Face ID / PIN?</h3>
              <p className="text-xs mb-6" style={{ color: '#8A8070', fontFamily: "'Jost', sans-serif", lineHeight: 1.6 }}>
                Skip the password next time. Use your device's biometric security for instant, secure login.
              </p>
              <div className="flex flex-col gap-3">
                <button
                  data-testid="enable-biometric-btn"
                  onClick={() => setMode('training')}
                  style={{ width: '100%', background: 'linear-gradient(135deg, #D4AF37 0%, #B8942A 100%)', border: 'none', borderRadius: 8, padding: '14px', fontFamily: "'Cinzel', serif", fontSize: 13, fontWeight: 600, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#FFF', cursor: 'pointer', boxShadow: '0 4px 20px rgba(212,175,55,0.3)', transition: 'all 0.3s ease' }}
                >
                  Enable Biometric
                </button>
                <button
                  data-testid="skip-biometric-btn"
                  onClick={() => goHome()}
                  style={{ width: '100%', background: 'transparent', border: '1px solid rgba(138,128,112,0.2)', borderRadius: 8, padding: '12px', fontFamily: "'Jost', sans-serif", fontSize: 12, fontWeight: 400, letterSpacing: '0.1em', color: '#8A8070', cursor: 'pointer', transition: 'all 0.3s ease' }}
                >
                  Skip for Now
                </button>
              </div>
            </div>
          )}

          <p className="text-center text-[11px] text-[#6A6560] mt-6" style={{ opacity: 0, animation: 'auremFadeSlideIn 0.6s ease forwards', animationDelay: '0.8s' }}>
            Protected by enterprise-grade security
          </p>
        </div>
      </div>

      <style>{`
        @keyframes auremLogoEntry { 0% { opacity: 0; transform: scale(0.5); } 60% { opacity: 1; transform: scale(1.05); } 100% { opacity: 1; transform: scale(1); } }
        @keyframes glassEntry { 0% { opacity: 0; transform: translateY(30px); } 100% { opacity: 1; transform: translateY(0); } }
        @keyframes auremPulseDelay { 0% { opacity: 0; } 10% { opacity: 1; } 100% { opacity: 1; } }
        .login-logo-glow { width: 100px; height: 100px; background: radial-gradient(circle, rgba(212,163,115,0.35) 0%, transparent 70%); border-radius: 50%; animation: pulseRing 3s ease-out infinite; }
        @keyframes pulseRing { 0% { transform: scale(0.8); opacity: 0.7; } 100% { transform: scale(2.5); opacity: 0; } }
      `}</style>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════
// LOGIN FORM
// ═══════════════════════════════════════════════════════════════
const LoginForm = ({ onLogin, onSwitchToFaceID, onSwitchToRegister, faceIDAvailable }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try { await onLogin(email, password); }
    catch (err) { setError(err.message || 'Login failed'); }
    finally { setLoading(false); }
  };

  const inputStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(212,163,115,0.22)',
    color: '#E8E4DE',
    caretColor: '#D4A373',
  };
  const labelClass = "block text-[11px] mb-1.5 uppercase tracking-wider font-semibold";
  const labelStyle = { color: '#BFA679' };

  return (
    <>
      <style>{`
        @keyframes auremShimmer {
          0%   { transform: translateX(-140%) rotate(10deg); opacity: 0; }
          18%  { opacity: 0.55; }
          55%  { opacity: 0.75; }
          100% { transform: translateX(140%) rotate(10deg); opacity: 0; }
        }
        @keyframes auremBreathe {
          0%, 100% { box-shadow: 0 30px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(212,163,115,0.18) inset, 0 0 48px rgba(212,163,115,0.08); }
          50%      { box-shadow: 0 34px 90px rgba(0,0,0,0.6), 0 0 0 1px rgba(212,163,115,0.28) inset, 0 0 72px rgba(212,163,115,0.14); }
        }
        .aurem-floating-login {
          position: relative;
          overflow: hidden;
          border-radius: 22px;
          background: linear-gradient(155deg, rgba(18,16,12,0.62) 0%, rgba(10,10,14,0.58) 55%, rgba(18,14,10,0.64) 100%) !important;
          backdrop-filter: blur(28px) saturate(160%);
          -webkit-backdrop-filter: blur(28px) saturate(160%);
          border: 1px solid rgba(212,163,115,0.22) !important;
          animation: auremBreathe 6s ease-in-out infinite;
          isolation: isolate;
        }
        .aurem-floating-login::before {
          content: '';
          position: absolute;
          top: -60%;
          left: 0;
          width: 55%;
          height: 220%;
          pointer-events: none;
          background: linear-gradient(
            110deg,
            transparent 0%,
            rgba(212,163,115,0.00) 35%,
            rgba(247,231,206,0.22) 50%,
            rgba(212,163,115,0.08) 60%,
            transparent 80%
          );
          filter: blur(14px);
          animation: auremShimmer 5.5s ease-in-out infinite;
          animation-delay: 0.8s;
          z-index: 0;
        }
        .aurem-floating-login::after {
          content: '';
          position: absolute;
          inset: 0;
          pointer-events: none;
          border-radius: inherit;
          background:
            radial-gradient(120% 60% at 50% 0%, rgba(212,163,115,0.10) 0%, transparent 55%),
            radial-gradient(80% 50% at 10% 100%, rgba(247,231,206,0.05) 0%, transparent 60%);
          z-index: 0;
        }
        .aurem-floating-login > * { position: relative; z-index: 1; }
        html.light .aurem-floating-login {
          background: linear-gradient(155deg, rgba(18,16,12,0.62) 0%, rgba(10,10,14,0.58) 55%, rgba(18,14,10,0.64) 100%) !important;
          border: 1px solid rgba(212,163,115,0.22) !important;
        }
        .aurem-floating-login input:focus {
          box-shadow: 0 0 0 2px rgba(212,163,115,0.35), inset 0 0 0 1px rgba(212,163,115,0.40) !important;
          border-color: rgba(212,163,115,0.55) !important;
        }
      `}</style>

    <div className="aurem-floating-login p-8" data-testid="login-form" style={{ padding: '34px 30px' }}>
      <h2 className="text-xl font-bold mb-1" data-testid="customer-signin-heading" style={{ fontFamily: "'Cinzel', 'Montserrat', serif", letterSpacing: '0.06em', color: '#F7E7CE' }}>Sign in to your business</h2>
      <p className="text-sm mb-6" style={{ color: '#BFA679', fontFamily: "'Jost', sans-serif" }}>Welcome back — log in with your email or BIN</p>

      {faceIDAvailable && (
        <>
          <button type="button" onClick={onSwitchToFaceID} data-testid="faceid-login-button"
            className="w-full p-4 rounded-xl text-sm font-semibold flex items-center justify-center gap-2.5 mb-4 transition-all hover:shadow-lg"
            style={{ background: 'rgba(212,163,115,0.08)', border: '1px solid rgba(212,163,115,0.2)', color: '#E8E4DE' }}>
            <Scan className="w-5 h-5" /> Sign in with FaceID
          </button>
          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#D4A373]/10" /></div>
            <div className="relative flex justify-center">
              <span className="px-2 text-[11px] text-[#9A9590]" style={{ background: 'rgba(15,15,15,0.65)' }}>or use password</span>
            </div>
          </div>
        </>
      )}

      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(220,38,38,0.12)', border: '1px solid rgba(220,38,38,0.25)', color: '#f87171' }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label className={labelClass} style={{ ...labelStyle, fontFamily: "'Jost', sans-serif" }}>Email or BIN</label>
          <input type="text" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com  or  AURE-XXXX" required data-testid="email-input"
            autoComplete="username"
            className="w-full px-4 py-3 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
            style={inputStyle} />
          <p className="text-[10px] mt-1.5" style={{ color: '#8A8070' }}>You can sign in with either your email or your AUREM Business ID (BIN).</p>
        </div>

        <div className="mb-6">
          <label className={labelClass} style={{ ...labelStyle, fontFamily: "'Jost', sans-serif" }}>Password</label>
          <div className="relative">
            <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password" required data-testid="password-input"
              className="w-full px-4 py-3 pr-12 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
              style={inputStyle} />
            <button type="button" onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 hover:text-[#F7E7CE]"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#BFA679' }}>
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <button type="submit" disabled={loading} data-testid="login-submit"
          className="w-full py-3.5 rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
          style={{
            fontFamily: "'Cinzel', 'Montserrat', serif", letterSpacing: '0.12em',
            background: 'linear-gradient(135deg, #D4A373 0%, #B38659 60%, #8B6F44 100%)',
            color: '#1A1208', border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: '0 6px 24px rgba(212,163,115,0.38), inset 0 1px 0 rgba(255,255,255,0.18)',
          }}>
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Authenticating...</> : <>SIGN IN <Lock className="w-4 h-4" /></>}
        </button>
      </form>

      {/* Switch to Register */}
      <div className="mt-6 text-center space-y-3">
        <p className="text-sm" style={{ color: '#BFA679' }}>
          New to AUREM?{' '}
          <button type="button" onClick={onSwitchToRegister} data-testid="switch-to-register"
            className="font-semibold hover:underline transition-colors"
            style={{ color: '#F7E7CE', background: 'none', border: 'none', cursor: 'pointer' }}>
            Create an account <ArrowRight className="w-3.5 h-3.5 inline" />
          </button>
        </p>
        <a href="/forgot-password" data-testid="forgot-password-link"
          className="text-[11px] hover:underline transition-colors block"
          style={{ color: '#BFA679' }}>
          Forgot your password?
        </a>
      </div>

      {/* Google OAuth Divider + Button */}
      <div className="mt-6">
        <div className="relative mb-4">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#D4A373]/15" /></div>
          <div className="relative flex justify-center">
            <span className="px-2 text-[11px]" style={{ background: 'rgba(14,12,10,0.82)', color: '#8A8070' }}>or</span>
          </div>
        </div>
        <button type="button" data-testid="google-login-button"
          onClick={() => {
            // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
            const redirectUrl = window.location.origin + '/dashboard';
            window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
          }}
          className="w-full p-3.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2.5 transition-all hover:shadow-lg"
          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(212,163,115,0.22)', color: '#E8E4DE' }}>
          <svg width="18" height="18" viewBox="0 0 18 18"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/><path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/></svg>
          Sign in with Google
        </button>
      </div>
    </div>
    </>
  );
};


// ═══════════════════════════════════════════════════════════════
// REGISTER FORM
// ═══════════════════════════════════════════════════════════════
const RegisterForm = ({ onRegister, onSwitchToLogin }) => {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    if (!phone || phone.replace(/\D/g, '').length < 7) {
      setError('Phone number is required (min 7 digits, e.g. +1 416 555 1234)');
      return;
    }
    setLoading(true);
    try { await onRegister(firstName, lastName, email, phone, password); }
    catch (err) { setError(err.message || 'Registration failed'); }
    finally { setLoading(false); }
  };

  const inputStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(212,163,115,0.22)',
    color: '#E8E4DE',
    caretColor: '#D4A373',
  };
  const labelClass = "block text-[11px] mb-1.5 uppercase tracking-wider font-semibold";
  const labelStyle = { color: '#BFA679', fontFamily: "'Jost', sans-serif" };

  return (
    <div className="aurem-floating-login" data-testid="register-form" style={{ padding: '34px 30px' }}>
      <h2 className="text-xl font-bold mb-1" style={{ fontFamily: "'Cinzel', 'Montserrat', serif", letterSpacing: '0.06em', color: '#F7E7CE' }}>Create Account</h2>
      <p className="text-sm mb-6" style={{ color: '#BFA679', fontFamily: "'Jost', sans-serif" }}>Join the AUREM Automation Platform</p>

      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(220,38,38,0.12)', border: '1px solid rgba(220,38,38,0.25)', color: '#f87171' }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className={labelClass} style={labelStyle}>First Name</label>
            <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)}
              placeholder="John" required data-testid="register-first-name"
              className="w-full px-4 py-3 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
              style={inputStyle} />
          </div>
          <div>
            <label className={labelClass} style={labelStyle}>Last Name</label>
            <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)}
              placeholder="Doe" required data-testid="register-last-name"
              className="w-full px-4 py-3 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
              style={inputStyle} />
          </div>
        </div>

        <div className="mb-4">
          <label className={labelClass} style={labelStyle}>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com" required data-testid="register-email"
            className="w-full px-4 py-3 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
            style={inputStyle} />
        </div>

        <div className="mb-4">
          <label className={labelClass} style={labelStyle}>Phone Number</label>
          <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 416 555 1234" required data-testid="register-phone"
            autoComplete="tel"
            className="w-full px-4 py-3 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
            style={inputStyle} />
          <p className="text-[10px] mt-1.5" style={{ color: '#8A8070' }}>Used for account recovery + transactional alerts</p>
        </div>

        <div className="mb-6">
          <label className={labelClass} style={labelStyle}>Password</label>
          <div className="relative">
            <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters" required data-testid="register-password"
              className="w-full px-4 py-3 pr-12 rounded-lg text-sm placeholder-[#6A6560] outline-none transition-all"
              style={inputStyle} />
            <button type="button" onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 hover:text-[#F7E7CE]"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#BFA679' }}>
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
          <p className="text-[10px] mt-1.5" style={{ color: '#8A8070' }}>Must include uppercase, lowercase, and a number</p>
        </div>

        <button type="submit" disabled={loading} data-testid="register-submit"
          className="w-full py-3.5 rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
          style={{
            fontFamily: "'Cinzel', 'Montserrat', serif", letterSpacing: '0.12em', textTransform: 'uppercase',
            background: 'linear-gradient(135deg, #D4A373 0%, #B38659 100%)',
            color: '#1A1208', border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: '0 4px 15px rgba(212,163,115,0.35)',
          }}>
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating Account...</> : <>Create Account <UserPlus className="w-4 h-4" /></>}
        </button>
      </form>

      {/* Switch to Login */}
      <div className="mt-6 text-center">
        <p className="text-sm" style={{ color: '#BFA679' }}>
          Already have an account?{' '}
          <button type="button" onClick={onSwitchToLogin} data-testid="switch-to-login"
            className="font-semibold hover:underline transition-colors"
            style={{ color: '#F7E7CE', background: 'none', border: 'none', cursor: 'pointer' }}>
            Sign in <ArrowRight className="w-3.5 h-3.5 inline" />
          </button>
        </p>
      </div>
    </div>
  );
};


export default FaceIDAuthWrapper;
