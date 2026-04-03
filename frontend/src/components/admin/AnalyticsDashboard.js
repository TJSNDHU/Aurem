import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  BarChart3, TrendingUp, TrendingDown, DollarSign, ShoppingCart,
  Users, Package, Eye, ArrowUpRight, ArrowDownRight, Calendar,
  RefreshCw, AlertCircle
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { useAdminBrand } from './useAdminBrand';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const AnalyticsDashboard = () => {
  const { activeBrand } = useAdminBrand();
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('30d');
  const [stats, setStats] = useState({
    total_revenue: 0,
    total_orders: 0,
    total_customers: 0,
    total_products: 0,
    avg_order_value: 0,
    conversion_rate: 0,
    top_products: [],
    recent_orders: [],
    revenue_change: 0,
    orders_change: 0,
    customers_change: 0,
    aov_change: 0,
    conversion_change: 0,
    visitor_tracking_enabled: false
  });

  useEffect(() => {
    fetchAnalytics();
  }, [period, activeBrand]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };

      const response = await axios.get(`${API}/admin/stats?period=${period}&brand=${activeBrand}`, { headers });
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const MetricCard = ({ title, value, change, icon: Icon, color, prefix = '', suffix = '', showChange = true }) => (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[#5A5A5A] mb-1">{title}</p>
            <p className={`text-3xl font-bold ${color}`}>
              {prefix}{typeof value === 'number' ? value.toLocaleString(undefined, {minimumFractionDigits: prefix === '$' ? 2 : 0, maximumFractionDigits: prefix === '$' ? 2 : 0}) : value}{suffix}
            </p>
            {showChange && change !== undefined && change !== null && (
              <p className={`text-sm mt-1 flex items-center gap-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {change >= 0 ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                {Math.abs(change)}% vs last period
              </p>
            )}
          </div>
          <div className={`p-3 rounded-xl ${color.replace('text-', 'bg-').replace('-600', '-100')}`}>
            <Icon className={`h-6 w-6 ${color}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const getPeriodLabel = () => {
    switch(period) {
      case 'today': return 'Today';
      case '7d': return 'Last 7 Days';
      case '30d': return 'Last 30 Days';
      case '90d': return 'Last 90 Days';
      default: return 'Last 30 Days';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Analytics Dashboard</h1>
          <p className="text-[#5A5A5A]">Track your store performance • {getPeriodLabel()}</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-36">
              <Calendar className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchAnalytics} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Data Quality Notice */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
          <div className="text-sm">
            <p className="font-medium text-blue-800">Data Quality: Verified</p>
            <p className="text-blue-600">
              Revenue and order metrics only include paid orders. Canceled, refunded, and test orders are excluded.
              {!stats.visitor_tracking_enabled && " Visitor tracking not enabled - conversion rate unavailable."}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Main Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Revenue"
          value={stats.total_revenue}
          prefix="$"
          change={stats.revenue_change}
          icon={DollarSign}
          color="text-green-600"
        />
        <MetricCard
          title="Paid Orders"
          value={stats.total_orders}
          change={stats.orders_change}
          icon={ShoppingCart}
          color="text-blue-600"
        />
        <MetricCard
          title="Customers"
          value={stats.total_customers}
          change={stats.customers_change}
          icon={Users}
          color="text-purple-600"
        />
        <MetricCard
          title="Products"
          value={stats.total_products}
          icon={Package}
          color="text-orange-600"
          showChange={false}
        />
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-[#F8A5B8]/20">
                <TrendingUp className="h-5 w-5 text-[#F8A5B8]" />
              </div>
              <div className="flex-1">
                <p className="text-sm text-[#5A5A5A]">Avg Order Value</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">${stats.avg_order_value?.toFixed(2) || '0.00'}</p>
              </div>
              {stats.aov_change !== 0 && (
                <Badge className={stats.aov_change >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                  {stats.aov_change >= 0 ? '+' : ''}{stats.aov_change}%
                </Badge>
              )}
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-[#F8A5B8] rounded-full transition-all" 
                style={{ width: `${Math.min((stats.avg_order_value / 150) * 100, 100)}%` }} 
              />
            </div>
            <p className="text-xs text-[#5A5A5A] mt-2">Target: $150.00</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-green-100">
                <Eye className="h-5 w-5 text-green-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm text-[#5A5A5A]">Conversion Rate</p>
                {stats.visitor_tracking_enabled ? (
                  <p className="text-2xl font-bold text-[#2D2A2E]">{stats.conversion_rate}%</p>
                ) : (
                  <p className="text-lg font-medium text-gray-400">Not tracked</p>
                )}
              </div>
              {stats.visitor_tracking_enabled && stats.conversion_change !== 0 && (
                <Badge className={stats.conversion_change >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                  {stats.conversion_change >= 0 ? '+' : ''}{stats.conversion_change}%
                </Badge>
              )}
            </div>
            {stats.visitor_tracking_enabled ? (
              <>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-green-500 rounded-full" style={{ width: `${Math.min(stats.conversion_rate * 20, 100)}%` }} />
                </div>
                <p className="text-xs text-[#5A5A5A] mt-2">Industry avg: 2.5%</p>
              </>
            ) : (
              <p className="text-xs text-amber-600 mt-2">Enable Google Analytics for conversion tracking</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-blue-100">
                <Users className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-[#5A5A5A]">Returning Customers</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">--</p>
              </div>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full" style={{ width: '0%' }} />
            </div>
            <p className="text-xs text-[#5A5A5A] mt-2">Requires order history tracking</p>
          </CardContent>
        </Card>
      </div>

      {/* Top Products & Recent Orders */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Products - Real Data */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-[#F8A5B8]" />
              Top Products
              <Badge variant="outline" className="ml-2 text-xs">Real Data</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats.top_products && stats.top_products.length > 0 ? (
                stats.top_products.map((product, index) => (
                  <div key={index} className="flex items-center gap-4">
                    <span className={`text-sm font-bold w-6 h-6 rounded-full flex items-center justify-center ${
                      index === 0 ? 'bg-yellow-100 text-yellow-700' : 
                      index === 1 ? 'bg-gray-100 text-gray-700' :
                      index === 2 ? 'bg-orange-100 text-orange-700' : 'bg-gray-50 text-gray-500'
                    }`}>
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-[#2D2A2E] truncate">{product.name}</p>
                      <p className="text-sm text-[#5A5A5A]">{product.sales} units sold</p>
                    </div>
                    <p className="font-bold text-green-600">${product.revenue?.toFixed(2) || '0.00'}</p>
                  </div>
                ))
              ) : (
                <div className="text-center py-8">
                  <Package className="h-10 w-10 text-gray-300 mx-auto mb-2" />
                  <p className="text-[#5A5A5A]">No sales data for this period</p>
                  <p className="text-sm text-gray-400">Completed orders will appear here</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Recent Orders - Real Data */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShoppingCart className="h-5 w-5 text-[#F8A5B8]" />
              Recent Paid Orders
              <Badge variant="outline" className="ml-2 text-xs">Real Data</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats.recent_orders && stats.recent_orders.length > 0 ? (
                stats.recent_orders.map((order, index) => (
                  <div key={index} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div>
                      <p className="font-medium text-[#2D2A2E]">
                        #{order.order_number || order.id?.slice(0, 8) || `ORD-${index + 1}`}
                      </p>
                      <p className="text-sm text-[#5A5A5A]">
                        {order.shipping_address?.first_name || order.customer_name || 'Customer'}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-green-600">${(order.total || 0).toFixed(2)}</p>
                      <p className="text-xs text-[#5A5A5A]">
                        {order.created_at ? new Date(order.created_at).toLocaleDateString() : 'Recent'}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8">
                  <ShoppingCart className="h-10 w-10 text-gray-300 mx-auto mb-2" />
                  <p className="text-[#5A5A5A]">No paid orders yet</p>
                  <p className="text-sm text-gray-400">Completed orders will appear here</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Revenue Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-[#F8A5B8]" />
            Revenue Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="text-center p-4 bg-green-50 rounded-xl">
              <p className="text-sm text-green-700 mb-1">Total Revenue</p>
              <p className="text-2xl font-bold text-green-600">${stats.total_revenue?.toFixed(2) || '0.00'}</p>
              <p className="text-xs text-green-600">All time (paid only)</p>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-xl">
              <p className="text-sm text-blue-700 mb-1">{getPeriodLabel()} Revenue</p>
              <p className="text-2xl font-bold text-blue-600">${stats.period_revenue?.toFixed(2) || '0.00'}</p>
              <p className="text-xs text-blue-600">{stats.period_orders || 0} orders</p>
            </div>
            <div className="text-center p-4 bg-purple-50 rounded-xl">
              <p className="text-sm text-purple-700 mb-1">Avg Order Value</p>
              <p className="text-2xl font-bold text-purple-600">${stats.avg_order_value?.toFixed(2) || '0.00'}</p>
              <p className="text-xs text-purple-600">After discounts</p>
            </div>
            <div className="text-center p-4 bg-orange-50 rounded-xl">
              <p className="text-sm text-orange-700 mb-1">Total Orders</p>
              <p className="text-2xl font-bold text-orange-600">{stats.total_orders || 0}</p>
              <p className="text-xs text-orange-600">Paid & completed</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AnalyticsDashboard;
