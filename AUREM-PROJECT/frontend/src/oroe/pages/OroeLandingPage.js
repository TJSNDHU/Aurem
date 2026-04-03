import React, { useState, useEffect, useRef } from "react";
import { Helmet } from "react-helmet-async";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import "../styles/oroe-design-system.css";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Currency configurations with flags for prestige display
const CURRENCIES = {
  USD: { symbol: "$", rate: 1, name: "US Dollar", flag: "🇺🇸" },
  CAD: { symbol: "C$", rate: 1.36, name: "Canadian Dollar", flag: "🇨🇦" },
  EUR: { symbol: "€", rate: 0.91, name: "Euro", flag: "🇪🇺" },
  GBP: { symbol: "£", rate: 0.79, name: "British Pound", flag: "🇬🇧" },
  AED: { symbol: "د.إ", rate: 3.67, name: "UAE Dirham", flag: "🇦🇪" }
};

// Language configurations
const LANGUAGES = {
  en: { name: "English", flag: "🇬🇧", nativeName: "English" },
  fr: { name: "Français", flag: "🇫🇷", nativeName: "Français" },
  ar: { name: "العربية", flag: "🇦🇪", rtl: true, nativeName: "العربية" }
};

// Elegant Dropdown Component for OROÉ
const LuxuryDropdown = ({ value, onChange, options, type = "currency" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);
  
  const currentOption = options.find(opt => opt.code === value);
  
  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm tracking-wide text-[#D4AF37] 
                   border border-[#D4AF37]/30 rounded-sm bg-transparent
                   hover:border-[#D4AF37]/60 hover:bg-[#D4AF37]/5 
                   transition-all duration-300 min-w-[100px]"
        data-testid={`${type}-selector`}
      >
        <span className="text-base">{currentOption?.flag}</span>
        <span className="font-light">{type === "currency" ? value : currentOption?.nativeName}</span>
        <svg 
          className={`w-3 h-3 ml-1 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {isOpen && (
        <div className="absolute top-full mt-2 right-0 min-w-[180px] 
                        bg-[#0A0A0A]/98 backdrop-blur-xl border border-[#D4AF37]/20 
                        rounded-sm shadow-2xl shadow-black/50 overflow-hidden z-50
                        animate-in fade-in slide-in-from-top-2 duration-200">
          {options.map((option) => (
            <button
              key={option.code}
              onClick={() => {
                onChange(option.code);
                setIsOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 text-sm text-left
                         transition-all duration-200
                         ${value === option.code 
                           ? 'bg-[#D4AF37]/10 text-[#D4AF37]' 
                           : 'text-[#FDF8F0]/70 hover:bg-[#D4AF37]/5 hover:text-[#D4AF37]'
                         }`}
              data-testid={`${type}-option-${option.code}`}
            >
              <span className="text-lg">{option.flag}</span>
              <div className="flex flex-col">
                <span className="font-light tracking-wide">
                  {type === "currency" ? option.code : option.nativeName}
                </span>
                <span className="text-xs text-[#FDF8F0]/40">
                  {type === "currency" ? option.name : option.name}
                </span>
              </div>
              {value === option.code && (
                <span className="ml-auto text-[#D4AF37]">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// Hide ReRoots global elements for OROÉ standalone experience
const useOroeMode = () => {
  useEffect(() => {
    // Add OROÉ mode class to body
    document.body.classList.add('oroe-mode');
    document.body.style.setProperty('--global-banner-display', 'none');
    
    // Hide ReRoots-specific elements
    const elementsToHide = document.querySelectorAll('[data-reroots-element], .pwa-install-prompt, .founding-member-banner, .bio-scan-banner');
    elementsToHide.forEach(el => {
      el.style.display = 'none';
    });
    
    return () => {
      document.body.classList.remove('oroe-mode');
      document.body.style.removeProperty('--global-banner-display');
      elementsToHide.forEach(el => {
        el.style.display = '';
      });
    };
  }, []);
};

// Translations
const translations = {
  en: {
    heroTitle: "The Golden Elixir",
    heroSubtitle: "Maison de la Lumière Dorée",
    heroTagline: "Where Science Meets Splendor",
    joinWaitlist: "Apply for Allocation",
    viewElixir: "Discover The Elixir",
    limitedEdition: "Limited to 500 Numbered Bottles",
    maisonTitle: "The Maison",
    maisonSubtitle: "A Legacy of Golden Light",
    elixirTitle: "The Luminous Elixir",
    elixirSubtitle: "Your Cellular Renaissance",
    waitlistTitle: "Apply for Allocation",
    waitlistSubtitle: "Request Your Place in Batch 01",
    firstName: "First Name",
    lastName: "Last Name",
    email: "Email Address",
    country: "Country of Residence",
    skinConcern: "Primary Skin Concern",
    whyJoin: "Why do you wish to join the Maison?",
    referredBy: "Who referred you to OROÉ?",
    referredByPlaceholder: "Name of your referrer (optional)",
    submitApplication: "Apply for Allocation",
    applicationReceived: "Application Received",
    welcomeMessage: "Welcome to the waiting room of the Maison. We shall be in touch."
  },
  fr: {
    heroTitle: "L'Élixir Doré",
    heroSubtitle: "Maison de la Lumière Dorée",
    heroTagline: "Où la Science Rencontre la Splendeur",
    joinWaitlist: "Demander une Allocation",
    viewElixir: "Découvrir L'Élixir",
    limitedEdition: "Limité à 500 Flacons Numérotés",
    maisonTitle: "La Maison",
    maisonSubtitle: "Un Héritage de Lumière Dorée",
    elixirTitle: "L'Élixir Lumineux",
    elixirSubtitle: "Votre Renaissance Cellulaire",
    waitlistTitle: "Demander une Allocation",
    waitlistSubtitle: "Demandez Votre Place dans le Lot 01",
    firstName: "Prénom",
    lastName: "Nom",
    email: "Adresse Email",
    country: "Pays de Résidence",
    skinConcern: "Préoccupation Cutanée Principale",
    whyJoin: "Pourquoi souhaitez-vous rejoindre la Maison?",
    referredBy: "Qui vous a recommandé OROÉ?",
    referredByPlaceholder: "Nom de votre référent (facultatif)",
    submitApplication: "Demander une Allocation",
    applicationReceived: "Demande Reçue",
    welcomeMessage: "Bienvenue dans la salle d'attente de la Maison. Nous vous contacterons."
  },
  ar: {
    heroTitle: "الإكسير الذهبي",
    heroSubtitle: "بيت النور الذهبي",
    heroTagline: "حيث يلتقي العلم بالروعة",
    joinWaitlist: "طلب تخصيص",
    viewElixir: "اكتشف الإكسير",
    limitedEdition: "إصدار محدود - 500 زجاجة مرقمة",
    maisonTitle: "البيت",
    maisonSubtitle: "إرث من النور الذهبي",
    elixirTitle: "الإكسير المضيء",
    elixirSubtitle: "نهضتك الخلوية",
    waitlistTitle: "طلب تخصيص",
    waitlistSubtitle: "اطلب مكانك في الدفعة الأولى",
    firstName: "الاسم الأول",
    lastName: "اسم العائلة",
    email: "البريد الإلكتروني",
    country: "بلد الإقامة",
    skinConcern: "القلق الجلدي الرئيسي",
    whyJoin: "لماذا ترغب في الانضمام إلى البيت؟",
    referredBy: "من أوصاك بـ OROÉ؟",
    referredByPlaceholder: "اسم المُحيل (اختياري)",
    submitApplication: "طلب تخصيص",
    applicationReceived: "تم استلام الطلب",
    welcomeMessage: "مرحباً بك في غرفة انتظار البيت. سنتواصل معك قريباً."
  }
};

// Countdown Timer Component for Founder's Batch Release
const CountdownTimer = () => {
  const [timeLeft, setTimeLeft] = useState({ days: 0, hours: 0, minutes: 0, seconds: 0 });
  
  useEffect(() => {
    // Set target date: Next batch release (e.g., 30 days from now or a specific date)
    // For now, use a rolling 30-day countdown that resets
    const getNextBatchDate = () => {
      const now = new Date();
      // Set next batch to the 1st of next month at midnight
      const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      return nextMonth;
    };
    
    const targetDate = getNextBatchDate();
    
    const calculateTimeLeft = () => {
      const now = new Date();
      const difference = targetDate - now;
      
      if (difference > 0) {
        return {
          days: Math.floor(difference / (1000 * 60 * 60 * 24)),
          hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
          minutes: Math.floor((difference / 1000 / 60) % 60),
          seconds: Math.floor((difference / 1000) % 60)
        };
      }
      return { days: 0, hours: 0, minutes: 0, seconds: 0 };
    };
    
    setTimeLeft(calculateTimeLeft());
    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft());
    }, 1000);
    
    return () => clearInterval(timer);
  }, []);
  
  return (
    <div className="mt-6 mb-4">
      <p className="text-[10px] tracking-[0.3em] text-[#D4AF37]/60 uppercase mb-3">
        Next Founder's Batch Release
      </p>
      <div className="flex justify-center gap-3">
        {[
          { value: timeLeft.days, label: 'Days' },
          { value: timeLeft.hours, label: 'Hours' },
          { value: timeLeft.minutes, label: 'Min' },
          { value: timeLeft.seconds, label: 'Sec' }
        ].map((item, idx) => (
          <div key={idx} className="text-center">
            <div className="w-14 h-14 bg-gradient-to-b from-[#D4AF37]/20 to-[#D4AF37]/5 
                          border border-[#D4AF37]/40 rounded-sm flex items-center justify-center
                          shadow-lg shadow-[#D4AF37]/10">
              <span className="text-xl font-display text-[#D4AF37]">
                {String(item.value).padStart(2, '0')}
              </span>
            </div>
            <span className="text-[8px] tracking-wider text-[#FDF8F0]/40 uppercase mt-1 block">
              {item.label}
            </span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-[#FDF8F0]/30 mt-3 italic">
        Only 50 bottles per batch • Artisan-crafted in Canada
      </p>
    </div>
  );
};

const OroeLandingPage = () => {
  const navigate = useNavigate();
  const [language, setLanguage] = useState("en");
  const [currency, setCurrency] = useState("USD");
  const [showWaitlist, setShowWaitlist] = useState(false);
  const [showCryptoPayment, setShowCryptoPayment] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [cryptoLoading, setCryptoLoading] = useState(false);
  const [selectedCrypto, setSelectedCrypto] = useState("USDC");
  const [scrollY, setScrollY] = useState(0);
  const heroRef = useRef(null);
  const videoRef = useRef(null);
  
  // Product data fetched from database
  const [product, setProduct] = useState(null);
  const [productLoading, setProductLoading] = useState(true);
  
  // Activate OROÉ standalone mode
  useOroeMode();
  
  // Scroll to top when page loads
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  
  // Fetch the Luminous Elixir product from database
  useEffect(() => {
    const fetchProduct = async () => {
      try {
        const response = await axios.get(`${API}/oroe/products`);
        const products = response.data?.products || response.data || [];
        
        // Priority order for finding the main product:
        // 1. "Luminous Elixir" with waitlist availability
        // 2. Any product with "Luminous Elixir" in name
        // 3. Any product with video_url (for hero video display)
        // 4. First active product
        const elixir = products.find(p => 
          p.name?.toLowerCase().includes('luminous elixir') && 
          p.availability === 'waitlist'
        ) || products.find(p => 
          p.name?.toLowerCase().includes('luminous elixir')
        ) || products.find(p => 
          p.video_url && p.status === 'active'
        ) || products[0];
        
        if (elixir) {
          console.log("OROÉ Product loaded:", elixir.name, {
            hasVideo: !!elixir.video_url,
            hasHeroImage: !!elixir.hero_image_url,
            hasDescription: !!elixir.descriptions
          });
        }
        setProduct(elixir);
      } catch (error) {
        console.error("Failed to fetch OROÉ product:", error);
      } finally {
        setProductLoading(false);
      }
    };
    fetchProduct();
  }, []);
  
  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    country: "",
    skinConcern: "",
    whyJoin: "",
    // Referral tracking for inner circle growth
    referredBy: "",  // Who referred them
    referralCode: "",  // If they used a code
    // New pre-qualification fields
    communicationPreference: "email",
    clinicalExperience: "",
    discoverySource: "",
    unitsRequested: "1",
    paymentPreference: "traditional"
  });
  
  // Multi-step form state
  const [formStep, setFormStep] = useState(1);
  const totalFormSteps = 3;
  
  const [cryptoFormData, setCryptoFormData] = useState({
    name: "",
    email: ""
  });

  const t = translations[language];
  const isRTL = LANGUAGES[language]?.rtl;
  const basePrice = 155; // USD
  const displayPrice = Math.round(basePrice * CURRENCIES[currency].rate);
  
  // Crypto options with icons
  const cryptoOptions = [
    { code: "USDC", name: "USD Coin", icon: "💵", color: "#2775CA" },
    { code: "BTC", name: "Bitcoin", icon: "₿", color: "#F7931A" },
    { code: "ETH", name: "Ethereum", icon: "Ξ", color: "#627EEA" }
  ];
  
  // Handle crypto payment
  const handleCryptoPayment = async () => {
    if (!cryptoFormData.name || !cryptoFormData.email) {
      alert(language === 'en' ? 'Please fill in all fields' : language === 'fr' ? 'Veuillez remplir tous les champs' : 'يرجى ملء جميع الحقول');
      return;
    }
    
    setCryptoLoading(true);
    try {
      const response = await fetch(`${API}/oroe/crypto/create-charge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: displayPrice.toString(),
          currency: currency,
          crypto_currency: selectedCrypto,
          description: `OROÉ Luminous Elixir - ${selectedCrypto} Payment`,
          customer_email: cryptoFormData.email,
          customer_name: cryptoFormData.name,
          product_id: "oroe-luminous-elixir"
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        if (data.is_mock) {
          // Demo mode - show success message
          alert(`Demo Mode: Your ${selectedCrypto} payment for ${displayPrice} ${currency} would be processed via Coinbase Commerce. Configure COINBASE_COMMERCE_API_KEY for live payments.`);
        } else {
          // Redirect to Coinbase Commerce checkout
          window.location.href = data.hosted_url;
        }
      } else {
        throw new Error(data.detail || 'Payment creation failed');
      }
    } catch (error) {
      console.error('Crypto payment error:', error);
      alert(language === 'en' ? 'Payment error. Please try again.' : language === 'fr' ? 'Erreur de paiement. Veuillez réessayer.' : 'خطأ في الدفع. يرجى المحاولة مرة أخرى.');
    } finally {
      setCryptoLoading(false);
    }
  };

  // Scroll Y with RAF throttling (prevents layout thrashing)
  useEffect(() => {
    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          setScrollY(window.scrollY);
          ticking = false;
        });
        ticking = true;
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email || !formData.firstName || !formData.country) {
      toast.error("Please complete the required fields");
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(`${API}/oroe/waitlist`, {
        ...formData,
        language,
        currency,
        source: "landing_page",
        timestamp: new Date().toISOString()
      });
      setSubmitted(true);
      // Store position for confirmation screen
      setFormData(prev => ({ ...prev, waitlistPosition: response.data.position }));
      toast.success(t.applicationReceived);
    } catch (error) {
      console.error("Waitlist error:", error);
      toast.error("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Multi-step navigation
  const nextStep = () => {
    if (formStep === 1 && (!formData.firstName || !formData.email || !formData.country)) {
      toast.error("Please complete the required fields");
      return;
    }
    if (formStep < totalFormSteps) setFormStep(formStep + 1);
  };
  
  const prevStep = () => {
    if (formStep > 1) setFormStep(formStep - 1);
  };

  return (
    <div className={`oroe-page ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
      <Helmet>
        <title>OROÉ | Maison de la Lumière Dorée</title>
        <meta name="description" content="Discover the OROÉ Luminous Elixir - Where cellular science meets golden luxury. Limited to 500 numbered bottles." />
        {/* Fonts now self-hosted via @fontsource - Cinzel added below */}
      </Helmet>

      {/* === NAVIGATION === */}
      <nav className="fixed top-0 left-0 right-0 z-50 transition-all duration-700" 
           style={{ 
             backgroundColor: scrollY > 100 ? 'rgba(10,10,10,0.95)' : 'transparent',
             backdropFilter: scrollY > 100 ? 'blur(20px)' : 'none'
           }}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          {/* Brand Logo */}
          <div className="flex items-center cursor-pointer" onClick={() => navigate('/oroe')}>
            <img 
              src="https://customer-assets.emergentagent.com/job_premium-brand-suite/artifacts/f2n5jwgb_Screenshot_20260122_183709_Gallery.jpg" 
              alt="OROÉ" 
              className="h-12 sm:h-14 w-auto"
            />
          </div>

          {/* Nav Links */}
          <div className="hidden md:flex items-center gap-8">
            <a href="#maison" className="text-sm tracking-widest text-[#FDF8F0]/70 hover:text-[#D4AF37] transition-colors uppercase">
              {language === 'fr' ? 'La Maison' : language === 'ar' ? 'البيت' : 'The Maison'}
            </a>
            <a href="#elixir" className="text-sm tracking-widest text-[#FDF8F0]/70 hover:text-[#D4AF37] transition-colors uppercase">
              {language === 'fr' ? "L'Élixir" : language === 'ar' ? 'الإكسير' : 'The Elixir'}
            </a>
            <button 
              onClick={() => setShowWaitlist(true)}
              className="oroe-btn-outline text-xs py-3 px-6"
            >
              {t.joinWaitlist}
            </button>
          </div>

          {/* Language & Currency Selectors - Luxury Dropdowns */}
          <div className="flex items-center gap-3">
            <LuxuryDropdown
              value={currency}
              onChange={setCurrency}
              type="currency"
              options={Object.entries(CURRENCIES).map(([code, data]) => ({
                code,
                ...data
              }))}
            />
            <LuxuryDropdown
              value={language}
              onChange={setLanguage}
              type="language"
              options={Object.entries(LANGUAGES).map(([code, data]) => ({
                code,
                ...data
              }))}
            />
          </div>
        </div>
      </nav>

      {/* === THE ATMOSPHERE - Video Hero Section === */}
      <section ref={heroRef} className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20 pb-16 md:pt-0 md:pb-0">
        {/* Video Background from Database */}
        {product?.video_url ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            loop
            playsInline
            className="absolute inset-0 w-full h-full object-cover"
            style={{ 
              opacity: 0.6,
              filter: 'brightness(0.7) contrast(1.1)'
            }}
          >
            <source src={product.video_url} type="video/mp4" />
          </video>
        ) : (
          /* Fallback: Animated Background */
          <div className="absolute inset-0 bg-[#0A0A0A]">
            {/* Golden particles */}
            <div className="absolute inset-0 opacity-30">
              {[...Array(50)].map((_, i) => (
                <div
                  key={i}
                  className="absolute w-1 h-1 bg-[#D4AF37] rounded-full"
                  style={{
                    left: `${Math.random() * 100}%`,
                    top: `${Math.random() * 100}%`,
                    animation: `float ${5 + Math.random() * 10}s ease-in-out infinite`,
                    animationDelay: `${Math.random() * 5}s`,
                    opacity: 0.3 + Math.random() * 0.7
                  }}
                />
              ))}
            </div>
          </div>
        )}
        
        {/* Dark Overlay for Text Readability */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#0A0A0A]/80 via-[#0A0A0A]/40 to-[#0A0A0A]/90" />
        
        {/* Radial gold gradient */}
        <div 
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse at 50% 30%, rgba(212,175,55,0.12) 0%, transparent 60%)`,
            transform: `translateY(${scrollY * 0.2}px)`
          }}
        />

        {/* Hero Content - The Hook */}
        <div className="relative z-10 text-center px-4 sm:px-6 max-w-4xl mx-auto pt-16 sm:pt-20 md:pt-24 pb-16 sm:pb-24">
          {/* OROÉ Emblem Logo - Centered in Hero (Round) */}
          <div className="mb-6 sm:mb-8 oroe-animate-in" style={{ animationDelay: '0.2s' }}>
            <div className="h-28 w-28 sm:h-36 sm:w-36 md:h-44 md:w-44 lg:h-52 lg:w-52 mx-auto rounded-full overflow-hidden"
                 style={{ 
                   boxShadow: '0 0 40px rgba(212,175,55,0.4), 0 0 80px rgba(212,175,55,0.2)',
                   border: '2px solid rgba(212,175,55,0.3)'
                 }}>
              <img 
                src="https://customer-assets.emergentagent.com/job_vipbrandportal/artifacts/ssry9pq3_Screenshot_20260122_185213_Chrome.jpg" 
                alt="OROÉ" 
                className="w-full h-full object-cover"
                data-testid="oroe-hero-logo"
              />
            </div>
          </div>
          
          {/* The Hook - Product Name */}
          <h1 className="font-display text-2xl sm:text-4xl md:text-6xl lg:text-7xl tracking-wide mb-3 sm:mb-6 oroe-animate-in" 
              style={{ 
                animationDelay: '0.4s',
                background: 'linear-gradient(135deg, #D4AF37 0%, #FDF8F0 50%, #D4AF37 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                textShadow: '0 0 60px rgba(212,175,55,0.2)'
              }}>
            {product?.name || "Luminous Elixir"}
          </h1>
          
          {/* Batch Signature */}
          <p className="text-xs sm:text-sm md:text-base tracking-[0.2em] sm:tracking-[0.3em] text-[#D4AF37]/80 uppercase mb-2 sm:mb-4 oroe-animate-in" 
             style={{ animationDelay: '0.6s' }}>
            {product?.batch_signature || "Batch 01"}
          </p>
          
          {/* Divider */}
          <div className="oroe-divider oroe-divider-long oroe-animate-in" style={{ animationDelay: '0.7s' }} />
          
          {/* The Science Hook */}
          <p className="oroe-body-elegant mt-4 sm:mt-8 mb-2 sm:mb-4 text-sm sm:text-lg md:text-xl oroe-animate-in" style={{ animationDelay: '0.8s' }}>
            {language === 'fr' ? 'La Science de la Résurrection Cellulaire' : 
             language === 'ar' ? 'علم القيامة الخلوية' : 
             'The Science of Cellular Resurrection'}
          </p>
          
          {/* Scarcity Badge */}
          <div className="inline-flex items-center gap-2 sm:gap-3 bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded-full px-3 sm:px-6 py-1.5 sm:py-2 mb-6 sm:mb-12 oroe-animate-in" 
               style={{ animationDelay: '1s' }}>
            <span className="w-1.5 sm:w-2 h-1.5 sm:h-2 bg-[#D4AF37] rounded-full animate-pulse" />
            <span className="text-xs sm:text-sm tracking-wider text-[#D4AF37]">
              {language === 'fr' ? `Limité à ${product?.limited_edition_quantity || 500} unités` :
               language === 'ar' ? `محدود إلى ${product?.limited_edition_quantity || 500} وحدة` :
               `Limited to ${product?.limited_edition_quantity || 500} units`}
            </span>
          </div>
          
          {/* Single Elegant CTA - Mobile Optimized */}
          <div className="oroe-animate-in" style={{ animationDelay: '1.2s' }}>
            <button 
              onClick={() => setShowWaitlist(true)}
              className="group relative px-6 sm:px-12 py-3 sm:py-4 bg-transparent border-2 border-[#D4AF37] text-[#D4AF37] 
                         text-xs sm:text-sm tracking-[0.2em] sm:tracking-[0.3em] uppercase font-medium
                         hover:bg-[#D4AF37] hover:text-[#0A0A0A] transition-all duration-500
                         overflow-hidden"
              data-testid="hero-apply-btn"
            >
              <span className="relative z-10">{t.joinWaitlist}</span>
              <div className="absolute inset-0 bg-[#D4AF37] transform -translate-x-full group-hover:translate-x-0 transition-transform duration-500" />
            </button>
          </div>
        </div>

        {/* Scroll Indicator - Hidden on mobile/tablet, only visible on desktop */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex-col items-center gap-2 opacity-50 oroe-animate-in hidden md:flex pointer-events-none" 
             style={{ animationDelay: '1.5s', zIndex: 5 }}>
          <span className="text-xs tracking-widest text-[#D4AF37]">DISCOVER</span>
          <div className="w-px h-16 bg-gradient-to-b from-[#D4AF37] to-transparent animate-pulse" />
        </div>
      </section>

      {/* === THE REVEAL - Product Showcase Section === */}
      <section id="elixir" className="oroe-section relative py-12 sm:py-20 bg-[#0A0A0A]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Left: Hero Product Image */}
            <div className="relative order-2 lg:order-1">
              <div 
                className="relative aspect-square max-w-lg mx-auto"
                style={{
                  opacity: Math.min(1, Math.max(0, (scrollY - 300) / 400)),
                  transform: `translateY(${Math.max(0, 50 - (scrollY - 300) / 8)}px)`
                }}
              >
                {/* Glow Effect */}
                <div className="absolute inset-0 bg-gradient-radial from-[#D4AF37]/20 via-transparent to-transparent blur-3xl" />
                
                {/* Product Image from Database */}
                {product?.hero_image_url ? (
                  <img 
                    src={product.hero_image_url} 
                    alt={product?.name || "Luminous Elixir"}
                    className="relative z-10 w-full h-full object-contain drop-shadow-2xl"
                    style={{ filter: 'drop-shadow(0 0 40px rgba(212,175,55,0.3))' }}
                  />
                ) : (
                  <div className="relative z-10 w-full h-full flex items-center justify-center">
                    <div className="text-[#D4AF37]/30 text-center">
                      <div className="text-6xl mb-4">✦</div>
                      <p className="text-sm tracking-widest">PRODUCT IMAGE</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
            
            {/* Right: Product Info */}
            <div className="order-1 lg:order-2 text-center lg:text-left">
              <p className="oroe-heading-section mb-4"
                 style={{
                   opacity: Math.min(1, Math.max(0, (scrollY - 400) / 300)),
                   transform: `translateY(${Math.max(0, 30 - (scrollY - 400) / 10)}px)`
                 }}>
                {t.elixirTitle}
              </p>
              <h2 className="oroe-heading-elegant oroe-gold-text mb-8"
                  style={{
                    opacity: Math.min(1, Math.max(0, (scrollY - 450) / 300)),
                    transform: `translateY(${Math.max(0, 30 - (scrollY - 450) / 10)}px)`
                  }}>
                {t.elixirSubtitle}
              </h2>
              
              {/* The Stats - Minimalist Grid */}
              <div className="grid grid-cols-3 gap-6 mb-12"
                   style={{
                     opacity: Math.min(1, Math.max(0, (scrollY - 500) / 300)),
                     transform: `translateY(${Math.max(0, 30 - (scrollY - 500) / 10)}px)`
                   }}>
                <div className="text-center p-4 border border-[#D4AF37]/20 bg-[#D4AF37]/5">
                  <p className="text-2xl md:text-3xl font-display oroe-gold-text mb-1">2.0%</p>
                  <p className="text-xs tracking-widest text-[#FDF8F0]/50">PDRN</p>
                </div>
                <div className="text-center p-4 border border-[#D4AF37]/20 bg-[#D4AF37]/5">
                  <p className="text-2xl md:text-3xl font-display oroe-gold-text mb-1">10%</p>
                  <p className="text-xs tracking-widest text-[#FDF8F0]/50">ARGIRELINE®</p>
                </div>
                <div className="text-center p-4 border border-[#D4AF37]/20 bg-[#D4AF37]/5">
                  <p className="text-2xl md:text-3xl font-display oroe-gold-text mb-1">24K</p>
                  <p className="text-xs tracking-widest text-[#FDF8F0]/50">GOLD</p>
                </div>
              </div>
              
              {/* Product Description */}
              <p className="oroe-body-elegant mb-8 max-w-lg mx-auto lg:mx-0"
                 style={{
                   opacity: Math.min(1, Math.max(0, (scrollY - 550) / 300)),
                   transform: `translateY(${Math.max(0, 30 - (scrollY - 550) / 10)}px)`
                 }}>
                {product?.descriptions?.[language] || product?.descriptions?.en || 
                 "A revolutionary fusion of cellular science and luxury. Each drop delivers targeted rejuvenation, targeting the appearance of fine lines while enveloping skin in liquid gold."}
              </p>
              
              {/* Price & CTA */}
              <div style={{
                     opacity: Math.min(1, Math.max(0, (scrollY - 600) / 300)),
                     transform: `translateY(${Math.max(0, 30 - (scrollY - 600) / 10)}px)`
                   }}>
                <p className="text-sm tracking-widest text-[#FDF8F0]/50 mb-2">ALLOCATION PRICE</p>
                <p className="text-4xl font-display oroe-gold-text tracking-wide mb-8">
                  {displayPrice} <span className="text-xl">{currency}</span>
                </p>
                <button 
                  onClick={() => setShowWaitlist(true)}
                  className="oroe-btn-primary"
                  data-testid="elixir-apply-btn"
                >
                  {t.joinWaitlist}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* === UNISEX PROOF - Gallery Section === */}
      {(product?.image_urls?.length > 0) && (
        <section className="py-24 bg-[#0A0A0A] border-t border-[#D4AF37]/10">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-16">
              <p className="oroe-heading-section mb-4">
                {language === 'fr' ? 'Pour Tous' : language === 'ar' ? 'للجميع' : 'For Everyone'}
              </p>
              <h3 className="oroe-heading-elegant oroe-gold-text">
                {language === 'fr' ? 'L\'Élégance Transcende' : language === 'ar' ? 'الأناقة تتجاوز' : 'Elegance Transcends'}
              </h3>
            </div>
            
            {/* Image Gallery - Unisex Proof */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {product.image_urls.slice(0, 4).map((url, idx) => (
                <div 
                  key={idx}
                  className="aspect-square overflow-hidden group"
                  style={{
                    opacity: Math.min(1, Math.max(0, (scrollY - 800 - idx * 50) / 300)),
                    transform: `translateY(${Math.max(0, 20 - (scrollY - 800 - idx * 50) / 15)}px)`
                  }}
                >
                  <img 
                    src={url} 
                    alt={`${product.name} - ${idx + 1}`}
                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                  />
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* === THE MAISON SECTION === */}
      <section id="maison" className="oroe-section oroe-section-rich">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            {/* Left: Visual - Logo in Gold Frame */}
            <div className="relative">
              <div 
                className="aspect-[3/4] rounded-sm oroe-gold-border overflow-hidden flex items-center justify-center"
                style={{ backgroundColor: '#0A0A0A' }}
              >
                <img 
                  src="https://customer-assets.emergentagent.com/job_vipbrandportal/artifacts/i4jfjhja_Screenshot_20260122_183709_Gallery.jpg" 
                  alt="OROÉ - Maison de la Lumière Dorée" 
                  className="w-3/4 h-auto object-contain"
                  style={{ filter: 'drop-shadow(0 0 30px rgba(212,175,55,0.3))' }}
                  data-testid="maison-logo"
                />
              </div>
            </div>

            {/* Right: Content */}
            <div>
              <p className="oroe-heading-section mb-4">{t.maisonTitle}</p>
              <h2 className="oroe-heading-display text-3xl md:text-4xl mb-6 text-[#FDF8F0]">
                {t.maisonSubtitle}
              </h2>
              <div className="oroe-divider mb-8" style={{ margin: '0 0 2rem 0' }} />
              
              <div className="space-y-6 oroe-body-elegant">
                <p>
                  {language === 'en' && "Born from the convergence of Italian artisanal heritage and cutting-edge biotechnology, OROÉ represents a new paradigm in cellular luxury."}
                  {language === 'fr' && "Née de la convergence du patrimoine artisanal italien et de la biotechnologie de pointe, OROÉ représente un nouveau paradigme du luxe cellulaire."}
                  {language === 'ar' && "نشأت من التقاء التراث الحرفي الإيطالي والتكنولوجيا الحيوية المتطورة، تمثل OROÉ نموذجًا جديدًا في الفخامة الخلوية."}
                </p>
                <p>
                  {language === 'en' && "Each formulation is a testament to our unwavering commitment: to harness the regenerative power of PDRN, elevated by 24-karat gold, creating an elixir worthy of the most discerning."}
                  {language === 'fr' && "Chaque formulation témoigne de notre engagement indéfectible : exploiter le pouvoir régénérateur du PDRN, sublimé par l'or 24 carats, créant un élixir digne des plus exigeants."}
                  {language === 'ar' && "كل تركيبة هي شهادة على التزامنا الراسخ: تسخير القوة التجديدية لـ PDRN، المعزز بالذهب عيار 24 قيراطًا، لإنشاء إكسير يستحق الأكثر تميزًا."}
                </p>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-8 mt-12 pt-8 border-t border-[#D4AF37]/20">
                <div className="text-center">
                  <p className="text-3xl font-display oroe-gold-text">2%</p>
                  <p className="text-xs tracking-wider text-[#FDF8F0]/50 mt-1">PDRN</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-display oroe-gold-text">24K</p>
                  <p className="text-xs tracking-wider text-[#FDF8F0]/50 mt-1">GOLD</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-display oroe-gold-text">500</p>
                  <p className="text-xs tracking-wider text-[#FDF8F0]/50 mt-1">LIMITED</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Crypto payment moved to application flow */}

      {/* === GOLDEN BIOTECHNOLOGY - Full Width Grid === */}
      <section className="oroe-section oroe-section-rich">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="oroe-heading-section mb-4">THE FORMULA</p>
            <h2 className="oroe-heading-display text-3xl md:text-4xl text-[#FDF8F0]">
              {language === 'en' ? 'Golden Biotechnology' : language === 'fr' ? 'Biotechnologie Dorée' : 'التكنولوجيا الحيوية الذهبية'}
            </h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-8">
            {[
              { name: "PDRN 2%", desc: "Polydeoxyribonucleotide for deep cellular regeneration", icon: "🧬" },
              { name: "Argireline® 10%", desc: "Clinical-grade peptide for expression line reduction", icon: "✨" },
              { name: "Tranexamic 5%", desc: "Advanced brightening complex for luminous skin", icon: "💎" },
              { name: "24K Gold Mica", desc: "Cosmetic gold particles for instant radiance", icon: "👑" }
            ].map((ingredient, idx) => (
              <div key={idx} className="text-center p-4 md:p-6 bg-[#0A0A0A]/50 border border-[#D4AF37]/20 rounded-sm hover:border-[#D4AF37]/50 transition-all">
                <div className="text-3xl md:text-4xl mb-3 md:mb-4">{ingredient.icon}</div>
                <h3 className="text-sm md:text-lg font-display oroe-gold-text mb-1 md:mb-2">{ingredient.name}</h3>
                <p className="text-xs md:text-sm text-[#FDF8F0]/60 hidden md:block">{ingredient.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* === RICH FOOTER === */}
      <footer className="oroe-section-dark border-t border-[#D4AF37]/20">
        <div className="max-w-6xl mx-auto px-6">
          {/* Main Footer Content */}
          <div className="grid md:grid-cols-4 gap-12 py-16">
            {/* Brand Column */}
            <div className="md:col-span-1">
              <img 
                src="https://customer-assets.emergentagent.com/job_premium-brand-suite/artifacts/f2n5jwgb_Screenshot_20260122_183709_Gallery.jpg" 
                alt="OROÉ" 
                className="h-16 w-auto mb-4"
              />
              <p className="text-sm text-[#FDF8F0]/60 leading-relaxed">
                Where cellular science meets golden luxury. Each formulation is a testament to our pursuit of timeless beauty.
              </p>
            </div>

            {/* The Maison Column */}
            <div>
              <h4 className="text-sm tracking-[0.2em] text-[#D4AF37] uppercase mb-6">The Maison</h4>
              <ul className="space-y-3">
                <li><a href="#maison" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">Our Story</a></li>
                <li><a href="#elixir" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">The Elixir</a></li>
                <li><a href="#" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">The Science</a></li>
                <li><a href="#" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">Sustainability</a></li>
              </ul>
            </div>

            {/* Client Services Column */}
            <div>
              <h4 className="text-sm tracking-[0.2em] text-[#D4AF37] uppercase mb-6">Client Services</h4>
              <ul className="space-y-3">
                <li><a href="#" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">Contact Concierge</a></li>
                <li><a href="#" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">Shipping & Returns</a></li>
                <li><a href="#" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="text-sm text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors">Terms of Service</a></li>
              </ul>
            </div>

            {/* Manufacturing Column */}
            <div>
              <h4 className="text-sm tracking-[0.2em] text-[#D4AF37] uppercase mb-6">Crafted With Care</h4>
              <p className="text-sm text-[#FDF8F0]/50 mb-4">
                Manufactured by<br />
                <span className="text-[#FDF8F0]/70 font-medium">Polaris Built Inc.</span><br />
                Ontario, Canada
              </p>
              <p className="text-xs text-[#FDF8F0]/40">
                Health Canada Compliant<br />
                NPN Registered Facility
              </p>
            </div>
          </div>

          {/* Certifications Bar */}
          <div className="border-t border-[#D4AF37]/10 py-8">
            <div className="flex flex-wrap justify-center items-center gap-8 md:gap-16">
              {/* Cruelty Free */}
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full border border-[#D4AF37]/30 flex items-center justify-center">
                  <svg className="w-6 h-6 text-[#D4AF37]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                  </svg>
                </div>
                <span className="text-[10px] tracking-wider text-[#FDF8F0]/50 uppercase">Cruelty-Free</span>
              </div>

              {/* Vegan */}
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full border border-[#D4AF37]/30 flex items-center justify-center">
                  <svg className="w-6 h-6 text-[#D4AF37]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                </div>
                <span className="text-[10px] tracking-wider text-[#FDF8F0]/50 uppercase">Vegan</span>
              </div>

              {/* FSC Paper */}
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full border border-[#D4AF37]/30 flex items-center justify-center">
                  <svg className="w-6 h-6 text-[#D4AF37]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                </div>
                <span className="text-[10px] tracking-wider text-[#FDF8F0]/50 uppercase">FSC Paper</span>
              </div>

              {/* 12M PAO */}
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full border border-[#D4AF37]/30 flex items-center justify-center">
                  <span className="text-xs font-bold text-[#D4AF37]">12M</span>
                </div>
                <span className="text-[10px] tracking-wider text-[#FDF8F0]/50 uppercase">Period After Opening</span>
              </div>

              {/* Made in Canada */}
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full border border-[#D4AF37]/30 flex items-center justify-center">
                  <span className="text-lg">🍁</span>
                </div>
                <span className="text-[10px] tracking-wider text-[#FDF8F0]/50 uppercase">Made in Canada</span>
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="border-t border-[#D4AF37]/10 py-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-xs text-[#FDF8F0]/30">
              © 2026 OROÉ · Maison de la Lumière Dorée · All rights reserved
            </p>
            <div className="flex items-center gap-6">
              <a href="#" className="text-[#FDF8F0]/30 hover:text-[#D4AF37] transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
              </a>
              <a href="#" className="text-[#FDF8F0]/30 hover:text-[#D4AF37] transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z"/></svg>
              </a>
            </div>
          </div>
        </div>
      </footer>

      {/* === WAITLIST MODAL === */}
      {showWaitlist && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-lg bg-[#0A0A0A] border border-[#D4AF37]/30 rounded-sm p-8 max-h-[90vh] overflow-y-auto">
            {/* Close Button */}
            <button 
              onClick={() => setShowWaitlist(false)}
              className="absolute top-4 right-4 text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {!submitted ? (
              <>
                {/* Header - Maison Application */}
                <div className="text-center mb-8">
                  <div className="inline-flex items-center gap-2 mb-4 px-4 py-2 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/30">
                    <span className="text-sm text-[#D4AF37] tracking-wider">VIP Application</span>
                  </div>
                  <h3 className="text-2xl font-display oroe-gold-text mb-2">Request Access to the Maison</h3>
                  <p className="text-sm text-[#FDF8F0]/50 max-w-md mx-auto">
                    Due to the high concentration of bio-active PDRN and our artisanal batch process, OROÉ is released in limited allocations.
                  </p>
                  
                  {/* Founder's Batch Countdown Timer */}
                  <CountdownTimer />
                  
                  <div className="oroe-divider mt-4" />
                  
                  {/* Progress Steps */}
                  <div className="flex items-center justify-center gap-4 mt-6">
                    {[1, 2, 3].map((step) => (
                      <div key={step} className="flex items-center gap-2">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 ${
                          formStep >= step 
                            ? 'bg-[#D4AF37] text-[#0A0A0A]' 
                            : 'border border-[#D4AF37]/30 text-[#D4AF37]/50'
                        }`}>
                          {formStep > step ? '✓' : step}
                        </div>
                        {step < 3 && (
                          <div className={`w-12 h-[2px] transition-all duration-300 ${
                            formStep > step ? 'bg-[#D4AF37]' : 'bg-[#D4AF37]/20'
                          }`} />
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-center gap-8 mt-2 text-[10px] tracking-wider text-[#D4AF37]/50">
                    <span className={formStep === 1 ? 'text-[#D4AF37]' : ''}>PROFILE</span>
                    <span className={formStep === 2 ? 'text-[#D4AF37]' : ''}>SKINCARE</span>
                    <span className={formStep === 3 ? 'text-[#D4AF37]' : ''}>PREFERENCES</span>
                  </div>
                </div>

                {/* Multi-Step Form */}
                <form onSubmit={handleSubmit} className="space-y-4">
                  
                  {/* STEP 1: Professional & Lifestyle Context */}
                  {formStep === 1 && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                      <p className="text-xs text-[#D4AF37]/70 uppercase tracking-wider mb-4">Professional & Lifestyle Context</p>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">{t.firstName} *</label>
                          <input
                            type="text"
                            value={formData.firstName}
                            onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                            className="oroe-input"
                            required
                          />
                        </div>
                        <div>
                          <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">{t.lastName}</label>
                          <input
                            type="text"
                            value={formData.lastName}
                            onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                            className="oroe-input"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">{t.email} *</label>
                        <input
                          type="email"
                          value={formData.email}
                          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                          className="oroe-input"
                          required
                        />
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">Primary Market / Residency *</label>
                        <select
                          value={formData.country}
                          onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                          className="oroe-input"
                          required
                        >
                          <option value="">Select Country</option>
                          <optgroup label="🇦🇪 Middle East">
                            <option value="UAE">🇦🇪 United Arab Emirates</option>
                            <option value="Saudi Arabia">🇸🇦 Saudi Arabia</option>
                            <option value="Qatar">🇶🇦 Qatar</option>
                            <option value="Kuwait">🇰🇼 Kuwait</option>
                            <option value="Bahrain">🇧🇭 Bahrain</option>
                            <option value="Oman">🇴🇲 Oman</option>
                          </optgroup>
                          <optgroup label="🇨🇦 North America">
                            <option value="Canada">🇨🇦 Canada</option>
                            <option value="USA">🇺🇸 United States</option>
                          </optgroup>
                          <optgroup label="🇪🇺 Europe">
                            <option value="UK">🇬🇧 United Kingdom</option>
                            <option value="France">🇫🇷 France</option>
                            <option value="Germany">🇩🇪 Germany</option>
                            <option value="Italy">🇮🇹 Italy</option>
                            <option value="Switzerland">🇨🇭 Switzerland</option>
                            <option value="Netherlands">🇳🇱 Netherlands</option>
                          </optgroup>
                          <optgroup label="🌏 Asia Pacific">
                            <option value="Japan">🇯🇵 Japan</option>
                            <option value="South Korea">🇰🇷 South Korea</option>
                            <option value="Singapore">🇸🇬 Singapore</option>
                            <option value="Hong Kong">🇭🇰 Hong Kong</option>
                            <option value="Australia">🇦🇺 Australia</option>
                          </optgroup>
                        </select>
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-2 block">Preferred Communication</label>
                        <div className="grid grid-cols-3 gap-2">
                          {[
                            { value: 'email', label: '📧 Email' },
                            { value: 'whatsapp', label: '💬 WhatsApp' },
                            { value: 'concierge', label: '👑 Private Concierge' }
                          ].map((opt) => (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setFormData({ ...formData, communicationPreference: opt.value })}
                              className={`p-3 rounded border text-xs transition-all duration-200 ${
                                formData.communicationPreference === opt.value
                                  ? 'border-[#D4AF37] bg-[#D4AF37]/10 text-[#D4AF37]'
                                  : 'border-[#D4AF37]/20 text-[#FDF8F0]/50 hover:border-[#D4AF37]/40'
                              }`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* STEP 2: Skincare Intelligence */}
                  {formStep === 2 && (
                    <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                      <p className="text-xs text-[#D4AF37]/70 uppercase tracking-wider mb-4">Skincare Intelligence</p>
                      
                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-2 block">
                          What is your current experience with clinical biotech (PDRN, Exosomes, or Peptides)?
                        </label>
                        <div className="space-y-2">
                          {[
                            { value: 'first-time', label: 'First-time user', desc: 'New to clinical skincare' },
                            { value: 'experienced', label: 'Experienced', desc: 'Familiar with advanced treatments' },
                            { value: 'professional', label: 'Professional Aesthetician', desc: 'Industry professional' }
                          ].map((opt) => (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setFormData({ ...formData, clinicalExperience: opt.value })}
                              className={`w-full p-4 rounded border text-left transition-all duration-200 ${
                                formData.clinicalExperience === opt.value
                                  ? 'border-[#D4AF37] bg-[#D4AF37]/10'
                                  : 'border-[#D4AF37]/20 hover:border-[#D4AF37]/40'
                              }`}
                            >
                              <span className={`text-sm ${formData.clinicalExperience === opt.value ? 'text-[#D4AF37]' : 'text-[#FDF8F0]'}`}>
                                {opt.label}
                              </span>
                              <p className="text-xs text-[#FDF8F0]/40 mt-1">{opt.desc}</p>
                            </button>
                          ))}
                        </div>
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-2 block">
                          How did you discover OROÉ?
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { value: 'private-referral', label: '🤝 Private Referral' },
                            { value: 'social-media', label: '📱 Social Media' },
                            { value: 'clinical-partner', label: '🏥 Clinical Partner' },
                            { value: 'reroots', label: '🌱 ReRoots Heritage' }
                          ].map((opt) => (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setFormData({ ...formData, discoverySource: opt.value })}
                              className={`p-3 rounded border text-xs transition-all duration-200 ${
                                formData.discoverySource === opt.value
                                  ? 'border-[#D4AF37] bg-[#D4AF37]/10 text-[#D4AF37]'
                                  : 'border-[#D4AF37]/20 text-[#FDF8F0]/50 hover:border-[#D4AF37]/40'
                              }`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">Primary Skin Concern</label>
                        <select
                          value={formData.skinConcern}
                          onChange={(e) => setFormData({ ...formData, skinConcern: e.target.value })}
                          className="oroe-input"
                        >
                          <option value="">Select Concern</option>
                          <option value="aging">Fine Lines & Wrinkles</option>
                          <option value="pigmentation">Dark Spots & Pigmentation</option>
                          <option value="dullness">Dull & Tired Skin</option>
                          <option value="texture">Uneven Texture</option>
                          <option value="all">Complete Transformation</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* STEP 3: Allocation Preferences */}
                  {formStep === 3 && (
                    <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                      <p className="text-xs text-[#D4AF37]/70 uppercase tracking-wider mb-4">Allocation Preferences</p>
                      
                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-2 block">
                          How many units of the Luminous Elixir would you like to reserve for your first year?
                        </label>
                        <div className="space-y-2">
                          {[
                            { value: '1', label: '1 Unit', desc: 'Individual', icon: '💎' },
                            { value: '3', label: '3 Units', desc: 'Full Cycle (Recommended)', icon: '✨', highlight: true },
                            { value: '6+', label: '6+ Units', desc: 'Professional / Collector', icon: '👑' }
                          ].map((opt) => (
                            <button
                              key={opt.value}
                              type="button"
                              onClick={() => setFormData({ ...formData, unitsRequested: opt.value })}
                              className={`w-full p-4 rounded border text-left transition-all duration-200 ${
                                formData.unitsRequested === opt.value
                                  ? 'border-[#D4AF37] bg-[#D4AF37]/10'
                                  : opt.highlight 
                                    ? 'border-[#D4AF37]/40 bg-[#D4AF37]/5' 
                                    : 'border-[#D4AF37]/20 hover:border-[#D4AF37]/40'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div>
                                  <span className={`text-sm ${formData.unitsRequested === opt.value ? 'text-[#D4AF37]' : 'text-[#FDF8F0]'}`}>
                                    {opt.icon} {opt.label}
                                  </span>
                                  <p className="text-xs text-[#FDF8F0]/40 mt-1">{opt.desc}</p>
                                </div>
                                {opt.highlight && (
                                  <span className="text-[8px] px-2 py-1 rounded bg-[#D4AF37]/20 text-[#D4AF37]">BEST VALUE</span>
                                )}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-2 block">
                          Preferred Payment Method
                        </label>
                        <div className="grid grid-cols-2 gap-3">
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, paymentPreference: 'traditional' })}
                            className={`p-4 rounded border text-center transition-all duration-200 ${
                              formData.paymentPreference === 'traditional'
                                ? 'border-[#D4AF37] bg-[#D4AF37]/10'
                                : 'border-[#D4AF37]/20 hover:border-[#D4AF37]/40'
                            }`}
                          >
                            <span className="text-2xl block mb-2">💳</span>
                            <span className={`text-sm ${formData.paymentPreference === 'traditional' ? 'text-[#D4AF37]' : 'text-[#FDF8F0]'}`}>
                              Traditional
                            </span>
                            <p className="text-[10px] text-[#FDF8F0]/40 mt-1">Visa / Mastercard</p>
                          </button>
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, paymentPreference: 'crypto' })}
                            className={`p-4 rounded border text-center transition-all duration-200 ${
                              formData.paymentPreference === 'crypto'
                                ? 'border-[#D4AF37] bg-[#D4AF37]/10'
                                : 'border-[#D4AF37]/20 hover:border-[#D4AF37]/40'
                            }`}
                          >
                            <span className="text-2xl block mb-2">₿</span>
                            <span className={`text-sm ${formData.paymentPreference === 'crypto' ? 'text-[#D4AF37]' : 'text-[#FDF8F0]'}`}>
                              Digital Asset
                            </span>
                            <p className="text-[10px] text-[#FDF8F0]/40 mt-1">BTC / ETH / USDC</p>
                          </button>
                        </div>
                      </div>

                      {/* Referral Source - Inner Circle Tracking */}
                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">
                          {t.referredBy || "Who referred you to OROÉ?"}
                        </label>
                        <input
                          type="text"
                          value={formData.referredBy}
                          onChange={(e) => setFormData({ ...formData, referredBy: e.target.value })}
                          className="oroe-input"
                          placeholder={t.referredByPlaceholder || "Name of your referrer (optional)"}
                          data-testid="referral-input"
                        />
                        <p className="text-xs text-[#D4AF37]/40 mt-1">
                          Our inner circle grows through trusted recommendations
                        </p>
                      </div>

                      <div>
                        <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">
                          Additional Notes (Optional)
                        </label>
                        <textarea
                          value={formData.whyJoin}
                          onChange={(e) => setFormData({ ...formData, whyJoin: e.target.value })}
                          className="oroe-input min-h-[80px] resize-none"
                          placeholder="Share your skincare journey or any special requests..."
                        />
                      </div>
                    </div>
                  )}

                  {/* Navigation Buttons */}
                  <div className="flex items-center gap-3 pt-4">
                    {formStep > 1 && (
                      <button
                        type="button"
                        onClick={prevStep}
                        className="flex-1 py-3 px-6 rounded border border-[#D4AF37]/30 text-[#D4AF37] text-sm tracking-wider
                                   hover:bg-[#D4AF37]/5 transition-all duration-200"
                      >
                        ← Back
                      </button>
                    )}
                    {formStep < totalFormSteps ? (
                      <button
                        type="button"
                        onClick={nextStep}
                        className="flex-1 oroe-btn-primary"
                      >
                        Continue →
                      </button>
                    ) : (
                      <button
                        type="submit"
                        disabled={loading}
                        className="flex-1 oroe-btn-primary"
                        data-testid="apply-allocation-btn"
                      >
                        {loading ? "Processing..." : (t.submitApplication || "Apply for Allocation")}
                      </button>
                    )}
                  </div>
                </form>

                <p className="text-xs text-center text-[#FDF8F0]/30 mt-6">
                  By applying, you agree to receive communications from the Maison.
                </p>
              </>
            ) : (
              /* Success State - L'Attesa è Finita */
              <div className="text-center py-8 animate-in fade-in zoom-in-95 duration-500">
                {/* Gold signature animation */}
                <div className="relative w-24 h-24 mx-auto mb-6">
                  <div className="absolute inset-0 rounded-full border-2 border-[#D4AF37] animate-pulse" />
                  <div className="absolute inset-2 rounded-full bg-gradient-to-br from-[#D4AF37]/20 to-transparent flex items-center justify-center">
                    <svg className="w-10 h-10 text-[#D4AF37]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
                
                <h3 className="text-2xl font-display oroe-gold-text mb-2 italic">L'Attesa è Finita.</h3>
                <p className="text-sm text-[#FDF8F0]/70 mb-6">(The Wait is Nearly Over)</p>
                
                <div className="oroe-divider mb-6" />
                
                {/* Status Tracker */}
                <div className="bg-[#D4AF37]/5 border border-[#D4AF37]/20 rounded-lg p-4 mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-[#D4AF37]/70 uppercase tracking-wider">Status</span>
                    <span className="text-xs px-2 py-1 rounded bg-[#D4AF37]/20 text-[#D4AF37]">In Review</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#D4AF37]/70 uppercase tracking-wider">Position</span>
                    <span className="text-lg font-display text-[#D4AF37]">#{formData.waitlistPosition || '—'}</span>
                  </div>
                </div>
                
                <p className="text-sm text-[#FDF8F0]/50 leading-relaxed mb-8 max-w-sm mx-auto">
                  Your profile has been submitted to the Maison OROÉ register. Our clinical team is reviewing Batch 01 allocations. 
                  A digital invitation will be sent once a bottle has been reserved in your name.
                </p>
                
                <a
                  href="/oroe/science"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded border border-[#D4AF37]/30 text-[#D4AF37] text-sm tracking-wider
                             hover:bg-[#D4AF37]/5 transition-all duration-200"
                >
                  Explore the Science →
                </a>
                
                <div className="oroe-divider mt-8 mb-4" />
                <p className="text-[10px] text-[#FDF8F0]/30 italic">
                  "Our Luminous Elixir requires a 21-day stabilization period for its bio-active PDRN"
                </p>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* === CRYPTO PAYMENT MODAL === */}
      {showCryptoPayment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-sm">
          <div 
            className="relative w-full max-w-md bg-[#0A0A0A] border border-[#D4AF37]/30 rounded-sm overflow-hidden"
            dir={isRTL ? 'rtl' : 'ltr'}
          >
            {/* Header with gradient */}
            <div className="bg-gradient-to-r from-[#F7931A]/10 via-[#627EEA]/10 to-[#2775CA]/10 p-6 border-b border-[#D4AF37]/20">
              <button 
                onClick={() => setShowCryptoPayment(false)}
                className="absolute top-4 right-4 text-[#FDF8F0]/50 hover:text-[#D4AF37] transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              
              <div className="text-center">
                <p className="text-xs tracking-[0.3em] text-[#D4AF37]/70 mb-2">
                  {language === 'en' ? 'CRYPTO PAYMENT' : language === 'fr' ? 'PAIEMENT CRYPTO' : 'الدفع بالعملات المشفرة'}
                </p>
                <h3 className="text-xl font-display oroe-gold-text">
                  {language === 'en' ? 'Pay with Cryptocurrency' : language === 'fr' ? 'Payer en Cryptomonnaie' : 'الدفع بالعملة المشفرة'}
                </h3>
              </div>
            </div>
            
            <div className="p-6 space-y-6">
              {/* Product Summary */}
              <div className="flex items-center gap-4 p-4 bg-[#D4AF37]/5 border border-[#D4AF37]/20 rounded-sm">
                <div className="w-16 h-16 bg-gradient-to-br from-[#D4AF37]/20 to-[#B8860B]/20 rounded-sm flex items-center justify-center">
                  <span className="text-2xl">✨</span>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-[#FDF8F0]/70">OROÉ Luminous Elixir</p>
                  <p className="text-2xl font-display oroe-gold-text">{displayPrice} {currency}</p>
                </div>
              </div>
              
              {/* Crypto Selection */}
              <div>
                <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-3 block">
                  {language === 'en' ? 'SELECT CRYPTOCURRENCY' : language === 'fr' ? 'SÉLECTIONNER LA CRYPTOMONNAIE' : 'اختر العملة المشفرة'}
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {cryptoOptions.map((crypto) => (
                    <button
                      key={crypto.code}
                      onClick={() => setSelectedCrypto(crypto.code)}
                      className={`p-4 rounded-sm border transition-all duration-300 text-center
                        ${selectedCrypto === crypto.code 
                          ? 'border-[#D4AF37] bg-[#D4AF37]/10' 
                          : 'border-[#D4AF37]/20 hover:border-[#D4AF37]/50 bg-transparent'
                        }`}
                      data-testid={`crypto-option-${crypto.code}`}
                    >
                      <span className="text-2xl block mb-1" style={{ color: crypto.color }}>{crypto.icon}</span>
                      <span className="text-xs text-[#FDF8F0]/70">{crypto.code}</span>
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Customer Info */}
              <div className="space-y-4">
                <div>
                  <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">
                    {language === 'en' ? 'FULL NAME' : language === 'fr' ? 'NOM COMPLET' : 'الاسم الكامل'} *
                  </label>
                  <input
                    type="text"
                    value={cryptoFormData.name}
                    onChange={(e) => setCryptoFormData({ ...cryptoFormData, name: e.target.value })}
                    className="oroe-input"
                    placeholder={language === 'en' ? 'Enter your name' : language === 'fr' ? 'Entrez votre nom' : 'أدخل اسمك'}
                    required
                    data-testid="crypto-name-input"
                  />
                </div>
                <div>
                  <label className="text-xs tracking-wider text-[#D4AF37]/70 mb-1 block">
                    {language === 'en' ? 'EMAIL ADDRESS' : language === 'fr' ? 'ADRESSE EMAIL' : 'البريد الإلكتروني'} *
                  </label>
                  <input
                    type="email"
                    value={cryptoFormData.email}
                    onChange={(e) => setCryptoFormData({ ...cryptoFormData, email: e.target.value })}
                    className="oroe-input"
                    placeholder={language === 'en' ? 'your@email.com' : language === 'fr' ? 'votre@email.com' : 'بريدك@الإلكتروني.com'}
                    required
                    data-testid="crypto-email-input"
                  />
                </div>
              </div>
              
              {/* Pay Button */}
              <button
                onClick={handleCryptoPayment}
                disabled={cryptoLoading || !cryptoFormData.name || !cryptoFormData.email}
                className={`w-full py-4 rounded-sm font-medium tracking-wider transition-all duration-300
                  ${cryptoLoading || !cryptoFormData.name || !cryptoFormData.email
                    ? 'bg-[#D4AF37]/20 text-[#D4AF37]/50 cursor-not-allowed'
                    : 'bg-gradient-to-r from-[#F7931A] via-[#627EEA] to-[#2775CA] text-white hover:opacity-90'
                  }`}
                data-testid="crypto-submit-btn"
              >
                {cryptoLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    {language === 'en' ? 'Processing...' : language === 'fr' ? 'Traitement...' : 'جاري المعالجة...'}
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <span>{cryptoOptions.find(c => c.code === selectedCrypto)?.icon}</span>
                    {language === 'en' ? `Pay with ${selectedCrypto}` : language === 'fr' ? `Payer avec ${selectedCrypto}` : `الدفع بـ ${selectedCrypto}`}
                  </span>
                )}
              </button>
              
              {/* Security Note */}
              <p className="text-[10px] text-[#FDF8F0]/40 text-center">
                {language === 'en' 
                  ? 'Secure payment powered by Coinbase Commerce. Your transaction is protected by blockchain technology.'
                  : language === 'fr'
                  ? 'Paiement sécurisé par Coinbase Commerce. Votre transaction est protégée par la technologie blockchain.'
                  : 'دفع آمن عبر Coinbase Commerce. معاملتك محمية بتقنية البلوكشين.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OroeLandingPage;
