/**
 * AUREM - Authentication Pages
 * Company: Polaris Built Inc.
 * Theme: "Obsidian Executive" with Framer Motion
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Target, Mail, Lock, Building, User, ArrowRight, Loader2, Eye, EyeOff, Shield, Radio } from 'lucide-react';
import { setPlatformToken, setPlatformUser } from '../utils/secureTokenStore';
import { BACKEND_URL } from '../lib/api';

// Smart resolver: forces same-origin on aurem.live so a stale baked-in
// preview-pod URL never bricks production login. Falls back to env var on preview.
const API_URL = BACKEND_URL;

// Login Page
export const PlatformLogin = () => {
  const navigate = useNavigate();
  const [authMode, setAuthMode] = useState('credentials'); // 'credentials' | 'pin'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [bin, setBin] = useState('');
  const [pin, setPin] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const formatErr = (detail) => {
    if (!detail) return 'Authentication failed';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((e) => e?.msg || JSON.stringify(e)).join(' ');
    return detail?.msg || String(detail);
  };

  const onSuccess = (data) => {
    setPlatformToken(data.token);
    setPlatformUser(data.user || data);
    try {
      const payload = JSON.parse(atob(data.token.split('.')[1]));
      if (payload.is_admin || payload.role === 'admin' || payload.role === 'super_admin') {
        navigate('/dashboard');
        return;
      }
    } catch {}
    navigate('/my');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const isPin = authMode === 'pin';
      const url = isPin
        ? `${API_URL}/api/platform/auth/login-pin`
        : `${API_URL}/api/platform/auth/login`;
      const body = isPin
        ? { bin: (bin || '').trim().toUpperCase(), pin: (pin || '').trim() }
        : { identifier: email, password };
      // iter 325w — DECOUPLED auth path.
      // /api/platform/auth/login is the UNIFIED login endpoint (iter 322bg)
      // that already accepts admin AND customer credentials natively against
      // db.users + db.platform_users. The legacy "admin privileges → retry
      // /api/auth/login" fallback created an unwanted coupling: if the admin
      // route had ANY issue (rate limit, scheduler death, downstream check)
      // the customer-facing form would silently retry it and surface the
      // admin error to the customer. With the unified endpoint, that retry
      // is dead code — and a real production foot-gun (per founder report
      // 2026-05-21 "customer panel attached to admin panel"). Removed.
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        // Non-JSON body (CDN 5xx / Cloudflare 520) — keep customer message
        // generic so we never surface ingress HTML or admin-side errors.
        setError('Backend temporarily unreachable. Please retry in a few seconds.');
        return;
      }
      if (res.ok) {
        onSuccess(data);
        return;
      }
      setError(formatErr(data?.detail));
    } catch (err) {
      setError('Connection error. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex relative customer-portal-bg lightning-bg" data-testid="platform-login-root" style={{ fontFamily: "'Inter', sans-serif", backgroundColor: '#050507' }}>
      {/* Robotic hero background — restored per founder ask (iter 322b) */}
      <div className="absolute inset-0" aria-hidden="true" style={{ zIndex: 0 }}>
        <div className="absolute inset-0" style={{
          backgroundImage: "url('/assets/aurem-hero-robot.jpg')",
          backgroundSize: 'cover',
          backgroundPosition: 'center right',
          filter: 'brightness(0.45) saturate(1.15)',
        }} />
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse at center, rgba(5,5,10,0.35) 0%, rgba(5,5,10,0.82) 70%, rgba(5,5,10,0.95) 100%)',
        }} />
      </div>
      {/* Left Panel - Branding (sits above bg overlay) */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden" style={{ background: 'rgba(5,5,10,0.45)', backdropFilter: 'blur(18px) saturate(140%)', WebkitBackdropFilter: 'blur(18px) saturate(140%)', borderRight: '1px solid rgba(212,175,55,0.18)', zIndex: 1 }}>
        {/* Background Grid */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: 'linear-gradient(#F97316 1px, transparent 1px), linear-gradient(90deg, #F97316 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}></div>
        </div>

        <div className="relative">
          <Link to="/platform" className="inline-flex items-center gap-3">
            <div className="relative">
              <div className="size-10 rounded bg-gradient-to-br from-[#F97316] to-[#8B7355] flex items-center justify-center">
                <Target className="size-5 text-[#050505]" />
              </div>
              <div className="absolute -top-1 -right-1 size-3 bg-[#009874] rounded-full animate-pulse"></div>
            </div>
            <div>
              <span className="text-lg tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM</span>
              <span className="text-[#F97316] text-xs ml-2">AUREM</span>
            </div>
          </Link>
        </div>
        
        <div className="relative">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-4xl text-white mb-4 leading-tight" 
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Access Your<br />
            <span className="text-[#F97316]">Command Center</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-[#C9C9D1] leading-relaxed max-w-md"
          >
            Monitor your ORA swarms. Track acquisitions. 
            Watch AUREM hunt, qualify, and close—autonomously.
          </motion.p>
        </div>

        <div className="relative flex items-center gap-2 text-[#9ca3af]">
          <Shield className="size-4 text-[#009874]" />
          <span className="text-xs tracking-wide">Enterprise-grade security. SOC 2 compliant.</span>
        </div>
      </div>

      {/* Right Panel - Form (floating glass card) */}
      <div className="flex-1 flex items-center justify-center p-8 relative" style={{ zIndex: 1 }}>
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="w-full max-w-md"
          style={{
            borderRadius: 22,
            padding: 32,
            background: 'rgba(15,18,28,0.62)',
            backdropFilter: 'blur(26px) saturate(150%)',
            WebkitBackdropFilter: 'blur(26px) saturate(150%)',
            border: '1px solid rgba(212,175,55,0.22)',
            boxShadow: '0 28px 70px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)',
          }}
        >
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-8">
            <Link to="/platform" className="inline-flex items-center gap-3">
              <div className="size-10 rounded bg-gradient-to-br from-[#F97316] to-[#8B7355] flex items-center justify-center">
                <Target className="size-5 text-[#050505]" />
              </div>
              <span className="text-lg tracking-[0.15em] text-white" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM</span>
            </Link>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-2xl text-white mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>Sign In</h2>
            <p className="text-sm text-[#9ca3af]">Access AUREM Command Center</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm"
                data-testid="login-error"
              >
                {error}
              </motion.div>
            )}

            {/* Tab toggle: Credentials | BIN + PIN */}
            <div
              className="grid grid-cols-2 gap-1 p-1 rounded"
              style={{ background: 'rgba(12,14,22,0.55)', border: '1px solid rgba(212,175,55,0.18)' }}
              data-testid="login-mode-tabs"
            >
              <button
                type="button"
                onClick={() => { setAuthMode('credentials'); setError(''); }}
                data-testid="login-tab-credentials"
                className="py-2.5 text-xs tracking-[0.18em] uppercase rounded transition-all"
                style={{
                  background: authMode === 'credentials'
                    ? 'linear-gradient(135deg,#F97316,#8B7355)'
                    : 'transparent',
                  color: authMode === 'credentials' ? '#050505' : '#9ca3af',
                  fontWeight: authMode === 'credentials' ? 700 : 500,
                }}
              >Credentials</button>
              <button
                type="button"
                onClick={() => { setAuthMode('pin'); setError(''); }}
                data-testid="login-tab-pin"
                className="py-2.5 text-xs tracking-[0.18em] uppercase rounded transition-all"
                style={{
                  background: authMode === 'pin'
                    ? 'linear-gradient(135deg,#F97316,#8B7355)'
                    : 'transparent',
                  color: authMode === 'pin' ? '#050505' : '#9ca3af',
                  fontWeight: authMode === 'pin' ? 700 : 500,
                }}
              >BIN + PIN</button>
            </div>

            {authMode === 'credentials' ? (
              <>
            <div>
              <label htmlFor="login-email" className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">Email or BIN</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#9ca3af]" />
                <input
                  id="login-email"
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@company.com or RST-TOR-9K82"
                  required
                  aria-label="Email address or BIN"
                  data-testid="login-identifier-input"
                  className="w-full pl-12 pr-4 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors"
                  style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#9ca3af]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  data-testid="login-password-input"
                  className="w-full pl-12 pr-12 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors"
                  style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label="Toggle password visibility"
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#F97316] transition-colors"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>
              </>
            ) : (
              <>
            <div>
              <label htmlFor="login-bin" className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">Business ID (BIN)</label>
              <div className="relative">
                <Building className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#9ca3af]" />
                <input
                  id="login-bin"
                  type="text"
                  value={bin}
                  onChange={(e) => setBin(e.target.value.toUpperCase())}
                  placeholder="AURE-RUGC"
                  required={authMode === 'pin'}
                  autoComplete="off"
                  inputMode="text"
                  spellCheck="false"
                  aria-label="Business ID (BIN)"
                  data-testid="login-bin-input"
                  className="w-full pl-12 pr-4 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors uppercase tracking-widest"
                  style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-pin" className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">PIN (4–6 digits)</label>
              <div className="relative">
                <Shield className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#9ca3af]" />
                <input
                  id="login-pin"
                  type={showPin ? 'text' : 'password'}
                  value={pin}
                  onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="••••"
                  required={authMode === 'pin'}
                  inputMode="numeric"
                  pattern="\d{4,6}"
                  minLength={4}
                  maxLength={6}
                  autoComplete="off"
                  data-testid="login-pin-input"
                  className="w-full pl-12 pr-12 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors tracking-[0.4em] text-center text-lg"
                  style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPin(!showPin)}
                  aria-label="Toggle PIN visibility"
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9ca3af] hover:text-[#F97316] transition-colors"
                >
                  {showPin ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              <p className="mt-2 text-xs text-[#6b7280]">
                No PIN yet? Sign in with credentials first, then set one in&nbsp;
                <span className="text-[#F97316]">Account → Security</span>.
              </p>
            </div>
              </>
            )}

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              disabled={loading}
              data-testid="login-submit-button"
              className="w-full py-3.5 bg-gradient-to-r from-[#F97316] to-[#8B7355] text-[#050505] rounded font-medium flex items-center justify-center gap-2 disabled:opacity-50 transition-all tracking-wide"
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <>
                  {authMode === 'pin' ? 'Sign in with PIN' : 'Access Command Center'}
                  <ArrowRight className="size-4" />
                </>
              )}
            </motion.button>

            <p className="text-center text-sm text-[#9ca3af]">
              New operator?{' '}
              <Link to="/platform/signup" className="text-[#F97316] hover:text-[#FDBA74] transition-colors">
                Request access
              </Link>
            </p>
            <p className="text-center text-xs text-[#6b7280] -mt-2">
              <Link
                to={authMode === 'pin' ? '/forgot-pin' : '/forgot-password'}
                data-testid={authMode === 'pin' ? 'forgot-pin-link' : 'forgot-password-link'}
                className="text-[#9ca3af] hover:text-[#F97316] transition-colors"
              >
                {authMode === 'pin' ? 'Forgot PIN?' : 'Forgot password?'}
              </Link>
            </p>
          </form>
        </motion.div>
      </div>
    </div>
  );
};

// Signup Page
export const PlatformSignup = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    company_name: '',
    full_name: '',
    pin: '',
    terms_accepted: false,
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Auto-apply dark theme based on OS preference (Day/Night). Tailwind is
  // configured with darkMode: "class", so we toggle the .dark class on <html>
  // while this page is mounted, and restore the previous state on unmount.
  useEffect(() => {
    const root = document.documentElement;
    const prevHadDark = root.classList.contains('dark');
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = (isDark) => {
      if (isDark) root.classList.add('dark');
      else root.classList.remove('dark');
    };
    apply(mq.matches);
    const onChange = (e) => apply(e.matches);
    mq.addEventListener ? mq.addEventListener('change', onChange) : mq.addListener(onChange);
    return () => {
      mq.removeEventListener ? mq.removeEventListener('change', onChange) : mq.removeListener(onChange);
      // restore
      if (prevHadDark) root.classList.add('dark');
      else root.classList.remove('dark');
    };
  }, []);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      setLoading(false);
      return;
    }

    if (formData.pin && !/^\d{4,6}$/.test(formData.pin.trim())) {
      setError('PIN must be 4 to 6 digits');
      setLoading(false);
      return;
    }

    if (!formData.terms_accepted) {
      setError('You must accept the Terms of Service and Privacy Policy to continue.');
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/platform/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await res.json();

      if (res.ok) {
        setPlatformToken(data.token);
        setPlatformUser(data.user || data);
        // iter 282h — single-hop: admin → /dashboard, customer → /my
        try {
          const payload = JSON.parse(atob(data.token.split('.')[1]));
          if (payload.is_admin || payload.role === 'admin') {
            navigate('/dashboard');
            return;
          }
        } catch {}
        navigate('/my');
      } else {
        setError(data.detail || 'Registration failed');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen flex relative lightning-bg" data-testid="platform-signup-page" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Shared robot hero background */}
      <div className="absolute inset-0 z-0" aria-hidden="true">
        <div className="absolute inset-0" style={{
          backgroundImage: 'url(/assets/aurem-hero-robot.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center right',
          filter: 'brightness(0.42) saturate(1.15)',
        }} />
        <div className="absolute inset-0" style={{
          background: 'linear-gradient(90deg, rgba(5,5,10,0.96) 0%, rgba(5,5,10,0.78) 35%, rgba(5,5,10,0.45) 65%, rgba(5,5,10,0.2) 100%)',
        }} />
      </div>

      {/* Left Panel — marketing */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden z-10">
        <div className="relative">
          <Link to="/platform" className="inline-flex items-center gap-3">
            <div className="relative">
              <div className="size-10 rounded bg-gradient-to-br from-[#F97316] to-[#8B7355] flex items-center justify-center" style={{ boxShadow: '0 8px 24px rgba(212,175,55,0.4)' }}>
                <Target className="size-5 text-[#050505]" />
              </div>
              <div className="absolute -top-1 -right-1 size-3 bg-[#009874] rounded-full animate-pulse"></div>
            </div>
            <div>
              <span className="text-lg tracking-[0.15em] text-[#F5E6C8]" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM</span>
              <span className="text-[#F97316] text-xs ml-2 tracking-widest">VANGUARD</span>
            </div>
          </Link>
        </div>

        <div className="relative">
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-4xl text-[#F5E6C8] mb-4 leading-tight"
            style={{ fontFamily: "'Playfair Display', serif", textShadow: '0 4px 24px rgba(0,0,0,0.6)' }}
          >
            Deploy Your<br />
            <span className="text-[#F97316] text-glow-gold">AI Swarm</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-[#D2C8B8] leading-relaxed max-w-md mb-8"
          >
            AUREM Vanguard hunts, qualifies, and closes leads autonomously.
            14-day evaluation. Full swarm capabilities.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="space-y-3"
          >
            {[
              '4 Elite ORA Agents (Scout, Architect, Envoy, Closer)',
              'OODA-based decision framework',
              'Voice, WhatsApp, Email channels',
              'Real-time swarm monitoring'
            ].map((feature, i) => (
              <div key={i} className="flex items-center gap-3 text-sm text-[#C5BBA9]">
                <div className="size-1.5 rounded-full bg-[#F97316]" style={{ boxShadow: '0 0 8px #F97316' }}></div>
                {feature}
              </div>
            ))}
          </motion.div>
        </div>

        <div className="relative flex items-center gap-2 text-[#8B8170]">
          <Shield className="size-4 text-[#009874]" />
          <span className="text-xs tracking-wide">Enterprise-grade security. SOC 2 compliant.</span>
        </div>
      </div>

      {/* Right Panel — floating glass form */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-8 relative z-10">
        <motion.div
          initial={{ opacity: 0, x: 20, scale: 0.97 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          transition={{ type: 'spring', stiffness: 180, damping: 22 }}
          className="w-full max-w-md spatial-glass"
          style={{ padding: '32px 28px' }}
        >
          <div className="lg:hidden text-center mb-8">
            <Link to="/platform" className="inline-flex items-center gap-3">
              <div className="size-10 rounded bg-gradient-to-br from-[#F97316] to-[#8B7355] flex items-center justify-center">
                <Target className="size-5 text-[#050505]" />
              </div>
              <span className="text-lg tracking-[0.15em] text-[#F5E6C8]" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM</span>
            </Link>
          </div>

          <div className="text-center mb-6">
            <h2 className="text-2xl text-[#F5E6C8] mb-2 text-glow-gold" style={{ fontFamily: "'Playfair Display', serif" }}>Deploy AUREM</h2>
            <p className="text-sm text-[#B8AE9F]">Initialize your autonomous ORA swarm</p>
          </div>

          {/* Prominent Sign In hint above the form */}
          <div
            className="mb-6 p-3 rounded-lg border border-[#F97316]/30 bg-[#F97316]/10 flex items-center justify-between gap-3"
            data-testid="signin-hint"
          >
            <span className="text-xs sm:text-sm text-[#B8AE9F]">
              Already have an account?
            </span>
            <Link
              to="/platform/login"
              className="text-xs sm:text-sm font-semibold text-[#8B7355] dark:text-[#F97316] hover:underline whitespace-nowrap"
              data-testid="signin-link-top"
            >
              Sign In →
            </Link>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="signup-name" className="block text-xs text-[#5C5C5C] dark:text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">Operator Name</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170] dark:text-[#666]" />
                  <input
                    id="signup-name"
                    type="text"
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="John Smith"
                    required
                    aria-label="Operator name"
                    className="w-full pl-12 pr-4 py-3.5 bg-white dark:bg-[#0F0F10] border border-[#E5E0D5] dark:border-[#2a2a2a] rounded text-[#1A1A2E] dark:text-[#F5E6C8] placeholder-[#A89F8C] dark:placeholder-[#555] focus:border-[#F97316] dark:focus:border-[#F97316]/60 focus:outline-none transition-colors text-sm"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="signup-org" className="block text-xs text-[#5C5C5C] dark:text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">Organization</label>
                <div className="relative">
                  <Building className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170] dark:text-[#666]" />
                  <input
                    id="signup-org"
                    type="text"
                    name="company_name"
                    value={formData.company_name}
                    onChange={handleChange}
                    placeholder="Acme Inc."
                    required
                    aria-label="Organization name"
                    className="w-full pl-12 pr-4 py-3.5 bg-white dark:bg-[#0F0F10] border border-[#E5E0D5] dark:border-[#2a2a2a] rounded text-[#1A1A2E] dark:text-[#F5E6C8] placeholder-[#A89F8C] dark:placeholder-[#555] focus:border-[#F97316] dark:focus:border-[#F97316]/60 focus:outline-none transition-colors text-sm"
                  />
                </div>
              </div>
            </div>

            <div>
              <label htmlFor="signup-email" className="block text-xs text-[#5C5C5C] dark:text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">Work Email</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170] dark:text-[#666]" />
                <input
                  id="signup-email"
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="operator@company.com"
                  required
                  aria-label="Work email address"
                  className="w-full pl-12 pr-4 py-3.5 bg-white dark:bg-[#0F0F10] border border-[#E5E0D5] dark:border-[#2a2a2a] rounded text-[#1A1A2E] dark:text-[#F5E6C8] placeholder-[#A89F8C] dark:placeholder-[#555] focus:border-[#F97316] dark:focus:border-[#F97316]/60 focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div>
              <label htmlFor="signup-password" className="block text-xs text-[#5C5C5C] dark:text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170] dark:text-[#666]" />
                <input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Min. 8 characters"
                  required
                  aria-label="Password"
                  minLength={8}
                  className="w-full pl-12 pr-12 py-3.5 bg-white dark:bg-[#0F0F10] border border-[#E5E0D5] dark:border-[#2a2a2a] rounded text-[#1A1A2E] dark:text-[#F5E6C8] placeholder-[#A89F8C] dark:placeholder-[#555] focus:border-[#F97316] dark:focus:border-[#F97316]/60 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label="Toggle password visibility"
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#8B8170] dark:text-[#666] hover:text-[#1A1A2E] dark:hover:text-[#F97316] transition-colors"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            {/* iter 322bg — Quick-login PIN (optional, 4–6 digits) */}
            <div>
              <label htmlFor="signup-pin" className="block text-xs text-[#5C5C5C] dark:text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">
                Quick-Login PIN <span className="text-[#8B8170] normal-case tracking-normal">(optional · 4–6 digits)</span>
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170] dark:text-[#666]" />
                <input
                  id="signup-pin"
                  type={showPin ? 'text' : 'password'}
                  inputMode="numeric"
                  pattern="\d{4,6}"
                  maxLength={6}
                  name="pin"
                  value={formData.pin}
                  onChange={(e) => setFormData({ ...formData, pin: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                  placeholder="e.g. 482190"
                  aria-label="Quick-login PIN"
                  data-testid="signup-pin-input"
                  className="w-full pl-12 pr-12 py-3.5 bg-white dark:bg-[#0F0F10] border border-[#E5E0D5] dark:border-[#2a2a2a] rounded text-[#1A1A2E] dark:text-[#F5E6C8] placeholder-[#A89F8C] dark:placeholder-[#555] focus:border-[#F97316] dark:focus:border-[#F97316]/60 focus:outline-none transition-colors tracking-[0.4em]"
                />
                <button
                  type="button"
                  onClick={() => setShowPin(!showPin)}
                  aria-label="Toggle PIN visibility"
                  data-testid="signup-pin-toggle"
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#8B8170] dark:text-[#666] hover:text-[#F97316] transition-colors"
                >
                  {showPin ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              <p className="mt-2 text-[11px] text-[#8B8170] dark:text-[#777] leading-relaxed">
                Sign in faster on mobile using your BIN + PIN. You can set or change this later in Settings.
              </p>
            </div>

            <div className="flex items-start gap-3 py-2">
              <input
                type="checkbox"
                id="terms_accepted"
                checked={formData.terms_accepted}
                onChange={(e) => setFormData({ ...formData, terms_accepted: e.target.checked })}
                required
                data-testid="terms-checkbox"
                className="mt-0.5 size-4 rounded border-[#A89F8C] dark:border-[#444] accent-[#F97316] cursor-pointer"
              />
              <label htmlFor="terms_accepted" className="text-xs text-[#5C5C5C] dark:text-[#B8AE9F] leading-relaxed cursor-pointer">
                I have read and agree to the{' '}
                <a href="/legal/terms" target="_blank" rel="noopener noreferrer" className="text-[#8B7355] dark:text-[#F97316] font-medium hover:underline">Terms of Service</a>
                {' '}and{' '}
                <a href="/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-[#8B7355] dark:text-[#F97316] font-medium hover:underline">Privacy Policy</a>
              </label>
            </div>

            <motion.button
              whileHover={{ scale: 1.02, boxShadow: '0 0 30px rgba(212, 175, 55, 0.2)' }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              disabled={loading || !formData.terms_accepted}
              className="w-full py-3.5 bg-gradient-to-r from-[#F97316] to-[#8B7355] text-[#050505] rounded font-medium flex items-center justify-center gap-2 disabled:opacity-50 transition-all tracking-wide"
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <>
                  Initialize Swarm
                  <Radio className="size-4" />
                </>
              )}
            </motion.button>

            <p className="text-center text-xs text-[#8B8170] dark:text-[#666]">
              View all policies at{' '}
              <a href="/legal" className="text-[#8B7355] dark:text-[#F97316] hover:underline">aurem.live/legal</a>
            </p>

            <p className="text-center text-sm text-[#5C5C5C] dark:text-[#B8AE9F]" data-testid="signin-link-bottom-wrap">
              Already have an account?{' '}
              <Link to="/platform/login" className="text-[#8B7355] dark:text-[#F97316] font-semibold hover:underline" data-testid="signin-link-bottom">
                Sign In
              </Link>
            </p>
          </form>
        </motion.div>
      </div>
    </div>
  );
};

export default PlatformLogin;

