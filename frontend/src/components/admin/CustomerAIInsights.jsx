import React, { useState, useEffect, useCallback } from 'react';
import { 
  Brain, 
  Users, 
  TrendingUp, 
  Star,
  ShoppingCart,
  Clock,
  RefreshCw,
  ChevronRight,
  Sparkles,
  Target
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

export default function CustomerAIInsights() {
  const [insights, setInsights] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Authorization': `Bearer ${token}` };

      const [insightsRes, customersRes] = await Promise.all([
        fetch(`${API_URL}/api/crm/ai-insights`, { headers }),
        fetch(`${API_URL}/api/crm/top-customers`, { headers })
      ]);

      if (insightsRes.ok) {
        const data = await insightsRes.json();
        setInsights(data);
      }

      if (customersRes.ok) {
        const data = await customersRes.json();
        setCustomers(data.customers || []);
      }
    } catch (error) {
      console.error('Failed to fetch AI insights:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600 bg-green-50';
    if (score >= 60) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="p-6 space-y-6" data-testid="customer-ai-insights">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="w-8 h-8 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Customer AI Insights</h1>
            <p className="text-sm text-gray-500">AI-powered customer analytics and predictions</p>
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Brain className="w-8 h-8 animate-pulse text-indigo-600" />
        </div>
      ) : (
        <>
          {/* AI Insights Summary */}
          {insights && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl p-6 text-white">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-5 h-5" />
                  <span className="font-medium">AI Prediction</span>
                </div>
                <div className="text-3xl font-bold mb-1">{insights.predicted_revenue || '$0'}</div>
                <p className="text-white/70 text-sm">Predicted next 30 days</p>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-2 text-gray-500">
                  <Target className="w-5 h-5" />
                  <span className="font-medium">Churn Risk</span>
                </div>
                <div className="text-3xl font-bold text-red-600 mb-1">{insights.churn_risk_count || 0}</div>
                <p className="text-gray-500 text-sm">Customers at risk</p>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-2 text-gray-500">
                  <TrendingUp className="w-5 h-5" />
                  <span className="font-medium">Growth Potential</span>
                </div>
                <div className="text-3xl font-bold text-green-600 mb-1">{insights.growth_potential || 0}%</div>
                <p className="text-gray-500 text-sm">Upsell opportunities</p>
              </div>
            </div>
          )}

          {/* Top Customers */}
          <div className="bg-white rounded-xl border border-gray-200">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Star className="w-5 h-5 text-amber-500" />
                Top Customers
              </h2>
            </div>

            {customers.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No customer data available</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {customers.slice(0, 10).map((customer, idx) => (
                  <div key={idx} className="p-4 hover:bg-gray-50 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-medium">
                        {customer.name?.[0] || 'C'}
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">{customer.name || customer.email}</div>
                        <div className="text-sm text-gray-500 flex items-center gap-2">
                          <ShoppingCart className="w-3 h-3" />
                          {customer.orders || 0} orders
                          <span className="mx-1">·</span>
                          ${customer.total_spent || 0} spent
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-sm font-medium ${getScoreColor(customer.loyalty_score || 0)}`}>
                        {customer.loyalty_score || 0}% loyalty
                      </span>
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
