/**
 * Auto Modularization Engine — Codebase Architecture Dashboard
 * Live visualization of the modularization state: health score,
 * server.py reduction, module distribution, and timeline.
 */

import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Layers, Server, FileCode, Activity, ChevronDown, ChevronRight, ArrowDown, CheckCircle, AlertTriangle, Cpu } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ─── Health Ring ────────────────────────────────────────── */
const HealthRing = ({ score }) => {
  const r = 62;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 85 ? '#22C55E' : score >= 65 ? '#EAB308' : '#EF4444';
  return (
    <div className="flex flex-col items-center" data-testid="modular-health-ring">
      <svg width="150" height="150" viewBox="0 0 150 150">
        <circle cx="75" cy="75" r={r} stroke="rgba(45,122,74,0.07)" strokeWidth="10" fill="none" />
        <circle cx="75" cy="75" r={r} stroke={color} strokeWidth="10" fill="none"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 75 75)" style={{ transition: 'stroke-dashoffset 1.2s ease-out' }} />
        <text x="75" y="68" textAnchor="middle" fontSize="32" fontWeight="bold" fill="#1A1A2E">{score}</text>
        <text x="75" y="88" textAnchor="middle" fontSize="9" fill="#888" fontWeight="600" letterSpacing="1.5">ARCHITECTURE</text>
      </svg>
    </div>
  );
};

/* ─── Stat Card ────────────────────────────────────────── */
const StatCard = ({ icon: Icon, label, value, sub, accent = '#FF6B00' }) => (
  <div className="p-4 bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl" data-testid={`stat-card-${label.toLowerCase().replace(/\s/g, '-')}`}>
    <div className="flex items-center gap-2 mb-2">
      <Icon className="size-4" style={{ color: accent }} />
      <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: '#888' }}>{label}</span>
    </div>
    <div className="text-2xl font-bold" style={{ color: '#1A1A2E' }}>{value}</div>
    {sub && <div className="text-[10px] mt-1" style={{ color: '#888' }}>{sub}</div>}
  </div>
);

/* ─── Size Bar ────────────────────────────────────────── */
const SizeBar = ({ distribution, total }) => {
  const cats = [
    { key: 'micro', label: '< 50', color: '#22C55E' },
    { key: 'small', label: '50-150', color: '#3B82F6' },
    { key: 'medium', label: '150-300', color: '#EAB308' },
    { key: 'large', label: '300-600', color: '#F97316' },
    { key: 'oversized', label: '600+', color: '#EF4444' },
  ];
  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-3 mb-2" data-testid="size-bar">
        {cats.map(c => {
          const count = distribution[c.key] || 0;
          const pct = total > 0 ? (count / total) * 100 : 0;
          return pct > 0 ? (
            <div key={c.key} style={{ width: `${pct}%`, background: c.color, transition: 'width 0.8s ease' }}
              title={`${c.label}: ${count}`} />
          ) : null;
        })}
      </div>
      <div className="flex flex-wrap gap-3">
        {cats.map(c => {
          const count = distribution[c.key] || 0;
          return count > 0 ? (
            <div key={c.key} className="flex items-center gap-1.5">
              <div className="size-2 rounded-full" style={{ background: c.color }} />
              <span className="text-[9px] font-medium" style={{ color: '#666' }}>{c.label}: {count}</span>
            </div>
          ) : null;
        })}
      </div>
    </div>
  );
};

/* ─── Timeline ────────────────────────────────────────── */
const Timeline = ({ milestones }) => (
  <div className="space-y-3" data-testid="modular-timeline">
    {milestones.map((m, i) => (
      <div key={i} className="flex gap-3 items-start">
        <div className="flex flex-col items-center">
          <div className={`size-3 rounded-full border-2 ${i === milestones.length - 1 ? 'bg-green-500 border-green-500' : 'bg-white border-emerald-400'}`} />
          {i < milestones.length - 1 && <div className="w-0.5 h-8 bg-emerald-200" />}
        </div>
        <div className="flex-1 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold" style={{ color: '#1A1A2E' }}>{m.event}</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-100" style={{ color: '#888' }}>{m.date}</span>
          </div>
          <div className="flex gap-4 mt-1">
            <span className="text-[9px]" style={{ color: '#666' }}>server.py: <b>{m.server_lines?.toLocaleString()}</b></span>
            <span className="text-[9px]" style={{ color: '#666' }}>Routers: <b>{m.routers}</b></span>
            <span className="text-[9px]" style={{ color: '#666' }}>Services: <b>{m.services}</b></span>
          </div>
        </div>
      </div>
    ))}
  </div>
);

/* ─── Module Table ────────────────────────────────────── */
const ModuleTable = ({ modules, title }) => {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? modules : modules.slice(0, 8);
  const sizeColor = (lines) => {
    if (lines > 600) return '#EF4444';
    if (lines > 300) return '#F97316';
    if (lines > 150) return '#EAB308';
    return '#22C55E';
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold" style={{ color: '#1A1A2E' }}>{title}</span>
        {modules.length > 8 && (
          <button onClick={() => setExpanded(!expanded)} className="text-[9px] font-medium flex items-center gap-1"
            style={{ color: '#FF6B00' }} data-testid={`toggle-${title.toLowerCase().replace(/\s/g, '-')}`}>
            {expanded ? 'Show less' : `Show all ${modules.length}`}
            {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
          </button>
        )}
      </div>
      <div className="space-y-1">
        {shown.map((m, i) => (
          <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-white/60" style={{ transition: 'background 0.15s' }}>
            <div className="flex items-center gap-2">
              <FileCode className="size-3" style={{ color: '#888' }} />
              <span className="text-[10px] font-medium" style={{ color: '#1A1A2E' }}>{m.name}</span>
              {m.type && (
                <span className="text-[8px] px-1 py-0.5 rounded" style={{
                  background: m.type === 'router' ? 'rgba(59,130,246,0.1)' : 'rgba(168,85,247,0.1)',
                  color: m.type === 'router' ? '#3B82F6' : '#A855F7',
                }}>{m.type}</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full" style={{
                  width: `${Math.min(100, (m.lines / 800) * 100)}%`,
                  background: sizeColor(m.lines),
                  transition: 'width 0.6s ease',
                }} />
              </div>
              <span className="text-[9px] font-mono w-10 text-right" style={{ color: sizeColor(m.lines) }}>{m.lines}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ─── Main Dashboard ────────────────────────────────────── */
export default function ModularizationEngine({ token }) {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, historyRes] = await Promise.all([
        fetch(`${API}/api/modularization/stats`, { headers }),
        fetch(`${API}/api/modularization/history`, { headers }),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (historyRes.ok) {
        const h = await historyRes.json();
        setHistory(h.milestones || []);
      }
    } catch (e) {
      console.error('Modularization fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="modular-loading">
        <div className="flex items-center gap-3">
          <Layers className="size-5 animate-pulse" style={{ color: '#FF6B00' }} />
          <span className="text-sm" style={{ color: '#888' }}>Scanning codebase…</span>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="modular-error">
        <span className="text-sm" style={{ color: '#888' }}>Failed to load modularization data</span>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'modules', label: 'Modules' },
    { id: 'timeline', label: 'Timeline' },
  ];

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="modularization-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: '#1A1A2E' }}>Auto Modularization Engine</h1>
          <p className="text-xs mt-1" style={{ color: '#888' }}>
            Live codebase architecture health — {stats.total_modules} modules extracted
          </p>
        </div>
        <div className="flex items-center gap-1 px-3 py-1.5 rounded-full" style={{ background: 'rgba(34,197,94,0.1)' }}>
          <CheckCircle className="size-3.5" style={{ color: '#22C55E' }} />
          <span className="text-[10px] font-semibold" style={{ color: '#22C55E' }}>MODULARIZED</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-xl w-fit" style={{ background: 'rgba(45,122,74,0.05)' }} data-testid="modular-tabs">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="px-4 py-1.5 rounded-lg text-[10px] font-semibold tracking-wide transition-all"
            style={{
              background: tab === t.id ? '#fff' : 'transparent',
              color: tab === t.id ? '#1A1A2E' : '#888',
              boxShadow: tab === t.id ? '0 1px 4px rgba(0,0,0,0.06)' : 'none',
            }}
            data-testid={`modular-tab-${t.id}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW TAB */}
      {tab === 'overview' && (
        <div className="space-y-6">
          {/* Top row: Health + Server.py reduction */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-5 flex flex-col items-center justify-center">
              <HealthRing score={stats.health.score} />
              {stats.health.penalties.length > 0 && (
                <div className="mt-3 space-y-1">
                  {stats.health.penalties.map((p, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <AlertTriangle className="size-3" style={{ color: '#EAB308' }} />
                      <span className="text-[9px]" style={{ color: '#888' }}>{p.rule} (-{p.penalty})</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-5 col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <Server className="size-4" style={{ color: '#FF6B00' }} />
                <span className="text-xs font-bold" style={{ color: '#1A1A2E' }}>server.py Reduction</span>
              </div>
              <div className="flex items-end gap-6 mb-3">
                <div>
                  <div className="text-[9px] uppercase tracking-wider font-medium mb-1" style={{ color: '#888' }}>Original</div>
                  <div className="text-2xl font-bold" style={{ color: '#EF4444' }}>{stats.server_py.original_lines.toLocaleString()}</div>
                </div>
                <ArrowDown className="size-6 mb-1" style={{ color: '#22C55E' }} />
                <div>
                  <div className="text-[9px] uppercase tracking-wider font-medium mb-1" style={{ color: '#888' }}>Current</div>
                  <div className="text-2xl font-bold" style={{ color: '#22C55E' }}>{stats.server_py.current_lines.toLocaleString()}</div>
                </div>
                <div className="ml-auto text-right">
                  <div className="text-3xl font-black" style={{ color: '#22C55E' }} data-testid="reduction-pct">
                    {stats.server_py.reduction_pct}%
                  </div>
                  <div className="text-[9px] font-medium" style={{ color: '#888' }}>reduction</div>
                </div>
              </div>
              {/* Reduction bar */}
              <div className="h-3 rounded-full bg-red-50 overflow-hidden">
                <div className="h-full rounded-full" style={{
                  width: `${100 - stats.server_py.reduction_pct}%`,
                  background: 'linear-gradient(90deg, #22C55E, #16A34A)',
                  transition: 'width 1.2s ease-out',
                }} />
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-[8px]" style={{ color: '#888' }}>0 lines</span>
                <span className="text-[8px]" style={{ color: '#888' }}>{stats.server_py.original_lines.toLocaleString()} lines</span>
              </div>
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={Layers} label="Routers" value={stats.routers.count}
              sub={`${stats.routers.avg_lines} avg lines`} />
            <StatCard icon={Cpu} label="Services" value={stats.services.count}
              sub={`${stats.services.avg_lines} avg lines`} accent="#8B5CF6" />
            <StatCard icon={FileCode} label="Total Modules" value={stats.total_modules}
              sub="routers + services" accent="#3B82F6" />
            <StatCard icon={Activity} label="Total Lines" value={stats.total_codebase_lines.toLocaleString()}
              sub="across entire backend" accent="#F59E0B" />
          </div>

          {/* Size distributions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-4">
              <div className="text-xs font-bold mb-3" style={{ color: '#1A1A2E' }}>Router Size Distribution</div>
              <SizeBar distribution={stats.routers.size_distribution} total={stats.routers.count} />
            </div>
            <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-4">
              <div className="text-xs font-bold mb-3" style={{ color: '#1A1A2E' }}>Service Size Distribution</div>
              <SizeBar distribution={stats.services.size_distribution} total={stats.services.count} />
            </div>
          </div>

          {/* Top modules */}
          <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-4">
            <ModuleTable modules={stats.top_modules} title="Largest Modules" />
          </div>
        </div>
      )}

      {/* MODULES TAB */}
      {tab === 'modules' && (
        <div className="space-y-6">
          <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-4">
            <ModuleTable
              modules={stats.top_modules.filter(m => m.type === 'router')}
              title={`All Routers (${stats.routers.count})`} />
          </div>
          <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-4">
            <ModuleTable
              modules={stats.top_modules.filter(m => m.type === 'service')}
              title={`All Services (${stats.services.count})`} />
          </div>
        </div>
      )}

      {/* TIMELINE TAB */}
      {tab === 'timeline' && (
        <div className="bg-white/70 backdrop-blur-sm border border-white/40 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="size-4" style={{ color: '#FF6B00' }} />
            <span className="text-xs font-bold" style={{ color: '#1A1A2E' }}>Modularization Journey</span>
          </div>
          <Timeline milestones={history} />
        </div>
      )}
    </div>
  );
}
