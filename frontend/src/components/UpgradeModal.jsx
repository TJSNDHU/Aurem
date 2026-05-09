/**
 * UpgradeModal — listens for `aurem:service-locked` and `aurem:quota-exceeded`
 * events emitted by lib/api.js and shows a Stripe-checkout-driven upgrade
 * flow. Mount once at App root.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../lib/api';

const PLAN_LABELS = {
  starter: 'Starter — $97/mo',
  growth: 'Growth — $197/mo',
  pro: 'Pro — $447/mo',
  enterprise: 'Enterprise — $997/mo',
};

const UpgradeModal = () => {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onLocked = (e) => {
      setReason({ kind: 'service_locked', ...(e.detail || {}) });
      setOpen(true);
    };
    const onQuota = (e) => {
      setReason({ kind: 'quota_exceeded', ...(e.detail || {}) });
      setOpen(true);
    };
    window.addEventListener('aurem:service-locked', onLocked);
    window.addEventListener('aurem:quota-exceeded', onQuota);
    return () => {
      window.removeEventListener('aurem:service-locked', onLocked);
      window.removeEventListener('aurem:quota-exceeded', onQuota);
    };
  }, []);

  const subscribePlan = async (planId) => {
    setBusy(true);
    try {
      const tok =
        localStorage.getItem('platform_token') ||
        localStorage.getItem('aurem_customer_token') ||
        localStorage.getItem('aurem_admin_token') ||
        localStorage.getItem('auth_token');
      const r = await axios.post(
        `${API}/billing/plan/subscribe`,
        { plan: planId, origin_url: window.location.origin },
        { headers: tok ? { Authorization: `Bearer ${tok}` } : {} }
      );
      const url = r?.data?.checkout_url;
      if (url) window.location.href = url;
    } catch (e) {
      // best-effort; surface in console
      // eslint-disable-next-line no-console
      console.error('upgrade subscribe failed', e);
      setBusy(false);
    }
  };

  if (!open || !reason) return null;
  const opts = (reason.upgrade_options || []).filter((o) => o.type === 'plan_upgrade');
  const recommended = opts[0];
  const headline =
    reason.kind === 'quota_exceeded'
      ? `You've hit the ${reason.quota_kind?.replace('_limit', '')} limit on your ${reason.plan} plan`
      : `${reason.service?.replace(/_/g, ' ')} is locked on your ${reason.plan || 'current'} plan`;

  return (
    <div
      data-testid="upgrade-modal"
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(8, 12, 20, 0.78)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
      }}
    >
      <div
        style={{
          background: 'linear-gradient(135deg, #131822 0%, #1f2937 100%)',
          color: '#f9fafb', borderRadius: 18, padding: 32,
          maxWidth: 480, width: '100%', boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
          border: '1px solid rgba(212, 175, 55, 0.2)',
        }}
      >
        <div style={{ fontSize: 12, color: '#d4af37', letterSpacing: 1.5, marginBottom: 6 }}>
          UPGRADE REQUIRED
        </div>
        <h3 style={{ margin: '0 0 18px', fontSize: 20, lineHeight: 1.3 }}>{headline}</h3>
        {recommended ? (
          <p style={{ marginBottom: 20, color: '#cbd5e1', fontSize: 14, lineHeight: 1.5 }}>
            Upgrade to <b>{PLAN_LABELS[recommended.plan] || recommended.name}</b> to unlock this and
            keep your team moving without interruption.
          </p>
        ) : (
          <p style={{ marginBottom: 20, color: '#cbd5e1', fontSize: 14 }}>
            Pick a plan below or add this service à-la-carte.
          </p>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {opts.map((o) => (
            <button
              key={o.plan}
              data-testid={`upgrade-plan-${o.plan}`}
              disabled={busy}
              onClick={() => subscribePlan(o.plan)}
              style={{
                background: o === recommended
                  ? 'linear-gradient(135deg, #d4af37 0%, #b8941f 100%)'
                  : 'rgba(255,255,255,0.04)',
                color: o === recommended ? '#0b0d11' : '#f9fafb',
                border: '1px solid rgba(212,175,55,0.25)',
                borderRadius: 12, padding: '12px 16px', fontWeight: 600,
                cursor: busy ? 'not-allowed' : 'pointer',
                fontSize: 14, textAlign: 'left',
              }}
            >
              {PLAN_LABELS[o.plan] || `${o.name} — $${o.price_cad}/mo`}
              {o === recommended && <span style={{ marginLeft: 8, fontSize: 11 }}>RECOMMENDED</span>}
            </button>
          ))}
          <button
            data-testid="upgrade-modal-dismiss"
            onClick={() => setOpen(false)}
            style={{
              background: 'transparent', color: '#94a3b8',
              border: 'none', padding: '10px 12px', cursor: 'pointer',
              fontSize: 13, marginTop: 4,
            }}
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
};

export default UpgradeModal;
