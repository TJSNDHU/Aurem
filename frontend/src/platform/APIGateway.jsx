/**
 * AUREM API Gateway Dashboard
 * Manage API endpoints, rate limiting, webhooks, and usage monitoring
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Code, Globe, Shield, Activity, Clock, Copy, Check,
  RefreshCw, AlertCircle, ChevronRight, Search, Filter,
  Zap, Lock, Unlock, BarChart3, ArrowUpRight, Eye, EyeOff,
  Plus, X, Settings, Terminal
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const ENDPOINT_GROUPS = [
  {
    category: 'Authentication',
    color: '#D4AF37',
    endpoints: [
      { method: 'POST', path: '/api/auth/login', description: 'User authentication', rateLimit: '30/min', status: 'active' },
      { method: 'POST', path: '/api/auth/register', description: 'User registration', rateLimit: '10/min', status: 'active' },
      { method: 'POST', path: '/api/biometric/pin-verify', description: 'PIN verification', rateLimit: '5/min', status: 'active' },
    ]
  },
  {
    category: 'AI & Chat',
    color: '#8B5CF6',
    endpoints: [
      { method: 'POST', path: '/api/aurem/chat', description: 'AI conversation', rateLimit: '60/min', status: 'active' },
      { method: 'GET', path: '/api/aurem/agents/status', description: 'Agent swarm status', rateLimit: '120/min', status: 'active' },
      { method: 'GET', path: '/api/aurem/metrics', description: 'Platform metrics', rateLimit: '120/min', status: 'active' },
    ]
  },
  {
    category: 'Integrations',
    color: '#4ade80',
    endpoints: [
      { method: 'GET', path: '/api/integration/keys', description: 'List API keys', rateLimit: '30/min', status: 'active' },
      { method: 'POST', path: '/api/integration/keys', description: 'Generate API key', rateLimit: '10/min', status: 'active' },
      { method: 'GET', path: '/api/gmail/{id}/messages', description: 'List Gmail messages', rateLimit: '60/min', status: 'active' },
      { method: 'POST', path: '/api/whatsapp/{id}/send', description: 'Send WhatsApp message', rateLimit: '30/min', status: 'active' },
    ]
  },
  {
    category: 'Analytics',
    color: '#f59e0b',
    endpoints: [
      { method: 'GET', path: '/api/aurem/activity/feed', description: 'Activity feed', rateLimit: '60/min', status: 'active' },
      { method: 'GET', path: '/api/scanner/analyze', description: 'Customer analysis', rateLimit: '20/min', status: 'active' },
      { method: 'GET', path: '/api/sales/pipeline', description: 'Sales pipeline data', rateLimit: '60/min', status: 'active' },
    ]
  }
];

const METHOD_COLORS = {
  GET: '#4ade80',
  POST: '#3b82f6',
  PUT: '#f59e0b',
  DELETE: '#ef4444',
  PATCH: '#8B5CF6'
};

export default function APIGateway({ token }) {
  const [gatewayStats, setGatewayStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEndpoint, setSelectedEndpoint] = useState(null);
  const [copied, setCopied] = useState(null);
  const [webhooks, setWebhooks] = useState([]);
  const [showAddWebhook, setShowAddWebhook] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookEvents, setWebhookEvents] = useState([]);
  const [activeTab, setActiveTab] = useState('endpoints');
  const [requestLogs, setRequestLogs] = useState([]);

  const fetchGatewayStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/gateway/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setGatewayStats(data);
      }
    } catch {
      setGatewayStats({
        total_requests_today: 0,
        avg_latency_ms: 0,
        error_rate: 0,
        active_webhooks: 0,
        uptime_percent: 100.0
      });
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchWebhooks = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/gateway/webhooks`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setWebhooks(data.webhooks || []);
      }
    } catch {
      setWebhooks([]);
    }
  }, [token]);

  const fetchRequestLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/gateway/request-logs?limit=30`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRequestLogs(data.logs || []);
      }
    } catch {
      setRequestLogs([]);
    }
  }, [token]);

  useEffect(() => {
    fetchGatewayStats();
    fetchWebhooks();
    fetchRequestLogs();
  }, [fetchGatewayStats, fetchWebhooks, fetchRequestLogs]);

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const filteredGroups = ENDPOINT_GROUPS.map(group => ({
    ...group,
    endpoints: group.endpoints.filter(ep =>
      !searchQuery || ep.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ep.description.toLowerCase().includes(searchQuery.toLowerCase())
    )
  })).filter(group => group.endpoints.length > 0);

  const stats = gatewayStats || { total_requests_today: 0, avg_latency_ms: 0, error_rate: 0, active_webhooks: 0, uptime_percent: 100 };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="api-gateway-loading">
        <div className="flex items-center gap-3 text-[#666]">
          <RefreshCw className="size-5 animate-spin" />
          <span className="text-sm">Loading API Gateway…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="api-gateway">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">API Gateway</h1>
            <p className="text-xs text-[#5a5a72]">Monitor endpoints, manage rate limits, and configure webhooks</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-medium bg-[#4ade80]/10 text-[#4ade80]">
              <div className="size-1.5 bg-[#4ade80] rounded-full animate-pulse" />
              OPERATIONAL
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-5 gap-3 mb-8">
          {[
            { label: 'REQUESTS TODAY', value: stats.total_requests_today.toLocaleString(), icon: Activity, color: '#D4AF37' },
            { label: 'AVG LATENCY', value: `${stats.avg_latency_ms}ms`, icon: Clock, color: '#4ade80' },
            { label: 'ERROR RATE', value: `${stats.error_rate}%`, icon: AlertCircle, color: stats.error_rate < 1 ? '#4ade80' : '#ef4444' },
            { label: 'WEBHOOKS', value: stats.active_webhooks, icon: Zap, color: '#D4AF37' },
            { label: 'UPTIME', value: `${stats.uptime_percent}%`, icon: Shield, color: '#4ade80' }
          ].map((stat, idx) => (
            <div key={idx} className="p-3.5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg">
              <div className="flex items-center gap-1.5 mb-1.5">
                <stat.icon className="size-3.5" style={{ color: stat.color }} />
                <span className="text-[9px] text-[#555] tracking-wider">{stat.label}</span>
              </div>
              <div className="text-xl font-semibold font-mono" style={{ color: stat.color }}>{stat.value}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/80 backdrop-blur-sm p-1 rounded-lg border border-[#FF6B00]/20 w-fit">
          {[
            { id: 'endpoints', label: 'Endpoints', icon: Code },
            { id: 'webhooks', label: 'Webhooks', icon: Zap },
            { id: 'logs', label: 'Request Logs', icon: Terminal }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`tab-${tab.id}`}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs transition-all ${
                activeTab === tab.id
                  ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30'
                  : 'text-[#666] hover:text-[#555]'
              }`}
            >
              <tab.icon className="size-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'endpoints' && (
          <>
            {/* Search */}
            <div className="relative mb-6">
              <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" />
              <input
                type="text"
                placeholder="Search endpoints..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                data-testid="api-search-input"
                className="w-full pl-10 pr-4 py-2.5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
              />
            </div>

            {/* Endpoint Groups */}
            <div className="space-y-6">
              {filteredGroups.map((group, gIdx) => (
                <div key={gIdx} className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-[#FF6B00]/20">
                    <div className="size-2 rounded-full" style={{ backgroundColor: group.color }} />
                    <h3 className="text-[11px] text-[#888] tracking-wider font-medium">{group.category.toUpperCase()}</h3>
                    <span className="text-[10px] text-[#555] ml-auto">{group.endpoints.length} endpoints</span>
                  </div>
                  <div className="divide-y divide-[#141414]">
                    {group.endpoints.map((ep, eIdx) => (
                      <div
                        key={eIdx}
                        className="flex items-center gap-4 px-4 py-3 hover:bg-white/40 transition-colors cursor-pointer group"
                        onClick={() => setSelectedEndpoint(ep)}
                      >
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-mono font-bold min-w-[50px] text-center"
                          style={{ backgroundColor: `${METHOD_COLORS[ep.method]}15`, color: METHOD_COLORS[ep.method] }}
                        >
                          {ep.method}
                        </span>
                        <code className="text-xs text-[#1A1A2E] font-mono flex-1">{ep.path}</code>
                        <span className="text-[10px] text-[#555] hidden group-hover:block">{ep.description}</span>
                        <span className="text-[10px] text-[#555] font-mono">{ep.rateLimit}</span>
                        <div className="size-1.5 rounded-full bg-[#4ade80]" />
                        <button
                          onClick={(e) => { e.stopPropagation(); copyToClipboard(ep.path, `${gIdx}-${eIdx}`); }}
                          className="text-[#555] hover:text-[#D4AF37] transition-colors"
                        >
                          {copied === `${gIdx}-${eIdx}` ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {activeTab === 'webhooks' && (
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#FF6B00]/20">
              <h3 className="text-xs text-[#555] tracking-wider">CONFIGURED WEBHOOKS</h3>
              <button
                onClick={() => setShowAddWebhook(true)}
                data-testid="add-webhook-btn"
                className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] text-[#050505] font-semibold bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity"
              >
                <Plus className="size-3" />
                Add Webhook
              </button>
            </div>
            {webhooks.length > 0 ? (
              <div className="divide-y divide-[#1A1A1A]">
                {webhooks.map((wh, idx) => (
                  <div key={idx} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <code className="text-xs text-[#1A1A2E] font-mono">{wh.url}</code>
                      <div className="flex gap-1.5 mt-1">
                        {(wh.events || []).map((ev, i) => (
                          <span key={i} className="px-1.5 py-0.5 text-[9px] bg-white/50 text-[#888] rounded">{ev}</span>
                        ))}
                      </div>
                    </div>
                    <div className="size-2 rounded-full bg-[#4ade80]" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-10 text-center">
                <Zap className="size-8 text-[#333] mx-auto mb-3" />
                <p className="text-sm text-[#555]">No webhooks configured</p>
                <p className="text-[11px] text-[#444] mt-1">Add a webhook to receive real-time event notifications</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#FF6B00]/20">
              <div className="flex items-center gap-2">
                <h3 className="text-xs text-[#555] tracking-wider">LIVE API REQUESTS</h3>
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] bg-[#4ade80]/10 text-[#4ade80]">
                  <div className="size-1.5 bg-[#4ade80] rounded-full animate-pulse" />
                  STREAMING
                </div>
              </div>
              <button onClick={fetchRequestLogs} className="text-[#555] hover:text-[#D4AF37] transition-colors" data-testid="refresh-logs-btn">
                <RefreshCw className="size-3.5" />
              </button>
            </div>
            <div className="p-4 font-mono text-xs space-y-1.5 max-h-[400px] overflow-auto bg-white/60">
              {requestLogs.length > 0 ? requestLogs.map((log, idx) => {
                const ts = log.timestamp ? new Date(log.timestamp) : new Date();
                const timeStr = ts.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
                return (
                  <div key={idx} className="flex items-center gap-3 text-[11px] py-1 hover:bg-white/80 backdrop-blur-sm rounded px-2 -mx-2" data-testid={`log-entry-${idx}`}>
                    <span className="text-[#555] w-16">{timeStr}</span>
                    <span className="w-12 font-bold" style={{ color: METHOD_COLORS[log.method] || '#888' }}>{log.method}</span>
                    <span className="text-[#555] flex-1">{log.path}</span>
                    <span className={log.status === 200 ? 'text-[#4ade80]' : 'text-[#ef4444]'}>{log.status}</span>
                    <span className="text-[#555] w-16 text-right">{log.latency_ms}ms</span>
                    <span className="text-[10px] text-[#888] w-20 text-right">{log.source || ''}</span>
                  </div>
                );
              }) : (
                <div className="text-center py-8 text-[#555]">
                  <Activity className="size-6 mx-auto mb-2 opacity-50" />
                  <p className="text-xs">No request logs yet</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Add Webhook Modal */}
      {showAddWebhook && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-2xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-[#FF6B00]/20">
              <h3 className="text-sm font-medium text-[#1A1A2E]">Add Webhook</h3>
              <button onClick={() => setShowAddWebhook(false)} className="text-[#555] hover:text-[#555]">
                <X className="size-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-[10px] text-[#5a5a72] mb-1.5 tracking-wider">WEBHOOK URL</label>
                <input
                  type="url"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  placeholder="https://your-server.com/webhook"
                  data-testid="webhook-url-input"
                  className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
                />
              </div>
              <div>
                <label className="block text-[10px] text-[#5a5a72] mb-2 tracking-wider">EVENTS</label>
                <div className="flex flex-wrap gap-2">
                  {['message.received', 'contact.created', 'deal.updated', 'invoice.paid'].map(event => (
                    <button
                      key={event}
                      onClick={() => setWebhookEvents(prev =>
                        prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event]
                      )}
                      className={`px-3 py-1.5 text-[10px] rounded-lg border transition-all ${
                        webhookEvents.includes(event)
                          ? 'bg-[#D4AF37]/10 border-[#D4AF37]/30 text-[#D4AF37]'
                          : 'border-[#FF6B00]/15 text-[#666] hover:text-[#555]'
                      }`}
                    >
                      {event}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3 p-5 border-t border-[#FF6B00]/20">
              <button
                onClick={() => setShowAddWebhook(false)}
                className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#FF6B00]/15 rounded-lg hover:bg-white/50"
              >
                Cancel
              </button>
              <button
                disabled={!webhookUrl.trim()}
                data-testid="webhook-submit-btn"
                className="flex-1 px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 disabled:opacity-50"
              >
                Create Webhook
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
