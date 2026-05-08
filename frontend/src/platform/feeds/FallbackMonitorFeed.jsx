/**
 * 8.12 Fallback Monitor — reads fallback_usage_log
 */
import { useEffect, useState, useCallback } from 'react';
import useLivePolling from '../../hooks/useLivePolling';
import { Shield, RefreshCw, AlertTriangle, TrendingDown } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

export default function FallbackMonitorFeed({ token }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = source ? `?limit=200&source=${source}` : '?limit=200';
      const res = await fetch(`${API}/api/dashboard-feeds/fallback-monitor${qs}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const j = await res.json();
      setRows(j.events || []);
      setSummary(j.summary || {});
    } catch (e) {
      console.error('fallback-monitor load failed', e);
    } finally {
      setLoading(false);
    }
  }, [token, source]);

  useEffect(() => { load(); }, [load]);
  // iter 270 — live refresh every 15s
  useLivePolling(load, 15000);

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="fallback-monitor-feed">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Shield className="w-7 h-7 text-[#FF6B00]" />
            <div>
              <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Fallback Monitor</h1>
              <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>
                Every time a primary service fell back to its backup (Scout→Dark Scout, WhatsApp→SMS, etc.)
              </p>
            </div>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition"
            style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00' }}
            data-testid="fallback-monitor-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard label="Fallbacks (24h)" value={summary.last_24h ?? 0} color="#FF6B00" testid="fb-stat-24h"
                    icon={<AlertTriangle className="w-4 h-4 text-[#FF6B00]" />} />
          <StatCard label="All Time" value={summary.total_all_time ?? 0} color="#3b82f6" testid="fb-stat-total" />
          <StatCard label="Sources Affected (7d)" value={(summary.by_source_7d || []).length} color="#16a34a" testid="fb-stat-sources" />
        </div>

        {/* By-source chips */}
        {summary.by_source_7d && summary.by_source_7d.length > 0 && (
          <div className="aurem-glass-card p-4 mb-6" data-testid="fallback-by-source">
            <div className="text-xs uppercase tracking-wider mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
              By source — last 7 days
            </div>
            <div className="flex flex-wrap gap-2">
              {summary.by_source_7d.map((s) => (
                <button
                  key={s.source}
                  onClick={() => setSource(source === s.source ? '' : s.source)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition"
                  style={{
                    background: source === s.source ? 'rgba(255,107,0,0.25)' : 'rgba(255,255,255,0.06)',
                    color: source === s.source ? '#FF6B00' : 'var(--aurem-heading)',
                    border: source === s.source ? '1px solid #FF6B00' : '1px solid rgba(255,255,255,0.1)',
                  }}
                  data-testid={`fallback-chip-${s.source}`}
                >
                  <TrendingDown className="w-3 h-3" />
                  {s.source}
                  <span className="opacity-70">· {s.count}</span>
                </button>
              ))}
              {source && (
                <button
                  onClick={() => setSource('')}
                  className="px-3 py-1.5 rounded-full text-xs"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--aurem-body-secondary)' }}
                  data-testid="fallback-clear-filter"
                >
                  Clear filter
                </button>
              )}
            </div>
          </div>
        )}

        <div className="aurem-glass-card overflow-hidden">
          <table className="w-full text-sm" data-testid="fallback-monitor-table">
            <thead>
              <tr style={{ background: 'rgba(255,107,0,0.08)', color: 'var(--aurem-heading)' }}>
                <th className="text-left px-4 py-3 font-medium">Source</th>
                <th className="text-left px-4 py-3 font-medium">From → To</th>
                <th className="text-left px-4 py-3 font-medium">Reason</th>
                <th className="text-left px-4 py-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={4} className="text-center py-10" style={{ color: 'var(--aurem-body-secondary)' }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={4} className="text-center py-10" style={{ color: 'var(--aurem-body-secondary)' }}>
                  No fallback events yet — your primary services are all healthy.
                </td></tr>
              )}
              {!loading && rows.map((e, i) => (
                <tr key={i} className="border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: 'var(--aurem-heading)' }}>{e.source || '—'}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {e.from_service ? (
                      <>
                        <span style={{ color: 'var(--aurem-heading)' }}>{e.from_service}</span>
                        <span className="mx-2 opacity-60">→</span>
                        <span className="text-[#FF6B00]">{e.to_service || '—'}</span>
                      </>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {e.reason || JSON.stringify(e.details || {}).slice(0, 80) || '—'}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{fmtDate(e.triggered_at)}</td>
                </tr>
              ))}
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
