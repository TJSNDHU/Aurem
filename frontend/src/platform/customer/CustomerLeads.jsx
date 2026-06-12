/**
 * CustomerLeads (iter D-84 §2) — pipeline funnel + leads table.
 * Real bin-scoped data: GET /api/customer/leads/funnel + /api/customer/leads.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Target, Loader2, Users } from 'lucide-react';
import { GOLD, INK, PANEL, STROKE, TEXT_HI, TEXT_MD } from '../luxe/tokens';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const STAGES = [
  { key: 'found', label: 'Found', color: '#4A8FD4' },
  { key: 'contacted', label: 'Contacted', color: '#C9A227' },
  { key: 'replied', label: 'Replied', color: '#9B6DD4' },
  { key: 'booked', label: 'Booked', color: '#4AD4A0' },
];

export default function CustomerLeads() {
  const [funnel, setFunnel] = useState(null);
  const [leads, setLeads] = useState([]);
  const [stage, setStage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const tok = getPlatformToken();
  const get = useCallback(async (path) => {
    const r = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${tok}` } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }, [tok]);

  const load = useCallback(async (st) => {
    setLoading(true);
    try {
      const [f, l] = await Promise.all([
        get('/api/customer/leads/funnel'),
        get(`/api/customer/leads${st ? `?stage=${st}` : ''}`),
      ]);
      setFunnel(f); setLeads(l.leads || []);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setLoading(false); }
  }, [get]);

  useEffect(() => { load(null); }, [load]);

  const pickStage = (st) => { const ns = stage === st ? null : st; setStage(ns); load(ns); };
  const maxCount = Math.max(1, ...(funnel?.funnel || []).map((s) => s.count));

  return (
    <div data-testid="customer-leads" style={{ color: TEXT_HI }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Target size={22} color={GOLD} />
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Leads & Pipeline</h1>
          <p style={{ fontSize: 13, color: TEXT_MD, margin: '2px 0 0' }}>Prospects ORA is hunting for you</p>
        </div>
      </div>

      {err && <div style={{ color: '#E0574F', fontSize: 13, marginBottom: 12 }} data-testid="leads-error">{err}</div>}

      {loading && !funnel ? (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', color: TEXT_MD }}><Loader2 size={16} className="spin" /> Loading…</div>
      ) : (
        <>
          {/* Funnel */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 10, marginBottom: 22 }}>
            {STAGES.map((s) => {
              const c = (funnel?.funnel || []).find((x) => x.stage === s.key)?.count || 0;
              const active = stage === s.key;
              return (
                <button key={s.key} data-testid={`funnel-${s.key}`} onClick={() => pickStage(s.key)}
                  style={{ textAlign: 'left', background: active ? `${s.color}1A` : PANEL,
                    border: `1px solid ${active ? s.color : STROKE}`, borderRadius: 12, padding: 14, cursor: 'pointer' }}>
                  <div style={{ fontSize: 11, color: s.color, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{s.label}</div>
                  <div style={{ fontSize: 30, fontWeight: 800, color: TEXT_HI }}>{c}</div>
                  <div style={{ height: 4, borderRadius: 3, marginTop: 6, background: 'rgba(255,255,255,0.06)' }}>
                    <div style={{ height: '100%', width: `${(c / maxCount) * 100}%`, background: s.color, borderRadius: 3 }} />
                  </div>
                </button>
              );
            })}
          </div>

          {/* Table / empty */}
          {leads.length === 0 ? (
            <div data-testid="leads-empty" style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 14, padding: 32, textAlign: 'center' }}>
              <Users size={26} color={GOLD} style={{ marginBottom: 8 }} />
              <p style={{ fontSize: 14, margin: 0 }}>{stage ? `No leads in “${stage}” yet.` : 'No leads yet.'}</p>
              <p style={{ fontSize: 12.5, color: TEXT_MD, margin: '6px 0 0' }}>ORA sources prospects automatically once your hunt is configured.</p>
            </div>
          ) : (
            <div style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 14, overflow: 'hidden' }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead><tr style={{ color: TEXT_MD, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    <th style={th}>Business</th><th style={th}>Source</th><th style={th}>Stage</th><th style={th}>Last touch</th>
                  </tr></thead>
                  <tbody>
                    {leads.map((l, i) => {
                      const sc = STAGES.find((s) => s.key === l.stage)?.color || GOLD;
                      return (
                        <tr key={i} data-testid="lead-row" style={{ borderTop: `1px solid ${STROKE}` }}>
                          <td style={{ ...td, fontWeight: 600 }}>{l.business_name}{l.contact_name ? <span style={{ color: TEXT_MD, fontWeight: 400 }}> · {l.contact_name}</span> : null}</td>
                          <td style={{ ...td, color: TEXT_MD }}>{l.source}</td>
                          <td style={td}><span style={{ color: sc, fontSize: 11, fontWeight: 700 }}>{l.stage}</span></td>
                          <td style={{ ...td, color: TEXT_MD }}>{(l.last_touch || '').slice(0, 10)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
      <style>{`.spin{animation:lspin 1s linear infinite}@keyframes lspin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
const th = { textAlign: 'left', padding: '11px 14px', fontWeight: 600 };
const td = { padding: '11px 14px', color: TEXT_HI };
