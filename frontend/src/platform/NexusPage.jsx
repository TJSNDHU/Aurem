import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Mail, Phone, Send, MessageCircle, Mic, CreditCard, Search,
  Cloud, Image, Box, Volume2, Brain, Cpu, DollarSign, Github,
  CheckCircle, XCircle, Loader2, Shield, Zap, X, Eye, EyeOff, Link2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ICONS = {
  mail: Mail, phone: Phone, send: Send, 'message-circle': MessageCircle,
  mic: Mic, 'credit-card': CreditCard, search: Search, cloud: Cloud,
  image: Image, box: Box, 'volume-2': Volume2, brain: Brain,
  cpu: Cpu, 'dollar-sign': DollarSign, github: Github,
};

const CATEGORY_COLORS = {
  'Communication': '#22c55e',
  'Payments': '#f59e0b',
  'Voice': '#8b5cf6',
  'AI / ML': '#38bdf8',
  'Developer': '#6366f1',
  'Search': '#14b8a6',
  'Media': '#ec4899',
  'Data': '#f97316',
};

const NexusPage = ({ token }) => {
  const [connectors, setConnectors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeModal, setActiveModal] = useState(null);
  const [formData, setFormData] = useState({});
  const [showValues, setShowValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('all');

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchConnectors = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/nexus/connectors`, { headers });
      if (res.ok) {
        const data = await res.json();
        setConnectors(data.connectors || []);
      }
    } catch (e) {
      console.error('Failed to load connectors:', e);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { fetchConnectors(); }, [fetchConnectors]);

  const handleConnect = async (connector) => {
    if (connector.method === 'oauth') {
      try {
        const res = await fetch(`${API_URL}/api/nexus/oauth/${connector.id}/initiate`, { headers });
        if (res.ok) {
          const data = await res.json();
          window.open(data.auth_url, '_blank', 'width=600,height=700');
        } else {
          const err = await res.json();
          setActiveModal({ ...connector, oauthError: err.detail });
        }
      } catch {
        setActiveModal({ ...connector, oauthError: 'Failed to initiate OAuth' });
      }
    } else {
      setFormData({});
      setActiveModal(connector);
    }
  };

  const handleSaveKey = async () => {
    if (!activeModal) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/nexus/connect/key`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ connector_id: activeModal.id, credentials: formData }),
      });
      if (res.ok) {
        setActiveModal(null);
        setFormData({});
        fetchConnectors();
      }
    } catch (e) {
      console.error('Save failed:', e);
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async (connectorId) => {
    try {
      await fetch(`${API_URL}/api/nexus/disconnect/${connectorId}`, { method: 'DELETE', headers });
      fetchConnectors();
    } catch (e) {
      console.error('Disconnect failed:', e);
    }
  };

  const categories = [...new Set(connectors.map(c => c.category))];
  const filtered = filter === 'all' ? connectors
    : filter === 'connected' ? connectors.filter(c => c.status === 'connected')
    : connectors.filter(c => c.category === filter);

  const connectedCount = connectors.filter(c => c.status === 'connected').length;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ background: '#080c10' }}>
        <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 2, repeat: Infinity }}>
          <Link2 className="size-8 text-emerald-500 mx-auto mb-3" />
          <p className="text-xs text-gray-500 tracking-[3px] uppercase">Loading Nexus</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto" style={{ background: '#080c10' }} data-testid="nexus-page">
      <div className="p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between" data-testid="nexus-header">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #059669, #10b981)', boxShadow: '0 0 24px rgba(16,185,129,0.3)' }}>
              <Zap className="size-4 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-wide">NEXUS</h1>
              <p className="text-[10px] text-gray-500 tracking-[2px] uppercase">Integration Hub, Connect Your Stack</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="px-3 py-1.5 rounded-lg" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.15)' }}>
              <span className="text-xs text-emerald-400 font-mono" data-testid="connected-count">{connectedCount}/{connectors.length} Connected</span>
            </div>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap" data-testid="nexus-filters">
          {['all', 'connected', ...categories].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase transition-all ${
                filter === f
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-gray-500 hover:text-gray-300 border border-transparent'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Connector Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="connector-grid">
          {filtered.map((c, i) => {
            const Icon = ICONS[c.icon] || Zap;
            const catColor = CATEGORY_COLORS[c.category] || '#6b7280';
            const isConnected = c.status === 'connected';

            return (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                data-testid={`connector-card-${c.id}`}
              >
                <div
                  className="rounded-xl p-4 h-full flex flex-col"
                  style={{
                    background: isConnected ? 'rgba(16,185,129,0.04)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${isConnected ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.05)'}`,
                  }}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${catColor}15` }}>
                        <Icon className="size-4" style={{ color: catColor }} />
                      </div>
                      <div>
                        <div className="text-sm font-bold text-white">{c.name}</div>
                        <div className="text-[9px] font-bold tracking-wider uppercase" style={{ color: `${catColor}88` }}>{c.category}</div>
                      </div>
                    </div>
                    {isConnected ? (
                      <span className="flex items-center gap-1 text-[9px] font-bold text-emerald-400 px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(16,185,129,0.1)' }}>
                        <CheckCircle className="size-3" /> LIVE
                      </span>
                    ) : (
                      <span className="text-[9px] text-gray-600 px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(255,255,255,0.03)' }}>
                        {c.method === 'oauth' ? 'OAuth' : 'API Key'}
                      </span>
                    )}
                  </div>

                  <p className="text-[11px] text-gray-500 mb-4 flex-1">{c.description}</p>

                  {isConnected ? (
                    <div className="flex items-center gap-2">
                      <div className="flex-1 text-[9px] text-gray-600">
                        Connected {c.connected_at ? new Date(c.connected_at).toLocaleDateString() : ''}
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[10px] text-red-400 hover:text-red-300 hover:bg-red-500/10 h-7 px-2"
                        onClick={() => handleDisconnect(c.id)}
                        data-testid={`disconnect-${c.id}`}
                      >
                        <XCircle className="size-3 mr-1" /> Disconnect
                      </Button>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      className="w-full h-8 text-[11px] font-bold tracking-wider"
                      style={{ background: `${catColor}20`, color: catColor, border: `1px solid ${catColor}30` }}
                      onClick={() => handleConnect(c)}
                      data-testid={`connect-${c.id}`}
                    >
                      {c.method === 'oauth' ? (
                        <><Shield className="size-3 mr-1.5" /> Sync Account</>
                      ) : (
                        <><Zap className="size-3 mr-1.5" /> Add Key</>
                      )}
                    </Button>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Modal for API Key input / OAuth error */}
      <AnimatePresence>
        {activeModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
            onClick={() => setActiveModal(null)}
            data-testid="nexus-modal"
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="w-full max-w-md rounded-xl p-5"
              style={{ background: '#0f1318', border: '1px solid rgba(16,185,129,0.15)' }}
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Shield className="size-5 text-emerald-500" />
                  <h2 className="text-sm font-bold text-white">{activeModal.name}</h2>
                </div>
                <button onClick={() => setActiveModal(null)} className="text-gray-500 hover:text-white">
                  <X className="size-4" />
                </button>
              </div>

              {activeModal.oauthError ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-lg" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.15)' }}>
                    <p className="text-xs text-amber-400">{activeModal.oauthError}</p>
                  </div>
                  <p className="text-[10px] text-gray-500">
                    OAuth requires provider credentials (Client ID / Secret) to be configured in the server environment.
                    Contact your administrator to set this up.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-[10px] text-gray-500 mb-2">
                    Credentials are encrypted with AES-256-GCM before storage. Only you can access them.
                  </p>
                  {(activeModal.fields || ['api_key']).map(field => (
                    <div key={field}>
                      <label className="text-[10px] text-gray-400 font-bold tracking-wider uppercase mb-1 block">
                        {field.replace(/_/g, ' ')}
                      </label>
                      <div className="relative">
                        <Input
                          type={showValues[field] ? 'text' : 'password'}
                          placeholder={`Enter ${field.replace(/_/g, ' ')}...`}
                          value={formData[field] || ''}
                          onChange={e => setFormData(prev => ({ ...prev, [field]: e.target.value }))}
                          className="bg-transparent border-gray-700 text-white text-xs pr-8"
                          data-testid={`input-${field}`}
                        />
                        <button
                          type="button"
                          onClick={() => setShowValues(p => ({ ...p, [field]: !p[field] }))}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                        >
                          {showValues[field] ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                        </button>
                      </div>
                    </div>
                  ))}
                  <Button
                    className="w-full h-9 text-xs font-bold tracking-wider mt-2"
                    style={{ background: 'rgba(16,185,129,0.15)', color: '#22c55e', border: '1px solid rgba(16,185,129,0.3)' }}
                    onClick={handleSaveKey}
                    disabled={saving || Object.values(formData).every(v => !v)}
                    data-testid="save-key-btn"
                  >
                    {saving ? <Loader2 className="size-3 animate-spin mr-1.5" /> : <Shield className="size-3 mr-1.5" />}
                    {saving ? 'Encrypting...' : 'Encrypt & Store'}
                  </Button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default NexusPage;
