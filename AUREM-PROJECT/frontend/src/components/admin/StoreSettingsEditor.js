import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAdminBrand } from './useAdminBrand';
import {
  Trash2,
  RefreshCw,
  Save,
  CreditCard,
  MessageCircle,
  Globe,
  Heart,
  Image,
  Shield,
  MapPin,
  Mail,
  Package,
  ImagePlus,
  Upload,
  Bot,
  Play,
  CheckCircle,
  X,
  Phone,
  Loader2,
  Megaphone,
  Sparkles,
  Gift,
  Ticket,
  Users,
  DollarSign,
  Lock,
  Bell,
  AlertTriangle,
  Clock,
  Timer,
  Key,
  ShieldCheck,
  UserX,
  FileText
} from 'lucide-react';

// Default logo with Cloudinary optimization (resized from 975KB to ~15KB)
const DEFAULT_LOGO_URL = `https://res.cloudinary.com/ddpphzqdg/image/fetch/w_200,h_80,c_fit,q_auto,f_auto/${encodeURIComponent("https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png")}`;

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { API, BACKEND_URL } from '@/lib/api';
import PermanentImageUpload from '@/components/common/PermanentImageUpload';

// NotificationsSection Component
const NotificationsSection = ({ settings, setSettings }) => {
  const [callbackRequests, setCallbackRequests] = useState([]);
  const [loadingCallbacks, setLoadingCallbacks] = useState(true);
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    axios.get(`${API}/admin/callback-requests`, { headers })
      .then(res => setCallbackRequests(res.data))
      .catch(console.error)
      .finally(() => setLoadingCallbacks(false));
  }, []);

  const updateCallbackStatus = async (id, status) => {
    try {
      await axios.put(`${API}/admin/callback-requests/${id}`, { status }, { headers });
      setCallbackRequests(callbackRequests.map(req => 
        req.id === id ? { ...req, status } : req
      ));
      toast.success("Status updated");
    } catch (err) {
      toast.error("Failed to update");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-4">
        <Mail className="h-5 w-5 text-[#F8A5B8]" />
        <h3 className="font-display text-xl font-bold">Notifications</h3>
      </div>

      <div>
        <Label>Admin Email (for order notifications)</Label>
        <Input
          value={settings.notifications?.admin_email || ""}
          onChange={(e) => setSettings({...settings, notifications: {...settings.notifications, admin_email: e.target.value}})}
          placeholder="admin@reroots.ca"
        />
      </div>

      <div>
        <Label>Notification Phone (for SMS alerts)</Label>
        <Input
          value={settings.notifications?.notification_phone || ""}
          onChange={(e) => setSettings({...settings, notifications: {...settings.notifications, notification_phone: e.target.value}})}
          placeholder="+12265017777"
        />
      </div>

      {/* Callback Requests */}
      <div className="border-t pt-6 mt-6">
        <div className="flex items-center gap-2 mb-4">
          <Phone className="h-5 w-5 text-amber-500" />
          <h3 className="font-display text-lg font-bold">Callback Requests</h3>
          {callbackRequests.filter(r => r.status === "pending").length > 0 && (
            <Badge className="bg-red-500 text-white">
              {callbackRequests.filter(r => r.status === "pending").length} pending
            </Badge>
          )}
        </div>

        {loadingCallbacks ? (
          <div className="text-center py-4"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
        ) : callbackRequests.length === 0 ? (
          <p className="text-sm text-[#5A5A5A]">No callback requests yet</p>
        ) : (
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {callbackRequests.map(req => (
              <div key={req.id} className={`p-3 border rounded-lg ${req.status === 'pending' ? 'border-amber-300 bg-amber-50' : 'bg-gray-50'}`}>
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium text-sm">{req.customer_name}</p>
                    <p className="text-sm text-[#2D2A2E] flex items-center gap-1">
                      <Phone className="h-3 w-3" /> {req.phone}
                    </p>
                    {req.email && <p className="text-xs text-[#5A5A5A]">{req.email}</p>}
                    {req.preferred_time && <p className="text-xs text-[#5A5A5A]">Preferred: {req.preferred_time}</p>}
                    {req.reason && <p className="text-xs text-[#5A5A5A] mt-1">"{req.reason}"</p>}
                  </div>
                  <select
                    value={req.status}
                    onChange={(e) => updateCallbackStatus(req.id, e.target.value)}
                    className={`text-xs border rounded px-2 py-1 ${
                      req.status === 'pending' ? 'bg-amber-100 border-amber-300' :
                      req.status === 'contacted' ? 'bg-blue-100 border-blue-300' :
                      'bg-green-100 border-green-300'
                    }`}
                  >
                    <option value="pending">Pending</option>
                    <option value="contacted">Contacted</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
                <p className="text-xs text-[#888888] mt-2">
                  {new Date(req.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// Store Settings Editor Component
const StoreSettingsEditor = ({ SecurityDashboard }) => {
  const { name: brandName, activeBrand, isLaVela } = useAdminBrand();
  const primaryColor = isLaVela ? '#0D4D4D' : '#F8A5B8';
  const primaryColorLight = isLaVela ? 'rgba(13,77,77,0.2)' : 'rgba(248,165,184,0.2)';
  
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeSection, setActiveSection] = useState("payment");
  const [refreshing, setRefreshing] = useState(false);
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const fetchSettings = () => {
    setLoading(true);
    axios.get(`${API}/admin/store-settings`, { headers })
      .then(res => setSettings(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  // Refresh function to reload all settings
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      // Clear any cached data
      const res = await axios.get(`${API}/admin/store-settings`, { headers });
      setSettings(res.data);
      toast.success("Settings refreshed!");
    } catch (error) {
      toast.error("Failed to refresh settings");
    }
    setRefreshing(false);
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/store-settings`, settings, { headers });
      toast.success("Settings saved!");
    } catch (error) {
      toast.error("Failed to save settings");
    }
    setSaving(false);
  };

  if (loading) {
    return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-t-2" style={{ borderColor: primaryColor }}></div></div>;
  }

  return (
    <div className="space-y-6">
      {/* Header with actions - Responsive for mobile */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Store Settings</h2>
          <p className="text-[#5A5A5A]">Manage payments, live chat, and integrations</p>
        </div>
        
        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          <Button onClick={saveSettings} disabled={saving} className="btn-primary gap-2 flex-1 sm:flex-none" size="sm">
            <Save className="h-4 w-4" /> {saving ? "Saving..." : "SAVE ALL"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Section Navigation */}
        <Card className="lg:col-span-1 h-fit">
          <CardContent className="p-2">
            <div className="space-y-1">
              {[
                { id: "logo", label: "Logo Settings", icon: ImagePlus },
                { id: "payment", label: "Payment Settings", icon: CreditCard },
                { id: "livechat", label: "Live Chat", icon: MessageCircle },
                { id: "promo", label: "Promo Popup", icon: Megaphone },
                { id: "firstpurchase", label: "First Purchase Bonus", icon: Gift },
                { id: "referral", label: "Referral Rewards", icon: Users },
                { id: "language", label: "Language & Region", icon: Globe },
                { id: "thankyou", label: "Thank You Messages", icon: Heart },
                { id: "loginbg", label: "Site Backgrounds", icon: Image },
                { id: "security", label: "Security", icon: Shield },
                { id: "google", label: "Google Business", icon: MapPin },
                { id: "notifications", label: "Notifications", icon: Mail },
                { id: "store", label: "Store Info", icon: Package }
              ].map(section => (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                    activeSection === section.id 
                      ? "text-[#2D2A2E] font-medium" 
                      : "hover:bg-gray-100 text-[#5A5A5A]"
                  }`}
                  style={activeSection === section.id ? { backgroundColor: primaryColorLight } : {}}
                >
                  <section.icon className="h-4 w-4" />
                  {section.label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Editor Panel */}
        <Card className="lg:col-span-3">
          <CardContent className="p-6">
            {/* Logo Settings */}
            {activeSection === "logo" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <ImagePlus className="h-5 w-5" style={{ color: primaryColor }} />
                  <h3 className="font-display text-xl font-bold">Logo Settings</h3>
                </div>
                
                {/* Info Banner - Permanent Hosting Active */}
                <div className="bg-green-50 border-2 border-green-300 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-green-800 font-medium">✓ Automatic Permanent Hosting Active</p>
                      <p className="text-xs text-green-700 mt-1">
                        Images uploaded here are automatically saved to permanent external hosting. Your images will persist after deployment!
                      </p>
                    </div>
                  </div>
                </div>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">📷 Logo Image</CardTitle>
                    <CardDescription>Upload or paste a URL for your brand logo</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Logo URL (Recommended ✓)</Label>
                      <Input
                        value={settings?.logo_url || ""}
                        onChange={(e) => setSettings({...settings, logo_url: e.target.value})}
                        placeholder="https://i.imgur.com/your-logo.png"
                        className="border-green-300 focus:border-green-500"
                      />
                      <p className="text-xs text-green-600 mt-1">✓ External URLs are permanent and won't disappear</p>
                    </div>
                    
                    <div>
                      <Label className="block mb-2">Or Upload Image (Auto-saves permanently) ✓</Label>
                      <PermanentImageUpload 
                        onUpload={(url) => {
                          setSettings({...settings, logo_url: url});
                        }}
                      />
                    </div>

                    {settings?.logo_url && (
                      <div className="mt-4">
                        <Label className="block mb-2">Preview</Label>
                        <div className="p-4 bg-gray-100 rounded-lg inline-block">
                          <img 
                            src={settings.logo_url} 
                            alt="Logo preview" 
                            className="h-16 w-auto object-contain"
                            style={{ mixBlendMode: 'multiply' }}
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                        </div>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="mt-2 ml-2 text-red-500"
                          onClick={() => setSettings({...settings, logo_url: ""})}
                        >
                          <Trash2 className="h-4 w-4 mr-1" /> Remove
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">📏 Logo Size</CardTitle>
                    <CardDescription>Adjust the size of your logo in the navigation bar</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-4 gap-3">
                      {[
                        { value: 'small', label: 'Small', desc: '40-48px' },
                        { value: 'medium', label: 'Medium', desc: '56-64px' },
                        { value: 'large', label: 'Large', desc: '80-96px' },
                        { value: 'xlarge', label: 'Extra Large', desc: '96-112px' }
                      ].map(size => (
                        <button
                          key={size.value}
                          onClick={() => setSettings({...settings, logo_size: size.value})}
                          className={`p-4 rounded-lg border-2 transition-all text-center ${
                            (settings?.logo_size || 'medium') === size.value 
                              ? 'border-purple-500 bg-purple-50' 
                              : 'border-gray-200 hover:border-purple-300'
                          }`}
                        >
                          <div className="font-medium">{size.label}</div>
                          <div className="text-xs text-gray-500">{size.desc}</div>
                        </button>
                      ))}
                    </div>

                    {/* Live Preview */}
                    <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                      <Label className="block mb-3">Live Preview</Label>
                      <div className="bg-white p-4 rounded-lg shadow-sm flex items-center gap-4">
                        <img 
                          src={settings?.logo_url || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png"} 
                          alt="Logo preview" 
                          className={`w-auto object-contain ${
                            settings?.logo_size === 'small' ? 'h-10' :
                            settings?.logo_size === 'large' ? 'h-20' :
                            settings?.logo_size === 'xlarge' ? 'h-24' :
                            'h-14'
                          }`}
                          style={{ mixBlendMode: 'multiply' }}
                        />
                        <span className="text-sm text-gray-400">← Your logo in navbar</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Logo Background Transparency */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">🎨 Logo Background</CardTitle>
                    <CardDescription>Adjust the background transparency of your logo container</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <Label>Background Opacity</Label>
                        <span className="text-sm font-medium text-purple-600">
                          {Math.round((settings?.logo_bg_opacity ?? 0.9) * 100)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={Math.round((settings?.logo_bg_opacity ?? 0.9) * 100)}
                        onChange={(e) => setSettings({...settings, logo_bg_opacity: parseInt(e.target.value) / 100})}
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-500"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>Transparent (0%)</span>
                        <span>Solid (100%)</span>
                      </div>
                    </div>

                    {/* Transparency Preview */}
                    <div className="mt-4">
                      <Label className="block mb-3">Preview on Different Backgrounds</Label>
                      <div className="grid grid-cols-3 gap-3">
                        {/* Light Background */}
                        <div className="p-4 bg-gray-100 rounded-lg text-center">
                          <div 
                            className="inline-block p-2 rounded-lg mb-2"
                            style={{ backgroundColor: `rgba(255, 255, 255, ${settings?.logo_bg_opacity ?? 0.9})` }}
                          >
                            <img 
                              src={settings?.logo_url || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png"} 
                              alt="Logo" 
                              className="h-10 w-auto object-contain"
                              style={{ mixBlendMode: 'multiply' }}
                            />
                          </div>
                          <p className="text-xs text-gray-500">Light</p>
                        </div>
                        {/* Dark Background */}
                        <div className="p-4 bg-gray-800 rounded-lg text-center">
                          <div 
                            className="inline-block p-2 rounded-lg mb-2"
                            style={{ backgroundColor: `rgba(255, 255, 255, ${settings?.logo_bg_opacity ?? 0.9})` }}
                          >
                            <img 
                              src={settings?.logo_url || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png"} 
                              alt="Logo" 
                              className="h-10 w-auto object-contain"
                              style={{ mixBlendMode: 'multiply' }}
                            />
                          </div>
                          <p className="text-xs text-gray-300">Dark</p>
                        </div>
                        {/* Pink/Brand Background */}
                        <div className="p-4 rounded-lg text-center" style={{ backgroundColor: '#F8A5B8' }}>
                          <div 
                            className="inline-block p-2 rounded-lg mb-2"
                            style={{ backgroundColor: `rgba(255, 255, 255, ${settings?.logo_bg_opacity ?? 0.9})` }}
                          >
                            <img 
                              src={settings?.logo_url || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png"} 
                              alt="Logo" 
                              className="h-10 w-auto object-contain"
                              style={{ mixBlendMode: 'multiply' }}
                            />
                          </div>
                          <p className="text-xs text-white">Brand</p>
                        </div>
                      </div>
                    </div>

                    {/* Quick Presets */}
                    <div className="mt-4">
                      <Label className="block mb-2">Quick Presets</Label>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSettings({...settings, logo_bg_opacity: 0})}
                          className={settings?.logo_bg_opacity === 0 ? 'border-purple-500 bg-purple-50' : ''}
                        >
                          No Background
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSettings({...settings, logo_bg_opacity: 0.5})}
                          className={settings?.logo_bg_opacity === 0.5 ? 'border-purple-500 bg-purple-50' : ''}
                        >
                          Semi-Transparent
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSettings({...settings, logo_bg_opacity: 0.9})}
                          className={(settings?.logo_bg_opacity ?? 0.9) === 0.9 ? 'border-purple-500 bg-purple-50' : ''}
                        >
                          Solid White
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>💡 Tip:</strong> For best results, use a logo with a transparent or white background. The logo will automatically blend with any background color.
                  </p>
                </div>
              </div>
            )}

            {/* Payment Settings */}
            {activeSection === "payment" && settings?.payment && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <CreditCard className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Payment Settings</h3>
                </div>
                
                <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-800">
                    <strong>💳 Payment Methods:</strong> Enable the payment methods you want to accept. Only enabled methods will show at checkout.
                  </p>
                </div>

                {/* TD Bank / Bambora Credit Card */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <span className="w-8 h-8 bg-[#00843D] rounded-lg flex items-center justify-center text-white text-xs font-bold">TD</span>
                        Credit/Debit Card (TD Bank)
                      </CardTitle>
                      <Switch 
                        checked={settings.payment.bambora_enabled !== false} 
                        onCheckedChange={(c) => setSettings({...settings, payment: {...settings.payment, bambora_enabled: c}})}
                      />
                    </div>
                  </CardHeader>
                  {settings.payment.bambora_enabled !== false && (
                    <CardContent>
                      <p className="text-sm text-gray-600">
                        Powered by Bambora/TD Bank. Accepts Visa, Mastercard, and Debit cards.
                      </p>
                    </CardContent>
                  )}
                </Card>

                {/* E-Transfer Settings */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <span className="w-8 h-8 bg-[#FFCC00] rounded-lg flex items-center justify-center text-black text-xs font-bold">e-T</span>
                        Interac e-Transfer
                      </CardTitle>
                      <Switch 
                        checked={settings.payment.etransfer_enabled !== false} 
                        onCheckedChange={(c) => setSettings({...settings, payment: {...settings.payment, etransfer_enabled: c}})}
                      />
                    </div>
                  </CardHeader>
                  {settings.payment.etransfer_enabled !== false && (
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>E-Transfer Email</Label>
                          <Input
                            value={settings.payment.etransfer_email || ""}
                            onChange={(e) => setSettings({...settings, payment: {...settings.payment, etransfer_email: e.target.value}})}
                            placeholder="admin@reroots.ca"
                          />
                        </div>
                        <div>
                          <Label>E-Transfer Phone (optional)</Label>
                          <Input
                            value={settings.payment.etransfer_phone || ""}
                            onChange={(e) => setSettings({...settings, payment: {...settings.payment, etransfer_phone: e.target.value}})}
                            placeholder="+1234567890"
                          />
                        </div>
                      </div>
                      <div>
                        <Label>Instructions for Customer</Label>
                        <Textarea
                          value={settings.payment.etransfer_instructions || ""}
                          onChange={(e) => setSettings({...settings, payment: {...settings.payment, etransfer_instructions: e.target.value}})}
                          placeholder="Send e-Transfer to our email. Include order number in message."
                          rows={2}
                        />
                      </div>
                    </CardContent>
                  )}
                </Card>

                {/* PayPal API Settings */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <span className="w-8 h-8 bg-[#003087] rounded-lg flex items-center justify-center text-white text-xs font-bold">PP</span>
                        PayPal API
                      </CardTitle>
                      <Switch 
                        checked={settings.payment.paypal_api_enabled === true} 
                        onCheckedChange={(c) => setSettings({...settings, payment: {...settings.payment, paypal_api_enabled: c}})}
                      />
                    </div>
                  </CardHeader>
                  {settings.payment.paypal_api_enabled && (
                    <CardContent className="space-y-4">
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-800 flex items-center gap-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          PayPal API automatically charges the exact order total. No manual price matching needed.
                        </p>
                      </div>
                      <div>
                        <Label>PayPal Client ID</Label>
                        <Input
                          value={settings.payment.paypal_client_id || ""}
                          onChange={(e) => setSettings({...settings, payment: {...settings.payment, paypal_client_id: e.target.value}})}
                          placeholder="AYbJu2QbFrRPm..."
                        />
                        <p className="text-xs text-gray-500 mt-1">Get from PayPal Developer Dashboard → Apps & Credentials</p>
                      </div>
                      <div>
                        <Label>PayPal Secret</Label>
                        <Input
                          type="password"
                          value={settings.payment.paypal_secret || ""}
                          onChange={(e) => setSettings({...settings, payment: {...settings.payment, paypal_secret: e.target.value}})}
                          placeholder="••••••••••••••••"
                        />
                      </div>
                      <div>
                        <Label>Environment</Label>
                        <Select 
                          value={settings.payment.paypal_mode || "live"} 
                          onValueChange={(value) => setSettings({...settings, payment: {...settings.payment, paypal_mode: value}})}
                        >
                          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="live">🟢 Live (Production)</SelectItem>
                            <SelectItem value="sandbox">🟡 Sandbox (Testing)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="pt-2 border-t">
                        <div className="flex items-center gap-2 text-sm">
                          <span className={`w-2 h-2 rounded-full ${settings.payment.paypal_client_id && settings.payment.paypal_secret ? 'bg-green-500' : 'bg-gray-300'}`}></span>
                          <span className="text-gray-600">
                            {settings.payment.paypal_client_id && settings.payment.paypal_secret 
                              ? '✓ Credentials configured' 
                              : 'Enter credentials to enable PayPal checkout'}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  )}
                </Card>

                <Separator />

                {/* General Settings */}
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label>Currency</Label>
                    <Select value={settings.payment.currency || "CAD"} onValueChange={(value) => setSettings({...settings, payment: {...settings.payment, currency: value}})}>
                      <SelectTrigger className="w-full"><SelectValue placeholder="Select currency" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="CAD">🇨🇦 CAD - Canadian Dollar</SelectItem>
                        <SelectItem value="USD">🇺🇸 USD - US Dollar</SelectItem>
                        <SelectItem value="EUR">🇪🇺 EUR - Euro</SelectItem>
                        <SelectItem value="GBP">🇬🇧 GBP - British Pound</SelectItem>
                        <SelectItem value="INR">🇮🇳 INR - Indian Rupee</SelectItem>
                        <SelectItem value="AUD">🇦🇺 AUD - Australian Dollar</SelectItem>
                        <SelectItem value="JPY">🇯🇵 JPY - Japanese Yen</SelectItem>
                        <SelectItem value="CNY">🇨🇳 CNY - Chinese Yuan</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Tax Rate (%)</Label>
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={settings.payment.tax_rate ?? 13}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || /^\d*\.?\d*$/.test(val)) {
                          setSettings({...settings, payment: {...settings.payment, tax_rate: val === '' ? 0 : parseFloat(val) || 0}});
                        }
                      }}
                    />
                  </div>
                  <div>
                    <Label>Free Shipping Threshold ($)</Label>
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={settings.payment.free_shipping_threshold ?? 75}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || /^\d*\.?\d*$/.test(val)) {
                          setSettings({...settings, payment: {...settings.payment, free_shipping_threshold: val === '' ? 0 : parseFloat(val) || 0}});
                        }
                      }}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Live Chat Settings - AI Powered */}
            {activeSection === "livechat" && settings?.live_chat && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Bot className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">AI Chat Settings</h3>
                </div>

                <div className="p-4 bg-gradient-to-r from-[#F8A5B8]/10 to-purple-100/50 rounded-lg border border-[#F8A5B8]/20">
                  <p className="text-sm text-[#2D2A2E]">
                    <strong>🤖 AI-Powered Chat:</strong> Customers chat with an AI assistant that handles inquiries automatically. 
                    All conversations are saved and you can respond from the <strong>Customer Chats</strong> tab.
                  </p>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Enable Chat Widget</p>
                    <p className="text-sm text-[#5A5A5A]">Show AI chat button on website</p>
                  </div>
                  <Switch 
                    checked={settings.live_chat.enabled} 
                    onCheckedChange={(checked) => setSettings({...settings, live_chat: {...settings.live_chat, enabled: checked}})}
                  />
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Enable AI Auto-Responses</p>
                    <p className="text-sm text-[#5A5A5A]">AI responds to customer messages automatically</p>
                  </div>
                  <Switch 
                    checked={settings.live_chat.ai_enabled !== false} 
                    onCheckedChange={(checked) => setSettings({...settings, live_chat: {...settings.live_chat, ai_enabled: checked}})}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Chat Mode</Label>
                    <Select 
                      value={settings.live_chat.chat_mode || "ai_first"} 
                      onValueChange={(v) => setSettings({...settings, live_chat: {...settings.live_chat, chat_mode: v}})}
                    >
                      <SelectTrigger className="w-full"><SelectValue placeholder="Select chat mode" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ai_first">AI First (Recommended)</SelectItem>
                        <SelectItem value="manual">Manual Only</SelectItem>
                        <SelectItem value="hybrid">Hybrid</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-[#5A5A5A] mt-1">How chats are handled initially</p>
                  </div>
                  <div>
                    <Label>AI Model</Label>
                    <Select 
                      value={settings.live_chat.ai_model || "gpt-4o"} 
                      onValueChange={(v) => setSettings({...settings, live_chat: {...settings.live_chat, ai_model: v}})}
                    >
                      <SelectTrigger className="w-full"><SelectValue placeholder="Select AI model" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="gpt-4o">GPT-4o (Best)</SelectItem>
                        <SelectItem value="gpt-4o-mini">GPT-4o Mini (Faster)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div>
                  <Label>Notification Email</Label>
                  <Input
                    value={settings.live_chat.notification_email || "admin@reroots.ca"}
                    onChange={(e) => setSettings({...settings, live_chat: {...settings.live_chat, notification_email: e.target.value}})}
                    placeholder="admin@reroots.ca"
                  />
                  <p className="text-xs text-[#5A5A5A] mt-1">Where to send chat notifications</p>
                </div>

                <div>
                  <Label>Welcome Message</Label>
                  <Textarea
                    value={settings.live_chat.welcome_message || ""}
                    onChange={(e) => setSettings({...settings, live_chat: {...settings.live_chat, welcome_message: e.target.value}})}
                    placeholder="Hi! Welcome to ReRoots. How can we help you today?"
                  />
                </div>

                <div>
                  <Label>AI Greeting Message</Label>
                  <Textarea
                    value={settings.live_chat.ai_greeting || ""}
                    onChange={(e) => setSettings({...settings, live_chat: {...settings.live_chat, ai_greeting: e.target.value}})}
                    placeholder="Hello! I'm your ReRoots assistant. I can help you with product questions, orders, and more."
                  />
                </div>

                <div>
                  <Label>Offline/Escalation Message</Label>
                  <Textarea
                    value={settings.live_chat.offline_message || ""}
                    onChange={(e) => setSettings({...settings, live_chat: {...settings.live_chat, offline_message: e.target.value}})}
                    placeholder="Thanks for reaching out! A team member will assist you shortly."
                  />
                  <p className="text-xs text-[#5A5A5A] mt-1">Shown when customer asks for human agent</p>
                </div>

                <div>
                  <Label>Business Hours</Label>
                  <Input
                    value={settings.live_chat.business_hours || ""}
                    onChange={(e) => setSettings({...settings, live_chat: {...settings.live_chat, business_hours: e.target.value}})}
                    placeholder="Mon-Fri 9AM-6PM EST"
                  />
                </div>
              </div>
            )}

            {/* Promo Popup Settings */}
            {activeSection === "promo" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Megaphone className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Promo Popup</h3>
                </div>

                <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-lg">
                  <p className="text-sm text-purple-800">
                    <strong>🎉 Promotional Popup:</strong> Shows a beautiful discount popup on the login/signup page to attract new customers.
                  </p>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Enable Promo Popup</p>
                    <p className="text-sm text-[#5A5A5A]">Show discount popup on login page</p>
                  </div>
                  <Switch 
                    checked={settings?.promo_banner_enabled || false} 
                    onCheckedChange={(checked) => setSettings({...settings, promo_banner_enabled: checked})}
                  />
                </div>

                {/* Design Style Selection */}
                <div>
                  <Label className="text-sm font-medium mb-3 block">Popup Design Style</Label>
                  <div className="grid grid-cols-5 gap-3">
                    {[
                      { id: 'modern', name: 'Modern', desc: 'Gradient', emoji: '🌈' },
                      { id: 'classic', name: 'Classic', desc: 'Elegant', emoji: '✨' },
                      { id: 'minimal', name: 'Minimal', desc: 'Clean', emoji: '⬛' },
                      { id: 'bold', name: 'Bold', desc: 'Colorful', emoji: '🎊' },
                      { id: 'founders', name: 'Founders', desc: 'Premium', emoji: '💎' }
                    ].map(design => (
                      <button
                        key={design.id}
                        onClick={() => setSettings({...settings, promo_banner_design: design.id})}
                        className={`p-3 rounded-lg border-2 text-center transition-all ${
                          (settings?.promo_banner_design || 'modern') === design.id
                            ? 'border-purple-500 bg-purple-50'
                            : 'border-gray-200 hover:border-purple-300'
                        }`}
                      >
                        <div className="text-2xl mb-1">{design.emoji}</div>
                        <div className="text-xs font-medium">{design.name}</div>
                        <div className="text-xs text-gray-500">{design.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Badge Title (e.g. FOUNDER'S)</Label>
                    <Input
                      value={settings?.promo_banner_title || "FOUNDER'S"}
                      onChange={(e) => setSettings({...settings, promo_banner_title: e.target.value})}
                      onBlur={(e) => setSettings({...settings, promo_banner_title: e.target.value.toUpperCase()})}
                      placeholder="FOUNDER'S"
                      className="uppercase"
                    />
                  </div>
                  <div>
                    <Label>Discount Percentage</Label>
                    <Input
                      type="text"
                      inputMode="decimal"
                      value={settings?.promo_banner_discount_percent ?? ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || /^\d*\.?\d*$/.test(val)) {
                          setSettings({...settings, promo_banner_discount_percent: val === "" ? "" : val});
                        }
                      }}
                      onBlur={(e) => {
                        const val = e.target.value;
                        setSettings({...settings, promo_banner_discount_percent: val === "" ? 0 : Math.min(100, parseFloat(val) || 0)});
                      }}
                      placeholder="0-100"
                    />
                  </div>
                </div>

                <div>
                  <Label>Promo Code</Label>
                  <Input
                    value={settings?.promo_banner_code || "FOUNDER50"}
                    onChange={(e) => setSettings({...settings, promo_banner_code: e.target.value})}
                    onBlur={(e) => setSettings({...settings, promo_banner_code: e.target.value.toUpperCase()})}
                    placeholder="FOUNDER50"
                    className="uppercase font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Background Color</Label>
                    <div className="flex gap-2 mt-1">
                      <input 
                        type="color"
                        value={settings?.promo_banner_bg_color || "#F8A5B8"}
                        onChange={(e) => setSettings({...settings, promo_banner_bg_color: e.target.value})}
                        className="w-12 h-10 rounded border cursor-pointer"
                      />
                      <Input 
                        value={settings?.promo_banner_bg_color || "#F8A5B8"}
                        onChange={(e) => setSettings({...settings, promo_banner_bg_color: e.target.value})}
                      />
                    </div>
                  </div>
                  <div>
                    <Label>Text Color</Label>
                    <div className="flex gap-2 mt-1">
                      <input 
                        type="color"
                        value={settings?.promo_banner_text_color || "#FFFFFF"}
                        onChange={(e) => setSettings({...settings, promo_banner_text_color: e.target.value})}
                        className="w-12 h-10 rounded border cursor-pointer"
                      />
                      <Input 
                        value={settings?.promo_banner_text_color || "#FFFFFF"}
                        onChange={(e) => setSettings({...settings, promo_banner_text_color: e.target.value})}
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <Label>Click Link (where popup leads to)</Label>
                  <Input
                    value={settings?.promo_banner_link || "/shop"}
                    onChange={(e) => setSettings({...settings, promo_banner_link: e.target.value})}
                    placeholder="/shop"
                  />
                </div>

                <div>
                  <Label>Popup Position</Label>
                  <div className="grid grid-cols-5 gap-2 mt-2">
                    {[
                      { id: 'bottom-left', label: '↙️ Bottom Left' },
                      { id: 'bottom-right', label: '↘️ Bottom Right' },
                      { id: 'top-left', label: '↖️ Top Left' },
                      { id: 'top-right', label: '↗️ Top Right' },
                      { id: 'center', label: '⬜ Center' }
                    ].map(pos => (
                      <Button
                        key={pos.id}
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setSettings({...settings, promo_banner_position: pos.id})}
                        className={`text-xs ${(settings?.promo_banner_position || 'bottom-right') === pos.id ? 'ring-2 ring-primary bg-primary/10' : ''}`}
                      >
                        {pos.label}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>💡 Tip:</strong> The popup appears on the bottom-right corner of the login/signup page. Customers can click to copy the code.
                  </p>
                </div>
              </div>
            )}

            {/* First Purchase Bonus Settings */}
            {activeSection === "firstpurchase" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Gift className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">First Purchase Bonus</h3>
                </div>

                <div className="p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-800">
                    <strong>🎁 Auto-Discount:</strong> Automatically applies an extra discount on every customer's FIRST order. Stacks on top of all other discounts!
                  </p>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Enable First Purchase Bonus</p>
                    <p className="text-sm text-[#5A5A5A]">Auto-apply discount on first order</p>
                  </div>
                  <Switch 
                    checked={settings?.first_purchase_discount_enabled !== false} 
                    onCheckedChange={(checked) => setSettings({...settings, first_purchase_discount_enabled: checked})}
                  />
                </div>

                <div>
                  <Label>First Purchase Discount (%)</Label>
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={settings?.first_purchase_discount_percent ?? ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '' || /^\d*\.?\d*$/.test(val)) {
                        setSettings({...settings, first_purchase_discount_percent: val === "" ? "" : val});
                      }
                    }}
                    onBlur={(e) => {
                      const val = e.target.value;
                      setSettings({...settings, first_purchase_discount_percent: val === "" ? 0 : Math.min(100, parseFloat(val) || 0)});
                    }}
                    className="max-w-xs"
                    placeholder="0-100"
                  />
                  <p className="text-xs text-[#5A5A5A] mt-1">Set to 0 to disable without turning off the feature</p>
                </div>

                <Card className="border-2 border-green-200 bg-green-50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">📊 How Stacking Works</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span>Product Price:</span>
                        <span className="font-medium">$100</span>
                      </div>
                      <div className="flex justify-between text-orange-600">
                        <span>→ Product Discount (50%):</span>
                        <span>$50</span>
                      </div>
                      <div className="flex justify-between text-purple-600">
                        <span>→ Partner Code (30%):</span>
                        <span>$35</span>
                      </div>
                      <div className="flex justify-between text-green-600 font-medium">
                        <span>→ First Purchase Bonus ({settings?.first_purchase_discount_percent ?? 10}%):</span>
                        <span>${(35 * (1 - (settings?.first_purchase_discount_percent ?? 10) / 100)).toFixed(2)}</span>
                      </div>
                      <div className="border-t pt-2 flex justify-between font-bold">
                        <span>Customer Pays:</span>
                        <span className="text-green-600">${(35 * (1 - (settings?.first_purchase_discount_percent ?? 10) / 100)).toFixed(2)}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-sm text-amber-800">
                    <strong>⚠️ Note:</strong> This bonus applies automatically at checkout for new customers. They don't need to enter any code - it just shows as "First Purchase Bonus" in their order summary.
                  </p>
                </div>

                <Separator className="my-6" />

                {/* First Purchase CODE - Special code for new customers */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Ticket className="h-5 w-5 text-purple-500" />
                      First-Time Buyer Code
                    </CardTitle>
                    <CardDescription>
                      Create a special discount code that ONLY works for first-time buyers (new customers with no previous orders)
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Enable First-Time Buyer Code</p>
                        <p className="text-sm text-gray-500">Customers must enter this code manually at checkout</p>
                      </div>
                      <Switch 
                        checked={settings?.first_purchase_code_enabled !== false} 
                        onCheckedChange={(checked) => setSettings({...settings, first_purchase_code_enabled: checked})}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Discount Code</Label>
                        <Input
                          value={settings?.first_purchase_code || "SIGNUP25"}
                          onChange={(e) => setSettings({...settings, first_purchase_code: e.target.value})}
                          onBlur={(e) => setSettings({...settings, first_purchase_code: e.target.value.toUpperCase()})}
                          placeholder="SIGNUP25"
                          className="font-mono uppercase"
                        />
                        <p className="text-xs text-gray-500 mt-1">This is what customers will type at checkout</p>
                      </div>
                      <div>
                        <Label>Discount Percentage (%)</Label>
                        <Input
                          type="text"
                          inputMode="decimal"
                          value={settings?.first_purchase_code_percent ?? ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            if (val === '' || /^\d*\.?\d*$/.test(val)) {
                              setSettings({...settings, first_purchase_code_percent: val === "" ? "" : val});
                            }
                          }}
                          onBlur={(e) => {
                            const val = e.target.value;
                            setSettings({...settings, first_purchase_code_percent: val === "" ? 0 : Math.min(100, parseFloat(val) || 0)});
                          }}
                          placeholder="0-100"
                        />
                      </div>
                    </div>

                    <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
                      <p className="text-sm text-purple-800">
                        <strong>🎯 How it works:</strong> When a customer uses code <strong className="font-mono">{settings?.first_purchase_code || "SIGNUP25"}</strong>, the system checks if they have any previous orders. If they're a new customer, they get <strong>{settings?.first_purchase_code_percent ?? 25}% off</strong>. If they've ordered before, the code will be rejected with a message "This code is only for first-time buyers."
                      </p>
                    </div>

                    <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                      <p className="text-sm text-green-800">
                        <strong>💡 Pro tip:</strong> Use this code in your promo banner! Go to <strong>Promo Popup</strong> section and set the code to <strong className="font-mono">{settings?.first_purchase_code || "SIGNUP25"}</strong>
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Referral Program Rewards Settings */}
            {activeSection === "referral" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Users className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Referral Program Rewards</h3>
                </div>

                <div className="p-4 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>🎁 Referral Rewards:</strong> Configure what customers earn when they refer friends, and what their friends get as new customers.
                  </p>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Enable Referral Program</p>
                    <p className="text-sm text-[#5A5A5A]">Allow customers to refer friends and earn rewards</p>
                  </div>
                  <Switch 
                    checked={settings?.referral_program?.enabled !== false} 
                    onCheckedChange={(checked) => setSettings({
                      ...settings, 
                      referral_program: {...(settings?.referral_program || {}), enabled: checked}
                    })}
                  />
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Gift className="h-5 w-5 text-green-500" />
                      Referrer Rewards (Person Who Refers)
                    </CardTitle>
                    <CardDescription>
                      What does the customer who refers a friend receive?
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Reward Type</Label>
                        <Select 
                          value={settings?.referral_program?.referrer_reward_type || "fixed_amount"} 
                          onValueChange={(v) => setSettings({
                            ...settings, 
                            referral_program: {...(settings?.referral_program || {}), referrer_reward_type: v}
                          })}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select reward type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="fixed_amount">Fixed Amount ($)</SelectItem>
                            <SelectItem value="percentage">Percentage (%)</SelectItem>
                            <SelectItem value="free_product">Free Product</SelectItem>
                            <SelectItem value="points">Store Points</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>
                          Reward Value {settings?.referral_program?.referrer_reward_type === "percentage" ? "(%)" : "($)"}
                        </Label>
                        <Input
                          type="text"
                          inputMode="decimal"
                          value={settings?.referral_program?.referrer_reward_value ?? ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            if (val === '' || /^\d*\.?\d*$/.test(val)) {
                              setSettings({
                                ...settings, 
                                referral_program: {...(settings?.referral_program || {}), referrer_reward_value: val === "" ? "" : val}
                              });
                            }
                          }}
                          onBlur={(e) => {
                            const val = e.target.value;
                            setSettings({
                              ...settings, 
                              referral_program: {...(settings?.referral_program || {}), referrer_reward_value: val === "" ? 10 : parseFloat(val) || 10}
                            });
                          }}
                          placeholder="10"
                        />
                      </div>
                    </div>
                    <div>
                      <Label>Reward Label (shown to customers)</Label>
                      <Input
                        value={settings?.referral_program?.referrer_reward_label || "$10 Store Credit"}
                        onChange={(e) => setSettings({
                          ...settings, 
                          referral_program: {...(settings?.referral_program || {}), referrer_reward_label: e.target.value}
                        })}
                        placeholder="$10 Store Credit"
                      />
                      <p className="text-xs text-gray-500 mt-1">This text appears in the referral widget</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Heart className="h-5 w-5 text-pink-500" />
                      Referee Rewards (New Customer)
                    </CardTitle>
                    <CardDescription>
                      What does the friend who signs up receive?
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Reward Type</Label>
                        <Select 
                          value={settings?.referral_program?.referee_reward_type || "fixed_amount"} 
                          onValueChange={(v) => setSettings({
                            ...settings, 
                            referral_program: {...(settings?.referral_program || {}), referee_reward_type: v}
                          })}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select reward type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="fixed_amount">Fixed Amount ($)</SelectItem>
                            <SelectItem value="percentage">Percentage (%)</SelectItem>
                            <SelectItem value="free_shipping">Free Shipping</SelectItem>
                            <SelectItem value="free_sample">Free Sample</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>
                          Reward Value {settings?.referral_program?.referee_reward_type === "percentage" ? "(%)" : "($)"}
                        </Label>
                        <Input
                          type="text"
                          inputMode="decimal"
                          value={settings?.referral_program?.referee_reward_value ?? ""}
                          onChange={(e) => {
                            const val = e.target.value;
                            if (val === '' || /^\d*\.?\d*$/.test(val)) {
                              setSettings({
                                ...settings, 
                                referral_program: {...(settings?.referral_program || {}), referee_reward_value: val === "" ? "" : val}
                              });
                            }
                          }}
                          onBlur={(e) => {
                            const val = e.target.value;
                            setSettings({
                              ...settings, 
                              referral_program: {...(settings?.referral_program || {}), referee_reward_value: val === "" ? 10 : parseFloat(val) || 10}
                            });
                          }}
                          placeholder="10"
                        />
                      </div>
                    </div>
                    <div>
                      <Label>Reward Label (shown to customers)</Label>
                      <Input
                        value={settings?.referral_program?.referee_reward_label || "$10 Off Your First Order"}
                        onChange={(e) => setSettings({
                          ...settings, 
                          referral_program: {...(settings?.referral_program || {}), referee_reward_label: e.target.value}
                        })}
                        placeholder="$10 Off Your First Order"
                      />
                      <p className="text-xs text-gray-500 mt-1">This text appears in the referral widget</p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-yellow-500" />
                      Widget Customization
                    </CardTitle>
                    <CardDescription>
                      Customize the referral popup widget that appears on your site
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div>
                        <p className="font-medium">Enable Referral Widget</p>
                        <p className="text-sm text-[#5A5A5A]">Show floating referral button on site</p>
                      </div>
                      <Switch 
                        checked={settings?.referral_program?.widget_enabled !== false} 
                        onCheckedChange={(checked) => setSettings({
                          ...settings, 
                          referral_program: {...(settings?.referral_program || {}), widget_enabled: checked}
                        })}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Button Text</Label>
                        <Input
                          value={settings?.referral_program?.widget_button_text || `Get ${brandName} FREE`}
                          onChange={(e) => setSettings({
                            ...settings, 
                            referral_program: {...(settings?.referral_program || {}), widget_button_text: e.target.value}
                          })}
                          placeholder={`Get ${brandName} FREE`}
                        />
                      </div>
                      <div>
                        <Label>Button Color</Label>
                        <div className="flex gap-2 mt-1">
                          <input 
                            type="color"
                            value={settings?.referral_program?.widget_button_color || "#D4AF37"}
                            onChange={(e) => setSettings({
                              ...settings, 
                              referral_program: {...(settings?.referral_program || {}), widget_button_color: e.target.value}
                            })}
                            className="w-12 h-10 rounded border cursor-pointer"
                          />
                          <Input 
                            value={settings?.referral_program?.widget_button_color || "#D4AF37"}
                            onChange={(e) => setSettings({
                              ...settings, 
                              referral_program: {...(settings?.referral_program || {}), widget_button_color: e.target.value}
                            })}
                          />
                        </div>
                      </div>
                    </div>

                    <div>
                      <Label>Popup Title</Label>
                      <Input
                        value={settings?.referral_program?.widget_popup_title || "Share the Glow ✨"}
                        onChange={(e) => setSettings({
                          ...settings, 
                          referral_program: {...(settings?.referral_program || {}), widget_popup_title: e.target.value}
                        })}
                        placeholder="Share the Glow ✨"
                      />
                    </div>

                    <div>
                      <Label>Share Message</Label>
                      <Textarea
                        value={settings?.referral_program?.widget_share_message || "I love ReRoots skincare! Use my link for $10 off your first order:"}
                        onChange={(e) => setSettings({
                          ...settings, 
                          referral_program: {...(settings?.referral_program || {}), widget_share_message: e.target.value}
                        })}
                        placeholder="I love ReRoots skincare! Use my link for $10 off your first order:"
                        rows={2}
                      />
                      <p className="text-xs text-gray-500 mt-1">Message pre-filled when customers share via WhatsApp or social media</p>
                    </div>

                    <div>
                      <Label>Widget Position</Label>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
                        {[
                          { id: 'bottom-right', label: '↘️ Bottom Right' },
                          { id: 'bottom-left', label: '↙️ Bottom Left' },
                          { id: 'side-right', label: '→ Side Right' },
                          { id: 'side-left', label: '← Side Left' }
                        ].map(pos => (
                          <Button
                            key={pos.id}
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => setSettings({
                              ...settings, 
                              referral_program: {...(settings?.referral_program || {}), widget_position: pos.id}
                            })}
                            className={`text-xs whitespace-nowrap ${(settings?.referral_program?.widget_position || 'bottom-right') === pos.id ? 'ring-2 ring-primary bg-primary/10' : ''}`}
                          >
                            {pos.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>💡 Tip:</strong> The referral widget appears on all pages. Customers can share their unique link to earn rewards when friends sign up and make purchases.
                  </p>
                </div>
              </div>
            )}

            {/* Language & Region Settings */}
            {activeSection === "language" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Globe className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Language & Region</h3>
                </div>

                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>🌍 Global Selling:</strong> Configure language options to serve customers worldwide. The website will automatically display in the customer's preferred language.
                  </p>
                </div>

                <div>
                  <Label>Default Language</Label>
                  <Select 
                    value={settings?.language?.default_language || "en-CA"} 
                    onValueChange={(value) => setSettings({...settings, language: {...(settings.language || {}), default_language: value}})}
                  >
                    <SelectTrigger className="w-full"><SelectValue placeholder="Select language" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en-CA">🇨🇦 English (Canada)</SelectItem>
                      <SelectItem value="en">🇬🇧 English (UK)</SelectItem>
                      <SelectItem value="en-US">🇺🇸 English (US)</SelectItem>
                      <SelectItem value="fr">🇫🇷 Français (French)</SelectItem>
                      <SelectItem value="es">🇪🇸 Español (Spanish)</SelectItem>
                      <SelectItem value="hi">🇮🇳 हिंदी (Hindi)</SelectItem>
                      <SelectItem value="zh">🇨🇳 中文 (Chinese)</SelectItem>
                      <SelectItem value="ar">🇸🇦 العربية (Arabic)</SelectItem>
                      <SelectItem value="pt">🇧🇷 Português (Portuguese)</SelectItem>
                      <SelectItem value="de">🇩🇪 Deutsch (German)</SelectItem>
                      <SelectItem value="ja">🇯🇵 日本語 (Japanese)</SelectItem>
                      <SelectItem value="ko">🇰🇷 한국어 (Korean)</SelectItem>
                      <SelectItem value="ru">🇷🇺 Русский (Russian)</SelectItem>
                      <SelectItem value="it">🇮🇹 Italiano (Italian)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Auto-Detect Language</p>
                    <p className="text-sm text-[#5A5A5A]">Automatically detect visitor's browser language</p>
                  </div>
                  <Switch 
                    checked={settings?.language?.auto_detect !== false} 
                    onCheckedChange={(c) => setSettings({...settings, language: {...(settings.language || {}), auto_detect: c}})}
                  />
                </div>

                <div>
                  <Label>Enabled Languages</Label>
                  <p className="text-xs text-[#5A5A5A] mb-2">Select which languages are available to customers (37 languages available)</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-96 overflow-y-auto p-2 border rounded-lg">
                    {[
                      { code: "en-CA", name: "🇨🇦 English (Canada)" },
                      { code: "en", name: "🇬🇧 English (UK)" },
                      { code: "en-US", name: "🇺🇸 English (US)" },
                      { code: "fr", name: "🇫🇷 French" },
                      { code: "es", name: "🇪🇸 Spanish" },
                      { code: "hi", name: "🇮🇳 Hindi" },
                      { code: "zh", name: "🇨🇳 Chinese" },
                      { code: "ar", name: "🇸🇦 Arabic" },
                      { code: "pt", name: "🇧🇷 Portuguese" },
                      { code: "de", name: "🇩🇪 German" },
                      { code: "ja", name: "🇯🇵 Japanese" },
                      { code: "ko", name: "🇰🇷 Korean" },
                      { code: "ru", name: "🇷🇺 Russian" },
                      { code: "it", name: "🇮🇹 Italian" },
                      { code: "nl", name: "🇳🇱 Dutch" },
                      { code: "tr", name: "🇹🇷 Turkish" },
                      { code: "pl", name: "🇵🇱 Polish" },
                      { code: "th", name: "🇹🇭 Thai" },
                      { code: "vi", name: "🇻🇳 Vietnamese" },
                      { code: "id", name: "🇮🇩 Indonesian" },
                      { code: "ms", name: "🇲🇾 Malay" },
                      { code: "bn", name: "🇧🇩 Bengali" },
                      { code: "ta", name: "🇮🇳 Tamil" },
                      { code: "te", name: "🇮🇳 Telugu" },
                      { code: "mr", name: "🇮🇳 Marathi" },
                      { code: "gu", name: "🇮🇳 Gujarati" },
                      { code: "pa", name: "🇮🇳 Punjabi" },
                      { code: "ur", name: "🇵🇰 Urdu" },
                      { code: "fa", name: "🇮🇷 Persian" },
                      { code: "he", name: "🇮🇱 Hebrew" },
                      { code: "sv", name: "🇸🇪 Swedish" },
                      { code: "no", name: "🇳🇴 Norwegian" },
                      { code: "da", name: "🇩🇰 Danish" },
                      { code: "fi", name: "🇫🇮 Finnish" },
                      { code: "el", name: "🇬🇷 Greek" },
                      { code: "cs", name: "🇨🇿 Czech" },
                      { code: "ro", name: "🇷🇴 Romanian" },
                      { code: "hu", name: "🇭🇺 Hungarian" },
                      { code: "uk", name: "🇺🇦 Ukrainian" }
                    ].map(lang => (
                      <label key={lang.code} className="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={(settings?.language?.supported_languages || ["en"]).includes(lang.code)}
                          onChange={(e) => {
                            const current = settings?.language?.supported_languages || ["en"];
                            const updated = e.target.checked 
                              ? [...current, lang.code]
                              : current.filter(l => l !== lang.code);
                            setSettings({...settings, language: {...(settings.language || {}), supported_languages: updated}});
                          }}
                          className="rounded"
                        />
                        <span className="text-sm">{lang.name}</span>
                      </label>
                    ))}
                  </div>
                  <p className="text-xs text-green-600 mt-2">✨ AI-powered instant translation for all content</p>
                </div>

                {/* Chat Translation Info */}
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <h4 className="font-medium text-blue-800 mb-2">💬 Chat Auto-Translation</h4>
                  <p className="text-sm text-blue-700">When customers write in their language, messages are automatically translated to English for you in the admin chat view.</p>
                </div>
              </div>
            )}

            {/* Thank You Messages */}
            {activeSection === "thankyou" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Heart className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Thank You Messages</h3>
                </div>

                <div className="p-4 bg-pink-50 border border-pink-200 rounded-lg">
                  <p className="text-sm text-pink-800">
                    <strong>💝 Customize Messages:</strong> Personalize the thank you messages shown to customers after various actions. These messages help build customer loyalty and improve user experience.
                  </p>
                </div>

                <div>
                  <Label>After Newsletter Subscription</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.subscription || "Thank you for subscribing! You'll receive exclusive offers and skincare tips."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), subscription: e.target.value}})}
                    placeholder="Thank you for subscribing!"
                    rows={3}
                  />
                </div>

                <div>
                  <Label>After Successful Payment/Order</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.payment || "Thank you for your purchase! Your order has been confirmed. We'll send you a confirmation email shortly."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), payment: e.target.value}})}
                    placeholder="Thank you for your purchase!"
                    rows={3}
                  />
                </div>

                <div>
                  <Label>After Chat Session Ends</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.chat || "Thank you for chatting with us! We hope we were able to help. Feel free to reach out again anytime."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), chat: e.target.value}})}
                    placeholder="Thank you for chatting with us!"
                    rows={3}
                  />
                </div>

                <div>
                  <Label>After Leaving a Review</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.review || "Thank you for your review! Your feedback helps us improve and helps other customers make informed decisions."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), review: e.target.value}})}
                    placeholder="Thank you for your review!"
                    rows={3}
                  />
                </div>

                <div>
                  <Label>After Account Registration</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.registration || "Welcome to ReRoots! Your account has been created successfully. Start exploring our premium skincare collection."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), registration: e.target.value}})}
                    placeholder="Welcome! Your account has been created."
                    rows={3}
                  />
                </div>

                <div>
                  <Label>After Callback Request</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.callback || "Thank you for your callback request! Our team will contact you within 24 hours."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), callback: e.target.value}})}
                    placeholder="Thank you for your callback request!"
                    rows={3}
                  />
                </div>

                <div>
                  <Label>After Partner/Influencer Application</Label>
                  <Textarea
                    value={settings?.thank_you_messages?.partner_application || "Thank you for applying to become a ReRoots Partner! 🌟 We're excited to review your application. Our team will get back to you within 48-72 hours with the next steps."}
                    onChange={(e) => setSettings({...settings, thank_you_messages: {...(settings.thank_you_messages || {}), partner_application: e.target.value}})}
                    placeholder="Thank you for applying to become a partner!"
                    rows={3}
                  />
                  <p className="text-xs text-[#5A5A5A] mt-1">This message is shown after someone submits a partner/influencer application</p>
                </div>
              </div>
            )}

            {/* Security Settings */}
            {activeSection === "security" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Security Settings</h3>
                </div>

                {/* Two-Factor Authentication */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                          <Lock className="h-5 w-5 text-green-600" />
                        </div>
                        <div>
                          <p className="font-medium">Two-Factor Authentication (2FA)</p>
                          <p className="text-sm text-[#5A5A5A]">Add an extra layer of security to admin accounts</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.two_factor_enabled || false}
                        onCheckedChange={(checked) => setSettings({
                          ...settings, 
                          security: { ...(settings?.security || {}), two_factor_enabled: checked }
                        })}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Admin Login Alerts */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <Bell className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="font-medium">Admin Login Alerts</p>
                          <p className="text-sm text-[#5A5A5A]">Get notified when an admin logs in</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.login_alerts || false}
                        onCheckedChange={(checked) => setSettings({
                          ...settings, 
                          security: { ...(settings?.security || {}), login_alerts: checked }
                        })}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Suspicious Activity Alerts */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
                          <AlertTriangle className="h-5 w-5 text-yellow-600" />
                        </div>
                        <div>
                          <p className="font-medium">Suspicious Activity Alerts</p>
                          <p className="text-sm text-[#5A5A5A]">Get notified of failed login attempts and unusual activity</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.suspicious_alerts || false}
                        onCheckedChange={(checked) => setSettings({
                          ...settings, 
                          security: { ...(settings?.security || {}), suspicious_alerts: checked }
                        })}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Rate Limiting */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                          <Clock className="h-5 w-5 text-purple-600" />
                        </div>
                        <div>
                          <p className="font-medium">Rate Limiting</p>
                          <p className="text-sm text-[#5A5A5A]">Limit login attempts to prevent brute force attacks</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.rate_limiting || true}
                        onCheckedChange={(checked) => setSettings({
                          ...settings, 
                          security: { ...(settings?.security || {}), rate_limiting: checked }
                        })}
                      />
                    </div>
                    {(settings?.security?.rate_limiting !== false) && (
                      <div className="mt-4 pl-12 grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-sm">Max Login Attempts</Label>
                          <Input 
                            type="number" 
                            min="3" 
                            max="10"
                            value={settings?.security?.max_login_attempts || 5}
                            onChange={(e) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), max_login_attempts: parseInt(e.target.value) || 5 }
                            })}
                          />
                        </div>
                        <div>
                          <Label className="text-sm">Lockout Duration (minutes)</Label>
                          <Input 
                            type="number" 
                            min="5" 
                            max="60"
                            value={settings?.security?.lockout_duration || 15}
                            onChange={(e) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), lockout_duration: parseInt(e.target.value) || 15 }
                            })}
                          />
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Session Timeout */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                        <Timer className="h-5 w-5 text-orange-600" />
                      </div>
                      <div>
                        <p className="font-medium">Session Timeout</p>
                        <p className="text-sm text-[#5A5A5A]">Automatically log out inactive admin users</p>
                      </div>
                    </div>
                    <div className="pl-12">
                      <Label className="text-sm">Session Timeout (minutes)</Label>
                      <Select 
                        value={String(settings?.security?.session_timeout || 60)}
                        onValueChange={(value) => setSettings({
                          ...settings,
                          security: { ...(settings?.security || {}), session_timeout: parseInt(value) }
                        })}
                      >
                        <SelectTrigger className="w-full max-w-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="15">15 minutes</SelectItem>
                          <SelectItem value="30">30 minutes</SelectItem>
                          <SelectItem value="60">1 hour</SelectItem>
                          <SelectItem value="120">2 hours</SelectItem>
                          <SelectItem value="480">8 hours</SelectItem>
                          <SelectItem value="1440">24 hours</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </CardContent>
                </Card>

                {/* Password Requirements */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                        <Key className="h-5 w-5 text-red-600" />
                      </div>
                      <div>
                        <p className="font-medium">Password Requirements</p>
                        <p className="text-sm text-[#5A5A5A]">Set minimum password security standards</p>
                      </div>
                    </div>
                    <div className="pl-12 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm">Minimum 8 characters</span>
                        <Switch 
                          checked={settings?.security?.password_min_length || true}
                          onCheckedChange={(checked) => setSettings({
                            ...settings,
                            security: { ...(settings?.security || {}), password_min_length: checked }
                          })}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm">Require uppercase letter</span>
                        <Switch 
                          checked={settings?.security?.password_uppercase || false}
                          onCheckedChange={(checked) => setSettings({
                            ...settings,
                            security: { ...(settings?.security || {}), password_uppercase: checked }
                          })}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm">Require number</span>
                        <Switch 
                          checked={settings?.security?.password_number || false}
                          onCheckedChange={(checked) => setSettings({
                            ...settings,
                            security: { ...(settings?.security || {}), password_number: checked }
                          })}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm">Require special character</span>
                        <Switch 
                          checked={settings?.security?.password_special || false}
                          onCheckedChange={(checked) => setSettings({
                            ...settings,
                            security: { ...(settings?.security || {}), password_special: checked }
                          })}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* IP Whitelist */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                          <Globe className="h-5 w-5 text-indigo-600" />
                        </div>
                        <div>
                          <p className="font-medium">Admin IP Whitelist</p>
                          <p className="text-sm text-[#5A5A5A]">Only allow admin access from specific IP addresses</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.ip_whitelist_enabled || false}
                        onCheckedChange={(checked) => setSettings({
                          ...settings,
                          security: { ...(settings?.security || {}), ip_whitelist_enabled: checked }
                        })}
                      />
                    </div>
                    {settings?.security?.ip_whitelist_enabled && (
                      <div className="pl-12">
                        <Label className="text-sm">Allowed IP Addresses (one per line)</Label>
                        <Textarea 
                          placeholder="192.168.1.1&#10;10.0.0.0/24"
                          rows={4}
                          value={settings?.security?.ip_whitelist || ''}
                          onChange={(e) => setSettings({
                            ...settings,
                            security: { ...(settings?.security || {}), ip_whitelist: e.target.value }
                          })}
                        />
                        <p className="text-xs text-[#9A9A9A] mt-1">Supports individual IPs and CIDR notation</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* HTTPS Enforcement */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                          <ShieldCheck className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div>
                          <p className="font-medium">Force HTTPS</p>
                          <p className="text-sm text-[#5A5A5A]">Redirect all HTTP requests to HTTPS</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.force_https || true}
                        onCheckedChange={(checked) => setSettings({
                          ...settings,
                          security: { ...(settings?.security || {}), force_https: checked }
                        })}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Fraud Detection */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center">
                          <UserX className="h-5 w-5 text-rose-600" />
                        </div>
                        <div>
                          <p className="font-medium">Fraud Detection</p>
                          <p className="text-sm text-[#5A5A5A]">Flag suspicious orders for review</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.fraud_detection || false}
                        onCheckedChange={(checked) => setSettings({
                          ...settings,
                          security: { ...(settings?.security || {}), fraud_detection: checked }
                        })}
                      />
                    </div>
                    {settings?.security?.fraud_detection && (
                      <div className="mt-4 pl-12 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm">Flag orders over $500</span>
                          <Switch 
                            checked={settings?.security?.flag_high_value || true}
                            onCheckedChange={(checked) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), flag_high_value: checked }
                            })}
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm">Flag different billing/shipping address</span>
                          <Switch 
                            checked={settings?.security?.flag_address_mismatch || false}
                            onCheckedChange={(checked) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), flag_address_mismatch: checked }
                            })}
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm">Flag international orders</span>
                          <Switch 
                            checked={settings?.security?.flag_international || false}
                            onCheckedChange={(checked) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), flag_international: checked }
                            })}
                          />
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Activity Log */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                          <FileText className="h-5 w-5 text-slate-600" />
                        </div>
                        <div>
                          <p className="font-medium">Activity Logging</p>
                          <p className="text-sm text-[#5A5A5A]">Keep detailed logs of all admin actions</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.activity_logging || true}
                        onCheckedChange={(checked) => setSettings({
                          ...settings,
                          security: { ...(settings?.security || {}), activity_logging: checked }
                        })}
                      />
                    </div>
                    {(settings?.security?.activity_logging !== false) && (
                      <div className="mt-4 pl-12">
                        <Label className="text-sm">Log Retention Period</Label>
                        <Select 
                          value={String(settings?.security?.log_retention_days || 90)}
                          onValueChange={(value) => setSettings({
                            ...settings,
                            security: { ...(settings?.security || {}), log_retention_days: parseInt(value) }
                          })}
                        >
                          <SelectTrigger className="w-full max-w-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="30">30 days</SelectItem>
                            <SelectItem value="60">60 days</SelectItem>
                            <SelectItem value="90">90 days</SelectItem>
                            <SelectItem value="180">6 months</SelectItem>
                            <SelectItem value="365">1 year</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* reCAPTCHA */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-cyan-100 flex items-center justify-center">
                          <Bot className="h-5 w-5 text-cyan-600" />
                        </div>
                        <div>
                          <p className="font-medium">reCAPTCHA Protection</p>
                          <p className="text-sm text-[#5A5A5A]">Protect forms from spam and bots</p>
                        </div>
                      </div>
                      <Switch 
                        checked={settings?.security?.recaptcha_enabled || false}
                        onCheckedChange={(checked) => setSettings({
                          ...settings,
                          security: { ...(settings?.security || {}), recaptcha_enabled: checked }
                        })}
                      />
                    </div>
                    {settings?.security?.recaptcha_enabled && (
                      <div className="pl-12 space-y-3">
                        <div>
                          <Label className="text-sm">reCAPTCHA Site Key</Label>
                          <Input 
                            placeholder="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
                            value={settings?.security?.recaptcha_site_key || ''}
                            onChange={(e) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), recaptcha_site_key: e.target.value }
                            })}
                          />
                        </div>
                        <div>
                          <Label className="text-sm">reCAPTCHA Secret Key</Label>
                          <Input 
                            type="password"
                            placeholder="Enter secret key"
                            value={settings?.security?.recaptcha_secret_key || ''}
                            onChange={(e) => setSettings({
                              ...settings,
                              security: { ...(settings?.security || {}), recaptcha_secret_key: e.target.value }
                            })}
                          />
                        </div>
                        <div className="space-y-2">
                          <p className="text-sm font-medium">Enable reCAPTCHA on:</p>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Login form</span>
                            <Switch 
                              checked={settings?.security?.recaptcha_login || true}
                              onCheckedChange={(checked) => setSettings({
                                ...settings,
                                security: { ...(settings?.security || {}), recaptcha_login: checked }
                              })}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Registration form</span>
                            <Switch 
                              checked={settings?.security?.recaptcha_register || true}
                              onCheckedChange={(checked) => setSettings({
                                ...settings,
                                security: { ...(settings?.security || {}), recaptcha_register: checked }
                              })}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Contact form</span>
                            <Switch 
                              checked={settings?.security?.recaptcha_contact || false}
                              onCheckedChange={(checked) => setSettings({
                                ...settings,
                                security: { ...(settings?.security || {}), recaptcha_contact: checked }
                              })}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">Checkout</span>
                            <Switch 
                              checked={settings?.security?.recaptcha_checkout || false}
                              onCheckedChange={(checked) => setSettings({
                                ...settings,
                                security: { ...(settings?.security || {}), recaptcha_checkout: checked }
                              })}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

              </div>
            )}

            {/* Google Business Settings */}
            {activeSection === "google" && settings?.google_business && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <MapPin className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Google Business</h3>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium">Enable Google Business Integration</p>
                    <p className="text-sm text-[#5A5A5A]">Show Google reviews and maps link</p>
                  </div>
                  <Switch 
                    checked={settings.google_business.enabled} 
                    onCheckedChange={(checked) => setSettings({...settings, google_business: {...settings.google_business, enabled: checked}})}
                  />
                </div>

                <div>
                  <Label>Business Name</Label>
                  <Input
                    value={settings.google_business.business_name || ""}
                    onChange={(e) => setSettings({...settings, google_business: {...settings.google_business, business_name: e.target.value}})}
                    placeholder="ReRoots"
                  />
                </div>

                <div>
                  <Label>Google Place ID</Label>
                  <Input
                    value={settings.google_business.place_id || ""}
                    onChange={(e) => setSettings({...settings, google_business: {...settings.google_business, place_id: e.target.value}})}
                    placeholder="ChIJ..."
                  />
                  <p className="text-xs text-[#5A5A5A] mt-1">
                    Find your Place ID at <a href="https://developers.google.com/maps/documentation/places/web-service/place-id" target="_blank" rel="noopener noreferrer" className="text-[#F8A5B8] underline">Google Place ID Finder</a>
                  </p>
                </div>

                <div>
                  <Label>Google Review URL</Label>
                  <Input
                    value={settings.google_business.review_url || ""}
                    onChange={(e) => setSettings({...settings, google_business: {...settings.google_business, review_url: e.target.value}})}
                    placeholder="https://g.page/r/..."
                  />
                </div>

                <div>
                  <Label>Google Maps URL</Label>
                  <Input
                    value={settings.google_business.maps_url || ""}
                    onChange={(e) => setSettings({...settings, google_business: {...settings.google_business, maps_url: e.target.value}})}
                    placeholder="https://maps.google.com/..."
                  />
                </div>
              </div>
            )}

            {/* Notification Settings */}
            {activeSection === "notifications" && settings?.notifications && (
              <NotificationsSection settings={settings} setSettings={setSettings} />
            )}

            {/* Login Background */}
            {activeSection === "loginbg" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Image className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Site Background Settings</h3>
                </div>
                
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <p className="text-sm text-amber-800">
                    <strong>💡 Tip:</strong> For best results in production, use external image URLs from services like Unsplash, Cloudinary, or Imgur. Local uploads may not persist after deployment.
                  </p>
                  <p className="text-xs text-amber-600 mt-2">
                    Example: https://images.unsplash.com/photo-1556228720-195a672e8a03?w=1200
                  </p>
                </div>

                {/* Global Site Background - NEW */}
                <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                          🌐 Global Site Background
                          <Badge className="bg-purple-100 text-purple-800">One-Click for ALL Pages</Badge>
                        </CardTitle>
                        <CardDescription>Apply one background to ALL pages (customer & admin)</CardDescription>
                      </div>
                      <Switch 
                        checked={settings?.global_background_enabled || false}
                        onCheckedChange={async (checked) => {
                          const newSettings = {...settings, global_background_enabled: checked};
                          setSettings(newSettings);
                          try {
                            const token = localStorage.getItem("admin_token");
                            await axios.put(`${API}/admin/store-settings/global-background`, 
                              { global_background_enabled: checked },
                              { headers: { Authorization: `Bearer ${token}` }}
                            );
                            toast.success(checked ? "Global background enabled!" : "Global background disabled");
                            window.location.reload(); // Refresh to apply changes
                          } catch (error) {
                            toast.error("Failed to update");
                          }
                        }}
                      />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Background Image URL</Label>
                      <Input
                        value={settings?.global_site_background || ""}
                        onChange={(e) => setSettings({...settings, global_site_background: e.target.value})}
                        placeholder="https://images.unsplash.com/photo-xxxxx?w=1920"
                      />
                    </div>
                    
                    <div>
                      <Label className="block mb-2">Or Upload Image</Label>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={async (e) => {
                          const file = e.target.files[0];
                          if (!file) return;
                          const formData = new FormData();
                          formData.append("file", file);
                          try {
                            const res = await axios.post(`${API}/upload/image`, formData, {
                              headers: { "Content-Type": "multipart/form-data" }
                            });
                            const imageUrl = res.data.url.startsWith('http') ? res.data.url : `${BACKEND_URL}${res.data.url}`;
                            setSettings({...settings, global_site_background: imageUrl});
                            if (res.data.permanent) {
                              toast.success("Image uploaded permanently!");
                            } else {
                              toast.success("Image uploaded!");
                            }
                          } catch (error) {
                            toast.error("Upload failed");
                          }
                        }}
                        className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Background Visibility</Label>
                        <div className="flex items-center gap-2 mt-2">
                          <input 
                            type="range" 
                            min="0.05" 
                            max="0.5" 
                            step="0.05"
                            value={settings?.global_background_opacity || 0.15}
                            onChange={(e) => setSettings({...settings, global_background_opacity: parseFloat(e.target.value)})}
                            className="flex-1"
                          />
                          <span className="text-sm text-gray-600 w-12">{Math.round((settings?.global_background_opacity || 0.15) * 100)}%</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">Lower = more visible background</p>
                      </div>
                      <div>
                        <Label>Overlay Color</Label>
                        <div className="flex items-center gap-2 mt-2">
                          <input 
                            type="color"
                            value={settings?.global_background_overlay_color || "#FFFFFF"}
                            onChange={(e) => setSettings({...settings, global_background_overlay_color: e.target.value})}
                            className="w-10 h-10 rounded border cursor-pointer"
                          />
                          <Input 
                            value={settings?.global_background_overlay_color || "#FFFFFF"}
                            onChange={(e) => setSettings({...settings, global_background_overlay_color: e.target.value})}
                            className="flex-1"
                          />
                        </div>
                      </div>
                    </div>

                    {settings?.global_site_background && (
                      <div className="mt-4">
                        <Label className="block mb-2">Preview</Label>
                        <div className="w-full h-48 rounded-lg overflow-hidden border relative">
                          <img 
                            src={settings.global_site_background} 
                            alt="Global background" 
                            className="w-full h-full object-cover"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                          <div 
                            className="absolute inset-0"
                            style={{
                              backgroundColor: settings?.global_background_overlay_color || "#FFFFFF",
                              opacity: 1 - (settings?.global_background_opacity || 0.15)
                            }}
                          />
                        </div>
                        <div className="flex gap-2 mt-2">
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="text-red-500"
                            onClick={() => setSettings({...settings, global_site_background: ""})}
                          >
                            <Trash2 className="h-4 w-4 mr-1" /> Remove
                          </Button>
                          <Button 
                            size="sm" 
                            className="bg-purple-600 hover:bg-purple-700"
                            onClick={async () => {
                              try {
                                const token = localStorage.getItem("admin_token");
                                await axios.put(`${API}/admin/store-settings/global-background`, {
                                  global_site_background: settings?.global_site_background,
                                  global_background_opacity: settings?.global_background_opacity,
                                  global_background_overlay_color: settings?.global_background_overlay_color,
                                  global_background_enabled: true
                                }, { headers: { Authorization: `Bearer ${token}` }});
                                toast.success("Global background saved! Refreshing...");
                                setTimeout(() => window.location.reload(), 1000);
                              } catch (error) {
                                toast.error("Failed to save");
                              }
                            }}
                          >
                            Apply to All Pages
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="p-3 bg-purple-100 rounded-lg">
                      <p className="text-sm text-purple-800">
                        <strong>🎨 How it works:</strong> When enabled, this background applies to:
                      </p>
                      <ul className="text-xs text-purple-700 mt-1 space-y-1">
                        <li>✓ Homepage, Shop, Product pages</li>
                        <li>✓ Cart, Checkout, Account pages</li>
                        <li>✓ Admin Dashboard</li>
                        <li>✓ All other pages</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>

                {/* Live/Animated Backgrounds Section */}
                <Card className="border-2 border-pink-200 bg-gradient-to-br from-pink-50 to-purple-50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      🎬 Live/Animated Backgrounds
                      <Badge className="bg-pink-100 text-pink-800">NEW</Badge>
                    </CardTitle>
                    <CardDescription>Add dynamic motion to your website background</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Background Type Selector */}
                    <div>
                      <Label className="block mb-3">Select Background Type</Label>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        {[
                          { value: "none", label: "None", icon: "🚫", desc: "Static only" },
                          { value: "image", label: "Image", icon: "🖼️", desc: "Custom upload" },
                          { value: "video", label: "Video", icon: "🎥", desc: "MP4/WebM loop" },
                          { value: "gradient", label: "Gradient", icon: "🌈", desc: "Flowing colors" },
                          { value: "particles", label: "Particles", icon: "✨", desc: "Floating bubbles" }
                        ].map(type => (
                          <div
                            key={type.value}
                            onClick={() => setSettings({...settings, live_background_type: type.value})}
                            className={`p-4 rounded-lg border-2 cursor-pointer transition-all text-center ${
                              (settings?.live_background_type || "none") === type.value 
                                ? "border-pink-500 bg-pink-50 shadow-md" 
                                : "border-gray-200 hover:border-pink-300"
                            }`}
                          >
                            <div className="text-2xl mb-1">{type.icon}</div>
                            <div className="font-medium text-sm">{type.label}</div>
                            <div className="text-xs text-gray-500">{type.desc}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Save Live Background Button */}
                    <Button
                      className="w-full bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600"
                      onClick={async () => {
                        try {
                          const token = localStorage.getItem("reroots_token");
                          await axios.put(`${API}/admin/store-settings/global-background`, {
                            live_background_type: settings?.live_background_type || "none",
                            live_background_video_url: settings?.live_background_video_url,
                            live_background_image_url: settings?.live_background_image_url,
                            global_site_background: settings?.live_background_image_url || settings?.global_site_background,
                            live_gradient_colors: settings?.live_gradient_colors,
                            live_gradient_speed: settings?.live_gradient_speed,
                            live_particles_enabled: settings?.live_particles_enabled,
                            live_particles_color: settings?.live_particles_color,
                            live_particles_count: settings?.live_particles_count,
                            global_background_enabled: true,
                            global_background_opacity: settings?.global_background_opacity
                          }, { headers: { Authorization: `Bearer ${token}` }});
                          toast.success("Live background saved! Refreshing...");
                          setTimeout(() => window.location.reload(), 1000);
                        } catch (error) {
                          toast.error("Failed to save live background");
                        }
                      }}
                    >
                      <Play className="h-4 w-4 mr-2" />
                      Save & Activate Live Background
                    </Button>
                  </CardContent>
                </Card>

                <div className="border-t pt-6">
                  <h4 className="font-medium text-lg mb-4">Login Page Specific Backgrounds</h4>
                  <p className="text-sm text-gray-600 mb-4">These override the global background only on login pages.</p>
                </div>

                {/* Customer Login Background */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">🛍️ Customer Login Background</CardTitle>
                    <CardDescription>Background image for the customer login page (/login)</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Image URL</Label>
                      <div className="flex gap-2">
                        <Input
                          value={settings?.login_background_image || ""}
                          onChange={(e) => setSettings({...settings, login_background_image: e.target.value})}
                          placeholder="https://images.unsplash.com/photo-xxxxx?w=1200"
                          className="flex-1"
                        />
                        <input
                          type="file"
                          accept="image/*"
                          id="login-bg-upload"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files[0];
                            if (!file) return;
                            const formData = new FormData();
                            formData.append("file", file);
                            try {
                              const res = await axios.post(`${API}/upload/image`, formData, {
                                headers: { "Content-Type": "multipart/form-data" }
                              });
                              // Use the URL directly - it's now permanent from Catbox
                              const imageUrl = res.data.url.startsWith('http') ? res.data.url : `${BACKEND_URL}${res.data.url}`;
                              setSettings({...settings, login_background_image: imageUrl});
                              if (res.data.permanent) {
                                toast.success("Image uploaded permanently!");
                              } else {
                                toast.success("Image uploaded!");
                              }
                            } catch (error) {
                              toast.error("Upload failed");
                            }
                          }}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => document.getElementById('login-bg-upload').click()}
                          className="border-green-300 hover:border-green-500"
                        >
                          <Upload className="h-4 w-4 mr-2" />
                          Upload
                        </Button>
                      </div>
                      <p className="text-xs text-green-600 mt-1">✓ Uploaded images are permanently saved</p>
                    </div>

                    {settings?.login_background_image && (
                      <div className="mt-4">
                        <Label className="block mb-2">Preview</Label>
                        <div className="w-full h-48 rounded-lg overflow-hidden border">
                          <img 
                            src={settings.login_background_image} 
                            alt="Customer login background" 
                            className="w-full h-full object-cover"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                        </div>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="mt-2 text-red-500"
                          onClick={() => setSettings({...settings, login_background_image: ""})}
                        >
                          <Trash2 className="h-4 w-4 mr-1" /> Remove
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Admin Login Background */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">🔐 Admin Login Background</CardTitle>
                    <CardDescription>Background image for the admin login page (/reroots-admin)</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Image URL</Label>
                      <div className="flex gap-2">
                        <Input
                          value={settings?.admin_login_background_image || ""}
                          onChange={(e) => setSettings({...settings, admin_login_background_image: e.target.value})}
                          placeholder="https://images.unsplash.com/photo-xxxxx?w=1200"
                          className="flex-1"
                        />
                        <input
                          type="file"
                          accept="image/*"
                          id="admin-login-bg-upload"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files[0];
                            if (!file) return;
                            const formData = new FormData();
                            formData.append("file", file);
                            try {
                              const res = await axios.post(`${API}/upload/image`, formData, {
                                headers: { "Content-Type": "multipart/form-data" }
                              });
                              const imageUrl = res.data.url.startsWith('http') ? res.data.url : `${BACKEND_URL}${res.data.url}`;
                              setSettings({...settings, admin_login_background_image: imageUrl});
                              if (res.data.permanent) {
                                toast.success("Image uploaded permanently!");
                              } else {
                                toast.success("Image uploaded!");
                              }
                            } catch (error) {
                              toast.error("Upload failed");
                            }
                          }}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => document.getElementById('admin-login-bg-upload').click()}
                          className="border-green-300 hover:border-green-500"
                        >
                          <Upload className="h-4 w-4 mr-2" />
                          Upload
                        </Button>
                      </div>
                      <p className="text-xs text-green-600 mt-1">✓ Uploaded images are permanently saved</p>
                    </div>

                    {settings?.admin_login_background_image && (
                      <div className="mt-4">
                        <Label className="block mb-2">Preview</Label>
                        <div className="w-full h-48 rounded-lg overflow-hidden border">
                          <img 
                            src={settings.admin_login_background_image} 
                            alt="Admin login background" 
                            className="w-full h-full object-cover"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                        </div>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="mt-2 text-red-500"
                          onClick={() => setSettings({...settings, admin_login_background_image: ""})}
                        >
                          <Trash2 className="h-4 w-4 mr-1" /> Remove
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>💡 Tip:</strong> Use high-quality images (1920x1080 or larger) for best results. After saving, the new background will appear on the login pages.
                  </p>
                </div>
              </div>
            )}

            {/* Store Info */}
            {activeSection === "store" && (
              <div className="space-y-6">
                <div className="flex items-center gap-2 mb-4">
                  <Package className="h-5 w-5 text-[#F8A5B8]" />
                  <h3 className="font-display text-xl font-bold">Store Information</h3>
                </div>

                <div>
                  <Label>Store Name</Label>
                  <Input
                    value={settings?.store_name || ""}
                    onChange={(e) => setSettings({...settings, store_name: e.target.value})}
                    placeholder="ReRoots"
                  />
                </div>

                <div>
                  <Label>Store Email</Label>
                  <Input
                    value={settings?.store_email || ""}
                    onChange={(e) => setSettings({...settings, store_email: e.target.value})}
                    placeholder="admin@reroots.ca"
                  />
                </div>

                <div>
                  <Label>Store Phone</Label>
                  <Input
                    value={settings?.store_phone || ""}
                    onChange={(e) => setSettings({...settings, store_phone: e.target.value})}
                    placeholder="+12265017777"
                  />
                </div>
              </div>
            )}

            <div className="mt-6 pt-6 border-t">
              <Button onClick={saveSettings} disabled={saving} className="btn-primary">
                {saving ? "Saving..." : "Save Settings"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default StoreSettingsEditor;
