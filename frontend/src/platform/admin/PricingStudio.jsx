/**
 * PricingStudio — Admin inline-edit for 17 services + bundle rules
 * ==================================================================
 * Part of AdminCommandHub. Edits `db.service_catalog` via PATCH endpoint.
 * Changes propagate to customer portal via polling (10s interval).
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Edit2, Check, X, Loader2, Plus, AlertTriangle, Package, Zap } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const CLUSTER_META = {
  repair:    { label: 'Repair & Performance', color: '#3b82f6', order: 1 },
  security:  { label: 'Security & Compliance', color: '#ef4444', order: 2 },
  crm:       { label: 'CRM (Volume Tiers)', color: '#22c55e', order: 3 },
  marketing: { label: 'Marketing & Outreach', color: '#a855f7', order: 4 },
  power:     { label: 'Power User / AI Agent', color: '#fb923c', order: 5 },
};

const card = {
  padding: 18, borderRadius: 14,
  background: 'rgba(15,18,28,0.55)',
  border: '1px solid rgba(212,175,55,0.14)',
  backdropFilter: 'blur(22px)',
  marginBottom: 14,
};

export default function PricingStudio({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [showBundleRules, setShowBundleRules] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/catalog`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        setData(await res.json());
        setError(null);
      } else {
        setError(`HTTP ${res.status}`);
      }
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const startEdit = (svc) => {
    setEditing({
      service_id: svc.service_id,
      name: svc.name,
      price_monthly: svc.price_monthly,
      cost_monthly: svc.cost_monthly,
      status: svc.status || 'live',
      description: svc.description,
    });
  };

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const body = {
        price_monthly: Number(editing.price_monthly),
        cost_monthly: Number(editing.cost_monthly),
        status: editing.status,
        name: editing.name,
        description: editing.description,
      };
      const res = await fetch(`${API}/api/admin/catalog/${editing.service_id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      setEditing(null);
      await load();
    } catch (e) { alert(e.message); } finally { setSaving(false); }
  };

  const toggleStatus = async (svc) => {
    const newStatus = svc.status === 'live' ? 'disabled' : 'live';
    try {
      await fetch(`${API}/api/admin/catalog/${svc.service_id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      await load();
    } catch (e) { alert(e.message); }
  };

  if (loading) return <div style={card}><Loader2 className="animate-spin" size={28} style={{ color: '#D4AF37', display: 'block', margin: '20px auto' }} /></div>;
  if (error) return <div style={{ ...card, color: '#ef4444' }}>Error: {error}</div>;

  const clusters = data?.clusters || {};
  const primitives = data?.primitives || [];

  return (
    <div data-testid="pricing-studio">
      {/* Summary header */}
      <div style={{ ...card, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        <Stat label="Total Services" value={data?.total_services || 0} />
        <Stat label="Active Subscribers" value={data?.total_active_subs || 0} />
        <Stat label="Platform MRR" value={`$${(data?.total_mrr || 0).toFixed(2)}`} color="#D4AF37" />
        <Stat label="Stripe Mode" value="LIVE ✓" color="#22C55E" />
      </div>

      {/* Clusters */}
      {Object.entries(clusters)
        .sort(([a], [b]) => (CLUSTER_META[a]?.order || 99) - (CLUSTER_META[b]?.order || 99))
        .map(([cluster, services]) => {
          const meta = CLUSTER_META[cluster] || { label: cluster, color: '#D4AF37' };
          return (
            <div key={cluster} style={card} data-testid={`cluster-${cluster}`}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: meta.color, letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 14px 0' }}>
                <Package size={14} />
                {meta.label} · {services.length} service{services.length !== 1 ? 's' : ''}
              </h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ color: '#8A8070', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                    <th style={{ textAlign: 'left', padding: '6px 6px' }}>Service</th>
                    <th style={{ textAlign: 'right', padding: '6px 6px', width: 80 }}>Cost</th>
                    <th style={{ textAlign: 'right', padding: '6px 6px', width: 90 }}>Price</th>
                    <th style={{ textAlign: 'right', padding: '6px 6px', width: 60 }}>Margin</th>
                    <th style={{ textAlign: 'right', padding: '6px 6px', width: 60 }}>Subs</th>
                    <th style={{ textAlign: 'right', padding: '6px 6px', width: 90 }}>MRR</th>
                    <th style={{ textAlign: 'center', padding: '6px 6px', width: 70 }}>Status</th>
                    <th style={{ padding: '6px 6px', width: 70 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {services.map(svc => (
                    <tr key={svc.service_id} data-testid={`row-${svc.service_id}`} style={{ borderTop: '1px solid rgba(212,175,55,0.08)' }}>
                      <td style={{ padding: '10px 6px' }}>
                        <div style={{ fontSize: 12, color: '#E8E0D0', fontWeight: 600 }}>{svc.name}</div>
                        <div style={{ fontSize: 10, color: '#8A8070', fontFamily: "'JetBrains Mono',monospace" }}>{svc.service_id}</div>
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right', fontSize: 12, color: '#8A8070', fontFamily: "'JetBrains Mono',monospace" }}>
                        ${(svc.cost_monthly || 0).toFixed(2)}
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right', fontSize: 13, color: '#D4AF37', fontFamily: "'JetBrains Mono',monospace", fontWeight: 700 }}>
                        ${(svc.price_monthly || 0).toFixed(2)}
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right', fontSize: 11, color: (svc.margin_pct || 0) >= 70 ? '#22c55e' : '#fb923c' }}>
                        {(svc.margin_pct || 0).toFixed(1)}%
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right', fontSize: 12, color: '#FFF', fontFamily: "'JetBrains Mono',monospace" }}>
                        {svc.active_subscribers || 0}
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right', fontSize: 12, color: '#22c55e', fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>
                        ${(svc.monthly_revenue || 0).toFixed(2)}
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'center' }}>
                        <button
                          data-testid={`toggle-${svc.service_id}`}
                          onClick={() => toggleStatus(svc)}
                          style={{
                            padding: '3px 8px', borderRadius: 6, fontSize: 9, fontWeight: 700,
                            letterSpacing: '0.1em', textTransform: 'uppercase',
                            background: svc.status === 'live' ? 'rgba(34,197,94,0.12)' : 'rgba(107,114,128,0.12)',
                            color: svc.status === 'live' ? '#22c55e' : '#6b7280',
                            border: `1px solid ${svc.status === 'live' ? 'rgba(34,197,94,0.3)' : 'rgba(107,114,128,0.3)'}`,
                            cursor: 'pointer',
                          }}
                        >{svc.status || 'live'}</button>
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'right' }}>
                        <button
                          onClick={() => startEdit(svc)}
                          data-testid={`edit-${svc.service_id}`}
                          style={{
                            padding: '6px 10px', borderRadius: 8,
                            background: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.3)',
                            color: '#D4AF37', fontSize: 10, fontWeight: 700, cursor: 'pointer',
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                          }}
                        ><Edit2 size={10} /> Edit</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}

      {/* Bundle rules */}
      <div style={card} data-testid="bundle-rules-card">
        <h3 style={{ fontSize: 12, color: '#D4AF37', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Zap size={14} /> Auto-Bundle Discount Rules
        </h3>
        <p style={{ fontSize: 11, color: '#8A8070', marginBottom: 10 }}>
          Applied automatically when a customer's active subscription count crosses the threshold. No admin action required.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {(data?.bundle_rules || []).map((r, i) => (
            <div key={i} data-testid={`rule-${r.min_services}`} style={{ padding: 12, borderRadius: 10, background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.2)' }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#22c55e', fontFamily: "'Cinzel',serif" }}>
                -{r.discount_pct}%
              </div>
              <div style={{ fontSize: 11, color: '#8A8070', marginTop: 4 }}>
                {r.min_services}+ active services
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Primitives */}
      <div style={card} data-testid="primitives-card">
        <h3 style={{ fontSize: 12, color: '#D4AF37', letterSpacing: '0.18em', textTransform: 'uppercase', fontWeight: 700, margin: '0 0 10px 0' }}>
          Free Primitives (Included with Any Recurring Service)
        </h3>
        <p style={{ fontSize: 11, color: '#8A8070', marginBottom: 10 }}>
          <AlertTriangle size={10} style={{ verticalAlign: '-1px', marginRight: 4, color: '#fb923c' }} />
          Bundled automatically. NOT included with one-off services (Genetic Repair).
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {primitives.map(p => (
            <div key={p.primitive_id} style={{ padding: '8px 14px', borderRadius: 8, background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)', color: '#22c55e', fontSize: 11, fontWeight: 600 }}>
              {p.name} · ${(p.cost_monthly || 0).toFixed(2)}/mo delivery cost
            </div>
          ))}
        </div>
      </div>

      {/* Edit modal */}
      {editing && (
        <div onClick={() => !saving && setEditing(null)} style={{ position: 'fixed', inset: 0, zIndex: 20000, background: 'rgba(5,5,10,0.8)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div onClick={e => e.stopPropagation()} data-testid="edit-modal" style={{ width: '100%', maxWidth: 520, background: 'linear-gradient(135deg, rgba(15,18,28,0.95) 0%, rgba(20,22,35,0.95) 100%)', border: '1px solid rgba(212,175,55,0.3)', borderRadius: 18, padding: 26, fontFamily: "'Jost',sans-serif", color: '#F4F4F4' }}>
            <h3 style={{ fontFamily: "'Cinzel',serif", fontSize: 18, margin: '0 0 18px 0', color: '#FFF' }}>Edit Service — {editing.service_id}</h3>
            <Field label="Service Name" value={editing.name} onChange={v => setEditing({ ...editing, name: v })} />
            <Field label="Description" value={editing.description} onChange={v => setEditing({ ...editing, description: v })} multiline />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Field label="Cost/mo ($)" value={editing.cost_monthly} onChange={v => setEditing({ ...editing, cost_monthly: v })} type="number" />
              <Field label="Price/mo ($)" value={editing.price_monthly} onChange={v => setEditing({ ...editing, price_monthly: v })} type="number" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 18 }}>
              {['live', 'beta', 'disabled'].map(s => (
                <button key={s} onClick={() => setEditing({ ...editing, status: s })}
                  style={{ padding: '8px', borderRadius: 8, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer',
                    background: editing.status === s ? 'rgba(212,175,55,0.2)' : 'transparent',
                    color: editing.status === s ? '#D4AF37' : '#8A8070',
                    border: `1px solid ${editing.status === s ? 'rgba(212,175,55,0.4)' : 'rgba(255,255,255,0.1)'}`
                  }}>{s}</button>
              ))}
            </div>
            <div style={{ fontSize: 11, color: '#8A8070', marginBottom: 14, padding: 10, background: 'rgba(34,197,94,0.06)', borderRadius: 8, border: '1px solid rgba(34,197,94,0.2)' }}>
              New margin: <strong style={{ color: '#22c55e' }}>
                {editing.price_monthly > 0 ? (((Number(editing.price_monthly) - Number(editing.cost_monthly)) / Number(editing.price_monthly)) * 100).toFixed(1) : 0}%
              </strong>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setEditing(null)} disabled={saving} data-testid="cancel-edit" style={{ flex: 1, padding: 10, borderRadius: 10, background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: '#8A8070', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
              <button onClick={saveEdit} disabled={saving} data-testid="save-edit" style={{ flex: 2, padding: 10, borderRadius: 10, background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)', border: 'none', color: '#0A0A0F', fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer' }}>
                {saving ? <Loader2 size={12} className="animate-spin" style={{ verticalAlign: 'middle' }} /> : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div style={{ padding: 12, borderRadius: 10, background: 'rgba(255,255,255,0.03)' }}>
      <div style={{ fontSize: 9, color: '#8A8070', letterSpacing: '0.16em', textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: color || '#FFF', marginTop: 4, fontFamily: "'Cinzel',serif" }}>{value}</div>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', multiline }) {
  const Tag = multiline ? 'textarea' : 'input';
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 9, color: '#8A8070', letterSpacing: '0.16em', textTransform: 'uppercase', fontWeight: 700, marginBottom: 5 }}>{label}</label>
      <Tag
        type={type}
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        rows={multiline ? 3 : undefined}
        style={{
          width: '100%', padding: '9px 12px', borderRadius: 8,
          background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(212,175,55,0.2)',
          color: '#F4F4F4', fontSize: 12, fontFamily: "'Jost',sans-serif",
          outline: 'none',
        }}
      />
    </div>
  );
}
