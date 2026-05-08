/**
 * CustomerServicesPopup — Admin modal showing a customer's active AUREM services
 * ===============================================================================
 * Triggered from ClientManager actions bar. Auto-refreshes every 5 seconds via
 * polling so admin sees live add/remove changes from Stripe webhook + customer side.
 *
 * Shows:
 *   • Trial status (days remaining, quota usage)
 *   • Active add-on subscriptions (service name, price, started date, usage for CRM tiers)
 *   • Bundle discount auto-applied (15% / 25% / 35% / 45%)
 *   • Final MRR (base total - bundle discount)
 *   • Per-service Cancel button (admin override)
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { X, Loader2, CheckCircle2, Clock, TrendingUp, Zap, XCircle, RefreshCw } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const CLUSTER_COLORS = {
  repair:    { bg: 'rgba(59,130,246,0.12)',  text: '#3b82f6', label: 'REPAIR' },
  security:  { bg: 'rgba(239,68,68,0.12)',   text: '#ef4444', label: 'SECURITY' },
  crm:       { bg: 'rgba(34,197,94,0.12)',   text: '#22c55e', label: 'CRM' },
  marketing: { bg: 'rgba(168,85,247,0.12)',  text: '#a855f7', label: 'MARKETING' },
  power:     { bg: 'rgba(251,146,60,0.12)',  text: '#fb923c', label: 'POWER' },
};

export default function CustomerServicesPopup({ customer, token, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastSynced, setLastSynced] = useState(null);
  const [cancelling, setCancelling] = useState(null);
  const pollRef = useRef(null);

  const bin = customer.business_id || customer.tenant_id || customer.id;

  const load = useCallback(async () => {
    if (!bin) return;
    try {
      const res = await fetch(
        `${API}/api/admin/customers/${encodeURIComponent(bin)}/services`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const j = await res.json();
        setData(j);
        setError(null);
        setLastSynced(new Date());
      } else if (res.status === 404) {
        setError('Customer not found in platform_users or tenant_customers');
      } else {
        setError(`Error ${res.status}`);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [bin, token]);

  useEffect(() => {
    load();
    // Auto-refresh every 5 seconds for live sync
    pollRef.current = setInterval(load, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [load]);

  const cancelSub = async (serviceId) => {
    if (!window.confirm(`Cancel ${serviceId} for this customer?`)) return;
    setCancelling(serviceId);
    try {
      // Admin-side cancel uses a different endpoint — impersonate-style
      const res = await fetch(`${API}/api/admin/customers/${encodeURIComponent(bin)}/services/${encodeURIComponent(serviceId)}/cancel`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        await load();
      } else {
        alert(`Cancel failed (${res.status})`);
      }
    } catch (e) {
      alert(`Cancel failed: ${e.message}`);
    } finally {
      setCancelling(null);
    }
  };

  return (
    <div
      data-testid="customer-services-popup"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(5,5,10,0.78)',
        backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 860, maxHeight: '86vh',
          overflowY: 'auto',
          background: 'linear-gradient(135deg, rgba(15,18,28,0.95) 0%, rgba(20,22,35,0.95) 100%)',
          backdropFilter: 'blur(24px) saturate(160%)',
          border: '1px solid rgba(212,175,55,0.22)',
          borderRadius: 20,
          boxShadow: '0 30px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(212,175,55,0.14)',
          padding: 28,
          fontFamily: "'Jost',sans-serif",
          color: '#F4F4F4',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
          <div>
            <h2 style={{ fontFamily: "'Cinzel',serif", fontSize: 22, fontWeight: 700, margin: 0, color: '#FFF' }}>
              Customer Services
            </h2>
            <p style={{ fontSize: 12, color: '#8A8070', marginTop: 4 }}>
              <strong style={{ color: '#D4AF37' }}>{customer.business_name || customer.contact_person || customer.contact_email || bin}</strong>
              {' · '}
              <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11 }}>{bin}</span>
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {lastSynced && (
              <div style={{ fontSize: 10, color: '#8A8070', display: 'flex', alignItems: 'center', gap: 4 }}>
                <RefreshCw size={10} style={{ animation: 'spin 2s linear infinite' }} />
                Live · {lastSynced.toLocaleTimeString()}
              </div>
            )}
            <button
              onClick={onClose}
              data-testid="close-services-popup"
              style={{
                background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8, padding: 8, cursor: 'pointer', color: '#8A8070',
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {loading && (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Loader2 size={32} style={{ color: '#D4AF37', animation: 'spin 1s linear infinite' }} />
            <p style={{ fontSize: 12, color: '#8A8070', marginTop: 12 }}>Loading services…</p>
          </div>
        )}

        {error && !loading && (
          <div data-testid="services-popup-error" style={{
            padding: 20, borderRadius: 12,
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
            color: '#ef4444', fontSize: 13,
          }}>
            {error}
          </div>
        )}

        {data && !loading && !error && (
          <>
            {/* Trial section */}
            {data.trial && (
              <div data-testid="services-trial-card" style={{
                marginBottom: 18,
                padding: 16, borderRadius: 14,
                background: data.trial.state === 'active'
                  ? 'rgba(34,197,94,0.08)'
                  : 'rgba(107,114,128,0.08)',
                border: `1px solid ${data.trial.state === 'active' ? 'rgba(34,197,94,0.3)' : 'rgba(107,114,128,0.3)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Clock size={14} style={{ color: data.trial.state === 'active' ? '#22c55e' : '#6b7280' }} />
                    <span style={{ fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, color: data.trial.state === 'active' ? '#22c55e' : '#6b7280' }}>
                      Power Trial · {data.trial.state}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono',monospace", color: '#E8E0D0' }}>
                    {data.trial.days_remaining ?? '—'} days left
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 11, color: '#8A8070' }}>
                  <span>Scanner: <strong style={{ color: '#FFF' }}>{data.trial.scanner_used}/{data.trial.scanner_quota}</strong></span>
                  <span>Friend Scans: <strong style={{ color: '#FFF' }}>{data.trial.friend_scans_used}/{data.trial.friend_scans_quota}</strong></span>
                  <span>ORA Msgs: <strong style={{ color: '#FFF' }}>{data.trial.ora_msgs_used}/{data.trial.ora_msgs_quota}</strong></span>
                </div>
              </div>
            )}

            {/* MRR Summary */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 18,
            }}>
              <StatCard label="Active Services" value={data.subscription_count} testid="stat-active-count" />
              <StatCard
                label={data.bundle?.rule_label || 'No bundle discount'}
                value={data.bundle?.discount_pct > 0 ? `-${data.bundle.discount_pct}%` : '—'}
                testid="stat-bundle-discount"
                accent={data.bundle?.discount_pct > 0 ? '#22c55e' : undefined}
              />
              <StatCard
                label="Final MRR"
                value={`$${(data.final_mrr || 0).toFixed(2)}`}
                testid="stat-final-mrr"
                accent="#D4AF37"
              />
            </div>

            {/* Service list */}
            {data.subscriptions.length === 0 ? (
              <div data-testid="no-services-state" style={{
                padding: 36, textAlign: 'center',
                borderRadius: 14, background: 'rgba(255,255,255,0.02)',
                border: '1px dashed rgba(212,175,55,0.2)',
              }}>
                <Zap size={28} style={{ color: '#8A8070', margin: '0 auto 8px', display: 'block' }} />
                <p style={{ fontSize: 13, color: '#8A8070', margin: 0 }}>No active add-ons yet.</p>
                <p style={{ fontSize: 11, color: '#5A5468', marginTop: 4 }}>Customer is on {data.customer.plan || 'free'} plan.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.subscriptions.map((sub, i) => {
                  const svc = sub.service_detail || {};
                  const cc = CLUSTER_COLORS[svc.cluster] || CLUSTER_COLORS.power;
                  return (
                    <div
                      key={sub.sub_id}
                      data-testid={`sub-${sub.service_id}`}
                      style={{
                        padding: 14, borderRadius: 12,
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid rgba(212,175,55,0.12)',
                        display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 14, alignItems: 'center',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <CheckCircle2 size={12} style={{ color: '#22c55e' }} />
                          <span style={{ fontSize: 13, color: '#FFF', fontWeight: 600 }}>{sub.service_name}</span>
                          <span style={{
                            fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700,
                            padding: '2px 6px', borderRadius: 4,
                            background: cc.bg, color: cc.text,
                          }}>{cc.label}</span>
                        </div>
                        <div style={{ fontSize: 10, color: '#8A8070', fontFamily: "'JetBrains Mono',monospace" }}>
                          {sub.service_id} · Started {(sub.started_at || '').slice(0, 10)}
                        </div>
                        {svc.limits && (
                          <div style={{ fontSize: 10, color: '#8A8070', marginTop: 4 }}>
                            Limits: {svc.limits.calls} calls · {svc.limits.sms} SMS · {svc.limits.emails} emails /mo
                          </div>
                        )}
                      </div>
                      <div style={{ textAlign: 'right', minWidth: 80 }}>
                        <div style={{ fontSize: 15, color: '#D4AF37', fontWeight: 700, fontFamily: "'Jost',sans-serif" }}>
                          ${sub.price_monthly?.toFixed(2)}
                        </div>
                        <div style={{ fontSize: 9, color: '#8A8070', letterSpacing: '0.12em', textTransform: 'uppercase' }}>/mo</div>
                      </div>
                      <button
                        onClick={() => cancelSub(sub.service_id)}
                        disabled={cancelling === sub.service_id}
                        data-testid={`cancel-sub-${sub.service_id}`}
                        style={{
                          padding: '6px 10px', borderRadius: 8,
                          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                          color: '#ef4444', fontSize: 10, cursor: 'pointer', fontWeight: 600,
                          letterSpacing: '0.08em', textTransform: 'uppercase',
                          opacity: cancelling === sub.service_id ? 0.5 : 1,
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                        }}
                      >
                        {cancelling === sub.service_id
                          ? <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} />
                          : <XCircle size={10} />}
                        Cancel
                      </button>
                    </div>
                  );
                })}

                {data.bundle && data.bundle.discount_pct > 0 && (
                  <div data-testid="bundle-applied-row" style={{
                    marginTop: 4, padding: 12, borderRadius: 10,
                    background: 'linear-gradient(135deg, rgba(212,175,55,0.08) 0%, rgba(34,197,94,0.08) 100%)',
                    border: '1px dashed rgba(34,197,94,0.35)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    fontSize: 12,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <TrendingUp size={12} style={{ color: '#22c55e' }} />
                      <span style={{ color: '#22c55e', fontWeight: 700 }}>{data.bundle.rule_label}</span>
                    </div>
                    <span style={{ color: '#FFF', fontFamily: "'JetBrains Mono',monospace" }}>
                      ${data.base_total.toFixed(2)} → <strong style={{ color: '#22c55e' }}>${data.final_mrr.toFixed(2)}</strong>
                      {' '}<span style={{ color: '#22c55e' }}>(−${data.bundle.discount_amount.toFixed(2)})</span>
                    </span>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        <style>{`
          @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        `}</style>
      </div>
    </div>
  );
}

function StatCard({ label, value, testid, accent }) {
  return (
    <div
      data-testid={testid}
      style={{
        padding: 14, borderRadius: 12,
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(212,175,55,0.12)',
      }}
    >
      <div style={{ fontSize: 9, color: '#8A8070', letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 600, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 800, color: accent || '#FFF', fontFamily: "'Cinzel',serif" }}>
        {value}
      </div>
    </div>
  );
}
