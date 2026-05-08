/**
 * Dark Scout Intelligence — AUREM Layer 3 Intelligence Dashboard
 * Trigger investigations, view history, monitor brand threats
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield, Search, AlertTriangle, Eye, Globe, Activity,
  ChevronDown, ChevronRight, RefreshCw, Send, Clock,
  CheckCircle, XCircle, Loader2, Lock
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const RISK_COLORS = {
  CRITICAL: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
  HIGH: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  MEDIUM: { color: '#D4AF37', bg: 'rgba(212,175,55,0.1)' },
  LOW: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)' },
  UNKNOWN: { color: '#6b7280', bg: 'rgba(107,114,128,0.1)' },
};

const PRESETS = [
  { id: 'brand_monitor', name: 'Brand Monitor', icon: Eye },
  { id: 'competitor_intel', name: 'Competitor Intel', icon: Globe },
  { id: 'breach_detection', name: 'Breach Detection', icon: Lock },
  { id: 'threat_landscape', name: 'Threat Landscape', icon: AlertTriangle },
];

const DarkScoutDashboard = ({ token }) => {
  const [status, setStatus] = useState(null);
  const [investigations, setInvestigations] = useState([]);
  const [invTotal, setInvTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [preset, setPreset] = useState('brand_monitor');
  const [running, setRunning] = useState(false);
  const [expandedInv, setExpandedInv] = useState(null);
  const [page, setPage] = useState(1);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = useCallback(async () => {
    if (!token) return;
    try {
      const [stRes, invRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/dark-scout/status`, { headers }),
        fetch(`${API_URL}/api/admin/dark-scout/investigations?page=${page}&limit=15`, { headers }),
      ]);
      if (stRes.ok) setStatus(await stRes.json());
      if (invRes.ok) { const d = await invRes.json(); setInvestigations(d.investigations || []); setInvTotal(d.total || 0); }
    } catch (e) { console.error('DarkScout fetch:', e); }
    setLoading(false);
  }, [token, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runInvestigation = async () => {
    if (!query.trim()) return;
    setRunning(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/dark-scout/investigate`, {
        method: 'POST', headers,
        body: JSON.stringify({ query: query.trim(), preset, max_results: 15 }),
      });
      if (res.ok) {
        setQuery('');
        await fetchData();
      }
    } catch (e) { console.error(e); }
    setRunning(false);
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-[#D4AF37]" /></div>
  );

  const st = status || {};
  const riskDist = st.risk_distribution || {};

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="dark-scout-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }} data-testid="dark-scout-title">
            Dark Scout Intelligence
          </h1>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Layer 3 — Surface &amp; Deep Web OSINT | Engine: {st.scraping_engine || 'initializing'}
            {st.tor_available && <span className="ml-2 text-purple-400">Tor Active</span>}
            {st.llm_available && <span className="ml-2 text-green-400">LLM Ready</span>}
          </p>
        </div>
        <button onClick={fetchData} className="p-2 rounded-lg border transition-all hover:scale-[1.02]"
          style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }} data-testid="refresh-scout-btn">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="scout-status-cards">
        <div className="p-4 rounded-xl border" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }}>
          <div className="flex items-center gap-2 mb-2"><Shield className="w-4 h-4 text-[#D4AF37]" /><span className="text-[9px] tracking-[0.15em] uppercase font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Investigations</span></div>
          <div className="text-2xl font-bold font-mono text-[#D4AF37]">{st.total_investigations || 0}</div>
        </div>
        {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(level => {
          const rc = RISK_COLORS[level];
          return (
            <div key={level} className="p-4 rounded-xl border" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full" style={{ background: rc.color }} />
                <span className="text-[9px] tracking-[0.15em] uppercase font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>{level}</span>
              </div>
              <div className="text-2xl font-bold font-mono" style={{ color: rc.color }}>{riskDist[level] || 0}</div>
            </div>
          );
        })}
      </div>

      {/* Investigation Input */}
      <div className="p-5 rounded-xl border space-y-4" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="investigation-input">
        <h3 className="text-sm font-bold tracking-widest uppercase" style={{ color: 'var(--aurem-body-secondary)' }}>
          <Search className="w-3.5 h-3.5 inline mr-1" /> New Investigation
        </h3>
        <div className="flex gap-3">
          <input
            type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="e.g. Polaris Built data breach, aurem.live credentials, competitor pricing..."
            onKeyDown={e => e.key === 'Enter' && runInvestigation()}
            className="flex-1 px-4 py-2.5 rounded-lg border text-sm"
            style={{ background: 'transparent', borderColor: 'var(--aurem-border)', color: 'var(--aurem-heading)' }}
            data-testid="investigation-query-input"
          />
          <button onClick={runInvestigation} disabled={running || !query.trim()} data-testid="run-investigation-btn"
            className="px-5 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all hover:scale-[1.02] disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #D4AF37, #A08028)', color: '#050507' }}>
            {running ? <><Loader2 className="w-3.5 h-3.5 inline mr-1 animate-spin" />Scanning...</> : <><Send className="w-3.5 h-3.5 inline mr-1" />Investigate</>}
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          {PRESETS.map(p => (
            <button key={p.id} onClick={() => setPreset(p.id)}
              className={`px-3 py-1.5 rounded-full text-[11px] font-bold transition-all ${preset === p.id ? 'ring-2 ring-[#D4AF37]' : ''}`}
              style={{ background: preset === p.id ? 'rgba(212,175,55,0.15)' : 'rgba(255,255,255,0.03)', color: preset === p.id ? '#D4AF37' : 'var(--aurem-body-secondary)' }}
              data-testid={`preset-${p.id}`}>
              <p.icon className="w-3 h-3 inline mr-1" />{p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Investigation History */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="investigation-history">
        <div className="p-4 border-b" style={{ borderColor: 'var(--aurem-border)' }}>
          <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Investigation History ({invTotal})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--aurem-border)' }}>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Query</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Preset</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Risk</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Results</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Status</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Time</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {investigations.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-16 text-center" style={{ color: 'var(--aurem-body-secondary)' }}>
                  <Shield className="w-8 h-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm font-medium mb-1">No investigations yet</p>
                  <p className="text-[11px]">Enter a query above to start your first Dark Scout investigation.</p>
                </td></tr>
              ) : investigations.map(inv => {
                const rc = RISK_COLORS[inv.risk_level] || RISK_COLORS.UNKNOWN;
                const isExpanded = expandedInv === inv.investigation_id;
                return (
                  <React.Fragment key={inv.investigation_id}>
                    <tr className="border-b cursor-pointer transition-colors hover:bg-white/5"
                      style={{ borderColor: 'rgba(255,255,255,0.03)' }}
                      onClick={() => setExpandedInv(isExpanded ? null : inv.investigation_id)}
                      data-testid={`inv-row-${inv.investigation_id}`}>
                      <td className="px-4 py-3 max-w-[200px]">
                        <span className="font-medium truncate block" style={{ color: 'var(--aurem-heading)' }}>{inv.query}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37' }}>{inv.preset}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: rc.bg, color: rc.color }}>{inv.risk_level}</span>
                      </td>
                      <td className="px-4 py-3 text-[10px] font-mono" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {inv.search_results || 0} found / {inv.scraped_pages || 0} scraped
                      </td>
                      <td className="px-4 py-3">
                        {inv.status === 'completed' ? <CheckCircle className="w-3.5 h-3.5 text-green-400" /> : inv.status === 'failed' ? <XCircle className="w-3.5 h-3.5 text-red-400" /> : <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />}
                      </td>
                      <td className="px-4 py-3 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {inv.started_at ? new Date(inv.started_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                      </td>
                      <td className="px-4 py-3">{isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-[#D4AF37]" /> : <ChevronRight className="w-3.5 h-3.5" style={{ color: 'var(--aurem-body-secondary)' }} />}</td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={7} className="px-6 py-4" style={{ background: 'rgba(212,175,55,0.02)' }}>
                          <div className="space-y-3" data-testid={`inv-detail-${inv.investigation_id}`}>
                            <div className="flex items-center gap-4 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                              <span>ID: <code className="text-[#D4AF37]">{inv.investigation_id}</code></span>
                              <span>Sources: {inv.filtered_results || 0}</span>
                              <span>Scraped: {inv.scraped_pages || 0}</span>
                            </div>
                            {inv.sources && inv.sources.length > 0 && (
                              <div>
                                <p className="text-[10px] font-bold mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Sources:</p>
                                <div className="space-y-1 max-h-32 overflow-y-auto">
                                  {inv.sources.slice(0, 5).map((s, i) => (
                                    <a key={i} href={s.link} target="_blank" rel="noopener noreferrer"
                                      className="block text-[10px] hover:underline truncate" style={{ color: '#D4AF37' }}>
                                      {s.title || s.link}
                                    </a>
                                  ))}
                                </div>
                              </div>
                            )}
                            {inv.analysis && (
                              <div className="p-3 rounded-lg border text-xs leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto"
                                style={{ borderColor: 'rgba(212,175,55,0.15)', color: 'var(--aurem-heading)', background: 'rgba(0,0,0,0.2)' }}>
                                {inv.analysis}
                              </div>
                            )}
                            {inv.error && <p className="text-[10px] text-red-400">{inv.error}</p>}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        {invTotal > 15 && (
          <div className="p-3 flex items-center justify-between border-t" style={{ borderColor: 'var(--aurem-border)' }}>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
              className="text-xs px-3 py-1 rounded border" style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>Prev</button>
            <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Page {page}</span>
            <button onClick={() => setPage(page + 1)} disabled={page * 15 >= invTotal}
              className="text-xs px-3 py-1 rounded border" style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default DarkScoutDashboard;
