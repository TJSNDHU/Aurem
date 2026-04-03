import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  Edit,
  Copy,
  Tag,
  Gift,
  Zap,
  ShoppingBag,
  Users,
  Megaphone,
  Sparkles,
  Package,
  Ticket,
  UserPlus,
  Power,
  ToggleLeft,
  ToggleRight,
  Settings,
  ExternalLink
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const API = process.env.REACT_APP_BACKEND_URL 
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : `${window.location.origin}/api`;

// Feature Toggle Card Component
const FeatureToggle = ({ title, description, enabled, onToggle, color, icon: Icon }) => (
  <div className={`p-4 rounded-xl border-2 transition-all ${enabled ? "border-green-400 bg-green-50" : "border-red-300 bg-red-50"}`}>
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="font-semibold text-gray-800">{title}</p>
          <p className="text-xs text-gray-500">{description}</p>
        </div>
      </div>
      <button
        onClick={onToggle}
        className={`px-4 py-2 rounded-full font-semibold text-sm flex items-center gap-2 transition-all ${
          enabled 
            ? "bg-green-500 text-white hover:bg-green-600" 
            : "bg-red-500 text-white hover:bg-red-600"
        }`}
      >
        {enabled ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
        {enabled ? "ON" : "OFF"}
      </button>
    </div>
  </div>
);

const PromotionsCenter = () => {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  
  // Data states
  const [discountCodes, setDiscountCodes] = useState([]);
  const [partnerVouchers, setPartnerVouchers] = useState([]);
  const [storeSettings, setStoreSettings] = useState(null);
  const [partners, setPartners] = useState([]);
  
  // Modal states
  const [showCreateCode, setShowCreateCode] = useState(false);
  const [showCreateVoucher, setShowCreateVoucher] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  
  // Form states
  const [codeForm, setCodeForm] = useState({
    code: "",
    type: "general",
    discount_type: "percentage",
    discount_value: 10,
    description: "",
    min_products: 1,
    min_order_amount: 0,
    max_uses: 0,
    start_date: "",
    end_date: "",
    is_active: true
  });
  
  const [voucherForm, setVoucherForm] = useState({
    partner_id: "",
    code: "",
    discount_type: "percentage",
    discount_value: 20,
    partner_commission: 15,
    min_order: 0,
    max_uses: 0,
    valid_until: "",
    is_active: true
  });

  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  // Fetch all data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [codesRes, settingsRes, partnersRes] = await Promise.all([
        axios.get(`${API}/admin/discount-codes`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/store-settings`, { headers }).catch(() => ({ data: {} })),
        axios.get(`${API}/admin/influencers`, { headers }).catch(() => ({ data: [] }))
      ]);
      
      // Ensure arrays
      const codesData = Array.isArray(codesRes.data) ? codesRes.data : [];
      // Partners API returns { applications: [...], stats: {...} }
      const partnersData = partnersRes.data?.applications || (Array.isArray(partnersRes.data) ? partnersRes.data : []);
      
      setDiscountCodes(codesData);
      setStoreSettings(settingsRes.data || {});
      setPartners(partnersData);
      
      // Extract partner vouchers from partners
      const vouchers = [];
      partnersData.forEach(partner => {
        if (partner.vouchers) {
          partner.vouchers.forEach(v => vouchers.push({ ...v, partner_name: partner.full_name, partner_id: partner.id }));
        }
      });
      setPartnerVouchers(vouchers);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Generate random code
  const generateCode = (prefix = "PROMO") => {
    const random = Math.random().toString(36).substring(2, 6).toUpperCase();
    return `${prefix}${random}`;
  };

  // Toggle feature on/off
  const toggleFeature = async (feature, currentValue) => {
    try {
      const updates = {};
      
      switch(feature) {
        case "firstpurchase":
          updates.first_purchase_discount_enabled = !currentValue;
          break;
        case "referral":
          updates.referral_program = { ...(storeSettings?.referral_program || {}), enabled: !currentValue };
          break;
        case "promo_banner":
          updates.promo_banner_enabled = !currentValue;
          break;
        default:
          return;
      }
      
      await axios.put(`${API}/admin/store-settings`, { ...storeSettings, ...updates }, { headers });
      setStoreSettings({ ...storeSettings, ...updates });
      toast.success(`${feature} ${!currentValue ? "enabled" : "disabled"}`);
    } catch (error) {
      toast.error("Failed to update settings");
    }
  };

  // Create discount code
  const createDiscountCode = async () => {
    if (!codeForm.code) {
      toast.error("Please enter a code");
      return;
    }
    
    try {
      if (editingItem) {
        await axios.put(`${API}/admin/discount-codes/${editingItem.id || editingItem.code}`, {
          ...codeForm,
          code: codeForm.code.toUpperCase(),
          discount_percent: codeForm.discount_type === "percentage" ? codeForm.discount_value : 0,
          discount_amount: codeForm.discount_type === "fixed" ? codeForm.discount_value : 0
        }, { headers });
        toast.success("Code updated!");
      } else {
        await axios.post(`${API}/admin/discount-codes`, {
          ...codeForm,
          code: codeForm.code.toUpperCase(),
          discount_percent: codeForm.discount_type === "percentage" ? codeForm.discount_value : 0,
          discount_amount: codeForm.discount_type === "fixed" ? codeForm.discount_value : 0
        }, { headers });
        toast.success("Code created!");
      }
      
      setShowCreateCode(false);
      setEditingItem(null);
      resetCodeForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save code");
    }
  };

  // Create partner voucher
  const createPartnerVoucher = async () => {
    if (!voucherForm.partner_id || !voucherForm.code) {
      toast.error("Please select a partner and enter a code");
      return;
    }
    
    try {
      await axios.post(`${API}/admin/vouchers`, {
        ...voucherForm,
        code: voucherForm.code.toUpperCase()
      }, { headers });
      toast.success("Voucher created!");
      setShowCreateVoucher(false);
      resetVoucherForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create voucher");
    }
  };

  // Delete code
  const deleteCode = async (code) => {
    if (!window.confirm("Delete this code?")) return;
    try {
      await axios.delete(`${API}/admin/discount-codes/${code.id || code.code}`, { headers });
      toast.success("Code deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete");
    }
  };

  // Toggle code active status
  const toggleCodeActive = async (code) => {
    try {
      await axios.put(`${API}/admin/discount-codes/${code.id || code.code}`, {
        ...code,
        is_active: !code.is_active
      }, { headers });
      fetchData();
      toast.success(code.is_active ? "Code deactivated" : "Code activated");
    } catch (error) {
      toast.error("Failed to update");
    }
  };

  // Reset forms
  const resetCodeForm = () => {
    setCodeForm({
      code: "",
      type: "general",
      discount_type: "percentage",
      discount_value: 10,
      description: "",
      min_products: 1,
      min_order_amount: 0,
      max_uses: 0,
      start_date: "",
      end_date: "",
      is_active: true
    });
  };

  const resetVoucherForm = () => {
    setVoucherForm({
      partner_id: "",
      code: "",
      discount_type: "percentage",
      discount_value: 20,
      partner_commission: 15,
      min_order: 0,
      max_uses: 0,
      valid_until: "",
      is_active: true
    });
  };

  // Copy code
  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success(`"${code}" copied!`);
  };

  // Edit code
  const editCode = (code) => {
    setEditingItem(code);
    setCodeForm({
      code: code.code,
      type: code.type || "general",
      discount_type: code.discount_percent ? "percentage" : "fixed",
      discount_value: code.discount_percent || code.discount_amount || 10,
      description: code.description || "",
      min_products: code.min_products || 1,
      min_order_amount: code.min_order_amount || 0,
      max_uses: code.max_uses || 0,
      start_date: code.start_date || "",
      end_date: code.end_date || "",
      is_active: code.is_active !== false
    });
    setShowCreateCode(true);
  };

  // Get referral reward display
  const getReferralRewardDisplay = () => {
    const rp = storeSettings?.referral_program || {};
    return rp.referrer_reward_label || `$${rp.referrer_reward_value || 10} Store Credit`;
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-[#F8A5B8]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 overflow-x-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-gray-800 flex items-center gap-2">
            <Sparkles className="w-5 h-5 sm:w-6 sm:h-6 text-yellow-500" />
            Promotions Center
          </h2>
          <p className="text-sm sm:text-base text-gray-500">Manage all discounts and offers</p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
        <Card className="bg-gradient-to-br from-green-50 to-white border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Tag className="w-8 h-8 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{discountCodes.filter(c => c.is_active).length}</p>
                <p className="text-xs text-gray-500">Active Codes</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Users className="w-8 h-8 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{partnerVouchers.length}</p>
                <p className="text-xs text-gray-500">Partner Vouchers</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <UserPlus className="w-8 h-8 text-purple-500" />
              <div>
                <p className={`text-2xl font-bold ${storeSettings?.first_purchase_discount_enabled ? "text-green-600" : "text-red-500"}`}>
                  {storeSettings?.first_purchase_discount_enabled ? "ON" : "OFF"}
                </p>
                <p className="text-xs text-gray-500">First Purchase</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-pink-50 to-white border-pink-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Gift className="w-8 h-8 text-pink-500" />
              <div>
                <p className={`text-2xl font-bold ${storeSettings?.referral_program?.enabled !== false ? "text-green-600" : "text-red-500"}`}>
                  {storeSettings?.referral_program?.enabled !== false ? "ON" : "OFF"}
                </p>
                <p className="text-xs text-gray-500">Referral Rewards</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature Toggles Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Power className="w-5 h-5 text-gray-600" />
            Quick Toggles
          </CardTitle>
          <CardDescription>Enable or disable promotional features instantly</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <FeatureToggle
            title="First Purchase Bonus"
            description={`${storeSettings?.first_purchase_discount_percent || 10}% auto-discount for new customers`}
            enabled={storeSettings?.first_purchase_discount_enabled !== false}
            onToggle={() => toggleFeature("firstpurchase", storeSettings?.first_purchase_discount_enabled !== false)}
            color="bg-purple-500"
            icon={UserPlus}
          />
          <FeatureToggle
            title="Referral Rewards"
            description={`Customers earn ${getReferralRewardDisplay()} for referring friends`}
            enabled={storeSettings?.referral_program?.enabled !== false}
            onToggle={() => toggleFeature("referral", storeSettings?.referral_program?.enabled !== false)}
            color="bg-pink-500"
            icon={Gift}
          />
          <FeatureToggle
            title="Promo Banner"
            description={`Shows "${storeSettings?.promo_banner_code || "PROMO"}" on login page`}
            enabled={storeSettings?.promo_banner_enabled || false}
            onToggle={() => toggleFeature("promo_banner", storeSettings?.promo_banner_enabled || false)}
            color="bg-yellow-500"
            icon={Megaphone}
          />
        </CardContent>
      </Card>

      {/* Info Box for Referral Settings */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-blue-600" />
          <div>
            <p className="font-medium text-blue-800">Referral Reward Settings</p>
            <p className="text-sm text-blue-600">
              Configure referral reward amounts in Settings → Referral Rewards
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" className="text-blue-600 border-blue-300" onClick={() => window.scrollTo(0, 0)}>
          <ExternalLink className="w-4 h-4 mr-1" /> Go to Settings
        </Button>
      </div>

      {/* Main Tabs - Simplified */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full overflow-hidden">
        <TabsList className="mb-4 bg-gray-100 p-1 rounded-lg flex flex-wrap sm:grid sm:grid-cols-3 w-full gap-1">
          <TabsTrigger value="overview" className="flex-1 min-w-[80px] text-xs sm:text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-2 py-1.5 sm:px-3 sm:py-2">
            📊 <span className="hidden xs:inline">Overview</span><span className="xs:hidden">Stats</span>
          </TabsTrigger>
          <TabsTrigger value="customer-codes" className="flex-1 min-w-[80px] text-xs sm:text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-2 py-1.5 sm:px-3 sm:py-2">
            🏷️ <span className="hidden sm:inline">Discount </span>Codes
          </TabsTrigger>
          <TabsTrigger value="partner-vouchers" className="flex-1 min-w-[80px] text-xs sm:text-sm data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-md px-2 py-1.5 sm:px-3 sm:py-2">
            🤝 <span className="hidden sm:inline">Partner </span>Vouchers
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Codes */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Recent Discount Codes</CardTitle>
                <Button size="sm" onClick={() => { resetCodeForm(); setEditingItem(null); setShowCreateCode(true); }}>
                  <Plus className="w-4 h-4 mr-1" /> New
                </Button>
              </CardHeader>
              <CardContent>
                {discountCodes.length > 0 ? (
                  discountCodes.slice(0, 5).map(code => (
                    <div key={code.id || code.code} className="flex items-center justify-between py-2 border-b last:border-0">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${code.is_active ? "bg-green-500" : "bg-red-500"}`} />
                        <span className="font-mono font-bold">{code.code}</span>
                        <Badge variant="outline" className="text-xs">
                          {code.discount_percent ? `${code.discount_percent}%` : `$${code.discount_amount || 0}`}
                        </Badge>
                      </div>
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => copyCode(code.code)}>
                          <Copy className="w-3 h-3" />
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => editCode(code)}>
                          <Edit className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-center text-gray-500 py-4">No discount codes yet</p>
                )}
              </CardContent>
            </Card>

            {/* Partner Vouchers Preview */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Partner Vouchers</CardTitle>
                <Button size="sm" onClick={() => { resetVoucherForm(); setShowCreateVoucher(true); }}>
                  <Plus className="w-4 h-4 mr-1" /> New
                </Button>
              </CardHeader>
              <CardContent>
                {partnerVouchers.length > 0 ? (
                  partnerVouchers.slice(0, 5).map((voucher, idx) => (
                    <div key={voucher.code + idx} className="flex items-center justify-between py-2 border-b last:border-0">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${voucher.is_active !== false ? "bg-green-500" : "bg-red-500"}`} />
                        <span className="font-mono font-bold">{voucher.code}</span>
                        <Badge variant="outline" className="text-xs">
                          {voucher.discount_value}% off
                        </Badge>
                      </div>
                      <span className="text-xs text-gray-500">{voucher.partner_name}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-center text-gray-500 py-4">No partner vouchers yet</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Customer Codes Tab */}
        <TabsContent value="customer-codes">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Discount Codes</CardTitle>
                <CardDescription>Create codes for customers to use at checkout</CardDescription>
              </div>
              <Button onClick={() => { resetCodeForm(); setEditingItem(null); setShowCreateCode(true); }} className="bg-green-500 hover:bg-green-600">
                <Plus className="w-4 h-4 mr-2" /> Create Code
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {discountCodes.map(code => (
                  <div 
                    key={code.id || code.code}
                    className={`p-4 rounded-lg border-2 ${code.is_active ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          code.type === "signup" ? "bg-purple-500" :
                          code.type === "bundle" ? "bg-blue-500" :
                          code.type === "flash" ? "bg-yellow-500" :
                          "bg-green-500"
                        }`}>
                          {code.type === "signup" ? <UserPlus className="w-5 h-5 text-white" /> :
                           code.type === "bundle" ? <Package className="w-5 h-5 text-white" /> :
                           code.type === "flash" ? <Zap className="w-5 h-5 text-white" /> :
                           <Tag className="w-5 h-5 text-white" />}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-lg">{code.code}</span>
                            <button onClick={() => copyCode(code.code)} className="text-gray-400 hover:text-gray-600">
                              <Copy className="w-4 h-4" />
                            </button>
                          </div>
                          <p className="text-sm text-gray-600">
                            {code.discount_percent ? `${code.discount_percent}% off` : `$${code.discount_amount || 0} off`}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleCodeActive(code)}
                          className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 ${
                            code.is_active ? "bg-green-500 text-white" : "bg-red-500 text-white"
                          }`}
                        >
                          {code.is_active ? <ToggleRight className="w-3 h-3" /> : <ToggleLeft className="w-3 h-3" />}
                          {code.is_active ? "ON" : "OFF"}
                        </button>
                        <Button size="sm" variant="outline" onClick={() => editCode(code)}>
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button size="sm" variant="outline" className="text-red-600" onClick={() => deleteCode(code)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
                {discountCodes.length === 0 && (
                  <div className="text-center py-12">
                    <Tag className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">No discount codes yet</p>
                    <Button onClick={() => setShowCreateCode(true)} variant="outline" className="mt-4">
                      Create Your First Code
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Partner Vouchers Tab */}
        <TabsContent value="partner-vouchers">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Partner/Influencer Vouchers</CardTitle>
                <CardDescription>Special codes for your partners to share with their audience</CardDescription>
              </div>
              <Button onClick={() => { resetVoucherForm(); setShowCreateVoucher(true); }} className="bg-blue-500 hover:bg-blue-600">
                <Plus className="w-4 h-4 mr-2" /> Create Voucher
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {partnerVouchers.map((voucher, idx) => (
                  <div 
                    key={voucher.code + idx}
                    className={`p-4 rounded-lg border-2 ${voucher.is_active !== false ? "border-blue-200 bg-blue-50" : "border-red-200 bg-red-50"}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-blue-500 flex items-center justify-center">
                          <Ticket className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-lg">{voucher.code}</span>
                            <button onClick={() => copyCode(voucher.code)} className="text-gray-400 hover:text-gray-600">
                              <Copy className="w-4 h-4" />
                            </button>
                          </div>
                          <p className="text-sm text-gray-600">
                            {voucher.discount_value}% off
                            {voucher.partner_name && ` • ${voucher.partner_name}`}
                            {voucher.partner_commission && ` • ${voucher.partner_commission}% commission`}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                          voucher.is_active !== false ? "bg-green-500 text-white" : "bg-red-500 text-white"
                        }`}>
                          {voucher.is_active !== false ? "ON" : "OFF"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
                {partnerVouchers.length === 0 && (
                  <div className="text-center py-12">
                    <Users className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500">No partner vouchers yet</p>
                    <p className="text-sm text-gray-400 mt-1">Create vouchers for your influencers and partners</p>
                    <Button onClick={() => setShowCreateVoucher(true)} variant="outline" className="mt-4">
                      Create Partner Voucher
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Code Modal */}
      <Dialog open={showCreateCode} onOpenChange={setShowCreateCode}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Tag className="w-5 h-5 text-green-500" />
              {editingItem ? "Edit Discount Code" : "Create Discount Code"}
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Code Type */}
            <div>
              <Label>Code Type</Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
                {[
                  { id: "general", label: "General", icon: Tag, color: "bg-green-500" },
                  { id: "signup", label: "First Purchase", icon: UserPlus, color: "bg-purple-500" },
                  { id: "bundle", label: "Bundle", icon: Package, color: "bg-blue-500" },
                  { id: "flash", label: "Flash Sale", icon: Zap, color: "bg-yellow-500" }
                ].map(type => (
                  <button
                    key={type.id}
                    onClick={() => setCodeForm({ ...codeForm, type: type.id })}
                    className={`p-3 rounded-lg border-2 flex flex-col items-center gap-1 ${
                      codeForm.type === type.id ? "border-gray-800 bg-gray-100" : "border-gray-200"
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-lg ${type.color} flex items-center justify-center`}>
                      <type.icon className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-xs font-medium">{type.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Code & Discount */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Discount Code</Label>
                <div className="flex gap-2">
                  <Input
                    value={codeForm.code}
                    onChange={(e) => setCodeForm({ ...codeForm, code: e.target.value.toUpperCase() })}
                    placeholder="SAVE20"
                    className="font-mono uppercase"
                  />
                  <Button variant="outline" size="sm" onClick={() => setCodeForm({ ...codeForm, code: generateCode() })}>
                    Generate
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label>Type</Label>
                  <Select value={codeForm.discount_type} onValueChange={(v) => setCodeForm({ ...codeForm, discount_type: v })}>
                    <SelectTrigger className="w-full"><SelectValue placeholder="Select type" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percentage">Percent (%)</SelectItem>
                      <SelectItem value="fixed">Fixed ($)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Value</Label>
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={codeForm.discount_value || ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === "" || /^\d*\.?\d*$/.test(val)) {
                        setCodeForm({ ...codeForm, discount_value: val });
                      }
                    }}
                    onBlur={(e) => {
                      const val = e.target.value;
                      setCodeForm({ ...codeForm, discount_value: val === "" ? 0 : parseFloat(val) || 0 });
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Conditions for bundle */}
            {codeForm.type === "bundle" && (
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <Label className="text-blue-800">Bundle Requirements</Label>
                <div className="grid grid-cols-2 gap-4 mt-2">
                  <div>
                    <Label className="text-sm">Min Products</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={codeForm.min_products || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === "" || /^\d*$/.test(val)) {
                          setCodeForm({ ...codeForm, min_products: val });
                        }
                      }}
                      onBlur={(e) => {
                        const val = e.target.value;
                        setCodeForm({ ...codeForm, min_products: val === "" ? 2 : Math.max(2, parseInt(val) || 2) });
                      }}
                      placeholder="2"
                    />
                  </div>
                  <div>
                    <Label className="text-sm">Min Order ($)</Label>
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={codeForm.min_order_amount || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === "" || /^\d*\.?\d*$/.test(val)) {
                          setCodeForm({ ...codeForm, min_order_amount: val });
                        }
                      }}
                      onBlur={(e) => {
                        const val = e.target.value;
                        setCodeForm({ ...codeForm, min_order_amount: val === "" ? 0 : parseFloat(val) || 0 });
                      }}
                      placeholder="0"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Dates for flash */}
            {codeForm.type === "flash" && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Start Date</Label>
                  <Input type="datetime-local" value={codeForm.start_date} onChange={(e) => setCodeForm({ ...codeForm, start_date: e.target.value })} />
                </div>
                <div>
                  <Label>End Date</Label>
                  <Input type="datetime-local" value={codeForm.end_date} onChange={(e) => setCodeForm({ ...codeForm, end_date: e.target.value })} />
                </div>
              </div>
            )}

            {/* Max Uses */}
            <div>
              <Label>Max Uses (0 = unlimited)</Label>
              <Input
                type="text"
                inputMode="numeric"
                value={codeForm.max_uses || ""}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === "" || /^\d*$/.test(val)) {
                    setCodeForm({ ...codeForm, max_uses: val });
                  }
                }}
                onBlur={(e) => {
                  const val = e.target.value;
                  setCodeForm({ ...codeForm, max_uses: val === "" ? 0 : parseInt(val) || 0 });
                }}
                placeholder="0 = unlimited"
              />
            </div>

            {/* Active Toggle */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium">Active</p>
                <p className="text-sm text-gray-500">Enable this code immediately</p>
              </div>
              <Switch
                checked={codeForm.is_active}
                onCheckedChange={(checked) => setCodeForm({ ...codeForm, is_active: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowCreateCode(false); setEditingItem(null); }}>Cancel</Button>
            <Button onClick={createDiscountCode} className="bg-green-500 hover:bg-green-600">
              {editingItem ? "Update Code" : "Create Code"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Voucher Modal */}
      <Dialog open={showCreateVoucher} onOpenChange={setShowCreateVoucher}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Ticket className="w-5 h-5 text-blue-500" />
              Create Partner Voucher
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            <div>
              <Label>Select Partner</Label>
              <Select value={voucherForm.partner_id} onValueChange={(v) => setVoucherForm({ ...voucherForm, partner_id: v })}>
                <SelectTrigger><SelectValue placeholder="Select a partner..." /></SelectTrigger>
                <SelectContent>
                  {partners.filter(p => p.status === "approved" || p.status === "active").map(partner => (
                    <SelectItem key={partner.id} value={partner.id}>{partner.full_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {partners.filter(p => p.status === "approved" || p.status === "active").length === 0 && (
                <p className="text-xs text-red-500 mt-1">No approved partners found</p>
              )}
            </div>

            <div>
              <Label>Voucher Code</Label>
              <div className="flex gap-2">
                <Input
                  value={voucherForm.code}
                  onChange={(e) => setVoucherForm({ ...voucherForm, code: e.target.value.toUpperCase() })}
                  placeholder="PARTNER20"
                  className="font-mono uppercase"
                />
                <Button variant="outline" size="sm" onClick={() => setVoucherForm({ ...voucherForm, code: generateCode("VIP") })}>
                  Generate
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Customer Discount (%)</Label>
                <Input
                  type="text"
                  inputMode="decimal"
                  value={voucherForm.discount_value || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "" || /^\d*\.?\d*$/.test(val)) {
                      setVoucherForm({ ...voucherForm, discount_value: val });
                    }
                  }}
                  onBlur={(e) => {
                    const val = e.target.value;
                    setVoucherForm({ ...voucherForm, discount_value: val === "" ? 20 : parseFloat(val) || 20 });
                  }}
                  placeholder="20"
                />
              </div>
              <div>
                <Label>Partner Commission (%)</Label>
                <Input
                  type="text"
                  inputMode="decimal"
                  value={voucherForm.partner_commission || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "" || /^\d*\.?\d*$/.test(val)) {
                      setVoucherForm({ ...voucherForm, partner_commission: val });
                    }
                  }}
                  onBlur={(e) => {
                    const val = e.target.value;
                    setVoucherForm({ ...voucherForm, partner_commission: val === "" ? 15 : parseFloat(val) || 15 });
                  }}
                  placeholder="15"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium">Active</p>
                <p className="text-sm text-gray-500">Enable this voucher immediately</p>
              </div>
              <Switch
                checked={voucherForm.is_active}
                onCheckedChange={(checked) => setVoucherForm({ ...voucherForm, is_active: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateVoucher(false)}>Cancel</Button>
            <Button onClick={createPartnerVoucher} className="bg-blue-500 hover:bg-blue-600">
              Create Voucher
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PromotionsCenter;
