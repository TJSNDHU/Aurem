/**
 * ReRoots AI Subscription Plans Page
 * Commercial subscription plans with Stripe/Razorpay integration
 */

import React, { useState, useEffect } from 'react';
import { Check, Zap, Shield, Globe, Star, ArrowRight } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SubscriptionPlans = () => {
  const [tiers, setTiers] = useState(null);
  const [features, setFeatures] = useState(null);
  const [billingCycle, setBillingCycle] = useState('monthly');
  const [selectedTier, setSelectedTier] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showCheckout, setShowCheckout] = useState(false);

  useEffect(() => {
    fetchTiers();
  }, []);

  const fetchTiers = async () => {
    try {
      const res = await fetch(`${API_URL}/api/subscriptions/tiers`);
      if (res.ok) {
        const data = await res.json();
        setTiers(data.tiers);
        setFeatures(data.features);
      }
    } catch (err) {
      console.error('Failed to fetch tiers:', err);
    }
    setIsLoading(false);
  };

  const tierOrder = ['starter', 'pro', 'business', 'enterprise'];
  const tierColors = {
    starter: 'from-gray-500 to-gray-600',
    pro: 'from-green-500 to-green-600',
    business: 'from-blue-500 to-blue-600',
    enterprise: 'from-purple-500 to-purple-600'
  };

  const tierIcons = {
    starter: <Zap className="w-6 h-6" />,
    pro: <Star className="w-6 h-6" />,
    business: <Globe className="w-6 h-6" />,
    enterprise: <Shield className="w-6 h-6" />
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 text-white">
      {/* Header */}
      <header className="text-center py-16 px-4">
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500/20 rounded-full text-amber-400 text-sm mb-6">
          <Zap className="w-4 h-4" />
          <span>Commercial AI Platform</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold mb-4">
          ReRoots AI <span className="text-amber-400">Subscription Plans</span>
        </h1>
        <p className="text-gray-400 max-w-2xl mx-auto text-lg">
          Powerful AI features for your skincare business. Scale your operations with intelligent automation.
        </p>

        {/* Billing Toggle */}
        <div className="flex items-center justify-center gap-4 mt-8">
          <span className={billingCycle === 'monthly' ? 'text-white' : 'text-gray-500'}>Monthly</span>
          <button
            onClick={() => setBillingCycle(prev => prev === 'monthly' ? 'yearly' : 'monthly')}
            className="w-14 h-7 rounded-full bg-white/10 relative"
          >
            <div className={`w-6 h-6 rounded-full bg-amber-500 absolute top-0.5 transition-all ${
              billingCycle === 'yearly' ? 'left-7' : 'left-0.5'
            }`} />
          </button>
          <span className={billingCycle === 'yearly' ? 'text-white' : 'text-gray-500'}>
            Yearly <span className="text-green-400 text-sm">(Save 17%)</span>
          </span>
        </div>
      </header>

      {/* Pricing Cards */}
      <div className="max-w-7xl mx-auto px-4 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {tiers && tierOrder.map((tierId, idx) => {
            const tier = tiers[tierId];
            if (!tier) return null;
            
            const price = billingCycle === 'yearly' ? tier.price_yearly : tier.price_monthly;
            const monthlyPrice = billingCycle === 'yearly' ? Math.round(tier.price_yearly / 12) : tier.price_monthly;
            const isPopular = tierId === 'business';

            return (
              <div
                key={tierId}
                className={`relative rounded-2xl p-6 transition-all hover:scale-105 ${
                  isPopular
                    ? 'bg-gradient-to-br from-amber-500/20 to-amber-600/10 border-2 border-amber-500/50'
                    : 'bg-white/5 border border-white/10'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-amber-500 text-black text-xs font-bold rounded-full">
                    MOST POPULAR
                  </div>
                )}

                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${tierColors[tierId]} flex items-center justify-center mb-4`}>
                  {tierIcons[tierId]}
                </div>

                <h3 className="text-xl font-bold mb-1">{tier.name}</h3>
                <p className="text-gray-400 text-sm mb-4">{tier.description}</p>

                <div className="mb-6">
                  <span className="text-4xl font-bold">${monthlyPrice}</span>
                  <span className="text-gray-400">/month</span>
                  {billingCycle === 'yearly' && (
                    <div className="text-sm text-green-400 mt-1">Billed ${price}/year</div>
                  )}
                </div>

                {/* Features */}
                <div className="space-y-3 mb-6">
                  <div className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-green-400" />
                    <span>{tier.api_calls_limit.toLocaleString()} API calls/month</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-green-400" />
                    <span>{tier.features.length} AI features</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-green-400" />
                    <span>{tier.rate_limit_per_min} requests/min</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Check className="w-4 h-4 text-green-400" />
                    <span className="capitalize">{tier.support.replace('_', ' ')} support</span>
                  </div>
                </div>

                {/* Feature List */}
                <div className="border-t border-white/10 pt-4 mb-6">
                  <div className="text-xs text-gray-500 mb-2">INCLUDED FEATURES:</div>
                  <div className="flex flex-wrap gap-1">
                    {tier.features.slice(0, 6).map((feat, i) => (
                      <span key={i} className="px-2 py-0.5 bg-white/5 rounded text-xs text-gray-400">
                        {features?.[feat]?.name || feat}
                      </span>
                    ))}
                    {tier.features.length > 6 && (
                      <span className="px-2 py-0.5 bg-amber-500/20 rounded text-xs text-amber-400">
                        +{tier.features.length - 6} more
                      </span>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => {
                    setSelectedTier(tierId);
                    setShowCheckout(true);
                  }}
                  className={`w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2 transition-all ${
                    isPopular
                      ? 'bg-amber-500 text-black hover:bg-amber-400'
                      : 'bg-white/10 hover:bg-white/20'
                  }`}
                >
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Custom Plan */}
        <div className="mt-12 p-8 rounded-2xl bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 text-center">
          <h3 className="text-2xl font-bold mb-2">Need a Custom Plan?</h3>
          <p className="text-gray-400 mb-6">
            For large enterprises with specific requirements, we offer custom plans with unlimited API calls, dedicated support, and tailored integrations.
          </p>
          <button className="px-8 py-3 bg-white/10 rounded-xl font-medium hover:bg-white/20 transition-all">
            Contact Sales
          </button>
        </div>

        {/* All Features Grid */}
        <div className="mt-20">
          <h2 className="text-2xl font-bold text-center mb-10">All AI Features</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {features && Object.entries(features).map(([id, feat]) => (
              <div key={id} className="p-4 rounded-xl bg-white/5 border border-white/10 hover:border-amber-500/50 transition-all">
                <div className="text-2xl mb-2">{getFeatureIcon(id)}</div>
                <div className="font-medium text-sm">{feat.name}</div>
                <div className="text-xs text-gray-500 mt-1">{feat.description}</div>
              </div>
            ))}
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-20 max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-10">Frequently Asked Questions</h2>
          <div className="space-y-4">
            {[
              {
                q: "How does billing work?",
                a: "You'll be charged at the beginning of each billing cycle. Monthly plans are billed every 30 days, yearly plans are billed annually with a 17% discount."
              },
              {
                q: "Can I upgrade or downgrade my plan?",
                a: "Yes! You can upgrade at any time and the change takes effect immediately. When downgrading, you'll retain your current features until the end of the billing cycle."
              },
              {
                q: "What happens if I exceed my API limit?",
                a: "We'll notify you when you reach 80% of your limit. You can either upgrade your plan or purchase additional API calls on-demand."
              },
              {
                q: "Do you offer refunds?",
                a: "We offer a 14-day money-back guarantee for all plans. If you're not satisfied, contact us within 14 days of purchase for a full refund."
              },
              {
                q: "What payment methods do you accept?",
                a: "We accept all major credit cards via Stripe, and UPI/NetBanking via Razorpay for customers in India."
              }
            ].map((faq, i) => (
              <details key={i} className="group p-4 rounded-xl bg-white/5 border border-white/10">
                <summary className="font-medium cursor-pointer list-none flex items-center justify-between">
                  {faq.q}
                  <span className="text-gray-500 group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <p className="text-gray-400 mt-3 text-sm">{faq.a}</p>
              </details>
            ))}
          </div>
        </div>
      </div>

      {/* Checkout Modal */}
      {showCheckout && selectedTier && tiers && (
        <CheckoutModal
          tier={tiers[selectedTier]}
          tierId={selectedTier}
          billingCycle={billingCycle}
          onClose={() => setShowCheckout(false)}
        />
      )}
    </div>
  );
};


// Checkout Modal Component
const CheckoutModal = ({ tier, tierId, billingCycle, onClose }) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    paymentMethod: 'stripe'
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);

  const price = billingCycle === 'yearly' ? tier.price_yearly : tier.price_monthly;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsProcessing(true);

    try {
      const res = await fetch(`${API_URL}/api/subscriptions/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subscriber_email: formData.email,
          subscriber_name: formData.name,
          tier: tierId,
          billing_cycle: billingCycle,
          payment_method: formData.paymentMethod
        })
      });

      const data = await res.json();
      if (res.ok) {
        setResult({
          success: true,
          subscription: data.subscription,
          apiKey: data.api_key
        });
      } else {
        setResult({ success: false, error: data.detail });
      }
    } catch (err) {
      setResult({ success: false, error: 'Failed to create subscription' });
    }

    setIsProcessing(false);
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="w-full max-w-md bg-gray-900 rounded-2xl border border-white/10 overflow-hidden">
        <div className="p-6 border-b border-white/10">
          <h3 className="text-xl font-bold">Subscribe to {tier.name}</h3>
          <p className="text-gray-400 text-sm mt-1">
            ${price}/{billingCycle === 'yearly' ? 'year' : 'month'}
          </p>
        </div>

        {result ? (
          <div className="p-6">
            {result.success ? (
              <div className="text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-500/20 flex items-center justify-center">
                  <Check className="w-8 h-8 text-green-400" />
                </div>
                <h4 className="text-lg font-bold mb-2">Subscription Created!</h4>
                <p className="text-gray-400 text-sm mb-4">Your API key has been generated.</p>
                
                <div className="p-4 bg-black/50 rounded-xl text-left mb-4">
                  <div className="text-xs text-gray-500 mb-1">Your API Key (save this!):</div>
                  <code className="text-amber-400 text-sm break-all">{result.apiKey}</code>
                </div>

                <button
                  onClick={onClose}
                  className="w-full py-3 bg-amber-500 text-black rounded-xl font-medium"
                >
                  Done
                </button>
              </div>
            ) : (
              <div className="text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
                  <span className="text-2xl">❌</span>
                </div>
                <h4 className="text-lg font-bold mb-2">Subscription Failed</h4>
                <p className="text-red-400 text-sm mb-4">{result.error}</p>
                <button
                  onClick={() => setResult(null)}
                  className="w-full py-3 bg-white/10 rounded-xl font-medium"
                >
                  Try Again
                </button>
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Full Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-4 py-3 bg-white/10 border border-white/10 rounded-xl text-white focus:border-amber-500 focus:outline-none"
                placeholder="John Doe"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email Address</label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-4 py-3 bg-white/10 border border-white/10 rounded-xl text-white focus:border-amber-500 focus:outline-none"
                placeholder="john@company.com"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Payment Method</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, paymentMethod: 'stripe' })}
                  className={`p-3 rounded-xl border text-center ${
                    formData.paymentMethod === 'stripe'
                      ? 'border-amber-500 bg-amber-500/10'
                      : 'border-white/10 bg-white/5'
                  }`}
                >
                  <div className="font-medium">💳 Stripe</div>
                  <div className="text-xs text-gray-500">Credit/Debit</div>
                </button>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, paymentMethod: 'razorpay' })}
                  className={`p-3 rounded-xl border text-center ${
                    formData.paymentMethod === 'razorpay'
                      ? 'border-amber-500 bg-amber-500/10'
                      : 'border-white/10 bg-white/5'
                  }`}
                >
                  <div className="font-medium">🏦 Razorpay</div>
                  <div className="text-xs text-gray-500">UPI/NetBanking</div>
                </button>
              </div>
            </div>

            <div className="pt-4 border-t border-white/10">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">{tier.name} Plan</span>
                <span>${price}</span>
              </div>
              <div className="flex justify-between font-bold">
                <span>Total</span>
                <span className="text-amber-400">${price}/{billingCycle === 'yearly' ? 'yr' : 'mo'}</span>
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-3 bg-white/10 rounded-xl font-medium hover:bg-white/20"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isProcessing}
                className="flex-1 py-3 bg-amber-500 text-black rounded-xl font-medium hover:bg-amber-400 disabled:opacity-50"
              >
                {isProcessing ? 'Processing...' : 'Subscribe'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};


// Helper function for feature icons
function getFeatureIcon(featureId) {
  const icons = {
    ai_chat: '🤖',
    weather_skincare: '🌤️',
    voice_commands: '🎤',
    toon_optimization: '⚡',
    skin_analysis: '📷',
    sms_alerts: '📱',
    sentiment_analysis: '❤️',
    translation: '🌐',
    whatsapp_alerts: '💬',
    video_generation: '🎬',
    inventory_ai: '📦',
    churn_prediction: '📉',
    ai_email: '📧',
    biometric_auth: '🔐',
    github_integration: '🐙',
    document_scanner: '📄',
    appointment_scheduler: '📅',
    product_description_ai: '✏️',
    custom_integrations: '🔧'
  };
  return icons[featureId] || '✨';
}


export default SubscriptionPlans;
