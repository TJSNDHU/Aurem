/**
 * AUREM Training Dashboard
 * Upload knowledge, view AutoTune profiles, manage A2A learning, voice training.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Brain, Upload, BookOpen, Mic, Users, Trash2, Plus,
  FileText, Zap, RefreshCw, ChevronRight, Database,
  BarChart3, ArrowUpRight, CheckCircle2, AlertCircle,
  TrendingUp, ThumbsUp, ThumbsDown, Activity
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const CATEGORIES = [
  { value: 'general', label: 'General Knowledge' },
  { value: 'faq', label: 'FAQ' },
  { value: 'product', label: 'Product Info' },
  { value: 'playbook', label: 'Sales Playbook' },
  { value: 'objection', label: 'Objection Handling' },
];

const TAB_CONFIG = [
  { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen },
  { id: 'autotune', label: 'AutoTune', icon: Zap },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'agents', label: 'Agent Learning', icon: Users },
  { id: 'voice', label: 'Voice Profiles', icon: Mic },
];

export default function TrainingDashboard({ token }) {
  const [activeTab, setActiveTab] = useState('knowledge');
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/training/overview`, { headers });
      if (res.ok) setOverview(await res.json());
    } catch (e) { console.error('Overview fetch error:', e); }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  const statCards = overview ? [
    { label: 'Knowledge Items', value: overview.knowledge_items, icon: BookOpen, color: '#FF6B00' },
    { label: 'AutoTune Feedbacks', value: overview.autotune_feedbacks, icon: Zap, color: '#FF6B00' },
    { label: 'Voice Profiles', value: overview.voice_profiles, icon: Mic, color: '#6366f1' },
    { label: 'Customer Memories', value: overview.customer_memories, icon: Brain, color: '#e11d48' },
  ] : [];

  return (
    <div className="flex-1 flex flex-col" style={{ background: 'transparent' }} data-testid="training-dashboard">
      <header className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid rgba(61,58,57,0.3)', background: 'rgba(255,255,255,0.5)', backdropFilter: 'blur(12px)' }}>
        <div>
          <h1 className="text-lg font-bold text-[#1A1A2E]" data-testid="training-title">AI Training Center</h1>
          <p className="text-xs text-[#888]">Feed ORA your business knowledge. The smarter it gets, the more money it makes.</p>
        </div>
        <button onClick={fetchOverview} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#FF6B00] border border-[rgba(255,107,0,0.12)] hover:bg-[rgba(45,122,74,0.05)] transition-colors" data-testid="refresh-training">
          <RefreshCw className="size-3.5" /> Refresh
        </button>
      </header>

      {/* Stats Row */}
      {!loading && overview && (
        <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          {statCards.map((s, i) => (
            <div key={i} className="rounded-xl p-4" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }} data-testid={`stat-${s.label.toLowerCase().replace(/\s/g,'-')}`}>
              <div className="flex items-center gap-2 mb-2">
                <s.icon className="size-4" style={{ color: s.color }} />
                <span className="text-[10px] font-semibold tracking-wider text-[#888] uppercase">{s.label}</span>
              </div>
              <div className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tab Nav */}
      <div className="px-6 flex gap-1" style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        {TAB_CONFIG.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium rounded-t-lg transition-colors ${
              activeTab === tab.id
                ? 'text-[#FF6B00] bg-white border border-b-0 border-[rgba(255,107,0,0.1)]'
                : 'text-[#888] hover:text-[#555]'
            }`}
          >
            <tab.icon className="size-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {activeTab === 'knowledge' && <KnowledgeTab token={token} onUpdate={fetchOverview} />}
        {activeTab === 'autotune' && <AutoTuneTab token={token} />}
        {activeTab === 'analytics' && <AutoTuneAnalyticsTab token={token} />}
        {activeTab === 'agents' && <AgentLearningTab token={token} />}
        {activeTab === 'voice' && <VoiceTab token={token} />}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* KNOWLEDGE BASE TAB                                         */
/* ═══════════════════════════════════════════════════════════ */
function KnowledgeTab({ token, onUpdate }) {
  const [items, setItems] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('general');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);

  // Force Sync state
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchItems = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/training/knowledge`, { headers });
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [headers]);

  // Fetch sync status on mount
  const fetchSyncStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/ora/knowledge/status`, { headers });
      if (res.ok) {
        const data = await res.json();
        setSyncStatus(data);
      }
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => { fetchItems(); fetchSyncStatus(); }, [fetchItems, fetchSyncStatus]);

  // Force Knowledge Sync
  const handleForceSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await fetch(`${API_URL}/api/ora/knowledge/force-sync`, {
        method: 'POST', headers,
      });
      if (res.ok) {
        const data = await res.json();
        setSyncResult(data);
        fetchSyncStatus(); // Refresh status
        onUpdate();
      } else {
        setSyncResult({ success: false, message: 'Sync failed' });
      }
    } catch (e) {
      setSyncResult({ success: false, message: e.message });
    } finally {
      setSyncing(false);
    }
  };

  const addKnowledge = async () => {
    if (!title.trim() || !content.trim()) return;
    setUploading(true);
    try {
      const res = await fetch(`${API_URL}/api/training/knowledge`, {
        method: 'POST', headers,
        body: JSON.stringify({ title, content, category }),
      });
      if (res.ok) {
        setTitle(''); setContent(''); setShowAdd(false);
        fetchItems(); onUpdate();
      }
    } catch (e) { console.error(e); }
    finally { setUploading(false); }
  };

  const deleteItem = async (id) => {
    try {
      await fetch(`${API_URL}/api/training/knowledge/${id}`, { method: 'DELETE', headers });
      fetchItems(); onUpdate();
    } catch (e) { console.error(e); }
  };

  const uploadFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('category', category);
      const res = await fetch(`${API_URL}/api/training/knowledge/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) { fetchItems(); onUpdate(); }
    } catch (e) { console.error(e); }
    finally { setUploading(false); e.target.value = ''; }
  };

  const catColor = (c) => {
    const map = { general: '#6B7280', faq: '#2563EB', product: '#059669', playbook: '#D97706', objection: '#DC2626' };
    return map[c] || '#6B7280';
  };

  return (
    <div data-testid="knowledge-tab">
      {/* Force Knowledge Sync Panel */}
      <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.3)' }} data-testid="knowledge-sync-panel">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-lg flex items-center justify-center" style={{ background: 'rgba(61,58,57,0.25)' }}>
              <Database className="size-4.5 text-[#FF6B00]" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-[#1A1A2E] tracking-wide">ORA Knowledge Sync</h3>
              <p className="text-[10px] text-[#888]">
                {syncStatus
                  ? syncStatus.status === 'never_synced'
                    ? `${syncStatus.total_training_files} training files — never synced`
                    : `Last sync: ${new Date(syncStatus.last_sync).toLocaleString()} — ${syncStatus.docs_synced} docs, ${syncStatus.total_vectors} vectors`
                  : 'Loading status...'
                }
              </p>
            </div>
          </div>
          <button
            onClick={handleForceSync}
            disabled={syncing}
            data-testid="force-sync-btn"
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
            style={{
              background: syncing ? 'rgba(61,58,57,0.25)' : '#FF6B00',
              color: syncing ? '#FF6B00' : '#fff',
            }}
          >
            <RefreshCw className={`size-3.5 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing...' : 'Force Sync'}
          </button>
        </div>
        {syncResult && (
          <div className={`mt-3 p-2.5 rounded-lg text-xs font-medium flex items-center gap-2 ${syncResult.success ? 'bg-[rgba(61,58,57,0.15)] text-[#FF6B00]' : 'bg-red-50 text-red-600'}`} data-testid="sync-result">
            {syncResult.success ? <CheckCircle2 className="size-3.5" /> : <AlertCircle className="size-3.5" />}
            {syncResult.message}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-[#1A1A2E]">Knowledge Base</h2>
          <p className="text-[11px] text-[#888]">Feed ORA your business data, FAQs, product info, sales playbooks, objection scripts</p>
        </div>
        <div className="flex gap-2">
          <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#FF6B00] border border-[rgba(255,107,0,0.12)] hover:bg-[rgba(45,122,74,0.05)] cursor-pointer transition-colors" data-testid="upload-file-btn">
            <Upload className="size-3.5" /> Upload File
            <input type="file" accept=".txt,.md,.csv,.json" onChange={uploadFile} className="hidden" />
          </label>
          <button onClick={() => setShowAdd(!showAdd)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-colors" style={{ background: '#FF6B00' }} data-testid="add-knowledge-btn">
            <Plus className="size-3.5" /> Add Knowledge
          </button>
        </div>
      </div>

      {/* Add Knowledge Form */}
      {showAdd && (
        <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.8)', border: '1px solid rgba(255,107,0,0.1)' }} data-testid="add-knowledge-form">
          <div className="grid grid-cols-2 gap-3 mb-3">
            <input
              value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="Title (e.g., 'Pricing FAQ')"
              className="px-3 py-2 rounded-lg text-sm border border-[rgba(0,0,0,0.1)] focus:outline-none focus:border-[#FF6B00]"
              data-testid="knowledge-title-input"
            />
            <select
              value={category} onChange={(e) => setCategory(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm border border-[rgba(0,0,0,0.1)] focus:outline-none focus:border-[#FF6B00]"
              data-testid="knowledge-category-select"
            >
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <textarea
            value={content} onChange={(e) => setContent(e.target.value)}
            placeholder="Paste your knowledge here — product descriptions, FAQ answers, sales scripts..."
            rows={6}
            className="w-full px-3 py-2 rounded-lg text-sm border border-[rgba(0,0,0,0.1)] focus:outline-none focus:border-[#FF6B00] resize-none"
            data-testid="knowledge-content-input"
          />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowAdd(false)} className="px-4 py-1.5 rounded-lg text-xs font-medium text-[#888] hover:text-[#555]">Cancel</button>
            <button onClick={addKnowledge} disabled={uploading || !title.trim() || !content.trim()} className="px-4 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50" style={{ background: '#FF6B00' }} data-testid="save-knowledge-btn">
              {uploading ? 'Indexing...' : 'Save & Index'}
            </button>
          </div>
        </div>
      )}

      {/* Knowledge List */}
      {loading ? (
        <div className="text-center py-8 text-[#888] text-sm">Loading knowledge base…</div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 rounded-xl" style={{ background: 'rgba(255,255,255,0.5)', border: '1px dashed rgba(0,0,0,0.1)' }} data-testid="empty-knowledge">
          <Database className="size-8 mx-auto mb-3 text-[#ccc]" />
          <p className="text-sm font-medium text-[#888]">No knowledge indexed yet</p>
          <p className="text-xs text-[#aaa] mt-1">Upload files or add knowledge manually to train ORA</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={item.id || i} className="flex items-start gap-3 p-3 rounded-xl group hover:shadow-sm transition-shadow" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.04)' }} data-testid={`knowledge-item-${i}`}>
              <FileText className="size-4 mt-0.5 text-[#888] shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[#1A1A2E] truncate">{item.title}</span>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider" style={{ color: catColor(item.category), background: `${catColor(item.category)}15` }}>{item.category}</span>
                  {item.indexed && <CheckCircle2 className="size-3 text-[#FF6B00]" />}
                </div>
                <p className="text-[11px] text-[#888] mt-0.5 line-clamp-2">{item.summary || item.content?.substring(0, 150)}</p>
                <span className="text-[10px] text-[#aaa] mt-1 block">{item.char_count?.toLocaleString()} chars</span>
              </div>
              <button onClick={() => deleteItem(item.id)} className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-[#ccc] hover:text-red-500 hover:bg-red-50 transition-all" data-testid={`delete-knowledge-${i}`}>
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* AUTOTUNE TAB                                               */
/* ═══════════════════════════════════════════════════════════ */
/* ═══════════════════════════════════════════════════════════ */
/* AUTOTUNE ANALYTICS TAB                                     */
/* ═══════════════════════════════════════════════════════════ */

const PROFILE_COLORS = {
  ANALYTICAL: '#3B82F6',
  STRATEGIC: '#8B5CF6',
  CREATIVE: '#EC4899',
  CONVERSATIONAL: '#10B981',
  CHAOTIC: '#F59E0B',
  BALANCED: '#6B7280',
};

function AutoTuneAnalyticsTab({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/training/autotune/analytics`, { headers });
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  if (loading) return <div className="text-center py-8 text-[#888] text-sm">Loading analytics…</div>;
  if (!data) return <div className="text-center py-8 text-[#888]">Failed to load analytics</div>;

  const { profile_usage, confidence_stats, learning, total_queries, timeline } = data;
  const profiles = Object.entries(profile_usage).sort((a, b) => b[1].count - a[1].count);
  const maxCount = profiles.length ? profiles[0][1].count : 1;

  const trendEmoji = confidence_stats.trend_direction === 'improving' ? '++' : confidence_stats.trend_direction === 'declining' ? '--' : '==';
  const trendColor = confidence_stats.trend_direction === 'improving' ? '#FF6B00' : confidence_stats.trend_direction === 'declining' ? '#FF6B6B' : '#888';

  const weeklyImprovement = confidence_stats.trend > 0
    ? `+${(confidence_stats.trend * 100).toFixed(1)}%`
    : `${(confidence_stats.trend * 100).toFixed(1)}%`;

  return (
    <div data-testid="autotune-analytics-tab">
      <div className="mb-4">
        <h2 className="text-sm font-bold text-[#1A1A2E]">AutoTune Analytics</h2>
        <p className="text-[11px] text-[#888]">Watch ORA get smarter in real time. Every query trains the model.</p>
      </div>

      {/* Card 4 — Learning Velocity (Hero) */}
      <div className="mb-4 p-5 rounded-xl" style={{ background: 'linear-gradient(135deg, #1C1712, #211D17)', border: '1px solid rgba(184,135,89,0.15)' }} data-testid="learning-velocity-card">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp className="size-4 text-[#D4A574]" />
          <span className="text-[10px] font-bold tracking-[1.5px] text-[#D4A574] uppercase">Learning Velocity</span>
        </div>
        <div className="flex items-end gap-3">
          <span className="text-3xl font-bold" style={{ color: trendColor }}>{weeklyImprovement}</span>
          <span className="text-xs text-[#9B8B7A] pb-1">confidence this period</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold" style={{
            background: confidence_stats.trend_direction === 'improving' ? 'rgba(255,107,0,0.1)' : 'rgba(255,107,107,0.1)',
            color: trendColor,
          }}>
            {trendEmoji} {confidence_stats.trend_direction.toUpperCase()}
          </span>
          <span className="text-[10px] text-[#6B5744]">
            Recent: {(confidence_stats.recent_avg * 100).toFixed(1)}% | Older: {(confidence_stats.older_avg * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Summary Stats Row */}
      <div className="grid grid-cols-4 gap-3 mb-4" data-testid="analytics-summary">
        <div className="p-3 rounded-xl text-center" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-xl font-bold text-[#1A1A2E]">{total_queries}</div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Total Queries</div>
        </div>
        <div className="p-3 rounded-xl text-center" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-xl font-bold text-[#FF6B00]">{(confidence_stats.overall_avg * 100).toFixed(0)}%</div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Avg Confidence</div>
        </div>
        <div className="p-3 rounded-xl text-center" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-xl font-bold text-[#FF6B00]">{learning.ema_profiles_learned}</div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">EMA Learned</div>
        </div>
        <div className="p-3 rounded-xl text-center" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-xl font-bold" style={{ color: learning.satisfaction_rate >= 70 ? '#FF6B00' : '#FF6B00' }}>
            {learning.satisfaction_rate}%
          </div>
          <div className="text-[9px] text-[#888] uppercase tracking-wider font-bold">Satisfaction</div>
        </div>
      </div>

      {/* Card 1 — Profile Usage Bar Chart */}
      <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }} data-testid="profile-usage-card">
        <h3 className="text-xs font-bold text-[#555] uppercase tracking-wider mb-3">Profile Usage Distribution</h3>
        {profiles.length === 0 ? (
          <p className="text-xs text-[#aaa] text-center py-4">No queries tracked yet. Start chatting with ORA!</p>
        ) : (
          <div className="space-y-2">
            {profiles.map(([ctx, info]) => (
              <div key={ctx} className="flex items-center gap-3" data-testid={`usage-${ctx}`}>
                <span className="text-[10px] font-bold w-28 text-right truncate" style={{ color: PROFILE_COLORS[ctx] || '#888' }}>{ctx}</span>
                <div className="flex-1 h-6 rounded-md overflow-hidden" style={{ background: 'rgba(0,0,0,0.04)' }}>
                  <div
                    className="h-full rounded-md flex items-center px-2 transition-all duration-700"
                    style={{
                      width: `${Math.max((info.count / maxCount) * 100, 8)}%`,
                      background: `${PROFILE_COLORS[ctx] || '#888'}20`,
                      borderLeft: `3px solid ${PROFILE_COLORS[ctx] || '#888'}`,
                    }}
                  >
                    <span className="text-[10px] font-bold" style={{ color: PROFILE_COLORS[ctx] || '#888' }}>{info.count}</span>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-[#aaa] w-10 text-right">{info.percentage}%</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Card 3 — Profile Accuracy Table */}
      <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }} data-testid="profile-accuracy-card">
        <h3 className="text-xs font-bold text-[#555] uppercase tracking-wider mb-3">Profile Performance</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[9px] text-[#aaa] uppercase tracking-wider">
              <th className="text-left py-1.5 font-bold">Profile</th>
              <th className="text-center py-1.5 font-bold">Queries</th>
              <th className="text-center py-1.5 font-bold">Avg Confidence</th>
              <th className="text-center py-1.5 font-bold">Avg Temp</th>
              <th className="text-center py-1.5 font-bold">EMA Learned</th>
            </tr>
          </thead>
          <tbody>
            {profiles.map(([ctx, info]) => (
              <tr key={ctx} className="border-t border-[rgba(0,0,0,0.04)]">
                <td className="py-2">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2 rounded-full" style={{ background: PROFILE_COLORS[ctx] || '#888' }} />
                    <span className="font-bold text-[#1A1A2E]">{ctx}</span>
                  </span>
                </td>
                <td className="text-center text-[#555]">{info.count}</td>
                <td className="text-center">
                  <span className={`font-mono font-bold ${info.avg_confidence >= 0.7 ? 'text-[#FF6B00]' : info.avg_confidence >= 0.4 ? 'text-[#FF6B00]' : 'text-[#FF6B6B]'}`}>
                    {(info.avg_confidence * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="text-center font-mono text-[#555]">{info.avg_temperature}</td>
                <td className="text-center">
                  {info.learned_count > 0 ? (
                    <span className="text-[#FF6B00] font-bold">{info.learned_count}</span>
                  ) : (
                    <span className="text-[#ccc]">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Card 2 — Confidence Trend (EMA Curve) */}
      <div className="mb-4 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }} data-testid="confidence-trend-card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold text-[#555] uppercase tracking-wider">Confidence Trend (EMA Curve)</h3>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold" style={{
            background: confidence_stats.trend_direction === 'improving' ? 'rgba(61,58,57,0.25)' : 'rgba(255,107,107,0.08)',
            color: trendColor,
          }}>
            {confidence_stats.trend_direction === 'improving' ? 'Rising' : confidence_stats.trend_direction === 'declining' ? 'Falling' : 'Stable'}
          </span>
        </div>
        {/* Mini bar chart from timeline data */}
        {timeline.length > 0 ? (
          <div className="flex items-end gap-0.5 h-16" data-testid="timeline-bars">
            {timeline.slice(-24).map((t, i) => {
              const maxT = Math.max(...timeline.slice(-24).map(x => x.total || 1));
              const h = Math.max(((t.total || 0) / maxT) * 100, 4);
              return (
                <div key={i} className="flex-1 rounded-t-sm transition-all" style={{
                  height: `${h}%`,
                  background: 'linear-gradient(to top, rgba(45,122,74,0.3), rgba(61,58,57,0.25))',
                  minWidth: '4px',
                }} title={`${t.hour}: ${t.total} queries`} />
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[#aaa] text-center py-4">Need more data points. Keep chatting with ORA!</p>
        )}
        <div className="flex justify-between mt-1 text-[8px] text-[#bbb]">
          <span>24h ago</span>
          <span>Now</span>
        </div>
      </div>

      {/* Feedback summary */}
      <div className="p-4 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.25)' }}>
        <div className="flex items-center gap-2 mb-2">
          <Activity className="size-4 text-[#FF6B00]" />
          <span className="text-xs font-bold text-[#FF6B00]">Feedback Loop</span>
        </div>
        <div className="flex gap-4">
          <div className="flex items-center gap-1.5">
            <ThumbsUp className="size-3.5 text-[#FF6B00]" />
            <span className="text-xs font-bold text-[#FF6B00]">{learning.thumbs_up}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ThumbsDown className="size-3.5 text-[#FF6B6B]" />
            <span className="text-xs font-bold text-[#FF6B6B]">{learning.thumbs_down}</span>
          </div>
          <span className="text-[10px] text-[#888]">Total: {learning.total_feedback} ratings</span>
        </div>
        <p className="text-[10px] text-[#888] mt-2">
          Each thumbs up/down in ORA Chat feeds the EMA curve. More ratings = faster learning.
        </p>
      </div>
    </div>
  );
}


function AutoTuneTab({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/training/autotune`, { headers });
        if (res.ok) setData(await res.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, [headers]);

  if (loading) return <div className="text-center py-8 text-[#888] text-sm">Loading AutoTune data…</div>;
  if (!data) return <div className="text-center py-8 text-[#888]">Failed to load AutoTune data</div>;

  const contexts = Object.keys(data.base_profiles || {});

  return (
    <div data-testid="autotune-tab">
      <div className="mb-4">
        <h2 className="text-sm font-bold text-[#1A1A2E]">AutoTune Learning</h2>
        <p className="text-[11px] text-[#888]">ORA learns from your feedback to optimize response quality per context</p>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1">Total Feedback</div>
          <div className="text-2xl font-bold text-[#FF6B00]">{data.feedback_count}</div>
        </div>
        <div className="p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1">Context Profiles</div>
          <div className="text-2xl font-bold text-[#FF6B00]">{contexts.length}</div>
        </div>
      </div>

      {/* Base Profiles */}
      <h3 className="text-xs font-bold text-[#555] uppercase tracking-wider mb-2">Base Context Profiles</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-6">
        {contexts.map(ctx => {
          const profile = data.base_profiles[ctx];
          return (
            <div key={ctx} className="p-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.04)' }} data-testid={`profile-${ctx.toLowerCase()}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#1A1A2E]">{ctx}</span>
                <span className="text-[9px] px-2 py-0.5 rounded-full bg-[rgba(61,58,57,0.15)] text-[#FF6B00] font-semibold">BASE</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(profile).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="text-center">
                    <div className="text-[10px] text-[#aaa] truncate">{k.replace(/_/g, ' ')}</div>
                    <div className="text-xs font-mono font-bold text-[#555]">{typeof v === 'number' ? v.toFixed(2) : v}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Learned Adjustments */}
      {data.learned_contexts?.length > 0 && (
        <>
          <h3 className="text-xs font-bold text-[#555] uppercase tracking-wider mb-2">Learned Adjustments (from your feedback)</h3>
          <div className="space-y-2">
            {data.learned_contexts.map((ctx, i) => (
              <div key={i} className="p-3 rounded-xl flex items-center gap-3" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.25)' }}>
                <ArrowUpRight className="size-4 text-[#FF6B00]" />
                <div className="flex-1">
                  <span className="text-xs font-bold text-[#FF6B00]">{ctx.context}</span>
                  <span className="text-[10px] text-[#888] ml-2">Samples: {ctx.sample_count || 0}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="mt-6 p-4 rounded-xl" style={{ background: 'rgba(212,163,115,0.08)', border: '1px solid rgba(212,163,115,0.15)' }}>
        <div className="flex items-start gap-2">
          <AlertCircle className="size-4 text-[#FF6B00] mt-0.5 shrink-0" />
          <div>
            <p className="text-xs font-medium text-[#1A1A2E]">How to train AutoTune faster</p>
            <p className="text-[11px] text-[#888] mt-1">Rate ORA responses using the thumbs up/down buttons in ORA Chat. Each rating teaches the system which LLM parameters work best for different conversation types (sales, analytics, creative, support).</p>
          </div>
        </div>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* AGENT LEARNING TAB                                         */
/* ═══════════════════════════════════════════════════════════ */
function AgentLearningTab({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/training/a2a`, { headers });
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const triggerLearning = async () => {
    setTriggering(true);
    try {
      const res = await fetch(`${API_URL}/api/training/a2a/trigger`, { method: 'POST', headers });
      if (res.ok) fetchData();
    } catch (e) { console.error(e); }
    finally { setTriggering(false); }
  };

  if (loading) return <div className="text-center py-8 text-[#888] text-sm">Loading agent data…</div>;
  if (!data) return <div className="text-center py-8 text-[#888]">Failed to load agent data</div>;

  const skillColor = (level) => {
    if (level >= 85) return '#FF6B00';
    if (level >= 70) return '#FF6B00';
    return '#e11d48';
  };

  return (
    <div data-testid="agents-tab">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-[#1A1A2E]">Agent-to-Agent Learning</h2>
          <p className="text-[11px] text-[#888]">Your 5 AI agents cross-train each other, sharing skills and knowledge</p>
        </div>
        <button onClick={triggerLearning} disabled={triggering} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50" style={{ background: '#FF6B00' }} data-testid="trigger-learning-btn">
          <RefreshCw className={`size-3.5 ${triggering ? 'animate-spin' : ''}`} />
          {triggering ? 'Learning...' : 'Trigger Daily Learning'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1">Learning Sessions</div>
          <div className="text-2xl font-bold text-[#FF6B00]">{data.total_sessions}</div>
        </div>
        <div className="p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1">Active Agents</div>
          <div className="text-2xl font-bold text-[#FF6B00]">{data.agents?.length || 0}</div>
        </div>
      </div>

      {/* Agent Cards */}
      <div className="space-y-2">
        {(data.agents || []).map((agent) => (
          <div key={agent.id} className="flex items-center gap-4 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.04)' }} data-testid={`agent-${agent.id}`}>
            <div className="size-10 rounded-full flex items-center justify-center text-white text-xs font-bold" style={{ background: skillColor(agent.skill_level) }}>
              {agent.skill_level}
            </div>
            <div className="flex-1">
              <div className="text-sm font-bold text-[#1A1A2E]">{agent.name}</div>
              <div className="text-[11px] text-[#888]">{agent.role}</div>
            </div>
            <div className="w-32">
              <div className="h-2 rounded-full bg-[rgba(0,0,0,0.06)]">
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${agent.skill_level}%`, background: skillColor(agent.skill_level) }} />
              </div>
            </div>
            <ChevronRight className="size-4 text-[#ccc]" />
          </div>
        ))}
      </div>

      {data.last_session && (
        <div className="mt-4 p-3 rounded-xl text-xs" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.25)' }}>
          <span className="font-bold text-[#FF6B00]">Last Session:</span>
          <span className="text-[#888] ml-2">
            {data.last_session.skills_shared} skills shared, {data.last_session.knowledge_synced} knowledge items synced, {data.last_session.errors_resolved} errors resolved
          </span>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* VOICE PROFILES TAB                                         */
/* ═══════════════════════════════════════════════════════════ */
function VoiceTab({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/training/voice`, { headers });
        if (res.ok) setData(await res.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, [headers]);

  if (loading) return <div className="text-center py-8 text-[#888] text-sm">Loading voice data…</div>;

  return (
    <div data-testid="voice-tab">
      <div className="mb-4">
        <h2 className="text-sm font-bold text-[#1A1A2E]">Voice Training Profiles</h2>
        <p className="text-[11px] text-[#888]">Train AI to sound like your sales team. Record samples to create custom voice personas.</p>
      </div>

      {(data?.profiles || []).length === 0 ? (
        <div className="text-center py-12 rounded-xl" style={{ background: 'rgba(255,255,255,0.5)', border: '1px dashed rgba(0,0,0,0.1)' }} data-testid="empty-voice">
          <Mic className="size-8 mx-auto mb-3 text-[#ccc]" />
          <p className="text-sm font-medium text-[#888]">No voice profiles yet</p>
          <p className="text-xs text-[#aaa] mt-1">Go to Voice Sales Agent to record training samples</p>
          <p className="text-[10px] text-[#bbb] mt-3">The V2V engine currently uses OpenAI TTS (alloy voice) by default</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.profiles.map((p, i) => (
            <div key={i} className="flex items-center gap-3 p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.04)' }} data-testid={`voice-profile-${i}`}>
              <Mic className="size-5 text-[#6366f1]" />
              <div className="flex-1">
                <div className="text-sm font-medium text-[#1A1A2E]">{p.name || p.profile_id}</div>
                <div className="text-[11px] text-[#888]">{p.samples?.length || 0} samples recorded</div>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${p.status === 'ready' ? 'bg-[rgba(61,58,57,0.15)] text-[#FF6B00]' : 'bg-[rgba(212,163,115,0.08)] text-[#FF6B00]'}`}>
                {p.status || 'TRAINING'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
