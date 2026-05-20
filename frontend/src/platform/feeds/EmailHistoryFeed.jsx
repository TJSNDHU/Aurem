/**
 * 6.3 Email History — reads email_logs
 */
import { useEffect, useState, useCallback } from 'react';
import useLivePolling from '../../hooks/useLivePolling';
import { Mail, RefreshCw, CheckCircle2, XCircle, Search } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

export default function EmailHistoryFeed({ token }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [status, setStatus] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = status ? `?limit=200&status=${status}` : '?limit=200';
      const res = await fetch(`${API}/api/dashboard-feeds/email-history${qs}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setRows(data.logs || []);
      setSummary(data.summary || {});
    } catch (e) {
      console.error('email-history load failed', e);
    } finally {
      setLoading(false);
    }
  }, [token, status]);

  useEffect(() => { load(); }, [load]);
  // iter 270 — live refresh every 20s
  useLivePolling(load, 20000);

  const filtered = rows.filter(r =>
    !filter ||
    (r.to || '').toLowerCase().includes(filter.toLowerCase()) ||
    (r.subject || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="email-history-feed">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Mail className="size-7 text-[#FF6B00]" />
            <div>
              <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Email History</h1>
              <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>
                Every outbound email logged from Resend engine
              </p>
            </div>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition"
            style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00' }}
            data-testid="email-history-refresh"
          >
            <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Summary chips */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard label="Sent (24h)" value={summary.sent_24h ?? 0} color="#16a34a" testid="email-stat-sent" />
          <StatCard label="Failed (24h)" value={summary.failed_24h ?? 0} color="#dc2626" testid="email-stat-failed" />
          <StatCard label="All Time" value={summary.total_all_time ?? 0} color="#FF6B00" testid="email-stat-total" />
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--aurem-body-secondary)' }} />
            <input
              type="text"
              placeholder="Search by recipient or subject…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              data-testid="email-history-search"
              className="w-full pl-10 pr-3 py-2 rounded-lg text-sm border"
              style={{ background: 'rgba(0,0,0,0.2)', borderColor: 'rgba(255,255,255,0.1)', color: 'var(--aurem-heading)' }}
            />
          </div>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            data-testid="email-history-status-filter"
            className="px-3 py-2 rounded-lg text-sm border"
            style={{ background: 'rgba(0,0,0,0.2)', borderColor: 'rgba(255,255,255,0.1)', color: 'var(--aurem-heading)' }}
          >
            <option value="">All statuses</option>
            <option value="success">Sent</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {/* Table */}
        <div className="aurem-glass-card overflow-hidden">
          <table className="w-full text-sm" data-testid="email-history-table">
            <thead>
              <tr style={{ background: 'rgba(255,107,0,0.08)', color: 'var(--aurem-heading)' }}>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Recipient</th>
                <th className="text-left px-4 py-3 font-medium">Subject</th>
                <th className="text-left px-4 py-3 font-medium">Engine</th>
                <th className="text-left px-4 py-3 font-medium">Sent At</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5} className="text-center py-10" style={{ color: 'var(--aurem-body-secondary)' }}>Loading…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={5} className="text-center py-10" style={{ color: 'var(--aurem-body-secondary)' }}>
                  No emails yet. Once Resend sends an email, it will show here.
                </td></tr>
              )}
              {!loading && filtered.map((r, i) => (
                <tr key={i} className="border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                  <td className="px-4 py-3">
                    {r.success
                      ? <CheckCircle2 className="size-5 text-green-500" />
                      : <XCircle className="size-5 text-red-500" title={r.error} />}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--aurem-heading)' }}>{r.to || '—'}</td>
                  <td className="px-4 py-3 truncate max-w-md" style={{ color: 'var(--aurem-heading)' }}>{r.subject || '—'}</td>
                  <td className="px-4 py-3 text-xs uppercase" style={{ color: 'var(--aurem-body-secondary)' }}>{r.engine || 'resend'}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{fmtDate(r.sent_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, testid }) {
  return (
    <div className="aurem-glass-card p-4" data-testid={testid}>
      <div className="text-xs uppercase tracking-wider mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</div>
      <div className="text-3xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}
