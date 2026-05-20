import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { FileText, RefreshCw, Settings, Check, X, ChevronDown, ChevronUp, Loader2, AlertTriangle, CheckCircle, DollarSign, MessageSquare, Users, Shield, Activity, Clock, Zap } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function Section({ title, icon: Icon, color, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-3">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between py-2 px-1 hover:bg-[rgba(45,122,74,0.02)] transition-colors rounded">
        <div className="flex items-center gap-2">
          <Icon className="size-4" style={{ color }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--aurem-heading)' }}>{title}</span>
        </div>
        {open ? <ChevronUp className="size-3.5" style={{ color: 'var(--aurem-body-secondary)' }} /> : <ChevronDown className="size-3.5" style={{ color: 'var(--aurem-body-secondary)' }} />}
      </button>
      {open && <div className="pl-6 mt-1">{children}</div>}
    </div>
  );
}

function BriefCard({ brief, expanded, onToggle, token, onRefresh }) {
  const sections = brief.sections || {};
  const stats = brief.stats || {};
  const isToday = brief.date === new Date().toISOString().split('T')[0];
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const handleApprove = async (id) => {
    await fetch(`${API}/api/approvals/${id}/approve`, { method: 'POST', headers });
    onRefresh();
  };

  return (
    <div className={`aurem-glass-card overflow-hidden transition-all ${isToday ? '' : 'opacity-80'}`}
      style={{ border: isToday ? '1.5px solid rgba(45,122,74,0.25)' : undefined }}
      data-testid={`brief-card-${brief.brief_id}`}>

      {/* Header */}
      <div className="px-5 py-4 cursor-pointer hover:bg-[rgba(45,122,74,0.02)] transition-colors" onClick={onToggle}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <div className="size-2 rounded-full" style={{ background: isToday ? '#22C55E' : '#6B7280' }} />
              <h3 className="text-sm font-bold tracking-wide" style={{ color: 'var(--aurem-heading)' }}>
                AUREM MORNING BRIEF
              </h3>
              {isToday && <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: 'rgba(34,197,94,0.15)', color: '#22C55E' }}>TODAY</span>}
            </div>
            <div className="flex items-center gap-4 mt-1 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
              <span>{new Date(brief.generated_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
              <span>Health: <strong style={{ color: brief.health_score >= 70 ? '#22C55E' : brief.health_score >= 40 ? '#EAB308' : '#EF4444' }}>{brief.health_score}/100</strong></span>
              <span>Actions: <strong>{stats.actions_taken || 0}</strong></span>
              <span>Attention: <strong style={{ color: (stats.items_attention || 0) > 0 ? '#EF4444' : '#22C55E' }}>{stats.items_attention || 0}</strong></span>
            </div>
          </div>
          {expanded ? <ChevronUp className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} /> : <ChevronDown className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />}
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-5 pb-5 border-t" style={{ borderColor: 'rgba(61,58,57,0.15)' }}>
          {/* Narrative (LLM-generated) */}
          {brief.narrative && (
            <div className="mt-4 mb-4 p-3 rounded-lg text-sm italic" style={{ background: 'rgba(255,107,0,0.04)', color: 'var(--aurem-heading)', lineHeight: 1.6 }} data-testid="brief-narrative">
              {brief.narrative}
            </div>
          )}

          {/* Handled Overnight */}
          <Section title="HANDLED OVERNIGHT" icon={CheckCircle} color="#22C55E">
            {(sections.handled_overnight || []).length > 0 ? (
              <ul className="space-y-1.5">
                {sections.handled_overnight.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                    <Check className="size-3 mt-0.5 text-green-500 flex-shrink-0" />
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No automated actions overnight</p>
            )}
          </Section>

          {/* Needs Attention */}
          <Section title="NEEDS YOUR ATTENTION" icon={AlertTriangle} color="#EF4444">
            {(sections.needs_attention || []).length > 0 ? (
              <ul className="space-y-2">
                {sections.needs_attention.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs" style={{ color: 'var(--aurem-heading)' }}>
                    <AlertTriangle className="size-3 mt-0.5 text-red-500 flex-shrink-0" />
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs" style={{ color: '#22C55E' }}>All clear, no items need attention</p>
            )}
          </Section>

          {/* Pending Approvals (actionable) */}
          {brief.scan_data?.approvals?.pending_list?.length > 0 && (
            <Section title="PENDING APPROVALS" icon={Shield} color="#EAB308" defaultOpen={isToday}>
              <div className="space-y-1.5">
                {brief.scan_data.approvals.pending_list.map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-xs p-2 rounded-lg" style={{ background: 'rgba(234,179,8,0.05)' }}>
                    <div>
                      <span className="font-medium" style={{ color: 'var(--aurem-heading)' }}>{p.type}</span>
                      <span className="ml-2" style={{ color: 'var(--aurem-body-secondary)' }}>{p.reason}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Priorities */}
          <Section title="TODAY'S PRIORITIES" icon={Zap} color="#FF6B00">
            <ol className="space-y-1.5">
              {(sections.priorities || []).map((p, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <span className="size-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                    style={{ background: i === 0 ? 'rgba(212,163,115,0.2)' : 'rgba(61,58,57,0.15)', color: i === 0 ? '#FF6B00' : 'var(--aurem-body-secondary)' }}>
                    {i + 1}
                  </span>
                  <span style={{ color: 'var(--aurem-heading)' }}>{p}</span>
                </li>
              ))}
            </ol>
          </Section>

          {/* Revenue Snapshot */}
          {sections.revenue && (
            <Section title="REVENUE SNAPSHOT" icon={DollarSign} color="#22C55E">
              <div className="flex items-center gap-6 text-xs">
                <div>
                  <span style={{ color: 'var(--aurem-body-secondary)' }}>Outstanding: </span>
                  <strong style={{ color: 'var(--aurem-heading)' }}>${sections.revenue.outstanding || 0}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--aurem-body-secondary)' }}>At Risk: </span>
                  <strong style={{ color: (sections.revenue.at_risk || 0) > 0 ? '#EF4444' : '#22C55E' }}>${sections.revenue.at_risk || 0}</strong>
                </div>
              </div>
            </Section>
          )}

          {/* System Health */}
          {sections.system_health && (
            <Section title="SYSTEM HEALTH" icon={Activity} color="#8B5CF6" defaultOpen={false}>
              <div className="flex items-center gap-4 text-xs">
                <span style={{ color: 'var(--aurem-body-secondary)' }}>Score: <strong style={{ color: 'var(--aurem-heading)' }}>{sections.system_health.score}/100</strong></span>
                <span style={{ color: 'var(--aurem-body-secondary)' }}>Issues: <strong>{sections.system_health.issues}</strong></span>
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function SettingsModal({ settings, onSave, onClose, loading }) {
  const [local, setLocal] = useState(settings);
  const update = (k, v) => setLocal({ ...local, [k]: v });
  const toggleChannel = (ch) => {
    const channels = local.channels || [];
    update('channels', channels.includes(ch) ? channels.filter(c => c !== ch) : [...channels, ch]);
  };
  const toggleSection = (sec) => {
    const sections = { ...(local.sections || {}) };
    sections[sec] = !sections[sec];
    update('sections', sections);
  };

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }} data-testid="brief-settings-modal">
      <div className="w-full max-w-md rounded-xl p-6" style={{ background: '#fff', boxShadow: '0 25px 50px rgba(0,0,0,0.15)' }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold" style={{ color: 'var(--aurem-heading)' }}>Brief Settings</h3>
          <button onClick={onClose}><X className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} /></button>
        </div>

        {/* Delivery Time */}
        <div className="mb-4">
          <label className="text-xs font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Delivery Time</label>
          <input type="time" value={local.delivery_time || '07:00'} onChange={e => update('delivery_time', e.target.value)}
            className="px-3 py-1.5 rounded-lg border text-sm w-full" style={{ borderColor: 'rgba(255,107,0,0.1)' }} data-testid="brief-time-input" />
        </div>

        {/* Timezone */}
        <div className="mb-4">
          <label className="text-xs font-medium block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Timezone</label>
          <select value={local.timezone || 'America/Toronto'} onChange={e => update('timezone', e.target.value)}
            className="px-3 py-1.5 rounded-lg border text-sm w-full" style={{ borderColor: 'rgba(255,107,0,0.1)' }} data-testid="brief-timezone-select">
            <option value="America/Toronto">America/Toronto (EST)</option>
            <option value="America/New_York">America/New_York</option>
            <option value="America/Vancouver">America/Vancouver (PST)</option>
            <option value="UTC">UTC</option>
          </select>
        </div>

        {/* Channels */}
        <div className="mb-4">
          <label className="text-xs font-medium block mb-1.5" style={{ color: 'var(--aurem-body-secondary)' }}>Delivery Channels</label>
          <div className="flex gap-2">
            {['dashboard', 'push', 'whatsapp', 'email'].map(ch => (
              <button key={ch} onClick={() => toggleChannel(ch)}
                className="px-3 py-1 rounded-lg text-xs font-medium border transition-all"
                style={{
                  borderColor: (local.channels || []).includes(ch) ? '#22C55E' : 'rgba(255,107,0,0.1)',
                  background: (local.channels || []).includes(ch) ? 'rgba(34,197,94,0.1)' : 'transparent',
                  color: (local.channels || []).includes(ch) ? '#22C55E' : 'var(--aurem-body-secondary)',
                }}
                data-testid={`channel-${ch}`}
              >{ch}</button>
            ))}
          </div>
        </div>

        {/* Section Toggles */}
        <div className="mb-4">
          <label className="text-xs font-medium block mb-1.5" style={{ color: 'var(--aurem-body-secondary)' }}>Sections</label>
          <div className="grid grid-cols-2 gap-1.5">
            {Object.entries(local.sections || {}).map(([key, val]) => (
              <button key={key} onClick={() => toggleSection(key)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-all"
                style={{
                  borderColor: val ? '#22C55E' : 'rgba(255,107,0,0.1)',
                  background: val ? 'rgba(34,197,94,0.05)' : 'transparent',
                  color: val ? '#22C55E' : 'var(--aurem-body-secondary)',
                }}
                data-testid={`section-${key}`}
              >
                <div className="size-3 rounded-sm border flex items-center justify-center" style={{ borderColor: val ? '#22C55E' : '#ccc' }}>
                  {val && <Check className="size-2" />}
                </div>
                {key.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Auto-act toggle */}
        <div className="flex items-center gap-3 mb-5">
          <label className="text-xs font-medium" style={{ color: 'var(--aurem-body-secondary)' }}>Auto-act before brief</label>
          <button onClick={() => update('auto_act_before_brief', !local.auto_act_before_brief)}
            className="relative w-10 h-5 rounded-full transition-colors"
            style={{ background: local.auto_act_before_brief ? '#22C55E' : '#374151' }}
            data-testid="auto-act-toggle"
          >
            <div className="absolute top-0.5 size-4 rounded-full bg-white transition-transform shadow-sm" style={{ left: local.auto_act_before_brief ? '22px' : '2px' }} />
          </button>
        </div>

        <div className="flex gap-2">
          <button onClick={() => onSave(local)} disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #22C55E)', color: '#fff' }} data-testid="save-brief-settings">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />} Save
          </button>
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'rgba(61,58,57,0.15)', color: 'var(--aurem-body-secondary)' }}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

export default function MorningBrief({ token }) {
  const [todayBrief, setTodayBrief] = useState(null);
  const [history, setHistory] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [expandedBrief, setExpandedBrief] = useState(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = useCallback(async () => {
    try {
      const [todayRes, histRes, setRes] = await Promise.all([
        fetch(`${API}/api/brief/today`, { headers }),
        fetch(`${API}/api/brief/history?limit=30`, { headers }),
        fetch(`${API}/api/brief/settings`, { headers }),
      ]);
      if (todayRes.ok) {
        const d = await todayRes.json();
        setTodayBrief(d);
        setExpandedBrief(d.brief_id);
      }
      if (histRes.ok) { const d = await histRes.json(); setHistory(d.briefs || []); }
      if (setRes.ok) setSettings(await setRes.json());
    } catch (e) { console.error('Brief fetch error:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const generateNow = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API}/api/brief/generate`, { method: 'POST', headers });
      if (res.ok) {
        const brief = await res.json();
        setTodayBrief(brief);
        setExpandedBrief(brief.brief_id);
        fetchData();
      }
    } catch (e) { console.error(e); }
    setGenerating(false);
  };

  const saveSettings = async (newSettings) => {
    setSettingsLoading(true);
    try {
      await fetch(`${API}/api/brief/settings`, { method: 'PUT', headers, body: JSON.stringify(newSettings) });
      setShowSettings(false);
      fetchData();
    } catch (e) { console.error(e); }
    setSettingsLoading(false);
  };

  const pastBriefs = history.filter(b => b.brief_id !== todayBrief?.brief_id);

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="morning-brief-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Morning Brief</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowSettings(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
            style={{ background: 'rgba(61,58,57,0.15)', color: 'var(--aurem-body-secondary)' }} data-testid="brief-settings-btn">
            <Settings className="size-4" />
          </button>
          <button onClick={generateNow} disabled={generating}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold transition-all hover:scale-[1.02]"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #22C55E)', color: '#fff' }} data-testid="generate-now-btn">
            {generating ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            Generate Now
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center py-20" data-testid="brief-loading">
          <Loader2 className="size-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
        </div>
      ) : (
        <>
          {/* Today's Brief */}
          {todayBrief ? (
            <div className="mb-6">
              <BriefCard
                brief={todayBrief}
                expanded={expandedBrief === todayBrief.brief_id}
                onToggle={() => setExpandedBrief(expandedBrief === todayBrief.brief_id ? null : todayBrief.brief_id)}
                token={token}
                onRefresh={fetchData}
              />
            </div>
          ) : (
            <div className="aurem-glass-card p-8 text-center mb-6" data-testid="no-brief">
              <FileText className="size-10 mx-auto mb-3" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.4 }} />
              <p className="text-sm mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>No brief for today yet</p>
              <button onClick={generateNow} disabled={generating}
                className="px-4 py-2 rounded-lg text-sm font-bold" style={{ background: 'linear-gradient(135deg, #FF6B00, #22C55E)', color: '#fff' }}>
                {generating ? 'Generating...' : 'Generate Now'}
              </button>
            </div>
          )}

          {/* Past Briefs */}
          {pastBriefs.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
                PAST BRIEFS ({pastBriefs.length})
              </h2>
              <div className="space-y-2">
                {pastBriefs.map(b => (
                  <BriefCard
                    key={b.brief_id}
                    brief={b}
                    expanded={expandedBrief === b.brief_id}
                    onToggle={() => setExpandedBrief(expandedBrief === b.brief_id ? null : b.brief_id)}
                    token={token}
                    onRefresh={fetchData}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Settings Modal */}
      {showSettings && settings && (
        <SettingsModal settings={settings} onSave={saveSettings} onClose={() => setShowSettings(false)} loading={settingsLoading} />
      )}
    </div>
  );
}
