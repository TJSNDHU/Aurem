/**
 * CustomerAppointments (iter D-84 §3) — upcoming + past bookings.
 * Real bin-scoped data: GET /api/customer/appointments. Honest empty-state.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Calendar, Loader2, Clock } from 'lucide-react';
import { GOLD, INK, PANEL, STROKE, TEXT_HI, TEXT_MD } from '../luxe/tokens';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

function Row({ a, upcoming }) {
  return (
    <div data-testid="appt-row" style={{ display: 'flex', gap: 12, padding: '13px 14px', borderTop: `1px solid ${STROKE}` }}>
      <span style={{ width: 34, height: 34, borderRadius: 9, flexShrink: 0, display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: upcoming ? 'rgba(74,212,160,0.12)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${upcoming ? 'rgba(74,212,160,0.35)' : STROKE}` }}>
        <Calendar size={15} color={upcoming ? '#4AD4A0' : TEXT_MD} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{a.with_whom}{a.channel ? <span style={{ color: TEXT_MD, fontWeight: 400 }}> · {a.channel}</span> : null}</div>
        {a.notes && <div style={{ fontSize: 12.5, color: TEXT_MD }}>{a.notes}</div>}
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 12.5, color: TEXT_HI }}>{(a.when || '').replace('T', ' ').slice(0, 16)}</div>
        <div style={{ fontSize: 11, color: TEXT_MD }}>{a.status}</div>
      </div>
    </div>
  );
}

export default function CustomerAppointments() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tok = getPlatformToken();
      const r = await fetch(`${API}/api/customer/appointments`, { headers: { Authorization: `Bearer ${tok}` } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) { setErr(String(e.message || e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const up = data?.upcoming || [];
  const past = data?.past || [];

  return (
    <div data-testid="customer-appointments" style={{ color: TEXT_HI }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Calendar size={22} color={GOLD} />
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Appointments</h1>
          <p style={{ fontSize: 13, color: TEXT_MD, margin: '2px 0 0' }}>Meetings ORA booked from your leads</p>
        </div>
      </div>

      {err && <div style={{ color: '#E0574F', fontSize: 13, marginBottom: 12 }} data-testid="appt-error">{err}</div>}

      {loading ? (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', color: TEXT_MD }}><Loader2 size={16} className="spin" /> Loading…</div>
      ) : (up.length + past.length === 0) ? (
        <div data-testid="appt-empty" style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 14, padding: 32, textAlign: 'center' }}>
          <Clock size={26} color={GOLD} style={{ marginBottom: 8 }} />
          <p style={{ fontSize: 14, margin: 0 }}>No appointments yet.</p>
          <p style={{ fontSize: 12.5, color: TEXT_MD, margin: '6px 0 0' }}>When a lead books a call, it appears here automatically.</p>
        </div>
      ) : (
        <>
          {up.length > 0 && (
            <div style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 14, overflow: 'hidden', marginBottom: 18 }}>
              <div style={{ padding: '12px 14px', fontSize: 11, color: '#4AD4A0', letterSpacing: '0.1em' }}>UPCOMING ({up.length})</div>
              {up.map((a, i) => <Row key={i} a={a} upcoming />)}
            </div>
          )}
          {past.length > 0 && (
            <div style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 14, overflow: 'hidden' }}>
              <div style={{ padding: '12px 14px', fontSize: 11, color: TEXT_MD, letterSpacing: '0.1em' }}>PAST ({past.length})</div>
              {past.map((a, i) => <Row key={i} a={a} upcoming={false} />)}
            </div>
          )}
        </>
      )}
      <style>{`.spin{animation:apspin 1s linear infinite}@keyframes apspin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
