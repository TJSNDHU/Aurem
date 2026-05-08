import React, { useState, useEffect, useRef, useCallback , useMemo } from 'react';
import { Play, X, Trash2, Loader2, CheckCircle, AlertTriangle, Zap, Users, FileText, MessageSquare, Code, Brain, DollarSign } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const STAGE_CONFIG = [
  { key: 'scout', label: 'SCOUT', desc: 'Scanning tenant...', icon: '01' },
  { key: 'architect', label: 'ARCHITECT', desc: 'Analyzing findings...', icon: '02' },
  { key: 'risk_gate', label: 'RISK GATE', desc: 'Evaluating risk...', icon: '03' },
  { key: 'envoy', label: 'ENVOY', desc: 'Deciding actions...', icon: '04' },
  { key: 'human_loop', label: 'HUMAN LOOP', desc: 'Approval check...', icon: '05' },
  { key: 'shadow_test', label: 'SHADOW TEST', desc: 'Validating fixes...', icon: '06' },
  { key: 'closer', label: 'CLOSER', desc: 'Executing fixes...', icon: '07' },
  { key: 'origin_lock', label: 'ORIGIN LOCK', desc: 'Anchoring results...', icon: '08' },
  { key: 'verifier', label: 'VERIFIER', desc: 'Confirming success...', icon: '09' },
  { key: 'learn', label: 'LEARN', desc: 'Updating knowledge...', icon: '10' },
];

function StageCard({ config, stageData, isActive }) {
  const latestEntry = stageData?.length > 0 ? stageData[stageData.length - 1] : null;
  const status = latestEntry?.status || 'pending';
  const data = latestEntry?.data || {};

  const isCompleted = ['completed', 'passed', 'all_verified', 'compiled'].includes(status);
  const isRunning = status === 'running';
  const isPending = !latestEntry;

  let borderColor = '#2a2a3a';
  let glowColor = 'none';
  if (isCompleted) { borderColor = '#22C55E'; glowColor = '0 0 20px rgba(34,197,94,0.3)'; }
  else if (isRunning) { borderColor = '#EAB308'; glowColor = '0 0 24px rgba(234,179,8,0.4)'; }

  return (
    <div
      className="relative rounded-xl p-4 transition-all duration-500"
      style={{
        background: isCompleted ? 'rgba(34,197,94,0.06)' : isRunning ? 'rgba(234,179,8,0.06)' : 'rgba(255,255,255,0.03)',
        border: `1.5px solid ${borderColor}`,
        boxShadow: glowColor,
        animation: isRunning ? 'demoPulse 1.5s infinite' : 'none',
        opacity: isPending ? 0.4 : 1,
        transform: isCompleted ? 'scale(1)' : isRunning ? 'scale(1.02)' : 'scale(0.98)',
      }}
      data-testid={`demo-stage-${config.key}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded" style={{
            background: isCompleted ? 'rgba(34,197,94,0.2)' : isRunning ? 'rgba(234,179,8,0.2)' : 'rgba(255,255,255,0.05)',
            color: isCompleted ? '#22C55E' : isRunning ? '#EAB308' : '#666',
          }}>{config.icon}</span>
          <span className="text-xs font-bold tracking-wider" style={{
            color: isCompleted ? '#22C55E' : isRunning ? '#EAB308' : '#888',
          }}>{config.label}</span>
        </div>
        {isCompleted && <CheckCircle className="w-4 h-4 text-green-500" />}
        {isRunning && <Loader2 className="w-4 h-4 text-yellow-500 animate-spin" />}
      </div>

      <p className="text-[11px] mb-1" style={{ color: isRunning ? '#EAB308' : isCompleted ? '#a0d8b0' : '#666' }}>
        {isRunning ? config.desc : isCompleted ? 'Complete' : 'Waiting...'}
      </p>

      {isCompleted && Object.keys(data).length > 0 && (
        <div className="mt-2 space-y-0.5">
          {Object.entries(data).slice(0, 4).map(([k, v]) => (
            <div key={k} className="text-[10px] flex justify-between" style={{ color: '#8a8a9a' }}>
              <span>{k.replace(/_/g, ' ')}</span>
              <span className="font-mono" style={{ color: '#c0c0d0' }}>
                {Array.isArray(v) ? v.length : typeof v === 'object' ? JSON.stringify(v) : String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DemoMode({ token, onClose }) {
  const [phase, setPhase] = useState('idle'); // idle, seeding, running, completed, error
  const [tenantId, setTenantId] = useState(null);
  const [runId, setRunId] = useState(null);
  const [stages, setStages] = useState([]);
  const [finalStatus, setFinalStatus] = useState(null);
  const [demoSummary, setDemoSummary] = useState(null);
  const [seededData, setSeededData] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const timerRef = useRef(null);
  const pollRef = useRef(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  // Elapsed timer
  useEffect(() => {
    if (phase === 'running') {
      const start = Date.now();
      timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 200);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [phase]);

  // Poll progress
  useEffect(() => {
    if (phase === 'running' && runId) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API}/api/pipeline/demo/progress/${runId}`, { headers });
          if (res.ok) {
            const data = await res.json();
            setStages(data.stages || []);
            if (data.final_status && data.final_status !== 'running') {
              setFinalStatus(data.final_status);
              setDemoSummary(data.demo_summary || null);
              setPhase('completed');
              clearInterval(pollRef.current);
            }
          }
        } catch (e) { /* ignore poll errors */ }
      }, 800);
    }
    return () => clearInterval(pollRef.current);
  }, [phase, runId, headers]);

  const launchDemo = async () => {
    setPhase('seeding');
    setStages([]);
    setFinalStatus(null);
    setDemoSummary(null);
    setElapsed(0);

    try {
      // Step 1: Seed data
      const seedRes = await fetch(`${API}/api/pipeline/demo/launch`, { method: 'POST', headers });
      if (!seedRes.ok) throw new Error('Failed to seed demo data');
      const seedData = await seedRes.json();
      setTenantId(seedData.tenant_id);
      setSeededData(seedData.seeded);

      // Step 2: Run pipeline
      setPhase('running');
      const runRes = await fetch(`${API}/api/pipeline/demo/run/${seedData.tenant_id}`, { method: 'POST', headers });
      if (!runRes.ok) throw new Error('Failed to start demo pipeline');
      const runData = await runRes.json();
      setRunId(runData.run_id);
    } catch (e) {
      console.error('Demo launch error:', e);
      setPhase('error');
    }
  };

  const cleanupDemo = async () => {
    if (!tenantId) return;
    setCleanupLoading(true);
    try {
      await fetch(`${API}/api/pipeline/demo/cleanup/${tenantId}`, { method: 'POST', headers });
      setPhase('idle');
      setTenantId(null);
      setRunId(null);
      setStages([]);
      setFinalStatus(null);
      setDemoSummary(null);
      setSeededData(null);
    } catch (e) { console.error(e); }
    setCleanupLoading(false);
  };

  // Group stages by key
  const stageMap = {};
  stages.forEach(s => {
    if (s.stage && s.stage !== 'error' && s.stage !== 'abort') {
      if (!stageMap[s.stage]) stageMap[s.stage] = [];
      stageMap[s.stage].push(s);
    }
  });

  const completedCount = STAGE_CONFIG.filter(c => {
    const entries = stageMap[c.key];
    return entries?.some(e => ['completed', 'passed', 'all_verified', 'compiled'].includes(e.status));
  }).length;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" style={{ background: 'rgba(5,5,15,0.95)', backdropFilter: 'blur(20px)' }} data-testid="demo-mode-overlay">
      {/* Close button */}
      <button onClick={onClose} className="absolute top-5 right-5 p-2 rounded-lg hover:bg-white/5 transition-colors z-10" data-testid="demo-close-btn">
        <X className="w-5 h-5 text-gray-400" />
      </button>

      <div className="w-full max-w-[1200px] mx-auto px-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-4" style={{ background: 'rgba(212,163,115,0.12)', border: '1px solid rgba(212,163,115,0.25)' }}>
            <Zap className="w-3.5 h-3.5" style={{ color: '#FF6B00' }} />
            <span className="text-xs font-bold tracking-widest" style={{ color: '#FF6B00' }}>AUREM LIVE DEMO</span>
          </div>
          <h1 className="text-3xl font-bold mb-2" style={{ color: '#f0f0f0' }}>
            Autonomous Pipeline
          </h1>
          <p className="text-sm" style={{ color: '#888' }}>
            10-stage AI workflow executing in real-time
          </p>
        </div>

        {/* Idle State */}
        {phase === 'idle' && (
          <div className="text-center" data-testid="demo-idle">
            <div className="max-w-md mx-auto mb-8">
              <div className="grid grid-cols-2 gap-3 text-left mb-6">
                <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <Users className="w-4 h-4 mb-1" style={{ color: '#FF6B00' }} />
                  <div className="text-xs font-semibold" style={{ color: '#ccc' }}>5 Leads</div>
                  <div className="text-[10px]" style={{ color: '#888' }}>2 VIP, scored 67-91</div>
                </div>
                <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <FileText className="w-4 h-4 mb-1" style={{ color: '#FF6B00' }} />
                  <div className="text-xs font-semibold" style={{ color: '#ccc' }}>3 Invoices</div>
                  <div className="text-[10px]" style={{ color: '#888' }}>$1,395 CAD total</div>
                </div>
                <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <MessageSquare className="w-4 h-4 mb-1" style={{ color: '#FF6B00' }} />
                  <div className="text-xs font-semibold" style={{ color: '#ccc' }}>3 Messages</div>
                  <div className="text-[10px]" style={{ color: '#888' }}>Unanswered &gt;2 hours</div>
                </div>
                <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <Code className="w-4 h-4 mb-1" style={{ color: '#FF6B00' }} />
                  <div className="text-xs font-semibold" style={{ color: '#ccc' }}>4 SEO Issues</div>
                  <div className="text-[10px]" style={{ color: '#888' }}>Site health: 62/100</div>
                </div>
              </div>
            </div>
            <button
              onClick={launchDemo}
              className="px-8 py-3.5 rounded-xl text-sm font-bold tracking-wider transition-all hover:scale-[1.03] active:scale-[0.98]"
              style={{
                background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
                color: '#0A0A00',
                boxShadow: '0 0 30px rgba(212,163,115,0.4)',
              }}
              data-testid="demo-launch-btn"
            >
              <span className="flex items-center gap-2">
                <Play className="w-4 h-4" /> Launch Demo
              </span>
            </button>
          </div>
        )}

        {/* Seeding State */}
        {phase === 'seeding' && (
          <div className="text-center py-12" data-testid="demo-seeding">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4" style={{ color: '#FF6B00' }} />
            <p className="text-sm font-medium" style={{ color: '#ccc' }}>Seeding demo tenant data...</p>
          </div>
        )}

        {/* Running State */}
        {(phase === 'running' || phase === 'completed') && (
          <div data-testid="demo-running">
            {/* Progress bar */}
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs font-mono" style={{ color: '#888' }}>
                {completedCount}/10 stages {phase === 'running' ? 'processing' : 'complete'}
              </div>
              <div className="text-xs font-mono" style={{ color: '#FF6B00' }}>
                {elapsed}s elapsed
              </div>
            </div>
            <div className="h-1.5 rounded-full mb-6 overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(completedCount / 10) * 100}%`,
                  background: phase === 'completed' ? '#22C55E' : 'linear-gradient(90deg, #FF6B00, #EAB308)',
                  boxShadow: phase === 'completed' ? '0 0 12px rgba(34,197,94,0.5)' : '0 0 12px rgba(212,163,115,0.5)',
                }}
              />
            </div>

            {/* Stage Grid */}
            <div className="grid grid-cols-5 gap-3 mb-6">
              {STAGE_CONFIG.map(config => (
                <StageCard
                  key={config.key}
                  config={config}
                  stageData={stageMap[config.key]}
                  isActive={phase === 'running'}
                />
              ))}
            </div>

            {/* Completed Summary */}
            {phase === 'completed' && demoSummary && (
              <div className="rounded-xl p-6 mt-4" style={{
                background: 'rgba(34,197,94,0.05)',
                border: '1.5px solid rgba(34,197,94,0.25)',
                boxShadow: '0 0 40px rgba(34,197,94,0.1)',
                animation: 'demoFadeIn 0.5s ease',
              }} data-testid="demo-summary">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <h3 className="text-base font-bold" style={{ color: '#22C55E' }}>
                    Demo completed in {elapsed} seconds
                  </h3>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4" style={{ color: '#FF6B00' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>{demoSummary.leads_scored} leads scored</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>{demoSummary.vip_flagged} VIP flagged for outreach</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4" style={{ color: '#FF6B00' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>{demoSummary.invoice_reminders} invoice reminder</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>Sent to overdue accounts</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4" style={{ color: '#FF6B00' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>{demoSummary.seo_fixes} SEO issues fixed</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>Meta, alt, CSS, H1 resolved</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" style={{ color: '#FF6B00' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>{demoSummary.messages_drafted} messages drafted</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>Customer responses ready</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4" style={{ color: '#22C55E' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#22C55E' }}>{demoSummary.ai_cost}</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>Sovereign free model stack</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4" style={{ color: '#FF6B00' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#e0e0e0' }}>Knowledge updated</div>
                      <div className="text-[10px]" style={{ color: '#888' }}>Fixes anchored permanently</div>
                    </div>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-3 mt-6 pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <button
                    onClick={launchDemo}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all hover:scale-[1.02]"
                    style={{ background: 'rgba(212,163,115,0.15)', color: '#FF6B00', border: '1px solid rgba(212,163,115,0.3)' }}
                    data-testid="demo-rerun-btn"
                  >
                    <Play className="w-3.5 h-3.5" /> Run Again
                  </button>
                  <button
                    onClick={cleanupDemo}
                    disabled={cleanupLoading}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all hover:scale-[1.02]"
                    style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.2)' }}
                    data-testid="demo-cleanup-btn"
                  >
                    {cleanupLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                    Clear Demo Data
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error State */}
        {phase === 'error' && (
          <div className="text-center py-12" data-testid="demo-error">
            <AlertTriangle className="w-8 h-8 mx-auto mb-4 text-red-500" />
            <p className="text-sm font-medium text-red-400 mb-4">Demo failed to launch</p>
            <button onClick={() => setPhase('idle')} className="px-4 py-2 rounded-lg text-xs font-bold" style={{ background: 'rgba(255,255,255,0.05)', color: '#ccc' }}>
              Try Again
            </button>
          </div>
        )}
      </div>

      {/* CSS */}
      <style>{`
        @keyframes demoPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        @keyframes demoFadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
