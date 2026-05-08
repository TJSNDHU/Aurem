/**
 * AUREM API Keys Settings
 * Add/edit/delete external API keys (Stripe, SendGrid, Twilio, Shopify, etc.)
 */
import React, { useState, useEffect, useCallback , useMemo } from 'react';
import {
  Key, Eye, EyeOff, Save, Trash2, RefreshCw, CheckCircle, AlertCircle, Edit2, X, Plus
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

export default function ApiKeysSettings({ token }) {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/settings/api-keys`, { headers });
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys || []);
      }
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleSave = async (keyName) => {
    if (!editValue.trim()) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/settings/api-keys`, {
        method: 'PUT', headers,
        body: JSON.stringify({ key_name: keyName, key_value: editValue.trim() }),
      });
      if (res.ok) {
        showMessage(`${keyName} saved successfully`);
        setEditing(null);
        setEditValue('');
        fetchKeys();
      } else {
        showMessage('Failed to save key', 'error');
      }
    } catch { showMessage('Network error', 'error'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (keyName) => {
    try {
      const res = await fetch(`${API_URL}/api/settings/api-keys/${keyName}`, {
        method: 'DELETE', headers,
      });
      if (res.ok) {
        showMessage(`${keyName} removed`);
        fetchKeys();
      }
    } catch { showMessage('Delete failed', 'error'); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" data-testid="api-keys-loading">
        <RefreshCw className="w-5 h-5 animate-spin text-[#888]" />
      </div>
    );
  }

  return (
    <div data-testid="api-keys-settings">
      <div className="flex items-center gap-3 mb-5">
        <Key className="w-5 h-5 text-[#FF6B00]" />
        <div>
          <h2 className="text-sm font-semibold text-white">API Keys</h2>
          <p className="text-[10px] text-[#888]">Connect external services by adding your API keys</p>
        </div>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 text-xs ${
          message.type === 'error' ? 'bg-red-500/10 text-red-400' : 'bg-[#4ade80]/10 text-[#4ade80]'
        }`}>
          {message.type === 'error' ? <AlertCircle className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
          {message.text}
        </div>
      )}

      <div className="space-y-2">
        {keys.map(k => (
          <div key={k.key} data-testid={`api-key-row-${k.key}`}
            className="flex items-center gap-3 p-3.5 border border-white/5 rounded-xl hover:border-white/10 transition-colors"
            style={{ background: 'rgba(255,255,255,0.02)' }}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-medium text-white">{k.label}</span>
                {k.configured ? (
                  <span className="px-1.5 py-0.5 text-[8px] font-bold bg-[#4ade80]/10 text-[#4ade80] rounded">SET</span>
                ) : (
                  <span className="px-1.5 py-0.5 text-[8px] font-bold bg-white/5 text-[#666] rounded">NOT SET</span>
                )}
              </div>
              {editing === k.key ? (
                <div className="flex items-center gap-2 mt-1.5">
                  <input
                    type="password"
                    value={editValue}
                    onChange={e => setEditValue(e.target.value)}
                    placeholder={`Enter ${k.label}${k.prefix ? ` (starts with ${k.prefix})` : ''}`}
                    className="flex-1 px-3 py-1.5 text-[11px] bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-[#555] focus:outline-none focus:border-[#FF6B00]/40"
                    data-testid={`api-key-input-${k.key}`}
                    autoFocus
                  />
                  <button onClick={() => handleSave(k.key)} disabled={saving}
                    data-testid={`api-key-save-${k.key}`}
                    className="p-1.5 text-[#4ade80] hover:bg-[#4ade80]/10 rounded-lg transition-colors disabled:opacity-50">
                    <Save className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => { setEditing(null); setEditValue(''); }}
                    className="p-1.5 text-[#888] hover:bg-white/5 rounded-lg transition-colors">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <span className="text-[10px] text-[#666] font-mono">{k.configured ? k.masked_value : 'Not configured'}</span>
              )}
            </div>
            {editing !== k.key && (
              <div className="flex items-center gap-1.5">
                <button onClick={() => { setEditing(k.key); setEditValue(''); }}
                  data-testid={`api-key-edit-${k.key}`}
                  className="p-1.5 text-[#888] hover:text-[#FF6B00] hover:bg-white/5 rounded-lg transition-colors">
                  {k.configured ? <Edit2 className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                </button>
                {k.configured && (
                  <button onClick={() => handleDelete(k.key)}
                    data-testid={`api-key-delete-${k.key}`}
                    className="p-1.5 text-[#888] hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
