/**
 * AUREM Pricing Page — Scientific-Luxe Theme
 * Frosted glass panels, copper wireframe accents
 * Growth tier highlighted as 'Professional Standard'
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Zap, Shield, Crown, Check, ChevronRight, Rocket,
  Brain, Phone, Target, Users, Globe, Activity,
  Star, ArrowRight, MonitorSmartphone,
} from 'lucide-react';
import '../theme/aurem-floating.css';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const FALLBACK_TIERS = [
  {
    tier: 'starter',
    plan_id: 'plan_starter',
    name: 'Starter',
    price_monthly: 97,
    price_annual: 970,
    currency: 'CAD',
    tagline: 'Perfect for solo founders and small teams',
    limits: { actions_per_month: 500, pipeline_runs_per_day: 3, lead_enrichment_per_month: 50, workspaces: 1, v2v_concurrent_sessions: 0 },
    features: { ora_voice: 'text_only', v2v_voice: false, morning_brief: true, geo_tracking: false, sentiment_analysis: false, deep_scout: false, revenue_forecasting: false, partner_referral: false, white_label: false, priority_support: false },
  },
  {
    tier: 'growth',
    plan_id: 'plan_growth',
    name: 'Growth',
    price_monthly: 297,
    price_annual: 2970,
    currency: 'CAD',
    tagline: 'For scaling businesses that need AI automation',
    is_popular: true,
    limits: { actions_per_month: 5000, pipeline_runs_per_day: 20, lead_enrichment_per_month: 500, workspaces: 3, v2v_concurrent_sessions: 5 },
    features: { ora_voice: 'v2v', v2v_voice: true, morning_brief: true, geo_tracking: true, sentiment_analysis: true, deep_scout: true, revenue_forecasting: true, partner_referral: true, white_label: false, priority_support: false },
  },
  {
    tier: 'enterprise',
    plan_id: 'plan_enterprise',
    name: 'Enterprise',
    price_monthly: 997,
    price_annual: 9970,
    currency: 'CAD',
    tagline: 'Full platform with white-label and unlimited resources',
    limits: { actions_per_month: -1, pipeline_runs_per_day: -1, lead_enrichment_per_month: -1, workspaces: -1, v2v_concurrent_sessions: 25 },
    features: { ora_voice: 'v2v', v2v_voice: true, morning_brief: true, geo_tracking: true, sentiment_analysis: true, deep_scout: true, revenue_forecasting: true, partner_referral: true, white_label: true, priority_support: true },
  },
];

const TIER_ICONS = { starter: Zap, growth: Rocket, enterprise: Crown };
const TIER_COLORS = {
  starter: { accent: '#888', gradient: 'linear-gradient(135deg, #2a2a2a, #1a1a1a)' },
  growth: { accent: '#FF6B00', gradient: 'linear-gradient(135deg, #FF6B00, #CC5500)' },
  enterprise: { accent: '#D4B977', gradient: 'linear-gradient(135deg, #D4B977, #A08028)' },
};

const FEATURE_LIST = {
  starter: [
    'ORA Text Chat',
    'Morning Brief',
    '500 actions / month',
    '3 pipeline runs / day',
    '50 lead enrichments / month',
    '1 workspace',
    'Approval queue',
  ],
  growth: [
    'Everything in Starter, plus:',
    'V2V Voice (5 concurrent)',
    '5,000 actions / month',
    '20 pipeline runs / day',
    '500 lead enrichments / month',
    '3 workspaces',
    'GEO Tracking & Sentiment Analysis',
    'Deep Scout & Revenue Forecasting',
    'Partner Referral Network',
    'Video Generation (480p, 10/month)',
  ],
  enterprise: [
    'Everything in Growth, plus:',
    'Unlimited actions & pipelines',
    '25 concurrent V2V sessions',
    'White-Label + CNAME',
    'HD Video Generation (unlimited)',
    'CONSORTIUM Multi-Model AI',
    'PentAGI Security Pentest',
    'ORA Avatar Lip Sync',
    'Priority Support',
  ],
};

export default function PricingPage() {
  const navigate = useNavigate();
  const [plans, setPlans] = useState(FALLBACK_TIERS);
  const [billing, setBilling] = useState('monthly');
  const [hoveredTier, setHoveredTier] = useState(null);

  const [checkoutLoading, setCheckoutLoading] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/plan/available`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.plans?.length >= 3) setPlans(d.plans);
      })
      .catch(() => {});
  }, []);

  const handleStartTrial = async (plan) => {
    const tier = plan.tier || plan.plan_id?.replace('plan_', '');
    setCheckoutLoading(tier);
    try {
      // Try Stripe checkout first
      const token = localStorage.getItem('aurem_token') || '';
      const res = await fetch(`${API_URL}/api/payments/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ package_id: tier, origin_url: window.location.origin }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.url) {
          window.location.href = data.url;
          return;
        }
      }
      // Fallback: go to register
      navigate(`/auth?mode=register&plan=plan_${tier}&tier=${tier}`);
    } catch (e) {
      navigate(`/auth?mode=register&plan=plan_${tier}&tier=${tier}`);
    } finally {
      setCheckoutLoading(null);
    }
  };

  const getPrice = (plan) => {
    if (billing === 'annual') {
      const annual = plan.price_annual || plan.price_monthly * 10;
      return Math.round(annual / 12);
    }
    return plan.price_monthly;
  };

  return (
    <div className="min-h-screen relative overflow-hidden aurem-page-bg-circuit" style={{ background: 'transparent' }}>
      {/* Copper wireframe grid background */}
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: `
          linear-gradient(rgba(212,163,115,0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(212,163,115,0.03) 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
      }} />
      {/* Radial glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] pointer-events-none" style={{
        background: 'radial-gradient(ellipse, rgba(255,107,0,0.06) 0%, transparent 70%)',
      }} />

      {/* Navigation */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5" data-testid="pricing-nav">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 group"
          data-testid="pricing-logo"
        >
          <div className="size-9 rounded-xl flex items-center justify-center" style={{
            background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
            boxShadow: '0 0 20px rgba(255,107,0,0.25)',
          }}>
            <span className="text-sm font-black text-[#050507]">A</span>
          </div>
          <span className="text-sm font-bold tracking-[3px] text-white/90">AUREM</span>
        </button>
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/login')}
            className="text-xs text-white/50 hover:text-white/80 transition-colors font-medium tracking-wider"
            data-testid="pricing-signin-btn"
          >
            SIGN IN
          </button>
          <button
            onClick={() => navigate('/auth?mode=register')}
            className="px-4 py-2 rounded-xl text-xs font-bold tracking-wider text-[#050507] transition-all hover:scale-[1.03]"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)', boxShadow: '0 4px 16px rgba(255,107,0,0.2)' }}
            data-testid="pricing-get-started-btn"
          >
            GET STARTED
          </button>
        </div>
      </nav>

      {/* Hero */}
      <header className="relative z-10 text-center pt-16 pb-12 px-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full mb-6" style={{
          background: 'rgba(255,107,0,0.08)',
          border: '1px solid rgba(255,107,0,0.15)',
        }}>
          <Activity className="size-3 text-[#FF6B00]" />
          <span className="text-[10px] font-bold tracking-[2px] text-[#FF6B00]">SUBSCRIPTION PLANS</span>
        </div>
        <h1
          className="text-4xl sm:text-5xl font-bold tracking-tight text-white mb-4"
          style={{ fontFamily: 'Cinzel, Georgia, serif' }}
          data-testid="pricing-heading"
        >
          Intelligence, <span style={{ color: '#FF6B00', textShadow: '0 0 30px rgba(255,107,0,0.3)' }}>Priced Right</span>
        </h1>
        <p className="text-sm text-white/50 max-w-lg mx-auto leading-relaxed mb-8">
          Every plan includes the full AUREM ORA platform. Choose the scale that fits your operation.
        </p>

        {/* Billing toggle */}
        <div className="inline-flex items-center gap-1 p-1 rounded-xl" style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.06)',
        }} data-testid="billing-toggle">
          <button
            onClick={() => setBilling('monthly')}
            className={`px-5 py-2 rounded-lg text-xs font-bold tracking-wider transition-all ${billing === 'monthly' ? 'text-[#050507]' : 'text-white/65 hover:text-white/60'}`}
            style={billing === 'monthly' ? { background: 'linear-gradient(135deg, #FF6B00, #CC5500)' } : {}}
            data-testid="billing-monthly-btn"
          >
            MONTHLY
          </button>
          <button
            onClick={() => setBilling('annual')}
            className={`px-5 py-2 rounded-lg text-xs font-bold tracking-wider transition-all ${billing === 'annual' ? 'text-[#050507]' : 'text-white/65 hover:text-white/60'}`}
            style={billing === 'annual' ? { background: 'linear-gradient(135deg, #D4B977, #A08028)' } : {}}
            data-testid="billing-annual-btn"
          >
            ANNUAL
            <span className="ml-1.5 text-[9px] opacity-80">SAVE 17%</span>
          </button>
        </div>
      </header>

      {/* Plan Cards */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pb-24" data-testid="pricing-cards-section">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {plans.map((plan, idx) => {
            const tierKey = plan.tier || ['starter', 'growth', 'enterprise'][idx];
            const colors = TIER_COLORS[tierKey] || TIER_COLORS.starter;
            const Icon = TIER_ICONS[tierKey] || Zap;
            const isGrowth = tierKey === 'growth';
            const features = FEATURE_LIST[tierKey] || [];
            const price = getPrice(plan);
            const isHovered = hoveredTier === tierKey;

            return (
              <div
                key={plan.plan_id || tierKey}
                onMouseEnter={() => setHoveredTier(tierKey)}
                onMouseLeave={() => setHoveredTier(null)}
                data-testid={`pricing-card-${tierKey}`}
                className={`relative rounded-2xl transition-all duration-300 aurem-floating-card ${idx === 1 ? 'delay-1' : idx === 2 ? 'delay-2' : idx === 3 ? 'delay-3' : ''}`}
                style={{
                  transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
                  ...(isGrowth ? { border: '1.5px solid rgba(255,107,0,0.45)' } : {}),
                }}
              >
                {/* Professional Standard badge */}
                {isGrowth && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-20">
                    <div className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[10px] font-bold tracking-[2px]" style={{
                      background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
                      color: '#050507',
                      boxShadow: '0 4px 16px rgba(255,107,0,0.3)',
                    }} data-testid="growth-badge">
                      <Star className="size-3" />
                      PROFESSIONAL STANDARD
                    </div>
                  </div>
                )}

                <div className={`p-8 ${isGrowth ? 'pt-10' : ''}`}>
                  {/* Icon + Name */}
                  <div className="flex items-center gap-3 mb-4">
                    <div className="size-10 rounded-xl flex items-center justify-center" style={{
                      background: `${colors.accent}15`,
                      border: `1px solid ${colors.accent}25`,
                    }}>
                      <Icon className="size-5" style={{ color: colors.accent }} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white tracking-wide" data-testid={`plan-name-${tierKey}`}>
                        {plan.name}
                      </h3>
                      <p className="text-[10px] text-white/65">{plan.tagline}</p>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="mb-6">
                    <div className="flex items-baseline gap-1">
                      <span className="text-[10px] text-white/60 font-medium">$</span>
                      <span className="text-4xl font-black text-white" style={{
                        fontFamily: 'Cinzel, Georgia, serif',
                        textShadow: isGrowth ? '0 0 20px rgba(255,107,0,0.2)' : 'none',
                      }} data-testid={`plan-price-${tierKey}`}>
                        {price}
                      </span>
                      <span className="text-xs text-white/60 ml-1">{plan.currency || 'CAD'} / mo</span>
                    </div>
                    {billing === 'annual' && (
                      <p className="text-[10px] text-[#D4B977] mt-1 font-medium">
                        Billed ${plan.price_annual || price * 12} / year
                      </p>
                    )}
                  </div>

                  {/* CTA */}
                  <button
                    onClick={() => handleStartTrial(plan)}
                    data-testid={`start-trial-${tierKey}`}
                    className="w-full py-3 rounded-xl text-xs font-bold tracking-[2px] transition-all hover:scale-[1.02] mb-8"
                    style={isGrowth ? {
                      background: colors.gradient,
                      color: '#050507',
                      boxShadow: '0 4px 20px rgba(255,107,0,0.25)',
                    } : {
                      background: 'rgba(255,255,255,0.05)',
                      color: colors.accent,
                      border: `1px solid ${colors.accent}30`,
                    }}
                  >
                    {checkoutLoading === tierKey ? 'REDIRECTING...' : tierKey === 'enterprise' ? 'SUBSCRIBE' : 'SUBSCRIBE NOW'}
                    {!checkoutLoading && <ArrowRight className="size-3 inline ml-2" />}
                  </button>

                  {/* Limits highlights */}
                  <div className="grid grid-cols-2 gap-2 mb-6">
                    {[
                      { label: 'Actions', value: plan.limits?.actions_per_month === -1 ? 'Unlimited' : `${(plan.limits?.actions_per_month || 500).toLocaleString()} / mo` },
                      { label: 'Pipelines', value: plan.limits?.pipeline_runs_per_day === -1 ? 'Unlimited' : `${plan.limits?.pipeline_runs_per_day || 3} / day` },
                      { label: 'Leads', value: plan.limits?.lead_enrichment_per_month === -1 ? 'Unlimited' : `${plan.limits?.lead_enrichment_per_month || 50} / mo` },
                      { label: 'V2V Voice', value: (plan.limits?.v2v_concurrent_sessions || 0) === 0 ? 'Text Only' : `${plan.limits?.v2v_concurrent_sessions} sessions` },
                    ].map((stat, si) => (
                      <div key={si} className="p-2.5 rounded-lg" style={{
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid rgba(255,255,255,0.04)',
                      }}>
                        <div className="text-[10px] text-white/60 mb-0.5">{stat.label}</div>
                        <div className="text-xs font-bold text-white/80">{stat.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Feature list */}
                  <div className="space-y-2.5">
                    {features.map((feat, fi) => (
                      <div key={fi} className="flex items-start gap-2.5">
                        {fi === 0 && tierKey !== 'starter' ? (
                          <ChevronRight className="size-3.5 mt-0.5 flex-shrink-0 text-white/55" />
                        ) : (
                          <div className="size-3.5 mt-0.5 rounded-full flex items-center justify-center flex-shrink-0" style={{
                            background: `${colors.accent}15`,
                          }}>
                            <Check className="size-2" style={{ color: colors.accent }} />
                          </div>
                        )}
                        <span className={`text-xs leading-relaxed ${fi === 0 && tierKey !== 'starter' ? 'font-semibold text-white/60' : 'text-white/70'}`}>
                          {feat}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom CTA */}
        <div className="text-center mt-16">
          <p className="text-xs text-white/60 mb-3">All plans include 14-day free trial. No credit card required.</p>
          <div className="flex items-center justify-center gap-6 text-[10px] text-white/55">
            <div className="flex items-center gap-1.5">
              <Shield className="size-3" />
              <span>SOC 2 Compliant</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Globe className="size-3" />
              <span>Canadian Infrastructure</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Brain className="size-3" />
              <span>Multi-Agent AI</span>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* SITE MONITOR — Uptime SKU (NEW)                                */}
      {/* ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pb-28" data-testid="site-monitor-section">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full mb-5" style={{
            background: 'rgba(74,222,128,0.08)',
            border: '1px solid rgba(74,222,128,0.2)',
          }}>
            <MonitorSmartphone className="size-3 text-[#4ade80]" />
            <span className="text-[10px] font-bold tracking-[2px] text-[#4ade80]">SITE MONITOR · ADD-ON</span>
          </div>
          <h2
            className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-3"
            style={{ fontFamily: 'Cinzel, Georgia, serif' }}
            data-testid="site-monitor-heading"
          >
            Never get surprised by <span style={{ color: '#4ade80', textShadow: '0 0 30px rgba(74,222,128,0.25)' }}>downtime</span>
          </h2>
          <p className="text-sm text-white/60 max-w-xl mx-auto leading-relaxed">
            Standalone uptime monitoring. Pings your websites 24/7 and alerts you the second they blip.
            Add on top of any plan, or subscribe standalone.
          </p>
          <div className="mt-5">
            <button
              onClick={() => navigate('/monitor-free')}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold tracking-wider transition-all hover:scale-[1.03]"
              style={{
                background: 'rgba(74,222,128,0.08)',
                border: '1px solid rgba(74,222,128,0.3)',
                color: '#4ade80',
              }}
              data-testid="site-monitor-free-cta-btn"
            >
              TRY FREE FOR 30 DAYS <ArrowRight className="size-3" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-start">
          {[
            {
              id: 'site_monitor_lite',
              name: 'Lite',
              price: 29,
              tagline: 'Solo sites & small shops',
              accent: '#888',
              features: [
                '5 URLs monitored',
                '10-minute checks',
                'Email alerts on downtime',
                'Live uptime dashboard',
                '30-day incident history',
              ],
            },
            {
              id: 'site_monitor_pro',
              name: 'Pro',
              price: 99,
              tagline: 'Agencies & growing businesses',
              accent: '#4ade80',
              popular: true,
              features: [
                'Everything in Lite, plus:',
                '25 URLs monitored',
                '5-minute checks',
                'WhatsApp alerts (downtime + recovery)',
                'Public status page (shareable)',
                'Full incident history & latency graphs',
              ],
            },
            {
              id: 'site_monitor_enterprise',
              name: 'Enterprise',
              price: 249,
              tagline: 'Mission-critical infrastructure',
              accent: '#D4B977',
              features: [
                'Everything in Pro, plus:',
                'Unlimited URLs',
                '1-minute checks',
                'SMS + WhatsApp + Email alerts',
                'AI root-cause analysis',
                'White-label status page',
                'Priority SLA + onboarding',
              ],
            },
          ].map((sm) => (
            <div
              key={sm.id}
              data-testid={`sm-card-${sm.id}`}
              className="relative rounded-2xl transition-all duration-300 hover:-translate-y-1"
              style={{
                background: 'rgba(16,16,18,0.65)',
                backdropFilter: 'blur(24px)',
                WebkitBackdropFilter: 'blur(24px)',
                border: sm.popular
                  ? '1.5px solid rgba(74,222,128,0.35)'
                  : '1px solid rgba(255,255,255,0.06)',
                boxShadow: sm.popular
                  ? '0 0 40px rgba(74,222,128,0.08), inset 0 1px 0 rgba(255,255,255,0.05)'
                  : '0 4px 20px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03)',
              }}
            >
              {sm.popular && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-20">
                  <div className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[10px] font-bold tracking-[2px]" style={{
                    background: 'linear-gradient(135deg, #4ade80, #22c55e)',
                    color: '#050507',
                    boxShadow: '0 4px 16px rgba(74,222,128,0.3)',
                  }}>
                    <Star className="size-3" />
                    MOST POPULAR
                  </div>
                </div>
              )}
              <div className={`p-7 ${sm.popular ? 'pt-9' : ''}`}>
                <div className="flex items-center gap-3 mb-4">
                  <div className="size-10 rounded-xl flex items-center justify-center" style={{
                    background: `${sm.accent}15`,
                    border: `1px solid ${sm.accent}25`,
                  }}>
                    <MonitorSmartphone className="size-5" style={{ color: sm.accent }} />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white tracking-wide" data-testid={`sm-name-${sm.id}`}>
                      Site Monitor — {sm.name}
                    </h3>
                    <p className="text-[10px] text-white/65">{sm.tagline}</p>
                  </div>
                </div>

                <div className="mb-6">
                  <div className="flex items-baseline gap-1">
                    <span className="text-[10px] text-white/60 font-medium">$</span>
                    <span className="text-4xl font-black text-white" style={{
                      fontFamily: 'Cinzel, Georgia, serif',
                      textShadow: sm.popular ? '0 0 20px rgba(74,222,128,0.2)' : 'none',
                    }} data-testid={`sm-price-${sm.id}`}>
                      {sm.price}
                    </span>
                    <span className="text-xs text-white/60 ml-1">CAD / mo</span>
                  </div>
                  <p className="text-[10px] text-white/50 mt-1">Billed monthly · Cancel anytime</p>
                </div>

                <button
                  onClick={() => navigate(`/auth?mode=register&addon=${sm.id}&redirect=/my/monitor`)}
                  data-testid={`sm-subscribe-${sm.id}`}
                  className="w-full py-3 rounded-xl text-xs font-bold tracking-[2px] transition-all hover:scale-[1.02] mb-6"
                  style={sm.popular ? {
                    background: 'linear-gradient(135deg, #4ade80, #22c55e)',
                    color: '#050507',
                    boxShadow: '0 4px 20px rgba(74,222,128,0.25)',
                  } : {
                    background: 'rgba(255,255,255,0.05)',
                    color: sm.accent,
                    border: `1px solid ${sm.accent}30`,
                  }}
                >
                  SUBSCRIBE <ArrowRight className="size-3 inline ml-2" />
                </button>

                <div className="space-y-2.5">
                  {sm.features.map((feat, fi) => (
                    <div key={fi} className="flex items-start gap-2.5">
                      {fi === 0 && sm.id !== 'site_monitor_lite' ? (
                        <ChevronRight className="size-3.5 mt-0.5 flex-shrink-0 text-white/55" />
                      ) : (
                        <div className="size-3.5 mt-0.5 rounded-full flex items-center justify-center flex-shrink-0" style={{
                          background: `${sm.accent}15`,
                        }}>
                          <Check className="size-2" style={{ color: sm.accent }} />
                        </div>
                      )}
                      <span className={`text-xs leading-relaxed ${fi === 0 && sm.id !== 'site_monitor_lite' ? 'font-semibold text-white/60' : 'text-white/70'}`}>
                        {feat}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        <p className="text-center text-[11px] text-white/50 mt-10 max-w-lg mx-auto leading-relaxed">
          Start with a <span className="text-[#4ade80]">7-day free trial</span>, 3 URLs, 15-min checks, email alerts.
          Upgrade anytime to unlock WhatsApp alerts, faster checks, and a public status page.
        </p>
      </section>
    </div>
  );
}
