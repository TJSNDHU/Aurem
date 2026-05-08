/**
 * Admin Daily Log — iter 282m
 * ============================
 * Audit page for the Founder Daily Brief system. Shows the
 * daily_verification_log collection so we can confirm real vs. claimed
 * numbers from MongoDB / Stripe / Resend.
 *
 * Route: /admin/daily-log
 */
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, XCircle, Mail, RefreshCw, Zap } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const ORANGE = '#F97316';
const PANEL = 'rgba(255,255,255,0.03)';
const BORDER = 'rgba(255,255,255,0.06)';

const EVENT_LABELS = {
  morning_armed:      { label: 'Morning Armed',      time: '9:00 AM',  icon: '🌅' },
  scout_complete:     { label: 'Scout Complete',     time: '9:30 AM',  icon: '🔍' },
  architect_complete: { label: 'Architect Complete', time: '10:30 AM', icon: '🏗️' },
  midday_check:       { label: 'Midday Check',       time: '1:00 PM',  icon: '📊' },
  envoy_complete:     { label: 'Envoy Complete',     time: '2:30 PM',  icon: '📧' },
  end_of_day:         { label: 'End of Day',         time: '6:00 PM',  icon: '🌙' },
  end_of_day_email:   { label: 'EOD Email Sent',     time: '6:00 PM',  icon: '📨' },
};

export default function AdminDailyLog() {
  const [days, setDays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [info, setInfo] = useState('');

  const token = getPlatformToken();
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/admin/daily-log?days=14`, { headers });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setDays(d.days || []);
      setError('');
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line

  const fireTest = async (event) => {
    setBusy(event); setInfo('');
    try {
      const r = await fetch(`${API}/api/admin/daily-log/test-push/${event}`, {
        method: 'POST', headers,
      });
      const d = await r.json();
      setInfo(r.ok ? `✓ ${event} fired` : `Failed: ${d.detail || 'error'}`);
      load();
    } catch (e) { setInfo(`Failed: ${e}`); }
    finally { setBusy(''); }
  };

  const fireEod = async () => {
    setBusy('eod'); setInfo('');
    try {
      const r = await fetch(`${API}/api/admin/daily-log/run-eod`, {
        method: 'POST', headers,
      });
      const d = await r.json();
      setInfo(d.ok ? `✓ EOD email sent · resend_id=${d.resend_id}` : `Failed: ${d.error}`);
      load();
    } catch (e) { setInfo(`Failed: ${e}`); }
    finally { setBusy(''); }
  };

  return (
    <div className="portal-shell" style={{ minHeight: '100vh', padding: '32px 28px 80px' }}>
      <div className="portal-circuit" aria-hidden="true" />

      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 28 }}>
          <div>
            <div className="section-eyebrow">AUREM · Daily Verification</div>
            <h1 className="section-title" style={{ fontSize: 32, marginTop: 4 }}>
              Daily Brief Log
            </h1>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)', marginTop: 6 }}>
              Real numbers from MongoDB, Stripe, Resend. No mocks. Push → email pipeline.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Link to="/admin" className="btn-aurem-ghost" data-testid="back-admin">← Admin</Link>
            <button
              onClick={load}
              className="btn-aurem-ghost"
              data-testid="refresh-btn"
              disabled={loading}
            >
              <RefreshCw size={13} /> Refresh
            </button>
            <button
              onClick={fireEod}
              className="btn-aurem-primary"
              data-testid="run-eod-btn"
              disabled={busy === 'eod'}
            >
              <Mail size={13} /> {busy === 'eod' ? 'SENDING…' : 'Run EOD Email Now'}
            </button>
          </div>
        </div>

        {/* Test push fire row */}
        <div className="glass-card" style={{ padding: 18, marginBottom: 22 }}>
          <div className="section-eyebrow" style={{ marginBottom: 10 }}>Manual Test Fire</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(EVENT_LABELS).filter(([k]) => k !== 'end_of_day' && k !== 'end_of_day_email').map(([key, meta]) => (
              <button
                key={key}
                onClick={() => fireTest(key)}
                disabled={busy === key}
                data-testid={`test-${key}`}
                style={{
                  padding: '8px 14px', borderRadius: 8,
                  background: 'rgba(249,115,22,0.06)',
                  border: '1px solid rgba(249,115,22,0.18)',
                  color: '#FDBA74', fontSize: 12,
                  cursor: 'pointer',
                  opacity: busy === key ? 0.5 : 1,
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                }}
              >
                <Zap size={11} /> {meta.icon} {meta.label}
              </button>
            ))}
          </div>
          {info && (
            <div data-testid="action-info" style={{ marginTop: 10, fontSize: 12, color: info.startsWith('✓') ? '#86EFAC' : '#FCA5A5' }}>
              {info}
            </div>
          )}
        </div>

        {error && (
          <div className="glass-card" style={{ padding: 14, marginBottom: 20, borderColor: 'rgba(252,165,165,0.4)', color: '#FCA5A5' }}>
            {error}
          </div>
        )}

        {loading && (
          <div className="glass-card" style={{ padding: 22, textAlign: 'center', color: '#8A8070' }}>Loading verification log…</div>
        )}

        {!loading && days.length === 0 && !error && (
          <div className="glass-card" style={{ padding: 28, textAlign: 'center', color: '#8A8070' }}>
            No verification events recorded yet. Cron jobs run at 9 AM, 9:30, 10:30, 1 PM, 2:30, 6 PM EST.
          </div>
        )}

        {/* Per-day groups */}
        {days.map((day) => (
          <div key={day.date} data-testid={`day-${day.date}`} className="glass-card" style={{ padding: 22, marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div>
                <div style={{ fontFamily: "'Cinzel', serif", fontSize: 18, color: '#FFF' }}>{day.date}</div>
                <div style={{ fontSize: 11, color: '#8A8070', marginTop: 2, letterSpacing: '0.06em' }}>
                  {day.event_count} event{day.event_count === 1 ? '' : 's'}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gap: 8 }}>
              {day.events.map((ev, idx) => {
                const meta = EVENT_LABELS[ev.event] || { label: ev.event, icon: '·', time: '' };
                const verified = ev.all_verified !== false;
                return (
                  <div
                    key={idx}
                    data-testid={`event-${ev.event}-${idx}`}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      gap: 12, padding: '10px 14px', borderRadius: 10,
                      background: 'rgba(0,0,0,0.3)',
                      border: `1px solid ${verified ? 'rgba(34,197,94,0.18)' : 'rgba(252,165,165,0.25)'}`,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: 16 }}>{meta.icon}</span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 13, color: '#E8E0D0', fontWeight: 500 }}>{meta.label}</div>
                        <div style={{ fontSize: 11, color: '#5A5248', marginTop: 1, letterSpacing: '0.04em' }}>
                          {(ev.ts_utc || '').slice(11, 19)} UTC · {meta.time}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 11, color: '#8A8070', flexWrap: 'wrap' }}>
                      {ev.leads_real_count != null && <span>leads: <b style={{ color: ORANGE }}>{ev.leads_real_count}</b></span>}
                      {ev.rendered != null && <span>sites: <b style={{ color: ORANGE }}>{ev.http_verified}/{ev.rendered}</b></span>}
                      {ev.emails_sent != null && <span>email: <b style={{ color: ORANGE }}>{ev.emails_resend_confirmed}/{ev.emails_sent}</b></span>}
                      {ev.opens != null && <span>opens: <b style={{ color: ORANGE }}>{ev.opens}</b></span>}
                      {ev.clicks != null && <span>clicks: <b style={{ color: ORANGE }}>{ev.clicks}</b></span>}
                      {ev.signups_mongodb_count != null && <span>signups: <b style={{ color: ORANGE }}>{ev.signups_mongodb_count}</b></span>}
                      {ev.stripe_revenue_real != null && <span>$<b style={{ color: '#86EFAC' }}>{ev.stripe_revenue_real}</b></span>}
                      {verified
                        ? <CheckCircle2 size={14} color="#86EFAC" />
                        : <XCircle size={14} color="#FCA5A5" />}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
