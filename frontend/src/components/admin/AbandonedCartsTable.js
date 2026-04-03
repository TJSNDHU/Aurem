import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  ShoppingCart, Clock, Mail, MessageCircle, RefreshCw, 
  ExternalLink, ChevronDown, Search, Filter, MoreVertical,
  Send, Trash2, Eye
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from '../ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Checkbox } from '../ui/checkbox';
import { cn } from '../../lib/utils';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const AbandonedCartsTable = () => {
  const [abandonedCarts, setAbandonedCarts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCarts, setSelectedCarts] = useState([]);
  const [selectedCart, setSelectedCart] = useState(null);
  const [showCartDetails, setShowCartDetails] = useState(false);
  const [sendingRecovery, setSendingRecovery] = useState(null);
  const [stats, setStats] = useState({
    total: 0,
    totalValue: 0,
    recovered: 0,
    recoveredValue: 0
  });

  // Fetch abandoned carts
  const fetchAbandonedCarts = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/admin/abandoned-carts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAbandonedCarts(res.data.carts || []);
      setStats(res.data.stats || stats);
    } catch (error) {
      console.error('Failed to fetch abandoned carts:', error);
      // Show empty state instead of mock data
      setAbandonedCarts([]);
      setStats({
        total: 0,
        totalValue: 0,
        avgValue: 0,
        recovered: 0,
        recoveryRate: 0
      });
      toast.error('Failed to load abandoned carts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAbandonedCarts();
  }, []);

  // Format time ago
  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    return `${diffDays} days ago`;
  };

  // Filter carts by search
  const filteredCarts = useMemo(() => {
    if (!searchQuery) return abandonedCarts;
    const query = searchQuery.toLowerCase();
    return abandonedCarts.filter(cart => 
      cart.customer_email?.toLowerCase().includes(query) ||
      cart.customer_name?.toLowerCase().includes(query) ||
      cart.items.some(item => item.name.toLowerCase().includes(query))
    );
  }, [abandonedCarts, searchQuery]);

  // Send recovery email
  const sendRecoveryEmail = async (cartId) => {
    setSendingRecovery(cartId);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.post(`${API}/admin/abandoned-carts/${cartId}/send-recovery-email`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Recovery email sent!');
      fetchAbandonedCarts();
    } catch (error) {
      toast.error('Failed to send recovery email');
    } finally {
      setSendingRecovery(null);
    }
  };

  // Send WhatsApp recovery
  const sendWhatsAppRecovery = async (cartId) => {
    setSendingRecovery(cartId);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.post(`${API}/admin/abandoned-carts/${cartId}/send-whatsapp`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('WhatsApp recovery sent!');
      fetchAbandonedCarts();
    } catch (error) {
      toast.error('Failed to send WhatsApp message');
    } finally {
      setSendingRecovery(null);
    }
  };

  // Delete cart
  const deleteCart = async (cartId) => {
    if (!confirm('Are you sure you want to delete this abandoned cart?')) return;
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/admin/abandoned-carts/${cartId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Cart deleted');
      fetchAbandonedCarts();
    } catch (error) {
      toast.error('Failed to delete cart');
    }
  };

  // Toggle select all
  const toggleSelectAll = () => {
    if (selectedCarts.length === filteredCarts.length && filteredCarts.length > 0) {
      setSelectedCarts([]);
    } else {
      setSelectedCarts(filteredCarts.map(c => c.id));
    }
  };
  
  // Toggle single cart selection
  const toggleCartSelection = (cartId) => {
    setSelectedCarts(prev => {
      if (prev.includes(cartId)) {
        return prev.filter(id => id !== cartId);
      } else {
        return [...prev, cartId];
      }
    });
  };

  // Bulk delete selected carts
  const bulkDelete = async () => {
    if (selectedCarts.length === 0) {
      toast.error('No carts selected');
      return;
    }
    
    if (!confirm(`Are you sure you want to delete ${selectedCarts.length} abandoned cart(s)?`)) return;
    
    const token = localStorage.getItem('reroots_token');
    let successCount = 0;
    let failCount = 0;
    
    for (const cartId of selectedCarts) {
      try {
        await axios.delete(`${API}/admin/abandoned-carts/${cartId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        console.error(`Failed to delete cart ${cartId}:`, error);
        failCount++;
      }
    }
    
    if (successCount > 0) {
      toast.success(`Deleted ${successCount} cart(s)`);
    }
    if (failCount > 0) {
      toast.error(`Failed to delete ${failCount} cart(s)`);
    }
    
    setSelectedCarts([]);
    fetchAbandonedCarts();
  };

  // Bulk send recovery
  const bulkSendRecovery = async (type) => {
    if (selectedCarts.length === 0) {
      toast.error('No carts selected');
      return;
    }
    
    const token = localStorage.getItem('reroots_token');
    let successCount = 0;
    let failCount = 0;
    
    toast.info(`Sending ${type} recovery to ${selectedCarts.length} carts...`);
    
    for (const cartId of selectedCarts) {
      try {
        const endpoint = type === 'email' 
          ? `${API}/admin/abandoned-carts/${cartId}/send-recovery-email`
          : `${API}/admin/abandoned-carts/${cartId}/send-whatsapp`;
        await axios.post(endpoint, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        console.error(`Failed to send ${type} to cart ${cartId}:`, error);
        failCount++;
      }
    }
    
    if (successCount > 0) {
      toast.success(`Sent ${type} to ${successCount} cart(s)`);
    }
    if (failCount > 0) {
      toast.error(`Failed to send to ${failCount} cart(s)`);
    }
    
    setSelectedCarts([]);
    fetchAbandonedCarts();
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">Abandoned Carts</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.total}</p>
              </div>
              <ShoppingCart className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">Total Value</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">${stats.totalValue.toFixed(2)}</p>
              </div>
              <span className="text-2xl">💰</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">Recovered</p>
                <p className="text-2xl font-bold text-green-600">{stats.recovered}</p>
              </div>
              <span className="text-2xl">✅</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">Recovered Value</p>
                <p className="text-2xl font-bold text-green-600">${stats.recoveredValue.toFixed(2)}</p>
              </div>
              <span className="text-2xl">💵</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Table Card */}
      <Card>
        <CardHeader className="border-b">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <CardTitle className="flex items-center gap-2">
              <ShoppingCart className="h-5 w-5 text-orange-500" />
              Abandoned Checkouts
            </CardTitle>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search carts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 w-64"
                />
              </div>
              <Button variant="outline" size="icon" onClick={fetchAbandonedCarts}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
          
          {/* Bulk Actions */}
          {selectedCarts.length > 0 && (
            <div className="flex items-center gap-3 mt-4 p-3 bg-[#F8A5B8]/10 border border-[#F8A5B8]/30 rounded-lg">
              <span className="text-sm font-semibold text-[#2D2A2E]">
                {selectedCarts.length} cart{selectedCarts.length > 1 ? 's' : ''} selected
              </span>
              <div className="flex gap-2 ml-auto">
                <Button size="sm" variant="outline" onClick={() => bulkSendRecovery('email')}>
                  <Mail className="h-4 w-4 mr-1" /> Send Email
                </Button>
                <Button size="sm" variant="outline" onClick={() => bulkSendRecovery('whatsapp')} className="text-green-600 border-green-300 hover:bg-green-50">
                  <MessageCircle className="h-4 w-4 mr-1" /> Send WhatsApp
                </Button>
                <Button size="sm" variant="outline" onClick={bulkDelete} className="text-red-600 border-red-300 hover:bg-red-50">
                  <Trash2 className="h-4 w-4 mr-1" /> Delete Selected
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setSelectedCarts([])}>
                  Clear Selection
                </Button>
              </div>
            </div>
          )}
        </CardHeader>
        
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-[#F8A5B8]" />
            </div>
          ) : filteredCarts.length === 0 ? (
            <div className="text-center py-12 text-[#5A5A5A]">
              <ShoppingCart className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No abandoned carts found</p>
              <p className="text-sm">Carts abandoned for more than 1 hour will appear here</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left">
                      <Checkbox 
                        checked={selectedCarts.length === filteredCarts.length && filteredCarts.length > 0}
                        onCheckedChange={toggleSelectAll}
                        className="data-[state=checked]:bg-[#F8A5B8] data-[state=checked]:border-[#F8A5B8]"
                      />
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Checkout</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Items</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredCarts.map((cart) => (
                    <tr 
                      key={cart.id} 
                      className={cn(
                        "hover:bg-gray-50 transition-colors cursor-pointer",
                        selectedCarts.includes(cart.id) && "bg-[#F8A5B8]/10 hover:bg-[#F8A5B8]/15"
                      )}
                      onClick={() => toggleCartSelection(cart.id)}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <Checkbox 
                          checked={selectedCarts.includes(cart.id)}
                          onCheckedChange={() => toggleCartSelection(cart.id)}
                          className="data-[state=checked]:bg-[#F8A5B8] data-[state=checked]:border-[#F8A5B8]"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <button 
                          onClick={() => {
                            setSelectedCart(cart);
                            setShowCartDetails(true);
                          }}
                          className="text-blue-600 hover:underline font-medium"
                        >
                          #{cart.id.slice(-6)}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 text-sm text-gray-600">
                          <Clock className="h-3 w-3" />
                          {formatTimeAgo(cart.abandoned_at)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-[#2D2A2E]">{cart.customer_name || 'Guest'}</p>
                          <p className="text-sm text-gray-500">{cart.customer_email || 'No email'}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm">
                          {cart.items.length} item{cart.items.length > 1 ? 's' : ''}
                          <p className="text-gray-500 truncate max-w-[150px]">
                            {cart.items.map(i => i.name).join(', ')}
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-medium">
                        ${cart.total.toFixed(2)} {cart.currency}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          {cart.recovery_email_sent && (
                            <Badge variant="outline" className="text-xs w-fit">
                              <Mail className="h-3 w-3 mr-1" /> Email sent
                            </Badge>
                          )}
                          {cart.recovery_whatsapp_sent && (
                            <Badge variant="outline" className="text-xs w-fit bg-green-50 text-green-700">
                              <MessageCircle className="h-3 w-3 mr-1" /> WhatsApp sent
                            </Badge>
                          )}
                          {!cart.recovery_email_sent && !cart.recovery_whatsapp_sent && (
                            <Badge variant="outline" className="text-xs w-fit text-orange-600 bg-orange-50">
                              Not contacted
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => {
                              setSelectedCart(cart);
                              setShowCartDetails(true);
                            }}>
                              <Eye className="h-4 w-4 mr-2" /> View Details
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {cart.customer_email && (
                              <DropdownMenuItem 
                                onClick={() => sendRecoveryEmail(cart.id)}
                                disabled={sendingRecovery === cart.id}
                              >
                                <Mail className="h-4 w-4 mr-2" /> 
                                {sendingRecovery === cart.id ? 'Sending...' : 'Send Recovery Email'}
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem 
                              onClick={() => sendWhatsAppRecovery(cart.id)}
                              disabled={sendingRecovery === cart.id}
                            >
                              <MessageCircle className="h-4 w-4 mr-2" /> 
                              Send WhatsApp
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem 
                              onClick={() => deleteCart(cart.id)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4 mr-2" /> Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cart Details Dialog */}
      <Dialog open={showCartDetails} onOpenChange={setShowCartDetails}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Abandoned Cart #{selectedCart?.id?.slice(-6)}</DialogTitle>
          </DialogHeader>
          {selectedCart && (
            <div className="space-y-4">
              {/* Customer Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Customer</p>
                  <p className="font-medium">{selectedCart.customer_name || 'Guest'}</p>
                  <p className="text-sm text-gray-600">{selectedCart.customer_email || 'No email'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Location</p>
                  <p className="font-medium">
                    {selectedCart.shipping_address 
                      ? `${selectedCart.shipping_address.city}, ${selectedCart.shipping_address.province}`
                      : 'Unknown'}
                  </p>
                </div>
              </div>

              {/* Cart Items */}
              <div>
                <p className="text-sm text-gray-500 mb-2">Cart Items</p>
                <div className="border rounded-lg divide-y">
                  {selectedCart.items.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-4 p-3">
                      <div className="w-12 h-12 bg-gray-100 rounded flex items-center justify-center">
                        <ShoppingCart className="h-6 w-6 text-gray-400" />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium">{item.name}</p>
                        <p className="text-sm text-gray-500">Qty: {item.quantity}</p>
                      </div>
                      <p className="font-medium">${item.price.toFixed(2)}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Total */}
              <div className="flex justify-between items-center pt-4 border-t">
                <span className="font-medium">Total</span>
                <span className="text-xl font-bold">${selectedCart.total.toFixed(2)} {selectedCart.currency}</span>
              </div>

              {/* Recovery Actions */}
              <div className="flex gap-2 pt-4">
                {selectedCart.customer_email && (
                  <Button 
                    onClick={() => sendRecoveryEmail(selectedCart.id)}
                    disabled={sendingRecovery === selectedCart.id}
                  >
                    <Mail className="h-4 w-4 mr-2" />
                    Send Recovery Email
                  </Button>
                )}
                <Button 
                  variant="outline"
                  onClick={() => sendWhatsAppRecovery(selectedCart.id)}
                  disabled={sendingRecovery === selectedCart.id}
                  className="bg-green-50 text-green-700 border-green-200 hover:bg-green-100"
                >
                  <MessageCircle className="h-4 w-4 mr-2" />
                  Send WhatsApp
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AbandonedCartsTable;
