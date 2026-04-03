import React, { useContext, useState, useEffect, useCallback, useRef, useMemo, lazy, Suspense, useTransition } from "react";
// Import contexts from centralized location to avoid circular dependencies
import { 
  AuthContext, 
  CartContext, 
  SiteContentContext, 
  TranslationContext, 
  CurrencyContext,
  WishlistContext,
  StoreSettingsContext,
  GlobalBackgroundContext,
  TypographyContext,
  WebSocketProvider,
  BrandProvider,
  useBrand
} from "@/contexts";
import { HelmetProvider, Helmet } from "react-helmet-async";
import "@/App.css";
import "@/styles/brand-themes.css";
import { BrowserRouter, Routes, Route, Link, useNavigate, useParams, useLocation, useSearchParams, Navigate } from "react-router-dom";
import axios from "axios";
// LazyMotion - reduces framer-motion bundle by ~50% (from ~34KB to ~4.6KB)
import { LazyMotionProvider, MotionDiv, MotionButton, AnimatePresence, m } from "@/components/LazyMotionWrapper";

// Lazy load heavy page components for better performance
const CheckoutPageLazy = lazy(() => import('./components/checkout/SimpleCheckout'));
const AdminDashboardLazy = lazy(() => import('./components/pages/AdminDashboard'));
const CustomerAppLazy = lazy(() => import('./pages/CustomerApp'));
const AdminPanelLazy = lazy(() => import('./pages/AdminPanel'));
const AccountPageLazy = lazy(() => import('./components/pages/AccountPage'));
const PostPurchaseSuccessLazy = lazy(() => import('./components/product/PostPurchaseSuccess'));
const WebsiteEditorLazy = lazy(() => import('./components/pages/WebsiteEditor'));
const OffersManagerLazy = lazy(() => import('./components/admin/OffersManager'));
const CustomersManagerLazy = lazy(() => import('./components/admin/CustomersManager'));
const SubscribersSectionLazy = lazy(() => import('./components/admin/SubscribersSection'));
const AdminLayoutLazy = lazy(() => import('./components/admin/AdminLayout'));
const ExitIntentModalLazy = lazy(() => import('./components/modals/ExitIntentModal'));
const SMSCapturePopupLazy = lazy(() => import('./components/modals/SMSCapturePopup'));
const PWAInstallBannerLazy = lazy(() => import('./components/PWAInstallBanner'));
const LiveChatWidgetLazy = lazy(() => import('./components/LiveChatWidget'));
const ReferralWidgetLazy = lazy(() => import('./components/ReferralWidget'));
const VoiceAIChatLazy = lazy(() => import('./components/VoiceAIChat'));
const RerootsChatLazy = lazy(() => import('./components/RerootsChat'));
const ReferralStickyBarLazy = lazy(() => import('./components/ReferralStickyBar'));
const ReviewPageLazy = lazy(() => import('./components/pages/ReviewPage'));

// PWA Luxury App Component
const PWAAppLazy = lazy(() => import('./pwa/PWAApp'));

// Google OAuth Component for Custom Credentials
import { GoogleAuthButton } from './components/GoogleAuthButton';

import { Toaster, toast } from "sonner";
import { 
  ShoppingBag, 
  User, 
  Menu, 
  X,
  XCircle,
  AlertTriangle, 
  Plus, 
  Minus, 
  Trash2, 
  Star, 
  Check,
  CheckCircle,
  CheckCircle2,
  ChevronRight,
  Search,
  Heart,
  Instagram,
  Facebook,
  ArrowRight,
  Leaf,
  Beaker,
  Sparkles,
  FlaskConical,
  Shield,
  ShieldX,
  ShieldCheck,
  Package,
  CreditCard,
  LogOut,
  Settings,
  LayoutDashboard,
  ChevronDown,
  Edit3,
  Edit,
  Image,
  Type,
  Globe,
  Move,
  ChevronUp,
  Save,
  Eye,
  EyeOff,
  Palette,
  MessageCircle,
  Phone,
  Mail,
  Twitter,
  Users,
  Download,
  DollarSign,
  MapPin,
  ExternalLink,
  Send,
  Bot,
  Loader2,
  RotateCcw,
  Layers,
  Upload,
  ImagePlus,
  Truck,
  Clock,
  Play,
  Pause,
  RefreshCw,
  Smartphone,
  Gift,
  Copy,
  Receipt,
  Calculator,
  Bell,
  FileText,
  Trophy,
  ArrowLeft,
  Ticket,
  Tag,
  Link2,
  Award,
  BadgeCheck,
  Dna,
  Droplets,
  TestTube,
  Microscope,
  Apple,
  Share2,
  Target,
  Crown,
  TrendingUp,
  QrCode,
  Edit2,
  BarChart3
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

// DnD-kit has been fully moved to AdminDashboard.js to reduce main bundle by ~20KB
// This improves mobile TBT significantly since DnD-kit is admin-only

// Extracted page components - Lazy loaded for better performance
const BecomePartnerPage = lazy(() => import('@/components/pages/BecomePartnerPage'));
const GlobalShippingPolicyPage = lazy(() => import('@/components/pages/GlobalShippingPolicyPage'));
const InfluencerLandingPage = lazy(() => import('@/components/pages/InfluencerLandingPage'));
const InfluencerPortalPage = lazy(() => import('@/components/pages/InfluencerPortalPage'));
const SciencePage = lazy(() => import('@/components/pages/SciencePage'));
const AboutPage = lazy(() => import('@/components/pages/AboutPage'));
const HomePage = lazy(() => import('@/components/pages/HomePage'));
const WaitlistPage = lazy(() => import('@/components/pages/WaitlistPage'));
const MissionControlPage = lazy(() => import('@/components/pages/MissionControlPage'));
const ReturnPolicyPage = lazy(() => import('@/components/pages/ReturnPolicyPage'));
const PrivacyPolicyPage = lazy(() => import('@/components/pages/PrivacyPolicyPage'));
const TermsOfServicePage = lazy(() => import('@/components/pages/TermsOfServicePage'));
const BioAgeScanPage = lazy(() => import('@/components/pages/BioAgeScanPage'));
const QRGeneratorPage = lazy(() => import('@/components/pages/QRGeneratorPage'));
const ProductsPage = lazy(() => import('@/components/pages/ProductsPage'));
const ShopPage = lazy(() => import('@/components/pages/ShopPage'));
const SkincareSetsPage = lazy(() => import('@/components/pages/SkincareSetsPage'));
const FamilySkinProtocolPage = lazy(() => import('@/components/pages/FamilySkinProtocolPage'));
const ProtocolPage = lazy(() => import('@/components/pages/ProtocolPage'));
const AuraGenProtocolPage = lazy(() => import('@/components/pages/AuraGenProtocolPage'));
const AuraGenSerumProtocolPage = lazy(() => import('@/components/pages/AuraGenSerumProtocolPage'));
const AuraGenCreamProtocolPage = lazy(() => import('@/components/pages/AuraGenCreamProtocolPage'));
const SkincareDictionaryPage = lazy(() => import('@/components/pages/SkincareDictionaryPage'));
const SkinQuizPage = lazy(() => import('@/components/pages/SkinQuizPage'));
const FindYourRitualPage = lazy(() => import('@/components/pages/FindYourRitualPage'));
const LinksPage = lazy(() => import('@/components/pages/LinksPage'));
const SitemapPage = lazy(() => import('@/components/pages/SitemapPage'));
const FAQPage = lazy(() => import('@/components/pages/FAQPage'));
const PDRNComparisonPage = lazy(() => import('@/components/pages/PDRNComparisonPage'));
const ScienceGlossaryPage = lazy(() => import('@/components/pages/ScienceGlossaryPage'));
const PartnerDashboard = lazy(() => import('@/components/pages/PartnerDashboard'));
const FoundingMemberPage = lazy(() => import('@/components/pages/FoundingMemberPage'));
const ApplyPartnerPage = lazy(() => import('@/components/pages/ApplyPartnerPage'));
const CartPage = lazy(() => import('@/components/pages/CartPage'));
const LoginPage = lazy(() => import('@/components/pages/LoginPage'));
const MolecularAuditorPage = lazy(() => import('@/components/pages/MolecularAuditorPage'));
const BrandShowcase = lazy(() => import('@/components/pages/BrandShowcase'));
const ProductDetailPage = lazy(() => import('@/components/pages/ProductDetailPage'));
const ContactPage = lazy(() => import('@/components/pages/ContactPage'));
const PartnerLandingPage = lazy(() => import('@/components/pages/PartnerLandingPage'));
const PartnerChatWidget = lazy(() => import('@/components/PartnerChatWidget'));

// Gift Points Claim Page
const GiftClaimPage = lazy(() => import('@/components/pages/GiftClaimPage'));

// Commercial Dashboard for API management
const CommercialDashboard = lazy(() => import('@/pages/CommercialDashboard'));

// Owner Panel for platform control
const OwnerPanel = lazy(() => import('@/pages/OwnerPanel'));

// Subscription Plans page
const SubscriptionPlans = lazy(() => import('@/pages/SubscriptionPlans'));

// Orchestrator Command Center
const OrchestratorCommandCenter = lazy(() => import('@/pages/OrchestratorCommandCenter'));

// AI Platform (Commercial Product)
const PlatformLanding = lazy(() => import('./platform/PlatformLanding'));
const PlatformDashboard = lazy(() => import('./platform/PlatformDashboard'));
const AuremAI = lazy(() => import('./platform/AuremAI'));
const AuremLanding = lazy(() => import('./platform/AuremLanding'));
const AuremOnboarding = lazy(() => import('./platform/AuremOnboarding'));
const ZImageStudio = lazy(() => import('./platform/ZImageStudio'));
const PlatformLogin = lazy(() => import('./platform/PlatformAuth').then(mod => ({ default: mod.PlatformLogin })));
const PlatformSignup = lazy(() => import('./platform/PlatformAuth').then(mod => ({ default: mod.PlatformSignup })));
import { AuremProtectedRoute } from './platform/AuremProtectedRoute';

// Order Tracking Page
const TrackOrderPage = lazy(() => import('@/components/pages/TrackOrderPage'));

// Blog Pages
const BlogListPage = lazy(() => import('@/components/pages/BlogPage').then(mod => ({ default: mod.BlogListPage })));
const BlogPostPage = lazy(() => import('@/components/pages/BlogPage').then(mod => ({ default: mod.BlogPostPage })));

// OROÉ Luxury Brand Pages
const OroeLandingPage = lazy(() => import('./oroe/pages/OroeLandingPage'));
const OroeNewLanding = lazy(() => import('./oroe/pages/OroeNewLanding'));
const TheRitualPage = lazy(() => import('./oroe/pages/TheRitualPage'));
const PDRNSciencePage = lazy(() => import('./oroe/pages/PDRNSciencePage'));

// LA VELA BIANCA - Teen Skincare Brand Pages
const LaVelaLandingPage = lazy(() => import('./lavela/pages/LaVelaLandingPage'));
const OroRosaPage = lazy(() => import('./lavela/pages/OroRosaPage'));
const LaVelaAuthPage = lazy(() => import('./lavela/pages/LaVelaAuthPage'));
const TheLabPage = lazy(() => import('./lavela/pages/TheLabPage'));
const FounderPage = lazy(() => import('./lavela/pages/FounderPage'));
const GlowClubPage = lazy(() => import('./lavela/pages/GlowClubPage'));

// Extracted admin components - Lazy loaded for better performance
const StoreSettingsEditor = lazy(() => import('@/components/admin/StoreSettingsEditor'));
const InfluencerManager = lazy(() => import('@/components/admin/InfluencerManager'));
const DiscountCodeManager = lazy(() => import('@/components/admin/DiscountCodeManager'));
const AIContentStudio = lazy(() => import('@/components/admin/AIContentStudio'));
const PromotionsCenter = lazy(() => import('@/components/admin/PromotionsCenter'));
const FinancialsManager = lazy(() => import('@/components/admin/FinancialsManager'));
const PayrollManager = lazy(() => import('@/components/admin/PayrollManager'));

// Named exports from InfluencerManager - NOW lazy loaded for better performance
const TeamManager = lazy(() => import('@/components/admin/InfluencerManager').then(mod => ({ default: mod.TeamManager })));
const CustomerChatsManager = lazy(() => import('@/components/admin/InfluencerManager').then(mod => ({ default: mod.CustomerChatsManager })));
const AdCampaignManager = lazy(() => import('@/components/admin/InfluencerManager').then(mod => ({ default: mod.AdCampaignManager })));
// AuthCallback for OAuth flow
import { AuthCallback } from '@/components/pages/LoginPage';

// Extracted UI components - Lazy loaded for smaller initial bundle
const PromoPopup = lazy(() => import('@/components/PromoPopup'));
const ShareCard = lazy(() => import('@/components/ShareCard'));
const DualBrandBanner = lazy(() => import('@/components/DualBrandBanner'));
import { Breadcrumbs, BreadcrumbsCompact } from '@/components/Breadcrumbs';

// OROÉ Luxury Brand Admin (Lazy loaded)
const OroeCommandCenter = lazy(() => import('@/components/admin/OroeCommandCenter'));

// LA VELA BIANCA Teen Skincare Admin
const LaVelaCommandCenter = lazy(() => import('@/components/admin/LaVelaCommandCenter'));

// App Version - increment this to force PWA cache clear
const APP_VERSION = '2.0.7';

// Clear PWA Cache function - can be called from console: window.clearPWACache()
if (typeof window !== 'undefined') {
  window.clearPWACache = async () => {
    console.log('Clearing PWA cache...');
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.map(name => caches.delete(name)));
      console.log('All caches cleared:', names);
    }
    if ('serviceWorker' in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map(reg => reg.unregister()));
      console.log('Service workers unregistered');
    }
    localStorage.removeItem('pwa-installed');
    localStorage.removeItem('pwa-declined');
    console.log('PWA cache cleared! Reloading...');
    window.location.reload(true);
  };
  window.APP_VERSION = APP_VERSION;
}

// Dynamic backend URL - uses same origin for custom domains, or env variable for preview
// API URL configuration - works on all domains
// Supports: localhost, preview.emergentagent.com, and custom domains (reroots.ca)
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // For localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    
    // For custom domains (reroots.ca, etc.) - ALWAYS use same origin
    // This ensures API calls go to the correct backend regardless of env var
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    
    // For preview/staging environments, use env var if available
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    
    // Fallback to same origin
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;

// ScrollToTop component - scrolls to top on every route change
const ScrollToTop = () => {
  const { pathname } = useLocation();
  
  useEffect(() => {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'instant'
    });
  }, [pathname]);
  
  return null;
};

// Phone country code helper - auto-detect and format phone numbers
const COUNTRY_CODES = {
  'CA': { code: '+1', name: 'Canada', flag: '🇨🇦' },
  'US': { code: '+1', name: 'USA', flag: '🇺🇸' },
  'GB': { code: '+44', name: 'UK', flag: '🇬🇧' },
  'IN': { code: '+91', name: 'India', flag: '🇮🇳' },
  'AU': { code: '+61', name: 'Australia', flag: '🇦🇺' },
  'DE': { code: '+49', name: 'Germany', flag: '🇩🇪' },
  'FR': { code: '+33', name: 'France', flag: '🇫🇷' },
  'CN': { code: '+86', name: 'China', flag: '🇨🇳' },
  'JP': { code: '+81', name: 'Japan', flag: '🇯🇵' },
  'MX': { code: '+52', name: 'Mexico', flag: '🇲🇽' },
  'BR': { code: '+55', name: 'Brazil', flag: '🇧🇷' },
  'AE': { code: '+971', name: 'UAE', flag: '🇦🇪' },
  'SA': { code: '+966', name: 'Saudi Arabia', flag: '🇸🇦' },
  'PK': { code: '+92', name: 'Pakistan', flag: '🇵🇰' },
};

const formatPhoneWithCountryCode = (phone, countryCode = 'CA') => {
  if (!phone) return '';
  // Remove all non-digits
  const digits = phone.replace(/\D/g, '');
  // If already has country code (starts with +), return as is
  if (phone.startsWith('+')) return phone;
  // If number is 10 digits (North American format), add country code
  const country = COUNTRY_CODES[countryCode] || COUNTRY_CODES['CA'];
  if (digits.length === 10) {
    return `${country.code}${digits}`;
  }
  // If number is 11 digits starting with 1 (like 1XXXXXXXXXX), format with +
  if (digits.length === 11 && digits.startsWith('1')) {
    return `+${digits}`;
  }
  // Otherwise return with country code prefix
  return `${country.code}${digits}`;
};

// Universal Back Button Component
const BackButton = ({ className = "", label = "Back" }) => {
  const navigate = useNavigate();
  
  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/');
    }
  };
  
  return (
    <Button 
      variant="ghost" 
      onClick={handleBack}
      className={`flex items-center gap-2 text-[#5A5A5A] hover:text-[#2D2A2E] ${className}`}
    >
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Button>
  );
};

// SortableTab and DEFAULT_ADMIN_TABS have been moved to AdminDashboard.js
// to reduce main bundle size by ~20KB (DnD-kit is admin-only)

// Contexts are now imported from @/contexts

// Currency Provider - Multi-currency support with auto-detection
const CurrencyProvider = ({ children }) => {
  // Default to CAD for Canadian store - do not auto-detect
  const [currency, setCurrency] = useState("CAD");
  const [rates, setRates] = useState({ CAD: 1, USD: 0.74, GBP: 0.58, EUR: 0.68, AUD: 1.12, INR: 61.5 });
  const [currencies, setCurrencies] = useState({});
  const [loading, setLoading] = useState(true);

  // Fetch exchange rates on mount
  useEffect(() => {
    const fetchRates = async () => {
      try {
        const res = await axios.get(`${API}/currency/rates`);
        setRates(res.data.rates || {});
        setCurrencies(res.data.currencies || {});
        
        // Disabled auto-detection - Canadian store always uses CAD by default
        // Users can manually change currency if needed
      } catch (error) {
        console.log("Using default exchange rates");
      } finally {
        setLoading(false);
      }
    };
    fetchRates();
  }, []);

  // Convert CAD price to selected currency
  const convertPrice = useCallback((cadPrice) => {
    if (!cadPrice || isNaN(cadPrice)) return 0;
    const rate = rates[currency] || 1;
    return cadPrice * rate;
  }, [currency, rates]);

  // Format price with currency symbol
  const formatPrice = useCallback((cadPrice, options = {}) => {
    const converted = convertPrice(cadPrice);
    const currencyInfo = currencies[currency] || { symbol: "$", locale: "en-CA" };
    
    // Format based on currency
    const formatters = {
      CAD: (v) => `$${v.toFixed(2)} CAD`,
      USD: (v) => `$${v.toFixed(2)} USD`,
      GBP: (v) => `£${v.toFixed(2)}`,
      EUR: (v) => `€${v.toFixed(2)}`,
      AUD: (v) => `A$${v.toFixed(2)}`,
      INR: (v) => `₹${v.toFixed(0)}`,
    };
    
    const formatter = formatters[currency] || ((v) => `$${v.toFixed(2)} ${currency}`);
    return formatter(converted);
  }, [convertPrice, currency, currencies]);

  // Change currency
  const changeCurrency = useCallback((newCurrency) => {
    if (rates[newCurrency]) {
      setCurrency(newCurrency);
      localStorage.setItem("reroots_currency", newCurrency);
    }
  }, [rates]);

  const value = {
    currency,
    rates,
    currencies,
    loading,
    convertPrice,
    formatPrice,
    changeCurrency,
    availableCurrencies: Object.keys(rates)
  };

  return (
    <CurrencyContext.Provider value={value}>
      {children}
    </CurrencyContext.Provider>
  );
};

const useCurrency = () => {
  const context = useContext(CurrencyContext);
  if (!context) {
    // Return fallback for non-wrapped components
    return {
      currency: "CAD",
      formatPrice: (price) => `$${(price || 0).toFixed(2)} CAD`,
      convertPrice: (price) => price,
      changeCurrency: () => {},
      availableCurrencies: ["CAD"]
    };
  }
  return context;
};

// WishlistContext is imported from @/contexts

const WishlistProvider = ({ children }) => {
  const [wishlist, setWishlist] = useState([]);
  const [loading, setLoading] = useState(false);
  const { user } = useAuth();

  // Load wishlist when user logs in and process any pending wishlist add
  useEffect(() => {
    if (user) {
      fetchWishlist();
      // Process pending wishlist add from before login
      const pendingProductId = sessionStorage.getItem('pendingWishlistAdd');
      if (pendingProductId) {
        sessionStorage.removeItem('pendingWishlistAdd');
        // Delay to ensure token is set properly
        setTimeout(async () => {
          try {
            const token = localStorage.getItem("reroots_token");
            await axios.post(`${API}/wishlist/${pendingProductId}`, {}, {
              headers: { Authorization: `Bearer ${token}` }
            });
            fetchWishlist();
            toast.success("Added to wishlist ❤️");
          } catch (error) {
            console.log("Failed to add pending wishlist item:", error);
          }
        }, 500);
      }
    } else {
      setWishlist([]);
    }
  }, [user]);

  const fetchWishlist = async () => {
    if (!user) return;
    try {
      const token = localStorage.getItem("reroots_token");
      const res = await axios.get(`${API}/wishlist`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWishlist(res.data.items || []);
    } catch (error) {
      console.log("Failed to fetch wishlist");
    }
  };

  const addToWishlist = async (productId) => {
    if (!user) {
      toast.error("Please login to add items to wishlist");
      // Store the intended action and redirect to login
      sessionStorage.setItem('redirectAfterLogin', window.location.pathname);
      sessionStorage.setItem('pendingWishlistAdd', productId);
      window.location.href = '/login';
      return false;
    }
    try {
      setLoading(true);
      const token = localStorage.getItem("reroots_token");
      await axios.post(`${API}/wishlist/${productId}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      await fetchWishlist();
      toast.success("Added to wishlist ❤️");
      return true;
    } catch (error) {
      if (error.response?.status === 401) {
        toast.error("Please login to add items to wishlist");
        sessionStorage.setItem('redirectAfterLogin', window.location.pathname);
        window.location.href = '/login';
      } else {
        toast.error("Failed to add to wishlist");
      }
      return false;
    } finally {
      setLoading(false);
    }
  };

  const removeFromWishlist = async (productId) => {
    try {
      setLoading(true);
      const token = localStorage.getItem("reroots_token");
      await axios.delete(`${API}/wishlist/${productId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setWishlist(prev => prev.filter(item => item.product_id !== productId));
      toast.success("Removed from wishlist");
      return true;
    } catch (error) {
      toast.error("Failed to remove from wishlist");
      return false;
    } finally {
      setLoading(false);
    }
  };

  const isInWishlist = (productId) => {
    return wishlist.some(item => item.product_id === productId);
  };

  const toggleWishlist = async (productId) => {
    if (isInWishlist(productId)) {
      return removeFromWishlist(productId);
    } else {
      return addToWishlist(productId);
    }
  };

  return (
    <WishlistContext.Provider value={{
      wishlist,
      loading,
      addToWishlist,
      removeFromWishlist,
      isInWishlist,
      toggleWishlist,
      wishlistCount: wishlist.length
    }}>
      {children}
    </WishlistContext.Provider>
  );
};

const useWishlist = () => {
  const context = useContext(WishlistContext);
  return context || { wishlist: [], isInWishlist: () => false, toggleWishlist: () => {}, wishlistCount: 0 };
};

// Recently Viewed Hook (session-based)
const useRecentlyViewed = () => {
  const [recentlyViewed, setRecentlyViewed] = useState([]);
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("reroots_session");
    if (existing) return existing;
    const id = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("reroots_session", id);
    return id;
  });

  const trackView = async (productId) => {
    try {
      await axios.post(`${API}/recently-viewed/${productId}?session_id=${sessionId}`);
    } catch (error) {
      console.log("Failed to track view");
    }
  };

  const fetchRecentlyViewed = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/recently-viewed?session_id=${sessionId}`);
      setRecentlyViewed(res.data.products || []);
    } catch (error) {
      console.log("Failed to fetch recently viewed");
    }
  }, [sessionId]);

  useEffect(() => {
    fetchRecentlyViewed();
  }, [fetchRecentlyViewed]);

  return { recentlyViewed, trackView, fetchRecentlyViewed };
};

// Currency Selector Component
const CurrencySelector = ({ scrolled = true }) => {
  const { currency, changeCurrency, currencies, availableCurrencies } = useCurrency();
  
  const currencyFlags = {
    CAD: "🇨🇦", USD: "🇺🇸", GBP: "🇬🇧", EUR: "🇪🇺", AUD: "🇦🇺", INR: "🇮🇳"
  };
  
  const currencyNames = {
    CAD: "CAD - Canadian Dollar",
    USD: "USD - US Dollar", 
    GBP: "GBP - British Pound",
    EUR: "EUR - Euro",
    AUD: "AUD - Australian Dollar",
    INR: "INR - Indian Rupee"
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1 px-2 transition-all hover:bg-gray-100" data-testid="currency-selector">
          <span className="text-sm">{currencyFlags[currency] || "💰"}</span>
          <span className="text-xs font-medium text-black">{currency}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <div className="px-2 py-1.5 text-xs text-[#5A5A5A] border-b">Select Currency</div>
        {availableCurrencies.map(curr => (
          <DropdownMenuItem 
            key={curr} 
            onClick={() => changeCurrency(curr)}
            className={currency === curr ? "bg-[#F8A5B8]/10" : ""}
          >
            <span className="mr-2">{currencyFlags[curr]}</span> 
            {currencyNames[curr] || curr}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

// Recently Viewed Section Component
const RecentlyViewedSection = () => {
  const { recentlyViewed } = useRecentlyViewed();
  const { formatPrice } = useCurrency();
  const { addToCart } = useCart();
  
  if (!recentlyViewed.length) return null;

  return (
    <section className="py-16 bg-white">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Clock className="h-6 w-6 text-[#F8A5B8]" />
            <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Recently Viewed</h2>
          </div>
          <Link to="/shop" className="text-sm text-[#5A5A5A] hover:text-[#F8A5B8] transition-colors">
            View All Products →
          </Link>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {recentlyViewed.slice(0, 5).map(product => {
            const effectivePrice = product.discount_percent 
              ? product.price * (1 - product.discount_percent / 100) 
              : product.price;
            
            return (
              <Link 
                key={product.id} 
                to={`/products/${product.slug || product.id}`}
                className="group"
              >
                <div className="aspect-square relative overflow-hidden bg-[#F5F5F3] rounded-lg mb-2">
                  <img
                    src={product.images?.[0] || "https://via.placeholder.com/200"}
                    alt={product.name}
                    loading="lazy"
                    decoding="async"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                  {product.discount_percent > 0 && (
                    <Badge className="absolute top-2 left-2 bg-[#F8A5B8] text-xs">
                      {product.discount_percent}% OFF
                    </Badge>
                  )}
                </div>
                <h3 className="font-medium text-sm text-[#2D2A2E] group-hover:text-[#F8A5B8] line-clamp-1 transition-colors">
                  {product.name}
                </h3>
                <p className="font-bold text-sm text-[#F8A5B8]">{formatPrice(effectivePrice)}</p>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
};

// Persistent translation cache using localStorage
const getTranslationCache = () => {
  try {
    return JSON.parse(localStorage.getItem("reroots_translations") || "{}");
  } catch {
    return {};
  }
};

const saveTranslationCache = (cache) => {
  try {
    // Keep only last 500 translations to avoid storage issues
    const keys = Object.keys(cache);
    if (keys.length > 500) {
      const newCache = {};
      keys.slice(-500).forEach(k => newCache[k] = cache[k]);
      localStorage.setItem("reroots_translations", JSON.stringify(newCache));
    } else {
      localStorage.setItem("reroots_translations", JSON.stringify(cache));
    }
  } catch {}
};

// Translation Provider - Optimized for speed
const TranslationProvider = ({ children }) => {
  const [currentLang, setCurrentLang] = useState(localStorage.getItem("reroots_lang") || "en-CA");
  const [translationCache, setTranslationCache] = useState(getTranslationCache);
  const pendingTranslations = useRef({});
  const batchTimeout = useRef(null);

  // Get cached translation immediately (sync)
  const getCached = useCallback((text, lang) => {
    const key = `${lang}:${text}`;
    return translationCache[key] || UI_TRANSLATIONS[lang]?.[text];
  }, [translationCache]);

  // Translate single text with caching
  const translateText = useCallback(async (text, targetLang = currentLang) => {
    if (!text || targetLang === "en" || targetLang === "en-US" || targetLang === "en-CA") return text;
    
    const key = `${targetLang}:${text}`;
    if (translationCache[key]) return translationCache[key];
    
    try {
      const res = await axios.post(`${API}/translate`, { text, target_lang: targetLang });
      const translated = res.data.translated;
      setTranslationCache(prev => {
        const updated = { ...prev, [key]: translated };
        saveTranslationCache(updated);
        return updated;
      });
      return translated;
    } catch {
      return text;
    }
  }, [currentLang, translationCache]);

  // Optimized batch translation with deduplication
  const translateBatch = useCallback(async (texts, targetLang = currentLang) => {
    if (!texts?.length || targetLang === "en" || targetLang === "en-US") return texts;
    
    const results = [];
    const uncachedTexts = [];
    const uncachedIndices = [];
    
    // Check cache first
    texts.forEach((text, idx) => {
      const key = `${targetLang}:${text}`;
      if (translationCache[key]) {
        results[idx] = translationCache[key];
      } else {
        uncachedTexts.push(text);
        uncachedIndices.push(idx);
        results[idx] = text; // Show original while loading
      }
    });
    
    if (uncachedTexts.length === 0) return results;
    
    try {
      const res = await axios.post(`${API}/translate/batch`, {
        texts: uncachedTexts,
        target_lang: targetLang
      });
      const translations = res.data.translations || uncachedTexts;
      
      const newCache = { ...translationCache };
      uncachedIndices.forEach((resultIdx, i) => {
        const key = `${targetLang}:${uncachedTexts[i]}`;
        newCache[key] = translations[i];
        results[resultIdx] = translations[i];
      });
      
      setTranslationCache(newCache);
      saveTranslationCache(newCache);
      return results;
    } catch {
      return texts;
    }
  }, [currentLang, translationCache]);

  const translateChatForAdmin = useCallback(async (message) => {
    try {
      const res = await axios.post(`${API}/translate/chat`, { message, to_admin: true });
      return res.data;
    } catch {
      return { translated: message, detected_lang: "en" };
    }
  }, []);

  const changeLang = useCallback((lang) => {
    setCurrentLang(lang);
    localStorage.setItem("reroots_lang", lang);
  }, []);

  return (
    <TranslationContext.Provider value={{ 
      currentLang, 
      setCurrentLang: changeLang,
      translateText, 
      translateBatch,
      translateChatForAdmin,
      getCached,
      translating: false 
    }}>
      {children}
    </TranslationContext.Provider>
  );
};

const useTranslation = () => useContext(TranslationContext);

// Simple Text Component - Uses pre-defined UI translations (instant, no API call)
const T = ({ children, as: Component = "span", className = "" }) => {
  const { currentLang } = useTranslation() || {};
  const lang = currentLang || "en";
  // Use pre-defined translations for common UI text
  const translated = UI_TRANSLATIONS[lang]?.[children] || UI_TRANSLATIONS.en?.[children] || children;
  return <Component className={className}>{translated}</Component>;
};

// Hook for UI text (instant, no API call)
const useT = (text) => {
  const { currentLang } = useTranslation() || {};
  const lang = currentLang || "en";
  return UI_TRANSLATIONS[lang]?.[text] || UI_TRANSLATIONS.en?.[text] || text;
};

// Hook for translating product data - OPTIMIZED: only translates on demand
const useTranslatedProduct = (product) => {
  const { currentLang, translateBatch } = useTranslation() || {};
  const [translatedProduct, setTranslatedProduct] = useState(product);
  const translationRef = useRef(null);
  
  useEffect(() => {
    if (!product) {
      setTranslatedProduct(null);
      return;
    }
    
    // For English, use original product immediately
    if (!currentLang || currentLang === "en" || currentLang === "en-US" || !translateBatch) {
      setTranslatedProduct(product);
      return;
    }
    
    // Show original first (instant), then translate in background
    setTranslatedProduct(product);
    
    // Debounce translation to prevent too many calls
    if (translationRef.current) clearTimeout(translationRef.current);
    
    translationRef.current = setTimeout(async () => {
      const textsToTranslate = [
        product.name || "",
        product.short_description || ""
      ].filter(t => t.length > 0);
      
      if (textsToTranslate.length === 0) return;
      
      try {
        const translations = await translateBatch(textsToTranslate, currentLang);
        let idx = 0;
        setTranslatedProduct({
          ...product,
          name: product.name ? translations[idx++] : product.name,
          short_description: product.short_description ? translations[idx++] : product.short_description
        });
      } catch {}
    }, 300); // 300ms debounce
    
    return () => {
      if (translationRef.current) clearTimeout(translationRef.current);
    };
  }, [product?.id, currentLang]); // Only re-run when product ID or language changes
  
  return translatedProduct;
};

// Hook for translating multiple products - OPTIMIZED
const useTranslatedProducts = (products) => {
  const { currentLang, translateBatch } = useTranslation() || {};
  const [translatedProducts, setTranslatedProducts] = useState(products);
  const translationRef = useRef(null);
  
  useEffect(() => {
    if (!products?.length) {
      setTranslatedProducts([]);
      return;
    }
    
    if (!currentLang || currentLang === "en" || currentLang === "en-US" || !translateBatch) {
      setTranslatedProducts(products);
      return;
    }
    
    // Show original first
    setTranslatedProducts(products);
    
    // Debounce translation
    if (translationRef.current) clearTimeout(translationRef.current);
    
    translationRef.current = setTimeout(async () => {
      const allTexts = [];
      const textMap = [];
      
      products.forEach((product, pIdx) => {
        if (product.name) {
          allTexts.push(product.name);
          textMap.push({ pIdx, field: 'name' });
        }
        if (product.short_description) {
          allTexts.push(product.short_description);
          textMap.push({ pIdx, field: 'short_description' });
        }
      });
      
      if (allTexts.length === 0) return;
      
      try {
        const translations = await translateBatch(allTexts, currentLang);
        const newProducts = products.map(p => ({...p}));
        
        textMap.forEach((mapping, idx) => {
          if (newProducts[mapping.pIdx]) {
            newProducts[mapping.pIdx][mapping.field] = translations[idx] || newProducts[mapping.pIdx][mapping.field];
          }
        });
        
        setTranslatedProducts(newProducts);
      } catch {}
    }, 300);
    
    return () => {
      if (translationRef.current) clearTimeout(translationRef.current);
    };
  }, [products?.length, currentLang]);
  
  return translatedProducts;
};

// Pre-defined translations for common UI elements
const UI_TRANSLATIONS = {
  // Canadian English - DEFAULT
  "en-CA": {
    shop_now: "SHOP NOW",
    learn_more: "LEARN MORE",
    add_to_cart: "Add to Cart",
    subscribe: "Subscribe",
    premium_skincare: "PREMIUM SKINCARE",
    transform_your_skin: "Transform Your Skin",
    hero_subtitle: "Science-backed formulas for radiant, healthy skin",
    view_product: "View Product",
    featured_products: "Featured Products",
    our_products: "Our Products",
    all_products: "All Products",
    products: "products",
    shop_all: "Shop All",
    join_community: "Join the ReRoots Community",
    newsletter_desc: "Get exclusive offers, skincare tips, and new product alerts",
    email_placeholder: "Enter your email",
    cart: "Cart",
    your_cart: "Your Cart",
    cart_empty: "Your cart is empty",
    continue_shopping: "Continue Shopping",
    checkout: "Checkout",
    proceed_checkout: "Proceed to Checkout",
    total: "Total",
    subtotal: "Subtotal",
    shipping: "Shipping",
    tax: "Tax",
    free: "FREE",
    home: "Home",
    shop: "Shop",
    about: "About",
    contact: "Contact",
    login: "Login",
    account: "Account",
    logout: "Logout",
    quantity: "Quantity",
    in_stock: "In Stock",
    out_of_stock: "Out of Stock",
    reviews: "reviews",
    write_review: "Write a Review",
    ingredients: "Ingredients",
    how_to_use: "How to Use",
    bestseller: "Bestseller",
    new_arrival: "New",
    sale: "Sale",
    thanks_subscribing: "Thanks for subscribing!",
    customer_reviews: "Customer Reviews",
    no_products: "No products found.",
    product_not_found: "Product not found",
    testimonials: "Testimonials",
    what_customers_say: "What Our Customers Say",
    view_all: "View All",
    discover_collection: "Discover our biotech skincare collection.",
    pre_order: "Pre-Order",
    pre_order_now: "Pre-Order Now",
    pre_order_item: "Pre-Order Item",
    available_on: "Available on",
    ships_soon: "Ships in 2-3 weeks after release",
    // Login page
    welcome_back: "Welcome Back,",
    esteemed_client: "Our Esteemed Client.",
    email: "Email",
    password: "Password",
    sign_in: "SIGN IN",
    signing_in: "Signing In...",
    dont_have_account: "Don't have an account?",
    join_community_link: "Join our exclusive community",
    already_have_account: "Already have an account?",
    sign_in_link: "Sign In",
    create_account: "Create Account",
    creating_account: "Creating Account...",
    first_name: "First Name",
    last_name: "Last Name",
    confirm_password: "Confirm Password",
    forgot_password: "Forgot Password?",
    forgot_password_title: "Forgot Your",
    password_word: "Password?",
    forgot_password_desc: "Enter your email and we'll send you a reset link.",
    send_reset_link: "Send Reset Link",
    sending: "Sending...",
    back_to_login: "Back to Login",
    check_email: "Check Your Email",
    check_email_desc: "We've sent a password reset link to your email address.",
    didnt_receive: "Didn't receive the email? Check your spam folder or",
    try_again: "try again",
    create_new_password: "Create New",
    new_password: "New Password",
    password_min_chars: "Password must be at least 8 characters long",
    resetting: "Resetting...",
    reset_password: "Reset Password",
    invalid_link: "Invalid or Expired Link",
    invalid_link_desc: "This password reset link is invalid or has expired. Please request a new one.",
    request_new_link: "Request New Link",
    // Admin Interface
    admin_dashboard: "Admin Dashboard",
    manage_store: "Manage your ReRoots skincare store",
    orders: "Orders",
    customers: "Customers",
    subscriptions: "Subscriptions",
    ads: "Ads",
    team: "Team",
    settings: "Settings",
    store_settings: "Store Settings",
    payment_settings: "Payment Settings",
    live_chat: "Live Chat",
    language_region: "Language & Region",
    thank_you_messages: "Thank You Messages",
    website_settings: "Website Settings",
    add_product: "Add Product",
    edit_product: "Edit Product",
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    search: "Search",
    filter: "Filter",
    all: "All",
    active: "Active",
    inactive: "Inactive",
    pending: "Pending",
    completed: "Completed",
    processing: "Processing",
    shipped: "Shipped",
    delivered: "Delivered",
    cancelled: "Cancelled",
    total_products: "Total Products",
    total_orders: "Total Orders",
    total_customers: "Total Customers",
    total_revenue: "Total Revenue",
    recent_orders: "Recent Orders",
    ai_chat: "AI Chat",
    order: "Order",
    customer: "Customer",
    status: "Status",
    categories: "Categories",
    sections: "Sections",
    typography: "Typography",
    overview: "Overview"
  },
  en: {
    shop_now: "SHOP NOW",
    learn_more: "LEARN MORE",
    add_to_cart: "Add to Cart",
    subscribe: "Subscribe",
    premium_skincare: "PREMIUM SKINCARE",
    transform_your_skin: "Transform Your Skin",
    hero_subtitle: "Science-backed formulas for radiant, healthy skin",
    view_product: "View Product",
    featured_products: "Featured Products",
    our_products: "Our Products",
    all_products: "All Products",
    products: "products",
    shop_all: "Shop All",
    join_community: "Join the ReRoots Community",
    newsletter_desc: "Get exclusive offers, skincare tips, and new product alerts",
    email_placeholder: "Enter your email",
    cart: "Cart",
    your_cart: "Your Cart",
    cart_empty: "Your cart is empty",
    continue_shopping: "Continue Shopping",
    checkout: "Checkout",
    proceed_checkout: "Proceed to Checkout",
    total: "Total",
    subtotal: "Subtotal",
    shipping: "Shipping",
    tax: "Tax",
    free: "FREE",
    home: "Home",
    shop: "Shop",
    about: "About",
    login: "Login",
    account: "Account",
    logout: "Logout",
    quantity: "Quantity",
    in_stock: "In Stock",
    out_of_stock: "Out of Stock",
    reviews: "Reviews",
    write_review: "Write a Review",
    ingredients: "Ingredients",
    how_to_use: "How to Use",
    bestseller: "Bestseller",
    new_arrival: "New",
    sale: "Sale",
    thanks_subscribing: "Thanks for subscribing!",
    customer_reviews: "Customer Reviews",
    no_products: "No products found.",
    product_not_found: "Product not found",
    testimonials: "Testimonials",
    what_customers_say: "What Our Customers Say",
    view_all: "View All",
    order_summary: "Order Summary",
    discover_collection: "Discover our biotech skincare collection.",
    pre_order: "Pre-Order",
    pre_order_now: "Pre-Order Now",
    pre_order_item: "Pre-Order Item",
    available_on: "Available on",
    ships_soon: "Ships in 2-3 weeks after release",
    // Login page
    welcome_back: "Welcome Back,",
    esteemed_client: "Our Esteemed Client.",
    email: "Email",
    password: "Password",
    sign_in: "SIGN IN",
    signing_in: "Signing In...",
    dont_have_account: "Don't have an account?",
    join_community_link: "Join our exclusive community",
    already_have_account: "Already have an account?",
    sign_in_link: "Sign In",
    create_account: "Create Account",
    creating_account: "Creating Account...",
    first_name: "First Name",
    last_name: "Last Name",
    confirm_password: "Confirm Password",
    forgot_password: "Forgot Password?",
    forgot_password_title: "Forgot Your",
    password_word: "Password?",
    forgot_password_desc: "Enter your email and we'll send you a reset link.",
    send_reset_link: "Send Reset Link",
    sending: "Sending...",
    back_to_login: "Back to Login",
    check_email: "Check Your Email",
    check_email_desc: "We've sent a password reset link to your email address.",
    didnt_receive: "Didn't receive the email? Check your spam folder or",
    try_again: "try again",
    create_new_password: "Create New",
    new_password: "New Password",
    password_min_chars: "Password must be at least 8 characters long",
    resetting: "Resetting...",
    reset_password: "Reset Password",
    invalid_link: "Invalid or Expired Link",
    invalid_link_desc: "This password reset link is invalid or has expired. Please request a new one.",
    request_new_link: "Request New Link",
    // Admin Interface
    admin_dashboard: "Admin Dashboard",
    manage_store: "Manage your ReRoots skincare store",
    products: "Products",
    orders: "Orders",
    customers: "Customers",
    reviews: "Reviews",
    subscriptions: "Subscriptions",
    ads: "Ads",
    team: "Team",
    settings: "Settings",
    store_settings: "Store Settings",
    payment_settings: "Payment Settings",
    live_chat: "Live Chat",
    language_region: "Language & Region",
    thank_you_messages: "Thank You Messages",
    website_settings: "Website Settings",
    add_product: "Add Product",
    edit_product: "Edit Product",
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    search: "Search",
    filter: "Filter",
    all: "All",
    active: "Active",
    inactive: "Inactive",
    pending: "Pending",
    completed: "Completed",
    processing: "Processing",
    shipped: "Shipped",
    delivered: "Delivered",
    cancelled: "Cancelled",
    total_products: "Total Products",
    total_orders: "Total Orders",
    total_customers: "Total Customers",
    total_revenue: "Total Revenue",
    recent_orders: "Recent Orders",
    view_all: "View All",
    logout: "Logout",
    ai_chat: "AI Chat",
    // Additional admin translations
    order: "Order",
    customer: "Customer",
    status: "Status",
    total: "Total",
    categories: "Categories",
    sections: "Sections",
    typography: "Typography",
    overview: "Overview"
  },
  "en-US": {
    shop_now: "SHOP NOW",
    learn_more: "LEARN MORE",
    add_to_cart: "Add to Cart",
    subscribe: "Subscribe",
    premium_skincare: "PREMIUM SKINCARE",
    transform_your_skin: "Transform Your Skin",
    hero_subtitle: "Science-backed formulas for radiant, healthy skin",
    view_product: "View Product",
    featured_products: "Featured Products",
    our_products: "Our Products",
    all_products: "All Products",
    products: "products",
    shop_all: "Shop All",
    join_community: "Join the ReRoots Community",
    newsletter_desc: "Get exclusive offers, skincare tips, and new product alerts",
    email_placeholder: "Enter your email",
    cart: "Cart",
    your_cart: "Your Cart",
    cart_empty: "Your cart is empty",
    continue_shopping: "Continue Shopping",
    checkout: "Checkout",
    proceed_checkout: "Proceed to Checkout",
    total: "Total",
    subtotal: "Subtotal",
    shipping: "Shipping",
    tax: "Tax",
    free: "FREE",
    home: "Home",
    shop: "Shop",
    about: "About",
    login: "Login",
    account: "Account",
    logout: "Logout",
    quantity: "Quantity",
    in_stock: "In Stock",
    out_of_stock: "Out of Stock",
    reviews: "Reviews",
    write_review: "Write a Review",
    ingredients: "Ingredients",
    how_to_use: "How to Use",
    bestseller: "Bestseller",
    new_arrival: "New",
    sale: "Sale",
    thanks_subscribing: "Thanks for subscribing!",
    customer_reviews: "Customer Reviews",
    no_products: "No products found.",
    product_not_found: "Product not found",
    testimonials: "Testimonials",
    what_customers_say: "What Our Customers Say",
    view_all: "View All",
    order_summary: "Order Summary",
    discover_collection: "Discover our biotech skincare collection.",
    pre_order: "Pre-Order",
    pre_order_now: "Pre-Order Now",
    pre_order_item: "Pre-Order Item",
    available_on: "Available on",
    ships_soon: "Ships in 2-3 weeks after release",
    // Login page
    welcome_back: "Welcome Back,",
    esteemed_client: "Our Esteemed Client.",
    email: "Email",
    password: "Password",
    sign_in: "SIGN IN",
    signing_in: "Signing In...",
    dont_have_account: "Don't have an account?",
    join_community_link: "Join our exclusive community",
    already_have_account: "Already have an account?",
    sign_in_link: "Sign In",
    create_account: "Create Account",
    creating_account: "Creating Account...",
    first_name: "First Name",
    last_name: "Last Name",
    confirm_password: "Confirm Password",
    forgot_password: "Forgot Password?",
    forgot_password_title: "Forgot Your",
    password_word: "Password?",
    forgot_password_desc: "Enter your email and we'll send you a reset link.",
    send_reset_link: "Send Reset Link",
    sending: "Sending...",
    back_to_login: "Back to Login",
    check_email: "Check Your Email",
    check_email_desc: "We've sent a password reset link to your email address.",
    didnt_receive: "Didn't receive the email? Check your spam folder or",
    try_again: "try again",
    create_new_password: "Create New",
    new_password: "New Password",
    password_min_chars: "Password must be at least 8 characters long",
    resetting: "Resetting...",
    reset_password: "Reset Password",
    invalid_link: "Invalid or Expired Link",
    invalid_link_desc: "This password reset link is invalid or has expired. Please request a new one.",
    request_new_link: "Request New Link"
  },
  pa: {
    shop_now: "ਹੁਣੇ ਖਰੀਦੋ",
    learn_more: "ਹੋਰ ਜਾਣੋ",
    add_to_cart: "ਕਾਰਟ ਵਿੱਚ ਪਾਓ",
    subscribe: "ਸਬਸਕ੍ਰਾਈਬ ਕਰੋ",
    premium_skincare: "ਪ੍ਰੀਮੀਅਮ ਸਕਿਨਕੇਅਰ",
    transform_your_skin: "ਆਪਣੀ ਚਮੜੀ ਨੂੰ ਬਦਲੋ",
    hero_subtitle: "ਚਮਕਦਾਰ, ਸਿਹਤਮੰਦ ਚਮੜੀ ਲਈ ਵਿਗਿਆਨਕ ਫਾਰਮੂਲੇ",
    view_product: "ਉਤਪਾਦ ਵੇਖੋ",
    featured_products: "ਵਿਸ਼ੇਸ਼ ਉਤਪਾਦ",
    our_products: "ਸਾਡੇ ਉਤਪਾਦ",
    all_products: "ਸਾਰੇ ਉਤਪਾਦ",
    products: "ਉਤਪਾਦ",
    shop_all: "ਸਭ ਖਰੀਦੋ",
    join_community: "ReRoots ਕਮਿਊਨਿਟੀ ਨਾਲ ਜੁੜੋ",
    newsletter_desc: "ਵਿਸ਼ੇਸ਼ ਪੇਸ਼ਕਸ਼ਾਂ, ਸਕਿਨਕੇਅਰ ਟਿਪਸ, ਅਤੇ ਨਵੇਂ ਉਤਪਾਦਾਂ ਦੀ ਜਾਣਕਾਰੀ ਪ੍ਰਾਪਤ ਕਰੋ",
    email_placeholder: "ਆਪਣੀ ਈਮੇਲ ਦਰਜ ਕਰੋ",
    cart: "ਕਾਰਟ",
    your_cart: "ਤੁਹਾਡੀ ਕਾਰਟ",
    cart_empty: "ਤੁਹਾਡੀ ਕਾਰਟ ਖਾਲੀ ਹੈ",
    continue_shopping: "ਖਰੀਦਦਾਰੀ ਜਾਰੀ ਰੱਖੋ",
    checkout: "ਚੈੱਕਆਊਟ",
    proceed_checkout: "ਚੈੱਕਆਊਟ ਲਈ ਅੱਗੇ ਵਧੋ",
    total: "ਕੁੱਲ",
    subtotal: "ਉਪ-ਜੋੜ",
    shipping: "ਸ਼ਿਪਿੰਗ",
    tax: "ਟੈਕਸ",
    free: "ਮੁਫ਼ਤ",
    home: "ਹੋਮ",
    shop: "ਦੁਕਾਨ",
    about: "ਸਾਡੇ ਬਾਰੇ",
    login: "ਲੌਗਇਨ",
    account: "ਖਾਤਾ",
    logout: "ਲੌਗਆਊਟ",
    quantity: "ਮਾਤਰਾ",
    in_stock: "ਸਟਾਕ ਵਿੱਚ",
    out_of_stock: "ਸਟਾਕ ਖਤਮ",
    reviews: "ਸਮੀਖਿਆਵਾਂ",
    write_review: "ਸਮੀਖਿਆ ਲਿਖੋ",
    ingredients: "ਸਮੱਗਰੀ",
    how_to_use: "ਕਿਵੇਂ ਵਰਤਣਾ ਹੈ",
    bestseller: "ਬੈਸਟਸੈਲਰ",
    new_arrival: "ਨਵਾਂ",
    sale: "ਸੇਲ",
    thanks_subscribing: "ਸਬਸਕ੍ਰਾਈਬ ਕਰਨ ਲਈ ਧੰਨਵਾਦ!",
    customer_reviews: "ਗਾਹਕ ਸਮੀਖਿਆਵਾਂ",
    no_products: "ਕੋਈ ਉਤਪਾਦ ਨਹੀਂ ਮਿਲਿਆ।",
    product_not_found: "ਉਤਪਾਦ ਨਹੀਂ ਮਿਲਿਆ",
    testimonials: "ਸ਼ਹਾਦਤਾਂ",
    what_customers_say: "ਸਾਡੇ ਗਾਹਕ ਕੀ ਕਹਿੰਦੇ ਹਨ",
    view_all: "ਸਭ ਵੇਖੋ",
    pre_order: "ਪ੍ਰੀ-ਆਰਡਰ",
    pre_order_now: "ਹੁਣੇ ਪ੍ਰੀ-ਆਰਡਰ ਕਰੋ",
    pre_order_item: "ਪ੍ਰੀ-ਆਰਡਰ ਆਈਟਮ",
    available_on: "ਉਪਲਬਧ ਤਾਰੀਖ",
    ships_soon: "ਰਿਲੀਜ਼ ਤੋਂ 2-3 ਹਫ਼ਤਿਆਂ ਬਾਅਦ ਸ਼ਿਪ ਕੀਤੀ ਜਾਵੇਗੀ",
    // Login page
    welcome_back: "ਵਾਪਸ ਸਵਾਗਤ ਹੈ,",
    esteemed_client: "ਸਾਡੇ ਸਤਿਕਾਰਤ ਗਾਹਕ।",
    email: "ਈਮੇਲ",
    password: "ਪਾਸਵਰਡ",
    sign_in: "ਸਾਈਨ ਇਨ ਕਰੋ",
    signing_in: "ਸਾਈਨ ਇਨ ਹੋ ਰਿਹਾ ਹੈ...",
    dont_have_account: "ਖਾਤਾ ਨਹੀਂ ਹੈ?",
    join_community_link: "ਸਾਡੀ ਵਿਸ਼ੇਸ਼ ਕਮਿਊਨਿਟੀ ਨਾਲ ਜੁੜੋ",
    already_have_account: "ਪਹਿਲਾਂ ਹੀ ਖਾਤਾ ਹੈ?",
    sign_in_link: "ਸਾਈਨ ਇਨ ਕਰੋ",
    create_account: "ਖਾਤਾ ਬਣਾਓ",
    creating_account: "ਖਾਤਾ ਬਣ ਰਿਹਾ ਹੈ...",
    first_name: "ਪਹਿਲਾ ਨਾਮ",
    last_name: "ਆਖਰੀ ਨਾਮ",
    confirm_password: "ਪਾਸਵਰਡ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ",
    forgot_password: "ਪਾਸਵਰਡ ਭੁੱਲ ਗਏ?",
    forgot_password_title: "ਆਪਣਾ",
    password_word: "ਪਾਸਵਰਡ ਭੁੱਲ ਗਏ?",
    forgot_password_desc: "ਆਪਣੀ ਈਮੇਲ ਦਰਜ ਕਰੋ ਅਤੇ ਅਸੀਂ ਤੁਹਾਨੂੰ ਰੀਸੈਟ ਲਿੰਕ ਭੇਜਾਂਗੇ।",
    send_reset_link: "ਰੀਸੈਟ ਲਿੰਕ ਭੇਜੋ",
    sending: "ਭੇਜ ਰਿਹਾ ਹੈ...",
    back_to_login: "ਲੌਗਇਨ ਤੇ ਵਾਪਸ ਜਾਓ",
    check_email: "ਆਪਣੀ ਈਮੇਲ ਚੈੱਕ ਕਰੋ",
    check_email_desc: "ਅਸੀਂ ਤੁਹਾਡੀ ਈਮੇਲ ਤੇ ਪਾਸਵਰਡ ਰੀਸੈਟ ਲਿੰਕ ਭੇਜ ਦਿੱਤਾ ਹੈ।",
    didnt_receive: "ਈਮੇਲ ਨਹੀਂ ਮਿਲੀ? ਆਪਣਾ ਸਪੈਮ ਫੋਲਡਰ ਚੈੱਕ ਕਰੋ ਜਾਂ",
    try_again: "ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ",
    create_new_password: "ਨਵਾਂ",
    new_password: "ਨਵਾਂ ਪਾਸਵਰਡ",
    password_min_chars: "ਪਾਸਵਰਡ ਘੱਟੋ-ਘੱਟ 8 ਅੱਖਰਾਂ ਦਾ ਹੋਣਾ ਚਾਹੀਦਾ ਹੈ",
    resetting: "ਰੀਸੈਟ ਹੋ ਰਿਹਾ ਹੈ...",
    reset_password: "ਪਾਸਵਰਡ ਰੀਸੈਟ ਕਰੋ",
    invalid_link: "ਅਵੈਧ ਜਾਂ ਮਿਆਦ ਪੁੱਗੀ ਲਿੰਕ",
    invalid_link_desc: "ਇਹ ਪਾਸਵਰਡ ਰੀਸੈਟ ਲਿੰਕ ਅਵੈਧ ਹੈ ਜਾਂ ਮਿਆਦ ਪੁੱਗ ਗਈ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਨਵੀਂ ਬੇਨਤੀ ਕਰੋ।",
    request_new_link: "ਨਵੀਂ ਲਿੰਕ ਦੀ ਬੇਨਤੀ ਕਰੋ",
    // Admin Interface
    admin_dashboard: "ਐਡਮਿਨ ਡੈਸ਼ਬੋਰਡ",
    manage_store: "ਆਪਣੇ ReRoots ਸਕਿਨਕੇਅਰ ਸਟੋਰ ਦਾ ਪ੍ਰਬੰਧਨ ਕਰੋ",
    products: "ਉਤਪਾਦ",
    orders: "ਆਰਡਰ",
    customers: "ਗਾਹਕ",
    reviews: "ਸਮੀਖਿਆਵਾਂ",
    subscriptions: "ਸਬਸਕ੍ਰਿਪਸ਼ਨ",
    ads: "ਇਸ਼ਤਿਹਾਰ",
    team: "ਟੀਮ",
    settings: "ਸੈਟਿੰਗਾਂ",
    store_settings: "ਸਟੋਰ ਸੈਟਿੰਗਾਂ",
    payment_settings: "ਭੁਗਤਾਨ ਸੈਟਿੰਗਾਂ",
    live_chat: "ਲਾਈਵ ਚੈਟ",
    language_region: "ਭਾਸ਼ਾ ਅਤੇ ਖੇਤਰ",
    thank_you_messages: "ਧੰਨਵਾਦ ਸੁਨੇਹੇ",
    website_settings: "ਵੈੱਬਸਾਈਟ ਸੈਟਿੰਗਾਂ",
    add_product: "ਉਤਪਾਦ ਸ਼ਾਮਲ ਕਰੋ",
    edit_product: "ਉਤਪਾਦ ਸੋਧੋ",
    save: "ਸੰਭਾਲੋ",
    cancel: "ਰੱਦ ਕਰੋ",
    delete: "ਮਿਟਾਓ",
    search: "ਖੋਜੋ",
    filter: "ਫਿਲਟਰ",
    all: "ਸਭ",
    active: "ਸਰਗਰਮ",
    inactive: "ਨਾ-ਸਰਗਰਮ",
    pending: "ਬਕਾਇਆ",
    completed: "ਮੁਕੰਮਲ",
    processing: "ਪ੍ਰੋਸੈਸਿੰਗ",
    shipped: "ਸ਼ਿਪ ਕੀਤਾ",
    delivered: "ਡਿਲੀਵਰ ਕੀਤਾ",
    cancelled: "ਰੱਦ ਕੀਤਾ",
    total_products: "ਕੁੱਲ ਉਤਪਾਦ",
    total_orders: "ਕੁੱਲ ਆਰਡਰ",
    total_customers: "ਕੁੱਲ ਗਾਹਕ",
    total_revenue: "ਕੁੱਲ ਆਮਦਨ",
    recent_orders: "ਹਾਲੀਆ ਆਰਡਰ",
    view_all: "ਸਭ ਵੇਖੋ",
    logout: "ਲੌਗਆਊਟ",
    ai_chat: "AI ਚੈਟ",
    // Additional admin translations
    order: "ਆਰਡਰ",
    customer: "ਗਾਹਕ",
    status: "ਸਥਿਤੀ",
    total: "ਕੁੱਲ",
    categories: "ਸ਼੍ਰੇਣੀਆਂ",
    sections: "ਭਾਗ",
    typography: "ਟਾਈਪੋਗ੍ਰਾਫੀ",
    overview: "ਸੰਖੇਪ"
  },
  hi: {
    shop_now: "अभी खरीदें",
    learn_more: "और जानें",
    add_to_cart: "कार्ट में डालें",
    subscribe: "सदस्यता लें",
    premium_skincare: "प्रीमियम स्किनकेयर",
    transform_your_skin: "अपनी त्वचा को बदलें",
    hero_subtitle: "चमकदार, स्वस्थ त्वचा के लिए विज्ञान-समर्थित फॉर्मूले",
    view_product: "उत्पाद देखें",
    featured_products: "विशेष उत्पाद",
    our_products: "हमारे उत्पाद",
    all_products: "सभी उत्पाद",
    products: "उत्पाद",
    shop_all: "सभी खरीदें",
    join_community: "ReRoots समुदाय से जुड़ें",
    newsletter_desc: "विशेष ऑफर, स्किनकेयर टिप्स और नए उत्पाद अलर्ट प्राप्त करें",
    email_placeholder: "अपना ईमेल दर्ज करें",
    cart: "कार्ट",
    your_cart: "आपकी कार्ट",
    cart_empty: "आपकी कार्ट खाली है",
    continue_shopping: "खरीदारी जारी रखें",
    checkout: "चेकआउट",
    proceed_checkout: "चेकआउट के लिए आगे बढ़ें",
    total: "कुल",
    subtotal: "उप-योग",
    shipping: "शिपिंग",
    tax: "कर",
    free: "मुफ्त",
    home: "होम",
    shop: "दुकान",
    about: "हमारे बारे में",
    login: "लॉगिन",
    account: "खाता",
    logout: "लॉगआउट",
    quantity: "मात्रा",
    in_stock: "स्टॉक में",
    out_of_stock: "स्टॉक में नहीं",
    reviews: "समीक्षाएं",
    write_review: "समीक्षा लिखें",
    ingredients: "सामग्री",
    how_to_use: "कैसे इस्तेमाल करें",
    bestseller: "बेस्टसेलर",
    new_arrival: "नया",
    sale: "सेल",
    thanks_subscribing: "सब्सक्राइब करने के लिए धन्यवाद!",
    customer_reviews: "ग्राहक समीक्षाएं",
    no_products: "कोई उत्पाद नहीं मिला।",
    product_not_found: "उत्पाद नहीं मिला",
    testimonials: "प्रशंसापत्र",
    what_customers_say: "हमारे ग्राहक क्या कहते हैं",
    view_all: "सभी देखें",
    pre_order: "प्री-ऑर्डर",
    pre_order_now: "अभी प्री-ऑर्डर करें",
    pre_order_item: "प्री-ऑर्डर आइटम",
    available_on: "उपलब्धता तिथि",
    ships_soon: "रिलीज़ के 2-3 सप्ताह बाद शिप होगा",
    // Login page
    welcome_back: "वापस स्वागत है,",
    esteemed_client: "हमारे सम्मानित ग्राहक।",
    email: "ईमेल",
    password: "पासवर्ड",
    sign_in: "साइन इन करें",
    signing_in: "साइन इन हो रहा है...",
    dont_have_account: "खाता नहीं है?",
    join_community_link: "हमारे विशेष समुदाय से जुड़ें",
    already_have_account: "पहले से खाता है?",
    sign_in_link: "साइन इन करें",
    create_account: "खाता बनाएं",
    creating_account: "खाता बन रहा है...",
    first_name: "पहला नाम",
    last_name: "उपनाम",
    confirm_password: "पासवर्ड की पुष्टि करें",
    forgot_password: "पासवर्ड भूल गए?",
    forgot_password_title: "अपना",
    password_word: "पासवर्ड भूल गए?",
    forgot_password_desc: "अपना ईमेल दर्ज करें और हम आपको रीसेट लिंक भेजेंगे।",
    send_reset_link: "रीसेट लिंक भेजें",
    sending: "भेज रहा है...",
    back_to_login: "लॉगिन पर वापस जाएं",
    check_email: "अपना ईमेल चेक करें",
    check_email_desc: "हमने आपके ईमेल पर पासवर्ड रीसेट लिंक भेज दिया है।",
    didnt_receive: "ईमेल नहीं मिली? अपना स्पैम फोल्डर चेक करें या",
    try_again: "फिर से कोशिश करें",
    create_new_password: "नया",
    new_password: "नया पासवर्ड",
    password_min_chars: "पासवर्ड कम से कम 8 अक्षरों का होना चाहिए",
    resetting: "रीसेट हो रहा है...",
    reset_password: "पासवर्ड रीसेट करें",
    invalid_link: "अमान्य या समाप्त लिंक",
    invalid_link_desc: "यह पासवर्ड रीसेट लिंक अमान्य है या समाप्त हो गई है। कृपया नई लिंक का अनुरोध करें।",
    request_new_link: "नई लिंक का अनुरोध करें",
    // Admin Interface
    admin_dashboard: "एडमिन डैशबोर्ड",
    manage_store: "अपने ReRoots स्किनकेयर स्टोर का प्रबंधन करें",
    products: "उत्पाद",
    orders: "ऑर्डर",
    customers: "ग्राहक",
    reviews: "समीक्षाएं",
    subscriptions: "सदस्यताएं",
    ads: "विज्ञापन",
    team: "टीम",
    settings: "सेटिंग्स",
    store_settings: "स्टोर सेटिंग्स",
    payment_settings: "भुगतान सेटिंग्स",
    live_chat: "लाइव चैट",
    language_region: "भाषा और क्षेत्र",
    thank_you_messages: "धन्यवाद संदेश",
    website_settings: "वेबसाइट सेटिंग्स",
    add_product: "उत्पाद जोड़ें",
    edit_product: "उत्पाद संपादित करें",
    save: "सहेजें",
    cancel: "रद्द करें",
    delete: "हटाएं",
    search: "खोजें",
    filter: "फ़िल्टर",
    all: "सभी",
    active: "सक्रिय",
    inactive: "निष्क्रिय",
    pending: "लंबित",
    completed: "पूर्ण",
    processing: "प्रसंस्करण",
    shipped: "शिप किया गया",
    delivered: "डिलीवर किया गया",
    cancelled: "रद्द किया गया",
    total_products: "कुल उत्पाद",
    total_orders: "कुल ऑर्डर",
    total_customers: "कुल ग्राहक",
    total_revenue: "कुल राजस्व",
    recent_orders: "हाल के ऑर्डर",
    view_all: "सभी देखें",
    logout: "लॉगआउट",
    ai_chat: "AI चैट",
    // Additional admin translations
    order: "ऑर्डर",
    customer: "ग्राहक",
    status: "स्थिति",
    total: "कुल",
    categories: "श्रेणियाँ",
    sections: "अनुभाग",
    typography: "टाइपोग्राफी",
    overview: "अवलोकन"
  },
  fr: {
    shop_now: "ACHETER",
    learn_more: "EN SAVOIR PLUS",
    add_to_cart: "Ajouter au panier",
    subscribe: "S'abonner",
    premium_skincare: "SOINS PREMIUM",
    transform_your_skin: "Transformez votre peau",
    hero_subtitle: "Des formules scientifiques pour une peau radieuse",
    view_product: "Voir le produit",
    featured_products: "Produits vedettes",
    our_products: "Nos produits",
    all_products: "Tous les produits",
    products: "produits",
    shop_all: "Tout voir",
    join_community: "Rejoignez la communauté ReRoots",
    newsletter_desc: "Offres exclusives, conseils beauté et alertes nouveautés",
    email_placeholder: "Entrez votre email",
    cart: "Panier",
    your_cart: "Votre panier",
    cart_empty: "Votre panier est vide",
    continue_shopping: "Continuer les achats",
    checkout: "Commander",
    proceed_checkout: "Passer la commande",
    total: "Total",
    subtotal: "Sous-total",
    shipping: "Livraison",
    tax: "Taxe",
    free: "GRATUIT",
    home: "Accueil",
    shop: "Boutique",
    about: "À propos",
    login: "Connexion",
    account: "Compte",
    logout: "Déconnexion",
    quantity: "Quantité",
    in_stock: "En stock",
    out_of_stock: "Rupture de stock",
    reviews: "Avis",
    write_review: "Écrire un avis",
    ingredients: "Ingrédients",
    how_to_use: "Mode d'emploi",
    bestseller: "Best-seller",
    new_arrival: "Nouveau",
    sale: "Promo",
    thanks_subscribing: "Merci de votre inscription!",
    pre_order: "Précommande",
    pre_order_now: "Précommander maintenant",
    pre_order_item: "Article en précommande",
    available_on: "Disponible le",
    ships_soon: "Expédition 2-3 semaines après la sortie",
    // Login page
    welcome_back: "Bon retour,",
    esteemed_client: "Cher client.",
    email: "E-mail",
    password: "Mot de passe",
    sign_in: "SE CONNECTER",
    signing_in: "Connexion...",
    dont_have_account: "Pas de compte?",
    join_community_link: "Rejoignez notre communauté exclusive",
    already_have_account: "Déjà un compte?",
    sign_in_link: "Se connecter",
    create_account: "Créer un compte",
    creating_account: "Création...",
    first_name: "Prénom",
    last_name: "Nom de famille",
    confirm_password: "Confirmer le mot de passe",
    forgot_password: "Mot de passe oublié?",
    forgot_password_title: "Mot de passe",
    password_word: "oublié?",
    forgot_password_desc: "Entrez votre e-mail et nous vous enverrons un lien de réinitialisation.",
    send_reset_link: "Envoyer le lien",
    sending: "Envoi...",
    back_to_login: "Retour à la connexion",
    check_email: "Vérifiez votre e-mail",
    check_email_desc: "Nous avons envoyé un lien de réinitialisation à votre e-mail.",
    didnt_receive: "Pas reçu? Vérifiez votre spam ou",
    try_again: "réessayez",
    create_new_password: "Créer un nouveau",
    new_password: "Nouveau mot de passe",
    password_min_chars: "Le mot de passe doit contenir au moins 8 caractères",
    resetting: "Réinitialisation...",
    reset_password: "Réinitialiser",
    invalid_link: "Lien invalide ou expiré",
    invalid_link_desc: "Ce lien est invalide ou a expiré. Veuillez en demander un nouveau.",
    request_new_link: "Demander un nouveau lien",
    // Admin Interface
    admin_dashboard: "Tableau de bord admin",
    manage_store: "Gérez votre boutique ReRoots",
    products: "Produits",
    orders: "Commandes",
    customers: "Clients",
    reviews: "Avis",
    subscriptions: "Abonnements",
    ads: "Publicités",
    team: "Équipe",
    settings: "Paramètres",
    store_settings: "Paramètres boutique",
    payment_settings: "Paramètres paiement",
    live_chat: "Chat en direct",
    language_region: "Langue et région",
    thank_you_messages: "Messages de remerciement",
    website_settings: "Paramètres site web",
    add_product: "Ajouter produit",
    edit_product: "Modifier produit",
    save: "Enregistrer",
    cancel: "Annuler",
    delete: "Supprimer",
    search: "Rechercher",
    filter: "Filtrer",
    all: "Tous",
    active: "Actif",
    inactive: "Inactif",
    pending: "En attente",
    completed: "Terminé",
    processing: "En cours",
    shipped: "Expédié",
    delivered: "Livré",
    cancelled: "Annulé",
    total_products: "Total produits",
    total_orders: "Total commandes",
    total_customers: "Total clients",
    total_revenue: "Revenu total",
    recent_orders: "Commandes récentes",
    view_all: "Voir tout",
    logout: "Déconnexion",
    ai_chat: "Chat IA",
    order: "Commande",
    customer: "Client",
    status: "Statut",
    total: "Total",
    categories: "Catégories",
    sections: "Sections",
    typography: "Typographie",
    overview: "Aperçu"
  },
  es: {
    shop_now: "COMPRAR",
    learn_more: "SABER MÁS",
    add_to_cart: "Añadir al carrito",
    subscribe: "Suscribirse",
    premium_skincare: "CUIDADO PREMIUM",
    transform_your_skin: "Transforma tu piel",
    hero_subtitle: "Fórmulas científicas para una piel radiante",
    view_product: "Ver producto",
    featured_products: "Productos destacados",
    our_products: "Nuestros productos",
    all_products: "Todos los productos",
    products: "productos",
    shop_all: "Ver todo",
    join_community: "Únete a la comunidad ReRoots",
    newsletter_desc: "Ofertas exclusivas, consejos de cuidado y alertas de productos",
    email_placeholder: "Ingresa tu email",
    cart: "Carrito",
    your_cart: "Tu carrito",
    cart_empty: "Tu carrito está vacío",
    continue_shopping: "Seguir comprando",
    checkout: "Pagar",
    proceed_checkout: "Proceder al pago",
    total: "Total",
    subtotal: "Subtotal",
    shipping: "Envío",
    tax: "Impuesto",
    free: "GRATIS",
    home: "Inicio",
    shop: "Tienda",
    about: "Nosotros",
    login: "Iniciar sesión",
    account: "Cuenta",
    logout: "Cerrar sesión",
    quantity: "Cantidad",
    in_stock: "En stock",
    out_of_stock: "Agotado",
    reviews: "Reseñas",
    write_review: "Escribir reseña",
    ingredients: "Ingredientes",
    how_to_use: "Cómo usar",
    bestseller: "Más vendido",
    new_arrival: "Nuevo",
    sale: "Oferta",
    thanks_subscribing: "¡Gracias por suscribirte!",
    pre_order: "Pre-pedido",
    pre_order_now: "Pre-ordenar ahora",
    pre_order_item: "Artículo en pre-pedido",
    available_on: "Disponible el",
    ships_soon: "Se envía 2-3 semanas después del lanzamiento",
    // Login page
    welcome_back: "Bienvenido de vuelta,",
    esteemed_client: "Estimado cliente.",
    email: "Correo electrónico",
    password: "Contraseña",
    sign_in: "INICIAR SESIÓN",
    signing_in: "Iniciando...",
    dont_have_account: "¿No tienes cuenta?",
    join_community_link: "Únete a nuestra comunidad exclusiva",
    already_have_account: "¿Ya tienes cuenta?",
    sign_in_link: "Iniciar sesión",
    create_account: "Crear cuenta",
    creating_account: "Creando...",
    first_name: "Nombre",
    last_name: "Apellido",
    confirm_password: "Confirmar contraseña",
    forgot_password: "¿Olvidaste tu contraseña?",
    forgot_password_title: "¿Olvidaste tu",
    password_word: "contraseña?",
    forgot_password_desc: "Ingresa tu correo y te enviaremos un enlace de restablecimiento.",
    send_reset_link: "Enviar enlace",
    sending: "Enviando...",
    back_to_login: "Volver al inicio de sesión",
    check_email: "Revisa tu correo",
    check_email_desc: "Hemos enviado un enlace de restablecimiento a tu correo.",
    didnt_receive: "¿No lo recibiste? Revisa spam o",
    try_again: "intenta de nuevo",
    create_new_password: "Crear nueva",
    new_password: "Nueva contraseña",
    password_min_chars: "La contraseña debe tener al menos 8 caracteres",
    resetting: "Restableciendo...",
    reset_password: "Restablecer contraseña",
    invalid_link: "Enlace inválido o expirado",
    invalid_link_desc: "Este enlace es inválido o ha expirado. Solicita uno nuevo.",
    request_new_link: "Solicitar nuevo enlace",
    // Admin Interface
    admin_dashboard: "Panel de administración",
    manage_store: "Administra tu tienda ReRoots",
    products: "Productos",
    orders: "Pedidos",
    customers: "Clientes",
    reviews: "Reseñas",
    subscriptions: "Suscripciones",
    ads: "Anuncios",
    team: "Equipo",
    settings: "Configuración",
    store_settings: "Config. tienda",
    payment_settings: "Config. pagos",
    live_chat: "Chat en vivo",
    language_region: "Idioma y región",
    thank_you_messages: "Mensajes de agradecimiento",
    website_settings: "Config. sitio web",
    add_product: "Agregar producto",
    edit_product: "Editar producto",
    save: "Guardar",
    cancel: "Cancelar",
    delete: "Eliminar",
    search: "Buscar",
    filter: "Filtrar",
    all: "Todos",
    active: "Activo",
    inactive: "Inactivo",
    pending: "Pendiente",
    completed: "Completado",
    processing: "Procesando",
    shipped: "Enviado",
    delivered: "Entregado",
    cancelled: "Cancelado",
    total_products: "Total productos",
    total_orders: "Total pedidos",
    total_customers: "Total clientes",
    total_revenue: "Ingresos totales",
    recent_orders: "Pedidos recientes",
    view_all: "Ver todo",
    logout: "Cerrar sesión",
    ai_chat: "Chat IA",
    order: "Pedido",
    customer: "Cliente",
    status: "Estado",
    total: "Total",
    categories: "Categorías",
    sections: "Secciones",
    typography: "Tipografía",
    overview: "Resumen"
  },
  zh: {
    shop_now: "立即购买",
    learn_more: "了解更多",
    add_to_cart: "加入购物车",
    subscribe: "订阅",
    premium_skincare: "优质护肤品",
    transform_your_skin: "改变你的肌肤",
    hero_subtitle: "科学配方，打造健康亮丽肌肤",
    view_product: "查看产品",
    featured_products: "特色产品",
    our_products: "我们的产品",
    all_products: "所有产品",
    products: "个产品",
    shop_all: "浏览全部",
    join_community: "加入ReRoots社区",
    newsletter_desc: "获取独家优惠、护肤技巧和新品提醒",
    email_placeholder: "输入您的邮箱",
    cart: "购物车",
    your_cart: "您的购物车",
    cart_empty: "购物车是空的",
    continue_shopping: "继续购物",
    checkout: "结账",
    proceed_checkout: "去结账",
    total: "总计",
    subtotal: "小计",
    shipping: "运费",
    tax: "税费",
    free: "免费",
    home: "首页",
    shop: "商店",
    about: "关于我们",
    login: "登录",
    account: "账户",
    logout: "退出",
    quantity: "数量",
    in_stock: "有货",
    out_of_stock: "缺货",
    reviews: "评价",
    write_review: "写评价",
    ingredients: "成分",
    how_to_use: "使用方法",
    bestseller: "畅销品",
    new_arrival: "新品",
    sale: "特价",
    thanks_subscribing: "感谢订阅！",
    pre_order: "预购",
    pre_order_now: "立即预购",
    pre_order_item: "预购商品",
    available_on: "上市日期",
    ships_soon: "发布后2-3周发货",
    // Login page
    welcome_back: "欢迎回来，",
    esteemed_client: "尊贵的客户。",
    email: "电子邮箱",
    password: "密码",
    sign_in: "登录",
    signing_in: "登录中...",
    dont_have_account: "没有账户？",
    join_community_link: "加入我们的专属社区",
    already_have_account: "已有账户？",
    sign_in_link: "登录",
    create_account: "创建账户",
    creating_account: "创建中...",
    first_name: "名",
    last_name: "姓",
    confirm_password: "确认密码",
    forgot_password: "忘记密码？",
    forgot_password_title: "忘记",
    password_word: "密码？",
    forgot_password_desc: "输入您的邮箱，我们会发送重置链接。",
    send_reset_link: "发送重置链接",
    sending: "发送中...",
    back_to_login: "返回登录",
    check_email: "查看您的邮箱",
    check_email_desc: "我们已发送密码重置链接到您的邮箱。",
    didnt_receive: "没收到？检查垃圾邮件或",
    try_again: "重试",
    create_new_password: "创建新",
    new_password: "新密码",
    password_min_chars: "密码至少需要8个字符",
    resetting: "重置中...",
    reset_password: "重置密码",
    invalid_link: "链接无效或已过期",
    invalid_link_desc: "此重置链接无效或已过期。请申请新链接。",
    request_new_link: "申请新链接",
    // Admin Interface
    admin_dashboard: "管理面板",
    manage_store: "管理您的 ReRoots 商店",
    products: "产品",
    orders: "订单",
    customers: "客户",
    reviews: "评论",
    subscriptions: "订阅",
    ads: "广告",
    team: "团队",
    settings: "设置",
    store_settings: "商店设置",
    payment_settings: "支付设置",
    live_chat: "在线聊天",
    language_region: "语言和地区",
    thank_you_messages: "感谢信息",
    website_settings: "网站设置",
    add_product: "添加产品",
    edit_product: "编辑产品",
    save: "保存",
    cancel: "取消",
    delete: "删除",
    search: "搜索",
    filter: "筛选",
    all: "全部",
    active: "活跃",
    inactive: "不活跃",
    pending: "待处理",
    completed: "已完成",
    processing: "处理中",
    shipped: "已发货",
    delivered: "已送达",
    cancelled: "已取消",
    total_products: "产品总数",
    total_orders: "订单总数",
    total_customers: "客户总数",
    total_revenue: "总收入",
    recent_orders: "最近订单",
    view_all: "查看全部",
    logout: "退出登录",
    ai_chat: "AI聊天",
    order: "订单",
    customer: "客户",
    status: "状态",
    total: "总计",
    categories: "分类",
    sections: "板块",
    typography: "字体",
    overview: "概览"
  },
  ar: {
    shop_now: "تسوق الآن",
    learn_more: "اعرف المزيد",
    add_to_cart: "أضف إلى السلة",
    subscribe: "اشترك",
    premium_skincare: "العناية الفاخرة",
    transform_your_skin: "حوّل بشرتك",
    hero_subtitle: "تركيبات علمية لبشرة مشرقة وصحية",
    view_product: "عرض المنتج",
    featured_products: "منتجات مميزة",
    our_products: "منتجاتنا",
    all_products: "جميع المنتجات",
    products: "منتج",
    shop_all: "عرض الكل",
    join_community: "انضم إلى مجتمع ReRoots",
    newsletter_desc: "احصل على عروض حصرية ونصائح للعناية بالبشرة",
    email_placeholder: "أدخل بريدك الإلكتروني",
    cart: "السلة",
    your_cart: "سلتك",
    cart_empty: "سلتك فارغة",
    continue_shopping: "مواصلة التسوق",
    checkout: "الدفع",
    proceed_checkout: "متابعة الدفع",
    total: "المجموع",
    subtotal: "المجموع الفرعي",
    shipping: "الشحن",
    tax: "الضريبة",
    free: "مجاني",
    home: "الرئيسية",
    shop: "المتجر",
    about: "من نحن",
    login: "تسجيل الدخول",
    account: "الحساب",
    logout: "تسجيل الخروج",
    quantity: "الكمية",
    in_stock: "متوفر",
    out_of_stock: "غير متوفر",
    reviews: "التقييمات",
    write_review: "اكتب تقييم",
    ingredients: "المكونات",
    how_to_use: "طريقة الاستخدام",
    bestseller: "الأكثر مبيعاً",
    new_arrival: "جديد",
    sale: "تخفيض",
    thanks_subscribing: "شكراً للاشتراك!",
    pre_order: "طلب مسبق",
    pre_order_now: "اطلب مسبقاً الآن",
    pre_order_item: "منتج للطلب المسبق",
    available_on: "تاريخ التوفر",
    ships_soon: "يُشحن بعد 2-3 أسابيع من الإصدار",
    // Login page
    welcome_back: "مرحباً بعودتك،",
    esteemed_client: "عميلنا الكريم.",
    email: "البريد الإلكتروني",
    password: "كلمة المرور",
    sign_in: "تسجيل الدخول",
    signing_in: "جاري الدخول...",
    dont_have_account: "ليس لديك حساب؟",
    join_community_link: "انضم إلى مجتمعنا الحصري",
    already_have_account: "لديك حساب؟",
    sign_in_link: "سجل الدخول",
    create_account: "إنشاء حساب",
    creating_account: "جاري الإنشاء...",
    first_name: "الاسم الأول",
    last_name: "اسم العائلة",
    confirm_password: "تأكيد كلمة المرور",
    forgot_password: "نسيت كلمة المرور؟",
    forgot_password_title: "نسيت",
    password_word: "كلمة المرور؟",
    forgot_password_desc: "أدخل بريدك الإلكتروني وسنرسل لك رابط إعادة التعيين.",
    send_reset_link: "إرسال الرابط",
    sending: "جاري الإرسال...",
    back_to_login: "العودة لتسجيل الدخول",
    check_email: "تحقق من بريدك",
    check_email_desc: "لقد أرسلنا رابط إعادة تعيين كلمة المرور إلى بريدك.",
    didnt_receive: "لم يصلك؟ تحقق من البريد المزعج أو",
    try_again: "حاول مرة أخرى",
    create_new_password: "إنشاء كلمة مرور",
    new_password: "كلمة المرور الجديدة",
    password_min_chars: "كلمة المرور يجب أن تكون 8 أحرف على الأقل",
    resetting: "جاري إعادة التعيين...",
    reset_password: "إعادة تعيين",
    invalid_link: "رابط غير صالح أو منتهي",
    invalid_link_desc: "هذا الرابط غير صالح أو منتهي الصلاحية. يرجى طلب رابط جديد.",
    request_new_link: "طلب رابط جديد",
    // Admin Interface
    admin_dashboard: "لوحة التحكم",
    manage_store: "إدارة متجر ReRoots الخاص بك",
    products: "المنتجات",
    orders: "الطلبات",
    customers: "العملاء",
    reviews: "التقييمات",
    subscriptions: "الاشتراكات",
    ads: "الإعلانات",
    team: "الفريق",
    settings: "الإعدادات",
    store_settings: "إعدادات المتجر",
    payment_settings: "إعدادات الدفع",
    live_chat: "الدردشة المباشرة",
    language_region: "اللغة والمنطقة",
    thank_you_messages: "رسائل الشكر",
    website_settings: "إعدادات الموقع",
    add_product: "إضافة منتج",
    edit_product: "تعديل منتج",
    save: "حفظ",
    cancel: "إلغاء",
    delete: "حذف",
    search: "بحث",
    filter: "تصفية",
    all: "الكل",
    active: "نشط",
    inactive: "غير نشط",
    pending: "قيد الانتظار",
    completed: "مكتمل",
    processing: "قيد المعالجة",
    shipped: "تم الشحن",
    delivered: "تم التوصيل",
    cancelled: "ملغي",
    total_products: "إجمالي المنتجات",
    total_orders: "إجمالي الطلبات",
    total_customers: "إجمالي العملاء",
    total_revenue: "إجمالي الإيرادات",
    recent_orders: "الطلبات الأخيرة",
    view_all: "عرض الكل",
    logout: "تسجيل الخروج",
    ai_chat: "دردشة الذكاء",
    order: "طلب",
    customer: "عميل",
    status: "الحالة",
    total: "الإجمالي",
    categories: "الفئات",
    sections: "الأقسام",
    typography: "الخطوط",
    overview: "نظرة عامة"
  }
};

// Hook to get translated UI text
const useUIText = (key) => {
  const { currentLang } = useTranslation() || {};
  const lang = currentLang || localStorage.getItem("reroots_lang") || "en-CA";
  const translations = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS["en-CA"] || UI_TRANSLATIONS.en;
  return translations[key] || UI_TRANSLATIONS["en-CA"]?.[key] || UI_TRANSLATIONS.en?.[key] || key;
};

// Site Content Provider
const SiteContentProvider = ({ children }) => {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchContent = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/site-content`);
      setContent(res.data);
    } catch (error) {
      console.error("Failed to fetch site content:", error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchContent();
  }, [fetchContent]);

  return (
    <SiteContentContext.Provider value={{ content, loading, refreshContent: fetchContent }}>
      {children}
    </SiteContentContext.Provider>
  );
};

const useSiteContent = () => useContext(SiteContentContext);

// StoreSettingsContext is imported from @/contexts

const StoreSettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState(null);

  useEffect(() => {
    axios.get(`${API}/store-settings`)
      .then(res => setSettings(res.data))
      .catch(console.error);
  }, []);

  return (
    <StoreSettingsContext.Provider value={{ settings }}>
      {children}
    </StoreSettingsContext.Provider>
  );
};

const useStoreSettings = () => useContext(StoreSettingsContext);

// GlobalBackgroundContext is imported from @/contexts

const GlobalBackgroundProvider = ({ children }) => {
  const [backgroundSettings, setBackgroundSettings] = useState({
    global_site_background: null,
    global_background_enabled: false,
    global_background_opacity: 0.15,
    global_background_overlay_color: "#FFFFFF",
    // Live background settings
    live_background_type: "none", // none, video, gradient, particles
    live_background_video_url: null,
    live_gradient_colors: ["#F8A5B8", "#C9A86C", "#FDF9F9"],
    live_gradient_speed: 10,
    live_particles_enabled: false,
    live_particles_color: "#F8A5B8",
    live_particles_count: 50
  });

  const fetchBackgroundSettings = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/public/site-background`);
      setBackgroundSettings(prev => ({...prev, ...res.data}));
    } catch (error) {
      console.error("Failed to load background settings:", error);
    }
  }, []);

  useEffect(() => {
    fetchBackgroundSettings();
  }, [fetchBackgroundSettings]);

  return (
    <GlobalBackgroundContext.Provider value={{ backgroundSettings, refreshBackground: fetchBackgroundSettings }}>
      {children}
    </GlobalBackgroundContext.Provider>
  );
};

const useGlobalBackground = () => useContext(GlobalBackgroundContext);

// Particle Effect Component
const ParticleEffect = ({ color = "#F8A5B8", count = 50 }) => {
  const particles = Array.from({ length: count }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    animationDelay: `${Math.random() * 5}s`,
    animationDuration: `${15 + Math.random() * 20}s`,
    size: `${4 + Math.random() * 8}px`,
    opacity: 0.3 + Math.random() * 0.5
  }));

  return (
    <div className="fixed inset-0 z-50 overflow-hidden pointer-events-none">
      <style>{`
        @keyframes float-up {
          0% { transform: translateY(100vh) rotate(0deg); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(-100px) rotate(720deg); opacity: 0; }
        }
        @keyframes sway {
          0%, 100% { transform: translateX(0); }
          50% { transform: translateX(30px); }
        }
      `}</style>
      {particles.map(p => (
        <div
          key={p.id}
          className="absolute rounded-full"
          style={{
            left: p.left,
            bottom: '-20px',
            width: p.size,
            height: p.size,
            backgroundColor: color,
            opacity: p.opacity,
            animation: `float-up ${p.animationDuration} ${p.animationDelay} infinite linear`,
            filter: 'blur(1px)'
          }}
        />
      ))}
    </div>
  );
};

// Animated Gradient Background Component
const AnimatedGradient = ({ colors = ["#F8A5B8", "#C9A86C", "#FDF9F9"], speed = 10 }) => {
  return (
    <div className="fixed inset-0 z-0">
      <style>{`
        @keyframes gradient-shift {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
      `}</style>
      <div 
        className="w-full h-full"
        style={{
          background: `linear-gradient(-45deg, ${colors.join(', ')})`,
          backgroundSize: '400% 400%',
          animation: `gradient-shift ${speed}s ease infinite`
        }}
      />
    </div>
  );
};

// Video Background Component
const VideoBackground = ({ videoUrl, opacity = 0.3 }) => {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden">
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute min-w-full min-h-full object-cover"
        style={{ opacity }}
      >
        <source src={videoUrl} type="video/mp4" />
      </video>
    </div>
  );
};

// Global Background Wrapper Component - applies background to entire site
const GlobalBackgroundWrapper = ({ children }) => {
  const location = useLocation();
  const { backgroundSettings } = useGlobalBackground();
  
  // Disable global ReRoots backgrounds on OROÉ, LA VELA BIANCA brand pages, and PWA
  const brandExcludedPaths = ['/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/pwa'];
  const isBrandPage = brandExcludedPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  // On brand pages and PWA, skip global background entirely - these have their own styling
  if (isBrandPage) {
    return <>{children}</>;
  }
  
  const liveType = backgroundSettings?.live_background_type || "none";
  const hasLiveBackground = liveType !== "none";
  const hasStaticBackground = backgroundSettings?.global_background_enabled && backgroundSettings?.global_site_background;
  const hasParticles = backgroundSettings?.live_particles_enabled;

  // If no backgrounds enabled at all, just render children
  if (!hasLiveBackground && !hasStaticBackground && !hasParticles) {
    return <>{children}</>;
  }

  // Background visibility: higher value = more visible background, less overlay
  const bgVisibility = backgroundSettings?.global_background_opacity || 0.15;
  const overlayOpacity = Math.max(0, Math.min(1, 1 - bgVisibility));

  return (
    <div className="relative min-h-screen">
      {/* Static Background Layer - shows when enabled (can combine with live backgrounds) */}
      {hasStaticBackground && (
        <div 
          className="fixed inset-0 z-0"
          style={{
            backgroundImage: `url('${backgroundSettings.global_site_background}')`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            backgroundRepeat: "no-repeat"
            // Note: backgroundAttachment: "fixed" removed - causes blank screen on mobile
          }}
        />
      )}

      {/* Live Background Layer - overlays on top of static if both enabled */}
      {liveType === "video" && backgroundSettings?.live_background_video_url && (
        <VideoBackground 
          videoUrl={backgroundSettings.live_background_video_url} 
          opacity={bgVisibility}
        />
      )}
      
      {liveType === "gradient" && (
        <AnimatedGradient 
          colors={backgroundSettings?.live_gradient_colors || ["#F8A5B8", "#C9A86C", "#FDF9F9"]}
          speed={backgroundSettings?.live_gradient_speed || 10}
        />
      )}

      {/* Particle Effect Overlay (can combine with any background) */}
      {(backgroundSettings.live_particles_enabled || liveType === "particles") && (
        <ParticleEffect 
          color={backgroundSettings.live_particles_color || "#F8A5B8"}
          count={backgroundSettings.live_particles_count || 50}
        />
      )}

      {/* Overlay for readability */}
      <div 
        className="fixed inset-0 z-0 pointer-events-none"
        style={{
          backgroundColor: backgroundSettings.global_background_overlay_color || "#FFFFFF",
          opacity: liveType === "gradient" ? overlayOpacity * 0.5 : overlayOpacity
        }}
      />

      {/* Content Layer */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
};

// TypographyContext is imported from @/contexts

const TypographyProvider = ({ children }) => {
  const [typography, setTypography] = useState(null);

  const fetchTypography = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/typography-settings`);
      setTypography(res.data);
      // Apply CSS variables dynamically
      if (res.data?.fonts) {
        const fonts = res.data.fonts;
        document.documentElement.style.setProperty('--font-family', fonts.family);
        document.documentElement.style.setProperty('--font-heading', fonts.heading_family);
        document.documentElement.style.setProperty('--font-size-base', `${fonts.base_size}px`);
        document.documentElement.style.setProperty('--font-size-h1', `${fonts.h1_size}px`);
        document.documentElement.style.setProperty('--font-size-h2', `${fonts.h2_size}px`);
        document.documentElement.style.setProperty('--font-size-h3', `${fonts.h3_size}px`);
        document.documentElement.style.setProperty('--font-size-h4', `${fonts.h4_size}px`);
        document.documentElement.style.setProperty('--font-size-body', `${fonts.body_size}px`);
        document.documentElement.style.setProperty('--font-size-small', `${fonts.small_size}px`);
        document.documentElement.style.setProperty('--color-primary', fonts.primary_color);
        document.documentElement.style.setProperty('--color-secondary', fonts.secondary_color);
        document.documentElement.style.setProperty('--color-accent', fonts.accent_color);
        document.documentElement.style.setProperty('--color-heading', fonts.heading_color);
        document.documentElement.style.setProperty('--color-link', fonts.link_color);
      }
    } catch (error) {
      console.error("Failed to fetch typography settings:", error);
    }
  }, []);

  useEffect(() => {
    fetchTypography();
  }, [fetchTypography]);

  return (
    <TypographyContext.Provider value={{ typography, refreshTypography: fetchTypography }}>
      {children}
    </TypographyContext.Provider>
  );
};

const useTypography = () => useContext(TypographyContext);

// LiveChatWidget - Extracted to /components/LiveChatWidget.js (lazy-loaded)
// VoiceAIChat - Extracted to /components/VoiceAIChat.js (lazy-loaded)

// Icon mapping
const iconMap = {
  Beaker: Beaker,
  Leaf: Leaf,
  Sparkles: Sparkles,
  Shield: Shield,
  Star: Star,
  Heart: Heart,
  Package: Package
};

// Image Uploader Component - Reusable component for image uploads
const ImageUploader = ({ value, onChange, placeholder = "Enter image URL or upload", showWarning = false, acceptVideo = false }) => {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    
    if (!isImage && !isVideo) {
      toast.error("Please select an image or video file");
      return;
    }
    
    if (isVideo && !acceptVideo) {
      toast.error("Please select an image file");
      return;
    }

    // Validate file size (max 10MB for images, 100MB for videos)
    const maxSize = isVideo ? 100 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error(isVideo ? "Video must be less than 100MB" : "Image must be less than 10MB");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const endpoint = isVideo ? `${API}/upload/video` : `${API}/upload/image`;
      const res = await axios.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000 // 2 minutes for larger files
      });
      
      const mediaUrl = res.data.url;
      const isPermanent = res.data.permanent;
      const host = res.data.host;
      
      // Use the URL directly if it's already a full URL
      const finalUrl = mediaUrl.startsWith('http') ? mediaUrl : `${BACKEND_URL}${mediaUrl}`;
      onChange(finalUrl);
      
      // Clear the input so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
      if (isPermanent) {
        const hostName = host === 'catbox' ? 'Catbox' : host === 'imgbb' ? 'ImgBB' : host;
        toast.success(`${isVideo ? 'Video' : 'Image'} uploaded to ${hostName} - Permanent! ✓`);
      } else {
        toast.success(`${isVideo ? 'Video' : 'Image'} uploaded!`);
        if (showWarning) {
          toast.warning("Local upload - may not persist after deployment", { duration: 5000 });
        }
      }
    } catch (error) {
      console.error("Upload error:", error);
      toast.error(`Failed to upload ${isVideo ? 'video' : 'image'}: ${error.message || 'Unknown error'}`);
    }
    setUploading(false);
  };

  const acceptTypes = acceptVideo ? "image/*,video/*" : "image/*";

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1"
        />
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept={acceptTypes}
          className="hidden"
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          title={acceptVideo ? "Upload image or video" : "Upload image (auto-saved permanently)"}
        >
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
        </Button>
      </div>
      {value && (
        <div className="relative w-20 h-20 rounded border overflow-hidden">
          <img loading="lazy" src={value} alt="Preview" className="w-full h-full object-cover" />
          <button
            type="button"
            onClick={() => onChange("")}
            className="absolute top-0 right-0 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
};

// Multi-file uploader for uploading multiple images/videos at once
const MultiFileUploader = ({ values = [], onChange, placeholder = "Upload files", acceptVideo = false, maxFiles = 10 }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = React.useRef(null);

  const handleMultiFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    if (files.length > maxFiles) {
      toast.error(`Maximum ${maxFiles} files allowed`);
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    const uploadedUrls = [...values];
    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const isImage = file.type.startsWith('image/');
      const isVideo = file.type.startsWith('video/');

      if (!isImage && !isVideo) {
        failCount++;
        continue;
      }

      if (isVideo && !acceptVideo) {
        failCount++;
        continue;
      }

      const maxSize = isVideo ? 100 * 1024 * 1024 : 10 * 1024 * 1024;
      if (file.size > maxSize) {
        failCount++;
        continue;
      }

      try {
        const formData = new FormData();
        formData.append('file', file);
        
        const endpoint = isVideo ? `${API}/upload/video` : `${API}/upload/image`;
        const res = await axios.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000
        });
        
        const mediaUrl = res.data.url;
        const finalUrl = mediaUrl.startsWith('http') ? mediaUrl : `${BACKEND_URL}${mediaUrl}`;
        uploadedUrls.push(finalUrl);
        successCount++;
      } catch (error) {
        console.error("Upload error:", error);
        failCount++;
      }

      setUploadProgress(Math.round(((i + 1) / files.length) * 100));
    }

    // Clear the input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    onChange(uploadedUrls);
    setUploading(false);
    setUploadProgress(0);

    if (successCount > 0) {
      toast.success(`${successCount} file(s) uploaded successfully!`);
    }
    if (failCount > 0) {
      toast.error(`${failCount} file(s) failed to upload`);
    }
  };

  const removeFile = (index) => {
    const newValues = values.filter((_, i) => i !== index);
    onChange(newValues);
  };

  const acceptTypes = acceptVideo ? "image/*,video/*" : "image/*";

  return (
    <div className="space-y-3">
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-gray-400 transition-colors">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleMultiFileUpload}
          accept={acceptTypes}
          multiple
          className="hidden"
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full"
        >
          {uploading ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Uploading {uploadProgress}%</>
          ) : (
            <><Upload className="h-4 w-4 mr-2" /> {placeholder} (up to {maxFiles})</>
          )}
        </Button>
        <p className="text-xs text-gray-500 mt-2">
          {acceptVideo ? "Images & Videos" : "Images only"} • Max {acceptVideo ? "100MB videos, 10MB images" : "10MB per file"}
        </p>
      </div>

      {values.length > 0 && (
        <div className="grid grid-cols-4 gap-2">
          {values.map((url, index) => (
            <div key={index} className="relative group">
              {url.match(/\.(mp4|webm|mov|avi)$/i) ? (
                <video src={url} className="w-full h-20 object-cover rounded border" />
              ) : (
                <img loading="lazy" src={url} alt={`Upload ${index + 1}`} className="w-full h-20 object-cover rounded border" />
              )}
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// PermanentImageUpload - Uses free permanent hosting (Catbox, ImgBB, or 0x0.st)
const PermanentImageUpload = ({ onUpload }) => {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast.error("Please select an image file");
      return;
    }

    // Validate file size (max 10MB for catbox)
    if (file.size > 10 * 1024 * 1024) {
      toast.error("Image must be less than 10MB");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${API}/upload/image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000 // 60 second timeout for upload
      });
      
      const imageUrl = res.data.url;
      const host = res.data.host;
      const isPermanent = res.data.permanent;
      
      if (imageUrl && isPermanent) {
        onUpload(imageUrl);
        const hostName = host === 'catbox' ? 'Catbox' : host === 'imgbb' ? 'ImgBB' : host;
        toast.success(`Image uploaded to ${hostName} - Permanent! ✓`);
      } else if (imageUrl) {
        // Fallback: use the returned URL
        const fullUrl = imageUrl.startsWith('http') ? imageUrl : `${BACKEND_URL}${imageUrl}`;
        onUpload(fullUrl);
        toast.warning("Image saved locally - may not persist after deployment");
      } else {
        throw new Error("No URL returned");
      }
    } catch (error) {
      console.error("Upload error:", error);
      toast.error("Failed to upload image. Try using an external URL instead.");
    }
    setUploading(false);
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept="image/*"
        className="hidden"
      />
      <Button
        type="button"
        variant="outline"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="border-green-300 hover:border-green-500 hover:bg-green-50"
      >
        {uploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="h-4 w-4 mr-2" />
            Upload Image (Permanent)
          </>
        )}
      </Button>
      <span className="text-xs text-green-600">✓ Auto-saved permanently</span>
    </div>
  );
};

// Generate session ID
const getSessionId = () => {
  let sessionId = localStorage.getItem("reroots_session_id");
  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("reroots_session_id", sessionId);
  }
  return sessionId;
};

// Auth Provider - Robust session persistence with localStorage as source of truth
const AuthProvider = ({ children }) => {
  // Initialize token from localStorage IMMEDIATELY
  const [token, setToken] = useState(() => localStorage.getItem("reroots_token") || null);
  
  // Initialize user from localStorage IMMEDIATELY (prevents flash of logged-out state)
  const [user, setUser] = useState(() => {
    try {
      const cachedUser = localStorage.getItem("reroots_user");
      const storedToken = localStorage.getItem("reroots_token");
      if (cachedUser && storedToken) {
        console.log("[Auth] Restored user from localStorage");
        return JSON.parse(cachedUser);
      }
    } catch (e) {
      console.error("[Auth] Failed to parse cached user:", e);
    }
    return null;
  });
  const [loading, setLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);

  // Validate token with backend (but don't clear user on network errors)
  const checkAuth = useCallback(async () => {
    const storedToken = localStorage.getItem("reroots_token");
    const cachedUser = localStorage.getItem("reroots_user");
    
    if (!storedToken) {
      setUser(null);
      setToken(null);
      setLoading(false);
      setAuthChecked(true);
      return;
    }
    
    setToken(storedToken);
    
    try {
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${storedToken}` },
        timeout: 10000
      });
      // Update user and cache with fresh data
      setUser(res.data);
      localStorage.setItem("reroots_user", JSON.stringify(res.data));
      console.log("[Auth] Token validated with server");
    } catch (error) {
      // ONLY clear session on CONFIRMED auth errors (401/403)
      if (error.response && (error.response.status === 401 || error.response.status === 403)) {
        console.log("[Auth] Token invalid (401/403), clearing session");
        localStorage.removeItem("reroots_token");
        localStorage.removeItem("reroots_remember_me");
        localStorage.removeItem("reroots_user");
        setUser(null);
        setToken(null);
      } else {
        // For network errors, timeouts, 500s - KEEP the cached user!
        console.warn("[Auth] Validation failed (network/server), keeping cached session");
        if (cachedUser && !user) {
          try {
            setUser(JSON.parse(cachedUser));
          } catch (e) {}
        }
      }
    } finally {
      setLoading(false);
      setAuthChecked(true);
    }
  }, [user]);

  useEffect(() => {
    checkAuth();
  }, []);  // Only run once on mount

  // Periodic auth check every 5 minutes (only if user is logged in)
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(checkAuth, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user, checkAuth]);

  const login = async (email, password, phone = null, rememberMe = false) => {
    const loginData = phone ? { phone, password } : { email, password };
    const res = await axios.post(`${API}/auth/login`, loginData);
    
    // Store token and user
    localStorage.setItem("reroots_token", res.data.token);
    localStorage.setItem("reroots_user", JSON.stringify(res.data.user));
    
    if (rememberMe) {
      localStorage.setItem("reroots_remember_me", "true");
    } else {
      localStorage.removeItem("reroots_remember_me");
    }
    
    setToken(res.data.token);
    setUser(res.data.user);
    console.log("[Auth] User logged in:", res.data.user.email);
    return res.data.user;
  };

  const register = async (data) => {
    const res = await axios.post(`${API}/auth/register`, data);
    localStorage.setItem("reroots_token", res.data.token);
    localStorage.setItem("reroots_user", JSON.stringify(res.data.user));
    setToken(res.data.token);
    setUser(res.data.user);
    console.log("[Auth] User registered:", res.data.user.email);
    return res.data.user;
  };

  const logout = () => {
    localStorage.removeItem("reroots_token");
    localStorage.removeItem("reroots_remember_me");
    localStorage.removeItem("reroots_user");
    // Don't clear cart on logout - guest carts should persist
    setToken(null);
    setUser(null);
    console.log("[Auth] User logged out");
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading, authChecked }}>
      {children}
    </AuthContext.Provider>
  );
};

// Cart Provider - with robust localStorage persistence
const CartProvider = ({ children }) => {
  // Initialize cart from localStorage FIRST (source of truth for persistence)
  const [cart, setCart] = useState(() => {
    try {
      const cachedCart = localStorage.getItem("reroots_cart_cache");
      if (cachedCart) {
        const parsed = JSON.parse(cachedCart);
        if (parsed && Array.isArray(parsed.items)) {
          console.log("[Cart] Restored from localStorage:", parsed.items.length, "items");
          return parsed;
        }
      }
    } catch (e) {
      console.error("[Cart] Failed to restore from localStorage:", e);
    }
    return { items: [] };
  });
  const [loading, setLoading] = useState(false);
  const [sideCartOpen, setSideCartOpen] = useState(false);
  const [serverSynced, setServerSynced] = useState(false);
  const sessionId = getSessionId();
  const { user, authChecked } = useAuth();

  // ALWAYS save cart to localStorage when it changes (this is the persistence layer)
  useEffect(() => {
    if (cart && cart.items) {
      try {
        localStorage.setItem("reroots_cart_cache", JSON.stringify(cart));
        console.log("[Cart] Saved to localStorage:", cart.items.length, "items");
      } catch (e) {
        console.error("[Cart] Failed to save to localStorage:", e);
      }
    }
  }, [cart]);

  // Sync with server - but MERGE, don't replace if local has items
  const syncCartWithServer = useCallback(async () => {
    if (!authChecked) return;
    
    try {
      const res = await axios.get(`${API}/cart/${sessionId}`);
      const serverCart = res.data;
      
      // Get current local cart
      const localCart = cart;
      const localItems = localCart?.items || [];
      const serverItems = serverCart?.items || [];
      
      console.log("[Cart] Server sync - Local items:", localItems.length, "Server items:", serverItems.length);
      
      // Strategy: If local has items but server is empty, push local to server
      if (localItems.length > 0 && serverItems.length === 0) {
        console.log("[Cart] Local cart has items, server empty - pushing to server");
        // Re-add each local item to server
        for (const item of localItems) {
          try {
            await axios.post(`${API}/cart/${sessionId}/add`, { 
              product_id: item.product_id, 
              quantity: item.quantity 
            });
          } catch (e) {
            console.warn("[Cart] Failed to sync item to server:", item.product_id);
          }
        }
        // Fetch the updated server cart
        const updatedRes = await axios.get(`${API}/cart/${sessionId}`);
        if (updatedRes.data?.items?.length > 0) {
          setCart(updatedRes.data);
        }
      } 
      // If server has items, use server as source of truth
      else if (serverItems.length > 0) {
        console.log("[Cart] Using server cart as source of truth");
        setCart(serverCart);
      }
      // Both empty - keep empty
      
      setServerSynced(true);
    } catch (error) {
      console.error("[Cart] Server sync failed:", error);
      // On error, keep local cart - don't clear it!
      setServerSynced(true);
    }
  }, [sessionId, authChecked, cart]);

  // Sync on mount (after auth is checked)
  useEffect(() => {
    if (authChecked && !serverSynced) {
      syncCartWithServer();
    }
  }, [authChecked, serverSynced, syncCartWithServer]);

  // Re-sync when user logs in
  useEffect(() => {
    if (authChecked && user && serverSynced) {
      setServerSynced(false); // Trigger re-sync
    }
  }, [user, authChecked]);

  const addToCart = async (productId, quantity = 1) => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/cart/${sessionId}/add`, { product_id: productId, quantity });
      setCart(res.data);
      setSideCartOpen(true);
      toast.success("Added to bag!");
    } catch (error) {
      console.error("[Cart] Add error:", error);
      toast.error("Failed to add to cart");
    }
    setLoading(false);
  };

  // Add a combo to cart with its discounted price
  const addComboToCart = async (comboId, quantity = 1) => {
    console.log('[Cart] addComboToCart called with comboId:', comboId, 'sessionId:', sessionId);
    
    if (!sessionId) {
      console.error('[Cart] No sessionId available!');
      toast.error("Session error. Please refresh the page.");
      return;
    }
    
    if (!comboId) {
      console.error('[Cart] No comboId provided!');
      toast.error("Invalid combo. Please try again.");
      return;
    }
    
    setLoading(true);
    try {
      const payload = { combo_id: comboId, quantity };
      console.log('[Cart] Sending combo payload:', JSON.stringify(payload));
      
      const res = await axios.post(`${API}/cart/${sessionId}/add-combo`, payload);
      console.log('[Cart] Combo added successfully:', res.data);
      
      setCart(res.data);
      setSideCartOpen(true);
      toast.success("Combo added to bag!");
    } catch (error) {
      console.error("[Cart] Combo cart error:", error);
      console.error("[Cart] Error response:", error?.response?.data);
      toast.error("Failed to add combo to cart");
      throw error;
    }
    setLoading(false);
  };

  const updateQuantity = async (productId, quantity) => {
    setLoading(true);
    try {
      const res = await axios.put(`${API}/cart/${sessionId}/update`, { product_id: productId, quantity });
      setCart(res.data);
    } catch (error) {
      toast.error("Failed to update cart");
    }
    setLoading(false);
  };

  const removeItem = async (productId) => {
    setLoading(true);
    try {
      const res = await axios.delete(`${API}/cart/${sessionId}/item/${productId}`);
      setCart(res.data);
      toast.success("Item removed");
    } catch (error) {
      toast.error("Failed to remove item");
    }
    setLoading(false);
  };

  const clearCart = async () => {
    try {
      await axios.delete(`${API}/cart/${sessionId}`);
      setCart({ items: [] });
      localStorage.removeItem("reroots_cart_cache");
    } catch (error) {
      console.error("Failed to clear cart:", error);
    }
  };

  const itemCount = cart.items?.reduce((sum, item) => sum + item.quantity, 0) || 0;
  
  // Calculate effective price accounting for combo items or product discount_percent
  const getEffectivePrice = (item) => {
    // Combo items have price set directly (total combo price)
    if (item.item_type === "combo") {
      return item.price || 0;
    }
    // Legacy combo items (with combo_price field)
    if (item.combo_price !== undefined && item.combo_price !== null) {
      return item.combo_price;
    }
    // Regular product item - use product price with any individual discount
    const product = item.product;
    if (!product) return 0;
    const price = product.price || 0;
    const discount = product.discount_percent || 0;
    return discount > 0 ? price * (1 - discount / 100) : price;
  };
  
  const subtotal = cart.items?.reduce((sum, item) => sum + getEffectivePrice(item) * item.quantity, 0) || 0;

  // Expose fetchCart as a wrapper around syncCartWithServer for backward compatibility
  const fetchCart = syncCartWithServer;

  return (
    <CartContext.Provider value={{ cart, addToCart, addComboToCart, updateQuantity, removeItem, clearCart, itemCount, subtotal, loading, sessionId, fetchCart, sideCartOpen, setSideCartOpen, getEffectivePrice }}>
      {children}
    </CartContext.Provider>
  );
};

const useAuth = () => useContext(AuthContext);
const useCart = () => useContext(CartContext);

// ============================================
// SIDE CART - Luxury Slide-out Panel
// ============================================
const SideCart = () => {
  const { cart, sideCartOpen, setSideCartOpen, updateQuantity, removeItem, subtotal, loading, getEffectivePrice } = useCart();
  const { formatPrice } = useCurrency();
  const navigate = useNavigate();
  
  const FREE_SHIPPING_THRESHOLD = 75;
  const amountToFreeShipping = Math.max(0, FREE_SHIPPING_THRESHOLD - subtotal);
  const hasItems = cart.items?.length > 0;
  
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') setSideCartOpen(false);
    };
    if (sideCartOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [sideCartOpen, setSideCartOpen]);

  return (
    <AnimatePresence>
      {sideCartOpen && (
        <>
          {/* Backdrop */}
          <MotionDiv
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
            onClick={() => setSideCartOpen(false)}
          />
          
          {/* Side Panel */}
          <MotionDiv
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col"
            style={{ fontFamily: 'Manrope, sans-serif' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <h2 className="text-xl font-semibold text-[#2D2A2E]" style={{ fontFamily: '"Playfair Display", serif' }}>
                Your Bag
              </h2>
              <button
                onClick={() => setSideCartOpen(false)}
                className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors"
              >
                <X className="w-5 h-5 text-[#2D2A2E]" />
              </button>
            </div>
            
            {/* Free Shipping Progress */}
            {hasItems && (
              <div className="px-6 py-4 bg-[#FDF9F9] border-b border-gray-100">
                {amountToFreeShipping > 0 ? (
                  <>
                    <div className="flex items-center gap-2 mb-2">
                      <Truck className="w-4 h-4 text-[#D4AF37]" />
                      <p className="text-sm text-[#2D2A2E]">
                        You're <span className="font-bold text-[#D4AF37]">${amountToFreeShipping.toFixed(2)}</span> away from free shipping!
                      </p>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <MotionDiv
                        initial={{ scaleX: 0 }}
                        animate={{ scaleX: Math.min(100, (subtotal / FREE_SHIPPING_THRESHOLD) * 100) / 100 }}
                        style={{ transformOrigin: 'left', width: '100%' }}
                        transition={{ duration: 0.5 }}
                        className="h-full bg-gradient-to-r from-[#D4AF37] to-[#E8C84B] rounded-full"
                      />
                    </div>
                  </>
                ) : (
                  <div className="flex items-center gap-2">
                    <BadgeCheck className="w-5 h-5 text-green-500" />
                    <p className="text-sm text-green-700 font-medium">
                      You've unlocked FREE shipping!
                    </p>
                  </div>
                )}
              </div>
            )}
            
            {/* Complimentary Samples Badge */}
            {hasItems && (
              <div className="px-6 py-3 bg-[#D4AF37]/10 border-b border-[#D4AF37]/20">
                <div className="flex items-center gap-2">
                  <Gift className="w-4 h-4 text-[#D4AF37]" />
                  <p className="text-xs text-[#2D2A2E] font-medium tracking-wide">
                    COMPLIMENTARY SAMPLES INCLUDED WITH EVERY ORDER
                  </p>
                </div>
              </div>
            )}
            
            {/* Cart Items */}
            <div className="flex-1 overflow-y-auto p-6">
              {!hasItems ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="w-20 h-20 bg-[#FDF9F9] rounded-full flex items-center justify-center mb-6">
                    <ShoppingBag className="w-8 h-8 text-gray-400" />
                  </div>
                  <p className="text-[#2D2A2E] font-medium mb-2" style={{ fontFamily: '"Playfair Display", serif' }}>
                    Your bag is empty
                  </p>
                  <p className="text-sm text-[#5A5A5A] mb-6">
                    Discover our biotech skincare collection
                  </p>
                  <Button
                    onClick={() => {
                      setSideCartOpen(false);
                      navigate('/shop');
                    }}
                    className="bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full px-8 py-5 font-semibold transition-all duration-500 hover:scale-105"
                  >
                    Shop Now
                  </Button>
                </div>
              ) : (
                <div className="space-y-6">
                  {cart.items.map((item) => {
                    // Check if this is a combo item
                    const isCombo = item.item_type === "combo";
                    const itemKey = isCombo ? item.combo_id : item.product?.id;
                    const itemPrice = getEffectivePrice(item);
                    
                    if (isCombo) {
                      // Render COMBO as single line item
                      return (
                        <MotionDiv
                          key={itemKey}
                          layout
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, x: -100 }}
                          className="pb-6 border-b border-gray-100 last:border-0"
                        >
                          {/* Combo Header with Badge */}
                          <div className="flex items-center gap-2 mb-3">
                            <span className="inline-flex items-center gap-1 px-3 py-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-semibold rounded-full">
                              <Sparkles className="w-3 h-3" /> COMBO DEAL
                            </span>
                            <span className="text-xs text-green-600 font-medium">
                              Save {Number(item.discount_percent || 0).toFixed(0)}%
                            </span>
                          </div>
                          
                          {/* Combo Name */}
                          <h3 className="font-medium text-[#2D2A2E] mb-3" style={{ fontFamily: '"Playfair Display", serif' }}>
                            {item.combo_name}
                          </h3>
                          
                          {/* Products in Combo */}
                          <div className="space-y-2 mb-4">
                            {item.products?.map((product, idx) => (
                              <div key={product.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                                <div className="w-12 h-12 bg-white rounded-lg overflow-hidden flex-shrink-0">
                                  <img
                                    src={product.images?.[0] || product.image || "/placeholder.png"}
                                    alt={product.name}
                                    className="w-full h-full object-cover"
                                  />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
                                  <p className="text-xs text-gray-500">Step {idx + 1}</p>
                                </div>
                                <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                              </div>
                            ))}
                          </div>
                          
                          {/* Quantity & Price */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 bg-gray-100 rounded-full p-1">
                              <button
                                onClick={() => updateQuantity(item.product_id, Math.max(1, item.quantity - 1))}
                                className="w-7 h-7 rounded-full bg-white flex items-center justify-center hover:bg-gray-50 transition-colors"
                                disabled={loading}
                              >
                                <Minus className="w-3 h-3" />
                              </button>
                              <span className="w-8 text-center text-sm font-medium">{item.quantity}</span>
                              <button
                                onClick={() => updateQuantity(item.product_id, item.quantity + 1)}
                                className="w-7 h-7 rounded-full bg-white flex items-center justify-center hover:bg-gray-50 transition-colors"
                                disabled={loading}
                              >
                                <Plus className="w-3 h-3" />
                              </button>
                            </div>
                            
                            <div className="text-right">
                              <p className="font-semibold text-[#2D2A2E]">
                                {formatPrice(itemPrice * item.quantity)}
                              </p>
                              {item.original_price && item.original_price > itemPrice && (
                                <p className="text-xs text-gray-400 line-through">
                                  {formatPrice(item.original_price * item.quantity)}
                                </p>
                              )}
                            </div>
                          </div>
                          
                          {/* Remove Button */}
                          <button
                            onClick={() => removeItem(item.product_id)}
                            className="mt-3 text-xs text-gray-400 hover:text-red-500 transition-colors flex items-center gap-1"
                            disabled={loading}
                          >
                            <Trash2 className="w-3 h-3" /> Remove combo
                          </button>
                        </MotionDiv>
                      );
                    }
                    
                    // Render REGULAR product item
                    return (
                    <MotionDiv
                      key={itemKey}
                      layout
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -100 }}
                      className="flex gap-4 pb-6 border-b border-gray-100 last:border-0"
                    >
                      {/* Product Image */}
                      <Link 
                        to={`/products/${item.product?.id}`} 
                        onClick={() => setSideCartOpen(false)}
                        className="w-24 h-28 bg-[#FDF9F9] rounded-xl overflow-hidden flex-shrink-0 relative"
                      >
                        {/* Loading placeholder */}
                        <div className="absolute inset-0 bg-gradient-to-br from-[#FDF9F9] to-[#F5F0F0] flex items-center justify-center">
                          <div className="w-8 h-8 border-2 border-[#D4AF37]/30 border-t-[#D4AF37] rounded-full animate-spin" />
                        </div>
                        <img
                          src={item.product?.images?.[0] || item.product?.image || "https://via.placeholder.com/100x120?text=Product"}
                          alt={item.product?.name}
                          loading="lazy"
                          decoding="async"
                          className="relative w-full h-full object-cover z-10"
                          onLoad={(e) => e.target.previousSibling.style.display = 'none'}
                          onError={(e) => {
                            e.target.previousSibling.style.display = 'none';
                            e.target.src = "https://via.placeholder.com/100x120?text=Product";
                          }}
                        />
                      </Link>
                      
                      {/* Product Details */}
                      <div className="flex-1 min-w-0">
                        <Link 
                          to={`/products/${item.product?.id}`}
                          onClick={() => setSideCartOpen(false)}
                          className="block"
                        >
                          <h3 className="font-medium text-[#2D2A2E] line-clamp-2 mb-1 hover:text-[#D4AF37] transition-colors" style={{ fontFamily: '"Playfair Display", serif' }}>
                            {item.product?.name}
                          </h3>
                        </Link>
                        <p className="text-sm text-[#5A5A5A] mb-3">
                          {item.product?.size || '30ml'}
                        </p>
                        
                        {/* Quantity & Price */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 bg-gray-100 rounded-full p-1">
                            <button
                              onClick={() => updateQuantity(item.product?.id, Math.max(1, item.quantity - 1))}
                              className="w-7 h-7 rounded-full bg-white flex items-center justify-center hover:bg-gray-50 transition-colors"
                              disabled={loading}
                            >
                              <Minus className="w-3 h-3" />
                            </button>
                            <span className="w-8 text-center text-sm font-medium">{item.quantity}</span>
                            <button
                              onClick={() => updateQuantity(item.product?.id, item.quantity + 1)}
                              className="w-7 h-7 rounded-full bg-white flex items-center justify-center hover:bg-gray-50 transition-colors"
                              disabled={loading}
                            >
                              <Plus className="w-3 h-3" />
                            </button>
                          </div>
                          
                          <p className="font-semibold text-[#2D2A2E]">
                            {formatPrice(getEffectivePrice(item) * item.quantity)}
                          </p>
                        </div>
                        
                        {/* Show combo badge if item is part of combo */}
                        {item.combo_id && (
                          <div className="mt-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">
                              <span>✨</span> {item.combo_name || 'Combo Deal'}
                            </span>
                          </div>
                        )}
                      </div>
                      
                      {/* Remove Button */}
                      <button
                        onClick={() => removeItem(item.product?.id)}
                        className="self-start p-2 text-gray-400 hover:text-red-500 transition-colors"
                        disabled={loading}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </MotionDiv>
                    );
                  })}
                </div>
              )}
            </div>
            
            {/* Footer */}
            {hasItems && (
              <div className="border-t border-gray-100 p-6 space-y-4 bg-white">
                {/* Subtotal */}
                <div className="flex items-center justify-between">
                  <span className="text-[#5A5A5A]">Subtotal</span>
                  <span className="text-xl font-bold text-[#2D2A2E]" style={{ fontFamily: '"Playfair Display", serif' }}>
                    {formatPrice(subtotal)}
                  </span>
                </div>
                
                <p className="text-xs text-[#5A5A5A] text-center">
                  Taxes and shipping calculated at checkout
                </p>
                
                {/* Checkout Button */}
                <Button
                  onClick={() => {
                    setSideCartOpen(false);
                    navigate('/checkout');
                  }}
                  className="w-full bg-[#2D2A2E] hover:bg-[#1a1819] text-white rounded-full py-6 font-semibold transition-all duration-500 hover:scale-[1.02]"
                >
                  Checkout
                </Button>
                
                {/* Continue Shopping */}
                <button
                  onClick={() => setSideCartOpen(false)}
                  className="w-full text-center text-sm text-[#5A5A5A] hover:text-[#D4AF37] transition-colors py-2"
                >
                  Continue Shopping
                </button>
              </div>
            )}
          </MotionDiv>
        </>
      )}
    </AnimatePresence>
  );
};

// Navbar Wrapper - hides navbar on standalone pages
const NavbarWrapper = () => {
  const location = useLocation();
  const hiddenPaths = ['/influencer', '/Bio-Age-Repair-Scan', '/quiz', '/skin-scan', '/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/admin', '/reroots-admin', '/admin-portal', '/manage', '/new-admin', '/app', '/pwa'];
  
  // Use includes check for more flexible path matching
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  if (shouldHide) {
    return null;
  }
  
  return <Navbar />;
};

// Navbar
// ============================================
// PROMO TOP BAR - Controlled by Admin Settings
// ============================================
const PromoTopBar = () => {
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(false);
  const [promoSettings, setPromoSettings] = useState(null);
  
  // Hide on bio-scan, quiz pages, OROÉ, LA VELA, Admin, and PWA pages
  const hiddenPaths = ['/Bio-Age-Repair-Scan', '/quiz', '/skin-scan', '/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/admin', '/reroots-admin', '/admin-portal', '/manage', '/new-admin', '/app', '/pwa'];
  const shouldHideOnPath = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  useEffect(() => {
    // Fetch promo settings from admin
    const fetchPromoSettings = async () => {
      try {
        const res = await fetch(`${API}/store-settings`);
        const data = await res.json();
        // Only show if promo_banner_enabled is explicitly TRUE
        if (data.promo_banner_enabled === true && data.promo_banner_title) {
          setPromoSettings({
            enabled: true,
            title: data.promo_banner_title,
            text: data.promo_banner_text || '',
            discount: data.promo_banner_discount_percent || 0,
            link: data.promo_banner_link || '/waitlist'
          });
          const dismissed = sessionStorage.getItem('promo_bar_dismissed');
          if (!dismissed) {
            setIsVisible(true);
          }
        } else {
          // Disabled - don't show
          setIsVisible(false);
        }
      } catch (err) {
        // If no settings, don't show the bar
        setIsVisible(false);
      }
    };
    fetchPromoSettings();
  }, []);
  
  const handleDismiss = () => {
    setIsVisible(false);
    sessionStorage.setItem('promo_bar_dismissed', 'true');
  };
  
  // Don't show if: disabled, hidden path, or dismissed
  if (!isVisible || shouldHideOnPath || !promoSettings?.enabled) return null;
  
  const displayText = promoSettings.discount > 0 
    ? `${promoSettings.title} — ${promoSettings.discount}% off!`
    : promoSettings.title;
  
  return (
    <div className="bg-gradient-to-r from-[#D4AF37] via-[#E5C158] to-[#D4AF37] text-white py-2.5 px-4 relative z-[60]">
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 text-center">
        <Sparkles className="h-4 w-4 hidden sm:block" />
        <p className="text-xs sm:text-sm font-medium tracking-wide">
          <span className="hidden sm:inline">🧬 {displayText} </span>
          <span className="sm:hidden">🧬 {displayText} </span>
          <Link to={promoSettings.link} className="font-bold ml-1 underline hover:no-underline">Join Now</Link>
        </p>
        <button 
          onClick={handleDismiss}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-white/70 hover:text-white transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

// ExitIntentModal - Extracted to /components/modals/ExitIntentModal.js (lazy-loaded)

// ============================================
// AUTO-APPLY DISCOUNT FROM URL
// ============================================
const AutoApplyDiscountHandler = () => {
  const location = useLocation();
  
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const discountCode = params.get('discount') || params.get('code') || params.get('promo');
    
    if (discountCode) {
      // Store the discount code for checkout
      localStorage.setItem('auto_apply_discount', discountCode.toUpperCase());
      // Show confirmation toast
      toast.success(`Discount code ${discountCode.toUpperCase()} will be applied at checkout!`, {
        duration: 4000,
        icon: '🎁'
      });
    }
  }, [location.search]);
  
  return null; // This component doesn't render anything
};

const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [isPending, startTransition] = useTransition(); // INP optimization for mobile menu
  const [currentLang, setCurrentLang] = useState(() => {
    const saved = localStorage.getItem("reroots_lang");
    // If no saved language, default to Canadian English
    if (!saved) {
      localStorage.setItem("reroots_lang", "en-CA");
      return "en-CA";
    }
    return saved;
  });
  const { user, logout } = useAuth();
  const { itemCount, setSideCartOpen } = useCart();
  const { settings } = useStoreSettings();
  const navigate = useNavigate();
  const location = useLocation();
  
  // Mobile menu toggle with startTransition for instant feedback
  const toggleMobileMenu = useCallback(() => {
    startTransition(() => {
      setIsOpen(prev => !prev);
    });
  }, []);
  
  // Sync with store settings default language
  useEffect(() => {
    if (settings?.language?.default_language) {
      const defaultLang = settings.language.default_language;
      const currentStored = localStorage.getItem("reroots_lang");
      // If current stored language is not in supported languages, reset to default
      const supported = settings.language.supported_languages || ["en-CA"];
      if (currentStored && !supported.includes(currentStored)) {
        localStorage.setItem("reroots_lang", defaultLang);
        setCurrentLang(defaultLang);
      }
    }
  }, [settings]);
  
  // Check if on admin pages - hide cart for admins
  const isAdminPage = location.pathname.startsWith('/admin') || 
                      location.pathname.startsWith('/reroots-admin') || 
                      location.pathname.startsWith('/admin-portal') ||
                      location.pathname.startsWith('/manage') ||
                      location.pathname.startsWith('/new-admin');

  const languages = [
    { code: "en-CA", name: "English (Canada)", flag: "🇨🇦" },
    { code: "en", name: "English (UK)", flag: "🇬🇧" },
    { code: "en-US", name: "English (US)", flag: "🇺🇸" },
    { code: "fr", name: "Français", flag: "🇫🇷" },
    { code: "es", name: "Español", flag: "🇪🇸" },
    { code: "hi", name: "हिंदी", flag: "🇮🇳" },
    { code: "zh", name: "中文", flag: "🇨🇳" },
    { code: "ar", name: "العربية", flag: "🇸🇦" },
    { code: "pt", name: "Português", flag: "🇧🇷" },
    { code: "de", name: "Deutsch", flag: "🇩🇪" },
    { code: "ja", name: "日本語", flag: "🇯🇵" },
    { code: "ko", name: "한국어", flag: "🇰🇷" },
    { code: "ru", name: "Русский", flag: "🇷🇺" },
    { code: "it", name: "Italiano", flag: "🇮🇹" },
    { code: "nl", name: "Nederlands", flag: "🇳🇱" },
    { code: "tr", name: "Türkçe", flag: "🇹🇷" },
    { code: "pl", name: "Polski", flag: "🇵🇱" },
    { code: "th", name: "ไทย", flag: "🇹🇭" },
    { code: "vi", name: "Tiếng Việt", flag: "🇻🇳" },
    { code: "id", name: "Bahasa Indonesia", flag: "🇮🇩" },
    { code: "ms", name: "Bahasa Melayu", flag: "🇲🇾" },
    { code: "bn", name: "বাংলা", flag: "🇧🇩" },
    { code: "ta", name: "தமிழ்", flag: "🇮🇳" },
    { code: "te", name: "తెలుగు", flag: "🇮🇳" },
    { code: "mr", name: "मराठी", flag: "🇮🇳" },
    { code: "gu", name: "ગુજરાતી", flag: "🇮🇳" },
    { code: "pa", name: "ਪੰਜਾਬੀ", flag: "🇮🇳" },
    { code: "ur", name: "اردو", flag: "🇵🇰" },
    { code: "fa", name: "فارسی", flag: "🇮🇷" },
    { code: "he", name: "עברית", flag: "🇮🇱" },
    { code: "sv", name: "Svenska", flag: "🇸🇪" },
    { code: "no", name: "Norsk", flag: "🇳🇴" },
    { code: "da", name: "Dansk", flag: "🇩🇰" },
    { code: "fi", name: "Suomi", flag: "🇫🇮" },
    { code: "el", name: "Ελληνικά", flag: "🇬🇷" },
    { code: "cs", name: "Čeština", flag: "🇨🇿" },
    { code: "ro", name: "Română", flag: "🇷🇴" },
    { code: "hu", name: "Magyar", flag: "🇭🇺" },
    { code: "uk", name: "Українська", flag: "🇺🇦" }
  ];

  const supportedLangs = settings?.language?.supported_languages || ["en-CA", "en", "en-US"];
  const availableLangs = languages.filter(l => supportedLangs.includes(l.code));

  const changeLanguage = (code) => {
    setCurrentLang(code);
    localStorage.setItem("reroots_lang", code);
    // Trigger page reload to apply translations
    window.location.reload();
  };

  // Auto-detect browser language on first visit - prioritize Canadian English for English speakers
  useEffect(() => {
    const savedLang = localStorage.getItem("reroots_lang");
    if (!savedLang && settings?.language?.auto_detect) {
      const browserLang = navigator.language || 'en-CA';
      const baseLang = browserLang.split('-')[0];
      
      // For English speakers, always default to Canadian English
      if (baseLang === 'en') {
        setCurrentLang('en-CA');
        localStorage.setItem("reroots_lang", 'en-CA');
      } else {
        // For other languages, try to match the base language
        const matchedLang = languages.find(l => l.code === baseLang);
        if (matchedLang && supportedLangs.includes(baseLang)) {
          setCurrentLang(baseLang);
          localStorage.setItem("reroots_lang", baseLang);
        } else {
          // Default to Canadian English if no match
          setCurrentLang('en-CA');
          localStorage.setItem("reroots_lang", 'en-CA');
        }
      }
    }
  }, [settings, supportedLangs]);

  // PERFORMANCE: IntersectionObserver for sticky header (Zero Forced Reflows)
  // This runs off the main thread - no layout thrashing on scroll
  useEffect(() => {
    // Create a sentinel element at the top of the page
    const sentinel = document.createElement('div');
    sentinel.id = 'header-scroll-sentinel';
    sentinel.style.cssText = 'position: absolute; top: 20px; left: 0; width: 1px; height: 1px; pointer-events: none;';
    document.body.prepend(sentinel);
    
    const handler = (entries) => {
      // If sentinel is NOT visible, user has scrolled down
      setScrolled(!entries[0].isIntersecting);
    };
    
    // IntersectionObserver is native and runs off the main thread
    const observer = new IntersectionObserver(handler, {
      threshold: 0,
      rootMargin: '0px'
    });
    
    observer.observe(sentinel);
    
    return () => {
      observer.disconnect();
      sentinel.remove();
    };
  }, []);

  // Global search state
  const [globalSearch, setGlobalSearch] = useState("");
  const [showSearchModal, setShowSearchModal] = useState(false);

  const handleGlobalSearch = (e) => {
    e.preventDefault();
    if (globalSearch.trim()) {
      navigate(`/shop?search=${encodeURIComponent(globalSearch.trim())}`);
      setShowSearchModal(false);
      setGlobalSearch("");
    }
  };

  return (
    <header 
      className={`fixed top-0 left-0 right-0 w-full z-50 transition-all duration-500 ease-out ${
        scrolled 
          ? "bg-white/95 backdrop-blur-lg shadow-[0_2px_20px_rgba(0,0,0,0.08)] border-b border-gray-100/50" 
          : "bg-white backdrop-blur-lg"
      }`}
    >
      {/* Global Search Modal */}
      {showSearchModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-20" onClick={() => setShowSearchModal(false)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-xl mx-4 p-4" onClick={e => e.stopPropagation()}>
            <form onSubmit={handleGlobalSearch}>
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search products, categories..."
                  value={globalSearch}
                  onChange={(e) => setGlobalSearch(e.target.value)}
                  className="w-full pl-12 pr-4 py-3 text-lg border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#F8A5B8]"
                  autoFocus
                />
                <button type="button" onClick={() => setShowSearchModal(false)} className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-2">Press Enter to search or ESC to close</p>
            </form>
          </div>
        </div>
      )}

      <nav className="w-full">
        <div className={`flex items-center justify-between px-4 md:px-6 lg:px-12 transition-all duration-500 ${scrolled ? "h-16" : "h-20"}`}>
          <Link to="/" className="flex items-center gap-2" data-testid="logo-link">
            <div 
              className={`rounded-lg transition-all duration-500 ${scrolled ? "p-1.5" : "p-2"}`}
              style={{ backgroundColor: scrolled ? `rgba(255, 255, 255, ${settings?.logo_bg_opacity ?? 0.9})` : 'transparent' }}
            >
              <img 
                src={(() => {
                  const logoUrl = settings?.logo_url || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png";
                  // Route through Cloudinary for optimization
                  if (logoUrl.includes('cloudinary.com')) return logoUrl;
                  return `https://res.cloudinary.com/ddpphzqdg/image/fetch/w_200,h_64,c_fit,q_auto,f_auto/${encodeURIComponent(logoUrl)}`;
                })()}
                alt="Reroots Aesthetics Inc. - Canadian Biotech Skincare" 
                className={`w-auto object-contain transition-all duration-500 ${
                  scrolled 
                    ? (settings?.logo_size === 'small' ? 'h-8 md:h-10' :
                       settings?.logo_size === 'large' ? 'h-14 md:h-16' :
                       settings?.logo_size === 'xlarge' ? 'h-16 md:h-18' :
                       'h-10 md:h-12')
                    : (settings?.logo_size === 'small' ? 'h-10 md:h-12' :
                       settings?.logo_size === 'large' ? 'h-20 md:h-24' :
                       settings?.logo_size === 'xlarge' ? 'h-24 md:h-28' :
                       'h-14 md:h-16')
                }`}
                style={{ mixBlendMode: 'multiply' }}
                width="200"
                height="64"
                fetchPriority="high"
                decoding="async"
              />
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-6">
            <Link to="/products" className={`font-medium transition-all ${scrolled ? 'text-[#2D2A2E] text-xs' : 'text-white text-sm'} hover:text-[#F8A5B8]`} data-testid="nav-products">
              {UI_TRANSLATIONS[currentLang]?.shop || "Shop"}
            </Link>
            <Link to="/products?category=serums" className={`font-medium transition-all ${scrolled ? 'text-[#5A5A5A] text-xs' : 'text-white/90 text-sm'} hover:text-[#F8A5B8]`} data-testid="nav-serums">
              Serums
            </Link>
            <Link to="/about" className={`font-medium transition-all ${scrolled ? 'text-[#5A5A5A] text-xs' : 'text-white/90 text-sm'} hover:text-[#F8A5B8]`} data-testid="nav-about">
              {UI_TRANSLATIONS[currentLang]?.about || "About"}
            </Link>
            {/* OROÉ & LA VELA BIANCA - Hidden until launch */}
            {/* 
            <Link 
              to="/oroe" 
              className={`font-medium transition-all ${scrolled ? 'text-xs' : 'text-sm'}`}
              data-testid="nav-oroe"
            >
              <span className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] bg-clip-text text-transparent hover:from-[#FFD700] hover:to-[#D4AF37]">
                OROÉ
              </span>
            </Link>
            */}
            {/* Prominent Shop Now CTA - Always visible */}
            <Link to="/shop" data-testid="nav-shop-now-cta">
              <Button className={`bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full font-semibold shadow-md hover:shadow-lg transition-all ${scrolled ? 'px-5 py-1.5 text-xs' : 'px-6 py-2 text-sm'}`}>
                Shop Now
              </Button>
            </Link>
          </div>

          <div className="flex items-center gap-3">
            {/* Search Button */}
            <Button 
              variant="ghost" 
              size="icon" 
              className="transition-all hover:bg-gray-100"
              onClick={() => setShowSearchModal(true)}
              title="Search"
            >
              <Search className="h-5 w-5 text-black" strokeWidth={2} />
            </Button>

            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="transition-all hover:bg-gray-100" data-testid="user-menu-trigger">
                    <User className="h-5 w-5 text-black" strokeWidth={2} />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48 bg-white">
                  <div className="px-2 py-1.5">
                    <p className="text-sm font-medium text-[#2D2A2E]">{user.first_name} {user.last_name}</p>
                    <p className="text-xs text-[#5A5A5A]">{user.email}</p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate("/account")} data-testid="menu-account" className="text-[#2D2A2E] cursor-pointer">
                    <Package className="mr-2 h-4 w-4" /> {UI_TRANSLATIONS[currentLang]?.account || "Orders"}
                  </DropdownMenuItem>
                  {user.is_admin && (
                    <DropdownMenuItem onClick={() => navigate("/admin")} data-testid="menu-admin" className="text-[#2D2A2E] cursor-pointer">
                      <LayoutDashboard className="mr-2 h-4 w-4" /> Admin
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={logout} data-testid="menu-logout" className="text-[#2D2A2E] cursor-pointer">
                    <LogOut className="mr-2 h-4 w-4" /> {UI_TRANSLATIONS[currentLang]?.logout || "Logout"}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <Link to="/login" data-testid="nav-login" aria-label="Login to your account">
                <Button variant="ghost" size="icon" className="transition-all hover:bg-gray-100" aria-label="Login">
                  <User className="h-5 w-5 text-black" strokeWidth={2} aria-hidden="true" />
                </Button>
              </Link>
            )}

            {/* Cart - Hidden on admin pages */}
            {!isAdminPage && (
              <>
                {/* Wishlist */}
                <Link to="/wishlist" className="relative hidden md:block" data-testid="nav-wishlist" aria-label="View your wishlist">
                  <Button variant="ghost" size="icon" className="transition-all hover:bg-gray-100" aria-label="Wishlist">
                    <Heart className="h-5 w-5 text-black" strokeWidth={2} aria-hidden="true" />
                  </Button>
                </Link>
                
                {/* Cart - Opens Side Cart */}
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={() => setSideCartOpen(true)} 
                  className="relative transition-all hover:bg-gray-100"
                  data-testid="nav-cart"
                  aria-label={`Shopping cart with ${itemCount} items`}
                >
                  <ShoppingBag className="h-5 w-5 text-black" strokeWidth={2} aria-hidden="true" />
                  {itemCount > 0 && (
                    <span className="absolute -top-1 -right-1 bg-[#F8A5B8] text-[#2D2A2E] text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center" aria-hidden="true">
                      {itemCount}
                    </span>
                  )}
                </Button>
              </>
            )}

            {/* Language Selector - Always visible */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-1 px-2 transition-all hover:bg-gray-100" data-testid="language-selector" aria-label="Select language">
                  <Globe className="h-4 w-4 text-black" strokeWidth={2} aria-hidden="true" />
                  <span className="text-sm">{languages.find(l => l.code === currentLang)?.flag || "🇨🇦"}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48 max-h-80 overflow-y-auto">
                <div className="px-2 py-1.5 text-xs text-[#5A5A5A] border-b">Select Language</div>
                {(availableLangs.length > 0 ? availableLangs : languages.slice(0, 10)).map(lang => (
                  <DropdownMenuItem 
                    key={lang.code} 
                    onClick={() => changeLanguage(lang.code)}
                    className={currentLang === lang.code ? "bg-[#F8A5B8]/10" : ""}
                  >
                    <span className="mr-2">{lang.flag}</span> {lang.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            
            {/* Currency Selector */}
            <CurrencySelector scrolled={scrolled} />

            <Button variant="ghost" size="icon" className="md:hidden transition-all hover:bg-gray-100" onClick={toggleMobileMenu} data-testid="mobile-menu-toggle" aria-label={isOpen ? "Close menu" : "Open menu"}>
              {isOpen ? <X className="h-5 w-5 text-black" strokeWidth={2} aria-hidden="true" /> : <Menu className="h-5 w-5 text-black" strokeWidth={2} aria-hidden="true" />}
            </Button>
          </div>
        </div>

        {/* Mobile Nav */}
        <AnimatePresence>
          {isOpen && (
            <MotionDiv
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className="md:hidden overflow-hidden absolute top-full left-0 right-0 bg-white/95 backdrop-blur-lg shadow-xl border-t border-gray-100/50 z-50"
            >
              <div className="py-4 px-6 space-y-4">
                {/* Prominent Shop Now Button for Mobile */}
                <Link to="/shop" onClick={() => setIsOpen(false)}>
                  <Button className="w-full bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-4 font-semibold text-lg shadow-md">
                    Shop Now
                  </Button>
                </Link>
                <Link to="/products" className="block text-lg font-medium text-[#2D2A2E] hover:text-[#F8A5B8] transition-colors" onClick={() => setIsOpen(false)}>{UI_TRANSLATIONS[currentLang]?.shop_all || "Shop All"}</Link>
                <Link to="/products?category=serums" className="block text-lg font-medium text-[#5A5A5A] hover:text-[#F8A5B8] transition-colors" onClick={() => setIsOpen(false)}>Serums</Link>
                <Link to="/about" className="block text-lg font-medium text-[#5A5A5A] hover:text-[#F8A5B8] transition-colors" onClick={() => setIsOpen(false)}>{UI_TRANSLATIONS[currentLang]?.about || "About"}</Link>
                {!user && (
                  <Link to="/login" className="block text-lg font-medium text-[#F8A5B8] hover:text-[#2D2A2E] transition-colors" onClick={() => setIsOpen(false)}>{UI_TRANSLATIONS[currentLang]?.login || "Login"}</Link>
                )}
              </div>
            </MotionDiv>
          )}
        </AnimatePresence>
      </nav>
    </header>
  );
};

// Notify Me Form Component for Out of Stock Products
const NotifyMeForm = ({ productId, productName }) => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error("Please enter your email");
      return;
    }
    
    setLoading(true);
    try {
      await axios.post(`${API}/waitlist`, {
        email,
        product_id: productId,
        product_name: productName
      });
      setSubmitted(true);
      toast.success("You'll be notified when this product is available!");
    } catch (error) {
      toast.error("Failed to join waitlist. Please try again.");
    }
    setLoading(false);
  };

  if (submitted) {
    return (
      <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-center">
        <Check className="h-8 w-8 text-green-500 mx-auto mb-2" />
        <p className="text-green-800 font-medium">You're on the list!</p>
        <p className="text-green-600 text-sm">We'll email you when {productName} is back in stock.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-2">
        <Input
          type="email"
          placeholder="Enter your email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="flex-1"
          required
        />
        <Button 
          type="submit" 
          disabled={loading}
          className="bg-[#F8A5B8] hover:bg-[#e8959a] text-white px-6"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Notify Me"}
        </Button>
      </div>
      <p className="text-xs text-gray-500 text-center">
        Be the first to know when this product is available
      </p>
    </form>
  );
};

// Newsletter Form Component with SMS/Email preferences
const NewsletterForm = ({ thankYouMessage, buttonText }) => {
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [countryCode, setCountryCode] = useState("CA");
  const [preferEmail, setPreferEmail] = useState(true);
  const [preferSms, setPreferSms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showPhoneField, setShowPhoneField] = useState(false);

  const handleToggle = (type) => {
    if (type === "email") {
      // Can't turn off email if SMS is off
      if (preferEmail && !preferSms) {
        toast.error("At least one notification method must be selected");
        return;
      }
      setPreferEmail(!preferEmail);
      if (!preferEmail) setShowPhoneField(false);
    } else {
      // Can't turn off SMS if email is off
      if (preferSms && !preferEmail) {
        toast.error("At least one notification method must be selected");
        return;
      }
      const newPreferSms = !preferSms;
      setPreferSms(newPreferSms);
      if (newPreferSms) setShowPhoneField(true);
    }
  };

  const handlePhoneChange = (e) => {
    const value = e.target.value;
    // Only allow numbers, +, and spaces
    const cleaned = value.replace(/[^\d\s+()-]/g, '');
    setPhone(cleaned);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!preferEmail && !preferSms) {
      toast.error("Please select at least one notification method");
      return;
    }
    
    if (preferEmail && !email) {
      toast.error("Please enter your email");
      return;
    }
    
    if (preferSms && !phone) {
      toast.error("Please enter your phone number for SMS notifications");
      return;
    }
    
    setLoading(true);
    try {
      // Format phone with country code if provided
      const formattedPhone = preferSms && phone ? formatPhoneWithCountryCode(phone, countryCode) : null;
      
      await axios.post(`${API}/newsletter/subscribe`, { 
        email: preferEmail ? email : null,
        phone: formattedPhone,
        prefer_email: preferEmail,
        prefer_sms: preferSms
      });
      toast.success(thankYouMessage || "Thanks for subscribing! 🎉 Check your email for confirmation.");
      setEmail("");
      setPhone("");
    } catch (err) {
      if (err.response?.data?.detail?.includes("already") || err.response?.data?.detail?.includes("updated")) {
        toast.info("Your preferences have been updated!");
      } else {
        toast.error(err.response?.data?.detail || "Failed to subscribe. Please try again.");
      }
    }
    setLoading(false);
  };

  return (
    <form className="space-y-4 max-w-md mx-auto" onSubmit={handleSubmit}>
      {/* Email/SMS Toggle */}
      <div className="flex justify-center gap-6 mb-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <div 
            onClick={() => handleToggle("email")}
            className={`w-12 h-6 rounded-full flex items-center transition-colors ${
              preferEmail ? 'bg-[#2D2A2E]' : 'bg-white/50'
            }`}
          >
            <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${
              preferEmail ? 'translate-x-6' : 'translate-x-0.5'
            }`} />
          </div>
          <span className="text-[#2D2A2E] font-medium">📧 Email</span>
        </label>
        
        <label className="flex items-center gap-2 cursor-pointer">
          <div 
            onClick={() => handleToggle("sms")}
            className={`w-12 h-6 rounded-full flex items-center transition-colors ${
              preferSms ? 'bg-[#2D2A2E]' : 'bg-white/50'
            }`}
          >
            <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${
              preferSms ? 'translate-x-6' : 'translate-x-0.5'
            }`} />
          </div>
          <span className="text-[#2D2A2E] font-medium">📱 SMS</span>
        </label>
      </div>
      
      {/* Input Fields */}
      <div className="flex flex-col gap-3">
        {preferEmail && (
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter your email"
            required={preferEmail}
            className="bg-white border-0 rounded-full px-6 h-14"
            data-testid="newsletter-email"
          />
        )}
        
        {(preferSms || showPhoneField) && (
          <div className="flex gap-2">
            <Select value={countryCode} onValueChange={setCountryCode}>
              <SelectTrigger className="w-24 bg-white border-0 rounded-full h-14">
                <SelectValue>
                  {COUNTRY_CODES[countryCode]?.flag} {COUNTRY_CODES[countryCode]?.code}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {Object.entries(COUNTRY_CODES).map(([code, data]) => (
                  <SelectItem key={code} value={code}>
                    {data.flag} {data.code} ({data.name})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="tel"
              value={phone}
              onChange={handlePhoneChange}
              placeholder="Phone number"
              required={preferSms}
              className="bg-white border-0 rounded-full px-6 h-14 flex-1"
              data-testid="newsletter-phone"
            />
          </div>
        )}
      </div>
      
      <Button 
        type="submit" 
        disabled={loading}
        className="w-full bg-[#2D2A2E] text-white hover:bg-[#2D2A2E]/90 rounded-full px-8 h-14" 
        data-testid="newsletter-submit"
      >
        {loading ? "Subscribing..." : buttonText || "Subscribe"}
      </Button>
    </form>
  );
};

// Footer Wrapper - Hides footer on specific pages
const FooterWrapper = () => {
  const location = useLocation();
  const hiddenPaths = ['/Bio-Age-Repair-Scan', '/bio-scan', '/quiz', '/skin-scan', '/influencer', '/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/admin', '/reroots-admin', '/admin-portal', '/manage', '/new-admin', '/app', '/pwa'];
  
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  if (shouldHide) {
    return null;
  }
  
  return <Footer />;
};

// Chat Widget Wrapper - Hides chat on PWA and admin pages
const RerootsChatWrapper = () => {
  const location = useLocation();
  const hiddenPaths = ['/pwa', '/admin', '/reroots-admin', '/admin-portal', '/manage', '/new-admin'];
  
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  if (shouldHide) {
    return null;
  }
  
  return (
    <Suspense fallback={null}>
      <RerootsChatLazy />
    </Suspense>
  );
};

// Live Chat Widget Wrapper - Hides on PWA pages
const LiveChatWidgetWrapper = () => {
  const location = useLocation();
  const hiddenPaths = ['/pwa', '/admin', '/reroots-admin'];
  
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  if (shouldHide) {
    return null;
  }
  
  return (
    <Suspense fallback={null}>
      <LiveChatWidgetLazy />
    </Suspense>
  );
};

// Referral Widget Wrapper - Hides on PWA pages
const ReferralWidgetWrapper = () => {
  const location = useLocation();
  const hiddenPaths = ['/pwa', '/admin', '/reroots-admin'];
  
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  if (shouldHide) {
    return null;
  }
  
  return (
    <Suspense fallback={null}>
      <ReferralWidgetLazy />
    </Suspense>
  );
};

// Footer - Now uses dynamic content from SiteContentProvider
const Footer = () => {
  const { settings } = useStoreSettings();
  const { content } = useSiteContent();
  const footer = content?.footer || {};
  
  // Optimize logo through Cloudinary for AVIF/WebP and proper sizing
  const rawLogoUrl = settings?.logo_url || "https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png";
  const logoUrl = rawLogoUrl.includes('cloudinary.com') 
    ? rawLogoUrl 
    : `https://res.cloudinary.com/ddpphzqdg/image/fetch/w_150,h_48,c_fit,q_auto,f_auto/${encodeURIComponent(rawLogoUrl)}`;
  
  const brandDescription = footer.brand_description || "Reroots Aesthetics Inc. is a Canadian biotech laboratory specializing in PDRN skincare. Our flagship Aura-Gen 17% Active Recovery Complex features PDRN, TXA, and Argireline for visible skin rejuvenation. Made in Toronto.";
  const instagramUrl = footer.instagram_url || "https://instagram.com/reroots.ca";
  const tiktokUrl = footer.tiktok_url || "https://tiktok.com/@reroots.ca";
  const facebookUrl = footer.facebook_url || "https://facebook.com/reroots.ca";
  const twitterUrl = footer.twitter_url || "https://twitter.com/rerootscanada";
  const supportEmail = footer.support_email || "support@reroots.ca";
  const copyright = footer.copyright || `${new Date().getFullYear()} ReRoots Biotech Skincare`;
  
  // Email share handler - opens native email app
  const handleEmailShare = () => {
    const subject = encodeURIComponent("Check out ReRoots Biotech Skincare");
    const body = encodeURIComponent(`Hi,\n\nI wanted to share ReRoots with you - a Canadian biotech skincare brand with high-performance PDRN serums that help skin look visibly rejuvenated.\n\nVisit: ${window.location.origin}\n\nBest regards`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };
  
  return (
    <footer 
      className="bg-[#2D2A2E] text-white py-16 md:py-24 min-h-[500px] md:min-h-[450px]"
      style={{ contain: 'layout paint', contentVisibility: 'auto' }}
    >
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-10 lg:gap-8">
          {/* Brand Section */}
          <div className="sm:col-span-2">
            <div 
              className="rounded-lg p-3 w-fit mb-4"
              style={{ backgroundColor: `rgba(255, 255, 255, ${settings?.logo_bg_opacity ?? 0.9})` }}
            >
              <img 
                src={logoUrl} 
                alt="Reroots Aesthetics Inc. Logo" 
                className="h-12 w-auto object-contain"
                loading="lazy"
                width="150"
                height="48"
              />
            </div>
            <p className="text-white/70 max-w-md mb-6 text-sm leading-relaxed">
              {brandDescription}
            </p>
            <div className="flex gap-4 items-center">
              <a href={instagramUrl} target="_blank" rel="noopener noreferrer" className="hover:text-[#F8A5B8] transition-colors" data-testid="footer-instagram" title="Follow us on Instagram">
                <Instagram className="h-5 w-5" />
              </a>
              <a href={tiktokUrl} target="_blank" rel="noopener noreferrer" className="hover:text-[#F8A5B8] transition-colors" data-testid="footer-tiktok" title="Follow us on TikTok">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z"/>
                </svg>
              </a>
              <a href={facebookUrl} target="_blank" rel="noopener noreferrer" className="hover:text-[#F8A5B8] transition-colors" data-testid="footer-facebook" title="Follow us on Facebook">
                <Facebook className="h-5 w-5" />
              </a>
              <a href={twitterUrl} target="_blank" rel="noopener noreferrer" className="hover:text-[#F8A5B8] transition-colors" data-testid="footer-twitter" title="Follow us on Twitter/X">
                <Twitter className="h-5 w-5" />
              </a>
              <a 
                href="https://wa.me/16475551234?text=Hi!%20I%20have%20a%20question%20about%20ReRoots%20skincare." 
                target="_blank" 
                rel="noopener noreferrer" 
                className="hover:text-green-400 transition-colors" 
                data-testid="footer-whatsapp" 
                title="Message us on WhatsApp"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
              </a>
              <button onClick={handleEmailShare} className="hover:text-[#F8A5B8] transition-colors ml-2" title="Share via Email">
                <Mail className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* SHOP Section - Products & Categories */}
          <div>
            <h3 className="font-bold text-sm uppercase tracking-wider mb-4">Shop</h3>
            <ul className="space-y-2">
              <li><Link to="/products" className="text-white/70 hover:text-[#F8A5B8] transition-colors">All Products</Link></li>
              <li><Link to="/products/prod-aura-gen" className="text-white/70 hover:text-[#F8A5B8] transition-colors">AURA-GEN Serum</Link></li>
              <li><Link to="/shop/dark-circles" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Dark Circles</Link></li>
              <li><Link to="/shop/pigmentation" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Pigmentation</Link></li>
              <li><Link to="/shop/anti-aging" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Anti-Aging</Link></li>
              <li><Link to="/shop/hydration" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Hydration</Link></li>
            </ul>
          </div>

          {/* PROGRAMS Section - Interactive Tools & Programs */}
          <div>
            <h3 className="font-bold text-sm uppercase tracking-wider mb-4">Programs</h3>
            <ul className="space-y-2">
              <li><Link to="/skin-quiz" className="text-white/70 hover:text-[#F8A5B8] transition-colors flex items-center gap-1">
                <Sparkles className="h-3 w-3" /> Skin Quiz
              </Link></li>
              <li><Link to="/Bio-Age-Repair-Scan" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Bio-Age Scan</Link></li>
              <li><Link to="/aura-gen-protocol" className="text-white/70 hover:text-[#C9A84C] transition-colors">30-Day Protocol</Link></li>
              <li><Link to="/molecular-auditor" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Product Compare</Link></li>
              <li><Link to="/founding-member" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Founding Member</Link></li>
              <li><Link to="/apply-partner" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Partner Program</Link></li>
            </ul>
          </div>

          {/* LEARN & SUPPORT Section */}
          <div>
            <h3 className="font-bold text-sm uppercase tracking-wider mb-4">Support</h3>
            <ul className="space-y-2">
              <li><Link to="/about" className="text-white/70 hover:text-[#F8A5B8] transition-colors">About Us</Link></li>
              <li><Link to="/science" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Science of PDRN</Link></li>
              <li><Link to="/science-glossary" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Science Glossary</Link></li>
              <li><Link to="/pdrn-comparison-guide" className="text-white/70 hover:text-[#F8A5B8] transition-colors">PDRN Comparison Guide</Link></li>
              <li><Link to="/blog" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Blog</Link></li>
              <li><Link to="/faq" className="text-white/70 hover:text-[#F8A5B8] transition-colors">FAQ</Link></li>
              <li><Link to="/contact" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Contact Us</Link></li>
              <li><Link to="/shipping-policy" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Shipping Policy</Link></li>
              <li><Link to="/return-policy" className="text-white/70 hover:text-[#F8A5B8] transition-colors">Returns & Refunds</Link></li>
              <li><a href={`mailto:${supportEmail}`} className="text-white/70 hover:text-[#F8A5B8] transition-colors">{supportEmail}</a></li>
            </ul>
          </div>
        </div>

        <Separator className="my-12 bg-white/10" />

        {/* 2026 Trust Badges - Green Hosting, Security, Made in Canada */}
        <div className="flex flex-wrap justify-center gap-6 mb-10">
          {/* Green Hosted Badge */}
          <div className="flex items-center gap-2 px-4 py-2 bg-green-900/30 rounded-full border border-green-500/30">
            <svg className="h-4 w-4 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3c.132 0 .263 0 .393 0a7.5 7.5 0 0 0 7.92 12.446a9 9 0 1 1 -8.313 -12.454z" />
              <path d="M17 4a2 2 0 0 0 2 2a2 2 0 0 0 -2 2a2 2 0 0 0 -2 -2a2 2 0 0 0 2 -2" />
            </svg>
            <span className="text-xs text-green-300 font-medium">Carbon Neutral Hosted</span>
          </div>
          
          {/* SSL Secure Badge */}
          <div className="flex items-center gap-2 px-4 py-2 bg-blue-900/30 rounded-full border border-blue-500/30">
            <svg className="h-4 w-4 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span className="text-xs text-blue-300 font-medium">SSL Secure Checkout</span>
          </div>
          
          {/* Made in Canada Badge */}
          <div className="flex items-center gap-2 px-4 py-2 bg-red-900/30 rounded-full border border-red-500/30">
            <span className="text-base">🇨🇦</span>
            <span className="text-xs text-red-300 font-medium">Made in Canada</span>
          </div>
          
          {/* Cruelty Free Badge */}
          <div className="flex items-center gap-2 px-4 py-2 bg-pink-900/30 rounded-full border border-pink-500/30">
            <svg className="h-4 w-4 text-pink-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
            <span className="text-xs text-pink-300 font-medium">Cruelty-Free</span>
          </div>
          
          {/* WCAG 2.2 Compliant Badge */}
          <div className="flex items-center gap-2 px-4 py-2 bg-purple-900/30 rounded-full border border-purple-500/30">
            <svg className="h-4 w-4 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
            <span className="text-xs text-purple-300 font-medium">WCAG 2.2 Accessible</span>
          </div>
        </div>

        {/* Global Footer Disclaimer - Clean Sans-Serif */}
        <div className="mb-10 text-center">
          <p className="font-clinical text-xs text-white/50 max-w-4xl mx-auto leading-relaxed">
            Disclaimer: ReRoots products are cosmetic in nature and are intended to improve the appearance of the skin. 
            They do not claim to heal, treat, or prevent any medical condition. Results may vary based on individual skin type and usage.
          </p>
        </div>

        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-white/50">
          <div className="text-center md:text-left">
            <p>&copy; {copyright}. All rights reserved.</p>
            <p className="text-xs mt-1 text-white/60">Reroots Aesthetics Inc. | Made in Toronto, Canada</p>
          </div>
          <div className="flex flex-wrap justify-center gap-4 md:gap-6">
            <Link to="/sitemap" className="hover:text-white transition-colors">Sitemap</Link>
            <Link to="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
            <Link to="/terms" className="hover:text-white transition-colors">Terms of Service</Link>
          </div>
        </div>
      </div>
    </footer>
  );
};


// ============================================
// AUTO DISCOUNTS MANAGER - Admin Component to manage automatic checkout discounts
// ============================================
const AutoDiscountsManager = () => {
  const [settings, setSettings] = useState({
    founder_discount_enabled: true,
    founder_discount_percent: 50.0,
    founder_discount_label: "Founder's Launch Subsidy",
    first_purchase_discount_enabled: true,
    first_purchase_discount_percent: 10.0,
    voucher_gate_enabled: true,
    voucher_gate_threshold: 10
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { token } = useAuth();
  
  // Fetch current settings
  useEffect(() => {
    const fetchSettings = async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await axios.get(`${API}/admin/store-settings/auto-discounts`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSettings(res.data);
      } catch (err) {
        console.error('Failed to load auto-discount settings:', err);
        toast.error('Failed to load auto-discount settings');
      } finally {
        setLoading(false);
      }
    };
    
    fetchSettings();
  }, [token]);
  
  const handleToggle = async (field) => {
    const newValue = !settings[field];
    const newSettings = { ...settings, [field]: newValue };
    setSettings(newSettings);
    
    // Auto-save on toggle
    try {
      setSaving(true);
      await axios.put(`${API}/admin/store-settings/auto-discounts`, { [field]: newValue }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${field === 'founder_discount_enabled' ? "Founder's Discount" : field === 'first_purchase_discount_enabled' ? "First-Time Discount" : "Voucher Gate"} ${newValue ? 'enabled' : 'disabled'}`);
    } catch (err) {
      // Revert on error
      setSettings(prev => ({ ...prev, [field]: !newValue }));
      toast.error('Failed to update setting');
    } finally {
      setSaving(false);
    }
  };
  
  const handleSavePercent = async (field, value) => {
    try {
      setSaving(true);
      await axios.put(`${API}/admin/store-settings/auto-discounts`, { [field]: parseFloat(value) }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Discount percentage updated');
    } catch (err) {
      toast.error('Failed to update percentage');
    } finally {
      setSaving(false);
    }
  };
  
  if (!token) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-gray-500">Please log in to manage auto-discounts</p>
      </div>
    );
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }
  
  const activeCount = [
    settings.founder_discount_enabled,
    settings.first_purchase_discount_enabled,
    settings.voucher_gate_enabled
  ].filter(Boolean).length;
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-emerald-600" />
          Auto Discounts
        </h2>
        <Badge className={activeCount === 3 ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"}>
          {activeCount}/3 Active
        </Badge>
      </div>
      
      <p className="text-sm text-[#5A5A5A] mb-4">
        These discounts are automatically applied at checkout based on customer eligibility. Turn them ON/OFF to control what appears in the checkout summary.
      </p>
      
      <div className="space-y-3">
        {/* Founder's Launch Subsidy */}
        <Card className={`transition-all duration-200 ${settings.founder_discount_enabled ? 'border-emerald-200 bg-emerald-50/30' : 'border-gray-200 bg-gray-50 opacity-75'}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${settings.founder_discount_enabled ? 'bg-emerald-100' : 'bg-gray-200'}`}>
                  <Crown className={`w-5 h-5 ${settings.founder_discount_enabled ? 'text-emerald-600' : 'text-gray-400'}`} />
                </div>
                <div>
                  <h3 className="font-semibold text-[#2D2A2E]">Founder's Launch Subsidy</h3>
                  <p className="text-sm text-[#5A5A5A]">
                    {settings.founder_discount_percent}% off for all customers (launch promotion)
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={settings.founder_discount_percent}
                    onChange={(e) => setSettings(prev => ({ ...prev, founder_discount_percent: e.target.value }))}
                    onBlur={(e) => handleSavePercent('founder_discount_percent', e.target.value)}
                    className="w-20 h-8 text-center text-sm"
                    min="0"
                    max="100"
                    disabled={!settings.founder_discount_enabled}
                  />
                  <span className="text-sm text-[#5A5A5A]">%</span>
                </div>
                <Switch
                  checked={settings.founder_discount_enabled}
                  onCheckedChange={() => handleToggle('founder_discount_enabled')}
                  className={settings.founder_discount_enabled ? 'bg-emerald-500' : ''}
                  data-testid="founder-discount-toggle"
                />
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* First-Time Protocol Access */}
        <Card className={`transition-all duration-200 ${settings.first_purchase_discount_enabled ? 'border-purple-200 bg-purple-50/30' : 'border-gray-200 bg-gray-50 opacity-75'}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${settings.first_purchase_discount_enabled ? 'bg-purple-100' : 'bg-gray-200'}`}>
                  <Gift className={`w-5 h-5 ${settings.first_purchase_discount_enabled ? 'text-purple-600' : 'text-gray-400'}`} />
                </div>
                <div>
                  <h3 className="font-semibold text-[#2D2A2E]">First-Time Protocol Access</h3>
                  <p className="text-sm text-[#5A5A5A]">
                    {settings.first_purchase_discount_percent}% off for first-time buyers only
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={settings.first_purchase_discount_percent}
                    onChange={(e) => setSettings(prev => ({ ...prev, first_purchase_discount_percent: e.target.value }))}
                    onBlur={(e) => handleSavePercent('first_purchase_discount_percent', e.target.value)}
                    className="w-20 h-8 text-center text-sm"
                    min="0"
                    max="100"
                    disabled={!settings.first_purchase_discount_enabled}
                  />
                  <span className="text-sm text-[#5A5A5A]">%</span>
                </div>
                <Switch
                  checked={settings.first_purchase_discount_enabled}
                  onCheckedChange={() => handleToggle('first_purchase_discount_enabled')}
                  className={settings.first_purchase_discount_enabled ? 'bg-purple-500' : ''}
                  data-testid="first-purchase-discount-toggle"
                />
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Voucher Gate (Referral Bonus) */}
        <Card className={`transition-all duration-200 ${settings.voucher_gate_enabled ? 'border-amber-200 bg-amber-50/30' : 'border-gray-200 bg-gray-50 opacity-75'}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${settings.voucher_gate_enabled ? 'bg-amber-100' : 'bg-gray-200'}`}>
                  <Users className={`w-5 h-5 ${settings.voucher_gate_enabled ? 'text-amber-600' : 'text-gray-400'}`} />
                </div>
                <div>
                  <h3 className="font-semibold text-[#2D2A2E]">Voucher Gate (Referral Bonus)</h3>
                  <p className="text-sm text-[#5A5A5A]">
                    50% off for customers with {settings.voucher_gate_threshold}+ referrals
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={settings.voucher_gate_threshold}
                    onChange={(e) => setSettings(prev => ({ ...prev, voucher_gate_threshold: e.target.value }))}
                    onBlur={(e) => {
                      const value = parseInt(e.target.value);
                      axios.put(`${API}/admin/store-settings/auto-discounts`, { voucher_gate_threshold: value }, {
                        headers: { Authorization: `Bearer ${token}` }
                      }).then(() => toast.success('Threshold updated')).catch(() => toast.error('Failed to update'));
                    }}
                    className="w-20 h-8 text-center text-sm"
                    min="1"
                    max="100"
                    disabled={!settings.voucher_gate_enabled}
                  />
                  <span className="text-sm text-[#5A5A5A]">refs</span>
                </div>
                <Switch
                  checked={settings.voucher_gate_enabled}
                  onCheckedChange={() => handleToggle('voucher_gate_enabled')}
                  className={settings.voucher_gate_enabled ? 'bg-amber-500' : ''}
                  data-testid="voucher-gate-toggle"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Info Card */}
      <Card className="mt-4 bg-blue-50 border-blue-200">
        <CardContent className="p-4">
          <div className="flex gap-3">
            <AlertTriangle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <strong>How it works:</strong> These discounts stack during checkout. Founder's Subsidy applies first, then First-Time if eligible, then Voucher Gate if the customer has enough referrals. Disable any you don't want to appear in checkout summaries.
            </div>
          </div>
        </CardContent>
      </Card>
      
      {saving && (
        <div className="fixed bottom-4 right-4 bg-[#2D2A2E] text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Saving...
        </div>
      )}
    </div>
  );
};

// ============================================
// MARKETING PROGRAMS MANAGER - Admin Component with Edit/Toggle
// ============================================
const MarketingProgramsManager = () => {
  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingProgram, setEditingProgram] = useState(null);
  const [editForm, setEditForm] = useState({});
  const { user, token } = useAuth();
  
  // Icon mapping
  const iconMap = {
    target: Target,
    crown: Crown,
    users: Users,
    star: Star,
    qrcode: QrCode,
    microscope: Microscope
  };
  
  // Fetch programs when token is available
  useEffect(() => {
    const fetchPrograms = async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await axios.get(`${API}/admin/marketing-programs`, { 
          headers: { Authorization: `Bearer ${token}` }
        });
        setPrograms(res.data.programs || []);
      } catch (err) {
        console.error('Failed to load marketing programs:', err);
        toast.error('Failed to load marketing programs');
      } finally {
        setLoading(false);
      }
    };
    
    fetchPrograms();
  }, [token]);
  
  const handleToggle = async (programId) => {
    try {
      const res = await axios.post(`${API}/admin/marketing-programs/${programId}/toggle`, {}, { 
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(res.data.message);
      // Update local state
      setPrograms(prev => prev.map(p => 
        p.id === programId ? { ...p, enabled: res.data.enabled } : p
      ));
    } catch (err) {
      toast.error('Failed to toggle program');
    }
  };
  
  const handleEdit = (program) => {
    setEditingProgram(program.id);
    setEditForm({
      name: program.name,
      subtitle: program.subtitle,
      description: program.description,
      url: program.url,
      button_text: program.button_text
    });
  };
  
  const handleSaveEdit = async (programId) => {
    try {
      await axios.put(`${API}/admin/marketing-programs/${programId}`, editForm, { 
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Program updated successfully');
      // Update local state
      setPrograms(prev => prev.map(p => 
        p.id === programId ? { ...p, ...editForm } : p
      ));
      setEditingProgram(null);
    } catch (err) {
      toast.error('Failed to update program');
    }
  };
  
  const handleCancelEdit = () => {
    setEditingProgram(null);
    setEditForm({});
  };
  
  // If no token yet, show loading briefly then show message
  if (!token) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-gray-500">Please log in to manage marketing programs</p>
      </div>
    );
  }
  
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#F8A5B8]"></div>
      </div>
    );
  }
  
  const activeCount = programs.filter(p => p.enabled).length;
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-[#C9A86C]" />
          Marketing Programs
        </h2>
        <Badge className={activeCount === programs.length ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"}>
          {activeCount}/{programs.length} Active
        </Badge>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {programs.map((program) => {
          const IconComponent = iconMap[program.icon] || Target;
          const isEditing = editingProgram === program.id;
          
          return (
            <Card 
              key={program.id} 
              className={`border-2 transition-all duration-200 ${
                program.enabled 
                  ? 'border-opacity-30 bg-gradient-to-br' 
                  : 'border-gray-200 bg-gray-50 opacity-60'
              }`}
              style={{
                borderColor: program.enabled ? program.gradient_from : undefined,
                background: program.enabled 
                  ? `linear-gradient(to bottom right, ${program.gradient_from}15, ${program.gradient_to}15)` 
                  : undefined
              }}
            >
              <CardContent className="p-5">
                {/* Header with Toggle */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-12 h-12 rounded-xl flex items-center justify-center"
                      style={{ 
                        background: program.enabled 
                          ? `linear-gradient(to bottom right, ${program.gradient_from}, ${program.gradient_to})`
                          : '#9CA3AF'
                      }}
                    >
                      <IconComponent className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      {isEditing ? (
                        <Input
                          value={editForm.name}
                          onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                          className="font-bold text-sm mb-1"
                        />
                      ) : (
                        <h3 className="font-bold text-[#2D2A2E]">{program.name}</h3>
                      )}
                      {isEditing ? (
                        <Input
                          value={editForm.subtitle}
                          onChange={(e) => setEditForm(prev => ({ ...prev, subtitle: e.target.value }))}
                          className="text-xs"
                        />
                      ) : (
                        <p className="text-sm text-[#5A5A5A]">{program.subtitle}</p>
                      )}
                    </div>
                  </div>
                  
                  {/* ON/OFF Toggle */}
                  <div className="flex flex-col items-end gap-1">
                    <Switch
                      checked={program.enabled}
                      onCheckedChange={() => handleToggle(program.id)}
                      className={program.enabled ? 'data-[state=checked]:bg-green-500' : ''}
                    />
                    <span className={`text-xs font-medium ${program.enabled ? 'text-green-600' : 'text-gray-400'}`}>
                      {program.enabled ? 'ON' : 'OFF'}
                    </span>
                  </div>
                </div>
                
                {/* Description */}
                {isEditing ? (
                  <Textarea
                    value={editForm.description}
                    onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                    className="text-sm mb-4"
                    rows={2}
                  />
                ) : (
                  <p className="text-sm text-[#5A5A5A] mb-4">{program.description}</p>
                )}
                
                {/* URL Edit */}
                {isEditing && (
                  <div className="mb-3 space-y-2">
                    <Input
                      value={editForm.url}
                      onChange={(e) => setEditForm(prev => ({ ...prev, url: e.target.value }))}
                      placeholder="URL path (e.g., /waitlist)"
                      className="text-sm"
                    />
                    <Input
                      value={editForm.button_text}
                      onChange={(e) => setEditForm(prev => ({ ...prev, button_text: e.target.value }))}
                      placeholder="Button text"
                      className="text-sm"
                    />
                  </div>
                )}
                
                {/* Action Buttons */}
                <div className="flex gap-2 mb-3">
                  {isEditing ? (
                    <>
                      <Button
                        size="sm"
                        className="flex-1 bg-green-500 hover:bg-green-600 text-white"
                        onClick={() => handleSaveEdit(program.id)}
                      >
                        <Check className="w-4 h-4 mr-1" />
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleCancelEdit}
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        size="sm"
                        className="flex-1 text-white"
                        style={{ 
                          background: program.enabled 
                            ? `linear-gradient(to right, ${program.gradient_from}, ${program.gradient_to})`
                            : '#9CA3AF'
                        }}
                        onClick={() => window.open(program.url, '_blank')}
                        disabled={!program.enabled}
                      >
                        <ExternalLink className="w-4 h-4 mr-2" />
                        {program.button_text}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleEdit(program)}
                        title="Edit program"
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          navigator.clipboard.writeText(`${window.location.origin}${program.url}`);
                          toast.success('Link copied!');
                        }}
                        disabled={!program.enabled}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </>
                  )}
                </div>
                
                {/* URL Display */}
                <div className="bg-white/80 rounded-lg p-2 text-center">
                  <code 
                    className="text-xs"
                    style={{ color: program.enabled ? program.gradient_from : '#9CA3AF' }}
                  >
                    {window.location.origin}{program.url}
                  </code>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
};


// ============================================
// ANALYTICS DASHBOARD - QR Scans, Traffic, Conversions
// ============================================
const AnalyticsDashboard = () => {
  const [qrData, setQrData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30'); // days
  const { token } = useAuth();
  
  useEffect(() => {
    if (token) {
      fetchAnalytics();
    }
  }, [token, dateRange]);
  
  const fetchAnalytics = async () => {
    try {
      const res = await axios.get(`${API}/admin/analytics/qr-scans`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setQrData(res.data);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
      </div>
    );
  }
  
  const totalScans = qrData?.total_scans || 0;
  const bySource = qrData?.by_source || [];
  const dailyScans = qrData?.daily_scans || [];
  
  // Calculate max for chart scaling
  const maxDaily = Math.max(...dailyScans.map(d => d.count), 1);
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-cyan-500" />
            Analytics Dashboard
          </h2>
          <p className="text-sm text-[#5A5A5A]">Track QR scans, traffic sources, and conversions</p>
        </div>
        <Button
          variant="outline"
          onClick={fetchAnalytics}
          className="flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>
      
      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-cyan-50 to-blue-50 border-cyan-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                <QrCode className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-[#5A5A5A]">Total QR Scans</p>
                <p className="text-3xl font-bold text-[#2D2A2E]">{totalScans}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-emerald-50 to-green-50 border-emerald-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-[#5A5A5A]">Thank You Cards</p>
                <p className="text-3xl font-bold text-[#2D2A2E]">
                  {bySource.find(s => s._id?.campaign === 'thank_you_card')?.count || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-purple-50 to-violet-50 border-purple-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center">
                <Tag className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-[#5A5A5A]">Perfume Tags</p>
                <p className="text-3xl font-bold text-[#2D2A2E]">
                  {bySource.find(s => s._id?.campaign === 'perfume_tag')?.count || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-sm text-[#5A5A5A]">Other Sources</p>
                <p className="text-3xl font-bold text-[#2D2A2E]">
                  {bySource.filter(s => !['thank_you_card', 'perfume_tag'].includes(s._id?.campaign)).reduce((sum, s) => sum + s.count, 0)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Scans Chart */}
        <Card>
          <CardContent className="p-6">
            <h3 className="font-bold text-[#2D2A2E] mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-cyan-500" />
              Daily QR Scans (Last 30 Days)
            </h3>
            
            {dailyScans.length > 0 ? (
              <div className="h-48 flex items-end gap-1">
                {dailyScans.slice(-30).map((day, idx) => (
                  <div
                    key={day._id}
                    className="flex-1 bg-gradient-to-t from-cyan-500 to-blue-500 rounded-t hover:from-cyan-400 hover:to-blue-400 transition-colors cursor-pointer group relative"
                    style={{ height: `${(day.count / maxDaily) * 100}%`, minHeight: day.count > 0 ? '8px' : '2px' }}
                    title={`${day._id}: ${day.count} scans`}
                  >
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-[#2D2A2E] text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap z-10">
                      {day.count}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-[#5A5A5A]">
                No scan data yet. QR codes will be tracked here.
              </div>
            )}
            
            <div className="flex justify-between text-xs text-[#5A5A5A] mt-2">
              <span>{dailyScans[0]?._id || '30 days ago'}</span>
              <span>Today</span>
            </div>
          </CardContent>
        </Card>
        
        {/* Sources Breakdown */}
        <Card>
          <CardContent className="p-6">
            <h3 className="font-bold text-[#2D2A2E] mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-500" />
              Scans by Source
            </h3>
            
            {bySource.length > 0 ? (
              <div className="space-y-3">
                {bySource.map((source, idx) => {
                  const campaign = source._id?.campaign || 'Unknown';
                  const medium = source._id?.source || 'qr_code';
                  const percent = totalScans > 0 ? (source.count / totalScans) * 100 : 0;
                  
                  // Color based on campaign type
                  const colors = {
                    'thank_you_card': 'from-emerald-500 to-green-500',
                    'perfume_tag': 'from-purple-500 to-violet-500',
                    'default': 'from-gray-400 to-gray-500'
                  };
                  const colorClass = colors[campaign] || colors.default;
                  
                  return (
                    <div key={idx}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-[#2D2A2E] font-medium capitalize">
                          {campaign.replace(/_/g, ' ')}
                        </span>
                        <span className="text-[#5A5A5A]">{source.count} ({percent.toFixed(1)}%)</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div 
                          className={`h-full bg-gradient-to-r ${colorClass} rounded-full transition-all duration-500`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-[#5A5A5A]">
                No source data yet
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      
      {/* QR Code URLs Reference */}
      <Card className="border-2 border-dashed border-cyan-300 bg-cyan-50/50">
        <CardContent className="p-6">
          <h3 className="font-bold text-[#2D2A2E] mb-4 flex items-center gap-2">
            <QrCode className="w-5 h-5 text-cyan-600" />
            QR Code URLs for Print Materials
          </h3>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white rounded-lg p-4 border border-cyan-200">
              <p className="text-sm font-medium text-[#2D2A2E] mb-2">📦 Thank You Cards</p>
              <code className="text-xs text-cyan-700 bg-cyan-100 px-2 py-1 rounded block break-all">
                {window.location.origin}/protocol?utm_source=qr_code&utm_medium=print&utm_campaign=thank_you_card
              </code>
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={() => {
                  navigator.clipboard.writeText(`${window.location.origin}/protocol?utm_source=qr_code&utm_medium=print&utm_campaign=thank_you_card`);
                  toast.success('URL copied!');
                }}
              >
                <Copy className="w-3 h-3 mr-1" />
                Copy URL
              </Button>
            </div>
            
            <div className="bg-white rounded-lg p-4 border border-purple-200">
              <p className="text-sm font-medium text-[#2D2A2E] mb-2">🏷️ Perfume Tags</p>
              <code className="text-xs text-purple-700 bg-purple-100 px-2 py-1 rounded block break-all">
                {window.location.origin}/protocol?utm_source=qr_code&utm_medium=print&utm_campaign=perfume_tag
              </code>
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={() => {
                  navigator.clipboard.writeText(`${window.location.origin}/protocol?utm_source=qr_code&utm_medium=print&utm_campaign=perfume_tag`);
                  toast.success('URL copied!');
                }}
              >
                <Copy className="w-3 h-3 mr-1" />
                Copy URL
              </Button>
            </div>
          </div>
          
          <p className="text-xs text-[#5A5A5A] mt-4">
            💡 Use these URLs when generating QR codes. Each scan will be tracked with the campaign source.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};




// Auditor Analytics Card - Shows share & conversion stats
const AuditorAnalyticsCard = ({ API, headers }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await axios.get(`${API}/admin/auditor/share-stats`, { headers });
        if (res.data?.success) {
          setStats(res.data);
        }
      } catch (err) {
        console.error('Failed to fetch auditor stats:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, [API, headers]);
  
  if (loading) {
    return (
      <Card className="mt-4 border-blue-200">
        <CardContent className="p-4">
          <div className="animate-pulse flex items-center gap-2">
            <div className="h-4 w-4 bg-blue-200 rounded" />
            <div className="h-4 w-32 bg-gray-200 rounded" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  if (!stats) return null;
  
  return (
    <Card className="mt-4 border-blue-200 bg-gradient-to-r from-blue-50/50 to-indigo-50/50">
      <CardContent className="p-4">
        <h4 className="font-medium text-[#2D2A2E] mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-600" />
          AURA-GEN Auditor Analytics
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white rounded-lg p-3 text-center shadow-sm">
            <p className="text-2xl font-bold text-blue-600">{stats.total_shares || 0}</p>
            <p className="text-xs text-[#5A5A5A]">Total Shares</p>
          </div>
          <div className="bg-white rounded-lg p-3 text-center shadow-sm">
            <p className="text-2xl font-bold text-indigo-600">{stats.total_audits || 0}</p>
            <p className="text-xs text-[#5A5A5A]">Audits Run</p>
          </div>
          <div className="bg-white rounded-lg p-3 text-center shadow-sm">
            <p className="text-2xl font-bold text-green-600">{stats.leads_captured || 0}</p>
            <p className="text-xs text-[#5A5A5A]">Leads Captured</p>
          </div>
          <div className="bg-white rounded-lg p-3 text-center shadow-sm">
            <p className="text-2xl font-bold text-amber-600">{stats.conversion_rate || 0}%</p>
            <p className="text-xs text-[#5A5A5A]">Conversion Rate</p>
          </div>
        </div>
        {stats.recent_shares_7d > 0 && (
          <p className="text-xs text-[#5A5A5A] mt-3 text-center">
            📈 {stats.recent_shares_7d} shares in the last 7 days
          </p>
        )}
      </CardContent>
    </Card>
  );
};

// Product Card - with translation support
const ProductCard = ({ product, translatedProduct }) => {
  const { addToCart, setSideCartOpen } = useCart();
  const { currentLang } = useTranslation() || {};
  const { formatPrice } = useCurrency();
  const { isInWishlist, toggleWishlist } = useWishlist();
  const [isHovered, setIsHovered] = useState(false);
  
  // Get UI translations
  const lang = currentLang || "en";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;
  
  // Use translated product data if available, otherwise original
  const displayProduct = translatedProduct || product;
  
  // Check if product is pre-order
  const isPreOrder = product.allow_preorder;
  
  // Calculate effective price
  const effectivePrice = product.discount_percent 
    ? product.price * (1 - product.discount_percent / 100) 
    : product.price;
    
  // Texture image for hover effect - use second image or fallback
  const textureImage = product.texture_image || product.images?.[1] || "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=800&q=80";
  
  const handleAddToBag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    addToCart(product.id, 1);
    setSideCartOpen(true);
  };

  return (
    <MotionDiv
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="product-card group relative"
      data-testid={`product-card-${product.id}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Wishlist Button */}
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-3 right-3 z-10 bg-white/90 hover:bg-white shadow-md rounded-full w-9 h-9"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleWishlist(product.id);
        }}
      >
        <Heart 
          className={`h-4 w-4 transition-colors ${isInWishlist(product.id) ? 'fill-red-500 text-red-500' : 'text-gray-600'}`} 
        />
      </Button>
      
      <Link to={`/products/${product.slug || product.id}`}>
        {/* Enhanced Image Container with Texture Hover Effect - 500ms transition */}
        <div className="aspect-[3/4] relative overflow-hidden bg-[#FDF9F9] rounded-2xl mb-5 shadow-[0_8px_30px_rgb(0,0,0,0.04)] group-hover:shadow-[0_20px_50px_rgb(0,0,0,0.1)] transition-all duration-500 border border-transparent group-hover:border-[#D4AF37]/20">
          {/* Loading placeholder */}
          <div className="absolute inset-0 bg-gradient-to-br from-[#FDF9F9] to-[#F0EAEA] flex items-center justify-center z-0">
            <div className="w-10 h-10 border-2 border-[#D4AF37]/30 border-t-[#D4AF37] rounded-full animate-spin" />
          </div>
          
          {/* Main Product Image - Fades out on hover */}
          <img
            src={product.images?.[0] || "https://via.placeholder.com/400x500?text=Product"}
            alt={displayProduct.name}
            loading="lazy"
            decoding="async"
            className="absolute inset-0 w-full h-full object-cover transition-all duration-500 ease-out z-10"
            style={{
              opacity: isHovered ? 0 : 1,
              transform: isHovered ? 'scale(1.02)' : 'scale(1)'
            }}
            onLoad={(e) => {
              const placeholder = e.target.parentElement.querySelector('.animate-spin')?.parentElement;
              if (placeholder) placeholder.style.display = 'none';
            }}
            onError={(e) => {
              e.target.src = "https://via.placeholder.com/400x500?text=Product";
            }}
          />
          
          {/* Texture/Macro Image - Fades in on hover with slight scale for depth */}
          <img
            src={textureImage}
            alt={`${displayProduct.name} texture`}
            loading="lazy"
            decoding="async"
            className="absolute inset-0 w-full h-full object-cover transition-all duration-500 ease-out z-10"
            style={{
              opacity: isHovered ? 1 : 0,
              transform: isHovered ? 'scale(1)' : 'scale(1.08)'
            }}
            onError={(e) => {
              e.target.src = product.images?.[0] || "https://via.placeholder.com/400x500?text=Product";
            }}
          />
          
          {/* Hover Overlay with "Feel the Texture" */}
          <div 
            className="absolute inset-0 bg-gradient-to-t from-[#2D2A2E]/80 via-transparent to-transparent flex items-end p-5 transition-opacity duration-500 z-20"
            style={{ opacity: isHovered ? 1 : 0 }}
          >
            <p className="font-clinical text-xs text-white/90 tracking-[0.2em] uppercase font-medium">
              Feel the texture
            </p>
          </div>
          
          {/* Badges */}
          <div className="absolute top-4 left-4 flex flex-col gap-2 z-20">
            {isPreOrder && (
              <Badge className="bg-purple-600 text-white hover:bg-purple-600 rounded-full px-3">
                {t.pre_order || "Pre-Order"}
              </Badge>
            )}
            {!isPreOrder && (product.compare_price || product.discount_percent) && (
              <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] rounded-full px-3">
                {product.discount_percent ? `${product.discount_percent}% OFF` : "SALE"}
              </Badge>
            )}
            {product.is_featured && (
              <Badge className="bg-[#D4AF37] text-white hover:bg-[#D4AF37] rounded-full px-3">
                ★ Bestseller
              </Badge>
            )}
          </div>
          
          {/* Low Stock Alert */}
          {product.stock > 0 && product.stock <= 5 && (
            <div className="absolute bottom-3 left-3 right-3">
              <Badge variant="destructive" className="w-full justify-center text-xs rounded-full py-1.5">
                🔥 Only {product.stock} left!
              </Badge>
            </div>
          )}
        </div>
        
        {/* Product Info */}
        <div className="space-y-2">
          <h3 className="font-luxury text-lg font-medium text-[#2D2A2E] group-hover:text-[#D4AF37] transition-colors duration-500 line-clamp-2">
            {displayProduct.name}
          </h3>
          <p className="font-clinical text-sm text-[#5A5A5A] line-clamp-2 leading-relaxed">{displayProduct.short_description}</p>
          <div className="flex items-center gap-2 flex-wrap pt-1">
            {product.discount_percent ? (
              <>
                <span className="font-clinical font-bold text-lg text-[#2D2A2E]">
                  {formatPrice(effectivePrice)}
                </span>
                <span className="font-clinical text-sm text-[#888888] line-through">{formatPrice(product.price)}</span>
              </>
            ) : (
              <>
                <span className="font-clinical font-bold text-lg text-[#2D2A2E]">{formatPrice(product.price)}</span>
                {product.compare_price && (
                  <span className="font-clinical text-sm text-[#888888] line-through">{formatPrice(product.compare_price)}</span>
                )}
              </>
            )}
          </div>
          {/* Pre-Order Info */}
          {isPreOrder && product.preorder_release_date && (
            <p className="text-xs text-purple-600 font-medium">
              📅 {t.available_on || "Available"}: {new Date(product.preorder_release_date).toLocaleDateString()}
            </p>
          )}
          {product.review_count > 0 && (
            <div className="flex items-center gap-1">
              <Star className="h-4 w-4 fill-[#D4AF37] text-[#D4AF37]" />
              <span className="font-clinical text-sm text-[#5A5A5A]">{product.average_rating} ({product.review_count})</span>
            </div>
          )}
        </div>
      </Link>
      
      {/* Add to Bag Button - Matches Luxury Style */}
      <Button
        className="w-full mt-5 bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-5 font-semibold shadow-lg hover:shadow-xl font-clinical transition-all duration-300"
        onClick={handleAddToBag}
        data-testid={`add-to-cart-${product.id}`}
      >
        {product.stock > 0 || !isPreOrder ? "Add to Bag" : `Pre-Order Now`}
      </Button>
    </MotionDiv>
  );
};

// HomePage is now imported from @/components/pages/HomePage

// Luxury Product Card with Texture Hover Effect
const LuxuryProductCard = ({ product, translatedProduct, index }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [showShareOptions, setShowShareOptions] = useState(false);
  const displayProduct = translatedProduct || product;
  const { formatPrice } = useCurrency();
  const { addToCart, setSideCartOpen } = useCart();
  
  const textureImage = product.texture_image || product.images?.[1] || "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=800&q=80";
  
  const handleAddToBag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    addToCart(product.id, 1);
  };
  
  const handleShareClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const productUrl = `${window.location.origin}/products/${product.slug || product.id}`;
    const shareTitle = displayProduct.name;
    const shareText = `Check out ${shareTitle} from ReRoots! 🌿`;
    
    // Try native share first (mobile)
    if (navigator.share) {
      navigator.share({
        title: shareTitle,
        text: shareText,
        url: productUrl
      }).catch(() => {});
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(productUrl).then(() => {
        toast.success("Product link copied!");
      }).catch(() => {
        toast.error("Failed to copy link");
      });
    }
  };
  
  return (
    <MotionDiv
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.8, delay: index * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
      className="group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Link to={`/products/${product.id}`} className="block">
        {/* Product Image with Texture Reveal - 500ms transition */}
        <div className="aspect-[3/4] bg-white rounded-2xl overflow-hidden mb-6 relative shadow-[0_8px_30px_rgb(0,0,0,0.04)] group-hover:shadow-[0_20px_50px_rgb(0,0,0,0.1)] transition-all duration-500 border border-transparent group-hover:border-[#D4AF37]/30">
          {/* Main product image - Fades out on hover */}
          <img
            src={product.images?.[0] || product.image}
            alt={displayProduct.name}
            loading="lazy"
            decoding="async"
            className="absolute inset-0 w-full h-full object-cover transition-all duration-500 ease-out"
            style={{
              opacity: isHovered ? 0 : 1,
              transform: isHovered ? 'scale(1.02)' : 'scale(1)'
            }}
          />
          
          {/* Texture/Macro image - Fades in on hover with slight scale for depth */}
          <img
            src={textureImage}
            alt={`${displayProduct.name} texture`}
            loading="lazy"
            decoding="async"
            className="absolute inset-0 w-full h-full object-cover transition-all duration-500 ease-out"
            style={{
              opacity: isHovered ? 1 : 0,
              transform: isHovered ? 'scale(1)' : 'scale(1.08)'
            }}
          />
          
          {/* Share button - appears on hover */}
          <button
            onClick={handleShareClick}
            className="absolute top-4 right-4 w-9 h-9 rounded-full bg-white/90 hover:bg-white flex items-center justify-center transition-all duration-300 shadow-md z-10"
            style={{ opacity: isHovered ? 1 : 0, transform: isHovered ? 'translateY(0)' : 'translateY(-10px)' }}
            data-testid={`share-product-card-${product.id}`}
          >
            <Share2 className="h-4 w-4 text-[#2D2A2E]" />
          </button>
          
          {/* Hover overlay */}
          <div 
            className="absolute inset-0 bg-gradient-to-t from-[#2D2A2E]/80 via-transparent to-transparent flex items-end p-5 transition-opacity duration-500"
            style={{ opacity: isHovered ? 1 : 0 }}
          >
            <p className="font-clinical text-xs text-white/90 tracking-[0.2em] uppercase font-medium">
              Feel the texture
            </p>
          </div>
          
          {/* Sale badge */}
          {product.compare_price && product.compare_price > product.price && (
            <Badge className="absolute top-4 left-4 bg-[#2D2A2E] text-white text-xs font-medium rounded-full px-3 py-1">
              SAVE {Math.round((1 - product.price / product.compare_price) * 100)}%
            </Badge>
          )}
        </div>
        
        {/* Product Info */}
        <div className="space-y-2">
          <h3 className="font-luxury text-lg md:text-xl font-medium text-[#2D2A2E] group-hover:text-[#D4AF37] transition-colors duration-500 line-clamp-2">
            {displayProduct.name}
          </h3>
          <p className="font-clinical text-sm text-[#5A5A5A] line-clamp-2 leading-relaxed">
            {displayProduct.short_description || displayProduct.description?.substring(0, 60)}
          </p>
          
          {/* Price Display with Clear Discount */}
          <div className="pt-2 space-y-1">
            {/* Final Price - Big and Bold */}
            <div className="flex items-baseline gap-2">
              <span className="font-clinical text-xl font-bold text-[#2D2A2E]">
                {formatPrice(product.discount_percent 
                  ? product.price * (1 - product.discount_percent / 100)
                  : product.price
                )}
              </span>
              {(product.compare_price && product.compare_price > product.price) && (
                <span className="font-clinical text-sm text-[#888] line-through">
                  {formatPrice(product.compare_price)}
                </span>
              )}
            </div>
            
            {/* Discount Badge - Show savings */}
            {(product.compare_price && product.compare_price > product.price) && (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-700">
                  SAVE {Math.round((1 - (product.discount_percent 
                    ? product.price * (1 - product.discount_percent / 100) 
                    : product.price) / product.compare_price) * 100)}%
                </span>
                <span className="text-xs text-green-600 font-medium">
                  You save {formatPrice(product.compare_price - (product.discount_percent 
                    ? product.price * (1 - product.discount_percent / 100) 
                    : product.price))}
                </span>
              </div>
            )}
          </div>
        </div>
      </Link>
      
      {/* Pill-shaped Add to Bag Button - Opens Side Cart */}
      <Button 
        className="luxury-btn w-full mt-5 bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-5 font-semibold shadow-lg hover:shadow-xl font-clinical"
        onClick={handleAddToBag}
        data-testid="add-to-bag-btn"
      >
        Add to Bag
      </Button>
    </MotionDiv>
  );
};

// CheckoutPage has been extracted to /components/pages/CheckoutPage.js for better performance

// Checkout Success Page

// Checkout Success Page
const CheckoutSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("loading");
  const [order, setOrder] = useState(null);
  const [pointsEarned, setPointsEarned] = useState(0);
  const [comboDetails, setComboDetails] = useState(null);
  const { clearCart } = useCart();
  const { settings } = useStoreSettings();
  const sessionId = searchParams.get("session_id");
  const orderId = searchParams.get("order_id");
  const paymentMethod = searchParams.get("payment_method");
  const paypalRedirect = searchParams.get("paypal_redirect") === "true";
  
  // PayPal API v2 uses order_id in return URL (not legacy token/PayerID)
  const isPayPalApiReturn = paymentMethod === "paypal_api";
  
  const thankYouMessage = settings?.thank_you_messages?.payment || "Thank you for your purchase. You'll receive an email confirmation shortly.";

  // Dynamically import ShippingTracker
  const ShippingTracker = React.lazy(() => import('@/components/checkout/ShippingTracker'));
  
  // Check if order contains a combo purchase
  const detectComboPurchase = async (orderData) => {
    try {
      // Fetch combo offers to check if this order contains a combo
      const combosRes = await axios.get(`${API}/combo-offers`);
      const combos = combosRes.data || [];
      
      // Check each combo to see if all its products are in the order
      const orderProductIds = orderData.items?.map(item => item.product_id || item.id) || [];
      
      for (const combo of combos) {
        const comboProductIds = combo.product_ids || [];
        // Check if all combo products are in the order
        const hasAllComboProducts = comboProductIds.every(pid => orderProductIds.includes(pid));
        
        if (hasAllComboProducts && comboProductIds.length >= 2) {
          // Fetch product details for the combo
          const productsRes = await axios.get(`${API}/products`);
          const allProducts = productsRes.data || [];
          const comboProducts = allProducts.filter(p => comboProductIds.includes(p.id));
          
          setComboDetails({
            name: combo.name,
            total_active_percent: combo.total_active_percent,
            products: comboProducts,
            tagline: combo.tagline
          });
          return;
        }
      }
    } catch (error) {
      console.log('Could not detect combo purchase:', error);
    }
  };

  useEffect(() => {
    // Handle PayPal API v2 redirect (user returning from PayPal after approval)
    // PayPal v2 API does NOT append token/PayerID - it redirects to return_url with our order_id
    if (isPayPalApiReturn && orderId) {
      const capturePayPalPayment = async () => {
        try {
          // Get the PayPal order ID we stored before redirecting
          const pendingPayPalOrderId = localStorage.getItem('pending_paypal_id');
          const pendingInternalOrderId = localStorage.getItem('pending_paypal_order') || orderId;
          
          console.log('Capturing PayPal v2 payment...', { 
            paypalOrderId: pendingPayPalOrderId, 
            internalOrderId: pendingInternalOrderId 
          });
          
          if (!pendingPayPalOrderId) {
            console.error('No PayPal order ID found in localStorage');
            setStatus("error");
            return;
          }
          
          const authToken = localStorage.getItem('reroots_token');
          
          const res = await axios.post(`${API}/payments/paypal/capture`, {
            orderID: pendingPayPalOrderId,
            order_id: pendingInternalOrderId
          }, {
            headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
          });
          
          console.log('PayPal capture result:', res.data);
          
          if (res.data.success || res.data.status === 'COMPLETED') {
            setStatus("success");
            clearCart();
            localStorage.removeItem('pending_paypal_order');
            localStorage.removeItem('pending_paypal_id');
            
            // Fetch order details
            const fetchOrderId = pendingInternalOrderId || orderId;
            if (fetchOrderId) {
              const orderRes = await axios.get(`${API}/orders/${fetchOrderId}`);
              setOrder(orderRes.data);
              if (orderRes.data?.items) {
                const totalQty = orderRes.data.items.reduce((sum, item) => sum + (item.quantity || 1), 0);
                setPointsEarned(totalQty * 250);
                // Detect if this is a combo purchase
                detectComboPurchase(orderRes.data);
              }
            }
          } else {
            setStatus("error");
          }
        } catch (error) {
          console.error('PayPal capture error:', error);
          setStatus("error");
        }
      };
      
      capturePayPalPayment();
      return;
    }
    
    // Handle e-Transfer orders (manual payment)
    if (paymentMethod === "etransfer") {
      setStatus("manual_payment");
      clearCart();
      // Fetch order details
      if (orderId) {
        axios.get(`${API}/orders/${orderId}`).then(res => {
          setOrder(res.data);
        }).catch(() => {});
      }
      return;
    }
    
    // Handle Bambora card payments (already processed)
    if (orderId && !sessionId) {
      setStatus("success");
      clearCart();
      axios.get(`${API}/orders/${orderId}`).then(res => {
        setOrder(res.data);
        if (res.data?.items) {
          const totalQty = res.data.items.reduce((sum, item) => sum + (item.quantity || 1), 0);
          setPointsEarned(totalQty * 250);
          // Detect if this is a combo purchase
          detectComboPurchase(res.data);
        }
      }).catch(() => {});
      return;
    }

    // Handle Stripe session
    if (!sessionId) {
      setStatus("error");
      return;
    }

    const checkStatus = async () => {
      try {
        const res = await axios.get(`${API}/payments/stripe/status/${sessionId}`);
        if (res.data.payment_status === "paid") {
          setStatus("success");
          clearCart();
          
          // Calculate points earned (250 per product)
          // This is approximate - actual points are calculated on backend
          const orderData = res.data.order;
          if (orderData?.items) {
            const totalQty = orderData.items.reduce((sum, item) => sum + (item.quantity || 1), 0);
            setPointsEarned(totalQty * 250);
          } else {
            setPointsEarned(250); // Default to 1 product
          }
        } else {
          setStatus("pending");
        }
      } catch (error) {
        setStatus("error");
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 2000);
    setTimeout(() => clearInterval(interval), 10000);

    return () => clearInterval(interval);
  }, [sessionId, orderId, paymentMethod, isPayPalApiReturn, clearCart]);

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      <div className="max-w-2xl mx-auto px-6 pb-12">
        {/* Status Messages */}
        <div className="text-center mb-8">
          {status === "loading" && (
          <>
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-[#2D2A2E] mx-auto mb-4" />
            <h1 className="font-display text-2xl font-bold text-[#2D2A2E]">Processing Payment...</h1>
          </>
        )}

        {/* Manual Payment Instructions (e-Transfer / PayPal) */}
        {status === "manual_payment" && (
          <>
            <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Package className="h-8 w-8 text-amber-600" />
            </div>
            <h1 className="font-display text-2xl font-bold text-[#2D2A2E] mb-2" data-testid="success-title">Order Created!</h1>
            <p className="text-[#5A5A5A] mb-4">Please complete your payment to confirm your order.</p>
            
            {/* Payment Instructions Card */}
            <div className={`text-left p-4 rounded-xl border-2 mb-6 ${
              paymentMethod === "etransfer" 
                ? "bg-[#FFCC00]/10 border-[#FFCC00]/50" 
                : "bg-[#003087]/5 border-[#003087]/30"
            }`}>
              <h3 className={`font-bold mb-3 ${
                paymentMethod === "etransfer" ? "text-[#B8860B]" : "text-[#003087]"
              }`}>
                {paymentMethod === "etransfer" ? "Interac e-Transfer Instructions" : "PayPal Payment Instructions"}
              </h3>
              
              <div className="space-y-3 text-sm">
                <div className="bg-white p-3 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">Send payment to:</p>
                  <p className="font-bold text-[#2D2A2E] text-lg">admin@reroots.ca</p>
                </div>
                
                {orderId && (
                  <div className="bg-white p-3 rounded-lg">
                    <p className="text-xs text-gray-500 mb-1">Your Order Number:</p>
                    <p className="font-mono font-bold text-[#2D2A2E] text-lg">{orderId.substring(0, 8).toUpperCase()}</p>
                    <p className="text-xs text-gray-500 mt-1">Include this in your payment message</p>
                  </div>
                )}

                {order?.total && (
                  <div className="bg-white p-3 rounded-lg">
                    <p className="text-xs text-gray-500 mb-1">Amount Due:</p>
                    <p className="font-bold text-[#2D2A2E] text-lg">${parseFloat(order.total).toFixed(2)} CAD</p>
                  </div>
                )}

                <div className="pt-2 border-t space-y-1 text-gray-600">
                  {paymentMethod === "etransfer" ? (
                    <>
                      <p>• We'll manually accept your e-Transfer</p>
                      <p>• Processing time: 1-2 business hours</p>
                      <p>• You'll receive an email confirmation once accepted</p>
                    </>
                  ) : (
                    <>
                      <p>• Send as "Friends & Family" to avoid fees</p>
                      <p>• Include your order number in the note</p>
                      <p>• You'll receive confirmation once payment is verified</p>
                    </>
                  )}
                </div>
              </div>
            </div>
            
            <Link to="/shop">
              <Button className="btn-primary">Continue Shopping</Button>
            </Link>
          </>
        )}

        {status === "success" && (
          <>
            <div className="w-16 h-16 bg-[#F8A5B8] rounded-full flex items-center justify-center mx-auto mb-4">
              <Check className="h-8 w-8 text-[#2D2A2E]" />
            </div>
            <h1 className="font-display text-2xl font-bold text-[#2D2A2E] mb-2" data-testid="success-title">Order Confirmed!</h1>
            <p className="text-[#5A5A5A] mb-4">{thankYouMessage}</p>
            
            {/* Points Earned Banner */}
            {pointsEarned > 0 && (
              <div className="bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-4 mb-6 inline-block">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <svg className="w-6 h-6 text-amber-600" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.31-8.86c-1.77-.45-2.34-.94-2.34-1.67 0-.84.79-1.43 2.1-1.43 1.38 0 1.9.66 1.94 1.64h1.71c-.05-1.34-.87-2.57-2.49-2.97V5H10.9v1.69c-1.51.32-2.72 1.3-2.72 2.81 0 1.79 1.49 2.69 3.66 3.21 1.95.46 2.34 1.15 2.34 1.87 0 .53-.39 1.39-2.1 1.39-1.6 0-2.23-.72-2.32-1.64H8.04c.1 1.7 1.36 2.66 2.86 2.97V19h2.34v-1.67c1.52-.29 2.72-1.16 2.73-2.77-.01-2.2-1.9-2.96-3.66-3.42z"/>
                  </svg>
                  <span className="font-bold text-amber-700 text-lg">You earned {pointsEarned} points!</span>
                </div>
                <p className="text-amber-600 text-sm">
                  Worth ${(pointsEarned * 0.05).toFixed(2)} off your next order
                </p>
              </div>
            )}
          </>
        )}
        
        {status === "pending" && (
          <>
            <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Package className="h-8 w-8 text-yellow-600" />
            </div>
            <h1 className="font-display text-2xl font-bold text-[#2D2A2E] mb-2">Payment Pending</h1>
            <p className="text-[#5A5A5A] mb-6">Your payment is being processed. Please wait...</p>
          </>
        )}
        
        {status === "error" && (
          <>
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <X className="h-8 w-8 text-red-600" />
            </div>
            <h1 className="font-display text-2xl font-bold text-[#2D2A2E] mb-2">Payment Failed</h1>
            <p className="text-[#5A5A5A] mb-6">Something went wrong. Please try again.</p>
            <Link to="/cart">
              <Button className="btn-primary">Return to Cart</Button>
            </Link>
          </>
        )}
        </div>
        
        {/* Post-Purchase Success - Shows clinical protocol for combo purchases */}
        {status === "success" && comboDetails && (
          <React.Suspense fallback={<div className="animate-pulse bg-gray-100 h-64 rounded-xl mb-8" />}>
            <div className="mb-8" data-testid="post-purchase-success">
              <PostPurchaseSuccessLazy order={order} comboDetails={comboDetails} />
            </div>
          </React.Suspense>
        )}

        {/* Shipping Tracker - Shows for successful orders */}
        {status === "success" && orderId && (
          <React.Suspense fallback={
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-[#2D2A2E] mx-auto mb-2" />
              <p className="text-gray-500 text-sm">Loading shipping status...</p>
            </div>
          }>
            <div className="mb-8">
              <ShippingTracker orderId={orderId} initialOrder={order} />
            </div>
          </React.Suspense>
        )}

        {/* Order Summary for successful orders */}
        {status === "success" && order && (
          <div className="bg-white border border-gray-200 rounded-xl p-4 mb-8">
            <h3 className="font-semibold text-[#2D2A2E] mb-3">Order Summary</h3>
            
            {/* Order Number */}
            <div className="flex justify-between items-center py-2 border-b">
              <span className="text-gray-600">Order Number</span>
              <span className="font-mono font-semibold">{order.order_number || orderId?.substring(0, 8).toUpperCase()}</span>
            </div>
            
            {/* Items */}
            <div className="py-3 border-b">
              {order.items?.map((item, idx) => (
                <div key={idx} className="flex justify-between items-center text-sm py-1">
                  <span className="text-gray-600">
                    {item.name || item.product_name} × {item.quantity}
                  </span>
                  <span className="font-medium">${(item.price * item.quantity).toFixed(2)}</span>
                </div>
              ))}
            </div>
            
            {/* Totals */}
            <div className="pt-2 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Subtotal</span>
                <span>${parseFloat(order.subtotal || 0).toFixed(2)}</span>
              </div>
              {order.shipping_cost > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Shipping</span>
                  <span>${parseFloat(order.shipping_cost).toFixed(2)}</span>
                </div>
              )}
              {order.tax_amount > 0 && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Tax</span>
                  <span>${parseFloat(order.tax_amount).toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between font-bold text-base pt-2 border-t">
                <span>Total</span>
                <span>${parseFloat(order.total || 0).toFixed(2)} CAD</span>
              </div>
            </div>
          </div>
        )}

        {/* Continue Shopping Button */}
        {(status === "success" || status === "manual_payment") && (
          <div className="text-center">
            <Link to="/shop">
              <Button className="btn-primary">Continue Shopping</Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

// Forgot Password Page
const ForgotPasswordPage = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [resetLink, setResetLink] = useState(null);
  const [loginBackground, setLoginBackground] = useState(null);
  const { currentLang } = useTranslation() || {};
  
  // Get translations
  const lang = currentLang || localStorage.getItem("reroots_lang") || "en-CA";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;

  useEffect(() => {
    axios.get(`${API}/public/login-backgrounds`)
      .then(res => setLoginBackground(res.data.login_background_image))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const res = await axios.post(`${API}/auth/forgot-password`, { email });
      setSubmitted(true);
      
      // Check if reset link was returned (email service unavailable)
      if (res.data.reset_link) {
        setResetLink(res.data.reset_link);
        toast.success("Reset link generated! Click the button below.");
      } else {
        toast.success(t.check_email_desc || "Check your email for the reset link.");
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Something went wrong");
    }
    setLoading(false);
  };

  // Use ReRoots product image as background
  const defaultBg = "https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/f80chpuq_1767220017661.jpg";

  return (
    <div 
      className="min-h-screen flex items-center justify-center py-12 px-4"
      style={{
        background: `linear-gradient(135deg, rgba(45,42,46,0.85) 0%, rgba(45,42,46,0.7) 100%), url('${loginBackground || defaultBg}') center/cover fixed`,
      }}
    >
      <div className="w-full max-w-md">
        <Card className="shadow-2xl border-0 bg-white/95 backdrop-blur-sm rounded-xl overflow-hidden" style={{ borderTop: '4px solid #C9A86C' }}>
          <CardHeader className="text-center pt-10 pb-4">
            <CardTitle className="font-display text-2xl text-[#2D2A2E]">
              {submitted ? (
                <>{t.check_email}</>
              ) : (
                <>
                  {t.forgot_password_title}<br />
                  <span className="text-[#2D2A2E]">{t.password_word}</span>
                </>
              )}
            </CardTitle>
            <p className="text-sm text-[#888888] mt-2">
              {submitted 
                ? (resetLink ? "Click the button below to reset your password" : t.check_email_desc)
                : t.forgot_password_desc
              }
            </p>
          </CardHeader>
          <CardContent>
            {submitted ? (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                  {resetLink ? (
                    <ExternalLink className="h-8 w-8 text-green-600" />
                  ) : (
                    <Mail className="h-8 w-8 text-green-600" />
                  )}
                </div>
                
                {resetLink ? (
                  <>
                    <a 
                      href={resetLink}
                      className="block w-full"
                    >
                      <Button 
                        className="w-full text-white font-bold"
                        style={{ background: 'linear-gradient(135deg, #C9A86C 0%, #B8956A 100%)' }}
                      >
                        Reset Password Now
                      </Button>
                    </a>
                    <p className="text-xs text-[#888888]">
                      This link expires in 1 hour
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-[#5A5A5A]">
                    {t.didnt_receive}{" "}
                    <button 
                      onClick={() => setSubmitted(false)} 
                      className="text-[#C9A86C] hover:underline"
                    >
                      {t.try_again}
                    </button>
                  </p>
                )}
                
                <Link to="/login">
                  <Button variant="outline" className="w-full">
                    {t.back_to_login}
                  </Button>
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="email">{t.email}</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t.email_placeholder}
                  />
                </div>
                <Button 
                  type="submit" 
                  className="w-full text-white font-medium tracking-wider rounded-full py-6" 
                  style={{ background: 'linear-gradient(135deg, #C9A86C 0%, #B8956A 100%)' }}
                  disabled={loading}
                >
                  {loading ? t.sending : t.send_reset_link}
                </Button>
                <div className="text-center">
                  <Link to="/login" className="text-sm text-[#888888] hover:text-[#C9A86C]">
                    ← {t.back_to_login}
                  </Link>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

// Reset Password Page
const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [loginBackground, setLoginBackground] = useState(null);
  const { currentLang } = useTranslation() || {};
  const token = searchParams.get("token");
  
  // Get translations
  const lang = currentLang || localStorage.getItem("reroots_lang") || "en-CA";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;

  useEffect(() => {
    axios.get(`${API}/public/login-backgrounds`)
      .then(res => setLoginBackground(res.data.login_background_image))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (token) {
      axios.get(`${API}/auth/verify-reset-token?token=${token}`)
        .then(() => {
          setTokenValid(true);
          setValidating(false);
        })
        .catch(() => {
          setTokenValid(false);
          setValidating(false);
        });
    } else {
      setValidating(false);
    }
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    
    if (password.length < 8) {
      toast.error(t.password_min_chars || "Password must be at least 8 characters");
      return;
    }
    
    setLoading(true);
    
    try {
      await axios.post(`${API}/auth/reset-password`, {
        token,
        new_password: password
      });
      toast.success("Password reset successful! Please log in.");
      navigate("/login");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to reset password");
    }
    setLoading(false);
  };

  // Use ReRoots product image as background
  const defaultBg = "https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/f80chpuq_1767220017661.jpg";

  if (validating) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#C9A86C]" />
      </div>
    );
  }

  return (
    <div 
      className="min-h-screen flex items-center justify-center py-12 px-4"
      style={{
        background: `linear-gradient(135deg, rgba(45,42,46,0.85) 0%, rgba(45,42,46,0.7) 100%), url('${loginBackground || defaultBg}') center/cover fixed`,
      }}
    >
      <div className="w-full max-w-md">
        <Card className="shadow-2xl border-0 bg-white/95 backdrop-blur-sm rounded-xl overflow-hidden" style={{ borderTop: '4px solid #C9A86C' }}>
          <CardHeader className="text-center pt-10 pb-4">
            <CardTitle className="font-display text-2xl text-[#2D2A2E]">
              {tokenValid ? (
                <>
                  {t.create_new_password}<br />
                  <span className="text-[#2D2A2E]">{t.password}</span>
                </>
              ) : (
                <>{t.invalid_link}</>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {tokenValid ? (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="new-password">{t.new_password}</Label>
                  <Input
                    id="new-password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t.new_password}
                    minLength={8}
                  />
                </div>
                <div>
                  <Label htmlFor="confirm-password">{t.confirm_password}</Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder={t.confirm_password}
                  />
                </div>
                <p className="text-xs text-[#888888]">
                  {t.password_min_chars}
                </p>
                <Button 
                  type="submit" 
                  className="w-full text-white font-medium tracking-wider rounded-full py-6" 
                  style={{ background: 'linear-gradient(135deg, #C9A86C 0%, #B8956A 100%)' }}
                  disabled={loading}
                >
                  {loading ? t.resetting : t.reset_password}
                </Button>
              </form>
            ) : (
              <div className="text-center space-y-4">
                <p className="text-sm text-[#5A5A5A]">
                  {t.invalid_link_desc}
                </p>
                <Link to="/forgot-password">
                  <Button className="w-full" style={{ background: 'linear-gradient(135deg, #C9A86C 0%, #B8956A 100%)' }}>
                    {t.request_new_link}
                  </Button>
                </Link>
                <Link to="/login" className="block text-sm text-[#888888] hover:text-[#C9A86C]">
                  ← {t.back_to_login}
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

// PromoPopup is now imported from '@/components/PromoPopup'

// Wishlist Page
const WishlistPage = () => {
  const { wishlist, removeFromWishlist, loading } = useWishlist();
  const { addToCart } = useCart();
  const { formatPrice } = useCurrency();
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return (
      <div className="min-h-screen pt-24 bg-[#FDF9F9]">
        <div className="max-w-4xl mx-auto px-6 py-12 text-center">
          <Heart className="h-16 w-16 mx-auto text-[#F8A5B8] mb-4" />
          <h1 className="font-display text-3xl font-bold text-[#2D2A2E] mb-4">Your Wishlist</h1>
          <p className="text-[#5A5A5A] mb-8">Please login to view your wishlist</p>
          <Button onClick={() => navigate("/login")} className="bg-[#2D2A2E] hover:bg-[#2D2A2E]/90">
            Login to Continue
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="flex items-center gap-3 mb-8">
          <Heart className="h-8 w-8 text-[#F8A5B8]" fill="#F8A5B8" />
          <h1 className="font-display text-3xl font-bold text-[#2D2A2E]">My Wishlist</h1>
          <Badge variant="secondary" className="ml-2">{wishlist.length} items</Badge>
        </div>

        {wishlist.length === 0 ? (
          <Card className="text-center py-16">
            <CardContent>
              <Heart className="h-16 w-16 mx-auto text-gray-300 mb-4" />
              <h2 className="font-display text-xl font-semibold text-[#2D2A2E] mb-2">Your wishlist is empty</h2>
              <p className="text-[#5A5A5A] mb-6">Save items you love to your wishlist</p>
              <Button onClick={() => navigate("/shop")} className="bg-[#2D2A2E] hover:bg-[#2D2A2E]/90">
                Start Shopping
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {wishlist.map((item) => {
              const product = item.product;
              if (!product) return null;
              
              const effectivePrice = product.discount_percent 
                ? product.price * (1 - product.discount_percent / 100) 
                : product.price;
              
              return (
                <Card key={item.id} className="overflow-hidden group">
                  <div className="relative aspect-square">
                    <img 
                      src={product.images?.[0] || "https://via.placeholder.com/400"} 
                      alt={product.name}
                      loading="lazy"
                      decoding="async"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    {product.discount_percent > 0 && (
                      <Badge className="absolute top-3 left-3 bg-[#F8A5B8] text-white">
                        {product.discount_percent}% OFF
                      </Badge>
                    )}
                    {product.stock === 0 && (
                      <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <Badge variant="destructive">Out of Stock</Badge>
                      </div>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute top-3 right-3 bg-white/90 hover:bg-white text-red-500"
                      onClick={() => removeFromWishlist(product.id)}
                      disabled={loading}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  <CardContent className="p-4">
                    <h3 className="font-semibold text-[#2D2A2E] mb-1 line-clamp-1">{product.name}</h3>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="font-bold text-[#F8A5B8]">{formatPrice(effectivePrice)}</span>
                      {product.discount_percent > 0 && (
                        <span className="text-sm text-gray-400 line-through">{formatPrice(product.price)}</span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button 
                        className="flex-1 bg-[#2D2A2E] hover:bg-[#2D2A2E]/90"
                        onClick={() => {
                          addToCart(product.id);
                          toast.success("Added to cart!");
                        }}
                        disabled={product.stock === 0}
                      >
                        <ShoppingBag className="h-4 w-4 mr-2" />
                        Add to Cart
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => navigate(`/products/${product.id}`)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

// ContactPage - Extracted to /components/pages/ContactPage.js (lazy-loaded)
// PartnerLandingPage - Extracted to /components/pages/PartnerLandingPage.js (lazy-loaded)
// PartnerChatWidget - Extracted to /components/PartnerChatWidget.js (lazy-loaded)

// REMOVED: PartnerLandingPage (285 lines) - now lazy-loaded
// REMOVED: PartnerChatWidget (218 lines) - now lazy-loaded

const CustomersManager = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerDetails, setCustomerDetails] = useState(null);
  const [selectedCustomers, setSelectedCustomers] = useState([]);
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [showReferralModal, setShowReferralModal] = useState(false);
  const [referralPrograms, setReferralPrograms] = useState([]);
  const [selectedReferralProgram, setSelectedReferralProgram] = useState(null);
  const [sendingReferral, setSendingReferral] = useState(false);
  const [offerData, setOfferData] = useState({
    subject: "",
    title: "",
    message: "",
    discount_code: "",
    discount_percent: "",
    is_exclusive: true,
    expires_at: ""
  });
  const [sendingOffer, setSendingOffer] = useState(false);
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    // Fetch customers
    axios.get(`${API}/admin/customers`, { headers })
      .then(res => setCustomers(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
    
    // Fetch referral programs
    axios.get(`${API}/admin/referral-programs`, { headers })
      .then(res => {
        const programs = res.data?.programs || res.data || [];
        setReferralPrograms(Array.isArray(programs) ? programs : []);
      })
      .catch(console.error);
  }, []);

  // Send referral invites to selected customers
  const sendReferralToCustomers = async () => {
    if (!selectedReferralProgram || selectedCustomers.length === 0) {
      toast.error("Please select a referral program and customers");
      return;
    }
    
    setSendingReferral(true);
    try {
      const customerEmails = customers
        .filter(c => selectedCustomers.includes(c.id))
        .map(c => c.email);
      
      const referralLink = `${window.location.origin}/shop?ref=${selectedReferralProgram.reward_discount_code}`;
      
      await axios.post(`${API}/admin/send-offer`, {
        emails: customerEmails,
        subject: `🎁 Refer Friends & Get ${selectedReferralProgram.reward_discount_percent}% Off!`,
        title: selectedReferralProgram.name,
        message: `Great news! You're invited to our referral program. Share your link with friends and family. When ${selectedReferralProgram.required_referrals} people ${selectedReferralProgram.referral_action === 'signup' ? 'sign up' : 'make a purchase'}, you'll receive ${selectedReferralProgram.reward_discount_percent}% off!\n\nYour referral link: ${referralLink}`,
        discount_code: selectedReferralProgram.reward_discount_code,
        discount_percent: selectedReferralProgram.reward_discount_percent.toString(),
        is_exclusive: false,
        expires_at: null
      }, { headers });
      
      toast.success(`Referral invite sent to ${customerEmails.length} customer(s)!`);
      setShowReferralModal(false);
      setSelectedCustomers([]);
      setSelectedReferralProgram(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send referral invites");
    }
    setSendingReferral(false);
  };

  const viewCustomer = async (customerId) => {
    const res = await axios.get(`${API}/admin/customers/${customerId}`, { headers });
    setCustomerDetails(res.data);
    setSelectedCustomer(customerId);
  };

  const exportCustomers = () => {
    const csv = [
      ["Email", "First Name", "Last Name", "Orders", "Total Spent", "Joined"],
      ...customers.map(c => [
        c.email,
        c.first_name,
        c.last_name,
        c.order_count,
        `$${c.total_spent?.toFixed(2) || "0.00"}`,
        new Date(c.created_at).toLocaleDateString()
      ])
    ].map(row => row.join(",")).join("\n");
    
    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reroots-customers-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    toast.success("Customer list exported!");
  };

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedCustomers.length === customers.length) {
      setSelectedCustomers([]);
    } else {
      setSelectedCustomers(customers.map(c => c.id));
    }
  };

  const toggleSelectCustomer = (customerId) => {
    setSelectedCustomers(prev => 
      prev.includes(customerId) 
        ? prev.filter(id => id !== customerId)
        : [...prev, customerId]
    );
  };

  const isAllSelected = customers.length > 0 && selectedCustomers.length === customers.length;
  const isSomeSelected = selectedCustomers.length > 0;

  // Send offer to selected customers
  const sendOffer = async () => {
    if (selectedCustomers.length === 0) {
      toast.error("Please select at least one customer");
      return;
    }
    if (!offerData.subject || !offerData.message) {
      toast.error("Please fill in subject and message");
      return;
    }

    setSendingOffer(true);
    try {
      const selectedEmails = customers
        .filter(c => selectedCustomers.includes(c.id))
        .map(c => c.email);

      await axios.post(`${API}/admin/send-offer`, {
        emails: selectedEmails,
        subject: offerData.subject,
        title: offerData.title,
        message: offerData.message,
        discount_code: offerData.discount_code,
        discount_percent: String(offerData.discount_percent || ""),
        is_exclusive: offerData.is_exclusive,
        expires_at: offerData.expires_at || null
      }, { headers });

      toast.success(`Offer sent to ${selectedEmails.length} customer(s)!`);
      setShowOfferModal(false);
      setSelectedCustomers([]);
      setOfferData({ subject: "", title: "", message: "", discount_code: "", discount_percent: "", is_exclusive: true, expires_at: "" });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send offer");
    }
    setSendingOffer(false);
  };

  if (loading) {
    return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-t-2 border-[#F8A5B8]"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center flex-wrap gap-4">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Customers</h2>
          <p className="text-[#5A5A5A]">{customers.length} registered customers</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {isSomeSelected && (
            <>
              <Button 
                onClick={() => setShowOfferModal(true)} 
                className="gap-2 bg-gradient-to-r from-[#F8A5B8] to-[#C9A86C] text-white"
              >
                <Gift className="h-4 w-4" /> Send Offer ({selectedCustomers.length})
              </Button>
              <Button 
                onClick={() => setShowReferralModal(true)} 
                className="gap-2 bg-blue-500 hover:bg-blue-600 text-white"
              >
                <Users className="h-4 w-4" /> Send Referral ({selectedCustomers.length})
              </Button>
            </>
          )}
          <Button onClick={exportCustomers} variant="outline" className="gap-2">
            <Download className="h-4 w-4" /> Export CSV
          </Button>
          <Button 
            onClick={async () => {
              if (window.confirm("⚠️ This will permanently delete ALL test orders, customers (except admin), reviews, and newsletter subscribers. Are you sure?")) {
                try {
                  const res = await axios.delete(`${API}/admin/cleanup-test-data`, { headers });
                  toast.success(`Cleaned: ${res.data.details.orders_deleted} orders, ${res.data.details.customers_deleted} customers, ${res.data.details.subscribers_deleted} subscribers`);
                  window.location.reload();
                } catch (error) {
                  toast.error("Failed to cleanup test data");
                }
              }
            }} 
            variant="outline" 
            className="gap-2 text-red-500 border-red-200 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" /> Clean Test Data
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#FDF9F9]">
                <tr>
                  <th className="text-left p-4 font-medium w-12">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded border-gray-300 text-[#F8A5B8] focus:ring-[#F8A5B8] cursor-pointer"
                    />
                  </th>
                  <th className="text-left p-4 font-medium">Customer</th>
                  <th className="text-left p-4 font-medium">Email</th>
                  <th className="text-left p-4 font-medium">Orders</th>
                  <th className="text-left p-4 font-medium">Total Spent</th>
                  <th className="text-left p-4 font-medium">Joined</th>
                  <th className="text-center p-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {customers.map(customer => (
                  <tr key={customer.id} className={`border-t hover:bg-gray-50 ${selectedCustomers.includes(customer.id) ? 'bg-[#F8A5B8]/10' : ''}`}>
                    <td className="p-4">
                      <input
                        type="checkbox"
                        checked={selectedCustomers.includes(customer.id)}
                        onChange={() => toggleSelectCustomer(customer.id)}
                        className="w-4 h-4 rounded border-gray-300 text-[#F8A5B8] focus:ring-[#F8A5B8] cursor-pointer"
                      />
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-[#F8A5B8]/20 flex items-center justify-center">
                          <User className="h-5 w-5 text-[#F8A5B8]" />
                        </div>
                        <span className="font-medium">{customer.first_name} {customer.last_name}</span>
                      </div>
                    </td>
                    <td className="p-4 text-[#5A5A5A]">{customer.email}</td>
                    <td className="p-4">{customer.order_count || 0}</td>
                    <td className="p-4 font-medium">${customer.total_spent?.toFixed(2) || "0.00"}</td>
                    <td className="p-4 text-[#5A5A5A]">{new Date(customer.created_at).toLocaleDateString()}</td>
                    <td className="p-4 text-center">
                      <Button variant="ghost" size="sm" onClick={() => viewCustomer(customer.id)}>
                        View Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {customers.length === 0 && (
              <div className="p-8 text-center text-[#5A5A5A]">No customers yet</div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Send Offer Modal */}
      {showOfferModal && (
        <Dialog open={true} onOpenChange={() => setShowOfferModal(false)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display text-xl flex items-center gap-2">
                <Gift className="h-5 w-5 text-[#F8A5B8]" /> Send Special Offer
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="bg-[#F8A5B8]/10 p-3 rounded-lg">
                <p className="text-sm text-[#5A5A5A]">
                  Sending to <span className="font-bold text-[#2D2A2E]">{selectedCustomers.length}</span> customer(s)
                </p>
              </div>
              
              <div>
                <Label>Email Subject *</Label>
                <Input
                  value={offerData.subject}
                  onChange={(e) => setOfferData({...offerData, subject: e.target.value})}
                  placeholder="e.g., Exclusive 20% Off Just For You!"
                />
              </div>

              <div>
                <Label>Offer Title</Label>
                <Input
                  value={offerData.title}
                  onChange={(e) => setOfferData({...offerData, title: e.target.value})}
                  placeholder="e.g., VIP Customer Discount"
                />
              </div>
              
              <div>
                <Label>Message *</Label>
                <textarea
                  value={offerData.message}
                  onChange={(e) => setOfferData({...offerData, message: e.target.value})}
                  placeholder="Write your offer message here..."
                  className="w-full min-h-[100px] p-3 border rounded-lg resize-none focus:ring-2 focus:ring-[#F8A5B8] focus:border-transparent"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Discount Code</Label>
                  <Input
                    value={offerData.discount_code}
                    onChange={(e) => setOfferData({...offerData, discount_code: e.target.value.toUpperCase()})}
                    placeholder="e.g., VIP20"
                  />
                </div>
                <div>
                  <Label>Discount %</Label>
                  <Input
                    type="number"
                    value={offerData.discount_percent}
                    onChange={(e) => setOfferData({...offerData, discount_percent: e.target.value === '' ? '' : e.target.value})}
                    onFocus={(e) => e.target.select()}
                    placeholder="e.g., 20"
                    min="0"
                    max="100"
                  />
                </div>
              </div>

              {offerData.discount_code && (
                <>
                  <div>
                    <Label>Expiry Date</Label>
                    <Input
                      type="date"
                      value={offerData.expires_at}
                      onChange={(e) => setOfferData({...offerData, expires_at: e.target.value})}
                      min={new Date().toISOString().split('T')[0]}
                    />
                    <p className="text-xs text-muted-foreground mt-1">Leave empty for no expiry</p>
                  </div>
                  
                  <div className="flex items-center gap-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <input
                      type="checkbox"
                      id="exclusive-offer"
                      checked={offerData.is_exclusive}
                      onChange={(e) => setOfferData({...offerData, is_exclusive: e.target.checked})}
                      className="w-4 h-4 rounded border-gray-300 text-[#F8A5B8] focus:ring-[#F8A5B8]"
                    />
                    <div className="flex-1">
                      <label htmlFor="exclusive-offer" className="font-medium text-amber-800 cursor-pointer">
                        🔒 Exclusive Code
                      </label>
                      <p className="text-xs text-amber-600">
                        Only these selected customers can use this code. Others will see "Invalid code".
                      </p>
                    </div>
                  </div>
                </>
              )}

              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  onClick={() => setShowOfferModal(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button 
                  onClick={sendOffer}
                  disabled={sendingOffer}
                  className="flex-1 bg-gradient-to-r from-[#F8A5B8] to-[#C9A86C] text-white"
                >
                  {sendingOffer ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Sending...</>
                  ) : (
                    <><Send className="h-4 w-4 mr-2" /> Send Offer</>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Customer Details Modal */}
      {selectedCustomer && customerDetails && (
        <Dialog open={true} onOpenChange={() => { setSelectedCustomer(null); setCustomerDetails(null); }}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="font-display text-xl">
                {customerDetails.customer.first_name} {customerDetails.customer.last_name}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-[#5A5A5A]">Email</Label>
                  <p className="font-medium">{customerDetails.customer.email}</p>
                </div>
                <div>
                  <Label className="text-[#5A5A5A]">Member Since</Label>
                  <p className="font-medium">{new Date(customerDetails.customer.created_at).toLocaleDateString()}</p>
                </div>
              </div>
              
              <div>
                <h4 className="font-semibold mb-3">Order History ({customerDetails.orders.length})</h4>
                {customerDetails.orders.length > 0 ? (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {customerDetails.orders.map(order => (
                      <div key={order.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                        <div>
                          <span className="font-medium">{order.order_number}</span>
                          <span className="text-sm text-[#5A5A5A] ml-2">{new Date(order.created_at).toLocaleDateString()}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge className={order.payment_status === "paid" ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}>
                            {order.payment_status}
                          </Badge>
                          <span className="font-bold">${order.total?.toFixed(2)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[#5A5A5A]">No orders yet</p>
                )}
              </div>
              
              <div className="flex gap-3">
                <Button variant="outline" className="gap-2" onClick={() => window.location.href = `mailto:${customerDetails.customer.email}`}>
                  <Mail className="h-4 w-4" /> Send Email
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Send Referral Modal for Customers */}
      <Dialog open={showReferralModal} onOpenChange={setShowReferralModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-500" /> Send Referral Invite
            </DialogTitle>
            <DialogDescription>
              Send referral program invite to {selectedCustomers.length} customer(s)
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Select Referral Program */}
            <div>
              <Label>Select Referral Program *</Label>
              {referralPrograms.length === 0 ? (
                <div className="bg-yellow-50 p-3 rounded-lg mt-2 text-sm text-yellow-700">
                  No referral programs found. Create one in the 🎁 Offers tab first.
                </div>
              ) : (
                <div className="mt-2 space-y-2">
                  {referralPrograms.map((program) => (
                    <div 
                      key={program.id}
                      onClick={() => setSelectedReferralProgram(program)}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                        selectedReferralProgram?.id === program.id 
                          ? 'border-blue-500 bg-blue-50' 
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-medium">{program.name}</span>
                        <Badge className={program.is_active ? "bg-green-100 text-green-700" : "bg-gray-100"}>
                          {program.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="text-sm text-[#5A5A5A] mt-1">
                        {program.reward_discount_percent}% off after {program.required_referrals} referrals
                      </p>
                      {program.reward_discount_code && (
                        <p className="text-xs text-blue-600 mt-1">
                          Code: <span className="font-mono">{program.reward_discount_code}</span>
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Customers Preview */}
            <div className="bg-gray-50 p-3 rounded-lg">
              <p className="text-sm text-[#5A5A5A]">
                Sending to <span className="font-bold text-[#2D2A2E]">{selectedCustomers.length}</span> customer(s)
              </p>
              <div className="mt-2 text-xs text-gray-500 max-h-20 overflow-y-auto">
                {customers.filter(c => selectedCustomers.includes(c.id)).map(c => c.email).join(", ")}
              </div>
            </div>

            {/* Email Preview */}
            {selectedReferralProgram && (
              <div className="bg-blue-50 p-3 rounded-lg text-sm">
                <p className="font-medium text-blue-800">Email Preview:</p>
                <p className="text-blue-600 mt-1">
                  Subject: 🎁 Refer Friends & Get {selectedReferralProgram.reward_discount_percent}% Off!
                </p>
              </div>
            )}
          </div>
          
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => {
              setShowReferralModal(false);
              setSelectedReferralProgram(null);
            }}>
              Cancel
            </Button>
            <Button 
              onClick={sendReferralToCustomers}
              disabled={sendingReferral || !selectedReferralProgram || referralPrograms.length === 0}
              className="bg-blue-500 hover:bg-blue-600 text-white"
            >
              {sendingReferral ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Sending...</>
              ) : (
                <><Send className="h-4 w-4 mr-2" /> Send Referral</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Newsletter Subscribers Section */}
      <SubscribersSection />
      
      {/* Quiz Analytics Dashboard */}
      <QuizAnalyticsDashboard />
    </div>
  );
};

// Quiz Analytics Dashboard Component
const QuizAnalyticsDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await axios.get(`${API}/admin/bio-scan/stats`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setStats(res.data);
      } catch (err) {
        console.error('Failed to fetch quiz stats:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Dna className="w-5 h-5 text-cyan-500" />
            Quiz Analytics
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center py-8">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-gray-400" />
        </CardContent>
      </Card>
    );
  }

  if (!stats) return null;

  const riskColors = {
    'High': 'bg-red-500',
    'Moderate': 'bg-yellow-500',
    'Low': 'bg-green-500',
    'Unknown': 'bg-gray-500'
  };

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Dna className="w-5 h-5 text-cyan-500" />
            Bio-Age Quiz Analytics
          </CardTitle>
          <Button variant="outline" size="sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Collapse' : 'Expand'}
          </Button>
        </div>
        <CardDescription>Track quiz submissions, contacts, and referral performance</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gradient-to-br from-cyan-50 to-cyan-100 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-cyan-700">{stats.total_scans}</p>
            <p className="text-sm text-cyan-600">Total Quizzes</p>
          </div>
          <div className="bg-gradient-to-br from-pink-50 to-pink-100 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-pink-700">{stats.contacts?.emails || 0}</p>
            <p className="text-sm text-pink-600">Emails Collected</p>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-blue-700">{stats.contacts?.phones || 0}</p>
            <p className="text-sm text-blue-600">Phone Numbers</p>
          </div>
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-green-700">${stats.referrals?.total_value || 0}</p>
            <p className="text-sm text-green-600">Referral Value</p>
          </div>
        </div>

        {/* Contact Breakdown */}
        <div className="grid md:grid-cols-2 gap-4 mb-6">
          <div className="bg-gray-50 rounded-xl p-4">
            <h4 className="font-medium mb-3">📧 Contact Breakdown</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Email only:</span>
                <span className="font-medium">{stats.contacts?.email_only || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Phone only:</span>
                <span className="font-medium">{stats.contacts?.phone_only || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Both email & phone:</span>
                <span className="font-medium">{stats.contacts?.both || 0}</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 rounded-xl p-4">
            <h4 className="font-medium mb-3">🔗 Referral Performance</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Referrals Started:</span>
                <span className="font-medium">{stats.referrals?.total_started || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Referrals Completed:</span>
                <span className="font-medium">{stats.referrals?.total_completed || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Conversion Rate:</span>
                <span className="font-medium text-green-600">{stats.referrals?.conversion_rate || 0}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Risk Distribution */}
        <div className="mb-6">
          <h4 className="font-medium mb-3">📊 Risk Level Distribution</h4>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(stats.risk_distribution || {}).map(([risk, count]) => (
              <div key={risk} className="flex items-center gap-2 bg-white border rounded-lg px-3 py-2">
                <div className={`w-3 h-3 rounded-full ${riskColors[risk] || 'bg-gray-400'}`}></div>
                <span className="text-sm">{risk}: <strong>{count}</strong></span>
              </div>
            ))}
          </div>
        </div>

        {expanded && (
          <>
            {/* Bio-Age Distribution */}
            <div className="mb-6">
              <h4 className="font-medium mb-3">🧬 Bio-Age Distribution (Years Added)</h4>
              <div className="flex gap-1 items-end h-24">
                {Object.entries(stats.bio_age_distribution || {}).map(([age, count]) => {
                  const maxCount = Math.max(...Object.values(stats.bio_age_distribution || {1: 1}));
                  const height = (count / maxCount) * 100;
                  return (
                    <div key={age} className="flex flex-col items-center flex-1">
                      <div 
                        className="w-full bg-gradient-to-t from-cyan-500 to-purple-500 rounded-t"
                        style={{ height: `${height}%`, minHeight: '4px' }}
                      ></div>
                      <span className="text-xs text-gray-500 mt-1">+{age}</span>
                      <span className="text-xs font-medium">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Top Referrers */}
            {stats.top_referrers?.length > 0 && (
              <div className="mb-6">
                <h4 className="font-medium mb-3">🏆 Top Referrers</h4>
                <div className="space-y-2">
                  {stats.top_referrers.map((referrer, idx) => (
                    <div key={idx} className="flex items-center justify-between bg-white border rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold ${idx === 0 ? 'bg-yellow-500' : idx === 1 ? 'bg-gray-400' : idx === 2 ? 'bg-orange-400' : 'bg-gray-300'}`}>
                          {idx + 1}
                        </span>
                        <div>
                          <p className="text-sm font-medium">{referrer.email || referrer.phone || 'Anonymous'}</p>
                          <p className="text-xs text-gray-500">Code: {referrer.referral_code}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold text-green-600">{referrer.referral_count} completed</p>
                        <p className="text-xs text-gray-500">{referrer.referrals_started || 0} started</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Submissions */}
            <div>
              <h4 className="font-medium mb-3">📝 Recent Submissions</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left p-2">Contact</th>
                      <th className="text-left p-2">Bio-Age</th>
                      <th className="text-left p-2">Risk</th>
                      <th className="text-left p-2">Referrals</th>
                      <th className="text-left p-2">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_submissions?.slice(0, 10).map((sub, idx) => (
                      <tr key={idx} className="border-t">
                        <td className="p-2">
                          <div>{sub.email || '-'}</div>
                          {sub.phone && <div className="text-xs text-gray-400">{sub.phone}</div>}
                        </td>
                        <td className="p-2 font-medium">+{sub.bio_age_offset || 0}y</td>
                        <td className="p-2">
                          <span className={`px-2 py-0.5 rounded text-xs ${sub.risk_level === 'High' ? 'bg-red-100 text-red-700' : sub.risk_level === 'Moderate' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>
                            {sub.risk_level || 'N/A'}
                          </span>
                        </td>
                        <td className="p-2">{sub.referral_count || 0}</td>
                        <td className="p-2 text-gray-500">{sub.created_at ? new Date(sub.created_at).toLocaleDateString() : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

// Newsletter Subscribers Section - Now shows ALL subscribers with source tracking
const SubscribersSection = () => {
  const [subscribers, setSubscribers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSubscribers, setSelectedSubscribers] = useState([]);
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [sendingOffer, setSendingOffer] = useState(false);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sources, setSources] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offerData, setOfferData] = useState({
    subject: "Special Offer Just For You! 🎁",
    title: "Exclusive Discount",
    message: "As a valued subscriber, we're giving you an exclusive discount on your next purchase!",
    discount_code: "",
    discount_percent: "15",
    is_exclusive: true,
    expires_at: ""
  });
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const fetchSubscribers = useCallback(async () => {
    setLoading(true);
    try {
      const url = sourceFilter === "all" 
        ? `${API}/admin/all-subscribers?limit=500`
        : `${API}/admin/all-subscribers?source=${sourceFilter}&limit=500`;
      const res = await axios.get(url, { headers });
      setSubscribers(res.data.subscribers || []);
      setSources(res.data.sources || []);
      setTotalCount(res.data.total || 0);
    } catch (err) {
      console.error(err);
      // Fallback to old endpoint
      axios.get(`${API}/admin/newsletter-subscribers`, { headers })
        .then(res => setSubscribers(res.data.map(s => ({ ...s, source: 'newsletter', source_display: 'Newsletter' }))))
        .catch(console.error);
    }
    setLoading(false);
  }, [sourceFilter]);

  useEffect(() => {
    fetchSubscribers();
  }, [fetchSubscribers]);

  const exportSubscribers = () => {
    const csv = [
      ["Email", "Phone", "Name", "Source", "Date"],
      ...subscribers.map(s => [
        s.email || "", 
        s.phone || "", 
        s.name || "",
        s.source_display || s.source || "",
        s.created_at ? new Date(s.created_at).toLocaleString() : ""
      ])
    ].map(row => row.join(",")).join("\n");
    
    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reroots-subscribers-${sourceFilter}-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    toast.success("Subscribers exported!");
  };

  const generateDiscountCode = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let code = "REROOTS";
    for (let i = 0; i < 6; i++) {
      code += chars[Math.floor(Math.random() * chars.length)];
    }
    return code;
  };

  const toggleSelectAll = () => {
    if (selectedSubscribers.length === subscribers.filter(s => s.email).length) {
      setSelectedSubscribers([]);
    } else {
      setSelectedSubscribers(subscribers.filter(s => s.email).map(s => s.email));
    }
  };

  const toggleSelectSubscriber = (email) => {
    if (!email) return;
    setSelectedSubscribers(prev => 
      prev.includes(email) 
        ? prev.filter(e => e !== email)
        : [...prev, email]
    );
  };

  const sendOffer = async () => {
    if (selectedSubscribers.length === 0) {
      toast.error("Please select at least one subscriber");
      return;
    }
    if (!offerData.subject || !offerData.message) {
      toast.error("Please fill in subject and message");
      return;
    }
    if (!offerData.discount_code) {
      toast.error("Please enter or generate a discount code");
      return;
    }

    setSendingOffer(true);
    try {
      await axios.post(`${API}/admin/send-offer`, {
        emails: selectedSubscribers,
        subject: offerData.subject,
        title: offerData.title,
        message: offerData.message,
        discount_code: offerData.discount_code.toUpperCase(),
        discount_percent: offerData.discount_percent,
        is_exclusive: offerData.is_exclusive,
        expires_at: offerData.expires_at || null
      }, { headers });

      toast.success(`Offer sent to ${selectedSubscribers.length} subscriber(s)!`);
      setShowOfferModal(false);
      setSelectedSubscribers([]);
      setOfferData({
        subject: "Special Offer Just For You! 🎁",
        title: "Exclusive Discount",
        message: "As a valued subscriber, we're giving you an exclusive discount on your next purchase!",
        discount_code: "",
        discount_percent: "15",
        is_exclusive: true,
        expires_at: ""
      });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send offer");
    }
    setSendingOffer(false);
  };

  const subscribersWithEmail = subscribers.filter(s => s.email);
  const isAllSelected = subscribersWithEmail.length > 0 && selectedSubscribers.length === subscribersWithEmail.length;

  return (
    <div className="mt-8 pt-8 border-t">
      <div className="flex justify-between items-center mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Mail className="h-5 w-5 text-[#F8A5B8]" />
          <h3 className="font-display text-xl font-bold">All Subscribers</h3>
          <Badge className="bg-[#F8A5B8] text-white">{totalCount}</Badge>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          {/* Source Filter */}
          <select 
            value={sourceFilter} 
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-1.5 text-sm border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#C9A86C]"
          >
            <option value="all">All Sources ({totalCount})</option>
            {sources.map(src => (
              <option key={src.value} value={src.value}>
                {src.label} ({src.count})
              </option>
            ))}
          </select>
          {selectedSubscribers.length > 0 && (
            <Button 
              onClick={() => setShowOfferModal(true)} 
              className="gap-2 bg-gradient-to-r from-pink-500 to-[#C9A86C] text-white"
            >
              <Gift className="h-4 w-4" /> Send Offer ({selectedSubscribers.length})
            </Button>
          )}
          {subscribers.length > 0 && (
            <Button onClick={exportSubscribers} variant="outline" size="sm" className="gap-2">
              <Download className="h-4 w-4" /> Export
            </Button>
          )}
        </div>
      </div>
      
      {/* Source Quick Stats */}
      {sources.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {sources.filter(s => s.count > 0).map(src => (
            <button
              key={src.value}
              onClick={() => setSourceFilter(src.value === sourceFilter ? "all" : src.value)}
              className={`px-3 py-1 text-xs rounded-full transition-all ${
                sourceFilter === src.value 
                  ? 'bg-[#C9A86C] text-white' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {src.label}: {src.count}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : subscribers.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-[#5A5A5A]">
            No subscribers found for this source.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left p-3 w-12">
                      <input
                        type="checkbox"
                        checked={isAllSelected}
                        onChange={toggleSelectAll}
                        className="w-4 h-4 rounded border-gray-300 text-[#F8A5B8] focus:ring-[#F8A5B8] cursor-pointer"
                      />
                    </th>
                    <th className="text-left p-3 text-sm font-medium">Email</th>
                    <th className="text-left p-3 text-sm font-medium">Phone</th>
                    <th className="text-left p-3 text-sm font-medium">Source</th>
                    <th className="text-left p-3 text-sm font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {subscribers.map((sub, idx) => (
                    <tr key={idx} className={`border-t hover:bg-gray-50 ${selectedSubscribers.includes(sub.email) ? 'bg-pink-50' : ''}`}>
                      <td className="p-3">
                        {sub.email && (
                          <input
                            type="checkbox"
                            checked={selectedSubscribers.includes(sub.email)}
                            onChange={() => toggleSelectSubscriber(sub.email)}
                            className="w-4 h-4 rounded border-gray-300 text-[#F8A5B8] focus:ring-[#F8A5B8] cursor-pointer"
                          />
                        )}
                      </td>
                      <td className="p-3">
                        {sub.email ? (
                          <a href={`mailto:${sub.email}`} className="text-[#F8A5B8] hover:underline text-sm">{sub.email}</a>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="p-3 text-sm">
                        {sub.phone ? (
                          <a href={`tel:${sub.phone}`} className="text-blue-600 hover:underline">{sub.phone}</a>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="p-3">
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${
                            sub.source === 'bio_scan' ? 'bg-cyan-50 text-cyan-700 border-cyan-200' :
                            sub.source === 'newsletter' ? 'bg-pink-50 text-pink-700 border-pink-200' :
                            sub.source === 'registered' ? 'bg-green-50 text-green-700 border-green-200' :
                            sub.source === 'google_auth' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                            sub.source === 'waitlist' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                            sub.source === 'reddit' ? 'bg-orange-50 text-orange-700 border-orange-200' :
                            'bg-gray-50 text-gray-700 border-gray-200'
                          }`}
                        >
                          {sub.source_display || sub.source}
                        </Badge>
                        {sub.extra_data?.bio_age_offset !== undefined && (
                          <div className="text-xs text-gray-400 mt-1">
                            Bio-Age: +{sub.extra_data.bio_age_offset}y
                          </div>
                        )}
                      </td>
                      <td className="p-3 text-xs text-[#5A5A5A]">
                        {sub.created_at ? new Date(sub.created_at).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Send Offer Modal */}
      <Dialog open={showOfferModal} onOpenChange={setShowOfferModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-display text-xl flex items-center gap-2">
              <Gift className="h-5 w-5 text-pink-500" /> Send Special Offer
            </DialogTitle>
            <DialogDescription>
              Send exclusive discount to {selectedSubscribers.length} subscriber(s)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-pink-50 p-3 rounded-lg">
              <p className="text-sm text-[#5A5A5A]">
                Sending to <span className="font-bold text-[#2D2A2E]">{selectedSubscribers.length}</span> subscriber(s)
              </p>
              <div className="mt-2 text-xs text-gray-500 max-h-20 overflow-y-auto">
                {selectedSubscribers.join(", ")}
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 sm:col-span-1">
                <Label>Discount Code *</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    value={offerData.discount_code}
                    onChange={(e) => setOfferData({...offerData, discount_code: e.target.value.toUpperCase()})}
                    placeholder="SUMMER20"
                    className="uppercase flex-1"
                  />
                  <Button type="button" variant="outline" size="sm" onClick={() => setOfferData({...offerData, discount_code: generateDiscountCode()})}>
                    Generate
                  </Button>
                </div>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <Label>Discount %</Label>
                <Input
                  type="number"
                  value={offerData.discount_percent}
                  onChange={(e) => setOfferData({...offerData, discount_percent: e.target.value === '' ? '' : e.target.value})}
                  onFocus={(e) => e.target.select()}
                  placeholder="15"
                  min="0"
                  max="100"
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <Label>Email Subject *</Label>
              <Input
                value={offerData.subject}
                onChange={(e) => setOfferData({...offerData, subject: e.target.value})}
                placeholder="e.g., Exclusive 20% Off Just For You!"
              />
            </div>

            <div>
              <Label>Offer Title</Label>
              <Input
                value={offerData.title}
                onChange={(e) => setOfferData({...offerData, title: e.target.value})}
                placeholder="e.g., VIP Subscriber Discount"
              />
            </div>
            
            <div>
              <Label>Message *</Label>
              <textarea
                value={offerData.message}
                onChange={(e) => setOfferData({...offerData, message: e.target.value})}
                placeholder="Write your offer message here..."
                className="w-full min-h-[80px] p-3 border rounded-lg resize-none focus:ring-2 focus:ring-pink-300 focus:border-transparent"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Expiry Date</Label>
                <Input
                  type="date"
                  value={offerData.expires_at}
                  onChange={(e) => setOfferData({...offerData, expires_at: e.target.value})}
                  min={new Date().toISOString().split('T')[0]}
                />
              </div>
              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  id="sub-exclusive-offer"
                  checked={offerData.is_exclusive}
                  onChange={(e) => setOfferData({...offerData, is_exclusive: e.target.checked})}
                  className="w-4 h-4 rounded"
                />
                <label htmlFor="sub-exclusive-offer" className="text-sm font-medium">
                  🔒 Exclusive Code
                </label>
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <Button variant="outline" onClick={() => setShowOfferModal(false)} className="flex-1">
                Cancel
              </Button>
              <Button 
                onClick={sendOffer}
                disabled={sendingOffer}
                className="flex-1 bg-gradient-to-r from-pink-500 to-[#C9A86C] text-white"
              >
                {sendingOffer ? (
                  <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Sending...</>
                ) : (
                  <><Send className="h-4 w-4 mr-2" /> Send Offer</>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// Admin QR Code Generator Component
const AdminQRGenerator = () => {
  const [url, setUrl] = useState("");
  const [qrGenerated, setQrGenerated] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [size, setSize] = useState(256);
  const [fgColor, setFgColor] = useState("#000000");
  const [bgColor, setBgColor] = useState("#FFFFFF");
  const [generating, setGenerating] = useState(false);
  const [savedQRs, setSavedQRs] = useState([]);

  const presetLinks = [
    { name: "Google Review", placeholder: "https://g.page/r/your-review-link", icon: "⭐" },
    { name: "Instagram", placeholder: "https://instagram.com/reroots.ca", icon: "📷" },
    { name: "TikTok", placeholder: "https://tiktok.com/@reroots.ca", icon: "🎵" },
    { name: "Website", placeholder: "https://reroots.ca", icon: "🌐" },
    { name: "Quiz", placeholder: `${window.location.origin}/Bio-Age-Repair-Scan`, icon: "🧬" },
    { name: "Shop", placeholder: `${window.location.origin}/shop`, icon: "🛍️" },
  ];

  const colorPresets = [
    { fg: "#000000", bg: "#FFFFFF", name: "Classic" },
    { fg: "#1a1a2e", bg: "#FFFFFF", name: "Dark Blue" },
    { fg: "#7c3aed", bg: "#FFFFFF", name: "Purple" },
    { fg: "#059669", bg: "#FFFFFF", name: "Emerald" },
    { fg: "#dc2626", bg: "#FFFFFF", name: "Red" },
    { fg: "#F8A5B8", bg: "#FFFFFF", name: "ReRoots Pink" },
  ];

  const generateQR = async () => {
    if (!url.trim()) {
      toast.error("Please enter a URL");
      return;
    }

    let finalUrl = url.trim();
    if (!finalUrl.startsWith("http") && !finalUrl.startsWith("mailto:") && !finalUrl.startsWith("tel:")) {
      finalUrl = "https://" + finalUrl;
    }

    setGenerating(true);
    try {
      // Dynamic import of qrcode library
      const QRCode = (await import('qrcode')).default;
      const dataUrl = await QRCode.toDataURL(finalUrl, {
        width: size,
        margin: 2,
        color: { dark: fgColor, light: bgColor },
        errorCorrectionLevel: 'H'
      });
      
      setQrDataUrl(dataUrl);
      setQrGenerated(true);
      toast.success("QR Code generated!");
    } catch (error) {
      console.error("QR Generation error:", error);
      toast.error("Failed to generate QR code");
    } finally {
      setGenerating(false);
    }
  };

  const downloadQR = () => {
    if (!qrDataUrl) return;
    const link = document.createElement('a');
    link.download = `qr-code-${Date.now()}.png`;
    link.href = qrDataUrl;
    link.click();
    toast.success("QR Code downloaded!");
  };

  const saveQR = () => {
    if (!qrDataUrl || !url) return;
    const newQR = {
      id: Date.now(),
      url: url,
      dataUrl: qrDataUrl,
      createdAt: new Date().toISOString()
    };
    setSavedQRs(prev => [newQR, ...prev].slice(0, 10)); // Keep last 10
    toast.success("QR Code saved!");
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <QrCode className="w-5 h-5 text-emerald-500" />
              Generate QR Code
            </CardTitle>
            <CardDescription>Create QR codes for Google Reviews, social media, menus, and more</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* URL Input */}
            <div>
              <Label>Enter URL or Link</Label>
              <Input
                placeholder="https://g.page/r/CY76Se2EyM-_EAE/review"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="mt-1"
              />
            </div>

            {/* Quick Links */}
            <div>
              <Label className="text-sm text-gray-500">Quick Links</Label>
              <div className="flex flex-wrap gap-2 mt-2">
                {presetLinks.map((link, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    size="sm"
                    onClick={() => setUrl(link.placeholder)}
                  >
                    {link.icon} {link.name}
                  </Button>
                ))}
              </div>
            </div>

            {/* Size */}
            <div>
              <Label>Size: {size}px</Label>
              <input
                type="range"
                min="128"
                max="512"
                step="32"
                value={size}
                onChange={(e) => setSize(parseInt(e.target.value))}
                className="w-full mt-2"
              />
            </div>

            {/* Colors */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>QR Color</Label>
                <div className="flex gap-2 mt-1">
                  <input
                    type="color"
                    value={fgColor}
                    onChange={(e) => setFgColor(e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer"
                  />
                  <Input value={fgColor} onChange={(e) => setFgColor(e.target.value)} className="flex-1" />
                </div>
              </div>
              <div>
                <Label>Background</Label>
                <div className="flex gap-2 mt-1">
                  <input
                    type="color"
                    value={bgColor}
                    onChange={(e) => setBgColor(e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer"
                  />
                  <Input value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="flex-1" />
                </div>
              </div>
            </div>

            {/* Color Presets */}
            <div>
              <Label className="text-sm text-gray-500">Color Presets</Label>
              <div className="flex gap-2 mt-2">
                {colorPresets.map((preset, idx) => (
                  <button
                    key={idx}
                    onClick={() => { setFgColor(preset.fg); setBgColor(preset.bg); }}
                    className="w-8 h-8 rounded border-2 border-gray-200 hover:border-gray-400 overflow-hidden"
                    title={preset.name}
                  >
                    <div className="w-full h-1/2" style={{ backgroundColor: preset.bg }} />
                    <div className="w-full h-1/2" style={{ backgroundColor: preset.fg }} />
                  </button>
                ))}
              </div>
            </div>

            {/* Generate Button */}
            <Button
              onClick={generateQR}
              disabled={generating || !url.trim()}
              className="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600"
            >
              {generating ? "Generating..." : "Generate QR Code"}
            </Button>
          </CardContent>
        </Card>

        {/* Preview Section */}
        <Card>
          <CardHeader>
            <CardTitle>Preview</CardTitle>
            <CardDescription>{qrGenerated ? "Your QR code is ready!" : "Generate a QR code to preview"}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="aspect-square max-w-xs mx-auto rounded-xl overflow-hidden bg-gray-100 flex items-center justify-center mb-4">
              {qrGenerated && qrDataUrl ? (
                <img loading="lazy" src={qrDataUrl} alt="Generated QR Code" className="w-full h-full object-contain p-4" />
              ) : (
                <div className="text-center p-8">
                  <QrCode className="w-20 h-20 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-400 text-sm">Your QR code will appear here</p>
                </div>
              )}
            </div>

            {qrGenerated && (
              <div className="flex gap-2">
                <Button onClick={downloadQR} className="flex-1 bg-emerald-500 hover:bg-emerald-600">
                  <Download className="w-4 h-4 mr-2" /> Download
                </Button>
                <Button onClick={saveQR} variant="outline" className="flex-1">
                  <Save className="w-4 h-4 mr-2" /> Save
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Saved QR Codes */}
      {savedQRs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recently Saved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {savedQRs.map((qr) => (
                <div key={qr.id} className="text-center">
                  <img loading="lazy" src={qr.dataUrl} alt="Saved QR" className="w-full aspect-square rounded-lg border" />
                  <p className="text-xs text-gray-500 mt-1 truncate">{qr.url}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tips */}
      <Card className="bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200">
        <CardContent className="p-4">
          <h3 className="font-bold text-emerald-800 mb-2">💡 Pro Tips</h3>
          <ul className="text-sm text-emerald-700 space-y-1">
            <li>• Use Google Review QR to boost your business ratings</li>
            <li>• Print QR codes on business cards, menus, or product packaging</li>
            <li>• Test the QR code with your phone before printing</li>
            <li>• Higher contrast colors scan better</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
};

// Science AI - Beauty Formulation Assistant Component
const ScienceAIAssistant = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => `formulation_${Date.now()}`);
  const [sessions, setSessions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [skinType, setSkinType] = useState("");
  const [concerns, setConcerns] = useState([]);
  const [productType, setProductType] = useState("");
  const messagesEndRef = React.useRef(null);
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const skinTypes = ["Normal", "Dry", "Oily", "Combination", "Sensitive", "Mature"];
  const skinConcerns = ["Acne", "Anti-aging", "Hyperpigmentation", "Dehydration", "Redness", "Fine Lines", "Dark Circles", "Pores", "Dullness", "Texture"];
  const productTypes = ["Serum", "Moisturizer", "Cleanser", "Toner", "Eye Cream", "Face Mask", "Exfoliant", "Sunscreen", "Oil", "Essence"];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch session history
  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API}/admin/formulation-history`, { headers });
      setSessions(res.data || []);
    } catch (error) {
      console.error("Failed to fetch history:", error);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const loadSession = async (session) => {
    setSessionId(session.session_id);
    setMessages(session.messages.map((m, i) => ({
      id: i,
      role: m.role,
      content: m.content
    })));
    setShowHistory(false);
  };

  const startNewSession = () => {
    setSessionId(`formulation_${Date.now()}`);
    setMessages([]);
    setSkinType("");
    setConcerns([]);
    setProductType("");
  };

  const toggleConcern = (concern) => {
    setConcerns(prev => 
      prev.includes(concern) 
        ? prev.filter(c => c !== concern)
        : [...prev, concern]
    );
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { id: Date.now(), role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const context = {};
      if (skinType) context.skin_type = skinType;
      if (concerns.length > 0) context.concerns = concerns;
      if (productType) context.product_type = productType;

      const res = await axios.post(`${API}/admin/formulation-assistant`, {
        message: input,
        session_id: sessionId,
        context: Object.keys(context).length > 0 ? context : null
      }, { headers });

      const aiMessage = { id: Date.now() + 1, role: "assistant", content: res.data.response };
      setMessages(prev => [...prev, aiMessage]);
      fetchHistory(); // Refresh history
    } catch (error) {
      console.error("Failed to send message:", error);
      toast.error("Failed to get response from Science AI");
    }
    setLoading(false);
  };

  const quickPrompts = [
    "Create a 2% retinol serum formula for anti-aging",
    "What's the best preservative system for water-based products?",
    "Formulate a vitamin C serum with 15% L-ascorbic acid",
    "How do I stabilize niacinamide with vitamin C?",
    "Create a gentle AHA exfoliant for sensitive skin",
    "What peptides work best for collagen production?",
    "Formulate a PDRN-based regenerative serum",
    "How to create an emulsion with natural emulsifiers?"
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-purple-500" />
            Science AI - Formulation Lab
          </h2>
          <p className="text-[#5A5A5A]">AI-powered cosmetic chemist for creating advanced skincare formulas</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowHistory(!showHistory)} className="gap-2">
            <Clock className="h-4 w-4" /> History
          </Button>
          <Button onClick={startNewSession} className="gap-2 bg-purple-600 hover:bg-purple-700">
            <Plus className="h-4 w-4" /> New Formula
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Context Panel */}
        <Card className="lg:col-span-1 h-fit">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Beaker className="h-5 w-5 text-purple-500" />
              Formula Context
            </CardTitle>
            <CardDescription>Set parameters for better formulations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-sm font-medium">Skin Type</Label>
              <Select value={skinType} onValueChange={setSkinType}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select skin type" />
                </SelectTrigger>
                <SelectContent>
                  {skinTypes.map(type => (
                    <SelectItem key={type} value={type.toLowerCase()}>{type}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-sm font-medium">Product Type</Label>
              <Select value={productType} onValueChange={setProductType}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select product type" />
                </SelectTrigger>
                <SelectContent>
                  {productTypes.map(type => (
                    <SelectItem key={type} value={type.toLowerCase()}>{type}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-sm font-medium mb-2 block">Skin Concerns</Label>
              <div className="flex flex-wrap gap-1">
                {skinConcerns.map(concern => (
                  <Badge
                    key={concern}
                    variant={concerns.includes(concern.toLowerCase()) ? "default" : "outline"}
                    className={`cursor-pointer text-xs ${concerns.includes(concern.toLowerCase()) ? 'bg-purple-500' : ''}`}
                    onClick={() => toggleConcern(concern.toLowerCase())}
                  >
                    {concern}
                  </Badge>
                ))}
              </div>
            </div>

            <Separator />

            <div>
              <Label className="text-sm font-medium mb-2 block">Quick Prompts</Label>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {quickPrompts.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => setInput(prompt)}
                    className="w-full text-left text-xs p-2 rounded bg-gray-50 hover:bg-purple-50 hover:text-purple-700 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Chat Area */}
        <Card className="lg:col-span-3">
          <CardContent className="p-0">
            {/* Messages */}
            <div className="h-[500px] overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center mb-4">
                    <FlaskConical className="h-10 w-10 text-white" />
                  </div>
                  <h3 className="font-display text-xl font-bold text-[#2D2A2E] mb-2">Welcome to Science AI Lab</h3>
                  <p className="text-[#5A5A5A] max-w-md mb-4">
                    Your expert cosmetic chemist assistant. I can help you create professional-grade skincare formulations with proper INCI nomenclature, percentages, and manufacturing instructions.
                  </p>
                  <div className="grid grid-cols-2 gap-2 max-w-md">
                    <div className="p-3 rounded-lg bg-purple-50 text-left">
                      <p className="text-xs font-medium text-purple-700">🧪 Formulation Design</p>
                      <p className="text-xs text-purple-600">Complete formulas with phases & percentages</p>
                    </div>
                    <div className="p-3 rounded-lg bg-pink-50 text-left">
                      <p className="text-xs font-medium text-pink-700">⚗️ Ingredient Science</p>
                      <p className="text-xs text-pink-600">Active ingredients & compatibility</p>
                    </div>
                    <div className="p-3 rounded-lg bg-blue-50 text-left">
                      <p className="text-xs font-medium text-blue-700">📊 Stability & Safety</p>
                      <p className="text-xs text-blue-600">pH, preservatives & stability testing</p>
                    </div>
                    <div className="p-3 rounded-lg bg-green-50 text-left">
                      <p className="text-xs font-medium text-green-700">📜 Regulatory Compliance</p>
                      <p className="text-xs text-green-600">FDA, Health Canada, EU standards</p>
                    </div>
                  </div>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl p-4 ${
                        msg.role === "user"
                          ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white"
                          : "bg-gray-100 text-[#2D2A2E]"
                      }`}
                    >
                      {msg.role === "assistant" ? (
                        <div className="prose prose-sm max-w-none">
                          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
                            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                              <FlaskConical className="h-3 w-3 text-white" />
                            </div>
                            <span className="text-xs font-medium text-purple-600">Science AI</span>
                          </div>
                          <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
                        </div>
                      ) : (
                        <div className="text-sm">{msg.content}</div>
                      )}
                    </div>
                  </div>
                ))
              )}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-2xl p-4">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-purple-500" />
                      <span className="text-sm text-[#5A5A5A]">Formulating response...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t p-4">
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about formulations, ingredients, or skincare science..."
                  className="min-h-[60px] resize-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                />
                <Button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 h-auto"
                >
                  {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                </Button>
              </div>
              <p className="text-xs text-[#888888] mt-2">
                💡 Tip: Set skin type and concerns in the context panel for more targeted formulations
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* History Sidebar */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/50 z-50 flex justify-end" onClick={() => setShowHistory(false)}>
          <div className="w-96 bg-white h-full p-6 overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-display text-lg font-bold">Formula History</h3>
              <Button variant="ghost" size="sm" onClick={() => setShowHistory(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {sessions.length === 0 ? (
              <p className="text-sm text-[#5A5A5A]">No previous sessions</p>
            ) : (
              <div className="space-y-2">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => loadSession(session)}
                    className="w-full text-left p-3 rounded-lg border hover:border-purple-300 hover:bg-purple-50 transition-colors"
                  >
                    <p className="font-medium text-sm truncate">{session.title}</p>
                    <p className="text-xs text-[#888888]">
                      {new Date(session.created_at).toLocaleDateString()} • {session.messages?.length || 0} messages
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// AI Chat Assistant Component for Admin
const AdminChatAssistant = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `admin_chat_${Date.now()}`);
  const [selectedModel, setSelectedModel] = useState("gpt-4o");
  const messagesEndRef = React.useRef(null);
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Load chat history
    axios.get(`${API}/admin/chat/history/${sessionId}`, { headers })
      .then(res => setMessages(res.data))
      .catch(() => {});
  }, [sessionId]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: "user", content: input, id: Date.now() };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await axios.post(`${API}/admin/chat`, {
        message: input,
        session_id: sessionId,
        model: selectedModel
      }, { headers });

      setMessages(prev => [...prev, { role: "assistant", content: res.data.response, id: Date.now() + 1 }]);
    } catch (error) {
      toast.error("Failed to get response. Please try again.");
      setMessages(prev => prev.slice(0, -1));
    }
    setLoading(false);
  };

  const clearHistory = async () => {
    try {
      await axios.delete(`${API}/admin/chat/history/${sessionId}`, { headers });
      setMessages([]);
      toast.success("Chat history cleared");
    } catch (error) {
      toast.error("Failed to clear history");
    }
  };

  return (
    <Card className="h-[600px] flex flex-col">
      <CardHeader className="pb-3 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-[#F8A5B8]" />
            <CardTitle className="text-lg">AI Assistant</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Select value={selectedModel} onValueChange={setSelectedModel}>
              <SelectTrigger className="w-[160px] h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                <SelectItem value="gpt-4o-mini">GPT-4o Mini</SelectItem>
                <SelectItem value="claude-sonnet-4-5-20250929">Claude Sonnet</SelectItem>
                <SelectItem value="gemini-2.5-flash">Gemini Flash</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="ghost" size="sm" onClick={clearHistory}>
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-1">Ask me anything about managing your store!</p>
      </CardHeader>
      
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full p-4">
          {messages.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">
              <Bot className="h-12 w-12 mx-auto mb-3 text-[#F8A5B8]/50" />
              <p className="text-sm">Start a conversation!</p>
              <p className="text-xs mt-1">I can help with products, orders, marketing tips, and more.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, idx) => (
                <div key={msg.id || idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-lg p-3 ${
                    msg.role === "user" 
                      ? "bg-[#2D2A2E] text-white" 
                      : "bg-[#FDF9F9] text-[#2D2A2E]"
                  }`}>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-[#FDF9F9] rounded-lg p-3">
                    <Loader2 className="h-4 w-4 animate-spin text-[#F8A5B8]" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>
      </CardContent>

      <div className="p-4 border-t">
        <form onSubmit={(e) => { e.preventDefault(); sendMessage(); }} className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={loading}
            className="flex-1"
          />
          <Button type="submit" disabled={loading || !input.trim()} className="btn-primary">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </Card>
  );
};

// Typography Settings Editor Component
const TypographyEditor = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { refreshTypography } = useTypography();
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    axios.get(`${API}/typography-settings`)
      .then(res => { setSettings(res.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/typography-settings`, settings, { headers });
      refreshTypography();
      toast.success("Typography settings saved!");
    } catch (error) {
      toast.error("Failed to save settings");
    }
    setSaving(false);
  };

  if (loading) return <div className="animate-pulse h-96 bg-gray-100 rounded-lg" />;
  if (!settings) return <div>Failed to load settings</div>;

  const fonts = settings.fonts || {};

  const updateFont = (key, value) => {
    setSettings({
      ...settings,
      fonts: { ...fonts, [key]: value }
    });
  };

  const googleFonts = [
    "Inter", "Playfair Display", "Roboto", "Open Sans", "Lato", "Montserrat", 
    "Poppins", "Raleway", "Merriweather", "Source Sans Pro", "Nunito", "Ubuntu",
    "PT Sans", "Oswald", "Quicksand", "Libre Baskerville", "Crimson Text"
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Typography Settings</h2>
          <p className="text-sm text-[#5A5A5A]">Customize fonts and colors across your website</p>
        </div>
        <Button onClick={saveSettings} disabled={saving} className="btn-primary">
          <Save className="h-4 w-4 mr-2" />
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Font Families */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Type className="h-5 w-5 text-[#F8A5B8]" />
              Font Families
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Body Font</Label>
              <Select value={fonts.family} onValueChange={(v) => updateFont("family", v)}>
                <SelectTrigger className="w-full"><SelectValue placeholder="Select font" /></SelectTrigger>
                <SelectContent>
                  {googleFonts.map(font => (
                    <SelectItem key={font} value={font}>{font}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Heading Font</Label>
              <Select value={fonts.heading_family} onValueChange={(v) => updateFont("heading_family", v)}>
                <SelectTrigger className="w-full"><SelectValue placeholder="Select font" /></SelectTrigger>
                <SelectContent>
                  {googleFonts.map(font => (
                    <SelectItem key={font} value={font}>{font}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Font Sizes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Type className="h-5 w-5 text-[#F8A5B8]" />
              Font Sizes (px)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>H1 Size</Label>
                <Input type="text" inputMode="numeric" value={fonts.h1_size} onChange={(e) => { const val = e.target.value; if (val === '' || /^\d*$/.test(val)) updateFont("h1_size", parseInt(val) || 0); }} />
              </div>
              <div>
                <Label>H2 Size</Label>
                <Input type="text" inputMode="numeric" value={fonts.h2_size} onChange={(e) => { const val = e.target.value; if (val === '' || /^\d*$/.test(val)) updateFont("h2_size", parseInt(val) || 0); }} />
              </div>
              <div>
                <Label>H3 Size</Label>
                <Input type="text" inputMode="numeric" value={fonts.h3_size} onChange={(e) => { const val = e.target.value; if (val === '' || /^\d*$/.test(val)) updateFont("h3_size", parseInt(val) || 0); }} />
              </div>
              <div>
                <Label>H4 Size</Label>
                <Input type="text" inputMode="numeric" value={fonts.h4_size} onChange={(e) => { const val = e.target.value; if (val === '' || /^\d*$/.test(val)) updateFont("h4_size", parseInt(val) || 0); }} />
              </div>
              <div>
                <Label>Body Size</Label>
                <Input type="text" inputMode="numeric" value={fonts.body_size} onChange={(e) => { const val = e.target.value; if (val === '' || /^\d*$/.test(val)) updateFont("body_size", parseInt(val) || 0); }} />
              </div>
              <div>
                <Label>Small Text</Label>
                <Input type="text" inputMode="numeric" value={fonts.small_size} onChange={(e) => { const val = e.target.value; if (val === '' || /^\d*$/.test(val)) updateFont("small_size", parseInt(val) || 0); }} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Colors */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Palette className="h-5 w-5 text-[#F8A5B8]" />
              Colors
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div>
                <Label>Primary</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={fonts.primary_color} onChange={(e) => updateFont("primary_color", e.target.value)} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={fonts.primary_color} onChange={(e) => updateFont("primary_color", e.target.value)} className="flex-1" />
                </div>
              </div>
              <div>
                <Label>Secondary</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={fonts.secondary_color} onChange={(e) => updateFont("secondary_color", e.target.value)} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={fonts.secondary_color} onChange={(e) => updateFont("secondary_color", e.target.value)} className="flex-1" />
                </div>
              </div>
              <div>
                <Label>Accent</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={fonts.accent_color} onChange={(e) => updateFont("accent_color", e.target.value)} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={fonts.accent_color} onChange={(e) => updateFont("accent_color", e.target.value)} className="flex-1" />
                </div>
              </div>
              <div>
                <Label>Headings</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={fonts.heading_color} onChange={(e) => updateFont("heading_color", e.target.value)} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={fonts.heading_color} onChange={(e) => updateFont("heading_color", e.target.value)} className="flex-1" />
                </div>
              </div>
              <div>
                <Label>Links</Label>
                <div className="flex gap-2 items-center">
                  <input type="color" value={fonts.link_color} onChange={(e) => updateFont("link_color", e.target.value)} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={fonts.link_color} onChange={(e) => updateFont("link_color", e.target.value)} className="flex-1" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Preview */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Eye className="h-5 w-5 text-[#F8A5B8]" />
              Live Preview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-6 bg-white border rounded-lg" style={{ fontFamily: fonts.family }}>
              <h1 style={{ fontFamily: fonts.heading_family, fontSize: `${fonts.h1_size}px`, color: fonts.heading_color, fontWeight: 700 }}>
                Heading 1
              </h1>
              <h2 style={{ fontFamily: fonts.heading_family, fontSize: `${fonts.h2_size}px`, color: fonts.heading_color, fontWeight: 600 }} className="mt-2">
                Heading 2
              </h2>
              <h3 style={{ fontFamily: fonts.heading_family, fontSize: `${fonts.h3_size}px`, color: fonts.heading_color, fontWeight: 600 }} className="mt-2">
                Heading 3
              </h3>
              <p style={{ fontSize: `${fonts.body_size}px`, color: fonts.primary_color }} className="mt-4">
                This is body text. It shows how your main content will look on the website.
              </p>
              <p style={{ fontSize: `${fonts.small_size}px`, color: fonts.secondary_color }} className="mt-2">
                This is small text for captions and secondary information.
              </p>
              <a href="#" style={{ fontSize: `${fonts.body_size}px`, color: fonts.link_color }} className="mt-2 inline-block">
                This is a link
              </a>
              <div className="mt-4 flex gap-4">
                <span className="px-3 py-1 rounded" style={{ backgroundColor: fonts.accent_color, color: "#fff" }}>Accent Color</span>
                <span className="px-3 py-1 rounded" style={{ backgroundColor: fonts.primary_color, color: "#fff" }}>Primary</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

// Homepage Sections Editor Component
const HomepageSectionsEditor = () => {
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingSection, setEditingSection] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showImageGuide, setShowImageGuide] = useState(false);

  const getHeaders = () => {
    const token = localStorage.getItem("reroots_token");
    return { Authorization: `Bearer ${token}` };
  };

  const fetchSections = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/homepage-sections`, { headers: getHeaders() });
      setSections(res.data);
    } catch (error) {
      console.error("Failed to fetch sections:", error);
      toast.error("Failed to load sections");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchSections();
  }, [fetchSections]);

  const saveSection = async (sectionData) => {
    try {
      if (editingSection) {
        await axios.put(`${API}/admin/homepage-sections/${editingSection.id}`, sectionData, { headers: getHeaders() });
        toast.success("Section updated!");
      } else {
        await axios.post(`${API}/admin/homepage-sections`, sectionData, { headers: getHeaders() });
        toast.success("Section created!");
      }
      fetchSections();
      setShowForm(false);
      setEditingSection(null);
    } catch (error) {
      console.error("Save section error:", error);
      toast.error("Failed to save section");
    }
  };

  const deleteSection = async (id) => {
    if (!window.confirm("Are you sure you want to delete this section?")) return;
    try {
      await axios.delete(`${API}/admin/homepage-sections/${id}`, { headers: getHeaders() });
      toast.success("Section deleted!");
      fetchSections();
    } catch (error) {
      toast.error("Failed to delete section");
    }
  };

  const toggleActive = async (section) => {
    try {
      await axios.put(`${API}/admin/homepage-sections/${section.id}`, { is_active: !section.is_active }, { headers: getHeaders() });
      fetchSections();
    } catch (error) {
      toast.error("Failed to update section");
    }
  };

  // Image Guide Component
  const ImageGuideDialog = () => (
    <Dialog open={showImageGuide} onOpenChange={setShowImageGuide}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl">📸 How to Add Permanent Images</DialogTitle>
          <DialogDescription>
            Follow these steps to ensure your images never disappear after deployment
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h4 className="font-semibold text-red-800 mb-2">⚠️ Why Images Disappear</h4>
            <p className="text-sm text-red-700">
              Uploaded images are stored temporarily on the server. When the site redeploys or restarts, 
              these files are lost. <strong>Always use external image URLs instead.</strong>
            </p>
          </div>
          
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h4 className="font-semibold text-green-800 mb-2">✅ Solution: Use External Image Hosting</h4>
            <div className="text-sm text-green-700 space-y-3">
              <div>
                <strong>Option 1: Unsplash (Free, Instant)</strong>
                <ol className="list-decimal ml-5 mt-1">
                  <li>Go to <a href="https://unsplash.com" target="_blank" rel="noopener noreferrer" className="underline">unsplash.com</a></li>
                  <li>Search for an image (e.g., "skincare")</li>
                  <li>Right-click the image → "Copy image address"</li>
                  <li>Paste the URL in the Image URL field</li>
                </ol>
              </div>
              
              <div>
                <strong>Option 2: Imgur (Free, Your Own Images)</strong>
                <ol className="list-decimal ml-5 mt-1">
                  <li>Go to <a href="https://imgur.com/upload" target="_blank" rel="noopener noreferrer" className="underline">imgur.com/upload</a></li>
                  <li>Upload your image (no account needed)</li>
                  <li>Right-click uploaded image → "Copy image address"</li>
                  <li>Paste the URL here</li>
                </ol>
              </div>
              
              <div>
                <strong>Option 3: ImgBB (Free, Easy)</strong>
                <ol className="list-decimal ml-5 mt-1">
                  <li>Go to <a href="https://imgbb.com" target="_blank" rel="noopener noreferrer" className="underline">imgbb.com</a></li>
                  <li>Click "Start uploading"</li>
                  <li>Upload your image</li>
                  <li>Copy the "Direct link"</li>
                </ol>
              </div>
            </div>
          </div>
          
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-semibold text-blue-800 mb-2">💡 Pro Tips</h4>
            <ul className="text-sm text-blue-700 list-disc ml-5">
              <li>Always test the URL by opening it in a new tab first</li>
              <li>Use high-quality images (at least 1200px wide)</li>
              <li>Product images should have clean white backgrounds</li>
              <li>Keep image file sizes under 2MB for faster loading</li>
            </ul>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={() => setShowImageGuide(false)}>Got it!</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  // Section Form Component
  const SectionForm = ({ section, onSave, onClose }) => {
    const [formData, setFormData] = useState(section || {
      title: "",
      subtitle: "",
      content: "",
      image_url: "",
      image_position: "right",
      background_color: "#FFFFFF",
      text_color: "#2D2A2E",
      button_text: "",
      button_link: "",
      section_type: "custom"
    });

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
          <CardHeader>
            <CardTitle>{section ? "Edit Section" : "Add New Section"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Section Type</Label>
                <Select value={formData.section_type} onValueChange={(v) => setFormData({...formData, section_type: v})}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Select section type" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="about_founder">About the Founder</SelectItem>
                    <SelectItem value="our_story">Our Story</SelectItem>
                    <SelectItem value="our_mission">Our Mission</SelectItem>
                    <SelectItem value="custom">Custom Section</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Image Position</Label>
                <Select value={formData.image_position} onValueChange={(v) => setFormData({...formData, image_position: v})}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Select position" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="left">Left</SelectItem>
                    <SelectItem value="right">Right</SelectItem>
                    <SelectItem value="background">Background</SelectItem>
                    <SelectItem value="none">No Image</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div>
              <Label>Title</Label>
              <Input value={formData.title} onChange={(e) => setFormData({...formData, title: e.target.value})} placeholder="Section Title" />
            </div>
            
            <div>
              <Label>Subtitle (optional)</Label>
              <Input value={formData.subtitle || ""} onChange={(e) => setFormData({...formData, subtitle: e.target.value})} placeholder="Section Subtitle" />
            </div>
            
            <div>
              <Label>Content</Label>
              <Textarea value={formData.content} onChange={(e) => setFormData({...formData, content: e.target.value})} rows={4} placeholder="Section content..." />
            </div>
            
            <div>
              <Label>Section Image</Label>
              <ImageUploader
                value={formData.image_url || ""}
                onChange={(url) => setFormData({...formData, image_url: url})}
                placeholder="Enter URL or upload image"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Background Color</Label>
                <div className="flex gap-2">
                  <input type="color" value={formData.background_color} onChange={(e) => setFormData({...formData, background_color: e.target.value})} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={formData.background_color} onChange={(e) => setFormData({...formData, background_color: e.target.value})} />
                </div>
              </div>
              <div>
                <Label>Text Color</Label>
                <div className="flex gap-2">
                  <input type="color" value={formData.text_color} onChange={(e) => setFormData({...formData, text_color: e.target.value})} className="w-10 h-10 rounded cursor-pointer" />
                  <Input value={formData.text_color} onChange={(e) => setFormData({...formData, text_color: e.target.value})} />
                </div>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Button Text (optional)</Label>
                <Input value={formData.button_text || ""} onChange={(e) => setFormData({...formData, button_text: e.target.value})} placeholder="Learn More" />
              </div>
              <div>
                <Label>Button Link (optional)</Label>
                <Input value={formData.button_link || ""} onChange={(e) => setFormData({...formData, button_link: e.target.value})} placeholder="/about" />
              </div>
            </div>
            
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button className="btn-primary" onClick={() => onSave(formData)}>Save Section</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  if (loading) return <div className="animate-pulse h-96 bg-gray-100 rounded-lg" />;

  return (
    <div className="space-y-6">
      {/* Permanent Image Hosting Banner */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
            <CheckCircle className="h-5 w-5 text-green-600" />
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-green-800 mb-1">✓ Permanent Image Hosting Active</h4>
            <p className="text-sm text-green-700 mb-2">
              <strong>Images are automatically saved permanently</strong> when uploaded. You can also paste external URLs from Unsplash, Imgur, or ImgBB.
            </p>
            <Button 
              variant="outline" 
              size="sm" 
              className="bg-white border-green-400 text-green-700 hover:bg-green-50"
              onClick={() => setShowImageGuide(true)}
            >
              📸 Image Upload Tips
            </Button>
          </div>
        </div>
      </div>
      
      <ImageGuideDialog />

      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Homepage Sections</h2>
          <p className="text-sm text-[#5A5A5A]">Manage content sections displayed on your homepage</p>
        </div>
        <Button className="btn-primary" onClick={() => { setEditingSection(null); setShowForm(true); }}>
          <Plus className="h-4 w-4 mr-2" /> Add Section
        </Button>
      </div>

      <div className="space-y-4">
        {sections.length === 0 ? (
          <Card className="p-8 text-center">
            <Layers className="h-12 w-12 mx-auto text-[#F8A5B8]/50 mb-4" />
            <p className="text-[#5A5A5A]">No sections yet. Add your first section!</p>
          </Card>
        ) : (
          sections.map((section) => (
            <Card key={section.id} className={`overflow-hidden ${!section.is_active ? 'opacity-60' : ''}`}>
              <div className="flex items-stretch">
                {section.image_url && (
                  <div className="w-32 h-32 flex-shrink-0">
                    <img loading="lazy" src={section.image_url} alt={section.title} className="w-full h-full object-cover" />
                  </div>
                )}
                <div className="flex-1 p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-display font-bold text-lg">{section.title}</h3>
                        <Badge variant="outline" className="text-xs">{section.section_type}</Badge>
                        {!section.is_active && <Badge variant="secondary">Hidden</Badge>}
                      </div>
                      {section.subtitle && <p className="text-sm text-[#5A5A5A]">{section.subtitle}</p>}
                      <p className="text-sm text-[#5A5A5A] mt-1 line-clamp-2">{section.content}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch checked={section.is_active} onCheckedChange={() => toggleActive(section)} />
                      <Button variant="ghost" size="sm" onClick={() => { setEditingSection(section); setShowForm(true); }}>
                        <Edit3 className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" className="text-red-500" onClick={() => deleteSection(section.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      {showForm && (
        <SectionForm 
          section={editingSection} 
          onSave={saveSection} 
          onClose={() => { setShowForm(false); setEditingSection(null); }} 
        />
      )}
    </div>
  );
};

// About Page Editor Component
const AboutPageEditor = () => {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const getHeaders = () => {
    const token = localStorage.getItem("reroots_token");
    return { Authorization: `Bearer ${token}` };
  };

  useEffect(() => {
    fetchContent();
  }, []);

  const fetchContent = async () => {
    try {
      const res = await axios.get(`${API}/admin/about-page`, { headers: getHeaders() });
      setContent(res.data);
    } catch (error) {
      console.error("Failed to fetch about page:", error);
      // Set defaults if not found
      setContent({
        hero_badge: "OUR STORY",
        hero_title: "Rooted in Science",
        hero_subtitle: "ReRoots was founded with a simple belief: skincare should be backed by science, not marketing hype.",
        mission_title: "Our Mission",
        mission_image: "https://images.unsplash.com/photo-1670444010821-e63091bddf1f?w=800",
        mission_text_1: "We combine cutting-edge biotechnology with time-tested natural ingredients to create skincare that delivers real, visible results.",
        mission_text_2: "Our flagship ingredient, PDRN (Polydeoxyribonucleotide), has been used in professional aesthetics for decades to help skin look more resilient and youthful.",
        mission_text_3: "Every product is developed in partnership with dermatologists and undergoes rigorous testing.",
        values_title: "Our Values",
        value_1_title: "Science-First",
        value_1_description: "Every ingredient is selected based on scientific research, not trends.",
        value_2_title: "Transparency",
        value_2_description: "We share our full ingredient lists and the science behind our formulations.",
        value_3_title: "Sustainability",
        value_3_description: "Eco-conscious packaging and responsibly sourced ingredients."
      });
    }
    setLoading(false);
  };

  const saveContent = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/about-page`, content, { headers: getHeaders() });
      toast.success("About page updated!");
    } catch (error) {
      toast.error("Failed to save changes");
    }
    setSaving(false);
  };

  const handleImageUpload = async (e, field) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${API}/upload/image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setContent({ ...content, [field]: res.data.url });
      if (res.data.permanent) {
        toast.success("Image uploaded permanently!");
      } else {
        toast.success("Image uploaded!");
      }
    } catch (error) {
      toast.error("Failed to upload image");
    }
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
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">About Page</h2>
          <p className="text-[#5A5A5A]">Edit the content shown on your About Us page</p>
        </div>
        <Button 
          onClick={saveContent} 
          disabled={saving}
          className="bg-[#F8A5B8] hover:bg-[#E991A5] text-white"
        >
          {saving ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Saving...</> : <><Save className="h-4 w-4 mr-2" /> SAVE CHANGES</>}
        </Button>
      </div>

      {/* Hero Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#2D2A2E] rounded-full flex items-center justify-center">
              <span className="text-white text-xs">1</span>
            </div>
            Hero Section
          </CardTitle>
          <CardDescription>The top banner of your About page</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Badge Text</Label>
              <Input
                value={content?.hero_badge || ""}
                onChange={(e) => setContent({ ...content, hero_badge: e.target.value })}
                placeholder="OUR STORY"
              />
            </div>
            <div>
              <Label>Main Title</Label>
              <Input
                value={content?.hero_title || ""}
                onChange={(e) => setContent({ ...content, hero_title: e.target.value })}
                placeholder="Rooted in Science"
              />
            </div>
          </div>
          <div>
            <Label>Subtitle</Label>
            <Textarea
              value={content?.hero_subtitle || ""}
              onChange={(e) => setContent({ ...content, hero_subtitle: e.target.value })}
              placeholder="Enter hero subtitle..."
              rows={2}
            />
          </div>
        </CardContent>
      </Card>

      {/* Mission Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#F8A5B8] rounded-full flex items-center justify-center">
              <span className="text-white text-xs">2</span>
            </div>
            Mission Section
          </CardTitle>
          <CardDescription>Tell your story and mission</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Section Title</Label>
            <Input
              value={content?.mission_title || ""}
              onChange={(e) => setContent({ ...content, mission_title: e.target.value })}
              placeholder="Our Mission"
            />
          </div>
          <div>
            <Label>Mission Image</Label>
            <div className="flex gap-2">
              <Input
                value={content?.mission_image || ""}
                onChange={(e) => setContent({ ...content, mission_image: e.target.value })}
                placeholder="https://..."
                className="flex-1"
              />
              <input
                type="file"
                accept="image/*"
                onChange={(e) => handleImageUpload(e, 'mission_image')}
                className="hidden"
                id="mission-image-upload"
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => document.getElementById('mission-image-upload').click()}
              >
                <Upload className="h-4 w-4" />
              </Button>
            </div>
            {content?.mission_image && (
              <img loading="lazy" src={content.mission_image} alt="Mission" className="mt-2 w-32 h-32 object-cover rounded-lg" />
            )}
          </div>
          <div>
            <Label>Paragraph 1</Label>
            <Textarea
              value={content?.mission_text_1 || ""}
              onChange={(e) => setContent({ ...content, mission_text_1: e.target.value })}
              rows={3}
            />
          </div>
          <div>
            <Label>Paragraph 2</Label>
            <Textarea
              value={content?.mission_text_2 || ""}
              onChange={(e) => setContent({ ...content, mission_text_2: e.target.value })}
              rows={3}
            />
          </div>
          <div>
            <Label>Paragraph 3</Label>
            <Textarea
              value={content?.mission_text_3 || ""}
              onChange={(e) => setContent({ ...content, mission_text_3: e.target.value })}
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      {/* Values Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
              <span className="text-white text-xs">3</span>
            </div>
            Values Section
          </CardTitle>
          <CardDescription>Your brand values (3 items)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label>Section Title</Label>
            <Input
              value={content?.values_title || ""}
              onChange={(e) => setContent({ ...content, values_title: e.target.value })}
              placeholder="Our Values"
            />
          </div>
          
          {/* Value 1 */}
          <div className="p-4 border rounded-lg space-y-3">
            <div className="flex items-center gap-2">
              <Badge className="bg-[#F8A5B8]">Value 1</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Title</Label>
                <Input
                  value={content?.value_1_title || ""}
                  onChange={(e) => setContent({ ...content, value_1_title: e.target.value })}
                />
              </div>
              <div>
                <Label>Description</Label>
                <Input
                  value={content?.value_1_description || ""}
                  onChange={(e) => setContent({ ...content, value_1_description: e.target.value })}
                />
              </div>
            </div>
          </div>

          {/* Value 2 */}
          <div className="p-4 border rounded-lg space-y-3">
            <div className="flex items-center gap-2">
              <Badge className="bg-[#F8A5B8]">Value 2</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Title</Label>
                <Input
                  value={content?.value_2_title || ""}
                  onChange={(e) => setContent({ ...content, value_2_title: e.target.value })}
                />
              </div>
              <div>
                <Label>Description</Label>
                <Input
                  value={content?.value_2_description || ""}
                  onChange={(e) => setContent({ ...content, value_2_description: e.target.value })}
                />
              </div>
            </div>
          </div>

          {/* Value 3 */}
          <div className="p-4 border rounded-lg space-y-3">
            <div className="flex items-center gap-2">
              <Badge className="bg-[#F8A5B8]">Value 3</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Title</Label>
                <Input
                  value={content?.value_3_title || ""}
                  onChange={(e) => setContent({ ...content, value_3_title: e.target.value })}
                />
              </div>
              <div>
                <Label>Description</Label>
                <Input
                  value={content?.value_3_description || ""}
                  onChange={(e) => setContent({ ...content, value_3_description: e.target.value })}
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preview Link */}
      <div className="flex justify-center">
        <a 
          href="/about" 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-[#F8A5B8] hover:underline flex items-center gap-2"
        >
          <Eye className="h-4 w-4" />
          Preview About Page
        </a>
      </div>
    </div>
  );
};


// Admin Portal Page - SEO Optimized Landing for Admin Access
const AdminPortal = () => {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState(""); // Can be email or phone
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [adminLoginBackground, setAdminLoginBackground] = useState(null);
  const [rememberMe, setRememberMe] = useState(localStorage.getItem("reroots_remember_me") === "true");

  // Set page title and meta for SEO
  useEffect(() => {
    document.title = "ReRoots Admin Portal | Store Management Dashboard";
    
    // Update meta description
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute('content', 'ReRoots Admin Portal - Secure access to manage your skincare store. Handle products, orders, customers, and website content.');
    }
    
    // Fetch admin login background
    axios.get(`${API}/public/login-backgrounds`)
      .then(res => setAdminLoginBackground(res.data.admin_login_background_image))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!authLoading && user?.is_admin) {
      navigate("/admin");
    }
  }, [user, authLoading, navigate]);

  // Handle successful Google login for admin
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const handleGoogleSuccess = (googleUser, token) => {
    if (googleUser.is_admin || googleUser.is_team_member) {
      navigate('/admin');
    }
  };

  const handleGoogleError = (error) => {
    console.error('Admin Google auth error:', error);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      // Detect if input is email or phone
      const isEmail = identifier.includes("@");
      const isPhone = /^[+]?[\d\s()-]+$/.test(identifier.replace(/\s/g, ''));
      
      if (isEmail) {
        await login(identifier, password, null, rememberMe);
      } else if (isPhone) {
        await login(null, password, identifier, rememberMe);
      } else {
        // Default to email
        await login(identifier, password, null, rememberMe);
      }
      toast.success("Welcome back, Admin!");
      navigate("/admin");
    } catch (error) {
      toast.error("Invalid admin credentials");
    }
    setIsLoading(false);
  };

  // Use gradient background instead of stock photo
  const defaultBg = null;

  // Dynamic greeting based on time of day
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning! Ready to start the day? ☀️";
    if (hour < 17) return "Good afternoon! Ready to manage the day? 💼";
    if (hour < 21) return "Good evening! Let's wrap things up! 🌙";
    return "Working late? Let's get things done! ⭐";
  };

  // Use ReRoots lab image as admin background
  const defaultAdminBg = "https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/vmettfqd_1767379332331.jpg";

  return (
    <div 
      className="min-h-screen flex items-center justify-center p-2 sm:p-4"
      style={{
        background: `linear-gradient(135deg, rgba(45,42,46,0.85) 0%, rgba(45,42,46,0.7) 100%), url('${adminLoginBackground || defaultAdminBg}') center/cover fixed`,
      }}
    >
      {/* SEO Hidden Content */}
      <h1 className="sr-only">ReRoots Admin Portal - Store Management Dashboard</h1>
      
      <div className="w-full max-w-md px-2 sm:px-0">
        <Card className="shadow-2xl border-0 bg-white/95 backdrop-blur-sm rounded-xl overflow-hidden" style={{ borderTop: '4px solid #C9A86C' }}>
          <CardHeader className="text-center pt-4 sm:pt-8 pb-2 px-4 sm:px-6">
            <img 
              src={`https://res.cloudinary.com/ddpphzqdg/image/fetch/w_160,h_64,c_fit,q_auto,f_auto/${encodeURIComponent("https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png")}`}
              alt="ReRoots Beauty Enhancer" 
              className="h-12 sm:h-16 w-auto object-contain mx-auto mb-2 sm:mb-4"
              style={{ mixBlendMode: 'multiply' }}
              width="160"
              height="64"
            />
            <CardTitle className="font-display text-lg sm:text-xl text-[#2D2A2E]">
              Central Operations<br />
              <span className="text-[#2D2A2E]">Team Login</span>
            </CardTitle>
            <p className="text-xs sm:text-sm text-[#888888] mt-1 sm:mt-2 italic">Secure Management Portal</p>
          </CardHeader>
          <CardContent className="px-4 sm:px-6 pb-4 sm:pb-6">
            <form onSubmit={handleLogin} className="space-y-3 sm:space-y-4">
              <div>
                <Label htmlFor="admin-identifier" className="text-sm">Email / Phone Number</Label>
                <Input
                  id="admin-identifier"
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="admin@reroots.ca or +1234567890"
                  className="mt-1 h-10 sm:h-11 text-sm"
                />
              </div>
              <div>
                <Label htmlFor="admin-password" className="text-sm">Password</Label>
                <Input
                  id="admin-password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="mt-1 h-10 sm:h-11 text-sm"
                />
              </div>
              <div className="flex items-center justify-between text-xs sm:text-sm">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="admin-remember-me"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-3 h-3 sm:w-4 sm:h-4 rounded border-gray-300 text-[#C9A86C] focus:ring-[#C9A86C]"
                  />
                  <Label htmlFor="admin-remember-me" className="text-xs sm:text-sm text-[#5A5A5A] cursor-pointer">
                    Keep me logged in
                  </Label>
                </div>
                <Link
                  to="/forgot-password"
                  className="text-xs sm:text-sm text-[#C9A86C] hover:text-[#B8956A] hover:underline"
                >
                  Forgot Password?
                </Link>
              </div>
              
              {/* Dynamic Greeting */}
              <p className="text-center text-xs sm:text-sm text-[#C9A86C] italic py-1 sm:py-2">
                {getGreeting()}
              </p>
              
              <Button
                type="submit"
                disabled={isLoading}
                className="w-full text-white font-medium tracking-wider rounded-full py-5 sm:py-6 text-sm sm:text-base"
                style={{ background: 'linear-gradient(135deg, #C9A86C 0%, #B8956A 100%)' }}
              >
                {isLoading ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Signing In...</>
                ) : (
                  "SIGN IN"
                )}
              </Button>

              {/* Divider */}
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200"></div>
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="px-3 bg-white text-gray-500">or continue with</span>
                </div>
              </div>

              {/* Google SSO Button - Uses Custom Google OAuth Credentials */}
              <GoogleAuthButton
                isAdmin={true}
                onSuccess={handleGoogleSuccess}
                onError={handleGoogleError}
                buttonText="Sign in with Google"
              />

              {/* Security Note */}
              <p className="text-center text-[10px] text-gray-400 mt-3">
                🔒 SSO login is only available for pre-approved admin accounts
              </p>
            </form>
          </CardContent>
        </Card>

        {/* Back to Store Link */}
        <div className="mt-4 sm:mt-6 text-center">
          <Link to="/" className="text-white/70 hover:text-white text-xs sm:text-sm flex items-center justify-center gap-1 italic">
            <ArrowRight className="h-3 w-3 rotate-180" /> Back to Store
          </Link>
        </div>

        {/* Admin Features Preview - Hidden on very small screens */}
        <div className="mt-4 sm:mt-8 grid grid-cols-4 sm:grid-cols-2 gap-2 sm:gap-3">
          <div className="bg-white/10 backdrop-blur rounded-lg p-2 sm:p-3 text-center">
            <Package className="h-4 w-4 sm:h-6 sm:w-6 text-[#F8A5B8] mx-auto mb-0.5 sm:mb-1" />
            <p className="text-white text-[10px] sm:text-xs">Products</p>
          </div>
          <div className="bg-white/10 backdrop-blur rounded-lg p-2 sm:p-3 text-center">
            <ShoppingBag className="h-4 w-4 sm:h-6 sm:w-6 text-[#F8A5B8] mx-auto mb-0.5 sm:mb-1" />
            <p className="text-white text-[10px] sm:text-xs">Orders</p>
          </div>
          <div className="bg-white/10 backdrop-blur rounded-lg p-2 sm:p-3 text-center">
            <Users className="h-4 w-4 sm:h-6 sm:w-6 text-[#F8A5B8] mx-auto mb-0.5 sm:mb-1" />
            <p className="text-white text-[10px] sm:text-xs">Customers</p>
          </div>
          <div className="bg-white/10 backdrop-blur rounded-lg p-2 sm:p-3 text-center">
            <Sparkles className="h-4 w-4 sm:h-6 sm:w-6 text-[#F8A5B8] mx-auto mb-0.5 sm:mb-1" />
            <p className="text-white text-[10px] sm:text-xs">AI Studio</p>
          </div>
        </div>
      </div>
    </div>
  );
};

// Subscriptions Manager Component
const SubscriptionsManager = () => {
  const [settings, setSettings] = useState(null);
  const [plans, setPlans] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [saving, setSaving] = useState(false);
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    try {
      const [settingsRes, plansRes, subsRes] = await Promise.all([
        axios.get(`${API}/subscription-settings`),
        axios.get(`${API}/admin/subscription-plans`, { headers }),
        axios.get(`${API}/admin/subscriptions`, { headers })
      ]);
      setSettings(settingsRes.data);
      setPlans(plansRes.data);
      setSubscriptions(subsRes.data);
    } catch (error) {
      console.error(error);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/subscription-settings`, settings, { headers });
      toast.success("Settings saved!");
    } catch (error) {
      toast.error("Failed to save settings");
    }
    setSaving(false);
  };

  const savePlan = async (planData) => {
    try {
      if (editingPlan) {
        await axios.put(`${API}/admin/subscription-plans/${editingPlan.id}`, planData, { headers });
        toast.success("Plan updated!");
      } else {
        await axios.post(`${API}/admin/subscription-plans`, planData, { headers });
        toast.success("Plan created!");
      }
      fetchData();
      setShowPlanForm(false);
      setEditingPlan(null);
    } catch (error) {
      toast.error("Failed to save plan");
    }
  };

  const deletePlan = async (id) => {
    if (!window.confirm("Delete this plan?")) return;
    try {
      await axios.delete(`${API}/admin/subscription-plans/${id}`, { headers });
      toast.success("Plan deleted!");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete plan");
    }
  };

  const updateSubscription = async (subId, data) => {
    try {
      await axios.put(`${API}/admin/subscriptions/${subId}`, data, { headers });
      toast.success("Subscription updated!");
      fetchData();
    } catch (error) {
      toast.error("Failed to update subscription");
    }
  };

  // Plan Form Component
  const PlanForm = ({ plan, onSave, onClose }) => {
    const [formData, setFormData] = useState(plan || {
      name: "", description: "", price: 0, 
      interval_type: "months", interval_value: 1,
      discount_percent: 15, features: [], min_commitment_months: 0, is_active: true
    });
    const [featureInput, setFeatureInput] = useState("");

    const addFeature = () => {
      if (featureInput.trim()) {
        setFormData({ ...formData, features: [...formData.features, featureInput.trim()] });
        setFeatureInput("");
      }
    };

    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
          <CardHeader>
            <CardTitle>{plan ? "Edit Plan" : "Create Subscription Plan"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Plan Name</Label>
              <Input value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} placeholder="Weekly Essentials" />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} placeholder="Get your skincare delivered automatically" rows={2} />
            </div>
            
            {/* Delivery Interval - Days/Weeks/Months */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <Label className="text-blue-800 mb-2 block">📦 Delivery Interval</Label>
              <p className="text-xs text-blue-600 mb-3">How often should products be delivered?</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm">Every</Label>
                  <Input 
                    type="text" 
                    inputMode="numeric"
                    value={formData.interval_value ?? ''} 
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '' || /^\d*$/.test(val)) {
                        setFormData({...formData, interval_value: val === '' ? '' : parseInt(val)});
                      }
                    }} 
                    placeholder="1"
                  />
                </div>
                <div>
                  <Label className="text-sm">Period</Label>
                  <Select value={formData.interval_type || "months"} onValueChange={(v) => setFormData({...formData, interval_type: v})}>
                    <SelectTrigger className="w-full"><SelectValue placeholder="Select period" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="days">Days</SelectItem>
                      <SelectItem value="weeks">Weeks</SelectItem>
                      <SelectItem value="months">Months</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <p className="text-xs text-blue-700 mt-2">
                ✨ Delivery: Every {formData.interval_value || 1} {formData.interval_type || "months"}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Price ($)</Label>
                <Input 
                  type="text" 
                  inputMode="decimal"
                  value={formData.price} 
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '' || /^\d*\.?\d*$/.test(val)) {
                      setFormData({...formData, price: val === '' ? '' : val});
                    }
                  }}
                  onFocus={(e) => e.target.select()}
                />
                <p className="text-xs text-muted-foreground">0 = use product price</p>
              </div>
              <div>
                <Label>Discount %</Label>
                <Input 
                  type="text" 
                  inputMode="numeric"
                  value={formData.discount_percent} 
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '' || /^\d*$/.test(val)) {
                      setFormData({...formData, discount_percent: val === '' ? '' : val});
                    }
                  }}
                  onFocus={(e) => e.target.select()}
                />
              </div>
            </div>
            <div>
              <Label>Features</Label>
              <div className="flex gap-2 mb-2">
                <Input value={featureInput} onChange={(e) => setFeatureInput(e.target.value)} placeholder="Add feature..." onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addFeature())} />
                <Button type="button" variant="outline" onClick={addFeature}><Plus className="h-4 w-4" /></Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {formData.features?.map((f, i) => (
                  <Badge key={i} variant="secondary" className="flex items-center gap-1">
                    {f}
                    <button onClick={() => setFormData({...formData, features: formData.features.filter((_, idx) => idx !== i)})}><X className="h-3 w-3" /></button>
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={formData.is_active} onCheckedChange={(c) => setFormData({...formData, is_active: c})} />
              <Label>Active</Label>
            </div>
            <div className="flex gap-2 pt-4">
              <Button className="flex-1 btn-primary" onClick={() => onSave(formData)}>Save Plan</Button>
              <Button variant="outline" onClick={onClose}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  if (loading) return <div className="animate-pulse h-96 bg-gray-100 rounded-lg" />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Subscriptions</h2>
          <p className="text-sm text-[#5A5A5A]">Manage subscription plans and customer subscriptions</p>
        </div>
      </div>

      {/* Subscription Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Settings className="h-5 w-5 text-[#F8A5B8]" />
            Subscription Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium">Enable Subscriptions</p>
              <p className="text-sm text-muted-foreground">Show subscription options on products</p>
            </div>
            <Switch checked={settings?.enabled} onCheckedChange={(c) => setSettings({...settings, enabled: c})} />
          </div>
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium">Allow Cancel Anytime</p>
              <p className="text-sm text-muted-foreground">Customers can cancel without commitment</p>
            </div>
            <Switch checked={settings?.allow_cancel_anytime} onCheckedChange={(c) => setSettings({...settings, allow_cancel_anytime: c})} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Default Discount %</Label>
              <Input 
                type="text" 
                inputMode="numeric"
                value={settings?.default_discount_percent || 15} 
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '' || /^\d*$/.test(val)) {
                    setSettings({...settings, default_discount_percent: val === '' ? 0 : parseInt(val) || 0});
                  }
                }} 
              />
            </div>
            <div>
              <Label>Subscribe Button Text</Label>
              <Input value={settings?.subscribe_button_text || ""} onChange={(e) => setSettings({...settings, subscribe_button_text: e.target.value})} />
            </div>
          </div>
          <div>
            <Label>Subscription Description</Label>
            <Textarea value={settings?.subscription_description || ""} onChange={(e) => setSettings({...settings, subscription_description: e.target.value})} rows={2} />
          </div>
          <Button onClick={saveSettings} disabled={saving} className="btn-primary">
            <Save className="h-4 w-4 mr-2" />{saving ? "Saving..." : "Save Settings"}
          </Button>
        </CardContent>
      </Card>

      {/* Subscription Plans */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="text-lg">Subscription Plans</CardTitle>
            <Button className="btn-primary" onClick={() => { setEditingPlan(null); setShowPlanForm(true); }}>
              <Plus className="h-4 w-4 mr-2" /> Add Plan
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {plans.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No plans yet. Create your first subscription plan!</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {plans.map(plan => (
                <Card key={plan.id} className={`${!plan.is_active ? 'opacity-60' : ''}`}>
                  <CardContent className="pt-6">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-bold text-lg">{plan.name}</h3>
                        <p className="text-2xl font-bold text-[#F8A5B8]">
                          ${plan.price || 0}
                          <span className="text-sm text-muted-foreground">
                            /every {plan.interval_value || 1} {plan.interval_type || plan.interval || "months"}
                          </span>
                        </p>
                      </div>
                      <Badge className={plan.is_active ? "bg-green-500" : "bg-gray-400"}>{plan.is_active ? "Active" : "Inactive"}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">{plan.description}</p>
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <Badge variant="outline" className="bg-green-50 text-green-700">{plan.discount_percent}% off</Badge>
                      <Badge variant="outline" className="bg-blue-50 text-blue-700">
                        📦 Every {plan.interval_value || 1} {plan.interval_type || "months"}
                      </Badge>
                    </div>
                    {plan.features?.length > 0 && (
                      <ul className="text-sm space-y-1 mb-4">
                        {plan.features.map((f, i) => <li key={i} className="flex items-center gap-2"><Check className="h-3 w-3 text-green-500" />{f}</li>)}
                      </ul>
                    )}
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" className="flex-1" onClick={() => { setEditingPlan(plan); setShowPlanForm(true); }}><Edit3 className="h-3 w-3 mr-1" /> Edit</Button>
                      <Button variant="outline" size="sm" className="text-red-500" onClick={() => deletePlan(plan.id)}><Trash2 className="h-3 w-3" /></Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Customer Subscriptions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Customer Subscriptions ({subscriptions.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {subscriptions.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No customer subscriptions yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Customer</th>
                    <th className="text-left py-2">Product/Plan</th>
                    <th className="text-left py-2">Delivery</th>
                    <th className="text-left py-2">Next Delivery</th>
                    <th className="text-left py-2">Status</th>
                    <th className="text-left py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {subscriptions.map(sub => (
                    <tr key={sub.id} className="border-b">
                      <td className="py-2">
                        <div>{sub.user_name || "Customer"}</div>
                        <div className="text-xs text-muted-foreground">{sub.user_email}</div>
                      </td>
                      <td className="py-2">{sub.product_name || sub.plan_id || "N/A"}</td>
                      <td className="py-2">
                        <Badge variant="outline" className="bg-blue-50">
                          Every {sub.interval_value || 1} {sub.interval_type || sub.interval || "months"}
                        </Badge>
                      </td>
                      <td className="py-2 text-xs">
                        {sub.next_delivery_date ? new Date(sub.next_delivery_date).toLocaleDateString() : "N/A"}
                      </td>
                      <td className="py-2">
                        <Badge className={sub.status === "active" ? "bg-green-500" : sub.status === "paused" ? "bg-yellow-500" : "bg-red-500"}>{sub.status}</Badge>
                      </td>
                      <td className="py-2">
                        <Select value={sub.status} onValueChange={(v) => updateSubscription(sub.id, { status: v })}>
                          <SelectTrigger className="w-28 h-8"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="active">Active</SelectItem>
                            <SelectItem value="paused">Paused</SelectItem>
                            <SelectItem value="cancelled">Cancelled</SelectItem>
                          </SelectContent>
                        </Select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {showPlanForm && <PlanForm plan={editingPlan} onSave={savePlan} onClose={() => { setShowPlanForm(false); setEditingPlan(null); }} />}
    </div>
  );
};

// OrderTrackingManager REMOVED - Now using FlagShip auto-labels only
// See /api/shipping/create-shipment for label generation

// Security Dashboard Component
const SecurityDashboard = () => {
  const [securityStatus, setSecurityStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSecurityStatus = async () => {
      try {
        const token = localStorage.getItem("reroots_admin_token") || localStorage.getItem("reroots_token");
        const res = await axios.get(`${API}/admin/security-status`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSecurityStatus(res.data);
      } catch (err) {
        console.error("Failed to fetch security status:", err);
      }
      setLoading(false);
    };
    fetchSecurityStatus();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="h-5 w-5 text-green-600" />
        <h3 className="font-display text-xl font-bold">Security Dashboard</h3>
      </div>

      {/* Security Status Banner */}
      <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
            <Check className="h-5 w-5 text-green-600" />
          </div>
          <div>
            <p className="font-semibold text-green-800">Your store is protected</p>
            <p className="text-sm text-green-600">All security features are active</p>
          </div>
        </div>
      </div>

      {/* Security Features Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {securityStatus?.security_features && Object.entries(securityStatus.security_features).map(([feature, enabled]) => (
          <div key={feature} className="flex items-center justify-between p-3 bg-white border rounded-lg">
            <div className="flex items-center gap-2">
              {enabled ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : (
                <X className="h-4 w-4 text-red-500" />
              )}
              <span className="text-sm capitalize">{feature.replace(/_/g, ' ')}</span>
            </div>
            <Badge className={enabled ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}>
              {enabled ? "Active" : "Inactive"}
            </Badge>
          </div>
        ))}
      </div>

      {/* Current Status */}
      <div className="p-4 bg-gray-50 rounded-lg">
        <h4 className="font-semibold mb-3">Current Status</h4>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 bg-white rounded border">
            <p className="text-2xl font-bold text-[#2D2A2E]">
              {securityStatus?.current_status?.locked_accounts || 0}
            </p>
            <p className="text-xs text-gray-500">Locked Accounts</p>
          </div>
          <div className="text-center p-3 bg-white rounded border">
            <p className="text-2xl font-bold text-[#2D2A2E]">
              {securityStatus?.current_status?.accounts_with_failed_logins || 0}
            </p>
            <p className="text-xs text-gray-500">Failed Login Attempts</p>
          </div>
          <div className="text-center p-3 bg-white rounded border">
            <p className="text-2xl font-bold text-[#2D2A2E]">
              {securityStatus?.current_status?.rate_limited_ips || 0}
            </p>
            <p className="text-xs text-gray-500">Rate Limited IPs</p>
          </div>
        </div>
      </div>

      {/* Security Recommendations */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h4 className="font-semibold text-blue-800 mb-3 flex items-center gap-2">
          <Shield className="h-4 w-4" />
          Security Recommendations
        </h4>
        <ul className="space-y-2">
          {securityStatus?.recommendations?.map((rec, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-blue-700">
              <Check className="h-4 w-4 mt-0.5 flex-shrink-0" />
              {rec}
            </li>
          ))}
        </ul>
      </div>

      {/* Security Features Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">🔒 Rate Limiting</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-gray-500">
              100 requests per minute per IP. Login attempts limited to 5 per 5 minutes.
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">🛡️ Account Lockout</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-gray-500">
              Accounts are locked for 15 minutes after 5 failed login attempts.
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">🔐 Password Security</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-gray-500">
              Passwords must be 8+ characters with uppercase, lowercase, and numbers. Hashed with bcrypt.
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">🌐 Security Headers</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-gray-500">
              XSS protection, clickjacking prevention, and content security policy enabled.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const SkincareNewsTicker = () => {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isPaused, setIsPaused] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null); // Category filter
  const tickerRef = useRef(null);

  const fetchNews = async () => {
    try {
      const token = localStorage.getItem("reroots_token");
      const res = await axios.get(`${API}/admin/skincare-news`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNews(res.data.news || []);
      setLastUpdated(new Date(res.data.last_updated));
      setError(null);
    } catch (err) {
      console.error("Failed to fetch news:", err);
      setError("Unable to load news");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNews();
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchNews, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Filter news by selected category
  const filteredNews = selectedCategory 
    ? news.filter(item => item.category === selectedCategory)
    : news;

  // Category colors
  const getCategoryColor = (category, isSelected = false) => {
    const colors = {
      'Skincare': isSelected ? 'bg-pink-500 text-white' : 'bg-pink-100 text-pink-700 hover:bg-pink-200',
      'Beauty': isSelected ? 'bg-purple-500 text-white' : 'bg-purple-100 text-purple-700 hover:bg-purple-200',
      'Cosmetics': isSelected ? 'bg-blue-500 text-white' : 'bg-blue-100 text-blue-700 hover:bg-blue-200',
      'Regulatory': isSelected ? 'bg-yellow-500 text-white' : 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200',
      'Business': isSelected ? 'bg-green-500 text-white' : 'bg-green-100 text-green-700 hover:bg-green-200'
    };
    return colors[category] || 'bg-gray-100 text-gray-700';
  };

  // Format time ago
  const formatTimeAgo = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return `${diffDays}d ago`;
    } catch {
      return '';
    }
  };

  if (loading) {
    return (
      <Card className="mb-6 bg-gradient-to-r from-[#2D2A2E] to-[#4A4548] text-white overflow-hidden">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="animate-pulse flex items-center gap-2">
              <div className="w-6 h-6 bg-white/20 rounded"></div>
              <div className="h-4 w-48 bg-white/20 rounded"></div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || news.length === 0) {
    return (
      <Card className="mb-6 bg-gradient-to-r from-[#2D2A2E] to-[#4A4548] text-white">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">📰</span>
              <span className="font-semibold">Skincare Industry News</span>
            </div>
            <Button size="sm" variant="ghost" className="text-white hover:bg-white/10" onClick={fetchNews}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-white/60 text-sm mt-2">{error || "No news available at the moment"}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mb-6 bg-gradient-to-r from-[#2D2A2E] to-[#4A4548] text-white overflow-hidden">
      <CardContent className="p-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xl animate-pulse">📰</span>
              <span className="font-semibold">Skincare Industry News</span>
              <Badge className="bg-red-500 text-white text-xs animate-pulse">LIVE</Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-xs text-white/50">
                Updated {formatTimeAgo(lastUpdated.toISOString())}
              </span>
            )}
            <Button 
              size="sm" 
              variant="ghost" 
              className="text-white hover:bg-white/10 h-8 w-8 p-0"
              onClick={() => setIsPaused(!isPaused)}
              title={isPaused ? "Resume" : "Pause"}
            >
              {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
            </Button>
            <Button 
              size="sm" 
              variant="ghost" 
              className="text-white hover:bg-white/10 h-8 w-8 p-0"
              onClick={fetchNews}
              title="Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Scrolling Ticker */}
        <div 
          className="relative overflow-hidden py-3 px-4"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
          <div 
            ref={tickerRef}
            className={`flex gap-8 whitespace-nowrap ${isPaused ? '' : 'animate-ticker'}`}
            style={{
              animation: isPaused ? 'none' : 'ticker 60s linear infinite'
            }}
          >
            {/* Double the news items for seamless loop */}
            {[...filteredNews, ...filteredNews].map((item, idx) => (
              <a 
                key={`${item.id}-${idx}`}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 hover:text-[#F8A5B8] transition-colors group"
              >
                <Badge className={`${getCategoryColor(item.category)} text-xs shrink-0`}>
                  {item.category}
                </Badge>
                <span className="font-medium group-hover:underline">{item.title}</span>
                <span className="text-white/40 text-xs shrink-0">
                  {item.source} • {formatTimeAgo(item.published)}
                </span>
                <span className="text-white/30 mx-4">|</span>
              </a>
            ))}
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex items-center gap-3 px-4 py-2 border-t border-white/10 bg-black/20 overflow-x-auto">
          <span className="text-xs text-white/40 shrink-0">Filter:</span>
          <Badge 
            className={`text-xs shrink-0 cursor-pointer transition-all ${
              selectedCategory === null 
                ? 'bg-white text-gray-800' 
                : 'bg-white/20 text-white hover:bg-white/30'
            }`}
            onClick={() => setSelectedCategory(null)}
          >
            All
          </Badge>
          {['Skincare', 'Beauty', 'Cosmetics', 'Regulatory', 'Business'].map(cat => (
            <Badge 
              key={cat} 
              className={`${getCategoryColor(cat, selectedCategory === cat)} text-xs shrink-0 cursor-pointer transition-all`}
              onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
            >
              {cat}
            </Badge>
          ))}
          {selectedCategory && (
            <span className="text-xs text-white/50 ml-2">
              ({filteredNews.length} articles)
            </span>
          )}
        </div>
      </CardContent>

      {/* CSS for ticker animation */}
      <style>{`
        @keyframes ticker {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-ticker {
          animation: ticker 60s linear infinite;
        }
      `}</style>
    </Card>
  );
};
// Main App
// SEO Component for dynamic meta tags - Enhanced for Tri-Brand Support
const SEO = ({ title, description, keywords, image, url, type = "website", product = null, brand = "reroots", reviews = [] }) => {
  const baseUrl = "https://reroots.ca";
  
  // Brand-specific configurations for Open Graph and Schema
  const BRAND_SEO_CONFIG = {
    reroots: {
      siteName: "ReRoots Biotech Skincare Canada",
      defaultImage: "https://images.unsplash.com/photo-1570194065650-d99fb4b38b17?w=1200",
      twitterHandle: "@rerootscanada",
      locale: "en_CA",
      themeColor: "#D4AF37",
      description: "Shop ReRoots Canada for high-performance bio-active PDRN skincare. Our formulas help your skin's surface feel more resilient and look visibly rejuvenated.",
      keywords: "ReRoots, PDRN skincare Canada, biotech skincare, bio-active serum, AURA-GEN, Canadian skincare brand"
    },
    oroe: {
      siteName: "OROÉ | Luxury Cellular Skincare",
      defaultImage: "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=1200",
      twitterHandle: "@oroe_skincare",
      locale: "en_CA",
      themeColor: "#D4AF37",
      description: "OROÉ - Ultra-luxury cellular rejuvenation with EGF & PDRN. Artisan-crafted in Canada for discerning skin. Limited batch releases for VIP members.",
      keywords: "OROÉ, luxury skincare, EGF serum, PDRN Canada, anti-aging, cellular rejuvenation, premium skincare"
    },
    lavela: {
      siteName: "LA VELA BIANCA | Teen Skincare",
      defaultImage: "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=1200",
      twitterHandle: "@La_Vela_Bianca",
      locale: "en_CA",
      themeColor: "#0D4D4D",
      description: "LA VELA BIANCA - Premium pediatric-safe skincare for teens 8-18. Centella Asiatica formulas designed for young, developing skin. Canadian-Italian technology.",
      keywords: "teen skincare, pediatric safe, LA VELA BIANCA, Centella Asiatica, Gen Alpha skincare, safe teen beauty"
    }
  };
  
  const brandConfig = BRAND_SEO_CONFIG[brand] || BRAND_SEO_CONFIG.reroots;
  const defaultImage = brandConfig.defaultImage;
  
  const seoTitle = title ? `${title} | ${brandConfig.siteName}` : brandConfig.siteName;
  const seoDescription = description || brandConfig.description;
  const seoKeywords = keywords || brandConfig.keywords;
  const seoImage = image || defaultImage;
  const seoUrl = url ? `${baseUrl}${url}` : baseUrl;
  
  // Build comprehensive product schema for Google - Enhanced with ingredients
  const buildProductSchema = (product) => {
    const schema = {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": product.name,
      "description": product.description,
      "image": product.images || [product.image],
      "brand": {
        "@type": "Brand",
        "name": product.brand || "ReRoots"
      },
      "sku": product.id,
      "category": product.google_product_category || "Health & Beauty > Skin Care > Facial Serums",
      "material": "PDRN (Polydeoxyribonucleotide), Tranexamic Acid, Niacinamide, Salicylic Acid",
      "additionalProperty": [
        {
          "@type": "PropertyValue",
          "name": "Active Ingredients",
          "value": "PDRN 2%, Tranexamic Acid 5%, Niacinamide, Salicylic Acid"
        },
        {
          "@type": "PropertyValue",
          "name": "Skin Type",
          "value": "All Skin Types"
        },
        {
          "@type": "PropertyValue",
          "name": "Skin Concerns",
          "value": "Dark Spots, Uneven Tone, Fine Lines, Dullness"
        },
        {
          "@type": "PropertyValue",
          "name": "Key Benefit",
          "value": "Bio-Regeneration, Skin Renewal, Brightening"
        },
        {
          "@type": "PropertyValue",
          "name": "Origin",
          "value": "Made in Canada"
        }
      ],
      "offers": {
        "@type": "Offer",
        "url": seoUrl,
        "priceCurrency": "CAD",
        "price": product.price,
        "priceValidUntil": new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        "availability": product.stock > 0 
          ? "https://schema.org/InStock" 
          : product.allow_preorder 
            ? "https://schema.org/PreOrder"
            : "https://schema.org/OutOfStock",
        "itemCondition": "https://schema.org/NewCondition",
        "seller": {
          "@type": "Organization",
          "name": "ReRoots Skincare"
        },
        "shippingDetails": {
          "@type": "OfferShippingDetails",
          "shippingRate": {
            "@type": "MonetaryAmount",
            "value": product.price >= 75 ? "0" : "9.99",
            "currency": "CAD"
          },
          "shippingDestination": {
            "@type": "DefinedRegion",
            "addressCountry": "CA"
          },
          "deliveryTime": {
            "@type": "ShippingDeliveryTime",
            "handlingTime": {
              "@type": "QuantitativeValue",
              "minValue": 1,
              "maxValue": 2,
              "unitCode": "DAY"
            },
            "transitTime": {
              "@type": "QuantitativeValue",
              "minValue": 3,
              "maxValue": 7,
              "unitCode": "DAY"
            }
          }
        },
        "hasMerchantReturnPolicy": {
          "@type": "MerchantReturnPolicy",
          "applicableCountry": "CA",
          "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
          "merchantReturnDays": 30,
          "returnMethod": "https://schema.org/ReturnByMail",
          "returnFees": "https://schema.org/FreeReturn"
        }
      }
    };
    
    // Add GTIN if available
    if (product.gtin) {
      schema.gtin = product.gtin;
      schema.gtin13 = product.gtin;
    }
    
    // Add MPN if available
    if (product.mpn) {
      schema.mpn = product.mpn;
    }
    
    // Add aggregate rating if available
    if (product.rating && product.review_count) {
      schema.aggregateRating = {
        "@type": "AggregateRating",
        "ratingValue": product.rating,
        "reviewCount": product.review_count,
        "bestRating": 5,
        "worstRating": 1
      };
    }
    
    return schema;
  };
  
  // Organization schema for site-wide SEO - Enhanced for brand differentiation
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${baseUrl}/#organization`,
    "name": "ReRoots Biotech Skincare",
    "alternateName": ["ReRoots Canada", "ReRoots Skincare", "ReRoots PDRN", "reroots.ca"],
    "url": baseUrl,
    "logo": {
      "@type": "ImageObject",
      "url": `${baseUrl}/logo.png`,
      "width": 200,
      "height": 200
    },
    "image": `${baseUrl}/og-image.jpg`,
    "description": "ReRoots is a Canadian biotech skincare brand featuring high-performance bio-active PDRN (Polydeoxyribonucleotide) serums. Our formulas help the skin's surface feel more resilient and look visibly rejuvenated. Not affiliated with organic farming or food brands.",
    "slogan": "Science-Backed Skincare for Radiant Skin",
    "foundingDate": "2024",
    "foundingLocation": {
      "@type": "Place",
      "address": {
        "@type": "PostalAddress",
        "addressCountry": "CA",
        "addressRegion": "Ontario"
      }
    },
    "areaServed": {
      "@type": "Country",
      "name": "Canada"
    },
    "knowsAbout": ["PDRN skincare", "biotech skincare", "visible rejuvenation", "skin resilience", "bio-active ingredients"],
    "contactPoint": {
      "@type": "ContactPoint",
      "email": "support@reroots.ca",
      "contactType": "customer service",
      "availableLanguage": ["English", "French"]
    },
    "sameAs": [
      "https://www.instagram.com/reroots.ca",
      "https://www.tiktok.com/@reroots.ca",
      "https://www.facebook.com/reroots.ca",
      "https://twitter.com/rerootscanada"
    ]
  };

  // Website schema for better Google recognition
  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${baseUrl}/#website`,
    "name": "ReRoots Biotech Skincare Canada",
    "alternateName": "ReRoots PDRN Skincare",
    "url": baseUrl,
    "description": "Canadian biotech skincare brand - High-performance PDRN serums for visible rejuvenation",
    "publisher": {
      "@id": `${baseUrl}/#organization`
    },
    "potentialAction": {
      "@type": "SearchAction",
      "target": {
        "@type": "EntryPoint",
        "urlTemplate": `${baseUrl}/products?search={search_term_string}`
      },
      "query-input": "required name=search_term_string"
    },
    "inLanguage": "en-CA"
  };

  // Brand schema for disambiguation
  const brandSchema = {
    "@context": "https://schema.org",
    "@type": "Brand",
    "@id": `${baseUrl}/#brand`,
    "name": "ReRoots Biotech Skincare",
    "alternateName": "ReRoots Canada Skincare",
    "description": "Canadian biotech skincare brand featuring bio-active PDRN serums - NOT an organic farm or food brand",
    "logo": `${baseUrl}/logo.png`,
    "slogan": "Science-Backed Skincare",
    "url": baseUrl
  };

  // FAQ Schema for ingredient searches - Compliant language
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "What is PDRN serum and how does it help skin?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "PDRN (Polydeoxyribonucleotide) is a bio-active compound derived from salmon DNA. Our dermatologist-recommended formula contains 2% PDRN which may help support skin renewal, promote a more youthful appearance, and assist in maintaining skin vitality. ReRoots AURA-GEN serum is formulated to address multiple skin concerns including dullness, uneven tone, and signs of aging."
        }
      },
      {
        "@type": "Question",
        "name": "What skin concerns can ReRoots products help with?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots biotech skincare is formulated to help address various skin concerns including: dark spots and hyperpigmentation, uneven skin tone, fine lines and wrinkles, dull or tired-looking skin, enlarged pores, acne marks, and loss of skin radiance. Our professional-strength formulas are designed based on dermatological research."
        }
      },
      {
        "@type": "Question",
        "name": "Is PDRN skincare safe for all skin types?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes, ReRoots PDRN skincare is formulated to be suitable for all skin types including sensitive skin. Our products are dermatologist-tested and made in Canada following strict quality standards. However, we always recommend doing a patch test before full application."
        }
      },
      {
        "@type": "Question",
        "name": "What is Tranexamic Acid and why is it in ReRoots serum?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Tranexamic Acid (5% in our formula) is a clinically-studied ingredient known to help target dark spots, melasma, and uneven skin tone. Combined with PDRN, Niacinamide, and other active ingredients, it creates a comprehensive formula that may help improve overall skin clarity and brightness."
        }
      },
      {
        "@type": "Question",
        "name": "Where can I buy PDRN serum in Canada?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots is a Canadian biotech skincare brand offering professional-strength PDRN serums. Shop directly at reroots.ca for authentic products with free shipping on orders over $75. Our AURA-GEN TXA+PDRN Bio-Regenerator is our flagship product featuring 2% PDRN and 5% Tranexamic Acid."
        }
      },
      {
        "@type": "Question",
        "name": "What makes ReRoots different from other skincare brands?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots combines biotech innovation with dermatologist-recommended ingredients. Our formula features professional-strength concentrations (2% PDRN, 5% Tranexamic Acid) that are typically found in clinical settings. Made in Canada, cruelty-free, and designed to help address multiple skin concerns in one comprehensive formula."
        }
      }
    ]
  };

  // ============================================
  // VOICE ASSISTANT OPTIMIZATION SCHEMAS
  // For Alexa, Google Assistant, Siri recognition
  // ============================================

  // Speakable Schema - Tells voice assistants which content to read aloud
  const speakableSchema = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "ReRoots Biotech Skincare Canada",
    "speakable": {
      "@type": "SpeakableSpecification",
      "cssSelector": [".speakable-content", "h1", "h2", ".product-description", ".brand-intro"]
    },
    "url": baseUrl
  };

  // Voice Search Optimized FAQ - Natural conversational questions
  const voiceFaqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "name": "ReRoots Skincare Voice Assistant FAQ",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "Hey, what is ReRoots skincare?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots is a Canadian biotech skincare brand specializing in PDRN serums. They make science-backed skincare products that help with dark spots, wrinkles, and skin rejuvenation. You can shop at reroots.ca."
        }
      },
      {
        "@type": "Question",
        "name": "Where can I buy ReRoots products?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "You can buy ReRoots skincare products directly from their website at reroots.ca. They offer free shipping on orders over $75 in Canada."
        }
      },
      {
        "@type": "Question",
        "name": "What does ReRoots sell?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots sells biotech skincare products including their flagship AURA-GEN serum with PDRN and Tranexamic Acid. Their products help with dark spots, fine lines, and skin rejuvenation."
        }
      },
      {
        "@type": "Question",
        "name": "Is ReRoots a Canadian company?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes, ReRoots is a Canadian biotech skincare brand. Their products are made in Canada and they ship across the country with free shipping over $75."
        }
      },
      {
        "@type": "Question",
        "name": "How much does ReRoots serum cost?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots AURA-GEN serum typically costs around $80 to $120 Canadian dollars. Check their website reroots.ca for current prices and promotions."
        }
      },
      {
        "@type": "Question",
        "name": "Does ReRoots offer free shipping?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes, ReRoots offers free shipping on orders over $75 within Canada. Standard shipping is available for smaller orders."
        }
      },
      {
        "@type": "Question",
        "name": "What is the best serum for dark spots in Canada?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots AURA-GEN serum is a popular choice for dark spots in Canada. It contains 5% Tranexamic Acid and 2% PDRN, both clinically studied for helping with hyperpigmentation and uneven skin tone."
        }
      },
      {
        "@type": "Question",
        "name": "Tell me about ReRoots skincare",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ReRoots is a Canadian biotech skincare brand founded in 2024. They specialize in professional-strength serums containing PDRN, a bio-active compound that helps with skin rejuvenation. Their products are dermatologist-tested and made in Canada."
        }
      }
    ]
  };

  // Local Business Schema - Helps with "near me" searches
  const localBusinessSchema = {
    "@context": "https://schema.org",
    "@type": "OnlineBusiness",
    "name": "ReRoots Biotech Skincare",
    "alternateName": ["ReRoots Canada", "ReRoots Skincare", "ReRoots PDRN"],
    "description": "Canadian biotech skincare brand featuring professional-strength PDRN serums for skin rejuvenation",
    "url": baseUrl,
    "logo": `${baseUrl}/logo.png`,
    "image": `${baseUrl}/og-image.jpg`,
    "priceRange": "$$",
    "currenciesAccepted": "CAD",
    "paymentAccepted": "Credit Card, Debit Card, PayPal",
    "areaServed": {
      "@type": "Country",
      "name": "Canada"
    },
    "address": {
      "@type": "PostalAddress",
      "addressCountry": "CA",
      "addressRegion": "Ontario"
    },
    "contactPoint": {
      "@type": "ContactPoint",
      "contactType": "customer service",
      "email": "support@reroots.ca",
      "availableLanguage": ["English", "French"]
    },
    "sameAs": [
      "https://www.instagram.com/reroots.ca",
      "https://www.tiktok.com/@reroots.ca",
      "https://www.facebook.com/reroots.ca"
    ]
  };

  // Action Schema - For voice commands like "Order from ReRoots"
  const actionSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "ReRoots Biotech Skincare",
    "url": baseUrl,
    "potentialAction": [
      {
        "@type": "SearchAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": `${baseUrl}/products?search={search_term_string}`
        },
        "query-input": "required name=search_term_string"
      },
      {
        "@type": "BuyAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": `${baseUrl}/products`
        },
        "name": "Shop ReRoots Skincare"
      },
      {
        "@type": "OrderAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": `${baseUrl}/cart`
        },
        "name": "Order from ReRoots"
      }
    ]
  };

  // How-To Schema - Voice assistants love step-by-step instructions
  const howToSchema = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    "name": "How to Use ReRoots PDRN Serum",
    "description": "Step-by-step guide for applying ReRoots AURA-GEN serum for best results",
    "totalTime": "PT5M",
    "step": [
      {
        "@type": "HowToStep",
        "position": 1,
        "name": "Cleanse",
        "text": "Start with a clean face. Wash with a gentle cleanser and pat dry."
      },
      {
        "@type": "HowToStep",
        "position": 2,
        "name": "Apply Serum",
        "text": "Apply 2-3 drops of ReRoots AURA-GEN serum to your face and neck."
      },
      {
        "@type": "HowToStep",
        "position": 3,
        "name": "Massage",
        "text": "Gently massage the serum into your skin using upward motions."
      },
      {
        "@type": "HowToStep",
        "position": 4,
        "name": "Wait",
        "text": "Allow the serum to absorb for 1-2 minutes before applying moisturizer."
      },
      {
        "@type": "HowToStep",
        "position": 5,
        "name": "Moisturize",
        "text": "Follow with your favorite moisturizer to lock in the benefits."
      }
    ]
  };
  
  return (
    <Helmet>
      <title>{seoTitle}</title>
      <meta name="description" content={seoDescription} />
      <meta name="keywords" content={seoKeywords} />
      <link rel="canonical" href={seoUrl} />
      
      {/* Brand disambiguation meta */}
      <meta name="author" content={brandConfig.siteName} />
      <meta name="robots" content="index, follow, max-image-preview:large" />
      <meta name="theme-color" content={brandConfig.themeColor} />
      
      {/* Open Graph - Enhanced for social sharing */}
      <meta property="og:type" content={type === "product" ? "product" : "website"} />
      <meta property="og:title" content={seoTitle} />
      <meta property="og:description" content={seoDescription} />
      <meta property="og:image" content={seoImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content={title || brandConfig.siteName} />
      <meta property="og:url" content={seoUrl} />
      <meta property="og:site_name" content={brandConfig.siteName} />
      <meta property="og:locale" content={brandConfig.locale} />
      
      {/* Product specific Open Graph */}
      {product && (
        <>
          <meta property="product:price:amount" content={product.price} />
          <meta property="product:price:currency" content="CAD" />
          <meta property="product:availability" content={product.stock > 0 ? "in stock" : "out of stock"} />
          {product.gtin && <meta property="product:retailer_item_id" content={product.gtin} />}
          {product.rating && <meta property="product:rating" content={product.rating} />}
        </>
      )}
      
      {/* Twitter Card - Large Image for better engagement */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={brandConfig.twitterHandle} />
      <meta name="twitter:creator" content={brandConfig.twitterHandle} />
      <meta name="twitter:title" content={seoTitle} />
      <meta name="twitter:description" content={seoDescription} />
      <meta name="twitter:image" content={seoImage} />
      <meta name="twitter:image:alt" content={title || brandConfig.siteName} />
      
      {/* Product structured data with comprehensive schema */}
      {product && (
        <script type="application/ld+json">
          {JSON.stringify(buildProductSchema(product))}
        </script>
      )}
      
      {/* Organization schema */}
      {!product && (
        <>
        <script type="application/ld+json">
          {JSON.stringify(organizationSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(websiteSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(brandSchema)}
        </script>
        {/* Voice Assistant Optimization Schemas */}
        <script type="application/ld+json">
          {JSON.stringify(speakableSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(voiceFaqSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(localBusinessSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(actionSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(howToSchema)}
        </script>
        <script type="application/ld+json">
          {JSON.stringify(faqSchema)}
        </script>
        </>
      )}
    </Helmet>
  );
};

// PWAInstallBanner - Extracted to /components/PWAInstallBanner.js (lazy-loaded)

function App() {
  // CRITICAL: Check for session_id in URL hash BEFORE routing
  // Emergent OAuth returns: {redirect_url}#session_id=xxx
  if (typeof window !== 'undefined' && window.location.hash?.includes('session_id=')) {
    // Import and render AuthCallback directly to handle the OAuth callback
    const AuthCallbackComponent = require('@/components/pages/LoginPage').AuthCallback;
    return (
      <HelmetProvider>
        <BrowserRouter>
          <Toaster richColors position="top-center" />
          <AuthCallbackComponent />
        </BrowserRouter>
      </HelmetProvider>
    );
  }
  
  return (
    <HelmetProvider>
      <BrandProvider>
      <LazyMotionProvider strict={false}>
        <AuthProvider>
          <WebSocketProvider>
            <CartProvider>
              <CurrencyProvider>
                <WishlistProvider>
                  <SiteContentProvider>
                    <StoreSettingsProvider>
                      <GlobalBackgroundProvider>
                        <TranslationProvider>
                          <TypographyProvider>
                            <BrowserRouter>
                              <ScrollToTop />
                              <GlobalBackgroundWrapper>
                                <Suspense fallback={null}><ReferralStickyBarLazy /></Suspense>
                                <AutoApplyDiscountHandler />
                                <PromoTopBar />
                                <main className="App" role="main">
                                  <NavbarWrapper />
                                  <SideCart />
                                  <Suspense fallback={null}><ExitIntentModalLazy /></Suspense>
                                  <Suspense fallback={null}><SMSCapturePopupLazy /></Suspense>
                                  <Suspense fallback={
                                    <div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]">
                                      <div className="text-center">
                                        <div className="w-12 h-12 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                                        <p className="text-[#5A5A5A] font-luxury">Loading...</p>
                                      </div>
                                    </div>
                                  }>
                                    <Routes>
                                    {/* Legacy Wix URL Redirects - SEO 301 */}
                                    {/* Note: /shop is now active, removed redirect */}
                                    
                                    <Route path="/" element={<HomePage />} />
                                  <Route path="/products" element={<ProductsPage />} />
                                  <Route path="/products/:productId" element={<ProductDetailPage />} />
                                  <Route path="/sets" element={<SkincareSetsPage />} />
                                  <Route path="/bundles" element={<SkincareSetsPage />} />
                                  <Route path="/skincare-sets" element={<SkincareSetsPage />} />
                                  <Route path="/protocols" element={<SkincareSetsPage />} />
                                  <Route path="/cart" element={<CartPage />} />
                                  <Route path="/checkout" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><CheckoutPageLazy /></Suspense>} />
                                  <Route path="/checkout/success" element={<CheckoutSuccessPage />} />
                                  <Route path="/checkout/cancel" element={<CartPage />} />
                                  <Route path="/track" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><TrackOrderPage /></Suspense>} />
                                  <Route path="/claim-gift/:token" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><GiftClaimPage /></Suspense>} />
                                  <Route path="/review/:token" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><ReviewPageLazy /></Suspense>} />
                                  <Route path="/login" element={<LoginPage />} />
                                  <Route path="/auth/callback" element={<AuthCallback />} />
                                  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                                  <Route path="/reset-password" element={<ResetPasswordPage />} />
                                  <Route path="/account" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><AccountPageLazy /></Suspense>} />
                                  <Route path="/wishlist" element={<WishlistPage />} />
                                  <Route path="/about" element={<AboutPage />} />
                                  <Route path="/science" element={<SciencePage />} />
                                  <Route path="/science-of-pdrn" element={<Navigate to="/science" replace />} />
                                  <Route path="/waitlist" element={<WaitlistPage />} />
                                  <Route path="/founding-member" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><FoundingMemberPage /></Suspense>} />
                                  <Route path="/founding-circle" element={<Navigate to="/founding-member" replace />} />
                                  <Route path="/mission-control" element={<MissionControlPage />} />
                                  <Route path="/Bio-Age-Repair-Scan" element={<BioAgeScanPage />} />
                                  <Route path="/bio-age-scan" element={<Navigate to="/Bio-Age-Repair-Scan" replace />} />
                                  <Route path="/bio-age" element={<Navigate to="/Bio-Age-Repair-Scan" replace />} />
                                  <Route path="/skin-scan" element={<Navigate to="/Bio-Age-Repair-Scan" replace />} />
                                  <Route path="/contact" element={<ContactPage />} />
                                  {/* Blog Routes */}
                                  <Route path="/blog" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><BlogListPage /></Suspense>} />
                                  <Route path="/blog/:slug" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><BlogPostPage /></Suspense>} />
                                  <Route path="/shipping" element={<Navigate to="/shipping-policy" replace />} />
                                  <Route path="/shipping-policy" element={<GlobalShippingPolicyPage />} />
                                  <Route path="/return-policy" element={<ReturnPolicyPage />} />
                                  <Route path="/returns" element={<Navigate to="/return-policy" replace />} />
                                  {/* Privacy & Terms */}
                                  <Route path="/privacy" element={<PrivacyPolicyPage />} />
                                  <Route path="/privacy-policy" element={<Navigate to="/privacy" replace />} />
                                  <Route path="/terms" element={<TermsOfServicePage />} />
                                  <Route path="/terms-of-service" element={<Navigate to="/terms" replace />} />
                                  <Route path="/sitemap" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><SitemapPage /></Suspense>} />
                                  <Route path="/faq" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><FAQPage /></Suspense>} />
                                  <Route path="/frequently-asked-questions" element={<Navigate to="/faq" replace />} />
                                  <Route path="/pdrn-comparison-guide" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><PDRNComparisonPage /></Suspense>} />
                                  <Route path="/compare-pdrn" element={<Navigate to="/pdrn-comparison-guide" replace />} />
                                  <Route path="/science-glossary" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><ScienceGlossaryPage /></Suspense>} />
                                  <Route path="/glossary" element={<Navigate to="/science-glossary" replace />} />
                                  <Route path="/partner-dashboard" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><PartnerDashboard /></Suspense>} />
                                  <Route path="/partner-portal" element={<Navigate to="/partner-dashboard" replace />} />
                                  {/* Partner/Influencer Program */}
                                  <Route path="/apply-partner" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><ApplyPartnerPage /></Suspense>} />
                                  <Route path="/become-partner" element={<BecomePartnerPage />} />
                                  <Route path="/partner-program" element={<Navigate to="/become-partner" replace />} />
                                  <Route path="/influencer" element={<InfluencerLandingPage />} />
                                  <Route path="/influancer" element={<Navigate to="/influencer" replace />} />
                                  <Route path="/partner-login" element={<InfluencerPortalPage />} />
                                  <Route path="/influencer-login" element={<Navigate to="/partner-login" replace />} />
                                  <Route path="/partner/:partnerCode" element={<PartnerLandingPage />} />
                                  <Route path="/ref/:partnerCode" element={<PartnerLandingPage />} />
                                  <Route path="/qr-generator" element={<QRGeneratorPage />} />
                                  <Route path="/qr" element={<Navigate to="/qr-generator" replace />} />
                                  <Route path="/qrcode" element={<Navigate to="/qr-generator" replace />} />
                                  {/* AURA-GEN Molecular Auditor */}
                                  <Route path="/molecular-auditor" element={<MolecularAuditorPage />} />
                                  <Route path="/compare" element={<Navigate to="/molecular-auditor" replace />} />
                                  <Route path="/auditor" element={<Navigate to="/molecular-auditor" replace />} />
                                  {/* Brand Showcase - Hidden until other brands launch */}
                                  <Route path="/brands" element={<Navigate to="/" replace />} />
                                  <Route path="/showcase" element={<Navigate to="/" replace />} />
                                  {/* OROÉ Luxury Brand Routes - Hidden until launch (redirect to homepage) */}
                                  <Route path="/oroe" element={<Navigate to="/" replace />} />
                                  <Route path="/oroe-new" element={<OroeNewLanding />} />
                                  <Route path="/oroe/ritual" element={<Navigate to="/" replace />} />
                                  <Route path="/oroe/science" element={<Navigate to="/" replace />} />
                                  <Route path="/ritual" element={<Navigate to="/" replace />} />
                                  {/* LA VELA BIANCA - Teen Skincare Brand (Active) */}
                                  <Route path="/lavela" element={<LaVelaLandingPage />} />
                                  <Route path="/la-vela-bianca" element={<LaVelaLandingPage />} />
                                  <Route path="/la-vela-bianca/*" element={<LaVelaLandingPage />} />
                                  <Route path="/lavela/auth" element={<LaVelaAuthPage />} />
                                  <Route path="/lavela/oro-rosa" element={<OroRosaPage />} />
                                  <Route path="/lavela/lab" element={<TheLabPage />} />
                                  <Route path="/lavela/founder" element={<FounderPage />} />
                                  <Route path="/lavela/glow-club" element={<GlowClubPage />} />
                                  {/* ReRoots AI Luxury PWA */}
                                  <Route path="/pwa" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><PWAAppLazy /></Suspense>} />
                                  <Route path="/pwa/*" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><PWAAppLazy /></Suspense>} />
                                  <Route path="/admin" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]"><Loader2 className="h-10 w-10 animate-spin text-[#F8A5B8]" /><span className="ml-3 text-lg text-[#2D2A2E]">Loading Admin...</span></div>}><AdminLayoutLazy /></Suspense>} />
                                  <Route path="/admin-old" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]"><Loader2 className="h-10 w-10 animate-spin text-[#F8A5B8]" /><span className="ml-3 text-lg text-[#2D2A2E]">Loading Admin...</span></div>}><AdminDashboardLazy /></Suspense>} />
                                  <Route path="/admin-v2" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]"><Loader2 className="h-10 w-10 animate-spin text-[#F8A5B8]" /><span className="ml-3 text-lg text-[#2D2A2E]">Loading Admin...</span></div>}><AdminLayoutLazy /></Suspense>} />
                                  {/* Commercial Dashboard - API Management */}
                                  <Route path="/commercial-dashboard" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><CommercialDashboard /></Suspense>} />
                                  <Route path="/api-dashboard" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><CommercialDashboard /></Suspense>} />
                                  {/* Owner Panel - Platform Control */}
                                  <Route path="/owner-panel" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><OwnerPanel /></Suspense>} />
                                  <Route path="/owner" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><OwnerPanel /></Suspense>} />
                                  {/* Subscription Plans */}
                                  <Route path="/pricing" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><SubscriptionPlans /></Suspense>} />
                                  <Route path="/subscribe" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><SubscriptionPlans /></Suspense>} />
                                  {/* Orchestrator Command Center */}
                                  <Route path="/orchestrator" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><OrchestratorCommandCenter /></Suspense>} />
                                  <Route path="/command-center" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><OrchestratorCommandCenter /></Suspense>} />
                                  <Route path="/brain" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><OrchestratorCommandCenter /></Suspense>} />
                                  {/* AI Platform (Commercial Product) */}
                                  <Route path="/platform" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-950"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><PlatformLanding /></Suspense>} />
                                  {/* AUREM Landing - Public */}
                                  <Route path="/aurem" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-[#c9a84c]" /></div>}><AuremLanding /></Suspense>} />
                                  <Route path="/aurem-landing" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-[#c9a84c]" /></div>}><AuremLanding /></Suspense>} />
                                  {/* AUREM AI - Protected (Admin Only) */}
                                  <Route path="/aurem-ai" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-[#c9a84c]" /></div>}><AuremProtectedRoute><AuremAI /></AuremProtectedRoute></Suspense>} />
                                  <Route path="/aurem-onboarding" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-[#c9a84c]" /></div>}><AuremProtectedRoute><AuremOnboarding /></AuremProtectedRoute></Suspense>} />
                                  <Route path="/z-image" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-[#c9a84c]" /></div>}><AuremProtectedRoute><ZImageStudio apiBase={process.env.REACT_APP_BACKEND_URL || ''} /></AuremProtectedRoute></Suspense>} />
                                  <Route path="/platform/login" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-950"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><PlatformLogin /></Suspense>} />
                                  <Route path="/platform/signup" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-950"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><PlatformSignup /></Suspense>} />
                                  <Route path="/platform/dashboard" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-950"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><PlatformDashboard /></Suspense>} />
                                  <Route path="/platform/dashboard/*" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-950"><Loader2 className="h-10 w-10 animate-spin text-purple-500" /></div>}><PlatformDashboard /></Suspense>} />
                                  {/* Easy Access Routes */}
                                  <Route path="/reroots-admin" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><AdminPortal /></Suspense>} />
                                  <Route path="/admin-portal" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><AdminPortal /></Suspense>} />
                                  <Route path="/manage" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" /></div>}><AdminPortal /></Suspense>} />
                                  <Route path="/shop" element={<ProductsPage />} />
                                  <Route path="/shop/:concern" element={<ProductsPage />} />
                                  <Route path="/concern/:concern" element={<ProductsPage />} />
                                  <Route path="/skin-quiz" element={<SkinQuizPage />} />
                                  <Route path="/quiz" element={<SkinQuizPage />} />
                                  <Route path="/find-your-ritual" element={<FindYourRitualPage />} />
                                  <Route path="/links" element={<LinksPage />} />
                                  <Route path="/family-skin-protocol" element={<FamilySkinProtocolPage />} />
                                  <Route path="/protocol" element={<ProtocolPage />} />
                                  <Route path="/aura-gen-protocol" element={<AuraGenProtocolPage />} />
                                  <Route path="/combo-protocol" element={<AuraGenProtocolPage />} />
                                  <Route path="/aura-gen-serum-protocol" element={<AuraGenSerumProtocolPage />} />
                                  <Route path="/serum-protocol" element={<AuraGenSerumProtocolPage />} />
                                  <Route path="/aura-gen-cream-protocol" element={<AuraGenCreamProtocolPage />} />
                                  <Route path="/cream-protocol" element={<AuraGenCreamProtocolPage />} />
                                  <Route path="/welcome" element={<ProtocolPage />} />
                                  <Route path="/skincare-dictionary" element={<SkincareDictionaryPage />} />
                                  <Route path="/library" element={<SkincareDictionaryPage />} />
                                  <Route path="/ingredients" element={<SkincareDictionaryPage />} />
                                  <Route path="/store" element={<ProductsPage />} />
                                  {/* V12 PWA Mobile Experience */}
                                  <Route path="/app" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]"><Loader2 className="h-10 w-10 animate-spin text-amber-500" /></div>}><PWAAppLazy /></Suspense>} />
                                  {/* CustomerApp Dark Store (legacy) */}
                                  <Route path="/dark-store" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#060608]"><div className="animate-spin h-8 w-8 border-2 border-[#C9A86E] border-t-transparent rounded-full" /></div>}><CustomerAppLazy /></Suspense>} />
                                  {/* New Admin Panel */}
                                  <Route path="/new-admin" element={<Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#050507]"><div className="animate-spin h-8 w-8 border-2 border-[#C9A86E] border-t-transparent rounded-full" /></div>}><AdminPanelLazy /></Suspense>} />
                                </Routes>
                              </Suspense>
                              <FooterWrapper />
                              <LiveChatWidgetWrapper />
                              <ReferralWidgetWrapper />
                              <RerootsChatWrapper />
                              <Suspense fallback={null}><PWAInstallBannerLazy /></Suspense>
                              <Toaster position="top-center" richColors />
                            </main>
                          </GlobalBackgroundWrapper>
                        </BrowserRouter>
                      </TypographyProvider>
                    </TranslationProvider>
                  </GlobalBackgroundProvider>
                </StoreSettingsProvider>
              </SiteContentProvider>
            </WishlistProvider>
          </CurrencyProvider>
        </CartProvider>
        </WebSocketProvider>
      </AuthProvider>
      </LazyMotionProvider>
      </BrandProvider>
    </HelmetProvider>
  );
}

export default App;
