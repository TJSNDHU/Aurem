/**
 * ReRoots AI Owner Panel
 * Master control panel for managing the commercial AI platform
 */

import React, { useState, useEffect } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════════════════════
// OWNER PANEL MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

const OwnerPanel = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [ownerToken, setOwnerToken] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [analytics, setAnalytics] = useState(null);
  const [subscribers, setSubscribers] = useState([]);
  const [credentials, setCredentials] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Check stored token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('owner_token');
    if (storedToken) {
      setOwnerToken(storedToken);
      setIsAuthenticated(true);
      fetchDashboardData(storedToken);
    }
  }, []);

  const fetchDashboardData = async (token) => {
    setIsLoading(true);
    try {
      // Fetch analytics
      const analyticsRes = await fetch(`${API_URL}/api/owner/analytics/dashboard`, {
        headers: { 'X-Owner-Token': token }
      });
      if (analyticsRes.ok) {
        const data = await analyticsRes.json();
        setAnalytics(data);
      }

      // Fetch subscribers
      const subsRes = await fetch(`${API_URL}/api/owner/subscribers?limit=20`, {
        headers: { 'X-Owner-Token': token }
      });
      if (subsRes.ok) {
        const data = await subsRes.json();
        setSubscribers(data.subscribers || []);
      }

      // Fetch credentials
      const credsRes = await fetch(`${API_URL}/api/owner/credentials`, {
        headers: { 'X-Owner-Token': token }
      });
      if (credsRes.ok) {
        const data = await credsRes.json();
        setCredentials(data.credentials || []);
      }
    } catch (err) {
      setError('Failed to fetch dashboard data');
    }
    setIsLoading(false);
  };

  const handleLogin = () => {
    if (ownerToken) {
      localStorage.setItem('owner_token', ownerToken);
      setIsAuthenticated(true);
      fetchDashboardData(ownerToken);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('owner_token');
    setIsAuthenticated(false);
    setOwnerToken('');
    setAnalytics(null);
  };

  // Login Screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md p-8 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
          <div className="text-center mb-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center text-2xl font-bold text-white">
              R
            </div>
            <h1 className="text-2xl font-bold text-white">Owner Panel</h1>
            <p className="text-gray-400 mt-2">ReRoots AI Platform Control</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Owner Token</label>
              <input
                type="password"
                value={ownerToken}
                onChange={(e) => setOwnerToken(e.target.value)}
                placeholder="Enter your owner token"
                className="w-full px-4 py-3 bg-white/10 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
              />
            </div>
            <button
              onClick={handleLogin}
              className="w-full py-3 bg-gradient-to-r from-amber-500 to-amber-600 text-black font-semibold rounded-xl hover:from-amber-400 hover:to-amber-500 transition-all"
            >
              Access Panel
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center font-bold text-lg">
                R
              </div>
              <div>
                <h1 className="text-xl font-bold">Owner Panel</h1>
                <p className="text-xs text-amber-400">Platform Control Center</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-white/10 bg-black/10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1 overflow-x-auto">
            {['dashboard', 'subscribers', 'credentials', 'features', 'billing'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-3 font-medium capitalize whitespace-nowrap transition-colors relative ${
                  activeTab === tab
                    ? 'text-amber-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tab}
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
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 mb-6">
            {error}
          </div>
        )}

        {activeTab === 'dashboard' && analytics && (
          <DashboardView analytics={analytics} />
        )}

        {activeTab === 'subscribers' && (
          <SubscribersView 
            subscribers={subscribers} 
            ownerToken={ownerToken}
            onRefresh={() => fetchDashboardData(ownerToken)}
          />
        )}

        {activeTab === 'credentials' && (
          <CredentialsView 
            credentials={credentials} 
            ownerToken={ownerToken}
            onRefresh={() => fetchDashboardData(ownerToken)}
          />
        )}

        {activeTab === 'features' && (
          <FeaturesView ownerToken={ownerToken} />
        )}

        {activeTab === 'billing' && (
          <BillingView analytics={analytics} />
        )}
      </main>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// DASHBOARD VIEW
// ═══════════════════════════════════════════════════════════════════════════════

const DashboardView = ({ analytics }) => {
  return (
    <div className="space-y-8">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          icon="👥"
          label="Active Subscribers"
          value={analytics?.subscribers?.active || 0}
          subtext={`${analytics?.subscribers?.new_this_month || 0} new this month`}
          color="blue"
        />
        <MetricCard
          icon="💰"
          label="Monthly Revenue"
          value={`$${(analytics?.revenue?.total_monthly || 0).toLocaleString()}`}
          subtext={`MRR: $${(analytics?.revenue?.mrr || 0).toLocaleString()}`}
          color="green"
        />
        <MetricCard
          icon="📊"
          label="API Calls"
          value={(analytics?.api_usage?.total_calls_this_month || 0).toLocaleString()}
          subtext="This month"
          color="purple"
        />
        <MetricCard
          icon="📉"
          label="Churn Rate"
          value={`${analytics?.subscribers?.churn_rate || 0}%`}
          subtext="All time"
          color="amber"
        />
      </div>

      {/* Tier Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
          <h3 className="text-lg font-semibold mb-4">Subscribers by Tier</h3>
          <div className="space-y-3">
            {Object.entries(analytics?.tier_breakdown || {}).map(([tier, data]) => (
              <div key={tier} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    tier === 'enterprise' ? 'bg-purple-500' :
                    tier === 'business' ? 'bg-blue-500' :
                    tier === 'pro' ? 'bg-green-500' :
                    'bg-gray-500'
                  }`} />
                  <span className="capitalize">{tier}</span>
                </div>
                <div className="text-right">
                  <span className="font-semibold">{data.count}</span>
                  <span className="text-gray-400 text-sm ml-2">${data.revenue}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
          <h3 className="text-lg font-semibold mb-4">API Usage by Feature</h3>
          <div className="space-y-3">
            {Object.entries(analytics?.api_usage?.by_feature || {}).slice(0, 6).map(([feature, count]) => (
              <div key={feature} className="flex items-center justify-between">
                <span className="text-gray-300">{feature.replace(/_/g, ' ')}</span>
                <span className="font-semibold">{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Daily Signups Chart */}
      {analytics?.daily_signups?.length > 0 && (
        <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
          <h3 className="text-lg font-semibold mb-4">Daily Signups (Last 30 Days)</h3>
          <div className="h-32 flex items-end gap-1">
            {analytics.daily_signups.map((day, idx) => (
              <div
                key={idx}
                className="flex-1 bg-amber-500/50 hover:bg-amber-500 transition-colors rounded-t"
                style={{ height: `${Math.max(10, (day.count / Math.max(...analytics.daily_signups.map(d => d.count))) * 100)}%` }}
                title={`${day._id}: ${day.count} signups`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// SUBSCRIBERS VIEW
// ═══════════════════════════════════════════════════════════════════════════════

const SubscribersView = ({ subscribers, ownerToken, onRefresh }) => {
  const [selectedSub, setSelectedSub] = useState(null);
  const [filter, setFilter] = useState('all');

  const handleSuspend = async (subscriptionId) => {
    if (!window.confirm('Are you sure you want to suspend this subscriber?')) return;
    
    await fetch(`${API_URL}/api/owner/subscribers/${subscriptionId}/suspend`, {
      method: 'POST',
      headers: { 'X-Owner-Token': ownerToken }
    });
    onRefresh();
  };

  const handleActivate = async (subscriptionId) => {
    await fetch(`${API_URL}/api/owner/subscribers/${subscriptionId}/activate`, {
      method: 'POST',
      headers: { 'X-Owner-Token': ownerToken }
    });
    onRefresh();
  };

  const filteredSubs = filter === 'all' 
    ? subscribers 
    : subscribers.filter(s => s.status === filter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Subscribers</h2>
        <div className="flex gap-2">
          {['all', 'active', 'suspended', 'cancelled'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-lg text-sm capitalize ${
                filter === f 
                  ? 'bg-amber-500 text-black' 
                  : 'bg-white/10 text-gray-400 hover:text-white'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-gray-400 border-b border-white/10">
              <th className="pb-3 font-medium">Subscriber</th>
              <th className="pb-3 font-medium">Tier</th>
              <th className="pb-3 font-medium">Status</th>
              <th className="pb-3 font-medium">Usage</th>
              <th className="pb-3 font-medium">Price</th>
              <th className="pb-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSubs.map((sub) => (
              <tr key={sub.subscription_id} className="border-b border-white/5 hover:bg-white/5">
                <td className="py-4">
                  <div>
                    <div className="font-medium">{sub.subscriber_name}</div>
                    <div className="text-sm text-gray-400">{sub.subscriber_email}</div>
                  </div>
                </td>
                <td className="py-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    sub.tier === 'enterprise' ? 'bg-purple-500/20 text-purple-400' :
                    sub.tier === 'business' ? 'bg-blue-500/20 text-blue-400' :
                    sub.tier === 'pro' ? 'bg-green-500/20 text-green-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {sub.tier}
                  </span>
                </td>
                <td className="py-4">
                  <span className={`px-2 py-1 rounded text-xs ${
                    sub.status === 'active' ? 'bg-green-500/20 text-green-400' :
                    sub.status === 'suspended' ? 'bg-red-500/20 text-red-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {sub.status}
                  </span>
                </td>
                <td className="py-4 text-gray-300">
                  {sub.usage_this_month?.toLocaleString() || 0} / {sub.api_calls_limit?.toLocaleString() || '∞'}
                </td>
                <td className="py-4 text-gray-300">
                  ${sub.price}/{sub.billing_cycle === 'yearly' ? 'yr' : 'mo'}
                </td>
                <td className="py-4">
                  <div className="flex gap-2">
                    {sub.status === 'active' ? (
                      <button
                        onClick={() => handleSuspend(sub.subscription_id)}
                        className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs hover:bg-red-500/30"
                      >
                        Suspend
                      </button>
                    ) : sub.status === 'suspended' && (
                      <button
                        onClick={() => handleActivate(sub.subscription_id)}
                        className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs hover:bg-green-500/30"
                      >
                        Activate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filteredSubs.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No subscribers found
        </div>
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// CREDENTIALS VIEW
// ═══════════════════════════════════════════════════════════════════════════════

const CredentialsView = ({ credentials, ownerToken, onRefresh }) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCred, setNewCred] = useState({
    service: '',
    name: '',
    api_key: '',
    api_secret: ''
  });

  const services = {
    stripe: { name: 'Stripe', icon: '💳' },
    razorpay: { name: 'Razorpay', icon: '💰' },
    twilio: { name: 'Twilio', icon: '📱' },
    openai: { name: 'OpenAI', icon: '🤖' },
    anthropic: { name: 'Anthropic', icon: '🧠' },
    resend: { name: 'Resend', icon: '📧' },
    whapi: { name: 'WHAPI', icon: '💬' },
    google_calendar: { name: 'Google Calendar', icon: '📅' },
    github: { name: 'GitHub', icon: '🐙' },
    emergent_llm: { name: 'Emergent LLM', icon: '⚡' }
  };

  const handleAddCredential = async () => {
    if (!newCred.service || !newCred.api_key) return;

    await fetch(`${API_URL}/api/owner/credentials`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Owner-Token': ownerToken
      },
      body: JSON.stringify(newCred)
    });

    setShowAddModal(false);
    setNewCred({ service: '', name: '', api_key: '', api_secret: '' });
    onRefresh();
  };

  const handleDeleteCredential = async (service) => {
    if (!window.confirm(`Delete credential for ${service}?`)) return;

    await fetch(`${API_URL}/api/owner/credentials/${service}`, {
      method: 'DELETE',
      headers: { 'X-Owner-Token': ownerToken }
    });
    onRefresh();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">API Credentials</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-amber-500 text-black rounded-lg font-medium hover:bg-amber-400"
        >
          + Add Credential
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(services).map(([key, service]) => {
          const cred = credentials.find(c => c.service === key);
          return (
            <div
              key={key}
              className={`p-4 rounded-xl border transition-all ${
                cred
                  ? 'bg-green-500/10 border-green-500/30'
                  : 'bg-white/5 border-white/10'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{service.icon}</span>
                  <div>
                    <div className="font-medium">{service.name}</div>
                    {cred && (
                      <div className="text-xs text-gray-400">{cred.name}</div>
                    )}
                  </div>
                </div>
                {cred && (
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                )}
              </div>

              {cred ? (
                <div className="space-y-2">
                  <div className="text-sm text-gray-400">
                    Key: <code className="text-amber-400">{cred.api_key_masked}</code>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDeleteCredential(key)}
                      className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs hover:bg-red-500/30"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setNewCred({ ...newCred, service: key, name: service.name });
                    setShowAddModal(true);
                  }}
                  className="w-full py-2 border border-dashed border-white/20 rounded-lg text-gray-400 text-sm hover:border-amber-500/50 hover:text-amber-400 transition-colors"
                >
                  + Configure
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md p-6 rounded-2xl bg-gray-900 border border-white/10">
            <h3 className="text-lg font-bold mb-4">Add API Credential</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Service</label>
                <select
                  value={newCred.service}
                  onChange={(e) => setNewCred({ ...newCred, service: e.target.value })}
                  className="w-full px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-white"
                >
                  <option value="">Select service...</option>
                  {Object.entries(services).map(([key, svc]) => (
                    <option key={key} value={key}>{svc.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Name</label>
                <input
                  type="text"
                  value={newCred.name}
                  onChange={(e) => setNewCred({ ...newCred, name: e.target.value })}
                  placeholder="e.g., Production Key"
                  className="w-full px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">API Key</label>
                <input
                  type="password"
                  value={newCred.api_key}
                  onChange={(e) => setNewCred({ ...newCred, api_key: e.target.value })}
                  placeholder="sk_..."
                  className="w-full px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">API Secret (optional)</label>
                <input
                  type="password"
                  value={newCred.api_secret}
                  onChange={(e) => setNewCred({ ...newCred, api_secret: e.target.value })}
                  placeholder="Optional..."
                  className="w-full px-4 py-2 bg-white/10 border border-white/10 rounded-lg text-white"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowAddModal(false)}
                className="flex-1 py-2 bg-white/10 rounded-lg hover:bg-white/20"
              >
                Cancel
              </button>
              <button
                onClick={handleAddCredential}
                className="flex-1 py-2 bg-amber-500 text-black rounded-lg font-medium hover:bg-amber-400"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// FEATURES VIEW
// ═══════════════════════════════════════════════════════════════════════════════

const FeaturesView = ({ ownerToken }) => {
  const [features, setFeatures] = useState({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchFeatures();
  }, []);

  const fetchFeatures = async () => {
    const res = await fetch(`${API_URL}/api/owner/features/status`, {
      headers: { 'X-Owner-Token': ownerToken }
    });
    if (res.ok) {
      const data = await res.json();
      setFeatures(data.features || {});
    }
    setIsLoading(false);
  };

  const toggleFeature = async (featureId, enabled) => {
    await fetch(`${API_URL}/api/owner/features/toggle/${featureId}?enabled=${enabled}`, {
      method: 'POST',
      headers: { 'X-Owner-Token': ownerToken }
    });
    setFeatures({ ...features, [featureId]: enabled });
  };

  const featureList = [
    { id: 'ai_chat', name: 'AI Chat Assistant', icon: '🤖' },
    { id: 'weather_skincare', name: 'Weather Skincare', icon: '🌤️' },
    { id: 'voice_commands', name: 'Voice Commands', icon: '🎤' },
    { id: 'toon_optimization', name: 'TOON Optimization', icon: '⚡' },
    { id: 'skin_analysis', name: 'AI Skin Analysis', icon: '📷' },
    { id: 'sms_alerts', name: 'SMS Alerts', icon: '📱' },
    { id: 'sentiment_analysis', name: 'Sentiment Analysis', icon: '❤️' },
    { id: 'translation', name: 'Multi-Language', icon: '🌐' },
    { id: 'whatsapp_alerts', name: 'WhatsApp Alerts', icon: '💬' },
    { id: 'video_generation', name: 'Video Generation', icon: '🎬' },
    { id: 'inventory_ai', name: 'Inventory AI', icon: '📦' },
    { id: 'churn_prediction', name: 'Churn Prediction', icon: '📉' },
    { id: 'ai_email', name: 'AI Email', icon: '📧' },
    { id: 'biometric_auth', name: 'Biometric Auth', icon: '🔐' },
    { id: 'github_integration', name: 'GitHub Integration', icon: '🐙' },
    { id: 'document_scanner', name: 'Document Scanner', icon: '📄' },
    { id: 'appointment_scheduler', name: 'Appointments', icon: '📅' },
    { id: 'product_description_ai', name: 'Product AI', icon: '✏️' }
  ];

  if (isLoading) {
    return <div className="text-center py-12">Loading features...</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Feature Toggles</h2>
      <p className="text-gray-400">Enable or disable AI features globally for all subscribers.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {featureList.map((feature) => (
          <div
            key={feature.id}
            className={`p-4 rounded-xl border transition-all ${
              features[feature.id] !== false
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-white/5 border-white/10 opacity-60'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{feature.icon}</span>
                <span className="font-medium">{feature.name}</span>
              </div>
              <button
                onClick={() => toggleFeature(feature.id, features[feature.id] === false)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  features[feature.id] !== false
                    ? 'bg-green-500'
                    : 'bg-gray-600'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${
                  features[feature.id] !== false
                    ? 'translate-x-6'
                    : 'translate-x-0.5'
                }`} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// BILLING VIEW
// ═══════════════════════════════════════════════════════════════════════════════

const BillingView = ({ analytics }) => {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Billing & Revenue</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 rounded-2xl bg-gradient-to-br from-green-500/20 to-green-600/10 border border-green-500/20">
          <div className="text-sm text-green-400 mb-2">Monthly Recurring Revenue</div>
          <div className="text-4xl font-bold">${(analytics?.revenue?.mrr || 0).toLocaleString()}</div>
        </div>
        <div className="p-6 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/20">
          <div className="text-sm text-blue-400 mb-2">Annual Revenue Run Rate</div>
          <div className="text-4xl font-bold">${(analytics?.revenue?.arr || 0).toLocaleString()}</div>
        </div>
        <div className="p-6 rounded-2xl bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/20">
          <div className="text-sm text-purple-400 mb-2">Total Monthly Revenue</div>
          <div className="text-4xl font-bold">${(analytics?.revenue?.total_monthly || 0).toLocaleString()}</div>
        </div>
      </div>

      <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
        <h3 className="text-lg font-semibold mb-4">Subscription Tiers Pricing</h3>
        <table className="w-full">
          <thead>
            <tr className="text-left text-gray-400 border-b border-white/10">
              <th className="pb-3">Tier</th>
              <th className="pb-3">Monthly</th>
              <th className="pb-3">Yearly</th>
              <th className="pb-3">API Limit</th>
              <th className="pb-3">Active Subs</th>
            </tr>
          </thead>
          <tbody>
            {[
              { tier: 'Starter', monthly: 29, yearly: 290, limit: '1,000' },
              { tier: 'Pro', monthly: 99, yearly: 990, limit: '10,000' },
              { tier: 'Business', monthly: 299, yearly: 2990, limit: '50,000' },
              { tier: 'Enterprise', monthly: 999, yearly: 9990, limit: '500,000' },
              { tier: 'Custom', monthly: 'Negotiable', yearly: 'Negotiable', limit: 'Unlimited' }
            ].map((tier) => (
              <tr key={tier.tier} className="border-b border-white/5">
                <td className="py-3 font-medium">{tier.tier}</td>
                <td className="py-3">{typeof tier.monthly === 'number' ? `$${tier.monthly}` : tier.monthly}</td>
                <td className="py-3">{typeof tier.yearly === 'number' ? `$${tier.yearly}` : tier.yearly}</td>
                <td className="py-3 text-gray-400">{tier.limit}/mo</td>
                <td className="py-3">
                  {analytics?.tier_breakdown?.[tier.tier.toLowerCase()]?.count || 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// SHARED COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

const MetricCard = ({ icon, label, value, subtext, color }) => {
  const colors = {
    blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/20',
    green: 'from-green-500/20 to-green-600/10 border-green-500/20',
    purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/20',
    amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/20'
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


export default OwnerPanel;
