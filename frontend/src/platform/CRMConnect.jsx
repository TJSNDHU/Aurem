/**
 * AUREM CRM Connect Dashboard
 * Manage CRM integrations, contact sync, and deal pipeline connections
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Globe, Users, Link2, Unlink, RefreshCw, CheckCircle, AlertCircle,
  ArrowUpRight, Database, BarChart3, Zap, Search, Filter,
  ChevronRight, Clock, Shield, Plus, Settings, X
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const CRM_PROVIDERS = [
  {
    id: 'salesforce',
    name: 'Salesforce',
    description: 'Enterprise CRM with full pipeline sync',
    color: '#00A1E0',
    features: ['Contacts', 'Deals', 'Activities', 'Reports'],
    logo: 'SF'
  },
  {
    id: 'hubspot',
    name: 'HubSpot',
    description: 'Marketing-first CRM with automation',
    color: '#FF7A59',
    features: ['Contacts', 'Deals', 'Email Tracking', 'Forms'],
    logo: 'HS'
  },
  {
    id: 'pipedrive',
    name: 'Pipedrive',
    description: 'Sales-focused CRM for deal tracking',
    color: '#017737',
    features: ['Contacts', 'Deals', 'Activities', 'Goals'],
    logo: 'PD'
  },
  {
    id: 'zoho',
    name: 'Zoho CRM',
    description: 'All-in-one business CRM suite',
    color: '#E42527',
    features: ['Contacts', 'Deals', 'Campaigns', 'Analytics'],
    logo: 'ZO'
  }
];

export default function CRMConnect({ token, user }) {
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncStats, setSyncStats] = useState(null);
  const [showSetup, setShowSetup] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [instanceUrl, setInstanceUrl] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [recentContacts, setRecentContacts] = useState([]);

  const fetchConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/crm/connections`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setConnections(data.connections || []);
        setSyncStats(data.stats || null);
      }
    } catch (err) {
      // Use default empty state
      setConnections([]);
      setSyncStats({
        total_contacts: 0,
        synced_today: 0,
        active_deals: 0,
        sync_health: 100
      });
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchRecentContacts = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/crm/contacts/recent`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRecentContacts(data.contacts || []);
      }
    } catch {
      setRecentContacts([]);
    }
  }, [token]);

  useEffect(() => {
    fetchConnections();
    fetchRecentContacts();
  }, [fetchConnections, fetchRecentContacts]);

  const handleConnect = async (providerId) => {
    if (!apiKey.trim()) return;
    setConnecting(true);
    try {
      const res = await fetch(`${API_URL}/api/crm/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          provider: providerId,
          api_key: apiKey,
          instance_url: instanceUrl || undefined
        })
      });
      if (res.ok) {
        setShowSetup(null);
        setApiKey('');
        setInstanceUrl('');
        fetchConnections();
      }
    } catch (err) {
      console.error('Connection failed:', err);
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async (providerId) => {
    try {
      await fetch(`${API_URL}/api/crm/disconnect/${providerId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      fetchConnections();
    } catch (err) {
      console.error('Disconnect failed:', err);
    }
  };

  const handleSync = async (providerId) => {
    setSyncing(providerId);
    try {
      const res = await fetch(`${API_URL}/api/crm/sync/${providerId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        fetchConnections();
      }
    } catch (err) {
      console.error('Sync failed:', err);
    } finally {
      setSyncing(null);
    }
  };

  const stats = syncStats || { total_contacts: 0, synced_today: 0, active_deals: 0, sync_health: 100 };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="crm-connect-loading">
        <div className="flex items-center gap-3 text-[#666]">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading CRM connections...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="crm-connect">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">CRM Connect</h1>
            <p className="text-xs text-[#5a5a72]">Sync contacts, deals, and activities across your CRM platforms</p>
          </div>
          <button
            onClick={() => setShowSetup(CRM_PROVIDERS[0])}
            data-testid="add-crm-btn"
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] text-xs font-semibold hover:opacity-90 transition-opacity"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Connection
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'TOTAL CONTACTS', value: stats.total_contacts.toLocaleString(), icon: Users, color: '#D4AF37' },
            { label: 'SYNCED TODAY', value: stats.synced_today.toLocaleString(), icon: RefreshCw, color: '#4ade80' },
            { label: 'ACTIVE DEALS', value: stats.active_deals.toLocaleString(), icon: BarChart3, color: '#D4AF37' },
            { label: 'SYNC HEALTH', value: `${stats.sync_health}%`, icon: Shield, color: stats.sync_health > 90 ? '#4ade80' : '#f59e0b' }
          ].map((stat, idx) => (
            <div key={idx} className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                <span className="text-[9px] text-[#555] tracking-wider">{stat.label}</span>
              </div>
              <div className="text-2xl font-semibold font-mono" style={{ color: stat.color }}>{stat.value}</div>
            </div>
          ))}
        </div>

        {/* CRM Providers */}
        <div className="mb-8">
          <h2 className="text-xs text-[#555] tracking-wider mb-4">AVAILABLE INTEGRATIONS</h2>
          <div className="grid grid-cols-2 gap-4">
            {CRM_PROVIDERS.map((provider) => {
              const isConnected = connections.some(c => c.provider === provider.id);
              return (
                <div
                  key={provider.id}
                  data-testid={`crm-provider-${provider.id}`}
                  className={`p-5 rounded-xl border transition-all ${
                    isConnected
                      ? 'bg-white/80 backdrop-blur-sm border-[#4ade80]/30'
                      : 'bg-white/80 backdrop-blur-sm border-[#FF6B00]/20 hover:border-[#D4AF37]/30'
                  }`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-11 h-11 rounded-lg flex items-center justify-center text-sm font-bold text-white"
                        style={{ backgroundColor: `${provider.color}30`, color: provider.color }}
                      >
                        {provider.logo}
                      </div>
                      <div>
                        <h3 className="text-sm font-medium text-[#1A1A2E]">{provider.name}</h3>
                        <p className="text-[11px] text-[#5a5a72] mt-0.5">{provider.description}</p>
                      </div>
                    </div>
                    {isConnected ? (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium bg-[#4ade80]/10 text-[#4ade80]">
                        <div className="w-1.5 h-1.5 bg-[#4ade80] rounded-full animate-pulse" />
                        Connected
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] text-[#5a5a72] bg-white/50 border border-[#FF6B00]/10">
                        <AlertCircle className="w-3 h-3" />
                        Not Connected
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {provider.features.map((f, i) => (
                      <span key={i} className="px-2 py-0.5 text-[9px] bg-white/50 text-[#888] rounded border border-[#FF6B00]/15">
                        {f}
                      </span>
                    ))}
                  </div>

                  <div className="flex gap-2">
                    {isConnected ? (
                      <>
                        <button
                          onClick={() => handleDisconnect(provider.id)}
                          className="flex items-center gap-1.5 px-3 py-2 text-[11px] text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg hover:bg-[#ef4444]/20 transition-colors"
                        >
                          <Unlink className="w-3 h-3" />
                          Disconnect
                        </button>
                        <button
                          onClick={() => handleSync(provider.id)}
                          data-testid={`sync-${provider.id}-btn`}
                          className="flex items-center gap-1.5 px-3 py-2 text-[11px] text-[#D4AF37] bg-[#D4AF37]/10 border border-[#D4AF37]/20 rounded-lg hover:bg-[#D4AF37]/20 transition-colors disabled:opacity-50"
                          disabled={syncing === provider.id}
                        >
                          <RefreshCw className={`w-3 h-3 ${syncing === provider.id ? 'animate-spin' : ''}`} />
                          {syncing === provider.id ? 'Syncing...' : 'Sync Now'}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setShowSetup(provider)}
                        className="flex items-center gap-1.5 px-4 py-2 text-[11px] text-[#050505] font-semibold bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity"
                      >
                        <Link2 className="w-3 h-3" />
                        Connect
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Contacts */}
        <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-[#FF6B00]/20">
            <h2 className="text-xs text-[#555] tracking-wider">RECENT SYNCED CONTACTS</h2>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[#555]" />
                <input
                  type="text"
                  placeholder="Search contacts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="crm-search-input"
                  className="pl-8 pr-3 py-1.5 bg-white/50 border border-[#FF6B00]/15 rounded text-[11px] text-[#1A1A2E] placeholder-[#555] outline-none w-48 focus:border-[#D4AF37]/50"
                />
              </div>
            </div>
          </div>
          {recentContacts.length > 0 ? (
            <div className="divide-y divide-[#1A1A1A]">
              {recentContacts
                .filter(c => !searchQuery || (c.name || '').toLowerCase().includes(searchQuery.toLowerCase()) || (c.company || '').toLowerCase().includes(searchQuery.toLowerCase()))
                .map((contact, idx) => (
                <div key={idx} className="flex items-center justify-between px-4 py-3 hover:bg-white/50 transition-colors" data-testid={`crm-contact-${idx}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-[#D4AF37]/10 flex items-center justify-center text-[10px] font-semibold text-[#D4AF37]">
                      {(contact.name || 'U')[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="text-xs text-[#1A1A2E] font-medium">{contact.name}</p>
                      <p className="text-[10px] text-[#5a5a72]">{contact.role ? `${contact.role} at ` : ''}{contact.company || contact.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {contact.score && (
                      <div className={`px-2 py-0.5 rounded-full text-[9px] font-medium ${
                        contact.score >= 80 ? 'bg-[#4ade80]/10 text-[#4ade80]' :
                        contact.score >= 60 ? 'bg-[#f59e0b]/10 text-[#f59e0b]' :
                        'bg-[#ef4444]/10 text-[#ef4444]'
                      }`}>
                        {contact.score}
                      </div>
                    )}
                    {contact.deal_value && (
                      <span className="text-[10px] text-[#D4AF37] font-mono">${(contact.deal_value / 1000).toFixed(0)}K</span>
                    )}
                    <span className="text-[10px] text-[#555] capitalize">{contact.source || 'Manual'}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-10 text-center">
              <Database className="w-8 h-8 text-[#333] mx-auto mb-3" />
              <p className="text-sm text-[#555]">No contacts synced yet</p>
              <p className="text-[11px] text-[#444] mt-1">Connect a CRM to start syncing contacts</p>
            </div>
          )}
        </div>
      </div>

      {/* Setup Modal */}
      {showSetup && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-2xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-[#FF6B00]/20">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold"
                  style={{ backgroundColor: `${showSetup.color}30`, color: showSetup.color }}
                >
                  {showSetup.logo}
                </div>
                <div>
                  <h3 className="text-sm font-medium text-[#1A1A2E]">Connect {showSetup.name}</h3>
                  <p className="text-[10px] text-[#5a5a72]">Enter your API credentials</p>
                </div>
              </div>
              <button
                onClick={() => { setShowSetup(null); setApiKey(''); setInstanceUrl(''); }}
                className="text-[#555] hover:text-[#555] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-[10px] text-[#5a5a72] mb-1.5 tracking-wider">API KEY</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={`Enter ${showSetup.name} API key`}
                  data-testid="crm-api-key-input"
                  className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
                />
              </div>
              {(showSetup.id === 'salesforce' || showSetup.id === 'zoho') && (
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1.5 tracking-wider">INSTANCE URL</label>
                  <input
                    type="url"
                    value={instanceUrl}
                    onChange={(e) => setInstanceUrl(e.target.value)}
                    placeholder="https://yourcompany.salesforce.com"
                    data-testid="crm-instance-url-input"
                    className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
                  />
                </div>
              )}
              <div className="flex items-start gap-2 p-3 bg-[#D4AF37]/5 border border-[#D4AF37]/10 rounded-lg">
                <Shield className="w-4 h-4 text-[#D4AF37] mt-0.5 flex-shrink-0" />
                <p className="text-[10px] text-[#888] leading-relaxed">
                  Your credentials are encrypted with AES-256 and stored securely. AUREM never stores plain-text secrets.
                </p>
              </div>
            </div>

            <div className="flex gap-3 p-5 border-t border-[#FF6B00]/20">
              <button
                onClick={() => { setShowSetup(null); setApiKey(''); setInstanceUrl(''); }}
                className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#FF6B00]/15 rounded-lg hover:bg-white/50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleConnect(showSetup.id)}
                disabled={!apiKey.trim() || connecting}
                data-testid="crm-connect-submit-btn"
                className="flex-1 px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {connecting ? 'Connecting...' : 'Connect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
