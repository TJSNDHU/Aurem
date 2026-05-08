/**
 * Founder TOTP Enrolment Screen
 * 1) GET QR via /api/auth/admin/2fa/setup
 * 2) Scan in Google Authenticator / Authy
 * 3) POST /admin/2fa/enable with 6-digit code
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Shield, Loader2, Check, AlertTriangle, Copy, ArrowRight, X } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';
import { BACKEND_URL } from '../lib/api';

const API_URL = BACKEND_URL;

const Admin2FAEnroll = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading'); // loading | enrolled | needs_setup | enabling | done | error
  const [qr, setQr] = useState('');
  const [secret, setSecret] = useState('');
  const [uri, setUri] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const token = getPlatformToken();

  const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  });

  // 1. Check current status
  useEffect(() => {
    if (!token) { navigate('/admin/login'); return; }
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/auth/admin/2fa/status`, { headers: authHeaders() });
        const data = await res.json();
        if (res.ok && data.totp_enabled) {
          setStatus('enrolled');
        } else {
          setStatus('needs_setup');
        }
      } catch {
        setStatus('error');
        setError('Could not reach server');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startSetup = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/auth/admin/2fa/setup`, { method: 'POST', headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Setup failed');
      setQr(data.qr_data_url);
      setSecret(data.secret);
      setUri(data.otpauth_uri);
      setStatus('enabling');
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const enable = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/auth/admin/2fa/enable`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Invalid code');
      setStatus('done');
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const disable = async () => {
    const c = window.prompt('Enter current 6-digit 2FA code to DISABLE 2FA:');
    if (!c) return;
    setBusy(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/auth/admin/2fa/disable`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ code: c }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Disable failed');
      setStatus('needs_setup');
      setQr(''); setSecret(''); setUri(''); setCode('');
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const copySecret = () => navigator.clipboard.writeText(secret).catch(() => {});

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12"
      style={{ background: '#050507', fontFamily: "'Inter', sans-serif" }}
      data-testid="admin-2fa-page">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md rounded-2xl"
        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', padding: '36px 32px' }}
      >
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg,#D4AF37,#8B7355)' }}>
              <Shield className="w-5 h-5 text-[#050507]" />
            </div>
            <div>
              <h1 className="text-base tracking-[0.15em]" style={{ fontFamily: "'Cinzel',serif", color: '#E8E6E1' }}>
                FOUNDER 2FA
              </h1>
              <p className="text-[10px] text-[#666] tracking-[0.2em] uppercase">TOTP · RFC 6238</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/admin/mission-control')}
            data-testid="admin-2fa-close"
            className="text-[#666] hover:text-[#E8E6E1] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg flex items-center gap-2 text-xs"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444' }}
            data-testid="admin-2fa-error">
            <AlertTriangle className="w-3.5 h-3.5" />{error}
          </div>
        )}

        {status === 'loading' && (
          <div className="flex items-center justify-center py-12 text-[#666]">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        )}

        {status === 'enrolled' && (
          <div data-testid="admin-2fa-enrolled">
            <div className="p-4 rounded-lg flex items-center gap-3 mb-6"
              style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)' }}>
              <Check className="w-4 h-4 text-[#22C55E]" />
              <div className="text-xs text-[#22C55E]">2FA is ACTIVE on this account.</div>
            </div>
            <p className="text-xs text-[#888] mb-6 leading-relaxed">
              Every admin login now requires the 6-digit code from your authenticator app.
              Lose your phone? Disable below using a current code, or revoke from a recovery shell.
            </p>
            <button
              onClick={disable}
              disabled={busy}
              data-testid="admin-2fa-disable-btn"
              className="w-full py-2.5 rounded-lg text-xs disabled:opacity-50"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#EF4444' }}>
              Disable 2FA (requires current code)
            </button>
          </div>
        )}

        {status === 'needs_setup' && (
          <div data-testid="admin-2fa-needs-setup">
            <p className="text-xs text-[#888] mb-6 leading-relaxed">
              Bind a TOTP authenticator (Google Authenticator, Authy, 1Password, Raivo) to this admin
              account. After enrolment, every login will require a fresh 6-digit code.
            </p>
            <button
              onClick={startSetup}
              disabled={busy}
              data-testid="admin-2fa-start-btn"
              className="w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 text-sm disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg,#D4AF37,#8B7355)', color: '#050507' }}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Start enrolment <ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
        )}

        {status === 'enabling' && (
          <form onSubmit={enable} data-testid="admin-2fa-enabling">
            <p className="text-[11px] text-[#888] mb-4">
              1. Open your authenticator app · 2. Scan the QR · 3. Enter the 6-digit code below.
            </p>
            {qr && (
              <div className="flex justify-center mb-5">
                <img src={qr} alt="2FA QR" className="rounded-lg" style={{ width: 220, height: 220, background: '#fff', padding: 8 }} data-testid="admin-2fa-qr" />
              </div>
            )}
            <div className="mb-5">
              <label className="block text-[9px] text-[#555] tracking-[0.2em] uppercase mb-1.5">Manual key (if scan fails)</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 px-3 py-2 rounded-lg text-[11px] font-mono break-all"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#D4AF37' }}
                  data-testid="admin-2fa-secret">{secret}</code>
                <button type="button" onClick={copySecret}
                  className="px-3 py-2 rounded-lg text-[#888] hover:text-[#D4AF37]"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <div className="mb-5">
              <label htmlFor="enroll-code" className="block text-[9px] text-[#555] tracking-[0.2em] uppercase mb-1.5">6-digit code</label>
              <input
                id="enroll-code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                required
                autoFocus
                data-testid="admin-2fa-code-input"
                className="w-full px-4 py-3 rounded-lg text-center text-lg tracking-[0.6em] font-mono"
                style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.25)', color: '#E8E6E1' }}
                placeholder="000000"
              />
            </div>
            <button
              type="submit"
              disabled={busy || code.length !== 6}
              data-testid="admin-2fa-confirm-btn"
              className="w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 text-sm disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg,#D4AF37,#8B7355)', color: '#050507' }}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Verify & enable <Check className="w-4 h-4" /></>}
            </button>
            <p className="text-[10px] text-[#444] mt-4 text-center">
              The QR is single-use. Don't refresh until enrolment is confirmed.
            </p>
          </form>
        )}

        {status === 'done' && (
          <div data-testid="admin-2fa-done">
            <div className="p-4 rounded-lg flex items-center gap-3 mb-6"
              style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)' }}>
              <Check className="w-4 h-4 text-[#22C55E]" />
              <div className="text-xs text-[#22C55E]">2FA enabled. Stolen-password attacks neutralised.</div>
            </div>
            <button
              onClick={() => navigate('/admin/mission-control')}
              data-testid="admin-2fa-go-mc"
              className="w-full py-3 rounded-lg font-medium text-sm"
              style={{ background: 'linear-gradient(135deg,#D4AF37,#8B7355)', color: '#050507' }}>
              Back to Mission Control
            </button>
          </div>
        )}

        {status === 'error' && (
          <div className="text-xs text-[#EF4444]">{error || 'Something went wrong.'}</div>
        )}
      </motion.div>
    </div>
  );
};

export default Admin2FAEnroll;
