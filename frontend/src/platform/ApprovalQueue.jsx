import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Check, X, RefreshCw, Settings, ChevronDown, ChevronUp, Loader2, Brain, Shield, Clock, AlertTriangle, CheckCircle, XCircle, Filter } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const RISK_BADGES = {
  auto_approved: { color: '#22C55E', bg: 'rgba(34,197,94,0.1)', label: 'AUTO', icon: CheckCircle },
  auto_cancel_pending: { color: '#EAB308', bg: 'rgba(234,179,8,0.1)', label: 'AUTO IN', icon: Clock },
  pending_manual: { color: '#EF4444', bg: 'rgba(239,68,68,0.1)', label: 'MANUAL', icon: Shield },
  blocked: { color: '#8B5CF6', bg: 'rgba(139,92,246,0.1)', label: 'BLOCKED', icon: AlertTriangle },
};

const ACTION_LABELS = {
  seo_fix: 'SEO Fix', css_fix: 'CSS Fix', lead_score_update: 'Lead Score',
  cache_warm: 'Cache Warm', knowledge_sync: 'Knowledge Sync', sentiment_analysis: 'Sentiment',
  message_draft: 'Message Draft', invoice_reminder: 'Invoice Reminder',
  lead_outreach: 'Lead Outreach', vip_outreach: 'VIP Outreach',
  config_change: 'Config Change', data_delete: 'Data Delete',
  payment_trigger: 'Payment', bulk_outreach: 'Bulk Outreach',
  queue_outreach: 'Lead Outreach', send_reminder: 'Invoice Reminder',
  seo_meta_fix: 'SEO Fix', pixel_css_fix: 'CSS Fix', inject_css: 'CSS Fix',
};

function RiskBadge({ status, countdown }) {
  const badge = RISK_BADGES[status] || RISK_BADGES.pending_manual;
  const Icon = badge.icon;
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-bold" style={{ background: badge.bg, color: badge.color }} data-testid="risk-badge">
      <Icon className="size-3" />
      {badge.label}
      {status === 'auto_cancel_pending' && countdown != null && (
        <span className="font-mono">{Math.ceil(countdown)}m</span>
      )}
    </div>
  );
}

function SettingsPanel({ settings, onUpdate, loading }) {
  const [localSettings, setLocalSettings] = useState(settings);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => { setLocalSettings(settings); }, [settings]);

  const update = (key, value) => {
    const updated = { ...localSettings, [key]: value };
    setLocalSettings(updated);
  };

  const updateRule = (actionType, value) => {
    const rules = { ...localSettings.rules, [actionType]: value };
    setLocalSettings({ ...localSettings, rules });
  };

  const save = () => onUpdate(localSettings);

  const ruleOptions = ['auto', 'auto_log', 'conditional', 'manual', 'blocked'];
  const editableRules = [
    'seo_fix', 'css_fix', 'message_draft', 'invoice_reminder',
    'lead_outreach', 'vip_outreach', 'config_change', 'data_delete',
    'payment_trigger', 'bulk_outreach',
  ];

  return (
    <div className="aurem-glass-card overflow-hidden mb-4" data-testid="approval-settings">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-5 py-3 hover:bg-[rgba(255,107,0,0.03)] transition-colors">
        <div className="flex items-center gap-2">
          <Settings className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--aurem-heading)' }}>Approval Rules & Thresholds</span>
        </div>
        {expanded ? <ChevronUp className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} /> : <ChevronDown className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />}
      </button>

      {expanded && (
        <div className="px-5 pb-4 space-y-4" style={{ borderTop: '1px solid rgba(61,58,57,0.15)' }}>
          {/* Thresholds */}
          <div className="grid grid-cols-2 gap-4 pt-3">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--aurem-body-secondary)' }}>Invoice Auto-Approve Limit (CAD)</label>
              <input
                type="range" min="0" max="2000" step="50"
                value={localSettings.invoice_auto_limit || 500}
                onChange={e => update('invoice_auto_limit', Number(e.target.value))}
                className="w-full"
                data-testid="invoice-threshold-slider"
              />
              <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--aurem-heading)' }}>${localSettings.invoice_auto_limit || 500}</div>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--aurem-body-secondary)' }}>VIP Lead Score Threshold</label>
              <input
                type="range" min="70" max="100" step="1"
                value={localSettings.vip_threshold || 85}
                onChange={e => update('vip_threshold', Number(e.target.value))}
                className="w-full"
                data-testid="vip-threshold-slider"
              />
              <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--aurem-heading)' }}>{localSettings.vip_threshold || 85}+</div>
            </div>
          </div>

          {/* Auto-approve hours */}
          <div>
            <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--aurem-body-secondary)' }}>Auto-Approve Hours (UTC)</label>
            <div className="flex items-center gap-2">
              <input type="number" min="0" max="23" value={(localSettings.auto_approve_hours || [9, 18])[0]}
                onChange={e => update('auto_approve_hours', [Number(e.target.value), (localSettings.auto_approve_hours || [9, 18])[1]])}
                className="w-16 px-2 py-1 rounded text-sm border" style={{ borderColor: 'rgba(255,107,0,0.1)', background: 'rgba(255,255,255,0.8)' }}
                data-testid="hours-start"
              />
              <span className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>to</span>
              <input type="number" min="0" max="23" value={(localSettings.auto_approve_hours || [9, 18])[1]}
                onChange={e => update('auto_approve_hours', [(localSettings.auto_approve_hours || [9, 18])[0], Number(e.target.value)])}
                className="w-16 px-2 py-1 rounded text-sm border" style={{ borderColor: 'rgba(255,107,0,0.1)', background: 'rgba(255,255,255,0.8)' }}
                data-testid="hours-end"
              />
            </div>
          </div>

          {/* Pattern Learning Toggle */}
          <div className="flex items-center gap-3">
            <label className="text-xs font-medium" style={{ color: 'var(--aurem-body-secondary)' }}>Pattern Learning</label>
            <button
              onClick={() => update('pattern_learning_enabled', !localSettings.pattern_learning_enabled)}
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{ background: localSettings.pattern_learning_enabled ? '#22C55E' : '#374151' }}
              data-testid="pattern-learning-toggle"
            >
              <div className="absolute top-0.5 size-4 rounded-full bg-white transition-transform shadow-sm" style={{ left: localSettings.pattern_learning_enabled ? '22px' : '2px' }} />
            </button>
            <span className="text-xs" style={{ color: localSettings.pattern_learning_enabled ? '#22C55E' : 'var(--aurem-body-secondary)' }}>
              {localSettings.pattern_learning_enabled ? 'ON' : 'OFF'}
            </span>
          </div>

          {/* Per-action rules */}
          <div>
            <label className="text-xs font-medium mb-2 block" style={{ color: 'var(--aurem-body-secondary)' }}>Rules per Action Type</label>
            <div className="grid grid-cols-2 gap-2">
              {editableRules.map(at => (
                <div key={at} className="flex items-center justify-between px-3 py-1.5 rounded-lg" style={{ background: 'rgba(255,107,0,0.03)' }}>
                  <span className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{ACTION_LABELS[at] || at}</span>
                  <select
                    value={(localSettings.rules || {})[at] || 'manual'}
                    onChange={e => updateRule(at, e.target.value)}
                    className="text-[10px] px-1.5 py-0.5 rounded border"
                    style={{ borderColor: 'rgba(255,107,0,0.1)', background: 'rgba(255,255,255,0.8)' }}
                    data-testid={`rule-${at}`}
                  >
                    {ruleOptions.map(o => <option key={o} value={o}>{o.replace('_', ' ')}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>

          <button onClick={save} disabled={loading} className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all hover:scale-[1.02]"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #22C55E)', color: '#fff' }} data-testid="save-settings-btn">
            {loading ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />} Save Settings
          </button>
        </div>
      )}
    </div>
  );
}

function PatternCard({ patterns }) {
  if (!patterns || !patterns.action_types) return null;

  const types = Object.entries(patterns.action_types);
  const automated = types.filter(([, v]) => v.automated).length;

  return (
    <div className="aurem-glass-card p-4 mb-4" data-testid="pattern-learning-card">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="size-4" style={{ color: '#8B5CF6' }} />
        <span className="text-sm font-semibold" style={{ color: 'var(--aurem-heading)' }}>Pattern Learning</span>
      </div>
      <p className="text-xs mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
        ORA has learned from <strong>{patterns.total_decisions}</strong> decisions.{' '}
        <strong style={{ color: '#22C55E' }}>{automated}</strong> action type{automated !== 1 ? 's' : ''} now fully automated.
      </p>
      <div className="space-y-2">
        {types.map(([type, stats]) => (
          <div key={type}>
            <div className="flex items-center justify-between text-[11px] mb-0.5">
              <span style={{ color: 'var(--aurem-heading)' }}>{ACTION_LABELS[type] || type}</span>
              <span style={{ color: stats.automated ? '#22C55E' : 'var(--aurem-body-secondary)' }}>
                {stats.automated ? 'Automated' : `${stats.remaining} more needed`}
              </span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(61,58,57,0.15)' }}>
              <div className="h-full rounded-full transition-all" style={{
                width: `${Math.min(100, (stats.total_decisions / (patterns.threshold || 20)) * 100)}%`,
                background: stats.automated ? '#22C55E' : stats.yes_rate >= 70 ? '#EAB308' : '#6B7280',
              }} />
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
              {stats.total_decisions} decisions | {stats.yes_rate}% yes rate
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ApprovalQueue({ token }) {
  const [pending, setPending] = useState([]);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [patterns, setPatterns] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [filterType, setFilterType] = useState('all');
  const [tab, setTab] = useState('pending');

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [pendRes, histRes, statsRes, patRes, setRes] = await Promise.all([
        fetch(`${API}/api/approvals/pending`, { headers }),
        fetch(`${API}/api/approvals/history?limit=50`, { headers }),
        fetch(`${API}/api/approvals/stats`, { headers }),
        fetch(`${API}/api/approvals/patterns`, { headers }),
        fetch(`${API}/api/approvals/settings`, { headers }),
      ]);
      if (pendRes.ok) { const d = await pendRes.json(); setPending(d.approvals || []); }
      if (histRes.ok) { const d = await histRes.json(); setHistory(d.history || []); if (d.stats) setStats(d.stats); }
      if (statsRes.ok) setStats(await statsRes.json());
      if (patRes.ok) setPatterns(await patRes.json());
      if (setRes.ok) setSettings(await setRes.json());
    } catch (e) { console.error('Approval fetch error:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { const i = setInterval(fetchData, 15000); return () => clearInterval(i); }, [fetchData]);

  const handleApprove = async (id) => {
    setActionLoading(id);
    await fetch(`${API}/api/approvals/${id}/approve`, { method: 'POST', headers });
    setActionLoading(null);
    fetchData();
  };

  const handleReject = async (id) => {
    setActionLoading(id);
    await fetch(`${API}/api/approvals/${id}/reject`, { method: 'POST', headers, body: JSON.stringify({ reason: 'Rejected via dashboard' }) });
    setActionLoading(null);
    fetchData();
  };

  const handleBulk = async (decision) => {
    if (selectedIds.length === 0) return;
    setActionLoading('bulk');
    await fetch(`${API}/api/approvals/bulk`, { method: 'POST', headers, body: JSON.stringify({ ids: selectedIds, decision }) });
    setActionLoading(null);
    setSelectedIds([]);
    fetchData();
  };

  const handleSettingsUpdate = async (newSettings) => {
    setSettingsLoading(true);
    await fetch(`${API}/api/approvals/settings`, { method: 'PUT', headers, body: JSON.stringify(newSettings) });
    setSettingsLoading(false);
    fetchData();
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const filteredPending = filterType === 'all' ? pending : pending.filter(a => a.action_type === filterType);
  const actionTypes = [...new Set(pending.map(a => a.action_type))];

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="approval-queue-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Smart Approvals</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Hybrid auto/manual approval engine with pattern learning
          </p>
        </div>
        <button onClick={() => { setLoading(true); fetchData(); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-[1.02]"
          style={{ background: 'rgba(61,58,57,0.25)', color: 'var(--aurem-heading)' }} data-testid="approval-refresh-btn">
          <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="aurem-glass-card p-4" data-testid="pending-count-card">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(239,68,68,0.15)' }}>
              <Shield className="size-5" style={{ color: '#EF4444' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{stats?.pending || 0}</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Pending</div>
            </div>
          </div>
        </div>
        <div className="aurem-glass-card p-4" data-testid="auto-today-card">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(34,197,94,0.15)' }}>
              <CheckCircle className="size-5" style={{ color: '#22C55E' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{stats?.auto_approved_today || 0}</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Auto Today</div>
            </div>
          </div>
        </div>
        <div className="aurem-glass-card p-4" data-testid="manual-today-card">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(234,179,8,0.15)' }}>
              <Clock className="size-5" style={{ color: '#EAB308' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{stats?.manual_today || 0}</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Manual Today</div>
            </div>
          </div>
        </div>
        <div className="aurem-glass-card p-4" data-testid="automation-rate-card">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(139,92,246,0.15)' }}>
              <Brain className="size-5" style={{ color: '#8B5CF6' }} />
            </div>
            <div>
              <div className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>{stats?.automation_rate || 0}%</div>
              <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Automated</div>
            </div>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {settings && <SettingsPanel settings={settings} onUpdate={handleSettingsUpdate} loading={settingsLoading} />}

      {/* Pattern Learning */}
      {patterns && patterns.total_decisions > 0 && <PatternCard patterns={patterns} />}

      {/* Tab Bar */}
      <div className="flex items-center gap-1 mb-4">
        {['pending', 'history'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: tab === t ? 'rgba(61,58,57,0.3)' : 'transparent',
              color: tab === t ? 'var(--aurem-heading)' : 'var(--aurem-body-secondary)',
            }}
            data-testid={`tab-${t}`}
          >
            {t === 'pending' ? `Pending (${pending.length})` : 'History'}
          </button>
        ))}
        <div className="flex-1" />
        {tab === 'pending' && pending.length > 0 && (
          <div className="flex items-center gap-2">
            <select value={filterType} onChange={e => setFilterType(e.target.value)}
              className="px-2 py-1 rounded text-xs border" style={{ borderColor: 'rgba(255,107,0,0.1)', background: 'rgba(255,255,255,0.8)' }}
              data-testid="filter-type-select">
              <option value="all">All Types</option>
              {actionTypes.map(at => <option key={at} value={at}>{ACTION_LABELS[at] || at}</option>)}
            </select>
            {selectedIds.length > 0 && (
              <>
                <button onClick={() => handleBulk('approve')} className="px-3 py-1 rounded-lg text-xs font-bold" style={{ background: 'rgba(34,197,94,0.15)', color: '#22C55E' }} data-testid="bulk-approve-btn">
                  Approve {selectedIds.length}
                </button>
                <button onClick={() => handleBulk('reject')} className="px-3 py-1 rounded-lg text-xs font-bold" style={{ background: 'rgba(239,68,68,0.15)', color: '#EF4444' }} data-testid="bulk-reject-btn">
                  Reject {selectedIds.length}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Pending Table */}
      {tab === 'pending' && (
        <div className="aurem-glass-card overflow-hidden" data-testid="pending-table">
          <div className="grid grid-cols-[32px_1fr_120px_1fr_120px_100px] gap-3 px-5 py-3 text-xs font-semibold border-b"
            style={{ borderColor: 'rgba(61,58,57,0.25)', color: 'var(--aurem-body-secondary)', background: 'rgba(255,107,0,0.03)' }}>
            <div />
            <div>Action</div>
            <div>Type</div>
            <div>Reason</div>
            <div>Status</div>
            <div>Actions</div>
          </div>

          {loading && pending.length === 0 ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="size-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} /></div>
          ) : filteredPending.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16" data-testid="no-pending">
              <CheckCircle className="size-10 mb-3" style={{ color: '#22C55E', opacity: 0.4 }} />
              <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>No pending approvals</p>
              <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.7 }}>All actions are auto-approved or queue is clear</p>
            </div>
          ) : (
            filteredPending.map(a => (
              <div key={a.approval_id}>
                <div className="grid grid-cols-[32px_1fr_120px_1fr_120px_100px] gap-3 px-5 py-3 items-center text-sm border-b cursor-pointer hover:bg-[rgba(45,122,74,0.02)] transition-colors"
                  style={{ borderColor: 'rgba(255,107,0,0.05)' }}
                  onClick={() => setExpandedId(expandedId === a.approval_id ? null : a.approval_id)}
                  data-testid={`approval-row-${a.approval_id}`}
                >
                  <input type="checkbox" checked={selectedIds.includes(a.approval_id)}
                    onChange={() => toggleSelect(a.approval_id)} onClick={e => e.stopPropagation()}
                    className="size-4 rounded" data-testid={`select-${a.approval_id}`} />
                  <div className="truncate font-medium" style={{ color: 'var(--aurem-heading)' }}>{a.action?.strategy || a.action_type}</div>
                  <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{ACTION_LABELS[a.action_type] || a.action_type}</div>
                  <div className="text-xs truncate" style={{ color: 'var(--aurem-body-secondary)' }}>{a.reason}</div>
                  <RiskBadge status={a.decision_type === 'auto_cancel' ? 'auto_cancel_pending' : a.decision_type === 'manual' ? 'pending_manual' : a.status} countdown={a.countdown_remaining_minutes} />
                  <div className="flex items-center gap-1">
                    <button onClick={e => { e.stopPropagation(); handleApprove(a.approval_id); }}
                      className="p-1.5 rounded-md hover:bg-green-50 transition-colors" title="Approve"
                      data-testid={`approve-btn-${a.approval_id}`}>
                      {actionLoading === a.approval_id ? <Loader2 className="size-4 animate-spin text-green-500" /> : <Check className="size-4 text-green-500" />}
                    </button>
                    <button onClick={e => { e.stopPropagation(); handleReject(a.approval_id); }}
                      className="p-1.5 rounded-md hover:bg-red-50 transition-colors" title="Reject"
                      data-testid={`reject-btn-${a.approval_id}`}>
                      <X className="size-4 text-red-500" />
                    </button>
                  </div>
                </div>
                {expandedId === a.approval_id && (
                  <div className="px-8 py-4 border-b" style={{ borderColor: 'rgba(255,107,0,0.05)', background: 'rgba(45,122,74,0.02)' }}>
                    <div className="grid grid-cols-2 gap-4 text-xs">
                      <div>
                        <div className="font-semibold mb-1" style={{ color: 'var(--aurem-heading)' }}>Action Details</div>
                        <div style={{ color: 'var(--aurem-body-secondary)' }}>Strategy: {a.action?.strategy || '-'}</div>
                        <div style={{ color: 'var(--aurem-body-secondary)' }}>Finding: {a.action?.finding_type || '-'}</div>
                        <div style={{ color: 'var(--aurem-body-secondary)' }}>Severity: {a.action?.severity || '-'}</div>
                      </div>
                      <div>
                        <div className="font-semibold mb-1" style={{ color: 'var(--aurem-heading)' }}>Approval Info</div>
                        <div style={{ color: 'var(--aurem-body-secondary)' }}>Decision: {a.decision_type}</div>
                        <div style={{ color: 'var(--aurem-body-secondary)' }}>Reason: {a.reason}</div>
                        {a.countdown_remaining_minutes != null && <div style={{ color: '#EAB308' }}>Auto-executes in {Math.ceil(a.countdown_remaining_minutes)} minutes</div>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* History Table */}
      {tab === 'history' && (
        <div className="aurem-glass-card overflow-hidden" data-testid="history-table">
          <div className="grid grid-cols-[1fr_120px_100px_100px_120px] gap-3 px-5 py-3 text-xs font-semibold border-b"
            style={{ borderColor: 'rgba(61,58,57,0.25)', color: 'var(--aurem-body-secondary)', background: 'rgba(255,107,0,0.03)' }}>
            <div>Action</div>
            <div>Type</div>
            <div>Decision</div>
            <div>Method</div>
            <div>Time</div>
          </div>

          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16" data-testid="no-history">
              <Clock className="size-10 mb-3" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.4 }} />
              <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>No approval history yet</p>
            </div>
          ) : (
            history.map((h, i) => (
              <div key={h.approval_id || i} className="grid grid-cols-[1fr_120px_100px_100px_120px] gap-3 px-5 py-2.5 items-center text-sm border-b"
                style={{ borderColor: 'rgba(255,107,0,0.04)' }}>
                <div className="truncate" style={{ color: 'var(--aurem-heading)' }}>{h.action?.strategy || h.action_type}</div>
                <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{ACTION_LABELS[h.action_type] || h.action_type}</div>
                <div className="flex items-center gap-1">
                  {h.status === 'approved' || h.status === 'auto_approved' || h.status === 'auto_cancel_approved' ? (
                    <><CheckCircle className="size-3.5 text-green-500" /><span className="text-xs text-green-600">Approved</span></>
                  ) : (
                    <><XCircle className="size-3.5 text-red-500" /><span className="text-xs text-red-600">Rejected</span></>
                  )}
                </div>
                <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{h.decided_by || (h.status?.includes('auto') ? 'Auto' : 'Manual')}</div>
                <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {h.decided_at ? new Date(h.decided_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-'}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
