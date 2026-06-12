/**
 * CustomerActivity (iter D-84 §1) — "Aaj ORA ne kya kiya" feed.
 * Real bin-scoped union from GET /api/customer/activity (scans, fixes, outreach,
 * leads, appointments). Honest empty-state when ORA hasn't acted yet.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Search, Wrench, Send, UserPlus, Calendar, Loader2, Sparkles } from 'lucide-react';
import { GOLD, INK, PANEL, STROKE, TEXT_HI, TEXT_MD } from '../luxe/tokens';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const ICONS = { scan: Search, fix: Wrench, outreach: Send, lead: UserPlus, appointment: Calendar };
const TINT = { scan: '#4A8FD4', fix: '#C9A227', outreach: '#4AD4A0', lead: '#9B6DD4', appointment: '#E0574F' };

export default function CustomerActivity() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async (before) => {
    setLoading(true);
    try {
      const tok = getPlatformToken();
      const url = `${API}/api/customer/activity?limit=30${before ? `&before=${encodeURIComponent(before)}` : ''}`;
      const r = await fetch(url, { headers: { Authorization: `Bearer ${tok}` } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setItems((prev) => before ? [...prev, ...(d.items || [])] : (d.items || []));
      setNext(d.next_before || null);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="customer-activity" style={{ color: TEXT_HI }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Activity size={22} color={GOLD} />
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>What ORA did</h1>
          <p style={{ fontSize: 13, color: TEXT_MD, margin: '2px 0 0' }}>Your autonomous business activity feed</p>
        </div>
      </div>

      {err && <div style={{ color: '#E0574F', fontSize: 13, marginBottom: 12 }} data-testid="activity-error">{err}</div>}

      {loading && items.length === 0 ? (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', color: TEXT_MD }}>
          <Loader2 size={16} className="spin" /> Loading…
        </div>
      ) : items.length === 0 ? (
        <div data-testid="activity-empty" style={{ background: PANEL, border: `1px solid ${STROKE}`, borderRadius: 14, padding: 32, textAlign: 'center' }}>
          <Sparkles size={28} color={GOLD} style={{ marginBottom: 10 }} />
          <p style={{ fontSize: 15, margin: 0 }}>ORA is warming up.</p>
          <p style={{ fontSize: 13, color: TEXT_MD, margin: '6px 0 0' }}>
            Once your scans, outreach and fixes begin, every action ORA takes shows up here in real time.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {items.map((it, i) => {
            const Ic = ICONS[it.type] || Activity;
            const tint = TINT[it.type] || GOLD;
            return (
              <button key={i} data-testid="activity-item"
                onClick={() => it.link && nav(it.link)}
                style={{ display: 'flex', gap: 14, alignItems: 'flex-start', textAlign: 'left',
                  padding: '13px 14px', background: 'transparent', border: 'none',
                  borderBottom: `1px solid ${STROKE}`, cursor: it.link ? 'pointer' : 'default', color: TEXT_HI }}>
                <span style={{ width: 32, height: 32, borderRadius: 9, flexShrink: 0, display: 'flex',
                  alignItems: 'center', justifyContent: 'center', background: `${tint}1A`, border: `1px solid ${tint}44` }}>
                  <Ic size={15} color={tint} />
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, display: 'block' }}>{it.title}</span>
                  {it.detail && <span style={{ fontSize: 12.5, color: TEXT_MD }}>{it.detail}</span>}
                </span>
                <span style={{ fontSize: 11, color: TEXT_MD, whiteSpace: 'nowrap' }}>
                  {(it.ts || '').replace('T', ' ').slice(0, 16)}
                </span>
              </button>
            );
          })}
          {next && (
            <button data-testid="activity-more" onClick={() => load(next)} disabled={loading}
              style={{ marginTop: 14, padding: '10px', borderRadius: 10, background: 'transparent',
                border: `1px solid ${STROKE}`, color: GOLD, fontSize: 13, cursor: 'pointer' }}>
              {loading ? 'Loading…' : 'Show more'}
            </button>
          )}
        </div>
      )}
      <style>{`.spin{animation:aspin 1s linear infinite}@keyframes aspin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
