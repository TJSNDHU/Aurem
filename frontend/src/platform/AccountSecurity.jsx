/**
 * AUREM — Account Security Page (iter 305e)
 *
 * Lets the authenticated user set up a PIN for the first time, change
 * an existing PIN, and see PIN status. Used in tandem with the BIN+PIN
 * tab on /platform/login.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Lock, Loader2, ChevronLeft, CheckCircle2 } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';
import { BACKEND_URL } from '../lib/api';

const API_URL = BACKEND_URL;

const fmtErr = (detail) => {
  if (!detail) return 'Something went wrong';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((e) => e?.msg || JSON.stringify(e)).join(' ');
  return detail?.msg || String(detail);
};

const sanitizePin = (v) => (v || '').replace(/\D/g, '').slice(0, 6);

export default function AccountSecurity() {
  const navigate = useNavigate();
  const token = getPlatformToken();

  const [status, setStatus] = useState({ loading: true, pin_set: false });
  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [oldPin, setOldPin] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  useEffect(() => {
    if (!token) {
      navigate('/platform/login');
      return;
    }
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/platform/auth/pin-status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const d = await r.json();
        if (r.ok) setStatus({ loading: false, pin_set: !!d.pin_set, pin_set_at: d.pin_set_at, locked: !!d.locked });
        else setStatus({ loading: false, pin_set: false });
      } catch {
        setStatus({ loading: false, pin_set: false });
      }
    })();
  }, [token, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setMsg({ type: '', text: '' });
    if (newPin.length < 4) {
      setMsg({ type: 'err', text: 'PIN must be 4–6 digits' });
      return;
    }
    if (newPin !== confirmPin) {
      setMsg({ type: 'err', text: 'PINs do not match' });
      return;
    }
    if (status.pin_set && !oldPin) {
      setMsg({ type: 'err', text: 'Enter your current PIN' });
      return;
    }
    setBusy(true);
    try {
      const url = status.pin_set
        ? `${API_URL}/api/platform/auth/change-pin`
        : `${API_URL}/api/platform/auth/setup-pin`;
      const body = status.pin_set
        ? { old_pin: oldPin, new_pin: newPin }
        : { pin: newPin };
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (r.ok) {
        setMsg({ type: 'ok', text: status.pin_set ? 'PIN updated successfully' : 'PIN set successfully' });
        setStatus({ ...status, pin_set: true, pin_set_at: new Date().toISOString() });
        setNewPin(''); setConfirmPin(''); setOldPin('');
      } else {
        setMsg({ type: 'err', text: fmtErr(d.detail) });
      }
    } catch {
      setMsg({ type: 'err', text: 'Network error — please try again' });
    }
    setBusy(false);
  };

  if (status.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#050510' }}>
        <Loader2 className="w-6 h-6 animate-spin text-[#F97316]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8" style={{ background: '#050510', color: '#E8E0D0', fontFamily: "'Inter', sans-serif" }}
         data-testid="account-security-page">
      <div className="max-w-md mx-auto">
        <button
          onClick={() => navigate(-1)}
          className="mb-6 inline-flex items-center gap-2 text-sm text-[#9ca3af] hover:text-[#F97316] transition-colors"
          data-testid="account-security-back"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>

        <div
          className="rounded p-8"
          style={{
            background: 'rgba(15,18,28,0.62)',
            backdropFilter: 'blur(26px) saturate(150%)',
            border: '1px solid rgba(212,175,55,0.22)',
          }}
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded flex items-center justify-center" style={{ background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.3)' }}>
              <Shield className="w-5 h-5 text-[#F97316]" />
            </div>
            <div>
              <h1 className="text-xl text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
                {status.pin_set ? 'Change PIN' : 'Set up PIN'}
              </h1>
              <p className="text-xs text-[#9ca3af]">
                {status.pin_set ? 'Update your fast-login PIN' : 'Enable BIN + PIN sign-in'}
              </p>
            </div>
          </div>

          {status.pin_set && (
            <div
              className="mb-6 p-3 rounded text-xs flex items-center gap-2"
              style={{ background: 'rgba(34,197,94,0.08)', color: '#86EFAC', border: '1px solid rgba(34,197,94,0.25)' }}
            >
              <CheckCircle2 className="w-4 h-4" />
              PIN is currently set on this account.
            </div>
          )}

          {msg.text && (
            <div
              className="mb-6 p-3 rounded text-sm"
              data-testid="account-security-msg"
              style={
                msg.type === 'ok'
                  ? { background: 'rgba(34,197,94,0.08)', color: '#86EFAC', border: '1px solid rgba(34,197,94,0.25)' }
                  : { background: 'rgba(239,68,68,0.08)', color: '#FCA5A5', border: '1px solid rgba(239,68,68,0.25)' }
              }
            >
              {msg.text}
            </div>
          )}

          <form onSubmit={submit} className="space-y-5">
            {status.pin_set && (
              <div>
                <label className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">Current PIN</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9ca3af]" />
                  <input
                    type="password"
                    inputMode="numeric"
                    pattern="\d{4,6}"
                    maxLength={6}
                    value={oldPin}
                    onChange={(e) => setOldPin(sanitizePin(e.target.value))}
                    placeholder="••••"
                    required
                    autoComplete="off"
                    data-testid="security-old-pin"
                    className="w-full pl-12 pr-4 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors tracking-[0.4em] text-center text-lg"
                    style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">
                {status.pin_set ? 'New PIN' : 'PIN'} (4–6 digits)
              </label>
              <div className="relative">
                <Shield className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9ca3af]" />
                <input
                  type="password"
                  inputMode="numeric"
                  pattern="\d{4,6}"
                  minLength={4}
                  maxLength={6}
                  value={newPin}
                  onChange={(e) => setNewPin(sanitizePin(e.target.value))}
                  placeholder="••••"
                  required
                  autoComplete="off"
                  data-testid="security-new-pin"
                  className="w-full pl-12 pr-4 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors tracking-[0.4em] text-center text-lg"
                  style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#F97316] tracking-[0.15em] uppercase mb-2">Confirm PIN</label>
              <div className="relative">
                <Shield className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9ca3af]" />
                <input
                  type="password"
                  inputMode="numeric"
                  pattern="\d{4,6}"
                  minLength={4}
                  maxLength={6}
                  value={confirmPin}
                  onChange={(e) => setConfirmPin(sanitizePin(e.target.value))}
                  placeholder="••••"
                  required
                  autoComplete="off"
                  data-testid="security-confirm-pin"
                  className="w-full pl-12 pr-4 py-3.5 rounded text-[#E8E0D0] focus:outline-none transition-colors tracking-[0.4em] text-center text-lg"
                  style={{ background: 'rgba(12,14,22,0.72)', border: '1px solid rgba(212,175,55,0.22)' }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={busy}
              data-testid="security-submit"
              className="w-full py-3.5 bg-gradient-to-r from-[#F97316] to-[#8B7355] text-[#050505] rounded font-semibold flex items-center justify-center gap-2 disabled:opacity-50 transition-all tracking-wide"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : (status.pin_set ? 'Update PIN' : 'Set PIN')}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
