import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Switch } from '../ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Checkbox } from '../ui/checkbox';

// Email & SMS Offers Manager Components
import EmailOffersManager from './EmailOffersManager';
import SMSOffersManager from './SMSOffersManager';

// Icons
import { 
  Loader2, Plus, Trash2, Gift, Tag, Users, Send, Mail, 
  Calendar, Percent, DollarSign, Copy, Check, RefreshCw,
  Settings, Crown, UserPlus, Edit2, ToggleLeft, ToggleRight,
  MessageCircle
} from 'lucide-react';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const OffersManager = () => {
  const [offers, setOffers] = useState([]);
  const [discountCodes, setDiscountCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeOfferTab, setActiveOfferTab] = useState("auto");
  const [showCreateOffer, setShowCreateOffer] = useState(false);
  const [showCreateDiscount, setShowCreateDiscount] = useState(false);
  const [subscribers, setSubscribers] = useState([]);
  const [selectedSubscribers, setSelectedSubscribers] = useState([]);
  
  // Edit discount state
  const [editingDiscount, setEditingDiscount] = useState(null);
  const [showEditDiscount, setShowEditDiscount] = useState(false);
  
  // Auto-discounts state
  const [autoDiscounts, setAutoDiscounts] = useState({
    founder_discount_enabled: false,
    founder_discount_percent: 50,
    founder_discount_label: "Founder's Launch Subsidy",
    first_purchase_discount_enabled: false,
    first_purchase_discount_percent: 10,
    voucher_gate_enabled: false,
    voucher_gate_threshold: 10
  });
  const [savingAutoDiscount, setSavingAutoDiscount] = useState(null);
  
  // New offer form
  const [newOffer, setNewOffer] = useState({
    subject: "Special Offer Just For You! 🎁",
    title: "Exclusive Discount",
    message: "As a valued customer, we're giving you an exclusive discount!",
    discount_code: "",
    discount_percent: 15,
    is_exclusive: true,
    expires_at: ""
  });
  
  // New discount code form
  const [newDiscount, setNewDiscount] = useState({
    code: "",
    discount_percent: 10,
    discount_amount: 0,
    min_order: 0,
    max_uses: "",
    expires_at: ""
  });

  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [offersRes, codesRes, subsRes, autoDiscountsRes] = await Promise.all([
        axios.get(`${API}/admin/offers`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/discount-codes`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/subscribers`, { headers }).catch(() => ({ data: { subscribers: [] } })),
        axios.get(`${API}/admin/store-settings/auto-discounts`, { headers }).catch(() => ({ data: {} }))
      ]);
      setOffers(Array.isArray(offersRes.data) ? offersRes.data : []);
      setDiscountCodes(Array.isArray(codesRes.data) ? codesRes.data : []);
      // API returns { subscribers: [], total: 0 } - extract the array
      const subscribersData = subsRes.data?.subscribers || subsRes.data || [];
      setSubscribers(Array.isArray(subscribersData) ? subscribersData : []);
      // Set auto-discounts
      if (autoDiscountsRes.data) {
        setAutoDiscounts(prev => ({ ...prev, ...autoDiscountsRes.data }));
      }
    } catch (error) {
      console.error('Failed to load offers data:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateAutoDiscount = async (field, value) => {
    setSavingAutoDiscount(field);
    try {
      await axios.put(`${API}/admin/store-settings/auto-discounts`, {
        [field]: value
      }, { headers });
      setAutoDiscounts(prev => ({ ...prev, [field]: value }));
      toast.success("Auto-discount updated!");
    } catch (error) {
      toast.error("Failed to update auto-discount");
    }
    setSavingAutoDiscount(null);
  };

  const createOffer = async () => {
    try {
      await axios.post(`${API}/admin/offers`, newOffer, { headers });
      toast.success("Offer created!");
      setShowCreateOffer(false);
      loadData();
    } catch (error) {
      toast.error("Failed to create offer");
    }
  };

  const createDiscountCode = async () => {
    try {
      const response = await axios.post(`${API}/admin/discount-codes`, newDiscount, { headers });
      toast.success(`Discount code ${response.data?.code || 'created'} created!`);
      setShowCreateDiscount(false);
      setNewDiscount({
        code: "",
        discount_percent: 10,
        discount_amount: 0,
        min_order: 0,
        max_uses: "",
        expires_at: ""
      });
      loadData();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || "Failed to create discount code";
      toast.error(errorMsg);
    }
  };

  // Generate random code based on discount percentage
  const generateRandomCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    const randomPart = Array.from({length: 5}, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    const code = `SAVE${newDiscount.discount_percent || 10}${randomPart}`;
    setNewDiscount({...newDiscount, code});
  };

  // Generate random code for edit modal
  const generateEditCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    const randomPart = Array.from({length: 5}, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    const code = `SAVE${editingDiscount?.discount_percent || 10}${randomPart}`;
    setEditingDiscount({...editingDiscount, code});
  };

  // Open edit modal
  const openEditDiscount = (code) => {
    setEditingDiscount({
      ...code,
      discount_percent: code.discount_percent || code.discount_value || 0,
      min_order: code.min_order_amount || code.min_order || 0,
      max_uses: code.max_uses || "",
      expires_at: code.expires_at || code.end_date || ""
    });
    setShowEditDiscount(true);
  };

  // Update discount code
  const updateDiscountCode = async () => {
    if (!editingDiscount) return;
    try {
      await axios.put(`${API}/admin/discount-codes/${editingDiscount.id}`, editingDiscount, { headers });
      toast.success(`Discount code ${editingDiscount.code} updated!`);
      setShowEditDiscount(false);
      setEditingDiscount(null);
      loadData();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || "Failed to update discount code";
      toast.error(errorMsg);
    }
  };

  // Toggle discount code active status
  const toggleDiscountStatus = async (code) => {
    try {
      const newStatus = !code.is_active;
      await axios.put(`${API}/admin/discount-codes/${code.id}`, {
        ...code,
        is_active: newStatus
      }, { headers });
      toast.success(`Code ${code.code} ${newStatus ? 'activated' : 'deactivated'}`);
      loadData();
    } catch (error) {
      toast.error("Failed to toggle status");
    }
  };

  const deleteDiscountCode = async (codeId) => {
    try {
      await axios.delete(`${API}/admin/discount-codes/${codeId}`, { headers });
      toast.success("Discount code deleted");
      loadData();
    } catch (error) {
      toast.error("Failed to delete code");
    }
  };

  const sendOffer = async () => {
    if (selectedSubscribers.length === 0) {
      toast.error("Please select at least one recipient");
      return;
    }
    try {
      await axios.post(`${API}/admin/offers/send`, {
        ...newOffer,
        recipient_ids: selectedSubscribers
      }, { headers });
      toast.success(`Offer sent to ${selectedSubscribers.length} subscribers!`);
      setShowCreateOffer(false);
      setSelectedSubscribers([]);
    } catch (error) {
      toast.error("Failed to send offer");
    }
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success("Code copied!");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Offers & Promotions</h2>
        <Button variant="outline" onClick={loadData} className="text-[#2D2A2E] border-gray-300">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Tabs value={activeOfferTab} onValueChange={setActiveOfferTab}>
        <TabsList>
          <TabsTrigger value="auto">
            <Settings className="h-4 w-4 mr-2" />
            Auto-Discounts
          </TabsTrigger>
          <TabsTrigger value="exclusive">
            <Mail className="h-4 w-4 mr-2" />
            Email Offers
          </TabsTrigger>
          <TabsTrigger value="sms">
            <MessageCircle className="h-4 w-4 mr-2" />
            SMS Offers
          </TabsTrigger>
          <TabsTrigger value="codes">
            <Tag className="h-4 w-4 mr-2" />
            Discount Codes
          </TabsTrigger>
        </TabsList>

        {/* Auto-Discounts Tab */}
        <TabsContent value="auto">
          <Card className="border-2 border-dashed border-amber-200 bg-gradient-to-br from-amber-50/50 to-white">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center">
                  <Settings className="w-5 h-5 text-white" />
                </div>
                <div>
                  <CardTitle>System Auto-Discounts</CardTitle>
                  <p className="text-sm text-gray-500">These discounts apply automatically at checkout (no code needed)</p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Founder's Launch Subsidy */}
                <div className={`p-4 rounded-xl border-2 transition-all ${
                  autoDiscounts.founder_discount_enabled 
                    ? 'border-green-500 bg-green-50' 
                    : 'border-gray-200 bg-gray-50'
                }`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        autoDiscounts.founder_discount_enabled ? 'bg-green-500' : 'bg-gray-400'
                      }`}>
                        <Crown className="w-4 h-4 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-sm">Founder's Launch Subsidy</p>
                        <p className="text-xs text-gray-500">Auto-applied to ALL orders</p>
                      </div>
                    </div>
                    {savingAutoDiscount === 'founder_discount_enabled' ? (
                      <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    ) : (
                      <Switch
                        checked={autoDiscounts.founder_discount_enabled}
                        onCheckedChange={(checked) => updateAutoDiscount('founder_discount_enabled', checked)}
                      />
                    )}
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="relative flex-1">
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={autoDiscounts.founder_discount_percent}
                        onChange={(e) => setAutoDiscounts(prev => ({
                          ...prev,
                          founder_discount_percent: parseFloat(e.target.value) || 0
                        }))}
                        className={`text-2xl font-bold h-12 pr-10 ${
                          autoDiscounts.founder_discount_enabled ? 'text-green-600 border-green-300' : 'text-gray-400'
                        }`}
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">%</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => updateAutoDiscount('founder_discount_percent', autoDiscounts.founder_discount_percent)}
                      disabled={savingAutoDiscount === 'founder_discount_percent'}
                      className="h-12 px-3"
                    >
                      {savingAutoDiscount === 'founder_discount_percent' ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Check className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-gray-500">
                    {autoDiscounts.founder_discount_enabled 
                      ? '✓ Active on all checkout orders' 
                      : '○ Currently disabled'}
                  </p>
                </div>

                {/* First Purchase Discount */}
                <div className={`p-4 rounded-xl border-2 transition-all ${
                  autoDiscounts.first_purchase_discount_enabled 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-200 bg-gray-50'
                }`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        autoDiscounts.first_purchase_discount_enabled ? 'bg-blue-500' : 'bg-gray-400'
                      }`}>
                        <UserPlus className="w-4 h-4 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-sm">First Purchase Discount</p>
                        <p className="text-xs text-gray-500">For new customers only</p>
                      </div>
                    </div>
                    {savingAutoDiscount === 'first_purchase_discount_enabled' ? (
                      <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    ) : (
                      <Switch
                        checked={autoDiscounts.first_purchase_discount_enabled}
                        onCheckedChange={(checked) => updateAutoDiscount('first_purchase_discount_enabled', checked)}
                      />
                    )}
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="relative flex-1">
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={autoDiscounts.first_purchase_discount_percent}
                        onChange={(e) => setAutoDiscounts(prev => ({
                          ...prev,
                          first_purchase_discount_percent: parseFloat(e.target.value) || 0
                        }))}
                        className={`text-2xl font-bold h-12 pr-10 ${
                          autoDiscounts.first_purchase_discount_enabled ? 'text-blue-600 border-blue-300' : 'text-gray-400'
                        }`}
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">%</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => updateAutoDiscount('first_purchase_discount_percent', autoDiscounts.first_purchase_discount_percent)}
                      disabled={savingAutoDiscount === 'first_purchase_discount_percent'}
                      className="h-12 px-3"
                    >
                      {savingAutoDiscount === 'first_purchase_discount_percent' ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Check className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-gray-500">
                    {autoDiscounts.first_purchase_discount_enabled 
                      ? '✓ Active for first-time buyers' 
                      : '○ Currently disabled'}
                  </p>
                </div>

                {/* Voucher Gate */}
                <div className={`p-4 rounded-xl border-2 transition-all ${
                  autoDiscounts.voucher_gate_enabled 
                    ? 'border-purple-500 bg-purple-50' 
                    : 'border-gray-200 bg-gray-50'
                }`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        autoDiscounts.voucher_gate_enabled ? 'bg-purple-500' : 'bg-gray-400'
                      }`}>
                        <Gift className="w-4 h-4 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-sm">Voucher Gate</p>
                        <p className="text-xs text-gray-500">Requires code at checkout</p>
                      </div>
                    </div>
                    {savingAutoDiscount === 'voucher_gate_enabled' ? (
                      <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    ) : (
                      <Switch
                        checked={autoDiscounts.voucher_gate_enabled}
                        onCheckedChange={(checked) => updateAutoDiscount('voucher_gate_enabled', checked)}
                      />
                    )}
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="relative flex-1">
                      <Input
                        type="number"
                        min="1"
                        max="1000"
                        value={autoDiscounts.voucher_gate_threshold}
                        onChange={(e) => setAutoDiscounts(prev => ({
                          ...prev,
                          voucher_gate_threshold: parseInt(e.target.value) || 1
                        }))}
                        className={`text-2xl font-bold h-12 pr-16 ${
                          autoDiscounts.voucher_gate_enabled ? 'text-purple-600 border-purple-300' : 'text-gray-400'
                        }`}
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">uses</span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => updateAutoDiscount('voucher_gate_threshold', autoDiscounts.voucher_gate_threshold)}
                      disabled={savingAutoDiscount === 'voucher_gate_threshold'}
                      className="h-12 px-3"
                    >
                      {savingAutoDiscount === 'voucher_gate_threshold' ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Check className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-gray-500">
                    {autoDiscounts.voucher_gate_enabled 
                      ? '✓ Codes required at checkout' 
                      : '○ Currently disabled'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Email Offers Tab - Full Feature Manager */}
        <TabsContent value="exclusive">
          <EmailOffersManager />
        </TabsContent>

        {/* SMS Offers Tab - WHAPI Integration */}
        <TabsContent value="sms">
          <SMSOffersManager />
        </TabsContent>

        {/* Discount Codes Tab */}
        <TabsContent value="codes">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Discount Codes</CardTitle>
              <Dialog open={showCreateDiscount} onOpenChange={setShowCreateDiscount}>
                <DialogTrigger asChild>
                  <Button className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                    <Plus className="h-4 w-4 mr-2" />
                    Create Code
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create Discount Code</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <Label>Code (leave empty to auto-generate)</Label>
                      <div className="flex gap-2">
                        <Input 
                          value={newDiscount.code}
                          onChange={(e) => setNewDiscount({...newDiscount, code: e.target.value.toUpperCase()})}
                          placeholder="Auto-generated if empty"
                          className="flex-1"
                        />
                        <Button 
                          type="button" 
                          variant="outline" 
                          onClick={generateRandomCode}
                          className="shrink-0"
                        >
                          Generate
                        </Button>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Discount %</Label>
                        <Input 
                          type="number"
                          value={newDiscount.discount_percent}
                          onChange={(e) => setNewDiscount({...newDiscount, discount_percent: parseInt(e.target.value)})}
                        />
                      </div>
                      <div>
                        <Label>Min Order ($)</Label>
                        <Input 
                          type="number"
                          value={newDiscount.min_order}
                          onChange={(e) => setNewDiscount({...newDiscount, min_order: parseInt(e.target.value)})}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Max Uses (blank = unlimited)</Label>
                        <Input 
                          type="number"
                          value={newDiscount.max_uses}
                          onChange={(e) => setNewDiscount({...newDiscount, max_uses: e.target.value})}
                        />
                      </div>
                      <div>
                        <Label>Expires</Label>
                        <Input 
                          type="date"
                          value={newDiscount.expires_at}
                          onChange={(e) => setNewDiscount({...newDiscount, expires_at: e.target.value})}
                        />
                      </div>
                    </div>
                    <Button onClick={createDiscountCode} className="w-full bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                      Create Code
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              {discountCodes.length === 0 ? (
                <div className="text-center py-8">
                  <Tag className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                  <p className="text-[#5A5A5A]">No discount codes yet</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {discountCodes.map((code) => (
                    <div key={code.id} className={`flex items-center justify-between p-4 border rounded-lg ${!code.is_active ? 'opacity-60 bg-gray-50' : ''}`}>
                      <div className="flex items-center gap-4">
                        <code className="bg-gray-100 px-3 py-1 rounded font-mono">{code.code}</code>
                        <Badge variant="outline">{code.discount_percent || code.discount_value || 0}% OFF</Badge>
                        {code.min_order_amount > 0 && (
                          <span className="text-xs text-gray-500">Min ${code.min_order_amount}</span>
                        )}
                        {code.uses_count !== undefined && (
                          <span className="text-sm text-[#5A5A5A]">{code.uses_count || 0} uses</span>
                        )}
                        <Badge variant={code.is_active !== false ? "default" : "secondary"} className={code.is_active !== false ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-600"}>
                          {code.is_active !== false ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => toggleDiscountStatus(code)}
                          title={code.is_active !== false ? "Deactivate" : "Activate"}
                        >
                          {code.is_active !== false ? (
                            <ToggleRight className="h-4 w-4 text-green-600" />
                          ) : (
                            <ToggleLeft className="h-4 w-4 text-gray-400" />
                          )}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openEditDiscount(code)} title="Edit">
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => copyCode(code.code)} title="Copy">
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" className="text-red-500" onClick={() => deleteDiscountCode(code.id)} title="Delete">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Edit Discount Dialog */}
          <Dialog open={showEditDiscount} onOpenChange={setShowEditDiscount}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Edit Discount Code</DialogTitle>
              </DialogHeader>
              {editingDiscount && (
                <div className="space-y-4">
                  <div>
                    <Label>Code</Label>
                    <div className="flex gap-2">
                      <Input 
                        value={editingDiscount.code || ""}
                        onChange={(e) => setEditingDiscount({...editingDiscount, code: e.target.value.toUpperCase()})}
                        placeholder="SAVE20"
                        className="flex-1"
                      />
                      <Button 
                        type="button" 
                        variant="outline" 
                        onClick={generateEditCode}
                        className="shrink-0"
                      >
                        Generate
                      </Button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Discount %</Label>
                      <Input 
                        type="number"
                        value={editingDiscount.discount_percent || ""}
                        onChange={(e) => setEditingDiscount({...editingDiscount, discount_percent: parseFloat(e.target.value) || 0})}
                        placeholder="10"
                      />
                    </div>
                    <div>
                      <Label>Min Order ($)</Label>
                      <Input 
                        type="number"
                        value={editingDiscount.min_order || ""}
                        onChange={(e) => setEditingDiscount({...editingDiscount, min_order: parseFloat(e.target.value) || 0})}
                        placeholder="0"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Max Uses (blank = unlimited)</Label>
                      <Input 
                        type="number"
                        value={editingDiscount.max_uses || ""}
                        onChange={(e) => setEditingDiscount({...editingDiscount, max_uses: e.target.value})}
                        placeholder="Unlimited"
                      />
                    </div>
                    <div>
                      <Label>Expires</Label>
                      <Input 
                        type="date"
                        value={editingDiscount.expires_at ? editingDiscount.expires_at.split('T')[0] : ""}
                        onChange={(e) => setEditingDiscount({...editingDiscount, expires_at: e.target.value})}
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <Label>Active Status</Label>
                      <p className="text-sm text-gray-500">Enable or disable this code</p>
                    </div>
                    <Switch 
                      checked={editingDiscount.is_active !== false}
                      onCheckedChange={(checked) => setEditingDiscount({...editingDiscount, is_active: checked})}
                    />
                  </div>
                  <Button onClick={updateDiscountCode} className="w-full bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                    Save Changes
                  </Button>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default OffersManager;
