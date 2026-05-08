/**
 * ASI-Evolve Dashboard — Self-Improvement Loop Visualization
 * Shows evolution history, pending approvals, active instructions, lineage view
 */
import React, { useState, useEffect, useCallback , useMemo } from 'react';
import {
  Sparkles, Check, X, Clock, AlertTriangle, Brain, Zap,
  TrendingUp, Shield, RefreshCw, ChevronRight, Activity
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const ASIEvolveDashboard = ({ token }) => {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [pending, setPending] = useState([]);
  const [activeInstructions, setActiveInstructions] = useState([]);
  const [triggering, setTriggering] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, histRes, pendRes, instrRes] = await Promise.all([
        fetch(`${API}/api/asi-evolve/stats`, { headers }),
        fetch(`${API}/api/asi-evolve/history?limit=15`, { headers }),
        fetch(`${API}/api/asi-evolve/pending`, { headers }),
        fetch(`${API}/api/asi-evolve/active-instructions`, { headers }),
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (histRes.ok) { const d = await histRes.json(); setHistory(d.evolutions || []); }
      if (pendRes.ok) { const d = await pendRes.json(); setPending(d.pending || []); }
      if (instrRes.ok) { const d = await instrRes.json(); setActiveInstructions(d.instructions || []); }
    } catch (e) { console.error('ASI-Evolve fetch error:', e); }
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const triggerCycle = async () => {
    setTriggering(true);
    try {
      const res = await fetch(`${API}/api/asi-evolve/trigger`, { method: 'POST', headers });
      if (res.ok) { await fetchData(); }
    } catch (e) { console.error(e); }
    finally { setTriggering(false); }
  };

  const handleApprove = async (patternId) => {
    try {
      const res = await fetch(`${API}/api/asi-evolve/approve/${patternId}`, { method: 'POST', headers });
      if (res.ok) await fetchData();
    } catch (e) { console.error(e); }
  };

  const handleReject = async (patternId) => {
    try {
      const res = await fetch(`${API}/api/asi-evolve/reject/${patternId}`, { method: 'POST', headers });
      if (res.ok) await fetchData();
    } catch (e) { console.error(e); }
  };

  const card = {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,107,0,0.12)',
    borderRadius: 12,
    padding: 20,
  };

  const tabBtn = (id) => ({
    padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 500, cursor: 'pointer',
    border: 'none', display: 'flex', alignItems: 'center', gap: 6, transition: 'all 0.2s',
    background: activeTab === id ? 'linear-gradient(135deg, #FF6B00, #CC5500)' : 'rgba(255,255,255,0.04)',
    color: activeTab === id ? '#fff' : 'rgba(255,255,255,0.5)',
  });

  const statusColor = (s) => s === 'approved' ? '#4ade80' : s === 'pending_approval' ? '#f59e0b' : '#ef4444';
  const statusBg = (s) => s === 'approved' ? 'rgba(74,222,128,0.1)' : s === 'pending_approval' ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)';

  return (
    <div data-testid="asi-evolve-dashboard" className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-light tracking-wider mb-1" style={{ color: 'var(--aurem-heading)', fontFamily: 'var(--aurem-font-heading)' }}>
              ASI-Evolve
            </h1>
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
              Self-Improvement Loop — Recursive Prompt Optimization
            </p>
          </div>
          <button onClick={triggerCycle} disabled={triggering} data-testid="trigger-evolution-btn"
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-opacity disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)', color: '#fff', border: 'none' }}>
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? 'animate-spin' : ''}`} />
            {triggering ? 'Evolving...' : 'Trigger Cycle'}
          </button>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {[
              { label: 'Total Evolutions', value: stats.total_evolutions, icon: Brain, color: '#FF6B00' },
              { label: 'Approved', value: stats.approved, icon: Check, color: '#4ade80' },
              { label: 'Pending', value: stats.pending_approval, icon: Clock, color: '#f59e0b' },
              { label: 'Active Instructions', value: stats.active_instructions, icon: Zap, color: '#a855f7' },
            ].map((s, i) => (
              <div key={i} style={card} className="flex items-center gap-3" data-testid={`stat-${s.label.toLowerCase().replace(/\s/g,'-')}`}>
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${s.color}15` }}>
                  <s.icon className="w-4 h-4" style={{ color: s.color }} />
                </div>
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--aurem-heading)' }}>{s.value}</div>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{s.label}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cycles Run strip — shows activity even when no evolutions generated */}
        {stats && (stats.cycles_run > 0 || stats.last_cycle) && (
          <div style={{ ...card, marginBottom: 16, padding: 12 }} data-testid="asi-cycles-strip" className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <RefreshCw className="w-3.5 h-3.5" style={{ color: '#FF6B00' }} />
              <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>
                {stats.cycles_run || 0} cycle{stats.cycles_run === 1 ? '' : 's'} run
              </span>
              {stats.last_cycle && (
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                  · last: {stats.last_cycle.status}
                  {stats.last_cycle.failures_analyzed > 0 ? ` · ${stats.last_cycle.failures_analyzed} failures analyzed` : ''}
                  {stats.last_cycle.patterns_detected > 0 ? ` · ${stats.last_cycle.patterns_detected} patterns` : ''}
                </span>
              )}
            </div>
            {stats.last_cycle?.created_at && (
              <span className="text-[10px] font-mono" style={{ color: 'var(--aurem-body-secondary)' }}>
                {new Date(stats.last_cycle.created_at).toLocaleString()}
              </span>
            )}
          </div>
        )}

        {/* Success Rate Bar */}
        {stats && stats.total_evolutions > 0 && (
          <div style={{ ...card, marginBottom: 16, padding: 16 }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>Evolution Success Rate</span>
              <span className="text-xs font-bold" style={{ color: '#FF6B00' }}>{stats.success_rate}%</span>
            </div>
            <div className="w-full h-2 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <div className="h-full rounded-full transition-all" style={{ width: `${stats.success_rate}%`, background: 'linear-gradient(90deg, #FF6B00, #D4AF37)' }} />
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-5">
          {[
            { id: 'overview', label: 'Lineage', icon: TrendingUp },
            { id: 'pending', label: `Approvals (${pending.length})`, icon: Shield },
            { id: 'active', label: 'Active Instructions', icon: Zap },
          ].map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)} style={tabBtn(t.id)} data-testid={`tab-${t.id}`}>
              <t.icon className="w-3.5 h-3.5" /> {t.label}
            </button>
          ))}
        </div>

        {/* Lineage Tab — Before/After Evolution View */}
        {activeTab === 'overview' && (
          <div className="space-y-3">
            {history.length === 0 ? (
              <div style={card} className="text-center py-12">
                <Brain className="w-12 h-12 mx-auto mb-3" style={{ color: 'rgba(255,255,255,0.12)' }} />
                <p className="text-sm mb-1" style={{ color: 'rgba(255,255,255,0.65)' }}>No evolutions yet</p>
                <p className="text-[10px]" style={{ color: 'rgba(255,255,255,0.6)' }}>Trigger a cycle to start the self-improvement loop</p>
              </div>
            ) : history.map((evo, i) => (
              <div key={i} style={card} data-testid={`evolution-${evo.pattern_id}`}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${statusColor(evo.status)}15` }}>
                      {evo.status === 'approved' ? <Check className="w-3.5 h-3.5" style={{ color: statusColor(evo.status) }} /> :
                       evo.status === 'pending_approval' ? <Clock className="w-3.5 h-3.5" style={{ color: statusColor(evo.status) }} /> :
                       <X className="w-3.5 h-3.5" style={{ color: statusColor(evo.status) }} />}
                    </div>
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{evo.domain}</span>
                      {evo.requires_approval && (
                        <span className="ml-2 px-1.5 py-0.5 text-[9px] rounded" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                          PROTECTED
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 text-[10px] font-medium rounded-full"
                    style={{ background: statusBg(evo.status), color: statusColor(evo.status) }}>
                    {(evo.status || '').replace('_', ' ')}
                  </span>
                </div>

                {/* Root Cause */}
                <p className="text-[11px] mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {evo.root_cause}
                </p>

                {/* Before / After Lineage */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
                  <div className="p-3 rounded-lg" style={{ background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.1)' }}>
                    <div className="text-[9px] font-bold mb-1 tracking-wider" style={{ color: '#ef4444' }}>BEFORE</div>
                    <p className="text-[10px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.5)' }}>
                      {evo.original_instruction || 'Default system instruction'}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg" style={{ background: 'rgba(74,222,128,0.04)', border: '1px solid rgba(74,222,128,0.1)' }}>
                    <div className="text-[9px] font-bold mb-1 tracking-wider" style={{ color: '#4ade80' }}>AFTER (Evolved)</div>
                    <p className="text-[10px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.5)' }}>
                      {evo.evolved_instruction || 'Generating...'}
                    </p>
                  </div>
                </div>

                {/* Shadow Test Result */}
                {evo.shadow_test && (
                  <div className="flex items-center gap-4 px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)' }}>
                    <div className="flex items-center gap-1.5">
                      <Activity className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Shadow Test:</span>
                    </div>
                    <span className="text-[10px] font-mono" style={{ color: '#ef4444' }}>A: {evo.shadow_test.run_a_score}%</span>
                    <ChevronRight className="w-3 h-3" style={{ color: 'var(--aurem-body-secondary)' }} />
                    <span className="text-[10px] font-mono" style={{ color: '#4ade80' }}>B: {evo.shadow_test.run_b_score}%</span>
                    <span className="text-[10px] font-bold ml-auto" style={{ color: evo.shadow_test.passed ? '#4ade80' : '#ef4444' }}>
                      {evo.shadow_test.passed ? `+${evo.shadow_test.improvement_pct}%` : `NEURAL NOISE (${evo.shadow_test.improvement_pct}%)`}
                    </span>
                  </div>
                )}

                <div className="mt-2 text-right">
                  <span className="text-[9px]" style={{ color: 'rgba(255,255,255,0.55)' }}>
                    {evo.created_at ? new Date(evo.created_at).toLocaleString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pending Approvals Tab */}
        {activeTab === 'pending' && (
          <div className="space-y-3">
            {pending.length === 0 ? (
              <div style={card} className="text-center py-12">
                <Shield className="w-12 h-12 mx-auto mb-3" style={{ color: 'rgba(255,255,255,0.12)' }} />
                <p className="text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>No pending approvals</p>
              </div>
            ) : pending.map((evo, i) => (
              <div key={i} style={{ ...card, borderColor: 'rgba(245,158,11,0.25)' }} data-testid={`pending-${evo.pattern_id}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <span className="text-xs font-medium" style={{ color: '#f59e0b' }}>{evo.domain}</span>
                    <span className="ml-2 px-1.5 py-0.5 text-[9px] rounded" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
                      MANUAL APPROVAL REQUIRED
                    </span>
                  </div>
                </div>

                <p className="text-[11px] mb-2" style={{ color: 'var(--aurem-body-secondary)' }}>{evo.root_cause}</p>

                <div className="p-3 rounded-lg mb-3" style={{ background: 'rgba(74,222,128,0.04)', border: '1px solid rgba(74,222,128,0.1)' }}>
                  <div className="text-[9px] font-bold mb-1 tracking-wider" style={{ color: '#4ade80' }}>PROPOSED EVOLUTION</div>
                  <p className="text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{evo.evolved_instruction}</p>
                </div>

                <div className="flex gap-2">
                  <button onClick={() => handleApprove(evo.pattern_id)} data-testid={`approve-${evo.pattern_id}`}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg"
                    style={{ background: 'rgba(74,222,128,0.12)', color: '#4ade80', border: '1px solid rgba(74,222,128,0.2)' }}>
                    <Check className="w-3.5 h-3.5" /> Approve
                  </button>
                  <button onClick={() => handleReject(evo.pattern_id)} data-testid={`reject-${evo.pattern_id}`}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg"
                    style={{ background: 'rgba(239,68,68,0.08)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                    <X className="w-3.5 h-3.5" /> Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Active Instructions Tab */}
        {activeTab === 'active' && (
          <div className="space-y-3">
            {activeInstructions.length === 0 ? (
              <div style={card} className="text-center py-12">
                <Zap className="w-12 h-12 mx-auto mb-3" style={{ color: 'rgba(255,255,255,0.12)' }} />
                <p className="text-sm" style={{ color: 'rgba(255,255,255,0.65)' }}>No active evolved instructions</p>
                <p className="text-[10px]" style={{ color: 'rgba(255,255,255,0.6)' }}>Approved evolutions will appear here as active instructions in the knowledge base</p>
              </div>
            ) : activeInstructions.map((instr, i) => (
              <div key={i} style={{ ...card, borderColor: 'rgba(168,85,247,0.2)' }} data-testid={`instruction-${instr.pattern_id}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4" style={{ color: '#a855f7' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{instr.domain}</span>
                  </div>
                  <span className="text-[10px] font-mono" style={{ color: '#a855f7' }}>
                    confidence: {Math.round((instr.confidence || 0) * 100)}%
                  </span>
                </div>
                <p className="text-[11px] mb-2" style={{ color: 'rgba(255,255,255,0.5)' }}>{instr.instruction}</p>
                <div className="flex items-center gap-3 text-[9px]" style={{ color: 'rgba(255,255,255,0.6)' }}>
                  <span>Targets: {(instr.target_stages || []).join(', ')}</span>
                  <span>Deployed: {instr.deployed_at ? new Date(instr.deployed_at).toLocaleString() : 'N/A'}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ASIEvolveDashboard;
