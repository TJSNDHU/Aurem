/**
 * AUREM Intelligence Hub — The "Autonomous Executive" Dashboard
 * Business DNA Profiler + Live ROI Dashboard + Dynamic Offer Generator + Stripe Checkout
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Search, Zap, TrendingUp, Shield, Globe, Eye,
  CreditCard, CheckCircle, Clock, ArrowRight, Loader2,
  AlertTriangle, Lock, Target, DollarSign, Users,
  Sparkles, ChevronRight, ExternalLink, Brain,
  ShoppingCart, Building2, Briefcase
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ═══ Category Icons ═══ */
const categoryIcon = (cat) => {
  const map = {
    ecommerce: ShoppingCart, saas: Building2, agency: Briefcase,
    healthcare: Shield, fintech: DollarSign, education: Brain,
    lead_gen: Target, professional_services: Briefcase,
  };
  return map[cat] || Globe;
};

/* ═══ Revenue Leak Bar ═══ */
const LeakBar = ({ leak }) => {
  const maxLoss = 900;
  const width = Math.min(100, (leak.estimated_monthly_loss / maxLoss) * 100);
  return (
    <div className="flex items-center gap-3 py-2" data-testid={`leak-${leak.issue}`}>
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] text-[#1A1A2E]">{leak.label}</span>
          <span className="text-[11px] font-bold text-[#FF6B6B]">-${leak.estimated_monthly_loss}/mo</span>
        </div>
        <div className="h-1.5 bg-[#FF6B6B]/10 rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${width}%`, background: 'linear-gradient(90deg, #FF6B6B, #FF4444)' }} />
        </div>
      </div>
    </div>
  );
};

/* ═══ Tier Offer Card ═══ */
const TierCard = ({ offer, recommended, onSelect, loading, isSelected }) => {
  const isCommission = offer.tier_id === 'commission';
  const isFree = offer.tier_id === 'free_shield';
  const hasDiscount = offer.discount_percent > 0;

  return (
    <div
      className={`relative p-5 rounded-2xl border-2 transition-all ${
        isFree ? 'border-[#22c55e]/60 shadow-lg shadow-[#22c55e]/5' :
        recommended ? 'border-[#D4AF37] shadow-xl shadow-[#D4AF37]/10' : 'border-white/30'
      } ${isSelected ? 'ring-2 ring-[#D4AF37] ring-offset-2' : ''} bg-white/50 backdrop-blur-sm`}
      data-testid={`offer-tier-${offer.tier_id}`}
    >
      {isFree && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 text-[7px] font-bold tracking-[2px] px-3 py-1 rounded-full text-white"
          style={{ background: 'linear-gradient(135deg, #22c55e, #16a34a)' }}>
          <Shield className="w-3 h-3" /> FREE SHIELD
        </div>
      )}
      {recommended && !isFree && (
        <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[7px] font-bold tracking-[2px] px-3 py-0.5 rounded-full text-white"
          style={{ background: isCommission ? 'linear-gradient(135deg, #4ade80, #FF6B00)' : 'linear-gradient(135deg, #D4AF37, #B88759)' }}>
          {isCommission ? 'ZERO RISK' : 'BEST VALUE'}
        </div>
      )}

      <div className="text-center mb-4">
        <div className="flex items-center justify-center gap-1.5 mb-0.5">
          {isFree && <Shield className="w-4 h-4 text-[#22c55e]" />}
          <h3 className="text-sm font-bold text-[#1A1A2E]">{offer.name}</h3>
        </div>
        <div className="flex items-center justify-center gap-2">
          {hasDiscount && (
            <span className="text-sm text-[#888] line-through">${offer.base_price}</span>
          )}
          {isFree ? (
            <div>
              <span className="text-2xl font-bold text-[#22c55e]">$0</span>
              <span className="text-xs text-[#888] ml-1">forever</span>
              {offer.pin && (
                <div className="text-[10px] text-[#D4AF37] font-bold mt-0.5">
                  PIN: {offer.pin}
                </div>
              )}
            </div>
          ) : isCommission ? (
            <div>
              <span className="text-2xl font-bold text-[#4ade80]">$0</span>
              <span className="text-xs text-[#888] ml-1">upfront</span>
              <div className="text-[10px] text-[#D4AF37] font-bold mt-0.5">
                + ${offer.commission_per_sale} per recovered sale
              </div>
            </div>
          ) : (
            <>
              <span className="text-2xl font-bold text-[#1A1A2E]">${offer.final_price}</span>
              {offer.type === 'monthly' && <span className="text-[10px] text-[#888]">/mo</span>}
            </>
          )}
        </div>
        {offer.discount_label && (
          <span className="inline-block mt-1 text-[8px] px-2 py-0.5 rounded-full font-bold tracking-wider"
            style={{ background: isCommission ? 'rgba(74,222,128,0.15)' : 'rgba(212,175,55,0.15)', color: isCommission ? '#FF6B00' : '#D4AF37' }}>
            {offer.discount_label}
          </span>
        )}
      </div>

      <p className="text-[10px] text-[#888] text-center mb-3">{offer.description}</p>

      {/* Features */}
      <div className="space-y-1.5 mb-4">
        {offer.features?.map((f, i) => (
          <div key={i} className="flex items-center gap-2">
            <CheckCircle className="w-3 h-3 text-[#4ade80] flex-shrink-0" />
            <span className="text-[10px] text-[#666]">{f}</span>
          </div>
        ))}
      </div>

      {/* ROI Message */}
      {offer.roi_message && (
        <div className="p-2 rounded-lg bg-[#4ade80]/5 border border-[#4ade80]/10 mb-3">
          <p className="text-[10px] text-[#FF6B00] font-bold text-center">{offer.roi_message}</p>
        </div>
      )}

      <button
        onClick={() => onSelect(offer.tier_id)}
        disabled={loading}
        data-testid={`select-tier-${offer.tier_id}`}
        className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
        style={isFree
          ? { background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: '#fff' }
          : recommended
          ? { background: isCommission ? 'linear-gradient(135deg, #4ade80, #FF6B00)' : 'linear-gradient(135deg, #D4AF37, #B88759)', color: '#fff' }
          : { background: 'rgba(61,58,57,0.15)', border: '1px solid rgba(255,107,0,0.12)', color: '#FF6B00' }
        }
      >
        {loading && isSelected ? <Loader2 className="w-4 h-4 animate-spin" /> : isFree ? <Shield className="w-4 h-4" /> : <CreditCard className="w-4 h-4" />}
        {isFree ? (loading && isSelected ? 'Activating...' : 'Activate Free Shield') : isCommission ? (loading && isSelected ? 'Processing...' : 'Start Free — Pay Per Sale') : (loading && isSelected ? 'Processing...' : `Get ${offer.name}`)}
      </button>
    </div>
  );
};


/* ═══════════════════════════════════════════════════════════════ */
/* ═══ MAIN COMPONENT ═══ */
/* ═══════════════════════════════════════════════════════════════ */

const IntelligenceHub = ({ token }) => {
  const [url, setUrl] = useState('');
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  // DNA Profile
  const [dnaProfile, setDnaProfile] = useState(null);

  // Offers
  const [offers, setOffers] = useState(null);
  const [offersLoading, setOffersLoading] = useState(false);
  const [selectedTier, setSelectedTier] = useState(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  // Behavior tracking
  const [timeOnPage, setTimeOnPage] = useState(0);
  const [flashOfferShown, setFlashOfferShown] = useState(false);
  const timerRef = useRef(null);

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  // Time-on-page tracker for flash offer
  const handleFlashOffer = useCallback(async () => {
    if (!dnaProfile) return;
    setOffersLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/intelligence/generate-offer`, {
        method: 'POST', headers,
        body: JSON.stringify({ profile_id: dnaProfile.profile_id, trigger: 'time_on_page' }),
      });
      const data = await res.json();
      if (res.ok) setOffers(data);
    } catch (e) { console.error(e); }
    finally { setOffersLoading(false); }
  }, [dnaProfile]);

  useEffect(() => {
    if (dnaProfile && offers && !flashOfferShown) {
      timerRef.current = setInterval(() => {
        setTimeOnPage(prev => {
          if (prev >= 60 && !flashOfferShown) {
            // Trigger flash offer after 60s
            setFlashOfferShown(true);
            handleFlashOffer();
          }
          return prev + 1;
        });
      }, 1000);
      return () => clearInterval(timerRef.current);
    }
  }, [dnaProfile, offers, flashOfferShown, handleFlashOffer]);

  /* ─── Forensic Pulse (DNA Profile) ─── */
  const handleScan = useCallback(async () => {
    if (!url.trim()) { setError('Enter a URL to analyze'); return; }
    setScanning(true); setError(''); setDnaProfile(null); setOffers(null);
    setTimeOnPage(0); setFlashOfferShown(false);
    try {
      const res = await fetch(`${API_URL}/api/intelligence/dna-profile`, {
        method: 'POST', headers, body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'DNA analysis failed');
      setDnaProfile(data);

      // Auto-generate initial offers (page_view trigger)
      const offerRes = await fetch(`${API_URL}/api/intelligence/generate-offer`, {
        method: 'POST', headers,
        body: JSON.stringify({ profile_id: data.profile_id, trigger: 'page_view' }),
      });
      const offerData = await offerRes.json();
      if (offerRes.ok) setOffers(offerData);
    } catch (e) { setError(e.message); }
    finally { setScanning(false); }
  }, [url]);

  /* ─── Flash Offer (time_on_page trigger) ─── */

  /* ─── Exit Intent Offer ─── */
  useEffect(() => {
    if (!dnaProfile || !offers) return;
    const handleExit = async (e) => {
      if (e.clientY <= 0 && !flashOfferShown) {
        setFlashOfferShown(true);
        try {
          const res = await fetch(`${API_URL}/api/intelligence/generate-offer`, {
            method: 'POST', headers,
            body: JSON.stringify({ profile_id: dnaProfile.profile_id, trigger: 'exit_intent' }),
          });
          const data = await res.json();
          if (res.ok) setOffers(data);
        } catch (e) { console.error(e); }
      }
    };
    document.addEventListener('mouseout', handleExit);
    return () => document.removeEventListener('mouseout', handleExit);
  }, [dnaProfile, offers, flashOfferShown]);

  /* ─── Stripe Checkout ─── */
  const handleCheckout = useCallback(async (tierId) => {
    if (!offers) return;
    setSelectedTier(tierId); setCheckoutLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/intelligence/checkout`, {
        method: 'POST', headers,
        body: JSON.stringify({
          offer_set_id: offers.offer_set_id,
          tier_id: tierId,
          origin_url: window.location.origin,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Checkout failed');
      window.location.href = data.checkout_url;
    } catch (e) { setError(e.message); setCheckoutLoading(false); }
  }, [offers]);

  const CatIcon = dnaProfile ? categoryIcon(dnaProfile.category) : Globe;

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">

        {/* ── Header ── */}
        <div className="mb-6" data-testid="intelligence-hub-header">
          <h1 className="text-xl font-bold text-[#1A1A2E] tracking-wider mb-1">Intelligence Hub</h1>
          <p className="text-xs text-[#888]">Autonomous Executive — Forensic Pulse + AI Proposal + Dynamic Offers</p>
        </div>

        {/* ── URL Input ── */}
        <div className="mb-6 p-5 bg-white/70 backdrop-blur-sm border border-white/40 rounded-2xl" data-testid="intelligence-url-input">
          <label className="block text-[10px] text-[#888] mb-2 uppercase tracking-[1.5px] font-bold">Enter any business URL for forensic analysis</label>
          <div className="flex gap-3">
            <input type="url" value={url} onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleScan()}
              placeholder="https://shopify-store.com"
              className="flex-1 px-4 py-3 bg-white/60 border border-[#FF6B00]/20 rounded-lg text-[#1A1A2E] placeholder-[#aaa] text-sm focus:outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/20"
              disabled={scanning} data-testid="intelligence-url-field" />
            <button onClick={handleScan} disabled={scanning} data-testid="forensic-scan-btn"
              className="px-6 py-3 text-white rounded-lg font-bold text-sm hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-[#D4AF37]/20"
              style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)' }}>
              {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
              {scanning ? 'Profiling Business DNA...' : 'Forensic Pulse'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50/80 border border-red-200/50 rounded-lg text-red-600 text-sm flex items-center gap-2" data-testid="intelligence-error">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />{error}
          </div>
        )}

        {/* ═══════════════════════════════════════════════ */}
        {/* ═══ BUSINESS DNA PROFILE ═══ */}
        {/* ═══════════════════════════════════════════════ */}
        {dnaProfile && (
          <div className="mb-6" data-testid="dna-profile">
            {/* Business Identity Card */}
            <div className="p-5 rounded-2xl border border-[#D4AF37]/20 bg-gradient-to-br from-[#1C1712] to-[#211D17] mb-4">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #D4AF37, #B88759)' }}>
                    <CatIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white">{dnaProfile.business_name}</h2>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[8px] px-2 py-0.5 rounded-full font-bold tracking-wider" style={{ background: 'rgba(212,175,55,0.2)', color: '#D4A574' }}>
                        {dnaProfile.category?.toUpperCase().replace('_', ' ')}
                      </span>
                      <span className="text-[8px] px-2 py-0.5 rounded-full font-bold tracking-wider" style={{ background: 'rgba(74,222,128,0.15)', color: '#4ade80' }}>
                        {dnaProfile.revenue_model?.toUpperCase().replace('_', ' ')}
                      </span>
                      <span className="text-[8px] px-2 py-0.5 rounded-full font-bold tracking-wider" style={{ background: 'rgba(100,200,255,0.15)', color: '#64C8FF' }}>
                        {dnaProfile.growth_stage?.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[9px] text-[#6B5744] uppercase tracking-wider mb-0.5">Urgency Score</div>
                  <div className="text-xl font-bold" style={{ color: dnaProfile.urgency_score >= 7 ? '#FF6B6B' : dnaProfile.urgency_score >= 5 ? '#D4B977' : '#4ade80' }}>
                    {dnaProfile.urgency_score}/10
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg" style={{ background: 'rgba(184,135,89,0.06)' }}>
                  <div className="text-[8px] text-[#6B5744] uppercase tracking-wider mb-1">Target Audience</div>
                  <div className="text-[11px] text-[#D4C5B5]">{dnaProfile.target_audience}</div>
                </div>
                <div className="p-3 rounded-lg" style={{ background: 'rgba(255,107,107,0.06)' }}>
                  <div className="text-[8px] text-[#6B5744] uppercase tracking-wider mb-1">Primary Pain Point</div>
                  <div className="text-[11px] text-[#FF6B6B]">{dnaProfile.primary_pain}</div>
                </div>
              </div>
            </div>

            {/* ═══ REVENUE LEAKAGE DASHBOARD ═══ */}
            <div className="p-5 rounded-2xl border border-[#FF6B6B]/20 bg-white/50 backdrop-blur-sm mb-4" data-testid="revenue-leakage">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-5 h-5 text-[#FF6B6B]" />
                  <h3 className="text-sm font-bold text-[#1A1A2E] tracking-wider">REVENUE LEAKAGE DETECTED</h3>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold text-[#FF6B6B]">${dnaProfile.estimated_monthly_loss?.toLocaleString()}/mo</div>
                  <div className="text-[9px] text-[#888]">${dnaProfile.estimated_annual_loss?.toLocaleString()}/year potential loss</div>
                </div>
              </div>

              {dnaProfile.revenue_leaks?.map((leak, i) => (
                <LeakBar key={i} leak={leak} />
              ))}

              {dnaProfile.issues_count > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-[#FF6B6B]/5 border border-[#FF6B6B]/10 text-center">
                  <p className="text-xs text-[#FF6B6B] font-bold">
                    {dnaProfile.issues_count} issues costing you an estimated ${dnaProfile.estimated_monthly_loss?.toLocaleString()}/month in lost revenue
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════ */}
        {/* ═══ AI PROPOSAL — TIERED OFFERS ═══ */}
        {/* ═══════════════════════════════════════════════ */}
        {offers && (
          <div className="mb-6" data-testid="ai-proposal">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-[#D4AF37]" />
              <h3 className="text-sm font-bold text-[#1A1A2E] tracking-wider">AI PROPOSAL — FIX IT NOW</h3>
              {offers.trigger !== 'page_view' && (
                <span className="text-[8px] px-2 py-0.5 rounded-full font-bold tracking-wider animate-pulse"
                  style={{ background: 'rgba(212,175,55,0.2)', color: '#D4AF37' }}>
                  {offers.trigger === 'time_on_page' ? 'FLASH OFFER' : 'SPECIAL OFFER'}
                </span>
              )}
            </div>

            <div className={`grid grid-cols-1 gap-4 ${(offers.offers?.length || 0) >= 4 ? 'md:grid-cols-4' : 'md:grid-cols-3'}`}>
              {offers.offers?.map((offer) => (
                <TierCard
                  key={offer.tier_id}
                  offer={offer}
                  recommended={offer.is_recommended || (!offers.offers.some(o => o.is_recommended) && offer.tier_id === 'builder')}
                  onSelect={handleCheckout}
                  loading={checkoutLoading}
                  isSelected={selectedTier === offer.tier_id}
                />
              ))}
            </div>

            <p className="text-center text-[9px] text-[#888] mt-3">
              <Lock className="w-2.5 h-2.5 inline mr-1" />
              Secure payment via Stripe. All offers include a 30-day money-back guarantee.
            </p>
          </div>
        )}

        {/* ═══ EMPTY STATE ═══ */}
        {!dnaProfile && !scanning && (
          <div className="text-center py-16" data-testid="intelligence-empty">
            <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: 'linear-gradient(135deg, rgba(212,175,55,0.2), rgba(255,107,0,0.12))' }}>
              <Brain className="w-8 h-8 text-[#D4AF37]" />
            </div>
            <h2 className="text-lg font-bold text-[#1A1A2E] mb-2">The Autonomous Executive</h2>
            <p className="text-sm text-[#888] max-w-lg mx-auto">
              Enter any business URL. ORA builds a <span className="font-bold text-[#D4AF37]">Business DNA Profile</span>,
              estimates revenue leakage, and generates a personalized
              <span className="font-bold text-[#4ade80]"> AI Proposal</span> with dynamic pricing — all in seconds.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default IntelligenceHub;
