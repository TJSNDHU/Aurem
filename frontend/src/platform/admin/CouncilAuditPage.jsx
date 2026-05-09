/**
 * CouncilAuditPage — SOC2 evidence audit feed for council_decisions_detailed.
 * ===========================================================================
 * Reads:
 *   GET /api/admin/autonomous/recent-decisions?limit=...&action=...&verdict=...
 *
 * Filters: action (regex), verdict (APPROVED|REJECTED), limit.
 * CSV export from current view (no server hit — exports what's on screen).
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  ShieldCheck, Search, Filter, Download, RefreshCw, CheckCircle2, XCircle,
} from 'lucide-react';

const API = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

const getAdminToken = () =>
  sessionStorage.getItem('platform_token') ||
  localStorage.getItem('platform_token') ||
  localStorage.getItem('aurem_admin_token') ||
  sessionStorage.getItem('aurem_admin_token') ||
  localStorage.getItem('token') ||
  '';

const fetchJSON = async (path) => {
  const t = getAdminToken();
  const r = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return r.json();
};

const COMP_BG = '#0E0E0F';
const COMP_BORDER = '#22201D';
const ACCENT = '#D4AF7A';

const fmtTs = (ts) => {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return isNaN(d) ? String(ts) : d.toISOString().replace('T', ' ').slice(0, 19);
  } catch { return String(ts); }
};

const downloadCSV = (rows) => {
  if (!rows?.length) return;
  const headers = ['ts', 'action', 'requesting_agent', 'verdict', 'confidence', 'rejected_by', 'votes'];
  const csvRows = [headers.join(',')];
  for (const r of rows) {
    const votes = JSON.stringify(r.votes || {}).replace(/"/g, '""');
    const line = [
      r.ts || '',
      `"${(r.action || '').replace(/"/g, '""')}"`,
      `"${(r.requesting_agent || '').replace(/"/g, '""')}"`,
      r.verdict || '',
      r.confidence ?? '',
      r.rejected_by || '',
      `"${votes}"`,
    ].join(',');
    csvRows.push(line);
  }
  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `council-audit-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};

export default function CouncilAuditPage() {
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [actionQ, setActionQ] = useState('');
  const [verdictQ, setVerdictQ] = useState('');
  const [limit, setLimit] = useState(50);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setErr('');
      const params = new URLSearchParams();
      params.set('limit', String(limit));
      if (actionQ) params.set('action', actionQ);
      if (verdictQ) params.set('verdict', verdictQ);
      const res = await fetchJSON(`/api/admin/autonomous/recent-decisions?${params}`);
      setRows(res.rows || []);
      setCount(res.count || 0);
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [actionQ, verdictQ, limit]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div data-testid="council-audit-page" style={{
      padding: 24, minHeight: '100vh', background: '#08080A', color: '#E8E2D4',
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto',
    }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{
          fontSize: 'clamp(20px, 3.5vw, 28px)', margin: 0, fontWeight: 600,
          letterSpacing: '-0.01em',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <ShieldCheck size={24} color={ACCENT} />
          Council Audit Trail
        </h1>
        <p style={{ color: '#8B8475', margin: '6px 0 0 0', fontSize: 13 }}>
          SOC2 evidence feed of council_decisions_detailed. Filter, inspect, export.
        </p>
      </header>

      {/* Filters */}
      <section style={{
        background: COMP_BG, border: `1px solid ${COMP_BORDER}`,
        borderRadius: 10, padding: 14, marginBottom: 16,
        display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: '1 1 200px' }}>
          <Search size={14} color={ACCENT} />
          <input
            data-testid="filter-action"
            placeholder="Filter by action (regex, e.g. hunter|followup|repair)"
            value={actionQ}
            onChange={(e) => setActionQ(e.target.value)}
            style={{
              flex: 1, padding: '6px 10px', background: '#1A1814',
              border: `1px solid ${COMP_BORDER}`, color: '#E8E2D4',
              borderRadius: 6, fontSize: 13, outline: 'none',
            }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Filter size={14} color={ACCENT} />
          <select
            data-testid="filter-verdict"
            value={verdictQ}
            onChange={(e) => setVerdictQ(e.target.value)}
            style={{
              padding: '6px 10px', background: '#1A1814',
              border: `1px solid ${COMP_BORDER}`, color: '#E8E2D4',
              borderRadius: 6, fontSize: 13, outline: 'none',
            }}
          >
            <option value="">all verdicts</option>
            <option value="APPROVED">APPROVED</option>
            <option value="REJECTED">REJECTED</option>
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#8B8475', fontSize: 12 }}>limit</span>
          <select
            data-testid="filter-limit"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            style={{
              padding: '6px 10px', background: '#1A1814',
              border: `1px solid ${COMP_BORDER}`, color: '#E8E2D4',
              borderRadius: 6, fontSize: 13, outline: 'none',
            }}
          >
            {[25, 50, 100, 200].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <button
          data-testid="council-audit-refresh"
          onClick={refresh}
          style={{
            padding: '6px 12px', background: 'transparent',
            border: `1px solid ${ACCENT}`, color: ACCENT,
            borderRadius: 6, fontSize: 12, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
        <button
          data-testid="council-audit-export"
          onClick={() => downloadCSV(rows)}
          disabled={!rows.length}
          style={{
            padding: '6px 12px', background: ACCENT, color: '#08080A',
            border: 'none', borderRadius: 6, fontSize: 12,
            cursor: rows.length ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', gap: 4,
            opacity: rows.length ? 1 : 0.5,
          }}
        >
          <Download size={12} /> Export CSV ({count})
        </button>
      </section>

      {err && (
        <div data-testid="council-audit-error" style={{
          padding: 12, background: '#2A1612', border: '1px solid #5A2A20',
          color: '#E0524A', borderRadius: 8, marginBottom: 16, fontSize: 13,
        }}>
          {err}
        </div>
      )}

      {/* Table */}
      <section style={{
        background: COMP_BG, border: `1px solid ${COMP_BORDER}`,
        borderRadius: 10, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '160px minmax(180px, 1.2fr) 140px 110px 80px minmax(180px, 1.5fr)',
          padding: '10px 14px', background: '#14130F',
          borderBottom: `1px solid ${COMP_BORDER}`,
          color: '#8B8475', fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}>
          <div>Timestamp</div>
          <div>Action</div>
          <div>Agent</div>
          <div>Verdict</div>
          <div>Conf</div>
          <div>Votes</div>
        </div>
        {loading && (
          <div style={{ padding: 20, color: '#8B8475', fontSize: 13 }}>Loading…</div>
        )}
        {!loading && !rows.length && (
          <div style={{ padding: 20, color: '#8B8475', fontSize: 13 }}>
            No council decisions match the current filters.
          </div>
        )}
        {!loading && rows.map((r, i) => (
          <div
            key={`${r.ts}-${i}`}
            data-testid={`council-row-${i}`}
            style={{
              display: 'grid',
              gridTemplateColumns: '160px minmax(180px, 1.2fr) 140px 110px 80px minmax(180px, 1.5fr)',
              padding: '10px 14px',
              borderBottom: i < rows.length - 1 ? `1px solid ${COMP_BORDER}` : 'none',
              fontSize: 12, alignItems: 'start',
            }}
          >
            <div style={{ color: '#8B8475', fontFamily: 'monospace' }}>
              {fmtTs(r.ts)}
            </div>
            <div style={{ color: '#E8E2D4' }}>
              {r.action || '—'}
            </div>
            <div style={{ color: ACCENT }}>
              {r.requesting_agent || '—'}
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              color: r.verdict === 'APPROVED' ? '#4AD4A0' :
                     r.verdict === 'REJECTED' ? '#E0524A' : '#8B8475',
              fontWeight: 600,
            }}>
              {r.verdict === 'APPROVED' ? <CheckCircle2 size={12} /> :
               r.verdict === 'REJECTED' ? <XCircle size={12} /> : null}
              {r.verdict || '—'}
            </div>
            <div style={{ color: '#E8E2D4' }}>
              {r.confidence?.toFixed?.(2) ?? '—'}
            </div>
            <div style={{ color: '#8B8475', fontSize: 11, fontFamily: 'monospace' }}>
              {Object.entries(r.votes || {}).map(([voter, v]) => (
                <div key={voter} style={{
                  display: 'flex', gap: 4, alignItems: 'baseline',
                }}>
                  <span style={{ color: '#5A5648', minWidth: 60 }}>{voter}:</span>
                  <span style={{
                    color: v?.vote === 'APPROVE' ? '#4AD4A0' :
                           v?.vote === 'REJECT' ? '#E0524A' : '#E8E2D4',
                  }}>{v?.vote || '?'}</span>
                  <span style={{ color: '#5A5648' }}>
                    {(v?.reason || '').slice(0, 60)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      <footer style={{ marginTop: 16, color: '#5A5648', fontSize: 11 }}>
        Showing {rows.length} of {count} decisions · Source:
        <code style={{ color: ACCENT, marginLeft: 4 }}>db.council_decisions_detailed</code>
      </footer>
    </div>
  );
}
