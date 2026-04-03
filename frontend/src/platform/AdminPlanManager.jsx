import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  DollarSign, Edit, Save, X, Plus, Trash2,
  CheckCircle, AlertCircle, Settings
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Admin Plan & Pricing Manager
 * Full CRUD for subscription plans and custom pricing
 */
const AdminPlanManager = () => {
  const [adminKey, setAdminKey] = useState(localStorage.getItem('admin_key') || '');
  const [plans, setPlans] = useState([]);
  const [customPricing, setCustomPricing] = useState(null);
  const [editingPlan, setEditingPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (adminKey) {
      loadPlans();
      loadCustomPricing();
    }
  }, [adminKey]);

  const fetchWithAuth = async (endpoint, options = {}) => {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        'X-Admin-Key': adminKey,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return response.json();
  };

  const loadPlans = async () => {
    try {
      setLoading(true);
      const data = await fetchWithAuth('/api/admin/plans/all');
      setPlans(data.plans);
    } catch (error) {
      console.error('Failed to load plans:', error);
      showMessage('Failed to load plans', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadCustomPricing = async () => {
    try {
      const data = await fetchWithAuth('/api/admin/plans/custom/pricing');
      setCustomPricing(data);
    } catch (error) {
      console.error('Failed to load custom pricing:', error);
    }
  };

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleUpdatePlan = async (planId, updates) => {
    try {
      setLoading(true);
      await fetchWithAuth(`/api/admin/plans/${planId}`, {
        method: 'PATCH',
        body: JSON.stringify(updates)
      });
      
      showMessage(`Plan ${planId} updated successfully!`);
      await loadPlans();
      setEditingPlan(null);
    } catch (error) {
      console.error('Update failed:', error);
      showMessage('Update failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivatePlan = async (planId) => {
    if (!confirm(`Deactivate plan ${planId}? This will hide it from customers.`)) return;
    
    try {
      setLoading(true);
      await fetchWithAuth(`/api/admin/plans/${planId}`, {
        method: 'DELETE'
      });
      
      showMessage(`Plan ${planId} deactivated`);
      await loadPlans();
    } catch (error) {
      console.error('Deactivation failed:', error);
      showMessage('Deactivation failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const PlanEditor = ({ plan }) => {
    const [formData, setFormData] = useState({
      name: plan.name,
      tagline: plan.tagline,
      price_monthly: plan.price_monthly,
      price_annual: plan.price_annual
    });

    const handleSave = () => {
      handleUpdatePlan(plan.plan_id, formData);
    };

    return (
      <div className="space-y-4 p-4 bg-blue-50 rounded-lg">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-slate-700">Plan Name</label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Tagline</label>
            <Input
              value={formData.tagline}
              onChange={(e) => setFormData({...formData, tagline: e.target.value})}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Monthly Price ($)</label>
            <Input
              type="number"
              value={formData.price_monthly}
              onChange={(e) => setFormData({...formData, price_monthly: parseFloat(e.target.value)})}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Annual Price ($)</label>
            <Input
              type="number"
              value={formData.price_annual}
              onChange={(e) => setFormData({...formData, price_annual: parseFloat(e.target.value)})}
            />
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button onClick={handleSave} className="flex items-center gap-2">
            <Save className="h-4 w-4" />
            Save Changes
          </Button>
          <Button variant="outline" onClick={() => setEditingPlan(null)}>
            <X className="h-4 w-4" />
            Cancel
          </Button>
        </div>
      </div>
    );
  };

  if (!adminKey) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-6 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Admin Authentication</CardTitle>
            <CardDescription>Enter admin key to manage plans</CardDescription>
          </CardHeader>
          <CardContent>
            <Input
              type="password"
              placeholder="Admin Key"
              value={adminKey}
              onChange={(e) => setAdminKey(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  localStorage.setItem('admin_key', adminKey);
                  window.location.reload();
                }
              }}
            />
            <Button 
              className="w-full mt-4"
              onClick={() => {
                localStorage.setItem('admin_key', adminKey);
                window.location.reload();
              }}
            >
              Access Admin Panel
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2 flex items-center gap-2">
            <Settings className="h-8 w-8 text-blue-600" />
            Plan & Pricing Manager
          </h1>
          <p className="text-slate-600">Manage subscription plans and custom pricing</p>
        </div>

        {/* Message Banner */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg flex items-center gap-2 ${
            message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>
            {message.type === 'success' ? <CheckCircle className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
            {message.text}
          </div>
        )}

        <Tabs defaultValue="plans">
          <TabsList>
            <TabsTrigger value="plans">Subscription Plans</TabsTrigger>
            <TabsTrigger value="custom">Custom Pricing</TabsTrigger>
          </TabsList>

          {/* Subscription Plans Tab */}
          <TabsContent value="plans" className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              {plans.map((plan) => (
                <Card key={plan.plan_id} className={!plan.active ? 'opacity-50' : ''}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {plan.name}
                          {plan.is_popular && (
                            <Badge className="bg-yellow-500">Popular</Badge>
                          )}
                          {!plan.active && (
                            <Badge variant="outline" className="text-red-600">Inactive</Badge>
                          )}
                        </CardTitle>
                        <CardDescription>{plan.tagline}</CardDescription>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditingPlan(plan.plan_id)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        {plan.active && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDeactivatePlan(plan.plan_id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-600" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {editingPlan === plan.plan_id ? (
                      <PlanEditor plan={plan} />
                    ) : (
                      <div className="grid grid-cols-4 gap-4">
                        <div>
                          <p className="text-sm text-slate-600">Monthly</p>
                          <p className="text-2xl font-bold text-slate-900">
                            ${plan.price_monthly}
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-600">Annual</p>
                          <p className="text-2xl font-bold text-slate-900">
                            ${plan.price_annual}
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-600">Discount</p>
                          <p className="text-lg font-bold text-green-600">
                            {Math.round((1 - plan.price_annual / (plan.price_monthly * 12)) * 100)}%
                          </p>
                        </div>
                        <div>
                          <p className="text-sm text-slate-600">Tier</p>
                          <Badge>{plan.tier}</Badge>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          {/* Custom Pricing Tab */}
          <TabsContent value="custom">
            {customPricing && (
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Base Platform Fee</CardTitle>
                    <CardDescription>Monthly base fee for custom plans</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-4">
                      <DollarSign className="h-8 w-8 text-slate-400" />
                      <div>
                        <p className="text-3xl font-bold text-slate-900">
                          ${customPricing.base_platform_fee}
                        </p>
                        <p className="text-sm text-slate-600">per month</p>
                      </div>
                      <Button variant="outline" size="sm" className="ml-auto">
                        <Edit className="h-4 w-4 mr-2" />
                        Edit
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Service Pricing</CardTitle>
                    <CardDescription>Per-service monthly pricing</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      {Object.entries(customPricing.service_pricing).map(([serviceId, price]) => (
                        <div key={serviceId} className="flex items-center justify-between p-3 bg-slate-50 rounded">
                          <span className="font-medium text-slate-700">{serviceId}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-lg font-bold text-slate-900">
                              ${price}/mo
                            </span>
                            <Button variant="ghost" size="sm">
                              <Edit className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminPlanManager;
