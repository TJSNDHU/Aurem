import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Brain, Database, Clock, Layers, Shield, RefreshCw, ChevronDown, ChevronUp, CheckCircle, XCircle, AlertTriangle, Loader2, TrendingUp, Zap, ArrowUpRight } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, PageTransition, ExpandSection, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

export default function MemoryDashboard({ token }) {
  const [stats, setStats] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [plans, setPlans] = useState([]);
  const [promotions, setPromotions] = useState([]);
  const [loopStats, setLoopStats] = useState(null);
  const [velocity, setVelocity] = useState(null);
  const [askUser, setAskUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggleLoading, setToggleLoading] = useState(false);
  const [expandedPlan, setExpandedPlan] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, episodesRes, plansRes, askRes, promoRes, loopRes, velRes] = await Promise.all([
        fetch(`${API}/api/memory/stats`, { headers }),
        fetch(`${API}/api/memory/episodes?limit=15`, { headers }),
        fetch(`${API}/api/memory/plans/recent?limit=10`, { headers }),
        fetch(`${API}/api/memory/ask-user`, { headers }),
        fetch(`${API}/api/memory/promotions?limit=10`, { headers }),
        fetch(`${API}/api/memory/loop-stats`, { headers }),
        fetch(`${API}/api/memory/learning-velocity`, { headers }),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (episodesRes.ok) { const d = await episodesRes.json(); setEpisodes(d.episodes || []); }
      if (plansRes.ok) { const d = await plansRes.json(); setPlans(d.plans || []); }
      if (askRes.ok) setAskUser(await askRes.json());
      if (promoRes.ok) { const d = await promoRes.json(); setPromotions(d.promotions || []); }
      if (loopRes.ok) setLoopStats(await loopRes.json());
      if (velRes.ok) setVelocity(await velRes.json());
    } catch (e) { console.error('Memory fetch:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggleAskUser = async () => {
    if (!askUser) return;
    setToggleLoading(true);
    try {
      const res = await fetch(`${API}/api/memory/ask-user`, {
        method: 'PUT', headers,
        body: JSON.stringify({ enabled: !askUser.ask_user }),
      });
      if (res.ok) setAskUser(await res.json());
    } catch (e) { console.error(e); }
    setToggleLoading(false);
  };

  function timeAgo(ts) {
    if (!ts) return '-';
    const ms = Date.now() - new Date(ts).getTime();
    if (ms < 60000) return 'just now';
    if (ms < 3600000) return `${Math.floor(ms / 60000)}m ago`;
    if (ms < 86400000) return `${Math.floor(ms / 3600000)}h ago`;
    return `${Math.floor(ms / 86400000)}d ago`;
  }

  const tierCards = stats ? [
    { label: 'Long-Term Knowledge', value: stats.tier1_knowledge || 0, icon: Database, color: '#8B5CF6', desc: 'Known fixes & patterns' },
    { label: 'Working Memory', value: stats.tier2_working || 0, icon: Clock, color: '#EAB308', desc: '24h session context' },
    { label: 'Episodic Memory', value: stats.tier3_episodic || 0, icon: Brain, color: '#22C55E', desc: '90-day action history' },
    { label: 'Auto-Promoted', value: stats.auto_promotions || 0, icon: TrendingUp, color: '#F97316', desc: `${stats.promotion_rate || 0}% promotion rate` },
    { label: 'Interactions', value: stats.total_interactions || 0, icon: Zap, color: '#06B6D4', desc: `Avg conf: ${stats.avg_confidence || 0}` },
    { label: 'Execution Plans', value: stats.execution_plans || 0, icon: Layers, color: '#3B82F6', desc: 'Architect blueprints' },
  ] : [];

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="memory-dashboard">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between mb-6"
      >
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Three-Tier Memory</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Long-term knowledge, working context, and episodic recall
          </p>
        </div>
        <motion.button onClick={() => { setLoading(true); fetchData(); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
          style={{ background: 'rgba(61,58,57,0.25)', color: 'var(--aurem-heading)' }}
          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          data-testid="memory-refresh-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </motion.button>
      </motion.div>

      {/* Learning Velocity */}
      {velocity && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 24 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6" data-testid="learning-velocity"
        >
          {[
            {
              label: 'Promotions Today',
              value: velocity.promotions_today,
              sub: velocity.promotions_today > 0
                ? `${velocity.promotions_today} pattern${velocity.promotions_today !== 1 ? 's' : ''} learned today`
                : `${velocity.lifetime_promotions ?? 0} lifetime · 0 today`,
              trend: velocity.trend_promotions || [],
              color: '#F97316',
            },
            {
              label: 'Pattern Reuse Rate',
              value: velocity.reuse_rate > 0
                ? `${velocity.reuse_rate}%`
                : `${velocity.lifetime_reuse_rate ?? 0}%`,
              sub: velocity.reuse_rate >= 40
                ? 'Healthy reuse'
                : (velocity.reuse_rate > 0
                    ? 'Growing — target >40%'
                    : `Lifetime: ${velocity.lifetime_scout_hits ?? 0}/${velocity.lifetime_runs ?? 0} scout hits`),
              trend: velocity.trend_reuse || [],
              color: '#22C55E',
            },
            {
              label: 'Compound Score',
              value: velocity.compound_score,
              sub: velocity.compound_score > 0
                ? '7-day rolling intelligence growth'
                : `${velocity.lifetime_runs ?? 0} lifetime pipeline runs`,
              trend: velocity.trend_compound || [],
              color: '#8B5CF6',
            },
          ].map((card, i) => {
            const maxVal = Math.max(...(card.trend.length ? card.trend : [1]), 1);
            return (
              <motion.div
                key={card.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 * i }}
                className="aurem-glass-card p-4 relative overflow-hidden"
                data-testid={`velocity-${card.label.toLowerCase().replace(/\s/g,'-')}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{card.label}</div>
                    <div className="text-2xl font-black" style={{ color: card.color }}>{card.value}</div>
                    <div className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{card.sub}</div>
                  </div>
                  <TrendingUp className="w-4 h-4 mt-1" style={{ color: card.color, opacity: 0.5 }} />
                </div>
                {/* Sparkline */}
                <svg viewBox={`0 0 ${card.trend.length * 14} 24`} className="w-full h-6" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={card.color} stopOpacity="0.3" />
                      <stop offset="100%" stopColor={card.color} stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  {card.trend.length > 1 && (
                    <>
                      <path
                        d={`M0,${24 - (card.trend[0] / maxVal) * 20} ${card.trend.map((v, j) => `L${j * 14},${24 - (v / maxVal) * 20}`).join(' ')} L${(card.trend.length - 1) * 14},24 L0,24 Z`}
                        fill={`url(#grad-${i})`}
                      />
                      <path
                        d={`M0,${24 - (card.trend[0] / maxVal) * 20} ${card.trend.map((v, j) => `L${j * 14},${24 - (v / maxVal) * 20}`).join(' ')}`}
                        fill="none" stroke={card.color} strokeWidth="1.5" strokeLinecap="round"
                      />
                    </>
                  )}
                  {card.trend.map((v, j) => (
                    <circle key={j} cx={j * 14} cy={24 - (v / maxVal) * 20} r="2" fill={card.color} opacity={j === card.trend.length - 1 ? 1 : 0.4} />
                  ))}
                </svg>
                <div className="flex justify-between mt-1">
                  <span className="text-[8px]" style={{ color: 'var(--aurem-body-secondary)' }}>7d ago</span>
                  <span className="text-[8px]" style={{ color: 'var(--aurem-body-secondary)' }}>today</span>
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      )}

      {/* ASK_USER Master Switch */}
      {askUser && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 24, delay: 0.1 }}
          className="aurem-glass-card p-4 mb-6" data-testid="ask-user-switch"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ background: askUser.ask_user ? 'rgba(234,179,8,0.15)' : 'rgba(239,68,68,0.15)' }}>
                <Shield className="w-5 h-5" style={{ color: askUser.ask_user ? '#EAB308' : '#EF4444' }} />
              </div>
              <div>
                <div className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>
                  ASK_USER Master Switch
                </div>
                <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {askUser.ask_user
                    ? 'SUPERVISED — All pipeline actions require human approval'
                    : 'AUTONOMOUS — Smart Approval engine decides auto vs manual'}
                </div>
              </div>
            </div>
            <motion.button
              onClick={toggleAskUser}
              disabled={toggleLoading}
              className="relative flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold tracking-wider"
              style={{
                background: askUser.ask_user
                  ? 'linear-gradient(135deg, #EAB308, #CA8A04)'
                  : 'linear-gradient(135deg, #EF4444, #DC2626)',
                color: '#fff',
                boxShadow: askUser.ask_user
                  ? '0 0 20px rgba(234,179,8,0.3)'
                  : '0 0 20px rgba(239,68,68,0.3)',
              }}
              whileHover={{ scale: 1.04, boxShadow: askUser.ask_user ? '0 0 30px rgba(234,179,8,0.5)' : '0 0 30px rgba(239,68,68,0.5)' }}
              whileTap={{ scale: 0.96 }}
              data-testid="ask-user-toggle-btn"
            >
              {toggleLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <div className="w-2 h-2 rounded-full" style={{
                    background: '#fff',
                    boxShadow: '0 0 6px rgba(255,255,255,0.6)',
                    animation: 'pulse 1.5s infinite',
                  }} />
                  {askUser.ask_user ? 'SUPERVISED MODE' : 'AUTONOMOUS MODE'}
                </>
              )}
            </motion.button>
          </div>
          <div className="mt-2 text-[10px] px-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Source: {askUser.source} {askUser.source === 'env' ? '(ASK_USER env var)' : '(Admin override)'}
          </div>
        </motion.div>
      )}

      {/* Tier Stats Cards */}
      {loading && !stats ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
        </div>
      ) : (
        <>
          <StaggerGrid className="grid grid-cols-4 gap-4 mb-6">
            {tierCards.map((card) => {
              const Icon = card.icon;
              return (
                <MotionCard key={card.label} className="aurem-glass-card p-4" data-testid={`memory-tier-${card.label.replace(/\s/g, '-').toLowerCase()}`}
                  variants={cardVariant}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ background: `${card.color}20` }}>
                      <Icon className="w-5 h-5" style={{ color: card.color }} />
                    </div>
                    <div>
                      <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{card.value}</div>
                      <div className="text-[10px] font-medium" style={{ color: 'var(--aurem-body-secondary)' }}>{card.label}</div>
                    </div>
                  </div>
                  <div className="text-[10px] mt-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.7 }}>{card.desc}</div>
                </MotionCard>
              );
            })}
          </StaggerGrid>

          {/* Memory Loop Stats Bar */}
          {loopStats && (loopStats.total_interactions > 0 || promotions.length > 0) && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 24, delay: 0.15 }}
              className="aurem-glass-card p-4 mb-6" data-testid="memory-loop-stats"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(249,115,22,0.12)' }}>
                  <ArrowUpRight className="w-4 h-4" style={{ color: '#F97316' }} />
                </div>
                <div>
                  <div className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Stage 3 AI Memory Loop</div>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                    Auto-promotes high-confidence interactions ({">"} 0.85) to long-term knowledge
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-4">
                  <div className="text-center">
                    <div className="text-lg font-bold" style={{ color: '#F97316' }}>{loopStats.total_interactions}</div>
                    <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Interactions</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold" style={{ color: '#22C55E' }}>{loopStats.promotions}</div>
                    <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Promoted</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold" style={{ color: '#8B5CF6' }}>{loopStats.promotion_rate}%</div>
                    <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Rate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold" style={{ color: '#06B6D4' }}>{loopStats.avg_confidence}</div>
                    <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Avg Conf</div>
                  </div>
                </div>
              </div>
              {/* Confidence threshold visualization */}
              <div className="relative h-2 rounded-full overflow-hidden" style={{ background: 'rgba(61,58,57,0.15)' }}>
                <motion.div
                  className="absolute left-0 top-0 h-full rounded-full"
                  style={{ background: 'linear-gradient(90deg, #EF4444, #EAB308, #22C55E)' }}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min((loopStats.avg_confidence || 0) * 100, 100)}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                />
                <div className="absolute top-0 h-full w-px" style={{ left: '85%', background: '#fff', opacity: 0.6 }} />
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>0.0</span>
                <span className="text-[9px]" style={{ color: '#F97316', marginLeft: '70%' }}>0.85 threshold</span>
                <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>1.0</span>
              </div>
            </motion.div>
          )}

          {/* Two columns: Episodes + Plans */}
          <div className="grid grid-cols-2 gap-6">
            {/* Episodic Memory */}
            <div className="aurem-glass-card overflow-hidden" data-testid="episodic-memory-list">
              <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(255,107,0,0.03)' }}>
                <Brain className="w-4 h-4" style={{ color: '#22C55E' }} />
                <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Episodic Memory</span>
                <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{episodes.length} records</span>
              </div>
              {episodes.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Brain className="w-8 h-8 mb-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.3 }} />
                  <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No episodes yet</p>
                  <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.6 }}>
                    Episodes are written after pipeline runs
                  </p>
                </div>
              ) : (
                <div className="max-h-[400px] overflow-y-auto aurem-scroll">
                  {episodes.map((ep, i) => (
                    <div key={i} className="px-5 py-3 border-b" style={{ borderColor: 'rgba(255,107,0,0.05)' }}>
                      <div className="flex items-center gap-2 mb-1">
                        {ep.outcome === 'success' ? (
                          <CheckCircle className="w-3 h-3" style={{ color: '#22C55E' }} />
                        ) : (
                          <XCircle className="w-3 h-3" style={{ color: '#EF4444' }} />
                        )}
                        <span className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{ep.action_type}</span>
                        <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{timeAgo(ep.timestamp)}</span>
                      </div>
                      <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{ep.action_taken}</div>
                      {ep.learned_pattern && (
                        <div className="text-[10px] mt-1 italic" style={{ color: '#8B5CF6' }}>Pattern: {ep.learned_pattern}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Execution Plans */}
            <div className="aurem-glass-card overflow-hidden" data-testid="execution-plans-list">
              <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(255,107,0,0.03)' }}>
                <Layers className="w-4 h-4" style={{ color: '#3B82F6' }} />
                <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Architect's Plans</span>
                <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{plans.length} plans</span>
              </div>
              {plans.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Layers className="w-8 h-8 mb-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.3 }} />
                  <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No execution plans yet</p>
                  <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.6 }}>
                    Architect writes plans during pipeline runs
                  </p>
                </div>
              ) : (
                <div className="max-h-[400px] overflow-y-auto aurem-scroll">
                  {plans.map((plan, i) => {
                    const isExpanded = expandedPlan === plan.pipeline_run_id;
                    const steps = plan.plan || [];
                    const completedSteps = steps.filter(s => s.status === 'completed').length;
                    const failedSteps = steps.filter(s => s.status === 'failed').length;
                    return (
                      <div key={plan.pipeline_run_id || i}>
                        <div
                          className="px-5 py-3 border-b cursor-pointer hover:bg-[rgba(255,107,0,0.03)] transition-colors"
                          style={{ borderColor: 'rgba(255,107,0,0.05)' }}
                          onClick={() => setExpandedPlan(isExpanded ? null : plan.pipeline_run_id)}
                          data-testid={`plan-row-${plan.pipeline_run_id}`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <div className="w-2 h-2 rounded-full" style={{
                              background: plan.status === 'complete' ? '#22C55E' : plan.status === 'failed' ? '#EF4444' : '#EAB308',
                            }} />
                            <span className="text-xs font-medium font-mono" style={{ color: 'var(--aurem-heading)' }}>
                              {plan.pipeline_run_id}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{
                              background: plan.status === 'complete' ? 'rgba(34,197,94,0.1)' : plan.status === 'failed' ? 'rgba(239,68,68,0.1)' : 'rgba(234,179,8,0.1)',
                              color: plan.status === 'complete' ? '#22C55E' : plan.status === 'failed' ? '#EF4444' : '#EAB308',
                            }}>{plan.status}</span>
                            <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{timeAgo(plan.created_at)}</span>
                            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </div>
                          <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                            {steps.length} steps | {completedSteps} done {failedSteps > 0 ? `| ${failedSteps} failed` : ''}
                          </div>
                        </div>
                        {isExpanded && (
                          <ExpandSection isOpen={isExpanded}>
                            <div className="px-5 py-3 border-b" style={{ borderColor: 'rgba(255,107,0,0.05)', background: 'rgba(45,122,74,0.02)' }}>
                            {steps.map((step, si) => (
                              <div key={si} className="flex items-center gap-2 py-1">
                                {step.status === 'completed' ? (
                                  <CheckCircle className="w-3 h-3 flex-shrink-0" style={{ color: '#22C55E' }} />
                                ) : step.status === 'failed' ? (
                                  <XCircle className="w-3 h-3 flex-shrink-0" style={{ color: '#EF4444' }} />
                                ) : (
                                  <Clock className="w-3 h-3 flex-shrink-0" style={{ color: '#6B7280' }} />
                                )}
                                <span className="text-[10px] font-medium" style={{ color: 'var(--aurem-heading)' }}>
                                  {step.action}
                                </span>
                                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                                  → {step.target}
                                </span>
                                <span className="text-[9px] px-1 py-0.5 rounded ml-auto" style={{
                                  background: step.severity === 'P0' ? 'rgba(239,68,68,0.1)' : step.severity === 'P1' ? 'rgba(234,179,8,0.1)' : 'rgba(107,114,128,0.1)',
                                  color: step.severity === 'P0' ? '#EF4444' : step.severity === 'P1' ? '#EAB308' : '#6B7280',
                                }}>{step.severity}</span>
                              </div>
                            ))}
                            {plan.completed_at && (
                              <div className="text-[10px] mt-2 pt-2 border-t" style={{ borderColor: 'rgba(61,58,57,0.15)', color: 'var(--aurem-body-secondary)' }}>
                                Completed: {new Date(plan.completed_at).toLocaleString()}
                              </div>
                            )}
                            </div>
                          </ExpandSection>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Auto-Promoted Knowledge */}
          {promotions.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="aurem-glass-card overflow-hidden mt-6" data-testid="auto-promotions-list"
            >
              <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(249,115,22,0.03)' }}>
                <TrendingUp className="w-4 h-4" style={{ color: '#F97316' }} />
                <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Auto-Promoted Knowledge</span>
                <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{promotions.length} patterns</span>
              </div>
              <div className="max-h-[300px] overflow-y-auto aurem-scroll">
                {promotions.map((p, i) => (
                  <div key={i} className="px-5 py-3 border-b flex items-center gap-3" style={{ borderColor: 'rgba(255,107,0,0.05)' }}>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: 'rgba(139,92,246,0.1)' }}>
                      <Database className="w-4 h-4" style={{ color: '#8B5CF6' }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium truncate" style={{ color: 'var(--aurem-heading)' }}>
                        {p.pattern_type || p.action_type || 'unknown'}
                      </div>
                      <div className="text-[10px] truncate" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {p.pattern || p.action_taken || '-'}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <div className="text-center">
                        <div className="text-xs font-bold" style={{ color: '#22C55E' }}>{p.success_count || 1}</div>
                        <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>hits</div>
                      </div>
                      <div className="text-center">
                        <div className="text-xs font-bold" style={{ color: p.confidence >= 0.9 ? '#22C55E' : '#F97316' }}>
                          {(p.confidence || 0).toFixed(2)}
                        </div>
                        <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>conf</div>
                      </div>
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{timeAgo(p.promoted_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </>
      )}
    </div>
  );
}
