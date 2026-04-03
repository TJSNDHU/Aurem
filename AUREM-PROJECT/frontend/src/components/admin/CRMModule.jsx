import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Search, 
  Star, 
  RefreshCw, 
  MessageCircle, 
  Mail, 
  Phone,
  DollarSign,
  ShoppingBag,
  Calendar,
  FileText,
  Tag,
  X,
  ChevronRight,
  User,
  ExternalLink
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const CRMModule = () => {
  const [customers, setCustomers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchCustomers();
  }, []);

  const getAuthHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem('reroots_token')}`
  });

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/admin/customers`, {
        headers: getAuthHeaders()
      });
      setCustomers(response.data || []);
    } catch (error) {
      console.error('Failed to fetch customers:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomerDetail = async (email) => {
    setDetailLoading(true);
    try {
      const response = await axios.get(`${API}/api/admin/customers/${encodeURIComponent(email)}`, {
        headers: getAuthHeaders()
      });
      setSelected(response.data);
    } catch (error) {
      console.error('Failed to fetch customer detail:', error);
    } finally {
      setDetailLoading(false);
    }
  };

  const updateNotes = async (email, notes) => {
    try {
      await axios.patch(`${API}/api/admin/customers/${encodeURIComponent(email)}/notes`, { notes }, {
        headers: getAuthHeaders()
      });
    } catch (error) {
      console.error('Failed to update notes:', error);
    }
  };

  const filtered = customers.filter(c => {
    const matchSearch = 
      (c.name?.toLowerCase() || '').includes(search.toLowerCase()) ||
      (c.email?.toLowerCase() || '').includes(search.toLowerCase());
    
    const matchFilter = 
      filter === 'all' ? true :
      filter === 'vip' ? c.vip_status :
      filter === 'repeat' ? (c.total_orders || 0) >= 2 :
      filter === 'whatsapp' ? c.whatsapp_opted_in : true;
    
    return matchSearch && matchFilter;
  });

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('en-CA');
    } catch {
      return dateStr;
    }
  };

  const statusColor = {
    pending: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    fulfilled: 'bg-green-100 text-green-800',
    shipped: 'bg-purple-100 text-purple-800',
    delivered: 'bg-green-100 text-green-800',
    refunded: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-800',
    return_requested: 'bg-orange-100 text-orange-800'
  };

  return (
    <div className="flex h-[calc(100vh-120px)]" data-testid="crm-module">
      {/* Left Panel - Customer List */}
      <div className="w-[380px] border-r border-gray-200 overflow-y-auto bg-white">
        <div className="p-4 border-b sticky top-0 bg-white z-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-[#2D2A2E]">Customers</h2>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={fetchCustomers}
              data-testid="refresh-customers-btn"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
              data-testid="customer-search-input"
            />
          </div>

          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            {[
              { key: 'all', label: 'All' },
              { key: 'vip', label: '⭐ VIP' },
              { key: 'repeat', label: '🔄 Repeat' },
              { key: 'whatsapp', label: '💬 WhatsApp' }
            ].map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  filter === f.key 
                    ? 'bg-[#2D2A2E] text-white' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
                data-testid={`filter-${f.key}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Customer List */}
        <div className="p-3">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading customers...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No customers found</div>
          ) : (
            filtered.map(c => (
              <div
                key={c.email}
                onClick={() => fetchCustomerDetail(c.email)}
                className={`p-3 rounded-lg mb-2 cursor-pointer border transition-all ${
                  selected?.customer?.email === c.email 
                    ? 'border-[#F8A5B8] bg-pink-50' 
                    : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                }`}
                data-testid={`customer-row-${c.email}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-[#2D2A2E] flex items-center justify-center text-white text-sm font-medium">
                      {c.name?.charAt(0)?.toUpperCase() || 'C'}
                    </div>
                    <div>
                      <div className="font-medium text-sm text-[#2D2A2E] flex items-center gap-1">
                        {c.name || 'Unknown'}
                        {c.vip_status && <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />}
                      </div>
                      <div className="text-xs text-gray-500">{c.email}</div>
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-2 text-xs">
                  <span className="text-green-600 font-semibold">
                    LTV: ${(c.ltv || 0).toFixed(2)}
                  </span>
                  <span className="text-gray-500">
                    {c.total_orders || 0} orders
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Panel - Customer Detail */}
      {selected ? (
        <div className="flex-1 overflow-y-auto bg-gray-50 p-6" data-testid="customer-detail-panel">
          {detailLoading ? (
            <div className="text-center py-12 text-gray-500">Loading customer details...</div>
          ) : (
            <>
              {/* Header */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
                    {selected.customer?.name || 'Customer'}
                    {selected.customer?.vip_status && (
                      <Badge className="bg-yellow-100 text-yellow-800 border-0">
                        <Star className="h-3 w-3 mr-1 fill-yellow-500" /> VIP
                      </Badge>
                    )}
                  </h2>
                  <p className="text-gray-500">{selected.customer?.email}</p>
                  {selected.customer?.phone && (
                    <p className="text-gray-500 text-sm">{selected.customer?.phone}</p>
                  )}
                </div>

                {/* Quick Actions */}
                <div className="flex gap-2">
                  {selected.customer?.whatsapp_opted_in && selected.customer?.whatsapp_phone && (
                    <a
                      href={`https://wa.me/${selected.customer.whatsapp_phone?.replace(/\D/g, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 px-3 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600"
                    >
                      <MessageCircle className="h-4 w-4" /> WhatsApp
                    </a>
                  )}
                  <a
                    href={`mailto:${selected.customer?.email}`}
                    className="flex items-center gap-1 px-3 py-2 bg-[#2D2A2E] text-white rounded-lg text-sm font-medium hover:bg-[#3d393d]"
                  >
                    <Mail className="h-4 w-4" /> Email
                  </a>
                </div>
              </div>

              {/* Stats Cards */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                {[
                  { 
                    label: 'Lifetime Value', 
                    value: `$${(selected.customer?.ltv || 0).toFixed(2)}`, 
                    icon: DollarSign,
                    color: 'text-green-600' 
                  },
                  { 
                    label: 'Total Orders', 
                    value: selected.customer?.total_orders || 0, 
                    icon: ShoppingBag,
                    color: 'text-[#2D2A2E]' 
                  },
                  { 
                    label: 'First Order', 
                    value: formatDate(selected.customer?.first_order_date), 
                    icon: Calendar,
                    color: 'text-gray-600' 
                  },
                  { 
                    label: 'Last Order', 
                    value: formatDate(selected.customer?.last_order_date), 
                    icon: Calendar,
                    color: 'text-gray-600' 
                  }
                ].map(stat => (
                  <Card key={stat.label} className="border-0 shadow-sm">
                    <CardContent className="p-4 text-center">
                      <stat.icon className={`h-5 w-5 mx-auto mb-2 ${stat.color}`} />
                      <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
                      <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Additional Info */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                {/* Shipping Address */}
                <Card className="border-0 shadow-sm">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-gray-600">Shipping Address</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 text-sm">
                    <p>{selected.customer?.shipping_address || '—'}</p>
                    <p>
                      {selected.customer?.shipping_city}
                      {selected.customer?.shipping_province && `, ${selected.customer.shipping_province}`}
                      {selected.customer?.shipping_postal_code && ` ${selected.customer.shipping_postal_code}`}
                    </p>
                  </CardContent>
                </Card>

                {/* Acquisition & Loyalty */}
                <Card className="border-0 shadow-sm">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-gray-600">Customer Info</CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0 text-sm space-y-1">
                    <p><span className="text-gray-500">Source:</span> {selected.customer?.acquisition_source || 'Direct'}</p>
                    <p><span className="text-gray-500">Loyalty Points:</span> {selected.customer?.loyalty_points || 0} Roots</p>
                    <p><span className="text-gray-500">Store Credit:</span> ${(selected.customer?.store_credit || 0).toFixed(2)}</p>
                  </CardContent>
                </Card>
              </div>

              {/* Notes */}
              <Card className="border-0 shadow-sm mb-6">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-gray-600">Admin Notes</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <textarea
                    defaultValue={selected.customer?.notes || ''}
                    onBlur={(e) => updateNotes(selected.customer?.email, e.target.value)}
                    placeholder="Add notes about this customer..."
                    className="w-full h-20 p-3 border rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#F8A5B8]"
                    data-testid="customer-notes"
                  />
                </CardContent>
              </Card>

              {/* Order History */}
              <Card className="border-0 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-lg">Order History</CardTitle>
                </CardHeader>
                <CardContent>
                  {selected.orders?.length === 0 ? (
                    <p className="text-gray-500 text-center py-4">No orders yet</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="bg-[#2D2A2E] text-white text-left text-sm">
                            <th className="px-3 py-2 rounded-tl-lg">Order ID</th>
                            <th className="px-3 py-2">Date</th>
                            <th className="px-3 py-2">Total</th>
                            <th className="px-3 py-2">Status</th>
                            <th className="px-3 py-2">Tracking</th>
                            <th className="px-3 py-2">Receipt</th>
                            <th className="px-3 py-2 rounded-tr-lg">Label</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selected.orders?.map((order, i) => (
                            <tr 
                              key={order.order_id} 
                              className={`text-sm border-b ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}
                            >
                              <td className="px-3 py-3 font-medium">#{order.order_id}</td>
                              <td className="px-3 py-3">{formatDate(order.created_at)}</td>
                              <td className="px-3 py-3 text-green-600 font-medium">
                                ${(order.total || 0).toFixed(2)}
                              </td>
                              <td className="px-3 py-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  statusColor[order.status] || statusColor.pending
                                }`}>
                                  {order.status || 'pending'}
                                </span>
                              </td>
                              <td className="px-3 py-3">
                                {order.tracking_number ? (
                                  <a
                                    href={`/track?order=${order.order_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[#F8A5B8] hover:underline flex items-center gap-1"
                                  >
                                    {order.tracking_number}
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-3">
                                {order.receipt_url || order.order_id ? (
                                  <a
                                    href={order.receipt_url || `${API}/api/receipt/${order.order_id}?email=${selected.customer?.email}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="px-2 py-1 bg-[#2D2A2E] text-white rounded text-xs hover:bg-[#3d393d]"
                                  >
                                    PDF
                                  </a>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-3">
                                {order.label_url ? (
                                  <a
                                    href={order.label_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="px-2 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
                                  >
                                    Label
                                  </a>
                                ) : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center bg-gray-50">
          <div className="text-center text-gray-400">
            <User className="h-16 w-16 mx-auto mb-4 opacity-50" />
            <p>Select a customer to view details</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default CRMModule;
