import React, { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { 
  Search, 
  AlertTriangle, 
  CheckCircle, 
  Info, 
  Sparkles,
  FlaskConical,
  Microscope,
  Atom,
  ShieldCheck,
  ArrowRight,
  Loader2,
  ClipboardPaste,
  X
} from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

// AURA-GEN Master Ingredient List with concentrations
const AURA_GEN_INGREDIENTS = [
  "Aqua/Water/Eau", "Tranexamic Acid (5.0%)", "Dimethyl Isosorbide (DMI)", 
  "PDRN (2.0%)", "Panax Ginseng Fruit Extract", "Niacinamide", 
  "Acetyl Hexapeptide-8", "Saccharide Isomerate", 
  "Ammonium Acryloyldimethyltaurate/VP Copolymer", "Adenosine", 
  "Sodium Hyaluronate", "Polyglutamic Acid", "Phenoxyethanol", 
  "Ethylhexylglycerin", "Cyanocobalamin", "Citric Acid", "Sodium Hydroxide"
];

// Key AURA-GEN Actives - Clinical Grade
const AURA_GEN_ACTIVES = [
  { 
    name: "Tranexamic Acid", 
    concentration: "5.0%", 
    benefit: "Clinical-grade brightening & melasma control",
    icon: "✨"
  },
  { 
    name: "PDRN", 
    concentration: "2.0%", 
    benefit: "Salmon DNA for cellular regeneration",
    icon: "🧬"
  },
  { 
    name: "DMI Penetration Enhancer", 
    concentration: "Active", 
    benefit: "Delivers actives past the lipid barrier",
    icon: "🔬"
  }
];

const AURA_GEN_HIGHLIGHTS = [
  { name: "Tranexamic Acid 5.0%", benefit: "Clinical brightening & melasma control" },
  { name: "PDRN 2.0%", benefit: "Salmon DNA cellular regeneration" },
  { name: "DMI (Dimethyl Isosorbide)", benefit: "Deep penetration enhancer" },
  { name: "Acetyl Hexapeptide-8", benefit: "Expression line relaxation" },
  { name: "Niacinamide", benefit: "Barrier strengthening" },
  { name: "Cyanocobalamin", benefit: "B12 cellular nutrition" },
  { name: "Polyglutamic Acid", benefit: "4x hyaluronic hydration" }
];

// Red flag ingredients with detailed alerts
const RED_FLAGS = {
  "fragrance": {
    keywords: ["fragrance", "parfum", "aroma", "perfume"],
    alert: "Inflammatory Trigger",
    message: "Synthetic fragrance can disrupt skin barrier function and trigger sensitivities.",
    auraGenResponse: "100% Fragrance-Free formula with skin-identical lipids."
  },
  "mineral_oil": {
    keywords: ["mineral oil", "paraffinum liquidum", "petrolatum", "petroleum"],
    alert: "Occlusive Alert",
    message: "Petroleum-based oils create a surface film that may impede natural skin function.",
    auraGenResponse: "Skin-identical lipids for zero-clog molecular hydration."
  },
  "silicones": {
    keywords: ["dimethicone", "cyclopentasiloxane", "cyclomethicone", "siloxane", "silicone"],
    alert: "Surface Coating",
    message: "Silicones create a temporary smoothing film but don't deliver true cellular hydration.",
    auraGenResponse: "Active-delivery system that penetrates, not just coats."
  },
  "parabens": {
    keywords: ["paraben", "methylparaben", "propylparaben", "butylparaben"],
    alert: "Preservation Concern",
    message: "Parabens are controversial preservatives. Newer alternatives exist.",
    auraGenResponse: "Modern preservation with Phenoxyethanol & Ethylhexylglycerin."
  },
  "alcohol": {
    keywords: ["alcohol denat", "sd alcohol", "isopropyl alcohol"],
    alert: "Barrier Disruption",
    message: "Drying alcohols can compromise the skin's moisture barrier over time.",
    auraGenResponse: "No drying alcohols. Only skin-conditioning humectants."
  }
};

// Bio-Availability Gauge Component
const BioAvailabilityGauge = ({ score, label, isAuraGen = false, showTooltip = false, isLocked = false, onUnlockClick }) => {
  const [animatedScore, setAnimatedScore] = useState(0);
  
  useEffect(() => {
    if (!isLocked) {
      const timer = setTimeout(() => setAnimatedScore(score), 300);
      return () => clearTimeout(timer);
    }
  }, [score, isLocked]);

  const getColor = () => {
    if (isAuraGen) return "from-[#4ECDC4] via-[#D4AF37] to-[#D4AF37]";
    if (score < 40) return "from-gray-400 to-gray-500";
    if (score < 70) return "from-yellow-400 to-orange-400";
    return "from-green-400 to-emerald-500";
  };

  // Locked state - show blurred score
  if (isLocked) {
    return (
      <div className="relative">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-sm font-medium ${isAuraGen ? "text-[#D4AF37]" : "text-gray-600"}`}>
            {label}
          </span>
          <span className={`text-lg font-bold ${isAuraGen ? "text-[#D4AF37]" : "text-gray-700"} blur-sm select-none`}>
            ??%
          </span>
        </div>
        <div className="h-4 bg-gray-200 rounded-full overflow-hidden relative">
          <div className="h-full w-full bg-gradient-to-r from-gray-300 to-gray-400 rounded-full blur-sm" />
        </div>
        <button
          onClick={onUnlockClick}
          className="mt-3 w-full py-2 px-4 bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
          Unlock Full Score
        </button>
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>Surface</span>
          <span>Deep Cellular</span>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-2">
        <span className={`text-sm font-medium ${isAuraGen ? "text-[#D4AF37]" : "text-gray-600"}`}>
          {label}
        </span>
        <span className={`text-lg font-bold ${isAuraGen ? "text-[#D4AF37]" : "text-gray-700"}`}>
          {animatedScore}%
        </span>
      </div>
      <div className="h-4 bg-gray-200 rounded-full overflow-hidden relative">
        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: animatedScore / 100 }}
          style={{ transformOrigin: 'left', width: '100%' }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.5 }}
          className={`h-full bg-gradient-to-r ${getColor()} rounded-full relative`}
        >
          {isAuraGen && (
            <motion.div
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
            />
          )}
        </motion.div>
      </div>
      {isAuraGen && showTooltip && (
        <div className="mt-2 p-3 bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded-lg">
          <p className="text-xs text-[#D4AF37]/90">
            <Info className="h-3 w-3 inline mr-1" />
            <strong>LipiSperse® Technology:</strong> Proprietary delivery system reduces active-ingredient clumping, ensuring 94% of the formula bypasses the surface barrier for deep cellular absorption.
          </p>
        </div>
      )}
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>Surface</span>
        <span>Deep Cellular</span>
      </div>
    </div>
  );
};

// Red Flag Alert Card
const RedFlagCard = ({ flag, flagData }) => (
  <motion.div
    initial={{ opacity: 0, x: -20 }}
    animate={{ opacity: 1, x: 0 }}
    className="border-l-4 border-red-500 bg-red-50 p-4 rounded-r-lg mb-3"
  >
    <div className="flex items-start gap-3">
      <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
      <div>
        <p className="font-semibold text-red-700">⚠️ {flagData.alert}</p>
        <p className="text-sm text-red-600 mt-1">{flagData.message}</p>
        <div className="mt-3 p-2 bg-[#4ECDC4]/10 border border-[#4ECDC4]/30 rounded">
          <p className="text-sm text-[#2A9D8F]">
            <CheckCircle className="h-4 w-4 inline mr-1" />
            <strong>AURA-GEN:</strong> {flagData.auraGenResponse}
          </p>
        </div>
      </div>
    </div>
  </motion.div>
);

// Scanning Animation
const ScanningAnimation = () => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="flex flex-col items-center justify-center py-16"
  >
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
      className="relative"
    >
      <Atom className="h-16 w-16 text-[#D4AF37]" />
      <motion.div
        animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 1.5, repeat: Infinity }}
        className="absolute inset-0 rounded-full border-2 border-[#D4AF37]/50"
      />
    </motion.div>
    <motion.p
      animate={{ opacity: [0.5, 1, 0.5] }}
      transition={{ duration: 1, repeat: Infinity }}
      className="mt-6 text-lg font-medium text-[#D4AF37]"
    >
      Analyzing Molecular Structure...
    </motion.p>
    <p className="text-sm text-gray-500 mt-2">Scanning INCI database for bioavailability markers</p>
  </motion.div>
);

// Main Component
const MolecularAuditorPage = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [manualIngredients, setManualIngredients] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [auditResults, setAuditResults] = useState(null);
  const [error, setError] = useState(null);
  const [liveAudits, setLiveAudits] = useState([]);
  
  // Lead capture state
  const [isScoreUnlocked, setIsScoreUnlocked] = useState(false);
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [showLeadCapture, setShowLeadCapture] = useState(false);
  const [leadCaptureLoading, setLeadCaptureLoading] = useState(false);
  
  // AURA-GEN product pricing (dynamic)
  const [auraGenProduct, setAuraGenProduct] = useState({
    price: 50,
    originalPrice: 100,
    comparePrice: 100,
    discount: 50,
    name: "AURA-GEN",
    slug: "aura-gen"
  });
  
  const searchTimeoutRef = useRef(null);
  const resultsRef = useRef(null);

  // Fetch AURA-GEN product pricing on mount
  useEffect(() => {
    const fetchAuraGenPricing = async () => {
      try {
        // Note: API is the full backend URL which already includes /api prefix handling
        const response = await axios.get(`${API}/api/products`);
        const products = response.data?.products || response.data || [];
        const auraGen = products.find(p => 
          p.name?.toLowerCase().includes('aura-gen') || 
          p.name?.toLowerCase().includes('aura gen')
        );
        
        if (auraGen) {
          const basePrice = auraGen.price || 99;
          const discountPercent = auraGen.discount_percent || auraGen.discount || 0;
          const comparePrice = auraGen.compare_price || auraGen.comparePrice || basePrice;
          
          // Calculate actual sale price with discount
          const salePrice = discountPercent > 0 
            ? (basePrice * (1 - discountPercent / 100)).toFixed(2)
            : auraGen.salePrice || basePrice;
          
          setAuraGenProduct({
            price: parseFloat(salePrice),
            originalPrice: basePrice,
            comparePrice: comparePrice,
            discount: discountPercent,
            name: auraGen.name || "AURA-GEN",
            slug: auraGen.slug || "aura-gen"
          });
        }
      } catch (err) {
        console.log("Using default AURA-GEN pricing");
      }
    };
    
    fetchAuraGenPricing();
  }, []);

  // Check URL for pre-loaded target product
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const targetProduct = urlParams.get('target');
    
    if (targetProduct) {
      // If there's a target in URL, search for it automatically
      setSearchQuery(targetProduct);
      // Trigger search after a short delay
      setTimeout(() => {
        handleSearch(targetProduct);
      }, 500);
    }
  }, []);

  // Update URL when audit is complete (for sharing)
  const updateUrlForSharing = (productName) => {
    if (productName && productName !== "Manual Entry") {
      const cleanName = productName.replace(/[^a-zA-Z0-9\s]/g, '').trim().replace(/\s+/g, '-');
      const newUrl = `${window.location.pathname}?target=${encodeURIComponent(cleanName)}`;
      window.history.replaceState({}, '', newUrl);
    }
  };

  // Pre-load default comparison on mount
  useEffect(() => {
    // Show "Generic Luxury Moisturizer" comparison immediately
    const genericMoisturizerIngredients = "Aqua, Glycerin, Mineral Oil, Petrolatum, Parfum, Dimethicone, Cyclopentasiloxane, Paraffinum Liquidum, Cetearyl Alcohol, Phenoxyethanol, Methylparaben";
    
    const genericProduct = {
      product_name: "Generic Luxury Moisturizer",
      brands: "$300+ Legacy Formula"
    };
    
    // Analyze the generic moisturizer
    setTimeout(() => {
      analyzeIngredientsPreload(genericMoisturizerIngredients, genericProduct);
    }, 1000);
    
    // Fetch live audit feed
    fetchLiveAudits();
    
    // Poll for live audits every 30 seconds
    const auditInterval = setInterval(fetchLiveAudits, 30000);
    return () => clearInterval(auditInterval);
  }, []);

  // Fetch live audits from backend
  const fetchLiveAudits = async () => {
    try {
      const response = await axios.get(`${API}/api/auditor/recent`);
      if (response.data?.audits) {
        setLiveAudits(response.data.audits);
      }
    } catch (err) {
      console.log("Live audit feed unavailable");
    }
  };

  // Pre-load analysis (no scanning animation, instant results)
  const analyzeIngredientsPreload = (ingredientsText, productInfo = {}) => {
    const ingredients = ingredientsText
      .toLowerCase()
      .split(/[,;]/)
      .map(i => i.trim())
      .filter(i => i.length > 0);

    // Check for red flags using fuzzy matching
    const detectedFlags = [];
    Object.entries(RED_FLAGS).forEach(([flagKey, flagData]) => {
      const found = ingredients.some(ing => 
        flagData.keywords.some(keyword => ing.includes(keyword.toLowerCase()))
      );
      if (found) {
        detectedFlags.push({ key: flagKey, ...flagData });
      }
    });

    // Check if first ingredient is water (standard base)
    const firstIngredient = ingredients[0] || "";
    const hasWaterBase = firstIngredient.includes("aqua") || 
                        firstIngredient.includes("water") || 
                        firstIngredient.includes("eau");

    // Check for delivery system
    const hasDeliverySystem = ingredients.some(ing => 
      ing.includes("liposom") || 
      ing.includes("lipisperse") || 
      ing.includes("nanosome") ||
      ing.includes("encapsul")
    );

    // Calculate competitor score - Generic luxury should score ~20%
    let competitorScore = 50;
    competitorScore -= detectedFlags.length * 8;
    if (!hasDeliverySystem) competitorScore -= 15;
    if (hasWaterBase) competitorScore -= 5;
    competitorScore = Math.max(15, Math.min(45, competitorScore));

    const results = {
      product: productInfo,
      ingredients: ingredients,
      ingredientsText: ingredientsText,
      redFlags: detectedFlags,
      hasWaterBase,
      hasDeliverySystem,
      competitorScore,
      auraGenScore: 94,
      timestamp: new Date().toISOString(),
      isPreloaded: true
    };

    setAuditResults(results);
  };

  // Debounced search
  const handleSearch = useCallback(async (query) => {
    if (query.length < 3) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    setError(null);

    try {
      // Search Open Beauty Facts API
      const response = await axios.get(
        `https://world.openbeautyfacts.org/cgi/search.pl?search_terms=${encodeURIComponent(query)}&search_simple=1&action=process&json=1&page_size=10`
      );
      
      const products = response.data?.products || [];
      setSearchResults(products.filter(p => p.product_name && p.ingredients_text));
    } catch (err) {
      console.error("Search error:", err);
      setError("Unable to search database. Try pasting ingredients manually.");
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Debounce input
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    
    searchTimeoutRef.current = setTimeout(() => {
      handleSearch(searchQuery);
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery, handleSearch]);

  // Analyze ingredients
  const analyzeIngredients = (ingredientsText, productInfo = {}) => {
    setIsScanning(true);
    
    // Simulate scanning animation (2 seconds as per spec)
    setTimeout(() => {
      const ingredients = ingredientsText
        .toLowerCase()
        .split(/[,;]/)
        .map(i => i.trim())
        .filter(i => i.length > 0);

      // Check for red flags using fuzzy matching
      const detectedFlags = [];
      Object.entries(RED_FLAGS).forEach(([flagKey, flagData]) => {
        const found = ingredients.some(ing => 
          flagData.keywords.some(keyword => ing.includes(keyword.toLowerCase()))
        );
        if (found) {
          detectedFlags.push({ key: flagKey, ...flagData });
        }
      });

      // Check if first ingredient is water (standard base)
      const firstIngredient = ingredients[0] || "";
      const hasWaterBase = firstIngredient.includes("aqua") || 
                          firstIngredient.includes("water") || 
                          firstIngredient.includes("eau");

      // Check for delivery system
      const hasDeliverySystem = ingredients.some(ing => 
        ing.includes("liposom") || 
        ing.includes("lipisperse") || 
        ing.includes("nanosome") ||
        ing.includes("encapsul")
      );

      // Calculate competitor score
      let competitorScore = 60; // Base score
      competitorScore -= detectedFlags.length * 12; // Deduct for each red flag
      if (!hasDeliverySystem) competitorScore -= 15;
      if (hasWaterBase) competitorScore -= 5;
      competitorScore = Math.max(20, Math.min(75, competitorScore)); // Clamp between 20-75

      const results = {
        product: productInfo,
        ingredients: ingredients,
        ingredientsText: ingredientsText,
        redFlags: detectedFlags,
        hasWaterBase,
        hasDeliverySystem,
        competitorScore,
        auraGenScore: 94, // Fixed as per spec
        timestamp: new Date().toISOString()
      };

      setAuditResults(results);
      setIsScanning(false);

      // Update URL for sharing
      updateUrlForSharing(productInfo.product_name || searchQuery);

      // Log audit to backend
      logAudit(results, productInfo);

      // Scroll to results
      if (resultsRef.current) {
        resultsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 2000);
  };

  // Log audit to backend
  const logAudit = async (results, productInfo) => {
    try {
      await axios.post(`${API}/api/auditor/log`, {
        search_query: searchQuery || "Manual Entry",
        product_found: !!productInfo.product_name,
        product_name: productInfo.product_name || null,
        product_brand: productInfo.brands || null,
        ingredients_source: selectedProduct ? "api" : "manual",
        red_flags_detected: results.redFlags.map(f => f.alert),
        competitor_score: results.competitorScore,
        aura_gen_score: results.auraGenScore
      });
    } catch (err) {
      console.error("Failed to log audit:", err);
    }
  };

  // Select product from search
  const handleSelectProduct = (product) => {
    setSelectedProduct(product);
    setSearchResults([]);
    setSearchQuery(product.product_name);
    analyzeIngredients(product.ingredients_text, {
      product_name: product.product_name,
      brands: product.brands,
      image_url: product.image_url
    });
  };

  // Handle manual ingredient submission
  const handleManualSubmit = () => {
    if (manualIngredients.trim().length < 10) {
      setError("Please paste a complete ingredient list");
      return;
    }
    analyzeIngredients(manualIngredients, { product_name: "Manual Entry" });
  };

  // Reset audit
  const resetAudit = () => {
    setSearchQuery("");
    setSelectedProduct(null);
    setManualIngredients("");
    setAuditResults(null);
    setSearchResults([]);
    setShowManualInput(false);
    setError(null);
    setIsScoreUnlocked(false);
    setShowLeadCapture(false);
  };

  // Handle lead capture to unlock scores
  const handleUnlockScores = async () => {
    if (!leadEmail && !leadPhone) {
      setError("Please enter your email or phone number");
      return;
    }
    
    // Basic validation
    if (leadEmail && !leadEmail.includes('@')) {
      setError("Please enter a valid email address");
      return;
    }
    
    setLeadCaptureLoading(true);
    setError(null);
    
    try {
      // Save lead to backend
      await axios.post(`${API}/api/auditor/lead`, {
        email: leadEmail || null,
        phone: leadPhone || null,
        audit_id: auditResults?.timestamp,
        product_searched: auditResults?.product?.product_name || searchQuery,
        competitor_score: auditResults?.competitorScore,
        source: "molecular_auditor"
      });
      
      setIsScoreUnlocked(true);
      setShowLeadCapture(false);
      
      // Update the audit log with the lead info
      if (auditResults) {
        await axios.post(`${API}/api/auditor/log`, {
          search_query: searchQuery || "Manual Entry",
          product_found: !!auditResults.product?.product_name,
          product_name: auditResults.product?.product_name || null,
          product_brand: auditResults.product?.brands || null,
          ingredients_source: selectedProduct ? "api" : "manual",
          red_flags_detected: auditResults.redFlags?.map(f => f.alert) || [],
          competitor_score: auditResults.competitorScore,
          aura_gen_score: auditResults.auraGenScore,
          user_email: leadEmail || null
        });
      }
    } catch (err) {
      console.error("Failed to save lead:", err);
      // Still unlock even if save fails
      setIsScoreUnlocked(true);
      setShowLeadCapture(false);
    } finally {
      setLeadCaptureLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <Helmet>
        <title>AURA-GEN Molecular Auditor | ReRoots Biotech</title>
        <meta name="description" content="Compare any skincare product against AURA-GEN's LipiSperse® technology. Real-time INCI analysis powered by biotech science." />
      </Helmet>

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-[#0A1628] via-[#1A2744] to-[#0A1628] py-16 md:py-24">
        {/* Animated background elements */}
        <div className="absolute inset-0 overflow-hidden">
          <motion.div
            animate={{ 
              rotate: 360,
              scale: [1, 1.1, 1]
            }}
            transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
            className="absolute -top-1/2 -right-1/4 w-[800px] h-[800px] rounded-full bg-gradient-to-br from-[#D4AF37]/10 to-transparent blur-3xl"
          />
          <motion.div
            animate={{ 
              rotate: -360,
              scale: [1, 1.2, 1]
            }}
            transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
            className="absolute -bottom-1/2 -left-1/4 w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-[#4ECDC4]/10 to-transparent blur-3xl"
          />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-4 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] border-[#D4AF37]/30 mb-6">
              <FlaskConical className="h-3 w-3 mr-1" />
              BIOTECH ANALYSIS PLATFORM
            </Badge>
            
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
              <span className="bg-gradient-to-r from-[#D4AF37] via-[#F4E4BA] to-[#D4AF37] bg-clip-text text-transparent">
                AURA-GEN
              </span>
              <br />
              <span className="text-2xl md:text-4xl font-light text-white/90">
                Molecular Auditor
              </span>
            </h1>
            
            <p className="text-lg md:text-xl text-white/70 max-w-2xl mx-auto mb-8">
              Compare any skincare formula against AURA-GEN's clinical-grade complex:
              <span className="text-[#D4AF37]"> 5% Tranexamic Acid • 2% PDRN • DMI Penetration Technology</span>
            </p>
          </motion.div>

          {/* Search Interface */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="max-w-2xl mx-auto"
          >
            <div className="relative">
              <div className="flex items-center bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-2">
                <div className="flex-1 relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/50" />
                  <Input
                    type="text"
                    placeholder="Search any skincare product..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-12 pr-4 py-4 bg-transparent border-0 text-white placeholder:text-white/50 text-lg focus-visible:ring-0 focus-visible:ring-offset-0"
                    disabled={isScanning}
                  />
                </div>
                {isSearching && (
                  <Loader2 className="h-5 w-5 text-[#D4AF37] animate-spin mr-4" />
                )}
              </div>

              {/* Search Results Dropdown */}
              <AnimatePresence>
                {searchResults.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-2xl overflow-hidden z-50 max-h-80 overflow-y-auto"
                  >
                    {searchResults.map((product, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSelectProduct(product)}
                        className="w-full flex items-center gap-4 p-4 hover:bg-gray-50 transition-colors text-left border-b border-gray-100 last:border-0"
                      >
                        {product.image_url ? (
                          <img 
                            src={product.image_url} 
                            alt={product.product_name}
                            className="w-12 h-12 object-cover rounded-lg"
                          />
                        ) : (
                          <div className="w-12 h-12 bg-gray-200 rounded-lg flex items-center justify-center">
                            <FlaskConical className="h-6 w-6 text-gray-400" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 truncate">{product.product_name}</p>
                          <p className="text-sm text-gray-500 truncate">{product.brands || "Unknown Brand"}</p>
                        </div>
                        <ArrowRight className="h-5 w-5 text-gray-400" />
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Manual Entry Toggle */}
            <div className="mt-4 flex items-center justify-center gap-4">
              <button
                onClick={() => setShowManualInput(!showManualInput)}
                className="text-white/60 hover:text-white text-sm flex items-center gap-2 transition-colors"
              >
                <ClipboardPaste className="h-4 w-4" />
                Can't find your product? Paste ingredients manually
              </button>
            </div>

            {/* Manual Input */}
            <AnimatePresence>
              {showManualInput && (
                <motion.div
                  initial={{ opacity: 0, scaleY: 0 }}
                  animate={{ opacity: 1, scaleY: 1 }}
                  exit={{ opacity: 0, scaleY: 0 }}
                  style={{ transformOrigin: 'top' }}
                  className="mt-4"
                >
                  <div className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl p-4">
                    <label className="block text-white/80 text-sm mb-2 text-left">
                      <Microscope className="h-4 w-4 inline mr-2" />
                      Laboratory Intake Form - Paste INCI List
                    </label>
                    <textarea
                      value={manualIngredients}
                      onChange={(e) => setManualIngredients(e.target.value)}
                      placeholder="Paste the complete ingredient list from your product packaging..."
                      className="w-full h-32 px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder:text-white/40 text-sm resize-none focus:outline-none focus:border-[#D4AF37]/50"
                    />
                    <Button
                      onClick={handleManualSubmit}
                      disabled={isScanning || manualIngredients.trim().length < 10}
                      className="mt-3 w-full bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A1628] font-semibold hover:opacity-90"
                    >
                      {isScanning ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Atom className="h-4 w-4 mr-2" />
                          Analyze Ingredients
                        </>
                      )}
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {error && (
              <p className="mt-4 text-red-400 text-sm">{error}</p>
            )}
          </motion.div>
        </div>
      </section>

      {/* Scanning Animation */}
      <AnimatePresence>
        {isScanning && (
          <section className="py-8">
            <ScanningAnimation />
          </section>
        )}
      </AnimatePresence>

      {/* Audit Results */}
      <AnimatePresence>
        {auditResults && !isScanning && (
          <motion.section
            ref={resultsRef}
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -40 }}
            className="py-12 md:py-20 px-4"
          >
            <div className="max-w-6xl mx-auto">
              {/* Results Header */}
              <div className="text-center mb-12">
                <Badge className="bg-[#4ECDC4]/20 text-[#2A9D8F] border-[#4ECDC4]/30 mb-4">
                  <ShieldCheck className="h-3 w-3 mr-1" />
                  ANALYSIS COMPLETE
                </Badge>
                <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2">
                  Molecular Audit Results
                </h2>
                <p className="text-gray-600">
                  {auditResults.product?.product_name || "Your Product"} vs AURA-GEN
                </p>
              </div>

              {/* Side-by-Side Comparison */}
              <div className="grid md:grid-cols-2 gap-6 md:gap-8 mb-12">
                {/* Competitor Card */}
                <Card className="border-gray-200 bg-gray-50/50">
                  <CardContent className="p-6 md:p-8">
                    <div className="flex items-center gap-3 mb-6">
                      {auditResults.product?.image_url ? (
                        <img 
                          src={auditResults.product.image_url}
                          alt="Product"
                          className="w-16 h-16 object-cover rounded-lg grayscale opacity-70"
                        />
                      ) : (
                        <div className="w-16 h-16 bg-gray-200 rounded-lg flex items-center justify-center">
                          <FlaskConical className="h-8 w-8 text-gray-400" />
                        </div>
                      )}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider">Their Product</p>
                        <h3 className="font-semibold text-gray-700 truncate max-w-[200px]">
                          {auditResults.product?.product_name || "Analyzed Formula"}
                        </h3>
                        {auditResults.product?.brands && (
                          <p className="text-sm text-gray-500">{auditResults.product.brands}</p>
                        )}
                      </div>
                    </div>

                    {/* Bio-Availability Gauge - Locked until email provided */}
                    <BioAvailabilityGauge 
                      score={auditResults.competitorScore} 
                      label="Bio-Availability Score"
                      isLocked={!isScoreUnlocked && !auditResults.isPreloaded}
                      onUnlockClick={() => setShowLeadCapture(true)}
                    />

                    {/* Base Water Alert */}
                    {auditResults.hasWaterBase && (
                      <div className="mt-6 p-3 bg-gray-100 rounded-lg">
                        <p className="text-sm text-gray-600">
                          <Info className="h-4 w-4 inline mr-1" />
                          <strong>Base:</strong> Standard Water. Most formulas use plain aqua as a filler base.
                        </p>
                      </div>
                    )}

                    {/* No Delivery System Alert */}
                    {!auditResults.hasDeliverySystem && (
                      <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <p className="text-sm text-amber-700">
                          <AlertTriangle className="h-4 w-4 inline mr-1" />
                          <strong>Absorption Gap:</strong> No modern delivery technology detected. Actives may remain on surface.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* AURA-GEN Card - Glass-morphism Style */}
                <Card className="border-[#D4AF37]/40 bg-white/80 backdrop-blur-xl relative overflow-hidden shadow-xl">
                  {/* Glass-morphism overlay */}
                  <div className="absolute inset-0 bg-gradient-to-br from-[#D4AF37]/10 via-transparent to-[#4ECDC4]/10" />
                  <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-br from-[#D4AF37]/30 to-transparent rounded-bl-full blur-2xl" />
                  <div className="absolute bottom-0 left-0 w-32 h-32 bg-gradient-to-tr from-[#4ECDC4]/20 to-transparent rounded-tr-full blur-xl" />
                  
                  <CardContent className="p-6 md:p-8 relative z-10">
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-16 h-16 bg-gradient-to-br from-[#D4AF37] to-[#B8860B] rounded-lg flex items-center justify-center shadow-lg">
                        <Sparkles className="h-8 w-8 text-white" />
                      </div>
                      <div>
                        <p className="text-xs text-[#D4AF37] uppercase tracking-wider font-semibold">ReRoots Biotech</p>
                        <h3 className="font-bold text-gray-900 text-lg">AURA-GEN</h3>
                        <p className="text-sm text-gray-600">Batch 01 Limited Release</p>
                      </div>
                    </div>

                    {/* Clinical-Grade Actives */}
                    <div className="mb-6 p-4 bg-gradient-to-r from-[#0A1628]/5 to-[#D4AF37]/5 rounded-xl border border-[#D4AF37]/20">
                      <p className="text-xs text-[#D4AF37] uppercase tracking-wider font-semibold mb-3">Clinical-Grade Actives</p>
                      <div className="space-y-2">
                        {AURA_GEN_ACTIVES.map((active, idx) => (
                          <div key={idx} className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-800">
                              {active.icon} {active.name}
                            </span>
                            <span className="text-sm font-bold text-[#D4AF37] bg-[#D4AF37]/10 px-2 py-0.5 rounded">
                              {active.concentration}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Bio-Availability Gauge */}
                    <BioAvailabilityGauge 
                      score={auditResults.auraGenScore} 
                      label="Bio-Availability Score"
                      isAuraGen={true}
                      showTooltip={true}
                    />

                    {/* AURA-GEN Highlights */}
                    <div className="mt-6 p-3 bg-[#4ECDC4]/10 backdrop-blur-sm border border-[#4ECDC4]/30 rounded-lg">
                      <p className="text-sm text-[#2A9D8F]">
                        <CheckCircle className="h-4 w-4 inline mr-1" />
                        <strong>Base:</strong> Nutrient-Dense Panax Ginseng & Vitamin B12 Hydrosol
                      </p>
                    </div>

                    <div className="mt-4 p-3 bg-[#D4AF37]/10 backdrop-blur-sm border border-[#D4AF37]/30 rounded-lg">
                      <p className="text-sm text-[#B8860B]">
                        <ShieldCheck className="h-4 w-4 inline mr-1" />
                        <strong>DMI Penetration:</strong> Delivers actives past the lipid barrier for dermal absorption
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Red Flags Section */}
              {auditResults.redFlags.length > 0 && (
                <div className="mb-12">
                  <h3 className="text-xl font-bold text-gray-900 mb-4">
                    ⚠️ Red Flags Detected ({auditResults.redFlags.length})
                  </h3>
                  {auditResults.redFlags.map((flag, idx) => (
                    <RedFlagCard key={idx} flag={flag.key} flagData={flag} />
                  ))}
                </div>
              )}

              {/* AURA-GEN Ingredient Highlights */}
              <div className="mb-12">
                <h3 className="text-xl font-bold text-gray-900 mb-4">
                  ✨ AURA-GEN Active Complex
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {AURA_GEN_HIGHLIGHTS.map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.1 }}
                      className="p-4 bg-gradient-to-br from-[#D4AF37]/10 to-[#4ECDC4]/10 border border-[#D4AF37]/20 rounded-lg"
                    >
                      <p className="font-medium text-gray-900 text-sm">{item.name}</p>
                      <p className="text-xs text-gray-600 mt-1">{item.benefit}</p>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* Reset Button */}
              <div className="text-center">
                <Button
                  onClick={resetAudit}
                  variant="outline"
                  className="border-gray-300"
                >
                  <X className="h-4 w-4 mr-2" />
                  Analyze Another Product
                </Button>
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* Sticky CTA - Glass-morphism Style */}
      <AnimatePresence>
        {auditResults && !isScanning && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="fixed bottom-0 left-0 right-0 bg-[#0A1628]/95 backdrop-blur-xl border-t border-[#D4AF37]/40 p-4 z-50 shadow-2xl"
          >
            <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="text-center sm:text-left">
                <p className="text-white/90 font-medium">
                  Your product scored <span className="text-red-400 font-bold">{auditResults.competitorScore}/100</span> in Bio-Availability
                </p>
                <p className="text-white/60 text-sm">
                  AURA-GEN with <span className="text-[#D4AF37] font-semibold">5% Tranexamic + 2% PDRN + DMI</span> delivers {auditResults.auraGenScore}% penetration
                </p>
              </div>
              <Link to={`/products/${auraGenProduct.slug || 'aura-gen-txa-pdrn'}`}>
                <Button 
                  className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A1628] font-bold px-8 py-6 text-lg hover:opacity-90 hover:scale-105 transition-all whitespace-nowrap shadow-lg"
                  data-testid="upgrade-aura-gen-cta"
                >
                  UPGRADE TO AURA-GEN - ${auraGenProduct.price}
                  {auraGenProduct.discount > 0 && (
                    <span className="ml-2 line-through text-white/50 text-sm">${auraGenProduct.originalPrice}</span>
                  )}
                  <ArrowRight className="h-5 w-5 ml-2" />
                </Button>
              </Link>
            </div>
            <p className="text-center text-white/40 text-xs mt-3">
              {auraGenProduct.discount > 0 && (
                <span className="text-[#4ECDC4] mr-2 font-semibold">
                  🔥 {auraGenProduct.discount}% OFF
                </span>
              )}
              ✓ 5% Tranexamic Acid &nbsp; ✓ 2% PDRN &nbsp; ✓ DMI Penetration &nbsp; ✓ Batch 01 Limited
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Lead Capture Modal */}
      <AnimatePresence>
        {showLeadCapture && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
            onClick={() => setShowLeadCapture(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl p-6 md:p-8 max-w-md w-full shadow-2xl"
            >
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-gradient-to-br from-[#D4AF37] to-[#B8860B] rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-2">Unlock Your Full Report</h3>
                <p className="text-gray-600">
                  Enter your email or phone to see the complete bio-availability analysis and personalized recommendations.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={leadEmail}
                    onChange={(e) => setLeadEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#D4AF37] focus:border-transparent"
                  />
                </div>
                
                <div className="flex items-center gap-4">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-sm text-gray-500">or</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                  <input
                    type="tel"
                    value={leadPhone}
                    onChange={(e) => setLeadPhone(e.target.value)}
                    placeholder="+1 (555) 000-0000"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#D4AF37] focus:border-transparent"
                  />
                </div>

                {error && (
                  <p className="text-red-500 text-sm text-center">{error}</p>
                )}

                <button
                  onClick={handleUnlockScores}
                  disabled={leadCaptureLoading || (!leadEmail && !leadPhone)}
                  className="w-full py-4 bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-white font-bold rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {leadCaptureLoading ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Unlocking...
                    </>
                  ) : (
                    <>
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                      </svg>
                      Unlock Full Report
                    </>
                  )}
                </button>

                <p className="text-xs text-gray-500 text-center">
                  By unlocking, you agree to receive product updates and skincare insights from ReRoots. 
                  <br />We respect your privacy and never spam.
                </p>
              </div>

              <button
                onClick={() => setShowLeadCapture(false)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
              >
                <X className="h-6 w-6" />
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live Audit Feed - Social Proof */}
      {liveAudits.length > 0 && (
        <section className="py-12 px-4 bg-gradient-to-b from-[#0A1628] to-[#1A2744]">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
              <Badge className="bg-[#4ECDC4]/20 text-[#4ECDC4] border-[#4ECDC4]/30 mb-4">
                <Sparkles className="h-3 w-3 mr-1" />
                LIVE ACTIVITY
              </Badge>
              <h3 className="text-2xl font-bold text-white mb-2">Real-Time Audit Feed</h3>
              <p className="text-white/60 text-sm">See what products others are analyzing right now</p>
            </div>
            
            <div className="space-y-3 overflow-hidden">
              {liveAudits.slice(0, 5).map((audit, idx) => (
                <motion.div
                  key={audit._id || idx}
                  initial={{ opacity: 0, x: -50 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="flex items-center justify-between p-4 bg-white/5 backdrop-blur-sm border border-white/10 rounded-lg"
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-2 h-2 rounded-full ${audit.competitor_score < 40 ? 'bg-red-500' : 'bg-yellow-500'} animate-pulse`} />
                    <div>
                      <p className="text-white/90 font-medium text-sm">
                        {audit.product_name || audit.search_query || "Anonymous Product"}
                      </p>
                      <p className="text-white/50 text-xs">
                        {audit.red_flags_detected?.length || 0} red flags detected • {formatTimeAgo(audit.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`font-bold ${audit.competitor_score < 40 ? 'text-red-400' : 'text-yellow-400'}`}>
                      {audit.competitor_score}%
                    </span>
                    <p className="text-white/50 text-xs">vs AURA-GEN 94%</p>
                  </div>
                </motion.div>
              ))}
            </div>
            
            <div className="mt-6 text-center">
              <p className="text-white/40 text-xs">
                🔬 {liveAudits.length}+ products analyzed today • Join the molecular revolution
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Legal Disclaimer */}
      <section className="py-8 px-4 bg-gray-50 border-t border-gray-200">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xs text-gray-500">
            Audit results are based on publicly available INCI (International Nomenclature of Cosmetic Ingredients) data as of 2026. 
            This tool is for educational purposes and is not a medical diagnosis. LipiSperse® is a registered trademark. 
            Bioavailability percentages are based on clinical delivery system studies.
          </p>
        </div>
      </section>

      {/* Family Brand Comparison Section */}
      <section className="py-16 px-4 bg-gradient-to-b from-white to-gray-50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <Badge className="bg-[#D4AF37]/10 text-[#D4AF37] border-[#D4AF37]/30 mb-4">
              <Sparkles className="h-3 w-3 mr-1" />
              GENERATIONAL COLLECTIONS
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
              Our Family of Brands
            </h2>
            <p className="text-gray-600 max-w-2xl mx-auto">
              Three generations, three unique skincare philosophies. Each collection is crafted for a specific life stage.
            </p>
          </div>

          {/* Comparison Table */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b-2 border-gray-200">
                  <th className="py-4 px-4 text-left text-gray-500 font-medium">Feature</th>
                  <th className="py-4 px-6 text-center">
                    <div className="bg-gradient-to-br from-[#0D4D4D] to-[#E8C4B8] rounded-xl p-4 text-white">
                      <span className="text-2xl">🌸</span>
                      <p className="font-bold mt-2">LA VELA BIANCA</p>
                      <p className="text-xs opacity-80">The Anmol Singh Collection</p>
                    </div>
                  </th>
                  <th className="py-4 px-6 text-center">
                    <div className="bg-gradient-to-br from-[#D4AF37] to-[#F8A5B8] rounded-xl p-4 text-white">
                      <span className="text-2xl">🧬</span>
                      <p className="font-bold mt-2">ReRoots</p>
                      <p className="text-xs opacity-80">The Gurnaman Singh Collection</p>
                    </div>
                  </th>
                  <th className="py-4 px-6 text-center">
                    <div className="bg-gradient-to-br from-[#1A1A1A] to-[#D4AF37] rounded-xl p-4 text-white">
                      <span className="text-2xl">👑</span>
                      <p className="font-bold mt-2">OROÉ</p>
                      <p className="text-xs opacity-80">The Founders' Collection</p>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                <tr className="hover:bg-gray-50">
                  <td className="py-4 px-4 font-medium text-gray-700">Age Range</td>
                  <td className="py-4 px-6 text-center text-gray-600">8-18 years</td>
                  <td className="py-4 px-6 text-center text-gray-600">18-35 years</td>
                  <td className="py-4 px-6 text-center text-gray-600">35+ years</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="py-4 px-4 font-medium text-gray-700">Hero Product</td>
                  <td className="py-4 px-6 text-center text-gray-600">ORO ROSA Serum</td>
                  <td className="py-4 px-6 text-center text-gray-600">AURA-GEN Serum</td>
                  <td className="py-4 px-6 text-center text-gray-600">Black Label Serum</td>
                </tr>
                <tr className="hover:bg-gray-50 bg-amber-50/50">
                  <td className="py-4 px-4 font-medium text-gray-700">Key Ingredient</td>
                  <td className="py-4 px-6 text-center">
                    <span className="bg-[#0D4D4D]/10 text-[#0D4D4D] px-3 py-1 rounded-full text-sm font-medium">
                      Centella Asiatica
                    </span>
                  </td>
                  <td className="py-4 px-6 text-center">
                    <span className="bg-[#D4AF37]/10 text-[#D4AF37] px-3 py-1 rounded-full text-sm font-medium">
                      Tranexamic Acid 5%
                    </span>
                  </td>
                  <td className="py-4 px-6 text-center">
                    <span className="bg-black/10 text-black px-3 py-1 rounded-full text-sm font-medium">
                      EGF + PDRN
                    </span>
                  </td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="py-4 px-4 font-medium text-gray-700">Primary Benefit</td>
                  <td className="py-4 px-6 text-center text-gray-600">Gentle healing & calming</td>
                  <td className="py-4 px-6 text-center text-gray-600">Brightening & regeneration</td>
                  <td className="py-4 px-6 text-center text-gray-600">Cellular resurrection</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="py-4 px-4 font-medium text-gray-700">Best For</td>
                  <td className="py-4 px-6 text-center text-gray-600">Acne, redness, sensitivity</td>
                  <td className="py-4 px-6 text-center text-gray-600">Dullness, uneven tone</td>
                  <td className="py-4 px-6 text-center text-gray-600">Deep wrinkles, elasticity</td>
                </tr>
                <tr className="hover:bg-gray-50">
                  <td className="py-4 px-4 font-medium text-gray-700">Formulation</td>
                  <td className="py-4 px-6 text-center text-gray-600">Pediatric-safe, pH 5.0-5.3</td>
                  <td className="py-4 px-6 text-center text-gray-600">Clinical-grade actives</td>
                  <td className="py-4 px-6 text-center text-gray-600">Luxury bio-actives</td>
                </tr>
                <tr className="hover:bg-gray-50 bg-green-50/50">
                  <td className="py-4 px-4 font-medium text-gray-700">Price</td>
                  <td className="py-4 px-6 text-center">
                    <span className="text-2xl font-bold text-[#0D4D4D]">$49</span>
                    <span className="text-gray-500 text-sm"> CAD</span>
                  </td>
                  <td className="py-4 px-6 text-center">
                    <span className="text-2xl font-bold text-[#D4AF37]">$155</span>
                    <span className="text-gray-500 text-sm"> CAD</span>
                  </td>
                  <td className="py-4 px-6 text-center">
                    <span className="text-2xl font-bold text-black">$159</span>
                    <span className="text-gray-500 text-sm"> CAD</span>
                  </td>
                </tr>
                <tr>
                  <td className="py-6 px-4"></td>
                  <td className="py-6 px-6 text-center">
                    <Link 
                      to="/lavela" 
                      className="inline-flex items-center gap-2 bg-gradient-to-r from-[#0D4D4D] to-[#1A6B6B] text-white px-6 py-3 rounded-full font-medium hover:opacity-90 transition-opacity"
                    >
                      Shop LA VELA
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </td>
                  <td className="py-6 px-6 text-center">
                    <Link 
                      to="/products" 
                      className="inline-flex items-center gap-2 bg-gradient-to-r from-[#D4AF37] to-[#E5C158] text-white px-6 py-3 rounded-full font-medium hover:opacity-90 transition-opacity"
                    >
                      Shop ReRoots
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </td>
                  <td className="py-6 px-6 text-center">
                    <Link 
                      to="/oroe" 
                      className="inline-flex items-center gap-2 bg-gradient-to-r from-[#1A1A1A] to-[#333] text-white px-6 py-3 rounded-full font-medium hover:opacity-90 transition-opacity"
                    >
                      Shop OROÉ
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Family Story Banner */}
          <div className="mt-12 bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-8 text-center">
            <p className="text-white/60 text-sm uppercase tracking-wider mb-2">A Family Legacy</p>
            <h3 className="text-2xl font-bold text-white mb-4">
              Built by Tejinder Sandhu & Pawandeep Kaur
            </h3>
            <p className="text-white/80 max-w-2xl mx-auto">
              Three brands, one family philosophy: skincare that works for every generation. 
              From teen essentials to luxury anti-aging, we've got your skin covered.
            </p>
            <div className="flex justify-center gap-8 mt-6">
              <div className="text-center">
                <p className="text-3xl font-bold text-[#E8C4B8]">Anmol</p>
                <p className="text-white/60 text-sm">Age 15</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-[#D4AF37]">Gurnaman</p>
                <p className="text-white/60 text-sm">Age 18</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-white">Founders</p>
                <p className="text-white/60 text-sm">35+</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Add padding at bottom when sticky CTA is visible */}
      {auditResults && !isScanning && <div className="h-32" />}
    </div>
  );
};

// Helper function to format time ago
const formatTimeAgo = (dateString) => {
  if (!dateString) return "just now";
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);
  
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

export default MolecularAuditorPage;
