import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { 
  Gift, TrendingUp, Users, DollarSign, Clock, 
  CheckCircle, ShoppingCart, AlertTriangle, Loader2,
  Search, RefreshCw, Send, Mail, MessageSquare, Phone
} from 'lucide-react';
import { useAdminBrand } from './useAdminBrand';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const GiftTrackingDashboard = () => {
  const { activeBrand } = useAdminBrand();
  const pointsName = activeBrand === 'lavela' ? 'Glow Points' : 'Roots';
  
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/admin/gift-tracking`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setData(res.data);
    } catch (error) {
      toast.error('Failed to load gift tracking data');
      console.error(error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getStatusBadge = (status) => {
    const styles = {
      pending: { bg: 'bg-amber-100', text: 'text-amber-800', icon: Clock },
      in_progress: { bg: 'bg-blue-100', text: 'text-blue-800', icon: Loader2 },
      claimed: { bg: 'bg-emerald-100', text: 'text-emerald-800', icon: CheckCircle },
      converted: { bg: 'bg-purple-100', text: 'text-purple-800', icon: ShoppingCart },
      expired: { bg: 'bg-gray-100', text: 'text-gray-800', icon: AlertTriangle }
    };
    const style = styles[status] || styles.pending;
    const Icon = style.icon;
    
    return (
      <Badge className={`${style.bg} ${style.text} gap-1`}>
        <Icon className="h-3 w-3" />
        {status.replace('_', ' ')}
      </Badge>
    );
  };

  const getNotificationIcons = (notifications) => {
    if (!notifications) return null;
    return (
      <div className="flex gap-1">
        {notifications.email && (
          <span className="text-blue-500" title="Email sent">
            <Mail className="h-3.5 w-3.5" />
          </span>
        )}
        {notifications.sms && (
          <span className="text-green-500" title="SMS sent">
            <Phone className="h-3.5 w-3.5" />
          </span>
        )}
        {notifications.whatsapp && (
          <span className="text-emerald-500" title="WhatsApp sent">
            <MessageSquare className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
    );
  };

  const filteredGifts = data?.recent_gifts?.filter(gift => {
    const matchesSearch = 
      gift.sender_email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      gift.recipient_email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      gift.recipient_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      gift.sender_name?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = filterStatus === 'all' || gift.status === filterStatus;
    
    return matchesSearch && matchesStatus;
  }) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  const stats = data?.stats || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Gift className="h-6 w-6 text-[#F8A5B8]" />
            Gift {pointsName} Tracking
          </h2>
          <p className="text-[#5A5A5A] text-sm mt-1">
            Track gift conversions and revenue from point gifting
          </p>
        </div>
        <Button onClick={fetchData} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-[#F8A5B8]/10">
                <Send className="h-5 w-5 text-[#F8A5B8]" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.total_gifts || 0}</p>
                <p className="text-xs text-[#5A5A5A]">Total Gifts</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-100">
                <Clock className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.pending_count || 0}</p>
                <p className="text-xs text-[#5A5A5A]">Pending</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-100">
                <CheckCircle className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.claimed_count || 0}</p>
                <p className="text-xs text-[#5A5A5A]">Claimed ({stats.claim_rate || 0}%)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-100">
                <ShoppingCart className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.converted_count || 0}</p>
                <p className="text-xs text-[#5A5A5A]">Converted ({stats.conversion_rate || 0}%)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-emerald-50 to-green-50 border-emerald-200">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-500">
                <DollarSign className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-700">${(stats.total_revenue || 0).toFixed(2)}</p>
                <p className="text-xs text-emerald-600">Revenue from Gifts</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Funnel Visualization */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-[#D4AF37]" />
            Gift Conversion Funnel
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-2">
            {/* Sent */}
            <div className="flex-1 text-center">
              <div className="h-20 bg-[#F8A5B8]/20 rounded-lg flex items-center justify-center mb-2 relative">
                <span className="text-2xl font-bold text-[#F8A5B8]">{stats.total_gifts || 0}</span>
              </div>
              <p className="text-sm text-[#5A5A5A]">Sent</p>
            </div>
            <div className="text-gray-300">→</div>
            
            {/* Claimed */}
            <div className="flex-1 text-center">
              <div className="h-16 bg-emerald-100 rounded-lg flex items-center justify-center mb-2">
                <span className="text-2xl font-bold text-emerald-600">{(stats.claimed_count || 0) + (stats.converted_count || 0)}</span>
              </div>
              <p className="text-sm text-[#5A5A5A]">Claimed</p>
              <p className="text-xs text-emerald-600">{stats.claim_rate || 0}%</p>
            </div>
            <div className="text-gray-300">→</div>
            
            {/* Converted */}
            <div className="flex-1 text-center">
              <div className="h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-2">
                <span className="text-2xl font-bold text-purple-600">{stats.converted_count || 0}</span>
              </div>
              <p className="text-sm text-[#5A5A5A]">Bought</p>
              <p className="text-xs text-purple-600">{stats.conversion_rate || 0}%</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Gifts Table */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Recent Gifts</CardTitle>
            <div className="flex gap-2">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9 w-48"
                />
              </div>
              
              {/* Filter */}
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="border rounded-md px-3 py-2 text-sm"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="claimed">Claimed</option>
                <option value="converted">Converted</option>
                <option value="expired">Expired</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-2 font-medium text-[#5A5A5A]">Sender</th>
                  <th className="text-left py-3 px-2 font-medium text-[#5A5A5A]">Recipient</th>
                  <th className="text-center py-3 px-2 font-medium text-[#5A5A5A]">Points</th>
                  <th className="text-center py-3 px-2 font-medium text-[#5A5A5A]">Notified</th>
                  <th className="text-center py-3 px-2 font-medium text-[#5A5A5A]">Status</th>
                  <th className="text-right py-3 px-2 font-medium text-[#5A5A5A]">Order Value</th>
                  <th className="text-right py-3 px-2 font-medium text-[#5A5A5A]">Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredGifts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-[#5A5A5A]">
                      {searchTerm || filterStatus !== 'all' 
                        ? 'No gifts match your filters' 
                        : 'No gifts sent yet'}
                    </td>
                  </tr>
                ) : (
                  filteredGifts.map((gift) => (
                    <tr key={gift.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2">
                        <div>
                          <p className="font-medium text-[#2D2A2E]">{gift.sender_name}</p>
                          <p className="text-xs text-[#5A5A5A]">{gift.sender_email}</p>
                        </div>
                      </td>
                      <td className="py-3 px-2">
                        <div>
                          <p className="font-medium text-[#2D2A2E]">{gift.recipient_name || '-'}</p>
                          <p className="text-xs text-[#5A5A5A]">
                            {gift.recipient_email || gift.recipient_phone || '-'}
                          </p>
                        </div>
                      </td>
                      <td className="py-3 px-2 text-center">
                        <span className="font-semibold text-[#D4AF37]">{gift.points_amount}</span>
                        <span className="text-xs text-[#5A5A5A] block">${gift.points_value?.toFixed(2)}</span>
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex justify-center">
                          {getNotificationIcons(gift.notifications_sent)}
                        </div>
                      </td>
                      <td className="py-3 px-2 text-center">
                        {getStatusBadge(gift.status)}
                      </td>
                      <td className="py-3 px-2 text-right">
                        {gift.order_value ? (
                          <span className="font-semibold text-emerald-600">
                            ${gift.order_value.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-[#5A5A5A]">-</span>
                        )}
                      </td>
                      <td className="py-3 px-2 text-right text-[#5A5A5A] text-xs">
                        {new Date(gift.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default GiftTrackingDashboard;
