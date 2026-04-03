import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { 
  RefreshCw, 
  CreditCard, 
  Truck, 
  Package, 
  CheckCircle2, 
  Clock, 
  AlertCircle,
  ExternalLink,
  Search,
  DollarSign,
  MapPin,
  ArrowRight,
  Zap,
  Eye,
  FileText,
  Printer,
  Download,
  CheckSquare,
  ArrowDown,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useWebSocket } from '../../contexts/WebSocketContext';
import { useAdminBrand } from './useAdminBrand';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Status badge configurations
const paymentStatusConfig = {
  paid: { color: 'bg-green-100 text-green-800', icon: CheckCircle2, label: 'Paid' },
  pending: { color: 'bg-yellow-100 text-yellow-800', icon: Clock, label: 'Pending' },
  failed: { color: 'bg-red-100 text-red-800', icon: AlertCircle, label: 'Failed' },
  refunded: { color: 'bg-gray-100 text-gray-800', icon: RefreshCw, label: 'Refunded' },
};

const shippingStatusConfig = {
  pending: { color: 'bg-gray-100 text-gray-800', icon: Clock, label: 'Pending' },
  processing: { color: 'bg-blue-100 text-blue-800', icon: Package, label: 'Processing' },
  shipped: { color: 'bg-purple-100 text-purple-800', icon: Truck, label: 'Shipped' },
  in_transit: { color: 'bg-indigo-100 text-indigo-800', icon: Truck, label: 'In Transit' },
  delivered: { color: 'bg-green-100 text-green-800', icon: CheckCircle2, label: 'Delivered' },
  cancelled: { color: 'bg-red-100 text-red-800', icon: AlertCircle, label: 'Cancelled' },
};

const paymentMethodIcons = {
  paypal: '💳',
  paypal_api: '🅿️',
  bambora_td: '🏦',
  stripe: '💳',
  etransfer: '📧',
  manual: '✋',
};

const OrderFlowDashboard = () => {
  const { isLaVela } = useAdminBrand();
  const activeBrand = isLaVela ? 'lavela' : 'reroots';
  
  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState({
    totalOrders: 0,
    pendingPayments: 0,
    awaitingShipment: 0,
    inTransit: 0,
    delivered: 0,
    totalRevenue: 0,
    labelsToprint: 0,
    labelsPrinted: 0,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [printedLabels, setPrintedLabels] = useState(() => {
    // Load printed labels from localStorage
    const saved = localStorage.getItem('reroots_printed_labels');
    return saved ? JSON.parse(saved) : [];
  });
  
  // Pagination state
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 20,
    total_count: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false
  });
  
  const { lastMessage } = useWebSocket();
  const headers = { Authorization: `Bearer ${localStorage.getItem('reroots_token')}` };

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPagination(prev => ({ ...prev, page: 1 })); // Reset to page 1 on search
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchOrders = useCallback(async (page = pagination.page) => {
    try {
      // Build query params
      const params = new URLSearchParams({
        page: page.toString(),
        limit: pagination.limit.toString(),
        sort_by: 'created_at',
        sort_order: 'desc',
        brand: activeBrand
      });
      
      if (debouncedSearch) {
        params.append('search', debouncedSearch);
      }
      
      if (activeTab !== 'all') {
        params.append('status', activeTab);
      }
      
      const res = await axios.get(`${API}/admin/orders?${params.toString()}`, { headers });
      const ordersData = res.data.orders || res.data || [];
      const paginationData = res.data.pagination || {};
      
      setOrders(ordersData);
      setPagination(prev => ({
        ...prev,
        ...paginationData,
        page: paginationData.page || page
      }));
      
      // Calculate stats from current page (for display purposes)
      // Note: For accurate total stats, you'd need a separate stats endpoint
      const paid = ordersData.filter(o => o.payment_status === 'paid');
      const ordersWithLabels = ordersData.filter(o => o.shipping_label_url);
      const unprintedLabels = ordersWithLabels.filter(o => !printedLabels.includes(o.id));
      const printedLabelOrders = ordersWithLabels.filter(o => printedLabels.includes(o.id));
      
      setStats({
        totalOrders: paginationData.total_count || ordersData.length,
        pendingPayments: ordersData.filter(o => o.payment_status === 'pending').length,
        awaitingShipment: paid.filter(o => !o.tracking_number && o.order_status !== 'cancelled').length,
        inTransit: ordersData.filter(o => ['shipped', 'in_transit'].includes(o.order_status)).length,
        delivered: ordersData.filter(o => o.order_status === 'delivered').length,
        totalRevenue: paid.reduce((sum, o) => sum + (parseFloat(o.total) || 0), 0),
        labelsToPrint: unprintedLabels.length,
        labelsPrinted: printedLabelOrders.length,
      });
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      toast.error('Failed to load orders');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [pagination.page, pagination.limit, debouncedSearch, activeTab, printedLabels]);

  // Fetch on mount and when dependencies change
  useEffect(() => {
    fetchOrders();
  }, [debouncedSearch, activeTab, activeBrand]);
  
  // Handle page change
  const handlePageChange = useCallback((newPage) => {
    setPagination(prev => ({ ...prev, page: newPage }));
    fetchOrders(newPage);
  }, [fetchOrders]);

  // Save printed labels to localStorage
  useEffect(() => {
    localStorage.setItem('reroots_printed_labels', JSON.stringify(printedLabels));
  }, [printedLabels]);

  // Listen for real-time updates with enhanced order ticker
  useEffect(() => {
    if (lastMessage) {
      const { type, data } = lastMessage;
      if (type === 'new_order') {
        // Refresh the orders list
        fetchOrders();
        
        // Play notification sound (optional - can add sound file)
        try {
          const audio = new Audio('/sounds/order-notification.mp3');
          audio.volume = 0.5;
          audio.play().catch(() => {}); // Ignore if sound fails
        } catch (e) {}
        
        // Show prominent order ticker notification
        toast.success(
          <div className="flex items-center gap-3">
            <div className="bg-green-100 rounded-full p-2">
              <span className="text-2xl">💰</span>
            </div>
            <div>
              <p className="font-bold text-green-700">New Order!</p>
              <p className="text-sm text-gray-600">#{data?.order_number}</p>
              <p className="text-lg font-semibold text-green-600">${data?.total?.toFixed(2)}</p>
            </div>
          </div>,
          {
            duration: 8000,
            position: 'top-right',
          }
        );
      } else if (type === 'order_shipped') {
        fetchOrders();
        toast.success(`📦 Order Shipped: #${data?.order_number}`, {
          description: `Tracking: ${data?.tracking_number || 'Pending'}`,
          duration: 5000,
        });
      } else if (type === 'payment_received') {
        fetchOrders();
        toast.success(`💳 Payment Received: #${data?.order_number}`, {
          description: `Amount: $${data?.amount?.toFixed(2) || 'N/A'}`,
          duration: 5000,
        });
      }
    }
  }, [lastMessage, fetchOrders]);

  // Mark label as printed
  const markLabelPrinted = useCallback((orderId) => {
    setPrintedLabels(prev => {
      if (!prev.includes(orderId)) {
        return [...prev, orderId];
      }
      return prev;
    });
    toast.success('Label marked as printed');
  }, []);

  // Mark label as unprinted (move back to queue)
  const markLabelUnprinted = useCallback((orderId) => {
    setPrintedLabels(prev => prev.filter(id => id !== orderId));
    toast.info('Label moved back to print queue');
  }, []);

  // Print and mark as printed
  const printLabel = useCallback((order) => {
    if (order.shipping_label_url) {
      window.open(order.shipping_label_url, '_blank');
      markLabelPrinted(order.id);
    }
  }, [markLabelPrinted]);

  // Print all unprinted labels
  const printAllLabels = useCallback(() => {
    const unprintedOrders = orders.filter(o => o.shipping_label_url && !printedLabels.includes(o.id));
    if (unprintedOrders.length === 0) {
      toast.info('No labels to print');
      return;
    }
    unprintedOrders.forEach((order, index) => {
      setTimeout(() => {
        window.open(order.shipping_label_url, '_blank');
        markLabelPrinted(order.id);
      }, index * 500); // Stagger opening to avoid popup blockers
    });
    toast.success(`Opening ${unprintedOrders.length} labels for printing`);
  }, [orders, printedLabels, markLabelPrinted]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchOrders();
  };

  const handleTrackShipment = async (trackingNumber) => {
    if (!trackingNumber) return;
    
    try {
      const res = await axios.get(`${API}/shipping/track/${trackingNumber}`, { headers });
      toast.success(`Tracking Status: ${res.data.status || 'Unknown'}`, {
        description: res.data.location || 'Tracking info retrieved',
      });
    } catch (error) {
      // Open external tracking
      window.open(`https://www.google.com/search?q=${trackingNumber}+tracking`, '_blank');
    }
  };

  // Since we're using server-side pagination and filtering, 
  // orders are already filtered - just use them directly
  const filteredOrders = orders;

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('en-CA', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const PaymentStatusBadge = ({ status }) => {
    const config = paymentStatusConfig[status] || paymentStatusConfig.pending;
    const Icon = config.icon;
    return (
      <Badge className={`${config.color} flex items-center gap-1`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </Badge>
    );
  };

  const ShippingStatusBadge = ({ status }) => {
    const config = shippingStatusConfig[status] || shippingStatusConfig.pending;
    const Icon = config.icon;
    return (
      <Badge className={`${config.color} flex items-center gap-1`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#00843D]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-500" />
            Live Order Flow Dashboard
          </h2>
          <p className="text-gray-500 mt-1">
            Real-time PayPal + FlagShip integrated order tracking
          </p>
        </div>
        <Button onClick={handleRefresh} disabled={refreshing} variant="outline">
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-blue-600 font-medium">Total Orders</p>
                <p className="text-2xl font-bold text-blue-800">{stats.totalOrders}</p>
              </div>
              <Package className="w-8 h-8 text-blue-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-yellow-50 to-yellow-100 border-yellow-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-yellow-600 font-medium">Pending Payment</p>
                <p className="text-2xl font-bold text-yellow-800">{stats.pendingPayments}</p>
              </div>
              <Clock className="w-8 h-8 text-yellow-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-orange-600 font-medium">Awaiting Ship</p>
                <p className="text-2xl font-bold text-orange-800">{stats.awaitingShipment}</p>
              </div>
              <Package className="w-8 h-8 text-orange-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-purple-600 font-medium">In Transit</p>
                <p className="text-2xl font-bold text-purple-800">{stats.inTransit}</p>
              </div>
              <Truck className="w-8 h-8 text-purple-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-green-600 font-medium">Delivered</p>
                <p className="text-2xl font-bold text-green-800">{stats.delivered}</p>
              </div>
              <CheckCircle2 className="w-8 h-8 text-green-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-emerald-600 font-medium">Revenue</p>
                <p className="text-2xl font-bold text-emerald-800">${stats.totalRevenue.toFixed(0)}</p>
              </div>
              <DollarSign className="w-8 h-8 text-emerald-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Flow Visualization */}
      <Card className="bg-gradient-to-r from-gray-50 to-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Order Flow Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between py-4">
            {/* Step 1: Order Placed */}
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center mb-2">
                <CreditCard className="w-6 h-6 text-blue-600" />
              </div>
              <span className="text-xs font-medium text-gray-600">Order Placed</span>
              <span className="text-lg font-bold text-blue-600">{stats.totalOrders}</span>
            </div>
            
            <ArrowRight className="w-6 h-6 text-gray-300" />
            
            {/* Step 2: Payment */}
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-yellow-100 flex items-center justify-center mb-2">
                <DollarSign className="w-6 h-6 text-yellow-600" />
              </div>
              <span className="text-xs font-medium text-gray-600">Payment</span>
              <span className="text-lg font-bold text-yellow-600">
                {stats.totalOrders - stats.pendingPayments} ✓
              </span>
            </div>
            
            <ArrowRight className="w-6 h-6 text-gray-300" />
            
            {/* Step 3: Auto-Ship */}
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center mb-2">
                <Zap className="w-6 h-6 text-orange-600" />
              </div>
              <span className="text-xs font-medium text-gray-600">Auto-Ship</span>
              <span className="text-lg font-bold text-orange-600">
                {stats.inTransit + stats.delivered}
              </span>
            </div>
            
            <ArrowRight className="w-6 h-6 text-gray-300" />
            
            {/* Step 4: In Transit */}
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center mb-2">
                <Truck className="w-6 h-6 text-purple-600" />
              </div>
              <span className="text-xs font-medium text-gray-600">In Transit</span>
              <span className="text-lg font-bold text-purple-600">{stats.inTransit}</span>
            </div>
            
            <ArrowRight className="w-6 h-6 text-gray-300" />
            
            {/* Step 5: Delivered */}
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-2">
                <CheckCircle2 className="w-6 h-6 text-green-600" />
              </div>
              <span className="text-xs font-medium text-gray-600">Delivered</span>
              <span className="text-lg font-bold text-green-600">{stats.delivered}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Print Labels Queue */}
      <Card className="border-2 border-orange-200 bg-gradient-to-r from-orange-50 to-amber-50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                <Printer className="w-5 h-5 text-orange-600" />
              </div>
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  Shipping Labels Queue
                  {stats.labelsToPrint > 0 && (
                    <Badge className="bg-orange-500 text-white animate-pulse">
                      {stats.labelsToPrint} to print
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  New labels appear at top • Printed labels move down
                </CardDescription>
              </div>
            </div>
            {stats.labelsToPrint > 0 && (
              <Button 
                onClick={printAllLabels} 
                className="bg-orange-500 hover:bg-orange-600 text-white"
                data-testid="print-all-labels-btn"
              >
                <Printer className="w-4 h-4 mr-2" />
                Print All ({stats.labelsToPrint})
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {/* Labels To Print - New ones at top */}
          {(() => {
            const unprintedOrders = orders
              .filter(o => o.shipping_label_url && !printedLabels.includes(o.id))
              .sort((a, b) => new Date(b.created_at) - new Date(a.created_at)); // Newest first
            
            const printedOrders = orders
              .filter(o => o.shipping_label_url && printedLabels.includes(o.id))
              .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            
            if (unprintedOrders.length === 0 && printedOrders.length === 0) {
              return (
                <div className="text-center py-8 text-gray-500">
                  <Package className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p className="font-medium">No shipping labels available</p>
                  <p className="text-sm">Labels will appear here after orders are paid and auto-shipped</p>
                </div>
              );
            }
            
            return (
              <div className="space-y-4">
                {/* Unprinted Labels - Priority Section */}
                {unprintedOrders.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <Badge variant="outline" className="bg-orange-100 text-orange-700 border-orange-300">
                        <Clock className="w-3 h-3 mr-1" />
                        To Print ({unprintedOrders.length})
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      {unprintedOrders.map((order, index) => (
                        <div 
                          key={order.id}
                          className={`flex items-center justify-between p-4 bg-white rounded-lg border-2 border-orange-200 shadow-sm hover:shadow-md transition-all ${
                            index === 0 ? 'ring-2 ring-orange-400 ring-offset-2' : ''
                          }`}
                          data-testid={`label-to-print-${order.order_number}`}
                        >
                          <div className="flex items-center gap-4">
                            {index === 0 && (
                              <Badge className="bg-orange-500 text-white text-xs">NEW</Badge>
                            )}
                            <div>
                              <p className="font-bold text-gray-900">
                                #{order.order_number || order.id?.slice(0, 8)}
                              </p>
                              <p className="text-sm text-gray-500">
                                {order.shipping_address?.first_name} {order.shipping_address?.last_name}
                              </p>
                              <p className="text-xs text-gray-400">
                                {order.shipping_address?.city}, {order.shipping_address?.province}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-right">
                              <p className="text-sm font-medium text-gray-600">
                                {order.shipping_carrier || 'FlagShip'}
                              </p>
                              <p className="text-xs text-gray-400">
                                {order.tracking_number?.slice(0, 15)}...
                              </p>
                            </div>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => window.open(order.shipping_label_url, '_blank')}
                                title="Download Label"
                                data-testid={`download-label-${order.order_number}`}
                              >
                                <Download className="w-4 h-4" />
                              </Button>
                              <Button
                                size="sm"
                                className="bg-orange-500 hover:bg-orange-600 text-white"
                                onClick={() => printLabel(order)}
                                title="Print & Mark as Printed"
                                data-testid={`print-label-${order.order_number}`}
                              >
                                <Printer className="w-4 h-4 mr-1" />
                                Print
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Divider with arrow */}
                {unprintedOrders.length > 0 && printedOrders.length > 0 && (
                  <div className="flex items-center justify-center py-2">
                    <div className="flex-1 border-t border-gray-300"></div>
                    <div className="px-4 flex items-center text-gray-400">
                      <ArrowDown className="w-4 h-4 mr-1" />
                      <span className="text-xs">Printed labels move down</span>
                    </div>
                    <div className="flex-1 border-t border-gray-300"></div>
                  </div>
                )}
                
                {/* Printed Labels - Archive Section */}
                {printedOrders.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <Badge variant="outline" className="bg-green-100 text-green-700 border-green-300">
                        <CheckSquare className="w-3 h-3 mr-1" />
                        Printed ({printedOrders.length})
                      </Badge>
                    </div>
                    <div className="space-y-2 opacity-75">
                      {printedOrders.slice(0, 5).map((order) => (
                        <div 
                          key={order.id}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                          data-testid={`label-printed-${order.order_number}`}
                        >
                          <div className="flex items-center gap-3">
                            <CheckCircle2 className="w-5 h-5 text-green-500" />
                            <div>
                              <p className="font-medium text-gray-700">
                                #{order.order_number || order.id?.slice(0, 8)}
                              </p>
                              <p className="text-xs text-gray-500">
                                {order.shipping_address?.first_name} {order.shipping_address?.last_name} • {order.shipping_carrier}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => window.open(order.shipping_label_url, '_blank')}
                              title="Re-download Label"
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => markLabelUnprinted(order.id)}
                              title="Move back to print queue"
                              className="text-orange-500 hover:text-orange-700"
                            >
                              <RefreshCw className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                      {printedOrders.length > 5 && (
                        <p className="text-center text-sm text-gray-400 py-2">
                          + {printedOrders.length - 5} more printed labels
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </CardContent>
      </Card>

      {/* Orders Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Recent Orders</CardTitle>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search orders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="all">All ({orders.length})</TabsTrigger>
              <TabsTrigger value="pending">Pending ({stats.pendingPayments})</TabsTrigger>
              <TabsTrigger value="paid">Paid ({stats.awaitingShipment})</TabsTrigger>
              <TabsTrigger value="shipped">Shipped ({stats.inTransit})</TabsTrigger>
              <TabsTrigger value="delivered">Delivered ({stats.delivered})</TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab}>
              <div className="rounded-lg border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead>Order</TableHead>
                      <TableHead>Customer</TableHead>
                      <TableHead>Payment</TableHead>
                      <TableHead>Shipping</TableHead>
                      <TableHead>Tracking</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredOrders.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                          No orders found
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredOrders.map((order) => (
                        <TableRow key={order.id} className="hover:bg-gray-50">
                          <TableCell>
                            <div className="font-medium">
                              #{order.order_number || order.id?.slice(0, 8)}
                            </div>
                            <div className="text-xs text-gray-500">
                              {paymentMethodIcons[order.payment_method] || '💳'} {order.payment_method}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="text-sm">
                              {order.shipping_address?.first_name} {order.shipping_address?.last_name}
                            </div>
                            <div className="text-xs text-gray-500">
                              {order.shipping_address?.email}
                            </div>
                          </TableCell>
                          <TableCell>
                            <PaymentStatusBadge status={order.payment_status} />
                          </TableCell>
                          <TableCell>
                            <ShippingStatusBadge status={order.order_status} />
                          </TableCell>
                          <TableCell>
                            {order.tracking_number ? (
                              <button
                                onClick={() => handleTrackShipment(order.tracking_number)}
                                className="text-blue-600 hover:underline text-sm flex items-center gap-1"
                              >
                                {order.tracking_number.slice(0, 12)}...
                                <ExternalLink className="w-3 h-3" />
                              </button>
                            ) : (
                              <span className="text-gray-400 text-sm">-</span>
                            )}
                            {order.shipping_carrier && (
                              <div className="text-xs text-gray-500">{order.shipping_carrier}</div>
                            )}
                          </TableCell>
                          <TableCell>
                            <span className="font-medium">${parseFloat(order.total || 0).toFixed(2)}</span>
                          </TableCell>
                          <TableCell className="text-sm text-gray-500">
                            {formatDate(order.created_at)}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              {order.shipping_label_url && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => window.open(order.shipping_label_url, '_blank')}
                                  title="Download Label"
                                >
                                  <FileText className="w-4 h-4" />
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setSelectedOrder(order)}
                                title="View Details"
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
              
              {/* Pagination Controls */}
              {pagination.total_pages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50 rounded-b-lg">
                  <div className="text-sm text-gray-600">
                    Showing {((pagination.page - 1) * pagination.limit) + 1} - {Math.min(pagination.page * pagination.limit, pagination.total_count)} of {pagination.total_count} orders
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(pagination.page - 1)}
                      disabled={!pagination.has_prev}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      Previous
                    </Button>
                    
                    {/* Page numbers */}
                    <div className="flex items-center gap-1">
                      {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                        let pageNum;
                        if (pagination.total_pages <= 5) {
                          pageNum = i + 1;
                        } else if (pagination.page <= 3) {
                          pageNum = i + 1;
                        } else if (pagination.page >= pagination.total_pages - 2) {
                          pageNum = pagination.total_pages - 4 + i;
                        } else {
                          pageNum = pagination.page - 2 + i;
                        }
                        return (
                          <Button
                            key={pageNum}
                            variant={pageNum === pagination.page ? "default" : "outline"}
                            size="sm"
                            className={`w-8 h-8 p-0 ${pageNum === pagination.page ? 'bg-[#F8A5B8] hover:bg-[#F8A5B8]/90' : ''}`}
                            onClick={() => handlePageChange(pageNum)}
                          >
                            {pageNum}
                          </Button>
                        );
                      })}
                    </div>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePageChange(pagination.page + 1)}
                      disabled={!pagination.has_next}
                    >
                      Next
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Order Detail Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Order #{selectedOrder.order_number || selectedOrder.id?.slice(0, 8)}</CardTitle>
                <CardDescription>
                  {formatDate(selectedOrder.created_at)}
                </CardDescription>
              </div>
              <Button variant="ghost" onClick={() => setSelectedOrder(null)}>✕</Button>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Order Flow Timeline */}
              <div className="space-y-3">
                <h4 className="font-medium text-sm text-gray-700">Order Timeline</h4>
                <div className="flex items-center gap-2 text-sm">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    selectedOrder.created_at ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <Package className="w-4 h-4" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">Order Placed</p>
                    <p className="text-xs text-gray-500">{formatDate(selectedOrder.created_at)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    selectedOrder.payment_status === 'paid' ? 'bg-green-100 text-green-600' : 'bg-yellow-100 text-yellow-600'
                  }`}>
                    <DollarSign className="w-4 h-4" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">Payment {selectedOrder.payment_status === 'paid' ? 'Received' : 'Pending'}</p>
                    <p className="text-xs text-gray-500">
                      {selectedOrder.payment_method} • ${parseFloat(selectedOrder.total || 0).toFixed(2)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    selectedOrder.tracking_number ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <Truck className="w-4 h-4" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">
                      {selectedOrder.tracking_number ? 'Shipped' : 'Awaiting Shipment'}
                    </p>
                    {selectedOrder.tracking_number && (
                      <p className="text-xs text-gray-500">
                        {selectedOrder.shipping_carrier} • {selectedOrder.tracking_number}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    selectedOrder.order_status === 'delivered' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'
                  }`}>
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">
                      {selectedOrder.order_status === 'delivered' ? 'Delivered' : 'Pending Delivery'}
                    </p>
                    {selectedOrder.delivered_at && (
                      <p className="text-xs text-gray-500">{formatDate(selectedOrder.delivered_at)}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Shipping Address */}
              <div className="space-y-2">
                <h4 className="font-medium text-sm text-gray-700 flex items-center gap-2">
                  <MapPin className="w-4 h-4" /> Shipping Address
                </h4>
                <div className="bg-gray-50 p-3 rounded-lg text-sm">
                  <p>{selectedOrder.shipping_address?.first_name} {selectedOrder.shipping_address?.last_name}</p>
                  <p>{selectedOrder.shipping_address?.address_line1 || selectedOrder.shipping_address?.address}</p>
                  <p>
                    {selectedOrder.shipping_address?.city}, {selectedOrder.shipping_address?.province} {selectedOrder.shipping_address?.postal_code}
                  </p>
                  <p className="text-gray-500">{selectedOrder.shipping_address?.email}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-col gap-2">
                {/* Shipping Note (if auto-ship failed) */}
                {selectedOrder.shipping_note && (
                  <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg text-sm text-amber-700">
                    <p className="font-medium">⚠️ {selectedOrder.shipping_note}</p>
                  </div>
                )}
                
                {selectedOrder.tracking_number && (
                  <Button
                    onClick={() => handleTrackShipment(selectedOrder.tracking_number)}
                    className="flex-1"
                  >
                    <Truck className="w-4 h-4 mr-2" />
                    Track Package
                  </Button>
                )}
                {selectedOrder.shipping_label_url && (
                  <Button
                    variant="outline"
                    onClick={() => window.open(selectedOrder.shipping_label_url, '_blank')}
                    className="flex-1"
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Download Label
                  </Button>
                )}
                
                {/* Manual Create Shipping Label button (when no tracking exists and order is paid) */}
                {!selectedOrder.tracking_number && selectedOrder.payment_status === 'paid' && (
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        const token = localStorage.getItem('reroots_admin_token') || localStorage.getItem('reroots_token');
                        const res = await fetch(`${API}/admin/orders/${selectedOrder.id}/create-shipment`, {
                          method: 'POST',
                          headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                          }
                        });
                        const data = await res.json();
                        if (data.success) {
                          toast.success(`Shipping label created! Tracking: ${data.tracking_number}`);
                          fetchOrders(); // Refresh orders
                        } else {
                          toast.error(data.detail || 'Failed to create shipping label');
                        }
                      } catch (err) {
                        toast.error('Failed to create shipping label');
                      }
                    }}
                    className="flex-1 bg-blue-50 text-blue-700 hover:bg-blue-100"
                  >
                    <Package className="w-4 h-4 mr-2" />
                    Create Shipping Label
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default OrderFlowDashboard;
