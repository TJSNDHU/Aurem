import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Helmet } from 'react-helmet-async';
import { useCart } from '../../contexts';
import { useAuth } from '../../contexts';
import { useCurrency } from '../../contexts';
import { useStoreSettings } from '../../contexts';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Separator } from '../ui/separator';
import { Badge } from '../ui/badge';
import { Checkbox } from '../ui/checkbox';
import { 
  Loader2, MapPin, Shield, Gift, Truck, Check, X, Globe, 
  Crown, Users, Tag, AlertTriangle, Lock, Sparkles, Coins, Zap
} from 'lucide-react';
import { Progress } from '../ui/progress';
// PayPal SDK v6 - Modern buttons approach
import PayPalSDKv6Buttons from '../checkout/PayPalSDKv6Buttons';

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
const PAYPAL_CLIENT_ID = process.env.REACT_APP_PAYPAL_CLIENT_ID;

// Points system constants - values come from loyalty config API but these are defaults for display
const POINTS_PER_REFERRAL = 60; // 60 points per successful referral

const CheckoutPage = () => {
  const { cart, subtotal, sessionId, clearCart, loading: cartLoading } = useCart();
  const { user } = useAuth();
  const { formatPrice } = useCurrency();
  const { settings: storeSettings } = useStoreSettings();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState(null); // Will be set based on enabled methods
  const [discountCode, setDiscountCode] = useState("");
  const [appliedDiscount, setAppliedDiscount] = useState(null);
  const [appliedDiscounts, setAppliedDiscounts] = useState([]);
  const [applyingDiscount, setApplyingDiscount] = useState(false);
  const [bamboraCard, setBamboraCard] = useState({ number: '', name: '', expiry_month: '', expiry_year: '', cvv: '' });
  
  // Payment settings from store
  const paymentSettings = storeSettings?.payment || {};
  const bamboraEnabled = paymentSettings.bambora_enabled !== false;
  const etransferEnabled = paymentSettings.etransfer_enabled !== false;
  const paypalApiEnabled = paymentSettings.paypal_api_enabled === true && !!PAYPAL_CLIENT_ID;
  const paypalEnabled = paypalApiEnabled; // Only API mode now
  const etransferEmail = paymentSettings.etransfer_email || 'admin@reroots.ca';
  const paypalEmail = paymentSettings.paypal_email || 'admin@reroots.ca';
  const etransferInstructions = paymentSettings.etransfer_instructions || '';
  const paypalLinkUrl = paymentSettings.paypal_link_url || ''; // Legacy manual PayPal link (if configured)

  // Set default payment method based on what's enabled
  useEffect(() => {
    if (!paymentMethod) {
      if (bamboraEnabled) setPaymentMethod('bambora');
      else if (etransferEnabled) setPaymentMethod('etransfer');
      else if (paypalEnabled) setPaymentMethod('paypal');
    }
  }, [bamboraEnabled, etransferEnabled, paypalEnabled, paymentMethod]);
  
  // Points redemption state
  const [userPoints, setUserPoints] = useState({ points: 0, value: 0 });
  const [loadingPoints, setLoadingPoints] = useState(false);
  const [pointsToRedeem, setPointsToRedeem] = useState(0);
  const [appliedPointsRedemption, setAppliedPointsRedemption] = useState(null);
  const [applyingPoints, setApplyingPoints] = useState(false);
  const [loyaltyConfig, setLoyaltyConfig] = useState({
    point_value: 0.05,
    max_redemption_percent: 30,
    points_per_dollar: 20
  });
  
  // 30% one-time discount eligibility
  const [thirtyPercentEligibility, setThirtyPercentEligibility] = useState(null);
  const [loadingEligibility, setLoadingEligibility] = useState(false);
  
  // FlagShip Live Shipping Rates
  const [shippingRates, setShippingRates] = useState([]);
  const [selectedShippingRate, setSelectedShippingRate] = useState(null);
  const [loadingShippingRates, setLoadingShippingRates] = useState(false);
  
  const [formData, setFormData] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    email: user?.email || "",
    phone: user?.phone || "",
    address_line1: "",
    address_line2: "",
    city: "",
    province: "",
    postal_code: "",
    country: "CA"
  });

  // Postal code lookup debounce ref
  const postalCodeDebounceRef = useRef(null);
  const [lookingUpPostalCode, setLookingUpPostalCode] = useState(false);

  // Look up city and province/state from postal code (Canada or US)
  const lookupPostalCode = useCallback(async (postalCode) => {
    // Only auto-fill for Canadian or US addresses
    if (formData.country !== "CA" && formData.country !== "US") return;
    
    // Clean the postal/ZIP code
    const cleanPostal = postalCode.replace(/\s/g, '').toUpperCase();
    
    // Need at least 3 characters to look up
    if (cleanPostal.length < 3) return;
    
    setLookingUpPostalCode(true);
    try {
      // Use appropriate endpoint based on country
      const endpoint = formData.country === "CA" 
        ? `${API}/postal-code/lookup` 
        : `${API}/zip-code/lookup`;
      const paramName = formData.country === "CA" ? 'postal_code' : 'zip_code';
      
      const res = await axios.get(endpoint, {
        params: { [paramName]: cleanPostal }
      });
      
      if (res.data.found) {
        const updates = {};
        
        // Only update city if we found one and current city is empty
        if (res.data.city && !formData.city) {
          updates.city = res.data.city;
        }
        
        // Only update province/state if we found one and current is empty
        const stateField = res.data.province || res.data.state;
        if (stateField && !formData.province) {
          updates.province = stateField;
        }
        
        if (Object.keys(updates).length > 0) {
          setFormData(prev => ({ ...prev, ...updates }));
          toast.success(`Auto-filled: ${updates.city || ''} ${updates.province || ''}`.trim(), {
            duration: 2000,
            icon: '📍'
          });
        }
      }
    } catch (error) {
      console.error("Postal/ZIP code lookup error:", error);
      // Silently fail - user can still type manually
    }
    setLookingUpPostalCode(false);
  }, [formData.country, formData.city, formData.province]);

  // Handle postal code input with debounced lookup
  const handlePostalCodeChange = (e) => {
    const value = e.target.value.toUpperCase();
    setFormData(prev => ({ ...prev, postal_code: value }));

    // Clear existing debounce timer
    if (postalCodeDebounceRef.current) {
      clearTimeout(postalCodeDebounceRef.current);
    }

    // Debounce the lookup request (500ms)
    postalCodeDebounceRef.current = setTimeout(() => {
      lookupPostalCode(value);
    }, 500);
  };

  // Fetch live shipping rates when address is complete
  useEffect(() => {
    const fetchShippingRates = async () => {
      // Only fetch if we have complete Canadian address
      if (!formData.address_line1 || !formData.city || !formData.province || !formData.postal_code || formData.country !== "CA") {
        return;
      }
      
      setLoadingShippingRates(true);
      try {
        const totalWeight = cart.items?.reduce((acc, item) => acc + ((item.product?.weight_grams || 200) * item.quantity), 0) || 500;
        
        const res = await axios.post(`${API}/shipping/rates`, {
          name: `${formData.first_name} ${formData.last_name}`.trim() || "Customer",
          address: formData.address_line1,
          city: formData.city,
          state: formData.province,
          postal_code: formData.postal_code,
          country: formData.country,
          phone: formData.phone || "",
          packages: [{ weight: totalWeight / 1000, description: "Skincare Products" }]
        });
        
        if (res.data.success && res.data.rates?.length > 0) {
          setShippingRates(res.data.rates);
          // Auto-select cheapest rate
          setSelectedShippingRate(res.data.rates[0]);
        } else {
          // Use fallback rates
          setShippingRates(res.data.rates || []);
        }
      } catch (error) {
        console.error("Failed to fetch shipping rates:", error);
        // Fallback to flat rate
        setShippingRates([
          { courier_name: "Standard Shipping", service_name: "Standard Delivery", total_price: 9.99, transit_days: 5, courier_code: "STANDARD" }
        ]);
      }
      setLoadingShippingRates(false);
    };
    
    // Debounce the fetch
    const timer = setTimeout(fetchShippingRates, 500);
    return () => clearTimeout(timer);
  }, [formData.address_line1, formData.city, formData.province, formData.postal_code, formData.country, cart.items]);

  // Fetch user's loyalty points when logged in
  useEffect(() => {
    const fetchUserPoints = async () => {
      if (!user) {
        setUserPoints({ points: 0, value: 0 });
        return;
      }
      setLoadingPoints(true);
      try {
        const token = localStorage.getItem('reroots_token');
        const res = await axios.get(`${API}/loyalty/points`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setUserPoints({
          points: res.data.points || 0,
          value: res.data.value || 0,
          lifetime_earned: res.data.lifetime_earned || 0
        });
        // Also get loyalty config
        if (res.data.config) {
          setLoyaltyConfig(res.data.config);
        }
      } catch (error) {
        console.error("Failed to fetch user points:", error);
        setUserPoints({ points: 0, value: 0 });
      }
      setLoadingPoints(false);
    };
    fetchUserPoints();
  }, [user]);

  // Check 30% discount eligibility
  useEffect(() => {
    const checkEligibility = async () => {
      if (!user) {
        setThirtyPercentEligibility(null);
        return;
      }
      setLoadingEligibility(true);
      try {
        const token = localStorage.getItem('reroots_token');
        const res = await axios.get(`${API}/loyalty/points/check-30-percent-eligibility`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setThirtyPercentEligibility(res.data);
      } catch (error) {
        console.error("Failed to check 30% eligibility:", error);
        setThirtyPercentEligibility(null);
      }
      setLoadingEligibility(false);
    };
    checkEligibility();
  }, [user]);

  // Redeem 30% one-time discount
  const redeem30PercentDiscount = async () => {
    if (!user || !thirtyPercentEligibility?.eligible) {
      toast.error("You're not eligible for this offer");
      return;
    }
    setApplyingPoints(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.post(`${API}/loyalty/points/redeem-30-percent`, { 
        order_subtotal: subtotal 
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAppliedPointsRedemption({
        token: res.data.redemption_token,
        points: res.data.points,
        value: res.data.discount_value,
        is30PercentOffer: true,
        discountPercent: res.data.discount_percent
      });
      toast.success(`🎉 ${res.data.discount_percent || 30}% off applied! (-$${res.data.discount_value.toFixed(2)})`);
      // Update eligibility state
      setThirtyPercentEligibility(prev => ({ ...prev, eligible: false, already_used: true }));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to redeem 30% discount");
    }
    setApplyingPoints(false);
  };

  // Redeem points for discount
  const redeemPoints = async (points) => {
    if (!user || points < 100) {
      toast.error("Minimum 100 Roots required to redeem");
      return;
    }
    if (points > userPoints.points) {
      toast.error("Insufficient Roots");
      return;
    }
    
    // Calculate max discount (30% cap)
    const maxDiscount = subtotal * (loyaltyConfig.max_redemption_percent / 100);
    const potentialDiscount = points * loyaltyConfig.point_value;
    
    // If trying to redeem more than 30% worth, warn user
    if (potentialDiscount > maxDiscount) {
      const maxPoints = Math.floor(maxDiscount / loyaltyConfig.point_value);
      toast.info(`Maximum discount is 30% of subtotal ($${maxDiscount.toFixed(2)}). Using ${maxPoints} Roots instead.`);
    }
    
    setApplyingPoints(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.post(`${API}/loyalty/points/redeem`, { 
        points,
        subtotal  // Send subtotal for 30% cap calculation
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAppliedPointsRedemption({
        token: res.data.redemption_token,
        points: res.data.points,
        value: res.data.discount_value,
        capped: res.data.capped
      });
      if (res.data.capped) {
        toast.success(`🎉 ${res.data.points} Roots = $${res.data.discount_value} off! (30% max applied)`);
      } else {
        toast.success(`🎉 ${res.data.points} Roots = $${res.data.discount_value} off!`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to redeem Roots");
    }
    setApplyingPoints(false);
  };

  // Remove points redemption
  const removePointsRedemption = () => {
    setAppliedPointsRedemption(null);
    setPointsToRedeem(0);
    toast.info("Roots redemption removed");
  };

  // Auto-apply discount from URL parameter or stored code
  useEffect(() => {
    const autoApplyCode = localStorage.getItem('auto_apply_discount');
    const partnerCode = sessionStorage.getItem('partner_code');
    const codeToApply = autoApplyCode || partnerCode;
    
    if (codeToApply && !appliedDiscount && appliedDiscounts.length === 0) {
      setDiscountCode(codeToApply);
      (async () => {
        setApplyingDiscount(true);
        try {
          const res = await axios.post(`${API}/validate-discount`, {
            code: codeToApply,
            email: user?.email || formData.email || ""
          });
          if (res.data.valid) {
            setAppliedDiscount(res.data);
            setAppliedDiscounts(prev => [...prev.filter(d => d.code !== res.data.code), res.data]);
            const isPartner = partnerCode === codeToApply;
            toast.success(`${isPartner ? 'Partner' : 'Discount'} code ${codeToApply} applied automatically!`, { icon: '🎉' });
            if (autoApplyCode) localStorage.removeItem('auto_apply_discount');
          }
        } catch (error) {
          console.log("Auto-apply discount failed:", error);
        }
        setApplyingDiscount(false);
      })();
    }
  }, [subtotal, appliedDiscount, appliedDiscounts.length]);

  // Gift Wrapping State
  const [giftWrap, setGiftWrap] = useState({
    enabled: false,
    option: "standard",
    message: ""
  });
  
  const giftWrapOptions = [
    { id: "standard", name: "🎀 Standard Gift Wrap", price: 5.99, description: "Elegant pink tissue paper with satin ribbon" },
    { id: "premium", name: "🎁 Premium Gift Box", price: 12.99, description: "Luxurious black box with gold foil accent" },
    { id: "eco", name: "🌿 Eco-Friendly Wrap", price: 4.99, description: "Recyclable kraft paper with dried flower" }
  ];
  const giftWrapPrice = giftWrap.enabled ? (giftWrapOptions.find(o => o.id === giftWrap.option)?.price || 5.99) : 0;

  // Country configurations
  const countryConfig = {
    CA: {
      name: "Canada", code: "ca", postalLabel: "Postal Code", postalPlaceholder: "A1A 1A1", regionLabel: "Province",
      regions: [
        { code: "ON", name: "Ontario" }, { code: "BC", name: "British Columbia" }, { code: "AB", name: "Alberta" },
        { code: "QC", name: "Quebec" }, { code: "MB", name: "Manitoba" }, { code: "SK", name: "Saskatchewan" },
        { code: "NS", name: "Nova Scotia" }, { code: "NB", name: "New Brunswick" }, { code: "NL", name: "Newfoundland & Labrador" },
        { code: "PE", name: "Prince Edward Island" }, { code: "NT", name: "Northwest Territories" }, { code: "YT", name: "Yukon" }, { code: "NU", name: "Nunavut" }
      ]
    },
    US: {
      name: "United States", code: "us", postalLabel: "ZIP Code", postalPlaceholder: "12345", regionLabel: "State",
      regions: [
        { code: "AL", name: "Alabama" }, { code: "AK", name: "Alaska" }, { code: "AZ", name: "Arizona" }, { code: "AR", name: "Arkansas" },
        { code: "CA", name: "California" }, { code: "CO", name: "Colorado" }, { code: "CT", name: "Connecticut" }, { code: "DE", name: "Delaware" },
        { code: "FL", name: "Florida" }, { code: "GA", name: "Georgia" }, { code: "HI", name: "Hawaii" }, { code: "ID", name: "Idaho" },
        { code: "IL", name: "Illinois" }, { code: "IN", name: "Indiana" }, { code: "IA", name: "Iowa" }, { code: "KS", name: "Kansas" },
        { code: "KY", name: "Kentucky" }, { code: "LA", name: "Louisiana" }, { code: "ME", name: "Maine" }, { code: "MD", name: "Maryland" },
        { code: "MA", name: "Massachusetts" }, { code: "MI", name: "Michigan" }, { code: "MN", name: "Minnesota" }, { code: "MS", name: "Mississippi" },
        { code: "MO", name: "Missouri" }, { code: "MT", name: "Montana" }, { code: "NE", name: "Nebraska" }, { code: "NV", name: "Nevada" },
        { code: "NH", name: "New Hampshire" }, { code: "NJ", name: "New Jersey" }, { code: "NM", name: "New Mexico" }, { code: "NY", name: "New York" },
        { code: "NC", name: "North Carolina" }, { code: "ND", name: "North Dakota" }, { code: "OH", name: "Ohio" }, { code: "OK", name: "Oklahoma" },
        { code: "OR", name: "Oregon" }, { code: "PA", name: "Pennsylvania" }, { code: "RI", name: "Rhode Island" }, { code: "SC", name: "South Carolina" },
        { code: "SD", name: "South Dakota" }, { code: "TN", name: "Tennessee" }, { code: "TX", name: "Texas" }, { code: "UT", name: "Utah" },
        { code: "VT", name: "Vermont" }, { code: "VA", name: "Virginia" }, { code: "WA", name: "Washington" }, { code: "WV", name: "West Virginia" },
        { code: "WI", name: "Wisconsin" }, { code: "WY", name: "Wyoming" }, { code: "DC", name: "Washington DC" }
      ]
    },
    GB: { name: "United Kingdom", code: "gb", postalLabel: "Postcode", postalPlaceholder: "SW1A 1AA", regionLabel: "County/Region",
      regions: [{ code: "ENG", name: "England" }, { code: "SCT", name: "Scotland" }, { code: "WLS", name: "Wales" }, { code: "NIR", name: "Northern Ireland" }]
    },
    AU: { name: "Australia", code: "au", postalLabel: "Postcode", postalPlaceholder: "2000", regionLabel: "State/Territory",
      regions: [{ code: "NSW", name: "New South Wales" }, { code: "VIC", name: "Victoria" }, { code: "QLD", name: "Queensland" }, { code: "WA", name: "Western Australia" },
        { code: "SA", name: "South Australia" }, { code: "TAS", name: "Tasmania" }, { code: "ACT", name: "Australian Capital Territory" }, { code: "NT", name: "Northern Territory" }]
    },
    IN: { name: "India", code: "in", postalLabel: "PIN Code", postalPlaceholder: "110001", regionLabel: "State",
      regions: [{ code: "DL", name: "Delhi" }, { code: "MH", name: "Maharashtra" }, { code: "KA", name: "Karnataka" }, { code: "TN", name: "Tamil Nadu" },
        { code: "GJ", name: "Gujarat" }, { code: "RJ", name: "Rajasthan" }, { code: "UP", name: "Uttar Pradesh" }, { code: "WB", name: "West Bengal" }]
    },
    DE: { name: "Germany", code: "de", postalLabel: "PLZ", postalPlaceholder: "10115", regionLabel: "State",
      regions: [{ code: "BE", name: "Berlin" }, { code: "BY", name: "Bavaria" }, { code: "HH", name: "Hamburg" }, { code: "NW", name: "North Rhine-Westphalia" }]
    },
    FR: { name: "France", code: "fr", postalLabel: "Code Postal", postalPlaceholder: "75001", regionLabel: "Region",
      regions: [{ code: "IDF", name: "Île-de-France" }, { code: "ARA", name: "Auvergne-Rhône-Alpes" }, { code: "PAC", name: "Provence-Alpes-Côte d'Azur" }]
    }
  };

  const currentCountry = countryConfig[formData.country] || countryConfig.CA;

  // Calculate totals
  // Calculate original subtotal from original prices (before combo discounts)
  const originalSubtotal = cart.items?.reduce((sum, item) => {
    const originalPrice = item.original_price || item.product?.price || 0;
    return sum + originalPrice * item.quantity;
  }, 0) || 0;
  const productDiscountAmount = originalSubtotal - subtotal;
  
  let runningSubtotal = subtotal;
  let totalCouponDiscount = 0;
  
  for (const discount of appliedDiscounts) {
    let discountAmt = 0;
    if (discount.discount_type === 'percentage' || discount.discount_percent) {
      const percent = discount.discount_percent || discount.discount_value || 0;
      discountAmt = runningSubtotal * (percent / 100);
    } else if (discount.discount_type === 'fixed' || discount.discount_value) {
      discountAmt = Math.min(discount.discount_value || 0, runningSubtotal);
    }
    totalCouponDiscount += discountAmt;
    runningSubtotal -= discountAmt;
    if (runningSubtotal < 0) runningSubtotal = 0;
  }
  
  const couponDiscountAmount = appliedDiscounts.length > 0 
    ? totalCouponDiscount
    : (appliedDiscount 
        ? (appliedDiscount.discount_type === 'fixed' 
            ? Math.min(appliedDiscount.discount_value || 0, subtotal)
            : (subtotal * ((appliedDiscount.discount_percent || appliedDiscount.discount_value || 0) / 100)))
        : 0);
  
  const afterAllDiscounts = appliedDiscounts.length > 0 ? runningSubtotal : (subtotal - couponDiscountAmount);
  const totalProductDiscount = productDiscountAmount + couponDiscountAmount;

  // Voucher gate pricing
  const [voucherGatePricing, setVoucherGatePricing] = useState(null);
  const [fetchingPricing, setFetchingPricing] = useState(false);
  const emailForPricing = user?.email || formData.email || "";
  
  useEffect(() => {
    const fetchVoucherGatePricing = async () => {
      if (!originalSubtotal || !cart.items?.length) return;
      setFetchingPricing(true);
      try {
        // Include applied discount codes in pricing request
        const appliedCodeNames = appliedDiscounts.map(d => d.code).filter(Boolean);
        const discountCodeToSend = appliedCodeNames[0] || appliedDiscount?.code || "";
        
        const res = await axios.post(`${API}/checkout/pricing`, {
          email: emailForPricing,
          original_subtotal: originalSubtotal,
          cart_items: cart.items.map(item => ({ product_id: item.product?.id, quantity: item.quantity })),
          discount_code: discountCodeToSend
        });
        setVoucherGatePricing(res.data);
      } catch (error) {
        console.error("Failed to fetch voucher gate pricing:", error);
      }
      setFetchingPricing(false);
    };
    fetchVoucherGatePricing();
  }, [user?.email, originalSubtotal, cart.items?.length, appliedDiscounts, appliedDiscount, emailForPricing]);

  // Landed cost
  const [landedCost, setLandedCost] = useState(null);
  const [calculatingLandedCost, setCalculatingLandedCost] = useState(false);
  
  useEffect(() => {
    const calculateLandedCostAsync = async () => {
      if (!formData.country || !originalSubtotal || !cart.items?.length) return;
      setCalculatingLandedCost(true);
      try {
        const totalWeight = cart.items.reduce((acc, item) => acc + ((item.product?.weight_grams || 200) * item.quantity), 0);
        const res = await axios.post(`${API}/calculate-landed-cost`, {
          subtotal: originalSubtotal, country_code: formData.country, province: formData.province || "ON",
          weight_grams: totalWeight, shipping_method: "standard"
        });
        setLandedCost(res.data);
      } catch (error) {
        console.error("Failed to calculate landed cost:", error);
        setLandedCost({
          tax: originalSubtotal * 0.13, tax_rate: 13, tax_name: "HST", duty: 0, duty_rate: 0,
          shipping: originalSubtotal >= 75 ? 0 : 10, shipping_days: "5-7 business days", is_international: false, duty_free: true
        });
      }
      setCalculatingLandedCost(false);
    };
    calculateLandedCostAsync();
  }, [formData.country, formData.province, originalSubtotal, cart.items?.length]);

  const tax = landedCost?.tax ?? (originalSubtotal * 0.13);
  const duty = landedCost?.duty ?? 0;
  
  // Use selected live shipping rate if available, otherwise fallback
  const shipping = selectedShippingRate 
    ? (originalSubtotal >= 75 ? 0 : selectedShippingRate.total_price) 
    : (landedCost?.shipping ?? (originalSubtotal >= 75 ? 0 : 10));
  const shippingDays = selectedShippingRate 
    ? `${selectedShippingRate.transit_days} business days` 
    : (landedCost?.shipping_days ?? "5-7 business days");
  const shippingCarrier = selectedShippingRate?.courier_name || "Standard";
  
  const isInternational = landedCost?.is_international ?? (formData.country !== "CA");
  const taxName = landedCost?.tax_name ?? "HST";
  const taxRate = landedCost?.tax_rate ?? 13;

  // Calculate points discount
  const pointsDiscount = appliedPointsRedemption?.value || 0;

  const finalSubtotalForTotal = voucherGatePricing ? voucherGatePricing.final_subtotal : afterAllDiscounts;
  const calculatedTax = voucherGatePricing?.tax?.amount ?? tax;
  const total = voucherGatePricing 
    ? (voucherGatePricing.final_subtotal + (voucherGatePricing.tax?.amount || 0) + duty + shipping + giftWrapPrice - pointsDiscount)
    : (finalSubtotalForTotal + tax + duty + shipping + giftWrapPrice - pointsDiscount);

  // Apply discount code
  const applyDiscount = async () => {
    if (!discountCode.trim()) return;
    setApplyingDiscount(true);
    try {
      const res = await axios.post(`${API}/validate-discount`, { code: discountCode, email: user?.email || formData.email || "" });
      const newDiscount = res.data;
      const existingIndex = appliedDiscounts.findIndex(d => 
        (d.is_partner_code && newDiscount.is_partner_code) || (d.is_first_purchase && newDiscount.is_first_purchase) || (d.code === newDiscount.code)
      );
      if (existingIndex >= 0) {
        const updated = [...appliedDiscounts];
        updated[existingIndex] = newDiscount;
        setAppliedDiscounts(updated);
      } else {
        setAppliedDiscounts([...appliedDiscounts, newDiscount]);
      }
      setAppliedDiscount(newDiscount);
      setDiscountCode("");
      toast.success(res.data.message);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Invalid discount code");
    }
    setApplyingDiscount(false);
  };

  const removeDiscount = (codeToRemove = null) => {
    if (codeToRemove) {
      setAppliedDiscounts(appliedDiscounts.filter(d => d.code !== codeToRemove));
      if (appliedDiscount?.code === codeToRemove) {
        setAppliedDiscount(appliedDiscounts.find(d => d.code !== codeToRemove) || null);
      }
    } else {
      setAppliedDiscount(null);
      setAppliedDiscounts([]);
    }
    setDiscountCode("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      // Validate card details first for Bambora
      if (paymentMethod === "bambora") {
        if (!bamboraCard.number || !bamboraCard.name || !bamboraCard.expiry_month || !bamboraCard.expiry_year || !bamboraCard.cvv) {
          toast.error("Please fill in all card details");
          setLoading(false);
          return;
        }
      }

      const allCodes = appliedDiscounts.map(d => d.code);
      const orderRes = await axios.post(`${API}/orders`, {
        shipping_address: formData, payment_method: paymentMethod, session_id: sessionId,
        discount_codes: allCodes.length > 0 ? allCodes : (appliedDiscount?.code ? [appliedDiscount.code] : []),
        discount_code: allCodes[0] || appliedDiscount?.code || null, discount_percent: appliedDiscount?.discount_percent || 0,
        points_to_redeem: appliedPointsRedemption?.points || 0,
        redemption_token: appliedPointsRedemption?.token || null,
        storefront: 'reroots' // Bright theme storefront
      }, { headers: user ? { Authorization: `Bearer ${localStorage.getItem("reroots_token")}` } : {} });

      if (!orderRes.data?.order_id) {
        toast.error("Failed to create order. Please try again.");
        setLoading(false);
        return;
      }

      // Handle different payment methods
      if (paymentMethod === "bambora") {
        try {
          const bamboraRes = await axios.post(`${API}/payments/bambora/checkout`, {
            order_id: orderRes.data.order_id,
            card_number: bamboraCard.number.replace(/\s/g, ''),
            expiry_month: parseInt(bamboraCard.expiry_month),
            expiry_year: parseInt(bamboraCard.expiry_year),
            cvv: bamboraCard.cvv,
            cardholder_name: bamboraCard.name,
            billing_postal_code: formData.postal_code
          });
          if (bamboraRes.data.success) {
            toast.success("Payment successful!");
            clearCart();
            navigate(`/checkout/success?order_id=${orderRes.data.order_id}`);
          } else {
            // Show user-friendly error with help text
            const errorMessage = bamboraRes.data.message || "Payment declined. Please check your card details.";
            const helpText = bamboraRes.data.help_text;
            
            toast.error(
              <div className="space-y-2">
                <p className="font-medium">{errorMessage}</p>
                {helpText && <p className="text-sm opacity-80">{helpText}</p>}
              </div>,
              { duration: 8000 }
            );
            setLoading(false);
          }
        } catch (bamboraError) {
          console.error("Bambora payment error:", bamboraError);
          const errorMsg = bamboraError.response?.data?.detail || 
                          bamboraError.response?.data?.message ||
                          "Payment failed. Please check your card details and try again.";
          const helpText = bamboraError.response?.data?.help_text;
          
          toast.error(
            <div className="space-y-2">
              <p className="font-medium">{errorMsg}</p>
              {helpText && <p className="text-sm opacity-80">{helpText}</p>}
            </div>,
            { duration: 8000 }
          );
          setLoading(false);
        }
      } else if (paymentMethod === "etransfer" || paymentMethod === "paypal") {
        // For e-Transfer and PayPal, order is created with pending payment
        // Customer will send payment manually
        toast.success(
          <div className="space-y-2">
            <p className="font-medium">Order placed successfully!</p>
            <p className="text-sm">Please send your {paymentMethod === "etransfer" ? "e-Transfer" : "PayPal payment"} to complete your order.</p>
          </div>,
          { duration: 6000 }
        );
        clearCart();
        
        // For PayPal: If a PayPal link URL is configured, redirect to it after showing success page
        if (paymentMethod === "paypal" && paypalLinkUrl) {
          // Navigate to success page first, then redirect to PayPal
          navigate(`/checkout/success?order_id=${orderRes.data.order_id}&payment_method=${paymentMethod}&paypal_redirect=true`);
        } else {
          navigate(`/checkout/success?order_id=${orderRes.data.order_id}&payment_method=${paymentMethod}`);
        }
      }
    } catch (error) {
      console.error("Checkout error:", error);
      const errorMsg = error.response?.data?.detail || 
                      error.response?.data?.message ||
                      "Failed to process order. Please try again.";
      toast.error(errorMsg);
      setLoading(false);
    }
  };

  // Redirect to cart if empty (with delay to allow cart to load)
  useEffect(() => {
    // Wait for cart to settle - give time for localStorage/server sync
    const timer = setTimeout(() => {
      setInitialLoadComplete(true);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    // Only redirect after initial load is complete and cart is still empty
    if (initialLoadComplete && !cart.items?.length) {
      console.log("[Checkout] Cart empty after initial load, redirecting to cart page");
      navigate("/cart");
    }
  }, [cart.items?.length, navigate, initialLoadComplete]);

  // Show loading state while cart is being loaded
  if (!initialLoadComplete || cartLoading) {
    return (
      <div className="min-h-screen pt-24 bg-[#FDF9F9] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37] mx-auto mb-4" />
          <p className="text-[#5A5A5A]">Loading your cart...</p>
        </div>
      </div>
    );
  }

  if (!cart.items?.length) {
    return null;
  }

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      <Helmet>
        <title>Checkout | ReRoots Biotech Skincare Canada</title>
        <meta name="description" content="Secure checkout for ReRoots skincare products. Free shipping on orders over $75 CAD. Canadian biotech skincare." />
        <meta name="robots" content="noindex, nofollow" />
        <link rel="canonical" href="https://reroots.ca/checkout" />
      </Helmet>
      <div className="max-w-7xl mx-auto px-6 md:px-12 py-12">
        <h1 className="font-display text-3xl font-bold text-[#2D2A2E] mb-8" data-testid="checkout-title">Checkout</h1>

        <form onSubmit={handleSubmit}>
          {/* Single column layout on mobile, 2 columns on desktop */}
          <div className="space-y-6 lg:space-y-0 lg:grid lg:grid-cols-5 lg:gap-8">
            {/* Left side: Contact, Shipping, Payment - takes 3 columns on desktop */}
            <div className="lg:col-span-3 space-y-6 order-1">
              {/* 1. Contact Info */}
              <Card>
                <CardHeader><CardTitle className="font-display text-xl">1. Contact Information</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {user && (
                    <div className="flex items-center gap-2 p-3 bg-green-50 rounded-lg border border-green-200 mb-4">
                      <Check className="h-4 w-4 text-green-600" />
                      <span className="text-sm text-green-700">Logged in as <strong>{user.email}</strong> - Info auto-filled</span>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="first_name">First Name</Label>
                      <Input id="first_name" required value={formData.first_name} onChange={(e) => setFormData({ ...formData, first_name: e.target.value })} data-testid="checkout-first-name" />
                    </div>
                    <div>
                      <Label htmlFor="last_name">Last Name</Label>
                      <Input id="last_name" required value={formData.last_name} onChange={(e) => setFormData({ ...formData, last_name: e.target.value })} data-testid="checkout-last-name" />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" required value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} data-testid="checkout-email" />
                  </div>
                  <div>
                    <Label htmlFor="phone">Phone</Label>
                    <Input id="phone" type="tel" required value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} data-testid="checkout-phone" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Order Summary - shows as 2nd on mobile, right column on desktop */}
            <div className="lg:col-span-2 order-2 lg:row-span-3">
              <Card className="lg:sticky lg:top-24">
                <CardHeader><CardTitle className="font-display text-xl">2. Order Summary</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {/* Cart Items */}
                  {cart.items?.map((item, idx) => {
                    // Check if this is a combo item (new single line item structure)
                    const isCombo = item.item_type === "combo";
                    
                    if (isCombo) {
                      // Render COMBO as single line item at combo_price
                      const comboPrice = item.price || 0;
                      return (
                        <div key={item.combo_id || idx} className="pb-4 border-b border-purple-100" data-testid={`checkout-combo-${idx}`}>
                          {/* Combo Badge */}
                          <div className="flex items-center gap-2 mb-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-semibold rounded-full">
                              <Sparkles className="w-3 h-3" /> COMBO
                            </span>
                            {item.discount_percent > 0 && (
                              <span className="text-xs text-green-600 font-medium">Save {Number(item.discount_percent).toFixed(0)}%</span>
                            )}
                          </div>
                          
                          {/* Combo Name */}
                          <p className="font-medium text-[#2D2A2E] mb-1">{item.combo_name}</p>
                          
                          {/* Includes: Product names */}
                          {item.products && item.products.length > 0 && (
                            <p className="text-xs text-gray-500 mb-2">
                              Includes: {item.products.map(p => p.name).join(' + ')}
                            </p>
                          )}
                          
                          <p className="text-sm text-[#5A5A5A]">Qty: {item.quantity}</p>
                          
                          {/* Price - Single combo_price */}
                          <div className="flex items-center gap-2 mt-1">
                            <p className="font-semibold text-[#2D2A2E]">${(comboPrice * item.quantity).toFixed(2)}</p>
                            {item.original_price && item.original_price > comboPrice && (
                              <p className="text-sm text-gray-400 line-through">${(item.original_price * item.quantity).toFixed(2)}</p>
                            )}
                          </div>
                        </div>
                      );
                    }
                    
                    // Legacy combo support (with combo_price field) or regular product
                    const itemPrice = item.combo_price !== undefined && item.combo_price !== null
                      ? item.combo_price
                      : (item.product?.price || 0);
                    
                    return (
                      <div key={item.product_id || idx} className="flex gap-4 pb-4 border-b" data-testid={`cart-item-${idx}`}>
                        <img src={item.product?.images?.[0] || item.product?.image || '/placeholder.jpg'} alt={item.product?.name}
                          className="w-16 h-16 object-cover rounded-lg" loading="lazy" />
                        <div className="flex-1">
                          <p className="font-medium text-[#2D2A2E]">{item.product?.name}</p>
                          {item.combo_name && (
                            <p className="text-xs text-purple-600 font-medium">{item.combo_name}</p>
                          )}
                          <p className="text-sm text-[#5A5A5A]">Qty: {item.quantity}</p>
                          <div className="flex items-center gap-2">
                            <p className="font-medium">${(itemPrice * item.quantity).toFixed(2)}</p>
                            {item.combo_price !== undefined && item.original_price && item.combo_price < item.original_price && (
                              <p className="text-sm text-gray-400 line-through">${(item.original_price * item.quantity).toFixed(2)}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Discount Code / Coupon */}
                  <div className="pt-4 border-t">
                    <div className="flex items-center gap-2 mb-2">
                      <Tag className="h-4 w-4 text-purple-600" />
                      <Label htmlFor="discount" className="font-semibold text-purple-700">Have a Coupon?</Label>
                    </div>
                    <div className="flex gap-2">
                      <Input 
                        id="discount" 
                        value={discountCode} 
                        onChange={(e) => setDiscountCode(e.target.value.toUpperCase())}
                        placeholder="Enter coupon code" 
                        className="flex-1 border-purple-200 focus:border-purple-400"
                        data-testid="discount-code-input" 
                      />
                      <Button 
                        type="button" 
                        onClick={applyDiscount} 
                        disabled={applyingDiscount} 
                        className="bg-purple-600 hover:bg-purple-700 text-white"
                      >
                        {applyingDiscount ? <Loader2 className="h-4 w-4 animate-spin" /> : "Apply"}
                      </Button>
                    </div>
                    {appliedDiscounts.map((d, idx) => (
                      <div key={idx} className="flex items-center justify-between mt-2 p-2 bg-green-50 rounded">
                        <span className="text-sm text-green-700"><Tag className="h-3 w-3 inline mr-1" />{d.code}</span>
                        <button type="button" onClick={() => removeDiscount(d.code)} className="text-red-500"><X className="h-4 w-4" /></button>
                      </div>
                    ))}
                  </div>

                  {/* Points Redemption Section */}
                  {user && (
                    <div className="pt-4 space-y-3 bg-gradient-to-br from-amber-50 to-orange-50 -mx-6 px-6 py-4 border-y border-amber-200/50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Coins className="h-5 w-5 text-amber-600" />
                          <span className="font-medium text-[#2D2A2E]">Reward Points</span>
                        </div>
                        {loadingPoints ? (
                          <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
                        ) : (
                          <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300">
                            {userPoints.points} pts
                          </Badge>
                        )}
                      </div>
                      
                      {/* Dynamic 30% Discount Calculation */}
                      {(() => {
                        // Calculate points needed for 30% discount based on current order
                        const maxDiscountPercent = loyaltyConfig.max_redemption_percent || 30;
                        const pointValue = loyaltyConfig.point_value || 0.05;
                        const pointsPerDollar = Math.round(1 / pointValue); // 20 points = $1
                        
                        // 30% of subtotal
                        const thirtyPercentDiscount = subtotal * (maxDiscountPercent / 100);
                        // Points needed for full 30% discount
                        const pointsFor30Percent = Math.ceil(thirtyPercentDiscount * pointsPerDollar);
                        
                        // Check if user has enough points for 30% off
                        const canGet30Percent = userPoints.points >= pointsFor30Percent;
                        const pointsShortage = pointsFor30Percent - userPoints.points;
                        
                        return (
                          <>
                            {/* 30% OFF Offer - Dynamic based on order total */}
                            {!appliedPointsRedemption && (
                              <div className={`p-3 rounded-lg border-2 ${
                                canGet30Percent 
                                  ? 'bg-gradient-to-r from-emerald-50 to-green-50 border-emerald-400' 
                                  : 'bg-purple-50 border-purple-300'
                              }`}>
                                {canGet30Percent ? (
                                  <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                      <Sparkles className="h-5 w-5 text-emerald-600" />
                                      <span className="font-bold text-emerald-700">{maxDiscountPercent}% OFF Available!</span>
                                      <Badge className="bg-emerald-500 text-white text-xs">MAX DISCOUNT</Badge>
                                    </div>
                                    <p className="text-sm text-emerald-600">
                                      Use <span className="font-bold">{pointsFor30Percent} points</span> for {maxDiscountPercent}% off
                                      <span className="font-semibold"> (-${thirtyPercentDiscount.toFixed(2)})</span>
                                    </p>
                                    <div className="text-xs text-emerald-500 bg-emerald-100 rounded p-2">
                                      Calculation: ${subtotal.toFixed(2)} × {maxDiscountPercent}% = ${thirtyPercentDiscount.toFixed(2)} 
                                      → {pointsPerDollar} pts/$1 × ${thirtyPercentDiscount.toFixed(2)} = <strong>{pointsFor30Percent} pts</strong>
                                    </div>
                                    <Button 
                                      type="button"
                                      onClick={() => redeemPoints(pointsFor30Percent)}
                                      disabled={applyingPoints}
                                      className="w-full bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 text-white"
                                      data-testid="redeem-30-percent-btn"
                                    >
                                      {applyingPoints ? (
                                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                      ) : (
                                        <Sparkles className="h-4 w-4 mr-2" />
                                      )}
                                      Redeem {pointsFor30Percent} pts for {maxDiscountPercent}% Off (-${thirtyPercentDiscount.toFixed(2)})
                                    </Button>
                                  </div>
                                ) : userPoints.points >= 100 ? (
                                  <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                      <Sparkles className="h-5 w-5 text-purple-500" />
                                      <span className="font-medium text-purple-700">Unlock {maxDiscountPercent}% OFF</span>
                                    </div>
                                    <p className="text-sm text-purple-600">
                                      Need <span className="font-bold">{pointsFor30Percent} pts</span> for max {maxDiscountPercent}% discount (-${thirtyPercentDiscount.toFixed(2)})
                                    </p>
                                    <Progress 
                                      value={(userPoints.points / pointsFor30Percent) * 100} 
                                      className="h-2 bg-purple-100"
                                    />
                                    <p className="text-xs text-gray-500 text-center">
                                      {userPoints.points}/{pointsFor30Percent} points ({pointsShortage} more needed)
                                    </p>
                                  </div>
                                ) : (
                                  <div className="text-center text-gray-500 text-sm">
                                    <p>Earn points through referrals!</p>
                                    <p className="text-xs mt-1">Need {pointsFor30Percent} pts for {maxDiscountPercent}% off this order</p>
                                  </div>
                                )}
                              </div>
                            )}
                          </>
                        );
                      })()}

                      {/* Regular Points Redemption */}
                      {userPoints.points >= 100 && !thirtyPercentEligibility?.eligible ? (
                        <>
                          {!appliedPointsRedemption ? (
                            <div className="space-y-2">
                              {/* Calculate max discount (30% cap) */}
                              {(() => {
                                const maxDiscountPercent = loyaltyConfig.max_redemption_percent || 30;
                                const pointValue = loyaltyConfig.point_value || 0.05;
                                const maxDiscount = subtotal * (maxDiscountPercent / 100);
                                const maxPointsForCap = Math.floor(maxDiscount / pointValue);
                                const effectiveMaxPoints = Math.min(userPoints.points, maxPointsForCap);
                                const currentDiscount = Math.min((pointsToRedeem || 0) * pointValue, maxDiscount);
                                
                                return (
                                  <>
                                    <div className="flex items-center justify-between text-sm">
                                      <span className="text-gray-600">Points to redeem:</span>
                                      <span className="font-medium text-amber-700">
                                        = ${currentDiscount.toFixed(2)} off
                                        {pointsToRedeem > 0 && (pointsToRedeem * pointValue) > maxDiscount && (
                                          <span className="text-xs text-gray-500 ml-1">(30% max)</span>
                                        )}
                                      </span>
                                    </div>
                                    <div className="flex gap-2">
                                      <Input 
                                        type="number" 
                                        min="100" 
                                        max={effectiveMaxPoints}
                                        step="100"
                                        value={pointsToRedeem || ''}
                                        onChange={(e) => setPointsToRedeem(Math.min(Number(e.target.value), effectiveMaxPoints))}
                                        placeholder={`Min 100, max ${effectiveMaxPoints}`}
                                        className="flex-1"
                                        data-testid="points-redeem-input"
                                      />
                                      <Button 
                                        type="button" 
                                        onClick={() => redeemPoints(pointsToRedeem)}
                                        disabled={applyingPoints || pointsToRedeem < 100}
                                        className="bg-amber-500 hover:bg-amber-600 text-white"
                                      >
                                        {applyingPoints ? <Loader2 className="h-4 w-4 animate-spin" /> : "Redeem"}
                                      </Button>
                                    </div>
                                    {/* Quick redeem buttons */}
                                    <div className="flex gap-2 flex-wrap">
                                      {[100, 200, 500, effectiveMaxPoints].filter((v, i, a) => v <= effectiveMaxPoints && v >= 100 && a.indexOf(v) === i).map(pts => (
                                        <button
                                          key={pts}
                                          type="button"
                                          onClick={() => setPointsToRedeem(pts)}
                                          className={`text-xs px-2 py-1 rounded-full border transition-colors ${
                                            pointsToRedeem === pts 
                                              ? 'bg-amber-500 text-white border-amber-500' 
                                              : 'border-amber-300 text-amber-700 hover:bg-amber-100'
                                          }`}
                                        >
                                          {pts === effectiveMaxPoints ? `Max (${pts})` : pts} pts
                                        </button>
                                      ))}
                                    </div>
                                    <div className="text-xs text-gray-500 space-y-0.5">
                                      <p>{Math.round(1 / pointValue)} points = $1 discount</p>
                                      <p className="text-amber-600">Max discount: {maxDiscountPercent}% of subtotal (${maxDiscount.toFixed(2)})</p>
                                    </div>
                                  </>
                                );
                              })()}
                            </div>
                          ) : (
                            <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200">
                              <div className="flex items-center gap-2">
                                <Check className="h-4 w-4 text-green-600" />
                                <div>
                                  <p className="text-sm font-medium text-green-700">
                                    {appliedPointsRedemption.is30PercentOffer 
                                      ? `${appliedPointsRedemption.discountPercent}% discount applied` 
                                      : `${appliedPointsRedemption.points} points applied`}
                                  </p>
                                  <p className="text-xs text-green-600">
                                    -${appliedPointsRedemption.value.toFixed(2)} off
                                    {appliedPointsRedemption.capped && " (30% max)"}
                                  </p>
                                </div>
                              </div>
                              <button 
                                type="button" 
                                onClick={removePointsRedemption}
                                className="text-red-500 hover:text-red-700"
                              >
                                <X className="h-4 w-4" />
                              </button>
                            </div>
                          )}
                        </>
                      ) : appliedPointsRedemption ? (
                        <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200">
                          <div className="flex items-center gap-2">
                            <Check className="h-4 w-4 text-green-600" />
                            <div>
                              <p className="text-sm font-medium text-green-700">
                                {appliedPointsRedemption.is30PercentOffer 
                                  ? `${appliedPointsRedemption.discountPercent}% discount applied` 
                                  : `${appliedPointsRedemption.points} points applied`}
                              </p>
                              <p className="text-xs text-green-600">
                                -${appliedPointsRedemption.value.toFixed(2)} off
                              </p>
                            </div>
                          </div>
                          <button 
                            type="button" 
                            onClick={removePointsRedemption}
                            className="text-red-500 hover:text-red-700"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      ) : userPoints.points < 100 && !thirtyPercentEligibility?.eligible && (
                        <div className="text-center py-2">
                          <p className="text-sm text-gray-500">
                            {userPoints.points > 0 
                              ? `You need ${100 - userPoints.points} more Roots to redeem` 
                              : "Earn Roots through referrals!"}
                          </p>
                          <p className="text-xs text-amber-600 mt-1">
                            <Zap className="h-3 w-3 inline" /> 1 referral = {POINTS_PER_REFERRAL} Roots
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  <Separator />

                  {/* Pricing */}
                  <div className="space-y-2">
                    <div className="flex justify-between"><span>Subtotal</span><span>${originalSubtotal.toFixed(2)}</span></div>
                    {voucherGatePricing?.discounts_applied?.map((d, idx) => (
                      <div key={idx} className="flex justify-between text-green-600">
                        <span className="flex items-center gap-1">{d.name} <Badge variant="outline" className="text-xs">AUTO</Badge></span>
                        <span>-{d.percent}%</span>
                      </div>
                    ))}
                    {appliedDiscounts
                      .filter(d => !voucherGatePricing?.discounts_applied?.some(pd => pd.name === d.code))
                      .map((d, idx) => (
                      <div key={idx} className="flex justify-between text-green-600">
                        <span>{d.code}</span><span>-{d.discount_percent || d.discount_value}%</span>
                      </div>
                    ))}
                    {appliedPointsRedemption && (
                      <div className="flex justify-between text-amber-600">
                        <span className="flex items-center gap-1">
                          <Coins className="h-3 w-3" /> Points ({appliedPointsRedemption.points})
                        </span>
                        <span>-${appliedPointsRedemption.value.toFixed(2)}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span>{taxName} ({taxRate}%)</span>
                      <span>${calculatedTax.toFixed(2)}</span>
                    </div>
                    
                    {/* Live Shipping Rate Selection */}
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="flex items-center gap-1">
                          <Truck className="h-4 w-4" aria-hidden="true" /> Shipping
                        </span>
                        {loadingShippingRates && <Loader2 className="h-4 w-4 animate-spin" />}
                      </div>
                      
                      {shippingRates.length > 0 && formData.country === "CA" ? (
                        <div className="space-y-2 pl-5">
                          {shippingRates.slice(0, 4).map((rate, idx) => (
                            <label 
                              key={idx} 
                              className={`flex items-center justify-between p-2 rounded-lg border cursor-pointer transition-colors ${
                                selectedShippingRate?.courier_code === rate.courier_code && selectedShippingRate?.service_name === rate.service_name
                                  ? 'border-[#D4AF37] bg-[#D4AF37]/5' 
                                  : 'border-gray-200 hover:border-gray-300'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <input 
                                  type="radio" 
                                  name="shipping_rate" 
                                  checked={selectedShippingRate?.courier_code === rate.courier_code && selectedShippingRate?.service_name === rate.service_name}
                                  onChange={() => setSelectedShippingRate(rate)}
                                  className="accent-[#D4AF37]"
                                />
                                <div>
                                  <p className="text-sm font-medium">{rate.courier_name}</p>
                                  <p className="text-xs text-gray-500">{rate.service_name} • {rate.transit_days} days</p>
                                </div>
                              </div>
                              <span className="font-medium">
                                {originalSubtotal >= 75 ? (
                                  <span className="text-green-600">FREE</span>
                                ) : (
                                  `$${rate.total_price.toFixed(2)}`
                                )}
                              </span>
                            </label>
                          ))}
                          {originalSubtotal >= 75 && (
                            <p className="text-xs text-green-600 flex items-center gap-1">
                              <Check className="h-3 w-3" /> Free shipping on orders over $75!
                            </p>
                          )}
                        </div>
                      ) : (
                        <div className="flex justify-between pl-5">
                          <span className="text-sm text-gray-500">{shippingCarrier} ({shippingDays})</span>
                          <span>{shipping === 0 ? <span className="text-green-600">FREE</span> : `$${shipping.toFixed(2)}`}</span>
                        </div>
                      )}
                    </div>
                    
                    {giftWrap.enabled && (
                      <div className="flex justify-between"><span>Gift Wrap</span><span>${giftWrapPrice.toFixed(2)}</span></div>
                    )}
                  </div>

                  <Separator />

                  <div className="flex justify-between text-lg font-bold">
                    <span>Total</span>
                    <span>${total.toFixed(2)} CAD</span>
                  </div>

                  {/* Pay button only shown on mobile inside summary (hidden when PayPal is selected) */}
                  {paymentMethod !== "paypal" && (
                    <div className="lg:hidden">
                      <Button type="submit" className="w-full bg-[#2D2A2E] hover:bg-[#2D2A2E]/90 text-white py-6 text-lg" disabled={loading || (formData.country === "CA" && !selectedShippingRate && shippingRates.length > 0)} data-testid="checkout-pay-button-mobile">
                        {loading ? <Loader2 className="h-5 w-5 animate-spin mr-2" /> : <Lock className="h-5 w-5 mr-2" />}
                        {loading ? "Processing..." : `PAY $${total.toFixed(2)}`}
                      </Button>
                      <p className="text-xs text-center text-[#5A5A5A] mt-2">
                        <Shield className="h-3 w-3 inline mr-1" />
                        Secure checkout powered by {paymentMethod === "bambora" ? "TD Bank" : "Interac"}
                      </p>
                    </div>
                  )}
                  
                  {/* Mobile PayPal section hint when PayPal is selected */}
                  {paymentMethod === "paypal" && (
                    <div className="lg:hidden p-3 bg-[#003087]/5 rounded-lg border border-[#003087]/20 text-center">
                      <p className="text-sm text-[#003087]">
                        Complete your payment using the PayPal button below in the Payment Method section
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* 3. Shipping Address - order-3 on mobile */}
            <div className="lg:col-span-3 order-3">
              <Card>
                <CardHeader><CardTitle className="font-display text-xl">3. Shipping Address</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label htmlFor="country">Country</Label>
                    <Select value={formData.country} onValueChange={(value) => setFormData({ ...formData, country: value, province: "", postal_code: "" })}>
                      <SelectTrigger data-testid="checkout-country"><SelectValue placeholder="Select country" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="CA">🇨🇦 Canada</SelectItem>
                        <SelectItem value="US">🇺🇸 United States</SelectItem>
                        <SelectItem value="GB">🇬🇧 United Kingdom</SelectItem>
                        <SelectItem value="AU">🇦🇺 Australia</SelectItem>
                        <SelectItem value="IN">🇮🇳 India</SelectItem>
                        <SelectItem value="DE">🇩🇪 Germany</SelectItem>
                        <SelectItem value="FR">🇫🇷 France</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="address_line1">Street Address</Label>
                    <Input 
                      id="address_line1" 
                      required 
                      value={formData.address_line1} 
                      onChange={(e) => setFormData({ ...formData, address_line1: e.target.value })}
                      placeholder="123 Main Street" 
                      data-testid="checkout-address"
                    />
                  </div>
                  <div>
                    <Label htmlFor="address_line2">Apartment, suite, etc. (optional)</Label>
                    <Input id="address_line2" value={formData.address_line2} onChange={(e) => setFormData({ ...formData, address_line2: e.target.value })} placeholder="Apt, Suite, Unit, etc." />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="city">City</Label>
                      <Input id="city" required value={formData.city} onChange={(e) => setFormData({ ...formData, city: e.target.value })} data-testid="checkout-city" />
                    </div>
                    <div>
                      <Label htmlFor="province">{currentCountry.regionLabel}</Label>
                      <Select value={formData.province} onValueChange={(value) => setFormData({ ...formData, province: value })}>
                        <SelectTrigger data-testid="checkout-province"><SelectValue placeholder={`Select ${currentCountry.regionLabel.toLowerCase()}`} /></SelectTrigger>
                        <SelectContent>
                          {currentCountry.regions.map((region) => (
                            <SelectItem key={region.code} value={region.code}>{region.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="postal_code" className="flex items-center gap-2">
                      {currentCountry.postalLabel}
                      {(formData.country === "CA" || formData.country === "US") && (
                        <span className="text-xs text-green-600 font-normal">(auto-fills city & {formData.country === "CA" ? "province" : "state"})</span>
                      )}
                    </Label>
                    <div className="relative">
                      <Input 
                        id="postal_code" 
                        required 
                        value={formData.postal_code} 
                        onChange={handlePostalCodeChange} 
                        placeholder={currentCountry.postalPlaceholder} 
                        data-testid="checkout-postal" 
                      />
                      {lookingUpPostalCode && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 4. Payment Method */}
              <Card>
                <CardHeader><CardTitle className="font-display text-xl">4. Payment Method</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {/* Calculate how many methods are enabled for grid layout */}
                  {(() => {
                    const enabledCount = [bamboraEnabled, etransferEnabled, paypalEnabled].filter(Boolean).length;
                    const gridCols = enabledCount === 1 ? 'grid-cols-1' : enabledCount === 2 ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-3';
                    return (
                      <div className={`grid ${gridCols} gap-3`}>
                        {/* TD Bank / Card */}
                        {bamboraEnabled && (
                          <button type="button" onClick={() => setPaymentMethod("bambora")}
                            className={`p-4 border-2 rounded-lg text-center transition-colors ${paymentMethod === "bambora" ? "border-[#00843D] bg-[#00843D]/10" : "border-gray-200 hover:border-gray-300"}`}
                            data-testid="payment-bambora">
                            <div className="h-10 w-10 mx-auto mb-2 flex items-center justify-center bg-[#00843D] rounded-lg">
                              <span className="text-white font-bold text-sm">TD</span>
                            </div>
                            <span className="font-medium block text-sm">Credit/Debit</span>
                            <span className="text-xs text-[#5A5A5A]">Visa, MC, Debit</span>
                          </button>
                        )}

                        {/* Interac e-Transfer */}
                        {etransferEnabled && (
                          <button type="button" onClick={() => setPaymentMethod("etransfer")}
                            className={`p-4 border-2 rounded-lg text-center transition-colors ${paymentMethod === "etransfer" ? "border-[#FFCC00] bg-[#FFCC00]/10" : "border-gray-200 hover:border-gray-300"}`}
                            data-testid="payment-etransfer">
                            <div className="h-10 w-10 mx-auto mb-2 flex items-center justify-center bg-[#FFCC00] rounded-lg">
                              <span className="text-black font-bold text-xs">e-T</span>
                            </div>
                            <span className="font-medium block text-sm">Interac</span>
                            <span className="text-xs text-[#5A5A5A]">e-Transfer</span>
                          </button>
                        )}

                        {/* PayPal */}
                        {paypalEnabled && (
                          <button type="button" onClick={() => setPaymentMethod("paypal")}
                            className={`p-4 border-2 rounded-lg text-center transition-colors ${paymentMethod === "paypal" ? "border-[#003087] bg-[#003087]/10" : "border-gray-200 hover:border-gray-300"}`}
                            data-testid="payment-paypal">
                            <div className="h-10 w-10 mx-auto mb-2 flex items-center justify-center bg-[#003087] rounded-lg">
                              <span className="text-white font-bold text-xs">PP</span>
                            </div>
                            <span className="font-medium block text-sm">PayPal</span>
                            <span className="text-xs text-[#5A5A5A]">{paypalApiEnabled ? "Auto checkout" : "Pay securely"}</span>
                          </button>
                        )}
                      </div>
                    );
                  })()}

                  {/* No payment methods enabled message */}
                  {!bamboraEnabled && !etransferEnabled && !paypalEnabled && (
                    <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-center">
                      <p className="text-red-700">No payment methods are currently available. Please contact us.</p>
                    </div>
                  )}

                  {/* TD Bank / Card Form */}
                  {paymentMethod === "bambora" && bamboraEnabled && (
                    <div className="mt-4 p-4 bg-[#00843D]/5 rounded-lg border border-[#00843D]/30">
                      <div className="flex items-center gap-2 mb-4">
                        <Shield className="h-4 w-4 text-[#00843D]" />
                        <span className="text-sm text-[#00843D] font-medium">TD Secure Payment</span>
                      </div>
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="card_number">Card Number</Label>
                          <Input id="card_number" type="text" placeholder="1234 5678 9012 3456" maxLength={19}
                            value={bamboraCard?.number || ""} onChange={(e) => {
                              const value = e.target.value.replace(/\D/g, '').replace(/(\d{4})/g, '$1 ').trim();
                              setBamboraCard({...bamboraCard, number: value});
                            }} data-testid="bambora-card-number" />
                        </div>
                        <div>
                          <Label htmlFor="cardholder_name">Cardholder Name</Label>
                          <Input id="cardholder_name" type="text" placeholder="John Smith" value={bamboraCard?.name || ""}
                            onChange={(e) => setBamboraCard({...bamboraCard, name: e.target.value})} data-testid="bambora-cardholder-name" />
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <Label>Month</Label>
                            <Select value={bamboraCard?.expiry_month || ""} onValueChange={(value) => setBamboraCard({...bamboraCard, expiry_month: value})}>
                              <SelectTrigger data-testid="bambora-expiry-month"><SelectValue placeholder="MM" /></SelectTrigger>
                              <SelectContent>
                                {Array.from({length: 12}, (_, i) => String(i + 1).padStart(2, '0')).map(m => (
                                  <SelectItem key={m} value={m}>{m}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>Year</Label>
                            <Select value={bamboraCard?.expiry_year || ""} onValueChange={(value) => setBamboraCard({...bamboraCard, expiry_year: value})}>
                              <SelectTrigger data-testid="bambora-expiry-year"><SelectValue placeholder="YY" /></SelectTrigger>
                              <SelectContent>
                                {Array.from({length: 10}, (_, i) => String(new Date().getFullYear() + i).slice(-2)).map(y => (
                                  <SelectItem key={y} value={y}>{y}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>CVV</Label>
                            <Input type="text" placeholder="123" maxLength={4} value={bamboraCard?.cvv || ""}
                              onChange={(e) => setBamboraCard({...bamboraCard, cvv: e.target.value.replace(/\D/g, '')})} data-testid="bambora-cvv" />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Interac e-Transfer Instructions */}
                  {paymentMethod === "etransfer" && etransferEnabled && (
                    <div className="mt-4 p-4 bg-[#FFCC00]/10 rounded-lg border border-[#FFCC00]/50">
                      <div className="flex items-center gap-2 mb-3">
                        <Shield className="h-4 w-4 text-[#B8860B]" />
                        <span className="text-sm text-[#B8860B] font-medium">Interac e-Transfer</span>
                      </div>
                      <div className="space-y-3 text-sm">
                        <p className="text-[#2D2A2E]">After placing your order, send an Interac e-Transfer to:</p>
                        <div className="bg-white p-3 rounded-lg border">
                          <p className="font-medium text-[#2D2A2E]">{etransferEmail}</p>
                        </div>
                        <div className="space-y-1 text-[#5A5A5A]">
                          <p>• Include your <strong>Order Number</strong> in the message</p>
                          <p>• Your order will be processed once payment is received</p>
                          <p>• Processing time: 1-2 business hours</p>
                          {etransferInstructions && <p>• {etransferInstructions}</p>}
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-amber-50 rounded text-amber-800 text-xs">
                          <AlertTriangle className="h-3 w-3" />
                          <span>No auto-deposit - we'll manually accept your transfer</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* PayPal Payment Options */}
                  {paymentMethod === "paypal" && paypalEnabled && (
                    <div className="mt-4 p-4 bg-[#003087]/5 rounded-lg border border-[#003087]/30">
                      <div className="flex items-center gap-2 mb-3">
                        <Shield className="h-4 w-4 text-[#003087]" />
                        <span className="text-sm text-[#003087] font-medium">PayPal Checkout</span>
                      </div>
                      
                      {/* PayPal SDK v6 Buttons */}
                      <PayPalSDKv6Buttons
                        amount={total}
                        currency="CAD"
                        disabled={loading || !formData.first_name || !formData.last_name || !formData.email || !formData.address_line1}
                        createOrderPayload={{
                          shipping_address: formData,
                          payment_method: "paypal_api",
                          session_id: sessionId,
                          discount_codes: appliedDiscounts.map(d => d.code).length > 0 
                            ? appliedDiscounts.map(d => d.code) 
                            : (appliedDiscount?.code ? [appliedDiscount.code] : []),
                          discount_code: appliedDiscounts.map(d => d.code)[0] || appliedDiscount?.code || null,
                          discount_percent: appliedDiscount?.discount_percent || 0,
                          points_to_redeem: appliedPointsRedemption?.points || 0,
                          redemption_token: appliedPointsRedemption?.token || null
                        }}
                        onApprove={(data) => {
                          toast.success("Payment successful!");
                          clearCart();
                          navigate(`/checkout/success?order_id=${data.order_id}`);
                        }}
                        onError={(error) => {
                          console.error("PayPal error:", error);
                          toast.error(error.response?.data?.detail || "PayPal payment failed");
                          setLoading(false);
                        }}
                        onCancel={() => {
                          toast.info("PayPal payment cancelled");
                        }}
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Pay Button - Desktop (hidden when PayPal is selected since PayPal has its own button) */}
              {paymentMethod !== "paypal" && (
                <div className="hidden lg:block">
                  <Button type="submit" className="w-full bg-[#2D2A2E] hover:bg-[#2D2A2E]/90 text-white py-6 text-lg" disabled={loading || (formData.country === "CA" && !selectedShippingRate && shippingRates.length > 0)} data-testid="checkout-pay-button">
                    {loading ? <Loader2 className="h-5 w-5 animate-spin mr-2" /> : <Lock className="h-5 w-5 mr-2" />}
                    {loading ? "Processing..." : `PAY $${total.toFixed(2)}`}
                  </Button>
                  <p className="text-xs text-center text-[#5A5A5A] mt-2">
                    <Shield className="h-3 w-3 inline mr-1" />
                    Secure checkout powered by {paymentMethod === "bambora" ? "TD Bank" : "Interac"}
                  </p>
                </div>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CheckoutPage;
