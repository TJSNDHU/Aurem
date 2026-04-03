import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  Edit,
  Copy,
  Check,
  X,
  Tag,
  Gift,
  Zap,
  Calendar,
  ShoppingBag,
  Users,
  Percent,
  DollarSign,
  Clock,
  Eye,
  EyeOff,
  Megaphone,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Package,
  Settings,
  Crown,
  UserPlus,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";

const API = process.env.REACT_APP_BACKEND_URL 
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : `${window.location.origin}/api`;

// Code type configurations
const CODE_TYPES = {
  signup: {
    label: "First Purchase / Sign Up",
    icon: Users,
    color: "bg-green-500",
    description: "Only works for first-time buyers (no previous orders)"
  },
  bundle: {
    label: "Bundle Discount",
    icon: Package,
    color: "bg-blue-500",
    description: "Works when customer buys 2+ products"
  },
  flash: {
    label: "Flash Sale",
    icon: Zap,
    color: "bg-yellow-500",
    description: "Limited time offer with countdown"
  },
  event: {
    label: "Event / Festival",
    icon: Calendar,
    color: "bg-purple-500",
    description: "Black Friday, Holiday sales, special events"
  },
  general: {
    label: "General Discount",
    icon: Tag,
    color: "bg-gray-500",
    description: "Standard discount code for anyone"
  }
};

// Placement options
const PLACEMENT_OPTIONS = [
  { id: "banner", label: "Promo Banner (Login Page)", icon: Megaphone },
  { id: "checkout", label: "Checkout Page", icon: ShoppingBag },
  { id: "popup", label: "Homepage Popup", icon: Eye },
  { id: "product", label: "Product Pages", icon: Tag },
  { id: "email", label: "Email Campaigns", icon: Gift }
];

const DiscountCodeManager = () => {
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCode, setEditingCode] = useState(null);
  const [expandedCode, setExpandedCode] = useState(null);
  
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
  const [autoDiscountsLoading, setAutoDiscountsLoading] = useState(true);
  const [savingAutoDiscount, setSavingAutoDiscount] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    code: "",
    type: "general",
    discount_type: "percentage",
    discount_value: 10,
    description: "",
    min_products: 1,
    min_order_amount: 0,
    max_uses: 0, // 0 = unlimited
    start_date: "",
    end_date: "",
    is_active: true,
    placements: []
  });

  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const fetchCodes = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/discount-codes`, { headers });
      setCodes(res.data || []);
    } catch (error) {
      console.error("Failed to fetch codes:", error);
    }
    setLoading(false);
  }, []);

  const fetchAutoDiscounts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/store-settings/auto-discounts`, { headers });
      setAutoDiscounts(res.data || {});
    } catch (error) {
      console.error("Failed to fetch auto-discounts:", error);
    }
    setAutoDiscountsLoading(false);
  }, []);

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

  useEffect(() => {
    fetchCodes();
    fetchAutoDiscounts();
  }, [fetchCodes, fetchAutoDiscounts]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const generateCode = () => {
    const prefixes = {
      signup: "WELCOME",
      bundle: "BUNDLE",
      flash: "FLASH",
      event: "SAVE",
      general: "DISCOUNT"
    };
    const prefix = prefixes[formData.type] || "CODE";
    const random = Math.random().toString(36).substring(2, 6).toUpperCase();
    const discount = formData.discount_value;
    return `${prefix}${discount}${random}`;
  };

  const handleSubmit = async () => {
    if (!formData.code) {
      toast.error("Please enter a discount code");
      return;
    }

    try {
      const payload = {
        ...formData,
        code: formData.code.toUpperCase()
      };

      if (editingCode) {
        await axios.put(`${API}/admin/discount-codes/${editingCode.id}`, payload, { headers });
        toast.success("Discount code updated!");
      } else {
        await axios.post(`${API}/admin/discount-codes`, payload, { headers });
        toast.success("Discount code created!");
      }

      setShowForm(false);
      setEditingCode(null);
      resetForm();
      fetchCodes();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save code");
    }
  };

  const handleDelete = async (codeId) => {
    if (!window.confirm("Delete this discount code?")) return;
    
    try {
      await axios.delete(`${API}/admin/discount-codes/${codeId}`, { headers });
      toast.success("Code deleted");
      fetchCodes();
    } catch (error) {
      toast.error("Failed to delete code");
    }
  };

  const handleToggleActive = async (code) => {
    try {
      await axios.put(`${API}/admin/discount-codes/${code.id}`, {
        ...code,
        is_active: !code.is_active
      }, { headers });
      fetchCodes();
      toast.success(code.is_active ? "Code deactivated" : "Code activated");
    } catch (error) {
      toast.error("Failed to update code");
    }
  };

  const handleEdit = (code) => {
    setEditingCode(code);
    setFormData({
      code: code.code,
      type: code.type || "general",
      discount_type: code.discount_type || "percentage",
      discount_value: code.discount_value || code.discount_percent || 10,
      description: code.description || "",
      min_products: code.min_products || 1,
      min_order_amount: code.min_order_amount || 0,
      max_uses: code.max_uses || 0,
      start_date: code.start_date || "",
      end_date: code.end_date || "",
      is_active: code.is_active !== false,
      placements: code.placements || []
    });
    setShowForm(true);
  };

  const resetForm = () => {
    setFormData({
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
      is_active: true,
      placements: []
    });
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success(`Code "${code}" copied!`);
  };

  const togglePlacement = (placementId) => {
    setFormData(prev => ({
      ...prev,
      placements: prev.placements.includes(placementId)
        ? prev.placements.filter(p => p !== placementId)
        : [...prev.placements, placementId]
    }));
  };

  const CodeTypeIcon = ({ type }) => {
    const config = CODE_TYPES[type] || CODE_TYPES.general;
    const Icon = config.icon;
    return (
      <div className={`w-8 h-8 rounded-lg ${config.color} flex items-center justify-center`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-yellow-500" />
            Discount Code Generator
          </h2>
          <p className="text-gray-500">Create and manage all discount codes in one place</p>
        </div>
        <Button 
          onClick={() => { resetForm(); setEditingCode(null); setShowForm(true); }}
          className="bg-gradient-to-r from-[#C9A86C] to-[#D4AF37] text-white gap-2"
        >
          <Plus className="w-4 h-4" />
          Create New Code
        </Button>
      </div>

      {/* Auto-Discounts Section */}
      <Card className="border-2 border-dashed border-[#C9A86C]/30 bg-gradient-to-br from-amber-50/50 to-white">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#C9A86C] to-[#D4AF37] flex items-center justify-center">
                <Settings className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-lg">System Auto-Discounts</CardTitle>
                <CardDescription>These discounts apply automatically at checkout (no code needed)</CardDescription>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {autoDiscountsLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-500">Loading auto-discounts...</span>
            </div>
          ) : (
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
                <div className="flex items-center gap-2">
                  <span className={`text-2xl font-bold ${
                    autoDiscounts.founder_discount_enabled ? 'text-green-600' : 'text-gray-400'
                  }`}>
                    {autoDiscounts.founder_discount_percent}%
                  </span>
                  <span className="text-sm text-gray-500">OFF</span>
                </div>
                <p className="text-xs text-gray-500 mt-2">
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
                <div className="flex items-center gap-2">
                  <span className={`text-2xl font-bold ${
                    autoDiscounts.first_purchase_discount_enabled ? 'text-blue-600' : 'text-gray-400'
                  }`}>
                    {autoDiscounts.first_purchase_discount_percent}%
                  </span>
                  <span className="text-sm text-gray-500">OFF</span>
                </div>
                <p className="text-xs text-gray-500 mt-2">
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
                <div className="flex items-center gap-2">
                  <span className={`text-2xl font-bold ${
                    autoDiscounts.voucher_gate_enabled ? 'text-purple-600' : 'text-gray-400'
                  }`}>
                    {autoDiscounts.voucher_gate_threshold}
                  </span>
                  <span className="text-sm text-gray-500">uses/code</span>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  {autoDiscounts.voucher_gate_enabled 
                    ? '✓ Codes required at checkout' 
                    : '○ Currently disabled'}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {Object.entries(CODE_TYPES).map(([key, config]) => {
          const count = codes.filter(c => c.type === key).length;
          const Icon = config.icon;
          return (
            <Card key={key} className="bg-white">
              <CardContent className="p-4 flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg ${config.color} flex items-center justify-center`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-xs text-gray-500">{config.label}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Codes List */}
      <Card>
        <CardHeader>
          <CardTitle>All Discount Codes</CardTitle>
          <CardDescription>Click on a code to see details and where it's placed</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading...</div>
          ) : codes.length === 0 ? (
            <div className="text-center py-12">
              <Tag className="w-12 h-12 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">No discount codes yet</p>
              <Button 
                onClick={() => setShowForm(true)} 
                variant="outline" 
                className="mt-4"
              >
                Create Your First Code
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {codes.map(code => (
                <div 
                  key={code.id}
                  className={`border rounded-lg overflow-hidden transition-all ${
                    expandedCode === code.id ? 'ring-2 ring-[#C9A86C]' : ''
                  }`}
                >
                  {/* Code Row */}
                  <div 
                    className="p-4 flex items-center gap-4 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedCode(expandedCode === code.id ? null : code.id)}
                  >
                    <CodeTypeIcon type={code.type} />
                    
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-lg">{code.code}</span>
                        <button 
                          onClick={(e) => { e.stopPropagation(); copyCode(code.code); }}
                          className="text-gray-400 hover:text-gray-600"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                      <p className="text-sm text-gray-500">
                        {code.discount_type === "percentage" 
                          ? `${code.discount_value || code.discount_percent}% off` 
                          : `$${code.discount_value || code.discount_amount} off`}
                        {code.min_products > 1 && ` • Min ${code.min_products} products`}
                        {code.end_date && ` • Ends ${new Date(code.end_date).toLocaleDateString()}`}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge variant={code.is_active ? "default" : "secondary"}>
                        {code.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {CODE_TYPES[code.type]?.label || "General"}
                      </Badge>
                      {expandedCode === code.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedCode === code.id && (
                    <div className="px-4 pb-4 pt-2 bg-gray-50 border-t">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div>
                          <p className="text-xs text-gray-500">Uses</p>
                          <p className="font-semibold">{code.uses || 0} / {code.max_uses || "∞"}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Min Order</p>
                          <p className="font-semibold">${code.min_order_amount || 0}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Start Date</p>
                          <p className="font-semibold">{code.start_date ? new Date(code.start_date).toLocaleDateString() : "Always"}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">End Date</p>
                          <p className="font-semibold">{code.end_date ? new Date(code.end_date).toLocaleDateString() : "Never"}</p>
                        </div>
                      </div>

                      {/* Placements */}
                      {code.placements && code.placements.length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs text-gray-500 mb-2">Active Placements:</p>
                          <div className="flex flex-wrap gap-2">
                            {code.placements.map(p => {
                              const placement = PLACEMENT_OPTIONS.find(opt => opt.id === p);
                              return placement ? (
                                <Badge key={p} variant="outline" className="gap-1">
                                  <placement.icon className="w-3 h-3" />
                                  {placement.label}
                                </Badge>
                              ) : null;
                            })}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => handleEdit(code)}>
                          <Edit className="w-4 h-4 mr-1" /> Edit
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => handleToggleActive(code)}
                        >
                          {code.is_active ? <EyeOff className="w-4 h-4 mr-1" /> : <Eye className="w-4 h-4 mr-1" />}
                          {code.is_active ? "Deactivate" : "Activate"}
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline" 
                          className="text-red-600 hover:bg-red-50"
                          onClick={() => handleDelete(code.id)}
                        >
                          <Trash2 className="w-4 h-4 mr-1" /> Delete
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Code Dialog */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-yellow-500" />
              {editingCode ? "Edit Discount Code" : "Create New Discount Code"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Code Type Selection */}
            <div>
              <Label className="mb-3 block">Code Type</Label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(CODE_TYPES).map(([key, config]) => {
                  const Icon = config.icon;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleInputChange("type", key)}
                      className={`p-3 rounded-lg border-2 text-left transition-all ${
                        formData.type === key 
                          ? 'border-[#C9A86C] bg-[#C9A86C]/10' 
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div className={`w-6 h-6 rounded ${config.color} flex items-center justify-center`}>
                          <Icon className="w-3 h-3 text-white" />
                        </div>
                        <span className="font-medium text-sm">{config.label}</span>
                      </div>
                      <p className="text-xs text-gray-500">{config.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <Separator />

            {/* Code & Discount */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Discount Code</Label>
                <div className="flex gap-2">
                  <Input
                    value={formData.code}
                    onChange={(e) => handleInputChange("code", e.target.value)}
                    onBlur={(e) => handleInputChange("code", e.target.value.toUpperCase())}
                    placeholder="SAVE20"
                    className="font-mono uppercase"
                  />
                  <Button 
                    type="button" 
                    variant="outline" 
                    size="sm"
                    onClick={() => handleInputChange("code", generateCode())}
                  >
                    Generate
                  </Button>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label>Discount Type</Label>
                  <Select 
                    value={formData.discount_type} 
                    onValueChange={(v) => handleInputChange("discount_type", v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percentage">Percentage (%)</SelectItem>
                      <SelectItem value="fixed">Fixed Amount ($)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Value</Label>
                  <div className="relative">
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={formData.discount_value === 0 ? "" : formData.discount_value}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || /^\d*\.?\d*$/.test(val)) {
                          handleInputChange("discount_value", val === "" ? "" : val);
                        }
                      }}
                      onBlur={(e) => {
                        const val = e.target.value;
                        handleInputChange("discount_value", val === "" ? 0 : parseFloat(val) || 0);
                      }}
                      className="pr-8"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                      {formData.discount_type === "percentage" ? "%" : "$"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Conditions based on type */}
            {formData.type === "bundle" && (
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <Label className="text-blue-800">Bundle Conditions</Label>
                <div className="grid grid-cols-2 gap-4 mt-2">
                  <div>
                    <Label className="text-sm">Minimum Products</Label>
                    <Input
                      type="text"
                      inputMode="numeric"
                      value={formData.min_products === 1 ? "" : formData.min_products}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || /^\d*$/.test(val)) {
                          handleInputChange("min_products", val === "" ? "" : val);
                        }
                      }}
                      onBlur={(e) => {
                        const val = e.target.value;
                        handleInputChange("min_products", val === "" ? 2 : Math.max(2, parseInt(val) || 2));
                      }}
                      placeholder="2"
                    />
                    <p className="text-xs text-blue-600 mt-1">Code only works when buying this many products</p>
                  </div>
                  <div>
                    <Label className="text-sm">Min Order Amount ($)</Label>
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={formData.min_order_amount === 0 ? "" : formData.min_order_amount}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || /^\d*\.?\d*$/.test(val)) {
                          handleInputChange("min_order_amount", val === "" ? "" : val);
                        }
                      }}
                      onBlur={(e) => {
                        const val = e.target.value;
                        handleInputChange("min_order_amount", val === "" ? 0 : parseFloat(val) || 0);
                      }}
                      placeholder="0"
                    />
                  </div>
                </div>
              </div>
            )}

            {(formData.type === "flash" || formData.type === "event") && (
              <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                <Label className="text-purple-800">Time-Limited Sale</Label>
                <div className="grid grid-cols-2 gap-4 mt-2">
                  <div>
                    <Label className="text-sm">Start Date</Label>
                    <Input
                      type="datetime-local"
                      value={formData.start_date}
                      onChange={(e) => handleInputChange("start_date", e.target.value)}
                    />
                  </div>
                  <div>
                    <Label className="text-sm">End Date</Label>
                    <Input
                      type="datetime-local"
                      value={formData.end_date}
                      onChange={(e) => handleInputChange("end_date", e.target.value)}
                    />
                  </div>
                </div>
                <p className="text-xs text-purple-600 mt-2">Leave empty for no time limit</p>
              </div>
            )}

            {/* Usage Limit */}
            <div>
              <Label>Maximum Uses (0 = unlimited)</Label>
              <Input
                type="text"
                inputMode="numeric"
                value={formData.max_uses === 0 ? "" : formData.max_uses}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '' || /^\d*$/.test(val)) {
                    handleInputChange("max_uses", val === "" ? "" : val);
                  }
                }}
                onBlur={(e) => {
                  const val = e.target.value;
                  handleInputChange("max_uses", val === "" ? 0 : parseInt(val) || 0);
                }}
                placeholder="0 = unlimited"
              />
            </div>

            {/* Description */}
            <div>
              <Label>Description (internal note)</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => handleInputChange("description", e.target.value)}
                placeholder="e.g., Black Friday 2025 sale"
                rows={2}
              />
            </div>

            <Separator />

            {/* Placement Selection */}
            <div>
              <Label className="mb-3 block">Where to Activate This Code</Label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {PLACEMENT_OPTIONS.map(option => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => togglePlacement(option.id)}
                    className={`p-3 rounded-lg border-2 text-left transition-all flex items-center gap-2 ${
                      formData.placements.includes(option.id)
                        ? 'border-green-500 bg-green-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded flex items-center justify-center ${
                      formData.placements.includes(option.id) ? 'bg-green-500 text-white' : 'bg-gray-100'
                    }`}>
                      <option.icon className="w-4 h-4" />
                    </div>
                    <span className="text-sm font-medium">{option.label}</span>
                    {formData.placements.includes(option.id) && (
                      <Check className="w-4 h-4 text-green-500 ml-auto" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Active Toggle */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium">Active</p>
                <p className="text-sm text-gray-500">Enable this discount code immediately</p>
              </div>
              <Switch
                checked={formData.is_active}
                onCheckedChange={(checked) => handleInputChange("is_active", checked)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowForm(false); setEditingCode(null); }}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} className="bg-[#C9A86C] hover:bg-[#B8975B]">
              {editingCode ? "Update Code" : "Create Code"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DiscountCodeManager;
