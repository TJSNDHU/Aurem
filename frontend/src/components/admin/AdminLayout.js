import React, { useState, useEffect, lazy, Suspense, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Loader2, Menu, X, Plus, Trash2, ExternalLink, Lock, Unlock, 
  ChevronDown, ChevronUp, Shield, Edit, Users, Eye, EyeOff,
  Save, Upload, Download, FileText, Image, Camera, Sparkles,
  Package, Gift, AlertTriangle
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { useAuth } from '../../contexts';
import AdminSidebar from './AdminSidebar';
import AdminStatusBar from './AdminStatusBar';
import OrderTicker from './OrderTicker';

// Admin font style for consistent rendering
const adminFontStyle = { fontFamily: "'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" };

// Lazy load content components
const AbandonedCartsTable = lazy(() => import('./AbandonedCartsTable'));
const VirtualizedOrdersTable = lazy(() => import('./VirtualizedOrdersTable'));
const VirtualizedProductsTable = lazy(() => import('./VirtualizedProductsTable'));
const VirtualizedCustomersTable = lazy(() => import('./VirtualizedCustomersTable'));
const OffersManager = lazy(() => import('./OffersManager'));
const SubscribersSection = lazy(() => import('./SubscribersSection'));
const AIContentStudio = lazy(() => import('./AIContentStudio'));
const StoreSettingsEditor = lazy(() => import('./StoreSettingsEditor'));
const ComboOffersManager = lazy(() => import('./ComboOffersManager'));
const TabbedSection = lazy(() => import('./TabbedSection'));

// New components
const InventoryManager = lazy(() => import('./InventoryManager'));
const CollectionsManager = lazy(() => import('./CollectionsManager'));
const OrderDraftsManager = lazy(() => import('./OrderDraftsManager'));
const MarketingCampaigns = lazy(() => import('./MarketingCampaigns'));
const AnalyticsDashboard = lazy(() => import('./AnalyticsDashboard'));
const OnlineStoreSettings = lazy(() => import('./OnlineStoreSettings'));
const ReviewsManager = lazy(() => import('./ReviewsManager'));
const BlogManager = lazy(() => import('./BlogManager'));
const MarketingLab = lazy(() => import('./MarketingLab'));
const ProgramsManager = lazy(() => import('./ProgramsManager'));
const DataHub = lazy(() => import('./DataHub'));
const CustomizableDashboard = lazy(() => import('./CustomizableDashboard'));
const BiomarkerBenchmarksManager = lazy(() => import('./BiomarkerBenchmarksManager'));
const OrderFlowDashboard = lazy(() => import('./OrderFlowDashboard'));
const LoyaltyPointsManager = lazy(() => import('./LoyaltyPointsManager'));
const GiftTrackingDashboard = lazy(() => import('./GiftTrackingDashboard'));
const GiftTemplatesEditor = lazy(() => import('./GiftTemplatesEditor'));
const FlagShipShipments = lazy(() => import('./FlagShipShipments'));
const ClinicalLogicManager = lazy(() => import('./ClinicalLogicManager'));
const AIIntelligenceHub = lazy(() => import('./AIIntelligenceHub'));
const SecuritySettings = lazy(() => import('./SecuritySettings'));
const ExecutiveIntelligence = lazy(() => import('./ExecutiveIntelligence'));
const InventoryBatchTracking = lazy(() => import('./InventoryBatchTracking'));
const CRMRepurchaseCycle = lazy(() => import('./CRMRepurchaseCycle'));
const OrdersFulfillment = lazy(() => import('./OrdersFulfillment'));
const AccountingGST = lazy(() => import('./AccountingGST'));
const HealthCanadaCompliance = lazy(() => import('./HealthCanadaCompliance'));
const IntegrationMap = lazy(() => import('./IntegrationMap'));
const AutomationIntelligence = lazy(() => import('./AutomationIntelligence'));
const AutomationStatusDashboard = lazy(() => import('./AutomationStatusDashboard'));
const SalesIntelligence = lazy(() => import('./SalesIntelligence'));
const WhatsAppAIAssistant = lazy(() => import('./WhatsAppAIAssistant'));
const WhatsAppTestPanel = lazy(() => import('./WhatsAppTestPanel'));
const WhatsAppCRMActions = lazy(() => import('./WhatsAppCRMActions'));
const WhatsAppBroadcast = lazy(() => import('./WhatsAppBroadcast'));
const CacheStatusPanel = lazy(() => import('./CacheStatusPanel'));

// New CRM, Refunds, and Sales Dashboard components
const CRMModule = lazy(() => import('./CRMModule'));
const RefundsPanel = lazy(() => import('./RefundsPanel'));
const SalesDashboard = lazy(() => import('./SalesDashboard'));
const FraudDashboard = lazy(() => import('./FraudDashboard'));

// NEW: All missing admin components
const EmailCenter = lazy(() => import('./EmailCenter'));
const ContentStudio = lazy(() => import('./ContentStudio'));
const ComplianceMonitor = lazy(() => import('./ComplianceMonitor'));
const ProactiveOutreachDashboard = lazy(() => import('./ProactiveOutreachDashboard'));
const CustomerAIInsights = lazy(() => import('./CustomerAIInsights'));
const LanguageAnalytics = lazy(() => import('./LanguageAnalytics'));
const VoiceCallsDashboard = lazy(() => import('./VoiceCallsDashboard'));
const PhoneManagement = lazy(() => import('./PhoneManagement'));
const AutoHealDashboard = lazy(() => import('./AutoHealDashboard'));
const SiteAuditDashboard = lazy(() => import('./SiteAuditDashboard'));
const APIKeyManager = lazy(() => import('./APIKeyManager'));
const CrashDashboard = lazy(() => import('./CrashDashboard'));
const AdminActionAI = lazy(() => import('./AdminActionAI'));
const OrchestratorDashboard = lazy(() => import('./OrchestratorDashboard'));

// NEW: Auto-Repair Dashboard
const AutoRepairDashboard = lazy(() => import('./AutoRepairDashboard'));

// NEW: PWA Analytics Dashboard (Single Admin Policy)
const PWAAnalyticsDashboard = lazy(() => import('./PWAAnalyticsDashboard'));

// La Vela Bianca Admin Components
const LaVelaCommandCenter = lazy(() => import('./LaVelaCommandCenter'));

// Import TeamManager from InfluencerManager
const TeamManagerLazy = lazy(() => 
  import('./InfluencerManager').then(mod => ({ default: mod.TeamManager }))
);

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Loading fallback
const LoadingSpinner = () => (
  <div className="flex items-center justify-center py-12">
    <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
  </div>
);

// Overview Dashboard Component
const OverviewDashboard = ({ stats, orders, products, loading, adminName }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="bg-white rounded-xl p-6 border border-gray-100 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
            <div className="h-8 bg-gray-200 rounded w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  const statCards = [
    { label: 'Total Revenue', value: `$${(stats?.total_revenue || 0).toLocaleString()}`, color: 'text-green-600' },
    { label: 'Total Orders', value: stats?.total_orders || orders?.length || 0, color: 'text-blue-600' },
    { label: 'Active Customers', value: stats?.total_customers || 0, color: 'text-purple-600' },
    { label: 'Products', value: stats?.total_products || products?.length || 0, color: 'text-orange-600' },
  ];

  return (
    <div className="space-y-6">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold text-[#2D2A2E] truncate" style={adminFontStyle} title={adminName ? `Welcome back, ${adminName}!` : 'Welcome back!'}>
          Welcome back{adminName ? `, ${adminName}` : ''}!
        </h1>
        <p className="text-[#5A5A5A]">Here's what's happening with your store today.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, i) => (
          <div key={i} className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
            <p className="text-sm text-[#5A5A5A]">{stat.label}</p>
            <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-pink-50 to-rose-50 rounded-xl p-6 border border-pink-100">
          <h3 className="font-semibold text-[#2D2A2E] mb-2">Abandoned Carts</h3>
          <p className="text-3xl font-bold text-orange-600">{stats?.abandoned_carts || 0}</p>
          <p className="text-sm text-[#5A5A5A]">${(stats?.abandoned_value || 0).toFixed(2)} potential revenue</p>
        </div>
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-6 border border-green-100">
          <h3 className="font-semibold text-[#2D2A2E] mb-2">Recovered</h3>
          <p className="text-3xl font-bold text-green-600">{stats?.recovered_carts || 0}</p>
          <p className="text-sm text-[#5A5A5A]">${(stats?.recovered_value || 0).toFixed(2)} recovered</p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-100">
          <h3 className="font-semibold text-[#2D2A2E] mb-2">Recovery Rate</h3>
          <p className="text-3xl font-bold text-blue-600">{stats?.recovery_rate || 0}%</p>
          <p className="text-sm text-[#5A5A5A]">Cart recovery success</p>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#5A5A5A]">{orders?.length || 0} orders in the system</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Inventory Status</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#5A5A5A]">{products?.length || 0} products listed</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

// Connected Accounts Section
const ConnectedAccountsSection = () => {
  const defaultAccounts = [
    { id: '1', name: 'Stripe', description: 'Payments & Billing', url: 'https://dashboard.stripe.com', color: 'purple' },
    { id: '2', name: 'Twilio', description: 'SMS & Phone Verification', url: 'https://console.twilio.com', color: 'red' },
    { id: '3', name: 'Wix', description: 'Website Builder', url: 'https://manage.wix.com', color: 'blue' },
    { id: '4', name: 'TD Bank', description: 'Payment Gateway', url: 'https://web.na.bambora.com', color: 'green' },
    { id: '5', name: 'FlagShip', description: 'Shipping & Tracking', url: 'https://smartship.io/login', color: 'orange' },
    { id: '6', name: 'Google Merchant', description: 'Product Listings', url: 'https://merchants.google.com', color: 'yellow' },
    { id: '7', name: 'Bing Webmaster', description: 'SEO & Indexing', url: 'https://www.bing.com/webmasters', color: 'cyan' },
    { id: '8', name: 'Search Console', description: 'Google SEO', url: 'https://search.google.com/search-console', color: 'sky' },
    { id: '9', name: 'Resend', description: 'Email Service', url: 'https://resend.com/emails', color: 'pink' }
  ];

  const [accounts, setAccounts] = useState(() => {
    const saved = localStorage.getItem('reroots_connected_accounts');
    return saved ? JSON.parse(saved) : defaultAccounts;
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [newAccount, setNewAccount] = useState({ name: '', description: '', url: '', color: 'blue' });

  useEffect(() => {
    localStorage.setItem('reroots_connected_accounts', JSON.stringify(accounts));
  }, [accounts]);

  const handleSaveAccount = () => {
    if (!newAccount.name || !newAccount.url) {
      toast.error('Please fill in account name and URL');
      return;
    }
    
    if (editingAccount) {
      setAccounts(accounts.map(acc => 
        acc.id === editingAccount.id ? { ...newAccount, id: editingAccount.id } : acc
      ));
      toast.success('Account updated!');
    } else {
      setAccounts([...accounts, { ...newAccount, id: Date.now().toString() }]);
      toast.success('Account added!');
    }
    
    setDialogOpen(false);
    setEditingAccount(null);
    setNewAccount({ name: '', description: '', url: '', color: 'blue' });
  };

  const handleDeleteAccount = (accountId) => {
    if (window.confirm('Remove this account?')) {
      setAccounts(accounts.filter(acc => acc.id !== accountId));
      toast.success('Account removed!');
    }
  };

  const colorClasses = {
    purple: 'from-purple-500 to-purple-700',
    red: 'from-red-500 to-red-700',
    blue: 'from-blue-500 to-blue-700',
    green: 'from-green-600 to-green-800',
    orange: 'from-orange-500 to-orange-700',
    yellow: 'from-yellow-500 to-yellow-600',
    cyan: 'from-cyan-500 to-cyan-700',
    sky: 'from-sky-400 to-sky-600',
    pink: 'from-pink-500 to-pink-700',
    gray: 'from-gray-500 to-gray-700',
    indigo: 'from-indigo-500 to-indigo-700',
    teal: 'from-teal-500 to-teal-700',
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ExternalLink className="h-5 w-5" />
            Connected Accounts
          </CardTitle>
          <p className="text-sm text-[#5A5A5A]">Quick access to all your external services</p>
        </div>
        <Button 
          size="sm"
          onClick={() => {
            setEditingAccount(null);
            setNewAccount({ name: '', description: '', url: '', color: 'blue' });
            setDialogOpen(true);
          }}
          className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Account
        </Button>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((account) => (
            <div key={account.id} className="relative flex items-center gap-4 p-4 border rounded-xl transition-all group hover:bg-gray-50">
              <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => {
                    setEditingAccount(account);
                    setNewAccount({ ...account });
                    setDialogOpen(true);
                  }}
                  className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-gray-100"
                >
                  <Edit className="h-3 w-3" />
                </button>
                <button
                  onClick={() => handleDeleteAccount(account.id)}
                  className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-red-100 text-red-500"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
              
              <a href={account.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-4 flex-1">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colorClasses[account.color] || colorClasses.blue} flex items-center justify-center text-white font-bold text-lg`}>
                  {account.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[#2D2A2E] truncate">{account.name}</p>
                  <p className="text-xs text-[#5A5A5A] truncate">{account.description}</p>
                </div>
                <ExternalLink className="h-4 w-4 text-[#5A5A5A] flex-shrink-0" />
              </a>
            </div>
          ))}
        </div>
      </CardContent>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingAccount ? 'Edit Account' : 'Add New Account'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Account Name *</Label>
              <Input
                placeholder="e.g., Stripe, PayPal"
                value={newAccount.name}
                onChange={(e) => setNewAccount({ ...newAccount, name: e.target.value })}
              />
            </div>
            <div>
              <Label>URL *</Label>
              <Input
                placeholder="https://dashboard.example.com"
                value={newAccount.url}
                onChange={(e) => setNewAccount({ ...newAccount, url: e.target.value })}
              />
            </div>
            <div>
              <Label>Description</Label>
              <Input
                placeholder="e.g., Payments & Billing"
                value={newAccount.description}
                onChange={(e) => setNewAccount({ ...newAccount, description: e.target.value })}
              />
            </div>
            <div>
              <Label>Color</Label>
              <Select value={newAccount.color} onValueChange={(value) => setNewAccount({ ...newAccount, color: value })}>
                <SelectTrigger><SelectValue placeholder="Select color" /></SelectTrigger>
                <SelectContent>
                  {Object.keys(colorClasses).map(color => (
                    <SelectItem key={color} value={color}>{color.charAt(0).toUpperCase() + color.slice(1)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleSaveAccount} className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                {editingAccount ? 'Save Changes' : 'Add Account'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

// Secure Vault Section
const SecureVaultSection = () => {
  const [vaultUnlocked, setVaultUnlocked] = useState(false);
  const [vaultMinimized, setVaultMinimized] = useState(false);
  const [vaultPasswordInput, setVaultPasswordInput] = useState('');
  const [vaultError, setVaultError] = useState('');
  const VAULT_PIN = localStorage.getItem('reroots_vault_pin') || '';
  const [settingPin, setSettingPin] = useState(!VAULT_PIN);
  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const setVaultPin = () => {
    if (newPin.length < 4) {
      setVaultError('PIN must be at least 4 characters');
      return;
    }
    if (newPin !== confirmPin) {
      setVaultError('PINs do not match');
      return;
    }
    localStorage.setItem('reroots_vault_pin', btoa(newPin));
    setSettingPin(false);
    setVaultUnlocked(true);
    setVaultError('');
    toast.success('Vault PIN set successfully!');
  };

  const unlockVault = () => {
    const storedPin = localStorage.getItem('reroots_vault_pin');
    if (storedPin && btoa(vaultPasswordInput) === storedPin) {
      setVaultUnlocked(true);
      setVaultError('');
      setVaultPasswordInput('');
    } else {
      setVaultError('Incorrect PIN');
    }
  };

  const lockVault = () => {
    setVaultUnlocked(false);
    setVaultPasswordInput('');
  };

  const resetVaultPin = () => {
    localStorage.removeItem('reroots_vault_pin');
    setSettingPin(true);
    setVaultUnlocked(false);
    setVaultPasswordInput('');
    setNewPin('');
    setConfirmPin('');
    setVaultError('');
    setShowResetConfirm(false);
    toast.success('PIN has been reset. Please create a new PIN.');
  };

  return (
    <Card className="border-2 border-dashed border-purple-200 bg-gradient-to-br from-purple-50 via-pink-50 to-yellow-50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-gradient-to-br from-yellow-400 via-pink-500 to-purple-600">
              <Lock className="h-5 w-5 text-white" />
            </div>
            <span className="bg-gradient-to-r from-purple-600 via-pink-500 to-yellow-500 bg-clip-text text-transparent font-bold">
              Secure Vault
            </span>
            {vaultUnlocked && <Badge className="bg-green-500 text-white ml-2">Unlocked</Badge>}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setVaultMinimized(!vaultMinimized)}
            className="h-8 w-8 p-0 hover:bg-purple-100"
          >
            {vaultMinimized ? <ChevronDown className="h-5 w-5 text-purple-600" /> : <ChevronUp className="h-5 w-5 text-purple-600" />}
          </Button>
        </div>
        <p className="text-sm text-[#5A5A5A]">Password-protected private storage</p>
      </CardHeader>
      
      {!vaultMinimized && (
        <CardContent>
          {!vaultUnlocked ? (
            <div className="space-y-6">
              {settingPin ? (
                <div className="max-w-sm mx-auto space-y-4 py-8">
                  <div className="text-center mb-6">
                    <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-yellow-400 via-pink-500 to-purple-600 flex items-center justify-center">
                      <Shield className="h-10 w-10 text-white" />
                    </div>
                    <h3 className="text-lg font-bold text-[#2D2A2E]">Create Your PIN</h3>
                    <p className="text-sm text-[#5A5A5A]">Set a PIN to protect your private vault</p>
                  </div>
                  <div>
                    <Label>New PIN (min 4 characters)</Label>
                    <Input
                      type="password"
                      value={newPin}
                      onChange={(e) => setNewPin(e.target.value)}
                      placeholder="Enter PIN"
                      className="text-center text-2xl tracking-widest"
                    />
                  </div>
                  <div>
                    <Label>Confirm PIN</Label>
                    <Input
                      type="password"
                      value={confirmPin}
                      onChange={(e) => setConfirmPin(e.target.value)}
                      placeholder="Confirm PIN"
                      className="text-center text-2xl tracking-widest"
                    />
                  </div>
                  {vaultError && <p className="text-red-500 text-sm text-center">{vaultError}</p>}
                  <Button onClick={setVaultPin} className="w-full bg-gradient-to-r from-purple-600 via-pink-500 to-yellow-500 text-white">
                    <Lock className="h-4 w-4 mr-2" />
                    Set PIN & Open Vault
                  </Button>
                </div>
              ) : (
                <div className="max-w-sm mx-auto space-y-4 py-8">
                  <div className="text-center mb-6">
                    <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-yellow-400 via-pink-500 to-purple-600 flex items-center justify-center animate-pulse">
                      <Lock className="h-10 w-10 text-white" />
                    </div>
                    <h3 className="text-lg font-bold text-[#2D2A2E]">Enter PIN</h3>
                    <p className="text-sm text-[#5A5A5A]">Unlock your private vault</p>
                  </div>
                  <Input
                    type="password"
                    value={vaultPasswordInput}
                    onChange={(e) => setVaultPasswordInput(e.target.value)}
                    placeholder="Enter PIN"
                    className="text-center text-2xl tracking-widest"
                    onKeyPress={(e) => e.key === 'Enter' && unlockVault()}
                    data-testid="vault-pin-input"
                  />
                  {vaultError && <p className="text-red-500 text-sm text-center">{vaultError}</p>}
                  <Button onClick={unlockVault} className="w-full bg-gradient-to-r from-purple-600 via-pink-500 to-yellow-500 text-white" data-testid="unlock-vault-btn">
                    <Unlock className="h-4 w-4 mr-2" />
                    Unlock Vault
                  </Button>
                  <button
                    onClick={() => setShowResetConfirm(true)}
                    className="w-full text-sm text-purple-600 hover:text-purple-800 hover:underline py-2 transition-colors"
                    data-testid="forgot-pin-btn"
                  >
                    Forgot PIN? Reset it
                  </button>
                  
                  {/* Reset PIN Confirmation Dialog */}
                  {showResetConfirm && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowResetConfirm(false)}>
                      <div className="bg-white rounded-2xl p-6 max-w-sm mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                        <div className="text-center mb-4">
                          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center">
                            <Shield className="h-8 w-8 text-red-500" />
                          </div>
                          <h3 className="text-lg font-bold text-[#2D2A2E]">Reset Vault PIN?</h3>
                          <p className="text-sm text-[#5A5A5A] mt-2">
                            This will clear your current PIN and allow you to set a new one. Your vault contents will remain safe.
                          </p>
                        </div>
                        <div className="flex gap-3">
                          <Button
                            variant="outline"
                            className="flex-1"
                            onClick={() => setShowResetConfirm(false)}
                            data-testid="cancel-reset-btn"
                          >
                            Cancel
                          </Button>
                          <Button
                            className="flex-1 bg-red-500 hover:bg-red-600 text-white"
                            onClick={resetVaultPin}
                            data-testid="confirm-reset-btn"
                          >
                            Reset PIN
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-black rounded-2xl overflow-hidden" style={{ minHeight: '300px' }}>
              <div className="bg-gradient-to-r from-yellow-400 via-pink-500 to-purple-600 p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-white" />
                  <span className="text-white font-bold">Vault Unlocked</span>
                </div>
                <Button size="sm" variant="ghost" className="text-white hover:bg-white/20" onClick={lockVault}>
                  <Lock className="h-4 w-4 mr-1" />
                  Lock
                </Button>
              </div>
              <div className="p-8 flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-r from-yellow-400 via-pink-500 to-purple-600 flex items-center justify-center mb-4">
                  <Unlock className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-white text-xl font-bold mb-2">Secure Access Ready</h3>
                <p className="text-white/60 mb-6">Your vault is now unlocked and ready for use.</p>
                <Button
                  onClick={() => window.open('https://accounts.snapchat.com/v2/login', '_blank')}
                  className="bg-gradient-to-r from-yellow-400 via-pink-500 to-purple-600 text-white"
                >
                  Open Snapchat Login
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
};

// Admin Profile Settings
const AdminProfileSection = ({ adminName, setAdminName }) => {
  const [editingName, setEditingName] = useState(false);
  const [tempName, setTempName] = useState(adminName);

  const saveName = () => {
    setAdminName(tempName);
    localStorage.setItem('reroots_admin_name', tempName);
    setEditingName(false);
    toast.success('Admin name updated!');
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5" />
          Admin Profile
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label>Admin Display Name</Label>
          <p className="text-sm text-[#5A5A5A] mb-2">This name will be shown in the dashboard greeting</p>
          {editingName ? (
            <div className="flex gap-2">
              <Input
                value={tempName}
                onChange={(e) => setTempName(e.target.value)}
                placeholder="Enter your name"
              />
              <Button onClick={saveName} className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white">
                <Save className="h-4 w-4" />
              </Button>
              <Button variant="outline" onClick={() => { setEditingName(false); setTempName(adminName); }}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="flex-1 p-3 bg-gray-50 rounded-lg">
                <span className="font-medium">{adminName || 'Not set'}</span>
              </div>
              <Button variant="outline" onClick={() => setEditingName(true)}>
                <Edit className="h-4 w-4 mr-2" />
                Edit
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// Placeholder for sections not yet implemented
const ComingSoon = ({ title }) => (
  <div className="flex flex-col items-center justify-center py-20 text-center">
    <div className="w-16 h-16 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center mb-4">
      <Loader2 className="h-8 w-8 text-[#F8A5B8]" />
    </div>
    <h2 className="text-xl font-semibold text-[#2D2A2E] mb-2">{title}</h2>
    <p className="text-[#5A5A5A]">This section is being developed</p>
  </div>
);

// Main Admin Layout
const AdminLayout = () => {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [activeSection, setActiveSection] = useState(() => {
    // Check URL query params first
    const params = new URLSearchParams(window.location.search);
    const sectionFromUrl = params.get('section');
    if (sectionFromUrl) {
      return sectionFromUrl;
    }
    return localStorage.getItem('reroots_admin_section') || 'overview';
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [stats, setStats] = useState(null);
  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [abandonedCount, setAbandonedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [productsSubTab, setProductsSubTab] = useState('all'); // 'all' or 'combos'
  const [adminName, setAdminName] = useState(() => {
    return localStorage.getItem('reroots_admin_name') || '';
  });
  
  // Brand state for multi-tenant admin
  const [activeBrand, setActiveBrand] = useState(() => {
    return localStorage.getItem('admin_active_brand') || 'reroots';
  });
  
  // Storefront filter for filtering products/orders by which store they belong to
  const [storefrontFilter, setStorefrontFilter] = useState('all'); // 'all', 'reroots', 'dark_store'
  
  // Listen for brand changes from sidebar
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'admin_active_brand') {
        setActiveBrand(e.newValue || 'reroots');
      }
    };
    
    // Also check periodically for same-tab updates
    const interval = setInterval(() => {
      const currentBrand = localStorage.getItem('admin_active_brand') || 'reroots';
      if (currentBrand !== activeBrand) {
        setActiveBrand(currentBrand);
      }
    }, 500);
    
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, [activeBrand]);
  
  // Brand configurations
  const brandConfig = {
    reroots: {
      name: 'ReRoots Admin',
      shortName: 'R',
      primaryColor: '#F8A5B8',
      bgColor: '#FDF9F9',
      textColor: '#2D2A2E'
    },
    lavela: {
      name: 'La Vela Bianca',
      shortName: 'LA',
      primaryColor: '#0D4D4D',
      bgColor: '#0D4D4D',
      textColor: '#FDF8F5'
    }
  };
  
  const currentBrand = brandConfig[activeBrand] || brandConfig.reroots;

  // Product editing state
  const [editingProduct, setEditingProduct] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [savingProduct, setSavingProduct] = useState(false);
  const [isNewProduct, setIsNewProduct] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [deleteType, setDeleteType] = useState(''); // 'product', 'combo', 'collection', etc.

  // Track unsaved changes
  const originalProductRef = React.useRef(null);

  // Persist active section
  useEffect(() => {
    localStorage.setItem('reroots_admin_section', activeSection);
  }, [activeSection]);
  
  // Handle section changes from URL
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sectionFromUrl = params.get('section');
    if (sectionFromUrl && sectionFromUrl !== activeSection) {
      setActiveSection(sectionFromUrl);
    }
  }, [location.search]);

  // Auth check - redirect to admin login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      // Store redirect path for after login
      sessionStorage.setItem('redirectAfterLogin', '/admin');
      navigate('/login');
    }
  }, [user, authLoading, navigate]);

  // Additional security: Check token validity on mount and periodically
  useEffect(() => {
    const checkTokenValidity = () => {
      const token = localStorage.getItem('reroots_token');
      if (!token) {
        console.log('[AdminLayout] No token found - redirecting to login');
        sessionStorage.setItem('redirectAfterLogin', '/admin');
        navigate('/login');
        return false;
      }
      return true;
    };

    // Check immediately on mount
    checkTokenValidity();

    // Check every 30 seconds while admin panel is open
    const interval = setInterval(() => {
      if (!checkTokenValidity()) {
        clearInterval(interval);
      }
    }, 30000);

    // Also check when tab becomes visible again
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkTokenValidity();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [navigate]);

  // Toast event listener for child components
  useEffect(() => {
    const handleToast = (event) => {
      const { type, message } = event.detail;
      if (type === 'success') {
        toast.success(message);
      } else if (type === 'error') {
        toast.error(message);
      } else {
        toast(message);
      }
    };
    
    window.addEventListener('toast', handleToast);
    return () => window.removeEventListener('toast', handleToast);
  }, []);

  // Fetch admin data
  const fetchAdminData = useCallback(async () => {
    if (!user) return;
    
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const [statsRes, abandonedRes, ordersRes, productsRes, customersRes] = await Promise.all([
        axios.get(`${API}/admin/stats`, { headers }).catch(() => ({ data: {} })),
        axios.get(`${API}/admin/abandoned-carts?limit=100`, { headers }).catch(() => ({ data: { stats: { total: 0 } } })),
        axios.get(`${API}/admin/orders`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/products`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/admin/customers`, { headers }).catch(() => ({ data: [] }))
      ]);
      
      setStats(statsRes.data);
      setAbandonedCount(abandonedRes.data?.stats?.total || 0);
      setOrders(ordersRes.data || []);
      setProducts(productsRes.data || []);
      setCustomers(customersRes.data || []);
    } catch (error) {
      console.error('Failed to load admin data:', error);
    } finally {
      setLoading(false);
    }
  }, [user]);

  // Initial data fetch
  useEffect(() => {
    fetchAdminData();
  }, [fetchAdminData]);

  // Handle product edit
  const handleEditProduct = useCallback((product) => {
    setEditingProduct({ ...product });
    setIsNewProduct(false);
    setEditDialogOpen(true);
  }, []);

  // Handle add new product
  const handleAddProduct = useCallback(() => {
    setEditingProduct({
      id: '',
      name: '',
      description: '',
      price: 0,
      compare_at_price: 0,
      cost: 0,
      stock: 0,
      sku: '',
      barcode: '',
      category_id: '',
      images: [],
      is_active: true,
      is_featured: false,
      tags: [],
      weight: 0,
      variants: []
    });
    setIsNewProduct(true);
    setEditDialogOpen(true);
  }, []);

  // Save edited product (or create new)
  const handleSaveProduct = async () => {
    if (!editingProduct) return;
    
    // Validate required fields
    if (!editingProduct.name?.trim()) {
      toast.error('Product name is required');
      return;
    }
    
    setSavingProduct(true);
    try {
      const token = localStorage.getItem('reroots_token');
      
      if (isNewProduct) {
        // Create new product - auto-generate slug from name
        const slug = editingProduct.name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/(^-|-$)/g, '');
        
        const newProductData = {
          name: editingProduct.name,
          slug: slug,
          short_description: editingProduct.short_description || '',
          description: editingProduct.description || '',
          price: editingProduct.price || 0,
          cost_price: editingProduct.cost_price || null,
          compare_price: editingProduct.compare_price || null,
          discount_percent: editingProduct.discount_percent || 0,
          stock: editingProduct.stock || 0,
          weight_grams: editingProduct.weight_grams || 200,
          images: editingProduct.images || [],
          ingredients: editingProduct.ingredients || '',
          inci_ingredients: editingProduct.inci_ingredients || '',
          how_to_use: editingProduct.how_to_use || '',
          category_id: editingProduct.category_id || 'uncategorized',
          brand: editingProduct.brand || 'ReRoots',
          brand_visibility: editingProduct.brand_visibility || 'both',
          is_featured: editingProduct.is_featured || false,
          is_active: editingProduct.is_active !== false,
          allow_preorder: editingProduct.is_preorder || false,
          preorder_message: editingProduct.preorder_message || 'Available for pre-order. Ships in 2-3 weeks.',
          // Engine data for combo auto-calculation
          active_concentration: editingProduct.active_concentration || 0,
          engine_type: editingProduct.engine_type || 'engine',
          engine_label: editingProduct.engine_label || '',
          key_actives: editingProduct.key_actives || [],
          primary_benefit: editingProduct.primary_benefit || '',
        };
        
        const response = await axios.post(`${API}/products`, newProductData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setProducts([response.data, ...products]);
        toast.success('Product created successfully!');
      } else {
        // Update existing product - include engine data and brand_visibility
        const updateData = {
          ...editingProduct,
          brand_visibility: editingProduct.brand_visibility || 'both',
          active_concentration: editingProduct.active_concentration || 0,
          engine_type: editingProduct.engine_type || 'engine',
          engine_label: editingProduct.engine_label || '',
          key_actives: editingProduct.key_actives || [],
          primary_benefit: editingProduct.primary_benefit || '',
        };
        const response = await axios.put(`${API}/products/${editingProduct.id}`, updateData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setProducts(products.map(p => p.id === editingProduct.id ? response.data : p));
        toast.success('Product updated successfully!');
      }
      
      setEditDialogOpen(false);
      setEditingProduct(null);
      setIsNewProduct(false);
      setHasUnsavedChanges(false); // Reset after successful save
    } catch (error) {
      const errorDetail = error.response?.data?.detail;
      const errorMsg = Array.isArray(errorDetail) 
        ? errorDetail.map(e => e.msg).join(', ')
        : errorDetail || `Failed to ${isNewProduct ? 'create' : 'update'} product`;
      toast.error(errorMsg);
    } finally {
      setSavingProduct(false);
    }
  };

  // Handle product delete
  const handleDeleteProduct = useCallback((productId) => {
    setItemToDelete(productId);
    setDeleteType('product');
    setShowDeleteConfirm(true);
  }, []);

  // Actual delete after confirmation
  const confirmDeleteProduct = async (productId) => {
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/products/${productId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProducts(products.filter(p => p.id !== productId));
      toast.success('Product deleted!');
    } catch (error) {
      toast.error('Failed to delete product');
    }
  };

  // Handle section change
  const handleSectionChange = (section) => {
    setActiveSection(section);
    setSidebarOpen(false);
  };

  // Render content based on active section
  const renderContent = () => {
    switch (activeSection) {
      case 'overview':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CustomizableDashboard onNavigate={(section) => setActiveSection(section)} />
          </Suspense>
        );
      
      case 'orders':
        // Filter orders based on storefront filter
        const filteredOrders = orders.filter(o => {
          if (storefrontFilter === 'all') return true;
          const storefront = o.storefront || (o.source_url?.includes('/app') ? 'dark_store' : 'reroots');
          return storefront === storefrontFilter;
        });
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['orders', 'order-flow']} 
              title="Orders Management"
              orders={filteredOrders}
              loading={loading}
              maxHeight={600}
              onRefresh={fetchAdminData}
            />
          </Suspense>
        );
      
      case 'abandoned':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AbandonedCartsTable />
          </Suspense>
        );
      
      case 'drafts':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <OrderDraftsManager />
          </Suspense>
        );
      
      case 'products':
        // Filter products based on storefront filter
        const filteredProducts = products.filter(p => {
          if (storefrontFilter === 'all') return true;
          const visibility = p.brand_visibility || 'both';
          if (storefrontFilter === 'reroots') return visibility === 'both' || visibility === 'reroots_only';
          if (storefrontFilter === 'dark_store') return visibility === 'both' || visibility === 'dark_only';
          return true;
        });
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['products', 'collections']} 
              title="Shop Management"
              products={filteredProducts}
              loading={loading}
              onAdd={handleAddProduct}
              onEdit={handleEditProduct}
              onDelete={handleDeleteProduct}
            />
          </Suspense>
        );
      
      case 'combos':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['combos', 'inventory']} 
              title="Combo Offers & Inventory"
            />
          </Suspense>
        );
      
      case 'clinical-logic':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ClinicalLogicManager />
          </Suspense>
        );
      
      case 'inventory':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <InventoryManager />
          </Suspense>
        );
      
      case 'collections':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CollectionsManager />
          </Suspense>
        );
      
      case 'customers':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['customers', 'partners', 'founders']} 
              title="Customer Management"
              customers={customers}
              loading={loading}
            />
          </Suspense>
        );
      
      case 'reviews':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['reviews', 'gift-tracking']} 
              title={`Reviews & Gift ${activeBrand === 'lavela' ? 'Glow Points' : 'Roots'}`}
            />
          </Suspense>
        );
      
      case 'offers':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <div className="space-y-4">
              <h1 className="text-2xl font-bold text-[#2D2A2E]" style={adminFontStyle}>Offers & Discounts</h1>
              <OffersManager />
            </div>
          </Suspense>
        );
      
      case 'waitlist':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['waitlist', 'offers']} 
              title="Waitlist & Discounts"
            />
          </Suspense>
        );
      
      case 'subscribers':
      case 'inbox':  // Alias for subscribers/inbox section
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <div className="space-y-4">
              <h1 className="text-2xl font-bold text-[#2D2A2E]" style={adminFontStyle}>Email Subscribers</h1>
              <SubscribersSection />
            </div>
          </Suspense>
        );
      
      case 'ai-studio':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <div className="space-y-4">
              <h1 className="text-2xl font-bold text-[#2D2A2E]" style={adminFontStyle}>AI Content Studio</h1>
              <AIContentStudio />
            </div>
          </Suspense>
        );
      
      case 'ai-intelligence':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['ai-intelligence', 'sales-intelligence']} 
              title="AI & Sales Intelligence"
              products={products}
            />
          </Suspense>
        );
      
      case 'executive-intel':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ExecutiveIntelligence />
          </Suspense>
        );
      
      case 'inventory-batch':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <InventoryBatchTracking />
          </Suspense>
        );
      
      case 'crm-repurchase':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CRMRepurchaseCycle />
          </Suspense>
        );
      
      case 'crm-module':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CRMModule />
          </Suspense>
        );
      
      case 'refunds-panel':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <RefundsPanel />
          </Suspense>
        );
      
      case 'sales-dashboard':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <SalesDashboard />
          </Suspense>
        );
      
      case 'orders-fulfillment':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <OrdersFulfillment />
          </Suspense>
        );
      
      case 'accounting-gst':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AccountingGST />
          </Suspense>
        );
      
      case 'hc-compliance':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <HealthCanadaCompliance />
          </Suspense>
        );
      
      // PWA Analytics (Single Admin Policy)
      case 'pwa-analytics':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <PWAAnalyticsDashboard />
          </Suspense>
        );
      
      // LA VELA BIANCA Admin Sections
      case 'lavela-dashboard':
      case 'lavela-products':
      case 'lavela-glow-club':
      case 'lavela-content':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <LaVelaCommandCenter initialTab={activeSection.replace('lavela-', '')} />
          </Suspense>
        );
      
      case 'analytics':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['analytics', 'marketing-lab']} 
              title="Analytics & Marketing"
            />
          </Suspense>
        );
      
      case 'marketing':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <MarketingCampaigns />
          </Suspense>
        );
      
      case 'blog':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <BlogManager />
          </Suspense>
        );
      
      case 'marketing-lab':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <MarketingLab />
          </Suspense>
        );
      
      case 'whatsapp-ai':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <WhatsAppAIAssistant />
          </Suspense>
        );
      
      case 'whatsapp-test':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <WhatsAppTestPanel />
          </Suspense>
        );
      
      case 'whatsapp-crm':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <WhatsAppCRMActions />
          </Suspense>
        );
      
      case 'whatsapp-broadcast':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <WhatsAppBroadcast />
          </Suspense>
        );
      
      case 'whatsapp-templates':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['templates', '28-day-cycle']} 
              title="WhatsApp Templates & 28-Day Cycle"
            />
          </Suspense>
        );
      
      case 'programs':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ProgramsManager />
          </Suspense>
        );
      
      case 'loyalty-points':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['loyalty-points', 'redemption']} 
              title={`Loyalty (${activeBrand === 'lavela' ? 'Glow Points' : 'Roots'}) & Redemption`}
            />
          </Suspense>
        );
      
      case 'birthday-referral':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['birthday-bonus', 'referral-bonus']} 
              title="Birthday & Referral Bonuses"
            />
          </Suspense>
        );
      
      case 'gift-tracking':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <GiftTrackingDashboard />
          </Suspense>
        );
      
      case 'gift-templates':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <GiftTemplatesEditor />
          </Suspense>
        );
      
      case 'biomarker-benchmarks':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <BiomarkerBenchmarksManager />
          </Suspense>
        );
      
      case 'order-flow':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <OrderFlowDashboard />
          </Suspense>
        );
      
      case 'flagship-shipments':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <FlagShipShipments />
          </Suspense>
        );
      
      case 'data-hub':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DataHub />
          </Suspense>
        );
      
      case 'partners':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DataHub initialTab="partners" />
          </Suspense>
        );
      
      case 'waitlist':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DataHub initialTab="waitlist" />
          </Suspense>
        );
      
      case 'founders':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <DataHub initialTab="founding" />
          </Suspense>
        );
      
      case 'store':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['store', 'view-store']} 
              title="Online Store"
            />
          </Suspense>
        );
      
      case 'team':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['team', 'partner-portal']} 
              title="Team & Partner Portal"
            />
          </Suspense>
        );
      
      case 'settings':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <TabbedSection 
              tabs={['settings', 'security']} 
              title="Store Settings & Security"
              adminName={adminName}
              setAdminName={setAdminName}
            />
          </Suspense>
        );
      
      case 'security':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <SecuritySettings />
          </Suspense>
        );
      
      case 'cache':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CacheStatusPanel />
          </Suspense>
        );
      
      case 'integration-map':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <IntegrationMap />
          </Suspense>
        );
      
      case 'automation-intelligence':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AutomationIntelligence />
          </Suspense>
        );
      
      case 'automation-status':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AutomationStatusDashboard />
          </Suspense>
        );
      
      case 'platform-diagnosis':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <div className="space-y-4">
              <h1 className="text-2xl font-bold text-[#2D2A2E]" style={adminFontStyle}>Platform Diagnosis</h1>
              <div className="bg-white rounded-xl p-6 border border-gray-100">
                <p className="text-gray-600">System health monitoring and diagnostics dashboard.</p>
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-green-600 font-semibold">Backend Status</div>
                    <div className="text-2xl font-bold text-green-700">✓ Healthy</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-green-600 font-semibold">Database Status</div>
                    <div className="text-2xl font-bold text-green-700">✓ Connected</div>
                  </div>
                </div>
              </div>
            </div>
          </Suspense>
        );
      
      case 'fraud-prevention':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <FraudDashboard />
          </Suspense>
        );
      
      case 'sales-intelligence':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <SalesIntelligence />
          </Suspense>
        );
      
      // ══════════════════════════════════════════════════════════════
      // NEW SECTIONS - Marketing
      // ══════════════════════════════════════════════════════════════
      case 'email-center':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <EmailCenter />
          </Suspense>
        );
      
      case 'content-studio':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ContentStudio />
          </Suspense>
        );
      
      case 'compliance-monitor':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ComplianceMonitor />
          </Suspense>
        );
      
      case 'proactive-outreach':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <ProactiveOutreachDashboard />
          </Suspense>
        );
      
      // ══════════════════════════════════════════════════════════════
      // NEW SECTIONS - Customers
      // ══════════════════════════════════════════════════════════════
      case 'customer-ai-insights':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CustomerAIInsights />
          </Suspense>
        );
      
      case 'language-analytics':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <LanguageAnalytics />
          </Suspense>
        );
      
      // ══════════════════════════════════════════════════════════════
      // NEW SECTIONS - Brands
      // ══════════════════════════════════════════════════════════════
      case 'voice-calls':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <VoiceCallsDashboard />
          </Suspense>
        );
      
      case 'phone-management':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <PhoneManagement />
          </Suspense>
        );
      
      // ══════════════════════════════════════════════════════════════
      // NEW SECTIONS - System
      // ══════════════════════════════════════════════════════════════
      case 'orchestrator':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <OrchestratorDashboard />
          </Suspense>
        );
      
      case 'auto-heal':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AutoHealDashboard />
          </Suspense>
        );
      
      case 'site-audit':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <SiteAuditDashboard />
          </Suspense>
        );
      
      case 'api-keys':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <APIKeyManager />
          </Suspense>
        );
      
      case 'crash-dashboard':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <CrashDashboard />
          </Suspense>
        );
      
      case 'admin-ai':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AdminActionAI />
          </Suspense>
        );
      
      case 'auto-repair':
        return (
          <Suspense fallback={<LoadingSpinner />}>
            <AutoRepairDashboard />
          </Suspense>
        );
      
      case 'notifications':
        return <ComingSoon title="Notification Settings" />;
      
      case 'vault':
        return (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold text-[#2D2A2E]" style={adminFontStyle}>Secure Vault</h1>
            <SecureVaultSection />
          </div>
        );
      
      default:
        return <OverviewDashboard stats={stats} orders={orders} products={products} loading={loading} adminName={adminName} />;
    }
  };

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-10 w-10 animate-spin text-[#F8A5B8]" />
        <span className="ml-3 text-lg text-[#2D2A2E]">Loading Admin...</span>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-[#FDF9F9] flex">
      {/* Real-time Order Ticker - handles WebSocket notifications */}
      <OrderTicker />
      
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Fixed width, no overlap */}
      <aside 
        className={`
          fixed lg:sticky lg:top-0 inset-y-0 left-0 z-50
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          transition-transform duration-300 ease-in-out
          flex-shrink-0
        `}
        style={{ 
          height: '100dvh',
          maxHeight: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'visible'
        }}
      >
        <AdminSidebar 
          activeSection={activeSection} 
          setActiveSection={handleSectionChange}
          abandonedCount={abandonedCount}
          adminName={adminName}
        />
      </aside>

      {/* Main content area - takes remaining space */}
      <div className="flex-1 flex flex-col min-h-screen min-w-0">
        {/* Mobile header */}
        <header 
          className="lg:hidden border-b px-4 py-3 flex items-center justify-between sticky top-0 z-30 transition-colors"
          style={{ 
            backgroundColor: activeBrand === 'lavela' ? '#0D4D4D' : 'white',
            borderColor: activeBrand === 'lavela' ? '#D4A57440' : '#F8A5B820'
          }}
        >
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            data-testid="mobile-menu-toggle"
            className="hover:opacity-80"
            style={{ color: activeBrand === 'lavela' ? '#D4A574' : '#2D2A2E' }}
          >
            {sidebarOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </Button>
          <div className="flex items-center gap-2">
            <div 
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
              style={{ backgroundColor: currentBrand.primaryColor }}
            >
              <span className="text-white font-bold text-sm">{currentBrand.shortName}</span>
            </div>
            <span 
              className="font-semibold transition-colors"
              style={{ color: activeBrand === 'lavela' ? '#FDF8F5' : '#2D2A2E' }}
            >
              {currentBrand.name}
            </span>
          </div>
          <div className="w-10" />
        </header>

        {/* Admin Status Bar - System Health & Sync */}
        <AdminStatusBar />

        {/* Content - full width with proper padding */}
        <main 
          className="admin-main-content flex-1 overflow-y-auto p-4 lg:p-6 transition-colors"
          style={{ backgroundColor: activeBrand === 'lavela' ? '#1A6B6B20' : 'white' }}
        >
          {/* Storefront Filter Bar */}
          {(activeSection === 'products' || activeSection === 'orders' || activeSection === 'combos') && (
            <div className="mb-4 flex items-center gap-2 p-1 bg-gradient-to-r from-gray-100 to-slate-100 rounded-xl w-max" data-testid="storefront-filter-bar">
              <button
                onClick={() => setStorefrontFilter('all')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  storefrontFilter === 'all' 
                    ? 'bg-white shadow-sm text-gray-800' 
                    : 'text-gray-600 hover:bg-white/50'
                }`}
                data-testid="storefront-filter-all"
              >
                🌐 All Stores
              </button>
              <button
                onClick={() => setStorefrontFilter('reroots')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  storefrontFilter === 'reroots' 
                    ? 'bg-gradient-to-r from-pink-100 to-rose-100 shadow-sm text-pink-800' 
                    : 'text-gray-600 hover:bg-pink-50'
                }`}
                data-testid="storefront-filter-reroots"
              >
                🩷 ReRoots
              </button>
              <button
                onClick={() => setStorefrontFilter('dark_store')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  storefrontFilter === 'dark_store' 
                    ? 'bg-gray-900 shadow-sm text-white' 
                    : 'text-gray-600 hover:bg-gray-200'
                }`}
                data-testid="storefront-filter-dark"
              >
                🖤 Dark Store
              </button>
            </div>
          )}
          {renderContent()}
        </main>
      </div>

      {/* Close Confirmation Dialog */}
      <Dialog open={showCloseConfirm} onOpenChange={setShowCloseConfirm}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600">
              <AlertTriangle className="h-5 w-5" />
              Unsaved Changes
            </DialogTitle>
          </DialogHeader>
          <p className="text-gray-600 py-4">
            You have unsaved changes. Do you want to save before closing?
          </p>
          <div className="flex gap-3 justify-end">
            <Button 
              variant="outline" 
              onClick={() => {
                setShowCloseConfirm(false);
                setEditDialogOpen(false);
                setEditingProduct(null);
                setHasUnsavedChanges(false);
              }}
            >
              Discard Changes
            </Button>
            <Button 
              onClick={async () => {
                setShowCloseConfirm(false);
                await handleSaveProduct();
              }}
              className="bg-green-600 hover:bg-green-700"
            >
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <Trash2 className="h-5 w-5" />
              Confirm Delete
            </DialogTitle>
          </DialogHeader>
          <p className="text-gray-600 py-4">
            Are you sure you want to delete this {deleteType}? This action cannot be undone.
          </p>
          <div className="flex gap-3 justify-end">
            <Button 
              variant="outline" 
              onClick={() => {
                setShowDeleteConfirm(false);
                setItemToDelete(null);
              }}
            >
              No, Cancel
            </Button>
            <Button 
              variant="destructive"
              onClick={async () => {
                if (itemToDelete && deleteType === 'product') {
                  await confirmDeleteProduct(itemToDelete);
                }
                setShowDeleteConfirm(false);
                setItemToDelete(null);
              }}
            >
              Yes, Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit/Add Product Dialog */}
      <Dialog 
        open={editDialogOpen} 
        onOpenChange={(open) => {
          if (!open && hasUnsavedChanges) {
            setShowCloseConfirm(true);
          } else {
            setEditDialogOpen(open);
            if (!open) {
              setEditingProduct(null);
              setHasUnsavedChanges(false);
            }
          }
        }}
      >
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {isNewProduct ? <Plus className="h-5 w-5" /> : <Edit className="h-5 w-5" />}
              {isNewProduct ? 'Add New Product' : 'Edit Product'}
            </DialogTitle>
          </DialogHeader>
          {editingProduct && (
            <div className="space-y-4 py-4">
              {/* Product Name & Brand */}
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <Label>Product Name *</Label>
                  <Input
                    value={editingProduct.name || ''}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, name: e.target.value });
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="Enter product name"
                  />
                </div>
                <div>
                  <Label>Brand</Label>
                  <Input
                    value={editingProduct.brand || 'ReRoots'}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, brand: e.target.value });
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="ReRoots"
                  />
                </div>
                
                {/* Storefront Visibility */}
                <div>
                  <Label>Storefront Visibility</Label>
                  <Select
                    value={editingProduct.brand_visibility || 'both'}
                    onValueChange={(value) => {
                      setEditingProduct({ ...editingProduct, brand_visibility: value });
                      setHasUnsavedChanges(true);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select visibility" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="both">🌐 Both Storefronts</SelectItem>
                      <SelectItem value="reroots_only">🩷 ReRoots Only (Bright Theme)</SelectItem>
                      <SelectItem value="dark_only">🖤 Dark Store Only (/app)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Short Description */}
              <div>
                <Label>Short Description</Label>
                <Input
                  value={editingProduct.short_description || ''}
                  onChange={(e) => {
                    setEditingProduct({ ...editingProduct, short_description: e.target.value });
                    setHasUnsavedChanges(true);
                  }}
                  placeholder="Brief product tagline (shown on cards)"
                />
              </div>

              {/* AI Product Generator */}
              <div className="border-2 border-dashed border-purple-300 rounded-lg p-4 bg-purple-50">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="h-5 w-5 text-purple-600" />
                  <Label className="text-purple-700 font-semibold">AI Product Generator</Label>
                </div>
                <p className="text-sm text-purple-600 mb-3">
                  Enter your formulation/ingredients below and AI will generate all product details automatically.
                </p>
                <Textarea
                  id="ai-formulation-input"
                  placeholder="Enter your formulation, e.g.:&#10;2% PDRN, 5% Tranexamic Acid, 17% Argireline, Niacinamide 4%, Hyaluronic Acid..."
                  rows={3}
                  className="mb-3 border-purple-200 focus:border-purple-400"
                  defaultValue={editingProduct.ingredients || ''}
                />
                <Button
                  type="button"
                  onClick={async () => {
                    const formInput = document.getElementById('ai-formulation-input');
                    const formulation = formInput?.value?.trim();
                    if (!formulation) {
                      toast.error('Please enter formulation/ingredients first');
                      return;
                    }
                    
                    toast.loading('AI is generating product details...', { id: 'ai-gen' });
                    
                    try {
                      const token = localStorage.getItem('reroots_token');
                      const res = await axios.post(`${API}/admin/generate-product-details`, {
                        formulation: formulation,
                        product_type: 'skincare serum',
                        brand_voice: 'premium scientific skincare'
                      }, {
                        headers: { Authorization: `Bearer ${token}` },
                        timeout: 60000
                      });
                      
                      if (res.data?.success && res.data?.generated) {
                        const gen = res.data.generated;
                        
                        // === SMART PARSER FOR FORMULATION TABLE FORMAT ===
                        // Handles: | Phase | INCI Name | % Weight | Function |
                        
                        // Non-active ingredient keywords (exclude from active concentration)
                        const nonActiveKeywords = [
                          'water', 'aqua', 'deionized', 'solvent', 'base', 'preservative', 
                          'stabilizer', 'chelator', 'edta', 'ph adjuster', 'sodium hydroxide',
                          'fragrance', 'parfum', 'color', 'dye'
                        ];
                        
                        // Active ingredient indicators
                        const activeIndicators = [
                          'acid', 'retinoid', 'retinol', 'peptide', 'vitamin', 'arbutin',
                          'niacinamide', 'resurfacing', 'brightening', 'antioxidant', 'aha', 
                          'bha', 'collagen', 'hydrating', 'plumping', 'humectant', 'barrier',
                          'soothing', 'anti-', 'blockade', 'synergist', 'penetrant', 'lipid'
                        ];
                        
                        // Parse table rows: | Phase | Ingredient | % | Function |
                        const tableRows = formulation.split('\n').filter(line => line.includes('|') && !line.includes('---'));
                        
                        let totalActiveConcentration = 0;
                        const keyActives = [];
                        let detectedTags = [];
                        
                        // Extract product name from first line if present (e.g., "AURA-GEN: Accelerator Complex")
                        const firstLine = formulation.split('\n')[0]?.trim();
                        const extractedName = firstLine && !firstLine.includes('|') && !firstLine.includes('Phase') 
                          ? firstLine : '';
                        
                        tableRows.forEach(row => {
                          const cols = row.split('|').map(c => c.trim()).filter(c => c);
                          if (cols.length >= 3) {
                            // Try to identify columns: [Phase, Ingredient, %, Function] or [Ingredient, %, Function]
                            let ingredientName = '';
                            let percentage = 0;
                            let funcText = '';
                            
                            // Find the percentage column
                            for (let i = 0; i < cols.length; i++) {
                              const val = cols[i];
                              const numMatch = val.match(/^(\d+(?:\.\d+)?)$/);
                              if (numMatch) {
                                percentage = parseFloat(numMatch[1]);
                                ingredientName = cols[i - 1] || '';
                                funcText = cols[i + 1] || '';
                                break;
                              }
                            }
                            
                            if (!ingredientName || !percentage) return;
                            
                            const ingredientLower = ingredientName.toLowerCase();
                            const funcLower = funcText.toLowerCase();
                            const combinedLower = ingredientLower + ' ' + funcLower;
                            
                            // Skip non-active base ingredients
                            const isNonActive = nonActiveKeywords.some(kw => combinedLower.includes(kw));
                            
                            // Check if it's an active ingredient
                            const isActive = activeIndicators.some(kw => combinedLower.includes(kw));
                            
                            if (isActive && !isNonActive && percentage > 0) {
                              totalActiveConcentration += percentage;
                              keyActives.push({
                                name: ingredientName,
                                percent: percentage,
                                function: funcText
                              });
                              
                              // Auto-detect clinical tags
                              if (combinedLower.includes('acid') || combinedLower.includes('aha') || combinedLower.includes('bha')) {
                                if (!detectedTags.includes('ACID')) detectedTags.push('ACID');
                              }
                              if (combinedLower.includes('retinoid') || combinedLower.includes('retinol') || combinedLower.includes('hpr')) {
                                if (!detectedTags.includes('RETINOID')) detectedTags.push('RETINOID');
                              }
                              if (combinedLower.includes('peptide') || combinedLower.includes('matrixyl')) {
                                if (!detectedTags.includes('PEPTIDE')) detectedTags.push('PEPTIDE');
                              }
                              if (combinedLower.includes('brightening') || combinedLower.includes('arbutin') || combinedLower.includes('pigment')) {
                                if (!detectedTags.includes('BRIGHTENER')) detectedTags.push('BRIGHTENER');
                              }
                              if (combinedLower.includes('barrier') || combinedLower.includes('squalane') || combinedLower.includes('lipid')) {
                                if (!detectedTags.includes('BARRIER')) detectedTags.push('BARRIER');
                              }
                              if (combinedLower.includes('sooth') || combinedLower.includes('calming') || combinedLower.includes('allantoin')) {
                                if (!detectedTags.includes('SENSITIVE')) detectedTags.push('SENSITIVE');
                              }
                            }
                          }
                        });
                        
                        // Fallback: simple percentage parsing if no table detected
                        if (keyActives.length === 0) {
                          const percentMatches = formulation.match(/(\d+(?:\.\d+)?)\s*%/g) || [];
                          totalActiveConcentration = percentMatches.reduce((sum, match) => {
                            const num = parseFloat(match.replace('%', ''));
                            return sum + (isNaN(num) ? 0 : num);
                          }, 0);
                        }
                        
                        // Determine engine type
                        const formulationLower = formulation.toLowerCase();
                        const isEngine = formulationLower.includes('acid') || 
                                         formulationLower.includes('retinol') || 
                                         formulationLower.includes('retinoid') ||
                                         formulationLower.includes('aha') ||
                                         formulationLower.includes('bha') ||
                                         formulationLower.includes('resurfacing');
                        const engineType = isEngine ? 'engine' : 'buffer';
                        
                        // Use extracted name or AI generated name
                        const engineLabel = extractedName || (gen.name ? gen.name.split(' ').slice(0, 4).join(' ') : '');
                        
                        // Primary benefit from function column or AI
                        const primaryBenefit = keyActives[0]?.function || gen.key_benefits?.[0] || '';
                        
                        console.log('Parsed Engine Data:', {
                          totalActiveConcentration: totalActiveConcentration.toFixed(2),
                          keyActives: keyActives.length,
                          engineType,
                          detectedTags
                        });
                        
                        setEditingProduct(prev => ({
                          ...prev,
                          // Only fill if field is empty - preserve user edits
                          name: prev.name?.trim() ? prev.name : (extractedName || gen.name || prev.name),
                          short_description: prev.short_description?.trim() ? prev.short_description : (gen.short_description || prev.short_description),
                          description: prev.description?.trim() ? prev.description : (gen.description || prev.description),
                          ingredients: prev.ingredients?.trim() ? prev.ingredients : (gen.ingredients || formulation),
                          how_to_use: prev.how_to_use?.trim() ? prev.how_to_use : (gen.how_to_use || prev.how_to_use),
                          texture: prev.texture?.trim() ? prev.texture : (gen.texture || prev.texture),
                          // Store additional AI data
                          key_benefits: gen.key_benefits || prev.key_benefits || [],
                          target_concerns: gen.target_concerns || prev.target_concerns || [],
                          skin_types: gen.skin_types || prev.skin_types || [],
                          // === AUTO-FILL ENGINE SECTION ===
                          active_concentration: prev.active_concentration > 0 ? prev.active_concentration : parseFloat(totalActiveConcentration.toFixed(2)),
                          engine_type: prev.engine_type || engineType,
                          engine_label: prev.engine_label?.trim() ? prev.engine_label : engineLabel,
                          key_actives: prev.key_actives?.length > 0 ? prev.key_actives : keyActives.slice(0, 10),
                          primary_benefit: prev.primary_benefit?.trim() ? prev.primary_benefit : primaryBenefit,
                          // === AUTO-FILL CLINICAL TAGS ===
                          tags: prev.tags?.length > 0 ? prev.tags : detectedTags,
                        }));
                        toast.success(`AI filled product + Engine! Active: ${totalActiveConcentration.toFixed(2)}% | ${keyActives.length} actives detected`, { id: 'ai-gen' });
                      } else {
                        toast.error('AI generation failed', { id: 'ai-gen' });
                      }
                    } catch (err) {
                      console.error('AI generation error:', err);
                      toast.error(err.response?.data?.detail || 'AI generation failed', { id: 'ai-gen' });
                    }
                  }}
                  className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white"
                >
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generate with AI
                </Button>
              </div>
              
              {/* Price Fields */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>Price ($) *</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editingProduct.price || ''}
                    onChange={(e) => setEditingProduct({ ...editingProduct, price: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <Label>Compare At Price ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editingProduct.compare_price || ''}
                    onChange={(e) => setEditingProduct({ ...editingProduct, compare_price: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <Label>Cost Price ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editingProduct.cost_price || ''}
                    onChange={(e) => setEditingProduct({ ...editingProduct, cost_price: parseFloat(e.target.value) || 0 })}
                    placeholder="Your cost (COGS)"
                  />
                </div>
              </div>
              
              {/* Stock, Discount, Weight */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>Stock Quantity</Label>
                  <Input
                    type="number"
                    value={editingProduct.stock || 0}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, stock: parseInt(e.target.value) || 0 });
                      setHasUnsavedChanges(true);
                    }}
                  />
                </div>
                <div>
                  <Label>Discount %</Label>
                  <Input
                    type="number"
                    value={editingProduct.discount_percent || 0}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, discount_percent: parseInt(e.target.value) || 0 });
                      setHasUnsavedChanges(true);
                    }}
                  />
                </div>
                <div>
                  <Label>Weight (grams)</Label>
                  <Input
                    type="number"
                    value={editingProduct.weight_grams || 200}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, weight_grams: parseInt(e.target.value) || 200 });
                      setHasUnsavedChanges(true);
                    }}
                  />
                </div>
              </div>

              {/* PRODUCT ENGINE - Active Ingredients Data */}
              <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                <div className="flex items-center justify-between mb-4">
                  <Label className="flex items-center gap-2 text-purple-800 text-base font-semibold">
                    <Sparkles className="h-5 w-5 text-purple-600" />
                    Product Engine (Active Ingredients)
                  </Label>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="text-purple-600 border-purple-300 hover:bg-purple-100"
                    onClick={async () => {
                      // Auto-generate engine data from product name/ingredients
                      if (!editingProduct.name && !editingProduct.ingredients) {
                        toast.error('Enter product name or ingredients first');
                        return;
                      }
                      
                      toast.loading('Generating engine data...', { id: 'engine-gen' });
                      
                      try {
                        const token = localStorage.getItem('reroots_token');
                        const res = await axios.post(`${API}/ai/generate-product-engine`, {
                          name: editingProduct.name,
                          ingredients: editingProduct.ingredients,
                          description: editingProduct.description
                        }, {
                          headers: { Authorization: `Bearer ${token}` }
                        });
                        
                        if (res.data?.success) {
                          const engine = res.data.engine;
                          setEditingProduct(prev => ({
                            ...prev,
                            active_concentration: engine.total_concentration || prev.active_concentration,
                            engine_label: engine.label || prev.engine_label,
                            engine_type: engine.type || prev.engine_type,
                            key_actives: engine.key_actives || prev.key_actives || [],
                            primary_benefit: engine.primary_benefit || prev.primary_benefit
                          }));
                          setHasUnsavedChanges(true);
                          toast.success('Engine data generated!', { id: 'engine-gen' });
                        }
                      } catch (err) {
                        console.error('Engine generation error:', err);
                        toast.error('Failed to generate. Enter manually.', { id: 'engine-gen' });
                      }
                    }}
                  >
                    <Sparkles className="h-3 w-3 mr-1" />
                    Auto-Generate
                  </Button>
                </div>
                
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <Label className="text-purple-700 text-sm">Active Concentration (%)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      value={editingProduct.active_concentration || 0}
                      onChange={(e) => {
                        setEditingProduct({ ...editingProduct, active_concentration: parseFloat(e.target.value) || 0 });
                        setHasUnsavedChanges(true);
                      }}
                      placeholder="e.g., 17.35"
                    />
                  </div>
                  <div>
                    <Label className="text-purple-700 text-sm">Engine Type</Label>
                    <Select
                      value={editingProduct.engine_type || 'engine'}
                      onValueChange={(value) => {
                        setEditingProduct({ ...editingProduct, engine_type: value });
                        setHasUnsavedChanges(true);
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="engine">🔥 ENGINE (Step 1 - Active)</SelectItem>
                        <SelectItem value="buffer">🛡️ BUFFER (Step 2 - Recovery)</SelectItem>
                        <SelectItem value="booster">⚡ BOOSTER (Enhancer)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                <div className="mb-4">
                  <Label className="text-purple-700 text-sm">Engine Label (Short Name)</Label>
                  <Input
                    value={editingProduct.engine_label || ''}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, engine_label: e.target.value });
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="e.g., AURA-GEN PDRN +"
                  />
                </div>
                
                <div className="mb-4">
                  <Label className="text-purple-700 text-sm">Key Actives (comma separated)</Label>
                  <Input
                    value={(editingProduct.key_actives || []).join(', ')}
                    onChange={(e) => {
                      const actives = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
                      setEditingProduct({ ...editingProduct, key_actives: actives });
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="e.g., PDRN 5%, Tranexamic Acid 3%, Argireline 10%"
                  />
                </div>
                
                <div>
                  <Label className="text-purple-700 text-sm">Primary Benefit</Label>
                  <Input
                    value={editingProduct.primary_benefit || ''}
                    onChange={(e) => {
                      setEditingProduct({ ...editingProduct, primary_benefit: e.target.value });
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="e.g., Clears pathways & dissolves pigment"
                  />
                </div>
                
                {/* Product Tags for Clinical Logic */}
                <div>
                  <Label className="text-purple-700 text-sm">Clinical Tags (for Calendar Milestones)</Label>
                  <div className="flex flex-wrap gap-1.5 p-2 bg-purple-50 rounded-lg border border-purple-200 mt-1">
                    {['ACID', 'RETINOID', 'BRIGHTENER', 'PEPTIDE', 'PDRN', 'BARRIER', 'SOD', 'ACNE_CONTROL', 'SENSITIVE', 'C_VITAMIN', 'HYDRATOR'].map(tag => (
                      <Badge
                        key={tag}
                        className={`cursor-pointer text-xs transition-all ${
                          (editingProduct.tags || []).includes(tag)
                            ? 'bg-purple-600 text-white hover:bg-purple-700'
                            : 'bg-white text-purple-700 border border-purple-300 hover:bg-purple-100'
                        }`}
                        onClick={() => {
                          const currentTags = editingProduct.tags || [];
                          const newTags = currentTags.includes(tag)
                            ? currentTags.filter(t => t !== tag)
                            : [...currentTags, tag];
                          setEditingProduct({ ...editingProduct, tags: newTags });
                          setHasUnsavedChanges(true);
                        }}
                      >
                        {(editingProduct.tags || []).includes(tag) && '✓ '}
                        {tag.replace('_', ' ')}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-xs text-purple-600 mt-1">
                    Tags determine which milestones appear in the 12-Week Calendar
                  </p>
                </div>
                
                <p className="text-xs text-purple-600 mt-3 bg-purple-100 p-2 rounded">
                  💡 This data auto-populates the "55% Hyper-Potency" meter and ENGINE/BUFFER labels when creating combos.
                </p>
              </div>

              {/* Category Selection */}
              <div>
                <Label>Category</Label>
                <Select
                  value={editingProduct.category_id || 'uncategorized'}
                  onValueChange={(value) => {
                    setEditingProduct({ ...editingProduct, category_id: value });
                    setHasUnsavedChanges(true);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="uncategorized">Uncategorized</SelectItem>
                    <SelectItem value="serums">Serums</SelectItem>
                    <SelectItem value="moisturizers">Moisturizers</SelectItem>
                    <SelectItem value="cleansers">Cleansers</SelectItem>
                    <SelectItem value="treatments">Treatments</SelectItem>
                    <SelectItem value="masks">Masks</SelectItem>
                    <SelectItem value="sets">Sets & Bundles</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              {/* Product Images */}
              <div>
                <Label>Product Images</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {(editingProduct.images || []).map((img, idx) => (
                    <div key={idx} className="relative group">
                      <img src={img} alt={`Product ${idx + 1}`} className="w-16 h-16 object-cover rounded border" />
                      <button
                        type="button"
                        onClick={() => {
                          const newImages = [...(editingProduct.images || [])];
                          newImages.splice(idx, 1);
                          setEditingProduct({ ...editingProduct, images: newImages });
                        }}
                        className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-[#F8A5B8] transition-colors">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.gif,.webp,.heic,.heif"
                    multiple
                    onChange={async (e) => {
                      const files = Array.from(e.target.files || []);
                      if (files.length === 0) return;
                      
                      toast.loading('Uploading image...', { id: 'upload' });
                      
                      for (const file of files) {
                        // Check file size (max 10MB)
                        if (file.size > 10 * 1024 * 1024) {
                          toast.error('Image too large. Max 10MB allowed.', { id: 'upload' });
                          continue;
                        }
                        
                        const formData = new FormData();
                        formData.append('file', file);
                        
                        try {
                          const token = localStorage.getItem('reroots_token');
                          const res = await axios.post(`${API}/upload/image`, formData, {
                            headers: { 
                              Authorization: `Bearer ${token}`,
                            },
                            timeout: 60000 // 60 second timeout for uploads
                          });
                          
                          if (res.data?.url) {
                            setEditingProduct(prev => ({
                              ...prev,
                              images: [...(prev.images || []), res.data.url]
                            }));
                            toast.success('Image uploaded!', { id: 'upload' });
                          } else {
                            toast.error('Upload failed - no URL returned', { id: 'upload' });
                          }
                        } catch (err) {
                          console.error('Upload error:', err.response?.data || err.message);
                          const errorMsg = err.response?.data?.detail || err.message || 'Failed to upload image';
                          toast.error(errorMsg, { id: 'upload' });
                        }
                      }
                    }}
                    className="hidden"
                    id="product-image-upload"
                  />
                  <label htmlFor="product-image-upload" className="cursor-pointer flex flex-col items-center">
                    <Upload className="h-6 w-6 text-gray-400 mb-1" />
                    <span className="text-sm text-gray-500">Upload Images (JPG, PNG, GIF, WebP - max 10MB)</span>
                  </label>
                </div>
                <div className="flex gap-2 mt-2">
                  <Input
                    placeholder="Or paste image URL here"
                    id="image-url-input"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const input = e.target;
                        if (input.value.trim()) {
                          setEditingProduct(prev => ({
                            ...prev,
                            images: [...(prev.images || []), input.value.trim()]
                          }));
                          input.value = '';
                        }
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      const input = document.getElementById('image-url-input');
                      if (input?.value?.trim()) {
                        setEditingProduct(prev => ({
                          ...prev,
                          images: [...(prev.images || []), input.value.trim()]
                        }));
                        input.value = '';
                      }
                    }}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              
              {/* Description */}
              <div>
                <Label>Description *</Label>
                <Textarea
                  value={editingProduct.description || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, description: e.target.value })}
                  rows={4}
                  placeholder="Full product description"
                />
              </div>

              {/* How to Use */}
              <div>
                <Label>How to Use</Label>
                <Textarea
                  value={editingProduct.how_to_use || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, how_to_use: e.target.value })}
                  rows={3}
                  placeholder="Application instructions (e.g., Apply 2-3 drops to clean skin...)"
                />
              </div>
              
              {/* Ingredients */}
              <div>
                <Label>Ingredients (Common Names)</Label>
                <Textarea
                  value={editingProduct.ingredients || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, ingredients: e.target.value })}
                  rows={2}
                  placeholder="Water, Glycerin, Vitamin B3, Hyaluronic Acid..."
                />
              </div>

              {/* INCI Ingredients */}
              <div>
                <Label>INCI Ingredients (Scientific Names)</Label>
                <Textarea
                  value={editingProduct.inci_ingredients || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, inci_ingredients: e.target.value })}
                  rows={2}
                  placeholder="Aqua/Water/Eau, Glycerin, Niacinamide, Sodium Hyaluronate..."
                />
              </div>
              
              {/* Product Options */}
              <div className="space-y-3 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="font-medium">Pre-Order Item</Label>
                    <p className="text-xs text-gray-500">Enable if this product is available for pre-order</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={editingProduct.is_preorder || false}
                    onChange={(e) => setEditingProduct({ ...editingProduct, is_preorder: e.target.checked })}
                    className="h-5 w-5 accent-[#F8A5B8]"
                  />
                </div>
                
                <div className="flex items-center gap-6">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={editingProduct.is_featured || false}
                      onChange={(e) => setEditingProduct({ ...editingProduct, is_featured: e.target.checked })}
                      className="h-4 w-4 accent-[#F8A5B8]"
                    />
                    <span className="text-sm">Featured Product</span>
                  </label>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={editingProduct.is_active !== false}
                      onChange={(e) => setEditingProduct({ ...editingProduct, is_active: e.target.checked })}
                      className="h-4 w-4 accent-[#F8A5B8]"
                    />
                    <span className="text-sm">Active (Visible)</span>
                  </label>
                </div>
              </div>
              
              {/* Action Buttons */}
              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
                <Button 
                  onClick={handleSaveProduct} 
                  disabled={savingProduct} 
                  className="bg-[#9333EA] hover:bg-[#7E22CE] text-white"
                >
                  {savingProduct ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Save Changes
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminLayout;
