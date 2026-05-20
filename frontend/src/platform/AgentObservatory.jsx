/**
 * Agent Observatory — Production monitoring & trace explorer
 * Live stats, activity chart, expandable trace table
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, Zap, AlertTriangle, Clock, Cpu, Eye,
  ChevronDown, ChevronRight, RefreshCw, Filter, Search,
  CheckCircle, XCircle, Loader2, BarChart3
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const STATUS_COLORS = {
  completed: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: 'Completed' },
  running: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', label: 'Running' },
  failed: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: 'Failed' },
  partial: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'Partial' },
};

const StatCard = ({ label, value, sub, icon: Icon, color, pulse }) => (
  <div className="p-4 rounded-xl border relative overflow-hidden" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }}
    data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
    <div className="flex items-center justify-between mb-2">
      <Icon className="size-4" style={{ color }} />
      <span className="text-[9px] tracking-[0.15em] uppercase font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</span>
    </div>
    <div className="text-2xl font-bold font-mono" style={{ color }}>{value}</div>
    {sub && <p className="text-[10px] mt-1 flex items-center gap-1" style={{ color: 'var(--aurem-body-secondary)' }}>
      {pulse && <span className="size-1.5 rounded-full inline-block animate-pulse" style={{ background: color }} />}
      {sub}
    </p>}
  </div>
);

const TraceRow = ({ trace, expanded, onToggle }) => {
  const st = STATUS_COLORS[trace.status] || STATUS_COLORS.completed;
  const time = new Date(trace.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const date = new Date(trace.completed_at).toLocaleDateString([], { month: 'short', day: 'numeric' });

  return (
    <>
      <tr className="border-b cursor-pointer transition-colors hover:bg-white/5"
        style={{ borderColor: 'rgba(255,255,255,0.03)' }}
        onClick={onToggle} data-testid={`trace-row-${trace.trace_id}`}>
        <td className="px-4 py-3">
          <code className="text-[10px] font-mono" style={{ color: '#D4AF37' }}>{trace.trace_id.slice(0, 16)}</code>
        </td>
        <td className="px-4 py-3 text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{trace.agent}</td>
        <td className="px-4 py-3">
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: st.bg, color: st.color }}>{st.label}</span>
        </td>
        <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--aurem-body-secondary)' }}>
          {trace.total_duration_ms >= 1000 ? `${(trace.total_duration_ms / 1000).toFixed(1)}s` : `${trace.total_duration_ms}ms`}
        </td>
        <td className="px-4 py-3">
          <div className="flex gap-1 flex-wrap">
            {(trace.tools_used || []).slice(0, 3).map((t, i) => (
              <span key={i} className="px-1.5 py-0.5 rounded text-[9px] font-mono" style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37' }}>{t}</span>
            ))}
            {(trace.tools_used || []).length > 3 && <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>+{trace.tools_used.length - 3}</span>}
          </div>
        </td>
        <td className="px-4 py-3 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{date} {time}</td>
        <td className="px-4 py-3">{expanded ? <ChevronDown className="size-3.5" style={{ color: '#D4AF37' }} /> : <ChevronRight className="size-3.5" style={{ color: 'var(--aurem-body-secondary)' }} />}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="px-4 py-0">
            <div className="py-4 pl-6 border-l-2 ml-4 space-y-2" style={{ borderColor: 'rgba(212,175,55,0.3)' }} data-testid={`trace-steps-${trace.trace_id}`}>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: 'var(--aurem-body-secondary)' }}>Trace: {trace.trace_id}</span>
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Session: {trace.session_id}</span>
                {trace.llm_calls > 0 && <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>LLM: {trace.llm_calls} calls</span>}
              </div>
              {(trace.steps || []).map((step, i) => {
                const stepOk = step.status === 'success';
                return (
                  <div key={i} className="flex items-start gap-3 py-2 px-3 rounded-lg" style={{ background: stepOk ? 'rgba(34,197,94,0.03)' : 'rgba(239,68,68,0.05)' }}>
                    <div className="size-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: stepOk ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)' }}>
                      {stepOk ? <CheckCircle className="size-3 text-green-400" /> : <XCircle className="size-3 text-red-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Step {step.step_number}: {step.agent}</span>
                        <span className="text-[10px] font-mono" style={{ color: '#D4AF37' }}>{step.action}</span>
                      </div>
                      <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{step.output_summary}</p>
                      {step.error && <p className="text-[10px] mt-0.5 text-red-400">{step.error}</p>}
                    </div>
                    <span className="text-[10px] font-mono flex-shrink-0" style={{ color: stepOk ? '#22c55e' : '#ef4444' }}>{step.duration_ms}ms</span>
                  </div>
                );
              })}
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

const AgentObservatory = ({ token }) => {
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);
  const [traces, setTraces] = useState([]);
  const [tracesTotal, setTracesTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedTrace, setExpandedTrace] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [seeding, setSeeding] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchAll = useCallback(async () => {
    if (!token) return;
    try {
      const [stRes, actRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/agent/status`, { headers }),
        fetch(`${API_URL}/api/admin/agent/activity`, { headers }),
      ]);
      if (stRes.ok) setStats(await stRes.json());
      if (actRes.ok) { const d = await actRes.json(); setActivity(d.activity || []); }
    } catch (e) { console.error('Observatory fetch:', e); }
    setLoading(false);
  }, [token]);

  const fetchTraces = useCallback(async () => {
    if (!token) return;
    const params = new URLSearchParams({ page, limit: 20 });
    if (statusFilter) params.set('status', statusFilter);
    try {
      const res = await fetch(`${API_URL}/api/admin/agent/traces?${params}`, { headers });
      if (res.ok) { const d = await res.json(); setTraces(d.traces || []); setTracesTotal(d.total || 0); }
    } catch (e) { console.error('Traces fetch:', e); }
  }, [token, page, statusFilter]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { fetchTraces(); }, [fetchTraces]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(() => { fetchAll(); fetchTraces(); }, 30000);
    return () => clearInterval(interval);
  }, [fetchAll, fetchTraces]);

  const seedTraces = async () => {
    setSeeding(true);
    try {
      await fetch(`${API_URL}/api/admin/agent/seed-traces`, { method: 'POST', headers });
      await fetchAll(); await fetchTraces();
    } catch (e) { console.error(e); }
    setSeeding(false);
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center" style={{ background: 'transparent' }}>
      <Loader2 className="size-8 animate-spin text-[#D4AF37]" />
    </div>
  );

  const s = stats || {};
  const hasData = (s.tasks_total || 0) > 0;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="agent-observatory">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }} data-testid="observatory-title">
            Agent Observatory
          </h1>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Production monitoring, auto-refreshes every 30s
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!hasData && (
            <button onClick={seedTraces} disabled={seeding} data-testid="seed-traces-btn"
              className="px-4 py-2 rounded-lg text-xs font-bold tracking-wider transition-all hover:scale-[1.02]"
              style={{ background: 'linear-gradient(135deg, #D4AF37, #A08028)', color: '#050507' }}>
              {seeding ? 'Seeding...' : 'Load Demo Data'}
            </button>
          )}
          <button onClick={() => { fetchAll(); fetchTraces(); }} data-testid="refresh-observatory-btn"
            className="p-2 rounded-lg border transition-all hover:scale-[1.02]"
            style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>
            <RefreshCw className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Stats Row 1 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="stats-row-1">
        <StatCard label="Uptime" value={`${s.uptime_percent || 100}%`} sub="Live" icon={Activity} color="#22c55e" pulse />
        <StatCard label="Tasks Today" value={s.tasks_today || 0} sub={`${s.tasks_total || 0} total`} icon={Zap} color="#D4AF37" />
        <StatCard label="Error Rate" value={`${s.error_rate || 0}%`} sub={s.error_rate > 0 ? 'Issues detected' : 'All clear'} icon={AlertTriangle} color={s.error_rate > 2 ? '#ef4444' : '#22c55e'} />
      </div>

      {/* Stats Row 2 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="stats-row-2">
        <StatCard label="Avg Response" value={s.avg_response_ms >= 1000 ? `${(s.avg_response_ms / 1000).toFixed(1)}s` : `${s.avg_response_ms || 0}ms`} icon={Clock} color="#8b5cf6" />
        <StatCard label="Pipeline Runs" value={s.pipeline_runs_today || 0} sub="today" icon={Cpu} color="#3b82f6" />
        <StatCard label="LLM Calls" value={s.llm_calls_today || 0} sub="today" icon={BarChart3} color="#f59e0b" />
      </div>

      {/* Activity Chart */}
      <div className="p-5 rounded-xl border" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="activity-chart">
        <h3 className="text-sm font-bold tracking-widest uppercase mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>
          Pipeline Activity, Last 24 Hours
        </h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={activity}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'var(--aurem-body-secondary)' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--aurem-body-secondary)' }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: '#0a0a0a', border: '1px solid rgba(212,175,55,0.2)', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: '#D4AF37' }}
                itemStyle={{ color: '#D4AF37' }}
              />
              <Line type="monotone" dataKey="count" stroke="#D4AF37" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#D4AF37' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2" data-testid="trace-filters">
        {['', 'completed', 'running', 'failed'].map(f => (
          <button key={f || 'all'} onClick={() => { setStatusFilter(f); setPage(1); }}
            className={`px-3 py-1.5 rounded-full text-[11px] font-bold transition-all ${statusFilter === f ? 'ring-2 ring-[#D4AF37]' : ''}`}
            style={{ background: f ? (STATUS_COLORS[f]?.bg || 'rgba(255,255,255,0.05)') : 'rgba(212,175,55,0.08)', color: f ? (STATUS_COLORS[f]?.color || '#888') : '#D4AF37' }}
            data-testid={`filter-${f || 'all'}`}>
            {f ? STATUS_COLORS[f]?.label : 'All'} {f === '' ? `(${tracesTotal})` : ''}
          </button>
        ))}
      </div>

      {/* Trace Explorer Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--aurem-card-bg)', borderColor: 'var(--aurem-border)' }} data-testid="trace-table">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--aurem-border)' }}>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Trace ID</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Agent</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Status</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Duration</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Tools</th>
                <th className="px-4 py-3 text-left font-bold tracking-wider uppercase" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>Time</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {traces.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-16 text-center" style={{ color: 'var(--aurem-body-secondary)' }}>
                    <Eye className="size-8 mx-auto mb-3 opacity-30" />
                    <p className="text-sm font-medium mb-1">No traces yet</p>
                    <p className="text-[11px]">Click "Load Demo Data" or run a pipeline to see agent traces.</p>
                  </td>
                </tr>
              ) : traces.map(trace => (
                <TraceRow
                  key={trace.trace_id}
                  trace={trace}
                  expanded={expandedTrace === trace.trace_id}
                  onToggle={() => setExpandedTrace(expandedTrace === trace.trace_id ? null : trace.trace_id)}
                />
              ))}
            </tbody>
          </table>
        </div>
        {tracesTotal > 20 && (
          <div className="p-3 flex items-center justify-between border-t" style={{ borderColor: 'var(--aurem-border)' }}>
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
              className="text-xs px-3 py-1 rounded border" style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>Prev</button>
            <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Page {page} of {Math.ceil(tracesTotal / 20)}</span>
            <button onClick={() => setPage(page + 1)} disabled={page * 20 >= tracesTotal}
              className="text-xs px-3 py-1 rounded border" style={{ borderColor: 'var(--aurem-border)', color: 'var(--aurem-body-secondary)' }}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentObservatory;
