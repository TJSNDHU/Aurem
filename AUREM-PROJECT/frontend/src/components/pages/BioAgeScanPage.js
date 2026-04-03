import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import axios from 'axios';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Dna, Thermometer, Shield, Zap, Activity, 
  ChevronRight, Lock, Mail, Phone, Globe,
  Copy, Check, Users, Gift, Sparkles,
  Facebook, Twitter, MessageCircle, Send,
  CheckCircle, Clock, Target, DollarSign,
  TrendingUp, UserPlus, ShoppingBag, Heart,
  Camera, Upload, Download, Share2, Image as ImageIcon,
  Loader2, Scan, AlertCircle, ChevronDown, Crown, ArrowRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import QRCode from 'qrcode';

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

const API = getBackendUrl();

// Quiz URL for QR code
const QUIZ_URL = 'https://reroots.ca/Bio-Age-Repair-Scan';

// Currency configuration with exchange rates (base: CAD)
const CURRENCY_CONFIG = {
  CAD: { symbol: 'C$', code: 'CAD', rate: 1, phoneCode: '+1', flag: '🇨🇦', name: 'Canada' },
  USD: { symbol: '$', code: 'USD', rate: 0.74, phoneCode: '+1', flag: '🇺🇸', name: 'USA' },
  GBP: { symbol: '£', code: 'GBP', rate: 0.58, phoneCode: '+44', flag: '🇬🇧', name: 'UK' },
  EUR: { symbol: '€', code: 'EUR', rate: 0.68, phoneCode: '+33', flag: '🇪🇺', name: 'Europe' },
  INR: { symbol: '₹', code: 'INR', rate: 61.5, phoneCode: '+91', flag: '🇮🇳', name: 'India' },
  AUD: { symbol: 'A$', code: 'AUD', rate: 1.12, phoneCode: '+61', flag: '🇦🇺', name: 'Australia' },
  AED: { symbol: 'د.إ', code: 'AED', rate: 2.72, phoneCode: '+971', flag: '🇦🇪', name: 'UAE' },
  PKR: { symbol: '₨', code: 'PKR', rate: 206, phoneCode: '+92', flag: '🇵🇰', name: 'Pakistan' },
  PHP: { symbol: '₱', code: 'PHP', rate: 41.2, phoneCode: '+63', flag: '🇵🇭', name: 'Philippines' },
  MXN: { symbol: 'MX$', code: 'MXN', rate: 12.6, phoneCode: '+52', flag: '🇲🇽', name: 'Mexico' },
  SGD: { symbol: 'S$', code: 'SGD', rate: 0.99, phoneCode: '+65', flag: '🇸🇬', name: 'Singapore' },
  NZD: { symbol: 'NZ$', code: 'NZD', rate: 1.21, phoneCode: '+64', flag: '🇳🇿', name: 'New Zealand' },
};

// Map browser locale/timezone to currency
const detectUserCurrency = () => {
  try {
    // Try to detect from timezone
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const locale = navigator.language || 'en-CA';
    
    // Timezone-based detection
    if (timezone.includes('America/Toronto') || timezone.includes('America/Vancouver') || timezone.includes('Canada')) return 'CAD';
    if (timezone.includes('America/New_York') || timezone.includes('America/Los_Angeles') || timezone.includes('America/Chicago')) return 'USD';
    if (timezone.includes('Europe/London')) return 'GBP';
    if (timezone.includes('Europe/Paris') || timezone.includes('Europe/Berlin') || timezone.includes('Europe/Rome')) return 'EUR';
    if (timezone.includes('Asia/Kolkata') || timezone.includes('Asia/Mumbai')) return 'INR';
    if (timezone.includes('Australia')) return 'AUD';
    if (timezone.includes('Asia/Dubai')) return 'AED';
    if (timezone.includes('Asia/Karachi')) return 'PKR';
    if (timezone.includes('Asia/Manila')) return 'PHP';
    if (timezone.includes('America/Mexico')) return 'MXN';
    if (timezone.includes('Asia/Singapore')) return 'SGD';
    if (timezone.includes('Pacific/Auckland')) return 'NZD';
    
    // Fallback to locale
    if (locale.startsWith('en-CA')) return 'CAD';
    if (locale.startsWith('en-US')) return 'USD';
    if (locale.startsWith('en-GB')) return 'GBP';
    if (locale.startsWith('en-AU')) return 'AUD';
    if (locale.startsWith('en-IN') || locale.startsWith('hi')) return 'INR';
    if (locale.startsWith('fr') || locale.startsWith('de') || locale.startsWith('es-ES') || locale.startsWith('it')) return 'EUR';
    if (locale.startsWith('ar-AE')) return 'AED';
    if (locale.startsWith('ur') || locale.startsWith('en-PK')) return 'PKR';
    if (locale.startsWith('fil') || locale.startsWith('tl')) return 'PHP';
    if (locale.startsWith('es-MX')) return 'MXN';
    
    return 'CAD'; // Default to Canadian
  } catch (e) {
    return 'CAD';
  }
};

// Format currency based on detected region
const formatCurrency = (amountInCAD, currencyCode, showCode = false) => {
  const config = CURRENCY_CONFIG[currencyCode] || CURRENCY_CONFIG.CAD;
  const convertedAmount = Math.round(amountInCAD * config.rate);
  
  if (showCode) {
    return `${config.symbol}${convertedAmount} ${config.code}`;
  }
  return `${config.symbol}${convertedAmount}`;
};

// AI-generated futuristic background
const BG_IMAGE_URL = 'https://static.prod-images.emergentagent.com/jobs/152b37c3-2aad-48f3-9f9e-f8d67e2eff9a/images/189be5ba75af322d4abeb33563ff3ebb024306bfd7bc0fb7653b0ff862d93568.png';

// Soulful compliments to show after selfie
const SOUL_COMPLIMENTS = [
  "Your eyes don't just have a color; they have a depth that makes it feel like I'm looking straight into your soul.",
  "There's a kindness in your eyes that tells me everything I need to know about your heart.",
  "I love the way your eyes light up when you talk about what you love; it's like seeing your soul catch fire.",
  "Your smile is so genuine—it's clear it comes from a very deep, beautiful place inside you.",
  "You have a 'whole-face' smile. It's like your heart is so full it just overflows onto your face.",
  "When you laugh, your face radiates a kind of warmth that can only come from a good soul.",
  "You have a rare kind of beauty that feels like it's shining from the inside out.",
  "There is such a peacefulness in your expression; it makes me think your heart is a very beautiful place to be.",
  "Your face is captivating, but it's the spirit behind it that I can't stop thinking about.",
  "Your face is just the beautiful cover to an even better story.",
  "You are proof that a beautiful soul creates a beautiful reflection.",
  "Your features are lovely, but your light is what's truly stunning.",
  "There is a certain 'life' in your face that most people don't have. It's like your spirit is too big to be contained, so it just glows through your skin.",
  "You have a very 'honest' face. I feel like I can see your heart's intentions just by looking at you.",
  "Looking at you feels like sitting in the sun. It's not just your features; it's the warmth of your soul hitting me.",
  "I love the tiny crinkles by your eyes when you laugh; they look like a map of every time your heart has been happy.",
  "Your face is so expressive—it's like your soul is constantly communicating with the world without you saying a word.",
  "There is a softness in your features that makes me think your heart must be incredibly gentle.",
  "Some people are just beautiful to look at, but you are beautiful to behold. Your face is a reflection of a very intentional, well-loved soul.",
  "If a person's face is a garden, yours is clearly tended to by a very kind heart.",
  "I've seen many faces, but yours is the only one that feels like 'home.' It's like my soul recognized yours the moment I saw you."
];

// Timer duration per question (seconds)
const QUESTION_TIMER = 20;

// Quiz Questions - Universal, survey-style language
const QUIZ_QUESTIONS = [
  {
    id: 'age_group',
    icon: Users,
    category: 'Age Profile',
    question: 'First, let\'s personalize your experience - which age group best describes you?',
    subtext: 'This helps us recommend the perfect product line for your skin\'s needs.',
    scienceHook: 'Different ages have different cellular needs. We\'ve developed specialized formulas for every life stage.',
    options: [
      { value: 'teen', label: '8-17 years (Teen)', bioAgeImpact: 0 },
      { value: 'young_adult', label: '18-34 years (Young Adult)', bioAgeImpact: 0 },
      { value: 'mature', label: '35+ years (Mature)', bioAgeImpact: 0 }
    ]
  },
  {
    id: 'primary_concern',
    icon: Target,
    category: 'Primary Concern',
    question: 'What\'s your #1 skin concern right now?',
    subtext: '',
    scienceHook: 'Identifying your primary concern helps us target the most effective active ingredients.',
    options: [
      { value: 'acne', label: 'Acne, breakouts, or congestion', bioAgeImpact: 2 },
      { value: 'aging', label: 'Fine lines, wrinkles, or loss of firmness', bioAgeImpact: 4 },
      { value: 'dark_circles', label: 'Dark circles or under-eye concerns', bioAgeImpact: 3 },
      { value: 'dullness', label: 'Dullness or uneven skin tone', bioAgeImpact: 3 },
      { value: 'sensitivity', label: 'Redness or sensitivity', bioAgeImpact: 2 },
      { value: 'hydration', label: 'Dryness or dehydration', bioAgeImpact: 3 }
    ]
  },
  {
    id: 'eye_concern',
    icon: Target,
    category: 'Eye Area Assessment',
    question: 'How would you describe your under-eye area?',
    subtext: 'The eye contour is often the first area to show signs of aging and fatigue.',
    scienceHook: 'The skin around eyes is 10x thinner than the rest of your face, requiring specialized treatment.',
    options: [
      { value: 'none', label: 'No major concerns - looks healthy', bioAgeImpact: 0 },
      { value: 'mild', label: 'Slight puffiness or occasional dark circles', bioAgeImpact: 2 },
      { value: 'moderate', label: 'Persistent dark circles or fine lines', bioAgeImpact: 4 },
      { value: 'severe', label: 'Deep wrinkles, hollows, or severe discoloration', bioAgeImpact: 6 }
    ]
  },
  {
    id: 'climate',
    icon: Thermometer,
    category: 'Environmental Stress',
    question: 'We\'d love to know - in the last 24 hours, how many hours was your skin exposed to extreme temperatures?',
    subtext: '(heating, AC, cold weather, or humidity changes)',
    scienceHook: 'Extreme temperature shifts cause "thermal shock," which PDRN is scientifically proven to repair at a cellular level.',
    options: [
      { value: 0, label: '0-2 hours (Minimal)', bioAgeImpact: 0 },
      { value: 1, label: '2-4 hours (Moderate)', bioAgeImpact: 2 },
      { value: 2, label: '4-6 hours (High)', bioAgeImpact: 4 },
      { value: 3, label: '6+ hours (Extreme)', bioAgeImpact: 6 }
    ]
  },
  {
    id: 'repair',
    icon: Activity,
    category: 'Cellular Recovery',
    question: 'Could you tell us how quickly your skin typically recovers from visible irritation, redness, or a blemish?',
    subtext: '',
    scienceHook: 'Slower recovery indicates depleted cellular energy (ATP). PDRN acts as a bio-stimulator to accelerate your natural healing cycle.',
    options: [
      { value: 0, label: '1-2 days (Very Fast)', bioAgeImpact: 0 },
      { value: 1, label: '3-5 days (Normal)', bioAgeImpact: 3 },
      { value: 2, label: '1-2 weeks (Slow)', bioAgeImpact: 5 },
      { value: 3, label: '2+ weeks (Very Slow)', bioAgeImpact: 8 }
    ]
  },
  {
    id: 'barrier',
    icon: Shield,
    category: 'Barrier Function',
    question: 'Please share - by mid-afternoon, does your skin feel "tight," dehydrated, or dull even after your morning skincare?',
    subtext: '',
    scienceHook: 'This indicates a "compromised skin barrier" where moisture escapes. Our serum bio-actively reinforces this protective layer.',
    options: [
      { value: 0, label: 'Never - stays hydrated', bioAgeImpact: 0 },
      { value: 1, label: 'Sometimes', bioAgeImpact: 3 },
      { value: 2, label: 'Most days', bioAgeImpact: 5 },
      { value: 3, label: 'Always tight/dull', bioAgeImpact: 7 }
    ]
  },
  {
    id: 'dna',
    icon: Dna,
    category: 'DNA Protection',
    question: 'We\'re curious - are you currently using products that protect against UV-induced DNA damage?',
    subtext: '(or only treating existing lines)',
    scienceHook: 'Most skincare only treats the surface; PDRN works deeper to protect the DNA blueprint of your skin cells.',
    options: [
      { value: 0, label: 'Yes, DNA-protective actives', bioAgeImpact: 0 },
      { value: 1, label: 'SPF only', bioAgeImpact: 3 },
      { value: 2, label: 'Surface treatments only', bioAgeImpact: 5 },
      { value: 3, label: 'No specific protection', bioAgeImpact: 8 }
    ]
  },
  {
    id: 'receptivity',
    icon: Zap,
    category: 'Product Efficacy',
    question: 'One last question - does your skincare routine often stop working or "plateau" after a few weeks?',
    subtext: '',
    scienceHook: 'This suggests your skin cells are in a "dormant" state. Bio-active PDRN "re-wakes" these cells for renewed receptivity.',
    options: [
      { value: 0, label: 'Never - always effective', bioAgeImpact: 0 },
      { value: 1, label: 'Rarely plateaus', bioAgeImpact: 2 },
      { value: 2, label: 'Sometimes plateaus', bioAgeImpact: 4 },
      { value: 3, label: 'Frequently stops working', bioAgeImpact: 7 }
    ]
  }
];

// Brand recommendation configuration
const BRAND_RECOMMENDATIONS = {
  lavela: {
    name: 'LA VELA BIANCA',
    tagline: 'The Anmol Singh Collection',
    subtitle: 'Premium Teen Skincare',
    description: 'Pediatric-safe, pH-balanced formulas designed specifically for young, developing skin. Created with Anmol Singh (15) in mind.',
    heroProduct: 'ORO ROSA Serum',
    price: '$49 CAD',
    keyIngredient: 'Centella Asiatica',
    keyBenefit: 'Calms inflammation & promotes healing without harsh actives',
    route: '/lavela',
    color: 'from-[#0D4D4D] to-[#E8C4B8]',
    icon: '🌸'
  },
  reroots: {
    name: 'ReRoots',
    tagline: 'The Gurnaman Singh Collection',
    subtitle: 'Bio-Active Skincare',
    description: 'Clinical-grade formulas for young adults seeking visible results. Created with Gurnaman Singh (18) in mind.',
    heroProduct: 'AURA-GEN Serum',
    price: '$155 CAD',
    keyIngredient: 'Tranexamic Acid 5%',
    keyBenefit: 'Clinical brightening & melasma control with PDRN regeneration',
    route: '/products/prod-aura-gen',
    color: 'from-[#D4AF37] to-[#F8A5B8]',
    icon: '🧬'
  },
  reroots_eye: {
    name: 'ReRoots',
    tagline: 'The Eye Protocol',
    subtitle: 'Targeted Eye Treatment',
    description: 'Specialized eye concentration designed for dark circles, puffiness, and periorbital aging. PDRN + Caffeine + Peptides.',
    heroProduct: 'ROSE-GEN Eye Concentration',
    price: '$89 CAD',
    keyIngredient: 'PDRN + Caffeine Complex',
    keyBenefit: 'Targets dark circles, puffiness & crow\'s feet at the source',
    route: '/products/prod-rose-gen',
    color: 'from-[#F8A5B8] to-[#E8B4BC]',
    icon: '👁️',
    isPreOrder: true,
    preOrderDate: 'Ships March 2026'
  },
  oroe: {
    name: 'OROÉ',
    tagline: 'The Founders\' Collection',
    subtitle: 'Luxury Anti-Aging',
    description: 'Ultra-luxury cellular rejuvenation for discerning skin. Created by Tejinder Sandhu & Pawandeep Kaur.',
    heroProduct: 'OROÉ Black Label Serum',
    price: '$159 CAD',
    keyIngredient: 'EGF (Epidermal Growth Factor)',
    keyBenefit: 'Cellular resurrection & deep wrinkle repair',
    route: '/oroe',
    color: 'from-[#1A1A1A] to-[#D4AF37]',
    icon: '👑'
  }
};

// Determine recommended brand AND specific product based on age and concerns
const getBrandRecommendation = (answers) => {
  const ageGroup = answers.age_group;
  const primaryConcern = answers.primary_concern;
  const eyeConcern = answers.eye_concern;
  
  // Teen (8-17): Always LA VELA BIANCA
  if (ageGroup === 'teen') {
    return 'lavela';
  }
  
  // Dark circles as primary concern OR significant eye concerns: ROSE-GEN Eye
  if (primaryConcern === 'dark_circles') {
    return 'reroots_eye';
  }
  
  // Moderate to severe eye concerns combined with mature age: ROSE-GEN Eye
  if (eyeConcern === 'severe' || (eyeConcern === 'moderate' && ageGroup === 'mature')) {
    return 'reroots_eye';
  }
  
  // Mature (35+) with aging concerns: OROÉ
  if (ageGroup === 'mature' && primaryConcern === 'aging') {
    return 'oroe';
  }
  
  // Young adult (18-34) or mature with texture/dullness: ReRoots AURA-GEN
  return 'reroots';
};

// Get secondary product recommendation (for dual-product protocol)
const getSecondaryRecommendation = (answers, primaryBrandKey) => {
  const eyeConcern = answers.eye_concern;
  const ageGroup = answers.age_group;
  
  // If primary is AURA-GEN and user has eye concerns, recommend ROSE-GEN as add-on
  if (primaryBrandKey === 'reroots' && (eyeConcern === 'moderate' || eyeConcern === 'mild')) {
    return 'reroots_eye';
  }
  
  // If primary is ROSE-GEN (eye), recommend AURA-GEN for full face
  if (primaryBrandKey === 'reroots_eye') {
    return 'reroots';
  }
  
  // If primary is OROÉ and has eye concerns, recommend ROSE-GEN
  if (primaryBrandKey === 'oroe' && eyeConcern !== 'none') {
    return 'reroots_eye';
  }
  
  return null;
};

const BioAgeScanPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const referrerCode = searchParams.get('ref') || '';
  
  // Currency & Region state
  const [userCurrency, setUserCurrency] = useState('CAD');
  const [showCurrencyPicker, setShowCurrencyPicker] = useState(false);
  
  // Detect user's currency on mount
  useEffect(() => {
    const detected = detectUserCurrency();
    setUserCurrency(detected);
  }, []);
  
  // Get current currency config
  const currencyConfig = useMemo(() => CURRENCY_CONFIG[userCurrency] || CURRENCY_CONFIG.CAD, [userCurrency]);
  
  // Helper to format amounts in user's currency
  const formatAmount = useCallback((cadAmount, showCode = false) => {
    return formatCurrency(cadAmount, userCurrency, showCode);
  }, [userCurrency]);
  
  // Quiz state
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [phoneCountryCode, setPhoneCountryCode] = useState('+1');
  const [showCountryPicker, setShowCountryPicker] = useState(false);
  const [loading, setLoading] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [userReferralCode, setUserReferralCode] = useState('');
  const [referralStats, setReferralStats] = useState({ 
    started: 0, 
    completed: 0, 
    points: 0,
    earnings: 0 
  });
  
  // State to show referral section after photo
  const [showReferralAfterPhoto, setShowReferralAfterPhoto] = useState(false);
  
  // Redemption popup state
  const [showRedeemPopup, setShowRedeemPopup] = useState(false);
  const [hasSeenRedeemPopup, setHasSeenRedeemPopup] = useState(false);
  
  // Set phone country code based on detected currency
  useEffect(() => {
    const config = CURRENCY_CONFIG[userCurrency];
    if (config) {
      setPhoneCountryCode(config.phoneCode);
    }
  }, [userCurrency]);
  
  // Timer state
  const [timeLeft, setTimeLeft] = useState(QUESTION_TIMER);
  const [timerActive, setTimerActive] = useState(false);
  
  // Camera & shareable image state
  const [showCamera, setShowCamera] = useState(false);
  const [capturedPhoto, setCapturedPhoto] = useState(null);
  const [rawPhoto, setRawPhoto] = useState(null); // Original unprocessed photo
  const [shareableImage, setShareableImage] = useState(null);
  const [processingImage, setProcessingImage] = useState(false);
  const [faceAnalysis, setFaceAnalysis] = useState(null);
  const [analysisStep, setAnalysisStep] = useState('');
  const [imageStyle, setImageStyle] = useState('clinical'); // 'clinical' or 'futuristic'
  const [soulCompliment, setSoulCompliment] = useState(''); // Random compliment after selfie
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  
  const totalQuestions = QUIZ_QUESTIONS.length;
  
  // Fetch referral stats helper
  const fetchReferralStats = useCallback(async (code) => {
    if (!code) return;
    try {
      const res = await axios.get(`${API}/api/bio-scan/stats/${code}`);
      setReferralStats({
        started: res.data.referrals_started || 0,
        completed: res.data.referral_count || 0,
        points: res.data.total_points || 0,
        earnings: (res.data.referral_count || 0) * 5
      });
    } catch (e) {
      console.error('Error fetching stats:', e);
    }
  }, []);
  
  // Save session to localStorage when quiz is completed
  const saveSession = useCallback((data) => {
    try {
      const sessionData = {
        email: data.email,
        phone: data.phone,
        referralCode: data.referralCode,
        bioAgeOffset: data.bioAgeOffset,
        riskLevel: data.riskLevel,
        savedAt: new Date().toISOString()
      };
      localStorage.setItem('bioScanSession', JSON.stringify(sessionData));
    } catch (e) {
      console.error('Error saving session:', e);
    }
  }, []);
  
  // ============ RESTORE SAVED SESSION ============
  // Check localStorage for saved quiz data on mount
  useEffect(() => {
    const savedData = localStorage.getItem('bioScanSession');
    if (savedData) {
      try {
        const data = JSON.parse(savedData);
        // Only restore if data is less than 30 days old
        const savedTime = new Date(data.savedAt);
        const now = new Date();
        const daysDiff = (now - savedTime) / (1000 * 60 * 60 * 24);
        
        if (daysDiff < 30 && data.referralCode) {
          // Restore saved session
          setEmail(data.email || '');
          setPhone(data.phone || '');
          setUserReferralCode(data.referralCode);
          setScanResult({
            bioAgeOffset: data.bioAgeOffset || 0,
            riskLevel: data.riskLevel || 'Low',
            referralCode: data.referralCode,
            isNewUser: false,
            recommendations: generateRecommendations({}) // Generate default recommendations
          });
          setCurrentStep(totalQuestions + 2); // Go directly to results
          
          // Fetch latest stats from server
          fetchReferralStats(data.referralCode);
          
          toast.success('Welcome back! Your session has been restored.');
        }
      } catch (e) {
        console.error('Error restoring session:', e);
        localStorage.removeItem('bioScanSession');
      }
    }
  }, [totalQuestions, fetchReferralStats]);
  
  // Show popup when 10+ referrals completed (must be after totalQuestions is defined)
  useEffect(() => {
    if (referralStats.completed >= 10 && !hasSeenRedeemPopup && currentStep === totalQuestions + 2) {
      // Small delay for dramatic effect
      const timer = setTimeout(() => {
        setShowRedeemPopup(true);
        setHasSeenRedeemPopup(true);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [referralStats.completed, hasSeenRedeemPopup, currentStep, totalQuestions]);
  
  // Start polling for live stats when on results page
  useEffect(() => {
    if (currentStep === totalQuestions + 2 && userReferralCode) {
      fetchReferralStats(userReferralCode);
      const interval = setInterval(() => {
        fetchReferralStats(userReferralCode);
      }, 10000);
      return () => clearInterval(interval);
    }
  }, [currentStep, userReferralCode, totalQuestions, fetchReferralStats]);
  
  // Track when someone starts the quiz via a referral link
  useEffect(() => {
    if (referrerCode && currentStep === 1) {
      axios.post(`${API}/api/bio-scan/track-start`, {
        referrer_code: referrerCode
      }).catch(err => console.error('Failed to track start:', err));
    }
  }, [referrerCode, currentStep]);
  
  // Timer effect
  useEffect(() => {
    if (timerActive && timeLeft > 0) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    } else if (timerActive && timeLeft === 0) {
      handleTimeUp();
    }
  }, [timerActive, timeLeft]);
  
  // Start timer when entering a question
  useEffect(() => {
    if (currentStep >= 1 && currentStep <= totalQuestions) {
      setTimeLeft(QUESTION_TIMER);
      setTimerActive(true);
    } else {
      setTimerActive(false);
    }
  }, [currentStep, totalQuestions]);
  
  const handleTimeUp = useCallback(() => {
    const question = QUIZ_QUESTIONS[currentStep - 1];
    if (question && answers[question.id] === undefined) {
      setAnswers(prev => ({ ...prev, [question.id]: 1 }));
    }
    
    if (currentStep < totalQuestions) {
      setCurrentStep(currentStep + 1);
    } else {
      setCurrentStep(totalQuestions + 1);
    }
  }, [currentStep, totalQuestions, answers]);
  
  // Calculate Bio-Age Score
  const calculateBioAge = () => {
    let totalImpact = 0;
    QUIZ_QUESTIONS.forEach(q => {
      const answer = answers[q.id];
      if (answer !== undefined) {
        const option = q.options.find(o => o.value === answer);
        if (option) {
          totalImpact += option.bioAgeImpact;
        }
      }
    });
    
    const bioAgeOffset = Math.round((totalImpact / 36) * 15);
    
    let riskLevel = 'Low';
    if (bioAgeOffset > 10) {
      riskLevel = 'High';
    } else if (bioAgeOffset > 5) {
      riskLevel = 'Moderate';
    }
    
    return {
      bioAgeOffset,
      riskLevel,
      recommendations: generateRecommendations(answers)
    };
  };
  
  const generateRecommendations = (ans) => {
    const recs = [];
    
    // Get brand recommendation based on age and concerns
    const brandKey = getBrandRecommendation(ans);
    const brand = BRAND_RECOMMENDATIONS[brandKey];
    
    // Build personalized recommendation text based on concerns
    let recommendationReason = '';
    if (ans.primary_concern === 'dark_circles') {
      recommendationReason = 'Your dark circles indicate periorbital pigmentation and vascular issues that need targeted treatment.';
    } else if (ans.eye_concern === 'severe' || ans.eye_concern === 'moderate') {
      recommendationReason = 'Your eye area shows signs that benefit from our specialized eye concentration formula.';
    } else if (ans.primary_concern === 'aging') {
      recommendationReason = 'Fine lines and firmness loss indicate cellular aging that requires deep regeneration.';
    } else if (ans.primary_concern === 'dullness') {
      recommendationReason = 'Uneven skin tone responds excellently to our Tranexamic Acid + PDRN protocol.';
    } else {
      recommendationReason = 'Based on your unique skin profile, this is your optimal cellular repair protocol.';
    }
    
    // Add brand-specific recommendation as first item
    recs.push({
      icon: Sparkles,
      title: `Your Perfect Match: ${brand.heroProduct}`,
      text: recommendationReason,
      brand: brand,
      isBrandRec: true,
      isPrimary: true
    });
    
    // Check for secondary product recommendation (dual-product protocol)
    const secondaryKey = getSecondaryRecommendation(ans, brandKey);
    if (secondaryKey) {
      const secondaryBrand = BRAND_RECOMMENDATIONS[secondaryKey];
      let secondaryReason = '';
      
      if (secondaryKey === 'reroots_eye') {
        secondaryReason = 'Add our Eye Concentration to target your under-eye area for a complete protocol.';
      } else if (secondaryKey === 'reroots') {
        secondaryReason = 'Pair with AURA-GEN Serum for full-face cellular regeneration.';
      }
      
      recs.push({
        icon: Target,
        title: `Complete Your Protocol: ${secondaryBrand.heroProduct}`,
        text: secondaryReason,
        brand: secondaryBrand,
        isBrandRec: true,
        isSecondary: true
      });
    }
    
    if (ans.climate >= 2) {
      recs.push({
        icon: Thermometer,
        title: 'Thermal Protection Needed',
        text: 'High exposure to temperature extremes is accelerating cellular aging.'
      });
    }
    
    if (ans.repair >= 2) {
      recs.push({
        icon: Activity,
        title: 'Boost Cellular Energy',
        text: 'Slow skin recovery indicates depleted ATP levels.'
      });
    }
    
    if (ans.barrier >= 2) {
      recs.push({
        icon: Shield,
        title: 'Barrier Reinforcement Required',
        text: 'Your skin barrier needs strengthening to prevent moisture loss.'
      });
    }
    
    if (ans.primary_concern === 'acne') {
      recs.push({
        icon: Shield,
        title: 'Congestion Control',
        text: 'Your skin needs gentle yet effective actives to clear breakouts without irritation.'
      });
    }
    
    // Add eye-specific recommendation if they have eye concerns but didn't get eye product as primary
    if ((ans.eye_concern === 'mild' || ans.eye_concern === 'moderate') && brandKey !== 'reroots_eye' && !secondaryKey) {
      recs.push({
        icon: Target,
        title: 'Eye Area Attention',
        text: 'Consider adding our ROSE-GEN Eye Concentration to your routine for targeted under-eye care.'
      });
    }
    
    if (recs.length === 1) {
      recs.push({
        icon: CheckCircle,
        title: 'Maintain Your Results',
        text: 'Your skin is in good condition! Our formula will help you maintain and enhance your natural cellular health.'
      });
    }
    
    return recs;
  };
  
  const handleAnswer = (questionId, value) => {
    setAnswers(prev => ({ ...prev, [questionId]: value }));
    setTimerActive(false);
    
    setTimeout(() => {
      if (currentStep < totalQuestions) {
        setCurrentStep(currentStep + 1);
      } else {
        setCurrentStep(totalQuestions + 1);
      }
    }, 400);
  };
  
  const handleSubmitEmail = async () => {
    if (!email && !phone) {
      toast.error('Please enter your email or phone number');
      return;
    }
    
    if (email && !email.includes('@')) {
      toast.error('Please enter a valid email');
      return;
    }
    
    setLoading(true);
    
    // Combine country code with phone number
    const fullPhone = phone.trim() ? `${phoneCountryCode}${phone.trim().replace(/^0+/, '')}` : '';
    
    try {
      const bioAge = calculateBioAge();
      const recommendations = generateRecommendations(answers);
      
      const res = await axios.post(`${API}/api/bio-scan/submit`, {
        email: email.toLowerCase().trim(),
        phone: fullPhone,
        answers,
        bio_age_offset: bioAge.bioAgeOffset,
        risk_level: bioAge.riskLevel,
        referrer_code: referrerCode
      });
      
      // Handle returning user - they already completed the quiz
      if (!res.data.is_new_user) {
        // Returning user - fetch their existing data and show referral dashboard
        const resultData = {
          bioAgeOffset: res.data.bio_age_offset || bioAge.bioAgeOffset,
          riskLevel: res.data.risk_level || bioAge.riskLevel,
          referralCode: res.data.referral_code,
          isNewUser: false,
          recommendations
        };
        
        setScanResult(resultData);
        setUserReferralCode(res.data.referral_code);
        setReferralStats({
          started: res.data.referrals_started || 0,
          completed: res.data.referral_count || 0,
          points: res.data.total_points || 0,
          earnings: (res.data.referral_count || 0) * 5
        });
        
        // Save session to localStorage
        saveSession({
          email: email.toLowerCase().trim(),
          phone: fullPhone,
          referralCode: res.data.referral_code,
          bioAgeOffset: res.data.bio_age_offset || bioAge.bioAgeOffset,
          riskLevel: res.data.risk_level || bioAge.riskLevel,
          recommendations
        });
        
        setCurrentStep(totalQuestions + 2);
        toast.success('Welcome back! Here\'s your referral dashboard.');
        return;
      }
      
      // New user flow
      const resultData = {
        ...bioAge,
        referralCode: res.data.referral_code,
        isNewUser: res.data.is_new_user,
        recommendations
      };
      
      setScanResult(resultData);
      setUserReferralCode(res.data.referral_code);
      setReferralStats({
        started: res.data.referrals_started || 0,
        completed: res.data.referral_count || 0,
        points: res.data.total_points || 0,
        earnings: (res.data.referral_count || 0) * 5
      });
      
      // Save session to localStorage
      saveSession({
        email: email.toLowerCase().trim(),
        phone: fullPhone,
        referralCode: res.data.referral_code,
        bioAgeOffset: bioAge.bioAgeOffset,
        riskLevel: bioAge.riskLevel,
        recommendations
      });
      
      setCurrentStep(totalQuestions + 2);
      
      if (referrerCode) {
        toast.success(`Thank you! Your referrer earned ${formatCurrency(5, userCurrency)}.`);
      }
      
    } catch (err) {
      console.error('Submit error:', err);
      toast.error(err.response?.data?.detail || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };
  
  // Start camera for selfie
  const startCamera = async () => {
    try {
      setShowCamera(true); // Show camera UI first
      
      // Small delay to ensure video element is mounted
      await new Promise(resolve => setTimeout(resolve, 100));
      
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          facingMode: 'user', 
          width: { ideal: 720 }, 
          height: { ideal: 720 } 
        } 
      });
      
      streamRef.current = stream;
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        // Wait for video to be ready
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play().catch(e => console.error('Play error:', e));
        };
      }
    } catch (err) {
      console.error('Camera error:', err);
      setShowCamera(false);
      toast.error('Could not access camera. Please allow camera permissions and try again.');
    }
  };
  
  // Stop camera
  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setShowCamera(false);
  };
  
  // Capture photo and create encouraging shareable image
  const capturePhoto = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    
    setProcessingImage(true);
    setAnalysisStep('Creating your shareable image...');
    
    // Pick a random soul compliment
    const randomCompliment = SOUL_COMPLIMENTS[Math.floor(Math.random() * SOUL_COMPLIMENTS.length)];
    setSoulCompliment(randomCompliment);
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // Set canvas size
    canvas.width = 720;
    canvas.height = 720;
    
    // Draw video frame (mirrored for selfie)
    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(video, -720, 0, 720, 720);
    ctx.restore();
    
    // Get raw photo
    const rawPhotoData = canvas.toDataURL('image/jpeg', 0.8);
    setRawPhoto(rawPhotoData); // Save for style switching
    
    // Create the styled shareable image with encouraging messaging
    await createStyledShareableImage(canvas, ctx, rawPhotoData, null, imageStyle);
    
    stopCamera();
    
    // Small delay to ensure image is ready
    setTimeout(() => {
      setProcessingImage(false);
      setAnalysisStep('');
      toast.success('Looking great! Now share your link below! 👇');
      
      // Show referral section prompt and scroll to it after 5-6 second delay
      setShowReferralAfterPhoto(true);
      setTimeout(() => {
        const referralSection = document.getElementById('referral-section');
        if (referralSection) {
          referralSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 5500); // 5.5 second delay before scrolling
    }, 500);
  };
  
  // Create the shareable image using the custom frame template
  const createStyledShareableImage = async (canvas, ctx, rawPhoto, analysis, style = 'clinical') => {
    const selfieImg = new Image();
    selfieImg.crossOrigin = 'anonymous';
    
    // Load the frame template
    const frameImg = new Image();
    frameImg.crossOrigin = 'anonymous';
    
    selfieImg.onload = async () => {
      // Load frame first, then compose the image
      frameImg.onload = () => {
        // Set canvas to match frame dimensions
        canvas.width = frameImg.width;
        canvas.height = frameImg.height;
        
        // Scale for output (720px wide)
        const scale = 720 / frameImg.width;
        canvas.width = 720;
        canvas.height = Math.round(frameImg.height * scale);
        
        const bioAge = scanResult?.bioAgeOffset || 0;
        const compliment = soulCompliment || SOUL_COMPLIMENTS[Math.floor(Math.random() * SOUL_COMPLIMENTS.length)];
        
        // Draw the frame first as background
        ctx.drawImage(frameImg, 0, 0, canvas.width, canvas.height);
        
        // The oval/circle for selfie - position inside the rope circle on frame
        const circleX = canvas.width * 0.505; // Centered horizontally
        const circleY = canvas.height * 0.31; // Position
        const radiusX = canvas.width * 0.16; // BIGGER radius to cover gap
        const radiusY = canvas.height * 0.115; // BIGGER radius to cover gap
        
        // Draw elliptical clipped selfie - centered in the rope circle
        ctx.save();
        ctx.beginPath();
        ctx.ellipse(circleX, circleY, radiusX, radiusY, 0, 0, Math.PI * 2);
        ctx.clip();
        
        // Scale selfie - ZOOMED IN more (1.3x)
        const selfieScale = Math.max((radiusX * 2) / selfieImg.width, (radiusY * 2) / selfieImg.height) * 1.3;
        const scaledW = selfieImg.width * selfieScale;
        const scaledH = selfieImg.height * selfieScale;
        // Shift image DOWN 4% - less shift to fill top gap
        ctx.drawImage(selfieImg, circleX - scaledW/2, circleY - scaledH/2 + (scaledH * 0.04), scaledW, scaledH);
        ctx.restore();
        
        // === TOP BANNER with Bio-Age - EXTENDED to cover any gap ===
        // === TOP BANNER - BIGGER ===
        const topBannerHeight = canvas.height * 0.13; // Even bigger
        
        // Banner background - tan/brown color - FULL WIDTH at top edge
        ctx.fillStyle = 'rgba(180, 140, 100, 1)';
        ctx.fillRect(0, 0, canvas.width, topBannerHeight);
        
        // Banner border at bottom
        ctx.fillStyle = '#8B6914';
        ctx.fillRect(0, topBannerHeight - 2, canvas.width, 2);
        
        // Bio-Age text - dark black - smaller, centered in middle
        ctx.fillStyle = '#1a0f0a';
        ctx.font = `bold ${Math.round(canvas.height * 0.032)}px "Georgia", serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`Bio-Age: +${bioAge} Years`, canvas.width * 0.5, topBannerHeight * 0.5);
        
        // === BOTTOM BANNER - BIGGER for multi-line compliments ===
        const bottomBannerHeight = canvas.height * 0.12; // Bigger for 2-3 lines
        const bottomBannerY = canvas.height - bottomBannerHeight;
        
        // Banner background - tan/brown color - FULL WIDTH at bottom edge
        ctx.fillStyle = 'rgba(180, 140, 100, 1)';
        ctx.fillRect(0, bottomBannerY, canvas.width, bottomBannerHeight);
        
        // Banner border at top
        ctx.fillStyle = '#8B6914';
        ctx.fillRect(0, bottomBannerY, canvas.width, 2);
        
        // Compliment text - dark black, BOLD
        ctx.fillStyle = '#1a0f0a';
        const fontSize = Math.round(canvas.height * 0.026);
        ctx.font = `bold ${fontSize}px "Georgia", serif`;
        ctx.textAlign = 'center';
        
        // Wrap text for multi-line display
        const maxWidth = canvas.width * 0.90;
        const complimentText = `"${compliment}"`;
        const words = complimentText.split(' ');
        const lines = [];
        let currentLine = '';
        
        for (const word of words) {
          const testLine = currentLine ? `${currentLine} ${word}` : word;
          const metrics = ctx.measureText(testLine);
          if (metrics.width > maxWidth && currentLine) {
            lines.push(currentLine);
            currentLine = word;
          } else {
            currentLine = testLine;
          }
        }
        if (currentLine) lines.push(currentLine);
        
        // Draw each line centered in banner
        const lineHeight = fontSize * 1.3;
        const totalTextHeight = lines.length * lineHeight;
        const startY = bottomBannerY + (bottomBannerHeight - totalTextHeight) / 2 + fontSize / 2;
        
        lines.forEach((line, index) => {
          ctx.fillText(line, canvas.width * 0.5, startY + index * lineHeight);
        });
        
        // Save final image
        const imageData = canvas.toDataURL('image/jpeg', 0.92);
        setCapturedPhoto(imageData);
        
        // Include user's referral link in share text
        const referralUrl = userReferralCode 
          ? `https://reroots.ca/Bio-Age-Repair-Scan?ref=${userReferralCode}`
          : 'https://reroots.ca/Bio-Age-Repair-Scan';
        
        const hashtags = '#ReRoots #BioAgeScan #SkinCare #BeautyQuiz #GlowUp #SelfCare';
        setShareableImage({
          image: imageData,
          text: `🧬 I just discovered my skin's Bio-Age! Find out yours too:\n\n${referralUrl}\n\n💫 It only takes 60 seconds!\n\n${hashtags}`,
          hashtags: hashtags
        });
      };
      
      frameImg.onerror = () => {
        console.error('Frame failed to load, using fallback');
        // Fallback - just draw the selfie with basic styling
        canvas.width = 720;
        canvas.height = 720;
        ctx.drawImage(selfieImg, 0, 0, 720, 720);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.92);
        setCapturedPhoto(imageData);
        setShareableImage({
          image: imageData,
          text: `🧬 My Bio-Age Result! Take the quiz: reroots.ca/Bio-Age-Repair-Scan`,
          hashtags: '#BioAgeScan #ReRoots'
        });
      };
      
      // Load the frame template
      frameImg.src = window.location.origin + '/quiz-frame.jpg';
    };
    
    selfieImg.src = rawPhoto;
  };
  
  // Helper function to wrap text
  const wrapText = (ctx, text, x, y, maxWidth, lineHeight) => {
    const words = text.split(' ');
    let line = '';
    let testLine = '';
    let lineCount = 0;
    
    for (let n = 0; n < words.length; n++) {
      testLine = line + words[n] + ' ';
      const metrics = ctx.measureText(testLine);
      if (metrics.width > maxWidth && n > 0) {
        ctx.fillText(line.trim(), x, y + (lineCount * lineHeight));
        line = words[n] + ' ';
        lineCount++;
      } else {
        line = testLine;
      }
    }
    ctx.fillText(line.trim(), x, y + (lineCount * lineHeight));
  };
  
  // Helper function to draw sparkle
  const drawSparkle = (ctx, x, y, size, color) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    
    // Main cross
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(0, size);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-size, 0);
    ctx.lineTo(size, 0);
    ctx.stroke();
    
    // Diagonal lines
    const diagSize = size * 0.6;
    ctx.beginPath();
    ctx.moveTo(-diagSize, -diagSize);
    ctx.lineTo(diagSize, diagSize);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(diagSize, -diagSize);
    ctx.lineTo(-diagSize, diagSize);
    ctx.stroke();
    
    // Center dot
    ctx.beginPath();
    ctx.arc(0, 0, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#FDF8F3';
    ctx.fill();
    ctx.stroke();
    
    ctx.restore();
  };
  
  // Helper function to draw star
  const drawStar = (ctx, x, y, size, color) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < 5; i++) {
      const angle = (i * 4 * Math.PI) / 5 - Math.PI / 2;
      const px = Math.cos(angle) * size;
      const py = Math.sin(angle) * size;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  };
  
  // Helper function to draw ReRoots flower logo
  const drawRerootsLogo = (ctx, centerX, centerY, size) => {
    ctx.save();
    ctx.translate(centerX, centerY);
    
    // Gold gradient for logo
    const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, size);
    gradient.addColorStop(0, '#D4AF37');
    gradient.addColorStop(1, '#C9A86C');
    
    ctx.fillStyle = gradient;
    ctx.strokeStyle = gradient;
    ctx.lineWidth = size * 0.05;
    
    // Draw 5 petals (flower shape)
    for (let i = 0; i < 5; i++) {
      ctx.save();
      ctx.rotate((i * 72 * Math.PI) / 180);
      
      // Petal shape
      ctx.beginPath();
      ctx.moveTo(0, -size * 0.15);
      ctx.bezierCurveTo(
        size * 0.3, -size * 0.4,
        size * 0.5, -size * 0.1,
        size * 0.2, size * 0.2
      );
      ctx.bezierCurveTo(
        size * 0.1, size * 0.3,
        -size * 0.1, size * 0.3,
        -size * 0.2, size * 0.2
      );
      ctx.bezierCurveTo(
        -size * 0.5, -size * 0.1,
        -size * 0.3, -size * 0.4,
        0, -size * 0.15
      );
      ctx.fill();
      
      // Curved accent line
      ctx.beginPath();
      ctx.moveTo(size * 0.35, -size * 0.2);
      ctx.quadraticCurveTo(size * 0.5, size * 0.1, size * 0.25, size * 0.35);
      ctx.stroke();
      
      ctx.restore();
    }
    
    // Center dot
    ctx.beginPath();
    ctx.arc(0, 0, size * 0.08, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.restore();
  };
  
  // Regenerate image with different style
  const regenerateWithStyle = async (style) => {
    if (!rawPhoto) return;
    setImageStyle(style);
    setProcessingImage(true);
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // Use the stored analysis or fallback
    const analysis = faceAnalysis || {
      detected_concerns: scanResult?.recommendations?.map(r => r.title) || ['Cellular Aging'],
      primary_zone: 'overall'
    };
    
    // Regenerate with new style using raw photo
    await createStyledShareableImage(canvas, ctx, rawPhoto, analysis, style);
    setProcessingImage(false);
  };
  
  // Download shareable image
  const downloadShareableImage = () => {
    if (!shareableImage?.image) return;
    
    const link = document.createElement('a');
    link.href = shareableImage.image;
    link.download = `reroots-bio-age-${scanResult?.bioAgeOffset || 0}.jpg`;
    link.click();
    toast.success('Image saved! Share it on social media');
  };
  
  // Share image directly using Web Share API
  const shareImageDirect = async (platform) => {
    if (!shareableImage?.image) {
      toast.error('Please take a selfie first!');
      return;
    }
    
    // ReRoots social media hashtags
    const hashtags = '#ReRoots #BioAgeScan #SkinCare #BeautyQuiz #SkincareRoutine #GlowUp #SelfCare #NaturalBeauty #AntiAging #SkinHealth';
    
    // Always include the user's referral link
    const referralUrl = shareUrl || `https://reroots.ca/Bio-Age-Repair-Scan${userReferralCode ? '?ref=' + userReferralCode : ''}`;
    
    // Share text with hashtags
    const shareText = `🧬 I just discovered my skin's Bio-Age! Take the quiz and find out yours:\n\n${referralUrl}\n\n💫 It only takes 60 seconds!\n\n${hashtags}`;
    
    // Shorter version for Twitter (character limit)
    const twitterText = `🧬 Just discovered my skin's Bio-Age! Find yours: ${referralUrl}\n\n#ReRoots #BioAgeScan #SkinCare #GlowUp`;
    
    // Convert base64 to blob
    const base64Response = await fetch(shareableImage.image);
    const blob = await base64Response.blob();
    const file = new File([blob], 'my-bio-age-result.jpg', { type: 'image/jpeg' });
    
    // Try Web Share API first (works on mobile) - user stays on page
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({
          files: [file],
          title: 'My Bio-Age Result',
          text: shareText,
        });
        toast.success('Shared successfully! Your referral link was included 🎉');
        return;
      } catch (err) {
        if (err.name === 'AbortError') {
          // User cancelled - that's fine
          return;
        }
        console.error('Share failed:', err);
      }
    }
    
    // Fallback: Download image and open platform in POPUP (user stays on current page)
    downloadShareableImage();
    toast.info('Image saved! Your referral link & hashtags included 📸');
    
    // Open the platform in a popup window so user stays on quiz page
    const urls = {
      whatsapp: `https://wa.me/?text=${encodeURIComponent(shareText)}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(referralUrl)}&quote=${encodeURIComponent(`🧬 I just discovered my skin's Bio-Age! Take the quiz too! ${hashtags}`)}`,
      twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(twitterText)}`,
      telegram: `https://t.me/share/url?url=${encodeURIComponent(referralUrl)}&text=${encodeURIComponent(`🧬 I just discovered my skin's Bio-Age! Take the quiz and find out yours! 💫\n\n${hashtags}`)}`
    };
    
    if (urls[platform]) {
      // Open in popup window - user can close popup and return to quiz easily
      const width = 600;
      const height = 500;
      const left = (window.innerWidth - width) / 2;
      const top = (window.innerHeight - height) / 2;
      
      window.open(
        urls[platform], 
        'share_popup',
        `width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes`
      );
    }
  };
  
  // Copy share text
  const copyShareText = () => {
    const text = shareableImage?.text || `🧬 My Skin Bio-Age is +${scanResult?.bioAgeOffset || 0} years! Take your scan at ${window.location.origin}/Bio-Age-Repair-Scan`;
    navigator.clipboard.writeText(`${text}\n\n${shareableImage?.hashtags || ''}`);
    toast.success('Caption copied! Paste it with your image');
  };
  
  const shareUrl = userReferralCode ? `${window.location.origin}/Bio-Age-Repair-Scan?ref=${userReferralCode}` : '';
  
  const handleCopy = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    toast.success('Link copied!');
    setTimeout(() => setCopied(false), 2000);
  };
  
  const shareLinks = [
    {
      name: 'WhatsApp',
      icon: MessageCircle,
      color: 'bg-green-500 hover:bg-green-600',
      url: `https://wa.me/?text=${encodeURIComponent(`I just discovered my skin's Bio-Age! Take this quick survey:\n\n${shareUrl}`)}`
    },
    {
      name: 'Facebook',
      icon: Facebook,
      color: 'bg-blue-600 hover:bg-blue-700',
      url: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`
    },
    {
      name: 'Twitter',
      icon: Twitter,
      color: 'bg-sky-500 hover:bg-sky-600',
      url: `https://twitter.com/intent/tweet?text=${encodeURIComponent('Just took this Bio-Age skin survey! Find out how old your skin really is:')}&url=${encodeURIComponent(shareUrl)}`
    },
    {
      name: 'Telegram',
      icon: Send,
      color: 'bg-blue-500 hover:bg-blue-600',
      url: `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent('Take this Bio-Age skin survey!')}`
    }
  ];
  
  // Timer Circle Component
  const TimerCircle = () => (
    <div className="relative w-14 h-14">
      <svg className="w-full h-full transform -rotate-90">
        <circle cx="28" cy="28" r="24" stroke="rgba(255,255,255,0.1)" strokeWidth="4" fill="none" />
        <circle
          cx="28" cy="28" r="24"
          stroke={timeLeft <= 5 ? "#ef4444" : "#06b6d4"}
          strokeWidth="4" fill="none" strokeLinecap="round"
          strokeDasharray={`${(timeLeft / QUESTION_TIMER) * 150.8} 150.8`}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className={`text-lg font-bold ${timeLeft <= 5 ? 'text-red-400' : 'text-white'}`}>
          {timeLeft}
        </span>
      </div>
    </div>
  );
  
  // Check if quiz is completed
  const isQuizCompleted = currentStep > totalQuestions + 1;
  
  // Check if eligible for redemption (10+ referrals)
  const canRedeem = referralStats.completed >= 10;
  
  // Render steps
  const renderStep = () => {
    // Intro
    if (currentStep === 0) {
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="text-center space-y-6"
        >
          {/* DNA Animation */}
          <div className="relative w-28 h-28 mx-auto">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-cyan-500/20 to-purple-500/20 animate-pulse" />
            <div className="absolute inset-4 rounded-full bg-gradient-to-br from-cyan-500/30 to-purple-500/30 animate-pulse" style={{ animationDelay: '0.5s' }} />
            <div className="absolute inset-0 flex items-center justify-center">
              <Dna className="w-12 h-12 text-cyan-400 animate-spin" style={{ animationDuration: '8s' }} />
            </div>
          </div>
          
          <div>
            <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/30 mb-3">
              Skin Health Survey
            </Badge>
            <h1 className="text-3xl font-bold text-white mb-3" style={{ fontFamily: '"Playfair Display", serif' }}>
              Bio-Age & Repair <span className="text-cyan-400">Scan</span>
            </h1>
            <p className="text-gray-400 text-sm">
              Help us understand your skin better in under 2 minutes
            </p>
          </div>
          
          {/* Survey Reward Banner */}
          <div className="bg-gradient-to-r from-green-500/20 to-emerald-500/20 border border-green-500/30 rounded-2xl p-5">
            <div className="flex items-center justify-center gap-3 mb-2">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                <Gift className="w-6 h-6 text-green-400" />
              </div>
              <div className="text-left">
                <p className="text-green-300 text-xs uppercase tracking-wider">Thank You Reward</p>
                <p className="text-2xl font-bold text-white">Unlock 30% Discount</p>
              </div>
            </div>
            <p className="text-green-200/80 text-sm">
              Get <span className="font-bold">10 successful signups</span> & unlock 30% off! (1 reference = 60 points)
            </p>
          </div>
          
          {/* Currency selector */}
          <div className="flex justify-center">
            <button 
              onClick={() => setShowCurrencyPicker(!showCurrencyPicker)}
              className="flex items-center gap-2 text-xs text-gray-400 hover:text-white transition-colors bg-white/5 px-3 py-1.5 rounded-full"
            >
              <Globe className="w-3 h-3" />
              <span>{currencyConfig.flag} {currencyConfig.name}</span>
              <ChevronDown className="w-3 h-3" />
            </button>
          </div>
          
          {/* Currency Picker Dropdown */}
          {showCurrencyPicker && (
            <div className="bg-black/80 border border-white/20 rounded-xl p-2 max-h-48 overflow-y-auto">
              <div className="grid grid-cols-2 gap-1">
                {Object.entries(CURRENCY_CONFIG).map(([code, config]) => (
                  <button
                    key={code}
                    onClick={() => { setUserCurrency(code); setShowCurrencyPicker(false); }}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors ${
                      userCurrency === code ? 'bg-cyan-500/20 text-cyan-300' : 'hover:bg-white/10 text-gray-300'
                    }`}
                  >
                    <span>{config.flag}</span>
                    <span>{config.name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {/* Quick Stats */}
          <div className="flex justify-center gap-6">
            <div className="text-center">
              <Clock className="w-5 h-5 text-cyan-400 mx-auto mb-1" />
              <p className="text-xs text-gray-400">2 Min</p>
            </div>
            <div className="text-center">
              <Target className="w-5 h-5 text-purple-400 mx-auto mb-1" />
              <p className="text-xs text-gray-400">8 Questions</p>
            </div>
            <div className="text-center">
              <Heart className="w-5 h-5 text-pink-400 mx-auto mb-1" />
              <p className="text-xs text-gray-400">Anonymous</p>
            </div>
          </div>
          
          {/* Referral Notice */}
          {referrerCode && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3">
              <p className="text-amber-300 text-sm">
                <Sparkles className="w-4 h-4 inline mr-1" />
                You were invited! Complete the survey to see your results.
              </p>
            </div>
          )}
          
          <Button 
            onClick={() => setCurrentStep(1)}
            className="w-full bg-gradient-to-r from-cyan-500 to-purple-500 hover:from-cyan-600 hover:to-purple-600 text-white py-6 text-lg rounded-xl"
            data-testid="start-scan-btn"
          >
            Start Survey
            <ChevronRight className="ml-2 w-5 h-5" />
          </Button>
          
          <p className="text-xs text-gray-500">
            Your responses help improve skincare research
          </p>
        </motion.div>
      );
    }
    
    // Questions (1-5)
    if (currentStep >= 1 && currentStep <= totalQuestions) {
      const question = QUIZ_QUESTIONS[currentStep - 1];
      const Icon = question.icon;
      
      return (
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -50 }}
          className="space-y-5"
        >
          {/* Progress Header */}
          <div className="text-center">
            <span className="text-sm text-gray-500">Question {currentStep} of {totalQuestions}</span>
          </div>
          
          {/* Progress Bar */}
          <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
            <motion.div 
              className="h-full bg-gradient-to-r from-cyan-500 to-purple-500"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: (currentStep / totalQuestions) }}
              style={{ transformOrigin: 'left' }}
              transition={{ duration: 0.5 }}
            />
          </div>
          
          {/* Timer - Centered below progress */}
          <div className="flex justify-center">
            <TimerCircle />
          </div>
          
          {/* Question Card */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center">
                <Icon className="w-6 h-6 text-cyan-400" />
              </div>
              <Badge className="bg-white/10 text-gray-300 border-white/20">
                {question.category}
              </Badge>
            </div>
            
            <h2 className="text-lg font-semibold text-white leading-snug mb-6">
              {question.question}
            </h2>
            {question.subtext && (
              <p className="text-sm text-gray-400 mb-6">{question.subtext}</p>
            )}
            
            {/* Options - More spacing */}
            <div className="space-y-3">
              {question.options.map((option, idx) => (
                <motion.button
                  key={idx}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => handleAnswer(question.id, option.value)}
                  className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
                    answers[question.id] === option.value
                      ? 'border-cyan-500 bg-cyan-500/20'
                      : 'border-white/10 bg-white/5 hover:border-cyan-500/50 hover:bg-white/10'
                  }`}
                  data-testid={`option-${question.id}-${idx}`}
                >
                  <span className="text-white text-sm">{option.label}</span>
                </motion.button>
              ))}
            </div>
          </div>
          
          {/* Science Hook */}
          <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-3">
            <p className="text-purple-300 text-xs flex items-start gap-2">
              <Sparkles className="w-3 h-3 mt-0.5 shrink-0" />
              <span>{question.scienceHook}</span>
            </p>
          </div>
        </motion.div>
      );
    }
    
    // Email Gate (step 6)
    if (currentStep === totalQuestions + 1) {
      const bioAge = calculateBioAge();
      
      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center space-y-5"
        >
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-amber-500/20 to-orange-500/20 flex items-center justify-center mx-auto">
            <Lock className="w-8 h-8 text-amber-400" />
          </div>
          
          <div>
            <h2 className="text-2xl font-bold text-white mb-2">
              Your Results Are Ready
            </h2>
            <p className="text-gray-400 text-sm">
              Please enter your email to view your personalized Bio-Age report
            </p>
          </div>
          
          {/* Bio-Age Preview */}
          <div className="bg-gradient-to-br from-cyan-500/10 to-purple-500/10 border border-white/10 rounded-2xl p-6">
            <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Your Skin Bio-Age</p>
            <div className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400">
              +{bioAge.bioAgeOffset} years
            </div>
            <p className="text-xs text-gray-500 mt-2">Unlock full breakdown below</p>
          </div>
          
          {/* Input Fields */}
          <div className="space-y-3">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
              <Input
                type="email"
                placeholder="Your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pl-10 bg-white/10 border-white/20 text-white placeholder:text-gray-500 h-12"
                data-testid="email-input"
              />
            </div>
            
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-white/10" />
              <span className="text-gray-500 text-xs">or</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            
            {/* Phone input with country code */}
            <div className="relative">
              <div className="flex">
                {/* Country code selector */}
                <button
                  type="button"
                  onClick={() => setShowCountryPicker(!showCountryPicker)}
                  className="flex items-center gap-1 bg-white/10 border border-white/20 border-r-0 rounded-l-lg px-3 h-12 text-white hover:bg-white/15 transition-colors"
                >
                  <span className="text-lg">{currencyConfig.flag}</span>
                  <span className="text-sm font-mono">{phoneCountryCode}</span>
                  <ChevronDown className="w-3 h-3 text-gray-400" />
                </button>
                <Input
                  type="tel"
                  placeholder="Phone number"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/[^0-9]/g, ''))}
                  className="flex-1 bg-white/10 border-white/20 text-white placeholder:text-gray-500 h-12 rounded-l-none"
                  data-testid="phone-input"
                />
              </div>
              
              {/* Country picker dropdown */}
              {showCountryPicker && (
                <div className="absolute top-14 left-0 z-50 bg-black/95 border border-white/20 rounded-xl p-2 w-full max-h-48 overflow-y-auto">
                  {Object.entries(CURRENCY_CONFIG).map(([code, config]) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => { 
                        setPhoneCountryCode(config.phoneCode); 
                        setUserCurrency(code);
                        setShowCountryPicker(false); 
                      }}
                      className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-left text-sm transition-colors ${
                        phoneCountryCode === config.phoneCode ? 'bg-cyan-500/20 text-cyan-300' : 'hover:bg-white/10 text-gray-300'
                      }`}
                    >
                      <span className="text-lg">{config.flag}</span>
                      <span className="flex-1">{config.name}</span>
                      <span className="font-mono text-gray-400">{config.phoneCode}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          <Button
            onClick={handleSubmitEmail}
            disabled={loading}
            className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white py-6 text-lg rounded-xl"
            data-testid="unlock-results-btn"
          >
            {loading ? 'Processing...' : 'View My Results'}
          </Button>
          
          <p className="text-xs text-gray-500">
            We respect your privacy. Your data is secure.
          </p>
        </motion.div>
      );
    }
    
    // Results (step 7)
    if (currentStep === totalQuestions + 2 && scanResult) {
      // Calculate potential earnings from started but not completed
      const pendingReferrals = referralStats.started - referralStats.completed;
      const potentialEarnings = pendingReferrals * 5;
      
      return (
        <>
          {/* Floating Referral Tracker - Always Visible with Live Stats */}
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-gradient-to-r from-green-600 to-emerald-600 shadow-2xl border-t-2 border-green-400"
          >
            <div className="max-w-md mx-auto p-3">
              {/* Top row - Stats */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className="text-white/70 text-xs">Started</p>
                    <p className="text-white font-bold text-lg">{referralStats.started}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-white/70 text-xs">Completed</p>
                    <p className="text-white font-bold text-lg">{referralStats.completed}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-white/70 text-xs">Points</p>
                    <p className="text-green-200 font-bold text-lg">{referralStats.completed * 60}/600</p>
                  </div>
                  {/* Potential earnings indicator */}
                  {pendingReferrals > 0 && (
                    <div className="text-center bg-yellow-500/30 rounded-lg px-2 py-1">
                      <p className="text-yellow-200/80 text-xs">Pending</p>
                      <p className="text-yellow-300 font-bold text-sm">+{pendingReferrals * 60} pts</p>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => {
                    const el = document.getElementById('referral-section');
                    if (el) el.scrollIntoView({ behavior: 'smooth' });
                  }}
                  className="bg-white text-green-700 px-3 py-1.5 rounded-full font-bold text-xs hover:bg-green-50 transition-all"
                >
                  Share
                </button>
              </div>
              
              {/* Progress bar */}
              <div className="w-full">
                <div className="flex justify-between text-xs text-white/80 mb-1">
                  <span>Progress: {referralStats.completed}/10 signups ({referralStats.completed * 60}/600 pts)</span>
                  <span>{referralStats.completed >= 10 ? '🎉 30% Discount Unlocked!' : `${10 - referralStats.completed} more to unlock 30%!`}</span>
                </div>
                <div className="w-full h-2 bg-white/20 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-white rounded-full transition-all duration-500"
                    style={{ width: `${Math.min((referralStats.completed / 10) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="space-y-5 pb-24"
          >
            {/* Bio-Age Score */}
            {/* Bio-Age Score - Hide when camera is open or photo is captured */}
            {!capturedPhoto && !showCamera && (
              <div className="text-center">
                <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/30 mb-3">
                  Your Bio-Age Report
                </Badge>
              
                <div className="relative w-36 h-36 mx-auto mb-4">
                  <svg className="w-full h-full transform -rotate-90">
                    <circle cx="72" cy="72" r="64" stroke="rgba(255,255,255,0.1)" strokeWidth="10" fill="none" />
                    <circle
                      cx="72" cy="72" r="64"
                      stroke="url(#gradient)"
                      strokeWidth="10" fill="none" strokeLinecap="round"
                      strokeDasharray={`${(scanResult.bioAgeOffset / 15) * 402} 402`}
                    />
                    <defs>
                      <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#06b6d4" />
                        <stop offset="100%" stopColor="#a855f7" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-4xl font-bold text-white">+{scanResult.bioAgeOffset}</span>
                    <span className="text-sm text-gray-400">years</span>
                  </div>
                </div>
              
                <Badge className={`${
                  scanResult.riskLevel === 'High' ? 'bg-red-500/20 text-red-300 border-red-500/30' :
                  scanResult.riskLevel === 'Moderate' ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' :
                  'bg-green-500/20 text-green-300 border-green-500/30'
                }`}>
                  {scanResult.riskLevel} Cellular Aging Risk
                </Badge>
              </div>
            )}
          
            {/* 🧬 FOUNDING MEMBER EXCLUSIVE OFFER - Success Page CTA */}
            {!capturedPhoto && !showCamera && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="bg-gradient-to-br from-amber-500/20 via-orange-500/20 to-amber-600/20 border-2 border-amber-500/50 rounded-2xl p-5 space-y-4 relative overflow-hidden"
              >
                {/* Decorative glow */}
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-amber-400/20 rounded-full blur-3xl" />
                <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-orange-400/20 rounded-full blur-3xl" />
                
                <div className="relative">
                  {/* Header */}
                  <div className="text-center mb-4">
                    <Badge className="bg-amber-500/30 text-amber-200 border-amber-500/50 mb-2">
                      <Dna className="w-3 h-3 mr-1" />
                      Bio-Age Analysis Complete
                    </Badge>
                    <h3 className="text-2xl font-bold text-white" style={{ fontFamily: '"Playfair Display", serif' }}>
                      Your Bio-Age Analysis is Complete 🧬
                    </h3>
                    <p className="text-amber-200/80 text-sm mt-2">
                      Based on your results, your skin is a <span className="font-semibold text-amber-100">prime candidate</span> for Biotech Recovery.
                    </p>
                  </div>
                  
                  {/* The Recommendation */}
                  <div className="bg-black/30 rounded-xl p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <Target className="w-5 h-5 text-amber-400" />
                      <span className="text-amber-100 font-semibold">Your Prescription:</span>
                    </div>
                    <p className="text-white text-sm">
                      To address your primary concern of <span className="font-bold text-amber-300">{
                        answers.primary_concern === 'dark_circles' ? 'Dark Circles' :
                        answers.primary_concern === 'aging' ? 'Fine Lines & Aging' :
                        answers.primary_concern === 'dullness' ? 'Dullness & Uneven Tone' :
                        answers.primary_concern === 'acne' ? 'Acne & Congestion' :
                        answers.primary_concern === 'sensitivity' ? 'Redness & Sensitivity' :
                        answers.primary_concern === 'hydration' ? 'Dryness & Dehydration' :
                        'Cellular Aging'
                      }</span>, our algorithm suggests the <span className="font-bold text-white">Aura-Gen PDRN Protocol</span>.
                    </p>
                  </div>
                  
                  {/* The Exclusive Offer */}
                  <div className="bg-gradient-to-r from-amber-600/30 to-orange-600/30 rounded-xl p-4 mt-4 border border-amber-400/30">
                    <div className="text-center">
                      <p className="text-amber-200/80 text-xs uppercase tracking-wider mb-2">
                        🎁 Diagnostic Scan Exclusive
                      </p>
                      <p className="text-white/90 text-sm mb-3">
                        Because you completed the diagnostic scan, you have been unlocked for <span className="font-bold text-amber-200">Founding Member Beta Pricing</span>.
                      </p>
                      
                      {/* Pricing Breakdown */}
                      <div className="space-y-2 mb-4">
                        <div className="flex justify-between items-center px-4">
                          <span className="text-gray-400 text-sm line-through">Current Retail Value:</span>
                          <span className="text-gray-400 line-through">{formatAmount(100)}</span>
                        </div>
                        <div className="flex justify-between items-center px-4">
                          <span className="text-green-300 text-sm">Your Diagnostic Subsidy:</span>
                          <span className="text-green-300 font-semibold">-{formatAmount(30)}</span>
                        </div>
                        <div className="h-px bg-amber-400/30 mx-4" />
                        <div className="flex justify-between items-center px-4">
                          <span className="text-white font-bold">Final Entry Price:</span>
                          <span className="text-3xl font-bold text-amber-300">{formatAmount(70)} CAD</span>
                        </div>
                      </div>
                      
                      <Button
                        onClick={() => {
                          // Pass referral code to Founding Member page for attribution
                          const params = new URLSearchParams();
                          if (referrerCode) params.set('ref', referrerCode);
                          if (userReferralCode) params.set('from_scan', userReferralCode);
                          params.set('concern', answers.primary_concern || 'aging');
                          navigate(`/founding-member${params.toString() ? '?' + params.toString() : ''}`);
                        }}
                        className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-black font-bold py-5 text-lg rounded-xl shadow-lg shadow-amber-500/30"
                        data-testid="founding-member-cta-btn"
                      >
                        <Crown className="w-5 h-5 mr-2" />
                        Claim My Founding Position & Shop Now
                        <ArrowRight className="w-5 h-5 ml-2" />
                      </Button>
                      
                      <p className="text-amber-200/60 text-xs mt-3 flex items-center justify-center gap-1">
                        <Lock className="w-3 h-3" />
                        Price locked forever • Cancel anytime
                      </p>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          
            {/* 📸 SHARE YOUR RESULTS - PROMINENT SECTION - Make this the first thing users see */}
            <div className="bg-gradient-to-br from-pink-500/20 via-purple-500/20 to-pink-500/20 border-2 border-pink-500/40 rounded-2xl p-5 space-y-4 animate-pulse-slow relative overflow-hidden">
              {/* Animated glow effect */}
              <div className="absolute -top-20 -right-20 w-40 h-40 bg-pink-500/30 rounded-full blur-3xl animate-pulse" />
              <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-purple-500/30 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '1s' }} />
              
              <div className="text-center relative z-10">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-pink-500 to-purple-500 flex items-center justify-center mx-auto mb-3 shadow-lg shadow-pink-500/30">
                  <Camera className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-xl font-bold text-white flex items-center justify-center gap-2">
                  📸 Share Your Results!
                </h3>
                <p className="text-pink-200 text-sm mt-1">Take a quick selfie with your Bio-Age score</p>
                <p className="text-white/60 text-xs mt-2">👇 Your friends will LOVE this!</p>
              </div>
            
            {/* Hidden canvas for image generation */}
            <canvas ref={canvasRef} className="hidden" />
            
            {/* Camera View */}
            {showCamera && (
              <div className="relative rounded-xl overflow-hidden">
                <video 
                  ref={videoRef} 
                  autoPlay 
                  playsInline 
                  muted
                  className="w-full aspect-square object-cover rounded-xl"
                  style={{ transform: 'scaleX(-1)' }}
                />
                {/* Analysis progress overlay */}
                {processingImage && analysisStep && (
                  <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center">
                    <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mb-3" />
                    <p className="text-white font-medium">{analysisStep}</p>
                    <p className="text-cyan-300 text-sm mt-1">AI analyzing your skin...</p>
                  </div>
                )}
                {!processingImage && (
                  <div className="absolute inset-0 flex items-end justify-center pb-4">
                    <div className="flex gap-3">
                      <Button
                        onClick={stopCamera}
                        variant="outline"
                        size="sm"
                        className="bg-black/50 border-white/30 text-white"
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={capturePhoto}
                        disabled={processingImage}
                        className="bg-gradient-to-r from-pink-500 to-purple-500 text-white px-6"
                      >
                        {processingImage ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
                      </Button>
                    </div>
                  </div>
                )}
                {/* Score overlay preview */}
                {!processingImage && (
                  <div className="absolute bottom-16 left-1/2 -translate-x-1/2 bg-black/60 px-4 py-2 rounded-full">
                    <span className="text-cyan-400 font-bold">+{scanResult.bioAgeOffset}</span>
                    <span className="text-white/60 text-sm ml-1">years</span>
                  </div>
                )}
              </div>
            )}
            
            {/* Captured Photo Preview */}
            {capturedPhoto && !showCamera && (
              <div className="space-y-3">
                <img 
                  src={capturedPhoto} 
                  alt="Your Bio-Age Result" 
                  className="w-full rounded-xl border-2 border-purple-500/50"
                />
                
                {/* Encouragement message */}
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 text-center">
                  <p className="text-green-300 text-sm font-medium">🎉 Ready to share!</p>
                  <p className="text-white/70 text-xs mt-1">Save your image and post it to inspire others!</p>
                </div>
                
                <div className="flex gap-2">
                  <Button
                    onClick={downloadShareableImage}
                    className="flex-1 bg-[#C9A86C] hover:bg-[#B8956B] text-black"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Save
                  </Button>
                  <Button
                    onClick={() => { setCapturedPhoto(null); setShareableImage(null); setFaceAnalysis(null); setRawPhoto(null); setSoulCompliment(''); }}
                    variant="outline"
                    className="border-white/20 text-white hover:bg-white/10"
                  >
                    Retake
                  </Button>
                </div>
              </div>
            )}
            
            {/* Take Selfie Button - LARGE AND PROMINENT */}
            {!showCamera && !capturedPhoto && (
              <div className="relative">
                <Button
                  onClick={startCamera}
                  className="w-full bg-gradient-to-r from-pink-500 via-purple-500 to-pink-500 hover:from-pink-600 hover:via-purple-600 hover:to-pink-600 py-6 rounded-xl text-lg font-bold shadow-lg shadow-pink-500/30 animate-shimmer"
                  data-testid="take-selfie-btn"
                >
                  <Camera className="w-6 h-6 mr-3" />
                  Take My Picture Now! 📸
                </Button>
                <p className="text-center text-pink-300/80 text-xs mt-2">
                  ⬆️ Tap to create your shareable image
                </p>
              </div>
            )}
            
            {/* Social Share Buttons - Share Image Directly */}
            {capturedPhoto && (
              <div className="pt-2 space-y-2">
                <div className="bg-green-500/20 border border-green-500/30 rounded-lg p-2 text-center">
                  <p className="text-green-300 text-xs font-medium">
                    ✅ Your referral link will be included automatically!
                  </p>
                </div>
                <p className="text-center text-xs text-white/60">Share your selfie + referral link:</p>
                <div className="grid grid-cols-4 gap-2">
                  <button
                    onClick={() => shareImageDirect('whatsapp')}
                    className="bg-green-500 hover:bg-green-600 text-white p-3 rounded-xl flex items-center justify-center transition-all hover:scale-105"
                  >
                    <MessageCircle className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => shareImageDirect('facebook')}
                    className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-xl flex items-center justify-center transition-all hover:scale-105"
                  >
                    <Facebook className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => shareImageDirect('twitter')}
                    className="bg-sky-500 hover:bg-sky-600 text-white p-3 rounded-xl flex items-center justify-center transition-all hover:scale-105"
                  >
                    <Twitter className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => shareImageDirect('telegram')}
                    className="bg-blue-500 hover:bg-blue-600 text-white p-3 rounded-xl flex items-center justify-center transition-all hover:scale-105"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )}
            
            {/* Original share links when no photo captured */}
            {!capturedPhoto && (
              <div className="pt-2">
                <p className="text-center text-xs text-white/60 mb-2">Share on:</p>
                <div className="grid grid-cols-4 gap-2">
                  {shareLinks.map((link) => {
                    const LinkIcon = link.icon;
                    return (
                      <a
                        key={link.name}
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`${link.color} text-white p-3 rounded-xl flex items-center justify-center transition-all hover:scale-105`}
                      >
                        <LinkIcon className="w-5 h-5" />
                      </a>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          
          {/* Brand Recommendation Card - Enhanced with Pre-Order Support */}
          {scanResult.recommendations.length > 0 && scanResult.recommendations[0].isBrandRec && (
            <div className={`bg-gradient-to-br ${scanResult.recommendations[0].brand.color} border border-white/20 rounded-2xl p-5 space-y-4`}>
              <div className="text-center">
                <span className="text-3xl">{scanResult.recommendations[0].brand.icon}</span>
                <p className="text-white/60 text-xs uppercase tracking-wider mt-2">Your Perfect Match</p>
                <h3 className="text-2xl font-bold text-white mt-1">{scanResult.recommendations[0].brand.name}</h3>
                <p className="text-white/80 text-sm italic">{scanResult.recommendations[0].brand.tagline}</p>
              </div>
              
              <div className="bg-black/20 rounded-xl p-4 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-white/70 text-sm">Recommended:</span>
                  <span className="text-white font-semibold">{scanResult.recommendations[0].brand.heroProduct}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white/70 text-sm">Key Ingredient:</span>
                  <span className="text-white font-semibold">{scanResult.recommendations[0].brand.keyIngredient}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white/70 text-sm">Price:</span>
                  <span className="text-white font-bold text-lg">{scanResult.recommendations[0].brand.price}</span>
                </div>
                {scanResult.recommendations[0].brand.isPreOrder && (
                  <div className="flex justify-between items-center bg-amber-500/20 rounded-lg px-3 py-2 mt-2">
                    <span className="text-amber-200 text-sm">Pre-Order:</span>
                    <span className="text-amber-100 font-semibold text-sm">{scanResult.recommendations[0].brand.preOrderDate}</span>
                  </div>
                )}
              </div>
              
              <p className="text-white/80 text-sm text-center">
                {scanResult.recommendations[0].brand.keyBenefit}
              </p>
              
              <Button
                onClick={() => navigate(scanResult.recommendations[0].brand.route)}
                className="w-full bg-white text-black hover:bg-white/90 py-4 text-base rounded-xl font-bold"
                data-testid="shop-brand-btn"
              >
                <ShoppingBag className="w-5 h-5 mr-2" />
                {scanResult.recommendations[0].brand.isPreOrder ? 'Pre-Order Now' : `Shop ${scanResult.recommendations[0].brand.heroProduct}`}
              </Button>
            </div>
          )}
          
          {/* Secondary Product Recommendation (Dual Protocol) */}
          {scanResult.recommendations.length > 1 && scanResult.recommendations[1].isBrandRec && scanResult.recommendations[1].isSecondary && (
            <div className={`bg-gradient-to-br ${scanResult.recommendations[1].brand.color} border border-white/10 rounded-2xl p-4 space-y-3`}>
              <div className="flex items-center gap-3">
                <span className="text-2xl">{scanResult.recommendations[1].brand.icon}</span>
                <div>
                  <p className="text-white/60 text-xs uppercase tracking-wider">Complete Your Protocol</p>
                  <h4 className="text-lg font-bold text-white">{scanResult.recommendations[1].brand.heroProduct}</h4>
                </div>
              </div>
              
              <p className="text-white/70 text-sm">{scanResult.recommendations[1].text}</p>
              
              <div className="flex items-center justify-between">
                <span className="text-white font-semibold">{scanResult.recommendations[1].brand.price}</span>
                {scanResult.recommendations[1].brand.isPreOrder && (
                  <span className="text-amber-300 text-xs bg-amber-500/20 px-2 py-1 rounded">Pre-Order</span>
                )}
              </div>
              
              <Button
                onClick={() => navigate(scanResult.recommendations[1].brand.route)}
                variant="outline"
                className="w-full border-white/30 text-white hover:bg-white/10 py-3 rounded-xl"
                data-testid="shop-secondary-btn"
              >
                {scanResult.recommendations[1].brand.isPreOrder ? 'Pre-Order' : 'Add to Protocol'}
              </Button>
            </div>
          )}
          
          {/* Other Recommendations */}
          {scanResult.recommendations.filter(rec => !rec.isBrandRec).slice(0, 2).map((rec, idx) => {
            const RecIcon = rec.icon;
            return (
              <div key={idx} className="bg-white/5 border border-white/10 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center shrink-0">
                    <RecIcon className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <h4 className="font-medium text-white">{rec.title}</h4>
                    <p className="text-sm text-gray-400 mt-1">{rec.text}</p>
                  </div>
                </div>
              </div>
            );
          })}
          
          {/* 🎁 SIGN UP TO REDEEM - Show prominently when goal is reached */}
          {canRedeem && (
            <div className="bg-gradient-to-br from-purple-500/30 to-pink-500/30 border-2 border-purple-400 rounded-2xl p-5 text-center space-y-3 animate-pulse-slow">
              <div className="w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center mx-auto shadow-lg shadow-purple-500/30">
                <Gift className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white">🎉 Congratulations!</h3>
              <p className="text-purple-200">
                You&apos;ve unlocked <span className="font-bold text-green-300 text-xl">30% Discount</span> with {referralStats.completed * 60} points!
              </p>
              <Button
                onClick={() => navigate('/login?signup=true&from=bio-scan&discount=30')}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 py-6 text-lg rounded-xl font-bold shadow-lg shadow-purple-500/30"
                data-testid="redeem-btn"
              >
                <UserPlus className="w-6 h-6 mr-2" />
                Sign Up & Claim 30% Off
              </Button>
              <p className="text-xs text-gray-400">
                Create your account to claim your discount! 🛍️
              </p>
            </div>
          )}
          
          {/* HOW IT WORKS - Education Section */}
          <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 border border-amber-500/30 rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-2 justify-center">
              <AlertCircle className="w-5 h-5 text-amber-400" />
              <h3 className="text-base font-bold text-white">⚡ How To Unlock 30% Discount</h3>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-start gap-3 bg-black/20 rounded-lg p-3">
                <div className="w-6 h-6 rounded-full bg-amber-500 flex items-center justify-center shrink-0 text-xs font-bold text-black">1</div>
                <div>
                  <p className="text-white text-sm font-medium">Copy YOUR unique link below</p>
                  <p className="text-amber-200/70 text-xs">Not the link you received - YOUR OWN link!</p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-black/20 rounded-lg p-3">
                <div className="w-6 h-6 rounded-full bg-amber-500 flex items-center justify-center shrink-0 text-xs font-bold text-black">2</div>
                <div>
                  <p className="text-white text-sm font-medium">Get 10 successful signups</p>
                  <p className="text-amber-200/70 text-xs">1 reference = 60 points (Total: 600 points)</p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-black/20 rounded-lg p-3">
                <div className="w-6 h-6 rounded-full bg-amber-500 flex items-center justify-center shrink-0 text-xs font-bold text-black">3</div>
                <div>
                  <p className="text-white text-sm font-medium">Unlock 30% discount on your next order!</p>
                  <p className="text-amber-200/70 text-xs">They must finish & enter their email/phone</p>
                </div>
              </div>
            </div>
            
            <div className="bg-red-500/20 border border-red-500/40 rounded-lg p-2 text-center">
              <p className="text-red-300 text-xs font-medium">
                ⚠️ Don&apos;t share the link you received! Only YOUR link below earns you points.
              </p>
            </div>
          </div>
          
          {/* SHARE YOUR LINK NOW - Shows after photo is taken */}
          {showReferralAfterPhoto && capturedPhoto && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-r from-green-500 to-emerald-500 rounded-2xl p-4 text-center shadow-lg shadow-green-500/30"
            >
              <p className="text-white font-bold text-lg">📸 Great photo! Now share your link! 👇</p>
              <p className="text-green-100 text-sm mt-1">Your friends will see your result when they click</p>
            </motion.div>
          )}
          
          {/* REFERRAL DASHBOARD */}
          <div id="referral-section" className={`bg-gradient-to-br from-green-500/20 to-emerald-500/20 border rounded-2xl p-5 space-y-4 transition-all duration-500 ${showReferralAfterPhoto ? 'border-2 border-green-400 shadow-lg shadow-green-500/20' : 'border-green-500/30'}`}>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-green-500/30 flex items-center justify-center mx-auto mb-2">
                <TrendingUp className="w-6 h-6 text-green-300" />
              </div>
              <h3 className="text-lg font-bold text-white">Your Referral Dashboard</h3>
              <p className="text-green-200 text-xs">Live tracking • Updates every 10 seconds</p>
            </div>
            
            {/* Live Stats with Potential Earnings */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-black/30 rounded-xl p-3 text-center">
                <Users className="w-4 h-4 text-blue-400 mx-auto mb-1" />
                <p className="text-xl font-bold text-white">{referralStats.started}</p>
                <p className="text-xs text-gray-400">Started</p>
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-center">
                <CheckCircle className="w-4 h-4 text-green-400 mx-auto mb-1" />
                <p className="text-xl font-bold text-white">{referralStats.completed}</p>
                <p className="text-xs text-gray-400">Signups</p>
              </div>
              <div className="bg-black/30 rounded-xl p-3 text-center">
                <Zap className="w-4 h-4 text-yellow-400 mx-auto mb-1" />
                <p className="text-xl font-bold text-green-400">{referralStats.completed * 60}</p>
                <p className="text-xs text-gray-400">Points</p>
              </div>
            </div>
            
            {/* Potential Earnings - Show when there are started but not completed */}
            {referralStats.started > referralStats.completed && (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2 text-center">
                <p className="text-yellow-300 text-sm">
                  ⚡ <span className="font-bold">{(referralStats.started - referralStats.completed) * 60} points</span> pending if {referralStats.started - referralStats.completed} friend{referralStats.started - referralStats.completed > 1 ? 's' : ''} complete the quiz!
                </p>
              </div>
            )}
            
            {/* Progress */}
            <div className="bg-black/30 rounded-xl p-3">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">Progress to 30% Discount</span>
                <span className="text-green-300 font-medium">{referralStats.completed * 60}/600 points</span>
              </div>
              <Progress value={Math.min((referralStats.completed / 10) * 100, 100)} className="h-2 bg-white/10" />
              <p className="text-xs text-gray-500 mt-2 text-center">
                {referralStats.completed >= 10 
                  ? "🎉 30% Discount Unlocked! Sign up to redeem!" 
                  : `${10 - referralStats.completed} more signups to unlock 30% discount!`}
              </p>
            </div>
            
            {/* YOUR UNIQUE LINK - Made Very Prominent */}
            <div className="space-y-2">
              <div className="bg-green-500/30 border-2 border-green-400 rounded-lg p-2 text-center animate-pulse">
                <p className="text-green-300 text-sm font-bold">👇 YOUR UNIQUE LINK - Share THIS one! 👇</p>
              </div>
              <div className="flex gap-2">
                <Input
                  value={shareUrl}
                  readOnly
                  className="bg-black/30 border-2 border-green-500/50 text-white text-xs h-12 font-mono"
                />
                <Button
                  onClick={handleCopy}
                  variant="outline"
                  size="sm"
                  className="shrink-0 border-green-500 bg-green-500/20 text-green-300 hover:bg-green-500/40 h-12 px-4"
                >
                  {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                </Button>
              </div>
              <p className="text-center text-xs text-gray-400">
                Your code: <span className="font-mono text-green-400 font-bold">{userReferralCode}</span>
              </p>
              
              {/* Social Share Buttons for Referral */}
              <p className="text-center text-xs text-white/60 pt-2">Quick share:</p>
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => window.open(`https://wa.me/?text=${encodeURIComponent(`🧬 I just took this Bio-Age Skin Quiz! Find out your skin's REAL age:\n\n${shareUrl}\n\nIt only takes 60 seconds! 💫\n\n#ReRoots #BioAgeScan #SkinCare #GlowUp #SelfCare`)}`, '_blank')}
                  className="w-12 h-12 rounded-full bg-green-500 hover:bg-green-600 flex items-center justify-center transition-all hover:scale-110"
                >
                  <MessageCircle className="w-6 h-6 text-white" />
                </button>
                <button
                  onClick={() => window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}&quote=${encodeURIComponent('🧬 Take the Bio-Age Skin Quiz! #ReRoots #BioAgeScan #SkinCare')}`, '_blank')}
                  className="w-12 h-12 rounded-full bg-blue-600 hover:bg-blue-700 flex items-center justify-center transition-all hover:scale-110"
                >
                  <Facebook className="w-6 h-6 text-white" />
                </button>
                <button
                  onClick={() => window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(`🧬 Take the Bio-Age Skin Quiz! Discover your skin's real age: ${shareUrl}\n\n#ReRoots #BioAgeScan #SkinCare #GlowUp`)}`, '_blank')}
                  className="w-12 h-12 rounded-full bg-sky-500 hover:bg-sky-600 flex items-center justify-center transition-all hover:scale-110"
                >
                  <Twitter className="w-6 h-6 text-white" />
                </button>
                <button
                  onClick={() => window.open(`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent('🧬 Take the Bio-Age Skin Quiz!\n\n#ReRoots #BioAgeScan #SkinCare #GlowUp')}`, '_blank')}
                  className="w-12 h-12 rounded-full bg-blue-500 hover:bg-blue-600 flex items-center justify-center transition-all hover:scale-110"
                >
                  <Send className="w-6 h-6 text-white" />
                </button>
              </div>
            </div>
          </div>
          
          {/* SIGN UP TO REDEEM - Only show after 10 referrals */}
          {canRedeem ? (
            <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 border-2 border-purple-500/40 rounded-2xl p-5 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-purple-500/30 flex items-center justify-center mx-auto">
                <Gift className="w-6 h-6 text-purple-300" />
              </div>
              <h3 className="text-xl font-bold text-white">Congratulations!</h3>
              <p className="text-purple-200 text-sm">
                You&apos;ve unlocked <span className="font-bold text-green-300">30% Discount</span> with {referralStats.completed * 60} points!
              </p>
              <Button
                onClick={() => navigate('/login?signup=true&from=bio-scan&discount=30')}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 py-5 text-base rounded-xl"
              >
                <UserPlus className="w-5 h-5 mr-2" />
                Sign Up & Claim 30% Off
              </Button>
              <p className="text-xs text-gray-400">
                * Tax & shipping apply at checkout
              </p>
            </div>
          ) : (
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <p className="text-gray-400 text-sm">
                Get <span className="text-green-300 font-bold">{10 - referralStats.completed} more signups</span> to unlock 30% discount! ({(10 - referralStats.completed) * 60} more pts)
              </p>
            </div>
          )}
        </motion.div>
        </>
      );
    }
    
    return null;
  };
  
  return (
    <>
      <Helmet>
        <title>🧬 Bio-Age Skin Quiz | How Old Is Your Skin Really?</title>
        <meta name="description" content="Take our 60-second quiz to discover your skin's REAL biological age. Share & unlock 30% discount!" />
        
        {/* Open Graph for WhatsApp, Facebook, etc. */}
        <meta property="og:type" content="website" />
        <meta property="og:title" content="🧬 Bio-Age Skin Quiz - How Old Is Your Skin?" />
        <meta property="og:description" content="Take this 60-second quiz to discover your skin's REAL biological age! 🔬 See if your skin is aging faster than you. Share & unlock 30% off!" />
        <meta property="og:url" content="https://reroots.ca/Bio-Age-Repair-Scan" />
        <meta property="og:image" content="https://static.prod-images.emergentagent.com/jobs/152b37c3-2aad-48f3-9f9e-f8d67e2eff9a/images/c3ac33107642e567d63840f95aab09e2d23094545b0c8e4c8da2b9e32fe1990c.png" />
        <meta property="og:image:width" content="1536" />
        <meta property="og:image:height" content="1024" />
        
        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="🧬 Bio-Age Skin Quiz - How Old Is Your Skin?" />
        <meta property="og:description" content="Take this 60-second quiz to discover your skin's REAL biological age! 🔬 Unlock 30% discount!" />
        <meta name="twitter:image" content="https://static.prod-images.emergentagent.com/jobs/152b37c3-2aad-48f3-9f9e-f8d67e2eff9a/images/c3ac33107642e567d63840f95aab09e2d23094545b0c8e4c8da2b9e32fe1990c.png" />
      </Helmet>
      
      <div className="min-h-screen bg-[#0a0a0a] relative overflow-hidden">
        {/* Background */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-80 h-80 rounded-full bg-cyan-500/10 blur-[100px]" />
          <div className="absolute bottom-1/4 right-1/4 w-64 h-64 rounded-full bg-purple-500/10 blur-[80px]" />
        </div>
        
        {/* Grid */}
        <div 
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}
        />
        
        {/* Header - Only show brand AFTER quiz is completed */}
        <header className="relative z-10 p-4">
          <div className="flex items-center justify-between max-w-lg mx-auto">
            {isQuizCompleted ? (
              <a href="/" className="text-white font-display text-lg">
                ReRoots<span className="text-cyan-400">.</span>
              </a>
            ) : (
              <div className="flex items-center gap-2">
                <Dna className="w-5 h-5 text-cyan-400" />
                <span className="text-white font-medium text-sm">Bio-Age Scan</span>
              </div>
            )}
            
            {currentStep > 0 && currentStep <= totalQuestions && (
              <Badge className="bg-green-500/20 text-green-300 border-green-500/30 text-xs">
                <Gift className="w-3 h-3 mr-1" />
                Unlock 30% Off
              </Badge>
            )}
          </div>
        </header>
        
        {/* Main */}
        <main className="relative z-10 px-4 pb-8">
          <div className="max-w-lg mx-auto">
            <AnimatePresence mode="wait">
              {renderStep()}
            </AnimatePresence>
          </div>
        </main>
      </div>
      
      {/* 🎉 CELEBRATION POPUP - Shows when 10+ referrals completed */}
      <AnimatePresence>
        {showRedeemPopup && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={() => setShowRedeemPopup(false)}
          >
            <motion.div
              initial={{ scale: 0.5, opacity: 0, y: 50 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.5, opacity: 0, y: 50 }}
              transition={{ type: "spring", damping: 15 }}
              className="bg-gradient-to-br from-[#1a1a2e] to-[#16213e] border-2 border-purple-500/50 rounded-3xl p-6 max-w-sm w-full text-center space-y-4 shadow-2xl shadow-purple-500/20"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Confetti Animation */}
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 text-6xl animate-bounce">
                🎉
              </div>
              
              {/* Trophy/Gift Icon */}
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-yellow-400 to-amber-500 flex items-center justify-center mx-auto shadow-lg shadow-yellow-500/30 mt-4">
                <Gift className="w-10 h-10 text-white" />
              </div>
              
              {/* Title */}
              <div>
                <h2 className="text-2xl font-bold text-white">
                  Congratulations! 🏆
                </h2>
                <p className="text-purple-300 text-sm mt-1">
                  You've unlocked 30% discount!
                </p>
              </div>
              
              {/* Amount Earned */}
              <div className="bg-green-500/20 border border-green-500/30 rounded-2xl p-4">
                <p className="text-green-400 text-sm">You've earned</p>
                <p className="text-4xl font-bold text-green-300 mt-1">
                  {referralStats.completed * 60} pts
                </p>
                <p className="text-green-400/70 text-xs mt-1">30% Discount Unlocked!</p>
              </div>
              
              {/* Stats */}
              <div className="flex justify-center gap-6 text-center">
                <div>
                  <p className="text-2xl font-bold text-white">{referralStats.completed}</p>
                  <p className="text-xs text-gray-400">Successful Signups</p>
                </div>
                <div className="w-px bg-white/10" />
                <div>
                  <p className="text-2xl font-bold text-purple-300">{referralStats.started}</p>
                  <p className="text-xs text-gray-400">Total Clicks</p>
                </div>
              </div>
              
              {/* CTA Button */}
              <Button
                onClick={() => {
                  setShowRedeemPopup(false);
                  navigate('/login?signup=true&from=bio-scan&discount=30');
                }}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 py-6 text-lg rounded-xl font-bold shadow-lg"
                data-testid="popup-redeem-btn"
              >
                <UserPlus className="w-5 h-5 mr-2" />
                Sign Up & Claim 30% Off
              </Button>
              
              {/* Later Link */}
              <button
                onClick={() => setShowRedeemPopup(false)}
                className="text-gray-400 text-sm hover:text-white transition-colors"
              >
                I'll do this later
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default BioAgeScanPage;
