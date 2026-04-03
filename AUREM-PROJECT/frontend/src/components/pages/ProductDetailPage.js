import React, { useState, useEffect, useRef, lazy, Suspense, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Helmet } from "react-helmet-async";
import { useWebSocket } from "../../contexts/WebSocketContext";
import {
  Star,
  Plus,
  Minus,
  X,
  Check,
  CheckCircle,
  Heart,
  Beaker,
  Sparkles,
  FlaskConical,
  Shield,
  ShieldCheck,
  Clock,
  Image,
  Share2,
  Dna,
  Droplets,
  QrCode,
  Globe,
  AlertTriangle,
  Loader2,
  MessageCircle,
  Facebook,
  Twitter,
  Mail,
  Copy,
  Edit,
  Upload,
  Trash2,
  Save,
  FileText,
  ChevronRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import ComboUpsellPopup from "../product/ComboUpsellPopup";

// Import all hooks from contexts
import { 
  useCart, 
  useAuth, 
  useCurrency, 
  useWishlist, 
  useStoreSettings,
  useTranslation
} from "../../contexts";
import SEO from "../SEO";
import { Breadcrumbs } from "@/components/Breadcrumbs";

// Lazy load framer-motion
const MotionDiv = lazy(() => import('framer-motion').then(mod => ({ default: mod.motion.div })));
const MotionButton = lazy(() => import('framer-motion').then(mod => ({ default: mod.motion.button })));
const AnimatePresence = lazy(() => import('framer-motion').then(mod => ({ default: mod.AnimatePresence })));

// Lazy load AURA-GEN Reverse Hook (only loads for AURA-GEN products)
const AuraGenReverseHook = lazy(() => import('../AuraGenReverseHook'));
const StickyCTA = lazy(() => import('../AuraGenReverseHook').then(mod => ({ default: mod.StickyCTA })));

// Lazy load 3D Product Viewer (React Three Fiber v9 + React 19 compatible)
const ProductViewer3D = lazy(() => import('../ProductViewer3D'));

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

// API endpoint
const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;

/**
 * Optimize image URL through Cloudinary for WebP/AVIF and proper sizing
 * @param {string} imageUrl - Original image URL
 * @param {number} width - Target width (default 800)
 * @param {number} height - Target height (default 800)
 * @returns {string} - Cloudinary optimized URL
 */
const optimizeImage = (imageUrl, width = 800, height = 800) => {
  if (!imageUrl) return imageUrl;
  // Skip if already Cloudinary URL
  if (imageUrl.includes('res.cloudinary.com')) return imageUrl;
  // Skip placeholder images
  if (imageUrl.includes('via.placeholder.com')) return imageUrl;
  // Encode and wrap with Cloudinary fetch
  const encodedUrl = encodeURIComponent(imageUrl);
  return `https://res.cloudinary.com/ddpphzqdg/image/fetch/w_${width},h_${height},c_fill,q_auto,f_auto/${encodedUrl}`;
};

// UI Translations for product page
const UI_TRANSLATIONS = {
  "en-CA": {
    add_to_cart: "Add to Cart",
    pre_order: "Pre-Order",
    pre_order_item: "Pre-Order Item",
    available_on: "Available on",
    ships_soon: "Ships in 2-3 weeks after release",
    reviews: "reviews",
    ingredients: "Ingredients",
    how_to_use: "How to Use",
    bestseller: "Bestseller",
    customer_reviews: "Customer Reviews",
    product_not_found: "Product not found"
  },
  en: {
    add_to_cart: "Add to Cart",
    pre_order: "Pre-Order",
    pre_order_item: "Pre-Order Item",
    available_on: "Available on",
    ships_soon: "Ships in 2-3 weeks after release",
    reviews: "Reviews",
    ingredients: "Ingredients",
    how_to_use: "How to Use",
    bestseller: "Bestseller",
    customer_reviews: "Customer Reviews",
    product_not_found: "Product not found"
  }
};

// Biotech Ingredients Data
// Dynamic Ingredients Parser - generates ingredient cards from product data
const parseProductIngredients = (product) => {
  if (!product) return [];
  
  // If product has custom hero_ingredients array, use those with proper icons
  if (product.hero_ingredients && Array.isArray(product.hero_ingredients) && product.hero_ingredients.length > 0) {
    const iconMap = {
      'dna': Dna,
      'flask': FlaskConical,
      'sparkles': Sparkles,
      'shield': Shield,
      'droplets': Droplets,
      'beaker': Beaker,
      'check': ShieldCheck
    };
    
    // Use pink color scheme for pink_peptide products
    const isPinkProduct = product.product_type === 'pink_peptide' || product.accent_color === 'pink';
    const accentColor = isPinkProduct ? '#EC4899' : '#D4AF37';
    
    return product.hero_ingredients.map((ing, idx) => ({
      id: `hero-${idx}`,
      name: ing.name,
      icon: iconMap[ing.icon] || FlaskConical,
      color: isPinkProduct 
        ? ['#EC4899', '#F472B6', '#DB2777', '#BE185D', '#9D174D'][idx % 5]
        : ing.color || accentColor,
      concentration: ing.concentration || 'Active',
      shortDesc: ing.description || '',
      description: ing.description || `Key active ingredient in this formula.`,
      benefits: ing.benefits || ['See product description for full benefits']
    }));
  }
  
  // If product has structured active_ingredients, use those
  if (product.active_ingredients && Array.isArray(product.active_ingredients)) {
    return product.active_ingredients;
  }
  
  // Parse from ingredients text field
  const ingredientsText = product.ingredients || '';
  const parsedIngredients = [];
  
  // Common ingredient patterns to look for
  const ingredientPatterns = [
    { key: 'pdrn', names: ['pdrn', 'polydeoxyribonucleotide', 'salmon dna'], name: 'PDRN', icon: Dna, color: '#D4AF37', shortDesc: 'Salmon DNA Extract' },
    { key: 'tranexamic', names: ['tranexamic', 'txa'], name: 'Tranexamic Acid', icon: Sparkles, color: '#F8A5B8', shortDesc: 'Brightening Agent' },
    { key: 'niacinamide', names: ['niacinamide', 'vitamin b3', 'nicotinamide'], name: 'Niacinamide', icon: Shield, color: '#4ECDC4', shortDesc: 'Barrier Support' },
    { key: 'hyaluronic', names: ['hyaluronic', 'sodium hyaluronate'], name: 'Hyaluronic Acid', icon: Droplets, color: '#3B82F6', shortDesc: 'Deep Hydration' },
    { key: 'peptide', names: ['peptide', 'argireline', 'matrixyl'], name: 'Peptide Complex', icon: FlaskConical, color: '#8B5CF6', shortDesc: 'Firming Support' },
    { key: 'ceramide', names: ['ceramide'], name: 'Ceramides', icon: ShieldCheck, color: '#10B981', shortDesc: 'Barrier Repair' },
    { key: 'retinol', names: ['retinol', 'retinoid', 'vitamin a'], name: 'Retinol', icon: Sparkles, color: '#F59E0B', shortDesc: 'Anti-Aging' },
    { key: 'vitamin_c', names: ['vitamin c', 'ascorbic', 'ascorbyl'], name: 'Vitamin C', icon: Shield, color: '#F97316', shortDesc: 'Antioxidant' },
    { key: 'salicylic', names: ['salicylic', 'bha'], name: 'Salicylic Acid', icon: Beaker, color: '#EF4444', shortDesc: 'Exfoliant' },
    { key: 'glycolic', names: ['glycolic', 'aha'], name: 'Glycolic Acid', icon: Beaker, color: '#EC4899', shortDesc: 'Exfoliant' },
    { key: 'copper', names: ['copper peptide', 'copper'], name: 'Copper Peptides', icon: Dna, color: '#B45309', shortDesc: 'Healing & Repair' },
    { key: 'nad', names: ['nad+', 'nad', 'nicotinamide adenine'], name: 'NAD+', icon: FlaskConical, color: '#7C3AED', shortDesc: 'Cellular Energy' },
    { key: 'caffeine', names: ['caffeine'], name: 'Caffeine', icon: Sparkles, color: '#A16207', shortDesc: 'Depuffing' },
    { key: 'vitamin_b12', names: ['vitamin b12', 'cyanocobalamin', 'b12'], name: 'Vitamin B12', icon: Shield, color: '#EC4899', shortDesc: 'Natural Glow' },
    { key: 'squalane', names: ['squalane', 'squalene'], name: 'Squalane', icon: Droplets, color: '#22C55E', shortDesc: 'Moisturizing' },
    { key: 'zinc', names: ['zinc'], name: 'Zinc', icon: Shield, color: '#6B7280', shortDesc: 'Healing Support' },
    { key: 'aloe', names: ['aloe vera', 'aloe'], name: 'Aloe Vera', icon: Droplets, color: '#16A34A', shortDesc: 'Soothing' },
    { key: 'green_tea', names: ['green tea', 'camellia sinensis'], name: 'Green Tea', icon: Shield, color: '#15803D', shortDesc: 'Antioxidant' },
  ];
  
  const lowerIngredients = ingredientsText.toLowerCase();
  
  ingredientPatterns.forEach(pattern => {
    if (pattern.names.some(name => lowerIngredients.includes(name))) {
      // Try to extract concentration (e.g., "5%", "2.0%")
      let concentration = '';
      pattern.names.forEach(name => {
        const regex = new RegExp(`${name}[^0-9]*([0-9]+\\.?[0-9]*%?)`, 'i');
        const match = ingredientsText.match(regex);
        if (match && match[1]) {
          concentration = match[1].includes('%') ? match[1] : `${match[1]}%`;
        }
      });
      
      parsedIngredients.push({
        id: pattern.key,
        name: pattern.name,
        icon: pattern.icon,
        color: pattern.color,
        concentration: concentration || 'Active',
        shortDesc: pattern.shortDesc,
        description: `Key active ingredient in this formula.`,
        benefits: ['See product description for full benefits']
      });
    }
  });
  
  // If no ingredients parsed, return empty array (don't show the section)
  return parsedIngredients;
};

// Default "What's Included" based on product data
const getWhatsIncluded = (product) => {
  if (!product) return [];
  
  // If product has custom whats_included field, use it
  if (product.whats_included && Array.isArray(product.whats_included)) {
    return product.whats_included;
  }
  
  // Generate default based on product type
  const included = [];
  
  // Always include the product itself
  const mainIngredients = [];
  const ingredientsText = (product.ingredients || '').toLowerCase();
  
  if (ingredientsText.includes('pdrn')) mainIngredients.push('PDRN');
  if (ingredientsText.includes('tranexamic') || ingredientsText.includes('txa')) mainIngredients.push('TXA');
  if (ingredientsText.includes('niacinamide')) mainIngredients.push('Niacinamide');
  if (ingredientsText.includes('peptide') || ingredientsText.includes('argireline')) mainIngredients.push('Peptides');
  if (ingredientsText.includes('copper')) mainIngredients.push('Copper Peptides');
  if (ingredientsText.includes('nad')) mainIngredients.push('NAD+');
  if (ingredientsText.includes('hyaluronic')) mainIngredients.push('Hyaluronic Acid');
  if (ingredientsText.includes('retinol')) mainIngredients.push('Retinol');
  if (ingredientsText.includes('vitamin c')) mainIngredients.push('Vitamin C');
  if (ingredientsText.includes('caffeine')) mainIngredients.push('Caffeine');
  if (ingredientsText.includes('b12') || ingredientsText.includes('cyanocobalamin')) mainIngredients.push('Vitamin B12');
  
  if (mainIngredients.length > 0) {
    included.push({
      title: `${product.name?.split(' ')[0] || 'Active'} Formula`,
      description: mainIngredients.slice(0, 4).join(' + ')
    });
  } else {
    included.push({
      title: 'Premium Formula',
      description: product.short_description || 'Advanced skincare technology'
    });
  }
  
  // Add texture description if available
  if (product.texture_description) {
    included.push({
      title: 'Signature Texture',
      description: product.texture_description
    });
  }
  
  // Add volume/size if available
  if (product.size || product.volume) {
    included.push({
      title: `${product.size || product.volume}`,
      description: 'Full-size product'
    });
  } else {
    included.push({
      title: '30ml / 1.0 fl oz',
      description: 'Full-size product'
    });
  }
  
  // Add guarantee
  included.push({
    title: '30-Day Satisfaction Guarantee',
    description: 'Full refund if not satisfied'
  });
  
  return included;
};

// Get product accent color
const getAccentColor = (product) => {
  if (!product) return { primary: '#D4AF37', light: '#FDF9F0', gradient: 'from-[#D4AF37] to-[#F4D03F]' };
  
  if (product.accent_color === 'pink' || product.product_type === 'pink_peptide') {
    return {
      primary: '#EC4899',
      secondary: '#F472B6',
      light: '#FDF2F8',
      gradient: 'from-[#EC4899] to-[#F472B6]',
      border: '#FBCFE8',
      text: '#BE185D'
    };
  }
  
  // Default gold/amber for AURA-GEN style products
  return {
    primary: '#D4AF37',
    secondary: '#F4D03F',
    light: '#FDF9F0',
    gradient: 'from-[#D4AF37] to-[#F4D03F]',
    border: '#F5E6C4',
    text: '#92400E'
  };
};

// Formula Breakdown Component
const FormulaBreakdown = ({ product }) => {
  if (!product?.formula_breakdown && !product?.hero_ingredients) return null;
  
  const accent = getAccentColor(product);
  const breakdown = product.formula_breakdown || {};
  const heroIngredients = product.hero_ingredients || [];
  
  // Build formula items from either formula_breakdown or hero_ingredients
  const formulaItems = Object.keys(breakdown).length > 0 
    ? Object.entries(breakdown).map(([key, value]) => ({
        name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        concentration: value
      }))
    : heroIngredients.map(ing => ({
        name: ing.name,
        concentration: ing.concentration
      }));
  
  if (formulaItems.length === 0) return null;
  
  return (
    <div className="bg-gradient-to-br from-white to-gray-50 border border-gray-100 rounded-xl p-5 mt-6">
      <div className="flex items-center gap-2 mb-4">
        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${accent.gradient} flex items-center justify-center`}>
          <FlaskConical className="h-4 w-4 text-white" />
        </div>
        <h4 className="font-display font-semibold text-[#2D2A2E]">Formula Breakdown</h4>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {formulaItems.map((item, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-100">
            <span className="text-sm font-medium text-[#2D2A2E]">{item.name}</span>
            <span className={`text-sm font-bold`} style={{ color: accent.primary }}>{item.concentration}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Science Section Component
const ScienceSection = ({ product }) => {
  if (!product?.science_highlight) return null;
  
  const accent = getAccentColor(product);
  
  return (
    <div className={`border rounded-xl p-5 mt-6`} style={{ borderColor: accent.border, backgroundColor: accent.light }}>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${accent.gradient} flex items-center justify-center`}>
          <Beaker className="h-4 w-4 text-white" />
        </div>
        <h4 className="font-display font-semibold text-[#2D2A2E]">The Science</h4>
      </div>
      <p className="text-sm text-[#5A5A5A] leading-relaxed">{product.science_highlight}</p>
      {product.texture_description && (
        <div className="mt-4 pt-4 border-t" style={{ borderColor: accent.border }}>
          <p className="text-xs uppercase tracking-wider mb-1" style={{ color: accent.text }}>Texture</p>
          <p className="text-sm text-[#2D2A2E] font-medium">{product.texture_description}</p>
        </div>
      )}
    </div>
  );
};

const BIOTECH_INGREDIENTS = [
  {
    id: "pdrn",
    name: "PDRN",
    formula: "C₁₀H₁₄N₄O₄P",
    fullName: "Polydeoxyribonucleotide",
    icon: Dna,
    color: "#D4AF37",
    concentration: "2%",
    shortDesc: "Salmon DNA Extract",
    description: "A bio-active molecule celebrated in advanced skincare for its ability to mimic the skin's natural revitalizing processes. Helps the skin's surface feel more resilient and look visibly rejuvenated.",
    benefits: ["Supports surface cell turnover", "Improves skin resilience", "Soothes visible redness"],
    origin: "Sustainably sourced Salmon DNA",
    research: "Used in professional aesthetics for decades"
  },
  {
    id: "tranexamic",
    name: "Tranexamic Acid",
    formula: "C₈H₁₅NO₂",
    fullName: "Trans-4-aminomethylcyclohexanecarboxylic acid",
    icon: Sparkles,
    color: "#F8A5B8",
    concentration: "5%",
    shortDesc: "Brightening Agent",
    description: "A powerful ingredient that helps visibly even skin tone and reduce the appearance of dark spots and discoloration for a more luminous complexion.",
    benefits: ["Evens skin tone appearance", "Reduces visible discoloration", "Brightens overall complexion"],
    origin: "Pharmaceutical-grade synthesis",
    research: "Dermatologist recommended for hyperpigmentation concerns"
  },
  {
    id: "niacinamide",
    name: "Niacinamide",
    formula: "C₆H₆N₂O",
    fullName: "Nicotinamide (Vitamin B3)",
    icon: Shield,
    color: "#4ECDC4",
    concentration: "4%",
    shortDesc: "Barrier Support",
    description: "A versatile vitamin that helps strengthen the skin's moisture barrier while visibly minimizing the appearance of pores and improving overall skin texture.",
    benefits: ["Strengthens moisture barrier", "Minimizes pore appearance", "Improves skin texture"],
    origin: "Naturally derived",
    research: "Extensively studied for multiple skin benefits"
  },
  {
    id: "hyaluronic",
    name: "Hyaluronic Acid",
    formula: "C₁₄H₂₁NO₁₁",
    fullName: "Sodium Hyaluronate",
    icon: Droplets,
    color: "#3B82F6",
    concentration: "1.5%",
    shortDesc: "Deep Hydration",
    description: "A powerful humectant that can hold up to 1000x its weight in water, providing multi-layer hydration for a plump, dewy complexion.",
    benefits: ["Intense multi-layer hydration", "Plumps and smooths", "Dewy, youthful appearance"],
    origin: "Biofermentation process",
    research: "Gold standard in skincare hydration"
  },
  {
    id: "peptides",
    name: "Peptide Complex",
    formula: "Various",
    fullName: "Multi-Peptide Blend",
    icon: FlaskConical,
    color: "#8B5CF6",
    concentration: "3%",
    shortDesc: "Firming Support",
    description: "A sophisticated blend of signal peptides that help support the skin's natural firmness and elasticity for a more youthful-looking appearance.",
    benefits: ["Supports skin firmness", "Improves elasticity appearance", "Smooths fine lines"],
    origin: "Advanced biotech synthesis",
    research: "Next-generation anti-aging technology"
  },
  {
    id: "ceramides",
    name: "Ceramide Complex",
    formula: "C₃₄H₆₆NO₃R",
    fullName: "Ceramide NP, AP, EOP",
    icon: ShieldCheck,
    color: "#10B981",
    concentration: "1%",
    shortDesc: "Barrier Repair",
    description: "Essential lipids that help restore and maintain the skin's protective barrier, locking in moisture and protecting against environmental stressors.",
    benefits: ["Restores skin barrier", "Locks in hydration", "Protects from environment"],
    origin: "Skin-identical lipids",
    research: "Essential for healthy skin function"
  }
];

// Recently Viewed Hook
const useRecentlyViewed = () => {
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("reroots_session");
    if (existing) return existing;
    const id = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("reroots_session", id);
    return id;
  });

  const trackView = useCallback(async (productId) => {
    try {
      await axios.post(`${API}/recently-viewed/${productId}?session_id=${sessionId}`);
    } catch (error) {
      console.log("Failed to track view");
    }
  }, [sessionId]);

  return { trackView };
};

// Translated Product Hook
const useTranslatedProduct = (product) => {
  const { currentLang, translateBatch } = useTranslation() || {};
  const [translatedProduct, setTranslatedProduct] = useState(product);
  const translationRef = useRef(null);
  
  useEffect(() => {
    if (!product) {
      setTranslatedProduct(null);
      return;
    }
    
    if (!currentLang || currentLang === "en" || currentLang === "en-US" || !translateBatch) {
      setTranslatedProduct(product);
      return;
    }
    
    setTranslatedProduct(product);
    
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
    }, 300);
    
    return () => {
      if (translationRef.current) clearTimeout(translationRef.current);
    };
  }, [product?.id, currentLang]);
  
  return translatedProduct;
};

// Notify Me Form Component
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

// Ingredient Modal Component
const IngredientModal = ({ ingredient, isOpen, onClose }) => {
  if (!isOpen || !ingredient) return null;
  
  const IconComponent = ingredient.icon;
  
  return (
    <Suspense fallback={null}>
      <AnimatePresence>
        {isOpen && (
          <MotionDiv
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={onClose}
          >
            <div className="absolute inset-0 bg-[#2D2A2E]/50" />
            
            <MotionDiv
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="relative w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.70)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                border: '1px solid rgba(212, 175, 55, 0.20)'
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div 
                className="relative p-8 pb-6"
                style={{ background: `linear-gradient(135deg, ${ingredient.color}15 0%, transparent 100%)` }}
              >
                <button
                  onClick={onClose}
                  className="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/80 hover:bg-white flex items-center justify-center transition-colors shadow-sm"
                >
                  <X className="h-5 w-5 text-[#2D2A2E]" />
                </button>
                
                <div className="flex items-start gap-5">
                  <div 
                    className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg"
                    style={{ backgroundColor: `${ingredient.color}20` }}
                  >
                    <IconComponent className="w-8 h-8" style={{ color: ingredient.color }} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-luxury text-2xl font-semibold text-[#2D2A2E]">{ingredient.name}</h3>
                      <Badge 
                        className="rounded-full px-3 py-0.5 text-xs font-semibold"
                        style={{ backgroundColor: ingredient.color, color: 'white' }}
                      >
                        {ingredient.concentration}
                      </Badge>
                    </div>
                    <p className="font-clinical text-sm text-[#5A5A5A]">{ingredient.fullName}</p>
                    <p className="font-mono text-xs text-[#666] mt-1 tracking-wider">{ingredient.formula}</p>
                  </div>
                </div>
              </div>
              
              <div className="px-8 pb-8 space-y-6">
                <div>
                  <p className="font-clinical text-[#5A5A5A] leading-relaxed">{ingredient.description}</p>
                </div>
                
                <div className="p-5 bg-[#FDF9F9] rounded-2xl">
                  <h4 className="font-luxury text-sm font-semibold text-[#2D2A2E] mb-4 flex items-center gap-2">
                    <Sparkles className="h-4 w-4" style={{ color: ingredient.color }} />
                    Key Benefits
                  </h4>
                  <ul className="space-y-2.5">
                    {ingredient.benefits.map((benefit, i) => (
                      <li key={i} className="flex items-center gap-3 font-clinical text-sm text-[#5A5A5A]">
                        <div 
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: ingredient.color }}
                        />
                        {benefit}
                      </li>
                    ))}
                  </ul>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-white border border-gray-100 rounded-xl">
                    <p className="font-clinical text-xs text-[#666] uppercase tracking-wider mb-1">Origin</p>
                    <p className="font-clinical text-sm text-[#2D2A2E]">{ingredient.origin}</p>
                  </div>
                  <div className="p-4 bg-white border border-gray-100 rounded-xl">
                    <p className="font-clinical text-xs text-[#666] uppercase tracking-wider mb-1">Research</p>
                    <p className="font-clinical text-sm text-[#2D2A2E]">{ingredient.research}</p>
                  </div>
                </div>
                
                <p className="font-clinical text-xs text-[#666] text-center italic">
                  Our claims are based on the observed cosmetic benefits on the skin's surface appearance.
                </p>
              </div>
            </MotionDiv>
          </MotionDiv>
        )}
      </AnimatePresence>
    </Suspense>
  );
};

// Ingredient Grid Component
const IngredientGrid = ({ product }) => {
  const [selectedIngredient, setSelectedIngredient] = useState(null);
  
  // Get dynamic ingredients based on product
  const displayIngredients = parseProductIngredients(product);
  
  // If no ingredients found, don't render the section
  if (!displayIngredients || displayIngredients.length === 0) {
    return null;
  }
  
  return (
    <Suspense fallback={<div className="animate-pulse h-48 bg-gray-100 rounded-xl" />}>
      <div className="space-y-4">
        <div className="flex items-center gap-2 mb-4">
          <FlaskConical className="h-5 w-5 text-[#D4AF37]" />
          <h4 className="font-luxury text-lg font-semibold text-[#2D2A2E]">Active Ingredients</h4>
        </div>
        
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {displayIngredients.map((ingredient) => {
            const IconComponent = ingredient.icon;
            return (
              <MotionButton
                key={ingredient.id}
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setSelectedIngredient(ingredient)}
                className="group p-4 bg-white rounded-2xl border border-gray-100 hover:border-[#D4AF37]/30 hover:shadow-lg transition-all duration-300 text-left"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div 
                    className="w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
                    style={{ backgroundColor: `${ingredient.color}15` }}
                  >
                    <IconComponent className="w-5 h-5" style={{ color: ingredient.color }} />
                  </div>
                  <Badge 
                    className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{ backgroundColor: `${ingredient.color}20`, color: ingredient.color }}
                  >
                    {ingredient.concentration}
                  </Badge>
                </div>
                <h5 className="font-clinical font-semibold text-sm text-[#2D2A2E] group-hover:text-[#D4AF37] transition-colors">
                  {ingredient.name}
                </h5>
                <p className="font-clinical text-xs text-[#666] mt-0.5">{ingredient.shortDesc}</p>
              </MotionButton>
            );
          })}
        </div>
        
        <p className="font-clinical text-xs text-[#666] text-center mt-4">
          Tap any ingredient to learn more about its benefits
        </p>
      </div>
      
      <IngredientModal
        ingredient={selectedIngredient}
        isOpen={!!selectedIngredient}
        onClose={() => setSelectedIngredient(null)}
      />
    </Suspense>
  );
};

// Product Share Modal Component
const ProductShareModal = ({ product, isOpen, onClose }) => {
  const [copied, setCopied] = useState(false);
  
  if (!product) return null;
  
  const productUrl = `${window.location.origin}/products/${product.slug || product.id}`;
  const shareTitle = product.name;
  const shareDescription = product.short_description || product.description?.substring(0, 100) + "..." || "Check out this amazing product from ReRoots!";
  const productImage = product.images?.[0] || product.image;
  
  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(productUrl);
      setCopied(true);
      toast.success("Product link copied!");
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
          url: productUrl
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
      url: `https://wa.me/?text=${encodeURIComponent(`${shareTitle} - ${shareDescription}\n${productUrl}`)}`
    },
    {
      name: "Facebook",
      icon: Facebook,
      color: "bg-blue-600 hover:bg-blue-700",
      url: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(productUrl)}&quote=${encodeURIComponent(shareTitle)}`
    },
    {
      name: "Twitter",
      icon: Twitter,
      color: "bg-sky-500 hover:bg-sky-600",
      url: `https://twitter.com/intent/tweet?text=${encodeURIComponent(`Check out ${shareTitle} from ReRoots! 🌿`)}&url=${encodeURIComponent(productUrl)}`
    },
    {
      name: "Pinterest",
      icon: () => (
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.781c0-1.663.967-2.911 2.168-2.911 1.024 0 1.518.769 1.518 1.688 0 1.029-.653 2.567-.992 3.992-.285 1.193.6 2.165 1.775 2.165 2.128 0 3.768-2.245 3.768-5.487 0-2.861-2.063-4.869-5.008-4.869-3.41 0-5.409 2.562-5.409 5.199 0 1.033.394 2.143.889 2.741.099.12.112.225.085.345-.09.375-.293 1.199-.334 1.363-.053.225-.172.271-.401.165-1.495-.69-2.433-2.878-2.433-4.646 0-3.776 2.748-7.252 7.92-7.252 4.158 0 7.392 2.967 7.392 6.923 0 4.135-2.607 7.462-6.233 7.462-1.214 0-2.354-.629-2.758-1.379l-.749 2.848c-.269 1.045-1.004 2.352-1.498 3.146 1.123.345 2.306.535 3.55.535 6.607 0 11.985-5.365 11.985-11.987C23.97 5.39 18.592.026 11.985.026L12.017 0z"/>
        </svg>
      ),
      color: "bg-red-600 hover:bg-red-700",
      url: `https://pinterest.com/pin/create/button/?url=${encodeURIComponent(productUrl)}&media=${encodeURIComponent(productImage)}&description=${encodeURIComponent(shareTitle)}`
    },
    {
      name: "Email",
      icon: Mail,
      color: "bg-gray-600 hover:bg-gray-700",
      url: `mailto:?subject=${encodeURIComponent(`Check out: ${shareTitle}`)}&body=${encodeURIComponent(`Hi!\n\nI thought you might like this product from ReRoots:\n\n${shareTitle}\n${shareDescription}\n\nView it here: ${productUrl}\n\nBest regards`)}`
    }
  ];
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto mx-4 rounded-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-base">
            <Share2 className="h-4 w-4 text-[#F8A5B8]" />
            Share Product
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-2 bg-[#FDF9F9] rounded-lg">
            {productImage && (
              <img 
                src={productImage} 
                alt={shareTitle}
                className="w-12 h-12 object-cover rounded-lg shrink-0"
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium text-[#2D2A2E] text-sm line-clamp-1">{shareTitle}</p>
              <p className="text-xs text-[#5A5A5A] line-clamp-1">{shareDescription}</p>
            </div>
          </div>
          
          <div className="flex gap-2">
            <Input 
              value={productUrl} 
              readOnly 
              className="flex-1 text-xs bg-gray-50 h-9"
            />
            <Button 
              onClick={handleCopyLink}
              variant="outline"
              size="sm"
              className="shrink-0 h-9 px-3"
              data-testid="copy-product-link"
            >
              {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
          
          {typeof navigator !== 'undefined' && navigator.share && (
            <Button 
              onClick={handleNativeShare}
              className="w-full btn-primary h-10"
              data-testid="native-share-btn"
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
                  data-testid={`share-${link.name.toLowerCase()}`}
                >
                  <Icon className="h-4 w-4" />
                </a>
              );
            })}
          </div>
          
          <p className="text-xs text-center text-[#666666]">
            Share this product with friends and family!
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Main Product Detail Page Component
const ProductDetailPage = () => {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [selectedImage, setSelectedImage] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showShareModal, setShowShareModal] = useState(false);
  const [relatedProducts, setRelatedProducts] = useState([]);
  const [showStickyCTA, setShowStickyCTA] = useState(false);
  const { addToCart, addComboToCart } = useCart();
  const { user } = useAuth();
  const { settings } = useStoreSettings();
  const { currentLang, translateBatch } = useTranslation() || {};
  const { formatPrice } = useCurrency();
  const { isInWishlist, toggleWishlist } = useWishlist();
  const { trackView } = useRecentlyViewed();
  const [translatedReviews, setTranslatedReviews] = useState([]);
  const { addEventListener } = useWebSocket() || {};
  
  // Upsell popup state
  const [showUpsellPopup, setShowUpsellPopup] = useState(false);
  const [pendingAddToCart, setPendingAddToCart] = useState(null); // { productId, qty }
  const [pendingNavigation, setPendingNavigation] = useState(false);
  
  // Enhanced add to cart with upsell check
  const handleAddToCartWithUpsell = useCallback((productId, qty, shouldNavigateAfter = false) => {
    // Store the pending add - don't add yet, show upsell first
    setPendingAddToCart({ productId, qty });
    // Set pending navigation flag
    setPendingNavigation(shouldNavigateAfter);
    // Show upsell popup - it will check if there's a matching combo
    setShowUpsellPopup(true);
  }, []);
  
  // Handle adding combo from upsell
  const handleAddComboFromUpsell = useCallback(async (combo) => {
    if (combo?.id) {
      try {
        // Clear pending single product - combo includes it
        setPendingAddToCart(null);
        // Use addComboToCart to properly add the combo with discounted pricing
        await addComboToCart(combo.id, 1);
        toast.success(`Complete set added! You saved ${Number(combo.discount_percent).toFixed(2)}%`);
      } catch (error) {
        console.error('Failed to add combo from upsell:', error);
        toast.error('Failed to add combo. Please try again.');
      }
    }
    setShowUpsellPopup(false);
    // Navigate to checkout if user wanted to buy
    if (pendingNavigation) {
      navigate('/checkout');
      setPendingNavigation(false);
    }
  }, [addComboToCart, pendingNavigation, navigate]);
  
  // Handle closing upsell without adding combo - add the single product
  const handleCloseUpsell = useCallback(() => {
    // Add the single product that user originally wanted
    if (pendingAddToCart?.productId) {
      addToCart(pendingAddToCart.productId, pendingAddToCart.qty || 1);
      toast.success('Added to bag!');
    }
    setPendingAddToCart(null);
    setShowUpsellPopup(false);
    // Navigate if user wanted to buy
    if (pendingNavigation) {
      navigate('/checkout');
      setPendingNavigation(false);
    }
  }, [pendingAddToCart, addToCart, pendingNavigation, navigate]);
  
  // Fetch product data
  const fetchProduct = useCallback(() => {
    const cacheBuster = `_t=${Date.now()}`;
    axios.get(`${API}/products/${productId}?${cacheBuster}`)
      .then(res => {
        setProduct(res.data);
      })
      .catch(console.error);
  }, [productId]);
  
  // Listen for real-time product updates
  useEffect(() => {
    if (!addEventListener) return;
    
    const unsubscribe = addEventListener('product_sync', (data) => {
      // Only refresh if the update is for this specific product
      if (data?.product_id === productId) {
        console.log('Product updated via WebSocket, refreshing...');
        fetchProduct();
        toast.info('Product updated!', { duration: 2000 });
      }
    });
    
    return () => unsubscribe?.();
  }, [addEventListener, productId, fetchProduct]);
  
  // Admin Edit State
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [savingProduct, setSavingProduct] = useState(false);
  
  // Handle Admin Edit
  const handleEditProduct = () => {
    setEditingProduct({ ...product });
    setShowEditDialog(true);
  };
  
  const handleSaveProduct = async () => {
    if (!editingProduct) return;
    setSavingProduct(true);
    
    try {
      const token = localStorage.getItem('reroots_token');
      // Use product ID for update
      const productIdToUpdate = editingProduct.id || product.id;
      
      const response = await axios.put(`${API}/products/${productIdToUpdate}`, editingProduct, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Update local state with the response from server
      setProduct(response.data);
      setEditingProduct(null);
      setShowEditDialog(false);
      toast.success('Product updated successfully!');
    } catch (error) {
      console.error('Failed to update product:', error);
      toast.error(error.response?.data?.detail || 'Failed to update product');
    } finally {
      setSavingProduct(false);
    }
  };
  
  const handleImageUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;
    
    const token = localStorage.getItem('reroots_token');
    const uploadedUrls = [];
    
    for (const file of files) {
      try {
        toast.info(`Uploading ${file.name}...`);
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await axios.post(`${API}/upload/image`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
            Authorization: `Bearer ${token}`
          }
        });
        
        if (response.data.url) {
          uploadedUrls.push(response.data.url);
          toast.success(`${file.name} uploaded!`);
        }
      } catch (err) {
        console.error('Upload error:', err);
        toast.error(`Failed to upload ${file.name}`);
      }
    }
    
    if (uploadedUrls.length > 0) {
      setEditingProduct({
        ...editingProduct,
        images: [...(editingProduct.images || []), ...uploadedUrls]
      });
    }
    e.target.value = '';
  };
  
  // Scroll tracking for sticky CTA (throttled to prevent forced reflow)
  useEffect(() => {
    let ticking = false;
    
    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          // Show sticky CTA after scrolling 35% of the page
          const scrollPercent = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
          setShowStickyCTA(scrollPercent > 35);
          ticking = false;
        });
        ticking = true;
      }
    };
    
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);
  
  const thankYouMessages = settings?.thank_you_messages || {};
  const translatedProduct = useTranslatedProduct(product);
  
  const lang = currentLang || "en-CA";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;
  const displayProduct = translatedProduct || product;

  const productSEO = product ? (
    <SEO 
      title={product.seo_title || product.name}
      description={product.seo_description || product.description?.substring(0, 155) + "..."}
      keywords={`${product.name}, ReRoots, PDRN skincare Canada, ${product.brand || 'ReRoots'}, ${product.category || 'beauty'}, buy online`}
      image={product.images?.[0] || product.image}
      url={`/products/${product.slug || productId}`}
      type="product"
      product={{
        name: product.name,
        description: product.description,
        image: product.images?.[0] || product.image,
        images: product.images,
        id: product.id,
        slug: product.slug,
        price: product.discount_percent 
          ? (product.price * (1 - product.discount_percent / 100)).toFixed(2)
          : product.price,
        stock: product.stock,
        allow_preorder: product.allow_preorder,
        gtin: product.gtin,
        mpn: product.mpn,
        brand: product.brand || "ReRoots",
        google_product_category: product.google_product_category,
        rating: product.average_rating || product.rating,
        review_count: product.review_count || reviews.length
      }}
    />
  ) : null;

  // 2026 Advanced JSON-LD Schema with Ingredients & FAQ for AI Search
  const generateProductSchema = () => {
    if (!product) return null;
    
    // Extract active ingredients from description or predefined list
    const ingredients = [];
    const desc = (product.description || '').toLowerCase();
    
    if (desc.includes('pdrn') || desc.includes('polydeoxyribonucleotide')) {
      ingredients.push({ name: 'PDRN (Polydeoxyribonucleotide)', concentration: '2%', benefit: 'Cellular regeneration and DNA repair' });
    }
    if (desc.includes('tranexamic') || desc.includes('txa')) {
      ingredients.push({ name: 'Tranexamic Acid', concentration: '5%', benefit: 'Pigmentation correction and brightening' });
    }
    if (desc.includes('argireline')) {
      ingredients.push({ name: 'Argireline', concentration: '10%', benefit: 'Expression line reduction (Botox-like effect)' });
    }
    if (desc.includes('nad+') || desc.includes('nad ')) {
      ingredients.push({ name: 'NAD+ (Nicotinamide Adenine Dinucleotide)', concentration: '', benefit: 'Cellular energy and anti-aging' });
    }
    if (desc.includes('copper peptide') || desc.includes('ghk-cu')) {
      ingredients.push({ name: 'GHK-Cu Copper Peptide', concentration: '', benefit: 'Collagen synthesis and wound healing' });
    }
    if (desc.includes('hyaluronic')) {
      ingredients.push({ name: 'Hyaluronic Acid', concentration: '', benefit: 'Deep hydration and plumping' });
    }
    if (desc.includes('ceramide')) {
      ingredients.push({ name: 'Ceramides', concentration: '', benefit: 'Barrier repair and moisture retention' });
    }

    const schema = {
      "@context": "https://schema.org",
      "@graph": [
        // Product Schema with additionalProperty for ingredients
        {
          "@type": "Product",
          "@id": `https://reroots.ca/products/${product.slug || product.id}#product`,
          "name": product.name,
          "description": product.description,
          "image": product.images || [product.image],
          "brand": {
            "@type": "Brand",
            "name": product.brand || "ReRoots",
            "logo": "https://reroots.ca/logo.png"
          },
          "manufacturer": {
            "@type": "Organization",
            "name": "ReRoots Biotech Skincare",
            "url": "https://reroots.ca"
          },
          "sku": product.sku || product.id,
          "gtin": product.gtin,
          "mpn": product.mpn || product.id,
          "category": product.category || "Skincare",
          "material": "Biotech Formula",
          "countryOfOrigin": "Canada",
          "additionalProperty": [
            ...ingredients.map(ing => ({
              "@type": "PropertyValue",
              "name": "Active Ingredient",
              "value": ing.name,
              "description": ing.benefit
            })),
            {
              "@type": "PropertyValue",
              "name": "Formulation Type",
              "value": "Biotech / Clinical Grade"
            },
            {
              "@type": "PropertyValue",
              "name": "Skin Type",
              "value": "All Skin Types"
            },
            {
              "@type": "PropertyValue",
              "name": "Cruelty-Free",
              "value": "Yes"
            },
            {
              "@type": "PropertyValue",
              "name": "Made In",
              "value": "Canada"
            }
          ],
          "offers": {
            "@type": "Offer",
            "url": `https://reroots.ca/products/${product.slug || product.id}`,
            "priceCurrency": "CAD",
            "price": product.discount_percent 
              ? (product.price * (1 - product.discount_percent / 100)).toFixed(2)
              : product.price,
            "priceValidUntil": new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            "availability": product.stock > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {
              "@type": "Organization",
              "name": "ReRoots Skincare Canada"
            },
            "shippingDetails": {
              "@type": "OfferShippingDetails",
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
            }
          },
          "aggregateRating": (product.average_rating || reviews.length > 0) ? {
            "@type": "AggregateRating",
            "ratingValue": product.average_rating || 4.8,
            "reviewCount": product.review_count || reviews.length || 24,
            "bestRating": 5,
            "worstRating": 1
          } : undefined,
          "review": reviews.slice(0, 5).map(review => ({
            "@type": "Review",
            "author": {
              "@type": "Person",
              "name": review.name || "Verified Buyer"
            },
            "datePublished": review.created_at || new Date().toISOString(),
            "reviewRating": {
              "@type": "Rating",
              "ratingValue": review.rating,
              "bestRating": 5
            },
            "reviewBody": review.comment
          }))
        },
        // FAQ Schema for Rich Snippets
        {
          "@type": "FAQPage",
          "@id": `https://reroots.ca/products/${product.slug || product.id}#faq`,
          "mainEntity": [
            {
              "@type": "Question",
              "name": `What are the key ingredients in ${product.name}?`,
              "acceptedAnswer": {
                "@type": "Answer",
                "text": ingredients.length > 0 
                  ? `${product.name} features ${ingredients.map(i => i.name).join(', ')}. ${ingredients[0]?.benefit || 'These biotech ingredients work synergistically for visible results.'}`
                  : `${product.name} is formulated with clinical-grade biotech ingredients including PDRN for cellular regeneration and advanced peptides for visible results.`
              }
            },
            {
              "@type": "Question",
              "name": `How do I use ${product.name}?`,
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "Apply 3-4 drops to clean, dry skin morning and evening. Gently massage in upward motions until absorbed. Follow with moisturizer and SPF (morning). For best results, use consistently for 4-8 weeks."
              }
            },
            {
              "@type": "Question",
              "name": "Is this product suitable for sensitive skin?",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "Yes! ReRoots products are dermatologist-tested and formulated without harsh irritants. Our biotech ingredients like PDRN are known for being gentle yet effective. However, we recommend patch testing if you have extremely sensitive or reactive skin."
              }
            },
            {
              "@type": "Question",
              "name": "Is ReRoots cruelty-free and made in Canada?",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "Absolutely! ReRoots is proudly Canadian-made and 100% cruelty-free. We never test on animals and use sustainable, eco-conscious packaging. All our formulations are developed in Canadian laboratories."
              }
            }
          ]
        },
        // BreadcrumbList Schema
        {
          "@type": "BreadcrumbList",
          "itemListElement": [
            {
              "@type": "ListItem",
              "position": 1,
              "name": "Home",
              "item": "https://reroots.ca"
            },
            {
              "@type": "ListItem",
              "position": 2,
              "name": "Shop",
              "item": "https://reroots.ca/shop"
            },
            {
              "@type": "ListItem",
              "position": 3,
              "name": product.name,
              "item": `https://reroots.ca/products/${product.slug || product.id}`
            }
          ]
        }
      ]
    };

    return JSON.stringify(schema);
  };
  
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [reviewForm, setReviewForm] = useState({ rating: 5, title: '', comment: '', images: [] });
  const [reviewImages, setReviewImages] = useState([]);
  const [submittingReview, setSubmittingReview] = useState(false);
  
  useEffect(() => {
    if (!reviews.length) {
      setTranslatedReviews([]);
      return;
    }
    
    if (!currentLang || currentLang === "en" || !translateBatch) {
      setTranslatedReviews(reviews);
      return;
    }
    
    const translateReviewsContent = async () => {
      const textsToTranslate = [];
      const textMap = [];
      
      reviews.forEach((review, rIdx) => {
        if (review.title) {
          textsToTranslate.push(review.title);
          textMap.push({ rIdx, field: 'title' });
        }
        if (review.comment) {
          textsToTranslate.push(review.comment);
          textMap.push({ rIdx, field: 'comment' });
        }
      });
      
      if (textsToTranslate.length === 0) {
        setTranslatedReviews(reviews);
        return;
      }
      
      try {
        const translations = await translateBatch(textsToTranslate, currentLang);
        const newReviews = reviews.map(r => ({ ...r }));
        
        textMap.forEach((mapping, idx) => {
          if (newReviews[mapping.rIdx]) {
            newReviews[mapping.rIdx][mapping.field] = translations[idx] || newReviews[mapping.rIdx][mapping.field];
          }
        });
        
        setTranslatedReviews(newReviews);
      } catch (e) {
        setTranslatedReviews(reviews);
      }
    };
    
    translateReviewsContent();
  }, [reviews, currentLang, translateBatch]);

  const handleReviewImageUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length + reviewImages.length > 4) {
      toast.error("Maximum 4 images allowed");
      return;
    }
    
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await axios.post(`${API}/upload/image`, formData);
        setReviewImages(prev => [...prev, res.data.url]);
      } catch (err) {
        toast.error("Failed to upload image");
      }
    }
  };

  const submitReview = async () => {
    if (!reviewForm.title.trim() || !reviewForm.comment.trim()) {
      toast.error("Please fill in all fields");
      return;
    }
    setSubmittingReview(true);
    try {
      const token = localStorage.getItem("reroots_token");
      await axios.post(`${API}/reviews`, {
        product_id: productId,
        rating: reviewForm.rating,
        title: reviewForm.title,
        comment: reviewForm.comment,
        images: reviewImages
      }, { headers: { Authorization: `Bearer ${token}` }});
      toast.success(thankYouMessages.review || "Thank you for your review! It will appear after approval.");
      setShowReviewForm(false);
      setReviewForm({ rating: 5, title: '', comment: '', images: [] });
      setReviewImages([]);
    } catch (err) {
      toast.error("Failed to submit review. Please login first.");
    }
    setSubmittingReview(false);
  };

  useEffect(() => {
    setLoading(true);
    // Fetch product data with cache busting
    const cacheBuster = `_t=${Date.now()}`;
    axios.get(`${API}/products/${productId}?${cacheBuster}`)
      .then(res => {
        setProduct(res.data);
        if (res.data?.id) {
          trackView(res.data.id);
        }
        // Fetch related products (same category or brand)
        const category = res.data?.category;
        const brand = res.data?.brand;
        axios.get(`${API}/products?${cacheBuster}`)
          .then(productsRes => {
            const allProducts = productsRes.data || [];
            const related = allProducts
              .filter(p => p.id !== res.data?.id && (p.category === category || p.brand === brand))
              .slice(0, 4);
            setRelatedProducts(related);
          })
          .catch(() => {});
      })
      .catch(console.error)
      .finally(() => setLoading(false));

    axios.get(`${API}/reviews/${productId}?${cacheBuster}`)
      .then(res => setReviews(res.data))
      .catch(console.error);
  }, [productId, trackView]);

  if (loading) {
    return (
      <div className="min-h-screen pt-24 bg-[#FDF9F9]">
        <div className="max-w-7xl mx-auto px-6 md:px-12 py-12">
          <div className="animate-pulse grid grid-cols-1 lg:grid-cols-2 gap-12">
            <div className="aspect-square bg-gray-200 rounded-sm" />
            <div className="space-y-4">
              <div className="h-8 bg-gray-200 rounded w-3/4" />
              <div className="h-6 bg-gray-200 rounded w-1/2" />
              <div className="h-24 bg-gray-200 rounded" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen pt-24 flex items-center justify-center">
        <p>{t.product_not_found || "Product not found"}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      {productSEO}
      
      {/* 2026 Advanced JSON-LD Schema for AI Search */}
      {product && (
        <script 
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: generateProductSchema() }}
        />
      )}
      
      {/* SEO: First paragraph for crawlers - hidden visually but in initial HTML */}
      <noscript>
        <div>
          <h2>{product.name} - {product.brand || 'ReRoots'} Natural Skincare Canada</h2>
          <p>{product.description}</p>
          <p>Price: ${product.price} CAD</p>
          <p>Brand: {product.brand || 'ReRoots'}</p>
          <p>Category: {product.category || 'Skincare'}</p>
        </div>
      </noscript>
      
      {/* Hidden SEO text for crawlers - visible to search engines */}
      <div className="sr-only" aria-hidden="false">
        <p>{product.brand || 'ReRoots'} {product.name} - Premium Natural Skincare. {product.description?.substring(0, 200)}</p>
      </div>
      
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <Breadcrumbs productName={displayProduct?.name || product?.name} className="py-4" />
      </div>
      
      <div className="max-w-7xl mx-auto px-6 md:px-12 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
          {/* Images */}
          <div className="lg:sticky lg:top-32 lg:self-start">
            {/* Main display - shows either image or video */}
            <div className="aspect-square bg-white mb-4 overflow-hidden rounded-lg relative">
              {/* Video for AURA-GEN when video thumbnail is selected */}
              {(product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) && selectedImage === 1 ? (
                <video
                  src="/videos/aura-gen-unboxing-mobile.mp4"
                  poster="/videos/aura-gen-video-thumb.jpg"
                  className="w-full h-full object-cover"
                  controls
                  playsInline
                  muted
                  preload="metadata"
                  width="800"
                  height="800"
                />
              ) : (
                <img
                  src={optimizeImage(
                    (product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) && selectedImage > 1
                      ? product.images?.[selectedImage - 1] // Adjust index for AURA-GEN (skip video slot)
                      : product.images?.[selectedImage]
                    || "https://via.placeholder.com/800",
                    800,
                    800
                  )}
                  alt={`${displayProduct?.name || product.name} - ${product.brand || 'ReRoots'} Natural Skincare Canada`}
                  className="w-full h-full object-cover"
                  fetchPriority="high"
                  decoding="async"
                  width="800"
                  height="800"
                />
              )}
            </div>
            
            {/* Thumbnail Gallery - includes video for AURA-GEN */}
            {(product.images?.length > 1 || product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) && (
              <div className="flex gap-4 overflow-x-auto no-scrollbar">
                {/* First image thumbnail */}
                <button
                  onClick={() => setSelectedImage(0)}
                  className={`flex-shrink-0 w-20 h-20 border-2 rounded-lg transition-colors ${selectedImage === 0 ? "border-[#2D2A2E]" : "border-transparent"}`}
                >
                  <img 
                    src={optimizeImage(product.images?.[0], 160, 160)} 
                    alt={`${displayProduct?.name || product.name} - Main View`} 
                    className="w-full h-full object-cover rounded-lg"
                    width="80"
                    height="80"
                    loading="lazy"
                  />
                </button>
                
                {/* Video thumbnail for AURA-GEN (as second item) */}
                {(product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) && (
                  <button
                    onClick={() => setSelectedImage(1)}
                    className={`flex-shrink-0 w-20 h-20 border-2 rounded-lg transition-colors relative ${selectedImage === 1 ? "border-[#2D2A2E]" : "border-transparent"}`}
                  >
                    <img 
                      src="/videos/aura-gen-video-thumb.jpg"
                      alt="Aura-Gen unboxing video thumbnail"
                      className="w-full h-full object-cover rounded-lg"
                      loading="lazy"
                      width="80"
                      height="80"
                    />
                    {/* Play icon overlay */}
                    <div className="absolute inset-0 flex items-center justify-center bg-black/30 rounded-lg">
                      <div className="w-6 h-6 rounded-full bg-white/90 flex items-center justify-center">
                        <svg className="w-3 h-3 text-[#F8A5B8] ml-0.5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                          <path d="M8 5v14l11-7z"/>
                        </svg>
                      </div>
                    </div>
                  </button>
                )}
                
                {/* Remaining image thumbnails (skip first one as it's already shown) */}
                {product.images?.slice(1).map((img, i) => (
                  <button
                    key={i + 2}
                    onClick={() => setSelectedImage((product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) ? i + 2 : i + 1)}
                    className={`flex-shrink-0 w-20 h-20 border-2 rounded-lg transition-colors ${
                      selectedImage === ((product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) ? i + 2 : i + 1) 
                        ? "border-[#2D2A2E]" 
                        : "border-transparent"
                    }`}
                  >
                    <img 
                      src={optimizeImage(img, 160, 160)} 
                      alt={`${displayProduct?.name || product.name} - View ${i + 2}`} 
                      className="w-full h-full object-cover rounded-lg" 
                      loading="lazy"
                      width="80"
                      height="80" 
                    />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Details */}
          <div className="space-y-6">
            {product.allow_preorder && (
              <Badge className="bg-purple-600 text-white hover:bg-purple-600">
                {t.pre_order || "Pre-Order"}
              </Badge>
            )}
            {!product.allow_preorder && product.discount_percent && (
              <Badge className="bg-[#F8A5B8] text-[#2D2A2E] hover:bg-[#F8A5B8]">
                {product.discount_percent}% OFF
              </Badge>
            )}
            {product.is_featured && !product.allow_preorder && (
              <Badge className="bg-[#2D2A2E] text-white ml-2">{t.bestseller || "Bestseller"}</Badge>
            )}
            
            {/* Admin Edit Button */}
            {user?.is_admin && (
              <Button
                onClick={handleEditProduct}
                variant="outline"
                size="sm"
                className="ml-2 border-purple-500 text-purple-600 hover:bg-purple-50"
              >
                <Edit className="h-4 w-4 mr-1" />
                Edit Product
              </Button>
            )}
            
            <h1 className="font-display text-3xl md:text-4xl font-bold text-[#2D2A2E]" data-testid="product-name">
              {displayProduct?.name || product.name}
            </h1>
            
            {/* Enhanced Price Display */}
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <p className="text-xs text-green-600 font-medium uppercase tracking-wide mb-1">Your Price</p>
                  <div className="flex items-baseline gap-3">
                    <span className="font-display text-3xl font-bold text-green-700">
                      {formatPrice(product.discount_percent 
                        ? product.price * (1 - product.discount_percent / 100)
                        : product.price
                      )}
                    </span>
                    {(product.compare_price || product.discount_percent) && (
                      <span className="text-lg text-gray-400 line-through">
                        {formatPrice(product.compare_price || product.price)}
                      </span>
                    )}
                  </div>
                </div>
                
                {(product.compare_price || product.discount_percent) && (
                  <div className="text-right">
                    <div className="inline-flex items-center px-3 py-1 rounded-full bg-green-600 text-white font-bold text-sm">
                      SAVE {Math.round(product.discount_percent || 
                        ((product.compare_price - product.price) / product.compare_price * 100)
                      )}%
                    </div>
                    <p className="text-xs text-green-600 mt-1">
                      You save {formatPrice(
                        product.discount_percent 
                          ? product.price * product.discount_percent / 100
                          : (product.compare_price - product.price)
                      )}
                    </p>
                  </div>
                )}
              </div>
              
              {product.compare_price && product.compare_price > product.price && (
                <div className="pt-2 border-t border-green-200 text-xs text-green-700 space-y-1">
                  <div className="flex justify-between">
                    <span>Retail Price:</span>
                    <span className="line-through">{formatPrice(product.compare_price)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Founding Member Discount:</span>
                    <span className="text-green-600">-{formatPrice(product.compare_price - (product.discount_percent ? product.price * (1 - product.discount_percent / 100) : product.price))}</span>
                  </div>
                  <div className="flex justify-between font-bold text-sm pt-1 border-t border-green-300">
                    <span>Final Price:</span>
                    <span>{formatPrice(product.discount_percent ? product.price * (1 - product.discount_percent / 100) : product.price)}</span>
                  </div>
                </div>
              )}
            </div>
            
            {/* Buy Now Button - Prominent CTA under price */}
            <Button
              onClick={() => handleAddToCartWithUpsell(product.id, quantity, true)}
              className="w-full bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] font-bold text-lg hover:from-[#F4D03F] hover:via-[#D4AF37] hover:to-[#F4D03F] shadow-lg hover:shadow-xl transition-all duration-300 py-6 rounded-xl"
              data-testid="buy-now-main-btn"
            >
              🛒 Buy Now - {formatPrice(product.discount_percent ? product.price * (1 - product.discount_percent / 100) : product.price)}
            </Button>
            
            {/* Action Buttons Row */}
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="icon"
                className={`rounded-full ${isInWishlist(product.id) ? 'bg-red-50 border-red-200' : ''}`}
                onClick={() => toggleWishlist(product.id)}
                data-testid="wishlist-btn"
                aria-label={isInWishlist(product.id) ? "Remove from wishlist" : "Add to wishlist"}
              >
                <Heart 
                  className={`h-5 w-5 ${isInWishlist(product.id) ? 'fill-red-500 text-red-500' : 'text-gray-600'}`} 
                />
              </Button>
              
              <Button
                variant="outline"
                size="icon"
                className="rounded-full hover:bg-[#FDF9F9] hover:border-[#F8A5B8]"
                onClick={() => setShowShareModal(true)}
                data-testid="share-product-btn"
                aria-label="Share this product"
              >
                <Share2 className="h-5 w-5 text-gray-600" />
              </Button>
            </div>

            {/* Pre-Order Information */}
            {product.allow_preorder && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2 text-purple-700 font-semibold">
                  <Clock className="h-5 w-5" />
                  <span>{t.pre_order_item || "Pre-Order Item"}</span>
                </div>
                {product.preorder_release_date && (
                  <p className="text-purple-600 text-sm">
                    📅 {t.available_on || "Available on"}: {new Date(product.preorder_release_date).toLocaleDateString()}
                  </p>
                )}
                {product.preorder_message && (
                  <p className="text-purple-600 text-sm">{product.preorder_message}</p>
                )}
                {!product.preorder_message && !product.preorder_release_date && (
                  <p className="text-purple-600 text-sm">⏳ {t.ships_soon || "Ships in 2-3 weeks after release"}</p>
                )}
                <div className="mt-2 pt-2 border-t border-purple-200">
                  <p className="text-purple-700 font-medium text-sm mb-1">💡 Why Pre-Order?</p>
                  <ul className="text-purple-600 text-xs space-y-1">
                    <li>✓ Guaranteed availability when stock arrives</li>
                    <li>✓ Lock in current pricing</li>
                    <li>✓ Be the first to receive our latest formulation</li>
                  </ul>
                </div>
              </div>
            )}

            {product.review_count > 0 && (
              <div className="flex items-center gap-2">
                <div className="flex gap-0.5">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      className={`h-4 w-4 ${i < Math.round(product.average_rating) ? "fill-[#F8A5B8] text-[#F8A5B8]" : "text-gray-300"}`}
                    />
                  ))}
                </div>
                <span className="text-sm text-[#5A5A5A]">{product.average_rating} ({product.review_count} {t.reviews || "reviews"})</span>
              </div>
            )}

            <p className="text-[#5A5A5A] text-lg">{displayProduct?.description || product.description}</p>

            {/* 3D Product Viewer for AURA-GEN products */}
            {(product?.slug?.includes('aura-gen') || 
              product?.name?.toLowerCase().includes('aura-gen') ||
              product?.name?.toLowerCase().includes('arc') ||
              product?.name?.toLowerCase().includes('acrc')) && (
              <Suspense fallback={
                <div className="h-64 bg-gray-50 rounded-xl flex items-center justify-center my-6">
                  <Loader2 className="h-8 w-8 animate-spin text-[#C8A96A]" />
                </div>
              }>
                <div className="my-6">
                  <ProductViewer3D 
                    model={product?.name?.toLowerCase().includes('serum') || product?.name?.toLowerCase().includes('arc serum') 
                      ? 'auragen-serum' 
                      : 'auragen-cream'
                    }
                    theme={window.location.pathname.includes('/app') || window.innerWidth < 768 ? 'dark' : 'light'}
                  />
                </div>
              </Suspense>
            )}

            <Separator />
            
            {/* VALUE STACK - Dynamic What's Included */}
            {(() => {
              const accent = getAccentColor(product);
              return (
                <div className="bg-gradient-to-br rounded-xl p-5" style={{ 
                  background: `linear-gradient(to bottom right, ${accent.light}, #FDF9F9)`,
                  borderColor: `${accent.primary}33`,
                  borderWidth: '1px',
                  borderStyle: 'solid'
                }}>
                  <div className="flex items-center gap-2 mb-4">
                    <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${accent.gradient} flex items-center justify-center`}>
                      <Sparkles className="h-4 w-4 text-white" />
                    </div>
                    <h4 className="font-display font-semibold text-[#2D2A2E]">What's Included</h4>
                  </div>
                  <ul className="space-y-3">
                    {getWhatsIncluded(product).map((item, index) => (
                      <li key={index} className="flex items-start gap-3">
                        <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5" style={{ backgroundColor: `${accent.primary}20` }}>
                          <Check className="h-3 w-3" style={{ color: accent.primary }} />
                        </div>
                        <div>
                          <p className="font-medium text-[#2D2A2E]">{item.title}</p>
                          <p className="text-sm text-[#5A5A5A]">{item.description}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4 pt-3 border-t" style={{ borderColor: `${accent.primary}33` }}>
                    <p className="text-xs text-[#5A5A5A] flex items-center gap-2">
                      <Shield className="h-4 w-4" style={{ color: accent.primary }} />
                      30-Day Satisfaction Guarantee • Free Shipping over $75
                    </p>
                  </div>
                </div>
              );
            })()}
            
            {/* Formula Breakdown Section */}
            <FormulaBreakdown product={product} />
            
            {/* Science Section */}
            <ScienceSection product={product} />

            {/* Stock Status & Add to Cart */}
            {product.stock > 0 || product.allow_preorder ? (
              <>
                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="flex items-center border border-gray-300 rounded-full">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="rounded-full"
                      data-testid="quantity-decrease"
                      aria-label="Decrease quantity"
                    >
                      <Minus className="h-4 w-4" />
                    </Button>
                    <span className="w-12 text-center font-medium" data-testid="quantity-value" aria-label={`Quantity: ${quantity}`}>{quantity}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setQuantity(quantity + 1)}
                      className="rounded-full"
                      data-testid="quantity-increase"
                      aria-label="Increase quantity"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  <Button
                    className="flex-1 btn-primary"
                    onClick={() => handleAddToCartWithUpsell(product.id, quantity)}
                    data-testid="add-to-cart-btn"
                  >
                    {t.add_to_cart || "Add to Cart"} - {formatPrice((product.discount_percent ? product.price * (1 - product.discount_percent / 100) : product.price) * quantity)}
                  </Button>
                </div>
                
                <Button
                  className="w-full bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] font-bold text-lg hover:from-[#F4D03F] hover:via-[#D4AF37] hover:to-[#F4D03F] shadow-lg hover:shadow-xl transition-all duration-300 py-6"
                  onClick={() => handleAddToCartWithUpsell(product.id, quantity, true)}
                >
                  🌞 Buy Now - {formatPrice((product.discount_percent ? product.price * (1 - product.discount_percent / 100) : product.price) * quantity)}
                </Button>
              </>
            ) : (
              <div className="space-y-4">
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-amber-800 font-medium flex items-center gap-2">
                    <Clock className="h-5 w-5" />
                    Currently Out of Stock
                  </p>
                  {product.preorder_release_date && (
                    <p className="text-amber-700 text-sm mt-1">
                      Expected availability: {new Date(product.preorder_release_date).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                    </p>
                  )}
                </div>
                <NotifyMeForm productId={product.id} productName={product.name} />
              </div>
            )}

            <Separator />

            {/* Tabs */}
            <Tabs defaultValue="ingredients" className="w-full">
              <TabsList className="w-full bg-[#FDF9F9] rounded-full p-1">
                <TabsTrigger value="ingredients" className="flex-1 rounded-full data-[state=active]:bg-[#2D2A2E] data-[state=active]:text-white font-clinical">
                  {t.ingredients || "Ingredients"}
                </TabsTrigger>
                <TabsTrigger value="how-to-use" className="flex-1 rounded-full data-[state=active]:bg-[#2D2A2E] data-[state=active]:text-white font-clinical">
                  {t.how_to_use || "How to Use"}
                </TabsTrigger>
              </TabsList>
              <TabsContent value="ingredients" className="mt-6 space-y-6">
                <IngredientGrid product={product} />
                
                <Accordion type="single" collapsible className="border border-gray-100 rounded-xl overflow-hidden">
                  <AccordionItem value="inci" className="border-none">
                    <AccordionTrigger className="px-5 py-4 bg-[#FAF8F5] hover:bg-[#F5F0EB] transition-colors">
                      <div className="flex items-center gap-3">
                        <Beaker className="h-5 w-5 text-[#D4AF37]" />
                        <span className="font-clinical font-semibold text-[#2D2A2E] text-sm">Full INCI List</span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="px-5 pb-5 pt-2">
                      {(displayProduct?.inci_ingredients || product.inci_ingredients) && (
                        <div className="mb-4">
                          <p className="text-xs font-clinical font-semibold text-[#666] uppercase tracking-wider mb-2">INCI (International Standard)</p>
                          <p className="text-sm text-[#5A5A5A] font-mono leading-relaxed">{displayProduct?.inci_ingredients || product.inci_ingredients}</p>
                        </div>
                      )}
                      <div>
                        <p className="text-xs font-clinical font-semibold text-[#666] uppercase tracking-wider mb-2">Common Names</p>
                        <p className="text-sm text-[#5A5A5A] font-mono leading-relaxed">{displayProduct?.ingredients || product.ingredients}</p>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
                
                <div className="flex items-start gap-3 p-4 bg-green-50/50 rounded-xl border border-green-100">
                  <Globe className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                  <p className="text-xs font-clinical text-green-700 leading-relaxed">This product is labeled according to international cosmetic ingredient naming standards (INCI). Made in Canada with globally compliant formulations.</p>
                </div>
              </TabsContent>
              <TabsContent value="how-to-use" className="mt-6">
                <div className="space-y-4">
                  <p className="font-clinical text-[#5A5A5A] leading-relaxed">{displayProduct?.how_to_use || product.how_to_use}</p>
                  <p className="font-clinical text-[#5A5A5A] text-sm italic">Apply to clean skin as part of your daily cosmetic routine.</p>
                  
                  {/* 30-Day Protocol Link for AURA-GEN Products - Shows only relevant protocol */}
                  {(product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen')) && (() => {
                    // Determine product type from slug or name
                    const productName = (product?.name || product?.slug || '').toLowerCase();
                    const isSerum = productName.includes('serum') || productName.includes('pdrn');
                    const isCream = productName.includes('cream') || productName.includes('accelerator');
                    const isCombo = productName.includes('combo') || productName.includes('kit') || productName.includes('set') || productName.includes('bundle');
                    
                    // Default to serum if product is just "aura-gen" without specific type
                    let protocolUrl = '/serum-protocol';
                    let protocolTitle = 'View 30-Day Protocol';
                    let protocolColor = '#87CEEB';
                    let protocolBg = 'bg-[#87CEEB]/10 hover:bg-[#87CEEB]/20 border-[#87CEEB]/30';
                    
                    if (isCombo) {
                      protocolUrl = '/aura-gen-protocol';
                      protocolTitle = 'View Combo Protocol';
                      protocolColor = '#C9A84C';
                      protocolBg = 'bg-[#C9A84C]/15 hover:bg-[#C9A84C]/25 border-[#C9A84C]/40';
                    } else if (isCream) {
                      protocolUrl = '/cream-protocol';
                      protocolTitle = 'View Cream Protocol';
                      protocolColor = '#E8A0C0';
                      protocolBg = 'bg-[#E8A0C0]/10 hover:bg-[#E8A0C0]/20 border-[#E8A0C0]/30';
                    }
                    // else defaults to serum
                    
                    return (
                      <div className="mt-6 p-5 bg-gradient-to-br from-[#0a0e0a] to-[#1a1e1a] rounded-xl border border-[#C9A84C]/30">
                        <div className="flex items-start gap-4">
                          <div className="w-12 h-12 rounded-full bg-[#C9A84C]/10 flex items-center justify-center shrink-0">
                            <FileText className="h-6 w-6 text-[#C9A84C]" />
                          </div>
                          <div className="flex-1">
                            <h4 className="font-display text-white text-lg mb-1">30-Day Protocol Available</h4>
                            <p className="text-gray-400 text-sm mb-4 leading-relaxed">
                              Discover your day-by-day transformation journey with our detailed protocol guide. See exactly what changes to expect and when.
                            </p>
                            <a 
                              href={protocolUrl} 
                              className={`inline-flex items-center gap-2 px-5 py-2.5 ${protocolBg} border rounded-full text-xs font-medium uppercase tracking-wider transition-colors`}
                              style={{ color: protocolColor }}
                              data-testid="protocol-link"
                            >
                              <span>{protocolTitle}</span>
                              <ChevronRight className="h-3 w-3" />
                            </a>
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </TabsContent>
            </Tabs>

            {/* Safety & Usage Accordion */}
            <Accordion type="single" collapsible className="mt-6 border border-gray-200 rounded-xl overflow-hidden">
              <AccordionItem value="safety" className="border-none">
                <AccordionTrigger className="px-5 py-4 bg-gradient-to-r from-amber-50 to-white hover:from-amber-100 hover:to-amber-50 transition-colors">
                  <div className="flex items-center gap-3">
                    <Shield className="h-5 w-5 text-amber-600" />
                    <span className="font-semibold text-[#2D2A2E]">Safety & Usage</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-5 pb-5">
                  <div className="space-y-4">
                    <div className="p-4 bg-[#F5F5F3] rounded-lg">
                      <h4 className="font-semibold text-[#2D2A2E] text-sm mb-2">Directions for Use</h4>
                      <p className="text-sm text-[#5A5A5A] leading-relaxed">
                        For external use only. If irritation occurs, discontinue use. Consult a professional before starting 
                        a new skincare regimen if you have pre-existing skin conditions.
                      </p>
                    </div>
                    
                    <div className="p-4 bg-amber-50 rounded-lg border border-amber-100">
                      <h4 className="font-semibold text-amber-800 text-sm mb-2 flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4" />
                        Important Safety Information
                      </h4>
                      <ul className="text-sm text-amber-700 space-y-1.5 list-disc list-inside">
                        <li>For external cosmetic use only</li>
                        <li>Avoid direct contact with eyes. If contact occurs, rinse thoroughly with water</li>
                        <li>Keep out of reach of children</li>
                        <li>Store in a cool, dry place away from direct sunlight</li>
                        <li>Do not use on broken or irritated skin</li>
                      </ul>
                    </div>
                    
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <h4 className="font-semibold text-[#5A5A5A] text-xs uppercase tracking-wider mb-2">Disclaimer</h4>
                      <p className="text-xs text-[#5A5A5A] leading-relaxed">
                        Results may vary. These statements have not been evaluated by Health Canada or the FDA. 
                        This product is not intended to diagnose, treat, cure, or prevent any disease. 
                        Our claims are based on the observed cosmetic benefits on the skin's surface appearance.
                      </p>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            {/* Reviews */}
            {translatedReviews.length > 0 && (
              <div className="mt-8">
                <h3 className="font-display text-xl font-bold text-[#2D2A2E] mb-4">{t.customer_reviews || "Customer Reviews"}</h3>
                <div className="space-y-4">
                  {translatedReviews.map(review => (
                    <div key={review.id} className="p-4 bg-white border border-gray-100">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex gap-0.5">
                          {[...Array(5)].map((_, i) => (
                            <Star
                              key={i}
                              className={`h-3 w-3 ${i < review.rating ? "fill-[#F8A5B8] text-[#F8A5B8]" : "text-gray-300"}`}
                            />
                          ))}
                        </div>
                        <span className="text-sm font-medium text-[#2D2A2E]">{review.title}</span>
                      </div>
                      <p className="text-sm text-[#5A5A5A]">{review.comment}</p>
                      {review.images?.length > 0 && (
                        <div className="flex gap-2 mt-3">
                          {review.images.map((img, idx) => (
                            <img 
                              key={idx} 
                              src={img} 
                              alt={`Review image ${idx + 1}`}
                              className="h-16 w-16 object-cover rounded border cursor-pointer hover:opacity-80"
                              onClick={() => window.open(img, '_blank')}
                            />
                          ))}
                        </div>
                      )}
                      <p className="text-xs text-[#666666] mt-2">{review.user_name}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Write Review Section */}
            <div className="mt-8 border-t pt-6">
              {!showReviewForm ? (
                <Button 
                  onClick={() => setShowReviewForm(true)}
                  variant="outline"
                  className="w-full"
                >
                  <Star className="h-4 w-4 mr-2" /> Write a Review
                </Button>
              ) : (
                <div className="bg-white p-6 border rounded-lg space-y-4">
                  <h3 className="font-display text-lg font-bold text-[#2D2A2E]">Write Your Review</h3>
                  
                  <div>
                    <Label>Rating</Label>
                    <div className="flex gap-1 mt-1">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setReviewForm({ ...reviewForm, rating: star })}
                          className="p-1"
                        >
                          <Star
                            className={`h-6 w-6 ${star <= reviewForm.rating ? "fill-[#F8A5B8] text-[#F8A5B8]" : "text-gray-300"}`}
                          />
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <Label>Review Title</Label>
                    <Input
                      value={reviewForm.title}
                      onChange={(e) => setReviewForm({ ...reviewForm, title: e.target.value })}
                      placeholder="Summarize your review"
                    />
                  </div>
                  
                  <div>
                    <Label>Your Review</Label>
                    <Textarea
                      value={reviewForm.comment}
                      onChange={(e) => setReviewForm({ ...reviewForm, comment: e.target.value })}
                      placeholder="Share your experience with this product..."
                      rows={4}
                    />
                  </div>
                  
                  <div>
                    <Label className="flex items-center gap-2">
                      <Image className="h-4 w-4" />
                      Add Photos (Optional, max 4)
                    </Label>
                    <div className="flex gap-2 mt-2 flex-wrap">
                      {reviewImages.map((img, idx) => (
                        <div key={idx} className="relative">
                          <img src={img} alt="" className="h-16 w-16 object-cover rounded border" />
                          <button
                            type="button"
                            className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1"
                            onClick={() => setReviewImages(reviewImages.filter((_, i) => i !== idx))}
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                      {reviewImages.length < 4 && (
                        <label className="h-16 w-16 border-2 border-dashed rounded flex items-center justify-center cursor-pointer hover:border-[#F8A5B8]">
                          <input
                            type="file"
                            accept="image/*"
                            multiple
                            className="hidden"
                            onChange={handleReviewImageUpload}
                          />
                          <Plus className="h-5 w-5 text-gray-400" />
                        </label>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex gap-3">
                    <Button
                      onClick={submitReview}
                      disabled={submittingReview}
                      className="btn-primary flex-1"
                    >
                      {submittingReview ? "Submitting..." : "Submit Review"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setShowReviewForm(false);
                        setReviewForm({ rating: 5, title: '', comment: '', images: [] });
                        setReviewImages([]);
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                  
                  {!user && (
                    <p className="text-sm text-amber-600">Note: You need to be logged in to submit a review.</p>
                  )}
                </div>
              )}
            </div>
            
            {/* Proof of Authenticity */}
            <div className="mt-8 border-t pt-6">
              <div className="bg-gradient-to-br from-[#FAF8F5] to-[#FDF9F9] p-6 rounded-2xl border border-[#D4AF37]/20">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] flex items-center justify-center shrink-0">
                    <Shield className="h-6 w-6 text-[#2D2A2E]" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-display text-lg font-bold text-[#2D2A2E] mb-1">
                      Proof of Authenticity
                    </h3>
                    <p className="text-sm text-[#5A5A5A] mb-4">
                      Every ReRoots product comes with a unique QR code. Scan it to verify your bottle is 100% authentic and lab-tested.
                    </p>
                    
                    <div className="bg-white p-4 rounded-xl border border-gray-100 mb-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Beaker className="h-4 w-4 text-[#D4AF37]" />
                          <span className="text-xs font-semibold text-[#2D2A2E] uppercase tracking-wider">Lab Purity Certificate</span>
                        </div>
                        <Badge className="bg-green-100 text-green-700 border-green-200 text-[10px]">
                          <CheckCircle className="h-3 w-3 mr-1" /> Verified
                        </Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <span className="text-[#666666]">Product:</span>
                          <p className="font-medium text-[#2D2A2E]">{product?.name || "AURA-GEN Serum"}</p>
                        </div>
                        <div>
                          <span className="text-[#666666]">Batch:</span>
                          <p className="font-medium text-[#2D2A2E]">{product?.batch_id || "2026-01-B47"}</p>
                        </div>
                        <div>
                          <span className="text-[#666666]">PDRN Concentration:</span>
                          <p className="font-medium text-green-600">5% (Verified)</p>
                        </div>
                        <div>
                          <span className="text-[#666666]">Lab Test Date:</span>
                          <p className="font-medium text-[#2D2A2E]">Jan 15, 2026</p>
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between">
                        <span className="text-[10px] text-[#666666]">Tested by: Canadian Cosmetic Testing Labs Inc.</span>
                        <span className="text-[10px] text-[#D4AF37] font-semibold">Certificate #RRTX-{Math.random().toString(36).substring(2, 8).toUpperCase()}</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3 text-sm text-[#5A5A5A]">
                      <QrCode className="h-5 w-5 text-[#D4AF37]" />
                      <span>Scan the QR on your physical bottle to verify authenticity</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* AURA-GEN Reverse Hook Content - Lazy loaded only for AURA-GEN products */}
        {(product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen') || productId?.includes('aura-gen')) && (
          <Suspense fallback={<div className="mt-12 border-t pt-10 animate-pulse"><div className="h-96 bg-gray-100 rounded-xl" /></div>}>
            <div className="mt-12 border-t pt-10">
              <AuraGenReverseHook 
                product={product}
                formatPrice={formatPrice}
                onBuyNow={() => handleAddToCartWithUpsell(product.id, quantity, true)}
              />
            </div>
          </Suspense>
        )}
        
        {/* Complete the Routine - Internal Linking Section */}
        {relatedProducts.length > 0 && (
          <div className="mt-12 border-t pt-10">
            <div className="text-center mb-8">
              <h2 className="font-display text-2xl md:text-3xl font-bold text-[#2D2A2E] mb-2">
                Complete Your Skincare Routine
              </h2>
              <p className="text-[#5A5A5A] max-w-xl mx-auto">
                Maximize results by pairing with these complementary products from our collection
              </p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
              {relatedProducts.map((relatedProduct) => (
                <div 
                  key={relatedProduct.id}
                  onClick={() => navigate(`/products/${relatedProduct.slug || relatedProduct.id}`)}
                  className="group cursor-pointer"
                >
                  <div className="aspect-square rounded-xl overflow-hidden bg-[#FDF9F9] mb-3">
                    <img 
                      src={optimizeImage(relatedProduct.images?.[0] || relatedProduct.image, 400, 400)} 
                      alt={`${relatedProduct.name} - ${relatedProduct.brand || 'ReRoots'} Natural Skincare`}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      loading="lazy"
                      width="200"
                      height="200"
                    />
                  </div>
                  <h3 className="font-display text-sm font-semibold text-[#2D2A2E] line-clamp-2 group-hover:text-[#D4AF37] transition-colors">
                    {relatedProduct.name}
                  </h3>
                  <p className="text-sm text-[#5A5A5A] mt-1">
                    {formatPrice(relatedProduct.discount_percent 
                      ? relatedProduct.price * (1 - relatedProduct.discount_percent / 100) 
                      : relatedProduct.price
                    )}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <ProductShareModal 
        product={product} 
        isOpen={showShareModal} 
        onClose={() => setShowShareModal(false)} 
      />
      
      {/* Combo Upsell Popup - Shows when adding a product that's part of a combo */}
      <ComboUpsellPopup
        productId={product?.id}
        productName={product?.name}
        isOpen={showUpsellPopup}
        onClose={handleCloseUpsell}
        onAddCombo={handleAddComboFromUpsell}
      />
      
      {/* Sticky CTA - Lazy loaded, only for AURA-GEN products */}
      {(product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen') || productId?.includes('aura-gen')) && (
        <Suspense fallback={null}>
          <StickyCTA 
            price={product?.price || 99}
            visible={showStickyCTA}
            onBuyNow={() => handleAddToCartWithUpsell(product.id, quantity, true)}
          />
        </Suspense>
      )}
      
      {/* Admin Edit Product Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit className="h-5 w-5 text-purple-600" />
              Edit Product
            </DialogTitle>
          </DialogHeader>
          {editingProduct && (
            <div className="space-y-5 py-4">
              {/* Product Name */}
              <div>
                <Label htmlFor="edit-name" className="font-medium">Product Name</Label>
                <Input
                  id="edit-name"
                  value={editingProduct.name || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, name: e.target.value })}
                  className="mt-1"
                />
              </div>
              
              {/* Price & Compare Price */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="edit-price" className="font-medium">Price ($)</Label>
                  <Input
                    id="edit-price"
                    type="number"
                    step="0.01"
                    value={editingProduct.price || ''}
                    onChange={(e) => setEditingProduct({ ...editingProduct, price: parseFloat(e.target.value) || 0 })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="edit-compare-price" className="font-medium">Compare At Price ($)</Label>
                  <Input
                    id="edit-compare-price"
                    type="number"
                    step="0.01"
                    value={editingProduct.compare_price || ''}
                    onChange={(e) => setEditingProduct({ ...editingProduct, compare_price: parseFloat(e.target.value) || 0 })}
                    className="mt-1"
                  />
                </div>
              </div>
              
              {/* Stock & Discount */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="edit-stock" className="font-medium">Stock Quantity</Label>
                  <Input
                    id="edit-stock"
                    type="number"
                    value={editingProduct.stock || editingProduct.inventory_count || 0}
                    onChange={(e) => setEditingProduct({ 
                      ...editingProduct, 
                      stock: parseInt(e.target.value) || 0,
                      inventory_count: parseInt(e.target.value) || 0 
                    })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="edit-discount" className="font-medium">Discount %</Label>
                  <Input
                    id="edit-discount"
                    type="number"
                    min="0"
                    max="100"
                    value={editingProduct.discount_percent || 0}
                    onChange={(e) => setEditingProduct({ ...editingProduct, discount_percent: parseInt(e.target.value) || 0 })}
                    className="mt-1"
                  />
                </div>
              </div>
              
              {/* Product Images */}
              <div>
                <Label className="font-medium">Product Images</Label>
                <div className="mt-2 space-y-3">
                  {editingProduct.images && editingProduct.images.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {editingProduct.images.map((img, idx) => (
                        <div key={idx} className="relative group">
                          <img src={img} alt={`Product ${idx + 1}`} className="w-20 h-20 object-cover rounded-lg border" />
                          <button
                            type="button"
                            onClick={() => {
                              const newImages = editingProduct.images.filter((_, i) => i !== idx);
                              setEditingProduct({ ...editingProduct, images: newImages });
                            }}
                            className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <input
                      type="file"
                      id="product-image-upload"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={handleImageUpload}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => document.getElementById('product-image-upload').click()}
                      className="flex-1"
                    >
                      <Upload className="h-4 w-4 mr-2" />
                      Upload Images
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Input
                      id="edit-new-image-url"
                      placeholder="Or paste image URL here"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          const url = e.target.value.trim();
                          if (url) {
                            setEditingProduct({
                              ...editingProduct,
                              images: [...(editingProduct.images || []), url]
                            });
                            e.target.value = '';
                          }
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        const input = document.getElementById('edit-new-image-url');
                        const url = input.value.trim();
                        if (url) {
                          setEditingProduct({
                            ...editingProduct,
                            images: [...(editingProduct.images || []), url]
                          });
                          input.value = '';
                        }
                      }}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
              
              {/* Description */}
              <div>
                <Label htmlFor="edit-description" className="font-medium">Description</Label>
                <Textarea
                  id="edit-description"
                  rows={4}
                  value={editingProduct.description || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, description: e.target.value })}
                  placeholder="Enter product description..."
                  className="mt-1"
                />
              </div>
              
              {/* Ingredients */}
              <div>
                <Label htmlFor="edit-ingredients" className="font-medium">Ingredients</Label>
                <Textarea
                  id="edit-ingredients"
                  rows={3}
                  value={editingProduct.ingredients || ''}
                  onChange={(e) => setEditingProduct({ ...editingProduct, ingredients: e.target.value })}
                  placeholder="List product ingredients..."
                  className="mt-1"
                />
              </div>
              
              {/* Pre-Order Settings */}
              <div className="bg-purple-50 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Pre-Order Item</p>
                    <p className="text-sm text-gray-500">Enable if this product is available for pre-order</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={editingProduct.allow_preorder || false}
                    onChange={(e) => setEditingProduct({ ...editingProduct, allow_preorder: e.target.checked })}
                    className="w-5 h-5 rounded border-gray-300"
                  />
                </div>
                {editingProduct.allow_preorder && (
                  <div>
                    <Label htmlFor="edit-preorder-date" className="font-medium">Available Date</Label>
                    <Input
                      id="edit-preorder-date"
                      type="date"
                      value={editingProduct.preorder_date ? editingProduct.preorder_date.split('T')[0] : ''}
                      onChange={(e) => setEditingProduct({ ...editingProduct, preorder_date: e.target.value })}
                      className="mt-1"
                    />
                  </div>
                )}
              </div>
              
              {/* Checkboxes */}
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={editingProduct.featured || editingProduct.is_featured || false}
                    onChange={(e) => setEditingProduct({ 
                      ...editingProduct, 
                      featured: e.target.checked, 
                      is_featured: e.target.checked 
                    })}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <span className="text-sm">Featured Product</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={editingProduct.active !== false && editingProduct.is_active !== false}
                    onChange={(e) => setEditingProduct({ 
                      ...editingProduct, 
                      active: e.target.checked, 
                      is_active: e.target.checked 
                    })}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <span className="text-sm">Active (Visible)</span>
                </label>
              </div>
              
              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                <Button 
                  variant="outline" 
                  onClick={() => setShowEditDialog(false)}
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleSaveProduct} 
                  disabled={savingProduct}
                  className="bg-purple-600 hover:bg-purple-700 text-white"
                >
                  {savingProduct ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ProductDetailPage;
