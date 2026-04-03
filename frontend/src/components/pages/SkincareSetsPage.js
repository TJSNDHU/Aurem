import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Sparkles, Package, Star, ShoppingBag, 
  ChevronRight, Loader2, Clock, Target, CheckCircle2, Zap,
  AlertTriangle, Sun, Shield, Droplets, Activity, TrendingUp,
  Play, Pause, RotateCcw, Share2, Copy, Check, MessageCircle, Facebook, Twitter, Mail,
  X, ArrowLeft
} from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { useCart } from '@/contexts';

// Dynamic API URL for custom domains
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const API = getBackendUrl() + '/api';

// Interactive 60-Second Countdown Timer Component
const CountdownTimer = ({ onComplete }) => {
  const [timeLeft, setTimeLeft] = useState(60);
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    let interval;
    if (isRunning && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            setIsRunning(false);
            setIsComplete(true);
            onComplete?.();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isRunning, timeLeft, onComplete]);

  const handleStart = () => {
    setIsRunning(true);
    setIsComplete(false);
  };

  const handlePause = () => setIsRunning(false);
  
  const handleReset = () => {
    setTimeLeft(60);
    setIsRunning(false);
    setIsComplete(false);
  };

  const progress = ((60 - timeLeft) / 60) * 100;

  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-4 border-2 border-amber-300">
      <div className="flex items-center gap-4">
        {/* Circular Progress Timer */}
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg className="w-20 h-20 transform -rotate-90">
            <circle
              cx="40"
              cy="40"
              r="36"
              stroke="#FED7AA"
              strokeWidth="6"
              fill="none"
            />
            <circle
              cx="40"
              cy="40"
              r="36"
              stroke={isComplete ? "#22C55E" : "#F59E0B"}
              strokeWidth="6"
              fill="none"
              strokeDasharray={`${2 * Math.PI * 36}`}
              strokeDashoffset={`${2 * Math.PI * 36 * (1 - progress / 100)}`}
              strokeLinecap="round"
              className="transition-all duration-1000"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-2xl font-bold ${isComplete ? 'text-green-600' : 'text-amber-700'}`}>
              {timeLeft}
            </span>
          </div>
        </div>

        <div className="flex-1">
          <h4 className="font-bold text-amber-800 mb-1">
            {isComplete ? '✓ Ready for Step 2!' : 'DMI Molecular Taxi Timer'}
          </h4>
          <p className="text-sm text-amber-700 mb-2">
            {isComplete 
              ? 'Apply Step 2 (Buffer) now while skin is still slightly damp.'
              : 'Wait 60 seconds for the actives to penetrate before Step 2.'
            }
          </p>
          
          {/* Control Buttons */}
          <div className="flex gap-2">
            {!isRunning && !isComplete && (
              <Button 
                size="sm" 
                onClick={handleStart}
                className="bg-amber-500 hover:bg-amber-600 text-white"
                data-testid="timer-start-btn"
              >
                <Play className="h-3 w-3 mr-1" />
                Start Timer
              </Button>
            )}
            {isRunning && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={handlePause}
                className="border-amber-500 text-amber-700"
              >
                <Pause className="h-3 w-3 mr-1" />
                Pause
              </Button>
            )}
            {(isComplete || timeLeft < 60) && (
              <Button 
                size="sm" 
                variant="ghost"
                onClick={handleReset}
                className="text-amber-600"
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                Reset
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Combo Share Modal Component
const ComboShareModal = ({ combo, isOpen, onClose }) => {
  const [copied, setCopied] = useState(false);
  
  if (!combo) return null;
  
  const comboUrl = `${window.location.origin}/sets?combo=${combo.id}`;
  const shareTitle = combo.name;
  const shareDescription = combo.tagline || combo.description || `Save ${Number(combo.discount_percent).toFixed(2)}% on this clinical skincare set from ReRoots!`;
  const comboImage = combo.products?.[0]?.images?.[0] || combo.products?.[0]?.image || '';
  
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(comboUrl);
      setCopied(true);
      toast.success("Link copied!");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error("Failed to copy link");
    }
  };
  
  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: shareTitle,
          text: shareDescription,
          url: comboUrl
        });
      } catch (err) {
        if (err.name !== 'AbortError') {
          toast.error("Share failed");
        }
      }
    }
  };
  
  const shareLinks = [
    {
      name: "WhatsApp",
      icon: MessageCircle,
      color: "bg-green-500 hover:bg-green-600",
      url: `https://wa.me/?text=${encodeURIComponent(`${shareTitle} - ${shareDescription}\n${comboUrl}`)}`
    },
    {
      name: "Facebook",
      icon: Facebook,
      color: "bg-blue-600 hover:bg-blue-700",
      url: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(comboUrl)}&quote=${encodeURIComponent(shareTitle)}`
    },
    {
      name: "Twitter",
      icon: Twitter,
      color: "bg-sky-500 hover:bg-sky-600",
      url: `https://twitter.com/intent/tweet?text=${encodeURIComponent(`Check out this skincare set from ReRoots! Save ${Number(combo.discount_percent).toFixed(2)}%`)}&url=${encodeURIComponent(comboUrl)}`
    },
    {
      name: "Pinterest",
      icon: () => (
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.781c0-1.663.967-2.911 2.168-2.911 1.024 0 1.518.769 1.518 1.688 0 1.029-.653 2.567-.992 3.992-.285 1.193.6 2.165 1.775 2.165 2.128 0 3.768-2.245 3.768-5.487 0-2.861-2.063-4.869-5.008-4.869-3.41 0-5.409 2.562-5.409 5.199 0 1.033.394 2.143.889 2.741.099.12.112.225.085.345-.09.375-.293 1.199-.334 1.363-.053.225-.172.271-.401.165-1.495-.69-2.433-2.878-2.433-4.646 0-3.776 2.748-7.252 7.92-7.252 4.158 0 7.392 2.967 7.392 6.923 0 4.135-2.607 7.462-6.233 7.462-1.214 0-2.354-.629-2.758-1.379l-.749 2.848c-.269 1.045-1.004 2.352-1.498 3.146 1.123.345 2.306.535 3.55.535 6.607 0 11.985-5.365 11.985-11.987C23.97 5.39 18.592.026 11.985.026L12.017 0z"/>
        </svg>
      ),
      color: "bg-red-600 hover:bg-red-700",
      url: `https://pinterest.com/pin/create/button/?url=${encodeURIComponent(comboUrl)}&media=${encodeURIComponent(comboImage)}&description=${encodeURIComponent(shareTitle)}`
    },
    {
      name: "Email",
      icon: Mail,
      color: "bg-gray-600 hover:bg-gray-700",
      url: `mailto:?subject=${encodeURIComponent(`Check out: ${shareTitle}`)}&body=${encodeURIComponent(`Hi!\n\nI thought you might like this skincare set from ReRoots:\n\n${shareTitle}\n${shareDescription}\n\nView it here: ${comboUrl}\n\nBest regards`)}`
    }
  ];
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto mx-4 rounded-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-base">
            <Share2 className="h-4 w-4 text-purple-500" />
            Share This Set
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg">
            {comboImage && (
              <img 
                src={comboImage} 
                alt={shareTitle}
                className="w-14 h-14 object-cover rounded-lg shrink-0"
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900 text-sm line-clamp-1">{shareTitle}</p>
              <p className="text-xs text-gray-600 line-clamp-1">{shareDescription}</p>
              <Badge className="mt-1 bg-purple-100 text-purple-700 text-xs">
                Save {Number(combo.discount_percent).toFixed(2)}%
              </Badge>
            </div>
          </div>
          
          <div className="flex gap-2">
            <Input 
              value={comboUrl} 
              readOnly 
              className="flex-1 text-xs bg-gray-50 h-9"
            />
            <Button 
              onClick={handleCopyLink}
              variant="outline"
              size="sm"
              className="shrink-0 h-9 px-3"
              data-testid="copy-combo-link"
            >
              {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
          
          {typeof navigator !== 'undefined' && navigator.share && (
            <Button 
              onClick={handleNativeShare}
              className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white h-10"
              data-testid="native-share-combo-btn"
            >
              <Share2 className="h-4 w-4 mr-2" />
              Share via...
            </Button>
          )}
          
          <div className="grid grid-cols-5 gap-2">
            {shareLinks.map((link) => {
              const Icon = link.icon;
              return (
                <a
                  key={link.name}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${link.color} text-white p-2.5 rounded-lg flex items-center justify-center transition-colors`}
                  title={`Share on ${link.name}`}
                  data-testid={`share-combo-${link.name.toLowerCase()}`}
                >
                  <Icon className="h-4 w-4" />
                </a>
              );
            })}
          </div>
          
          <p className="text-xs text-center text-gray-500">
            Share this clinical set with friends and family!
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};


// Synergy Performance Index Data
const SYNERGY_DATA = {
  concerns: [
    {
      id: 'melasma',
      name: 'Melasma',
      icon: '🎯',
      actives: 'Tranexamic Acid + Alpha Arbutin + HPR',
      speedAdvantage: '+55% Faster',
      result: 'Breaks down deep pigment clusters 2x faster than single acids.',
      acceleratorRole: '5% Mandelic Acid and 2% Alpha Arbutin act as the "scouts," finding and lifting surface pigment.',
      recoveryRole: '5% Tranexamic Acid and Niacinamide act as the "guardians," preventing new pigment from forming in the deeper layers.',
      comboResult: 'Clears visible melasma patches 2x faster by attacking the issue from both the top and bottom of the skin.',
      color: 'purple'
    },
    {
      id: 'hyperpigmentation',
      name: 'Hyperpigmentation',
      icon: '✨',
      actives: 'Mandelic Acid + Niacinamide + Vitamin B12',
      speedAdvantage: '+60% Faster',
      result: 'Immediate surface exfoliation paired with deep pigment blockade.',
      acceleratorRole: 'Mandelic Acid gently dissolves the "glue" between dead, pigmented cells on the surface.',
      recoveryRole: 'Niacinamide stops the melanocyte cells from overproducing new pigment at the source.',
      comboResult: 'Visible dark spots fade within 2-3 weeks instead of 6-8 weeks with single products.',
      color: 'amber'
    },
    {
      id: 'acne',
      name: 'Acne & Pimples',
      icon: '💧',
      actives: 'Mandelic Acid + PDRN + Panthenol',
      speedAdvantage: '+45% Faster',
      result: 'Mandelic clears pores while PDRN heals active lesions overnight.',
      acceleratorRole: 'Antibacterial Mandelic Acid kills P.acnes bacteria and flushes out the pore.',
      recoveryRole: 'PDRN and Ceramides rapidly repair the "skin crater" left by the blemish to prevent permanent scarring.',
      comboResult: 'Reduces recovery time of active breakouts to under 48 hours.',
      color: 'blue'
    },
    {
      id: 'fine-lines',
      name: 'Fine Lines',
      icon: '🌟',
      actives: 'Matrixyl 3000 + Argireline (10%)',
      speedAdvantage: '+50% Faster',
      result: 'Double-peptide action: one fills volume, the other relaxes expression lines.',
      acceleratorRole: 'Argireline (10%) relaxes facial micro-muscles, preventing new lines from forming.',
      recoveryRole: 'Matrixyl 3000 stimulates collagen production to "fill" existing wrinkles from below.',
      comboResult: 'Expression lines visibly soften within 2 weeks; deeper wrinkles improve by week 6.',
      color: 'pink'
    },
    {
      id: 'aging',
      name: 'Aging / Sagging',
      icon: '🔬',
      actives: 'HPR + Bakuchiol + PDRN',
      speedAdvantage: '+40% Faster',
      result: 'Accelerated cellular DNA repair and increased collagen density.',
      acceleratorRole: 'HPR Retinoid accelerates cellular turnover and triggers DNA repair mechanisms.',
      recoveryRole: 'PDRN (Salmon DNA) floods cells with the building blocks for new collagen synthesis.',
      comboResult: 'Skin density and firmness improve measurably within 8 weeks.',
      color: 'emerald'
    }
  ]
};

// Safety information for high-intensity actives
const SAFETY_INFO = {
  phLevel: {
    title: 'pH 4.0 – 4.2 Formulation',
    warning: 'High-intensity acid formulation',
    soothingAgent: 'Panthenol (2%) in Recovery Serum acts as mandatory soothing agent to prevent irritation'
  },
  requirements: [
    { icon: Sun, text: 'SPF 30+ mandatory during daytime use', critical: true },
    { icon: Clock, text: 'Best applied in PM routine for optimal absorption', critical: false },
    { icon: Droplets, text: 'Wait 60-90 seconds between Step 1 and Step 2', critical: false },
    { icon: Shield, text: 'Patch test recommended for sensitive skin', critical: true }
  ],
  faq: [
    {
      question: 'Is 55% total active concentration safe for daily use?',
      answer: 'Yes, but only when used as a system. The Accelerator (17.35%) is the "Engine" that resurfaces, while the Recovery Serum (37.67%) is the "Buffer." The Recovery Serum is specifically formulated with Panthenol (2%), Ceramides, and Vitamin B12 to instantly neutralize the potential irritation from the Accelerator\'s acids. We recommend starting 3 nights a week and moving to nightly as tolerated.'
    },
    {
      question: 'Will I experience "Purging" or breakouts initially?',
      answer: 'Because the Accelerator contains Mandelic Acid and HPR Retinoid, you are accelerating cellular turnover. This may push existing congestion to the surface. However, the PDRN and Tranexamic Acid in the Recovery Serum are designed to heal these spots 45% faster than standard treatments, typically resolving the "purge" phase within 7–10 days.'
    },
    {
      question: 'Can this combo cause Melasma to rebound or darken?',
      answer: 'No. Melasma often rebounds when skin is overheated or over-irritated. Our protocol prevents this by pairing resurfacing with 5% Tranexamic Acid and Dipotassium Glycyrrhizate, which soothe the melanocytes (pigment-producing cells) while they are being treated. Note: Daily SPF 30+ is mandatory to protect these results.'
    },
    {
      question: 'Why is there a "Wait Time" between Step 1 and Step 2?',
      answer: 'The Accelerator uses high-performance penetrants (DMI & Ethoxydiglycol). Waiting 60–90 seconds allows these "molecular taxis" to pull the Mandelic Acid and Retinoid into the deeper layers. Once absorbed, the Recovery Serum can then seal the surface and deliver its DNA-repairing PDRN and Argireline without dilution.'
    },
    {
      question: 'Can I use this with other Vitamin C or Acid serums?',
      answer: 'We do not recommend mixing this combo with other high-percentage acids or L-Ascorbic Acid in the same evening. The 55% total active load is already a complete clinical treatment. Use your Vitamin C in the morning and the Resurface & Rebuild Duo in the evening.'
    }
  ]
};

const SkincareSetsPage = () => {
  const navigate = useNavigate();
  const { addComboToCart } = useCart();
  const [combos, setCombos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCombo, setSelectedCombo] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline');
  const [selectedConcern, setSelectedConcern] = useState(null);
  const [showShareModal, setShowShareModal] = useState(false);
  const [addingToCart, setAddingToCart] = useState(false);
  const [selectedProducts, setSelectedProducts] = useState(new Set()); // Track selected products for combo
  const [stockInfo, setStockInfo] = useState({}); // Track stock info after adding to cart

  useEffect(() => {
    fetchCombos();
  }, []);
  
  // Check for combo ID in URL params to auto-load
  const [searchParams] = useSearchParams();
  const comboIdFromUrl = searchParams.get('combo');
  
  useEffect(() => {
    if (comboIdFromUrl && combos.length > 0) {
      fetchComboDetails(comboIdFromUrl);
    }
  }, [comboIdFromUrl, combos]);

  const fetchCombos = async () => {
    try {
      const res = await axios.get(`${API}/combo-offers`);
      setCombos(res.data || []);
    } catch (err) {
      console.error('Failed to fetch combos:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchComboDetails = async (comboId) => {
    try {
      const res = await axios.get(`${API}/combo-offers/${comboId}`);
      setSelectedCombo(res.data);
      setActiveTab('timeline');
      // Auto-select all products when combo is loaded
      if (res.data?.products) {
        setSelectedProducts(new Set(res.data.products.map(p => p.id)));
      }
    } catch (err) {
      console.error('Failed to fetch combo details:', err);
    }
  };
  
  // Toggle product selection in combo
  const toggleProductSelection = (productId) => {
    setSelectedProducts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(productId)) {
        newSet.delete(productId);
      } else {
        newSet.add(productId);
      }
      return newSet;
    });
  };
  
  // Check if at least one product is selected (user can add partial combo)
  const hasProductsSelected = selectedProducts.size > 0;
  
  // Check if all products are selected (for full combo)
  const allProductsSelected = selectedCombo?.products?.length > 0 && 
    selectedCombo.products.every(p => selectedProducts.has(p.id));

  // Fetch stock info for combo products
  const fetchStockInfo = async (products) => {
    const stockData = {};
    for (const product of products) {
      try {
        const res = await axios.get(`${API}/products/${product.id}`);
        stockData[product.id] = {
          stock: res.data?.stock || res.data?.inventory_count || 0,
          name: product.name
        };
      } catch (err) {
        console.error(`Failed to fetch stock for ${product.id}:`, err);
        stockData[product.id] = { stock: 'Unknown', name: product.name };
      }
    }
    return stockData;
  };

  const handleAddComboToCart = async () => {
    console.log('[Combo Cart] Starting add to cart...');
    console.log('[Combo Cart] selectedCombo:', selectedCombo);
    console.log('[Combo Cart] selectedCombo.id:', selectedCombo?.id);
    
    if (!selectedCombo?.id) {
      console.error('[Combo Cart] No combo selected or combo has no id:', selectedCombo);
      toast.error('Unable to add to cart. Please try again.');
      return;
    }
    
    if (!hasProductsSelected) {
      console.error('[Combo Cart] No products selected');
      toast.error('Please select at least one product from the combo.');
      return;
    }
    
    setAddingToCart(true);
    try {
      console.log('[Combo Cart] Calling addComboToCart with id:', selectedCombo.id);
      await addComboToCart(selectedCombo.id, 1);
      
      // Fetch stock info after successful add
      if (selectedCombo.products?.length > 0) {
        const stockData = await fetchStockInfo(selectedCombo.products);
        setStockInfo(stockData);
        
        // Show stock info in toast
        const lowStockItems = Object.values(stockData).filter(s => typeof s.stock === 'number' && s.stock < 20);
        if (lowStockItems.length > 0) {
          const stockMsg = lowStockItems.map(s => `${s.name}: Only ${s.stock} left!`).join(' ');
          toast.info(stockMsg, { duration: 5000 });
        }
      }
      
      toast.success(`${selectedCombo.name} added to cart! You saved ${Number(selectedCombo.discount_percent).toFixed(2)}%`);
    } catch (error) {
      console.error('[Combo Cart] Failed to add combo to cart:', error);
      console.error('[Combo Cart] Error response:', error?.response?.data);
      console.error('[Combo Cart] Combo ID was:', selectedCombo.id);
      toast.error('Failed to add set to cart. Please try again.');
    } finally {
      setAddingToCart(false);
    }
  };
  
  // Generate meta tags based on selected combo or default
  const pageTitle = selectedCombo 
    ? `${selectedCombo.name} - Save ${Number(selectedCombo.discount_percent).toFixed(2)}% | ReRoots Biotech Skincare`
    : "Clinical Skincare Sets & Bundles | ReRoots Biotech Skincare";
  
  const pageDescription = selectedCombo
    ? `${selectedCombo.tagline || selectedCombo.description} Save ${Number(selectedCombo.discount_percent).toFixed(2)}% with this clinical skincare protocol. Made in Canada with PDRN biotech.`
    : "Curated clinical skincare protocols designed for maximum results. AI-powered routines with biotech PDRN formulations. Made in Canada.";
  
  const pageImage = selectedCombo?.products?.[0]?.images?.[0] 
    || selectedCombo?.products?.[0]?.image 
    || "https://reroots.ca/og-image.jpg";

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-purple-50 via-white to-pink-50 pt-20">
      {/* SEO Meta Tags */}
      <Helmet>
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
        
        {/* Open Graph / Facebook */}
        <meta property="og:type" content="product" />
        <meta property="og:site_name" content="ReRoots Biotech Skincare" />
        <meta property="og:title" content={pageTitle} />
        <meta property="og:description" content={pageDescription} />
        <meta property="og:image" content={pageImage} />
        <meta property="og:url" content={window.location.href} />
        
        {/* Twitter */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={pageTitle} />
        <meta name="twitter:description" content={pageDescription} />
        <meta name="twitter:image" content={pageImage} />
        
        {/* Additional SEO */}
        <meta name="keywords" content="PDRN skincare, biotech skincare, clinical skincare, skincare sets, anti-aging, pigmentation, ReRoots, Canadian skincare" />
        <meta name="author" content="ReRoots Biotech Skincare" />
        <link rel="canonical" href={window.location.href} />
      </Helmet>
      
      {/* Hero Section */}
      <div className="bg-gradient-to-r from-purple-600 via-pink-500 to-rose-400 text-white py-16">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <Badge className="bg-white/20 text-white mb-4">
            <Sparkles className="h-3 w-3 mr-1" /> AI-Powered Skincare Routines
          </Badge>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Skincare Sets & Bundles
          </h1>
          <p className="text-lg text-purple-100 max-w-2xl mx-auto">
            Curated product combinations designed for maximum results. See exactly what each routine will do for your skin.
          </p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-12">
        {/* Synergy Performance Index Table */}
        <div className="mb-12">
          <div className="text-center mb-8">
            <Badge className="bg-purple-100 text-purple-700 mb-3">
              <TrendingUp className="h-3 w-3 mr-1" /> Clinical Performance Data
            </Badge>
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
              The Synergy Performance Index
            </h2>
            <p className="text-gray-600 max-w-2xl mx-auto">
              See how much faster you'll achieve results with our clinical combo protocol vs. individual products
            </p>
          </div>

          {/* Performance Table - Desktop */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full border-collapse bg-white rounded-xl shadow-lg overflow-hidden">
              <thead>
                <tr className="bg-gradient-to-r from-purple-600 to-pink-500 text-white">
                  <th className="px-6 py-4 text-left font-semibold">Skin Concern</th>
                  <th className="px-6 py-4 text-left font-semibold">Key Actives Involved</th>
                  <th className="px-6 py-4 text-center font-semibold">Speed Advantage</th>
                  <th className="px-6 py-4 text-left font-semibold">Results vs. Individual Use</th>
                </tr>
              </thead>
              <tbody>
                {SYNERGY_DATA.concerns.map((concern, idx) => (
                  <tr 
                    key={concern.id}
                    className={`border-b border-gray-100 hover:bg-purple-50 cursor-pointer transition-colors ${
                      selectedConcern?.id === concern.id ? 'bg-purple-50' : ''
                    }`}
                    onClick={() => setSelectedConcern(selectedConcern?.id === concern.id ? null : concern)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{concern.icon}</span>
                        <span className="font-medium text-gray-900">{concern.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{concern.actives}</td>
                    <td className="px-6 py-4 text-center">
                      <Badge className={`bg-${concern.color}-100 text-${concern.color}-700 font-bold`}>
                        {concern.speedAdvantage}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">{concern.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Performance Cards - Mobile */}
          <div className="md:hidden space-y-3">
            {SYNERGY_DATA.concerns.map((concern) => (
              <Card 
                key={concern.id}
                className={`cursor-pointer transition-all ${
                  selectedConcern?.id === concern.id ? 'ring-2 ring-purple-500 bg-purple-50' : ''
                }`}
                onClick={() => setSelectedConcern(selectedConcern?.id === concern.id ? null : concern)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{concern.icon}</span>
                      <span className="font-semibold text-gray-900">{concern.name}</span>
                    </div>
                    <Badge className="bg-purple-100 text-purple-700 font-bold text-xs">
                      {concern.speedAdvantage}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mb-1">{concern.actives}</p>
                  <p className="text-sm text-gray-700">{concern.result}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Expanded Concern Detail */}
          {selectedConcern && (
            <div className="mt-6 p-6 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border-2 border-purple-200 animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-2xl">{selectedConcern.icon}</span>
                <h3 className="text-xl font-bold text-purple-800">
                  Target: {selectedConcern.name}
                </h3>
              </div>
              
              <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div className="p-4 bg-white rounded-lg border border-purple-200">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded-full bg-purple-500 text-white flex items-center justify-center text-xs font-bold">1</div>
                    <h4 className="font-semibold text-purple-700">The Accelerator Role</h4>
                  </div>
                  <p className="text-sm text-gray-700">{selectedConcern.acceleratorRole}</p>
                </div>
                
                <div className="p-4 bg-white rounded-lg border border-pink-200">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded-full bg-pink-500 text-white flex items-center justify-center text-xs font-bold">2</div>
                    <h4 className="font-semibold text-pink-700">The Recovery Role</h4>
                  </div>
                  <p className="text-sm text-gray-700">{selectedConcern.recoveryRole}</p>
                </div>
              </div>

              <div className="p-4 bg-gradient-to-r from-emerald-50 to-green-50 rounded-lg border border-emerald-200">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  <h4 className="font-semibold text-emerald-700">Combo Result</h4>
                </div>
                <p className="text-sm text-emerald-800 font-medium">{selectedConcern.comboResult}</p>
              </div>
            </div>
          )}
        </div>

        {/* Combo Cards */}
        <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">Available Clinical Protocols</h2>
        
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {combos.map((combo) => (
            <Card 
              key={combo.id} 
              className="overflow-hidden hover:shadow-xl transition-all cursor-pointer group relative"
              onClick={() => fetchComboDetails(combo.id)}
            >
              {/* Share button on card */}
              <button
                className="absolute top-3 right-3 z-10 p-2 bg-white/90 rounded-full shadow-md hover:bg-white hover:scale-110 transition-all opacity-0 group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedCombo(combo);
                  setShowShareModal(true);
                }}
                data-testid={`share-combo-card-${combo.id}`}
                title="Share this set"
              >
                <Share2 className="h-4 w-4 text-purple-600" />
              </button>
              
              <div className="bg-gradient-to-r from-purple-500 to-pink-500 p-4 text-white">
                <Badge className="bg-white/20 text-white mb-2">
                  <Sparkles className="h-3 w-3 mr-1" /> {Number(combo.discount_percent).toFixed(2)}% OFF
                </Badge>
                <h3 className="font-bold text-lg">{combo.name}</h3>
              </div>
              <CardContent className="p-4">
                <p className="text-sm text-gray-600 mb-3">{combo.tagline || combo.description}</p>
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xl font-bold text-purple-600">
                      ${combo.combo_price?.toFixed(2)}
                    </span>
                    <span className="text-sm text-gray-400 line-through ml-2">
                      ${combo.original_price?.toFixed(2)}
                    </span>
                  </div>
                  <Button variant="ghost" size="sm" className="group-hover:bg-purple-100">
                    View Details <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Selected Combo Detail */}
        {selectedCombo && (
          <div 
            className="bg-white rounded-2xl shadow-xl mb-12 animate-in fade-in slide-in-from-bottom-4 duration-500 relative"
            style={{
              maxHeight: '85vh',
              overflowY: 'auto',
              overscrollBehavior: 'contain',
              maxWidth: '100%',
            }}
          >
            {/* Prominent X Close Button - Fixed position on top right corner */}
            <button
              onClick={() => {
                setSelectedCombo(null);
                setSelectedProducts(new Set());
              }}
              aria-label="Close"
              className="absolute top-3 right-3 z-50 w-10 h-10 rounded-full bg-white shadow-lg flex items-center justify-center text-gray-600 hover:text-black hover:bg-gray-100 transition-all border border-gray-200"
              data-testid="close-combo-x-btn"
              title="Close"
            >
              <X className="h-5 w-5" />
            </button>
            
            {/* Combo Header */}
            <div className="bg-gradient-to-r from-purple-600 to-pink-500 p-6 pt-14 text-white">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-5 w-5" />
                <span className="font-semibold text-lg">{selectedCombo.name}</span>
              </div>
              <p className="text-purple-100">{selectedCombo.tagline || selectedCombo.description}</p>
            </div>

            <div className="p-6">
              {/* Products with Selection */}
              <div className="mb-6">
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Package className="h-5 w-5 text-purple-600" />
                  Products Included - Click to Select
                </h3>
                
                <div className="grid md:grid-cols-2 gap-4">
                  {selectedCombo.products?.map((product, idx) => {
                    const isSelected = selectedProducts.has(product.id);
                    return (
                      <div 
                        key={product.id}
                        className={`flex items-center gap-4 p-4 rounded-xl border-2 transition-all cursor-pointer relative ${
                          isSelected 
                            ? 'bg-purple-50 border-purple-400 ring-2 ring-purple-200' 
                            : 'bg-gray-50 border-gray-200 hover:border-purple-300'
                        }`}
                        onClick={() => toggleProductSelection(product.id)}
                        data-testid={`combo-product-${idx}`}
                      >
                        {/* Selected Badge */}
                        {isSelected && (
                          <div className="absolute -top-2 -right-2 bg-green-500 text-white text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1 shadow-md">
                            <CheckCircle2 className="h-3 w-3" />
                            Selected
                          </div>
                        )}
                        
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
                          idx === 0 ? 'bg-purple-500' : 'bg-pink-500'
                        }`}>
                          {idx + 1}
                        </div>
                        <div className="w-16 h-16 rounded-lg overflow-hidden bg-white border">
                          <img 
                            src={product.images?.[0] || '/placeholder.png'}
                            alt={product.name}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900 text-sm">{product.name}</p>
                          <p className="text-xs text-gray-500">
                            {idx === 0 ? 'Apply first on cleansed skin' : 'Apply after Step 1 to seal'}
                          </p>
                          <p className="text-xs text-purple-600 mt-1">
                            {isSelected ? '✓ Click to deselect' : 'Click to select'}
                          </p>
                        </div>
                        <ChevronRight className="h-5 w-5 text-gray-400" />
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Synergy Note */}
              {selectedCombo.synergy_note && (
                <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl mb-6">
                  <div className="flex items-start gap-2">
                    <Zap className="h-5 w-5 text-purple-600 mt-0.5" />
                    <div>
                      <span className="font-semibold text-purple-700">The Synergy: </span>
                      <span className="text-gray-700">{selectedCombo.synergy_note}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Total Active Power Display */}
              {selectedCombo.total_active_percent > 0 && (
                <div className="p-6 bg-gradient-to-r from-amber-50 via-orange-50 to-yellow-50 rounded-xl border-2 border-amber-300 mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Zap className="h-6 w-6 text-amber-600" />
                      <h3 className="font-bold text-amber-900 text-lg">Total Active Power</h3>
                    </div>
                    <Badge className="bg-gradient-to-r from-amber-500 to-orange-500 text-white px-4 py-1 text-lg font-bold">
                      {selectedCombo.total_active_percent}%
                    </Badge>
                  </div>
                  
                  {/* Power Meter */}
                  <div className="relative h-6 bg-amber-200 rounded-full overflow-hidden mb-4">
                    <div 
                      className="h-full bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 transition-all duration-1000 ease-out rounded-full"
                      style={{ width: `${Math.min(parseFloat(selectedCombo.total_active_percent), 100)}%` }}
                    />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-bold text-white drop-shadow">HYPER-POTENCY FORMULA</span>
                    </div>
                  </div>

                  {/* DMI Driver Note */}
                  <div className="p-3 bg-white/70 rounded-lg border border-amber-200 mb-3">
                    <div className="flex items-start gap-2">
                      <TrendingUp className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                      <div className="text-sm">
                        <span className="font-semibold text-amber-800">Deep Delivery System: </span>
                        <span className="text-gray-700">
                          AURA-GEN uses a 4.5% DMI Molecular Taxi system. While other brands sit on the surface, 
                          our {selectedCombo.total_active_percent}% active load is pulled directly into the dermis 
                          for faster cellular reprogramming.
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Active Breakdown */}
                  <div className="grid grid-cols-2 gap-3">
                    {selectedCombo.products?.map((product, idx) => {
                      const isEngine = idx === 0;
                      return (
                        <div 
                          key={product.id}
                          className={`p-3 rounded-lg ${isEngine ? 'bg-purple-100 border border-purple-200' : 'bg-pink-100 border border-pink-200'}`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-xs font-bold ${isEngine ? 'bg-purple-500' : 'bg-pink-500'}`}>
                              {idx + 1}
                            </div>
                            <span className={`text-xs font-bold ${isEngine ? 'text-purple-700' : 'text-pink-700'}`}>
                              {isEngine ? 'ENGINE' : 'BUFFER'}
                            </span>
                          </div>
                          <p className="text-sm font-medium text-gray-900 truncate">{product.name?.split(' ').slice(0, 3).join(' ')}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Safety Badge */}
              <div className="flex items-center gap-3 p-3 bg-emerald-50 rounded-lg border border-emerald-200 mb-6">
                <Shield className="h-6 w-6 text-emerald-600" />
                <div>
                  <span className="font-semibold text-emerald-800">Dermatologically Balanced</span>
                  <p className="text-xs text-emerald-700">
                    Pairs Acidic Resurfacing (pH 4.0) with Lipid Barrier Recovery (Ceramides/PDRN) for maximum results with zero downtime.
                  </p>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
                {[
                  { id: 'timeline', label: 'Results', icon: Clock },
                  { id: 'concerns', label: 'Concerns', icon: Target },
                  { id: 'howto', label: 'How to Use', icon: Activity },
                  { id: 'safety', label: 'Safety', icon: Shield },
                ].map((tab) => (
                  <Button
                    key={tab.id}
                    variant={activeTab === tab.id ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setActiveTab(tab.id)}
                    className={activeTab === tab.id ? 'bg-purple-600' : ''}
                  >
                    <tab.icon className="h-4 w-4 mr-1" />
                    {tab.label}
                  </Button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="min-h-[200px]">
                {activeTab === 'timeline' && selectedCombo.results_timeline && (
                  <div className="space-y-4">
                    {selectedCombo.results_timeline.map((phase, idx) => (
                      <div key={idx} className="flex gap-4">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold ${
                          idx === 0 ? 'bg-purple-500' : idx === 1 ? 'bg-pink-500' : 'bg-emerald-500'
                        }`}>
                          {idx + 1}
                        </div>
                        <div className="flex-1 p-4 bg-gray-50 rounded-lg">
                          <h4 className="font-semibold text-gray-900">{phase.period}</h4>
                          <p className="text-sm text-purple-600 mb-2">{phase.phase_name}</p>
                          <ul className="space-y-1">
                            {phase.results?.map((result, i) => (
                              <li key={i} className="text-sm text-gray-600 flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                {result}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {activeTab === 'concerns' && (
                  <div className="space-y-4">
                    <p className="text-gray-600 mb-4">
                      Select your primary concern to see how this combo targets it:
                    </p>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {SYNERGY_DATA.concerns.map((concern) => (
                        <div
                          key={concern.id}
                          className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                            selectedConcern?.id === concern.id 
                              ? 'border-purple-500 bg-purple-50' 
                              : 'border-gray-200 hover:border-purple-300'
                          }`}
                          onClick={() => setSelectedConcern(selectedConcern?.id === concern.id ? null : concern)}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xl">{concern.icon}</span>
                            <span className="font-medium">{concern.name}</span>
                          </div>
                          <Badge className="bg-green-100 text-green-700 text-xs">
                            {concern.speedAdvantage}
                          </Badge>
                        </div>
                      ))}
                    </div>
                    
                    {selectedConcern && (
                      <div className="mt-4 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                        <h4 className="font-semibold text-purple-800 mb-3">
                          {selectedConcern.icon} Targeting {selectedConcern.name}
                        </h4>
                        <p className="text-sm text-gray-700">{selectedConcern.comboResult}</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'howto' && (
                  <div className="space-y-4">
                    {/* If combo has explicit steps, show them */}
                    {selectedCombo.how_to_use_steps ? (
                      selectedCombo.how_to_use_steps.map((step, idx) => (
                        <React.Fragment key={idx}>
                          <div className="flex gap-4 items-start">
                            <div className="w-8 h-8 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center font-bold text-sm">
                              {idx + 1}
                            </div>
                            <div className="flex-1">
                              <h4 className="font-medium text-gray-900">{step.title || `Step ${idx + 1}`}</h4>
                              <p className="text-sm text-gray-600">{step.description || step}</p>
                            </div>
                          </div>
                          
                          {/* 60-Second Protocol Timer - Shows after Step 1 */}
                          {idx === 0 && selectedCombo.how_to_use_steps.length > 1 && (
                            <div className="ml-4">
                              <CountdownTimer onComplete={() => toast.success('Ready for Step 2! Apply now while skin is damp.')} />
                            </div>
                          )}
                        </React.Fragment>
                      ))
                    ) : (
                      /* Default protocol steps for combos without explicit how_to_use_steps */
                      <>
                        {/* Step 1 - Engine/Accelerator */}
                        <div className="flex gap-4 items-start">
                          <div className="w-8 h-8 rounded-full bg-purple-500 text-white flex items-center justify-center font-bold text-sm">
                            1
                          </div>
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-900">Apply Step 1 (Engine)</h4>
                            <p className="text-sm text-gray-600">
                              Cleanse face thoroughly. Apply the first product (Accelerator) evenly across face, 
                              avoiding eye area. Use gentle upward strokes.
                            </p>
                          </div>
                        </div>
                        
                        {/* 60-Second Protocol Timer */}
                        <div className="ml-4">
                          <CountdownTimer onComplete={() => toast.success('Ready for Step 2! Apply now while skin is damp.')} />
                        </div>
                        
                        {/* Step 2 - Buffer/Recovery */}
                        <div className="flex gap-4 items-start">
                          <div className="w-8 h-8 rounded-full bg-pink-500 text-white flex items-center justify-center font-bold text-sm">
                            2
                          </div>
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-900">Apply Step 2 (Buffer)</h4>
                            <p className="text-sm text-gray-600">
                              While skin is still slightly damp from Step 1, apply the second product (Recovery). 
                              Gently press into skin using patting motions for optimal absorption.
                            </p>
                          </div>
                        </div>
                        
                        {/* SPF Reminder */}
                        <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200 flex items-start gap-3">
                          <Sun className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                          <div>
                            <h5 className="font-medium text-blue-800 text-sm">Morning Routine</h5>
                            <p className="text-sm text-blue-700">
                              Always finish with SPF 30+ sunscreen. These active ingredients increase photosensitivity.
                            </p>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {activeTab === 'safety' && (
                  <div className="space-y-4">
                    {/* pH Level Warning */}
                    <div className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
                        <div>
                          <h4 className="font-semibold text-amber-800 mb-1">{SAFETY_INFO.phLevel.title}</h4>
                          <p className="text-sm text-amber-700 mb-2">{SAFETY_INFO.phLevel.warning}</p>
                          <p className="text-sm text-amber-600">
                            <span className="font-medium">Soothing Protocol: </span>
                            {SAFETY_INFO.phLevel.soothingAgent}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Safety Requirements */}
                    <div className="grid sm:grid-cols-2 gap-3">
                      {SAFETY_INFO.requirements.map((req, idx) => (
                        <div 
                          key={idx}
                          className={`p-3 rounded-lg border ${
                            req.critical 
                              ? 'bg-red-50 border-red-200' 
                              : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <req.icon className={`h-4 w-4 ${req.critical ? 'text-red-600' : 'text-gray-600'}`} />
                            <span className={`text-sm ${req.critical ? 'text-red-700 font-medium' : 'text-gray-700'}`}>
                              {req.text}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Warnings from Combo */}
                    {selectedCombo.warnings?.length > 0 && (
                      <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                        <h4 className="font-semibold text-red-800 mb-2">Important Warnings</h4>
                        <ul className="space-y-1">
                          {selectedCombo.warnings.map((warning, idx) => (
                            <li key={idx} className="text-sm text-red-700 flex items-start gap-2">
                              <span>•</span> {warning}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Do Not Use With */}
                    {selectedCombo.do_not_use_with?.length > 0 && (
                      <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                        <h4 className="font-semibold text-gray-800 mb-2">Do Not Use With:</h4>
                        <div className="flex flex-wrap gap-2">
                          {selectedCombo.do_not_use_with.map((item, idx) => (
                            <Badge key={idx} variant="outline" className="bg-white text-red-600 border-red-200">
                              {item}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Safety FAQ Accordion */}
                    <div className="mt-6">
                      <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        <Shield className="h-5 w-5 text-purple-600" />
                        Safety & Protocol FAQ
                      </h4>
                      <div className="space-y-2">
                        {SAFETY_INFO.faq.map((item, idx) => (
                          <details key={idx} className="group bg-white rounded-lg border border-gray-200 overflow-hidden">
                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors">
                              <span className="font-medium text-gray-800 text-sm pr-4">{item.question}</span>
                              <ChevronRight className="h-5 w-5 text-gray-400 group-open:rotate-90 transition-transform flex-shrink-0" />
                            </summary>
                            <div className="p-4 pt-0 border-t border-gray-100">
                              <p className="text-sm text-gray-600 leading-relaxed">{item.answer}</p>
                            </div>
                          </details>
                        ))}
                      </div>
                    </div>

                    {/* 60-Second Timer Note */}
                    <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <Clock className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="font-semibold text-blue-800 text-sm">60-Second Protocol</p>
                          <p className="text-xs text-blue-700">
                            Wait 60s between Step 1 and Step 2 to allow Molecular Taxis (DMI) to clear the surface.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* CTA Section */}
              <div className="mt-8 p-6 bg-gradient-to-r from-purple-50 via-white to-pink-50 rounded-xl border-2 border-purple-200">
                {/* Selection Status */}
                {!hasProductsSelected && (
                  <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-amber-600" />
                    <span className="text-sm text-amber-800">
                      Please select at least one product above to add to your bag
                    </span>
                  </div>
                )}
                
                {/* Stock Info Display (after adding to cart) */}
                {Object.keys(stockInfo).length > 0 && (
                  <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm font-medium text-blue-800 mb-1">Stock Availability:</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.values(stockInfo).map((info, idx) => (
                        <span key={idx} className={`text-xs px-2 py-1 rounded-full ${
                          typeof info.stock === 'number' && info.stock < 10 
                            ? 'bg-red-100 text-red-700' 
                            : typeof info.stock === 'number' && info.stock < 20 
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-green-100 text-green-700'
                        }`}>
                          {info.name}: {info.stock} left
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-3xl font-bold text-gray-900">
                        ${Number(selectedCombo.combo_price).toFixed(2)}
                      </span>
                      <span className="text-lg text-gray-400 line-through">
                        ${Number(selectedCombo.original_price).toFixed(2)}
                      </span>
                    </div>
                    <Badge className="bg-gradient-to-r from-emerald-500 to-green-500 text-white">
                      <Sparkles className="h-3 w-3 mr-1" />
                      Save {Number(selectedCombo.discount_percent).toFixed(2)}% (${(selectedCombo.original_price - selectedCombo.combo_price).toFixed(2)})
                    </Badge>
                    {/* Selection count */}
                    <p className="text-xs text-gray-500 mt-2">
                      {selectedProducts.size} of {selectedCombo.products?.length || 0} products selected
                    </p>
                  </div>
                  <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
                    {/* Continue Shopping Button */}
                    <Button 
                      onClick={() => {
                        setSelectedCombo(null);
                        setSelectedProducts(new Set());
                        setStockInfo({});
                      }}
                      size="lg"
                      variant="outline"
                      className="w-full sm:w-auto border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-6"
                      data-testid="continue-shopping-btn"
                    >
                      <ArrowLeft className="h-5 w-5 mr-2" />
                      Continue Shopping
                    </Button>
                    
                    {/* Share Button */}
                    <Button 
                      onClick={() => setShowShareModal(true)}
                      size="lg"
                      variant="outline"
                      className="border-purple-300 text-purple-600 hover:bg-purple-50 px-4 py-6"
                      data-testid="share-combo-btn"
                    >
                      <Share2 className="h-5 w-5" />
                    </Button>
                    
                    {/* Add to Cart Button - Enabled when at least 1 product selected */}
                    <Button 
                      onClick={handleAddComboToCart}
                      size="lg"
                      disabled={addingToCart || !hasProductsSelected}
                      className={`w-full sm:w-auto px-10 py-6 text-lg shadow-xl transition-all ${
                        hasProductsSelected 
                          ? 'bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white hover:shadow-2xl' 
                          : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      }`}
                      data-testid="add-combo-to-cart-btn"
                    >
                      {addingToCart ? (
                        <>
                          <Loader2 className="h-6 w-6 mr-2 animate-spin" />
                          Adding...
                        </>
                      ) : (
                        <>
                          <ShoppingBag className="h-6 w-6 mr-2" />
                          Add Complete Set to Bag
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Share Modal */}
        <ComboShareModal 
          combo={selectedCombo} 
          isOpen={showShareModal} 
          onClose={() => setShowShareModal(false)} 
        />

        {/* Empty State */}
        {combos.length === 0 && !loading && (
          <div className="text-center py-16">
            <Package className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-700 mb-2">No Sets Available</h3>
            <p className="text-gray-500 mb-6">Check back soon for curated skincare bundles!</p>
            <Button onClick={() => navigate('/products')}>
              Browse Individual Products
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SkincareSetsPage;
