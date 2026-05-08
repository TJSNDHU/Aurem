/**
 * ORA Self-Heal Status Widget — Mission Control SYSTEM section.
 *
 * Polls /api/admin/ora-health/status every 30s and renders the 5 watched
 * services as colored dots (green/yellow/red), plus the last incident.
 *
 * iter 281.1 — Phase 2.1
 */
import React, { useEffect, useState, useCallback } from 'react';
import { ShieldCheck, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const STATUS_COLOR = {
  green:  '#22c55e',
  yellow: '#f59e0b',
  red:    '#ef4444',
  unknown:'#6b7280',
};

const SERVICE_LABEL = {
  stripe: 'Stripe',
  mongo:  'MongoDB',
  twilio: 'Twilio',
  redis:  'Redis',
  ora:    'ORA',
};

function fmtAgo(iso) {
  if (!iso) return 'never';
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 0 || isNaN(ms)) return '—';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

export default function OraSelfHealWidget({ token }) {
  const [data, setData] = useState({ rollup_status: 'unknown', services: {}, incidents: [] });
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/admin/ora-health/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (r.ok) setData(await r.json());
    } catch (_) { /* swallow */ }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  const runNow = async () => {
    if (!token) return;
    setRunning(true);
    try {
      await fetch(`${API_URL}/api/admin/ora-health/run-now`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      await load();
    } catch (_) { /* swallow */ }
    setRunning(false);
  };

  const order = ['stripe', 'mongo', 'twilio', 'redis', 'ora'];
  const rollup = data.rollup_status || 'unknown';
  const lastIncident = (data.incidents || [])[0] || null;

  return (
    <div
      data-testid="ora-self-heal-widget"
      className="rounded-xl p-4 border"
      style={{
        background: 'rgba(15,18,28,0.6)',
        borderColor: 'rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} style={{ color: STATUS_COLOR[rollup] || STATUS_COLOR.unknown }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--aurem-heading, #fff)' }}>
            ORA Self-Heal
          </span>
          <span
            data-testid="ora-self-heal-rollup"
            className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase"
            style={{
              background: `${STATUS_COLOR[rollup]}22`,
              color: STATUS_COLOR[rollup],
              border: `1px solid ${STATUS_COLOR[rollup]}55`,
            }}
          >
            {rollup}
          </span>
        </div>
        <button
          data-testid="ora-self-heal-run-now"
          onClick={runNow}
          disabled={running}
          title="Force health check now"
          className="flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-1 rounded"
          style={{
            background: 'rgba(212,175,55,0.08)',
            color: '#D4AF37',
            border: '1px solid rgba(212,175,55,0.25)',
            cursor: running ? 'wait' : 'pointer',
            fontWeight: 700,
          }}
        >
          <RefreshCw size={11} className={running ? 'animate-spin' : ''} />
          {running ? 'Checking…' : 'Check now'}
        </button>
      </div>

      {loading ? (
        <div className="text-[11px]" style={{ color: 'var(--aurem-body-secondary, #8A8070)' }}>
          Loading watchdog status…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-5 gap-2 mb-3">
            {order.map((key) => {
              const s = data.services?.[key] || { status: 'unknown', last_check: null };
              const color = STATUS_COLOR[s.status] || STATUS_COLOR.unknown;
              return (
                <div
                  key={key}
                  data-testid={`ora-self-heal-service-${key}`}
                  className="rounded-lg p-2 text-center"
                  style={{ background: `${color}10`, border: `1px solid ${color}40` }}
                  title={s.reason || ''}
                >
                  <div className="flex items-center justify-center gap-1 mb-1">
                    <span
                      className="inline-block rounded-full"
                      style={{ width: 8, height: 8, background: color }}
                    />
                    <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color }}>
                      {s.status}
                    </span>
                  </div>
                  <div className="text-[10px] font-medium" style={{ color: 'var(--aurem-heading, #fff)' }}>
                    {SERVICE_LABEL[key]}
                  </div>
                  <div className="text-[9px] mt-0.5" style={{ color: 'var(--aurem-body-secondary, #8A8070)' }}>
                    {fmtAgo(s.last_check)}
                  </div>
                </div>
              );
            })}
          </div>

          <div
            className="text-[10px] pt-2 border-t flex items-center justify-between"
            style={{ borderColor: 'rgba(255,255,255,0.06)', color: 'var(--aurem-body-secondary, #8A8070)' }}
          >
            <span>
              {lastIncident ? (
                <>
                  Last incident:&nbsp;
                  <span style={{ color: STATUS_COLOR[lastIncident.to_status] || '#fff' }}>
                    {SERVICE_LABEL[lastIncident.service] || lastIncident.service}
                  </span>
                  &nbsp;{lastIncident.from_status} → {lastIncident.to_status}
                  &nbsp;<span style={{ opacity: 0.7 }}>· {fmtAgo(lastIncident.ts)}</span>
                </>
              ) : (
                'No incidents recorded'
              )}
            </span>
            <span>Polls every 5 min</span>
          </div>
        </>
      )}
    </div>
  );
}
