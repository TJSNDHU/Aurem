/**
 * ReRoots AI Commercial Dashboard
 * Complete interface for API key management and all AI features
 */

import React, { useState, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMMERCIAL DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

const ReRootsAICommercialDashboard = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [apiKeys, setApiKeys] = useState([]);
  const [tiers, setTiers] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    totalKeys: 0,
    activeKeys: 0,
    totalUsage: 0,
    features: 8
  });

  // Fetch data on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch tiers
        const tiersRes = await fetch(`${API_URL}/api/admin/api-keys/tiers`);
        if (tiersRes.ok) {
          const data = await tiersRes.json();
          setTiers(data.tiers || {});
        }
      } catch (err) {
        console.error(err);
      }
      setIsLoading(false);
    };
    fetchData();
  }, []);

  const features = [
    { icon: '🤖', name: 'AI Chat Assistant', desc: 'RAG-powered skincare advisor', status: 'active' },
    { icon: '📧', name: 'AI Email Generator', desc: 'Automated email campaigns', status: 'active' },
    { icon: '💬', name: 'WhatsApp Alerts', desc: 'Order & promo notifications', status: 'active' },
    { icon: '🌤️', name: 'Weather Skincare', desc: 'Climate-based recommendations', status: 'active' },
    { icon: '🔐', name: 'Biometric Auth', desc: 'Face, voice, fingerprint', status: 'active' },
    { icon: '🎤', name: 'Voice Commands', desc: 'Multi-language voice I/O', status: 'active' },
    { icon: '📦', name: 'GitHub Integration', desc: 'Auto-build RAG from repos', status: 'active' },
    { icon: '⚡', name: 'TOON Optimization', desc: '50% token savings', status: 'active' },
    { icon: '📞', name: 'AI Calling Agent', desc: 'Phone calls with AI', status: 'coming' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center font-bold text-lg">
                R
              </div>
              <div>
                <h1 className="text-xl font-bold">ReRoots AI</h1>
                <p className="text-xs text-amber-400">Commercial Platform</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm font-medium">
                ● All Systems Operational
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-white/10 bg-black/10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {['overview', 'api-keys', 'features', 'usage', 'docs'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-3 font-medium capitalize transition-colors relative ${
                  activeTab === tab
                    ? 'text-amber-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tab.replace('-', ' ')}
                {activeTab === tab && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-400" />
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard 
                icon="🔑" 
                label="API Keys" 
                value={stats.activeKeys} 
                subtext="Active keys"
                color="amber"
              />
              <StatCard 
                icon="📊" 
                label="Total Requests" 
                value="12.5K" 
                subtext="This month"
                color="blue"
              />
              <StatCard 
                icon="⚡" 
                label="Tokens Saved" 
                value="45%" 
                subtext="With TOON"
                color="green"
              />
              <StatCard 
                icon="🚀" 
                label="Features" 
                value={features.filter(f => f.status === 'active').length} 
                subtext="Active features"
                color="purple"
              />
            </div>

            {/* Features Overview */}
            <div>
              <h2 className="text-xl font-bold mb-4">AI Features</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {features.map((feature, idx) => (
                  <div
                    key={idx}
                    className={`p-4 rounded-xl border transition-all ${
                      feature.status === 'active'
                        ? 'bg-white/5 border-white/10 hover:border-amber-500/50'
                        : 'bg-white/[0.02] border-white/5 opacity-60'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">{feature.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold">{feature.name}</h3>
                          {feature.status === 'coming' && (
                            <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded">
                              Coming Soon
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-400 mt-1">{feature.desc}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-6 rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-600/10 border border-amber-500/20">
                <h3 className="text-lg font-bold mb-2">Generate API Key</h3>
                <p className="text-gray-400 text-sm mb-4">
                  Create a new API key to integrate ReRoots AI into your application.
                </p>
                <button 
                  onClick={() => setActiveTab('api-keys')}
                  className="px-4 py-2 bg-amber-500 text-black rounded-lg font-medium hover:bg-amber-400 transition-colors"
                >
                  Create Key
                </button>
              </div>
              <div className="p-6 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/20">
                <h3 className="text-lg font-bold mb-2">API Documentation</h3>
                <p className="text-gray-400 text-sm mb-4">
                  Learn how to integrate ReRoots AI features into your platform.
                </p>
                <button 
                  onClick={() => setActiveTab('docs')}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-400 transition-colors"
                >
                  View Docs
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'api-keys' && (
          <APIKeysPanel tiers={tiers} />
        )}

        {activeTab === 'features' && (
          <FeaturesPanel features={features} />
        )}

        {activeTab === 'usage' && (
          <UsagePanel />
        )}

        {activeTab === 'docs' && (
          <DocsPanel />
        )}
      </main>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

const StatCard = ({ icon, label, value, subtext, color }) => {
  const colors = {
    amber: 'from-amber-500/20 to-amber-600/5 border-amber-500/20',
    blue: 'from-blue-500/20 to-blue-600/5 border-blue-500/20',
    green: 'from-green-500/20 to-green-600/5 border-green-500/20',
    purple: 'from-purple-500/20 to-purple-600/5 border-purple-500/20',
  };

  return (
    <div className={`p-5 rounded-xl bg-gradient-to-br border ${colors[color]}`}>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl">{icon}</span>
        <span className="text-gray-400 text-sm">{label}</span>
      </div>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm text-gray-500 mt-1">{subtext}</div>
    </div>
  );
};


const APIKeysPanel = ({ tiers }) => {
  const [keys, setKeys] = useState([]);
  const [isCreating, setIsCreating] = useState(false);
  const [newKey, setNewKey] = useState(null);
  const [form, setForm] = useState({
    client_name: '',
    tier: 'starter',
    expires_in_days: 365
  });

  const createKey = async () => {
    setIsCreating(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/api-keys/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      if (res.ok) {
        const data = await res.json();
        setNewKey(data);
        setForm({ client_name: '', tier: 'starter', expires_in_days: 365 });
      }
    } catch (err) {
      console.error(err);
    }
    setIsCreating(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">API Keys</h2>
      </div>

      {/* Tiers Info */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {Object.entries(tiers).map(([name, info]) => (
          <div key={name} className="p-4 rounded-xl bg-white/5 border border-white/10">
            <h3 className="font-semibold capitalize text-amber-400">{name}</h3>
            <p className="text-2xl font-bold mt-2">
              {info.limit > 0 ? info.limit.toLocaleString() : '∞'}
            </p>
            <p className="text-sm text-gray-400">requests/month</p>
          </div>
        ))}
      </div>

      {/* Create Key Form */}
      <div className="p-6 rounded-xl bg-white/5 border border-white/10">
        <h3 className="font-semibold mb-4">Create New API Key</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Client Name</label>
            <input
              type="text"
              value={form.client_name}
              onChange={(e) => setForm({ ...form, client_name: e.target.value })}
              placeholder="e.g., Acme Corp"
              className="w-full px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Tier</label>
            <select
              value={form.tier}
              onChange={(e) => setForm({ ...form, tier: e.target.value })}
              className="w-full px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-white focus:border-amber-500 focus:outline-none"
            >
              {Object.keys(tiers).map((tier) => (
                <option key={tier} value={tier} className="bg-gray-800">
                  {tier.charAt(0).toUpperCase() + tier.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={createKey}
              disabled={!form.client_name || isCreating}
              className="w-full px-4 py-2 bg-amber-500 text-black rounded-lg font-medium hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isCreating ? 'Creating...' : 'Generate Key'}
            </button>
          </div>
        </div>

        {/* New Key Display */}
        {newKey && (
          <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-green-400 mb-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="font-semibold">API Key Created!</span>
            </div>
            <p className="text-sm text-gray-400 mb-2">Save this key now - it won't be shown again!</p>
            <div className="p-3 bg-black/30 rounded font-mono text-sm break-all text-amber-400">
              {newKey.api_key}
            </div>
            <div className="mt-2 text-sm text-gray-500">
              Client: {newKey.client_name} • Tier: {newKey.tier} • Limit: {newKey.monthly_limit}/month
            </div>
          </div>
        )}
      </div>
    </div>
  );
};


const FeaturesPanel = ({ features }) => {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">AI Features</h2>
      
      <div className="grid gap-4">
        {features.map((feature, idx) => (
          <div
            key={idx}
            className={`p-6 rounded-xl border transition-all ${
              feature.status === 'active'
                ? 'bg-white/5 border-white/10'
                : 'bg-white/[0.02] border-white/5 opacity-60'
            }`}
          >
            <div className="flex items-start gap-4">
              <span className="text-4xl">{feature.icon}</span>
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-lg font-semibold">{feature.name}</h3>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    feature.status === 'active' 
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-amber-500/20 text-amber-400'
                  }`}>
                    {feature.status === 'active' ? 'Active' : 'Coming Soon'}
                  </span>
                </div>
                <p className="text-gray-400">{feature.desc}</p>
                
                {/* Feature-specific details */}
                {feature.name === 'AI Chat Assistant' && (
                  <div className="mt-3 text-sm text-gray-500">
                    Endpoints: <code className="text-amber-400">/api/rag/chat</code>, <code className="text-amber-400">/api/ai/chat</code>
                  </div>
                )}
                {feature.name === 'TOON Optimization' && (
                  <div className="mt-3 text-sm text-gray-500">
                    Endpoints: <code className="text-amber-400">/api/toon/convert</code>, <code className="text-amber-400">/api/toon/products</code>
                  </div>
                )}
                {feature.name === 'Weather Skincare' && (
                  <div className="mt-3 text-sm text-gray-500">
                    Endpoints: <code className="text-amber-400">/api/weather-skincare/analyze/city</code>
                  </div>
                )}
                {feature.name === 'Biometric Auth' && (
                  <div className="mt-3 text-sm text-gray-500">
                    Endpoints: <code className="text-amber-400">/api/biometric/face/verify</code>, <code className="text-amber-400">/api/biometric/voice/verify</code>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};


const UsagePanel = () => {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Usage Analytics</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-6 rounded-xl bg-white/5 border border-white/10">
          <h3 className="text-gray-400 text-sm mb-2">Total API Calls</h3>
          <div className="text-3xl font-bold">12,458</div>
          <div className="text-green-400 text-sm mt-1">↑ 23% from last month</div>
        </div>
        <div className="p-6 rounded-xl bg-white/5 border border-white/10">
          <h3 className="text-gray-400 text-sm mb-2">Tokens Processed</h3>
          <div className="text-3xl font-bold">2.4M</div>
          <div className="text-green-400 text-sm mt-1">↑ 15% from last month</div>
        </div>
        <div className="p-6 rounded-xl bg-white/5 border border-white/10">
          <h3 className="text-gray-400 text-sm mb-2">Avg Response Time</h3>
          <div className="text-3xl font-bold">1.2s</div>
          <div className="text-green-400 text-sm mt-1">↓ 8% faster</div>
        </div>
      </div>

      {/* Usage by Feature */}
      <div className="p-6 rounded-xl bg-white/5 border border-white/10">
        <h3 className="font-semibold mb-4">Usage by Feature</h3>
        <div className="space-y-4">
          {[
            { name: 'AI Chat', usage: 4521, percent: 36 },
            { name: 'Weather Skincare', usage: 2834, percent: 23 },
            { name: 'Email Generation', usage: 1876, percent: 15 },
            { name: 'WhatsApp Alerts', usage: 1543, percent: 12 },
            { name: 'TOON Conversion', usage: 987, percent: 8 },
            { name: 'Biometric Auth', usage: 697, percent: 6 },
          ].map((item, idx) => (
            <div key={idx}>
              <div className="flex justify-between text-sm mb-1">
                <span>{item.name}</span>
                <span className="text-gray-400">{item.usage.toLocaleString()} calls</span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-amber-500 to-amber-400 rounded-full"
                  style={{ width: `${item.percent}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};


const DocsPanel = () => {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">API Documentation</h2>

      <div className="p-6 rounded-xl bg-white/5 border border-white/10">
        <h3 className="font-semibold mb-4">Authentication</h3>
        <p className="text-gray-400 mb-4">
          All API requests require the <code className="text-amber-400">X-Reroots-API-Key</code> header.
        </p>
        <div className="p-4 bg-black/30 rounded-lg font-mono text-sm overflow-x-auto">
          <span className="text-blue-400">curl</span> -X POST \<br/>
          &nbsp;&nbsp;-H <span className="text-green-400">"X-Reroots-API-Key: rr_live_xxxx..."</span> \<br/>
          &nbsp;&nbsp;-H <span className="text-green-400">"Content-Type: application/json"</span> \<br/>
          &nbsp;&nbsp;-d <span className="text-yellow-400">'{`{"message": "Hello"}`}'</span> \<br/>
          &nbsp;&nbsp;<span className="text-gray-500">https://api.reroots.ca/api/rag/chat</span>
        </div>
      </div>

      <div className="p-6 rounded-xl bg-white/5 border border-white/10">
        <h3 className="font-semibold mb-4">Endpoints</h3>
        <div className="space-y-3">
          {[
            { method: 'POST', path: '/api/rag/chat', desc: 'AI Chat with RAG' },
            { method: 'POST', path: '/api/ai-email/generate', desc: 'Generate AI email' },
            { method: 'POST', path: '/api/whatsapp-alerts/send', desc: 'Send WhatsApp alert' },
            { method: 'POST', path: '/api/weather-skincare/analyze/city', desc: 'Weather-based recommendations' },
            { method: 'POST', path: '/api/biometric/face/verify', desc: 'Face verification' },
            { method: 'POST', path: '/api/biometric/voice/verify', desc: 'Voice verification' },
            { method: 'POST', path: '/api/github/chat', desc: 'Chat with GitHub repos' },
            { method: 'POST', path: '/api/toon/convert', desc: 'Convert JSON to TOON' },
          ].map((endpoint, idx) => (
            <div key={idx} className="flex items-center gap-3 p-3 bg-black/20 rounded-lg">
              <span className={`px-2 py-1 rounded text-xs font-bold ${
                endpoint.method === 'POST' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
              }`}>
                {endpoint.method}
              </span>
              <code className="text-amber-400 flex-1 font-mono text-sm">{endpoint.path}</code>
              <span className="text-gray-500 text-sm">{endpoint.desc}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="p-6 rounded-xl bg-white/5 border border-white/10">
        <h3 className="font-semibold mb-4">Rate Limits</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-white/10">
              <th className="pb-2">Tier</th>
              <th className="pb-2">Requests/Month</th>
              <th className="pb-2">Rate Limit</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-white/5">
              <td className="py-2 font-medium">Starter</td>
              <td className="py-2">500</td>
              <td className="py-2">10/min</td>
            </tr>
            <tr className="border-b border-white/5">
              <td className="py-2 font-medium">Growth</td>
              <td className="py-2">2,000</td>
              <td className="py-2">30/min</td>
            </tr>
            <tr className="border-b border-white/5">
              <td className="py-2 font-medium">Enterprise</td>
              <td className="py-2">10,000</td>
              <td className="py-2">100/min</td>
            </tr>
            <tr>
              <td className="py-2 font-medium">Unlimited</td>
              <td className="py-2">∞</td>
              <td className="py-2">No limit</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};


export default ReRootsAICommercialDashboard;
