import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  RefreshCw, 
  TrendingUp, 
  TrendingDown,
  DollarSign,
  ShoppingBag,
  Users,
  Package,
  Calendar,
  ArrowUpRight
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const COLORS = ['#2D2A2E', '#4CAF50', '#FF9800', '#9C27B0', '#2196F3', '#F8A5B8'];

const SalesDashboard = () => {
  const [period, setPeriod] = useState('daily');
  const [sales, setSales] = useState(null);
  const [acquisition, setAcquisition] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [period]);

  const getAuthHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem('reroots_token')}`
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [salesRes, acqRes] = await Promise.all([
        axios.get(`${API}/api/admin/analytics/sales?period=${period}`, { headers: getAuthHeaders() }),
        axios.get(`${API}/api/admin/analytics/acquisition`, { headers: getAuthHeaders() })
      ]);
      setSales(salesRes.data);
      setAcquisition(acqRes.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  const { summary, chart_data, top_products } = sales || {};
  const { by_source, funnel } = acquisition || {};

  // Calculate funnel max for scaling
  const funnelMax = funnel?.visitors || 1;

  return (
    <div className="p-6 bg-gray-50 min-h-screen" data-testid="sales-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E]">Sales Dashboard</h2>
          <p className="text-gray-500 text-sm">Business performance overview</p>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={fetchData}
          data-testid="refresh-analytics-btn"
        >
          <RefreshCw className="h-4 w-4 mr-2" /> Refresh
        </Button>
      </div>

      {/* Period Toggle */}
      <div className="flex gap-2 mb-6">
        {['daily', 'weekly', 'monthly'].map(p => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-5 py-2 rounded-full text-sm font-semibold transition-all ${
              period === p 
                ? 'bg-[#2D2A2E] text-white shadow-md' 
                : 'bg-white text-gray-600 hover:bg-gray-100 shadow-sm'
            }`}
            data-testid={`period-${p}`}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { 
            label: 'Revenue (30d)', 
            value: `$${(summary?.total_revenue || 0).toLocaleString()}`, 
            icon: DollarSign,
            color: 'text-green-600',
            bg: 'bg-green-50'
          },
          { 
            label: 'Orders (30d)', 
            value: summary?.total_orders || 0, 
            icon: ShoppingBag,
            color: 'text-[#2D2A2E]',
            bg: 'bg-gray-100'
          },
          { 
            label: 'Avg Order Value', 
            value: `$${(summary?.avg_order_value || 0).toFixed(2)}`, 
            icon: Package,
            color: 'text-orange-600',
            bg: 'bg-orange-50'
          },
          { 
            label: 'Unique Customers', 
            value: summary?.unique_customers || 0, 
            icon: Users,
            color: 'text-purple-600',
            bg: 'bg-purple-50'
          }
        ].map(card => (
          <Card key={card.label} className="border-0 shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">{card.label}</p>
                  <p className={`text-2xl font-bold mt-1 ${card.color}`}>{card.value}</p>
                </div>
                <div className={`p-2 rounded-lg ${card.bg}`}>
                  <card.icon className={`h-5 w-5 ${card.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Revenue Chart */}
      <Card className="border-0 shadow-sm mb-6">
        <CardHeader className="pb-0">
          <CardTitle className="text-lg">Revenue Over Time</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          {chart_data?.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chart_data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="period" 
                  tickFormatter={(v) => v?.split('-').slice(-1)[0] || v}
                  fontSize={12}
                  tick={{ fill: '#666' }}
                />
                <YAxis 
                  fontSize={12}
                  tick={{ fill: '#666' }}
                  tickFormatter={(v) => `$${v}`}
                />
                <Tooltip 
                  formatter={(v) => [`$${parseFloat(v).toFixed(2)}`, 'Revenue']}
                  labelFormatter={(v) => `Period: ${v}`}
                  contentStyle={{ borderRadius: '8px', border: '1px solid #eee' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="revenue" 
                  stroke="#2D2A2E" 
                  strokeWidth={2}
                  dot={{ fill: '#2D2A2E', r: 4 }}
                  activeDot={{ r: 6, fill: '#F8A5B8' }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-12 text-gray-400">
              No revenue data for this period
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Top Products */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-0">
            <CardTitle className="text-lg">Top Products</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {top_products?.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={top_products} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" fontSize={12} tickFormatter={(v) => `$${v}`} />
                  <YAxis 
                    dataKey="product" 
                    type="category" 
                    fontSize={11} 
                    width={120}
                    tickFormatter={(v) => v?.length > 15 ? v.slice(0, 15) + '...' : v}
                  />
                  <Tooltip 
                    formatter={(v) => [`$${parseFloat(v).toFixed(2)}`, 'Revenue']}
                    contentStyle={{ borderRadius: '8px', border: '1px solid #eee' }}
                  />
                  <Bar 
                    dataKey="revenue" 
                    fill="#2D2A2E" 
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center py-12 text-gray-400">
                No product data available
              </div>
            )}
          </CardContent>
        </Card>

        {/* Acquisition Sources */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-0">
            <CardTitle className="text-lg">Acquisition Sources</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {by_source?.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={140}>
                  <PieChart>
                    <Pie
                      data={by_source}
                      dataKey="customers"
                      nameKey="acquisition_source"
                      cx="50%"
                      cy="50%"
                      outerRadius={55}
                      label={({ acquisition_source, percent }) => 
                        `${acquisition_source} ${(percent * 100).toFixed(0)}%`
                      }
                      labelLine={false}
                    >
                      {by_source.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>

                {/* Source Table */}
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-gray-500 border-b">
                        <th className="text-left pb-2">Source</th>
                        <th className="text-right pb-2">Customers</th>
                        <th className="text-right pb-2">Revenue</th>
                        <th className="text-right pb-2">Avg LTV</th>
                      </tr>
                    </thead>
                    <tbody>
                      {by_source.map((s, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          <td className="py-2 flex items-center gap-2">
                            <div 
                              className="w-3 h-3 rounded-full"
                              style={{ background: COLORS[i % COLORS.length] }}
                            />
                            {s.acquisition_source}
                          </td>
                          <td className="text-right py-2">{s.customers}</td>
                          <td className="text-right py-2 text-green-600">
                            ${(s.total_revenue || 0).toFixed(0)}
                          </td>
                          <td className="text-right py-2">
                            ${(s.avg_ltv || 0).toFixed(0)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-gray-400">
                No acquisition data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Conversion Funnel */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-0">
          <CardTitle className="text-lg">Conversion Funnel</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="flex items-end justify-around gap-4 h-32">
            {[
              { label: 'Visitors', key: 'visitors', color: '#e3f2fd' },
              { label: 'Quiz', key: 'quiz_completions', color: '#bbdefb' },
              { label: '1st Purchase', key: 'first_purchase', color: '#90caf9' },
              { label: 'Repeat', key: 'repeat_purchase', color: '#42a5f5' },
              { label: 'VIP', key: 'vip', color: '#2D2A2E' }
            ].map((step, i) => {
              const val = funnel?.[step.key] || 0;
              const height = Math.max((val / funnelMax) * 100, 8);
              const conversionRate = i > 0 && funnel 
                ? ((val / (funnel[['visitors', 'quiz_completions', 'first_purchase', 'repeat_purchase'][i-1]] || 1)) * 100).toFixed(1)
                : null;
              
              return (
                <div key={step.key} className="flex-1 text-center">
                  <div className="text-lg font-bold text-[#2D2A2E] mb-1">{val}</div>
                  {conversionRate && (
                    <div className="text-xs text-gray-400 mb-1">{conversionRate}%</div>
                  )}
                  <div 
                    className="mx-auto rounded-t-lg transition-all duration-500"
                    style={{
                      height: `${height}px`,
                      background: step.color,
                      width: '60%',
                      border: '1px solid #e0e0e0'
                    }}
                  />
                  <div className="text-xs text-gray-600 mt-2 font-medium">
                    {step.label}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Funnel insights */}
          {funnel && funnel.visitors > 0 && (
            <div className="mt-6 pt-4 border-t grid grid-cols-3 gap-4 text-center text-sm">
              <div>
                <p className="text-gray-500">Quiz → Purchase</p>
                <p className="font-bold text-[#2D2A2E]">
                  {funnel.quiz_completions > 0 
                    ? ((funnel.first_purchase / funnel.quiz_completions) * 100).toFixed(1)
                    : 0}%
                </p>
              </div>
              <div>
                <p className="text-gray-500">Repeat Rate</p>
                <p className="font-bold text-green-600">
                  {funnel.first_purchase > 0 
                    ? ((funnel.repeat_purchase / funnel.first_purchase) * 100).toFixed(1)
                    : 0}%
                </p>
              </div>
              <div>
                <p className="text-gray-500">VIP Conversion</p>
                <p className="font-bold text-purple-600">
                  {funnel.first_purchase > 0 
                    ? ((funnel.vip / funnel.first_purchase) * 100).toFixed(1)
                    : 0}%
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default SalesDashboard;
