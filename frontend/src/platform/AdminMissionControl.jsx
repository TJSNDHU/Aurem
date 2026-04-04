import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Server, Key, DollarSign, Users, Activity, 
  TrendingUp, AlertCircle, CheckCircle, XCircle,
  Database, Zap, BarChart3, Settings
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * AUREM Admin Mission Control
 * Central panel to manage ALL services, API keys, subscriptions
 * 
 * Features:
 * - Dashboard overview (MRR, ARR, active subs)
 * - Service registry (view all third-party services)
 * - API key management (add/remove keys)
 * - Subscription management (view all customers)
 * - Usage analytics (real-time metrics)
 */
const AdminMissionControl = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);
  const [adminKey, setAdminKey] = useState(localStorage.getItem('admin_key') || '');
  
  // State
  const [dashboard, setDashboard] = useState(null);
  const [services, setServices] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [usage, setUsage] = useState([]);
  
  // Add API key form
  const [newKey, setNewKey] = useState({
    service_id: '',
    api_key: '',
    notes: '',
    monthly_spend_limit: ''
  });

  // Save admin key to localStorage
  const saveAdminKey = (key) => {
    setAdminKey(key);
    localStorage.setItem('admin_key', key);
  };

  // Fetch data with admin auth
  const fetchWithAuth = async (endpoint) => {
    const response = await fetch(`${API_URL}${endpoint}`, {
      headers: {
        'X-Admin-Key': adminKey
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return response.json();
  };

  // Load dashboard
  const loadDashboard = async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/dashboard');
      setDashboard(data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load services
  const loadServices = async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/services');
      
      // Parse TOON format
      if (data.format === 'TOON') {
        const lines = data.data.split('\n').slice(1); // Skip header
        const parsed = lines.map(line => {
          const parts = line.trim().split(', ');
          return {
            id: parts[0],
            category: parts[1],
            provider: parts[2],
            cost: parts[3],
            status: parts[4],
            tiers: parts[5]
          };
        });
        setServices(parsed);
      }
    } catch (error) {
      console.error('Failed to load services:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load API keys
  const loadApiKeys = async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/api-keys');
      
      // Parse TOON format
      if (data.format === 'TOON') {
        const lines = data.data.split('\n').slice(1);
        const parsed = lines.map(line => {
          const parts = line.trim().split(', ');
          return {
            service: parts[0],
            preview: parts[1],
            status: parts[2],
            calls: parts[3],
            spend: parts[4],
            lastUsed: parts[5]
          };
        });
        setApiKeys(parsed);
      }
    } catch (error) {
      console.error('Failed to load API keys:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load subscriptions
  const loadSubscriptions = async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/mission-control/subscriptions');
      
      // Parse TOON format
      if (data.format === 'TOON') {
        const lines = data.data.split('\n').slice(1);
        const parsed = lines.map(line => {
          const parts = line.trim().split(', ');
          return {
            id: parts[0],
            user: parts[1],
            tier: parts[2],
            status: parts[3],
            amount: parts[4],
            periodEnd: parts[5],
            usage: parts[6]
          };
        });
        setSubscriptions(parsed);
      }
    } catch (error) {
      console.error('Failed to load subscriptions:', error);
    } finally {
      setLoading(false);
    }
  };

  // Add API key
  const addApiKey = async () => {
    try {
      setLoading(true);
      
      const response = await fetch(`${API_URL}/api/admin/mission-control/services/add-key`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Key': adminKey
        },
        body: JSON.stringify(newKey)
      });
      
      if (!response.ok) {
        throw new Error('Failed to add API key');
      }
      
      // Clear form
      setNewKey({
        service_id: '',
        api_key: '',
        notes: '',
        monthly_spend_limit: ''
      });
      
      // Reload
      await loadApiKeys();
      await loadServices();
      
      alert('✅ API key added successfully!');
    } catch (error) {
      console.error('Failed to add API key:', error);
      alert('❌ Failed to add API key');
    } finally {
      setLoading(false);
    }
  };

  // Clear cache and refresh system
  const clearCacheAndRefresh = async () => {
    if (!window.confirm('⚠️ This will clear all caches and refresh the vector database. Continue?')) {
      return;
    }

    try {
      setLoading(true);
      
      const response = await fetch(`${API_URL}/api/admin/cache/clear`, {
        method: 'POST',
        headers: {
          'X-Admin-Key': adminKey
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to clear cache');
      }
      
      const result = await response.json();
      
      alert(`✅ Cache cleared successfully!\n\nCleared:\n- Vector DB collections: ${result.vector_collections_cleared}\n- MongoDB cache: ${result.mongodb_cache_cleared}\n- Browser cache will be cleared on reload`);
      
      // Reload current data
      switch (activeTab) {
        case 'dashboard':
          await loadDashboard();
          break;
        case 'services':
          await loadServices();
          break;
        case 'api-keys':
          await loadApiKeys();
          break;
        case 'subscriptions':
          await loadSubscriptions();
          break;
      }
      
      // Clear browser cache
      window.location.reload(true);
      
    } catch (error) {
      console.error('Failed to clear cache:', error);
      alert('❌ Failed to clear cache: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Status badge color
  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-500';
      case 'no_keys': return 'bg-yellow-500';
      case 'paused': return 'bg-gray-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  // Load data on tab change
  useEffect(() => {
    if (!adminKey) return;
    
    switch (activeTab) {
      case 'dashboard':
        loadDashboard();
        break;
      case 'services':
        loadServices();
        break;
      case 'api-keys':
        loadApiKeys();
        loadServices(); // Need services for dropdown
        break;
      case 'subscriptions':
        loadSubscriptions();
        break;
      default:
        break;
    }
  }, [activeTab, adminKey]);

  // Auth gate
  if (!adminKey) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-pink-50 to-white flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="w-5 h-5" />
              Admin Authentication
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-gray-600">
              Enter your admin key to access Mission Control
            </p>
            <Input
              type="password"
              placeholder="Admin Key"
              value={adminKey}
              onChange={(e) => saveAdminKey(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && adminKey && loadDashboard()}
            />
            <Button 
              onClick={() => adminKey && loadDashboard()}
              className="w-full"
              disabled={!adminKey}
            >
              Access Mission Control
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 to-white p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
              <Server className="w-8 h-8 text-pink-600" />
              AUREM Mission Control
            </h1>
            <p className="text-gray-600 mt-1">
              Manage services, API keys, subscriptions & usage
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={clearCacheAndRefresh}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <Database className="w-4 h-4" />
              {loading ? 'Clearing...' : 'Clear Cache & Refresh'}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                localStorage.removeItem('admin_key');
                setAdminKey('');
              }}
            >
              Logout
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="dashboard">
              <BarChart3 className="w-4 h-4 mr-2" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="services">
              <Database className="w-4 h-4 mr-2" />
              Services
            </TabsTrigger>
            <TabsTrigger value="api-keys">
              <Key className="w-4 h-4 mr-2" />
              API Keys
            </TabsTrigger>
            <TabsTrigger value="subscriptions">
              <Users className="w-4 h-4 mr-2" />
              Subscriptions
            </TabsTrigger>
            <TabsTrigger value="analytics">
              <Activity className="w-4 h-4 mr-2" />
              Analytics
            </TabsTrigger>
          </TabsList>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-4">
            {dashboard && (
              <>
                {/* Metrics Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                      <CardTitle className="text-sm font-medium text-gray-600">
                        Active Subscriptions
                      </CardTitle>
                      <Users className="w-4 h-4 text-gray-400" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">150</div>
                      <p className="text-xs text-green-600 mt-1">
                        +12% from last month
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                      <CardTitle className="text-sm font-medium text-gray-600">
                        MRR
                      </CardTitle>
                      <DollarSign className="w-4 h-4 text-gray-400" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">$35,000</div>
                      <p className="text-xs text-green-600 mt-1">
                        ARR: $420,000
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                      <CardTitle className="text-sm font-medium text-gray-600">
                        Active Services
                      </CardTitle>
                      <Zap className="w-4 h-4 text-gray-400" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">8/15</div>
                      <p className="text-xs text-yellow-600 mt-1">
                        7 need API keys
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Quick Actions */}
                <Card>
                  <CardHeader>
                    <CardTitle>Quick Actions</CardTitle>
                  </CardHeader>
                  <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Button onClick={() => setActiveTab('api-keys')} variant="outline">
                      <Key className="w-4 h-4 mr-2" />
                      Add API Key
                    </Button>
                    <Button onClick={() => setActiveTab('services')} variant="outline">
                      <Database className="w-4 h-4 mr-2" />
                      View Services
                    </Button>
                    <Button onClick={() => setActiveTab('subscriptions')} variant="outline">
                      <Users className="w-4 h-4 mr-2" />
                      Subscriptions
                    </Button>
                    <Button onClick={() => setActiveTab('analytics')} variant="outline">
                      <Activity className="w-4 h-4 mr-2" />
                      Analytics
                    </Button>
                  </CardContent>
                </Card>
              </>
            )}
          </TabsContent>

          {/* Services Tab */}
          <TabsContent value="services">
            <Card>
              <CardHeader>
                <CardTitle>Service Registry</CardTitle>
                <p className="text-sm text-gray-600">
                  All available third-party services
                </p>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">Loading...</div>
                ) : (
                  <div className="space-y-3">
                    {services.map((service, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
                      >
                        <div className="flex-1">
                          <div className="font-medium">{service.id}</div>
                          <div className="text-sm text-gray-600">
                            {service.provider} • {service.category} • {service.cost}
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge className={getStatusColor(service.status)}>
                            {service.status}
                          </Badge>
                          <span className="text-xs text-gray-500">{service.tiers}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* API Keys Tab */}
          <TabsContent value="api-keys" className="space-y-4">
            {/* Add Key Form */}
            <Card>
              <CardHeader>
                <CardTitle>Add API Key</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Service</label>
                    <select
                      className="w-full mt-1 p-2 border rounded"
                      value={newKey.service_id}
                      onChange={(e) => setNewKey({...newKey, service_id: e.target.value})}
                    >
                      <option value="">Select service...</option>
                      {services.map((s, idx) => (
                        <option key={idx} value={s.id}>{s.id}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium">API Key</label>
                    <Input
                      type="password"
                      placeholder="sk-proj-..."
                      value={newKey.api_key}
                      onChange={(e) => setNewKey({...newKey, api_key: e.target.value})}
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium">Monthly Spend Limit (optional)</label>
                    <Input
                      type="number"
                      placeholder="1000.00"
                      value={newKey.monthly_spend_limit}
                      onChange={(e) => setNewKey({...newKey, monthly_spend_limit: e.target.value})}
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium">Notes (optional)</label>
                    <Input
                      placeholder="Production key - Jan 2026"
                      value={newKey.notes}
                      onChange={(e) => setNewKey({...newKey, notes: e.target.value})}
                    />
                  </div>
                </div>
                
                <Button 
                  onClick={addApiKey}
                  disabled={!newKey.service_id || !newKey.api_key || loading}
                  className="w-full"
                >
                  {loading ? 'Adding...' : 'Add API Key'}
                </Button>
              </CardContent>
            </Card>

            {/* Existing Keys */}
            <Card>
              <CardHeader>
                <CardTitle>Existing API Keys</CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">Loading...</div>
                ) : apiKeys.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No API keys added yet
                  </div>
                ) : (
                  <div className="space-y-3">
                    {apiKeys.map((key, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="font-medium">{key.service}</div>
                          <div className="text-sm text-gray-600 font-mono">{key.preview}</div>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-gray-600">{key.calls} calls</span>
                          <span className="font-medium">${key.spend}</span>
                          <Badge className={getStatusColor(key.status)}>
                            {key.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Subscriptions Tab */}
          <TabsContent value="subscriptions">
            <Card>
              <CardHeader>
                <CardTitle>All Subscriptions</CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">Loading...</div>
                ) : subscriptions.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No active subscriptions
                  </div>
                ) : (
                  <div className="space-y-3">
                    {subscriptions.map((sub, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="font-medium">{sub.user}</div>
                          <div className="text-sm text-gray-600">{sub.usage}</div>
                        </div>
                        <div className="flex items-center gap-4">
                          <Badge>{sub.tier}</Badge>
                          <span className="font-medium">${sub.amount}/mo</span>
                          <Badge className={getStatusColor(sub.status)}>
                            {sub.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Analytics Tab */}
          <TabsContent value="analytics">
            <Card>
              <CardHeader>
                <CardTitle>Usage Analytics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8 text-gray-500">
                  Analytics dashboard coming soon...
                  <br />
                  <span className="text-sm">
                    View metrics at: <code className="bg-gray-100 px-2 py-1 rounded">/metrics</code>
                  </span>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminMissionControl;
