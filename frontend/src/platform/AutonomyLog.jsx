/**
 * AUREM Autonomy Log — Self-Audit + A2A Problem Resolution Dashboard
 * Real-time feed: problem detected → agent solved → duration → success/fail
 */
import React, { useState, useCallback, useEffect } from 'react';
import {
  Zap, Shield, Brain, Search, Wrench, Play, RefreshCw,
  CheckCircle, XCircle, AlertTriangle, Clock, Activity,
  ChevronDown, ChevronRight, Loader2, BarChart3,
  Timer, Radio, CalendarClock, RotateCcw
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const AGENT_ICONS = { scout: Search, shannon: Shield, architect: Brain, hermes: Brain, repair: Wrench };
const AGENT_COLORS = { scout: '#3b82f6', shannon: '#ef4444', architect: '#a855f7', hermes: '#D4AF37', repair: '#22c55e' };
const SEV_COLORS = { P0: '#ef4444', P1: '#f59e0b', P2: '#3b82f6', P3: '#888' };

const StatBox = ({ label, value, color, icon: Icon }) => (
  <div className="rounded-2xl p-4 flex flex-col gap-2" style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}>
    <div className="flex items-center gap-2">
      {Icon && <Icon size={14} style={{ color }} />}
      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary, #888)' }}>{label}</span>
    </div>
    <div className="text-2xl font-black" style={{ color }}>{value}</div>
  </div>
);

const CronMonitorCard = ({ cronStatus, triggerCron, triggeringCron }) => {
  if (!cronStatus) return null;
  const sched = cronStatus.schedule || {};
  const persistent = cronStatus.persistent || {};
  const inMem = cronStatus.in_memory || {};
  const runs = cronStatus.recent_runs || [];
  const lastRun = persistent.last_run || {};
  const cronState = persistent.status || inMem.status || 'unknown';
  const nextRun = persistent.next_run || inMem.next_run;

  const stateColor = cronState === 'running' ? '#3b82f6' : cronState === 'waiting' ? '#22c55e' : cronState === 'error' ? '#ef4444' : cronState === 'disabled' ? '#888' : '#D4AF37';
  const stateLabel = cronState === 'running' ? 'RUNNING NOW' : cronState === 'waiting' ? 'ACTIVE' : cronState === 'error' ? 'ERROR' : cronState === 'disabled' ? 'DISABLED' : cronState.toUpperCase();

  const formatTime = (iso) => {
    if (!iso) return '--';
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
  };
  const timeUntil = (iso) => {
    if (!iso) return '--';
    try {
      const diff = new Date(iso) - new Date();
      if (diff < 0) return 'overdue';
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      return h > 0 ? `${h}h ${m}m` : `${m}m`;
    } catch { return '--'; }
  };

  return (
    <div className="rounded-2xl p-5 space-y-4" data-testid="cron-monitor"
      style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CalendarClock size={16} style={{ color: '#D4AF37' }} />
          <h3 className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>CRON MONITOR</h3>
          <span className="text-[9px] font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1.5"
            style={{ background: `${stateColor}15`, color: stateColor, border: `1px solid ${stateColor}30` }}>
            <Radio size={8} style={{ color: stateColor }} className={cronState === 'running' ? 'animate-pulse' : ''} />
            {stateLabel}
          </span>
        </div>
        <button onClick={triggerCron} disabled={triggeringCron} data-testid="trigger-cron-btn"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all hover:opacity-80"
          style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.2)' }}>
          {triggeringCron ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />}
          {triggeringCron ? 'Running...' : 'Trigger Now'}
        </button>
      </div>

      {/* Schedule + Next Run */}
      <div className="grid grid-cols-4 gap-3">
        <div className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#888' }}>Schedule</p>
          <p className="text-xs font-bold" style={{ color: 'var(--aurem-text, #ccc)' }}>
            {sched.frequency === 'daily' ? 'Daily' : sched.frequency === 'weekly' ? 'Weekly' : 'Off'} at {String(sched.hour || 2).padStart(2, '0')}:{String(sched.minute || 0).padStart(2, '0')} UTC
          </p>
        </div>
        <div className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#888' }}>Next Run</p>
          <p className="text-xs font-bold" style={{ color: '#D4AF37' }}>{timeUntil(nextRun)}</p>
          <p className="text-[8px] mt-0.5" style={{ color: '#666' }}>{formatTime(nextRun)}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#888' }}>Last Run</p>
          <p className="text-xs font-bold" style={{ color: lastRun.status === 'success' ? '#22c55e' : lastRun.status === 'error' ? '#ef4444' : '#888' }}>
            {lastRun.status ? lastRun.status.toUpperCase() : 'NEVER'}
          </p>
          <p className="text-[8px] mt-0.5" style={{ color: '#666' }}>{formatTime(lastRun.finished_at)}</p>
        </div>
        <div className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <p className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{ color: '#888' }}>Last Duration</p>
          <p className="text-xs font-bold" style={{ color: 'var(--aurem-text, #ccc)' }}>
            {lastRun.duration_ms != null ? `${lastRun.duration_ms}ms` : '--'}
          </p>
          {lastRun.total_issues != null && (
            <p className="text-[8px] mt-0.5" style={{ color: '#666' }}>{lastRun.total_issues} issues / {lastRun.total_fixed || 0} fixed</p>
          )}
        </div>
      </div>

      {/* Recent Runs History */}
      {runs.length > 0 && (
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider mb-2" style={{ color: '#888' }}>Recent Executions</p>
          <div className="space-y-1">
            {runs.map((run, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.015)' }}>
                <div className="flex items-center gap-2">
                  {run.status === 'success' ? <CheckCircle size={10} style={{ color: '#22c55e' }} /> : <XCircle size={10} style={{ color: '#ef4444' }} />}
                  <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary, #888)' }}>{formatTime(run.started_at)}</span>
                  {run.trigger === 'manual' && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>MANUAL</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px]" style={{ color: '#3b82f6' }}>{run.total_issues || 0} issues</span>
                  <span className="text-[10px]" style={{ color: '#22c55e' }}>{run.total_fixed || 0} fixed</span>
                  <span className="text-[10px] font-mono" style={{ color: '#888' }}>{run.duration_ms || 0}ms</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default function AutonomyLog({ token }) {
  const [auditResult, setAuditResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [history, setHistory] = useState([]);
  const [agentStats, setAgentStats] = useState([]);
  const [tier, setTier] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [backups, setBackups] = useState([]);
  const [rollingBack, setRollingBack] = useState(null);
  const [cronStatus, setCronStatus] = useState(null);
  const [triggeringCron, setTriggeringCron] = useState(false);

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const runAudit = useCallback(async () => {
    setRunning(true);
    setAuditResult(null);
    try {
      const res = await fetch(`${API_URL}/api/self-audit/run`, { method: 'POST', headers, body: JSON.stringify({ auto_fix: true }) });
      if (res.ok) setAuditResult(await res.json());
    } catch (e) { console.error(e); }
    setRunning(false);
  }, [token]);

  const fetchHistory = useCallback(async () => {
    try {
      const [hRes, sRes, tRes, bRes, cRes] = await Promise.all([
        fetch(`${API_URL}/api/self-audit/log?limit=5`, { headers }),
        fetch(`${API_URL}/api/self-audit/stats`, { headers }),
        fetch(`${API_URL}/api/self-audit/tier`, { headers }),
        fetch(`${API_URL}/api/self-audit/backups?limit=10`, { headers }),
        fetch(`${API_URL}/api/self-audit/cron-status`, { headers }),
      ]);
      if (hRes.ok) { const d = await hRes.json(); setHistory(d.audits || []); }
      if (sRes.ok) { const d = await sRes.json(); setAgentStats(d.agents || []); }
      if (tRes.ok) setTier(await tRes.json());
      if (bRes.ok) { const d = await bRes.json(); setBackups(d.backups || []); }
      if (cRes.ok) setCronStatus(await cRes.json());
    } catch (e) { console.error(e); }
  }, [token]);

  const rollbackFix = useCallback(async (backupId) => {
    setRollingBack(backupId);
    try {
      const res = await fetch(`${API_URL}/api/self-audit/rollback/${backupId}`, { method: 'POST', headers });
      if (res.ok) {
        const d = await res.json();
        if (d.rolled_back) {
          setBackups(prev => prev.map(b => b.backup_id === backupId ? { ...b, rolled_back: true, can_undo: false } : b));
        }
      }
    } catch (e) { console.error(e); }
    setRollingBack(null);
  }, [token]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const triggerCron = useCallback(async () => {
    setTriggeringCron(true);
    try {
      const res = await fetch(`${API_URL}/api/self-audit/cron-trigger`, { method: 'POST', headers });
      if (res.ok) {
        const d = await res.json();
        if (d.triggered) setAuditResult(d.report);
        fetchHistory();
      }
    } catch (e) { console.error(e); }
    setTriggeringCron(false);
  }, [token, fetchHistory]);

  const report = auditResult || (history.length > 0 ? history[0] : null);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="autonomy-log">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-black tracking-tight" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>Autonomous Operations</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-text-secondary, #888)' }}>Self-Audit + A2A Problem Resolution — 5 agents, zero human interference</p>
        </div>
        <div className="flex items-center gap-3">
          {tier && (
            <span className="text-[9px] font-bold px-3 py-1 rounded-full" data-testid="survival-tier"
              style={{ background: tier.tier === 'abundant' ? '#22c55e18' : tier.tier === 'economical' ? '#D4AF3718' : tier.tier === 'survival' ? '#f59e0b18' : '#ef444418',
                       color: tier.tier === 'abundant' ? '#22c55e' : tier.tier === 'economical' ? '#D4AF37' : tier.tier === 'survival' ? '#f59e0b' : '#ef4444' }}>
              {tier.label || tier.tier?.toUpperCase()}
            </span>
          )}
          <button onClick={runAudit} disabled={running} data-testid="run-audit-btn"
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all hover:opacity-90"
            style={{ background: running ? 'rgba(128,128,128,0.2)' : 'linear-gradient(135deg, #D4AF37, #B87333)', color: running ? '#888' : '#141216' }}>
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? 'Scanning...' : 'Run Full Audit'}
          </button>
        </div>
      </div>

      {/* Stats Row */}
      {report && (
        <div className="grid grid-cols-5 gap-3">
          <StatBox label="Issues Found" value={report.total_issues || 0} color="#3b82f6" icon={Search} />
          <StatBox label="Auto-Fixed" value={report.auto_fixed || 0} color="#22c55e" icon={CheckCircle} />
          <StatBox label="Needs Review" value={report.needs_review || 0} color="#f59e0b" icon={AlertTriangle} />
          <StatBox label="Agents Active" value={report.agents_scanned || 5} color="#a855f7" icon={Activity} />
          <StatBox label="Scan Time" value={`${report.scan_duration_ms || 0}ms`} color="#D4AF37" icon={Clock} />
        </div>
      )}

      {/* Cron Monitor */}
      <CronMonitorCard cronStatus={cronStatus} triggerCron={triggerCron} triggeringCron={triggeringCron} />

      {/* Live Feed */}
      {report && (
        <div className="rounded-2xl p-5 space-y-3" style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}
          data-testid="audit-feed">
          <h3 className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>AUDIT FEED</h3>

          {/* Fixes Applied — with Undo button */}
          {report.fixes_applied?.map((fix, i) => {
            const matchingBackup = backups.find(b => b.fix_action === fix.fix_action && b.can_undo);
            return (
            <div key={`fix-${i}`} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}>
              <CheckCircle size={14} style={{ color: '#22c55e' }} />
              <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: `${AGENT_COLORS[fix.agent] || '#888'}18`, color: AGENT_COLORS[fix.agent] || '#888' }}>
                {fix.agent?.toUpperCase()}
              </span>
              <span className="text-xs flex-1" style={{ color: 'var(--aurem-text, #ccc)' }}>
                Fixed <strong>{fix.issue_type?.replace(/_/g, ' ')}</strong> — {fix.records_fixed || 0} records
              </span>
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${SEV_COLORS[fix.severity] || '#888'}18`, color: SEV_COLORS[fix.severity] || '#888' }}>
                {fix.severity}
              </span>
              {matchingBackup && (
                <button onClick={() => rollbackFix(matchingBackup.backup_id)} disabled={rollingBack === matchingBackup.backup_id}
                  data-testid={`undo-fix-${i}`}
                  className="text-[9px] font-bold px-2.5 py-1 rounded-lg transition-all hover:opacity-80"
                  style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                  {rollingBack === matchingBackup.backup_id ? <Loader2 size={10} className="animate-spin" /> : 'Undo'}
                </button>
              )}
            </div>
            );
          })}

          {/* Needs Review */}
          {report.needs_human_review?.map((item, i) => (
            <div key={`review-${i}`} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}>
              <AlertTriangle size={14} style={{ color: '#f59e0b' }} />
              <span className="text-xs flex-1" style={{ color: 'var(--aurem-text, #ccc)' }}>
                {item.description}
              </span>
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: '#f59e0b18', color: '#f59e0b' }}>
                REVIEW
              </span>
            </div>
          ))}

          {/* Assignments */}
          {report.assignments?.map((a, i) => (
            <div key={`assign-${i}`} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}>
              {a.assigned_to ? (
                React.createElement(AGENT_ICONS[a.assigned_to] || Zap, { size: 14, style: { color: AGENT_COLORS[a.assigned_to] || '#888' } })
              ) : (
                <XCircle size={14} style={{ color: '#ef4444' }} />
              )}
              <span className="text-xs flex-1" style={{ color: 'var(--aurem-text-secondary, #888)' }}>
                {a.issue_type?.replace(/_/g, ' ')} → {a.assigned_to ? <strong style={{ color: AGENT_COLORS[a.assigned_to] }}>{a.assigned_to}</strong> : 'unassigned'}
              </span>
              <span className="text-[10px] font-mono" style={{ color: 'var(--aurem-text-secondary, #888)' }}>
                {(a.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}

          {/* Suggestions */}
          {report.suggestions?.length > 0 && (
            <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(128,128,128,0.15)' }}>
              <h4 className="text-[10px] font-bold mb-2" style={{ color: 'var(--aurem-text-secondary, #888)' }}>SUGGESTIONS</h4>
              {report.suggestions.map((s, i) => (
                <p key={i} className="text-[10px] py-1" style={{ color: 'var(--aurem-text, #ccc)' }}>
                  {s}
                </p>
              ))}
            </div>
          )}

          {report.total_issues === 0 && (
            <div className="text-center py-6">
              <CheckCircle size={32} style={{ color: '#22c55e', margin: '0 auto 8px' }} />
              <p className="text-sm font-bold" style={{ color: '#22c55e' }}>All Clear</p>
              <p className="text-[10px]" style={{ color: 'var(--aurem-text-secondary, #888)' }}>No issues detected. System healthy.</p>
            </div>
          )}
        </div>
      )}

      {/* Agent Stats */}
      {agentStats.length > 0 && (
        <div className="rounded-2xl p-5" style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}
          data-testid="agent-stats">
          <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>AGENT PERFORMANCE</h3>
          <div className="grid grid-cols-5 gap-3">
            {agentStats.map((s, i) => {
              const Icon = AGENT_ICONS[s.agent] || Zap;
              const color = AGENT_COLORS[s.agent] || '#888';
              return (
                <div key={i} className="rounded-xl p-3 text-center" style={{ background: `${color}08`, border: `1px solid ${color}20` }}>
                  <Icon size={18} style={{ color, margin: '0 auto 4px' }} />
                  <p className="text-sm font-black" style={{ color }}>{s.problems_solved || 0}</p>
                  <p className="text-[9px] font-bold mt-0.5" style={{ color: 'var(--aurem-text-secondary, #888)' }}>{s.agent?.toUpperCase()}</p>
                  <p className="text-[8px]" style={{ color: 'var(--aurem-text-secondary, #666)' }}>{s.records_fixed || 0} records</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Backups — Undo History */}
      {backups.length > 0 && (
        <div className="rounded-2xl p-5" style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}
          data-testid="backup-list">
          <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>SAFETY BACKUPS (7-day undo)</h3>
          {backups.map((b, i) => (
            <div key={i} className="flex items-center justify-between py-2.5" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: `${AGENT_COLORS[b.agent] || '#888'}18`, color: AGENT_COLORS[b.agent] || '#888' }}>
                  {b.agent?.toUpperCase()}
                </span>
                <span className="text-[10px]" style={{ color: 'var(--aurem-text, #ccc)' }}>
                  {b.fix_action?.replace(/_/g, ' ')} — {b.records_count || 0} records
                </span>
              </div>
              <div className="flex items-center gap-2">
                {b.days_remaining !== undefined && <span className="text-[9px]" style={{ color: '#888' }}>{b.days_remaining}d left</span>}
                {b.rolled_back ? (
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded" style={{ background: '#f59e0b18', color: '#f59e0b' }}>Rolled Back</span>
                ) : b.can_undo ? (
                  <button onClick={() => rollbackFix(b.backup_id)} disabled={rollingBack === b.backup_id}
                    data-testid={`rollback-${i}`}
                    className="text-[9px] font-bold px-2.5 py-1 rounded-lg hover:opacity-80"
                    style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                    {rollingBack === b.backup_id ? '...' : 'Undo'}
                  </button>
                ) : (
                  <span className="text-[9px]" style={{ color: '#555' }}>Expired</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="rounded-2xl p-5" style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}
          data-testid="audit-history">
          <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>AUDIT HISTORY</h3>
          {history.map((audit, i) => (
            <div key={i} className="flex items-center justify-between py-2.5" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}
              onClick={() => setExpanded(expanded === i ? null : i)}>
              <div className="flex items-center gap-3 cursor-pointer">
                {expanded === i ? <ChevronDown size={12} style={{ color: '#888' }} /> : <ChevronRight size={12} style={{ color: '#888' }} />}
                <span className="text-[10px] font-mono" style={{ color: 'var(--aurem-text-secondary, #888)' }}>
                  {audit.timestamp ? new Date(audit.timestamp).toLocaleString() : '—'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold" style={{ color: '#3b82f6' }}>{audit.total_issues || 0} issues</span>
                <span className="text-[10px] font-bold" style={{ color: '#22c55e' }}>{audit.auto_fixed || 0} fixed</span>
                <span className="text-[10px] font-bold" style={{ color: '#f59e0b' }}>{audit.needs_review || 0} review</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!report && !running && (
        <div className="text-center py-16 rounded-2xl" style={{ background: 'var(--aurem-card-bg, rgba(20,18,22,0.6))', border: '1px solid var(--aurem-card-border, rgba(255,255,255,0.06))' }}>
          <Zap size={40} style={{ color: '#D4AF37', margin: '0 auto 12px' }} />
          <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--aurem-heading, #F5F5F5)' }}>Autonomous Operations</h3>
          <p className="text-[11px] mb-6" style={{ color: 'var(--aurem-text-secondary, #888)' }}>
            5 agents scan your customer database simultaneously.<br />
            Problems detected → agents bid → best agent fixes → zero human interference.
          </p>
          <button onClick={runAudit} data-testid="first-audit-btn"
            className="px-6 py-2.5 rounded-xl text-xs font-bold"
            style={{ background: 'linear-gradient(135deg, #D4AF37, #B87333)', color: '#141216' }}>
            Run First Audit
          </button>
        </div>
      )}
    </div>
  );
}
