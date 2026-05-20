/**
 * 6.5 / 12.2 Call Logs — reads voice_calls collection
 */
import { useEffect, useState, useCallback } from 'react';
import useLivePolling from '../../hooks/useLivePolling';
import { Phone, RefreshCw, Radio, Smile, Meh, Frown, Search } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};
const fmtDur = (s) => {
  if (!s) return '—';
  const m = Math.floor(s / 60); const ss = s % 60;
  return `${m}m ${ss}s`;
};

const sentimentIcon = (s) => {
  if (s === 'positive') return <Smile className="size-4 text-green-500" />;
  if (s === 'neutral') return <Meh className="size-4 text-yellow-500" />;
  if (s === 'negative') return <Frown className="size-4 text-red-500" />;
  return <span className="text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>—</span>;
};

const statusColor = (s) => {
  if (s === 'active') return { bg: 'rgba(59,130,246,0.18)', fg: '#3b82f6' };
  if (s === 'queued') return { bg: 'rgba(234,179,8,0.18)', fg: '#eab308' };
  if (s === 'completed') return { bg: 'rgba(22,163,74,0.18)', fg: '#16a34a' };
  return { bg: 'rgba(255,255,255,0.06)', fg: 'rgba(255,255,255,0.5)' };
};

export default function CallLogsFeed({ token }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [status, setStatus] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = status ? `?limit=200&status=${status}` : '?limit=200';
      const res = await fetch(`${API}/api/dashboard-feeds/call-logs${qs}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setRows(data.logs || []);
      setSummary(data.summary || {});
    } catch (e) {
      console.error('call-logs load failed', e);
    } finally {
      setLoading(false);
    }
  }, [token, status]);

  useEffect(() => { load(); }, [load]);
  // iter 270 — live refresh every 15s
  useLivePolling(load, 15000);

  const filtered = rows.filter(r =>
    !filter ||
    (r.caller_phone || '').toLowerCase().includes(filter.toLowerCase()) ||
    (r.persona_name || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="call-logs-feed">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Phone className="size-7 text-[#FF6B00]" />
            <div>
              <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Call Logs</h1>
              <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>
                Live voice call records from ORA voice agents
              </p>
            </div>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition"
            style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00' }}
            data-testid="call-logs-refresh"
          >
            <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="Completed (24h)" value={summary.completed_24h ?? 0} color="#16a34a" testid="call-stat-completed" />
          <StatCard label="Active Now" value={summary.active ?? 0} color="#3b82f6" testid="call-stat-active" icon={<Radio className="size-4 text-blue-400 animate-pulse" />} />
          <StatCard label="Queued" value={summary.queued ?? 0} color="#eab308" testid="call-stat-queued" />
          <StatCard label="All Time" value={summary.total_all_time ?? 0} color="#FF6B00" testid="call-stat-total" />
        </div>

        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--aurem-body-secondary)' }} />
            <input
              type="text"
              placeholder="Search by phone or persona…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              data-testid="call-logs-search"
              className="w-full pl-10 pr-3 py-2 rounded-lg text-sm border"
              style={{ background: 'rgba(0,0,0,0.2)', borderColor: 'rgba(255,255,255,0.1)', color: 'var(--aurem-heading)' }}
            />
          </div>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            data-testid="call-logs-status-filter"
            className="px-3 py-2 rounded-lg text-sm border"
            style={{ background: 'rgba(0,0,0,0.2)', borderColor: 'rgba(255,255,255,0.1)', color: 'var(--aurem-heading)' }}
          >
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="active">Active</option>
            <option value="queued">Queued</option>
          </select>
        </div>

        <div className="aurem-glass-card overflow-hidden">
          <table className="w-full text-sm" data-testid="call-logs-table">
            <thead>
              <tr style={{ background: 'rgba(255,107,0,0.08)', color: 'var(--aurem-heading)' }}>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Caller</th>
                <th className="text-left px-4 py-3 font-medium">Persona</th>
                <th className="text-left px-4 py-3 font-medium">Direction</th>
                <th className="text-left px-4 py-3 font-medium">Mood</th>
                <th className="text-left px-4 py-3 font-medium">Duration</th>
                <th className="text-left px-4 py-3 font-medium">Action</th>
                <th className="text-left px-4 py-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} className="text-center py-10" style={{ color: 'var(--aurem-body-secondary)' }}>Loading…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={8} className="text-center py-10" style={{ color: 'var(--aurem-body-secondary)' }}>
                  No calls yet.
                </td></tr>
              )}
              {!loading && filtered.map((r, i) => {
                const sc = statusColor(r.status);
                return (
                  <tr key={i} className="border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium uppercase" style={{ background: sc.bg, color: sc.fg }}>
                        {r.status || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--aurem-heading)' }}>{r.caller_phone || '—'}</td>
                    <td className="px-4 py-3" style={{ color: 'var(--aurem-heading)' }}>{r.persona_name || '—'}</td>
                    <td className="px-4 py-3 capitalize text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{r.direction || '—'}</td>
                    <td className="px-4 py-3">{sentimentIcon(r.sentiment)}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-heading)' }}>{fmtDur(r.duration_seconds)}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                      {(r.actions_taken && r.actions_taken[0]) || '—'}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{fmtDate(r.started_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, testid, icon }) {
  return (
    <div className="aurem-glass-card p-4" data-testid={testid}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>
        {icon}{label}
      </div>
      <div className="text-3xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}
