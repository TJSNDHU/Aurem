/**
 * APIKeyManager.jsx
 * Admin dashboard for managing Reroots AI API keys
 * Create, view, and revoke API keys for external clients
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Key,
  Plus,
  Copy,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  Eye,
  EyeOff,
  Shield,
  Activity,
  Calendar,
  Users
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Tier badge colors
const TIER_COLORS = {
  starter: 'bg-gray-500',
  growth: 'bg-blue-500',
  enterprise: 'bg-purple-500',
  unlimited: 'bg-green-500'
};

// New key modal
const CreateKeyModal = ({ isOpen, onClose, onCreated }) => {
  const [clientName, setClientName] = useState('');
  const [brand, setBrand] = useState('reroots');
  const [tier, setTier] = useState('starter');
  const [customLimit, setCustomLimit] = useState('');
  const [expiryDays, setExpiryDays] = useState('365');
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState(null);
  
  const handleCreate = async () => {
    if (!clientName.trim()) {
      toast.error('Client name is required');
      return;
    }
    
    setCreating(true);
    const token = localStorage.getItem('reroots_token');
    
    try {
      const res = await fetch(`${API}/api/admin/api-keys/create`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          client_name: clientName,
          brand: brand,
          tier: tier,
          monthly_limit: customLimit ? parseInt(customLimit) : null,
          expires_in_days: parseInt(expiryDays)
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setNewKey(data.api_key);
        toast.success('API key created!');
        onCreated();
      } else {
        toast.error('Failed to create key');
      }
    } catch (error) {
      toast.error('Error creating key');
    } finally {
      setCreating(false);
    }
  };
  
  const handleCopyKey = () => {
    navigator.clipboard.writeText(newKey);
    toast.success('API key copied to clipboard!');
  };
  
  const handleClose = () => {
    setNewKey(null);
    setClientName('');
    setTier('starter');
    setCustomLimit('');
    onClose();
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl">
        {newKey ? (
          // Show the new key
          <div className="text-center space-y-4">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <Key className="h-8 w-8 text-green-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900">API Key Created!</h3>
            <p className="text-sm text-red-600 font-medium">
              Save this key now! It will not be shown again.
            </p>
            <div className="bg-gray-100 p-4 rounded-xl font-mono text-sm break-all">
              {newKey}
            </div>
            <div className="flex gap-3">
              <Button onClick={handleCopyKey} className="flex-1">
                <Copy className="h-4 w-4 mr-2" />
                Copy Key
              </Button>
              <Button variant="outline" onClick={handleClose}>
                Done
              </Button>
            </div>
          </div>
        ) : (
          // Create form
          <>
            <h3 className="text-xl font-semibold text-gray-900 mb-4">Create API Key</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Client Name *
                </label>
                <Input
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="Acme Corp"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Brand
                </label>
                <select
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="reroots">Reroots</option>
                  <option value="oroe">OROÉ</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tier
                </label>
                <select
                  value={tier}
                  onChange={(e) => setTier(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="starter">Starter (500/month)</option>
                  <option value="growth">Growth (2,000/month)</option>
                  <option value="enterprise">Enterprise (10,000/month)</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Custom Limit (optional)
                </label>
                <Input
                  type="number"
                  value={customLimit}
                  onChange={(e) => setCustomLimit(e.target.value)}
                  placeholder="Leave empty for tier default"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expires In (days)
                </label>
                <Input
                  type="number"
                  value={expiryDays}
                  onChange={(e) => setExpiryDays(e.target.value)}
                />
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={onClose} className="flex-1">
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={creating} className="flex-1">
                {creating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Key
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// API key row
const APIKeyRow = ({ apiKey, onRevoke }) => {
  const [revoking, setRevoking] = useState(false);
  
  const usagePercent = apiKey.monthly_limit > 0 
    ? (apiKey.used_this_month / apiKey.monthly_limit) * 100 
    : 0;
  
  const handleRevoke = async () => {
    if (!window.confirm(`Revoke key for ${apiKey.client_name}? This cannot be undone.`)) {
      return;
    }
    
    setRevoking(true);
    const token = localStorage.getItem('reroots_token');
    
    try {
      const res = await fetch(`${API}/api/admin/api-keys/${encodeURIComponent(apiKey.key_preview)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        toast.success('API key revoked');
        onRevoke();
      } else {
        toast.error('Failed to revoke key');
      }
    } catch (error) {
      toast.error('Error revoking key');
    } finally {
      setRevoking(false);
    }
  };
  
  return (
    <div className="p-4 bg-white border rounded-xl">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${apiKey.active ? 'bg-green-100' : 'bg-gray-100'}`}>
            <Key className={`h-5 w-5 ${apiKey.active ? 'text-green-600' : 'text-gray-400'}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-medium text-gray-900">{apiKey.client_name}</h4>
              <Badge className={`${TIER_COLORS[apiKey.tier]} text-white text-[10px]`}>
                {apiKey.tier}
              </Badge>
              {!apiKey.active && (
                <Badge variant="destructive" className="text-[10px]">Revoked</Badge>
              )}
            </div>
            <p className="text-xs text-gray-500 font-mono mt-0.5">{apiKey.key_preview}</p>
          </div>
        </div>
        
        {apiKey.active && (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleRevoke}
            disabled={revoking}
            className="text-red-500 hover:text-red-700 hover:bg-red-50"
          >
            {revoking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
          </Button>
        )}
      </div>
      
      {/* Usage bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>Usage this month</span>
          <span>{apiKey.used_this_month.toLocaleString()} / {apiKey.monthly_limit > 0 ? apiKey.monthly_limit.toLocaleString() : '∞'}</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all ${usagePercent > 90 ? 'bg-red-500' : usagePercent > 70 ? 'bg-yellow-500' : 'bg-green-500'}`}
            style={{ width: `${Math.min(usagePercent, 100)}%` }}
          />
        </div>
      </div>
      
      {/* Meta info */}
      <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          Expires: {new Date(apiKey.expires_at).toLocaleDateString()}
        </span>
        {apiKey.last_used_at && (
          <span className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            Last used: {new Date(apiKey.last_used_at).toLocaleDateString()}
          </span>
        )}
        <span className="flex items-center gap-1">
          <Users className="h-3 w-3" />
          Total: {apiKey.total_used?.toLocaleString() || 0}
        </span>
      </div>
    </div>
  );
};

export default function APIKeyManager() {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  
  // Fetch keys
  const fetchKeys = useCallback(async () => {
    const token = localStorage.getItem('reroots_token');
    if (!token) return;
    
    try {
      const res = await fetch(`${API}/api/admin/api-keys?include_inactive=${showInactive}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys || []);
      }
    } catch (error) {
      console.error('Failed to fetch keys:', error);
    } finally {
      setLoading(false);
    }
  }, [showInactive]);
  
  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);
  
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }
  
  const activeKeys = keys.filter(k => k.active);
  const totalUsage = keys.reduce((sum, k) => sum + (k.used_this_month || 0), 0);
  
  return (
    <div className="space-y-6" data-testid="api-key-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600">
            <Shield className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">API Key Manager</h2>
            <p className="text-sm text-gray-500">Control access to Reroots AI</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchKeys}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setShowCreate(true)} className="bg-amber-600 hover:bg-amber-700">
            <Plus className="h-4 w-4 mr-2" />
            Create Key
          </Button>
        </div>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-green-50 rounded-xl border border-green-200">
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5 text-green-600" />
            <span className="text-sm text-green-700">Active Keys</span>
          </div>
          <p className="text-2xl font-bold text-green-900 mt-1">{activeKeys.length}</p>
        </div>
        <div className="p-4 bg-blue-50 rounded-xl border border-blue-200">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-600" />
            <span className="text-sm text-blue-700">This Month</span>
          </div>
          <p className="text-2xl font-bold text-blue-900 mt-1">{totalUsage.toLocaleString()}</p>
        </div>
        <div className="p-4 bg-purple-50 rounded-xl border border-purple-200">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-purple-600" />
            <span className="text-sm text-purple-700">Total Clients</span>
          </div>
          <p className="text-2xl font-bold text-purple-900 mt-1">{keys.length}</p>
        </div>
      </div>
      
      {/* Filter */}
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded"
          />
          Show revoked keys
        </label>
      </div>
      
      {/* Keys list */}
      {keys.length === 0 ? (
        <div className="p-8 text-center bg-gray-50 rounded-xl border border-dashed border-gray-200">
          <Key className="h-10 w-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No API keys yet</p>
          <p className="text-xs text-gray-400 mt-1">
            Create your first key to give clients access to Reroots AI
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map((key, idx) => (
            <APIKeyRow key={idx} apiKey={key} onRevoke={fetchKeys} />
          ))}
        </div>
      )}
      
      {/* Create modal */}
      <CreateKeyModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={fetchKeys}
      />
    </div>
  );
}
