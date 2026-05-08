/**
 * Agent Command Center
 * ────────────────────
 * Live view of all 4 AUREM agents: Hunter, Follow-up, Closer, Referral.
 * Pulls from /api/agents/status every 8s + subscribes to SSE for instant A2A events.
 *
 * Includes:
 *  • 4 agent status cards with pause/resume/run-now controls
 *  • Auto-Hunt master toggle + ramp mode selector (Safe vs Aggressive)
 *  • Today's combined stats strip
 *  • Live A2A activity feed (last 30 events, auto-updated via SSE)
 *  • Next 7 days hunt queue preview
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ─────────────────────────────────────────────
// Small UI helpers
// ─────────────────────────────────────────────
const Pill = ({ status }) => {
  const map = {
    active:  { label: '🟢 ACTIVE',  bg: 'rgba(27,94,58,.12)',  fg: '#1B5E3A' },
    paused:  { label: '⏸ PAUSED',   bg: 'rgba(136,136,136,.12)', fg: '#666' },
    standby: { label: '🟡 STANDBY', bg: 'rgba(184,134,11,.12)', fg: '#B8860B' },
  };
  const cfg = map[status] || map.standby;
  return (
    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full tracking-wide"
          style={{ background: cfg.bg, color: cfg.fg }}>
      {cfg.label}
    </span>
  );
};

const AgentCard = ({ agent, onPause, onResume, onRunNow }) => {
  const st = agent.today_stats || {};
  const total = st.scouted || st.drip_sent || st.closer_attempts || st.referrals_contacted || 0;
  const target = agent.agent_id === 'hunter_ora' ? (agent.target || 80) : 0;

  return (
    <div
      data-testid={`agent-card-${agent.agent_id}`}
      className="rounded-xl p-4 space-y-3"
      style={{
        border: '1px solid rgba(61,58,57,0.15)',
        background: 'rgba(255,255,255,0.6)',
        backdropFilter: 'blur(8px)',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{agent.emoji}</span>
          <div>
            <div className="text-sm font-semibold" style={{ color: 'var(--aurem-heading)' }}>
              {agent.name}
            </div>
            <div className="text-[11px] opacity-60">{agent.job}</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Pill status={agent.status} />
        </div>
      </div>

      <div className="text-xs opacity-75">
        Working: <span className="font-mono">{agent.current_task || 'idle'}</span>
      </div>

      {/* Stats line */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {Object.entries(st).map(([k, v]) => (
          <span key={k}>
            <strong>{v}</strong> <span className="opacity-60">{k.replace(/_/g, ' ')}</span>
          </span>
        ))}
        {Object.keys(st).length === 0 && (
          <span className="opacity-50 italic">no activity yet today</span>
        )}
      </div>

      {target > 0 && (
        <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(27,94,58,0.1)' }}>
          <div className="h-full transition-all duration-500"
               style={{ width: `${Math.min(100, Math.round((total/target)*100))}%`,
                        background: 'linear-gradient(90deg, #FF6B00, #1B5E3A)' }} />
        </div>
      )}

      <div className="flex gap-2 pt-1">
        {agent.status === 'paused' ? (
          <button onClick={() => onResume(agent.agent_id)}
                  data-testid={`btn-resume-${agent.agent_id}`}
                  className="text-xs px-3 py-1 rounded-md"
                  style={{ background: '#1B5E3A', color: 'white' }}>
            ▶️ Resume
          </button>
        ) : (
          <button onClick={() => onPause(agent.agent_id)}
                  data-testid={`btn-pause-${agent.agent_id}`}
                  className="text-xs px-3 py-1 rounded-md border"
                  style={{ borderColor: 'rgba(61,58,57,0.25)' }}>
            ⏸ Pause
          </button>
        )}
        <button onClick={() => onRunNow(agent.agent_id)}
                data-testid={`btn-run-now-${agent.agent_id}`}
                className="text-xs px-3 py-1 rounded-md border"
                style={{ borderColor: 'rgba(255,107,0,0.4)', color: '#FF6B00' }}>
          🔄 Run Now
        </button>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────
// Main Agent Command Center
// ─────────────────────────────────────────────
export default function AgentCommandCenter({ token }) {
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [queue, setQueue] = useState(null);
  const [a2aFeed, setA2aFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const sseRef = useRef(null);

  const authH = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    try {
      const [s, se, q] = await Promise.all([
        fetch(`${API_URL}/api/agents/status`,     { headers: authH }).then(r => r.json()),
        fetch(`${API_URL}/api/auto-hunt/settings`, { headers: authH }).then(r => r.json()),
        fetch(`${API_URL}/api/auto-hunt/queue`,    { headers: authH }).then(r => r.json()),
      ]);
      setStatus(s);
      setSettings(se);
      setQueue(q);
      if (s?.a2a_recent) setA2aFeed(s.a2a_recent);
      setLoading(false);
    } catch (e) {
      console.error('[AgentCommandCenter] fetch failed', e);
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 8000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  // SSE for live A2A events
  useEffect(() => {
    let clientId = sessionStorage.getItem('aurem_sse_client_id');
    if (!clientId) {
      clientId = `acc_${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem('aurem_sse_client_id', clientId);
    }
    const es = new EventSource(`${API_URL}/api/admin/events/${clientId}`);
    es.onmessage = (evt) => {
      let p; try { p = JSON.parse(evt.data); } catch { return; }
      if (p?.type === 'a2a_event') {
        setA2aFeed(prev => [p.data, ...prev].slice(0, 30));
      }
    };
    es.onerror = () => { /* auto-reconnect */ };
    sseRef.current = es;
    return () => { try { es.close(); } catch { /* noop */ } };
  }, []);

  const callAction = async (url, method = 'POST') => {
    try {
      await fetch(`${API_URL}${url}`, { method, headers: authH });
      await fetchAll();
    } catch (e) { console.error(e); }
  };

  const onPause = (id) => callAction(`/api/agents/${id}/pause`);
  const onResume = (id) => callAction(`/api/agents/${id}/resume`);
  const onRunNow = (id) => callAction(`/api/agents/${id}/run-now`);

  const downloadAuditPdf = async () => {
    const end = new Date().toISOString().slice(0, 10);
    const startDate = new Date(); startDate.setDate(startDate.getDate() - 30);
    const start = startDate.toISOString().slice(0, 10);
    try {
      const res = await fetch(
        `${API_URL}/api/compliance/audit-report.pdf?start=${start}&end=${end}`,
        { headers: authH }
      );
      if (!res.ok) {
        alert(`Audit PDF failed: HTTP ${res.status}`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aurem-audit-${start}-${end}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) { alert(`Audit download error: ${e.message}`); }
  };

  const toggleMaster = () => callAction('/api/auto-hunt/toggle');

  const setRampMode = async (mode) => {
    await fetch(`${API_URL}/api/auto-hunt/settings`, {
      method: 'POST',
      headers: { ...authH, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ramp_mode: mode }),
    });
    await fetchAll();
  };

  if (loading) {
    return <div className="p-8 text-sm opacity-60">Loading Agent Command Center…</div>;
  }

  const combined = status?.combined_today || {};
  const rampMode = settings?.ramp_mode || 'safe';

  return (
    <div className="space-y-6 p-6" data-testid="agent-command-center">
      {/* Header + master toggle */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-semibold" style={{ color: 'var(--aurem-heading)' }}>
            🤖 Agent Command Center
          </h2>
          <p className="text-xs opacity-60 mt-1">
            4 autonomous agents · A2A bus · CASL compliant · nightly self-learning
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={downloadAuditPdf}
            data-testid="audit-pdf-btn"
            className="text-xs px-3 py-2 rounded-lg border transition-colors"
            style={{ borderColor: 'rgba(27,94,58,0.3)', color: '#1B5E3A' }}
            title="CASL audit report — last 30 days"
          >
            📄 Export Audit PDF
          </button>
          <button
            onClick={toggleMaster}
            data-testid="auto-hunt-master-toggle"
            className="text-sm px-4 py-2 rounded-lg font-semibold"
            style={{
              background: settings?.enabled ? '#1B5E3A' : 'rgba(136,136,136,0.12)',
              color: settings?.enabled ? 'white' : 'var(--aurem-heading)',
              border: settings?.enabled ? 'none' : '1px solid rgba(61,58,57,0.25)',
            }}
          >
            {settings?.enabled ? '🟢 Auto-Hunt ON' : '⚪ Auto-Hunt OFF'} · {settings?.current_daily_limit || 0}/day
          </button>
        </div>
      </div>

      {/* Ramp mode selector */}
      <div className="rounded-xl p-4"
           style={{ border: '1px solid rgba(61,58,57,0.15)', background: 'rgba(255,255,255,0.5)' }}>
        <div className="text-xs font-semibold mb-3 opacity-80">RAMP MODE</div>
        <div className="grid grid-cols-2 gap-3">
          {[
            { id: 'safe',       label: '🐢 Safe',       schedule: '20 → 50 → 100 → 200/day', note: 'Recommended — better deliverability, zero spam risk' },
            { id: 'aggressive', label: '🚀 Aggressive', schedule: '50 → 100 → 200/day',     note: 'Fast scaling — use after domain is warmed up' },
          ].map(m => {
            const selected = rampMode === m.id;
            return (
              <button
                key={m.id}
                onClick={() => setRampMode(m.id)}
                data-testid={`ramp-mode-${m.id}`}
                className="p-3 rounded-lg text-left transition-all"
                style={{
                  border: selected ? '2px solid #FF6B00' : '1px solid rgba(61,58,57,0.2)',
                  background: selected ? 'rgba(255,107,0,0.06)' : 'rgba(255,255,255,0.4)',
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm" style={{ color: 'var(--aurem-heading)' }}>
                    {m.label} {selected ? '✓' : ''}
                  </span>
                </div>
                <div className="text-[11px] opacity-80 mt-1 font-mono">{m.schedule}</div>
                <div className="text-[10px] opacity-60 mt-1">{m.note}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 4 agent cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4" data-testid="agents-grid">
        {status?.agents?.map(a => (
          <AgentCard key={a.agent_id} agent={a}
                     onPause={onPause} onResume={onResume} onRunNow={onRunNow} />
        ))}
      </div>

      {/* Today combined strip */}
      <div className="rounded-xl p-4"
           style={{ border: '1px solid rgba(61,58,57,0.15)', background: 'rgba(255,255,255,0.5)' }}>
        <div className="text-xs font-semibold mb-3 opacity-80">📊 TODAY COMBINED</div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 text-center">
          <Stat label="New" value={combined.new_today || 0} />
          <Stat label="Follow-up" value={combined.followup_today || 0} />
          <Stat label="Closing" value={combined.closing_today || 0} />
          <Stat label="Referral" value={combined.referral_today || 0} />
          <Stat label="Replied" value={combined.replied || 0} />
          <Stat label="Revenue CAD" value={`$${combined.revenue_cad || 0}`} highlight />
        </div>
      </div>

      {/* A2A feed + Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl p-4"
             style={{ border: '1px solid rgba(61,58,57,0.15)', background: 'rgba(255,255,255,0.5)' }}>
          <div className="text-xs font-semibold mb-3 opacity-80">🔄 A2A ACTIVITY</div>
          <div className="space-y-1 text-[11px] font-mono max-h-56 overflow-y-auto aurem-scroll"
               data-testid="a2a-feed">
            {a2aFeed.length === 0 && <div className="opacity-50 italic">No agent-to-agent events yet…</div>}
            {a2aFeed.slice(0, 15).map((e, i) => {
              const ts = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '';
              return (
                <div key={`${e.a2a_id || i}-${i}`} className="flex gap-2">
                  <span className="opacity-50 flex-shrink-0">{ts.slice(0, 8)}</span>
                  <span style={{ color: 'var(--aurem-heading)' }}>
                    {e.from_agent}→{e.to_agent}
                  </span>
                  <span className="opacity-80 truncate">{e.event}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl p-4"
             style={{ border: '1px solid rgba(61,58,57,0.15)', background: 'rgba(255,255,255,0.5)' }}>
          <div className="text-xs font-semibold mb-3 opacity-80">📅 NEXT 7 DAYS QUEUE</div>
          <div className="space-y-1 text-[11px]" data-testid="hunt-queue">
            {queue?.next_7_days?.map(d => (
              <div key={d.date} className="flex gap-3">
                <span className="opacity-60 flex-shrink-0 w-14">{d.day} {d.date.slice(5)}</span>
                <span>{d.targets.map(t => `${t.territory} ${t.industry}`).join(' + ') || '—'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const Stat = ({ label, value, highlight }) => (
  <div>
    <div className={`text-lg font-semibold ${highlight ? '' : ''}`}
         style={{ color: highlight ? '#1B5E3A' : 'var(--aurem-heading)' }}>
      {value}
    </div>
    <div className="text-[10px] opacity-60 uppercase tracking-wide">{label}</div>
  </div>
);
