/**
 * ForgotPin — request a PIN reset code by email/BIN, then submit new PIN.
 * iter 322bg
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Lock, Mail, Loader2, ShieldCheck, ArrowLeft } from 'lucide-react';
import { BACKEND_URL } from '../lib/api';

const API = BACKEND_URL;

export default function ForgotPin() {
  const [step, setStep] = useState('request'); // request | confirm | done
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [newPin, setNewPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const submitRequest = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setNotice('');
    try {
      const res = await fetch(`${API}/api/platform/auth/forgot-pin/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: identifier.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setNotice('If your account exists, a 6-digit code has been emailed to you.');
        setStep('confirm');
      } else {
        setError(data.detail || 'Could not send reset code.');
      }
    } catch (_) {
      setError('Connection error. Please try again.');
    }
    setLoading(false);
  };

  const submitConfirm = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setNotice('');
    if (!/^\d{4,6}$/.test(newPin.trim())) {
      setError('New PIN must be 4–6 digits'); setLoading(false); return;
    }
    try {
      const res = await fetch(`${API}/api/platform/auth/forgot-pin/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identifier: identifier.trim(),
          code: code.trim(),
          new_pin: newPin.trim(),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setStep('done');
      } else {
        setError(data.detail || 'Could not reset PIN.');
      }
    } catch (_) {
      setError('Connection error. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div
      data-testid="forgot-pin-page"
      className="min-h-screen flex items-center justify-center px-4"
      style={{
        backgroundColor: '#050507',
        backgroundImage: "url('/assets/aurem-hero-robot.jpg')",
        backgroundSize: 'cover',
        backgroundPosition: 'center right',
        fontFamily: "'Inter', sans-serif",
      }}
    >
      <div
        className="absolute inset-0"
        aria-hidden="true"
        style={{ background: 'radial-gradient(ellipse at center, rgba(5,5,10,0.6) 0%, rgba(5,5,10,0.94) 80%)' }}
      />
      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 180, damping: 22 }}
        className="relative w-full max-w-md"
        style={{
          background: 'rgba(13,13,23,0.78)',
          backdropFilter: 'blur(22px) saturate(160%)',
          WebkitBackdropFilter: 'blur(22px) saturate(160%)',
          border: '1px solid rgba(212,175,55,0.22)',
          borderRadius: 18,
          padding: '34px 28px',
          boxShadow: '0 24px 60px rgba(0,0,0,0.55)',
        }}
      >
        <Link
          to="/platform/login"
          data-testid="forgot-pin-back"
          className="inline-flex items-center gap-2 text-xs text-[#B8AE9F] hover:text-[#F97316] mb-5"
        >
          <ArrowLeft className="size-3.5" /> Back to sign in
        </Link>

        <div className="flex items-center gap-3 mb-1">
          <div className="size-10 rounded-lg bg-gradient-to-br from-[#F97316] to-[#8B7355] flex items-center justify-center">
            <ShieldCheck className="size-5 text-[#050505]" />
          </div>
          <div>
            <h1 className="text-xl text-[#F5E6C8]" style={{ fontFamily: "'Playfair Display', serif" }}>
              Reset Your PIN
            </h1>
            <p className="text-[11px] tracking-[0.15em] uppercase text-[#8B8170]">Email verification</p>
          </div>
        </div>

        {error && (
          <div className="mt-5 p-3 rounded border border-red-500/30 bg-red-500/10 text-red-300 text-sm" data-testid="forgot-pin-error">
            {error}
          </div>
        )}
        {notice && step === 'confirm' && (
          <div className="mt-5 p-3 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-sm">
            {notice}
          </div>
        )}

        {step === 'request' && (
          <form onSubmit={submitRequest} className="space-y-4 mt-6">
            <div>
              <label htmlFor="fp-id" className="block text-xs text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">
                BIN or Email
              </label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170]" />
                <input
                  id="fp-id"
                  data-testid="forgot-pin-identifier"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                  placeholder="AURE-XXXX  or  you@company.com"
                  className="w-full pl-12 pr-4 py-3.5 bg-[#0F0F10] border border-[#2a2a2a] rounded text-[#F5E6C8] placeholder-[#555] focus:border-[#F97316]/60 focus:outline-none transition-colors text-sm"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="forgot-pin-send"
              className="w-full py-3.5 bg-gradient-to-r from-[#F97316] to-[#8B7355] text-[#050505] rounded font-medium flex items-center justify-center gap-2 disabled:opacity-50 tracking-wide"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : 'Email me a code'}
            </button>
          </form>
        )}

        {step === 'confirm' && (
          <form onSubmit={submitConfirm} className="space-y-4 mt-6">
            <div>
              <label htmlFor="fp-code" className="block text-xs text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">
                6-Digit Code
              </label>
              <input
                id="fp-code"
                data-testid="forgot-pin-code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                required
                inputMode="numeric"
                placeholder="••••••"
                className="w-full px-4 py-3.5 bg-[#0F0F10] border border-[#2a2a2a] rounded text-[#F5E6C8] placeholder-[#555] focus:border-[#F97316]/60 focus:outline-none tracking-[0.5em] text-center"
              />
            </div>
            <div>
              <label htmlFor="fp-new" className="block text-xs text-[#9CA3AF] tracking-[0.15em] uppercase mb-2">
                New PIN (4–6 digits)
              </label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 size-4 text-[#8B8170]" />
                <input
                  id="fp-new"
                  data-testid="forgot-pin-new"
                  type="password"
                  value={newPin}
                  onChange={(e) => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  required
                  inputMode="numeric"
                  placeholder="••••••"
                  className="w-full pl-12 pr-4 py-3.5 bg-[#0F0F10] border border-[#2a2a2a] rounded text-[#F5E6C8] placeholder-[#555] focus:border-[#F97316]/60 focus:outline-none tracking-[0.4em]"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="forgot-pin-confirm"
              className="w-full py-3.5 bg-gradient-to-r from-[#F97316] to-[#8B7355] text-[#050505] rounded font-medium flex items-center justify-center gap-2 disabled:opacity-50 tracking-wide"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : 'Reset PIN'}
            </button>
            <button
              type="button"
              onClick={() => { setStep('request'); setCode(''); setNewPin(''); setError(''); setNotice(''); }}
              className="w-full text-xs text-[#9CA3AF] hover:text-[#F97316]"
            >
              Didn't get the code? Send again
            </button>
          </form>
        )}

        {step === 'done' && (
          <div className="mt-6 text-center" data-testid="forgot-pin-done">
            <p className="text-[#F5E6C8] mb-4">Your PIN has been reset.</p>
            <Link
              to="/platform/login"
              className="inline-block px-5 py-2.5 bg-gradient-to-r from-[#F97316] to-[#8B7355] text-[#050505] rounded font-medium tracking-wide"
            >
              Sign in now
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  );
}
