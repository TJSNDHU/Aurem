/**
 * MyBilling — full /my/billing page.
 *   • Current Plan card (plan name, status, renewal, services)
 *   • Per-service usage bars (data from /api/billing/usage)
 *   • Plan comparison table with upgrade buttons
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../lib/api';

const PLAN_TIERS = [
  { id: 'starter',    name: 'Starter',    price: 97,  bullet: ['Scout + CRM Starter', 'Email Campaigns', 'Site Health Monitor'] },
  { id: 'growth',     name: 'Growth',     price: 197, bullet: ['Everything in Starter', 'CRM Growth + SMS', 'WhatsApp + AI Chat'] },
  { id: 'pro',        name: 'Pro',        price: 447, bullet: ['Everything in Growth', 'Voice AI + SEO Pro', 'GEO + Security Patcher'], featured: true },
  { id: 'enterprise', name: 'Enterprise', price: 997, bullet: ['Everything', 'White-label', '25x voice concurrency'] },
];

const _tok = () =>
  localStorage.getItem('platform_token') ||
  localStorage.getItem('aurem_customer_token') ||
  localStorage.getItem('aurem_admin_token') ||
  localStorage.getItem('auth_token');

const MyBilling = () => {
  const [state, setState] = useState(null);
  const [usage, setUsage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    const run = async () => {
      const tok = _tok();
      if (!tok) { setErr('Please sign in to view billing.'); return; }
      try {
        const [s, u] = await Promise.all([
          axios.get(`${API}/billing/plan/state`, { headers: { Authorization: `Bearer ${tok}` } }),
          axios.get(`${API}/billing/usage`,      { headers: { Authorization: `Bearer ${tok}` } }),
        ]);
        setState(s.data); setUsage(u.data);
      } catch (e) {
        setErr(e?.response?.data?.detail || e?.message || 'Failed to load');
      }
    };
    run();
  }, []);

  const upgrade = async (planId) => {
    setBusy(true);
    try {
      const tok = _tok();
      const r = await axios.post(`${API}/billing/plan/subscribe`, { plan: planId, origin_url: window.location.origin },
        { headers: { Authorization: `Bearer ${tok}` } });
      if (r?.data?.checkout_url) window.location.href = r.data.checkout_url;
    } catch (e) {
      setErr(e?.response?.data?.detail || e?.message || 'Upgrade failed');
    } finally { setBusy(false); }
  };

  if (err) return <div data-testid="my-billing-error" style={{ padding: 32, color: '#fff' }}>{String(err)}</div>;
  if (!state) return <div data-testid="my-billing-loading" style={{ padding: 32, color: '#94a3b8' }}>Loading…</div>;

  const isLifetimeFree = state.plan === 'lifetime_free';
  const isTrial = state.plan === 'trial';
  const isExpired = state.plan === 'trial_expired';

  return (
    <div data-testid="my-billing-page" style={{ minHeight: '100vh', background: '#0b0d11', color: '#f9fafb', padding: 32 }}>
      <h1 style={{ fontSize: 28, marginBottom: 6 }}>Billing & Plan</h1>
      <p style={{ color: '#94a3b8', marginBottom: 28 }}>Manage your AUREM subscription and add-ons.</p>

      {/* Current plan card */}
      <div data-testid="my-billing-current-card" style={{
        background: 'linear-gradient(135deg, #131822 0%, #1f2937 100%)',
        border: '1px solid rgba(212,175,55,0.18)', borderRadius: 16, padding: 24, marginBottom: 28,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, color: '#d4af37', letterSpacing: 1.5 }}>CURRENT PLAN</div>
            <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, textTransform: 'capitalize' }}>
              {state.plan?.replace('_', ' ')}
            </div>
            <div style={{ marginTop: 6, color: '#94a3b8', fontSize: 13 }}>
              Status: <span style={{ color: isExpired ? '#ef4444' : '#10b981' }}>{state.subscription_status}</span>
              {state.trial_ends_at && isTrial && <span style={{ marginLeft: 12 }}>· trial ends {new Date(state.trial_ends_at).toLocaleDateString()}</span>}
              {state.current_period_end && !isTrial && <span style={{ marginLeft: 12 }}>· renews {new Date(state.current_period_end).toLocaleDateString()}</span>}
            </div>
          </div>
          {!isLifetimeFree && (
            <a href="#plans" style={{
              background: 'linear-gradient(135deg, #d4af37, #b8941f)', color: '#0b0d11',
              padding: '10px 20px', borderRadius: 10, fontWeight: 700, textDecoration: 'none',
            }}>{isTrial || isExpired ? 'Pick a plan' : 'Upgrade plan'}</a>
          )}
        </div>
        <div style={{ marginTop: 16, fontSize: 13, color: '#cbd5e1' }}>
          Services unlocked: <b>{state.services_unlocked?.includes('*') ? 'All services' : (state.services_unlocked || []).length}</b>
        </div>
      </div>

      {/* Usage bars */}
      {usage && usage.bars && usage.bars.length > 0 && (
        <div data-testid="my-billing-usage" style={{
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 16, padding: 22, marginBottom: 28,
        }}>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 14 }}>This month's usage</div>
          {usage.bars.filter(b => b.limit != null).map(b => (
            <div key={b.service} data-testid={`usage-bar-${b.service}`} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
                <span style={{ textTransform: 'capitalize' }}>{b.service.replace(/_/g, ' ')}</span>
                <span style={{ color: b.pct >= 90 ? '#ef4444' : b.pct >= 70 ? '#f59e0b' : '#94a3b8' }}>
                  {b.used} / {b.limit}
                </span>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.05)', borderRadius: 4 }}>
                <div style={{ width: `${b.pct}%`, height: '100%', borderRadius: 4,
                  background: b.pct >= 90 ? '#ef4444' : b.pct >= 70 ? '#f59e0b' : '#10b981' }} />
              </div>
            </div>
          ))}
          {usage.bars.filter(b => b.limit != null).length === 0 && (
            <div style={{ color: '#64748b', fontSize: 13 }}>No metered services in your current plan.</div>
          )}
        </div>
      )}

      {/* Plan comparison */}
      {!isLifetimeFree && (
        <div id="plans" data-testid="my-billing-plans">
          <h2 style={{ fontSize: 22, marginBottom: 16 }}>Choose a plan</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
            {PLAN_TIERS.map(p => {
              const isCurrent = state.plan === p.id;
              return (
                <div key={p.id} data-testid={`plan-card-${p.id}`} style={{
                  background: p.featured ? 'linear-gradient(135deg, #1a2332 0%, #2d3a52 100%)' : '#131822',
                  border: p.featured ? '1px solid rgba(212,175,55,0.3)' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 14, padding: 20, position: 'relative',
                }}>
                  {p.featured && <div style={{ position: 'absolute', top: -10, right: 14, background: '#d4af37', color: '#0b0d11', padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 700 }}>POPULAR</div>}
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{p.name}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, marginTop: 6 }}>${p.price}<span style={{ fontSize: 13, color: '#94a3b8', fontWeight: 400 }}>/mo CAD</span></div>
                  <ul style={{ marginTop: 12, padding: 0, listStyle: 'none', fontSize: 13, color: '#cbd5e1' }}>
                    {p.bullet.map((b, i) => <li key={i} style={{ marginBottom: 6 }}>· {b}</li>)}
                  </ul>
                  <button
                    data-testid={`plan-cta-${p.id}`}
                    disabled={busy || isCurrent}
                    onClick={() => upgrade(p.id)}
                    style={{
                      marginTop: 14, width: '100%', padding: '10px',
                      background: isCurrent ? 'rgba(255,255,255,0.06)' : (p.featured ? 'linear-gradient(135deg, #d4af37, #b8941f)' : 'rgba(255,255,255,0.06)'),
                      color: isCurrent ? '#94a3b8' : (p.featured ? '#0b0d11' : '#f9fafb'),
                      border: 'none', borderRadius: 8, fontWeight: 700, cursor: isCurrent ? 'default' : 'pointer',
                    }}
                  >{isCurrent ? 'Current plan' : 'Choose'}</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default MyBilling;
