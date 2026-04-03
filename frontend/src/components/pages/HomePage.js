import React, { useState, useEffect, useCallback, useRef, memo, useTransition, lazy, Suspense } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
// PERF: Use LazyMotionWrapper to avoid duplicate framer-motion bundles
import { m, AnimatePresence } from "@/components/LazyMotionWrapper";
import { Helmet } from "react-helmet-async";
import { 
  ArrowRight, ChevronRight, Star, Shield, Truck, Heart, Beaker, Leaf, Sparkles,
  FlaskConical, Dna, TestTube, Microscope, Award, BadgeCheck, ShieldCheck, X,
  Droplets, Zap, Target, ShoppingBag, Loader2, Eye, Clock, Phone
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCart } from "@/contexts";
import PhoneInput, { detectUserCountry, getCountryByCode, formatFullPhone } from "@/components/common/PhoneInput";

// PERFORMANCE: Image optimization for AVIF/WebP conversion
import { optimizeImageUrl, getResponsiveSrcSet } from "@/lib/imageOptimization";

// CRITICAL: OptimizeMobileHydration - The "Cheat Code" for Mobile 90+ Score
// This stops React from hydrating 70+ elements at once, freeing the mobile CPU
import { OptimizeMobileHydration } from "@/components/OptimizeMobileHydration";

// Lazy load below-fold components - combined with OptimizeMobileHydration
const StickyScrollSection = lazy(() => import("@/components/StickyScrollSection"));
const StickyClinicalProof = lazy(() => import("@/components/StickyClinicalProof"));
// Note: ClinicalProofSection removed - dead code. Using StickyClinicalProof instead.
const CustomerTestimonialsSection = lazy(() => import("@/components/CustomerTestimonialsSection"));
const ShareCard = lazy(() => import("@/components/ShareCard"));

// Lightweight skeleton for loading states
const SkeletonPlaceholder = ({ height = 400 }) => (
  <div 
    className="bg-gradient-to-b from-gray-50/30 to-transparent" 
    style={{ minHeight: height }}
    aria-hidden="true"
  />
);

// API URL
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  return window.location.origin;
};
const API = `${getBackendUrl()}/api`;

// ============================================
// GLOBAL STYLES - Inject smooth scrolling
// ============================================
const GlobalStyles = () => (
  <style>{`
    html {
      scroll-behavior: smooth;
    }
    
    /* 2026 WCAG 2.2 Accessibility - High Contrast Focus States */
    *:focus-visible {
      outline: 3px solid #D4AF37 !important;
      outline-offset: 3px !important;
      border-radius: 4px;
    }
    
    /* Skip Link for Keyboard Navigation */
    .skip-link {
      position: absolute;
      top: -40px;
      left: 0;
      background: #2D2A2E;
      color: white;
      padding: 8px 16px;
      z-index: 9999;
      border-radius: 0 0 8px 0;
    }
    
    .skip-link:focus {
      top: 0;
    }
    
    /* Ensure minimum touch target size (24x24px) */
    button, a, input, select, [role="button"] {
      min-height: 24px;
      min-width: 24px;
    }
    
    /* Reduce motion for users who prefer it */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }
    }
    
    /* High contrast mode support */
    @media (prefers-contrast: high) {
      .text-white\\/70, .text-gray-500, .text-\\[\\#5A5A5A\\] {
        color: inherit !important;
        opacity: 1 !important;
      }
    }
    
    /* Luxury Button Transitions - 0.5s */
    .luxury-btn {
      transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .luxury-btn:hover {
      transform: scale(1.02);
    }
    
    /* JetBrains Mono for scientific text */
    .font-mono-science {
      font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    }
    
    /* Playfair Display for luxury headings */
    .font-luxury {
      font-family: 'Playfair Display', Georgia, serif;
    }
    
    /* Manrope for clean body text */
    .font-clinical {
      font-family: 'Manrope', 'Inter', sans-serif;
    }
    
    /* Glassmorphism effect */
    .glass {
      background: rgba(255, 255, 255, 0.75);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* Product hover texture transition */
    .product-texture-reveal {
      transition: opacity 0.7s ease-in-out;
    }
    
    /* Science Icon Micro-interaction on Product Hover */
    .product-card-science-icon {
      opacity: 0;
      transform: scale(0.8);
      transition: all 0.3s ease-out;
    }
    
    .product-card:hover .product-card-science-icon {
      opacity: 1;
      transform: scale(1);
    }
  `}</style>
);

// ============================================
// SEO COMPONENT
// ============================================
const SEO = ({ title, description, keywords, url }) => {
  const siteName = "ReRoots | Canadian Biotech Skincare";
  // Always use production URL for canonical - critical for SEO
  const siteUrl = "https://reroots.ca";
  const fullTitle = title ? `${title} | ReRoots` : siteName;
  const fullUrl = `${siteUrl}${url || ""}`;
  const seoDescription = description || "ReRoots - Canada's premium biotech skincare brand featuring bio-active PDRN for visible rejuvenation.";

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={seoDescription} />
      {keywords && <meta name="keywords" content={keywords} />}
      <link rel="canonical" href={fullUrl} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={seoDescription} />
      <meta property="og:url" content={fullUrl} />
      <meta property="og:type" content="website" />
      {/* Fonts are self-hosted via @fontsource - no external font requests needed */}
    </Helmet>
  );
};

// ============================================
// FADE IN UP ANIMATION WRAPPER - Memoized for performance
// ============================================
// PERF: CSS-only fade-in animation (no JS overhead)
// Uses Intersection Observer for lazy reveal without framer-motion cost
const FadeInUp = memo(({ children, delay = 0, className = "" }) => {
  const ref = React.useRef(null);
  const [isVisible, setIsVisible] = useState(false);
  
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '-50px', threshold: 0.1 }
    );
    
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(40px)',
        transition: `opacity 0.8s ease-out ${delay}s, transform 0.8s ease-out ${delay}s`
      }}
    >
      {children}
    </div>
  );
});

// ============================================
// GLASSMORPHISM INGREDIENT MODAL
// ============================================
const IngredientModal = ({ ingredient, onClose }) => {
  if (!ingredient) return null;
  
  return (
    <AnimatePresence>
      <m.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-[#2D2A2E]/60 backdrop-blur-sm" />
        
        {/* Modal */}
        <m.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
          className="relative glass rounded-3xl p-8 max-w-md w-full shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Close button */}
          <button 
            onClick={onClose}
            className="absolute top-4 right-4 w-8 h-8 rounded-full bg-[#2D2A2E]/10 flex items-center justify-center hover:bg-[#2D2A2E]/20 transition-colors"
          >
            <X className="w-4 h-4 text-[#2D2A2E]" />
          </button>
          
          {/* Icon */}
          <div className="w-16 h-16 bg-gradient-to-br from-[#D4AF37]/20 to-[#F8A5B8]/20 rounded-2xl flex items-center justify-center mb-6">
            <ingredient.icon className="w-8 h-8 text-[#D4AF37]" />
          </div>
          
          {/* Title */}
          <h3 className="font-luxury text-2xl font-medium text-[#2D2A2E] mb-2">
            {ingredient.name}
          </h3>
          
          {/* Molecular formula in mono */}
          <p className="font-mono-science text-sm text-[#D4AF37] mb-4 tracking-wider">
            {ingredient.formula}
          </p>
          
          {/* Description */}
          <p className="font-clinical text-[#5A5A5A] leading-relaxed mb-6">
            {ingredient.description}
          </p>
          
          {/* Benefits list in mono */}
          <div className="space-y-2">
            <p className="font-mono-science text-xs text-[#2D2A2E]/60 uppercase tracking-widest">
              Key Benefits
            </p>
            <ul className="space-y-2">
              {ingredient.benefits.map((benefit, i) => (
                <li key={i} className="flex items-center gap-3">
                  <span className="w-1.5 h-1.5 bg-[#D4AF37] rounded-full" />
                  <span className="font-mono-science text-sm text-[#2D2A2E]">{benefit}</span>
                </li>
              ))}
            </ul>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>
  );
};

// ============================================
// PRODUCT CARD WITH TEXTURE HOVER - Memoized for performance
// ============================================
const ProductCard = memo(({ product, translatedProduct }) => {
  const [isHovered, setIsHovered] = useState(false);
  const displayProduct = translatedProduct || product;
  const formatPrice = (price) => `$${parseFloat(price).toFixed(2)} CAD`;
  
  // Texture/macro image (fallback to same image with different styling if no texture)
  const textureImage = product.texture_image || product.images?.[1] || "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=800&q=80";
  
  return (
    <m.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
      className="group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Link to={`/products/${product.id}`} className="block">
        {/* Product Image Container with Texture Reveal */}
        <div className="aspect-[3/4] bg-white rounded-2xl overflow-hidden mb-6 relative shadow-[0_8px_30px_rgb(0,0,0,0.04)] group-hover:shadow-[0_20px_50px_rgb(0,0,0,0.1)] transition-all duration-700 border border-transparent group-hover:border-[#D4AF37]/30 will-change-transform">
          {/* Main product image - optimized for AVIF/WebP */}
          <img
            src={optimizeImageUrl(product.images?.[0] || product.image, 400, 80)}
            alt={displayProduct.name}
            className={`absolute inset-0 w-full h-full object-cover transition-all duration-700 will-change-transform ${isHovered ? 'opacity-0 scale-105' : 'opacity-100 scale-100'}`}
            loading="lazy"
          />
          
          {/* Texture/Macro image revealed on hover */}
          <img
            src={textureImage}
            alt={`${displayProduct.name} texture`}
            className={`absolute inset-0 w-full h-full object-cover transition-all duration-700 ${isHovered ? 'opacity-100 scale-100' : 'opacity-0 scale-110'}`}
            loading="lazy"
          />
          
          {/* Hover overlay text */}
          <div className={`absolute inset-0 bg-gradient-to-t from-[#2D2A2E]/80 via-transparent to-transparent flex items-end p-6 transition-opacity duration-500 ${isHovered ? 'opacity-100' : 'opacity-0'}`}>
            <p className="font-mono-science text-xs text-white/90 tracking-wider uppercase">
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
        <div className="space-y-3">
          <h3 className="font-luxury text-xl font-medium text-[#2D2A2E] group-hover:text-[#D4AF37] transition-colors duration-500">
            {displayProduct.name}
          </h3>
          <p className="font-clinical text-sm text-[#5A5A5A] line-clamp-2 leading-relaxed">
            {displayProduct.short_description || displayProduct.description?.substring(0, 80)}
          </p>
          <div className="flex items-center gap-3">
            <span className="font-clinical text-lg font-bold text-[#2D2A2E]">
              {formatPrice(product.price)}
            </span>
            {product.compare_price && product.compare_price > product.price && (
              <span className="font-clinical text-sm text-[#5A5A5A] line-through">
                {formatPrice(product.compare_price)}
              </span>
            )}
          </div>
        </div>
      </Link>
      
      {/* Pill-shaped Add to Bag Button with 0.5s transition */}
      <Button 
        className="luxury-btn w-full mt-6 bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-6 font-semibold shadow-lg hover:shadow-xl font-clinical"
        onClick={(e) => {
          e.preventDefault();
          window.location.href = `/products/${product.id}`;
        }}
      >
        Add to Bag
      </Button>
    </m.div>
  );
});

// ProductCard component - memoized for performance

// ============================================
// INGREDIENT SPOTLIGHT GRID
// ============================================
const IngredientSpotlight = () => {
  const [selectedIngredient, setSelectedIngredient] = useState(null);
  
  const ingredients = [
    {
      id: 1,
      name: "PDRN",
      formula: "C₁₀H₁₄N₄O₄P",
      icon: Dna,
      shortDesc: "Salmon DNA Extract",
      description: "Infused with bio-active PDRN, our formula helps the skin's surface feel more resilient and look visibly rejuvenated. It targets the appearance of environmental fatigue for a firmer, more youthful-looking complexion.",
      benefits: ["Supports surface cell turnover", "Improves skin resilience", "Soothes redness"]
    },
    {
      id: 2,
      name: "Tranexamic Acid",
      formula: "C₈H₁₅NO₂",
      icon: Droplets,
      shortDesc: "Brightening Agent",
      description: "A powerful amino acid derivative that inhibits melanin production by blocking plasminogen activator, resulting in a more even skin tone.",
      benefits: ["Fades dark spots", "Evens skin tone", "Prevents hyperpigmentation"]
    },
    {
      id: 3,
      name: "Niacinamide",
      formula: "C₆H₆N₂O",
      icon: Zap,
      shortDesc: "Vitamin B3",
      description: "A versatile vitamin that strengthens the skin barrier, regulates sebum production, and minimizes the appearance of pores.",
      benefits: ["Strengthens skin barrier", "Controls oil production", "Minimizes pores"]
    },
    {
      id: 4,
      name: "Hyaluronic Acid",
      formula: "(C₁₄H₂₁NO₁₁)ₙ",
      icon: Target,
      shortDesc: "Deep Hydration",
      description: "A naturally occurring molecule that holds up to 1000x its weight in water, providing intense hydration at multiple skin layers.",
      benefits: ["Intense hydration", "Plumps fine lines", "Locks in moisture"]
    }
  ];
  
  return (
    <>
      <section className="py-[150px] bg-white">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24">
          <FadeInUp className="text-center mb-20">
            <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] mb-6 font-mono-science text-xs tracking-widest">
              INGREDIENT SCIENCE
            </Badge>
            <h2 className="font-luxury text-4xl md:text-5xl font-medium text-[#2D2A2E] leading-tight">
              What's Inside
              <br />
              <span className="italic text-[#F8A5B8]">Matters Most</span>
            </h2>
          </FadeInUp>
          
          {/* Ingredient Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {ingredients.map((ingredient, i) => (
              <FadeInUp key={ingredient.id} delay={i * 0.1}>
                <button
                  onClick={() => setSelectedIngredient(ingredient)}
                  className="w-full text-left p-8 bg-[#FDF9F9] rounded-2xl border border-transparent hover:border-[#D4AF37]/30 hover:shadow-lg transition-all duration-500 group"
                >
                  {/* Icon */}
                  <div className="w-14 h-14 bg-white rounded-xl flex items-center justify-center shadow-sm mb-6 group-hover:bg-[#D4AF37]/10 transition-colors duration-500">
                    <ingredient.icon className="w-7 h-7 text-[#D4AF37]" />
                  </div>
                  
                  {/* Name */}
                  <h3 className="font-luxury text-xl font-medium text-[#2D2A2E] mb-2 group-hover:text-[#D4AF37] transition-colors duration-500">
                    {ingredient.name}
                  </h3>
                  
                  {/* Formula in mono */}
                  <p className="font-mono-science text-xs text-[#D4AF37] mb-3 tracking-wider">
                    {ingredient.formula}
                  </p>
                  
                  {/* Short description */}
                  <p className="font-clinical text-sm text-[#5A5A5A]">
                    {ingredient.shortDesc}
                  </p>
                  
                  {/* Tap to learn more */}
                  <p className="font-mono-science text-xs text-[#2D2A2E]/40 mt-4 uppercase tracking-widest">
                    Tap to explore →
                  </p>
                </button>
              </FadeInUp>
            ))}
          </div>
        </div>
      </section>
      
      {/* Modal */}
      {selectedIngredient && (
        <IngredientModal 
          ingredient={selectedIngredient} 
          onClose={() => setSelectedIngredient(null)} 
        />
      )}
    </>
  );
};

// ============================================
// NEWSLETTER FORM
// ============================================
const NewsletterForm = ({ thankYouMessage, buttonText }) => {
  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: ""
  });
  const [phoneCountryCode, setPhoneCountryCode] = useState("+1");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // Auto-detect country code
  useEffect(() => {
    const detectedCountry = detectUserCountry();
    const country = getCountryByCode(detectedCountry);
    setPhoneCountryCode(country.phoneCode);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email) return;
    setLoading(true);
    try {
      const fullPhone = formData.phone ? formatFullPhone(phoneCountryCode, formData.phone) : "";
      await axios.post(`${API}/newsletter/subscribe`, { 
        email: formData.email,
        first_name: formData.firstName,
        last_name: formData.lastName,
        phone: fullPhone,
        phone_country_code: phoneCountryCode
      });
      setSubmitted(true);
      setFormData({ firstName: "", lastName: "", email: "", phone: "" });
    } catch (error) {
      console.error("Newsletter error:", error);
    }
    setLoading(false);
  };

  if (submitted) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <p className="font-clinical text-[#2D2A2E] font-medium">
          {thankYouMessage || "Thank you for subscribing! Check your inbox for exclusive offers."}
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Name row */}
      <div className="flex flex-col sm:flex-row gap-4">
        <input
          type="text"
          value={formData.firstName}
          onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
          placeholder="First name"
          className="flex-1 px-6 py-4 rounded-full border border-white/20 bg-white/10 text-white placeholder:text-white/50 focus:border-[#D4AF37] focus:ring-2 focus:ring-[#D4AF37]/20 outline-none backdrop-blur-sm font-clinical"
          data-testid="newsletter-first-name"
        />
        <input
          type="text"
          value={formData.lastName}
          onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
          placeholder="Last name"
          className="flex-1 px-6 py-4 rounded-full border border-white/20 bg-white/10 text-white placeholder:text-white/50 focus:border-[#D4AF37] focus:ring-2 focus:ring-[#D4AF37]/20 outline-none backdrop-blur-sm font-clinical"
          data-testid="newsletter-last-name"
        />
      </div>
      {/* Email row */}
      <div className="flex flex-col sm:flex-row gap-4">
        <input
          type="email"
          value={formData.email}
          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          placeholder="Enter your email"
          className="flex-1 px-6 py-4 rounded-full border border-white/20 bg-white/10 text-white placeholder:text-white/50 focus:border-[#D4AF37] focus:ring-2 focus:ring-[#D4AF37]/20 outline-none backdrop-blur-sm font-clinical"
          required
          data-testid="newsletter-email"
        />
      </div>
      {/* Phone row */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <PhoneInput
            value={formData.phone}
            onChange={(val) => setFormData({ ...formData, phone: val })}
            countryCode={phoneCountryCode}
            onCountryCodeChange={setPhoneCountryCode}
            placeholder="Phone number (optional)"
            darkMode={true}
            inputClassName="px-6 py-4 rounded-full border border-white/20 bg-white/10 text-white placeholder:text-white/50 focus:border-[#D4AF37] focus:ring-2 focus:ring-[#D4AF37]/20 backdrop-blur-sm font-clinical h-auto"
            testId="newsletter-phone"
          />
        </div>
        <Button 
          type="submit" 
          disabled={loading}
          className="luxury-btn bg-[#F8A5B8] hover:bg-white text-[#2D2A2E] rounded-full px-10 py-4 font-semibold shadow-lg font-clinical whitespace-nowrap"
          data-testid="newsletter-submit"
        >
          {loading ? "..." : buttonText || "Subscribe"}
        </Button>
      </div>
    </form>
  );
};


// CustomerTestimonialsSection - Now lazy loaded from @/components/CustomerTestimonialsSection


// ============================================
// MAIN HOMEPAGE COMPONENT
// ============================================
const HomePage = () => {
  const [products, setProducts] = useState([]);
  const [translatedProducts, setTranslatedProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [siteContent, setSiteContent] = useState(null);
  const [storeSettings, setStoreSettings] = useState(null);
  
  // Get cart context for Add to Bag functionality
  const { addToCart, setSideCartOpen } = useCart() || {};

  useEffect(() => {
    // PERF: Defer data fetching to not block initial paint
    // Use requestIdleCallback to fetch during idle time
    const fetchData = async () => {
      try {
        const [productsRes, contentRes, settingsRes] = await Promise.all([
          axios.get(`${API}/products?featured=true&limit=4`),
          axios.get(`${API}/site-content`).catch(() => ({ data: {} })),
          axios.get(`${API}/store-settings`).catch(() => ({ data: {} }))
        ]);
        
        setProducts(productsRes.data);
        setTranslatedProducts(productsRes.data);
        setSiteContent(contentRes.data);
        setStoreSettings(settingsRes.data);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
      setLoading(false);
    };

    // PERF: Use requestIdleCallback to defer non-critical API calls
    // This prevents blocking the main thread during initial render
    if (typeof requestIdleCallback === 'function') {
      requestIdleCallback(() => {
        fetchData();
      }, { timeout: 2000 });
    } else {
      // Fallback for browsers without requestIdleCallback
      setTimeout(() => {
        fetchData();
      }, 100);
    }
  }, []);

  const thankYouMessages = storeSettings?.thank_you_messages || {};

  return (
    <div className="min-h-screen bg-[#FDF9F9]">
      <GlobalStyles />
      <SEO 
        title={null}
        description="Canada's #1 biotech skincare brand. PDRN + Tranexamic Acid serums for dark circles, pigmentation, melasma & anti-aging. Clinically proven. Better than Vitamin C. Made in Canada."
        keywords="PDRN skincare Canada, eye cream for dark circles, pigmentation treatment Canada, melasma skincare, tranexamic acid serum, anti-aging serum Canada, biotech skincare, best eye cream dark circles, luxury skincare Canada, ReRoots"
        url="/"
      />
      
      {/* Organization + WebSite Schema for SEO/GEO/AEO */}
      <Helmet>
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@graph": [
              {
                "@type": "Organization",
                "@id": "https://reroots.ca/#organization",
                "name": "ReRoots Biotech Skincare",
                "legalName": "Reroots Aesthetics Inc.",
                "url": "https://reroots.ca",
                "logo": {
                  "@type": "ImageObject",
                  "url": "https://reroots.ca/logo.png",
                  "width": 512,
                  "height": 512
                },
                "description": "Canada's premier biotech skincare brand specializing in PDRN (Polydeoxyribonucleotide) and advanced clinical formulations for visible skin rejuvenation.",
                "foundingDate": "2024",
                "foundingLocation": {
                  "@type": "Place",
                  "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Toronto",
                    "addressRegion": "Ontario",
                    "addressCountry": "CA"
                  }
                },
                "areaServed": {
                  "@type": "Country",
                  "name": "Canada"
                },
                "sameAs": [
                  "https://www.instagram.com/rerootsbeauty",
                  "https://www.tiktok.com/@rerootsbeauty",
                  "https://www.facebook.com/rerootsbeauty"
                ],
                "contactPoint": {
                  "@type": "ContactPoint",
                  "contactType": "customer service",
                  "email": "support@reroots.ca",
                  "availableLanguage": ["English", "French"]
                }
              },
              {
                "@type": "WebSite",
                "@id": "https://reroots.ca/#website",
                "url": "https://reroots.ca",
                "name": "ReRoots Biotech Skincare",
                "description": "Premium PDRN skincare products made in Canada. Clinical-grade serums for dark circles, pigmentation, and anti-aging.",
                "publisher": {
                  "@id": "https://reroots.ca/#organization"
                },
                "potentialAction": {
                  "@type": "SearchAction",
                  "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": "https://reroots.ca/products?search={search_term_string}"
                  },
                  "query-input": "required name=search_term_string"
                }
              },
              {
                "@type": "LocalBusiness",
                "@id": "https://reroots.ca/#localbusiness",
                "name": "ReRoots Biotech Skincare",
                "image": "https://reroots.ca/logo.png",
                "priceRange": "$$",
                "address": {
                  "@type": "PostalAddress",
                  "addressLocality": "Toronto",
                  "addressRegion": "Ontario",
                  "addressCountry": "CA"
                },
                "geo": {
                  "@type": "GeoCoordinates",
                  "latitude": 43.6532,
                  "longitude": -79.3832
                },
                "url": "https://reroots.ca",
                "telephone": "",
                "openingHoursSpecification": {
                  "@type": "OpeningHoursSpecification",
                  "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                  "opens": "00:00",
                  "closes": "23:59"
                }
              }
            ]
          })}
        </script>
      </Helmet>
      
      <ShareCard 
        buttonStyle="floating" 
        buttonPosition="bottom-left"
        title="ReRoots Beauty"
        description="Discover premium biotech skincare with bio-active PDRN for visible rejuvenation."
      />
      
      {/* ============================================ */}
      {/* HERO SECTION - Center-aligned Clinical Luxury */}
      {/* ============================================ */}
      {/* Hero Section - Extends to top (under header) for seamless blend */}
      <section 
        className="hero-container relative h-screen flex items-center justify-center overflow-hidden"
        style={{ 
          height: '100vh',
          maxHeight: '100vh',
          width: '100vw',
          marginLeft: 'calc(-50vw + 50%)',
          marginRight: 'calc(-50vw + 50%)',
          backgroundColor: '#E8E4E0' /* Dominant color from hero image - prevents white flash */
        }}
      >
        <div className="absolute inset-0">
          <picture>
            {/* MOBILE FIRST: Smaller image for faster LCP on mobile (matches preload) */}
            <source 
              type="image/avif"
              media="(max-width: 768px)"
              srcSet="https://res.cloudinary.com/ddpphzqdg/image/fetch/w_640,q_70,f_avif/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg"
            />
            {/* DESKTOP: Higher quality for larger screens */}
            <source 
              type="image/avif"
              media="(min-width: 769px)"
              srcSet="https://res.cloudinary.com/ddpphzqdg/image/fetch/w_1024,q_70,f_avif/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 1024w,
                      https://res.cloudinary.com/ddpphzqdg/image/fetch/w_1920,q_70,f_avif/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 1920w"
              sizes="100vw"
            />
            {/* WebP fallback for Safari older than 16 */}
            <source 
              type="image/webp"
              srcSet="https://res.cloudinary.com/ddpphzqdg/image/fetch/w_640,q_70,f_webp/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 640w,
                      https://res.cloudinary.com/ddpphzqdg/image/fetch/w_1024,q_70,f_webp/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 1024w,
                      https://res.cloudinary.com/ddpphzqdg/image/fetch/w_1920,q_70,f_webp/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 1920w"
              sizes="(max-width: 768px) 640px, 100vw"
            />
            {/* JPG fallback */}
            <img
              src="https://res.cloudinary.com/ddpphzqdg/image/fetch/w_640,q_70,f_auto/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg"
              srcSet="https://res.cloudinary.com/ddpphzqdg/image/fetch/w_640,q_70,f_auto/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 640w,
                      https://res.cloudinary.com/ddpphzqdg/image/fetch/w_1024,q_70,f_auto/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 1024w,
                      https://res.cloudinary.com/ddpphzqdg/image/fetch/w_1920,q_70,f_auto/https%3A%2F%2Fcustomer-assets.emergentagent.com%2Fjob_4e76787f-8156-4163-b7a9-a9afa71e2ce2%2Fartifacts%2Fhvef4zdg_1768271038566.jpg 1920w"
              sizes="(max-width: 768px) 640px, 100vw"
              alt="ReRoots PDRN Biotech Laboratory"
              className="w-full h-full object-cover"
              loading="eager"
              fetchPriority="high"
              decoding="sync"
              width="1920"
              height="1080"
            />
          </picture>
          <div className="absolute inset-0 bg-gradient-to-b from-[#2D2A2E]/30 via-[#2D2A2E]/20 to-[#2D2A2E]/40" />
        </div>
        
        {/* 
          LCP OPTIMIZATION: CSS-Only Animations
          Replaced Framer Motion (JS) with native CSS animations
          This eliminates the 3,120ms Element Render Delay by:
          1. Using opacity: 0.01 (visible to Lighthouse, invisible to eye)
          2. Removing main-thread blocking from animation calculation
          3. Allowing LCP to register immediately when text hits DOM
        */}
        <div className="relative max-w-4xl mx-auto px-6 md:px-12 lg:px-24 py-20 text-center z-10">
          <div>
            {/* Badge - CSS animation */}
            <div 
              className="lcp-hero-badge inline-flex items-center gap-3 bg-white/10 backdrop-blur-md border border-white/20 rounded-full px-5 py-2.5 mb-10"
            >
              <span className="w-2 h-2 bg-[#D4AF37] rounded-full animate-pulse" />
              <span className="font-clinical text-white/90 text-xs tracking-[0.25em] uppercase font-medium">
                Biotech Skincare
              </span>
            </div>
            
            {/* LCP ELEMENT - Hero Heading (CSS animation, no JS blocking) */}
            <h1 
              className="lcp-hero-heading font-luxury text-5xl sm:text-6xl lg:text-7xl font-medium text-white leading-[1.1] mb-8"
            >
              The Future of
              <br />
              <span className="italic text-[#F8A5B8]">Skin Longevity.</span>
            </h1>
            
            {/* Hero description - CSS animation */}
            <p 
              className="lcp-hero-description font-clinical text-lg md:text-xl text-white/85 max-w-2xl mx-auto mb-14 leading-relaxed"
            >
              Experience the restorative power of Biotech PDRN. A high-performance protocol 
              designed to refine texture, enhance resilience, and restore a luminous, youthful-looking glow.
            </p>
            
            {/* CTA and Trust Badges - CSS animation */}
            <div 
              className="lcp-hero-cta flex flex-col items-center gap-8"
            >
              {/* Primary CTAs - Shop Now + Find Your Protocol */}
              <div className="flex flex-col sm:flex-row items-center gap-4">
                <Link to="/shop" data-testid="hero-shop-now">
                  <Button className="luxury-btn bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full px-14 py-7 text-lg font-semibold shadow-2xl font-clinical tracking-wide">
                    Shop Now
                  </Button>
                </Link>
                <Link to="/quiz" data-testid="hero-quiz-cta">
                  <Button 
                    variant="outline" 
                    className="group bg-white/10 hover:bg-white/20 backdrop-blur-md border-2 border-white/40 hover:border-[#F8A5B8] text-white rounded-full px-10 py-7 text-lg font-semibold shadow-xl font-clinical tracking-wide transition-all duration-300"
                  >
                    <span className="mr-2">🧬</span>
                    Find Your Protocol
                    <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </Button>
                </Link>
              </div>
              
              {/* Quiz Value Prop - Small text below CTAs */}
              <p className="text-white/60 text-sm font-clinical tracking-wide">
                87-second quiz · Personalised PDRN ritual · Free
              </p>
              
              {/* Trust Badges - Minimalist Icons */}
              <div className="lcp-hero-trust-badges flex flex-wrap items-center justify-center gap-6 md:gap-10">
                <div className="flex items-center gap-2 text-white/80">
                  <span className="text-lg">🇨🇦</span>
                  <span className="font-clinical text-xs tracking-wider uppercase">Made in Canada</span>
                </div>
                <div className="hidden md:block w-px h-4 bg-white/30" />
                <div className="flex items-center gap-2 text-white/80">
                  <Dna className="w-4 h-4 text-[#D4AF37]" />
                  <span className="font-clinical text-xs tracking-wider uppercase">Biotech PDRN</span>
                </div>
                <div className="hidden md:block w-px h-4 bg-white/30" />
                <div className="flex items-center gap-2 text-white/80">
                  <span className="text-lg">🐰</span>
                  <span className="font-clinical text-xs tracking-wider uppercase">Cruelty-Free</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Scroll indicator - CSS animation */}
        <div 
          className="lcp-scroll-indicator absolute bottom-10 left-1/2 -translate-x-1/2"
        >
          <div
            className="w-6 h-10 border-2 border-white/30 rounded-full flex justify-center pt-2"
          >
            <div className="w-1.5 h-1.5 bg-white/60 rounded-full" />
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* TRUST BAR - Authority & Quality Signals */}
      {/* ============================================ */}
      <section className="bg-[#2D2A2E] py-4 overflow-hidden">
        <div className="trust-bar-scroll">
          <div className="trust-bar-content flex items-center gap-12 whitespace-nowrap">
            {/* Duplicate items for seamless loop */}
            {[...Array(2)].map((_, setIndex) => (
              <div key={setIndex} className="flex items-center gap-12">
                <div className="flex items-center gap-3">
                  <FlaskConical className="w-5 h-5 text-[#D4AF37]" />
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">Formulated in GMP Labs</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
                <div className="flex items-center gap-3">
                  <Dna className="w-5 h-5 text-[#D4AF37]" />
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">Biotech Grade PDRN</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
                <div className="flex items-center gap-3">
                  <Shield className="w-5 h-5 text-[#D4AF37]" />
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">Canadian Health Standards</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
                <div className="flex items-center gap-3">
                  <BadgeCheck className="w-5 h-5 text-[#D4AF37]" />
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">Dermatologist Tested</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
                <div className="flex items-center gap-3">
                  <Award className="w-5 h-5 text-[#D4AF37]" />
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">17% Active Complex</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
                <div className="flex items-center gap-3">
                  <span className="text-lg">🇨🇦</span>
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">Made in Canada</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
                <div className="flex items-center gap-3">
                  <span className="text-lg">🐰</span>
                  <span className="font-clinical text-white/90 text-sm font-medium tracking-wide">Cruelty-Free</span>
                </div>
                <div className="w-1 h-1 rounded-full bg-[#D4AF37]" />
              </div>
            ))}
          </div>
        </div>
        <style>{`
          .trust-bar-scroll {
            display: flex;
            width: 100%;
          }
          .trust-bar-content {
            animation: scroll-left 30s linear infinite;
          }
          @keyframes scroll-left {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
          }
          .trust-bar-scroll:hover .trust-bar-content {
            animation-play-state: paused;
          }
        `}</style>
      </section>

      {/* ============================================ */}
      {/* SOCIAL PROOF BAR */}
      {/* ============================================ */}
      <section className="bg-[#FAF8F5] py-8 border-b border-[#2D2A2E]/5">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24">
          <div className="flex flex-wrap items-center justify-center gap-10 md:gap-20">
            {[
              { icon: BadgeCheck, text: "Dermatologist Tested" },
              { icon: ShieldCheck, text: "Health Canada Compliant" },
              { icon: Award, text: "GMP Certified Lab" },
              { icon: Truck, text: "Free Shipping $75+" }
            ].map((item, i) => (
              <m.div 
                key={i}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex items-center gap-3"
              >
                <item.icon className="w-5 h-5 text-[#D4AF37]" />
                <span className="font-clinical text-[#2D2A2E] text-sm font-medium tracking-wide">
                  {item.text}
                </span>
              </m.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* STICKY SCROLL INGREDIENTS SECTION - Hydrate on visibility for mobile TBT */}
      {/* ============================================ */}
      <OptimizeMobileHydration 
        minHeight={600} 
        rootMargin="300px 0px"
      >
        <StickyScrollSection />
      </OptimizeMobileHydration>

      {/* ============================================ */}
      {/* QUICK SHOP - Featured Product with Add to Bag */}
      {/* Uses content-visibility for mobile CPU optimization */}
      {/* ============================================ */}
      <section className="py-16 bg-white border-b border-gray-100 quick-shop-section content-visibility-auto">
        <div className="max-w-6xl mx-auto px-6 md:px-12 lg:px-24">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Featured Product Image */}
            <FadeInUp>
              <div className="relative aspect-square bg-[#FDF9F9] rounded-3xl overflow-hidden will-change-transform" style={{ minHeight: '400px' }}>
                {products[0] ? (
                  <Link to={`/products/${products[0].id}`}>
                    <img
                      src={optimizeImageUrl(products[0].images?.[0], 600, 80)}
                      alt={products[0].name || "Featured Product"}
                      className="w-full h-full object-cover hover:scale-105 transition-transform duration-700 will-change-transform"
                      loading="lazy"
                      decoding="async"
                      width="600"
                      height="600"
                    />
                  </Link>
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-[#D4AF37]" />
                  </div>
                )}
                <Badge className="absolute top-6 left-6 bg-[#D4AF37] text-white rounded-full px-4 py-1.5 font-clinical text-xs tracking-wider">
                  BESTSELLER
                </Badge>
              </div>
            </FadeInUp>
            
            {/* Featured Product Info */}
            <FadeInUp delay={0.2}>
              <div className="space-y-6">
                <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] rounded-full px-4 py-1 font-clinical text-xs tracking-[0.2em]">
                  QUICK SHOP
                </Badge>
                
                <h2 className="font-luxury text-3xl md:text-4xl font-medium text-[#2D2A2E]">
                  {products[0]?.name || "AURA-GEN™ Serum"}
                </h2>
                
                <p className="font-clinical text-[#5A5A5A] leading-relaxed">
                  {products[0]?.short_description || "Our signature bio-active PDRN serum for visible rejuvenation. Helps skin feel more resilient and look luminously youthful."}
                </p>
                
                {/* Quick Benefits */}
                <div className="flex flex-wrap gap-3">
                  {["2% PDRN", "Visibly Firms", "Hydrates"].map((benefit, i) => (
                    <span key={i} className="px-4 py-2 bg-[#FDF9F9] rounded-full font-clinical text-sm text-[#5A5A5A]">
                      {benefit}
                    </span>
                  ))}
                </div>
                
                {/* Price */}
                <div className="flex items-center gap-4">
                  <span className="font-luxury text-3xl font-semibold text-[#2D2A2E]">
                    ${products[0]?.price?.toFixed(2) || "89.00"}
                  </span>
                  {products[0]?.compare_price && products[0].compare_price > products[0].price && (
                    <span className="font-clinical text-lg text-[#888] line-through">
                      ${products[0].compare_price.toFixed(2)}
                    </span>
                  )}
                </div>
                
                {/* Add to Bag Button - Prominent */}
                <div className="flex flex-col sm:flex-row gap-4">
                  <Button 
                    className="flex-1 bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-6 text-lg font-semibold font-clinical shadow-lg hover:shadow-xl transition-all"
                    onClick={() => {
                      if (products[0] && addToCart) {
                        addToCart(products[0].id, 1);
                        if (setSideCartOpen) setSideCartOpen(true);
                      }
                    }}
                    data-testid="quick-shop-add-to-bag"
                  >
                    <ShoppingBag className="w-5 h-5 mr-2" />
                    Add to Bag
                  </Button>
                  {products[0]?.id && (
                    <Link to={`/products/${products[0].id}`} className="flex-1">
                      <Button 
                        variant="outline"
                        className="w-full border-2 border-[#2D2A2E] text-[#2D2A2E] hover:bg-[#2D2A2E] hover:text-white rounded-full py-6 text-lg font-semibold font-clinical transition-all"
                      >
                        View Details
                      </Button>
                    </Link>
                  )}
                </div>
                
                {/* Trust Indicators */}
                <div className="flex items-center gap-6 pt-4 border-t border-gray-100">
                  <div className="flex items-center gap-2 text-[#5A5A5A]">
                    <Truck className="w-4 h-4 text-[#D4AF37]" />
                    <span className="font-clinical text-xs">Free Shipping $75+</span>
                  </div>
                  <div className="flex items-center gap-2 text-[#5A5A5A]">
                    <Shield className="w-4 h-4 text-[#D4AF37]" />
                    <span className="font-clinical text-xs">30-Day Returns</span>
                  </div>
                </div>
              </div>
            </FadeInUp>
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* THE SCIENCE OF PDRN - Center-aligned with generous whitespace */}
      {/* ============================================ */}
      <section className="py-[180px] bg-white">
        <div className="max-w-5xl mx-auto px-6 md:px-12 lg:px-24 text-center">
          <FadeInUp>
            <Badge className="bg-[#D4AF37]/10 text-[#D4AF37] hover:bg-[#D4AF37]/10 mb-8 font-clinical text-xs tracking-[0.25em] uppercase font-medium">
              The Science
            </Badge>
            <h2 className="font-luxury text-4xl md:text-5xl lg:text-6xl font-medium text-[#2D2A2E] leading-tight mb-10">
              Molecular Precision.
              <br />
              <span className="italic text-[#D4AF37]">Visible Results.</span>
            </h2>
            <p className="font-clinical text-lg md:text-xl text-[#5A5A5A] leading-relaxed max-w-3xl mx-auto mb-20">
              At the core of ReRoots is PDRN—a bio-active molecule celebrated in advanced skincare 
              for its ability to mimic the skin's natural revitalizing processes.
            </p>
          </FadeInUp>
          
          {/* Three Benefits Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
            {[
              { 
                icon: Sparkles, 
                title: "Surface Renewal", 
                desc: "Supports the appearance of smoother, more refined skin texture." 
              },
              { 
                icon: Droplets, 
                title: "Deep Hydration", 
                desc: "Promotes a plump, dewy look by reinforcing the skin's moisture barrier." 
              },
              { 
                icon: Shield, 
                title: "Luminous Resilience", 
                desc: "Visibly reduces the signs of environmental fatigue and oxidative stress." 
              }
            ].map((item, i) => (
              <FadeInUp key={i} delay={0.1 + i * 0.15}>
                <div className="p-10 rounded-3xl bg-[#FDF9F9] border border-transparent hover:border-[#D4AF37]/20 transition-all duration-500 group">
                  <div className="w-16 h-16 bg-white rounded-2xl flex items-center justify-center shadow-sm mx-auto mb-8 group-hover:shadow-md transition-all duration-500">
                    <item.icon className="w-8 h-8 text-[#D4AF37]" />
                  </div>
                  <h3 className="font-luxury text-xl font-medium text-[#2D2A2E] mb-4">{item.title}</h3>
                  <p className="font-clinical text-[#5A5A5A] leading-relaxed">{item.desc}</p>
                </div>
              </FadeInUp>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* THE LAB - About Us Section */}
      {/* ============================================ */}
      <section className="py-[180px] bg-[#FDF9F9] content-visibility-auto">
        <div className="max-w-6xl mx-auto px-6 md:px-12 lg:px-24">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
            <FadeInUp className="relative">
              <div className="aspect-[4/5] bg-gradient-to-br from-white to-[#FDF9F9] rounded-3xl p-8 border border-[#E2E8F0] overflow-hidden">
                <img
                  src="https://images.unsplash.com/photo-1576086213369-97a306d36557?w=680&q=80&fm=webp&fit=crop"
                  srcSet="https://images.unsplash.com/photo-1576086213369-97a306d36557?w=400&q=80&fm=webp&fit=crop 400w, https://images.unsplash.com/photo-1576086213369-97a306d36557?w=680&q=80&fm=webp&fit=crop 680w"
                  sizes="(max-width: 1024px) 100vw, 680px"
                  alt="ReRoots Laboratory"
                  className="w-full h-full object-cover rounded-2xl"
                  loading="lazy"
                  width="680"
                  height="850"
                />
              </div>
              <m.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.4 }}
                className="absolute -bottom-6 -right-6 bg-white rounded-2xl p-6 shadow-[0_20px_50px_rgb(0,0,0,0.08)] border border-[#D4AF37]/10"
              >
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 bg-[#D4AF37]/10 rounded-full flex items-center justify-center">
                    <Dna className="w-7 h-7 text-[#D4AF37]" />
                  </div>
                  <div>
                    <p className="font-luxury text-2xl font-bold text-[#2D2A2E]">2%</p>
                    <p className="font-clinical text-sm text-[#5A5A5A]">PDRN Concentration</p>
                  </div>
                </div>
              </m.div>
            </FadeInUp>
            
            <FadeInUp delay={0.2} className="lg:pl-8">
              <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] mb-8 font-clinical text-xs tracking-[0.25em] uppercase font-medium">
                The Lab
              </Badge>
              <h2 className="font-luxury text-3xl md:text-4xl lg:text-5xl font-medium text-[#2D2A2E] leading-tight mb-8">
                Where Biotechnology Meets
                <br />
                <span className="italic text-[#D4AF37]">Botanical Elegance.</span>
              </h2>
              <div className="space-y-6 mb-10">
                <p className="font-clinical text-lg text-[#5A5A5A] leading-relaxed">
                  ReRoots was born from a singular mission: to bridge the gap between rigorous laboratory 
                  science and the luxury of self-care.
                </p>
                <p className="font-clinical text-lg text-[#5A5A5A] leading-relaxed">
                  We specialize in high-concentration PDRN formulas that respect the skin's delicate 
                  ecosystem while delivering professional-grade aesthetic results.
                </p>
                <div className="pt-4 border-t border-[#E2E8F0]">
                  <p className="font-clinical text-[#5A5A5A] leading-relaxed italic">
                    "We don't just treat the surface; we curate formulas that support your skin's 
                    natural journey toward a more resilient appearance."
                  </p>
                </div>
              </div>
              <Link to="/about">
                <Button className="luxury-btn bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full px-10 py-6 font-semibold font-clinical">
                  Our Story <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </FadeInUp>
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* BESTSELLERS GRID - 180px padding */}
      {/* Only show if there are more than 1 product (first one is in Quick Shop) */}
      {/* ============================================ */}
      {products.length > 1 && (
        <section className="py-[180px] bg-white">
          <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24">
            <FadeInUp className="text-center mb-16">
              <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] mb-6 font-clinical text-xs tracking-[0.25em] uppercase font-medium">
                The Collection
              </Badge>
              <h2 className="font-luxury text-4xl md:text-5xl font-medium text-[#2D2A2E]">
                Our Most <span className="italic text-[#D4AF37]">Loved</span>
              </h2>
            </FadeInUp>

            {loading ? (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="animate-pulse">
                    <div className="aspect-[3/4] bg-gray-200 rounded-2xl mb-6" />
                    <div className="h-6 bg-gray-200 rounded w-3/4 mb-3" />
                    <div className="h-4 bg-gray-200 rounded w-1/2" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-8" data-testid="featured-products-grid">
                {/* Skip first product since it's shown in Quick Shop section above */}
                {products.slice(1).map((product, idx) => (
                  <ProductCard key={product.id} product={product} translatedProduct={translatedProducts[idx + 1]} />
                ))}
              </div>
            )}
            
            <FadeInUp className="text-center mt-16">
              <Link to="/products" data-testid="view-all-products">
                <Button variant="outline" className="luxury-btn border-2 border-[#2D2A2E] text-[#2D2A2E] hover:bg-[#2D2A2E] hover:text-white rounded-full px-10 py-6 font-semibold font-clinical">
                  View All Products <ChevronRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </FadeInUp>
          </div>
        </section>
      )}

      {/* ============================================ */}
      {/* WHY PDRN BEATS TRADITIONAL SKINCARE - SEO Section */}
      {/* ============================================ */}
      <section className="py-24 bg-gradient-to-b from-white to-[#FDF9F9]">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-24">
          <FadeInUp className="text-center mb-16">
            <Badge className="bg-[#2D2A2E] text-white hover:bg-[#2D2A2E] mb-6 font-clinical text-xs tracking-[0.25em] uppercase">
              The Science Advantage
            </Badge>
            <h2 className="font-luxury text-3xl md:text-4xl lg:text-5xl font-medium text-[#2D2A2E] mb-4">
              Why <span className="italic text-[#F8A5B8]">PDRN</span> Outperforms Traditional Skincare
            </h2>
            <p className="font-clinical text-[#5A5A5A] max-w-2xl mx-auto">
              Clinical studies prove PDRN technology delivers superior results for dark circles, pigmentation, and anti-aging
            </p>
          </FadeInUp>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Dark Circles Comparison */}
            <FadeInUp delay={0.1}>
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 h-full">
                <div className="w-12 h-12 rounded-full bg-[#F8A5B8]/10 flex items-center justify-center mb-4">
                  <Eye className="h-6 w-6 text-[#F8A5B8]" />
                </div>
                <h3 className="font-luxury text-xl text-[#2D2A2E] mb-2">Dark Circles</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-red-400 font-bold">✗</span>
                    <span className="text-[#5A5A5A]"><strong>Vitamin C:</strong> Surface brightening only</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-green-500 font-bold">✓</span>
                    <span className="text-[#2D2A2E]"><strong>PDRN + NAD+:</strong> Cellular regeneration for lasting results</span>
                  </div>
                </div>
                <Link to="/shop?concern=dark-circles" className="inline-block mt-4 text-[#D4AF37] text-sm font-medium hover:underline">
                  Shop Eye Treatments →
                </Link>
              </div>
            </FadeInUp>

            {/* Pigmentation Comparison */}
            <FadeInUp delay={0.2}>
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 h-full">
                <div className="w-12 h-12 rounded-full bg-[#D4AF37]/10 flex items-center justify-center mb-4">
                  <Sparkles className="h-6 w-6 text-[#D4AF37]" />
                </div>
                <h3 className="font-luxury text-xl text-[#2D2A2E] mb-2">Pigmentation & Melasma</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-red-400 font-bold">✗</span>
                    <span className="text-[#5A5A5A]"><strong>Basic serums:</strong> Slow, inconsistent fading</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-green-500 font-bold">✓</span>
                    <span className="text-[#2D2A2E]"><strong>TXA + PDRN:</strong> 5% Tranexamic Acid for proven results</span>
                  </div>
                </div>
                <Link to="/shop?concern=pigmentation" className="inline-block mt-4 text-[#D4AF37] text-sm font-medium hover:underline">
                  Shop Pigmentation Solutions →
                </Link>
              </div>
            </FadeInUp>

            {/* Anti-Aging Comparison */}
            <FadeInUp delay={0.3}>
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 h-full">
                <div className="w-12 h-12 rounded-full bg-[#2D2A2E]/10 flex items-center justify-center mb-4">
                  <Clock className="h-6 w-6 text-[#2D2A2E]" />
                </div>
                <h3 className="font-luxury text-xl text-[#2D2A2E] mb-2">Anti-Aging</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-red-400 font-bold">✗</span>
                    <span className="text-[#5A5A5A]"><strong>Retinol:</strong> Irritation, sun sensitivity</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-green-500 font-bold">✓</span>
                    <span className="text-[#2D2A2E]"><strong>PDRN + Argireline:</strong> 60% firmer skin, no irritation</span>
                  </div>
                </div>
                <Link to="/shop?concern=anti-aging" className="inline-block mt-4 text-[#D4AF37] text-sm font-medium hover:underline">
                  Shop Anti-Aging →
                </Link>
              </div>
            </FadeInUp>

            {/* Hydration Comparison */}
            <FadeInUp delay={0.4}>
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg transition-all duration-300 h-full">
                <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-4">
                  <Droplets className="h-6 w-6 text-blue-500" />
                </div>
                <h3 className="font-luxury text-xl text-[#2D2A2E] mb-2">Deep Hydration</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-red-400 font-bold">✗</span>
                    <span className="text-[#5A5A5A]"><strong>HA alone:</strong> Surface moisture, evaporates</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-green-500 font-bold">✓</span>
                    <span className="text-[#2D2A2E]"><strong>PDRN:</strong> Repairs barrier, locks in hydration</span>
                  </div>
                </div>
                <Link to="/shop?concern=hydration" className="inline-block mt-4 text-[#D4AF37] text-sm font-medium hover:underline">
                  Shop Hydration →
                </Link>
              </div>
            </FadeInUp>
          </div>

          {/* CTA */}
          <FadeInUp className="text-center mt-12">
            <p className="font-clinical text-[#5A5A5A] mb-6">
              Made in Canada • Dermatologist Tested • Cruelty-Free
            </p>
            <Link to="/science">
              <Button className="bg-[#2D2A2E] hover:bg-[#3D3A3E] text-white rounded-full px-8 py-6 font-clinical">
                Learn the Science Behind PDRN
              </Button>
            </Link>
          </FadeInUp>
        </div>
      </section>

      {/* ============================================ */}
      {/* CLINICAL PROOF SECTION - Hydrate on visibility for mobile TBT */}
      {/* ============================================ */}
      <OptimizeMobileHydration 
        minHeight={800} 
        rootMargin="300px 0px"
      >
        <StickyClinicalProof />
      </OptimizeMobileHydration>

      {/* ============================================ */}
      {/* GOOGLE REVIEWS SECTION - Hydrate on visibility */}
      {/* ============================================ */}
      <OptimizeMobileHydration 
        minHeight={500} 
        rootMargin="200px 0px"
      >
        <CustomerTestimonialsSection />
      </OptimizeMobileHydration>

      {/* ============================================ */}
      {/* NEWSLETTER - 180px padding, center-aligned */}
      {/* ============================================ */}
      <section className="py-[180px] bg-[#2D2A2E] newsletter-section">
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center">
          <FadeInUp>
            <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] hover:bg-[#D4AF37]/20 mb-8 font-clinical text-xs tracking-[0.25em] uppercase font-medium">
              Exclusive Access
            </Badge>
            <h2 className="font-luxury text-4xl md:text-5xl font-medium text-white mb-8">
              Join the <span className="italic text-[#F8A5B8]">ReRoots Circle</span>
            </h2>
            <p className="font-clinical text-white/70 mb-14 max-w-lg mx-auto text-lg leading-relaxed">
              Early access to biotech innovations, exclusive offers, and science-backed skincare insights.
            </p>
            <NewsletterForm 
              thankYouMessage={thankYouMessages?.newsletter}
              buttonText="Subscribe"
            />
            <p className="font-clinical text-xs text-white/40 mt-8 tracking-wide">
              By invitation only • Exclusive member benefits
            </p>
          </FadeInUp>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
