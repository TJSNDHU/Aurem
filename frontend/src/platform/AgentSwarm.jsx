/**
 * AUREM Agent Swarm Dashboard
 * Deploy and manage AI agent teams - Scout, Architect, Closer, Envoy, and Orchestrator
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, Brain, Zap, Activity, RefreshCw, Play, Pause,
  Settings, ChevronRight, Shield, Target, Eye, Clock,
  MessageSquare, TrendingUp, CheckCircle, AlertCircle,
  BarChart3, ArrowUpRight, Cpu, Workflow
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const AGENT_CONFIGS = [
  {
    id: 'scout',
    name: 'Scout Agent',
    role: 'Market Intelligence',
    description: 'Scans markets, analyzes competitors, and identifies growth opportunities',
    capabilities: ['Market Analysis', 'Competitor Tracking', 'Lead Discovery', 'Trend Detection'],
    color: '#D4AF37',
    metrics: { tasks_completed: 0, success_rate: 0, avg_time: '0s' }
  },
  {
    id: 'architect',
    name: 'Architect Agent',
    role: 'Strategy Builder',
    description: 'Designs automation pipelines, optimizes workflows, and builds integrations',
    capabilities: ['Pipeline Design', 'Workflow Optimization', 'Integration Setup', 'A/B Testing'],
    color: '#3b82f6',
    metrics: { tasks_completed: 0, success_rate: 0, avg_time: '0s' }
  },
  {
    id: 'closer',
    name: 'Closer Agent',
    role: 'Deal Conversion',
    description: 'Manages negotiations, generates proposals, and closes deals',
    capabilities: ['Deal Negotiation', 'Proposal Generation', 'Contract Review', 'Upsell Detection'],
    color: '#4ade80',
    metrics: { tasks_completed: 0, success_rate: 0, avg_time: '0s' }
  },
  {
    id: 'envoy',
    name: 'Envoy Agent',
    role: 'Communication Hub',
    description: 'Handles multi-channel communication — email, WhatsApp, chat, and voice',
    capabilities: ['Email Drafting', 'WhatsApp Replies', 'Voice Handling', 'Sentiment Analysis'],
    color: '#8B5CF6',
    metrics: { tasks_completed: 0, success_rate: 0, avg_time: '0s' }
  },
  {
    id: 'orchestrator',
    name: 'Orchestrator',
    role: 'Swarm Commander',
    description: 'Coordinates all agents, assigns tasks, and optimizes swarm performance',
    capabilities: ['Task Assignment', 'Load Balancing', 'Conflict Resolution', 'Performance Tuning'],
    color: '#f59e0b',
    metrics: { tasks_completed: 0, success_rate: 0, avg_time: '0s' }
  }
];

export default function AgentSwarm({ token }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [swarmStatus, setSwarmStatus] = useState('active');
  const [executing, setExecuting] = useState(null);
  const [executionResults, setExecutionResults] = useState({});
  const [swarmRunning, setSwarmRunning] = useState(false);
  const [swarmResult, setSwarmResult] = useState(null);
  const [auditChain, setAuditChain] = useState([]);

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/agents/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.agents && data.agents.length > 0) {
          setAgents(data.agents.map((a, i) => ({
            ...AGENT_CONFIGS[i % AGENT_CONFIGS.length],
            ...a,
            status: 'active',
          })));
        } else {
          setAgents(AGENT_CONFIGS.map(a => ({ ...a, status: 'active' })));
        }
      } else {
        setAgents(AGENT_CONFIGS.map(a => ({ ...a, status: 'active' })));
      }
    } catch {
      setAgents(AGENT_CONFIGS.map(a => ({ ...a, status: 'active' })));
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchAuditChain = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/agents/audit-chain?limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAuditChain(data.chain || []);
      }
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => {
    fetchAgents();
    fetchAuditChain();
  }, [fetchAgents, fetchAuditChain]);

  const executeAgent = async (agentId) => {
    setExecuting(agentId);
    try {
      const res = await fetch(`${API_URL}/api/agents/execute`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, action: 'auto', parameters: {} }),
      });
      if (res.ok) {
        const data = await res.json();
        setExecutionResults(prev => ({ ...prev, [agentId]: data.result }));
        fetchAuditChain();
      }
    } catch (e) {
      console.error('Agent execution failed:', e);
    } finally {
      setExecuting(null);
    }
  };

  const executeSwarm = async () => {
    setSwarmRunning(true);
    setSwarmResult(null);
    try {
      const res = await fetch(`${API_URL}/api/agents/swarm/execute`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective: 'Full business analysis', auto_select: true }),
      });
      if (res.ok) {
        const data = await res.json();
        setSwarmResult(data);
        // Update execution results from swarm
        Object.entries(data.results || {}).forEach(([id, r]) => {
          if (r.status === 'completed') {
            setExecutionResults(prev => ({ ...prev, [id]: r.result }));
          }
        });
        fetchAuditChain();
      }
    } catch (e) {
      console.error('Swarm execution failed:', e);
    } finally {
      setSwarmRunning(false);
    }
  };

  const handleToggleAgent = (agentId) => {
    setAgents(prev => prev.map(a =>
      a.id === agentId ? { ...a, status: a.status === 'active' ? 'standby' : 'active' } : a
    ));
  };

  const totalTasks = agents.reduce((sum, a) => sum + (a.metrics?.tasks_completed || 0), 0);
  const avgSuccess = agents.length > 0
    ? Math.round(agents.reduce((sum, a) => sum + (a.metrics?.success_rate || 0), 0) / agents.length)
    : 0;
  const activeCount = agents.filter(a => a.status === 'active').length;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="agent-swarm-loading">
        <div className="flex items-center gap-3 text-[#666]">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading agent swarm...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--aurem-bg)' }} data-testid="agent-swarm">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold tracking-wider mb-1" style={{ color: '#e2c97e' }}>Agent Swarm</h1>
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Deploy ORA agent teams — Scout, Architect, Closer, Envoy, and Oracle working together</p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-medium ${
              swarmStatus === 'active'
                ? 'bg-[#4ade80]/10 text-[#4ade80]'
                : 'bg-[#f59e0b]/10 text-[#f59e0b]'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${
                swarmStatus === 'active' ? 'bg-[#4ade80]' : 'bg-[#f59e0b]'
              }`} />
              SWARM {swarmStatus.toUpperCase()}
            </div>
            <button
              onClick={() => setSwarmStatus(s => s === 'active' ? 'paused' : 'active')}
              data-testid="toggle-swarm-btn"
              className="flex items-center gap-2 px-4 py-2 text-xs border border-[#FF6B00]/15 rounded-lg transition-colors"
              style={{ color: 'var(--aurem-body-secondary)' }}
            >
              {swarmStatus === 'active' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              {swarmStatus === 'active' ? 'Pause' : 'Resume'}
            </button>
            <button
              onClick={executeSwarm}
              disabled={swarmRunning}
              data-testid="execute-swarm-btn"
              className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg text-white transition-all"
              style={{ background: swarmRunning ? '#555' : 'linear-gradient(135deg, #FF6B00, #4ADE80)' }}
            >
              {swarmRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
              {swarmRunning ? 'Executing...' : 'Execute All Agents'}
            </button>
          </div>
        </div>

        {/* Swarm Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'TOTAL AGENTS', value: agents.length, icon: Users, color: '#D4AF37' },
            { label: 'ACTIVE', value: activeCount, icon: Activity, color: '#4ade80' },
            { label: 'TASKS COMPLETED', value: totalTasks.toLocaleString(), icon: CheckCircle, color: '#D4AF37' },
            { label: 'AVG SUCCESS', value: `${avgSuccess}%`, icon: Target, color: '#4ade80' }
          ].map((stat, idx) => (
            <div key={idx} className="p-4 rounded-lg" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                <span className="text-[9px] tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>{stat.label}</span>
              </div>
              <div className="text-2xl font-semibold font-mono" style={{ color: stat.color }}>{stat.value}</div>
            </div>
          ))}
        </div>

        {/* Agent Grid */}
        <div className="space-y-4">
          {agents.map(agent => (
            <div
              key={agent.id}
              data-testid={`agent-card-${agent.id}`}
              className={`p-5 rounded-xl transition-all cursor-pointer`}
              style={{
                background: 'var(--aurem-card-bg)',
                border: selectedAgent?.id === agent.id ? '1px solid #D4AF3766' : '1px solid var(--aurem-border)',
              }}
              onClick={() => setSelectedAgent(selectedAgent?.id === agent.id ? null : agent)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  {/* Agent Avatar */}
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center"
                    style={{ backgroundColor: `${agent.color}15` }}
                  >
                    <Brain className="w-6 h-6" style={{ color: agent.color }} />
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>{agent.name}</h3>
                      <span className="text-[9px] tracking-wider px-2 py-0.5 rounded-full" style={{ backgroundColor: `${agent.color}15`, color: agent.color }}>
                        {agent.role}
                      </span>
                    </div>
                    <p className="text-[11px] mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>{agent.description}</p>

                    {/* Capabilities */}
                    <div className="flex flex-wrap gap-1.5">
                      {agent.capabilities.map((cap, i) => (
                        <span key={i} className="px-2 py-0.5 text-[9px] bg-white/50 text-[#888] rounded border border-[#FF6B00]/15">
                          {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {/* Metrics */}
                  <div className="flex items-center gap-4 text-[10px] text-[#555] mr-3">
                    <div className="text-center">
                      <div className="font-mono text-sm text-[#1A1A2E]">{agent.metrics?.tasks_completed || 0}</div>
                      <div>tasks</div>
                    </div>
                    <div className="text-center">
                      <div className="font-mono text-sm text-[#4ade80]">{agent.metrics?.success_rate || 0}%</div>
                      <div>success</div>
                    </div>
                    <div className="text-center">
                      <div className="font-mono text-sm text-[#1A1A2E]">{agent.metrics?.avg_time || '0s'}</div>
                      <div>avg time</div>
                    </div>
                  </div>

                  {/* Status & Toggle */}
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${
                      agent.status === 'active'
                        ? 'bg-[#4ade80]/10 text-[#4ade80]'
                        : 'bg-[#555]/10 text-[#555]'
                    }`}>
                      {agent.status === 'active' ? 'Active' : 'Standby'}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleToggleAgent(agent.id); }}
                      data-testid={`toggle-agent-${agent.id}`}
                      className={`w-10 h-5 rounded-full transition-colors relative ${
                        agent.status === 'active' ? 'bg-[#4ade80]' : 'bg-[#333]'
                      }`}
                    >
                      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                        agent.status === 'active' ? 'translate-x-5' : 'translate-x-0.5'
                      }`} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Expanded Details */}
              {selectedAgent?.id === agent.id && (
                <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--aurem-border)' }}>
                  {/* Execute button */}
                  <div className="mb-4">
                    <button
                      onClick={(e) => { e.stopPropagation(); executeAgent(agent.id); }}
                      disabled={executing === agent.id}
                      data-testid={`execute-agent-${agent.id}`}
                      className="flex items-center gap-2 px-4 py-2 text-xs rounded-lg text-white transition-all"
                      style={{ background: executing === agent.id ? '#555' : `linear-gradient(135deg, ${agent.color}, ${agent.color}aa)` }}
                    >
                      {executing === agent.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                      {executing === agent.id ? 'Executing...' : `Execute ${agent.name.split(' ')[0]}`}
                    </button>
                  </div>

                  {/* Execution Result */}
                  {executionResults[agent.id] && (
                    <div className="mb-4 p-3 rounded-lg" style={{ background: 'rgba(61,58,57,0.15)', border: '1px solid rgba(255,107,0,0.12)' }}>
                      <h4 className="text-[9px] tracking-wider mb-2" style={{ color: '#4ade80' }}>LAST EXECUTION RESULT</h4>
                      <p className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{executionResults[agent.id].summary}</p>
                      {executionResults[agent.id].results && (
                        <div className="mt-2 space-y-1">
                          {executionResults[agent.id].results.slice(0, 3).map((r, i) => (
                            <div key={i} className="text-[10px] flex items-center gap-2" style={{ color: 'var(--aurem-body-secondary)' }}>
                              <CheckCircle className="w-3 h-3 flex-shrink-0" style={{ color: '#4ade80' }} />
                              {r.name || r.contact || r.deal || JSON.stringify(r).substring(0, 80)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 bg-white/60 rounded-lg">
                      <h4 className="text-[9px] text-[#555] tracking-wider mb-2">RECENT ACTIVITY</h4>
                      <div className="space-y-2">
                        {[
                          'Completed market scan for 3 verticals',
                          'Generated 12 lead recommendations',
                          'Updated competitor analysis report'
                        ].map((act, i) => (
                          <div key={i} className="flex items-center gap-2 text-[10px] text-[#888]">
                            <CheckCircle className="w-3 h-3 text-[#4ade80] flex-shrink-0" />
                            {act}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="p-3 bg-white/60 rounded-lg">
                      <h4 className="text-[9px] text-[#555] tracking-wider mb-2">PERFORMANCE</h4>
                      <div className="space-y-2">
                        <div>
                          <div className="flex justify-between text-[10px] mb-1">
                            <span className="text-[#888]">Accuracy</span>
                            <span className="text-[#4ade80]">96%</span>
                          </div>
                          <div className="w-full h-1 bg-[#1A1A1A] rounded-full"><div className="h-full bg-[#4ade80] rounded-full" style={{ width: '96%' }} /></div>
                        </div>
                        <div>
                          <div className="flex justify-between text-[10px] mb-1">
                            <span className="text-[#888]">Speed</span>
                            <span className="text-[#D4AF37]">89%</span>
                          </div>
                          <div className="w-full h-1 bg-[#1A1A1A] rounded-full"><div className="h-full bg-[#D4AF37] rounded-full" style={{ width: '89%' }} /></div>
                        </div>
                        <div>
                          <div className="flex justify-between text-[10px] mb-1">
                            <span className="text-[#888]">Utilization</span>
                            <span className="text-[#8B5CF6]">78%</span>
                          </div>
                          <div className="w-full h-1 bg-[#1A1A1A] rounded-full"><div className="h-full bg-[#8B5CF6] rounded-full" style={{ width: '78%' }} /></div>
                        </div>
                      </div>
                    </div>
                    <div className="p-3 bg-white/60 rounded-lg">
                      <h4 className="text-[9px] text-[#555] tracking-wider mb-2">CONFIGURATION</h4>
                      <div className="space-y-2 text-[10px]">
                        <div className="flex justify-between"><span className="text-[#888]">Model</span><span className="text-[#1A1A2E] font-mono">GPT-4o</span></div>
                        <div className="flex justify-between"><span className="text-[#888]">Temperature</span><span className="text-[#1A1A2E] font-mono">0.7</span></div>
                        <div className="flex justify-between"><span className="text-[#888]">Max Tokens</span><span className="text-[#1A1A2E] font-mono">4,096</span></div>
                        <div className="flex justify-between"><span className="text-[#888]">Priority</span><span className="text-[#D4AF37]">High</span></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Swarm Execution Result */}
        {swarmResult && (
          <div className="mt-6 p-5 rounded-xl" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }} data-testid="swarm-result">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4" style={{ color: '#4ade80' }} />
              <h3 className="text-xs tracking-wider" style={{ color: 'var(--aurem-heading)' }}>SWARM EXECUTION COMPLETE</h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80' }}>
                {swarmResult.agents_completed}/{swarmResult.agents_executed} agents
              </span>
            </div>
            <div className="grid grid-cols-5 gap-3">
              {Object.entries(swarmResult.results || {}).map(([id, r]) => (
                <div key={id} className="p-2 rounded-lg text-center" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--aurem-border)' }}>
                  <div className="text-[10px] font-medium mb-1" style={{ color: 'var(--aurem-heading)' }}>{id}</div>
                  <div className="text-[9px]" style={{ color: r.status === 'completed' ? '#4ade80' : '#f87171' }}>{r.status}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Audit Chain */}
        {auditChain.length > 0 && (
          <div className="mt-6 p-5 rounded-xl" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }} data-testid="audit-chain">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4" style={{ color: '#D4AF37' }} />
              <h3 className="text-xs tracking-wider" style={{ color: 'var(--aurem-heading)' }}>BLOCKCHAIN AUDIT TRAIL</h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80' }}>VERIFIED</span>
            </div>
            <div className="space-y-2">
              {auditChain.slice(0, 5).map((entry, i) => (
                <div key={i} className="flex items-center gap-3 text-[10px] p-2 rounded" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <span className="font-mono" style={{ color: '#D4AF37' }}>#{entry.sequence}</span>
                  <span style={{ color: 'var(--aurem-heading)' }}>{entry.agent_id}</span>
                  <span style={{ color: 'var(--aurem-body-secondary)' }}>{entry.action}</span>
                  <span className="font-mono ml-auto" style={{ color: 'var(--aurem-body-secondary)', fontSize: '9px' }}>{entry.hash?.substring(0, 16)}...</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Swarm Architecture */}
        <div className="mt-8 p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
          <h3 className="text-xs text-[#555] tracking-wider mb-4">SWARM ARCHITECTURE</h3>
          <div className="flex items-center justify-center gap-4">
            {agents.slice(0, 4).map((agent, idx) => (
              <React.Fragment key={agent.id}>
                <div className="flex flex-col items-center gap-2">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: `${agent.color}15`, border: `2px solid ${agent.color}40` }}>
                    <Brain className="w-5 h-5" style={{ color: agent.color }} />
                  </div>
                  <span className="text-[9px] text-[#888]">{agent.name.split(' ')[0]}</span>
                </div>
                {idx < 3 && (
                  <div className="flex items-center">
                    <div className="w-8 h-[1px] bg-[#333]" />
                    <ChevronRight className="w-3 h-3 text-[#333]" />
                  </div>
                )}
              </React.Fragment>
            ))}
            <div className="flex items-center">
              <div className="w-8 h-[1px] bg-[#D4AF37]/50" />
              <ChevronRight className="w-3 h-3 text-[#D4AF37]" />
            </div>
            <div className="flex flex-col items-center gap-2">
              <div className="w-12 h-12 rounded-full flex items-center justify-center bg-[#f59e0b]/10 border-2 border-[#f59e0b]/40">
                <Cpu className="w-6 h-6 text-[#f59e0b]" />
              </div>
              <span className="text-[9px] text-[#f59e0b]">Orchestrator</span>
            </div>
          </div>
          <p className="text-center text-[10px] text-[#555] mt-4">
            The Orchestrator coordinates all agents, assigns tasks based on priority, and optimizes swarm performance
          </p>
        </div>
      </div>
    </div>
  );
}
