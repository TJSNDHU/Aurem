/**
 * TrialBanner — Section 8
 * Shows trial days remaining + upgrade CTA. Polls /api/trial/status on
 * mount. Hides itself when no trial / customer is paid.
 *
 * States:
 *   • active   → gold banner, "X days left" + Upgrade CTA
 *   • expired  → red banner, "Trial ended — keep your preview live"
 *   • (none)   → render null
 */
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, AlertCircle } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function TrialBanner() {
  const [trial, setTrial] = useState(null);
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem('aurem.trial.dismissed') === '1',
  );

  useEffect(() => {
    const tok = getPlatformToken();
    if (!tok) return;
    fetch(`${API}/api/trial/status`, {
      headers: { Authorization: `Bearer ${tok}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setTrial(d?.trial || null))
      .catch(() => setTrial(null));
  }, []);

  if (!trial || dismissed) return null;
  const state = trial.state;
  if (state !== 'active' && state !== 'expired') return null;

  const isExpired = state === 'expired';
  const days = Number(trial.days_remaining || 0);

  const gradient = isExpired
    ? 'linear-gradient(90deg, rgba(220,38,38,0.20), rgba(220,38,38,0.06))'
    : 'linear-gradient(90deg, rgba(201,162,39,0.22), rgba(249,115,22,0.10))';
  const accent = isExpired ? '#EF4444' : '#C9A227';
  const Icon = isExpired ? AlertCircle : Sparkles;

  const heading = isExpired
    ? 'Trial ended — keep your preview live'
    : days <= 1
      ? 'Trial ends today'
      : `Trial: ${days} day${days === 1 ? '' : 's'} left`;
  const sub = isExpired
    ? "Pick a plan to keep your AI agents running — your preview stays live for 7 more days."
    : 'Pick a plan now to keep your AI agents going past trial.';

  return (
    <AnimatePresence>
      <motion.div
        data-testid="trial-banner"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -12 }}
        transition={{ type: 'spring', stiffness: 220, damping: 24 }}
        style={{
          display: 'flex', alignItems: 'center', gap: 14,
          padding: '14px 18px', borderRadius: 12,
          background: gradient,
          border: `1px solid ${accent}55`,
          marginBottom: 20,
        }}
      >
        <Icon size={22} color={accent} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            data-testid="trial-banner-heading"
            style={{
              fontFamily: "'Cinzel',serif", fontSize: 14, fontWeight: 700,
              color: accent, letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            {heading}
          </div>
          <div style={{ fontSize: 12.5, color: '#E8E0D0', marginTop: 3 }}>
            {sub}
          </div>
        </div>
        <Link
          to="/my/billing"
          data-testid="trial-banner-upgrade"
          style={{
            padding: '8px 16px', borderRadius: 6,
            background: accent, color: '#0A0A0A',
            fontWeight: 700, fontSize: 12, letterSpacing: '0.08em',
            textTransform: 'uppercase', textDecoration: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          {isExpired ? 'Pick a Plan' : 'Upgrade'}
        </Link>
        <button
          data-testid="trial-banner-dismiss"
          onClick={() => {
            sessionStorage.setItem('aurem.trial.dismissed', '1');
            setDismissed(true);
          }}
          aria-label="Dismiss"
          style={{
            background: 'transparent', border: 'none',
            color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
            fontSize: 18, padding: 4,
          }}
        >
          ×
        </button>
      </motion.div>
    </AnimatePresence>
  );
}
