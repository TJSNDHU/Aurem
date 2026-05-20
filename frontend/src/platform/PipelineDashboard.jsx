import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Activity, Play, Square, RefreshCw, ChevronDown, ChevronUp, RotateCcw, ExternalLink, Clock, Zap, XCircle, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const STAGES = [
  { key: 'scout', label: 'Scout' },
  { key: 'architect', label: 'Architect' },
  { key: 'risk_gate', label: 'Risk Gate' },
  { key: 'envoy', label: 'Envoy' },
  { key: 'human_loop', label: 'Human' },
  { key: 'shadow_test', label: 'Shadow' },
  { key: 'closer', label: 'Closer' },
  { key: 'origin_lock', label: 'Origin' },
  { key: 'verifier', label: 'Verifier' },
  { key: 'learn', label: 'Learn' },
];

function stageColor(stage) {
  const s = stage?.status || '';
  if (['completed', 'passed', 'all_verified', 'compiled', 'completed_clean'].includes(s)) return '#22C55E';
  if (['failed', 'aborted', 'partial_fail', 'aborted_with_rollback'].includes(s)) return '#EF4444';
  if (['running', 'queued'].includes(s)) return '#EAB308';
  if (['skipped_validated', 'skipped'].includes(s)) return '#6B7280';
  return '#374151';
}

function statusBadge(finalStatus) {
  if (!finalStatus) return { color: '#6B7280', label: 'Unknown' };
  if (finalStatus === 'running') return { color: '#EAB308', label: 'Running' };
  if (finalStatus.startsWith('completed')) return { color: '#22C55E', label: finalStatus === 'completed_no_issues' ? 'Clean' : finalStatus === 'completed_with_issues' ? 'Issues' : 'Done' };
  if (finalStatus.startsWith('aborted')) return { color: '#EF4444', label: 'Aborted' };
  if (finalStatus === 'error') return { color: '#EF4444', label: 'Error' };
  if (finalStatus === 'queued_quiet_hours') return { color: '#8B5CF6', label: 'Queued' };
  return { color: '#6B7280', label: finalStatus.replace(/_/g, ' ') };
}

function duration(start, end) {
  if (!start) return '-';
  const s = new Date(start);
  const e = end ? new Date(end) : new Date();
  const ms = e - s;
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function timeAgo(ts) {
  if (!ts) return '-';
  const ms = Date.now() - new Date(ts).getTime();
  if (ms < 60000) return 'just now';
  if (ms < 3600000) return `${Math.floor(ms / 60000)}m ago`;
  if (ms < 86400000) return `${Math.floor(ms / 3600000)}h ago`;
  return `${Math.floor(ms / 86400000)}d ago`;
}

function StageBoxes({ stages }) {
  const stageMap = {};
  (stages || []).forEach(s => {
    if (s.stage && s.stage !== 'error' && s.stage !== 'abort') {
      stageMap[s.stage] = s;
    }
  });

  return (
    <div className="flex gap-[3px]" data-testid="pipeline-stage-boxes">
      {STAGES.map(({ key, label }) => {
        const stg = stageMap[key];
        const color = stg ? stageColor(stg) : '#374151';
        return (
          <div
            key={key}
            title={`${label}: ${stg?.status || 'pending'}`}
            className="relative group"
          >
            <div
              className="w-[22px] h-[22px] rounded-[3px] transition-all duration-200"
              style={{
                background: color,
                boxShadow: stg?.status === 'running' ? `0 0 8px ${color}` : 'none',
                animation: stg?.status === 'running' ? 'pulse 1.5s infinite' : 'none',
              }}
            />
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 text-[10px] rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50"
              style={{ background: '#1a1a2e', color: '#e0e0e0', border: '1px solid rgba(255,255,255,0.1)' }}>
              {label}: {stg?.status || 'pending'}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ExpandedRow({ run, token, onRetrigger }) {
  const stageMap = {};
  (run.stages || []).forEach(s => {
    if (s.stage) stageMap[s.stage] = s;
  });

  return (
    <div className="px-6 py-4 border-t" style={{ borderColor: 'rgba(61,58,57,0.15)', background: 'rgba(45,122,74,0.02)' }}>
      <div className="grid grid-cols-5 gap-3 mb-4">
        {STAGES.map(({ key, label }) => {
          const stg = stageMap[key];
          const color = stg ? stageColor(stg) : '#374151';
          return (
            <div key={key} className="rounded-lg p-2" style={{ background: 'rgba(255,255,255,0.6)', border: `1px solid ${color}33` }}>
              <div className="flex items-center gap-1.5 mb-1">
                <div className="size-2.5 rounded-full" style={{ background: color }} />
                <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>{label}</span>
              </div>
              <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                {stg?.status || 'pending'}
              </div>
              {stg?.timestamp && (
                <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {timeAgo(stg.timestamp)}
                </div>
              )}
              {stg?.data && Object.keys(stg.data).length > 0 && (
                <div className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {Object.entries(stg.data).map(([k, v]) => (
                    <div key={k}>{k}: {JSON.stringify(v)}</div>
                  ))}
                </div>
              )}
              {stg?.error && (
                <div className="text-[10px] mt-1 text-red-500">{stg.error}</div>
              )}
            </div>
          );
        })}
      </div>

      {run.final_status?.includes('abort') && (
        <div className="rounded-lg p-3 mb-3" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
          <div className="flex items-center gap-2 text-sm font-medium text-red-600">
            <XCircle className="size-4" /> Aborted
          </div>
          {run.aborted_by && <div className="text-xs text-red-500 mt-1">By: {run.aborted_by}</div>}
          {run.aborted_at && <div className="text-xs text-red-500">At: {new Date(run.aborted_at).toLocaleString()}</div>}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => onRetrigger(run.tenant_id)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-[1.02]"
          style={{ background: 'linear-gradient(135deg, #FF6B00, #22C55E)', color: '#fff' }}
          data-testid="pipeline-retrigger-btn"
        >
          <Play className="size-3" /> Re-trigger
        </button>
      </div>
    </div>
  );
}

export default function PipelineDashboard({ token }) {
  const [runs, setRuns] = useState([]);
  const [activeRuns, setActiveRuns] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(10);
  const [expandedRun, setExpandedRun] = useState(null);
  const [triggerLoading, setTriggerLoading] = useState(null);
  const [abortLoading, setAbortLoading] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [histRes, activeRes, statsRes] = await Promise.all([
        fetch(`${API}/api/pipeline/history/all?limit=${limit}`, { headers }),
        fetch(`${API}/api/pipeline/runs/active`, { headers }),
        fetch(`${API}/api/pipeline/stats`, { headers }),
      ]);
      if (histRes.ok) {
        const d = await histRes.json();
        setRuns(d.runs || []);
      }
      if (activeRes.ok) {
        const d = await activeRes.json();
        setActiveRuns(d.active_runs || []);
      }
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (e) {
      console.error('Pipeline fetch error:', e);
    }
    setLoading(false);
  }, [limit, headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const triggerPipeline = async (tenantId) => {
    setTriggerLoading(tenantId);
    try {
      await fetch(`${API}/api/pipeline/trigger/${tenantId}`, {
        method: 'POST', headers, body: JSON.stringify({ trigger_type: 'manual' }),
      });
      setTimeout(fetchData, 1500);
    } catch (e) { console.error(e); }
    setTriggerLoading(null);
  };

  const abortPipeline = async (runId) => {
    setAbortLoading(runId);
    try {
      await fetch(`${API}/api/pipeline/abort/${runId}`, { method: 'POST', headers });
      setTimeout(fetchData, 500);
    } catch (e) { console.error(e); }
    setAbortLoading(null);
  };

  const completedToday = runs.filter(r => {
    if (!r.completed_at) return false;
    const d = new Date(r.completed_at);
    const now = new Date();
    return d.toDateString() === now.toDateString() && r.final_status?.startsWith('completed');
  }).length;

  const abortedToday = runs.filter(r => {
    const ts = r.aborted_at || r.completed_at;
    if (!ts) return false;
    const d = new Date(ts);
    const now = new Date();
    return d.toDateString() === now.toDateString() && (r.final_status?.includes('abort') || r.final_status === 'error');
  }).length;

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="pipeline-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Pipeline Monitor</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            10-stage autonomous flow: Scout &rarr; Learn
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); fetchData(); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
          style={{ background: 'rgba(61,58,57,0.25)', color: 'var(--aurem-heading)' }}
          data-testid="pipeline-refresh-btn"
        >
          <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="aurem-glass-card p-4" data-testid="pipeline-active-count">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(234,179,8,0.15)' }}>
              <Activity className="size-5" style={{ color: '#EAB308' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{activeRuns.length}</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Active Pipelines</div>
            </div>
          </div>
        </div>
        <div className="aurem-glass-card p-4" data-testid="pipeline-completed-count">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(34,197,94,0.15)' }}>
              <CheckCircle className="size-5" style={{ color: '#22C55E' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{completedToday}</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Completed Today</div>
            </div>
          </div>
        </div>
        <div className="aurem-glass-card p-4" data-testid="pipeline-aborted-count">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.15)' }}>
              <XCircle className="size-5" style={{ color: '#EF4444' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{abortedToday}</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Aborted Today</div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      {stats && (
        <div className="aurem-glass-card p-3 mb-6 flex items-center gap-6 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
          <span>Total Runs: <strong style={{ color: 'var(--aurem-heading)' }}>{stats.total_runs || 0}</strong></span>
          <span>Success Rate: <strong style={{ color: (stats.success_rate || 0) >= 80 ? '#22C55E' : '#EAB308' }}>{stats.success_rate || 0}%</strong></span>
          <span>Last 24h: <strong style={{ color: 'var(--aurem-heading)' }}>{stats.last_24h || 0}</strong></span>
          <span>Errors: <strong style={{ color: (stats.errors || 0) > 0 ? '#EF4444' : '#22C55E' }}>{stats.errors || 0}</strong></span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="px-3 py-1.5 rounded-lg text-sm border"
          style={{ borderColor: 'rgba(255,107,0,0.1)', background: 'rgba(255,255,255,0.8)', color: 'var(--aurem-heading)' }}
          data-testid="pipeline-limit-select"
        >
          <option value={10}>Last 10</option>
          <option value={25}>Last 25</option>
          <option value={50}>Last 50</option>
        </select>
        <div className="flex-1" />
        <div className="flex gap-1">
          {STAGES.map(s => (
            <div key={s.key} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,107,0,0.05)', color: 'var(--aurem-body-secondary)' }}>
              {s.label}
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline Runs Table */}
      <div className="aurem-glass-card overflow-hidden" data-testid="pipeline-runs-table">
        {/* Table Header */}
        <div className="grid grid-cols-[140px_80px_90px_80px_1fr_100px_90px] gap-3 px-5 py-3 text-xs font-semibold border-b"
          style={{ borderColor: 'rgba(61,58,57,0.25)', color: 'var(--aurem-body-secondary)', background: 'rgba(255,107,0,0.03)' }}>
          <div>Tenant</div>
          <div>Trigger</div>
          <div>Started</div>
          <div>Duration</div>
          <div>Stages</div>
          <div>Result</div>
          <div>Actions</div>
        </div>

        {loading && runs.length === 0 ? (
          <div className="flex items-center justify-center py-16" data-testid="pipeline-loading">
            <Loader2 className="size-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16" data-testid="pipeline-empty">
            <Activity className="size-10 mb-3" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.4 }} />
            <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>No pipeline runs yet</p>
            <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.7 }}>
              Trigger a pipeline from Optimization or use the API
            </p>
          </div>
        ) : (
          runs.map((run, idx) => {
            const badge = statusBadge(run.final_status);
            const isActive = run.final_status === 'running';
            const isExpanded = expandedRun === run.run_id;

            return (
              <div key={run.run_id || idx}>
                <div
                  className="grid grid-cols-[140px_80px_90px_80px_1fr_100px_90px] gap-3 px-5 py-3 items-center text-sm cursor-pointer transition-colors hover:bg-[rgba(255,107,0,0.03)]"
                  style={{
                    borderBottom: '1px solid rgba(255,107,0,0.05)',
                    animation: isActive ? 'auremPulse 2s infinite' : 'none',
                  }}
                  onClick={() => setExpandedRun(isExpanded ? null : run.run_id)}
                  data-testid={`pipeline-run-${run.run_id}`}
                >
                  <div className="font-medium truncate" style={{ color: 'var(--aurem-heading)' }} title={run.tenant_id}>
                    {run.tenant_id?.slice(0, 14) || '-'}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {run.trigger || 'manual'}
                  </div>
                  <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {timeAgo(run.started_at)}
                  </div>
                  <div className="text-xs font-mono" style={{ color: 'var(--aurem-body-secondary)' }}>
                    {duration(run.started_at, run.completed_at)}
                  </div>
                  <StageBoxes stages={run.stages} />
                  <div className="flex items-center gap-1.5">
                    <div className="size-2 rounded-full" style={{ background: badge.color }} />
                    <span className="text-xs font-medium" style={{ color: badge.color }}>{badge.label}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {isActive && (
                      <button
                        onClick={(e) => { e.stopPropagation(); abortPipeline(run.run_id); }}
                        className="p-1 rounded hover:bg-red-50 transition-colors"
                        title="Abort"
                        data-testid={`pipeline-abort-${run.run_id}`}
                      >
                        {abortLoading === run.run_id ? (
                          <Loader2 className="size-3.5 animate-spin text-red-500" />
                        ) : (
                          <Square className="size-3.5 text-red-500" />
                        )}
                      </button>
                    )}
                    {isExpanded ? (
                      <ChevronUp className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />
                    ) : (
                      <ChevronDown className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <ExpandedRow run={run} token={token} onRetrigger={triggerPipeline} />
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Pulse animation CSS */}
      <style>{`
        @keyframes auremPulse {
          0%, 100% { background: transparent; }
          50% { background: rgba(234,179,8,0.03); }
        }
      `}</style>
    </div>
  );
}
