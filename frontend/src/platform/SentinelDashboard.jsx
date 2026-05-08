/**
 * AUREM Sentinel — Self-Healing Dashboard
 * Real-time view of the autonomous monitoring loop.
 * Auto-refreshes every 10 seconds.
 */

import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Activity, Shield, Zap, CheckCircle, XCircle, AlertTriangle, RefreshCw, Database, Clock, Heart, ChevronDown, ChevronRight, Play } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const SeverityBadge = ({ severity }) => {
  const styles = {
    P0: { bg: 'rgba(255,59,48,0.1)', color: '#FF3B30', label: 'CRITICAL' },
    P1: { bg: 'rgba(255,149,0,0.1)', color: '#FF9500', label: 'HIGH' },
    P2: { bg: 'rgba(255,204,0,0.1)', color: '#FFCC00', label: 'MEDIUM' },
    P3: { bg: 'rgba(142,142,147,0.1)', color: '#8E8E93', label: 'LOW' },
  };
  const s = styles[severity] || styles.P3;
  return (
    <span className="text-[8px] px-1.5 py-0.5 rounded font-bold tracking-wider" style={{ background: s.bg, color: s.color }}>
      {severity} {s.label}
    </span>
  );
};

const HealthGauge = ({ score }) => {
  const color = score >= 80 ? '#4ade80' : score >= 60 ? '#D4B977' : '#FF6B6B';
  const circumference = 2 * Math.PI * 70;
  const offset = circumference - (score / 100) * circumference;
  return (
    <div className="flex flex-col items-center" data-testid="health-gauge">
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle cx="80" cy="80" r="70" stroke="rgba(255,107,0,0.05)" strokeWidth="10" fill="none" />
        <circle cx="80" cy="80" r="70" stroke={color} strokeWidth="10" fill="none"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 80 80)" style={{ transition: 'stroke-dashoffset 1.5s ease-out' }} />
        <text x="80" y="72" textAnchor="middle" fontSize="36" fontWeight="bold" fill="#1A1A2E">{score}</text>
        <text x="80" y="95" textAnchor="middle" fontSize="10" fill="#888" fontWeight="600">HEALTH</text>
      </svg>
    </div>
  );
};

export default function SentinelDashboard({ token }) {
  const [status, setStatus] = useState(null);
  const [pulses, setPulses] = useState([]);
  const [fixes, setFixes] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [knownFixes, setKnownFixes] = useState([]);
  const [searchStats, setSearchStats] = useState(null);
  const [modelRouting, setModelRouting] = useState(null);
  const [costToday, setCostToday] = useState(null);
  const [costMonth, setCostMonth] = useState(null);
  const [costAlltime, setCostAlltime] = useState(null);
  const [costChart, setCostChart] = useState([]);
  const [gitBackup, setGitBackup] = useState(null);
  const [activeTab, setActiveTab] = useState('health');
  const [expandedSection, setExpandedSection] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchAll = useCallback(async () => {
    try {
      const [statusRes, pulseRes, fixesRes, alertsRes, knownRes, searchRes, routingRes, todayRes, monthRes, alltimeRes, chartRes, gitRes] = await Promise.all([
        fetch(`${API_URL}/api/sentinel/status`, { headers }),
        fetch(`${API_URL}/api/sentinel/pulse-history?limit=30`, { headers }),
        fetch(`${API_URL}/api/sentinel/fixes-log?limit=10`, { headers }),
        fetch(`${API_URL}/api/sentinel/alerts?limit=10`, { headers }),
        fetch(`${API_URL}/api/sentinel/known-fixes`, { headers }),
        fetch(`${API_URL}/api/sentinel/search-stats`, { headers }),
        fetch(`${API_URL}/api/sentinel/model-routing`, { headers }),
        fetch(`${API_URL}/api/sentinel/cost/today`, { headers }),
        fetch(`${API_URL}/api/sentinel/cost/month`, { headers }),
        fetch(`${API_URL}/api/sentinel/cost/alltime`, { headers }),
        fetch(`${API_URL}/api/sentinel/cost/chart?days=7`, { headers }),
        fetch(`${API_URL}/api/sentinel/git-backup`, { headers }),
      ]);

      if (statusRes.ok) setStatus(await statusRes.json());
      if (pulseRes.ok) { const d = await pulseRes.json(); setPulses(d.pulses || []); }
      if (fixesRes.ok) { const d = await fixesRes.json(); setFixes(d.fixes || []); }
      if (alertsRes.ok) { const d = await alertsRes.json(); setAlerts(d.alerts || []); }
      if (knownRes.ok) { const d = await knownRes.json(); setKnownFixes(d.fixes || []); }
      if (searchRes.ok) setSearchStats(await searchRes.json());
      if (routingRes.ok) setModelRouting(await routingRes.json());
      if (todayRes.ok) setCostToday(await todayRes.json());
      if (monthRes.ok) setCostMonth(await monthRes.json());
      if (alltimeRes.ok) setCostAlltime(await alltimeRes.json());
      if (chartRes.ok) setCostChart(await chartRes.json());
      if (gitRes.ok) setGitBackup(await gitRes.json());
    } catch (e) { console.error('Sentinel fetch:', e); }
    finally { setLoading(false); }
  }, [headers]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const triggerCycle = async () => {
    setTriggering(true);
    try {
      const res = await fetch(`${API_URL}/api/sentinel/trigger-cycle`, { method: 'POST', headers });
      if (res.ok) { await fetchAll(); }
    } catch (e) { console.error(e); }
    finally { setTriggering(false); }
  };

  const healthScore = status?.health_score || 0;
  const isRunning = status?.running;
  const healthColor = healthScore >= 80 ? '#4ade80' : healthScore >= 60 ? '#D4B977' : '#FF6B6B';

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(61,58,57,0.15)' }}>
              <Shield className="w-5 h-5 text-[#FF6B00]" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#1A1A2E] tracking-wider" data-testid="sentinel-title">Sentinel</h1>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-[#4ade80] animate-pulse' : 'bg-[#FF6B6B]'}`} />
                <span className="text-[10px] text-[#888]">{isRunning ? 'Autonomous Loop Active' : 'Loop Stopped'}</span>
              </div>
            </div>
          </div>
          <button onClick={triggerCycle} disabled={triggering} data-testid="trigger-cycle-btn"
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-[#FF6B00] text-white hover:opacity-90 transition-all disabled:opacity-50">
            <Play className={`w-3.5 h-3.5 ${triggering ? 'animate-spin' : ''}`} />
            {triggering ? 'Running...' : 'Trigger Cycle'}
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-1 mb-6 p-1 bg-white/50 backdrop-blur-sm rounded-xl border border-white/40 w-fit" data-testid="sentinel-tabs">
          {[
            { id: 'health', label: 'System Health', icon: <Shield className="w-3.5 h-3.5" /> },
            { id: 'cost', label: 'Cost Savings', icon: <Zap className="w-3.5 h-3.5" /> },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} data-testid={`tab-${tab.id}`}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === tab.id
                  ? 'bg-[#1A1A2E] text-white shadow-sm'
                  : 'text-[#888] hover:text-[#1A1A2E]'
              }`}>
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-12">
            <Activity className="w-6 h-6 animate-spin text-[#888] mx-auto mb-2" />
            <span className="text-xs text-[#888]">Loading Sentinel data...</span>
          </div>
        ) : !status ? (
          <div className="flex flex-col items-center justify-center py-16 text-center" data-testid="sentinel-empty-state">
            <Shield className="w-10 h-10 text-[#888]" style={{ opacity: 0.3 }} />
            <h2 className="text-lg font-bold mt-4 text-[#1A1A2E]">No data yet</h2>
            <p className="text-xs mt-1 text-[#888]">Sentinel monitoring data will appear here once the system starts collecting.</p>
            <button onClick={fetchAll} className="mt-4 flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-[#888] hover:text-[#1A1A2E] transition-colors" style={{ background: 'rgba(128,128,128,0.08)' }} data-testid="sentinel-retry-btn">
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          </div>
        ) : (
          <>
          {activeTab === 'health' ? (
          <>
            {/* Health Gauge + Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl flex justify-center" data-testid="health-panel">
                <HealthGauge score={healthScore} />
              </div>
              <div className="col-span-2 grid grid-cols-2 gap-3">
                <StatCard icon={<RefreshCw className="w-4 h-4" />} label="Cycle" value={status?.cycle_number || 0} sub="Current cycle" color="#FF6B00" testid="cycle-count" />
                <StatCard icon={<AlertTriangle className="w-4 h-4" />} label="Issues" value={status?.issues_count || 0} sub="Active issues" color={status?.issues_count > 0 ? '#FF6B6B' : '#4ade80'} testid="issues-count" />
                <StatCard icon={<Zap className="w-4 h-4" />} label="Auto-Fixes" value={status?.total_auto_fixes || 0} sub="Total applied" color="#D4AF37" testid="fixes-count" />
                <StatCard icon={<Database className="w-4 h-4" />} label="Known Fixes" value={status?.known_fixes_count || 0} sub="Learned patterns" color="#64C8FF" testid="known-count" />
                <StatCard icon={<Clock className="w-4 h-4" />} label="Last Check"
                  value={status?.last_check ? new Date(status.last_check).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                  sub="Next in 60s" color="#888" testid="last-check" />
                <StatCard icon={<Heart className="w-4 h-4" />} label="Status" value={isRunning ? 'ACTIVE' : 'STOPPED'}
                  sub={isRunning ? 'Loop running 24/7' : 'Needs restart'} color={isRunning ? '#4ade80' : '#FF6B6B'} testid="loop-status" />
              </div>
            </div>

            {/* Git Backup Status */}
            {gitBackup && (
              <div className="mb-6 p-4 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="git-backup-card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ background: gitBackup.status === 'current' ? 'rgba(34,197,94,0.1)' : gitBackup.status === 'behind' ? 'rgba(234,179,8,0.1)' : 'rgba(136,136,136,0.1)' }}>
                      <Database className="w-4 h-4" style={{ color: gitBackup.status === 'current' ? '#22C55E' : gitBackup.status === 'behind' ? '#EAB308' : '#888' }} />
                    </div>
                    <div>
                      <div className="text-xs font-bold" style={{ color: '#1A1A2E' }}>GitHub Backup</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>
                        {gitBackup.last_backup
                          ? `Last: ${new Date(gitBackup.last_backup).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
                          : 'No backups yet'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      gitBackup.status === 'current' ? 'bg-green-50 text-green-600' :
                      gitBackup.status === 'behind' ? 'bg-yellow-50 text-yellow-600' :
                      'bg-gray-50 text-gray-500'
                    }`} data-testid="git-backup-status">
                      {gitBackup.status === 'current' ? 'Current' : gitBackup.status === 'behind' ? 'Behind' : 'Never'}
                    </span>
                    <span className="text-[10px]" style={{ color: '#888' }}>{gitBackup.total_backups || 0} total</span>
                    {gitBackup.fail_streak > 0 && (
                      <span className="text-[10px] text-red-500">{gitBackup.fail_streak}x failed</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Health Sparkline */}
            {pulses.length > 1 && (
              <div className="mb-6 p-4 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="health-sparkline">
                <div className="flex items-center gap-2 mb-3">
                  <Activity className="w-4 h-4 text-[#FF6B00]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Health Over Time</span>
                  <span className="text-[10px] text-[#888] ml-auto">{pulses.length} cycles</span>
                </div>
                <div className="h-16 flex items-end gap-0.5">
                  {pulses.map((p, i) => {
                    const score = p.health_score || 0;
                    const color = score >= 80 ? '#4ade80' : score >= 60 ? '#D4B977' : '#FF6B6B';
                    return (
                      <div key={i} className="flex-1 rounded-t transition-all" style={{ height: `${Math.max(score, 5)}%`, background: color, opacity: 0.8 }}
                        title={`Cycle ${p.cycle_number}: ${score}/100`} />
                    );
                  })}
                </div>
              </div>
            )}

            {/* Last Issue */}
            {status?.last_issue && (
              <div className="mb-4 p-4 rounded-xl flex items-center gap-3" style={{ background: 'rgba(255,107,107,0.04)', border: '1px solid rgba(255,107,107,0.12)' }} data-testid="last-issue">
                <AlertTriangle className="w-5 h-5 text-[#FF6B6B] flex-shrink-0" />
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-bold text-[#1A1A2E]">{status.last_issue.service}</span>
                    <SeverityBadge severity={status.last_issue.severity} />
                  </div>
                  <span className="text-[10px] text-[#888]">{status.last_issue.error}</span>
                </div>
              </div>
            )}

            {/* Sovereign Brain Status */}
            {modelRouting && (
              <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.3)' }} data-testid="sovereign-brain">
                <div className="flex items-center gap-2 mb-3">
                  <Zap className="w-4 h-4 text-[#D4AF37]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Sovereign Brain — {modelRouting.mode || '$0 FREE'}</span>
                  <span className="text-[8px] px-1.5 py-0.5 rounded font-bold" style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80' }}>
                    {modelRouting.estimated_cost || '$0/mo'}
                  </span>
                </div>
                {modelRouting.ora_brain && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div className="p-2 rounded-lg bg-white/40">
                      <span className="text-[8px] font-bold text-[#888] tracking-wider block mb-0.5">GENERAL</span>
                      <span className="text-[9px] text-[#1A1A2E] font-mono">{(modelRouting.ora_brain.general || '').split('/').pop()}</span>
                    </div>
                    <div className="p-2 rounded-lg bg-white/40">
                      <span className="text-[8px] font-bold text-[#888] tracking-wider block mb-0.5">ANALYSIS</span>
                      <span className="text-[9px] text-[#1A1A2E] font-mono">{(modelRouting.ora_brain.analysis || '').split('/').pop()}</span>
                    </div>
                    <div className="p-2 rounded-lg bg-white/40">
                      <span className="text-[8px] font-bold text-[#888] tracking-wider block mb-0.5">SEARCH</span>
                      <span className="text-[9px] text-[#1A1A2E] font-mono">{(modelRouting.ora_brain.search || '').split('/').pop()}</span>
                    </div>
                  </div>
                )}
                {modelRouting.free_models && (
                  <div className="mt-2 text-[9px] text-[#888]">
                    Fallback chain: {modelRouting.free_models.length} free models → paid (last resort)
                  </div>
                )}
              </div>
            )}

            {/* ScoutSearch Stats */}
            {searchStats && searchStats.total_searches > 0 && (
              <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(100,200,255,0.04)', border: '1px solid rgba(100,200,255,0.12)' }} data-testid="scout-search-stats">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-[#64C8FF]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">ScoutSearch</span>
                  <span className="text-[9px] text-[#888] ml-auto">Last: {searchStats.last_source || 'none'}</span>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <div className="text-center">
                    <div className="text-sm font-bold text-[#1A1A2E]">{searchStats.total_searches}</div>
                    <div className="text-[8px] text-[#888]">Searches</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-[#4ade80]">{searchStats.duckduckgo_hits}</div>
                    <div className="text-[8px] text-[#888]">DDG Hits</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-[#1A1A2E]">{searchStats.avg_response_ms}ms</div>
                    <div className="text-[8px] text-[#888]">Avg Time</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold" style={{ color: searchStats.failures > 0 ? '#FF6B6B' : '#4ade80' }}>{searchStats.failures}</div>
                    <div className="text-[8px] text-[#888]">Failures</div>
                  </div>
                </div>
              </div>
            )}

            {/* Last Fix */}
            {status?.last_fix && status.last_fix.success && (
              <div className="mb-4 p-4 rounded-xl flex items-center gap-3" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.3)' }} data-testid="last-fix">
                <CheckCircle className="w-5 h-5 text-[#4ade80] flex-shrink-0" />
                <div>
                  <span className="text-xs font-bold text-[#FF6B00]">Auto-Fixed: {status.last_fix.fix_type}</span>
                  <p className="text-[10px] text-[#888]">{status.last_fix.message}</p>
                </div>
              </div>
            )}

            {/* Expandable Sections */}
            <ExpandSection title="Auto-Fix Log" icon={<Zap className="w-4 h-4" />} count={fixes.length} expanded={expandedSection === 'fixes'} onToggle={() => setExpandedSection(expandedSection === 'fixes' ? '' : 'fixes')} testid="fixes-section">
              {fixes.length === 0 ? (
                <p className="text-xs text-[#888] py-4 text-center">No auto-fixes applied yet.</p>
              ) : (
                <div className="space-y-2">
                  {fixes.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/40">
                      {f.resolved ? <CheckCircle className="w-3.5 h-3.5 text-[#4ade80]" /> : <XCircle className="w-3.5 h-3.5 text-[#FF6B6B]" />}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-[#1A1A2E]">{f.service || f.check_name}</span>
                          <span className="text-[8px] text-[#888]">{f.fix_type}</span>
                        </div>
                        <span className="text-[10px] text-[#888] truncate block">{f.action_taken || f.issue_found}</span>
                      </div>
                      <span className="text-[9px] text-[#888] flex-shrink-0">{f.timestamp ? new Date(f.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </ExpandSection>

            <ExpandSection title="Alerts" icon={<AlertTriangle className="w-4 h-4" />} count={alerts.length} expanded={expandedSection === 'alerts'} onToggle={() => setExpandedSection(expandedSection === 'alerts' ? '' : 'alerts')} testid="alerts-section">
              {alerts.length === 0 ? (
                <p className="text-xs text-[#888] py-4 text-center">No alerts. All clear.</p>
              ) : (
                <div className="space-y-2">
                  {alerts.map((a, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-white/40">
                      <div className="flex items-center gap-2 mb-1">
                        <SeverityBadge severity={a.severity} />
                        <span className="text-[10px] font-bold text-[#1A1A2E]">{a.service}</span>
                        <span className="text-[9px] text-[#888] ml-auto">{a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : ''}</span>
                      </div>
                      <p className="text-[10px] text-[#888]">{a.error || a.message}</p>
                      {a.diagnosis && <p className="text-[10px] text-[#FF6B00] italic mt-0.5">{a.diagnosis}</p>}
                    </div>
                  ))}
                </div>
              )}
            </ExpandSection>

            <ExpandSection title="Known Fixes (Learned)" icon={<Database className="w-4 h-4" />} count={knownFixes.length} expanded={expandedSection === 'known'} onToggle={() => setExpandedSection(expandedSection === 'known' ? '' : 'known')} testid="known-section">
              {knownFixes.length === 0 ? (
                <p className="text-xs text-[#888] py-4 text-center">No learned patterns yet. Sentinel learns from every fix.</p>
              ) : (
                <div className="space-y-2">
                  {knownFixes.map((kf, i) => (
                    <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/40">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold" style={{ background: `rgba(45,122,74,${Math.min(kf.success_rate || 0.5, 1) * 0.15})`, color: '#FF6B00' }}>
                        {Math.round((kf.success_rate || 0) * 100)}%
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-[10px] font-bold text-[#1A1A2E]">{kf.issue_pattern}</span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[9px] text-[#888]">Applied {kf.times_applied}x</span>
                          <span className="text-[9px] text-[#FF6B00]">{kf.fix_type}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ExpandSection>
          </>
          ) : (
          /* ═══════ COST SAVINGS TAB ═══════ */
          <div data-testid="cost-savings-tab">
            {/* Card Row: Today + Month + All Time */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {/* Card 1 — Today */}
              <div className="p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="cost-today">
                <div className="flex items-center gap-2 mb-3">
                  <Zap className="w-4 h-4 text-[#4ade80]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">Today's Savings</span>
                </div>
                <div className="text-2xl font-bold text-[#4ade80] mb-1">
                  ${(costToday?.estimated_saved || 0).toFixed(2)}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-[#888]">
                  <span>{costToday?.free_queries || 0} free</span>
                  <span className="text-[#FF6B6B]">{costToday?.paid_queries || 0} paid</span>
                  <span>{costToday?.total_queries || 0} total</span>
                </div>
              </div>

              {/* Card 2 — Month */}
              <div className="p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="cost-month">
                <div className="flex items-center gap-2 mb-3">
                  <Activity className="w-4 h-4 text-[#D4AF37]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">This Month</span>
                </div>
                <div className="text-2xl font-bold text-[#D4AF37] mb-1">
                  ${(costMonth?.estimated_saved || 0).toFixed(2)}
                </div>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="text-[#4ade80] font-bold">{costMonth?.free_pct || 100}% free</span>
                  <span className="text-[#FF6B6B]">{costMonth?.paid_pct || 0}% paid</span>
                  <span className="text-[#888]">{costMonth?.total_queries || 0} queries</span>
                </div>
              </div>

              {/* Card 3 — All Time */}
              <div className="p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid="cost-alltime">
                <div className="flex items-center gap-2 mb-3">
                  <Database className="w-4 h-4 text-[#FF6B00]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">All Time</span>
                </div>
                <div className="text-2xl font-bold text-[#FF6B00] mb-1">
                  ${(costAlltime?.total_saved || 0).toFixed(2)}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-[#888]">
                  <span>{costAlltime?.total_queries || 0} total queries</span>
                  <span className="text-[#4ade80]">{costAlltime?.free_queries || 0} free</span>
                  <span className="text-[#FF6B6B]">{costAlltime?.paid_queries || 0} paid</span>
                </div>
              </div>
            </div>

            {/* 7-Day Bar Chart */}
            <div className="p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl mb-6" data-testid="cost-chart">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4 text-[#FF6B00]" />
                <span className="text-[10px] font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">7-Day Query Breakdown</span>
                <div className="flex items-center gap-3 ml-auto">
                  <span className="flex items-center gap-1 text-[9px]"><span className="w-2.5 h-2.5 rounded-sm bg-[#4ade80]" /> Free</span>
                  <span className="flex items-center gap-1 text-[9px]"><span className="w-2.5 h-2.5 rounded-sm bg-[#FF9500]" /> Paid</span>
                </div>
              </div>
              {costChart.length > 0 ? (
                <div className="flex items-end gap-2 h-32">
                  {costChart.map((day, i) => {
                    const total = day.free + day.paid;
                    const maxTotal = Math.max(...costChart.map(d => d.free + d.paid), 1);
                    const barH = total > 0 ? Math.max((total / maxTotal) * 100, 4) : 4;
                    const freeH = total > 0 ? (day.free / total) * barH : barH;
                    const paidH = total > 0 ? (day.paid / total) * barH : 0;
                    const dayLabel = day.date ? day.date.slice(5) : '';
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <div className="w-full flex flex-col-reverse rounded-t-sm overflow-hidden" style={{ height: `${barH}%` }}>
                          <div style={{ height: `${freeH}%`, background: '#4ade80' }} />
                          {paidH > 0 && <div style={{ height: `${paidH}%`, background: '#FF9500' }} />}
                        </div>
                        <span className="text-[8px] text-[#888]">{dayLabel}</span>
                        {total > 0 && <span className="text-[8px] text-[#1A1A2E] font-bold">{total}</span>}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8 text-xs text-[#888]">No query data yet. Start chatting with ORA to see savings.</div>
              )}
            </div>

            {/* Card 4 — Model Performance Table */}
            {costAlltime?.model_rankings?.length > 0 && (
              <div className="p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl mb-6" data-testid="model-performance">
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="w-4 h-4 text-[#FF6B00]" />
                  <span className="text-[10px] font-bold tracking-[1.5px] text-[#1A1A2E] uppercase">Model Performance</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px]">
                    <thead>
                      <tr className="text-[#888] text-left border-b border-white/40">
                        <th className="pb-2 font-bold tracking-wider">Model</th>
                        <th className="pb-2 font-bold tracking-wider text-center">Queries</th>
                        <th className="pb-2 font-bold tracking-wider text-center">Success</th>
                        <th className="pb-2 font-bold tracking-wider text-center">Avg ms</th>
                        <th className="pb-2 font-bold tracking-wider text-right">Saved</th>
                      </tr>
                    </thead>
                    <tbody>
                      {costAlltime.model_rankings.map((m, i) => (
                        <tr key={i} className="border-b border-white/20">
                          <td className="py-2 font-mono text-[#1A1A2E]">
                            {(m.model || '').split('/').pop()}
                            {(m.model || '').includes(':free') && (
                              <span className="ml-1 text-[8px] px-1 py-0.5 rounded bg-[rgba(74,222,128,0.1)] text-[#4ade80] font-bold">FREE</span>
                            )}
                          </td>
                          <td className="py-2 text-center text-[#1A1A2E] font-bold">{m.queries}</td>
                          <td className="py-2 text-center">
                            <span className={m.success_rate >= 90 ? 'text-[#4ade80]' : m.success_rate >= 70 ? 'text-[#D4AF37]' : 'text-[#FF6B6B]'} style={{ fontWeight: 700 }}>
                              {m.success_rate}%
                            </span>
                          </td>
                          <td className="py-2 text-center text-[#888]">{m.avg_response_ms}ms</td>
                          <td className="py-2 text-right text-[#4ade80] font-bold">${m.total_saved.toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
          )}
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub, color, testid }) {
  return (
    <div className="p-3.5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid={testid}>
      <div className="flex items-center gap-2 mb-1.5">
        <div style={{ color }}>{icon}</div>
        <span className="text-[9px] font-bold tracking-[1.5px] text-[#888] uppercase">{label}</span>
      </div>
      <div className="text-lg font-bold text-[#1A1A2E]" style={{ color: typeof value === 'string' ? color : undefined }}>{value}</div>
      <span className="text-[9px] text-[#888]">{sub}</span>
    </div>
  );
}

function ExpandSection({ title, icon, count, expanded, onToggle, children, testid }) {
  return (
    <div className="mb-3" data-testid={testid}>
      <button onClick={onToggle} className="w-full flex items-center gap-3 p-3.5 rounded-xl bg-white/70 backdrop-blur-sm border border-white/40 hover:bg-white/90 transition-all">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(255,107,0,0.05)' }}>
          {icon}
        </div>
        <span className="text-xs font-bold text-[#1A1A2E] tracking-wide flex-1 text-left">{title}</span>
        {count > 0 && <span className="text-[9px] font-bold text-[#888]">{count}</span>}
        {expanded ? <ChevronDown className="w-4 h-4 text-[#888]" /> : <ChevronRight className="w-4 h-4 text-[#888]" />}
      </button>
      {expanded && <div className="mt-1 p-3 rounded-xl bg-white/50 border border-white/30">{children}</div>}
    </div>
  );
}
