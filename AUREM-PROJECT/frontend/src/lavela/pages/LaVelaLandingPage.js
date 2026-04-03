import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Star, ChevronDown, Shield, Award, Leaf, Download, X } from "lucide-react";
import "../styles/lavela-design-system.css";

const LaVelaLandingPage = () => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstallBanner, setShowInstallBanner] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  // SEO Schema for LA VELA BIANCA
  const brandSchema = {
    "@context": "https://schema.org",
    "@type": "Brand",
    "name": "LA VELA BIANCA",
    "alternateName": ["La Vela Bianca", "LaVelaBianca", "The Anmol Singh Collection"],
    "description": "Premium pediatric-safe skincare for teens aged 8-18. Canadian-Italian technology with Centella Asiatica. The New Era of Elite Glow.",
    "url": "https://lavelabianca.com",
    "logo": "https://reroots.ca/lavela-icon-512.png",
    "slogan": "Clean light for your skin",
    "sameAs": [
      "https://instagram.com/La_Vela_Bianca",
      "https://reroots.ca/la-vela-bianca"
    ]
  };

  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "LA VELA BIANCA",
    "url": "https://lavelabianca.com",
    "logo": "https://reroots.ca/lavela-icon-512.png",
    "description": "Luxury teen skincare brand. Premium pediatric-safe formulations for ages 8-18. Made in Canada.",
    "foundingDate": "2026",
    "founder": {
      "@type": "Person",
      "name": "Anmol Singh"
    },
    "contactPoint": {
      "@type": "ContactPoint",
      "email": "Anmol@lavelabianca.com",
      "contactType": "customer service",
      "availableLanguage": ["English", "French"]
    },
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Toronto",
      "addressRegion": "Ontario",
      "addressCountry": "CA"
    },
    "areaServed": {
      "@type": "Country",
      "name": "Canada"
    },
    "sameAs": [
      "https://instagram.com/La_Vela_Bianca"
    ]
  };

  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "ORO ROSA Bio-Glow Serum",
    "alternateName": "ORO ROSA",
    "description": "Translucent bouncy pink gel serum for young skin ages 8-16. Features 4 hero ingredients: PDRN (The Healer), Glutathione (The Glow Molecule), Hyaluronic Acid (The Hydrator), and Vitamin B12 (The Pink Power). Targets acne scars, uneven texture, dull skin, and dehydration.",
    "brand": { "@type": "Brand", "name": "LA VELA BIANCA" },
    "image": ["https://reroots.ca/oro-rosa-product.png", "https://reroots.ca/lavela-icon-512.png"],
    "sku": "LV-ORO-001",
    "category": "Health & Beauty > Skin Care > Facial Serums",
    "audience": {
      "@type": "PeopleAudience",
      "suggestedMinAge": 8,
      "suggestedMaxAge": 16
    },
    "offers": {
      "@type": "Offer",
      "price": "49.00",
      "priceCurrency": "CAD",
      "availability": "https://schema.org/InStock",
      "url": "https://lavelabianca.com/shop",
      "priceValidUntil": "2026-12-31",
      "seller": {
        "@type": "Organization",
        "name": "LA VELA BIANCA"
      }
    },
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "4.9",
      "reviewCount": "2847",
      "bestRating": "5",
      "worstRating": "1"
    }
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "LA VELA BIANCA",
    "url": "https://lavelabianca.com",
    "description": "Luxury teen skincare - Clean light for your skin",
    "potentialAction": {
      "@type": "SearchAction",
      "target": "https://lavelabianca.com/search?q={search_term_string}",
      "query-input": "required name=search_term_string"
    }
  };
  
  // FAQ Schema for GEO/AI optimization
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "Is La Vela Bianca safe for teens?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes, La Vela Bianca is specifically formulated for ages 8-18 with pediatric-safe, pH-balanced formulas (5.0-5.3). All ingredients are gentle and clinically tested for young, developing skin."
        }
      },
      {
        "@type": "Question",
        "name": "What is ORO ROSA serum?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "ORO ROSA is a translucent pink gel serum designed for young skin. It contains 4 hero ingredients: PDRN for healing, Glutathione for glow, Hyaluronic Acid for hydration, and Vitamin B12 for soothing. Price: $49 CAD."
        }
      },
      {
        "@type": "Question",
        "name": "Where is La Vela Bianca made?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "La Vela Bianca products are made in Canada using Canadian-Italian skincare technology. Our formulations combine premium ingredients with pediatric-safe standards."
        }
      }
    ]
  };

  useEffect(() => {
    setIsLoaded(true);
    
    // Force scroll to work
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    document.documentElement.style.overflow = 'auto';
    document.documentElement.style.height = 'auto';
    
    // Register LA VELA BIANCA Service Worker (separate from ReRoots)
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/lavela-sw.js', { scope: '/' })
        .then(reg => console.log('LA VELA PWA: Service Worker registered', reg.scope))
        .catch(err => console.log('LA VELA PWA: SW registration failed', err));
    }
    
    // Remove ReRoots manifest and add LA VELA manifest
    const reRootsManifest = document.querySelector('link[rel="manifest"]:not([data-lavela])');
    if (reRootsManifest) {
      reRootsManifest.remove();
    }
    
    // Add LA VELA manifest dynamically
    let existingManifest = document.querySelector('link[rel="manifest"][data-lavela]');
    if (!existingManifest) {
      const manifestLink = document.createElement('link');
      manifestLink.rel = 'manifest';
      manifestLink.href = '/lavela-manifest.json';
      manifestLink.setAttribute('data-lavela', 'true');
      document.head.appendChild(manifestLink);
    }
    
    // Update theme color for LA VELA
    let themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.setAttribute('content', '#0D4D4D');
    } else {
      const meta = document.createElement('meta');
      meta.name = 'theme-color';
      meta.content = '#0D4D4D';
      document.head.appendChild(meta);
    }
    
    // Update apple touch icon
    let appleTouchIcon = document.querySelector('link[rel="apple-touch-icon"]');
    if (appleTouchIcon) {
      appleTouchIcon.href = '/lavela-icon-192.png';
    }
    
    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
    }
    
    // Listen for install prompt
    const handleBeforeInstall = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      // Show install banner after 3 seconds
      setTimeout(() => setShowInstallBanner(true), 3000);
    };
    
    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
      setIsInstalled(true);
      setShowInstallBanner(false);
    }
    setDeferredPrompt(null);
  };

  // Reduced star particles for better performance (15 instead of 30)
  const stars = Array.from({ length: 15 }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    top: `${Math.random() * 100}%`,
    size: Math.random() * 2 + 1,
    delay: Math.random() * 2,
    duration: Math.random() * 3 + 3
  }));

  return (
    <>
      {/* SEO Meta Tags for LA VELA BIANCA */}
      <Helmet>
        <title>LA VELA BIANCA | Luxury Teen Skincare | Clean Light for Your Skin | Canada</title>
        <meta name="description" content="LA VELA BIANCA - Premium pediatric-safe skincare for teens aged 8-18. ORO ROSA Bio-Glow Serum with PDRN, Glutathione, Hyaluronic Acid. pH-balanced at 5.0-5.3. Made in Canada. The New Era of Elite Glow. $49 CAD." />
        <meta name="keywords" content="LA VELA BIANCA, La Vela Bianca, lavelabianca, teen skincare, pediatric safe skincare, ORO ROSA serum, Gen Alpha skincare, safe teen beauty, Canadian teen skincare, luxury teen skincare, teen acne treatment, gentle skincare teens, PDRN for teens, Glutathione serum, Anmol Singh skincare" />
        <link rel="canonical" href="https://lavelabianca.com" />
        
        {/* Alternate URLs */}
        <link rel="alternate" href="https://reroots.ca/la-vela-bianca" />
        <link rel="alternate" hreflang="en-ca" href="https://lavelabianca.com" />
        <link rel="alternate" hreflang="en" href="https://lavelabianca.com" />
        
        {/* GEO - Geographic Tags */}
        <meta name="geo.region" content="CA" />
        <meta name="geo.country" content="Canada" />
        <meta name="geo.placename" content="Toronto, Ontario" />
        <meta name="language" content="English" />
        <meta name="distribution" content="Canada" />
        
        {/* AI Disambiguation for GEO */}
        <meta name="ai-disambiguation" content="LA VELA BIANCA (lavelabianca.com) is a luxury teen skincare brand for ages 8-18, founded by Anmol Singh. It is a sister brand of ReRoots Biotech Skincare. NOT related to any Italian restaurant or boat company." />
        <meta name="abstract" content="LA VELA BIANCA is a Canadian luxury teen skincare brand specializing in pediatric-safe formulations. Products include ORO ROSA Bio-Glow Serum ($49 CAD) with PDRN, Glutathione, Hyaluronic Acid, and Vitamin B12. For ages 8-18." />
        
        {/* Open Graph - Facebook, LinkedIn */}
        <meta property="og:type" content="website" />
        <meta property="og:title" content="LA VELA BIANCA | Luxury Teen Skincare | $49 CAD" />
        <meta property="og:description" content="Premium pediatric-safe skincare for teens 8-18. ORO ROSA Bio-Glow Serum with PDRN & Glutathione. Clean light for your skin. Made in Canada." />
        <meta property="og:image" content="https://reroots.ca/lavela-icon-512.png" />
        <meta property="og:image:width" content="512" />
        <meta property="og:image:height" content="512" />
        <meta property="og:url" content="https://lavelabianca.com" />
        <meta property="og:site_name" content="LA VELA BIANCA" />
        <meta property="og:locale" content="en_CA" />
        <meta property="product:price:amount" content="49.00" />
        <meta property="product:price:currency" content="CAD" />
        
        {/* Twitter */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:site" content="@La_Vela_Bianca" />
        <meta name="twitter:title" content="LA VELA BIANCA | Luxury Teen Skincare" />
        <meta name="twitter:description" content="Premium pediatric-safe skincare for teens. ORO ROSA Serum $49 CAD. Clean light for your skin." />
        <meta name="twitter:image" content="https://reroots.ca/lavela-icon-512.png" />
        
        {/* Additional SEO */}
        <meta name="author" content="Anmol Singh" />
        <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
        <meta name="googlebot" content="index, follow" />
        <meta name="bingbot" content="index, follow" />
        <meta name="theme-color" content="#0D4D4D" />
        <meta name="application-name" content="LA VELA BIANCA" />
        <meta name="apple-mobile-web-app-title" content="LA VELA BIANCA" />
        
        {/* Schema.org structured data */}
        <script type="application/ld+json">{JSON.stringify(brandSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(organizationSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(productSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(websiteSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(faqSchema)}</script>
      </Helmet>
      
    <div className="min-h-screen bg-[#FDF8F5] overflow-y-auto overflow-x-hidden">
      {/* PWA Install Banner */}
      <AnimatePresence>
        {showInstallBanner && !isInstalled && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="fixed bottom-4 left-4 right-4 z-50 bg-gradient-to-r from-[#0D4D4D] to-[#1A6B6B] rounded-2xl p-4 shadow-2xl border border-[#E6BE8A]/30"
          >
            <button 
              onClick={() => setShowInstallBanner(false)}
              className="absolute top-2 right-2 text-white/60 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-[#E6BE8A] to-[#D4A574] flex items-center justify-center flex-shrink-0">
                <img src="/lavela-icon.png" alt="LA VELA" className="w-10 h-10 rounded-lg" />
              </div>
              <div className="flex-1">
                <h4 className="text-white font-semibold text-sm">Get the LA VELA App</h4>
                <p className="text-[#E8C4B8]/80 text-xs">Add to home screen for the best experience ✨</p>
              </div>
              <button
                onClick={handleInstall}
                className="bg-[#E6BE8A] hover:bg-[#D4A574] text-[#0D4D4D] font-semibold py-2 px-4 rounded-lg text-sm flex items-center gap-2 transition-colors"
              >
                <Download className="w-4 h-4" />
                Install
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Navigation - White Header */}
      <nav className="bg-white px-4 sm:px-6 py-2 border-b border-[#E6BE8A]/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Login Button - LEFT side */}
          <Link 
            to="/lavela/auth" 
            className="bg-[#D4A574] hover:bg-[#B8956A] text-white text-[10px] font-medium py-1.5 px-4 rounded transition-colors"
          >
            LOG IN
          </Link>
          
          {/* Logo - CENTER */}
          <Link to="/la-vela-bianca" className="flex items-center flex-shrink-0 absolute left-1/2 transform -translate-x-1/2">
            <img src="/lavela-header-logo.png" alt="LA VELA BIANCA - The New Era of Elite Glow" className="h-7 sm:h-8" />
          </Link>
          
          {/* Nav Links - Desktop Only - RIGHT */}
          <div className="hidden md:flex items-center gap-5">
            <Link to="/la-vela-bianca" className="text-[#2D2A2E] text-xs hover:text-[#D4A574] transition-colors">Home</Link>
            <Link to="/lavela/founder" className="text-[#2D2A2E] text-xs hover:text-[#D4A574] transition-colors">About</Link>
            <Link to="/lavela/oro-rosa" className="text-[#2D2A2E] text-xs hover:text-[#D4A574] transition-colors">Shop</Link>
            <Link to="/lavela/lab" className="text-[#2D2A2E] text-xs hover:text-[#D4A574] transition-colors">The Lab</Link>
            <Link to="/lavela/glow-club" className="text-[#2D2A2E] text-xs hover:text-[#D4A574] transition-colors">Glow Club</Link>
          </div>
          
          {/* Mobile: Empty div for spacing */}
          <div className="md:hidden w-16"></div>
        </div>
      </nav>

      {/* Hero Section - Midnight to Dawn Gradient */}
      <section className="relative min-h-[80vh]" style={{
        background: 'linear-gradient(135deg, #0D4D4D 0%, #1A6B6B 35%, #D4A090 75%, #E8C4B8 100%)'
      }}>
        {/* Constellation SVG Background */}
        <svg className="absolute inset-0 w-full h-full opacity-40" preserveAspectRatio="xMidYMid slice">
          <defs>
            <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#F0E6D3" stopOpacity="1"/>
              <stop offset="100%" stopColor="#F0E6D3" stopOpacity="0"/>
            </radialGradient>
          </defs>
          {/* Constellation lines */}
          <path d="M100 80 L250 120 L400 90 L550 150 L700 100" stroke="#E6BE8A" strokeWidth="0.5" fill="none" opacity="0.4"/>
          <path d="M800 60 L900 110 L1000 80 L1100 140" stroke="#E6BE8A" strokeWidth="0.5" fill="none" opacity="0.3"/>
          <path d="M150 200 L300 180 L450 220" stroke="#E6BE8A" strokeWidth="0.5" fill="none" opacity="0.3"/>
          {/* Stars at constellation points */}
          <circle cx="100" cy="80" r="3" fill="#F0E6D3"/>
          <circle cx="250" cy="120" r="2" fill="#E6BE8A"/>
          <circle cx="400" cy="90" r="3" fill="#F0E6D3"/>
          <circle cx="550" cy="150" r="2" fill="#E6BE8A"/>
          <circle cx="700" cy="100" r="3" fill="#F0E6D3"/>
          <circle cx="800" cy="60" r="2" fill="#F0E6D3"/>
          <circle cx="900" cy="110" r="3" fill="#E6BE8A"/>
          <circle cx="1000" cy="80" r="2" fill="#F0E6D3"/>
          <circle cx="1100" cy="140" r="3" fill="#F0E6D3"/>
          <circle cx="150" cy="200" r="2" fill="#E6BE8A"/>
          <circle cx="300" cy="180" r="3" fill="#F0E6D3"/>
          <circle cx="450" cy="220" r="2" fill="#E6BE8A"/>
        </svg>
        
        {/* Animated stars */}
        {stars.map(star => (
          <motion.div
            key={star.id}
            className="absolute rounded-full bg-[#F0E6D3]"
            style={{
              left: star.left,
              top: star.top,
              width: star.size,
              height: star.size,
            }}
            animate={{
              opacity: [0.3, 1, 0.3],
              scale: [1, 1.3, 1],
            }}
            transition={{
              duration: star.duration,
              delay: star.delay,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        ))}

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-8 py-12 sm:py-16">
          <div className="grid lg:grid-cols-2 gap-8 items-center">
            {/* Left - Text Content */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={isLoaded ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.8 }}
              className="text-center lg:text-left"
            >
              {/* Main Headline */}
              <h1 className="text-white text-4xl sm:text-5xl lg:text-6xl leading-tight mb-6" style={{fontFamily: "'Playfair Display', serif", fontWeight: 500}}>
                Unveil Your
                <br />
                <span className="text-[#E6BE8A]">Inner Radiance</span>
              </h1>
              
              {/* Description */}
              <p className="text-[#F5DED6]/90 text-sm sm:text-base mb-8 max-w-md mx-auto lg:mx-0 leading-relaxed">
                Luxury skincare designed for young, radiant skin. 
                Clinically tested, pediatric-safe formulas that deliver 
                visible results without compromise.
              </p>
              
              {/* CTA Button - Outline Style */}
              <Link 
                to="/lavela/oro-rosa" 
                className="inline-block border-2 border-[#E6BE8A] text-[#E6BE8A] hover:bg-[#E6BE8A] hover:text-[#0D4D4D] font-semibold py-3 px-8 transition-all duration-300 text-sm tracking-wider"
              >
                SHOP NOW
              </Link>
              
              {/* Carousel dots */}
              <div className="flex gap-2 mt-8 justify-center lg:justify-start">
                <div className="w-2 h-2 rounded-full bg-white"></div>
                <div className="w-2 h-2 rounded-full bg-white/40"></div>
                <div className="w-2 h-2 rounded-full bg-white/40"></div>
                <div className="w-2 h-2 rounded-full bg-white/40"></div>
              </div>
            </motion.div>

            {/* Right - Product Display */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={isLoaded ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="relative flex justify-center items-center"
            >
              {/* Product Image - Full Display */}
              <motion.div
                className="relative z-10"
                whileHover={{ scale: 1.02 }}
                transition={{ duration: 0.3 }}
              >
                <img 
                  src="/oro-rosa-product.png" 
                  alt="ORO ROSA Serum" 
                  className="h-[350px] sm:h-[450px] object-contain drop-shadow-2xl"
                  loading="lazy"
                  decoding="async"
                />
              </motion.div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Our Story + Key Ingredients Section - Light Gradient */}
      <section className="py-16 sm:py-24 px-4" style={{
        background: 'linear-gradient(180deg, #FDF8F5 0%, #F5DED6 50%, #E8C4B8 100%)'
      }}>
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12">
            {/* Our Story */}
            <div>
              <h2 className="text-[#2D2A2E] text-2xl sm:text-3xl mb-6" style={{fontFamily: "'Playfair Display', serif"}}>
                Our Story
              </h2>
              <p className="text-[#5D6D7E] text-sm leading-relaxed mb-4">
                Born from a vision to create skincare that teens deserve — 
                luxurious, effective, and safe. LA VELA BIANCA bridges the 
                gap between clinical efficacy and youthful radiance.
              </p>
              <p className="text-[#5D6D7E] text-sm leading-relaxed mb-6">
                Our Canadian-Italian formulation philosophy combines the 
                precision of dermatological science with the elegance of 
                luxury skincare. Every product is pediatric-safe, pH-balanced 
                at 5.0-5.3, and designed specifically for developing skin.
              </p>
              <Link 
                to="/lavela/founder" 
                className="inline-block border border-[#D4A574] text-[#D4A574] hover:bg-[#D4A574] hover:text-white font-medium py-2 px-6 text-sm transition-all duration-300"
              >
                OUR FOUNDER
              </Link>
            </div>
            
            {/* Key Ingredients */}
            <div>
              <h2 className="text-[#2D2A2E] text-2xl sm:text-3xl mb-6" style={{fontFamily: "'Playfair Display', serif"}}>
                Key Ingredients
              </h2>
              <p className="text-[#5D6D7E] text-sm leading-relaxed">
                We source only the finest active ingredients — PDRN Complex 
                for cellular regeneration, Glutathione for radiant brightness, 
                and Hyaluronic Acid for deep hydration. Each formula is 
                dermatologist-tested and free from harsh chemicals, parabens, 
                and artificial fragrances.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Key Ingredients Cards - Dark Section */}
      <section className="py-16 sm:py-24 px-4 relative overflow-hidden" style={{
        background: 'linear-gradient(180deg, #0D4D4D 0%, #1A5C5C 100%)'
      }}>
        {/* Stars background */}
        <div className="absolute inset-0 opacity-30">
          {stars.slice(0, 20).map(star => (
            <motion.div
              key={`ing-${star.id}`}
              className="absolute rounded-full bg-[#F0E6D3]"
              style={{
                left: star.left,
                top: star.top,
                width: star.size,
                height: star.size,
              }}
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: star.duration, delay: star.delay, repeat: Infinity }}
            />
          ))}
        </div>
        
        <div className="max-w-6xl mx-auto relative z-10">
          <div className="text-center mb-12">
            <p className="text-[#E6BE8A] text-sm uppercase tracking-[0.2em] mb-4">Key Ingredients</p>
            <h2 className="text-white text-3xl sm:text-4xl" style={{fontFamily: "'Playfair Display', serif"}}>
              Premium Actives for 
              <span className="text-[#E6BE8A]"> Radiant Skin</span>
            </h2>
          </div>
          
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { name: "PDRN Complex", desc: "Cellular regeneration & DNA repair", icon: "🧬" },
              { name: "Glutathione", desc: "Master antioxidant for bright, even tone", icon: "✨" },
              { name: "Hyaluronic Acid", desc: "Deep hydration & plumping effect", icon: "💧" },
              { name: "Niacinamide", desc: "Pore refinement & oil control", icon: "🌟" },
              { name: "Vitamin C", desc: "Radiance boosting & protection", icon: "🍊" },
              { name: "Ceramides", desc: "Barrier repair & moisture lock", icon: "🛡️" },
            ].map((ingredient, i) => (
              <motion.div
                key={i}
                className="bg-white/10 backdrop-blur-sm border border-[#E6BE8A]/20 rounded-xl p-6 text-center"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <span className="text-4xl mb-4 block">{ingredient.icon}</span>
                <h3 className="text-[#E6BE8A] font-semibold mb-2">{ingredient.name}</h3>
                <p className="text-[#F5DED6]/70 text-sm">{ingredient.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-16 sm:py-24 px-4" style={{
        background: 'linear-gradient(180deg, #FDF8F5 0%, #F5DED6 100%)'
      }}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-[#D4A574] text-sm uppercase tracking-[0.2em] mb-4">Testimonials</p>
            <h2 className="text-[#2D2A2E] text-3xl sm:text-4xl" style={{fontFamily: "'Playfair Display', serif"}}>
              What Our Customers Say
            </h2>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { name: "Sarah M.", age: "15", text: "Finally a serum that doesn't irritate my sensitive skin! My acne cleared up in 2 weeks." },
              { name: "Emma K.", age: "14", text: "The glow is REAL! All my friends keep asking what I'm using. Obsessed! 💕" },
              { name: "Olivia T.", age: "16", text: "As a mom, I love that it's pediatric-safe. As a teen, my daughter loves the results!" },
            ].map((testimonial, i) => (
              <motion.div
                key={i}
                className="bg-white/80 backdrop-blur-sm border border-[#D4A574]/20 rounded-xl p-6"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15 }}
              >
                <div className="flex gap-1 mb-4">
                  {[1,2,3,4,5].map(s => <Star key={s} className="w-4 h-4 fill-[#E6BE8A] text-[#E6BE8A]" />)}
                </div>
                <p className="text-[#5D6D7E] italic mb-4 text-sm">"{testimonial.text}"</p>
                <p className="text-[#D4A574] font-medium text-sm">{testimonial.name}, {testimonial.age}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 sm:py-24 px-4 relative overflow-hidden" style={{
        background: 'linear-gradient(135deg, #1A5C5C 0%, #0D4D4D 100%)'
      }}>
        {/* Stars */}
        <div className="absolute inset-0 opacity-20">
          {stars.slice(0, 15).map(star => (
            <div
              key={`cta-${star.id}`}
              className="absolute rounded-full bg-[#F0E6D3]"
              style={{ left: star.left, top: star.top, width: star.size, height: star.size }}
            />
          ))}
        </div>
        
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <h2 className="text-white text-3xl sm:text-4xl lg:text-5xl mb-6" style={{fontFamily: "'Playfair Display', serif"}}>
            Begin Your <span className="text-[#E6BE8A]">Glow Journey</span>
          </h2>
          <p className="text-[#F5DED6]/80 text-base mb-8 max-w-2xl mx-auto">
            Join thousands of teens who've discovered their inner radiance with LA VELA BIANCA
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              to="/lavela/oro-rosa" 
              className="bg-[#D4A574] hover:bg-[#B8956A] text-white font-semibold py-3 px-8 transition-colors text-sm tracking-wider"
            >
              DISCOVER ORO ROSA
            </Link>
            <button 
              onClick={handleInstall}
              className="border-2 border-[#E6BE8A] text-[#E6BE8A] hover:bg-[#E6BE8A] hover:text-[#0D4D4D] font-semibold py-3 px-8 transition-all text-sm tracking-wider flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4" />
              ADD TO HOMESCREEN
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#0F3D3D] py-12 px-4 border-t border-[#E6BE8A]/20">
        <div className="max-w-6xl mx-auto">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8 mb-10">
            <div>
              <div className="mb-4">
                {/* Text-based logo for footer - no background issues */}
                <h3 className="text-xl text-[#E6BE8A] font-semibold" style={{ fontFamily: "'Playfair Display', serif" }}>
                  LA VELA BIANCA
                </h3>
                <p className="text-[10px] tracking-[0.15em] text-[#E6BE8A]/60">THE NEW ERA OF ELITE GLOW</p>
              </div>
              <p className="text-[#E8C4B8]/60 text-sm">
                The New Era of Elite Glow. Premium skincare for young, developing skin.
              </p>
            </div>
            
            <div>
              <h4 className="text-[#E6BE8A] font-semibold mb-4 text-sm">Shop</h4>
              <ul className="space-y-2 text-[#E8C4B8]/60 text-sm">
                <li><Link to="/lavela/oro-rosa" className="hover:text-[#E6BE8A] transition-colors">ORO ROSA Serum</Link></li>
                <li><Link to="/lavela/glow-club" className="hover:text-[#E6BE8A] transition-colors">Glow Club</Link></li>
                <li>
                  <button 
                    onClick={handleInstall}
                    className="hover:text-[#E6BE8A] transition-colors flex items-center gap-2"
                  >
                    <Download className="w-3 h-3" />
                    Add to Homescreen
                  </button>
                </li>
              </ul>
            </div>
            
            <div>
              <h4 className="text-[#E6BE8A] font-semibold mb-4 text-sm">About</h4>
              <ul className="space-y-2 text-[#E8C4B8]/60 text-sm">
                <li><Link to="/lavela/founder" className="hover:text-[#E6BE8A] transition-colors">Our Story</Link></li>
                <li><Link to="/lavela/lab" className="hover:text-[#E6BE8A] transition-colors">The Lab</Link></li>
              </ul>
            </div>
            
            <div>
              <h4 className="text-[#E6BE8A] font-semibold mb-4 text-sm">Connect</h4>
              <ul className="space-y-2 text-[#E8C4B8]/60 text-sm">
                <li>
                  <a href="https://instagram.com/La_Vela_Bianca" target="_blank" rel="noopener noreferrer" className="hover:text-[#E6BE8A] transition-colors flex items-center gap-2">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                    @La_Vela_Bianca
                  </a>
                </li>
                <li>
                  <a href="mailto:Anmol@lavelabianca.com" className="hover:text-[#E6BE8A] transition-colors flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                    Email Us
                  </a>
                </li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-[#E6BE8A]/20 pt-8 text-center text-[#E8C4B8]/40 text-sm">
            <p>© 2026 LA VELA BIANCA. All rights reserved.</p>
            <p className="mt-2">Pediatric-Safe • Dermatologist Tested • Made with Love in Canada 🇨🇦</p>
            
            {/* Pediatric Safety Disclaimer */}
            <div className="mt-6 mx-auto max-w-xl p-4 bg-[#0D4D4D]/50 border border-[#E6BE8A]/30 rounded-lg">
              <p className="text-[#E8C4B8]/80 text-xs leading-relaxed flex items-start gap-2">
                <Shield className="w-4 h-4 text-[#E6BE8A] shrink-0 mt-0.5" />
                <span>
                  <strong className="text-[#E6BE8A]">Safety Note:</strong> Formulated for young skin barriers. 
                  We recommend a patch test for children under 10. Always use in conjunction with daily SPF protection.
                </span>
              </p>
            </div>
            
            <p className="mt-4">
              <a href="mailto:Anmol@lavelabianca.com" className="hover:text-[#E6BE8A] transition-colors">Anmol@lavelabianca.com</a>
            </p>
          </div>
        </div>
      </footer>
    </div>
    </>
  );
};

export default LaVelaLandingPage;
