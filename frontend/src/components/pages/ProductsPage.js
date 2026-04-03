import React, { useState, useEffect, useMemo, useTransition, useCallback, memo, useRef } from "react";
import { Link, useSearchParams, useNavigate, useParams } from "react-router-dom";
import { LazyMotion, domAnimation, m } from "framer-motion";
import axios from "axios";
import { Search, X, Star, Heart, Loader2, Sparkles, Eye, Droplets, Clock, Package, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCart, useAuth, useCurrency, useWishlist, useTranslation } from "@/contexts";
import { useWebSocket } from "@/contexts/WebSocketContext";
import { API } from "@/lib/api";
import { Helmet } from "react-helmet-async";
import { optimizeImageUrl } from "@/lib/imageOptimization";
import { Grid } from "react-window";
import { toast } from "sonner";
import ComboBuilder from "../product/ComboBuilder";

// Skin concern categories for SEO and filtering
const SKIN_CONCERNS = [
  { id: 'all', name: 'All Products', icon: Sparkles, keywords: [], slug: '' },
  { id: 'anti-aging', name: 'Anti-Aging', icon: Clock, keywords: ['anti-aging', 'wrinkle', 'firming', 'argireline', 'peptide', 'collagen', 'rejuvenation'], slug: 'anti-aging' },
  { id: 'dark-circles', name: 'Dark Circles', icon: Eye, keywords: ['eye', 'dark circle', 'puffiness', 'under-eye', 'brightening', 'nad+', 'nad'], slug: 'dark-circles' },
  { id: 'pigmentation', name: 'Pigmentation', icon: Sparkles, keywords: ['pigmentation', 'dark spot', 'melasma', 'tranexamic', 'brightening', 'txa', 'uneven tone'], slug: 'pigmentation' },
  { id: 'hydration', name: 'Hydration', icon: Droplets, keywords: ['hydrat', 'moisture', 'hyaluronic', 'barrier', 'dry skin', 'plumping', 'ceramide'], slug: 'hydration' },
];

// Ingredient filters for "Filter by Ingredient" feature
const INGREDIENT_FILTERS = [
  { id: 'pdrn', name: 'PDRN', keywords: ['pdrn', 'polydeoxyribonucleotide', 'salmon dna', 'sodium dna'], description: 'Salmon DNA for cellular regeneration' },
  { id: 'nad', name: 'NAD+', keywords: ['nad+', 'nad', 'nicotinamide'], description: 'Energy coenzyme for skin vitality' },
  { id: 'tranexamic', name: 'Tranexamic Acid', keywords: ['tranexamic', 'txa'], description: 'Clinical brightening active' },
  { id: 'argireline', name: 'Argireline', keywords: ['argireline', 'acetyl hexapeptide'], description: 'Peptide for expression lines' },
  { id: 'niacinamide', name: 'Niacinamide', keywords: ['niacinamide', 'vitamin b3'], description: 'Pore-refining & brightening' },
  { id: 'centella', name: 'Centella Asiatica', keywords: ['centella', 'cica', 'madecassoside'], description: 'Soothing & healing botanical' },
];

// UI Translations fallback
const UI_TRANSLATIONS = {
  en: { products: "Products", addToCart: "Add to Cart", search: "Search" }
};

// Debounce hook for search optimization
const useDebounce = (value, delay = 300) => {
  const [debouncedValue, setDebouncedValue] = useState(value);
  
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    
    return () => clearTimeout(handler);
  }, [value, delay]);
  
  return debouncedValue;
};

// Idle callback hook - defers non-critical work to idle periods
// Improves INP by not blocking main thread during user interactions
const useIdleCallback = (callback, deps = []) => {
  useEffect(() => {
    if ('requestIdleCallback' in window) {
      const id = window.requestIdleCallback(callback, { timeout: 2000 });
      return () => window.cancelIdleCallback(id);
    } else {
      // Fallback for Safari
      const id = setTimeout(callback, 1);
      return () => clearTimeout(id);
    }
  }, deps);
};

// Grid configuration for react-window virtualization
const GRID_CONFIG = {
  COLUMN_COUNT_MOBILE: 2,
  COLUMN_COUNT_DESKTOP: 4,
  ROW_HEIGHT: 520, // Approximate height of product card
  GAP: 24, // 6 * 4 = gap-6
  VIRTUALIZATION_THRESHOLD: 20, // Only virtualize if more than 20 products
};

// Luxury Product Card - Memoized to prevent unnecessary re-renders
// Uses content-visibility: auto for off-screen cards (mobile performance)
const LuxuryProductCard = memo(({ product, translatedProduct, index, isAboveFold, comboMode, isSelectedForCombo, onToggleCombo }) => {
  const { addToCart, setSideCartOpen } = useCart();
  const { currentLang } = useTranslation() || {};
  const { formatPrice } = useCurrency();
  const { isInWishlist, toggleWishlist } = useWishlist();
  const hoverTimeoutRef = useRef(null);
  const prefetchedRef = useRef(false);
  
  const lang = currentLang || "en-CA";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;
  const displayProduct = translatedProduct || product;
  const isPreOrder = product.allow_preorder;
  const effectivePrice = product.discount_percent 
    ? product.price * (1 - product.discount_percent / 100) 
    : product.price;
  
  const handleAddToBag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    addToCart(product.id, 1);
    setSideCartOpen(true);
  }, [addToCart, product.id, setSideCartOpen]);

  const handleToggleWishlist = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleWishlist(product.id);
  }, [toggleWishlist, product.id]);
  
  const handleComboToggle = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (onToggleCombo) {
      onToggleCombo(product);
    }
  }, [onToggleCombo, product]);

  // Instant-Click: Prefetch product page data after 100ms hover
  // This makes navigation feel instantaneous
  const handleMouseEnter = useCallback(() => {
    if (prefetchedRef.current) return;
    
    hoverTimeoutRef.current = setTimeout(() => {
      const productUrl = product.slug || product.id;
      
      // Prefetch the product detail API data
      fetch(`${API.replace('/api', '')}/api/products/${productUrl}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        priority: 'low'
      }).catch(() => {}); // Silently fail - it's just a prefetch
      
      // Prefetch the first product image at higher resolution
      if (product.images?.[0]) {
        const prefetchImage = new Image();
        prefetchImage.src = optimizeImageUrl(product.images[0], 800, 85);
      }
      
      prefetchedRef.current = true;
    }, 100); // 100ms hover delay before prefetching
  }, [product.slug, product.id, product.images]);

  const handleMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
  }, []);

  // CSS style for content-visibility optimization
  // Above-fold cards render immediately, below-fold use content-visibility
  const cardStyle = isAboveFold ? {} : {
    contentVisibility: 'auto',
    containIntrinsicSize: 'auto 520px', // Estimated card height
  };

  return (
    <m.div
      initial={isAboveFold ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      whileInView={isAboveFold ? undefined : { opacity: 1, y: 0 }}
      viewport={isAboveFold ? undefined : { once: true, margin: '-50px' }}
      transition={isAboveFold ? undefined : { duration: 0.4, delay: Math.min((index - 4) * 0.05, 0.15) }}
      className={`product-card group relative ${isSelectedForCombo ? 'ring-2 ring-purple-500 rounded-2xl' : ''}`}
      data-testid={`product-card-${product.id}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={cardStyle}
    >
      {/* Combo Selection Button - appears when combo mode is active */}
      {comboMode && (
        <Button
          variant={isSelectedForCombo ? "default" : "outline"}
          size="icon"
          className={`absolute top-3 left-3 z-20 shadow-md rounded-full w-9 h-9 transition-all ${
            isSelectedForCombo 
              ? 'bg-purple-500 hover:bg-purple-600 text-white border-purple-500' 
              : 'bg-white/90 hover:bg-purple-50 border-purple-300 text-purple-600'
          }`}
          onClick={handleComboToggle}
        >
          {isSelectedForCombo ? (
            <span className="text-sm font-bold">✓</span>
          ) : (
            <Plus className="h-4 w-4" />
          )}
        </Button>
      )}
      
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-3 right-3 z-10 bg-white/90 hover:bg-white shadow-md rounded-full w-9 h-9"
        onClick={handleToggleWishlist}
      >
        <Heart 
          className={`h-4 w-4 transition-colors ${isInWishlist(product.id) ? 'fill-red-500 text-red-500' : 'text-gray-600'}`} 
        />
      </Button>
      
      <Link to={`/products/${product.slug || product.id}`}>
        <div className="aspect-[3/4] relative overflow-hidden bg-gradient-to-br from-gray-100 to-gray-50 rounded-2xl mb-5 shadow-[0_8px_30px_rgb(0,0,0,0.04)] group-hover:shadow-[0_20px_50px_rgb(0,0,0,0.1)] transition-all duration-500 border border-transparent group-hover:border-[#D4AF37]/20">
          {/* Low-quality placeholder shimmer */}
          <div className="absolute inset-0 bg-gradient-to-r from-gray-100 via-gray-200 to-gray-100 animate-pulse" 
               style={{ animationDuration: '1.5s' }} />
          <img
            src={optimizeImageUrl(product.images?.[0], 400, 80) || "https://via.placeholder.com/400x500"}
            alt={displayProduct.name}
            className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 ease-out group-hover:scale-105"
            loading={isAboveFold ? "eager" : "lazy"}
            fetchPriority={isAboveFold ? "high" : "auto"}
            decoding="async"
            width="400"
            height="500"
            onLoad={(e) => {
              // Hide placeholder when image loads
              if (e.target.previousElementSibling) {
                e.target.previousElementSibling.style.display = 'none';
              }
            }}
          />
          
          <div className="absolute top-4 left-4 flex flex-col gap-2">
            {isPreOrder && (
              <Badge className="bg-purple-600 text-white hover:bg-purple-600 rounded-full px-3">
                {t.pre_order || "Pre-Order"}
              </Badge>
            )}
            {!isPreOrder && (product.compare_price || product.discount_percent) && (
              <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] rounded-full px-3">
                {product.discount_percent ? `${Number(product.discount_percent).toFixed(2)}% OFF` : "SALE"}
              </Badge>
            )}
            {product.is_featured && (
              <Badge className="bg-[#D4AF37] text-white hover:bg-[#D4AF37] rounded-full px-3">
                ★ Bestseller
              </Badge>
            )}
          </div>
          
          {product.stock > 0 && product.stock <= 5 && (
            <div className="absolute bottom-3 left-3 right-3">
              <Badge variant="destructive" className="w-full justify-center text-xs rounded-full py-1.5">
                🔥 Only {product.stock} left!
              </Badge>
            </div>
          )}
          
          {/* 2026 Micro-interaction: Science icon on hover - Using SVG sprite for smaller DOM */}
          <div 
            className="product-card-science-icon absolute bottom-3 right-3 bg-white/95 backdrop-blur-sm rounded-full p-2 shadow-lg"
            aria-hidden="true"
          >
            <svg className="h-5 w-5 text-[#D4AF37]" aria-label="Biotech Science Formula">
              <use href="#icon-science-flask" />
            </svg>
          </div>
        </div>
        
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
      
      <Button
        className="w-full mt-5 bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-5 font-semibold shadow-lg hover:shadow-xl font-clinical transition-all duration-300"
        onClick={handleAddToBag}
        data-testid={`add-to-cart-${product.id}`}
      >
        {product.stock > 0 || !isPreOrder ? "Add to Bag" : `Pre-Order Now`}
      </Button>
    </m.div>
  );
});

const ProductsPage = () => {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [comboOffers, setComboOffers] = useState([]); // Combo offers state
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const { concern: urlConcern } = useParams(); // Get concern from URL path
  const selectedCategory = searchParams.get("category") || "";
  const [searchQuery, setSearchQuery] = useState(searchParams.get("search") || "");
  const { currentLang, translateBatch } = useTranslation() || {};
  const [translatedCategories, setTranslatedCategories] = useState([]);
  const [translatedProducts, setTranslatedProducts] = useState([]);
  const { user } = useAuth();
  const navigate = useNavigate();
  const { addEventListener } = useWebSocket() || {};
  
  // Combo Builder state - for "Build Your Routine" feature
  const [comboMode, setComboMode] = useState(false);
  const [selectedComboProducts, setSelectedComboProducts] = useState([]);
  
  // Fetch products function
  const fetchProducts = useCallback(() => {
    const params = selectedCategory ? `?category=${selectedCategory}` : "";
    const cacheBuster = params ? `&_t=${Date.now()}` : `?_t=${Date.now()}`;
    axios.get(`${API}/products${params}${cacheBuster}`)
      .then(res => {
        // Filter products for bright theme (ReRoots) visibility
        const filteredProducts = (res.data || []).filter(p => {
          const visibility = p.brand_visibility || 'both';
          return visibility === 'both' || visibility === 'reroots_only';
        });
        setProducts(filteredProducts);
        setTranslatedProducts(filteredProducts);
      })
      .catch(console.error);
  }, [selectedCategory]);
  
  // Fetch combo offers
  useEffect(() => {
    axios.get(`${API}/combo-offers`)
      .then(res => {
        const activeCombos = (res.data || []).filter(c => c.is_active !== false);
        setComboOffers(activeCombos);
      })
      .catch(console.error);
  }, []);
  
  // Listen for real-time product updates
  useEffect(() => {
    if (!addEventListener) return;
    
    const unsubscribe = addEventListener('product_sync', (data) => {
      console.log('Products updated via WebSocket, refreshing...');
      fetchProducts();
      if (data?.action === 'created') {
        toast.info(`New product added: ${data?.product_name || 'Unknown'}`, { duration: 3000 });
      } else if (data?.action === 'updated') {
        toast.info('Product updated!', { duration: 2000 });
      } else if (data?.action === 'deleted') {
        toast.info(`Product removed: ${data?.product_name || 'Unknown'}`, { duration: 3000 });
      }
    });
    
    return () => unsubscribe?.();
  }, [addEventListener, fetchProducts]);
  
  // Preview mode state
  const [isPreview, setIsPreview] = useState(false);
  const [previewContent, setPreviewContent] = useState(null);
  
  // Check for preview data
  useEffect(() => {
    const previewData = sessionStorage.getItem('preview_shop_page');
    if (previewData) {
      try {
        const parsed = JSON.parse(previewData);
        if (parsed._isPreview && Date.now() - parsed._timestamp < 5 * 60 * 1000) {
          setPreviewContent(parsed);
          setIsPreview(true);
          // Clear the preview data after use - use setTimeout to handle React StrictMode double-invocation
          setTimeout(() => {
            sessionStorage.removeItem('preview_shop_page');
          }, 100);
        }
      } catch (e) {
        console.error('Invalid preview data:', e);
      }
    }
  }, []);
  
  // React 18 useTransition for non-urgent state updates (INP optimization)
  // This keeps the UI responsive during filtering/searching
  const [isPending, startTransition] = useTransition();
  
  // Initialize concern from URL param or default to 'all'
  const [selectedConcern, setSelectedConcern] = useState(() => {
    if (urlConcern) {
      const found = SKIN_CONCERNS.find(c => c.slug === urlConcern || c.id === urlConcern);
      return found ? found.id : 'all';
    }
    return 'all';
  });
  
  // Ingredient filter state (multi-select)
  const [selectedIngredients, setSelectedIngredients] = useState(new Set());
  
  // Wrap filter changes in startTransition for better INP
  const handleConcernChange = useCallback((concernId) => {
    startTransition(() => {
      setSelectedConcern(concernId);
      const concern = SKIN_CONCERNS.find(c => c.id === concernId);
      if (concern?.slug) {
        navigate(`/shop/${concern.slug}`);
      } else {
        navigate('/shop');
      }
    });
  }, [navigate]);
  
  // Wrap search in startTransition for better INP
  const handleSearchChange = useCallback((value) => {
    startTransition(() => {
      setSearchQuery(value);
    });
  }, []);
  
  // Toggle ingredient filter (multi-select)
  const handleIngredientToggle = useCallback((ingredientId) => {
    startTransition(() => {
      setSelectedIngredients(prev => {
        const newSet = new Set(prev);
        if (newSet.has(ingredientId)) {
          newSet.delete(ingredientId);
        } else {
          newSet.add(ingredientId);
        }
        return newSet;
      });
    });
  }, []);
  
  // Clear all ingredient filters
  const clearIngredientFilters = useCallback(() => {
    startTransition(() => {
      setSelectedIngredients(new Set());
    });
  }, []);
  
  // Update concern when URL changes
  useEffect(() => {
    if (urlConcern) {
      const found = SKIN_CONCERNS.find(c => c.slug === urlConcern || c.id === urlConcern);
      if (found && found.id !== selectedConcern) {
        setSelectedConcern(found.id);
      }
    } else if (selectedConcern !== 'all') {
      // If no URL concern but state has concern, could be direct navigation
    }
  }, [urlConcern]);
  
  const lang = currentLang || "en-CA";
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.en;
  
  // Debounce search query for better performance (prevents filtering on every keystroke)
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  // Filter products by search query, skin concern, AND ingredients
  const filteredProducts = useMemo(() => {
    const source = translatedProducts.length ? translatedProducts : products;
    let filtered = source;
    
    // Filter by skin concern
    if (selectedConcern && selectedConcern !== 'all') {
      const concernData = SKIN_CONCERNS.find(c => c.id === selectedConcern);
      if (concernData) {
        filtered = filtered.filter(p => {
          // Handle ingredients - could be array or string
          const ingredientsText = Array.isArray(p.ingredients) 
            ? p.ingredients.join(' ') 
            : (p.ingredients || '');
          const searchText = `${p.name || ''} ${p.description || ''} ${p.short_description || ''} ${ingredientsText}`.toLowerCase();
          return concernData.keywords.some(keyword => searchText.includes(keyword.toLowerCase()));
        });
      }
    }
    
    // Filter by selected ingredients (AND logic - must contain ALL selected)
    if (selectedIngredients.size > 0) {
      filtered = filtered.filter(p => {
        const ingredientsText = Array.isArray(p.ingredients) 
          ? p.ingredients.join(' ') 
          : (p.ingredients || '');
        const searchText = `${p.name || ''} ${p.description || ''} ${p.short_description || ''} ${ingredientsText}`.toLowerCase();
        
        // Product must match ALL selected ingredients
        return Array.from(selectedIngredients).every(ingredientId => {
          const ingredientData = INGREDIENT_FILTERS.find(i => i.id === ingredientId);
          if (!ingredientData) return true;
          return ingredientData.keywords.some(keyword => searchText.includes(keyword.toLowerCase()));
        });
      });
    }
    
    // Filter by debounced search query (doesn't fire on every keystroke)
    if (debouncedSearchQuery.trim()) {
      const query = debouncedSearchQuery.toLowerCase();
      filtered = filtered.filter(p => 
        p.name?.toLowerCase().includes(query) ||
        p.description?.toLowerCase().includes(query) ||
        p.category?.toLowerCase().includes(query)
      );
    }
    
    return filtered;
  }, [debouncedSearchQuery, products, translatedProducts, selectedConcern, selectedIngredients]);

  useEffect(() => {
    axios.get(`${API}/categories`).then(res => setCategories(res.data)).catch(console.error);
  }, []);
  
  useEffect(() => {
    if (!categories.length) return;
    
    if (!currentLang || currentLang === "en" || currentLang === "en-US" || !translateBatch) {
      setTranslatedCategories(categories);
      return;
    }
    
    const translateCats = async () => {
      const names = categories.map(c => c.name);
      try {
        const translations = await translateBatch(names, currentLang);
        setTranslatedCategories(categories.map((cat, idx) => ({
          ...cat,
          name: translations[idx] || cat.name
        })));
      } catch (e) {
        setTranslatedCategories(categories);
      }
    };
    translateCats();
  }, [categories, currentLang, translateBatch]);

  // Fetch products on category change
  useEffect(() => {
    setLoading(true);
    fetchProducts();
    setLoading(false);
  }, [fetchProducts]);
  
  useEffect(() => {
    if (!products.length) {
      setTranslatedProducts([]);
      return;
    }
    
    if (!currentLang || currentLang === "en" || currentLang === "en-US" || !translateBatch) {
      setTranslatedProducts(products);
      return;
    }
    
    const translateProds = async () => {
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
      
      if (allTexts.length === 0) {
        setTranslatedProducts(products);
        return;
      }
      
      try {
        const translations = await translateBatch(allTexts, currentLang);
        const newProducts = products.map(p => ({...p}));
        
        textMap.forEach((mapping, idx) => {
          if (newProducts[mapping.pIdx]) {
            newProducts[mapping.pIdx][mapping.field] = translations[idx] || newProducts[mapping.pIdx][mapping.field];
          }
        });
        
        setTranslatedProducts(newProducts);
      } catch {
        setTranslatedProducts(products);
      }
    };
    
    translateProds();
  }, [products, currentLang, translateBatch]);

  // Dynamic SEO based on selected concern - targeting competitor keywords
  const getSEOContent = () => {
    const concernSEO = {
      'all': {
        title: 'Shop Biotech Skincare | PDRN Serums & Anti-Aging | ReRoots Canada',
        description: 'Shop ReRoots premium biotech skincare. PDRN serums for dark circles, pigmentation, melasma & anti-aging. Dermatologist-tested, made in Canada. Better than Vitamin C alone. Free shipping $75+.',
        keywords: 'PDRN skincare Canada, biotech serum, anti-aging treatment, dark circles eye cream, pigmentation treatment Canada, melasma skincare, tranexamic acid serum, best eye cream dark circles Canada'
      },
      'anti-aging': {
        title: 'Anti-Aging Skincare | PDRN + Argireline Serums | ReRoots Canada',
        description: 'Advanced anti-aging with PDRN technology. Clinically proven to reduce wrinkles by 60%. Features Argireline, peptides & salmon DNA. Better results than traditional Vitamin C serums.',
        keywords: 'anti-aging serum Canada, PDRN anti-aging, Argireline cream, peptide serum, wrinkle treatment Canada, biotech anti-aging, best anti-aging products Canada'
      },
      'dark-circles': {
        title: 'Eye Cream for Dark Circles | PDRN Eye Treatment | ReRoots Canada',
        description: 'Best eye cream for dark circles in Canada. PDRN + NAD+ technology reduces puffiness & brightens under-eyes. Clinically proven results. Superior to Vitamin C eye creams.',
        keywords: 'eye cream dark circles Canada, under eye treatment, PDRN eye cream, NAD+ eye concentrate, dark circles treatment, puffiness cream, best eye cream Canada'
      },
      'pigmentation': {
        title: 'Pigmentation & Melasma Treatment | Tranexamic Acid + PDRN | ReRoots',
        description: 'Treat pigmentation & melasma with 5% Tranexamic Acid + 2% PDRN. Clinically proven to fade dark spots. Made in Canada. Better than traditional brightening serums.',
        keywords: 'pigmentation treatment Canada, melasma skincare, tranexamic acid serum, dark spot correction, uneven skin tone, hyperpigmentation cream, best melasma treatment Canada'
      },
      'hydration': {
        title: 'Hydrating Skincare | Hyaluronic Acid + PDRN | ReRoots Canada',
        description: 'Deep hydration with PDRN technology. Barrier-strengthening formulas for dry & sensitive skin. Clinically tested, dermatologist approved. Made in Canada.',
        keywords: 'hydrating serum Canada, hyaluronic acid serum, dry skin treatment, barrier repair cream, moisturizer Canada, PDRN hydration'
      }
    };
    return concernSEO[selectedConcern] || concernSEO['all'];
  };

  const seoContent = getSEOContent();
  const concernSlug = SKIN_CONCERNS.find(c => c.id === selectedConcern)?.slug || '';
  const canonicalUrl = selectedConcern !== 'all' ? `https://reroots.ca/shop/${concernSlug}` : 'https://reroots.ca/shop';
  
  const shopSEO = (
    <Helmet>
      <title>{seoContent.title}</title>
      <meta name="description" content={seoContent.description} />
      <meta name="keywords" content={seoContent.keywords} />
      <link rel="canonical" href={canonicalUrl} />
      {/* Open Graph for social sharing */}
      <meta property="og:title" content={seoContent.title} />
      <meta property="og:description" content={seoContent.description} />
      <meta property="og:type" content="website" />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:image" content="https://reroots.ca/og-image-shop.jpg" />
      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={seoContent.title} />
      <meta name="twitter:description" content={seoContent.description} />
    </Helmet>
  );

  // JSON-LD Structured Data for AI Search (2026 SEO)
  const generateStructuredData = () => {
    const baseSchema = {
      "@context": "https://schema.org",
      "@graph": [
        // Organization Schema
        {
          "@type": "Organization",
          "@id": "https://reroots.ca/#organization",
          "name": "ReRoots Biotech Skincare",
          "url": "https://reroots.ca",
          "logo": "https://reroots.ca/logo.png",
          "sameAs": [
            "https://www.instagram.com/reroots.beauty",
            "https://www.tiktok.com/@reroots.beauty"
          ],
          "description": "Canada's #1 biotech skincare brand featuring PDRN technology for dark circles, pigmentation, and anti-aging.",
          "foundingDate": "2024",
          "foundingLocation": "Canada",
          "areaServed": "CA",
          "slogan": "The Future of Skin Longevity"
        },
        // Local Business Schema
        {
          "@type": "LocalBusiness",
          "@id": "https://reroots.ca/#localbusiness",
          "name": "ReRoots Skincare Canada",
          "image": "https://reroots.ca/storefront.jpg",
          "address": {
            "@type": "PostalAddress",
            "addressCountry": "CA"
          },
          "priceRange": "$50-$200 CAD",
          "paymentAccepted": "Credit Card, PayPal, Crypto",
          "currenciesAccepted": "CAD, USD"
        },
        // ItemList for Products
        {
          "@type": "ItemList",
          "@id": "https://reroots.ca/shop/#itemlist",
          "name": selectedConcern !== 'all' ? `${concernName} Skincare Products` : "All Skincare Products",
          "description": seoContent.description,
          "numberOfItems": filteredProducts.length,
          "itemListElement": filteredProducts.slice(0, 10).map((product, index) => ({
            "@type": "ListItem",
            "position": index + 1,
            "item": {
              "@type": "Product",
              "@id": `https://reroots.ca/products/${product.slug || product.id}`,
              "name": product.name,
              "description": product.short_description || product.description,
              "image": product.images?.[0],
              "brand": {
                "@type": "Brand",
                "name": "ReRoots"
              },
              "offers": {
                "@type": "Offer",
                "price": product.price,
                "priceCurrency": "CAD",
                "availability": "https://schema.org/InStock",
                "seller": {
                  "@type": "Organization",
                  "name": "ReRoots Skincare"
                }
              }
            }
          }))
        },
        // FAQ Schema for Rich Snippets
        {
          "@type": "FAQPage",
          "@id": `https://reroots.ca/shop/${concernSlug}#faq`,
          "mainEntity": [
            {
              "@type": "Question",
              "name": "What is PDRN and how does it benefit skin?",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "PDRN (Polydeoxyribonucleotide) is a biotech ingredient derived from salmon DNA that promotes cellular regeneration, collagen synthesis, and skin repair. Clinical studies show PDRN can improve skin firmness by up to 60% and is more effective than traditional Vitamin C for treating pigmentation and dark circles."
              }
            },
            {
              "@type": "Question",
              "name": "Is ReRoots skincare made in Canada?",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "Yes! ReRoots products are proudly made in Canada using biotech formulations. All products are dermatologist-tested, cruelty-free, and formulated with high concentrations of active ingredients like 2% PDRN and 5% Tranexamic Acid."
              }
            },
            {
              "@type": "Question",
              "name": "How does Tranexamic Acid help with pigmentation and melasma?",
              "acceptedAnswer": {
                "@type": "Answer",
                "text": "Tranexamic Acid (TXA) at 5% concentration is clinically proven to inhibit melanin production, making it highly effective for treating melasma, hyperpigmentation, and uneven skin tone. Combined with PDRN, it delivers superior results compared to Vitamin C alone."
              }
            }
          ]
        },
        // Ingredient Schema (Medical Entity for AI Search)
        {
          "@type": "MedicalEntity",
          "@id": "https://reroots.ca/#pdrn-ingredient",
          "name": "PDRN (Polydeoxyribonucleotide)",
          "alternateName": ["Salmon DNA", "PN", "Polydeoxyribonucleotide"],
          "description": "A biotech skincare ingredient derived from salmon DNA that promotes cellular regeneration, wound healing, and collagen synthesis.",
          "medicineSystem": "https://schema.org/WesternConventional",
          "relevantSpecialty": "Dermatology"
        }
      ]
    };
    return JSON.stringify(baseSchema);
  };
  
  const selectedCatName = translatedCategories.find(c => c.id === selectedCategory)?.name || 
                          categories.find(c => c.id === selectedCategory)?.name || "";
  const concernName = SKIN_CONCERNS.find(c => c.id === selectedConcern)?.name || "";
  const pageTitle = selectedConcern !== 'all' ? concernName : (selectedCategory ? selectedCatName : (t.all_products || "All Products"));

  // Preview content overrides
  const heroTitle = previewContent?.hero?.title || null;
  const heroSubtitle = previewContent?.hero?.subtitle || null;
  const heroDescription = previewContent?.hero?.description || null;
  const heroBadge = previewContent?.hero?.badge_text || "BIOTECH SKINCARE";

  // Preload first 4 product images for faster LCP
  const preloadImages = filteredProducts.slice(0, 4).map(p => optimizeImageUrl(p.images?.[0], 400, 80)).filter(Boolean);

  return (
    <LazyMotion features={domAnimation}>
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      {/* Preview Banner */}
      {isPreview && (
        <div className="fixed top-0 left-0 right-0 z-[100] bg-gradient-to-r from-amber-500 to-orange-500 text-white py-2 px-4 text-center shadow-lg" data-testid="preview-banner">
          <p className="text-sm font-medium flex items-center justify-center gap-2">
            <Eye className="h-4 w-4" />
            <span>Preview Mode — Changes not saved yet</span>
            <button 
              onClick={() => window.close()}
              className="ml-4 px-3 py-1 bg-white/20 hover:bg-white/30 rounded text-xs font-semibold transition-colors"
            >
              Close Preview
            </button>
          </p>
        </div>
      )}
      
      {shopSEO}
      
      {/* Preload critical images for faster LCP */}
      {preloadImages.map((src, i) => (
        <link key={i} rel="preload" as="image" href={src} />
      ))}
      
      {/* JSON-LD Structured Data for AI Search */}
      <script 
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: generateStructuredData() }}
      />
      
      <style>{`
        .font-luxury { font-family: 'Playfair Display', Georgia, serif; }
        .font-clinical { font-family: 'Manrope', 'Inter', sans-serif; }
        .font-mono-science { font-family: 'JetBrains Mono', monospace; }
        .luxury-btn { transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1); }
        .luxury-btn:hover { transform: scale(1.02); }
      `}</style>
      
      <div className="relative bg-[#2D2A2E] py-20 mb-8 overflow-hidden">
        <div className="absolute inset-0 opacity-30">
          <img 
            src={previewContent?.hero?.image || optimizeImageUrl("https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/vmettfqd_1767379332331.jpg", 1200, 60)} 
            alt="" 
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
        <div className="absolute inset-0 bg-gradient-to-r from-[#2D2A2E] via-[#2D2A2E]/80 to-[#2D2A2E]" />
        <div className="relative max-w-7xl mx-auto px-6 md:px-12 lg:px-24 text-center">
          <m.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] hover:bg-[#D4AF37]/20 mb-6 font-mono-science text-xs tracking-[0.2em]">
              {heroBadge}
            </Badge>
            <h1 className="font-luxury text-4xl md:text-5xl lg:text-6xl font-medium text-white mb-4" data-testid="products-title">
              {heroTitle ? (
                <>{heroTitle} {heroSubtitle && <span className="italic text-[#F8A5B8]">{heroSubtitle}</span>}</>
              ) : selectedConcern !== 'all' ? (
                <>Shop <span className="italic text-[#F8A5B8]">{concernName}</span></>
              ) : pageTitle === "All Products" ? (
                <>Shop Our <span className="italic text-[#F8A5B8]">Collection</span></>
              ) : pageTitle}
            </h1>
            <p className="font-clinical text-white/70 text-lg max-w-2xl mx-auto">
              {heroDescription ? heroDescription : (
                <>
                  {selectedConcern === 'anti-aging' && "PDRN + Argireline technology for visible wrinkle reduction"}
                  {selectedConcern === 'dark-circles' && "PDRN + NAD+ formulas to brighten & rejuvenate under-eyes"}
                  {selectedConcern === 'pigmentation' && "Tranexamic Acid + PDRN to fade dark spots & even skin tone"}
                  {selectedConcern === 'hydration' && "Barrier-strengthening formulas for lasting hydration"}
                  {selectedConcern === 'all' && "High-performance formulas with bio-active PDRN technology for visible results"}
                </>
              )}
            </p>
          </m.div>
        </div>
      </div>

      {/* SHOP BY CONCERN - SEO Optimized Section */}
      <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24 mb-12">
        <m.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <h2 className="font-luxury text-2xl text-[#2D2A2E] text-center mb-6">
            Shop By <span className="italic text-[#F8A5B8]">Concern</span>
          </h2>
          <div className="flex flex-wrap justify-center gap-3" data-testid="shop-by-concern">
            {SKIN_CONCERNS.map((concern) => {
              const IconComponent = concern.icon;
              const isActive = selectedConcern === concern.id;
              return (
                <Button
                  key={concern.id}
                  variant={isActive ? "default" : "outline"}
                  onClick={() => handleConcernChange(concern.id)}
                  className={`
                    rounded-full px-6 py-5 font-clinical text-sm transition-all duration-300
                    ${isActive 
                      ? 'bg-[#2D2A2E] text-white hover:bg-[#3D3A3E] shadow-lg' 
                      : 'bg-white border-gray-200 text-[#5A5A5A] hover:border-[#D4AF37] hover:text-[#D4AF37]'
                    }
                  `}
                  data-testid={`concern-${concern.id}`}
                >
                  <IconComponent className={`h-4 w-4 mr-2 ${isActive ? 'text-[#D4AF37]' : ''}`} />
                  {concern.name}
                </Button>
              );
            })}
          </div>
          
          {/* SEO-rich description for selected concern */}
          {selectedConcern !== 'all' && (
            <m.p 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center text-sm text-[#5A5A5A] mt-4 max-w-2xl mx-auto font-clinical"
            >
              {selectedConcern === 'anti-aging' && "Our PDRN anti-aging serums outperform traditional Vitamin C by promoting cellular regeneration. Clinical studies show 60% improvement in skin firmness."}
              {selectedConcern === 'dark-circles' && "Unlike basic eye creams, our PDRN + NAD+ eye treatments target the root cause of dark circles. See visible results in 2-4 weeks."}
              {selectedConcern === 'pigmentation' && "Our 5% Tranexamic Acid + 2% PDRN formula is clinically proven more effective than Vitamin C alone for melasma and hyperpigmentation."}
              {selectedConcern === 'hydration' && "PDRN technology enhances your skin's natural moisture retention, providing deeper hydration than hyaluronic acid alone."}
            </m.p>
          )}
        </m.div>
      </div>
      
      {/* FILTER BY INGREDIENT - Science-First Navigation */}
      <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24 mb-12">
        <m.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-luxury text-xl text-[#2D2A2E]">
              Filter by <span className="italic text-[#D4AF37]">Ingredient</span>
            </h2>
            {selectedIngredients.size > 0 && (
              <button 
                onClick={clearIngredientFilters}
                className="text-sm text-[#F8A5B8] hover:text-[#e8959a] font-medium transition-colors"
              >
                Clear filters ({selectedIngredients.size})
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-2" data-testid="filter-by-ingredient">
            {INGREDIENT_FILTERS.map((ingredient) => {
              const isActive = selectedIngredients.has(ingredient.id);
              return (
                <button
                  key={ingredient.id}
                  onClick={() => handleIngredientToggle(ingredient.id)}
                  className={`
                    group relative rounded-full px-4 py-2 font-clinical text-sm transition-all duration-200
                    flex items-center gap-2
                    ${isActive 
                      ? 'bg-[#D4AF37] text-white shadow-md' 
                      : 'bg-white border border-gray-200 text-[#5A5A5A] hover:border-[#D4AF37] hover:text-[#D4AF37]'
                    }
                  `}
                  data-testid={`ingredient-${ingredient.id}`}
                >
                  {/* Checkbox indicator */}
                  <span className={`
                    w-4 h-4 rounded border-2 flex items-center justify-center text-xs transition-colors
                    ${isActive 
                      ? 'bg-white border-white text-[#D4AF37]' 
                      : 'border-gray-300 group-hover:border-[#D4AF37]'
                    }
                  `}>
                    {isActive && '✓'}
                  </span>
                  {ingredient.name}
                  
                  {/* Tooltip on hover */}
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-[#2D2A2E] text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                    {ingredient.description}
                    <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#2D2A2E]" />
                  </span>
                </button>
              );
            })}
          </div>
          
          {/* Active ingredient filter summary */}
          {selectedIngredients.size > 0 && (
            <m.div 
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mt-4 p-3 bg-[#D4AF37]/5 rounded-xl border border-[#D4AF37]/20"
            >
              <p className="text-sm text-[#5A5A5A] font-clinical">
                <span className="text-[#D4AF37] font-semibold">Filtering by: </span>
                {Array.from(selectedIngredients).map(id => INGREDIENT_FILTERS.find(i => i.id === id)?.name).join(' + ')}
              </p>
            </m.div>
          )}
        </m.div>
      </div>
      
      <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24 pb-24">
        <m.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12 pb-8 border-b border-gray-200"
        >
          <div>
            <p className="font-clinical text-[#5A5A5A]">
              <span className="font-mono-science text-[#D4AF37] font-semibold">{filteredProducts.length}</span> {t.products || "products"}
              {selectedConcern !== 'all' && <span className="ml-2 text-[#F8A5B8]">for {concernName}</span>}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto">
            <div className="relative flex-1 sm:w-72">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="text"
                placeholder={t.search || "Search products..."}
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="pl-11 bg-white border-gray-200 rounded-full py-5 font-clinical focus:border-[#D4AF37] focus:ring-[#D4AF37]/20"
              />
              {searchQuery && (
                <button 
                  onClick={() => handleSearchChange("")}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            
            {/* Show pending indicator during transitions */}
            {isPending && (
              <div className="absolute right-12 top-1/2 -translate-y-1/2">
                <Loader2 className="h-4 w-4 animate-spin text-[#D4AF37]" />
              </div>
            )}
            
            <Select value={selectedCategory || "all"} onValueChange={(value) => setSearchParams(value && value !== "all" ? { category: value } : {})}>
              <SelectTrigger className="w-full sm:w-[200px] bg-white border-gray-200 rounded-full py-5 font-clinical" data-testid="category-filter" aria-label="Filter products by category">
                <SelectValue placeholder={t.all_products || "All Categories"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all" className="font-clinical">{t.all_products || "All Categories"}</SelectItem>
                {translatedCategories.map(cat => (
                  <SelectItem key={cat.id} value={cat.id} className="font-clinical">{cat.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Build Your Routine Toggle */}
            <Button
              variant={comboMode ? "default" : "outline"}
              onClick={() => {
                setComboMode(!comboMode);
                if (!comboMode) {
                  toast.info('Select 2-4 products to build your routine');
                } else {
                  setSelectedComboProducts([]);
                }
              }}
              className={`flex items-center gap-2 rounded-full px-5 py-5 ${
                comboMode 
                  ? 'bg-gradient-to-r from-purple-600 to-pink-500 text-white border-0' 
                  : 'border-purple-300 text-purple-600 hover:bg-purple-50'
              }`}
            >
              <Package className="h-4 w-4" />
              <span className="hidden sm:inline">Build Routine</span>
              {comboMode && selectedComboProducts.length > 0 && (
                <Badge className="bg-white text-purple-600 ml-1">{selectedComboProducts.length}</Badge>
              )}
            </Button>
          </div>
        </m.div>

        {/* FEATURED COMBO OFFERS - Clinical Protocols */}
        {comboOffers.length > 0 && !searchQuery && selectedConcern === 'all' && (
          <m.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mb-12"
          >
            <h2 className="font-luxury text-2xl text-[#2D2A2E] text-center mb-6">
              Clinical <span className="italic text-[#F8A5B8]">Protocols</span>
            </h2>
            <p className="font-clinical text-[#5A5A5A] text-center mb-8 max-w-2xl mx-auto">
              Curated product combinations designed for maximum results. Save more when you buy together.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {comboOffers.map((combo) => {
                const originalPrice = combo.original_price || 0;
                const comboPrice = combo.combo_price || originalPrice * (1 - (combo.discount_percent || 15) / 100);
                const savings = originalPrice - comboPrice;
                
                return (
                  <Link 
                    key={combo.id} 
                    to="/sets"
                    className="group block"
                  >
                    <div className="relative bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-100 hover:border-purple-300 hover:shadow-lg transition-all duration-300 h-full">
                      {/* Discount Badge */}
                      {combo.discount_percent && (
                        <Badge className="absolute top-4 right-4 bg-gradient-to-r from-purple-600 to-pink-500 text-white">
                          Save {Number(combo.discount_percent).toFixed(2)}%
                        </Badge>
                      )}
                      
                      {/* Combo Name */}
                      <h3 className="font-luxury text-xl text-[#2D2A2E] mb-2 group-hover:text-purple-700 transition-colors">
                        {combo.name}
                      </h3>
                      
                      {/* Tagline */}
                      <p className="font-clinical text-sm text-[#5A5A5A] mb-4">
                        {combo.tagline || 'Complete skincare protocol'}
                      </p>
                      
                      {/* Active Potency Badge */}
                      {combo.total_active_percent && (
                        <div className="flex items-center gap-2 mb-4">
                          <div className="px-3 py-1 bg-amber-100 rounded-full">
                            <span className="font-mono-science text-amber-700 text-sm font-semibold">
                              {combo.total_active_percent}% Active
                            </span>
                          </div>
                          <span className="text-xs text-gray-500">Hyper-Potency</span>
                        </div>
                      )}
                      
                      {/* Price */}
                      <div className="flex items-baseline gap-2 mt-auto">
                        <span className="font-clinical font-bold text-2xl text-[#2D2A2E]">
                          ${comboPrice.toFixed(2)}
                        </span>
                        {originalPrice > comboPrice && (
                          <span className="font-clinical text-sm text-gray-400 line-through">
                            ${originalPrice.toFixed(2)}
                          </span>
                        )}
                      </div>
                      
                      {/* Savings */}
                      {savings > 0 && (
                        <p className="font-clinical text-sm text-green-600 mt-1">
                          You save ${savings.toFixed(2)}
                        </p>
                      )}
                      
                      {/* View Details Link */}
                      <div className="mt-4 flex items-center gap-2 text-purple-600 font-clinical text-sm group-hover:text-purple-800">
                        <span>View Protocol Details</span>
                        <span className="group-hover:translate-x-1 transition-transform">→</span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </m.div>
        )}

        {loading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 md:gap-10">
            {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
              <div key={i} className="animate-pulse">
                <div className="aspect-[3/4] bg-gray-200 rounded-2xl mb-6" />
                <div className="h-6 bg-gray-200 rounded w-3/4 mb-3" />
                <div className="h-4 bg-gray-200 rounded w-1/2 mb-4" />
                <div className="h-12 bg-gray-200 rounded-full" />
              </div>
            ))}
          </div>
        ) : filteredProducts.length === 0 ? (
          <m.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-16"
          >
            <div className="max-w-md mx-auto">
              <div className="w-20 h-20 mx-auto mb-6 bg-[#FDF9F9] rounded-full flex items-center justify-center">
                <Search className="w-8 h-8 text-gray-400" />
              </div>
              <h2 className="font-display text-2xl font-semibold text-[#2D2A2E] mb-3">
                {selectedCategory ? `No ${selectedCategory} products yet` : (searchQuery ? `No results for "${searchQuery}"` : "No products found")}
              </h2>
              <p className="font-clinical text-[#5A5A5A] text-base mb-6">
                {selectedCategory 
                  ? `We're working on expanding our ${selectedCategory} collection. Check out our other premium skincare products below.`
                  : "Try adjusting your search or browse our full collection of premium biotech skincare."
                }
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                {(searchQuery || selectedCategory) && (
                  <Button 
                    variant="outline" 
                    className="luxury-btn rounded-full px-8 py-5 font-clinical"
                    onClick={() => {
                      setSearchQuery("");
                      setSearchParams({});
                    }}
                  >
                    View All Products
                  </Button>
                )}
                <Button 
                  className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] rounded-full px-8 py-5 font-clinical font-semibold"
                  onClick={() => navigate('/products/prod-aura-gen')}
                >
                  Shop AURA-GEN Serum
                </Button>
              </div>
              {/* SEO content to prevent soft 404 */}
              <div className="mt-12 pt-8 border-t border-gray-100 text-left">
                <h3 className="font-display text-lg font-semibold text-[#2D2A2E] mb-3">Discover ReRoots Biotech Skincare</h3>
                <p className="font-clinical text-sm text-[#5A5A5A] leading-relaxed">
                  ReRoots is Canada's premier biotech skincare brand, featuring professional-strength PDRN serums and active complexes. 
                  Our flagship AURA-GEN serum combines 2% PDRN (Salmon DNA), 5% Tranexamic Acid, and 10% Argireline for a powerful 17% active formula 
                  that targets wrinkles, dark spots, and skin rejuvenation. Free shipping on orders over $75 across Canada.
                </p>
              </div>
            </div>
          </m.div>
        ) : (
          <ProductGrid 
            products={filteredProducts}
            translatedProducts={translatedProducts}
            comboMode={comboMode}
            selectedComboProducts={selectedComboProducts}
            onToggleCombo={(product) => {
              const isSelected = selectedComboProducts.some(p => p.id === product.id);
              if (isSelected) {
                setSelectedComboProducts(prev => prev.filter(p => p.id !== product.id));
              } else if (selectedComboProducts.length < 4) {
                setSelectedComboProducts(prev => [...prev, product]);
                if (selectedComboProducts.length === 0) {
                  toast.info('Select 1 more product to see AI combo benefits!');
                } else if (selectedComboProducts.length === 1) {
                  toast.success('Great choice! AI is analyzing your routine...');
                }
              } else {
                toast.error('Maximum 4 products in a combo');
              }
            }}
          />
        )}
        
        {/* Combo Builder - Fixed bottom panel */}
        {comboMode && selectedComboProducts.length > 0 && (
          <ComboBuilder
            selectedProducts={selectedComboProducts}
            onRemoveProduct={(productId) => {
              setSelectedComboProducts(prev => prev.filter(p => p.id !== productId));
            }}
            onClearAll={() => setSelectedComboProducts([])}
            onAddToCart={async (products, comboPrice) => {
              for (const product of products) {
                await addToCart(product, 1);
              }
              toast.success(`Added ${products.length} products to your bag!`);
              setSelectedComboProducts([]);
            }}
          />
        )}
      </div>
      
      {/* Spacer for combo builder */}
      {comboMode && selectedComboProducts.length > 0 && (
        <div className="h-64" />
      )}
    </div>
    </LazyMotion>
  );
};

// Smart Product Grid - Uses virtualization only when needed for performance
const ProductGrid = memo(({ products, translatedProducts, comboMode, selectedComboProducts, onToggleCombo }) => {
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [useVirtualization, setUseVirtualization] = useState(false);
  
  // Calculate columns based on screen width
  const columnCount = containerWidth >= 1024 ? 4 : 2;
  const rowCount = Math.ceil(products.length / columnCount);
  
  // Update container width on resize (RAF to prevent forced reflow)
  useEffect(() => {
    if (!containerRef.current) return;
    
    let rafId;
    const updateWidth = () => {
      // Use requestAnimationFrame to batch layout reads
      rafId = requestAnimationFrame(() => {
        if (containerRef.current) {
          setContainerWidth(containerRef.current.offsetWidth);
        }
      });
    };
    
    updateWidth();
    
    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(containerRef.current);
    
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
    };
  }, []);
  
  // Only enable virtualization for large lists
  useEffect(() => {
    setUseVirtualization(products.length > GRID_CONFIG.VIRTUALIZATION_THRESHOLD);
  }, [products.length]);
  
  // Cell renderer for virtualized grid
  const Cell = useCallback(({ columnIndex, rowIndex, style }) => {
    const index = rowIndex * columnCount + columnIndex;
    if (index >= products.length) return null;
    
    const product = products[index];
    const translatedProduct = translatedProducts[index];
    const isSelected = comboMode && selectedComboProducts?.some(p => p.id === product.id);
    
    return (
      <div style={{ ...style, padding: `${GRID_CONFIG.GAP / 2}px` }}>
        <LuxuryProductCard 
          product={product} 
          translatedProduct={translatedProduct}
          index={index}
          isAboveFold={index < 4}
          comboMode={comboMode}
          isSelectedForCombo={isSelected}
          onToggleCombo={onToggleCombo}
        />
      </div>
    );
  }, [products, translatedProducts, columnCount, comboMode, selectedComboProducts, onToggleCombo]);
  
  // Regular grid for small product lists (better UX, no virtualization overhead)
  if (!useVirtualization) {
    return (
      <div 
        ref={containerRef}
        className="grid grid-cols-2 lg:grid-cols-4 gap-6 md:gap-10" 
        data-testid="products-grid"
      >
        {products.map((product, idx) => {
          const isSelected = comboMode && selectedComboProducts?.some(p => p.id === product.id);
          return (
            <LuxuryProductCard 
              key={product.id} 
              product={product} 
              translatedProduct={translatedProducts[idx]}
              index={idx}
              isAboveFold={idx < 4}
              comboMode={comboMode}
              isSelectedForCombo={isSelected}
              onToggleCombo={onToggleCombo}
            />
          );
        })}
      </div>
    );
  }
  
  // Virtualized grid for large product lists (>20 products)
  const columnWidth = containerWidth / columnCount;
  
  return (
    <div ref={containerRef} data-testid="products-grid-virtualized">
      {containerWidth > 0 && (
        <Grid
          columnCount={columnCount}
          columnWidth={columnWidth}
          height={Math.min(rowCount * GRID_CONFIG.ROW_HEIGHT, window.innerHeight * 2)}
          rowCount={rowCount}
          rowHeight={GRID_CONFIG.ROW_HEIGHT}
          width={containerWidth}
          overscanCount={2}
          cellComponent={Cell}
        />
      )}
    </div>
  );
});

export default ProductsPage;
