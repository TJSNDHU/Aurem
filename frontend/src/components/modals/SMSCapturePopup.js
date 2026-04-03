import React, { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { X, Gift, Phone, Loader2, CheckCircle, Sparkles, ShoppingBag, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import axios from 'axios';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Country codes for phone number dropdown
const COUNTRY_CODES = [
  { code: '+1', country: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: '+1', country: 'US', name: 'United States', flag: '🇺🇸' },
  { code: '+44', country: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: '+91', country: 'IN', name: 'India', flag: '🇮🇳' },
  { code: '+61', country: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: '+49', country: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: '+33', country: 'FR', name: 'France', flag: '🇫🇷' },
  { code: '+39', country: 'IT', name: 'Italy', flag: '🇮🇹' },
  { code: '+34', country: 'ES', name: 'Spain', flag: '🇪🇸' },
  { code: '+31', country: 'NL', name: 'Netherlands', flag: '🇳🇱' },
  { code: '+55', country: 'BR', name: 'Brazil', flag: '🇧🇷' },
  { code: '+52', country: 'MX', name: 'Mexico', flag: '🇲🇽' },
  { code: '+81', country: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: '+82', country: 'KR', name: 'South Korea', flag: '🇰🇷' },
  { code: '+86', country: 'CN', name: 'China', flag: '🇨🇳' },
  { code: '+65', country: 'SG', name: 'Singapore', flag: '🇸🇬' },
  { code: '+971', country: 'AE', name: 'UAE', flag: '🇦🇪' },
  { code: '+966', country: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' },
  { code: '+27', country: 'ZA', name: 'South Africa', flag: '🇿🇦' },
  { code: '+234', country: 'NG', name: 'Nigeria', flag: '🇳🇬' },
  { code: '+254', country: 'KE', name: 'Kenya', flag: '🇰🇪' },
  { code: '+63', country: 'PH', name: 'Philippines', flag: '🇵🇭' },
  { code: '+92', country: 'PK', name: 'Pakistan', flag: '🇵🇰' },
  { code: '+880', country: 'BD', name: 'Bangladesh', flag: '🇧🇩' },
  { code: '+62', country: 'ID', name: 'Indonesia', flag: '🇮🇩' },
  { code: '+60', country: 'MY', name: 'Malaysia', flag: '🇲🇾' },
  { code: '+66', country: 'TH', name: 'Thailand', flag: '🇹🇭' },
  { code: '+84', country: 'VN', name: 'Vietnam', flag: '🇻🇳' },
  { code: '+7', country: 'RU', name: 'Russia', flag: '🇷🇺' },
  { code: '+48', country: 'PL', name: 'Poland', flag: '🇵🇱' },
  { code: '+46', country: 'SE', name: 'Sweden', flag: '🇸🇪' },
  { code: '+47', country: 'NO', name: 'Norway', flag: '🇳🇴' },
  { code: '+45', country: 'DK', name: 'Denmark', flag: '🇩🇰' },
  { code: '+358', country: 'FI', name: 'Finland', flag: '🇫🇮' },
  { code: '+41', country: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: '+43', country: 'AT', name: 'Austria', flag: '🇦🇹' },
  { code: '+32', country: 'BE', name: 'Belgium', flag: '🇧🇪' },
  { code: '+351', country: 'PT', name: 'Portugal', flag: '🇵🇹' },
  { code: '+30', country: 'GR', name: 'Greece', flag: '🇬🇷' },
  { code: '+353', country: 'IE', name: 'Ireland', flag: '🇮🇪' },
  { code: '+64', country: 'NZ', name: 'New Zealand', flag: '🇳🇿' },
  { code: '+20', country: 'EG', name: 'Egypt', flag: '🇪🇬' },
  { code: '+972', country: 'IL', name: 'Israel', flag: '🇮🇱' },
  { code: '+90', country: 'TR', name: 'Turkey', flag: '🇹🇷' },
];

// Phone capture popup - Shows on exit intent to capture phone for SMS offers
// Works on ALL pages including product pages - automatically applies to new products
const SMSCapturePopup = () => {
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(false);
  const [hasShown, setHasShown] = useState(false);
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [smsPopupEnabled, setSmsPopupEnabled] = useState(true);
  const [currentProduct, setCurrentProduct] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [selectedCountry, setSelectedCountry] = useState(COUNTRY_CODES[0]); // Default to Canada
  const [showCountryDropdown, setShowCountryDropdown] = useState(false);
  
  // Get session ID from localStorage (same as CartContext uses)
  useEffect(() => {
    try {
      const storedSession = localStorage.getItem('reroots_session_id');
      if (storedSession) {
        setSessionId(storedSession);
      }
    } catch (e) {
      console.log('[SMS Popup] Could not get session ID');
    }
  }, []);
  
  // Pages where popup should NOT appear (admin, checkout, login areas)
  // Product pages (/product/*, /shop/*) ARE included - popup shows there
  const excludedPaths = ['/checkout', '/admin', '/login', '/account', '/oroe', '/la-vela-bianca', '/lavela'];
  const shouldHideOnPath = excludedPaths.some(path => 
    location.pathname.toLowerCase().startsWith(path.toLowerCase())
  );
  
  // Check if we're on a product page
  const isProductPage = location.pathname.startsWith('/product/') || 
                        location.pathname.match(/^\/shop\/[^/]+$/);
  
  // Format phone number as user types
  const formatPhoneNumber = (value) => {
    const digits = value.replace(/\D/g, '');
    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
  };
  
  const handlePhoneChange = (e) => {
    const formatted = formatPhoneNumber(e.target.value);
    setPhone(formatted);
  };
  
  // Fetch current product info if on product page
  useEffect(() => {
    if (isProductPage) {
      const slug = location.pathname.split('/').pop();
      // Try to get product name from page title or fetch from API
      const titleEl = document.querySelector('h1');
      if (titleEl) {
        setCurrentProduct({ name: titleEl.textContent });
      }
    } else {
      setCurrentProduct(null);
    }
  }, [location.pathname, isProductPage]);
  
  // Close country dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (showCountryDropdown && !e.target.closest('[data-testid="country-code-selector"]') && !e.target.closest('.country-dropdown')) {
        setShowCountryDropdown(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [showCountryDropdown]);
  
  // Check if popup should be enabled
  useEffect(() => {
    const checkSettings = async () => {
      try {
        const res = await fetch(`${API}/store-settings`);
        const data = await res.json();
        // Default to enabled unless explicitly disabled
        setSmsPopupEnabled(data.sms_popup_enabled !== false);
      } catch {
        setSmsPopupEnabled(true);
      }
    };
    checkSettings();
  }, []);
  
  // Exit intent detection
  useEffect(() => {
    if (shouldHideOnPath || !smsPopupEnabled) return;
    
    // Check if already shown in this session
    const shown = sessionStorage.getItem('sms_popup_shown');
    // Check if user already subscribed
    const subscribed = localStorage.getItem('sms_subscribed');
    
    if (shown || subscribed) {
      setHasShown(true);
      return;
    }
    
    // Desktop: Mouse leave detection
    const handleMouseLeave = (e) => {
      if (e.clientY <= 10 && !hasShown) {
        setIsVisible(true);
        setHasShown(true);
        sessionStorage.setItem('sms_popup_shown', 'true');
      }
    };
    
    // Mobile: Back button / scroll up detection (simplified)
    let lastScrollY = window.scrollY;
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      // User scrolled up significantly near top of page - might be leaving
      if (currentScrollY < 100 && lastScrollY - currentScrollY > 50 && !hasShown) {
        // Only trigger after some engagement (scrolled down at least 300px)
        if (lastScrollY > 300) {
          setIsVisible(true);
          setHasShown(true);
          sessionStorage.setItem('sms_popup_shown', 'true');
        }
      }
      lastScrollY = currentScrollY;
    };
    
    // Delay before activating (let user browse first)
    const timer = setTimeout(() => {
      document.addEventListener('mouseleave', handleMouseLeave);
      window.addEventListener('scroll', handleScroll, { passive: true });
    }, 8000); // 8 seconds delay
    
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('scroll', handleScroll);
    };
  }, [hasShown, shouldHideOnPath, smsPopupEnabled]);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const phoneDigits = phone.replace(/\D/g, '');
    if (phoneDigits.length < 7) {
      toast.error('Please enter a valid phone number');
      return;
    }
    
    setLoading(true);
    try {
      // Format phone with selected country code
      const formattedPhone = `${selectedCountry.code}${phoneDigits}`;
      
      // Submit to backend
      await axios.post(`${API}/sms-subscribers`, {
        phone: formattedPhone,
        email: email || null,
        source: isProductPage ? 'product_page_popup' : 'exit_popup',
        page_url: location.pathname,
        product_name: currentProduct?.name || null,
        country_code: selectedCountry.code,
        country: selectedCountry.country
      });
      
      // Also link to abandoned cart if we have a session
      if (sessionId) {
        try {
          await axios.post(`${API}/checkout/track-contact`, {
            session_id: sessionId,
            phone: formattedPhone,
            email: email || null,
            checkout_step: 'browsing'
          });
          console.log('[SMS Popup] Phone linked to cart for abandoned cart recovery');
        } catch (err) {
          console.log('[SMS Popup] Could not link to cart (non-critical)');
        }
      }
      
      setSuccess(true);
      localStorage.setItem('sms_subscribed', 'true');
      toast.success('You\'re in! Check your phone for a special offer.');
      
      // Auto close after success
      setTimeout(() => {
        setIsVisible(false);
      }, 3000);
      
    } catch (error) {
      console.error('SMS signup error:', error);
      if (error.response?.status === 409) {
        toast.info('You\'re already subscribed!');
        localStorage.setItem('sms_subscribed', 'true');
        setSuccess(true);
      } else {
        toast.error('Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };
  
  const handleClose = () => {
    setIsVisible(false);
  };
  
  if (shouldHideOnPath || !isVisible || !smsPopupEnabled) return null;
  
  return (
    <div 
      className="fixed inset-0 z-[80] flex items-center justify-center p-4 animate-in fade-in duration-300"
      onClick={handleClose}
      data-testid="sms-capture-popup"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      
      {/* Modal */}
      <div
        className="relative w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 bg-white"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-3 right-3 w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors z-10"
          data-testid="sms-popup-close"
        >
          <X className="h-4 w-4 text-gray-600" />
        </button>
        
        {/* Decorative header */}
        <div className="bg-gradient-to-r from-[#F8A5B8] to-[#E88DA0] p-6 text-center">
          <div className="w-16 h-16 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center mx-auto mb-4">
            {success ? (
              <CheckCircle className="w-8 h-8 text-white" />
            ) : isProductPage ? (
              <ShoppingBag className="w-8 h-8 text-white" />
            ) : (
              <Gift className="w-8 h-8 text-white" />
            )}
          </div>
          <h2 className="text-2xl font-bold text-white mb-1">
            {success ? 'You\'re In!' : isProductPage ? 'Interested in This?' : 'Wait! Don\'t Miss Out'}
          </h2>
          <p className="text-white/90 text-sm">
            {success 
              ? 'Check your phone for your discount code' 
              : isProductPage 
                ? 'Get 10% OFF this product right now!'
                : 'Get 10% OFF your first order'}
          </p>
        </div>
        
        {/* Content */}
        <div className="p-6">
          {success ? (
            <div className="text-center py-4">
              <div className="flex items-center justify-center gap-2 text-green-600 mb-3">
                <Sparkles className="w-5 h-5" />
                <span className="font-semibold">Discount code sent!</span>
              </div>
              <p className="text-gray-600 text-sm">
                We've sent a special 10% discount code to your phone. 
                {isProductPage && currentProduct?.name && (
                  <> Use it on <strong>{currentProduct.name}</strong>!</>
                )}
                {!isProductPage && ' Use it on your next purchase!'}
              </p>
            </div>
          ) : (
            <>
              <p className="text-gray-600 text-center mb-6">
                {isProductPage ? (
                  <>Get your <strong>instant 10% discount code</strong> for this product. Plus, receive exclusive SMS-only offers and flash sales!</>
                ) : (
                  <>Enter your phone number to receive exclusive SMS-only offers, flash sales, and your <strong>instant 10% discount code</strong>.</>
                )}
              </p>
              
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Phone Number - Primary */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone Number *
                  </label>
                  <div className="flex gap-2">
                    {/* Country Code Dropdown */}
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowCountryDropdown(!showCountryDropdown)}
                        className="flex items-center gap-1 h-12 px-3 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors min-w-[90px]"
                        data-testid="country-code-selector"
                      >
                        <span className="text-lg">{selectedCountry.flag}</span>
                        <span className="text-sm font-medium text-gray-700">{selectedCountry.code}</span>
                        <ChevronDown className="w-3 h-3 text-gray-500" />
                      </button>
                      
                      {/* Dropdown Menu */}
                      {showCountryDropdown && (
                        <div className="country-dropdown absolute top-full left-0 mt-1 w-64 max-h-60 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                          {COUNTRY_CODES.map((country, idx) => (
                            <button
                              key={`${country.code}-${country.country}-${idx}`}
                              type="button"
                              onClick={() => {
                                setSelectedCountry(country);
                                setShowCountryDropdown(false);
                              }}
                              className={`w-full flex items-center gap-3 px-3 py-2 hover:bg-gray-50 text-left ${
                                selectedCountry.code === country.code && selectedCountry.country === country.country
                                  ? 'bg-pink-50'
                                  : ''
                              }`}
                            >
                              <span className="text-lg">{country.flag}</span>
                              <span className="text-sm text-gray-800">{country.name}</span>
                              <span className="text-sm text-gray-500 ml-auto">{country.code}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    
                    {/* Phone Input */}
                    <div className="relative flex-1">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                        <Phone className="w-4 h-4" />
                      </span>
                      <Input
                        type="tel"
                        value={phone}
                        onChange={handlePhoneChange}
                        placeholder={selectedCountry.country === 'CA' || selectedCountry.country === 'US' ? "(416) 555-0123" : "Phone number"}
                        className="pl-10 h-12 text-lg"
                        required
                        autoFocus
                        data-testid="sms-popup-phone"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {selectedCountry.name} ({selectedCountry.code}) - Tap to change country
                  </p>
                </div>
                
                {/* Email - Optional */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email (optional)
                  </label>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="h-11"
                    data-testid="sms-popup-email"
                  />
                </div>
                
                {/* Submit Button */}
                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full h-12 bg-[#2D2A2E] hover:bg-[#1a1819] text-white text-lg font-semibold"
                  data-testid="sms-popup-submit"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      Get My 10% Discount
                    </>
                  )}
                </Button>
                
                {/* Trust signals */}
                <p className="text-xs text-gray-400 text-center">
                  No spam, unsubscribe anytime. By signing up, you agree to receive 
                  marketing messages. Msg & data rates may apply.
                </p>
              </form>
            </>
          )}
        </div>
        
        {/* Skip button */}
        {!success && (
          <div className="px-6 pb-4">
            <button 
              onClick={handleClose}
              className="w-full text-center text-sm text-gray-400 hover:text-gray-600 transition-colors py-2"
              data-testid="sms-popup-skip"
            >
              No thanks, I'll pay full price
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SMSCapturePopup;
