/**
 * AUREM API Keys Manager
 * Generate and manage integration API keys for external websites
 */

import React, { useState, useEffect } from 'react';
import { Key, Copy, Trash2, Plus, ExternalLink, CheckCircle, AlertCircle, Code } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const APIKeysManager = ({ token, user }) => {
  const [apiKeys, setApiKeys] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [newKey, setNewKey] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [error, setError] = useState(null);

  // Fetch existing API keys
  useEffect(() => {
    fetchApiKeys();
  }, []);

  const fetchApiKeys = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_URL}/api/integration/keys`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setApiKeys(data.keys || []);
      } else {
        throw new Error('Failed to fetch API keys');
      }
    } catch (err) {
      console.error('Fetch keys error:', err);
      setError('Failed to load API keys');
    } finally {
      setIsLoading(false);
    }
  };

  // Generate new API key
  const handleGenerateKey = async () => {
    try {
      setIsGenerating(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/api/integration/keys`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setNewKey(data);
        fetchApiKeys(); // Refresh list
      } else {
        throw new Error('Failed to generate API key');
      }
    } catch (err) {
      console.error('Generate key error:', err);
      setError('Failed to generate API key');
    } finally {
      setIsGenerating(false);
    }
  };

  // Revoke API key
  const handleRevokeKey = async (keyId) => {
    if (!window.confirm('Are you sure? This will break any websites using this key.')) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/integration/keys/${keyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        fetchApiKeys(); // Refresh list
      } else {
        throw new Error('Failed to revoke key');
      }
    } catch (err) {
      console.error('Revoke key error:', err);
      setError('Failed to revoke API key');
    }
  };

  // Copy to clipboard
  const copyToClipboard = (text, type = 'key') => {
    navigator.clipboard.writeText(text);
    if (type === 'key') {
      setCopiedKey(text);
      setTimeout(() => setCopiedKey(null), 2000);
    } else {
      setCopiedSnippet(true);
      setTimeout(() => setCopiedSnippet(false), 2000);
    }
  };

  // Generate HTML snippet
  const generateSnippet = (apiKey) => {
    return `<!-- AUREM AI Chat Widget -->
<script src="${API_URL}/static/aurem-widget.js"></script>
<script>
  AUREM.init({
    apiKey: '${apiKey}',
    businessId: '${apiKey.split('_')[2]}' // Auto-extracted from key
  });
</script>`;
  };

  // Mask API key for display
  const maskKey = (key) => {
    if (!key) return '';
    const parts = key.split('_');
    if (parts.length >= 3) {
      return `${parts[0]}_${parts[1]}_${'•'.repeat(20)}${parts[2].slice(-4)}`;
    }
    return key;
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#050505]">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-[#666]">Loading API keys...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#050505] p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-light text-[#F4F4F4] tracking-wider mb-2">API Keys</h1>
          <p className="text-sm text-[#666]">
            Generate API keys to integrate AUREM chat widget into your external websites
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-red-400">{error}</p>
            </div>
          </div>
        )}

        {/* New Key Alert (shows after generation) */}
        {newKey && (
          <div className="mb-6 p-6 bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded-lg">
            <div className="flex items-start gap-3 mb-4">
              <CheckCircle className="w-5 h-5 text-[#D4AF37] flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-medium text-[#D4AF37] mb-1">API Key Generated Successfully!</h3>
                <p className="text-xs text-[#888]">
                  Copy this key now — it won't be shown again for security reasons.
                </p>
              </div>
            </div>
            
            <div className="bg-[#0A0A0A] p-4 rounded border border-[#1A1A1A] mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[#666] uppercase tracking-wider">Your API Key</span>
                <button
                  onClick={() => copyToClipboard(newKey.api_key, 'key')}
                  className="flex items-center gap-2 px-3 py-1 text-xs text-[#D4AF37] hover:bg-[#D4AF37]/10 rounded transition-all"
                >
                  {copiedKey === newKey.api_key ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  {copiedKey === newKey.api_key ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <code className="text-sm text-[#D4AF37] font-mono break-all">{newKey.api_key}</code>
            </div>

            <div className="bg-[#0A0A0A] p-4 rounded border border-[#1A1A1A]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[#666] uppercase tracking-wider">Embed Code</span>
                <button
                  onClick={() => copyToClipboard(generateSnippet(newKey.api_key), 'snippet')}
                  className="flex items-center gap-2 px-3 py-1 text-xs text-[#D4AF37] hover:bg-[#D4AF37]/10 rounded transition-all"
                >
                  {copiedSnippet ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  {copiedSnippet ? 'Copied!' : 'Copy Code'}
                </button>
              </div>
              <pre className="text-xs text-[#888] font-mono overflow-x-auto">
                {generateSnippet(newKey.api_key)}
              </pre>
            </div>

            <button
              onClick={() => setNewKey(null)}
              className="mt-4 text-xs text-[#666] hover:text-[#D4AF37] transition-all"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Generate Button */}
        <div className="mb-8">
          <button
            onClick={handleGenerateKey}
            disabled={isGenerating}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded-lg font-medium hover:opacity-90 transition-all disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            {isGenerating ? 'Generating...' : 'Generate New API Key'}
          </button>
        </div>

        {/* Existing Keys List */}
        <div>
          <h2 className="text-sm font-medium text-[#F4F4F4] mb-4 uppercase tracking-wider">Your API Keys</h2>
          
          {apiKeys.length === 0 ? (
            <div className="p-12 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
              <Key className="w-12 h-12 text-[#333] mx-auto mb-4" />
              <p className="text-sm text-[#666] mb-2">No API keys yet</p>
              <p className="text-xs text-[#555]">Generate your first API key to start integrating AUREM</p>
            </div>
          ) : (
            <div className="space-y-3">
              {apiKeys.map((key) => (
                <div
                  key={key.key_id}
                  className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg flex items-center justify-between hover:border-[#252525] transition-all"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Key className="w-4 h-4 text-[#D4AF37]" />
                      <code className="text-sm text-[#888] font-mono">{maskKey(key.key_preview)}</code>
                      {key.active ? (
                        <span className="px-2 py-0.5 text-[9px] bg-green-500/10 text-green-400 border border-green-500/30 rounded uppercase tracking-wider">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-[9px] bg-red-500/10 text-red-400 border border-red-500/30 rounded uppercase tracking-wider">
                          Revoked
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[#555]">
                      <span>Created: {new Date(key.created_at).toLocaleDateString()}</span>
                      {key.last_used && <span>Last used: {new Date(key.last_used).toLocaleDateString()}</span>}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => copyToClipboard(generateSnippet(key.key_preview), 'snippet')}
                      className="p-2 text-[#666] hover:text-[#D4AF37] hover:bg-[#151515] rounded transition-all"
                      title="Copy embed code"
                    >
                      <Code className="w-4 h-4" />
                    </button>
                    {key.active && (
                      <button
                        onClick={() => handleRevokeKey(key.key_id)}
                        className="p-2 text-[#666] hover:text-red-400 hover:bg-[#151515] rounded transition-all"
                        title="Revoke key"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Documentation */}
        <div className="mt-8 p-6 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
          <div className="flex items-start gap-3 mb-4">
            <ExternalLink className="w-5 h-5 text-[#D4AF37] flex-shrink-0" />
            <div>
              <h3 className="text-sm font-medium text-[#F4F4F4] mb-2">How to Use</h3>
              <ol className="text-xs text-[#888] space-y-2 list-decimal list-inside">
                <li>Click "Generate New API Key" above</li>
                <li>Copy the embed code snippet</li>
                <li>Paste it before the closing <code className="text-[#D4AF37]">&lt;/body&gt;</code> tag on your website</li>
                <li>The AUREM chat widget will appear on your site automatically</li>
              </ol>
            </div>
          </div>
          
          <div className="mt-4 p-3 bg-[#050505] rounded border border-[#1A1A1A]">
            <p className="text-xs text-[#666]">
              💡 <strong className="text-[#888]">Tip:</strong> You can customize the widget appearance by passing additional options to <code className="text-[#D4AF37]">AUREM.init()</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default APIKeysManager;
