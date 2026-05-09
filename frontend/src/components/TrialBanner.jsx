/**
 * TrialBanner — fixed top banner with countdown to trial expiry. Auto-fetches
 * `/api/billing/plan/state` on mount + every 5 min. Hidden when plan is not
 * "trial" (paid users / lifetime_free see nothing).
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../lib/api';

const TrialBanner = () => {
  const [state, setState] = useState(null);

  const fetchState = async () => {
    const tok =
      localStorage.getItem('platform_token') ||
      localStorage.getItem('aurem_customer_token') ||
      localStorage.getItem('aurem_admin_token') ||
      localStorage.getItem('auth_token');
    if (!tok) return;
    try {
      const r = await axios.get(`${API}/billing/plan/state`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      setState(r.data);
    } catch (_e) { /* silent */ }
  };

  useEffect(() => {
    fetchState();
    const t = setInterval(fetchState, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  if (!state) return null;
  if (state.plan !== 'trial' && state.plan !== 'trial_expired') return null;

  const expired = state.plan === 'trial_expired';
  const endsAt = state.trial_ends_at;
  let daysLeft = null;
  if (endsAt && !expired) {
    const ends = new Date(endsAt);
    const ms = ends.getTime() - Date.now();
    daysLeft = Math.max(0, Math.ceil(ms / 86400000));
  }

  const goToBilling = () => {
    if (typeof window !== 'undefined') window.location.href = '/my/billing';
  };

  return (
    <div
      data-testid="trial-banner"
      style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: expired
          ? 'linear-gradient(90deg, #b91c1c 0%, #7f1d1d 100%)'
          : 'linear-gradient(90deg, #d4af37 0%, #b8941f 100%)',
        color: expired ? '#fef2f2' : '#0b0d11',
        padding: '10px 18px', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between',
        fontSize: 14, fontWeight: 600,
      }}
    >
      <div>
        {expired
          ? 'Your trial has ended — pick a plan to keep your data and access.'
          : daysLeft != null && daysLeft <= 1
            ? 'Less than 24 hours left in your AUREM trial.'
            : `${daysLeft ?? '7'} days left in your AUREM trial.`}
      </div>
      <button
        data-testid="trial-banner-cta"
        onClick={goToBilling}
        style={{
          background: expired ? '#fef2f2' : '#0b0d11',
          color: expired ? '#7f1d1d' : '#d4af37',
          border: 'none', borderRadius: 8,
          padding: '6px 14px', fontWeight: 700, cursor: 'pointer',
        }}
      >
        Pick a plan →
      </button>
    </div>
  );
};

export default TrialBanner;
