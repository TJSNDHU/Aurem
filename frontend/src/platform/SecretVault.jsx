/**
 * AUREM Secret Vault Dashboard
 * BYON (Bring Your Own Network) — Encrypted secret management for tenant API keys
 * AES-256 vault-level encryption for Twilio, WhatsApp, Stripe, Coinbase, and custom API keys
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield, Key, Lock, Unlock, Eye, EyeOff, Copy, Check,
  Plus, Trash2, RefreshCw, AlertCircle, CheckCircle,
  Search, Settings, X, ArrowRight, ChevronRight, Database
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const SECRET_TYPES = [
  {
    id: 'stripe',
    name: 'Stripe',
    description: 'Payment processing API keys',
    fields: [
      { key: 'publishable_key', label: 'Publishable Key', prefix: 'pk_' },
      { key: 'secret_key', label: 'Secret Key', prefix: 'sk_', sensitive: true },
      { key: 'webhook_secret', label: 'Webhook Secret', prefix: 'whsec_', sensitive: true }
    ],
    color: '#635BFF',
    logo: 'ST'
  },
  {
    id: 'twilio',
    name: 'Twilio',
    description: 'SMS and voice communication',
    fields: [
      { key: 'account_sid', label: 'Account SID', prefix: 'AC' },
      { key: 'auth_token', label: 'Auth Token', sensitive: true },
      { key: 'phone_number', label: 'Phone Number', prefix: '+' }
    ],
    color: '#F22F46',
    logo: 'TW'
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp Business',
    description: 'WhatsApp Business API credentials',
    fields: [
      { key: 'phone_number_id', label: 'Phone Number ID' },
      { key: 'access_token', label: 'Access Token', sensitive: true },
      { key: 'verify_token', label: 'Verify Token', sensitive: true }
    ],
    color: '#25D366',
    logo: 'WA'
  },
  {
    id: 'apollo',
    name: 'Apollo.io',
    description: 'Lead enrichment & contact intelligence',
    fields: [
      { key: 'api_key', label: 'API Key', sensitive: true }
    ],
    color: '#6C5CE7',
    logo: 'AP'
  },
  {
    id: 'hubspot',
    name: 'HubSpot',
    description: 'CRM — contacts, deals, and pipeline sync',
    fields: [
      { key: 'access_token', label: 'Private App Access Token', prefix: 'pat-', sensitive: true }
    ],
    color: '#FF7A59',
    logo: 'HS'
  },
  {
    id: 'salesforce',
    name: 'Salesforce',
    description: 'CRM — enterprise contacts and opportunity sync',
    fields: [
      { key: 'access_token', label: 'Access Token', sensitive: true },
      { key: 'instance_url', label: 'Instance URL', prefix: 'https://' }
    ],
    color: '#00A1E0',
    logo: 'SF'
  },
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT and ORA model access',
    fields: [
      { key: 'api_key', label: 'API Key', prefix: 'sk-', sensitive: true },
      { key: 'organization_id', label: 'Organization ID', prefix: 'org-' }
    ],
    color: '#10A37F',
    logo: 'AI'
  },
  {
    id: 'custom',
    name: 'Custom API',
    description: 'Any third-party API credentials',
    fields: [
      { key: 'api_key', label: 'API Key', sensitive: true },
      { key: 'api_secret', label: 'API Secret', sensitive: true },
      { key: 'base_url', label: 'Base URL' }
    ],
    color: '#888',
    logo: 'AP'
  }
];

export default function SecretVault({ token }) {
  const [secrets, setSecrets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedType, setSelectedType] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [secretName, setSecretName] = useState('');
  const [saving, setSaving] = useState(false);
  const [revealedSecrets, setRevealedSecrets] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [copied, setCopied] = useState(null);
  const [activeTab, setActiveTab] = useState('secrets');
  const [auditLog, setAuditLog] = useState([]);
  const [auditSummary, setAuditSummary] = useState(null);
  const [rotateTarget, setRotateTarget] = useState(null);
  const [rotateValues, setRotateValues] = useState({});
  const [rotating, setRotating] = useState(false);

  const fetchSecrets = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/vault/secrets`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSecrets(data.secrets || []);
      }
    } catch {
      setSecrets([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSecrets();
  }, [fetchSecrets]);

  const fetchAuditLog = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/vault/audit?limit=100`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAuditLog(data.entries || []);
      }
    } catch { setAuditLog([]); }
  }, [token]);

  const fetchAuditSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/vault/audit/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) setAuditSummary(await res.json());
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAuditLog();
      fetchAuditSummary();
    }
  }, [activeTab, fetchAuditLog, fetchAuditSummary]);

  const handleRotateSecret = async () => {
    if (!rotateTarget) return;
    setRotating(true);
    try {
      const res = await fetch(`${API_URL}/api/vault/secrets/${rotateTarget.id}/rotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ credentials: rotateValues })
      });
      if (res.ok) {
        setRotateTarget(null);
        setRotateValues({});
        fetchSecrets();
      }
    } catch (err) {
      console.error('Rotate failed:', err);
    } finally {
      setRotating(false);
    }
  };

  const handleSaveSecret = async () => {
    if (!selectedType || !secretName.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/vault/secrets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: secretName,
          provider: selectedType.id,
          credentials: formValues
        })
      });
      if (res.ok) {
        setShowAddModal(false);
        setSelectedType(null);
        setFormValues({});
        setSecretName('');
        fetchSecrets();
      }
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSecret = async (secretId) => {
    try {
      await fetch(`${API_URL}/api/vault/secrets/${secretId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      fetchSecrets();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleRevealSecret = async (secretId) => {
    if (revealedSecrets[secretId]) {
      setRevealedSecrets(prev => { const next = {...prev}; delete next[secretId]; return next; });
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/vault/secrets/${secretId}/reveal`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRevealedSecrets(prev => ({ ...prev, [secretId]: data.credentials }));
        setTimeout(() => {
          setRevealedSecrets(prev => { const next = {...prev}; delete next[secretId]; return next; });
        }, 30000);
      }
    } catch {
      console.error('Reveal failed');
    }
  };

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const filteredSecrets = secrets.filter(s =>
    !searchQuery ||
    s.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.provider?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getTypeConfig = (provider) => SECRET_TYPES.find(t => t.id === provider) || SECRET_TYPES[SECRET_TYPES.length - 1];

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="secret-vault-loading">
        <div className="flex items-center gap-3 text-[#666]">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading vault...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="secret-vault">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">Secret Vault</h1>
            <p className="text-xs text-[#5a5a72]">BYON Compliance — AES-256 encrypted storage for your API keys and credentials</p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            data-testid="add-secret-btn"
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] text-xs font-semibold hover:opacity-90 transition-opacity"
          >
            <Plus className="w-3.5 h-3.5" />
            Store Secret
          </button>
        </div>

        {/* Tabs: Secrets / Audit Log */}
        <div className="flex items-center gap-1 mb-6 p-1 bg-white/40 backdrop-blur-sm rounded-lg w-fit border border-[#FF6B00]/10">
          {[
            { id: 'secrets', label: 'Secrets', icon: Key },
            { id: 'audit', label: 'Audit Log', icon: Shield },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`tab-${tab.id}`}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-[#D4AF37]/15 text-[#D4AF37] border border-[#D4AF37]/20'
                  : 'text-[#888] hover:text-[#555]'
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Security Banner */}
        {activeTab === 'secrets' && (
        <>
        <div className="flex items-center gap-4 p-4 bg-white/80 backdrop-blur-sm border border-[#4ade80]/20 rounded-xl mb-8">
          <div className="w-10 h-10 rounded-lg bg-[#4ade80]/10 flex items-center justify-center flex-shrink-0">
            <Shield className="w-5 h-5 text-[#4ade80]" />
          </div>
          <div className="flex-1">
            <h3 className="text-xs font-medium text-[#4ade80]">Vault-Level Security</h3>
            <p className="text-[10px] text-[#5a5a72] mt-0.5">All credentials are encrypted with AES-256-GCM before storage. Secrets are only decrypted on reveal with automatic 30s timeout.</p>
          </div>
          <div className="flex items-center gap-3 text-[10px]">
            <div className="flex items-center gap-1 text-[#4ade80]">
              <Lock className="w-3 h-3" />
              <span>AES-256</span>
            </div>
            <div className="flex items-center gap-1 text-[#4ade80]">
              <Shield className="w-3 h-3" />
              <span>At Rest</span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'STORED SECRETS', value: secrets.length, icon: Key, color: '#D4AF37' },
            { label: 'PROVIDERS', value: [...new Set(secrets.map(s => s.provider))].length, icon: Database, color: '#4ade80' },
            { label: 'ENCRYPTION', value: 'AES-256', icon: Lock, color: '#4ade80' }
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

        {/* Search */}
        <div className="relative mb-6">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#555]" />
          <input
            type="text"
            placeholder="Search secrets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            data-testid="vault-search-input"
            className="w-full pl-10 pr-4 py-2.5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
          />
        </div>

        {/* Secrets List */}
        {filteredSecrets.length > 0 ? (
          <div className="space-y-3">
            {filteredSecrets.map(secret => {
              const typeConfig = getTypeConfig(secret.provider);
              const isRevealed = !!revealedSecrets[secret.id];
              return (
                <div
                  key={secret.id}
                  data-testid={`secret-${secret.id}`}
                  className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl hover:border-[#D4AF37]/20 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold"
                        style={{ backgroundColor: `${typeConfig.color}15`, color: typeConfig.color }}
                      >
                        {typeConfig.logo}
                      </div>
                      <div>
                        <h3 className="text-sm font-medium text-[#1A1A2E]">{secret.name}</h3>
                        <p className="text-[10px] text-[#5a5a72]">{typeConfig.name} - Added {secret.created_at ? new Date(secret.created_at).toLocaleDateString() : 'recently'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 px-2 py-0.5 text-[10px] bg-[#4ade80]/10 text-[#4ade80] rounded-full">
                        <Lock className="w-3 h-3" />
                        Encrypted
                      </div>
                    </div>
                  </div>

                  {/* Credential Fields */}
                  <div className="space-y-2 mb-4">
                    {typeConfig.fields.map(field => {
                      const revealedValue = isRevealed ? revealedSecrets[secret.id]?.[field.key] : null;
                      return (
                        <div key={field.key} className="flex items-center justify-between p-2.5 bg-white/60 rounded-lg">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-[#555] w-28">{field.label}</span>
                            <code className="text-xs font-mono text-[#888]">
                              {revealedValue || (secret.masked?.[field.key] || '••••••••••••')}
                            </code>
                          </div>
                          {revealedValue && (
                            <button
                              onClick={() => copyToClipboard(revealedValue, `${secret.id}-${field.key}`)}
                              className="text-[#555] hover:text-[#D4AF37] transition-colors"
                            >
                              {copied === `${secret.id}-${field.key}` ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleRevealSecret(secret.id)}
                      data-testid={`reveal-${secret.id}`}
                      className={`flex items-center gap-1.5 px-3 py-2 text-[11px] rounded-lg border transition-colors ${
                        isRevealed
                          ? 'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/20'
                          : 'text-[#D4AF37] bg-[#D4AF37]/10 border-[#D4AF37]/20 hover:bg-[#D4AF37]/20'
                      }`}
                    >
                      {isRevealed ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                      {isRevealed ? 'Hide (30s auto-lock)' : 'Reveal'}
                    </button>
                    <button
                      onClick={() => { setRotateTarget(secret); setRotateValues({}); }}
                      data-testid={`rotate-${secret.id}`}
                      className="flex items-center gap-1.5 px-3 py-2 text-[11px] text-[#6C5CE7] bg-[#6C5CE7]/10 border border-[#6C5CE7]/20 rounded-lg hover:bg-[#6C5CE7]/20 transition-colors"
                    >
                      <RefreshCw className="w-3 h-3" />
                      Rotate
                    </button>
                    <button
                      onClick={() => handleDeleteSecret(secret.id)}
                      className="flex items-center gap-1.5 px-3 py-2 text-[11px] text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg hover:bg-[#ef4444]/20 transition-colors"
                    >
                      <Trash2 className="w-3 h-3" />
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="p-16 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl text-center">
            <Key className="w-10 h-10 text-[#333] mx-auto mb-4" />
            <h3 className="text-sm font-medium text-[#1A1A2E] mb-2">Vault is empty</h3>
            <p className="text-[11px] text-[#5a5a72] mb-6">Store your first API credentials securely</p>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity"
            >
              Store First Secret
            </button>
          </div>
        )}
        </>
        )}

        {/* ═══ AUDIT LOG TAB ═══ */}
        {activeTab === 'audit' && (
          <div className="space-y-6">
            {/* Audit Summary Cards */}
            {auditSummary && (
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: 'TOTAL EVENTS', value: auditSummary.total_events || 0, color: '#D4AF37' },
                  { label: 'REVEALS', value: auditSummary.action_stats?.reveal?.count || 0, color: '#f59e0b' },
                  { label: 'ROTATIONS', value: auditSummary.action_stats?.rotate?.count || 0, color: '#6C5CE7' },
                  { label: 'DELETIONS', value: auditSummary.action_stats?.delete?.count || 0, color: '#ef4444' },
                ].map((stat, idx) => (
                  <div key={idx} className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg">
                    <div className="text-[9px] text-[#555] tracking-wider mb-2">{stat.label}</div>
                    <div className="text-2xl font-semibold font-mono" style={{ color: stat.color }}>{stat.value}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Rotation Health */}
            {auditSummary?.rotation_info?.length > 0 && (
              <div className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
                <h3 className="text-xs font-medium text-[#1A1A2E] mb-3 flex items-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 text-[#6C5CE7]" />
                  Key Rotation Health
                </h3>
                <div className="space-y-2">
                  {auditSummary.rotation_info.map((item, idx) => {
                    const daysSinceRotation = item.last_rotated_at
                      ? Math.floor((Date.now() - new Date(item.last_rotated_at).getTime()) / 86400000)
                      : null;
                    const daysSinceCreation = item.created_at
                      ? Math.floor((Date.now() - new Date(item.created_at).getTime()) / 86400000)
                      : 0;
                    const isStale = daysSinceRotation === null ? daysSinceCreation > 30 : daysSinceRotation > 30;

                    return (
                      <div key={idx} className="flex items-center justify-between p-2.5 bg-white/60 rounded-lg">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ background: isStale ? '#ef4444' : '#4ade80' }} />
                          <span className="text-xs text-[#1A1A2E]">{item.name}</span>
                          <span className="text-[10px] text-[#888]">({item.provider})</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-[#6C5CE7]">{item.rotation_count || 0} rotations</span>
                          <span className={`text-[10px] ${isStale ? 'text-[#ef4444]' : 'text-[#4ade80]'}`}>
                            {item.last_rotated_at
                              ? `Last: ${daysSinceRotation}d ago`
                              : `Created ${daysSinceCreation}d ago — never rotated`
                            }
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Audit Trail */}
            <div className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
              <h3 className="text-xs font-medium text-[#1A1A2E] mb-3 flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-[#D4AF37]" />
                Audit Trail
              </h3>
              {auditLog.length > 0 ? (
                <div className="space-y-1 max-h-80 overflow-y-auto">
                  {auditLog.map((entry, idx) => {
                    const actionColors = { reveal: '#f59e0b', rotate: '#6C5CE7', delete: '#ef4444', store: '#4ade80' };
                    return (
                      <div key={idx} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/40 transition-colors">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ background: actionColors[entry.action] || '#888' }}
                          />
                          <span className="text-xs font-medium uppercase" style={{ color: actionColors[entry.action] || '#888' }}>
                            {entry.action}
                          </span>
                          <span className="text-[10px] text-[#555]">
                            Secret: {entry.secret_id}
                          </span>
                        </div>
                        <span className="text-[10px] text-[#888]">
                          {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '—'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-[#888] text-center py-8">No audit events yet</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Rotate Secret Modal */}
      {rotateTarget && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
          <div className="bg-white/80 backdrop-blur-sm border border-[#6C5CE7]/20 rounded-2xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-[#6C5CE7]/20">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-[#6C5CE7]" />
                <h3 className="text-sm font-medium text-[#1A1A2E]">Rotate: {rotateTarget.name}</h3>
              </div>
              <button onClick={() => { setRotateTarget(null); setRotateValues({}); }} className="text-[#555] hover:text-[#1A1A2E]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="flex items-start gap-2 p-3 bg-[#6C5CE7]/5 border border-[#6C5CE7]/10 rounded-lg">
                <AlertCircle className="w-4 h-4 text-[#6C5CE7] mt-0.5 flex-shrink-0" />
                <p className="text-[10px] text-[#888] leading-relaxed">
                  Enter new credentials to replace the current values. Old credentials will be permanently overwritten.
                </p>
              </div>
              {(() => {
                const typeConfig = getTypeConfig(rotateTarget.provider);
                return typeConfig.fields.map(field => (
                  <div key={field.key}>
                    <label className="block text-[10px] text-[#5a5a72] mb-1.5 tracking-wider">{field.label.toUpperCase()}</label>
                    <input
                      type={field.sensitive ? 'password' : 'text'}
                      value={rotateValues[field.key] || ''}
                      onChange={(e) => setRotateValues({ ...rotateValues, [field.key]: e.target.value })}
                      placeholder={`New ${field.label}`}
                      data-testid={`rotate-input-${field.key}`}
                      className="w-full px-3 py-2.5 bg-white/50 border border-[#6C5CE7]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#6C5CE7]/50 font-mono"
                    />
                  </div>
                ));
              })()}
            </div>
            <div className="flex gap-3 p-5 border-t border-[#6C5CE7]/20">
              <button
                onClick={() => { setRotateTarget(null); setRotateValues({}); }}
                className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#FF6B00]/15 rounded-lg hover:bg-white/50"
              >
                Cancel
              </button>
              <button
                onClick={handleRotateSecret}
                disabled={rotating || Object.values(rotateValues).every(v => !v)}
                data-testid="confirm-rotate-btn"
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold text-white bg-[#6C5CE7] rounded-lg hover:opacity-90 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${rotating ? 'animate-spin' : ''}`} />
                {rotating ? 'Rotating...' : 'Rotate Keys'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Secret Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-2xl w-full max-w-lg overflow-hidden max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-[#FF6B00]/20">
              <h3 className="text-sm font-medium text-[#1A1A2E]">
                {selectedType ? `Store ${selectedType.name} Credentials` : 'Choose Provider'}
              </h3>
              <button onClick={() => { setShowAddModal(false); setSelectedType(null); setFormValues({}); setSecretName(''); }} className="text-[#555] hover:text-[#555]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-5">
              {!selectedType ? (
                <div className="grid grid-cols-2 gap-3">
                  {SECRET_TYPES.map(type => (
                    <button
                      key={type.id}
                      onClick={() => setSelectedType(type)}
                      data-testid={`select-provider-${type.id}`}
                      className="flex items-center gap-3 p-4 bg-white/50 border border-[#FF6B00]/15 rounded-xl hover:border-[#D4AF37]/30 transition-colors text-left"
                    >
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold"
                        style={{ backgroundColor: `${type.color}15`, color: type.color }}
                      >
                        {type.logo}
                      </div>
                      <div>
                        <p className="text-xs font-medium text-[#1A1A2E]">{type.name}</p>
                        <p className="text-[10px] text-[#5a5a72]">{type.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="block text-[10px] text-[#5a5a72] mb-1.5 tracking-wider">SECRET NAME</label>
                    <input
                      type="text"
                      value={secretName}
                      onChange={(e) => setSecretName(e.target.value)}
                      placeholder={`My ${selectedType.name} Key`}
                      data-testid="secret-name-input"
                      className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50"
                    />
                  </div>
                  {selectedType.fields.map(field => (
                    <div key={field.key}>
                      <label className="block text-[10px] text-[#5a5a72] mb-1.5 tracking-wider">{field.label.toUpperCase()}</label>
                      <input
                        type={field.sensitive ? 'password' : 'text'}
                        value={formValues[field.key] || ''}
                        onChange={(e) => setFormValues({ ...formValues, [field.key]: e.target.value })}
                        placeholder={field.prefix ? `${field.prefix}...` : `Enter ${field.label}`}
                        data-testid={`input-${field.key}`}
                        className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50 font-mono"
                      />
                    </div>
                  ))}
                  <div className="flex items-start gap-2 p-3 bg-[#D4AF37]/5 border border-[#D4AF37]/10 rounded-lg">
                    <Shield className="w-4 h-4 text-[#D4AF37] mt-0.5 flex-shrink-0" />
                    <p className="text-[10px] text-[#888] leading-relaxed">
                      Credentials are encrypted with AES-256-GCM before storage. Only you can reveal them.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {selectedType && (
              <div className="flex gap-3 p-5 border-t border-[#FF6B00]/20">
                <button
                  onClick={() => { setSelectedType(null); setFormValues({}); setSecretName(''); }}
                  className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#FF6B00]/15 rounded-lg hover:bg-white/50"
                >
                  Back
                </button>
                <button
                  onClick={handleSaveSecret}
                  disabled={!secretName.trim() || saving}
                  data-testid="save-secret-btn"
                  className="flex-1 px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 disabled:opacity-50"
                >
                  {saving ? 'Encrypting...' : 'Store Securely'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
