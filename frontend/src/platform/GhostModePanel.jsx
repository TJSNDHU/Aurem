import React, { useState, useEffect, useCallback , useMemo } from 'react';
import {
  Ghost, Moon, Sun, Bell, BellRing, Shield, Zap, Eye, EyeOff,
  CheckCircle, AlertCircle, Clock, DollarSign, TrendingUp,
  Activity, RefreshCw, X, ChevronRight, Settings, Play,
  FileText, Package, Users, Loader2
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function GhostModePanel({ token }) {
  const [config, setConfig] = useState(null);
  const [brief, setBrief] = useState(null);
  const [showBrief, setShowBrief] = useState(false);
  const [history, setHistory] = useState([]);
  const [running, setRunning] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes, bRes, hRes] = await Promise.all([
        fetch(`${API}/api/ghost/config`, { headers }),
        fetch(`${API}/api/ghost/morning-brief`, { headers }),
        fetch(`${API}/api/ghost/history?limit=10`, { headers }),
      ]);
      if (cRes.ok) setConfig(await cRes.json());
      if (bRes.ok) {
        const data = await bRes.json();
        if (data.available) { setBrief(data.brief); setShowBrief(true); }
      }
      if (hRes.ok) setHistory((await hRes.json()).history || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const toggleGhost = async (enabled) => {
    setToggling(true);
    try {
      const res = await fetch(`${API}/api/ghost/toggle`, {
        method: 'POST', headers,
        body: JSON.stringify({ enabled }),
      });
      if (res.ok) fetchAll();
    } catch (e) { console.error(e); }
    setToggling(false);
  };

  const runCycle = async () => {
    setRunning(true);
    try {
      const res = await fetch(`${API}/api/ghost/run-cycle`, { method: 'POST', headers });
      if (res.ok) fetchAll();
    } catch (e) { console.error(e); }
    setRunning(false);
  };

  if (loading || !config) return (
    <div className="flex items-center justify-center p-12">
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--aurem-text-secondary)' }} />
    </div>
  );

  const isOn = config.enabled;

  return (
    <div className="space-y-6" data-testid="ghost-mode-panel">
      {/* Morning Brief Modal */}
      {showBrief && brief && (
        <div className="relative overflow-hidden rounded-2xl p-6" style={{ background: 'linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%)', border: '1px solid rgba(212,175,55,0.2)' }} data-testid="morning-brief-modal">
          <button onClick={() => setShowBrief(false)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/10">
            <X size={16} style={{ color: 'rgba(255,255,255,0.5)' }} />
          </button>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(212,175,55,0.15)' }}>
              <Ghost size={20} style={{ color: '#D4AF37' }} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">{brief.headline}</h2>
              <p className="text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
                Ghost Mode Brief — {brief.cycle_time?.slice(0, 16).replace('T', ' ')}
              </p>
            </div>
          </div>

          {/* Narrative Lines */}
          <div className="space-y-2 mb-4">
            {(brief.narrative || []).map((line, i) => (
              <div key={i} className="flex items-start gap-2">
                <CheckCircle size={14} className="shrink-0 mt-0.5" style={{ color: '#D4AF37' }} />
                <p className="text-sm text-white/90">{line}</p>
              </div>
            ))}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Collected', value: `$${(brief.revenue_stats?.total_collected || 0).toLocaleString()}`, icon: DollarSign, color: '#10b981' },
              { label: 'Pending', value: brief.revenue_stats?.pending_invoices || 0, icon: Clock, color: '#f59e0b' },
              { label: 'Overdue', value: brief.revenue_stats?.overdue_invoices || 0, icon: AlertCircle, color: '#ef4444' },
              { label: 'AI Orders', value: brief.agent_activity?.ai_orders_24h || 0, icon: Zap, color: '#8B5CF6' },
            ].map((s, i) => (
              <div key={i} className="p-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.05)' }}>
                <s.icon size={14} style={{ color: s.color }} />
                <div className="text-lg font-bold text-white mt-1">{s.value}</div>
                <div className="text-[9px] uppercase tracking-wider" style={{ color: 'rgba(255,255,255,0.65)' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ghost Mode Toggle Card */}
      <div className="aurem-glass-card p-6 rounded-2xl" style={{ border: isOn ? '1px solid rgba(212,175,55,0.3)' : '1px solid transparent' }}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: isOn ? 'rgba(212,175,55,0.12)' : 'rgba(128,128,128,0.08)' }}>
              <Ghost size={24} style={{ color: isOn ? '#D4AF37' : 'var(--aurem-text-secondary)' }} />
            </div>
            <div>
              <h2 className="text-xl font-bold" style={{ color: 'var(--aurem-text)' }}>Ghost Mode</h2>
              <p className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>
                {isOn ? "AUREM is autonomously managing your business" : "Enable autonomous operation"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {isOn && (
              <button onClick={runCycle} disabled={running}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37' }} data-testid="run-cycle-btn">
                {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                {running ? 'Running...' : 'Run Now'}
              </button>
            )}
            <button onClick={() => toggleGhost(!isOn)} disabled={toggling}
              className="relative w-14 h-7 rounded-full transition-all duration-300 cursor-pointer"
              style={{ background: isOn ? 'linear-gradient(135deg, #D4AF37, #8B7355)' : 'rgba(128,128,128,0.2)' }}
              data-testid="ghost-toggle">
              <div className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-lg transition-all duration-300 ${isOn ? 'left-7' : 'left-0.5'}`} />
            </button>
          </div>
        </div>

        {/* Autonomous Tasks Config */}
        {isOn && (
          <div className="grid grid-cols-4 gap-3 mt-4 pt-4" style={{ borderTop: '1px solid rgba(128,128,128,0.1)' }}>
            {[
              { label: 'Auto Reminders', key: 'auto_reminders', icon: Bell, desc: 'Send overdue invoice reminders' },
              { label: 'SEO Repair', key: 'auto_seo', icon: Eye, desc: 'Fix SEO issues automatically' },
              { label: 'Cart Recovery', key: 'auto_recovery', icon: DollarSign, desc: 'Recover abandoned carts' },
              { label: 'Inventory Alerts', key: 'auto_inventory_alerts', icon: Package, desc: 'Flag low stock items' },
            ].map(task => (
              <div key={task.key} className="p-3 rounded-xl" style={{ background: config[task.key] ? 'rgba(16,185,129,0.06)' : 'rgba(128,128,128,0.04)', border: `1px solid ${config[task.key] ? 'rgba(16,185,129,0.15)' : 'rgba(128,128,128,0.1)'}` }}>
                <div className="flex items-center gap-2 mb-1">
                  <task.icon size={13} style={{ color: config[task.key] ? '#10b981' : 'var(--aurem-text-secondary)' }} />
                  <span className="text-xs font-semibold" style={{ color: 'var(--aurem-text)' }}>{task.label}</span>
                </div>
                <p className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{task.desc}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Activity */}
      {history.length > 0 && (
        <div className="aurem-glass-card p-5 rounded-2xl">
          <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-text)' }}>Ghost Activity Log</h3>
          <div className="space-y-2">
            {history.slice(0, 8).map((h, i) => (
              <div key={h.id || i} className="flex items-center gap-3 py-1.5" style={{ borderBottom: '1px solid rgba(128,128,128,0.06)' }}>
                <Activity size={12} style={{ color: '#D4AF37' }} />
                <span className="text-xs font-medium flex-1" style={{ color: 'var(--aurem-text)' }}>{h.action_type?.replace(/_/g, ' ')}</span>
                <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{h.created_at?.slice(0, 16).replace('T', ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
