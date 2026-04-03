import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useWebSocket, useWebSocketEvent } from '@/contexts';
import { 
  Users, Award, Sparkles, TestTube, GitCompare, 
  Settings, Save, ChevronDown, ChevronRight, 
  DollarSign, Percent, Gift, Clock, Target, Zap, Crown, Star,
  Share2, Copy, ExternalLink, BarChart3, TrendingUp, Eye,
  Link2, QrCode, Mail, MessageCircle, Twitter, Facebook,
  Coins, ArrowUpRight, ArrowDownRight, RefreshCw, Download,
  Edit3, Trash2, Plus, Check, X, FileText, Image, Type,
  ShoppingBag, Bell, Send, ArrowRight, ArrowLeft, 
  ClipboardList, UserCheck, UserX, Upload, Phone, Calendar,
  ChevronUp, Filter, Search, MoreHorizontal, Package, AlertCircle, CheckSquare, Square,
  Wifi, WifiOff
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Switch } from '../ui/switch';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { Progress } from '../ui/progress';
import { Checkbox } from '../ui/checkbox';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// ============ FOUNDING PRICING EDITOR COMPONENT ============
// Standalone component for the critical pricing controls
const FoundingPricingEditor = () => {
  const [pricing, setPricing] = useState({
    retail_value: 100,
    referral_discount_percent: 30,
    max_discount_percent: 30,
    final_price: 70
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const MAX_DISCOUNT = 30; // Hard-coded safety limit

  // Fetch current pricing on mount
  useEffect(() => {
    const fetchPricing = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        const res = await axios.get(`${API}/api/admin/founding-pricing`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.data) {
          setPricing(res.data);
        }
      } catch (error) {
        console.error('Failed to fetch pricing:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchPricing();
  }, []);

  // Calculate final price when discount changes
  const handleDiscountChange = (value) => {
    let discount = parseFloat(value) || 0;
    // Enforce max 30% cap
    if (discount > MAX_DISCOUNT) {
      discount = MAX_DISCOUNT;
      toast.warning(`Maximum discount is ${MAX_DISCOUNT}%`);
    }
    if (discount < 0) discount = 0;
    
    const finalPrice = pricing.retail_value * (1 - discount / 100);
    setPricing(prev => ({
      ...prev,
      referral_discount_percent: discount,
      final_price: Math.round(finalPrice * 100) / 100
    }));
  };

  // Save pricing
  const savePricing = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/api/admin/founding-pricing`, {
        retail_value: pricing.retail_value,
        referral_discount_percent: pricing.referral_discount_percent
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Pricing updated! Final price is now $' + pricing.final_price.toFixed(2));
    } catch (error) {
      console.error('Failed to save pricing:', error);
      toast.error('Failed to update pricing');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-amber-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Retail Value - Display Only */}
        <div>
          <Label className="text-amber-800">Retail Value</Label>
          <div className="flex items-center gap-2 mt-1">
            <Input
              type="number"
              value={pricing.retail_value}
              onChange={(e) => {
                const val = parseFloat(e.target.value) || 100;
                const finalPrice = val * (1 - pricing.referral_discount_percent / 100);
                setPricing(prev => ({
                  ...prev,
                  retail_value: val,
                  final_price: Math.round(finalPrice * 100) / 100
                }));
              }}
              className="bg-white border-amber-200"
            />
            <span className="text-amber-700 font-medium">CAD</span>
          </div>
        </div>

        {/* Referral Discount - THE KEY FIELD */}
        <div>
          <Label className="text-amber-800 font-semibold">
            Referral Discount %
            <span className="text-red-600 ml-1">(Max 30%)</span>
          </Label>
          <div className="flex items-center gap-2 mt-1">
            <Input
              type="number"
              min={0}
              max={MAX_DISCOUNT}
              value={pricing.referral_discount_percent}
              onChange={(e) => handleDiscountChange(e.target.value)}
              className="bg-white border-amber-300 border-2 font-bold text-lg"
              data-testid="referral-discount-input"
            />
            <span className="text-amber-700 font-medium">%</span>
          </div>
          <p className="text-xs text-amber-600 mt-1">
            Hard cap prevents exceeding 30%
          </p>
        </div>

        {/* Final Price - Calculated */}
        <div>
          <Label className="text-amber-800">Final Price (Calculated)</Label>
          <div className="bg-gradient-to-r from-green-100 to-emerald-100 border-2 border-green-300 rounded-lg p-3 mt-1">
            <span 
              className="text-2xl font-bold text-green-700"
              data-testid="calculated-final-price"
            >
              ${pricing.final_price.toFixed(2)} CAD
            </span>
          </div>
          <p className="text-xs text-green-600 mt-1">
            = ${pricing.retail_value} - {pricing.referral_discount_percent}%
          </p>
        </div>
      </div>

      {/* Price Preview Box */}
      <div className="bg-white border border-amber-200 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Price shown on /founding-member page:</p>
            <p className="text-lg">
              <span className="line-through text-gray-400">${pricing.retail_value.toFixed(2)}</span>
              <span className="mx-2">→</span>
              <span className="font-bold text-green-600 text-xl">${pricing.final_price.toFixed(2)} CAD</span>
            </p>
          </div>
          <Button
            onClick={savePricing}
            disabled={saving}
            className="bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-white"
          >
            {saving ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Update Pricing
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
// ============ END FOUNDING PRICING EDITOR ============

const ProgramsManager = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeProgram, setActiveProgram] = useState('influencer');
  const [activeTab, setActiveTab] = useState('settings'); // Changed to settings as default since control panels are now inline
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareProgram, setShareProgram] = useState(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [adminReferralCode, setAdminReferralCode] = useState(null);
  const [rewardsProfile, setRewardsProfile] = useState(null);
  
  // Last sync timestamp for Quick Actions widget
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [, setTimeTick] = useState(0); // Force re-render for relative time
  
  // Expanded card state for inline control panels
  const [expandedCards, setExpandedCards] = useState({
    influencer: true,  // Partner Program expanded by default
    bioAgeScan: false,
    waitlist: false,
    shop: false,
  });
  
  // Page Editor State
  const [showPageEditor, setShowPageEditor] = useState(false);
  const [pageContent, setPageContent] = useState(null);
  const [savingPage, setSavingPage] = useState(false);
  
  // Analytics data
  const [analytics, setAnalytics] = useState({
    influencer: { totalReferrals: 0, conversions: 0, clicks: 0, earnings: 0, activeUsers: 0 },
    founder: { totalMembers: 0, redemptions: 0, pointsIssued: 0, pointsRedeemed: 0 },
    quiz: { completions: 0, emailsCaptured: 0, discountsUsed: 0, conversionRate: 0 },
    bioAgeScan: { scansCompleted: 0, emailsCaptured: 0, discountsUsed: 0, avgBioAge: 0 },
    comparison: { comparisons: 0, productsCompared: 0, addToCartRate: 0 },
  });

  // Referral tracking data
  const [referralData, setReferralData] = useState([]);
  const [pointsHistory, setPointsHistory] = useState([]);
  const [giftAnalytics, setGiftAnalytics] = useState({
    summary: { total_gifts: 0, total_points_gifted: 0, completed_gifts: 0, pending_gifts: 0, unique_gifters: 0, unique_recipients: 0, avg_gift_size: 0 },
    top_gifters: [],
    top_recipients: [],
    relationships: [],
    recent_gifts: []
  });
  
  // ============ CONTROL PANEL STATE ============
  // Bio-Age Scan Control Panel
  const [bioScans, setBioScans] = useState([]);
  const [bioScansLoading, setBioScansLoading] = useState(false);
  const [selectedScan, setSelectedScan] = useState(null);
  const [showScanDrawer, setShowScanDrawer] = useState(false);
  const [scanResultFile, setScanResultFile] = useState(null);
  const [uploadingResult, setUploadingResult] = useState(false);
  const [sendingNotification, setSendingNotification] = useState(false);
  
  // Partner/Influencer Control Panel
  const [partners, setPartners] = useState([]);
  const [partnersLoading, setPartnersLoading] = useState(false);
  const [selectedPartner, setSelectedPartner] = useState(null);
  const [showPartnerDrawer, setShowPartnerDrawer] = useState(false);
  const [partnerStats, setPartnerStats] = useState({ total: 0, pending: 0, approved: 0, active: 0 });
  
  // Waitlist Control Panel
  const [waitlist, setWaitlist] = useState([]);
  const [waitlistLoading, setWaitlistLoading] = useState(false);
  const [selectedWaitlistEntry, setSelectedWaitlistEntry] = useState(null);
  const [showWaitlistDrawer, setShowWaitlistDrawer] = useState(false);
  
  // Shop Control Panel (products)
  const [products, setProducts] = useState([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [showProductDrawer, setShowProductDrawer] = useState(false);
  
  // Control Panel filters
  const [controlPanelFilter, setControlPanelFilter] = useState('all');
  const [controlPanelSearch, setControlPanelSearch] = useState('');
  
  // Bulk Selection State
  const [selectedPartnerIds, setSelectedPartnerIds] = useState([]);
  const [selectedWaitlistIds, setSelectedWaitlistIds] = useState([]);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  // ============ END CONTROL PANEL STATE ============
  
  // ============ WEBSOCKET REAL-TIME UPDATES ============
  const { isConnected, connectionStatus } = useWebSocket();
  
  // Handler for new orders - show toast and optionally refresh data
  const handleNewOrder = useCallback((data) => {
    toast.success(`🎉 New Order! #${data.order_number}`, {
      description: `$${data.total?.toFixed(2) || 0} from ${data.customer_email || 'customer'}`,
      duration: 5000,
    });
  }, []);
  
  // Handler for new partner applications
  const handleNewPartnerApplication = useCallback((data) => {
    toast.info(`📩 New Partner Application`, {
      description: `${data.name} (${data.platform}, ${data.followers?.toLocaleString() || 0} followers)`,
      duration: 5000,
    });
    // Refresh partners list if the partner section is visible
    if (expandedCards.influencer) {
      fetchPartners();
    }
  }, []);
  
  // Handler for partner approval/rejection
  const handlePartnerStatusChange = useCallback((data) => {
    // Refresh partners list
    fetchPartners();
  }, []);
  
  // Handler for new waitlist signups
  const handleNewWaitlistSignup = useCallback((data) => {
    toast.info(`👋 New Waitlist Signup`, {
      description: `${data.name || data.email}${data.referred_by ? ` (referred by ${data.referred_by})` : ''}`,
      duration: 4000,
    });
    // Refresh waitlist if visible
    if (expandedCards.waitlist) {
      fetchWaitlist();
    }
  }, []);
  
  // Handler for new bio scans
  const handleNewBioScan = useCallback((data) => {
    toast.info(`🔬 New Bio-Age Scan`, {
      description: `${data.name || data.email}`,
      duration: 4000,
    });
    // Refresh bio scans if visible
    if (expandedCards.bioAgeScan) {
      fetchBioScans();
    }
  }, []);
  
  // Subscribe to WebSocket events
  useWebSocketEvent('new_order', handleNewOrder);
  useWebSocketEvent('new_partner_application', handleNewPartnerApplication);
  useWebSocketEvent('partner_approved', handlePartnerStatusChange);
  useWebSocketEvent('partner_rejected', handlePartnerStatusChange);
  useWebSocketEvent('new_waitlist_signup', handleNewWaitlistSignup);
  useWebSocketEvent('new_bio_scan', handleNewBioScan);
  // ============ END WEBSOCKET ============

  // Program settings state
  const [programs, setPrograms] = useState({
    influencer: {
      enabled: true,
      program_name: 'ReRoots Partner Program',
      commission_type: 'percentage',
      commission_rate: 10,
      customer_discount_type: 'percentage',
      customer_discount_value: 20,
      customer_discount_label: 'Partner Exclusive',
      allow_coupon_stacking: true,
      min_payout_threshold: 50,
      cookie_duration_days: 30,
      points_per_dollar: 1,
      points_redemption_rate: 100, // 100 points = $1
    },
    founder: {
      enabled: true,
      founder_discount_enabled: true,
      founder_discount_percent: 50,
      founder_subsidy: {
        enabled: true,
        rate: 50,
        max_subsidy_amount: 100,
        applies_to: 'all',
      },
      voucher_gate_enabled: false,
      voucher_gate_threshold: 100,
      points_multiplier: 2, // Founders earn 2x points
      exclusive_rewards: true,
    },
    quiz: {
      enabled: true,
      quiz_name: 'Skin Health Quiz',
      completion_reward_type: 'points',
      completion_reward_value: 50,
      show_product_recommendations: true,
      collect_email: true,
      collect_phone: false,
      bonus_points_for_sharing: 25,
    },
    bioAgeScan: {
      enabled: true,
      scan_name: 'Bio-Age Skin Analysis',
      show_age_estimate: true,
      show_recommendations: true,
      collect_email: true,
      email_results: true,
      offer_discount: true,
      discount_code: 'BIOSCAN10',
      discount_value: 10,
      points_for_scan: 100,
      points_for_sharing: 50,
    },
    comparison: {
      enabled: true,
      tool_name: 'Product Comparison Tool',
      max_products: 4,
      show_pricing: true,
      show_ingredients: true,
      highlight_differences: true,
      points_for_using: 10,
    },
  });

  // Load settings and analytics
  useEffect(() => {
    const loadData = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        const headers = { Authorization: `Bearer ${token}` };
        
        // Load admin's rewards profile for referral code
        try {
          const profileRes = await axios.get(`${API}/api/rewards/profile`, { headers });
          if (profileRes.data) {
            setRewardsProfile(profileRes.data);
            setAdminReferralCode(profileRes.data.referral_code);
          }
        } catch (e) {
          console.log('Could not load rewards profile:', e);
        }
        
        // Load settings
        const settingsRes = await axios.get(`${API}/api/store-settings`, { headers });
        const settings = settingsRes.data;
        
        // Map backend settings to our state
        setPrograms(prev => ({
          ...prev,
          influencer: {
            ...prev.influencer,
            enabled: settings.influencer_program?.enabled ?? true,
            program_name: settings.influencer_program?.program_name || 'ReRoots Partner Program',
            commission_type: settings.influencer_program?.commission_type || 'percentage',
            commission_rate: settings.influencer_program?.commission_rate || 10,
            customer_discount_type: settings.influencer_program?.customer_discount_type || 'percentage',
            customer_discount_value: settings.influencer_program?.customer_discount_value || 20,
            customer_discount_label: settings.influencer_program?.customer_discount_label || 'Partner Exclusive',
            allow_coupon_stacking: settings.influencer_program?.allow_coupon_stacking ?? true,
            min_payout_threshold: settings.influencer_program?.min_payout_threshold || 50,
            cookie_duration_days: settings.influencer_program?.cookie_duration_days || 30,
            points_per_dollar: settings.influencer_program?.points_per_dollar || 1,
            points_redemption_rate: settings.influencer_program?.points_redemption_rate || 100,
          },
          founder: {
            ...prev.founder,
            enabled: settings.founder_discount_enabled ?? true,
            founder_discount_enabled: settings.founder_discount_enabled ?? true,
            founder_discount_percent: settings.founder_discount_percent || 50,
            founder_subsidy: settings.founder_subsidy || prev.founder.founder_subsidy,
            voucher_gate_enabled: settings.influencer_program?.voucher_gate_enabled ?? false,
            voucher_gate_threshold: settings.influencer_program?.voucher_gate_threshold || 100,
            points_multiplier: settings.founder_points_multiplier || 2,
          },
          quiz: {
            ...prev.quiz,
            enabled: settings.quiz_program?.enabled ?? true,
            quiz_name: settings.quiz_program?.quiz_name || 'Skin Health Quiz',
            completion_reward_type: settings.quiz_program?.completion_reward_type || 'points',
            completion_reward_value: settings.quiz_program?.completion_reward_value || 50,
            show_product_recommendations: settings.quiz_program?.show_product_recommendations ?? true,
            collect_email: settings.quiz_program?.collect_email ?? true,
            collect_phone: settings.quiz_program?.collect_phone ?? false,
            bonus_points_for_sharing: settings.quiz_program?.bonus_points_for_sharing || 25,
          },
          bioAgeScan: {
            ...prev.bioAgeScan,
            enabled: settings.bio_age_scan?.enabled ?? true,
            scan_name: settings.bio_age_scan?.scan_name || 'Bio-Age Skin Analysis',
            show_age_estimate: settings.bio_age_scan?.show_age_estimate ?? true,
            show_recommendations: settings.bio_age_scan?.show_recommendations ?? true,
            collect_email: settings.bio_age_scan?.collect_email ?? true,
            email_results: settings.bio_age_scan?.email_results ?? true,
            offer_discount: settings.bio_age_scan?.offer_discount ?? true,
            discount_code: settings.bio_age_scan?.discount_code || 'BIOSCAN10',
            discount_value: settings.bio_age_scan?.discount_value || 10,
            points_for_scan: settings.bio_age_scan?.points_for_scan || 100,
            points_for_sharing: settings.bio_age_scan?.points_for_sharing || 50,
          },
          comparison: {
            ...prev.comparison,
            enabled: settings.comparison_tool?.enabled ?? true,
            tool_name: settings.comparison_tool?.tool_name || 'Product Comparison Tool',
            max_products: settings.comparison_tool?.max_products || 4,
            show_pricing: settings.comparison_tool?.show_pricing ?? true,
            show_ingredients: settings.comparison_tool?.show_ingredients ?? true,
            highlight_differences: settings.comparison_tool?.highlight_differences ?? true,
            points_for_using: settings.comparison_tool?.points_for_using || 10,
          },
        }));

        // Load analytics data from real API
        try {
          const analyticsRes = await axios.get(`${API}/api/admin/program-analytics`, { headers });
          if (analyticsRes.data) {
            setAnalytics(analyticsRes.data);
          }
        } catch (e) {
          console.log('Could not load program analytics:', e);
          // Keep default values (zeros)
        }

        // Load referral tracking data from real API
        try {
          const referralsRes = await axios.get(`${API}/api/admin/referral-tracking`, { headers });
          setReferralData(referralsRes.data?.referrals || []);
        } catch (e) {
          console.log('Could not load referral tracking data:', e);
          setReferralData([]);
        }

        // Load points history from real API
        try {
          const pointsRes = await axios.get(`${API}/api/admin/points-history`, { headers });
          setPointsHistory(pointsRes.data?.history || []);
        } catch (e) {
          console.log('Could not load points history:', e);
          setPointsHistory([]);
        }

        // Load gift analytics (THE GOLD MINE)
        try {
          const giftRes = await axios.get(`${API}/api/admin/gift-analytics`, { headers });
          setGiftAnalytics(giftRes.data || {
            summary: { total_gifts: 0, total_points_gifted: 0, completed_gifts: 0, pending_gifts: 0, unique_gifters: 0, unique_recipients: 0, avg_gift_size: 0 },
            top_gifters: [],
            top_recipients: [],
            relationships: [],
            recent_gifts: []
          });
        } catch (e) {
          console.log('Could not load gift analytics:', e);
        }

      } catch (error) {
        console.error('Failed to load data:', error);
        toast.error('Failed to load program data');
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, []);

  // Save all program settings
  const saveSettings = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('reroots_token');
      
      const updateData = {
        influencer_program: {
          enabled: programs.influencer.enabled,
          program_name: programs.influencer.program_name,
          commission_type: programs.influencer.commission_type,
          commission_rate: programs.influencer.commission_rate,
          customer_discount_type: programs.influencer.customer_discount_type,
          customer_discount_value: programs.influencer.customer_discount_value,
          customer_discount_label: programs.influencer.customer_discount_label,
          allow_coupon_stacking: programs.influencer.allow_coupon_stacking,
          min_payout_threshold: programs.influencer.min_payout_threshold,
          cookie_duration_days: programs.influencer.cookie_duration_days,
          points_per_dollar: programs.influencer.points_per_dollar,
          points_redemption_rate: programs.influencer.points_redemption_rate,
          voucher_gate_enabled: programs.founder.voucher_gate_enabled,
          voucher_gate_threshold: programs.founder.voucher_gate_threshold,
        },
        founder_discount_enabled: programs.founder.enabled,
        founder_discount_percent: programs.founder.founder_discount_percent,
        founder_subsidy: programs.founder.founder_subsidy,
        founder_points_multiplier: programs.founder.points_multiplier,
        quiz_program: {
          enabled: programs.quiz.enabled,
          quiz_name: programs.quiz.quiz_name,
          completion_reward_type: programs.quiz.completion_reward_type,
          completion_reward_value: programs.quiz.completion_reward_value,
          show_product_recommendations: programs.quiz.show_product_recommendations,
          collect_email: programs.quiz.collect_email,
          collect_phone: programs.quiz.collect_phone,
          bonus_points_for_sharing: programs.quiz.bonus_points_for_sharing,
        },
        bio_age_scan: {
          enabled: programs.bioAgeScan.enabled,
          scan_name: programs.bioAgeScan.scan_name,
          show_age_estimate: programs.bioAgeScan.show_age_estimate,
          show_recommendations: programs.bioAgeScan.show_recommendations,
          collect_email: programs.bioAgeScan.collect_email,
          email_results: programs.bioAgeScan.email_results,
          offer_discount: programs.bioAgeScan.offer_discount,
          discount_code: programs.bioAgeScan.discount_code,
          discount_value: programs.bioAgeScan.discount_value,
          points_for_scan: programs.bioAgeScan.points_for_scan,
          points_for_sharing: programs.bioAgeScan.points_for_sharing,
        },
        comparison_tool: {
          enabled: programs.comparison.enabled,
          tool_name: programs.comparison.tool_name,
          max_products: programs.comparison.max_products,
          show_pricing: programs.comparison.show_pricing,
          show_ingredients: programs.comparison.show_ingredients,
          highlight_differences: programs.comparison.highlight_differences,
          points_for_using: programs.comparison.points_for_using,
        },
      };
      
      await axios.put(`${API}/api/admin/store-settings`, updateData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success('Program settings saved!');
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  // Update a specific program setting
  const updateProgram = (programKey, field, value) => {
    setPrograms(prev => ({
      ...prev,
      [programKey]: {
        ...prev[programKey],
        [field]: value,
      },
    }));
  };

  // Update nested setting
  const updateNestedSetting = (programKey, parentField, field, value) => {
    setPrograms(prev => ({
      ...prev,
      [programKey]: {
        ...prev[programKey],
        [parentField]: {
          ...prev[programKey][parentField],
          [field]: value,
        },
      },
    }));
  };

  // ============ CONTROL PANEL DATA FETCHING ============
  
  // Fetch Bio-Age Scans for Control Panel
  const fetchBioScans = useCallback(async () => {
    setBioScansLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/api/admin/bio-age-scans`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBioScans(res.data?.scans || []);
    } catch (error) {
      console.error('Failed to fetch bio scans:', error);
      toast.error('Failed to load bio scans');
    } finally {
      setBioScansLoading(false);
    }
  }, []);

  // Fetch Partners/Influencers for Control Panel
  const fetchPartners = useCallback(async () => {
    setPartnersLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/api/admin/influencers`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPartners(res.data?.applications || []);
      // Stats are nested under res.data.stats
      const stats = res.data?.stats || {};
      setPartnerStats({
        total: stats.total || 0,
        pending: stats.pending || 0,
        approved: stats.approved || 0,
        active: stats.active || 0,
      });
    } catch (error) {
      console.error('Failed to fetch partners:', error);
      toast.error('Failed to load partners');
    } finally {
      setPartnersLoading(false);
    }
  }, []);

  // Fetch Waitlist entries for Control Panel
  const fetchWaitlist = useCallback(async () => {
    setWaitlistLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/api/admin/waitlist`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWaitlist(res.data?.entries || []);
    } catch (error) {
      console.error('Failed to fetch waitlist:', error);
      toast.error('Failed to load waitlist');
    } finally {
      setWaitlistLoading(false);
    }
  }, []);

  // Fetch Products for Shop Control Panel
  const fetchProducts = useCallback(async () => {
    setProductsLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.get(`${API}/api/products`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProducts(res.data || []);
    } catch (error) {
      console.error('Failed to fetch products:', error);
      toast.error('Failed to load products');
    } finally {
      setProductsLoading(false);
    }
  }, []);

  // Load ALL Control Panel data on initial mount for inline panels
  useEffect(() => {
    // Fetch all data needed for inline control panels
    fetchPartners();
    fetchWaitlist();
    fetchBioScans();
    fetchProducts();
  }, [fetchPartners, fetchWaitlist, fetchBioScans, fetchProducts]);

  // Update sync timestamp when data loads
  useEffect(() => {
    if (!partnersLoading && !waitlistLoading && !bioScansLoading && !productsLoading && !loading) {
      setLastSyncTime(new Date());
    }
  }, [partnersLoading, waitlistLoading, bioScansLoading, productsLoading, loading]);

  // Update relative time every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setTimeTick(t => t + 1);
    }, 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  // Helper function to get relative time string
  const getRelativeTime = (date) => {
    if (!date) return 'Never';
    const now = new Date();
    const diffMs = now - date;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    
    if (diffSeconds < 30) return 'Just now';
    if (diffSeconds < 60) return `${diffSeconds} seconds ago`;
    if (diffMinutes === 1) return '1 minute ago';
    if (diffMinutes < 60) return `${diffMinutes} minutes ago`;
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;
    return date.toLocaleString();
  };

  // Manual refresh all data
  const refreshAllData = async () => {
    await Promise.all([
      fetchPartners(),
      fetchWaitlist(),
      fetchBioScans(),
      fetchProducts()
    ]);
    setLastSyncTime(new Date());
    toast.success('Data refreshed!');
  };
  
  // Toggle expanded state for inline control panels
  const toggleCardExpanded = (programKey) => {
    setExpandedCards(prev => ({
      ...prev,
      [programKey]: !prev[programKey]
    }));
  };

  // Approve Partner
  const handleApprovePartner = async (partnerId) => {
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.put(`${API}/api/admin/influencers/${partnerId}/approve`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Approved! Partner code: ${res.data.partner_code}`);
      fetchPartners(); // Refresh list
      setShowPartnerDrawer(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to approve partner');
    }
  };

  // Reject Partner
  const handleRejectPartner = async (partnerId, reason = 'Does not meet requirements') => {
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/api/admin/influencers/${partnerId}/reject`, { reason }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Application rejected');
      fetchPartners(); // Refresh list
      setShowPartnerDrawer(false);
    } catch (error) {
      toast.error('Failed to reject partner');
    }
  };

  // Send invite to waitlist member
  const handleSendWaitlistInvite = async (entry) => {
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.post(`${API}/api/admin/waitlist/invite`, { email: entry.email }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Invite sent to ${entry.email}`);
    } catch (error) {
      toast.error('Failed to send invite');
    }
  };

  // Open detail drawer with user info
  const openDetailDrawer = (type, item) => {
    if (type === 'scan') {
      setSelectedScan(item);
      setShowScanDrawer(true);
    } else if (type === 'partner') {
      setSelectedPartner(item);
      setShowPartnerDrawer(true);
    } else if (type === 'waitlist') {
      setSelectedWaitlistEntry(item);
      setShowWaitlistDrawer(true);
    } else if (type === 'product') {
      setSelectedProduct(item);
      setShowProductDrawer(true);
    }
  };

  // ============ BULK ACTION FUNCTIONS ============
  
  // Toggle partner selection
  const togglePartnerSelection = (partnerId) => {
    setSelectedPartnerIds(prev => 
      prev.includes(partnerId) 
        ? prev.filter(id => id !== partnerId)
        : [...prev, partnerId]
    );
  };

  // Toggle all partners selection
  const toggleAllPartners = (filteredPartners) => {
    const pendingPartners = filteredPartners.filter(p => p.status === 'pending');
    const pendingIds = pendingPartners.map(p => p.id);
    
    if (selectedPartnerIds.length === pendingIds.length && pendingIds.length > 0) {
      setSelectedPartnerIds([]);
    } else {
      setSelectedPartnerIds(pendingIds);
    }
  };

  // Bulk approve partners
  const handleBulkApprovePartners = async () => {
    if (selectedPartnerIds.length === 0) return;
    
    setBulkActionLoading(true);
    const token = localStorage.getItem('reroots_token');
    let successCount = 0;
    let failCount = 0;
    
    for (const partnerId of selectedPartnerIds) {
      try {
        await axios.put(`${API}/api/admin/influencers/${partnerId}/approve`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        failCount++;
      }
    }
    
    setBulkActionLoading(false);
    setSelectedPartnerIds([]);
    fetchPartners();
    
    if (successCount > 0) {
      toast.success(`Approved ${successCount} partner${successCount > 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      toast.error(`Failed to approve ${failCount} partner${failCount > 1 ? 's' : ''}`);
    }
  };

  // Bulk reject partners
  const handleBulkRejectPartners = async () => {
    if (selectedPartnerIds.length === 0) return;
    
    setBulkActionLoading(true);
    const token = localStorage.getItem('reroots_token');
    let successCount = 0;
    let failCount = 0;
    
    for (const partnerId of selectedPartnerIds) {
      try {
        await axios.put(`${API}/api/admin/influencers/${partnerId}/reject`, { reason: 'Bulk rejection' }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        failCount++;
      }
    }
    
    setBulkActionLoading(false);
    setSelectedPartnerIds([]);
    fetchPartners();
    
    if (successCount > 0) {
      toast.success(`Rejected ${successCount} partner${successCount > 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      toast.error(`Failed to reject ${failCount} partner${failCount > 1 ? 's' : ''}`);
    }
  };

  // Toggle waitlist selection
  const toggleWaitlistSelection = (entryId) => {
    setSelectedWaitlistIds(prev => 
      prev.includes(entryId) 
        ? prev.filter(id => id !== entryId)
        : [...prev, entryId]
    );
  };

  // Toggle all waitlist selection
  const toggleAllWaitlist = (filteredWaitlist) => {
    const allIds = filteredWaitlist.map(w => w.id || w.email);
    
    if (selectedWaitlistIds.length === allIds.length && allIds.length > 0) {
      setSelectedWaitlistIds([]);
    } else {
      setSelectedWaitlistIds(allIds);
    }
  };

  // Bulk send invites to waitlist
  const handleBulkSendInvites = async () => {
    if (selectedWaitlistIds.length === 0) return;
    
    setBulkActionLoading(true);
    const token = localStorage.getItem('reroots_token');
    let successCount = 0;
    let failCount = 0;
    
    const selectedEntries = waitlist.filter(w => selectedWaitlistIds.includes(w.id || w.email));
    
    for (const entry of selectedEntries) {
      try {
        await axios.post(`${API}/api/admin/waitlist/invite`, { email: entry.email }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        failCount++;
      }
    }
    
    setBulkActionLoading(false);
    setSelectedWaitlistIds([]);
    
    if (successCount > 0) {
      toast.success(`Sent ${successCount} invite${successCount > 1 ? 's' : ''}`);
    }
    if (failCount > 0) {
      toast.error(`Failed to send ${failCount} invite${failCount > 1 ? 's' : ''}`);
    }
  };
  // ============ END BULK ACTION FUNCTIONS ============

  // ============ BIO-AGE SCAN RESULT FUNCTIONS ============
  
  // Handle PDF file selection for bio-age results
  const handleResultFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.type !== 'application/pdf') {
        toast.error('Please select a PDF file');
        return;
      }
      if (file.size > 10 * 1024 * 1024) { // 10MB limit
        toast.error('File size must be less than 10MB');
        return;
      }
      setScanResultFile(file);
      toast.success(`Selected: ${file.name}`);
    }
  };

  // Upload PDF result to Cloudinary and save to scan record
  const handleUploadResult = async () => {
    if (!scanResultFile || !selectedScan) return;
    
    setUploadingResult(true);
    const token = localStorage.getItem('reroots_token');
    
    try {
      // Create form data for file upload
      const formData = new FormData();
      formData.append('file', scanResultFile);
      formData.append('scan_id', selectedScan.id || selectedScan._id);
      
      // Upload to backend which will handle Cloudinary
      const response = await axios.post(`${API}/api/admin/bio-age-scans/upload-result`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      
      if (response.data.success) {
        toast.success('Result PDF uploaded successfully!');
        
        // Update local state
        setSelectedScan(prev => ({
          ...prev,
          result_pdf_url: response.data.pdf_url,
          results_uploaded: true,
          results_uploaded_at: new Date().toISOString()
        }));
        
        setScanResultFile(null);
        
        // Refresh scans list
        fetchBioScans();
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error(error.response?.data?.detail || 'Failed to upload result');
    } finally {
      setUploadingResult(false);
    }
  };

  // Send results notification email to customer
  const handleSendResultsNotification = async () => {
    if (!selectedScan?.email) {
      toast.error('No email address available');
      return;
    }
    
    setSendingNotification(true);
    const token = localStorage.getItem('reroots_token');
    
    try {
      const response = await axios.post(`${API}/api/admin/bio-age-scans/send-results`, {
        scan_id: selectedScan.id || selectedScan._id,
        email: selectedScan.email,
        name: selectedScan.name,
        bio_age: selectedScan.bio_age || selectedScan.bioAge,
        pdf_url: selectedScan.result_pdf_url
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.success) {
        toast.success('Results notification sent to customer!');
        
        // Update local state
        setSelectedScan(prev => ({
          ...prev,
          results_sent: true,
          results_sent_at: new Date().toISOString()
        }));
        
        // Refresh scans list
        fetchBioScans();
      }
    } catch (error) {
      console.error('Send notification error:', error);
      toast.error(error.response?.data?.detail || 'Failed to send notification');
    } finally {
      setSendingNotification(false);
    }
  };
  // ============ END BIO-AGE SCAN RESULT FUNCTIONS ============

  // ============ SHOP QUICK ACTION FUNCTIONS ============
  
  // Quick toggle product stock (mark as sold out / in stock)
  const handleQuickToggleStock = async (productId, currentStock) => {
    const token = localStorage.getItem('reroots_token');
    const newStock = currentStock === 0 ? 10 : 0; // Toggle between sold out and 10
    
    try {
      await axios.put(`${API}/api/admin/products/${productId}`, 
        { stock: newStock },
        { headers: { Authorization: `Bearer ${token}` }}
      );
      
      // Update local state
      setProducts(prev => prev.map(p => 
        (p.id === productId || p._id === productId) 
          ? { ...p, stock: newStock }
          : p
      ));
      
      toast.success(newStock === 0 ? 'Marked as Sold Out' : 'Marked as In Stock (10)');
    } catch (error) {
      toast.error('Failed to update stock');
    }
  };

  // Quick edit price (inline)
  const [editingProductPrice, setEditingProductPrice] = useState(null);
  const [tempPrice, setTempPrice] = useState('');
  
  const handleQuickPriceEdit = async (productId) => {
    const token = localStorage.getItem('reroots_token');
    const newPrice = parseFloat(tempPrice);
    
    if (isNaN(newPrice) || newPrice < 0) {
      toast.error('Please enter a valid price');
      return;
    }
    
    try {
      await axios.put(`${API}/api/admin/products/${productId}`, 
        { price: newPrice },
        { headers: { Authorization: `Bearer ${token}` }}
      );
      
      // Update local state
      setProducts(prev => prev.map(p => 
        (p.id === productId || p._id === productId) 
          ? { ...p, price: newPrice }
          : p
      ));
      
      setEditingProductPrice(null);
      setTempPrice('');
      toast.success('Price updated!');
    } catch (error) {
      toast.error('Failed to update price');
    }
  };
  // ============ END SHOP QUICK ACTION FUNCTIONS ============

  // ============ END CONTROL PANEL FUNCTIONS ============

  // Copy referral link
  const copyReferralLink = (link) => {
    navigator.clipboard.writeText(link);
    setCopiedLink(true);
    toast.success('Link copied to clipboard!');
    setTimeout(() => setCopiedLink(false), 2000);
  };

  // Open share modal
  const openShareModal = (programKey) => {
    setShareProgram(programKey);
    setShowShareModal(true);
  };

  // Get program link for sharing (clean URL without referral code for admin)
  const getProgramLink = (programKey) => {
    const baseUrl = 'https://www.reroots.ca'; // Production URL
    const programPaths = {
      influencer: '/influencer',
      founder: '/founding-member',
      quiz: '/skin-quiz',
      bioAgeScan: '/Bio-Age-Repair-Scan',
      comparison: '/compare',
      shop: '/shop',
      waitlist: '/waitlist',
    };
    return `${baseUrl}${programPaths[programKey] || ''}`;
  };

  // Load page content for editing
  const loadPageContent = async (programKey) => {
    const token = localStorage.getItem('reroots_token');
    try {
      const endpoints = {
        influencer: `${API}/api/influencer-page`,
        quiz: `${API}/api/quiz-page`,
        bioAgeScan: `${API}/api/bio-scan-page`,
        comparison: `${API}/api/comparison-page`,
        shop: `${API}/api/shop-page`,
        waitlist: `${API}/api/waitlist-page`,
      };
      
      const endpoint = endpoints[programKey];
      
      if (endpoint) {
        const res = await axios.get(endpoint, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setPageContent(res.data);
        setActiveProgram(programKey);
        setShowPageEditor(true);
      }
    } catch (e) {
      console.error('Error loading page content:', e);
      toast.error('Failed to load page content');
    }
  };

  // Save page content
  const savePageContent = async () => {
    const token = localStorage.getItem('reroots_token');
    setSavingPage(true);
    try {
      const endpoints = {
        influencer: `${API}/api/admin/influencer-page`,
        quiz: `${API}/api/admin/quiz-page`,
        bioAgeScan: `${API}/api/admin/bio-scan-page`,
        comparison: `${API}/api/admin/comparison-page`,
        shop: `${API}/api/admin/shop-page`,
        waitlist: `${API}/api/admin/waitlist-page`,
      };
      
      const endpoint = endpoints[activeProgram];
      
      if (endpoint) {
        await axios.put(endpoint, pageContent, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Page content saved successfully!');
        setShowPageEditor(false);
      }
    } catch (e) {
      console.error('Error saving page content:', e);
      toast.error('Failed to save page content');
    } finally {
      setSavingPage(false);
    }
  };

  // Update page content field
  const updatePageField = (section, field, value) => {
    setPageContent(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }));
  };

  // Preview page with unsaved changes
  const previewPage = () => {
    // Map program keys to page URLs and storage keys
    const pageConfig = {
      influencer: { url: '/influencer', storageKey: 'preview_influencer_page' },
      quiz: { url: '/skin-quiz', storageKey: 'preview_quiz_page' },
      bioAgeScan: { url: '/Bio-Age-Repair-Scan', storageKey: 'preview_bio_scan_page' },
      comparison: { url: '/compare', storageKey: 'preview_comparison_page' },
      shop: { url: '/shop', storageKey: 'preview_shop_page' },
      waitlist: { url: '/waitlist', storageKey: 'preview_waitlist_page' },
    };

    const config = pageConfig[activeProgram];
    if (!config || !pageContent) {
      toast.error('Unable to preview this page');
      return;
    }

    // Save current editor content to sessionStorage
    sessionStorage.setItem(config.storageKey, JSON.stringify({
      ...pageContent,
      _isPreview: true,
      _timestamp: Date.now()
    }));

    // Open the page in a new tab
    window.open(config.url, '_blank');
    toast.success('Preview opened in new tab');
  };

  const programCards = [
    {
      key: 'influencer',
      icon: Users,
      title: 'Partner/Influencer Program',
      description: 'Manage affiliate commissions and partner discounts',
      color: 'purple',
      stats: analytics.influencer,
    },
    {
      key: 'founder',
      icon: Crown,
      title: 'Founder Program',
      description: 'Exclusive discounts for founding members',
      color: 'yellow',
      stats: analytics.founder,
    },
    {
      key: 'quiz',
      icon: Sparkles,
      title: 'Quiz Program',
      description: 'Skin health quiz with rewards',
      color: 'pink',
      stats: analytics.quiz,
    },
    {
      key: 'bioAgeScan',
      icon: TestTube,
      title: 'Bio-Age Scan',
      description: 'AI-powered skin analysis tool',
      color: 'blue',
      stats: analytics.bioAgeScan,
    },
    {
      key: 'comparison',
      icon: GitCompare,
      title: 'Comparison Tool',
      description: 'Product comparison feature settings',
      color: 'green',
      stats: analytics.comparison,
      hasSubFeatures: true, // Flag to show Biomarker Benchmarks link
    },
    {
      key: 'shop',
      icon: ShoppingBag,
      title: 'Shop Page',
      description: 'Collections and shop landing page',
      color: 'orange',
      stats: { comparisons: 0, productsCompared: 0, addToCartRate: 0 },
    },
    {
      key: 'waitlist',
      icon: Bell,
      title: 'Waitlist Page',
      description: 'Early access and waitlist signup page',
      color: 'teal',
      stats: { comparisons: 0, productsCompared: 0, addToCartRate: 0 },
    },
  ];

  const getColorClasses = (color, enabled) => {
    const colors = {
      purple: enabled ? 'bg-purple-100 border-purple-300 text-purple-700' : 'bg-gray-100 border-gray-300 text-gray-500',
      yellow: enabled ? 'bg-yellow-100 border-yellow-300 text-yellow-700' : 'bg-gray-100 border-gray-300 text-gray-500',
      pink: enabled ? 'bg-pink-100 border-pink-300 text-pink-700' : 'bg-gray-100 border-gray-300 text-gray-500',
      blue: enabled ? 'bg-blue-100 border-blue-300 text-blue-700' : 'bg-gray-100 border-gray-300 text-gray-500',
      green: enabled ? 'bg-green-100 border-green-300 text-green-700' : 'bg-gray-100 border-gray-300 text-gray-500',
      orange: enabled ? 'bg-orange-100 border-orange-300 text-orange-700' : 'bg-gray-100 border-gray-300 text-gray-500',
      teal: enabled ? 'bg-teal-100 border-teal-300 text-teal-700' : 'bg-gray-100 border-gray-300 text-gray-500',
    };
    return colors[color] || colors.gray;
  };

  // Stats Card Component
  const StatCard = ({ label, value, icon: Icon, trend, color = 'blue' }) => (
    <div className={`bg-${color}-50 rounded-lg p-3`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-600">{label}</span>
        {Icon && <Icon className={`h-4 w-4 text-${color}-500`} />}
      </div>
      <div className="flex items-end gap-2 mt-1">
        <span className={`text-xl font-bold text-${color}-700`}>{value}</span>
        {trend && (
          <span className={`text-xs flex items-center ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend > 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>
    </div>
  );

  // ============ INLINE CONTROL PANEL COMPONENTS ============
  
  // Inline Partner Control Panel - shows pending applications with action buttons
  const InlinePartnerControlPanel = () => {
    const pendingPartners = partners.filter(p => p.status === 'pending');
    const displayPartners = pendingPartners.slice(0, 5); // Show max 5 items inline
    
    return (
      <div className="mt-4 pt-4 border-t border-purple-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-purple-600" />
            <span className="text-sm font-medium text-purple-800">Pending Applications</span>
            {pendingPartners.length > 0 && (
              <Badge className="bg-yellow-100 text-yellow-700 text-xs">{pendingPartners.length}</Badge>
            )}
          </div>
          {pendingPartners.length > 5 && (
            <Button 
              size="sm" 
              variant="ghost" 
              className="text-xs text-purple-600"
              onClick={(e) => {
                e.stopPropagation();
                setActiveProgram('influencer');
                setActiveTab('control');
              }}
            >
              View All ({pendingPartners.length})
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
        
        {partnersLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600"></div>
          </div>
        ) : displayPartners.length === 0 ? (
          <div className="text-center py-4 bg-purple-50/50 rounded-lg">
            <UserCheck className="h-6 w-6 mx-auto text-green-500 mb-1" />
            <p className="text-xs text-gray-600">All caught up! No pending applications.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Bulk select all if multiple pending */}
            {displayPartners.length > 1 && (
              <div className="flex items-center justify-between bg-purple-50/50 rounded px-2 py-1.5 mb-2">
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={selectedPartnerIds.length === displayPartners.length && displayPartners.length > 0}
                    onCheckedChange={() => {
                      const ids = displayPartners.map(p => p.id);
                      if (selectedPartnerIds.length === ids.length) {
                        setSelectedPartnerIds([]);
                      } else {
                        setSelectedPartnerIds(ids);
                      }
                    }}
                    onClick={(e) => e.stopPropagation()}
                    data-testid="inline-select-all-partners"
                  />
                  <span className="text-xs text-purple-700">Select All</span>
                </div>
                {selectedPartnerIds.length > 0 && (
                  <div className="flex gap-1">
                    <Button 
                      size="sm" 
                      className="h-6 px-2 text-xs bg-green-600 hover:bg-green-700"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleBulkApprovePartners();
                      }}
                      disabled={bulkActionLoading}
                      data-testid="inline-bulk-approve-btn"
                    >
                      <Check className="h-3 w-3 mr-1" />
                      Approve ({selectedPartnerIds.length})
                    </Button>
                    <Button 
                      size="sm" 
                      variant="destructive"
                      className="h-6 px-2 text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleBulkRejectPartners();
                      }}
                      disabled={bulkActionLoading}
                      data-testid="inline-bulk-reject-btn"
                    >
                      <X className="h-3 w-3 mr-1" />
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            )}
            
            {displayPartners.map((partner, idx) => (
              <div 
                key={partner.id || idx} 
                className="flex items-center justify-between bg-white border border-purple-100 rounded-lg p-2 hover:border-purple-300 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={selectedPartnerIds.includes(partner.id)}
                    onCheckedChange={() => togglePartnerSelection(partner.id)}
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`inline-partner-checkbox-${idx}`}
                  />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      openDetailDrawer('partner', partner);
                    }}
                    className="text-left hover:text-purple-600 cursor-pointer"
                    data-testid={`inline-partner-name-${idx}`}
                  >
                    <p className="text-sm font-medium">{partner.name || partner.email?.split('@')[0]}</p>
                    <p className="text-xs text-gray-500">{partner.email}</p>
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  <Button 
                    size="sm" 
                    className="h-7 px-2 text-xs bg-green-600 hover:bg-green-700"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleApprovePartner(partner.id);
                    }}
                    data-testid={`inline-approve-btn-${idx}`}
                  >
                    <Check className="h-3 w-3 mr-1" />
                    Approve
                  </Button>
                  <Button 
                    size="sm" 
                    variant="ghost"
                    className="h-7 px-2 text-xs text-red-600 hover:bg-red-50"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRejectPartner(partner.id);
                    }}
                    data-testid={`inline-reject-btn-${idx}`}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Inline Waitlist Control Panel - shows waitlist entries with invite buttons
  const InlineWaitlistControlPanel = () => {
    const displayWaitlist = waitlist.slice(0, 5);
    
    return (
      <div className="mt-4 pt-4 border-t border-teal-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-teal-600" />
            <span className="text-sm font-medium text-teal-800">Waitlist Members</span>
            {waitlist.length > 0 && (
              <Badge className="bg-teal-100 text-teal-700 text-xs">{waitlist.length}</Badge>
            )}
          </div>
          {waitlist.length > 5 && (
            <Button 
              size="sm" 
              variant="ghost" 
              className="text-xs text-teal-600"
              onClick={(e) => {
                e.stopPropagation();
                setActiveProgram('waitlist');
                setActiveTab('control');
              }}
            >
              View All ({waitlist.length})
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
        
        {waitlistLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-teal-600"></div>
          </div>
        ) : displayWaitlist.length === 0 ? (
          <div className="text-center py-4 bg-teal-50/50 rounded-lg">
            <Bell className="h-6 w-6 mx-auto text-gray-400 mb-1" />
            <p className="text-xs text-gray-600">No waitlist entries yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Bulk select all */}
            {displayWaitlist.length > 1 && (
              <div className="flex items-center justify-between bg-teal-50/50 rounded px-2 py-1.5 mb-2">
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={selectedWaitlistIds.length === displayWaitlist.length && displayWaitlist.length > 0}
                    onCheckedChange={() => {
                      const ids = displayWaitlist.map(w => w.id || w.email);
                      if (selectedWaitlistIds.length === ids.length) {
                        setSelectedWaitlistIds([]);
                      } else {
                        setSelectedWaitlistIds(ids);
                      }
                    }}
                    onClick={(e) => e.stopPropagation()}
                    data-testid="inline-select-all-waitlist"
                  />
                  <span className="text-xs text-teal-700">Select All</span>
                </div>
                {selectedWaitlistIds.length > 0 && (
                  <Button 
                    size="sm" 
                    className="h-6 px-2 text-xs bg-teal-600 hover:bg-teal-700"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleBulkSendInvites();
                    }}
                    disabled={bulkActionLoading}
                    data-testid="inline-bulk-invite-btn"
                  >
                    <Send className="h-3 w-3 mr-1" />
                    Send All ({selectedWaitlistIds.length})
                  </Button>
                )}
              </div>
            )}
            
            {displayWaitlist.map((entry, idx) => (
              <div 
                key={entry.id || idx} 
                className="flex items-center justify-between bg-white border border-teal-100 rounded-lg p-2 hover:border-teal-300 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={selectedWaitlistIds.includes(entry.id || entry.email)}
                    onCheckedChange={() => toggleWaitlistSelection(entry.id || entry.email)}
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`inline-waitlist-checkbox-${idx}`}
                  />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      openDetailDrawer('waitlist', entry);
                    }}
                    className="text-left hover:text-teal-600 cursor-pointer"
                    data-testid={`inline-waitlist-name-${idx}`}
                  >
                    <p className="text-sm font-medium">{entry.name || entry.email?.split('@')[0]}</p>
                    <p className="text-xs text-gray-500">{entry.email}</p>
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  {entry.referral_code && (
                    <Badge className="text-xs bg-teal-50 text-teal-700 mr-1">{entry.referrals || 0} refs</Badge>
                  )}
                  <Button 
                    size="sm" 
                    className="h-7 px-2 text-xs bg-teal-600 hover:bg-teal-700"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSendWaitlistInvite(entry);
                    }}
                    data-testid={`inline-invite-btn-${idx}`}
                  >
                    <Send className="h-3 w-3 mr-1" />
                    Invite
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Inline Bio-Age Scan Control Panel
  const InlineBioScanControlPanel = () => {
    const pendingScans = bioScans.filter(s => !s.results_sent);
    const displayScans = pendingScans.slice(0, 5);
    
    return (
      <div className="mt-4 pt-4 border-t border-blue-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TestTube className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800">Pending Results</span>
            {pendingScans.length > 0 && (
              <Badge className="bg-yellow-100 text-yellow-700 text-xs">{pendingScans.length}</Badge>
            )}
          </div>
          {bioScans.length > 5 && (
            <Button 
              size="sm" 
              variant="ghost" 
              className="text-xs text-blue-600"
              onClick={(e) => {
                e.stopPropagation();
                setActiveProgram('bioAgeScan');
                setActiveTab('control');
              }}
            >
              View All ({bioScans.length})
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
        
        {bioScansLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
          </div>
        ) : displayScans.length === 0 ? (
          <div className="text-center py-4 bg-blue-50/50 rounded-lg">
            <CheckSquare className="h-6 w-6 mx-auto text-green-500 mb-1" />
            <p className="text-xs text-gray-600">All results sent! No pending scans.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayScans.map((scan, idx) => (
              <div 
                key={scan.id || idx} 
                className="flex items-center justify-between bg-white border border-blue-100 rounded-lg p-2 hover:border-blue-300 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    openDetailDrawer('scan', scan);
                  }}
                  className="text-left hover:text-blue-600 cursor-pointer"
                  data-testid={`inline-scan-name-${idx}`}
                >
                  <p className="text-sm font-medium">{scan.name || scan.email?.split('@')[0] || 'Anonymous'}</p>
                  <p className="text-xs text-gray-500">{scan.email}</p>
                </button>
                <div className="flex items-center gap-2">
                  {scan.bio_age && (
                    <Badge className="text-xs bg-blue-50 text-blue-700">Age: {scan.bio_age}</Badge>
                  )}
                  <Button 
                    size="sm" 
                    className="h-7 px-2 text-xs bg-blue-600 hover:bg-blue-700"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (scan.email) {
                        window.location.href = `mailto:${scan.email}?subject=Your Bio-Age Scan Results`;
                      }
                    }}
                    data-testid={`inline-email-btn-${idx}`}
                  >
                    <Mail className="h-3 w-3 mr-1" />
                    Email
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Inline Shop Control Panel - shows products needing attention WITH QUICK ACTIONS
  const InlineShopControlPanel = () => {
    const lowStockProducts = products.filter(p => (p.stock || 0) <= 5);
    const displayProducts = lowStockProducts.slice(0, 5);
    
    return (
      <div className="mt-4 pt-4 border-t border-orange-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-orange-600" />
            <span className="text-sm font-medium text-orange-800">Low Stock Alert</span>
            {lowStockProducts.length > 0 && (
              <Badge className="bg-red-100 text-red-700 text-xs">{lowStockProducts.length}</Badge>
            )}
          </div>
          {products.length > 0 && (
            <Button 
              size="sm" 
              variant="ghost" 
              className="text-xs text-orange-600"
              onClick={(e) => {
                e.stopPropagation();
                setActiveProgram('shop');
                setActiveTab('control');
              }}
            >
              All Products ({products.length})
              <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
        
        {productsLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-orange-600"></div>
          </div>
        ) : displayProducts.length === 0 ? (
          <div className="text-center py-4 bg-orange-50/50 rounded-lg">
            <CheckSquare className="h-6 w-6 mx-auto text-green-500 mb-1" />
            <p className="text-xs text-gray-600">All products well stocked!</p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayProducts.map((product, idx) => {
              const productId = product.id || product._id;
              const isEditingPrice = editingProductPrice === productId;
              
              return (
                <div 
                  key={productId || idx} 
                  className="flex items-center justify-between bg-white border border-orange-100 rounded-lg p-2 hover:border-orange-300 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      openDetailDrawer('product', product);
                    }}
                    className="text-left hover:text-orange-600 cursor-pointer flex-1 min-w-0"
                    data-testid={`inline-product-name-${idx}`}
                  >
                    <p className="text-sm font-medium truncate">{product.name || 'Unnamed Product'}</p>
                    {isEditingPrice ? (
                      <div className="flex items-center gap-1 mt-1" onClick={(e) => e.stopPropagation()}>
                        <span className="text-xs text-gray-500">$</span>
                        <Input
                          type="number"
                          value={tempPrice}
                          onChange={(e) => setTempPrice(e.target.value)}
                          className="h-6 w-20 text-xs px-1"
                          step="0.01"
                          min="0"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleQuickPriceEdit(productId);
                            if (e.key === 'Escape') { setEditingProductPrice(null); setTempPrice(''); }
                          }}
                        />
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleQuickPriceEdit(productId); }}
                          className="text-green-600 hover:text-green-700"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button 
                          onClick={(e) => { e.stopPropagation(); setEditingProductPrice(null); setTempPrice(''); }}
                          className="text-red-600 hover:text-red-700"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-500">${product.price?.toFixed(2) || '0.00'}</p>
                    )}
                  </button>
                  
                  <div className="flex items-center gap-1 ml-2">
                    {/* Stock Badge */}
                    <Badge className={`text-xs ${(product.stock || 0) === 0 ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                      {product.stock || 0} left
                    </Badge>
                    
                    {/* Toggle Stock Button */}
                    <Button 
                      size="sm" 
                      variant="ghost"
                      className={`h-7 w-7 p-0 ${(product.stock || 0) === 0 ? 'text-green-600 hover:bg-green-50' : 'text-red-600 hover:bg-red-50'}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleQuickToggleStock(productId, product.stock || 0);
                      }}
                      title={(product.stock || 0) === 0 ? 'Mark In Stock' : 'Mark Sold Out'}
                      data-testid={`toggle-stock-btn-${idx}`}
                    >
                      {(product.stock || 0) === 0 ? (
                        <CheckSquare className="h-4 w-4" />
                      ) : (
                        <X className="h-4 w-4" />
                      )}
                    </Button>
                    
                    {/* Edit Price Button */}
                    <Button 
                      size="sm" 
                      variant="ghost"
                      className="h-7 w-7 p-0 text-orange-600 hover:bg-orange-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingProductPrice(productId);
                        setTempPrice(product.price?.toString() || '0');
                      }}
                      title="Edit Price"
                      data-testid={`edit-price-btn-${idx}`}
                    >
                      <DollarSign className="h-4 w-4" />
                    </Button>
                    
                    {/* Full Edit Button */}
                    <Button 
                      size="sm" 
                      variant="outline"
                      className="h-7 px-2 text-xs border-orange-300 text-orange-700 hover:bg-orange-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        openDetailDrawer('product', product);
                      }}
                      data-testid={`inline-edit-product-btn-${idx}`}
                    >
                      <Edit3 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };
  // ============ END INLINE CONTROL PANEL COMPONENTS ============

  // ============ QUICK ACTIONS WIDGET ============
  // Calculate pending items for "Daily To-Do" bar
  const pendingPartnerCount = partners.filter(p => p.status === 'pending').length;
  const waitlistCount = waitlist.length;
  const pendingScansCount = bioScans.filter(s => !s.results_sent).length;
  const lowStockCount = products.filter(p => (p.stock || 0) <= 5).length;
  
  // Check for scans older than 48 hours without results (urgent alert)
  const urgentScans = bioScans.filter(s => {
    if (s.results_sent) return false;
    if (!s.created_at) return false;
    const createdDate = new Date(s.created_at);
    const hoursSinceCreation = (Date.now() - createdDate.getTime()) / (1000 * 60 * 60);
    return hoursSinceCreation > 48;
  });
  
  // Scroll to section function for anchor links
  const scrollToSection = (sectionId) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Add highlight effect
      element.classList.add('ring-4', 'ring-yellow-400', 'ring-opacity-75');
      setTimeout(() => {
        element.classList.remove('ring-4', 'ring-yellow-400', 'ring-opacity-75');
      }, 2000);
    }
  };
  // ============ END QUICK ACTIONS WIDGET ============

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#F8A5B8]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-[#2D2A2E]">Programs Manager</h2>
          <p className="text-sm text-[#5A5A5A]">Configure, track, and share your marketing programs</p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline"
            onClick={() => window.location.reload()}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button 
            onClick={saveSettings} 
            disabled={saving}
            className="bg-gradient-to-r from-[#F8A5B8] to-[#E88DA0] hover:from-[#E88DA0] hover:to-[#D77A8D] text-white"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save All Changes
          </Button>
        </div>
      </div>

      {/* Quick Actions - Daily To-Do Bar */}
      {(pendingPartnerCount > 0 || waitlistCount > 0 || pendingScansCount > 0 || urgentScans.length > 0 || lowStockCount > 0) && (
        <Card className="bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200" data-testid="quick-actions-bar">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-amber-600" />
                <h3 className="font-semibold text-amber-800">Quick Actions - Your To-Do List</h3>
              </div>
              <div className="flex items-center gap-3">
                {/* WebSocket Connection Status */}
                <div 
                  className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
                    isConnected 
                      ? 'bg-green-100 text-green-700' 
                      : 'bg-gray-100 text-gray-500'
                  }`}
                  title={isConnected ? 'Real-time updates active' : 'Connecting to real-time updates...'}
                  data-testid="websocket-status"
                >
                  {isConnected ? (
                    <>
                      <Wifi className="h-3 w-3" />
                      <span>Live</span>
                    </>
                  ) : (
                    <>
                      <WifiOff className="h-3 w-3" />
                      <span>Offline</span>
                    </>
                  )}
                </div>
                {/* Timestamp */}
                <div className="flex items-center gap-1.5 text-xs text-amber-700" data-testid="sync-timestamp">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Last updated: {getRelativeTime(lastSyncTime)}</span>
                </div>
                {/* Refresh Button */}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 text-amber-700 hover:bg-amber-100"
                  onClick={refreshAllData}
                  disabled={partnersLoading || waitlistLoading || bioScansLoading || productsLoading}
                  data-testid="refresh-data-btn"
                >
                  <RefreshCw className={`h-3.5 w-3.5 mr-1 ${(partnersLoading || waitlistLoading || bioScansLoading || productsLoading) ? 'animate-spin' : ''}`} />
                  Sync
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              {/* Urgent: Scans older than 48 hours */}
              {urgentScans.length > 0 && (
                <button
                  onClick={() => scrollToSection('bioscan-section')}
                  className="flex items-center gap-2 bg-red-100 border border-red-300 text-red-800 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors animate-pulse"
                  data-testid="urgent-scans-action"
                >
                  <AlertCircle className="h-4 w-4" />
                  <span className="font-semibold">{urgentScans.length} scan{urgentScans.length > 1 ? 's' : ''} waiting 48+ hours!</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
              
              {/* Pending Partners */}
              {pendingPartnerCount > 0 && (
                <button
                  onClick={() => scrollToSection('partner-section')}
                  className="flex items-center gap-2 bg-purple-100 border border-purple-300 text-purple-800 px-4 py-2 rounded-lg hover:bg-purple-200 transition-colors"
                  data-testid="pending-partners-action"
                >
                  <Users className="h-4 w-4" />
                  <span>{pendingPartnerCount} partner{pendingPartnerCount > 1 ? 's' : ''} awaiting approval</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
              
              {/* Waitlist to Invite */}
              {waitlistCount > 0 && (
                <button
                  onClick={() => scrollToSection('waitlist-section')}
                  className="flex items-center gap-2 bg-teal-100 border border-teal-300 text-teal-800 px-4 py-2 rounded-lg hover:bg-teal-200 transition-colors"
                  data-testid="waitlist-action"
                >
                  <Bell className="h-4 w-4" />
                  <span>{waitlistCount} on waitlist to invite</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
              
              {/* Pending Scans (non-urgent) */}
              {pendingScansCount > 0 && urgentScans.length === 0 && (
                <button
                  onClick={() => scrollToSection('bioscan-section')}
                  className="flex items-center gap-2 bg-blue-100 border border-blue-300 text-blue-800 px-4 py-2 rounded-lg hover:bg-blue-200 transition-colors"
                  data-testid="pending-scans-action"
                >
                  <TestTube className="h-4 w-4" />
                  <span>{pendingScansCount} scan{pendingScansCount > 1 ? 's' : ''} pending results</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
              
              {/* Low Stock Alert */}
              {lowStockCount > 0 && (
                <button
                  onClick={() => scrollToSection('shop-section')}
                  className="flex items-center gap-2 bg-orange-100 border border-orange-300 text-orange-800 px-4 py-2 rounded-lg hover:bg-orange-200 transition-colors"
                  data-testid="low-stock-action"
                >
                  <Package className="h-4 w-4" />
                  <span>{lowStockCount} product{lowStockCount > 1 ? 's' : ''} low on stock</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* All Clear Message */}
      {pendingPartnerCount === 0 && waitlistCount === 0 && pendingScansCount === 0 && lowStockCount === 0 && (
        <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-full">
                  <Check className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-green-800">All Caught Up!</h3>
                  <p className="text-sm text-green-600">No pending actions - your programs are running smoothly.</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {/* Timestamp */}
                <div className="flex items-center gap-1.5 text-xs text-green-700" data-testid="sync-timestamp-clear">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Last updated: {getRelativeTime(lastSyncTime)}</span>
                </div>
                {/* Refresh Button */}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 text-green-700 hover:bg-green-100"
                  onClick={refreshAllData}
                  disabled={partnersLoading || waitlistLoading || bioScansLoading || productsLoading}
                  data-testid="refresh-data-btn-clear"
                >
                  <RefreshCw className={`h-3.5 w-3.5 mr-1 ${(partnersLoading || waitlistLoading || bioScansLoading || productsLoading) ? 'animate-spin' : ''}`} />
                  Sync
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Overall Stats */}
      <Card className="bg-gradient-to-r from-purple-50 to-pink-50">
        <CardContent className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-purple-700">{analytics.influencer.activeUsers + analytics.founder.totalMembers}</p>
              <p className="text-xs text-gray-600">Active Members</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-pink-700">{analytics.founder.pointsIssued.toLocaleString()}</p>
              <p className="text-xs text-gray-600">Points Issued</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-700">${analytics.influencer.earnings.toLocaleString()}</p>
              <p className="text-xs text-gray-600">Total Earnings</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-700">{analytics.quiz.completions + analytics.bioAgeScan.scansCompleted}</p>
              <p className="text-xs text-gray-600">Engagements</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-orange-700">{Math.round((analytics.quiz.conversionRate + analytics.comparison.addToCartRate) / 2)}%</p>
              <p className="text-xs text-gray-600">Avg Conversion</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Program Cards Grid - Now with Inline Control Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Partner Program Card - WITH INLINE CONTROL PANEL */}
        <Card 
          id="partner-section"
          className={`transition-all hover:shadow-md ${
            activeProgram === 'influencer' ? 'ring-2 ring-purple-400' : ''
          } ${!programs.influencer?.enabled ? 'opacity-60' : ''}`}
          data-testid="partner-program-card"
        >
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-lg ${getColorClasses('purple', programs.influencer?.enabled)}`}>
                  <Users className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-[#2D2A2E]">Partner Program</h3>
                  <p className="text-xs text-[#5A5A5A]">Manage affiliate applications & commissions</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => loadPageContent('influencer')}
                  title="Edit Page Content"
                >
                  <Edit3 className="h-4 w-4 text-blue-500" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => openShareModal('influencer')}
                  title="Share Program"
                >
                  <Share2 className="h-4 w-4 text-gray-500" />
                </Button>
                <Switch
                  checked={programs.influencer?.enabled}
                  onCheckedChange={(checked) => updateProgram('influencer', 'enabled', checked)}
                />
              </div>
            </div>
            
            {/* Quick Stats Row */}
            <div className="mt-4 grid grid-cols-4 gap-3">
              <div className="text-center p-2 bg-yellow-50 rounded-lg">
                <p className="text-xl font-bold text-yellow-700">{partnerStats.pending}</p>
                <p className="text-[10px] text-gray-600">Pending</p>
              </div>
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <p className="text-xl font-bold text-green-700">{partnerStats.approved}</p>
                <p className="text-[10px] text-gray-600">Approved</p>
              </div>
              <div className="text-center p-2 bg-blue-50 rounded-lg">
                <p className="text-xl font-bold text-blue-700">{partnerStats.active}</p>
                <p className="text-[10px] text-gray-600">Active</p>
              </div>
              <div className="text-center p-2 bg-purple-50 rounded-lg">
                <p className="text-xl font-bold text-purple-700">{partnerStats.total}</p>
                <p className="text-[10px] text-gray-600">Total</p>
              </div>
            </div>
            
            {/* Inline Control Panel - Always visible */}
            <InlinePartnerControlPanel />
            
            {/* Footer Actions */}
            <div className="flex items-center justify-between mt-4 pt-3 border-t">
              <Badge 
                variant={programs.influencer?.enabled ? "default" : "secondary"} 
                className={`text-xs ${programs.influencer?.enabled ? 'bg-green-100 text-green-700' : ''}`}
              >
                {programs.influencer?.enabled ? 'Active' : 'Disabled'}
              </Badge>
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => {
                  setActiveProgram('influencer');
                  setActiveTab('settings');
                }}
              >
                <Settings className="h-3 w-3 mr-1" />
                Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Waitlist Card - WITH INLINE CONTROL PANEL */}
        <Card 
          id="waitlist-section"
          className={`transition-all hover:shadow-md ${
            activeProgram === 'waitlist' ? 'ring-2 ring-teal-400' : ''
          } ${!programs.waitlist?.enabled ? 'opacity-60' : ''}`}
          data-testid="waitlist-program-card"
        >
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-lg ${getColorClasses('teal', programs.waitlist?.enabled !== false)}`}>
                  <Bell className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-[#2D2A2E]">Waitlist</h3>
                  <p className="text-xs text-[#5A5A5A]">Early access signups & invite management</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => loadPageContent('waitlist')}
                  title="Edit Page Content"
                >
                  <Edit3 className="h-4 w-4 text-blue-500" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => openShareModal('waitlist')}
                  title="Share Program"
                >
                  <Share2 className="h-4 w-4 text-gray-500" />
                </Button>
              </div>
            </div>
            
            {/* Quick Stats Row */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="text-center p-2 bg-teal-50 rounded-lg">
                <p className="text-xl font-bold text-teal-700">{waitlist.length}</p>
                <p className="text-[10px] text-gray-600">Total Signups</p>
              </div>
              <div className="text-center p-2 bg-purple-50 rounded-lg">
                <p className="text-xl font-bold text-purple-700">{waitlist.filter(w => w.referrals > 0).length}</p>
                <p className="text-[10px] text-gray-600">With Referrals</p>
              </div>
              <div className="text-center p-2 bg-yellow-50 rounded-lg">
                <p className="text-xl font-bold text-yellow-700">{waitlist.filter(w => w.is_vip).length}</p>
                <p className="text-[10px] text-gray-600">VIP</p>
              </div>
            </div>
            
            {/* Inline Control Panel */}
            <InlineWaitlistControlPanel />
            
            {/* Footer Actions */}
            <div className="flex items-center justify-between mt-4 pt-3 border-t">
              <Badge className="text-xs bg-green-100 text-green-700">Active</Badge>
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => {
                  setActiveProgram('waitlist');
                  setActiveTab('settings');
                }}
              >
                <Settings className="h-3 w-3 mr-1" />
                Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Bio-Age Scan Card - WITH INLINE CONTROL PANEL */}
        <Card 
          id="bioscan-section"
          className={`transition-all hover:shadow-md ${
            activeProgram === 'bioAgeScan' ? 'ring-2 ring-blue-400' : ''
          } ${!programs.bioAgeScan?.enabled ? 'opacity-60' : ''}`}
          data-testid="bioscan-program-card"
        >
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-lg ${getColorClasses('blue', programs.bioAgeScan?.enabled)}`}>
                  <TestTube className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-[#2D2A2E]">Bio-Age Scan</h3>
                  <p className="text-xs text-[#5A5A5A]">AI skin analysis & result delivery</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => loadPageContent('bioAgeScan')}
                  title="Edit Page Content"
                >
                  <Edit3 className="h-4 w-4 text-blue-500" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => openShareModal('bioAgeScan')}
                  title="Share Program"
                >
                  <Share2 className="h-4 w-4 text-gray-500" />
                </Button>
                <Switch
                  checked={programs.bioAgeScan?.enabled}
                  onCheckedChange={(checked) => updateProgram('bioAgeScan', 'enabled', checked)}
                />
              </div>
            </div>
            
            {/* Quick Stats Row */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="text-center p-2 bg-blue-50 rounded-lg">
                <p className="text-xl font-bold text-blue-700">{bioScans.length}</p>
                <p className="text-[10px] text-gray-600">Total Scans</p>
              </div>
              <div className="text-center p-2 bg-yellow-50 rounded-lg">
                <p className="text-xl font-bold text-yellow-700">{bioScans.filter(s => !s.results_sent).length}</p>
                <p className="text-[10px] text-gray-600">Pending</p>
              </div>
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <p className="text-xl font-bold text-green-700">{bioScans.filter(s => s.results_sent).length}</p>
                <p className="text-[10px] text-gray-600">Sent</p>
              </div>
            </div>
            
            {/* Inline Control Panel */}
            <InlineBioScanControlPanel />
            
            {/* Footer Actions */}
            <div className="flex items-center justify-between mt-4 pt-3 border-t">
              <Badge 
                variant={programs.bioAgeScan?.enabled ? "default" : "secondary"} 
                className={`text-xs ${programs.bioAgeScan?.enabled ? 'bg-green-100 text-green-700' : ''}`}
              >
                {programs.bioAgeScan?.enabled ? 'Active' : 'Disabled'}
              </Badge>
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => {
                  setActiveProgram('bioAgeScan');
                  setActiveTab('settings');
                }}
              >
                <Settings className="h-3 w-3 mr-1" />
                Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Shop Card - WITH INLINE CONTROL PANEL */}
        <Card 
          id="shop-section"
          className={`transition-all hover:shadow-md ${
            activeProgram === 'shop' ? 'ring-2 ring-orange-400' : ''
          } ${!programs.shop?.enabled ? 'opacity-60' : ''}`}
          data-testid="shop-program-card"
        >
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-lg ${getColorClasses('orange', programs.shop?.enabled !== false)}`}>
                  <ShoppingBag className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-[#2D2A2E]">Shop</h3>
                  <p className="text-xs text-[#5A5A5A]">Product inventory & stock management</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => loadPageContent('shop')}
                  title="Edit Page Content"
                >
                  <Edit3 className="h-4 w-4 text-blue-500" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0"
                  onClick={() => openShareModal('shop')}
                  title="Share Program"
                >
                  <Share2 className="h-4 w-4 text-gray-500" />
                </Button>
              </div>
            </div>
            
            {/* Quick Stats Row */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="text-center p-2 bg-orange-50 rounded-lg">
                <p className="text-xl font-bold text-orange-700">{products.length}</p>
                <p className="text-[10px] text-gray-600">Products</p>
              </div>
              <div className="text-center p-2 bg-red-50 rounded-lg">
                <p className="text-xl font-bold text-red-700">{products.filter(p => (p.stock || 0) === 0).length}</p>
                <p className="text-[10px] text-gray-600">Out of Stock</p>
              </div>
              <div className="text-center p-2 bg-yellow-50 rounded-lg">
                <p className="text-xl font-bold text-yellow-700">{products.filter(p => (p.stock || 0) > 0 && (p.stock || 0) <= 5).length}</p>
                <p className="text-[10px] text-gray-600">Low Stock</p>
              </div>
            </div>
            
            {/* Inline Control Panel */}
            <InlineShopControlPanel />
            
            {/* Footer Actions */}
            <div className="flex items-center justify-between mt-4 pt-3 border-t">
              <Badge className="text-xs bg-green-100 text-green-700">Active</Badge>
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => {
                  setActiveProgram('shop');
                  setActiveTab('settings');
                }}
              >
                <Settings className="h-3 w-3 mr-1" />
                Settings
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Other Programs - Compact Cards (Founder, Quiz, Comparison) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {programCards.filter(p => ['founder', 'quiz', 'comparison'].includes(p.key)).map(program => {
          const Icon = program.icon;
          const enabled = programs[program.key]?.enabled;
          return (
            <Card 
              key={program.key}
              className={`cursor-pointer transition-all hover:shadow-md ${
                activeProgram === program.key ? 'ring-2 ring-[#F8A5B8]' : ''
              } ${!enabled ? 'opacity-60' : ''}`}
              onClick={() => setActiveProgram(program.key)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className={`p-2 rounded-lg ${getColorClasses(program.color, enabled)}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex items-center gap-2">
                    {['quiz', 'comparison'].includes(program.key) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          loadPageContent(program.key);
                        }}
                        title="Edit Page Content"
                      >
                        <Edit3 className="h-4 w-4 text-blue-500" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        openShareModal(program.key);
                      }}
                      title="Share Program"
                    >
                      <Share2 className="h-4 w-4 text-gray-500" />
                    </Button>
                    <Switch
                      checked={enabled}
                      onCheckedChange={(checked) => updateProgram(program.key, 'enabled', checked)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                </div>
                <h3 className="font-medium mt-3 text-[#2D2A2E]">{program.title}</h3>
                <p className="text-xs text-[#5A5A5A] mt-1">{program.description}</p>
                
                {/* Quick Stats */}
                <div className="mt-3 pt-3 border-t grid grid-cols-2 gap-2">
                  {program.key === 'founder' && (
                    <>
                      <div className="text-center">
                        <p className="text-lg font-bold text-yellow-600">{program.stats.totalMembers}</p>
                        <p className="text-[10px] text-gray-500">Members</p>
                      </div>
                      <div className="text-center">
                        <p className="text-lg font-bold text-orange-600">{program.stats.pointsIssued}</p>
                        <p className="text-[10px] text-gray-500">Points</p>
                      </div>
                    </>
                  )}
                  {program.key === 'quiz' && (
                    <>
                      <div className="text-center">
                        <p className="text-lg font-bold text-pink-600">{program.stats.completions}</p>
                        <p className="text-[10px] text-gray-500">Completions</p>
                      </div>
                      <div className="text-center">
                        <p className="text-lg font-bold text-blue-600">{program.stats.conversionRate}%</p>
                        <p className="text-[10px] text-gray-500">Conversion</p>
                      </div>
                    </>
                  )}
                  {program.key === 'comparison' && (
                    <>
                      <div className="text-center">
                        <p className="text-lg font-bold text-green-600">{program.stats.comparisons}</p>
                        <p className="text-[10px] text-gray-500">Uses</p>
                      </div>
                      <div className="text-center">
                        <p className="text-lg font-bold text-emerald-600">{program.stats.addToCartRate}%</p>
                        <p className="text-[10px] text-gray-500">Add to Cart</p>
                      </div>
                    </>
                  )}
                </div>
                
                <div className="flex items-center justify-between mt-3">
                  <Badge 
                    variant={enabled ? "default" : "secondary"} 
                    className={`text-xs ${enabled ? 'bg-green-100 text-green-700' : ''}`}
                  >
                    {enabled ? 'Active' : 'Disabled'}
                  </Badge>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-xs text-[#F8A5B8] hover:text-[#E88DA0]"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveProgram(program.key);
                      setActiveTab('settings');
                    }}
                  >
                    <Edit3 className="h-3 w-3 mr-1" />
                    Edit
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Selected Program Details */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              {React.createElement(programCards.find(p => p.key === activeProgram)?.icon || Settings, { className: "h-5 w-5 text-[#F8A5B8]" })}
              {programCards.find(p => p.key === activeProgram)?.title} - Details
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => openShareModal(activeProgram)}
            >
              <Share2 className="h-4 w-4 mr-2" />
              Share & Track
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="settings" className="flex items-center gap-1">
                <Settings className="h-4 w-4" />
                Settings
              </TabsTrigger>
              <TabsTrigger value="analytics" className="flex items-center gap-1">
                <BarChart3 className="h-4 w-4" />
                Analytics
              </TabsTrigger>
              <TabsTrigger value="tracking" className="flex items-center gap-1">
                <Eye className="h-4 w-4" />
                Tracking
              </TabsTrigger>
              <TabsTrigger value="points" className="flex items-center gap-1">
                <Coins className="h-4 w-4" />
                Points
              </TabsTrigger>
              <TabsTrigger value="control" className="flex items-center gap-1">
                <ClipboardList className="h-4 w-4" />
                Full List
              </TabsTrigger>
            </TabsList>

            {/* FULL LIST TAB - View All Items (moved from inline panels) */}
            <TabsContent value="control">
              {/* Bio-Age Scan Full List */}
              {activeProgram === 'bioAgeScan' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-lg">All Bio-Age Scan Submissions</h4>
                      <p className="text-sm text-gray-500">Complete list - review submissions, upload results, email clients</p>
                    </div>
                    <div className="flex gap-2">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <Input 
                          placeholder="Search by email..." 
                          value={controlPanelSearch}
                          onChange={(e) => setControlPanelSearch(e.target.value)}
                          className="pl-9 w-64"
                        />
                      </div>
                      <Button variant="outline" size="sm" onClick={fetchBioScans}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${bioScansLoading ? 'animate-spin' : ''}`} />
                        Refresh
                      </Button>
                    </div>
                  </div>

                  {bioScansLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    </div>
                  ) : bioScans.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border">
                      <TestTube className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                      <p className="text-gray-600 font-medium">No Bio-Age Scans Yet</p>
                      <p className="text-sm text-gray-500 mt-1">Scans will appear here when users complete them</p>
                    </div>
                  ) : (
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left">User</th>
                            <th className="px-4 py-3 text-left">Contact</th>
                            <th className="px-4 py-3 text-center">Bio-Age</th>
                            <th className="px-4 py-3 text-center">Date</th>
                            <th className="px-4 py-3 text-center">Status</th>
                            <th className="px-4 py-3 text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {bioScans
                            .filter(scan => !controlPanelSearch || 
                              scan.email?.toLowerCase().includes(controlPanelSearch.toLowerCase()) ||
                              scan.name?.toLowerCase().includes(controlPanelSearch.toLowerCase()))
                            .slice(0, 50)
                            .map((scan, idx) => (
                            <tr key={scan.id || idx} className="border-t hover:bg-gray-50">
                              <td className="px-4 py-3">
                                <button 
                                  onClick={() => openDetailDrawer('scan', scan)}
                                  className="text-left hover:text-blue-600 font-medium cursor-pointer"
                                  data-testid={`scan-name-${idx}`}
                                >
                                  {scan.name || scan.email?.split('@')[0] || 'Anonymous'}
                                </button>
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex flex-col">
                                  {scan.email && <span className="text-xs text-gray-600">{scan.email}</span>}
                                  {scan.phone && <span className="text-xs text-gray-500">{scan.phone}</span>}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-center">
                                {scan.bio_age || scan.bioAge || '--'}
                              </td>
                              <td className="px-4 py-3 text-center text-xs text-gray-500">
                                {scan.created_at ? new Date(scan.created_at).toLocaleDateString() : '--'}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <Badge 
                                  variant={scan.results_sent ? 'default' : 'secondary'}
                                  className={scan.results_sent ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}
                                >
                                  {scan.results_sent ? 'Results Sent' : 'Pending'}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex justify-end gap-1">
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    onClick={() => openDetailDrawer('scan', scan)}
                                    title="View Details"
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    className="text-blue-600 hover:bg-blue-50"
                                    onClick={() => {
                                      if (scan.email) {
                                        window.location.href = `mailto:${scan.email}?subject=Your Bio-Age Scan Results`;
                                      }
                                    }}
                                    title="Email Client"
                                  >
                                    <Mail className="h-4 w-4" />
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Partner/Influencer Control Panel */}
              {activeProgram === 'influencer' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-lg">Partner Applications</h4>
                      <p className="text-sm text-gray-500">Review and approve partner/influencer applications</p>
                    </div>
                    <div className="flex gap-2">
                      <select 
                        value={controlPanelFilter}
                        onChange={(e) => setControlPanelFilter(e.target.value)}
                        className="px-3 py-2 border rounded-md text-sm"
                      >
                        <option value="all">All ({partnerStats.total})</option>
                        <option value="pending">Pending ({partnerStats.pending})</option>
                        <option value="approved">Approved ({partnerStats.approved})</option>
                        <option value="active">Active ({partnerStats.active})</option>
                      </select>
                      <Button variant="outline" size="sm" onClick={fetchPartners}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${partnersLoading ? 'animate-spin' : ''}`} />
                        Refresh
                      </Button>
                    </div>
                  </div>

                  {/* Quick Stats */}
                  <div className="grid grid-cols-4 gap-4">
                    <Card className="bg-yellow-50 border-yellow-200">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-yellow-700">{partnerStats.pending}</p>
                        <p className="text-xs text-gray-600">Pending Review</p>
                      </CardContent>
                    </Card>
                    <Card className="bg-green-50 border-green-200">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-green-700">{partnerStats.approved}</p>
                        <p className="text-xs text-gray-600">Approved</p>
                      </CardContent>
                    </Card>
                    <Card className="bg-blue-50 border-blue-200">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-blue-700">{partnerStats.active}</p>
                        <p className="text-xs text-gray-600">Active</p>
                      </CardContent>
                    </Card>
                    <Card className="bg-purple-50 border-purple-200">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-purple-700">{partnerStats.total}</p>
                        <p className="text-xs text-gray-600">Total</p>
                      </CardContent>
                    </Card>
                  </div>

                  {partnersLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
                    </div>
                  ) : partners.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border">
                      <Users className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                      <p className="text-gray-600 font-medium">No Partner Applications</p>
                      <p className="text-sm text-gray-500 mt-1">Applications will appear here when users apply</p>
                    </div>
                  ) : (
                    <>
                      {/* Bulk Action Bar */}
                      {selectedPartnerIds.length > 0 && (
                        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <CheckSquare className="h-5 w-5 text-purple-600" />
                            <span className="font-medium text-purple-800">
                              {selectedPartnerIds.length} selected
                            </span>
                          </div>
                          <div className="flex gap-2">
                            <Button 
                              size="sm" 
                              className="bg-green-600 hover:bg-green-700"
                              onClick={handleBulkApprovePartners}
                              disabled={bulkActionLoading}
                              data-testid="bulk-approve-btn"
                            >
                              {bulkActionLoading ? (
                                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                              ) : (
                                <UserCheck className="h-4 w-4 mr-2" />
                              )}
                              Approve All
                            </Button>
                            <Button 
                              size="sm" 
                              variant="destructive"
                              onClick={handleBulkRejectPartners}
                              disabled={bulkActionLoading}
                              data-testid="bulk-reject-btn"
                            >
                              <UserX className="h-4 w-4 mr-2" />
                              Reject All
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => setSelectedPartnerIds([])}
                            >
                              <X className="h-4 w-4 mr-2" />
                              Clear
                            </Button>
                          </div>
                        </div>
                      )}
                      
                      <div className="border rounded-lg overflow-hidden">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-3 py-3 text-center w-12">
                                <Checkbox 
                                  checked={
                                    partners.filter(p => p.status === 'pending').length > 0 &&
                                    selectedPartnerIds.length === partners.filter(p => p.status === 'pending').length
                                  }
                                  onCheckedChange={() => toggleAllPartners(partners)}
                                  data-testid="select-all-partners"
                                />
                              </th>
                              <th className="px-4 py-3 text-left">Applicant</th>
                              <th className="px-4 py-3 text-left">Social</th>
                              <th className="px-4 py-3 text-center">Followers</th>
                              <th className="px-4 py-3 text-center">Status</th>
                              <th className="px-4 py-3 text-center">Applied</th>
                              <th className="px-4 py-3 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {partners
                              .filter(p => controlPanelFilter === 'all' || p.status === controlPanelFilter)
                              .slice(0, 50)
                              .map((partner, idx) => (
                              <tr key={partner.id || idx} className={`border-t hover:bg-gray-50 ${selectedPartnerIds.includes(partner.id) ? 'bg-purple-50' : ''}`}>
                                <td className="px-3 py-3 text-center">
                                  {partner.status === 'pending' && (
                                    <Checkbox 
                                      checked={selectedPartnerIds.includes(partner.id)}
                                      onCheckedChange={() => togglePartnerSelection(partner.id)}
                                      data-testid={`select-partner-${idx}`}
                                    />
                                  )}
                                </td>
                                <td className="px-4 py-3">
                                  <button 
                                    onClick={() => openDetailDrawer('partner', partner)}
                                    className="text-left hover:text-purple-600 font-medium cursor-pointer"
                                  data-testid={`partner-name-${idx}`}
                                >
                                  {partner.full_name || partner.email?.split('@')[0]}
                                </button>
                                <p className="text-xs text-gray-500">{partner.email}</p>
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex flex-col text-xs">
                                  {partner.instagram && <span>@{partner.instagram}</span>}
                                  {partner.tiktok && <span className="text-gray-500">TikTok: @{partner.tiktok}</span>}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-center">
                                {partner.follower_count?.toLocaleString() || '--'}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <Badge 
                                  variant={partner.status === 'approved' || partner.status === 'active' ? 'default' : 'secondary'}
                                  className={
                                    partner.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                                    partner.status === 'approved' ? 'bg-green-100 text-green-700' :
                                    partner.status === 'active' ? 'bg-blue-100 text-blue-700' :
                                    'bg-red-100 text-red-700'
                                  }
                                >
                                  {partner.status}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 text-center text-xs text-gray-500">
                                {partner.created_at ? new Date(partner.created_at).toLocaleDateString() : '--'}
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex justify-end gap-1">
                                  <Button 
                                    size="sm" 
                                    variant="ghost"
                                    onClick={() => openDetailDrawer('partner', partner)}
                                    title="View Profile"
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                  {partner.status === 'pending' && (
                                    <>
                                      <Button 
                                        size="sm" 
                                        variant="ghost"
                                        className="text-green-600 hover:bg-green-50"
                                        onClick={() => handleApprovePartner(partner.id)}
                                        title="Approve"
                                      >
                                        <UserCheck className="h-4 w-4" />
                                      </Button>
                                      <Button 
                                        size="sm" 
                                        variant="ghost"
                                        className="text-red-600 hover:bg-red-50"
                                        onClick={() => handleRejectPartner(partner.id)}
                                        title="Reject"
                                      >
                                        <UserX className="h-4 w-4" />
                                      </Button>
                                    </>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    </>
                  )}
                </div>
              )}

              {/* Waitlist Control Panel */}
              {activeProgram === 'waitlist' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-lg">Waitlist Members</h4>
                      <p className="text-sm text-gray-500">View waitlist, send invites, track referrals</p>
                    </div>
                    <div className="flex gap-2">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <Input 
                          placeholder="Search by email..." 
                          value={controlPanelSearch}
                          onChange={(e) => setControlPanelSearch(e.target.value)}
                          className="pl-9 w-64"
                        />
                      </div>
                      <Button variant="outline" size="sm" onClick={fetchWaitlist}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${waitlistLoading ? 'animate-spin' : ''}`} />
                        Refresh
                      </Button>
                    </div>
                  </div>

                  {waitlistLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600"></div>
                    </div>
                  ) : waitlist.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border">
                      <Bell className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                      <p className="text-gray-600 font-medium">No Waitlist Entries</p>
                      <p className="text-sm text-gray-500 mt-1">Users will appear here when they join the waitlist</p>
                    </div>
                  ) : (
                    <>
                      {/* Bulk Action Bar for Waitlist */}
                      {selectedWaitlistIds.length > 0 && (
                        <div className="bg-teal-50 border border-teal-200 rounded-lg p-3 flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <CheckSquare className="h-5 w-5 text-teal-600" />
                            <span className="font-medium text-teal-800">
                              {selectedWaitlistIds.length} selected
                            </span>
                          </div>
                          <div className="flex gap-2">
                            <Button 
                              size="sm" 
                              className="bg-teal-600 hover:bg-teal-700"
                              onClick={handleBulkSendInvites}
                              disabled={bulkActionLoading}
                              data-testid="bulk-send-invites-btn"
                            >
                              {bulkActionLoading ? (
                                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                              ) : (
                                <Send className="h-4 w-4 mr-2" />
                              )}
                              Send All Invites
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => setSelectedWaitlistIds([])}
                            >
                              <X className="h-4 w-4 mr-2" />
                              Clear
                            </Button>
                          </div>
                        </div>
                      )}
                      
                      <div className="border rounded-lg overflow-hidden">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-3 py-3 text-center w-12">
                                <Checkbox 
                                  checked={
                                    waitlist.length > 0 &&
                                    selectedWaitlistIds.length === waitlist.filter(w => 
                                      !controlPanelSearch || 
                                      w.email?.toLowerCase().includes(controlPanelSearch.toLowerCase()) ||
                                      w.name?.toLowerCase().includes(controlPanelSearch.toLowerCase())
                                    ).length
                                  }
                                  onCheckedChange={() => toggleAllWaitlist(
                                    waitlist.filter(w => 
                                      !controlPanelSearch || 
                                      w.email?.toLowerCase().includes(controlPanelSearch.toLowerCase()) ||
                                      w.name?.toLowerCase().includes(controlPanelSearch.toLowerCase())
                                    )
                                  )}
                                  data-testid="select-all-waitlist"
                                />
                              </th>
                              <th className="px-4 py-3 text-left">Member</th>
                              <th className="px-4 py-3 text-center">Referral Code</th>
                              <th className="px-4 py-3 text-center">Referrals</th>
                              <th className="px-4 py-3 text-center">VIP Status</th>
                              <th className="px-4 py-3 text-center">Joined</th>
                              <th className="px-4 py-3 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {waitlist
                              .filter(entry => !controlPanelSearch || 
                                entry.email?.toLowerCase().includes(controlPanelSearch.toLowerCase()) ||
                                entry.name?.toLowerCase().includes(controlPanelSearch.toLowerCase()))
                              .slice(0, 50)
                              .map((entry, idx) => (
                              <tr key={entry.id || idx} className={`border-t hover:bg-gray-50 ${selectedWaitlistIds.includes(entry.id || entry.email) ? 'bg-teal-50' : ''}`}>
                                <td className="px-3 py-3 text-center">
                                  <Checkbox 
                                    checked={selectedWaitlistIds.includes(entry.id || entry.email)}
                                    onCheckedChange={() => toggleWaitlistSelection(entry.id || entry.email)}
                                    data-testid={`select-waitlist-${idx}`}
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  <button 
                                    onClick={() => openDetailDrawer('waitlist', entry)}
                                    className="text-left hover:text-teal-600 font-medium cursor-pointer"
                                    data-testid={`waitlist-name-${idx}`}
                                  >
                                    {entry.name || entry.full_name || entry.email?.split('@')[0]}
                                  </button>
                                  <p className="text-xs text-gray-500">{entry.email}</p>
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {entry.referral_code && (
                                    <code className="bg-gray-100 px-2 py-1 rounded text-xs">{entry.referral_code}</code>
                                  )}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {entry.successful_referrals || entry.referral_count || 0}
                                </td>
                                <td className="px-4 py-3 text-center">
                                  {entry.voucher_unlocked ? (
                                    <Badge className="bg-purple-100 text-purple-700">VIP</Badge>
                                  ) : (
                                    <Badge variant="secondary">Standard</Badge>
                                  )}
                                </td>
                                <td className="px-4 py-3 text-center text-xs text-gray-500">
                                  {entry.created_at ? new Date(entry.created_at).toLocaleDateString() : '--'}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  <div className="flex justify-end gap-1">
                                    <Button 
                                      size="sm" 
                                      variant="ghost"
                                      onClick={() => openDetailDrawer('waitlist', entry)}
                                      title="View Details"
                                    >
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                    <Button 
                                      size="sm" 
                                      variant="ghost"
                                      className="text-teal-600 hover:bg-teal-50"
                                      onClick={() => handleSendWaitlistInvite(entry)}
                                      title="Send Invite"
                                    >
                                      <Send className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Shop Control Panel */}
              {activeProgram === 'shop' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-lg">Product Management</h4>
                      <p className="text-sm text-gray-500">Toggle stock, edit prices, manage products</p>
                    </div>
                    <div className="flex gap-2">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <Input 
                          placeholder="Search products..." 
                          value={controlPanelSearch}
                          onChange={(e) => setControlPanelSearch(e.target.value)}
                          className="pl-9 w-64"
                        />
                      </div>
                      <Button variant="outline" size="sm" onClick={fetchProducts}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${productsLoading ? 'animate-spin' : ''}`} />
                        Refresh
                      </Button>
                    </div>
                  </div>

                  {productsLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
                    </div>
                  ) : products.length === 0 ? (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border">
                      <Package className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                      <p className="text-gray-600 font-medium">No Products</p>
                      <p className="text-sm text-gray-500 mt-1">Products will appear here</p>
                    </div>
                  ) : (
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left">Product</th>
                            <th className="px-4 py-3 text-center">Price</th>
                            <th className="px-4 py-3 text-center">Stock</th>
                            <th className="px-4 py-3 text-center">Status</th>
                            <th className="px-4 py-3 text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {products
                            .filter(p => !controlPanelSearch || 
                              p.name?.toLowerCase().includes(controlPanelSearch.toLowerCase()) ||
                              p.title?.toLowerCase().includes(controlPanelSearch.toLowerCase()))
                            .slice(0, 50)
                            .map((product, idx) => (
                            <tr key={product.id || idx} className="border-t hover:bg-gray-50">
                              <td className="px-4 py-3">
                                <button 
                                  onClick={() => openDetailDrawer('product', product)}
                                  className="text-left hover:text-orange-600 font-medium cursor-pointer flex items-center gap-2"
                                  data-testid={`product-name-${idx}`}
                                >
                                  {product.image && (
                                    <img src={product.image} alt="" className="w-8 h-8 rounded object-cover" />
                                  )}
                                  {product.name || product.title}
                                </button>
                              </td>
                              <td className="px-4 py-3 text-center font-medium">
                                ${product.price?.toFixed(2) || '--'}
                              </td>
                              <td className="px-4 py-3 text-center">
                                {product.stock ?? product.inventory ?? '--'}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <Badge 
                                  variant={product.is_active !== false ? 'default' : 'secondary'}
                                  className={product.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}
                                >
                                  {product.is_active !== false ? 'Active' : 'Inactive'}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <Button 
                                  size="sm" 
                                  variant="ghost"
                                  onClick={() => openDetailDrawer('product', product)}
                                  title="Edit Product"
                                >
                                  <Edit3 className="h-4 w-4" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Generic Control Panel for other programs */}
              {!['bioAgeScan', 'influencer', 'waitlist', 'shop'].includes(activeProgram) && (
                <div className="text-center py-12 bg-gray-50 rounded-lg border">
                  <ClipboardList className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-600 font-medium">Control Panel</p>
                  <p className="text-sm text-gray-500 mt-1">Activity management for this program is available in Settings</p>
                </div>
              )}
            </TabsContent>

            {/* Settings Tab */}
            <TabsContent value="settings">
              {/* Influencer Program Settings */}
              {activeProgram === 'influencer' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Program Name</Label>
                      <Input
                        value={programs.influencer.program_name}
                        onChange={(e) => updateProgram('influencer', 'program_name', e.target.value)}
                        placeholder="Partner Program Name"
                      />
                    </div>
                    <div>
                      <Label>Cookie Duration (Days)</Label>
                      <Input
                        type="number"
                        value={programs.influencer.cookie_duration_days}
                        onChange={(e) => updateProgram('influencer', 'cookie_duration_days', parseInt(e.target.value))}
                      />
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-green-600" />
                      Commission Settings
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <Label>Commission Type</Label>
                        <select
                          value={programs.influencer.commission_type}
                          onChange={(e) => updateProgram('influencer', 'commission_type', e.target.value)}
                          className="w-full px-3 py-2 border rounded-md"
                        >
                          <option value="percentage">Percentage</option>
                          <option value="flat">Flat Amount</option>
                          <option value="tiered">Tiered</option>
                        </select>
                      </div>
                      <div>
                        <Label>Commission Rate (%)</Label>
                        <Input
                          type="number"
                          value={programs.influencer.commission_rate}
                          onChange={(e) => updateProgram('influencer', 'commission_rate', parseFloat(e.target.value))}
                        />
                      </div>
                      <div>
                        <Label>Min Payout ($)</Label>
                        <Input
                          type="number"
                          value={programs.influencer.min_payout_threshold}
                          onChange={(e) => updateProgram('influencer', 'min_payout_threshold', parseFloat(e.target.value))}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Coins className="h-4 w-4 text-yellow-600" />
                      Points Settings
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label>Points per $1 Spent</Label>
                        <Input
                          type="number"
                          value={programs.influencer.points_per_dollar}
                          onChange={(e) => updateProgram('influencer', 'points_per_dollar', parseInt(e.target.value))}
                        />
                      </div>
                      <div>
                        <Label>Points to Redeem $1</Label>
                        <Input
                          type="number"
                          value={programs.influencer.points_redemption_rate}
                          onChange={(e) => updateProgram('influencer', 'points_redemption_rate', parseInt(e.target.value))}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Gift className="h-4 w-4 text-pink-600" />
                      Customer Discount Settings
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <Label>Discount Type</Label>
                        <select
                          value={programs.influencer.customer_discount_type}
                          onChange={(e) => updateProgram('influencer', 'customer_discount_type', e.target.value)}
                          className="w-full px-3 py-2 border rounded-md"
                        >
                          <option value="percentage">Percentage</option>
                          <option value="fixed_amount">Fixed Amount</option>
                          <option value="free_shipping">Free Shipping</option>
                        </select>
                      </div>
                      <div>
                        <Label>Discount Value</Label>
                        <Input
                          type="number"
                          value={programs.influencer.customer_discount_value}
                          onChange={(e) => updateProgram('influencer', 'customer_discount_value', parseFloat(e.target.value))}
                        />
                      </div>
                      <div>
                        <Label>Discount Label</Label>
                        <Input
                          value={programs.influencer.customer_discount_label}
                          onChange={(e) => updateProgram('influencer', 'customer_discount_label', e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-4">
                      <Switch
                        checked={programs.influencer.allow_coupon_stacking}
                        onCheckedChange={(checked) => updateProgram('influencer', 'allow_coupon_stacking', checked)}
                      />
                      <Label>Allow Coupon Stacking</Label>
                    </div>
                  </div>
                </div>
              )}

              {/* Founder Program Settings - CORRECTED: Single Referral Discount with 30% Max Cap */}
              {activeProgram === 'founder' && (
                <div className="space-y-6">
                  {/* CRITICAL: Founding Member Pricing Editor */}
                  <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200 rounded-lg p-4">
                    <h4 className="font-semibold mb-3 flex items-center gap-2 text-amber-800">
                      <DollarSign className="h-5 w-5 text-amber-600" />
                      Founding Member Pricing Editor
                      <Badge className="bg-red-100 text-red-700 text-xs ml-2">CRITICAL</Badge>
                    </h4>
                    <p className="text-xs text-amber-700 mb-4">
                      Controls the price displayed on <code className="bg-amber-100 px-1 rounded">/founding-member</code> page. 
                      <strong> Hard limit: 30% maximum discount</strong> to protect revenue.
                    </p>
                    
                    <FoundingPricingEditor />
                  </div>

                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Crown className="h-4 w-4 text-yellow-600" />
                      Additional Founder Settings
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label>Points Multiplier</Label>
                        <Input
                          type="number"
                          value={programs.founder.points_multiplier}
                          onChange={(e) => updateProgram('founder', 'points_multiplier', parseInt(e.target.value))}
                        />
                        <p className="text-xs text-gray-500 mt-1">Founders earn {programs.founder.points_multiplier}x points</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={programs.founder.exclusive_rewards}
                          onCheckedChange={(checked) => updateProgram('founder', 'exclusive_rewards', checked)}
                        />
                        <Label>Enable Exclusive Rewards</Label>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Quiz Program Settings */}
              {activeProgram === 'quiz' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Quiz Name</Label>
                      <Input
                        value={programs.quiz.quiz_name}
                        onChange={(e) => updateProgram('quiz', 'quiz_name', e.target.value)}
                      />
                    </div>
                    <div>
                      <Label>Completion Reward Type</Label>
                      <select
                        value={programs.quiz.completion_reward_type}
                        onChange={(e) => updateProgram('quiz', 'completion_reward_type', e.target.value)}
                        className="w-full px-3 py-2 border rounded-md"
                      >
                        <option value="points">Points</option>
                        <option value="discount">Discount Code</option>
                        <option value="none">No Reward</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Reward Value (Points or %)</Label>
                      <Input
                        type="number"
                        value={programs.quiz.completion_reward_value}
                        onChange={(e) => updateProgram('quiz', 'completion_reward_value', parseFloat(e.target.value))}
                      />
                    </div>
                    <div>
                      <Label>Bonus Points for Sharing</Label>
                      <Input
                        type="number"
                        value={programs.quiz.bonus_points_for_sharing}
                        onChange={(e) => updateProgram('quiz', 'bonus_points_for_sharing', parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="space-y-3 border-t pt-4">
                    <h4 className="font-medium">Data Collection</h4>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.quiz.collect_email}
                        onCheckedChange={(checked) => updateProgram('quiz', 'collect_email', checked)}
                      />
                      <Label>Collect Email</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.quiz.collect_phone}
                        onCheckedChange={(checked) => updateProgram('quiz', 'collect_phone', checked)}
                      />
                      <Label>Collect Phone Number</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.quiz.show_product_recommendations}
                        onCheckedChange={(checked) => updateProgram('quiz', 'show_product_recommendations', checked)}
                      />
                      <Label>Show Product Recommendations</Label>
                    </div>
                  </div>
                </div>
              )}

              {/* Bio-Age Scan Settings */}
              {activeProgram === 'bioAgeScan' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Scan Name</Label>
                      <Input
                        value={programs.bioAgeScan.scan_name}
                        onChange={(e) => updateProgram('bioAgeScan', 'scan_name', e.target.value)}
                      />
                    </div>
                    <div>
                      <Label>Points for Completing Scan</Label>
                      <Input
                        type="number"
                        value={programs.bioAgeScan.points_for_scan}
                        onChange={(e) => updateProgram('bioAgeScan', 'points_for_scan', parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="space-y-3 border-t pt-4">
                    <h4 className="font-medium">Display & Rewards</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={programs.bioAgeScan.show_age_estimate}
                          onCheckedChange={(checked) => updateProgram('bioAgeScan', 'show_age_estimate', checked)}
                        />
                        <Label>Show Age Estimate</Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={programs.bioAgeScan.email_results}
                          onCheckedChange={(checked) => updateProgram('bioAgeScan', 'email_results', checked)}
                        />
                        <Label>Email Results</Label>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.bioAgeScan.offer_discount}
                        onCheckedChange={(checked) => updateProgram('bioAgeScan', 'offer_discount', checked)}
                      />
                      <Label>Offer Discount After Scan</Label>
                    </div>
                    {programs.bioAgeScan.offer_discount && (
                      <div className="grid grid-cols-2 gap-4 pl-6">
                        <div>
                          <Label>Discount Code</Label>
                          <Input
                            value={programs.bioAgeScan.discount_code}
                            onChange={(e) => updateProgram('bioAgeScan', 'discount_code', e.target.value)}
                          />
                        </div>
                        <div>
                          <Label>Discount Value (%)</Label>
                          <Input
                            type="number"
                            value={programs.bioAgeScan.discount_value}
                            onChange={(e) => updateProgram('bioAgeScan', 'discount_value', parseFloat(e.target.value))}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Comparison Tool Settings */}
              {activeProgram === 'comparison' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Tool Name</Label>
                      <Input
                        value={programs.comparison.tool_name}
                        onChange={(e) => updateProgram('comparison', 'tool_name', e.target.value)}
                      />
                    </div>
                    <div>
                      <Label>Max Products to Compare</Label>
                      <Input
                        type="number"
                        min={2}
                        max={6}
                        value={programs.comparison.max_products}
                        onChange={(e) => updateProgram('comparison', 'max_products', parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Points for Using Tool</Label>
                      <Input
                        type="number"
                        value={programs.comparison.points_for_using}
                        onChange={(e) => updateProgram('comparison', 'points_for_using', parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="space-y-3 border-t pt-4">
                    <h4 className="font-medium">Display Options</h4>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.comparison.show_pricing}
                        onCheckedChange={(checked) => updateProgram('comparison', 'show_pricing', checked)}
                      />
                      <Label>Show Pricing</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.comparison.show_ingredients}
                        onCheckedChange={(checked) => updateProgram('comparison', 'show_ingredients', checked)}
                      />
                      <Label>Show Ingredients</Label>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={programs.comparison.highlight_differences}
                        onCheckedChange={(checked) => updateProgram('comparison', 'highlight_differences', checked)}
                      />
                      <Label>Highlight Differences</Label>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Save Button - Sticky at bottom of settings */}
              <div className="sticky bottom-0 bg-white border-t pt-4 mt-6 -mx-6 px-6 pb-2">
                <Button 
                  onClick={saveSettings} 
                  disabled={saving}
                  className="w-full bg-gradient-to-r from-[#F8A5B8] to-[#E88DA0] hover:from-[#E88DA0] hover:to-[#D77A8D] text-white py-3"
                  data-testid="save-settings-btn"
                >
                  {saving ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Save All Program Settings
                </Button>
              </div>
            </TabsContent>

            {/* Analytics Tab */}
            <TabsContent value="analytics">
              <div className="space-y-4">
                {activeProgram === 'influencer' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Total Partners" value={analytics.influencer.activeUsers} icon={Users} color="purple" trend={12} />
                    <StatCard label="Total Clicks" value={analytics.influencer.clicks} icon={Eye} color="blue" trend={8} />
                    <StatCard label="Conversions" value={analytics.influencer.conversions} icon={TrendingUp} color="green" trend={15} />
                    <StatCard label="Total Earnings" value={`$${analytics.influencer.earnings}`} icon={DollarSign} color="emerald" trend={22} />
                  </div>
                )}
                {activeProgram === 'founder' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Total Members" value={analytics.founder.totalMembers} icon={Crown} color="yellow" trend={5} />
                    <StatCard label="Points Issued" value={analytics.founder.pointsIssued.toLocaleString()} icon={Coins} color="orange" trend={18} />
                    <StatCard label="Points Redeemed" value={analytics.founder.pointsRedeemed.toLocaleString()} icon={Gift} color="pink" trend={12} />
                    <StatCard label="Redemptions" value={analytics.founder.redemptions} icon={Check} color="green" trend={8} />
                  </div>
                )}
                {activeProgram === 'quiz' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Completions" value={analytics.quiz.completions} icon={Sparkles} color="pink" trend={25} />
                    <StatCard label="Emails Captured" value={analytics.quiz.emailsCaptured} icon={Mail} color="blue" trend={22} />
                    <StatCard label="Discounts Used" value={analytics.quiz.discountsUsed} icon={Percent} color="green" trend={10} />
                    <StatCard label="Conversion Rate" value={`${analytics.quiz.conversionRate}%`} icon={TrendingUp} color="purple" trend={5} />
                  </div>
                )}
                {activeProgram === 'bioAgeScan' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Scans Completed" value={analytics.bioAgeScan.scansCompleted} icon={TestTube} color="blue" trend={30} />
                    <StatCard label="Emails Captured" value={analytics.bioAgeScan.emailsCaptured} icon={Mail} color="teal" trend={28} />
                    <StatCard label="Discounts Used" value={analytics.bioAgeScan.discountsUsed} icon={Gift} color="green" trend={15} />
                    <StatCard label="Avg Bio-Age" value={analytics.bioAgeScan.avgBioAge} icon={Clock} color="purple" />
                  </div>
                )}
                {activeProgram === 'comparison' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Comparisons" value={analytics.comparison.comparisons} icon={GitCompare} color="green" trend={20} />
                    <StatCard label="Products Compared" value={analytics.comparison.productsCompared} icon={Eye} color="blue" trend={25} />
                    <StatCard label="Add to Cart Rate" value={`${analytics.comparison.addToCartRate}%`} icon={TrendingUp} color="emerald" trend={8} />
                  </div>
                )}

                {/* Conversion Funnel */}
                <Card className="mt-4">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Conversion Funnel</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span>Views</span>
                          <span>1,234</span>
                        </div>
                        <Progress value={100} className="h-2" />
                      </div>
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span>Engaged</span>
                          <span>456</span>
                        </div>
                        <Progress value={37} className="h-2" />
                      </div>
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span>Converted</span>
                          <span>89</span>
                        </div>
                        <Progress value={7} className="h-2" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Tracking Tab */}
            <TabsContent value="tracking">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium">Referral Tracking</h4>
                  <Button variant="outline" size="sm" disabled={referralData.length === 0}>
                    <Download className="h-4 w-4 mr-2" />
                    Export
                  </Button>
                </div>
                {referralData.length === 0 ? (
                  <div className="border rounded-lg p-8 text-center bg-gray-50">
                    <Link2 className="h-12 w-12 mx-auto text-gray-300 mb-3" />
                    <p className="text-gray-600 font-medium">No referral data yet</p>
                    <p className="text-sm text-gray-500 mt-1">Share program links to promote your pages</p>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="mt-4"
                      onClick={() => openShareModal(activeProgram)}
                    >
                      <Share2 className="h-4 w-4 mr-2" />
                      Create & Share Link
                    </Button>
                  </div>
                ) : (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left">Name</th>
                          <th className="px-4 py-2 text-left">Code</th>
                          <th className="px-4 py-2 text-center">Clicks</th>
                          <th className="px-4 py-2 text-center">Conversions</th>
                          <th className="px-4 py-2 text-right">Earnings</th>
                          <th className="px-4 py-2 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {referralData.map((ref) => (
                          <tr key={ref.id} className="border-t">
                            <td className="px-4 py-2">{ref.name}</td>
                            <td className="px-4 py-2">
                              <code className="bg-gray-100 px-2 py-1 rounded text-xs">{ref.code}</code>
                            </td>
                            <td className="px-4 py-2 text-center">{ref.clicks}</td>
                            <td className="px-4 py-2 text-center">{ref.conversions}</td>
                            <td className="px-4 py-2 text-right">${ref.earnings}</td>
                            <td className="px-4 py-2 text-center">
                              <Badge variant={ref.status === 'active' ? 'default' : 'secondary'} className="text-xs">
                                {ref.status}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </TabsContent>

            {/* Points Tab */}
            <TabsContent value="points">
              <div className="space-y-4">
                {/* Points Economy Settings */}
                <Card className="bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Settings className="h-4 w-4 text-amber-600" />
                      Points Economy
                    </CardTitle>
                    <CardDescription className="text-xs">How points are earned and redeemed</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-center">
                      <div className="p-3 bg-white rounded-lg shadow-sm">
                        <Users className="h-5 w-5 mx-auto text-purple-500 mb-1" />
                        <p className="text-lg font-bold text-purple-600">60 pts</p>
                        <p className="text-[10px] text-gray-500">Per Referral</p>
                      </div>
                      <div className="p-3 bg-white rounded-lg shadow-sm">
                        <Award className="h-5 w-5 mx-auto text-orange-500 mb-1" />
                        <p className="text-lg font-bold text-orange-600">600 pts</p>
                        <p className="text-[10px] text-gray-500">= 30% Off</p>
                      </div>
                    </div>
                    <div className="mt-4 p-3 bg-amber-100/50 rounded-lg">
                      <p className="text-xs text-amber-800 font-medium">Milestone:</p>
                      <div className="flex gap-4 mt-2">
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-purple-500 text-white flex items-center justify-center text-xs">10</div>
                          <span className="text-xs">Referrals = 30% discount (600 pts)</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid grid-cols-3 gap-4">
                  <Card className="bg-gradient-to-br from-yellow-50 to-orange-50">
                    <CardContent className="p-4 text-center">
                      <Coins className="h-8 w-8 mx-auto text-yellow-600 mb-2" />
                      <p className="text-2xl font-bold text-yellow-700">{analytics.founder.pointsIssued.toLocaleString()}</p>
                      <p className="text-xs text-gray-600">Total Points Issued</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-gradient-to-br from-green-50 to-emerald-50">
                    <CardContent className="p-4 text-center">
                      <Gift className="h-8 w-8 mx-auto text-green-600 mb-2" />
                      <p className="text-2xl font-bold text-green-700">{analytics.founder.pointsRedeemed.toLocaleString()}</p>
                      <p className="text-xs text-gray-600">Points Redeemed</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-gradient-to-br from-blue-50 to-indigo-50">
                    <CardContent className="p-4 text-center">
                      <TrendingUp className="h-8 w-8 mx-auto text-blue-600 mb-2" />
                      <p className="text-2xl font-bold text-blue-700">{(analytics.founder.pointsIssued - analytics.founder.pointsRedeemed).toLocaleString()}</p>
                      <p className="text-xs text-gray-600">Outstanding Points</p>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Recent Points Activity</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {pointsHistory.length === 0 ? (
                      <div className="text-center py-8 text-gray-500">
                        <Coins className="h-12 w-12 mx-auto text-gray-300 mb-2" />
                        <p className="text-sm">No points activity yet</p>
                        <p className="text-xs">Points will appear here when users earn or redeem</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {pointsHistory.map((item) => (
                          <div key={item.id} className="flex items-center justify-between py-2 border-b last:border-0">
                            <div className="flex items-center gap-3">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${item.points > 0 ? 'bg-green-100' : 'bg-red-100'}`}>
                                {item.points > 0 ? <Plus className="h-4 w-4 text-green-600" /> : <ArrowDownRight className="h-4 w-4 text-red-600" />}
                              </div>
                              <div>
                                <p className="text-sm font-medium">{item.action}</p>
                                <p className="text-xs text-gray-500">{item.user}</p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className={`font-bold ${item.points > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {item.points > 0 ? '+' : ''}{item.points} pts
                              </p>
                              <p className="text-xs text-gray-500">{item.date}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Gift Analytics - THE GOLD MINE */}
                <Card className="bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-amber-800">
                      <Sparkles className="h-4 w-4" />
                      Gift Points Analytics
                      <Badge className="bg-amber-200 text-amber-800 text-[10px]">Gold Mine</Badge>
                    </CardTitle>
                    <CardDescription className="text-xs text-amber-700">
                      Track who's gifting points to whom - valuable relationship data
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {/* Summary Stats */}
                    <div className="grid grid-cols-4 gap-2 mb-4">
                      <div className="p-2 bg-white rounded-lg text-center">
                        <p className="text-lg font-bold text-amber-700">{giftAnalytics.summary?.total_gifts || 0}</p>
                        <p className="text-[10px] text-gray-500">Total Gifts</p>
                      </div>
                      <div className="p-2 bg-white rounded-lg text-center">
                        <p className="text-lg font-bold text-green-600">{giftAnalytics.summary?.total_points_gifted?.toLocaleString() || 0}</p>
                        <p className="text-[10px] text-gray-500">Points Gifted</p>
                      </div>
                      <div className="p-2 bg-white rounded-lg text-center">
                        <p className="text-lg font-bold text-purple-600">{giftAnalytics.summary?.unique_gifters || 0}</p>
                        <p className="text-[10px] text-gray-500">Unique Gifters</p>
                      </div>
                      <div className="p-2 bg-white rounded-lg text-center">
                        <p className="text-lg font-bold text-blue-600">{giftAnalytics.summary?.unique_recipients || 0}</p>
                        <p className="text-[10px] text-gray-500">Recipients</p>
                      </div>
                    </div>

                    {/* Relationships - The Real Gold */}
                    {giftAnalytics.relationships?.length > 0 ? (
                      <div>
                        <p className="text-xs font-medium text-amber-800 mb-2">Top Gift Relationships</p>
                        <div className="space-y-1 max-h-40 overflow-y-auto">
                          {giftAnalytics.relationships.slice(0, 10).map((rel, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 bg-white rounded text-xs">
                              <div className="flex items-center gap-2 truncate flex-1">
                                <span className="text-gray-600 truncate max-w-[100px]">{rel.sender}</span>
                                <ArrowRight className="h-3 w-3 text-amber-500 flex-shrink-0" />
                                <span className="text-gray-600 truncate max-w-[100px]">{rel.recipient}</span>
                              </div>
                              <Badge variant="outline" className="text-amber-600 ml-2">{rel.total_points} pts ({rel.gift_count}x)</Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-4 text-gray-500">
                        <Send className="h-8 w-8 mx-auto text-gray-300 mb-2" />
                        <p className="text-xs">No gift activity yet</p>
                        <p className="text-[10px]">Relationship data will appear when users gift points</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* ============ DETAIL DRAWERS ============ */}
      
      {/* Bio-Age Scan Detail Drawer */}
      <Dialog open={showScanDrawer} onOpenChange={(open) => {
        setShowScanDrawer(open);
        if (!open) {
          setScanResultFile(null); // Clear file when drawer closes
        }
      }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <TestTube className="h-5 w-5 text-blue-600" />
              Bio-Age Scan Details
            </DialogTitle>
            <DialogDescription>
              Review scan submission, upload results, and notify customer
            </DialogDescription>
          </DialogHeader>
          
          {selectedScan && (
            <div className="space-y-4 py-4">
              {/* User Info */}
              <div className="bg-blue-50 rounded-lg p-4">
                <h4 className="font-medium text-blue-800 mb-2">User Information</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-gray-500">Name</p>
                    <p className="font-medium">{selectedScan.name || 'Not provided'}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Email</p>
                    <p className="font-medium">{selectedScan.email || 'Not provided'}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Phone</p>
                    <p className="font-medium">{selectedScan.phone || selectedScan.whatsapp || 'Not provided'}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Date</p>
                    <p className="font-medium">
                      {selectedScan.created_at ? new Date(selectedScan.created_at).toLocaleDateString() : '--'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Scan Results */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium mb-2">Scan Results</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-gradient-to-br from-purple-50 to-blue-50 p-3 rounded-lg text-center">
                    <p className="text-gray-500 text-xs">Bio-Age</p>
                    <p className="text-2xl font-bold text-purple-700">{selectedScan.bio_age || selectedScan.bioAge || '--'}</p>
                  </div>
                  <div className="bg-gradient-to-br from-green-50 to-teal-50 p-3 rounded-lg text-center">
                    <p className="text-gray-500 text-xs">Actual Age</p>
                    <p className="text-2xl font-bold text-green-700">{selectedScan.actual_age || selectedScan.age || '--'}</p>
                  </div>
                </div>
                
                {/* Concerns */}
                {(selectedScan.concerns || selectedScan.skin_concerns) && (
                  <div className="mt-4">
                    <p className="text-sm text-gray-500 mb-2">Identified Concerns</p>
                    <div className="flex flex-wrap gap-2">
                      {(selectedScan.concerns || selectedScan.skin_concerns || []).map((concern, i) => (
                        <Badge key={i} variant="outline" className="bg-gray-50">
                          {concern}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Upload Results PDF Section */}
              <div className="border-2 border-dashed border-blue-200 rounded-lg p-4 bg-blue-50/50">
                <h4 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
                  <Upload className="h-4 w-4" />
                  Upload Results PDF
                </h4>
                
                {selectedScan.result_pdf_url ? (
                  // PDF already uploaded
                  <div className="bg-green-50 rounded-lg p-3 border border-green-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="h-5 w-5 text-green-600" />
                        <div>
                          <p className="text-sm font-medium text-green-800">Result PDF Uploaded</p>
                          <p className="text-xs text-green-600">
                            {selectedScan.results_uploaded_at 
                              ? new Date(selectedScan.results_uploaded_at).toLocaleString()
                              : 'Ready to send'}
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="h-8"
                          onClick={() => window.open(selectedScan.result_pdf_url, '_blank')}
                        >
                          <Eye className="h-3 w-3 mr-1" />
                          View
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline"
                          className="h-8"
                          onClick={() => {
                            setSelectedScan(prev => ({ ...prev, result_pdf_url: null }));
                          }}
                        >
                          Replace
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  // Upload area
                  <div className="space-y-3">
                    <div className="relative">
                      <input
                        type="file"
                        accept=".pdf,application/pdf"
                        onChange={handleResultFileSelect}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        data-testid="scan-result-file-input"
                      />
                      <div className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                        scanResultFile ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
                      }`}>
                        {scanResultFile ? (
                          <div className="flex items-center justify-center gap-2">
                            <FileText className="h-6 w-6 text-green-600" />
                            <div className="text-left">
                              <p className="font-medium text-green-800">{scanResultFile.name}</p>
                              <p className="text-xs text-green-600">{(scanResultFile.size / 1024).toFixed(1)} KB</p>
                            </div>
                          </div>
                        ) : (
                          <>
                            <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                            <p className="text-sm text-gray-600">Drag & drop PDF or click to browse</p>
                            <p className="text-xs text-gray-400 mt-1">Max 10MB</p>
                          </>
                        )}
                      </div>
                    </div>
                    
                    {scanResultFile && (
                      <Button 
                        onClick={handleUploadResult}
                        disabled={uploadingResult}
                        className="w-full bg-blue-600 hover:bg-blue-700"
                        data-testid="upload-result-btn"
                      >
                        {uploadingResult ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                            Uploading...
                          </>
                        ) : (
                          <>
                            <Upload className="h-4 w-4 mr-2" />
                            Upload Result PDF
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                )}
              </div>

              {/* Status Indicator */}
              <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2">
                  {selectedScan.result_pdf_url ? (
                    <CheckSquare className="h-4 w-4 text-green-600" />
                  ) : (
                    <Square className="h-4 w-4 text-gray-400" />
                  )}
                  <span className={`text-sm ${selectedScan.result_pdf_url ? 'text-green-700' : 'text-gray-500'}`}>
                    PDF Uploaded
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {selectedScan.results_sent ? (
                    <CheckSquare className="h-4 w-4 text-green-600" />
                  ) : (
                    <Square className="h-4 w-4 text-gray-400" />
                  )}
                  <span className={`text-sm ${selectedScan.results_sent ? 'text-green-700' : 'text-gray-500'}`}>
                    Notification Sent
                  </span>
                </div>
              </div>

              {/* Referral Info */}
              {selectedScan.referred_by && (
                <div className="bg-amber-50 rounded-lg p-4">
                  <h4 className="font-medium text-amber-800 mb-2">Referral Information</h4>
                  <p className="text-sm">Referred by: <span className="font-medium">{selectedScan.referred_by}</span></p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t">
                {/* Send Notification - Primary Action */}
                {selectedScan.email && (
                  <Button 
                    className={`flex-1 ${
                      selectedScan.result_pdf_url 
                        ? 'bg-green-600 hover:bg-green-700' 
                        : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                    onClick={handleSendResultsNotification}
                    disabled={sendingNotification || !selectedScan.result_pdf_url}
                    title={!selectedScan.result_pdf_url ? 'Upload PDF first' : 'Send results to customer'}
                    data-testid="send-notification-btn"
                  >
                    {sendingNotification ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4 mr-2" />
                        {selectedScan.results_sent ? 'Resend Results' : 'Send Results'}
                      </>
                    )}
                  </Button>
                )}
                
                {/* Manual Email Link */}
                {selectedScan.email && (
                  <Button 
                    variant="outline"
                    onClick={() => {
                      const pdfLink = selectedScan.result_pdf_url 
                        ? `\n\nYour personalized results report: ${selectedScan.result_pdf_url}` 
                        : '';
                      window.location.href = `mailto:${selectedScan.email}?subject=Your Bio-Age Scan Results Are Ready!&body=Hi ${selectedScan.name || 'there'},\n\nGreat news! Your Bio-Age Scan results are ready.\n\nYour Bio-Age: ${selectedScan.bio_age || selectedScan.bioAge || 'See attached report'}${pdfLink}\n\nBest regards,\nReRoots Team`;
                    }}
                  >
                    <Mail className="h-4 w-4 mr-2" />
                    Manual Email
                  </Button>
                )}
                
                <Button variant="outline" onClick={() => setShowScanDrawer(false)}>
                  Close
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Partner Detail Drawer */}
      <Dialog open={showPartnerDrawer} onOpenChange={setShowPartnerDrawer}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-purple-600" />
              Partner Application
            </DialogTitle>
            <DialogDescription>
              Review profile and approve/reject application
            </DialogDescription>
          </DialogHeader>
          
          {selectedPartner && (
            <div className="space-y-4 py-4">
              {/* Applicant Info */}
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-12 h-12 rounded-full bg-purple-200 flex items-center justify-center text-purple-700 font-bold text-lg">
                    {selectedPartner.full_name?.charAt(0) || '?'}
                  </div>
                  <div>
                    <h4 className="font-semibold text-purple-800">{selectedPartner.full_name}</h4>
                    <p className="text-sm text-gray-600">{selectedPartner.email}</p>
                  </div>
                  <Badge 
                    className={`ml-auto ${
                      selectedPartner.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                      selectedPartner.status === 'approved' ? 'bg-green-100 text-green-700' :
                      selectedPartner.status === 'active' ? 'bg-blue-100 text-blue-700' :
                      'bg-red-100 text-red-700'
                    }`}
                  >
                    {selectedPartner.status}
                  </Badge>
                </div>
              </div>

              {/* Social Media */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium mb-3">Social Media</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {selectedPartner.instagram && (
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-pink-100 flex items-center justify-center">
                        <span className="text-pink-600 text-xs">IG</span>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Instagram</p>
                        <a href={`https://instagram.com/${selectedPartner.instagram}`} target="_blank" rel="noopener noreferrer" className="text-pink-600 hover:underline">
                          @{selectedPartner.instagram}
                        </a>
                      </div>
                    </div>
                  )}
                  {selectedPartner.tiktok && (
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                        <span className="text-gray-600 text-xs">TT</span>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">TikTok</p>
                        <a href={`https://tiktok.com/@${selectedPartner.tiktok}`} target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:underline">
                          @{selectedPartner.tiktok}
                        </a>
                      </div>
                    </div>
                  )}
                  {selectedPartner.youtube && (
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
                        <span className="text-red-600 text-xs">YT</span>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">YouTube</p>
                        <span className="text-red-600">{selectedPartner.youtube}</span>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                      <Users className="h-4 w-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Followers</p>
                      <p className="font-medium">{selectedPartner.follower_count?.toLocaleString() || 'Not specified'}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Application Details */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium mb-3">Application Details</h4>
                <div className="space-y-3 text-sm">
                  {selectedPartner.why_partner && (
                    <div>
                      <p className="text-gray-500">Why they want to partner</p>
                      <p className="mt-1 bg-gray-50 p-2 rounded">{selectedPartner.why_partner}</p>
                    </div>
                  )}
                  {selectedPartner.content_niche && (
                    <div>
                      <p className="text-gray-500">Content Niche</p>
                      <p className="font-medium">{selectedPartner.content_niche}</p>
                    </div>
                  )}
                  {selectedPartner.previous_brands && (
                    <div>
                      <p className="text-gray-500">Previous Brand Partnerships</p>
                      <p className="mt-1 bg-gray-50 p-2 rounded">{selectedPartner.previous_brands}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Partner Code (if approved) */}
              {selectedPartner.partner_code && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h4 className="font-medium text-green-800 mb-2">Partner Code</h4>
                  <div className="flex items-center gap-2">
                    <code className="bg-white px-3 py-2 rounded border text-lg font-mono">{selectedPartner.partner_code}</code>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => {
                        navigator.clipboard.writeText(selectedPartner.partner_code);
                        toast.success('Code copied!');
                      }}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t">
                {selectedPartner.status === 'pending' && (
                  <>
                    <Button 
                      className="flex-1 bg-green-600 hover:bg-green-700"
                      onClick={() => handleApprovePartner(selectedPartner.id)}
                    >
                      <UserCheck className="h-4 w-4 mr-2" />
                      Approve
                    </Button>
                    <Button 
                      variant="destructive"
                      className="flex-1"
                      onClick={() => handleRejectPartner(selectedPartner.id)}
                    >
                      <UserX className="h-4 w-4 mr-2" />
                      Reject
                    </Button>
                  </>
                )}
                <Button variant="outline" onClick={() => setShowPartnerDrawer(false)}>
                  Close
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Waitlist Detail Drawer */}
      <Dialog open={showWaitlistDrawer} onOpenChange={setShowWaitlistDrawer}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-teal-600" />
              Waitlist Member
            </DialogTitle>
            <DialogDescription>
              View member details and send invitations
            </DialogDescription>
          </DialogHeader>
          
          {selectedWaitlistEntry && (
            <div className="space-y-4 py-4">
              {/* Member Info */}
              <div className="bg-teal-50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-12 h-12 rounded-full bg-teal-200 flex items-center justify-center text-teal-700 font-bold text-lg">
                    {(selectedWaitlistEntry.name || selectedWaitlistEntry.email)?.charAt(0)?.toUpperCase() || '?'}
                  </div>
                  <div>
                    <h4 className="font-semibold text-teal-800">
                      {selectedWaitlistEntry.name || selectedWaitlistEntry.full_name || selectedWaitlistEntry.email?.split('@')[0]}
                    </h4>
                    <p className="text-sm text-gray-600">{selectedWaitlistEntry.email}</p>
                  </div>
                  {selectedWaitlistEntry.voucher_unlocked && (
                    <Badge className="ml-auto bg-purple-100 text-purple-700">VIP</Badge>
                  )}
                </div>
              </div>

              {/* Referral Stats */}
              <div className="grid grid-cols-3 gap-3">
                <Card className="bg-blue-50">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700">
                      {selectedWaitlistEntry.successful_referrals || selectedWaitlistEntry.referral_count || 0}
                    </p>
                    <p className="text-xs text-gray-600">Referrals</p>
                  </CardContent>
                </Card>
                <Card className="bg-green-50">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-green-700">
                      {selectedWaitlistEntry.total_points || 0}
                    </p>
                    <p className="text-xs text-gray-600">Points</p>
                  </CardContent>
                </Card>
                <Card className="bg-purple-50">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-purple-700">
                      {selectedWaitlistEntry.voucher_unlocked ? 'Yes' : 'No'}
                    </p>
                    <p className="text-xs text-gray-600">VIP Status</p>
                  </CardContent>
                </Card>
              </div>

              {/* Referral Code */}
              {selectedWaitlistEntry.referral_code && (
                <div className="border rounded-lg p-4">
                  <h4 className="font-medium mb-2">Referral Code</h4>
                  <div className="flex items-center gap-2">
                    <code className="bg-gray-100 px-3 py-2 rounded text-lg font-mono flex-1">{selectedWaitlistEntry.referral_code}</code>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => {
                        navigator.clipboard.writeText(`https://reroots.ca/Bio-Age-Repair-Scan?ref=${selectedWaitlistEntry.referral_code}`);
                        toast.success('Referral link copied!');
                      }}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Details */}
              <div className="border rounded-lg p-4">
                <h4 className="font-medium mb-3">Details</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-gray-500">Joined</p>
                    <p className="font-medium">
                      {selectedWaitlistEntry.created_at ? new Date(selectedWaitlistEntry.created_at).toLocaleDateString() : '--'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">Source</p>
                    <p className="font-medium">{selectedWaitlistEntry.source || 'Direct'}</p>
                  </div>
                  {selectedWaitlistEntry.phone || selectedWaitlistEntry.phone_number && (
                    <div>
                      <p className="text-gray-500">Phone</p>
                      <p className="font-medium">{selectedWaitlistEntry.phone || selectedWaitlistEntry.phone_number}</p>
                    </div>
                  )}
                  {selectedWaitlistEntry.referred_by && (
                    <div>
                      <p className="text-gray-500">Referred By</p>
                      <p className="font-medium">{selectedWaitlistEntry.referred_by}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t">
                <Button 
                  className="flex-1 bg-teal-600 hover:bg-teal-700"
                  onClick={() => handleSendWaitlistInvite(selectedWaitlistEntry)}
                >
                  <Send className="h-4 w-4 mr-2" />
                  Send Invite
                </Button>
                {selectedWaitlistEntry.email && (
                  <Button 
                    variant="outline"
                    onClick={() => {
                      window.location.href = `mailto:${selectedWaitlistEntry.email}`;
                    }}
                  >
                    <Mail className="h-4 w-4 mr-2" />
                    Email
                  </Button>
                )}
                <Button variant="outline" onClick={() => setShowWaitlistDrawer(false)}>
                  Close
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Product Detail Drawer */}
      <Dialog open={showProductDrawer} onOpenChange={setShowProductDrawer}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-orange-600" />
              Product Details
            </DialogTitle>
            <DialogDescription>
              View and edit product information
            </DialogDescription>
          </DialogHeader>
          
          {selectedProduct && (
            <div className="space-y-4 py-4">
              {/* Product Image & Name */}
              <div className="flex items-center gap-4">
                {selectedProduct.image && (
                  <img 
                    src={selectedProduct.image} 
                    alt={selectedProduct.name || selectedProduct.title} 
                    className="w-20 h-20 rounded-lg object-cover border"
                  />
                )}
                <div>
                  <h4 className="font-semibold text-lg">{selectedProduct.name || selectedProduct.title}</h4>
                  <Badge 
                    className={selectedProduct.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}
                  >
                    {selectedProduct.is_active !== false ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>

              {/* Pricing */}
              <div className="grid grid-cols-3 gap-3">
                <Card className="bg-green-50">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-green-700">${selectedProduct.price?.toFixed(2) || '--'}</p>
                    <p className="text-xs text-gray-600">Price</p>
                  </CardContent>
                </Card>
                <Card className="bg-blue-50">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700">{selectedProduct.stock ?? selectedProduct.inventory ?? '--'}</p>
                    <p className="text-xs text-gray-600">Stock</p>
                  </CardContent>
                </Card>
                <Card className="bg-purple-50">
                  <CardContent className="p-3 text-center">
                    <p className="text-2xl font-bold text-purple-700">{selectedProduct.sold || 0}</p>
                    <p className="text-xs text-gray-600">Sold</p>
                  </CardContent>
                </Card>
              </div>

              {/* Description */}
              {selectedProduct.description && (
                <div className="border rounded-lg p-4">
                  <h4 className="font-medium mb-2">Description</h4>
                  <p className="text-sm text-gray-600">{selectedProduct.description}</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t">
                <Button 
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    window.open(`/shop/${selectedProduct.slug || selectedProduct.id}`, '_blank');
                  }}
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View Page
                </Button>
                <Button variant="outline" onClick={() => setShowProductDrawer(false)}>
                  Close
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      {/* ============ END DETAIL DRAWERS ============ */}

      {/* Share Modal */}
      <Dialog open={showShareModal} onOpenChange={setShowShareModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Share2 className="h-5 w-5 text-[#F8A5B8]" />
              Share {programCards.find(p => p.key === shareProgram)?.title}
            </DialogTitle>
            <DialogDescription>
              Share this program page link with your audience
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Program Link */}
            <div>
              <Label className="text-xs text-gray-500">Program Link</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  value={getProgramLink(shareProgram || 'influencer')}
                  readOnly
                  className="text-sm"
                />
                <Button
                  variant="outline"
                  onClick={() => copyReferralLink(getProgramLink(shareProgram || 'influencer'))}
                >
                  {copiedLink ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            {/* Share Buttons */}
            <div>
              <Label className="text-xs text-gray-500 mb-2 block">Share via</Label>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => window.open(`https://twitter.com/intent/tweet?url=${encodeURIComponent(getProgramLink(shareProgram || 'influencer'))}&text=Check out this amazing program!`, '_blank')}
                >
                  <Twitter className="h-4 w-4 mr-2" />
                  Twitter
                </Button>
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(getProgramLink(shareProgram || 'influencer'))}`, '_blank')}
                >
                  <Facebook className="h-4 w-4 mr-2" />
                  Facebook
                </Button>
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={() => window.open(`mailto:?subject=Check this out&body=${encodeURIComponent(getProgramLink(shareProgram || 'influencer'))}`, '_blank')}
                >
                  <Mail className="h-4 w-4 mr-2" />
                  Email
                </Button>
              </div>
            </div>

            {/* QR Code placeholder */}
            <div className="border rounded-lg p-4 text-center bg-gray-50">
              <QrCode className="h-12 w-12 mx-auto text-gray-400 mb-2" />
              <p className="text-xs text-gray-500">QR Code for easy sharing</p>
              <Button variant="ghost" size="sm" className="mt-2">
                <Download className="h-4 w-4 mr-1" />
                Download QR
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Page Editor Modal */}
      <Dialog open={showPageEditor} onOpenChange={setShowPageEditor}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit3 className="h-5 w-5 text-blue-500" />
              Edit {activeProgram === 'influencer' ? 'Influencer Landing' : 
                    activeProgram === 'quiz' ? 'Skin Quiz' :
                    activeProgram === 'bioAgeScan' ? 'Bio-Age Repair Scan' :
                    activeProgram === 'comparison' ? 'Comparison Tool' :
                    activeProgram === 'shop' ? 'Shop' :
                    activeProgram === 'waitlist' ? 'Waitlist' : ''} Page
            </DialogTitle>
            <DialogDescription>
              Customize the content displayed on your {activeProgram === 'influencer' ? 'partner program' : 
                activeProgram === 'quiz' ? 'skin quiz' :
                activeProgram === 'bioAgeScan' ? 'bio-age repair scan' :
                activeProgram === 'comparison' ? 'comparison tool' :
                activeProgram === 'shop' ? 'shop' :
                activeProgram === 'waitlist' ? 'waitlist' : ''} page
            </DialogDescription>
          </DialogHeader>
          
          {pageContent && (
            <div className="space-y-6 py-4">
              {/* Hero Section */}
              <div className="space-y-4 p-4 border rounded-lg bg-gray-50">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <Star className="h-4 w-4 text-yellow-500" />
                  Hero Section
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Badge Text</Label>
                    <Input
                      value={pageContent?.hero?.badge_text || ''}
                      onChange={(e) => updatePageField('hero', 'badge_text', e.target.value)}
                      placeholder={activeProgram === 'influencer' ? 'GOLD PARTNER PROGRAM' : 
                                   activeProgram === 'quiz' ? 'FREE SKIN ANALYSIS' :
                                   activeProgram === 'bioAgeScan' ? 'FREE BIO-AGE SCAN' :
                                   activeProgram === 'shop' ? 'EXCLUSIVE COLLECTIONS' :
                                   activeProgram === 'waitlist' ? 'EXCLUSIVE ACCESS' : 'PRODUCT COMPARISON'}
                    />
                  </div>
                  <div>
                    <Label>Hero Image URL</Label>
                    <Input
                      value={pageContent?.hero?.image || ''}
                      onChange={(e) => updatePageField('hero', 'image', e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                </div>
                
                <div>
                  <Label>Title</Label>
                  <Input
                    value={pageContent?.hero?.title || ''}
                    onChange={(e) => updatePageField('hero', 'title', e.target.value)}
                    placeholder={activeProgram === 'influencer' ? 'Join the ReRoots Family' :
                                 activeProgram === 'quiz' ? 'Discover Your Perfect Skincare' :
                                 activeProgram === 'bioAgeScan' ? "Discover Your Skin's True Age" :
                                 activeProgram === 'shop' ? 'Shop Our Collections' :
                                 activeProgram === 'waitlist' ? 'Join the ReRoots Waitlist' : 'Compare Products Side by Side'}
                  />
                </div>
                
                <div>
                  <Label>Subtitle</Label>
                  <Input
                    value={pageContent?.hero?.subtitle || ''}
                    onChange={(e) => updatePageField('hero', 'subtitle', e.target.value)}
                    placeholder="Enter subtitle..."
                  />
                </div>
                
                <div>
                  <Label>Description</Label>
                  <Textarea
                    value={pageContent?.hero?.description || ''}
                    onChange={(e) => updatePageField('hero', 'description', e.target.value)}
                    placeholder="Enter description..."
                    rows={3}
                  />
                </div>
              </div>

              {/* About Section */}
              <div className="space-y-4 p-4 border rounded-lg bg-gray-50">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <FileText className="h-4 w-4 text-blue-500" />
                  About Section
                </div>
                
                <div>
                  <Label>Title</Label>
                  <Input
                    value={pageContent?.about?.title || ''}
                    onChange={(e) => updatePageField('about', 'title', e.target.value)}
                    placeholder={activeProgram === 'influencer' ? 'About ReRoots' :
                                 activeProgram === 'quiz' ? 'How It Works' :
                                 activeProgram === 'bioAgeScan' ? 'What is Bio-Age?' :
                                 activeProgram === 'shop' ? 'Our Philosophy' :
                                 activeProgram === 'waitlist' ? 'Why Join?' : 'Why Compare?'}
                  />
                </div>
                
                <div>
                  <Label>Description</Label>
                  <Textarea
                    value={pageContent?.about?.description || ''}
                    onChange={(e) => updatePageField('about', 'description', e.target.value)}
                    placeholder="Enter about description..."
                    rows={4}
                  />
                </div>
              </div>

              {/* CTA Section */}
              <div className="space-y-4 p-4 border rounded-lg bg-gray-50">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <Zap className="h-4 w-4 text-orange-500" />
                  Call to Action
                </div>
                
                <div>
                  <Label>CTA Title</Label>
                  <Input
                    value={pageContent?.cta?.title || ''}
                    onChange={(e) => updatePageField('cta', 'title', e.target.value)}
                    placeholder="Ready to Start?"
                  />
                </div>
                
                <div>
                  <Label>CTA Description</Label>
                  <Textarea
                    value={pageContent?.cta?.description || ''}
                    onChange={(e) => updatePageField('cta', 'description', e.target.value)}
                    placeholder="Enter call to action description..."
                    rows={2}
                  />
                </div>
                
                <div>
                  <Label>Button Text</Label>
                  <Input
                    value={pageContent?.cta?.button_text || ''}
                    onChange={(e) => updatePageField('cta', 'button_text', e.target.value)}
                    placeholder={activeProgram === 'influencer' ? 'Apply Now' :
                                 activeProgram === 'quiz' ? 'Start Quiz' :
                                 activeProgram === 'bioAgeScan' ? 'Start Bio-Scan' :
                                 activeProgram === 'shop' ? 'Take Skin Quiz' :
                                 activeProgram === 'waitlist' ? 'Join Waitlist' : 'Compare Now'}
                  />
                </div>
              </div>

              {/* Preview Link */}
              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-blue-700">
                  <Eye className="h-4 w-4" />
                  Preview your changes on the live page
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const urls = {
                      influencer: 'https://reroots.ca/influencer',
                      quiz: 'https://reroots.ca/skin-quiz',
                      bioAgeScan: 'https://reroots.ca/Bio-Age-Repair-Scan',
                      comparison: 'https://reroots.ca/compare',
                      shop: 'https://reroots.ca/shop',
                      waitlist: 'https://reroots.ca/waitlist',
                    };
                    window.open(urls[activeProgram] || 'https://reroots.ca', '_blank');
                  }}
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  View Page
                </Button>
              </div>
            </div>
          )}
          
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowPageEditor(false)}>
              Cancel
            </Button>
            <Button 
              variant="outline"
              onClick={previewPage}
              className="border-blue-300 text-blue-600 hover:bg-blue-50"
              data-testid="preview-page-btn"
            >
              <Eye className="h-4 w-4 mr-2" />
              Preview
            </Button>
            <Button 
              onClick={savePageContent} 
              disabled={savingPage}
              className="bg-[#F8A5B8] hover:bg-[#e8959a] text-white"
              data-testid="save-page-btn"
            >
              {savingPage ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Changes
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ProgramsManager;
