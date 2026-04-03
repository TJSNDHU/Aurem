import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useCart } from '../../contexts';
import { useAuth } from '../../contexts';
import { Card, CardContent } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Loader2, MapPin, Truck, Tag, Shield, Check } from 'lucide-react';
import RootsRedemption from './RootsRedemption';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';
const PAYPAL_CLIENT_ID = process.env.REACT_APP_PAYPAL_CLIENT_ID;

// Canadian provinces
const PROVINCES = [
  { code: 'AB', name: 'Alberta' },
  { code: 'BC', name: 'British Columbia' },
  { code: 'MB', name: 'Manitoba' },
  { code: 'NB', name: 'New Brunswick' },
  { code: 'NL', name: 'Newfoundland and Labrador' },
  { code: 'NS', name: 'Nova Scotia' },
  { code: 'NT', name: 'Northwest Territories' },
  { code: 'NU', name: 'Nunavut' },
  { code: 'ON', name: 'Ontario' },
  { code: 'PE', name: 'Prince Edward Island' },
  { code: 'QC', name: 'Quebec' },
  { code: 'SK', name: 'Saskatchewan' },
  { code: 'YT', name: 'Yukon' }
];

// Default shipping options - Standard is FREE when qualifying
const DEFAULT_SHIPPING_OPTIONS = [
  { id: 'standard', courier_name: 'Standard Shipping', service_name: 'Standard', total_price: 0, transit_days: '5-7', isFreeEligible: true },
  { id: 'express', courier_name: 'Express Shipping', service_name: 'Express', total_price: 14.99, transit_days: '2-3', isFreeEligible: false }
];

const SimpleCheckout = ({ storefront = 'reroots' }) => {
  const { cart, subtotal, sessionId, clearCart, loading: cartLoading } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  
  const [discountCode, setDiscountCode] = useState('');
  const [appliedDiscount, setAppliedDiscount] = useState(null);
  const [applyingDiscount, setApplyingDiscount] = useState(false);
  const [shippingRates, setShippingRates] = useState(DEFAULT_SHIPPING_OPTIONS);
  const [selectedShippingRate, setSelectedShippingRate] = useState(DEFAULT_SHIPPING_OPTIONS[0]);
  const [loadingShippingRates, setLoadingShippingRates] = useState(false);
  
  // Roots redemption state
  const [rootsRedemption, setRootsRedemption] = useState(null);
  
  // PayPal state
  const [sdkReady, setSdkReady] = useState(false);
  const [buttonsRendered, setButtonsRendered] = useState(false);
  const paypalContainerRef = useRef(null);
  
  // Refs to store latest values for PayPal callbacks
  const formDataRef = useRef(null);
  const isFormValidRef = useRef(false);
  const sessionIdRef = useRef(null);
  const appliedDiscountRef = useRef(null);
  const selectedShippingRateRef = useRef(null);
  const finalShippingRef = useRef(0);
  const rootsRedemptionRef = useRef(null);

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    address_line1: '',
    city: '',
    province: 'ON',
    postal_code: '',
    country: 'CA',
    whatsapp_opted_in: false  // WhatsApp opt-in for order updates
  });

  // Auto-fill user data and saved address when user loads
  useEffect(() => {
    if (user) {
      setFormData(prev => ({
        ...prev,
        first_name: user.first_name || prev.first_name,
        last_name: user.last_name || prev.last_name,
        email: user.email || prev.email,
        phone: user.phone || prev.phone
      }));
      
      // Fetch user's saved shipping address
      const fetchSavedAddress = async () => {
        try {
          const token = localStorage.getItem('reroots_token');
          if (token) {
            const res = await axios.get(`${API}/users/me/address`, {
              headers: { Authorization: `Bearer ${token}` }
            });
            if (res.data && res.data.address_line1) {
              setFormData(prev => ({
                ...prev,
                address_line1: res.data.address_line1 || prev.address_line1,
                city: res.data.city || prev.city,
                province: res.data.province || prev.province,
                postal_code: res.data.postal_code || prev.postal_code
              }));
              toast.success('Saved address loaded', { duration: 2000, icon: '📍' });
            }
          }
        } catch (error) {
          // No saved address found - that's ok
          console.log('No saved address');
        }
      };
      fetchSavedAddress();
    }
  }, [user]);

  // Save address when order is placed (for future auto-fill)
  const saveUserAddress = async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      if (token && formData.address_line1) {
        await axios.put(`${API}/users/me/address`, {
          address_line1: formData.address_line1,
          city: formData.city,
          province: formData.province,
          postal_code: formData.postal_code,
          country: formData.country
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (error) {
      console.log('Failed to save address');
    }
  };

  // Postal code lookup - auto-fills city and province
  const postalCodeDebounceRef = useRef(null);
  const handlePostalCodeChange = useCallback((e) => {
    const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    
    // Format postal code as A1A 1A1
    let formatted = value;
    if (value.length > 3) {
      formatted = value.slice(0, 3) + ' ' + value.slice(3, 6);
    }
    
    setFormData(prev => ({ ...prev, postal_code: formatted }));

    if (postalCodeDebounceRef.current) {
      clearTimeout(postalCodeDebounceRef.current);
    }

    postalCodeDebounceRef.current = setTimeout(async () => {
      if (value.length >= 3) {
        try {
          const res = await axios.get(`${API}/postal-code/lookup`, {
            params: { postal_code: value }
          });
          if (res.data.found) {
            setFormData(prev => ({
              ...prev,
              city: res.data.city || prev.city,
              province: res.data.province || prev.province
            }));
            if (res.data.city) {
              toast.success(`Auto-filled: ${res.data.city}, ${res.data.province}`, {
                duration: 2000,
                icon: '📍'
              });
            }
          }
        } catch (error) {
          console.log('Postal code lookup failed');
        }
      }
    }, 400);
  }, []);

  // Track contact info for abandoned cart recovery when phone/email changes
  const trackContactDebounceRef = useRef(null);
  useEffect(() => {
    if (trackContactDebounceRef.current) {
      clearTimeout(trackContactDebounceRef.current);
    }
    
    // Only track if we have meaningful contact info
    const phoneDigits = formData.phone?.replace(/\D/g, '') || '';
    if (phoneDigits.length >= 10 || formData.email) {
      trackContactDebounceRef.current = setTimeout(async () => {
        try {
          await axios.post(`${API}/checkout/track-contact`, {
            session_id: sessionId,
            email: formData.email || null,
            phone: phoneDigits.length >= 10 ? `+1${phoneDigits}` : null,
            name: `${formData.first_name} ${formData.last_name}`.trim() || null,
            checkout_step: 'shipping'
          });
          console.log('[Checkout] Contact tracked for abandoned cart recovery');
        } catch (error) {
          // Silently fail - this is just tracking
          console.log('[Checkout] Contact tracking failed (non-critical)');
        }
      }, 2000); // 2 second debounce
    }
    
    return () => {
      if (trackContactDebounceRef.current) {
        clearTimeout(trackContactDebounceRef.current);
      }
    };
  }, [formData.phone, formData.email, formData.first_name, formData.last_name, sessionId]);

  // Fetch live shipping rates from FlagShip when address is complete
  useEffect(() => {
    const fetchShippingRates = async () => {
      if (!formData.postal_code || formData.postal_code.replace(/\s/g, '').length < 6) {
        return;
      }
      
      setLoadingShippingRates(true);
      try {
        const totalWeight = cart.items?.reduce((acc, item) => 
          acc + ((item.product?.weight_grams || 200) * item.quantity), 0) || 500;
        
        const res = await axios.post(`${API}/shipping/rates`, {
          name: `${formData.first_name} ${formData.last_name}`.trim() || 'Customer',
          address: formData.address_line1 || '123 Main St',
          city: formData.city || 'Toronto',
          state: formData.province,
          postal_code: formData.postal_code.replace(/\s/g, ''),
          country: formData.country,
          packages: [{ weight: totalWeight / 1000, description: 'Products' }]
        });
        
        if (res.data.success && res.data.rates?.length > 0) {
          // Map to our format with free shipping eligibility
          const rates = res.data.rates.slice(0, 3).map((r, idx) => ({
            id: `rate-${idx}`,
            courier_name: r.courier_name || (idx === 0 ? 'Standard Shipping' : 'Express Shipping'),
            service_name: r.service_name || 'Delivery',
            total_price: r.total_price || (idx === 0 ? 0 : 14.99),
            transit_days: r.transit_days || (idx === 0 ? '5-7' : '2-3'),
            isFreeEligible: idx === 0 // First option (cheapest) is free-eligible
          }));
          setShippingRates(rates);
          setSelectedShippingRate(rates[0]);
        }
      } catch (error) {
        console.error('Failed to fetch shipping rates, using defaults');
        // Keep default options
      }
      setLoadingShippingRates(false);
    };
    
    const timer = setTimeout(fetchShippingRates, 800);
    return () => clearTimeout(timer);
  }, [formData.postal_code, formData.province, formData.city, formData.address_line1, formData.country, cart.items, formData.first_name, formData.last_name]);

  // Apply discount code
  const applyDiscount = async () => {
    if (!discountCode.trim()) return;
    
    setApplyingDiscount(true);
    try {
      const res = await axios.post(`${API}/validate-discount`, {
        code: discountCode,
        email: formData.email
      });
      if (res.data.valid) {
        setAppliedDiscount(res.data);
        toast.success(`${res.data.discount_percent}% discount applied!`);
      } else {
        toast.error('Invalid discount code');
      }
    } catch (error) {
      toast.error('Failed to apply discount');
    }
    setApplyingDiscount(false);
  };

  // Calculate totals
  const discountAmount = appliedDiscount ? (subtotal * appliedDiscount.discount_percent / 100) : 0;
  const discountedSubtotal = subtotal - discountAmount;
  const freeShippingThreshold = 75;
  const qualifiesForFreeShipping = discountedSubtotal >= freeShippingThreshold;
  
  // Standard shipping is FREE when qualifying, Express always has cost
  const getShippingCost = (rate) => {
    if (!rate) return 0;
    if (qualifiesForFreeShipping && rate.isFreeEligible) return 0;
    return rate.total_price || 0;
  };
  
  const finalShipping = getShippingCost(selectedShippingRate);
  const taxRate = 0.13;
  // Tax is calculated on ORIGINAL subtotal (before discounts) - matches backend
  const taxAmount = subtotal * taxRate;
  
  // Calculate Roots redemption discount
  const rootsDiscount = rootsRedemption?.value || 0;
  const subtotalAfterRoots = discountedSubtotal - rootsDiscount;
  
  const total = Math.max(0, subtotalAfterRoots) + finalShipping + taxAmount;

  // Check if form is valid - phone is now required
  const isFormValid = formData.first_name && formData.last_name && 
    formData.email && formData.phone && formData.phone.replace(/\D/g, '').length >= 10 &&
    formData.address_line1 && 
    formData.city && formData.province && formData.postal_code;

  // Keep refs updated with latest values for PayPal callbacks
  useEffect(() => {
    formDataRef.current = formData;
    isFormValidRef.current = isFormValid;
    sessionIdRef.current = sessionId;
    appliedDiscountRef.current = appliedDiscount;
    selectedShippingRateRef.current = selectedShippingRate;
    finalShippingRef.current = finalShipping;
    rootsRedemptionRef.current = rootsRedemption;
  }, [formData, isFormValid, sessionId, appliedDiscount, selectedShippingRate, finalShipping, rootsRedemption]);

  // Load PayPal SDK (only once)
  useEffect(() => {
    if (window.paypal) {
      setSdkReady(true);
      return;
    }

    // Remove any existing PayPal scripts to avoid duplicates
    const existingScripts = document.querySelectorAll('script[src*="paypal.com/sdk"]');
    existingScripts.forEach(s => s.remove());

    const script = document.createElement('script');
    script.src = `https://www.paypal.com/sdk/js?client-id=${PAYPAL_CLIENT_ID}&currency=CAD&intent=capture&disable-funding=credit,paylater`;
    script.async = true;
    script.onload = () => setSdkReady(true);
    script.onerror = () => toast.error('Failed to load payment system');
    document.body.appendChild(script);
  }, []);

  // Render PayPal buttons (render immediately when SDK is ready)
  useEffect(() => {
    if (!sdkReady || !window.paypal || !paypalContainerRef.current || buttonsRendered) {
      return;
    }

    // Clear container first
    paypalContainerRef.current.innerHTML = '';

    const createPayPalOrder = async () => {
      // Use refs to get latest values
      const currentFormData = formDataRef.current;
      const currentIsFormValid = isFormValidRef.current;
      const currentSessionId = sessionIdRef.current;
      const currentAppliedDiscount = appliedDiscountRef.current;
      const currentSelectedShippingRate = selectedShippingRateRef.current;
      const currentFinalShipping = finalShippingRef.current;
      const currentRootsRedemption = rootsRedemptionRef.current;
      
      // Validate form before creating order
      if (!currentIsFormValid) {
        toast.error('Please fill in all required shipping information');
        return Promise.reject(new Error('Form validation failed'));
      }
      
      const token = localStorage.getItem('reroots_token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      // Save user's address for future auto-fill
      await saveUserAddress();

      // Create internal order with shipping info for auto-fulfillment
      const orderResponse = await axios.post(`${API}/orders`, {
        shipping_address: currentFormData,
        payment_method: 'paypal_api',
        session_id: currentSessionId,
        discount_code: currentAppliedDiscount?.code || null,
        discount_percent: currentAppliedDiscount?.discount_percent || 0,
        shipping_method: currentSelectedShippingRate?.service_name || 'Standard',
        shipping_cost: currentFinalShipping,
        // Include shipping details for auto-fulfillment
        shipping_carrier: currentSelectedShippingRate?.courier_name || 'Standard Shipping',
        auto_ship: true, // Flag for automatic shipping label creation
        // Roots redemption
        points_to_redeem: currentRootsRedemption?.points || 0,
        redemption_token: currentRootsRedemption?.token || null,
        // Track which storefront the order came from
        storefront: storefront
      }, { headers });

      const internalOrderId = orderResponse.data.order_id;
      localStorage.setItem('pending_paypal_order', internalOrderId);

      // Create PayPal order
      const paypalResponse = await axios.post(
        `${API}/payments/paypal/create-order`,
        { order_id: internalOrderId },
        { headers }
      );

      localStorage.setItem('pending_paypal_id', paypalResponse.data.id);
      return paypalResponse.data.id;
    };

    const onPayPalApprove = async (data) => {
      const token = localStorage.getItem('reroots_token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const pendingOrderId = localStorage.getItem('pending_paypal_order');

      // Capture payment - this triggers auto-shipping in backend
      await axios.post(
        `${API}/payments/paypal/capture`,
        { orderID: data.orderID, order_id: pendingOrderId },
        { headers }
      );

      localStorage.removeItem('pending_paypal_order');
      localStorage.removeItem('pending_paypal_id');

      toast.success('Payment successful! Your order is being processed.');
      clearCart();
      navigate(`/checkout/success?order_id=${pendingOrderId}`);
    };

    // Render single PayPal button set with error handling
    try {
      window.paypal.Buttons({
        style: {
          layout: 'vertical',
          color: 'gold',
          shape: 'rect',
          label: 'paypal',
          tagline: false
        },
        createOrder: createPayPalOrder,
        onApprove: onPayPalApprove,
        onCancel: () => toast.info('Payment cancelled'),
        onError: (err) => {
          // Ignore "zoid destroyed" errors during navigation
          if (err?.message?.includes('zoid destroyed')) {
            console.log('PayPal component cleanup during navigation');
            return;
          }
          console.error('PayPal error:', err);
          toast.error('Payment failed. Please try again.');
        }
      }).render(paypalContainerRef.current).then(() => {
        setButtonsRendered(true);
      }).catch((err) => {
        // Ignore render errors during component cleanup
        if (err?.message?.includes('zoid destroyed') || err?.message?.includes('Container element')) {
          console.log('PayPal render cleanup');
          return;
        }
        console.error('PayPal render error:', err);
      });
    } catch (err) {
      console.error('PayPal initialization error:', err);
    }

  }, [sdkReady, buttonsRendered]); // Render buttons once SDK is ready, validation happens in createOrder

  if (cartLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FDF9F9]">
        <Loader2 className="h-8 w-8 animate-spin text-[#2D2A2E]" />
      </div>
    );
  }

  if (!cart.items || cart.items.length === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#FDF9F9] px-4">
        <h1 className="text-2xl font-bold text-[#2D2A2E] mb-4">Your cart is empty</h1>
        <button 
          onClick={() => navigate('/shop')}
          className="bg-[#2D2A2E] text-white px-6 py-3 rounded-lg"
        >
          Continue Shopping
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FDF9F9] pt-20 pb-12">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-2xl font-bold text-[#2D2A2E] mb-6 text-center">Checkout</h1>
        
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Section 1: Customer Info & Shipping */}
          <Card className="border-0 shadow-sm">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-[#2D2A2E] text-white rounded-full flex items-center justify-center text-sm font-bold">1</div>
                <h2 className="text-lg font-semibold text-[#2D2A2E]">Shipping Information</h2>
              </div>

              {user && (
                <div className="bg-green-50 text-green-700 text-sm p-2 rounded mb-4 flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  Logged in as {user.email}
                </div>
              )}

              <div className="space-y-4">
                {/* Phone Number - FIRST for early capture */}
                <div className="bg-gradient-to-r from-[#F8A5B8]/10 to-[#E88DA0]/10 p-4 rounded-lg border border-[#F8A5B8]/20">
                  <Label className="text-sm font-medium text-[#2D2A2E] flex items-center gap-2">
                    📱 Phone Number * <span className="text-xs text-gray-500 font-normal">(for order updates)</span>
                  </Label>
                  <Input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, '');
                      let formatted = digits;
                      if (digits.length > 3 && digits.length <= 6) {
                        formatted = `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
                      } else if (digits.length > 6) {
                        formatted = `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
                      }
                      setFormData(prev => ({ ...prev, phone: formatted }));
                    }}
                    className="mt-2 h-12 text-lg"
                    placeholder="(416) 555-0123"
                    required
                    data-testid="checkout-phone"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    You'll receive shipping updates & tracking info via SMS
                  </p>
                  
                  {/* WhatsApp Opt-In Checkbox */}
                  <label className="flex items-start gap-3 mt-3 p-3 bg-green-50/50 rounded-lg border border-green-200/50 cursor-pointer hover:bg-green-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={formData.whatsapp_opted_in}
                      onChange={(e) => setFormData(prev => ({ ...prev, whatsapp_opted_in: e.target.checked }))}
                      className="mt-0.5 w-5 h-5 rounded border-green-400 text-green-600 focus:ring-green-500"
                      data-testid="checkout-whatsapp-optin"
                    />
                    <span className="text-sm text-gray-700">
                      <span className="font-medium text-green-700">💬 Get updates via WhatsApp</span>
                      <br />
                      <span className="text-xs text-gray-500">Order updates + skincare tips directly on WhatsApp</span>
                    </span>
                  </label>
                </div>

                {/* Name Row */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-sm text-gray-600">First Name *</Label>
                    <Input
                      value={formData.first_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, first_name: e.target.value }))}
                      className="mt-1"
                      placeholder="John"
                    />
                  </div>
                  <div>
                    <Label className="text-sm text-gray-600">Last Name *</Label>
                    <Input
                      value={formData.last_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, last_name: e.target.value }))}
                      className="mt-1"
                      placeholder="Doe"
                    />
                  </div>
                </div>

                {/* Email */}
                <div>
                  <Label className="text-sm text-gray-600">Email *</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    className="mt-1"
                    placeholder="john@example.com"
                  />
                </div>

                {/* Postal Code First - Auto-fills City & Province */}
                <div>
                  <Label className="text-sm text-gray-600">Postal Code * (auto-fills city & province)</Label>
                  <Input
                    value={formData.postal_code}
                    onChange={handlePostalCodeChange}
                    className="mt-1"
                    placeholder="M5V 1J1"
                    maxLength={7}
                  />
                </div>

                {/* Address */}
                <div>
                  <Label className="text-sm text-gray-600">Street Address *</Label>
                  <Input
                    value={formData.address_line1}
                    onChange={(e) => setFormData(prev => ({ ...prev, address_line1: e.target.value }))}
                    className="mt-1"
                    placeholder="123 Main Street"
                  />
                </div>

                {/* City & Province (auto-filled from postal code) */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-sm text-gray-600">City *</Label>
                    <Input
                      value={formData.city}
                      onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
                      className="mt-1"
                      placeholder="Toronto"
                    />
                  </div>
                  <div>
                    <Label className="text-sm text-gray-600">Province *</Label>
                    <Select 
                      value={formData.province} 
                      onValueChange={(v) => setFormData(prev => ({ ...prev, province: v }))}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PROVINCES.map(p => (
                          <SelectItem key={p.code} value={p.code}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Shipping Options */}
                <div className="mt-4 pt-4 border-t">
                  <Label className="text-sm text-gray-600 flex items-center gap-2 mb-3">
                    <Truck className="h-4 w-4" /> Shipping Method
                  </Label>
                  
                  {loadingShippingRates ? (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading shipping options...
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {shippingRates.map((rate) => {
                        const isFree = qualifiesForFreeShipping && rate.isFreeEligible;
                        return (
                          <label 
                            key={rate.id}
                            className={`flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-colors ${
                              selectedShippingRate?.id === rate.id 
                                ? 'border-[#2D2A2E] bg-gray-50' 
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <input
                                type="radio"
                                name="shipping"
                                checked={selectedShippingRate?.id === rate.id}
                                onChange={() => setSelectedShippingRate(rate)}
                                className="w-4 h-4 accent-[#2D2A2E]"
                              />
                              <div>
                                <p className="font-medium text-sm flex items-center gap-2">
                                  {rate.courier_name}
                                  {isFree && (
                                    <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded">FREE</span>
                                  )}
                                </p>
                                <p className="text-xs text-gray-500">{rate.transit_days} business days</p>
                              </div>
                            </div>
                            <span className={`font-semibold text-sm ${isFree ? 'text-green-600 line-through' : ''}`}>
                              {isFree ? `$${rate.total_price?.toFixed(2)}` : `$${rate.total_price?.toFixed(2)}`}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                  
                  {qualifiesForFreeShipping && (
                    <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
                      <Check className="h-3 w-3" /> You qualify for FREE Standard Shipping!
                    </p>
                  )}
                  {!qualifiesForFreeShipping && (
                    <p className="text-xs text-gray-500 mt-2">
                      Free standard shipping on orders over ${freeShippingThreshold}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Section 2: Order Summary & Payment */}
          <Card className="border-0 shadow-sm">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-[#2D2A2E] text-white rounded-full flex items-center justify-center text-sm font-bold">2</div>
                <h2 className="text-lg font-semibold text-[#2D2A2E]">Order Summary</h2>
              </div>

              {/* Cart Items */}
              <div className="space-y-3 mb-4">
                {cart.items?.map((item, idx) => {
                  // Check if this is a combo item (new single line item structure)
                  const isCombo = item.item_type === "combo";
                  
                  if (isCombo) {
                    // Render COMBO as single line item
                    const comboPrice = item.price || 0;
                    return (
                      <div key={item.combo_id || idx} className="p-3 bg-purple-50 rounded-lg border border-purple-200">
                        {/* Combo Badge */}
                        <div className="flex items-center gap-2 mb-2">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-semibold rounded-full">
                            ✨ COMBO
                          </span>
                          {item.discount_percent > 0 && (
                            <span className="text-xs text-green-600 font-medium">Save {Number(item.discount_percent).toFixed(0)}%</span>
                          )}
                        </div>
                        
                        {/* Combo Name */}
                        <p className="font-medium text-sm text-[#2D2A2E] mb-1">{item.combo_name}</p>
                        
                        {/* Includes: Product names */}
                        {item.products && item.products.length > 0 && (
                          <p className="text-xs text-gray-500 mb-2">
                            Includes: {item.products.map(p => p.name).join(' + ')}
                          </p>
                        )}
                        
                        <div className="flex justify-between items-center">
                          <p className="text-xs text-gray-500">Qty: {item.quantity}</p>
                          <div className="text-right">
                            <p className="font-semibold text-sm">${(comboPrice * item.quantity).toFixed(2)}</p>
                            {item.original_price && item.original_price > comboPrice && (
                              <p className="text-xs text-gray-400 line-through">${(item.original_price * item.quantity).toFixed(2)}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  }
                  
                  // Regular product item
                  const itemPrice = item.combo_price !== undefined && item.combo_price !== null
                    ? item.combo_price
                    : (item.product?.price || 0);
                  
                  return (
                    <div key={idx} className="flex gap-3">
                      <img 
                        src={item.product?.images?.[0] || '/placeholder.jpg'} 
                        alt={item.product?.name}
                        className="w-16 h-16 object-cover rounded-lg bg-gray-100"
                      />
                      <div className="flex-1">
                        <p className="font-medium text-sm text-[#2D2A2E] line-clamp-1">{item.product?.name}</p>
                        {item.combo_name && (
                          <p className="text-xs text-purple-600 font-medium">{item.combo_name}</p>
                        )}
                        <p className="text-xs text-gray-500">Qty: {item.quantity}</p>
                      </div>
                      <p className="font-semibold text-sm">${(itemPrice * item.quantity).toFixed(2)}</p>
                    </div>
                  );
                })}
              </div>

              {/* Discount Code */}
              <div className="flex gap-2 mb-4">
                <Input
                  value={discountCode}
                  onChange={(e) => setDiscountCode(e.target.value.toUpperCase())}
                  placeholder="Discount code"
                  className="flex-1"
                />
                <button
                  onClick={applyDiscount}
                  disabled={applyingDiscount || !discountCode}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-sm font-medium rounded-lg disabled:opacity-50"
                >
                  {applyingDiscount ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Apply'}
                </button>
              </div>

              {appliedDiscount && (
                <div className="bg-green-50 text-green-700 text-sm p-2 rounded mb-4 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Tag className="h-4 w-4" />
                    {appliedDiscount.code}: {appliedDiscount.discount_percent}% off
                  </span>
                  <button onClick={() => setAppliedDiscount(null)} className="text-green-800 hover:underline text-xs">
                    Remove
                  </button>
                </div>
              )}

              {/* Roots Redemption */}
              <RootsRedemption
                subtotal={discountedSubtotal}
                onRedemptionApplied={(redemption) => setRootsRedemption(redemption)}
                onRedemptionRemoved={() => setRootsRedemption(null)}
              />

              {/* Price Breakdown */}
              <div className="border-t pt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Subtotal</span>
                  <span>${subtotal.toFixed(2)}</span>
                </div>
                {appliedDiscount && (
                  <div className="flex justify-between text-green-600">
                    <span>Discount ({appliedDiscount.discount_percent}%)</span>
                    <span>-${discountAmount.toFixed(2)}</span>
                  </div>
                )}
                {rootsRedemption && (
                  <div className="flex justify-between text-emerald-600">
                    <span>Roots Redeemed ({rootsRedemption.points})</span>
                    <span>-${rootsRedemption.value.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-600">
                    Shipping ({selectedShippingRate?.courier_name})
                  </span>
                  <span className={finalShipping === 0 ? 'text-green-600' : ''}>
                    {finalShipping === 0 ? 'FREE' : `$${finalShipping.toFixed(2)}`}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Tax (HST 13%)</span>
                  <span>${taxAmount.toFixed(2)}</span>
                </div>
                <div className="flex justify-between font-bold text-lg pt-2 border-t">
                  <span>Total</span>
                  <span>${total.toFixed(2)} CAD</span>
                </div>
              </div>

              {/* Payment Buttons */}
              <div className="mt-6">
                {!isFormValid && (
                  <div className="bg-amber-50 text-amber-700 text-sm p-3 rounded-lg mb-4 flex items-center gap-2">
                    <MapPin className="h-4 w-4" />
                    Please fill in your shipping information above
                  </div>
                )}

                {!sdkReady ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-[#003087]" />
                    <span className="ml-2 text-sm text-gray-600">Loading payment options...</span>
                  </div>
                ) : (
                  <div 
                    ref={paypalContainerRef}
                    className={!isFormValid ? 'opacity-50 pointer-events-none' : ''}
                    style={{ minHeight: '150px' }}
                  />
                )}

                <p className="text-xs text-center text-gray-500 mt-4 flex items-center justify-center gap-1">
                  <Shield className="h-3 w-3" />
                  Secure checkout powered by PayPal
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default SimpleCheckout;
