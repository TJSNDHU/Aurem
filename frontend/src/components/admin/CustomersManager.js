import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAdminBrand } from './useAdminBrand';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

// Virtualized Table
import VirtualizedCustomersTable from './VirtualizedCustomersTable';

// Icons
import { 
  Loader2, Users, Mail, Gift, Search, Eye, Send, 
  ChevronRight, Calendar, DollarSign, ShoppingBag
} from 'lucide-react';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const CustomersManager = () => {
  const { isLaVela } = useAdminBrand();
  const activeBrand = isLaVela ? 'lavela' : 'reroots';
  
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerDetails, setCustomerDetails] = useState(null);
  const [selectedCustomers, setSelectedCustomers] = useState([]);
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [offerData, setOfferData] = useState({
    subject: "Special Offer Just For You! 🎁",
    title: "Exclusive Discount",
    message: "As a valued customer, enjoy this exclusive discount!",
    discount_code: "",
    discount_percent: 15,
    is_exclusive: true,
    expires_at: ""
  });
  const [sendingOffer, setSendingOffer] = useState(false);
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    loadCustomers();
  }, [activeBrand]);

  const loadCustomers = () => {
    setLoading(true);
    axios.get(`${API}/admin/customers?brand=${activeBrand}`, { headers })
      .then(res => setCustomers(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const viewCustomerDetails = async (customerId) => {
    try {
      const res = await axios.get(`${API}/admin/customers/${customerId}`, { headers });
      setCustomerDetails(res.data);
      setSelectedCustomer(customerId);
    } catch (error) {
      toast.error("Failed to load customer details");
    }
  };

  const sendOffer = async () => {
    if (selectedCustomers.length === 0) {
      toast.error("Please select at least one customer");
      return;
    }
    setSendingOffer(true);
    try {
      await axios.post(`${API}/admin/offers/send`, {
        ...offerData,
        recipient_ids: selectedCustomers
      }, { headers });
      toast.success(`Offer sent to ${selectedCustomers.length} customers!`);
      setShowOfferModal(false);
      setSelectedCustomers([]);
    } catch (error) {
      toast.error("Failed to send offer");
    } finally {
      setSendingOffer(false);
    }
  };

  const filteredCustomers = customers.filter(c => 
    c.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.first_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.last_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelectCustomer = useCallback((customerId, checked) => {
    if (checked) {
      setSelectedCustomers(prev => [...prev, customerId]);
    } else {
      setSelectedCustomers(prev => prev.filter(id => id !== customerId));
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" style={{ minHeight: '400px' }}>
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
          <Users className="h-6 w-6" />
          Customer Management
        </h2>
        <div className="flex gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input 
              placeholder="Search customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 w-64"
            />
          </div>
          <Button 
            onClick={() => setShowOfferModal(true)}
            disabled={selectedCustomers.length === 0}
          >
            <Gift className="h-4 w-4 mr-2" />
            Send Offer ({selectedCustomers.length})
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">Total Customers</p>
                <p className="text-2xl font-bold">{customers.length}</p>
              </div>
              <Users className="h-8 w-8 text-[#F8A5B8]" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">With Orders</p>
                <p className="text-2xl font-bold">{customers.filter(c => c.order_count > 0).length}</p>
              </div>
              <ShoppingBag className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">Total Revenue</p>
                <p className="text-2xl font-bold">${customers.reduce((sum, c) => sum + (c.total_spent || 0), 0).toFixed(0)}</p>
              </div>
              <DollarSign className="h-8 w-8 text-[#C9A86C]" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-[#5A5A5A]">This Month</p>
                <p className="text-2xl font-bold">{customers.filter(c => {
                  const created = new Date(c.created_at);
                  const now = new Date();
                  return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear();
                }).length}</p>
              </div>
              <Calendar className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Customer List - Virtualized */}
      <VirtualizedCustomersTable
        customers={filteredCustomers}
        loading={false}
        selectedCustomers={selectedCustomers}
        onSelectCustomer={handleSelectCustomer}
        onViewCustomer={viewCustomerDetails}
        maxHeight={500}
      />

      {/* Send Offer Modal */}
      <Dialog open={showOfferModal} onOpenChange={setShowOfferModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Send Exclusive Offer</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Subject Line</Label>
              <Input 
                value={offerData.subject}
                onChange={(e) => setOfferData({...offerData, subject: e.target.value})}
              />
            </div>
            <div>
              <Label>Offer Title</Label>
              <Input 
                value={offerData.title}
                onChange={(e) => setOfferData({...offerData, title: e.target.value})}
              />
            </div>
            <div>
              <Label>Message</Label>
              <Textarea 
                value={offerData.message}
                onChange={(e) => setOfferData({...offerData, message: e.target.value})}
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Discount Code</Label>
                <Input 
                  value={offerData.discount_code}
                  onChange={(e) => setOfferData({...offerData, discount_code: e.target.value.toUpperCase()})}
                  placeholder="SAVE15"
                />
              </div>
              <div>
                <Label>Discount %</Label>
                <Input 
                  type="number"
                  value={offerData.discount_percent}
                  onChange={(e) => setOfferData({...offerData, discount_percent: parseInt(e.target.value)})}
                />
              </div>
            </div>
            <p className="text-sm text-[#5A5A5A]">
              Sending to {selectedCustomers.length} selected customers
            </p>
            <Button onClick={sendOffer} disabled={sendingOffer} className="w-full">
              {sendingOffer ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
              Send Offer
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Customer Details Modal */}
      <Dialog open={!!selectedCustomer} onOpenChange={() => setSelectedCustomer(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Customer Details</DialogTitle>
          </DialogHeader>
          {customerDetails ? (
            <div className="space-y-4">
              <div>
                <p className="font-medium text-lg">
                  {customerDetails.first_name} {customerDetails.last_name}
                </p>
                <p className="text-[#5A5A5A]">{customerDetails.email}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-sm text-[#5A5A5A]">Total Orders</p>
                  <p className="text-xl font-bold">{customerDetails.order_count || 0}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-sm text-[#5A5A5A]">Total Spent</p>
                  <p className="text-xl font-bold">${customerDetails.total_spent?.toFixed(2) || '0.00'}</p>
                </div>
              </div>
              <div>
                <p className="text-sm text-[#5A5A5A]">Member Since</p>
                <p>{new Date(customerDetails.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          ) : (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CustomersManager;
