import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { 
  Sparkles, DollarSign, Check, Info, 
  Zap, Mic, CreditCard, TrendingUp, MessageSquare
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Custom Subscription Builder
 * A-la-carte service selection with real-time pricing
 */
const CustomSubscriptionBuilder = () => {
  const [services, setServices] = useState([]);
  const [selectedServices, setSelectedServices] = useState([]);
  const [billingCycle, setBillingCycle] = useState('monthly');
  const [pricing, setPricing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [baseFee, setBaseFee] = useState(49);
  const [annualDiscount, setAnnualDiscount] = useState(20);

  // Load available services
  useEffect(() => {
    loadAvailableServices();
  }, []);

  // Calculate pricing when selection changes
  useEffect(() => {
    if (selectedServices.length > 0) {
      calculatePricing();
    } else {
      setPricing(null);
    }
  }, [selectedServices, billingCycle]);

  const loadAvailableServices = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/subscriptions/custom/available-services`);
      const data = await response.json();
      
      setServices(data.services.filter(s => s.available_for_custom));
      setBaseFee(data.base_platform_fee);
      setAnnualDiscount(data.annual_discount);
    } catch (error) {
      console.error('Failed to load services:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculatePricing = async () => {
    try {
      const response = await fetch(`${API_URL}/api/subscriptions/custom/calculate-pricing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selected_services: selectedServices,
          billing_cycle: billingCycle
        })
      });
      
      const data = await response.json();
      setPricing(data);
    } catch (error) {
      console.error('Failed to calculate pricing:', error);
    }
  };

  const toggleService = (serviceId) => {
    setSelectedServices(prev => 
      prev.includes(serviceId)
        ? prev.filter(id => id !== serviceId)
        : [...prev, serviceId]
    );
  };

  const handleCreateSubscription = async () => {
    try {
      setLoading(true);
      
      // Get user ID from localStorage (or auth context)
      const userId = localStorage.getItem('user_id') || 'demo_user';
      
      const response = await fetch(`${API_URL}/api/subscriptions/custom/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          selected_services: selectedServices,
          billing_cycle: billingCycle
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert(`✅ Custom plan created! Plan ID: ${data.plan_id}\n\nNext: Proceed to checkout`);
        // Redirect to checkout
        window.location.href = data.checkout_url;
      }
    } catch (error) {
      console.error('Failed to create subscription:', error);
      alert('❌ Failed to create subscription. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'llm': return <MessageSquare className="h-5 w-5" />;
      case 'voice': return <Mic className="h-5 w-5" />;
      case 'payment': return <CreditCard className="h-5 w-5" />;
      case 'analytics': return <TrendingUp className="h-5 w-5" />;
      default: return <Zap className="h-5 w-5" />;
    }
  };

  const getCategoryColor = (category) => {
    switch (category) {
      case 'llm': return 'bg-blue-100 text-blue-700';
      case 'voice': return 'bg-purple-100 text-purple-700';
      case 'payment': return 'bg-green-100 text-green-700';
      case 'analytics': return 'bg-orange-100 text-orange-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2 flex items-center justify-center gap-2">
            <Sparkles className="h-8 w-8 text-yellow-500" />
            Build Your Perfect Plan
          </h1>
          <p className="text-slate-600 text-lg">
            Select only the services you need. Pay only for what you use.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Services Selection */}
          <div className="lg:col-span-2 space-y-4">
            
            {/* Billing Cycle Toggle */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-700">Billing Cycle</span>
                  <div className="flex gap-2">
                    <Button
                      variant={billingCycle === 'monthly' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setBillingCycle('monthly')}
                      data-testid="billing-cycle-monthly"
                    >
                      Monthly
                    </Button>
                    <Button
                      variant={billingCycle === 'annual' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setBillingCycle('annual')}
                      className="relative"
                      data-testid="billing-cycle-annual"
                    >
                      Annual
                      <Badge className="ml-2 bg-green-500 text-white">
                        Save {annualDiscount}%
                      </Badge>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Service Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {services.map((service) => {
                const isSelected = selectedServices.includes(service.service_id);
                
                return (
                  <Card
                    key={service.service_id}
                    className={`cursor-pointer transition-all ${
                      isSelected 
                        ? 'border-2 border-blue-500 shadow-lg' 
                        : 'border hover:border-slate-300'
                    }`}
                    onClick={() => toggleService(service.service_id)}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${getCategoryColor(service.category)}`}>
                            {getCategoryIcon(service.category)}
                          </div>
                          <div>
                            <CardTitle className="text-base">{service.name}</CardTitle>
                            <CardDescription className="text-xs">
                              {service.provider}
                            </CardDescription>
                          </div>
                        </div>
                        <Checkbox 
                          checked={isSelected}
                          onCheckedChange={() => toggleService(service.service_id)}
                        />
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-slate-600">
                          {service.category.toUpperCase()}
                        </span>
                        <span className="text-lg font-bold text-slate-900">
                          ${service.custom_price_monthly}/mo
                        </span>
                      </div>
                      {service.status === 'active' && (
                        <Badge variant="outline" className="mt-2 text-green-600 border-green-600">
                          <Check className="h-3 w-3 mr-1" />
                          Active
                        </Badge>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>

          {/* Pricing Summary */}
          <div className="lg:col-span-1">
            <div className="sticky top-6">
              <Card className="border-2 border-slate-200" data-testid="pricing-summary-card">
                <CardHeader className="bg-gradient-to-br from-blue-50 to-purple-50">
                  <CardTitle className="flex items-center gap-2">
                    <DollarSign className="h-5 w-5" />
                    Pricing Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-6 space-y-4">
                  
                  {/* Base Fee */}
                  <div className="flex justify-between items-center pb-3 border-b">
                    <span className="text-sm text-slate-600">Platform Access</span>
                    <span className="font-medium" data-testid="base-fee">${baseFee}/mo</span>
                  </div>

                  {/* Selected Services */}
                  {pricing && Object.keys(pricing.service_fees).length > 0 ? (
                    <div className="space-y-2">
                      <span className="text-sm font-medium text-slate-700">Selected Services:</span>
                      {Object.entries(pricing.service_fees).map(([serviceId, price]) => (
                        <div key={serviceId} className="flex justify-between items-center text-sm">
                          <span className="text-slate-600">{serviceId}</span>
                          <span className="text-slate-900">${price}/mo</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-slate-400 text-sm">
                      <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      Select services to see pricing
                    </div>
                  )}

                  {pricing && (
                    <>
                      {/* Total */}
                      <div className="pt-3 border-t">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm text-slate-600">Monthly Total</span>
                          <span className="text-lg font-bold text-slate-900" data-testid="monthly-total">
                            ${pricing.total_monthly.toFixed(2)}
                          </span>
                        </div>
                        
                        {billingCycle === 'annual' && (
                          <>
                            <div className="flex justify-between items-center mb-2">
                              <span className="text-sm text-slate-600">Annual Total</span>
                              <span className="text-lg font-bold text-green-600" data-testid="annual-total">
                                ${pricing.total_annual.toFixed(2)}
                              </span>
                            </div>
                            <div className="bg-green-50 border border-green-200 rounded p-2 text-center">
                              <span className="text-sm text-green-700 font-medium" data-testid="annual-savings">
                                💰 Save ${pricing.annual_savings.toFixed(2)} annually
                              </span>
                            </div>
                          </>
                        )}
                      </div>

                      {/* CTA */}
                      <Button 
                        className="w-full mt-4" 
                        size="lg"
                        onClick={handleCreateSubscription}
                        disabled={loading || selectedServices.length === 0}
                        data-testid="checkout-button"
                      >
                        {loading ? 'Processing...' : 'Continue to Checkout'}
                      </Button>
                    </>
                  )}

                  {/* Info */}
                  <div className="pt-4 border-t text-xs text-slate-500 space-y-1">
                    <p>✓ Cancel anytime</p>
                    <p>✓ Add/remove services monthly</p>
                    <p>✓ No hidden fees</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustomSubscriptionBuilder;
