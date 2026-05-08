/**
 * AUREM Partner Referral Portal
 * Opt-in referral program for tenants to earn rewards by referring other businesses
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Gift, Users, Copy, Check, TrendingUp, DollarSign,
  Share2, Star, ArrowUpRight, RefreshCw, ChevronRight,
  Shield, Clock, Link2, ExternalLink, Award, Zap
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const REWARD_TIERS = [
  { tier: 'Bronze', min: 0, max: 4, reward: '$25', color: '#CD7F32', perkText: '$25 credit per referral' },
  { tier: 'Silver', min: 5, max: 14, reward: '$50', color: '#C0C0C0', perkText: '$50 credit + priority support' },
  { tier: 'Gold', min: 15, max: 49, reward: '$100', color: '#D4AF37', perkText: '$100 credit + 1 month free' },
  { tier: 'Platinum', min: 50, max: 999, reward: '$200', color: '#8B5CF6', perkText: '$200 credit + enterprise features' }
];

export default function PartnerReferralPortal({ token, user }) {
  const [loading, setLoading] = useState(true);
  const [referralData, setReferralData] = useState(null);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const fetchReferralData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/referrals/dashboard`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setReferralData(data);
      }
    } catch {
      setReferralData({
        referral_code: `AUREM-${(user?.first_name || 'USER').toUpperCase().slice(0, 4)}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
        referral_link: `${window.location.origin}/join?ref=AUREM-${(user?.first_name || 'USER').toUpperCase().slice(0, 4)}`,
        total_referrals: 0,
        active_referrals: 0,
        pending_referrals: 0,
        total_earned: 0,
        current_tier: 'Bronze',
        referral_history: []
      });
    } finally {
      setLoading(false);
    }
  }, [token, user]);

  useEffect(() => {
    fetchReferralData();
  }, [fetchReferralData]);

  const handleCopyCode = () => {
    if (referralData?.referral_code) {
      navigator.clipboard.writeText(referralData.referral_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleCopyLink = () => {
    if (referralData?.referral_link) {
      navigator.clipboard.writeText(referralData.referral_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const data = referralData || { total_referrals: 0, active_referrals: 0, pending_referrals: 0, total_earned: 0, current_tier: 'Bronze', referral_code: '', referral_link: '', referral_history: [] };
  const currentTier = REWARD_TIERS.find(t => t.tier === data.current_tier) || REWARD_TIERS[0];
  const nextTier = REWARD_TIERS[REWARD_TIERS.indexOf(currentTier) + 1];

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="partner-portal-loading">
        <div className="flex items-center gap-3 text-[#666]">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading referral portal...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="partner-referral-portal">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">Partner Referral Portal</h1>
            <p className="text-xs text-[#5a5a72]">Earn rewards by referring businesses to the AUREM platform</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-bold" style={{ backgroundColor: `${currentTier.color}15`, color: currentTier.color }}>
              <Award className="w-3 h-3" />
              {currentTier.tier} Partner
            </div>
          </div>
        </div>

        {/* Referral Code Banner */}
        <div className="p-6 bg-gradient-to-r from-[#0A0A0A] to-[#111] border border-[#D4AF37]/20 rounded-xl mb-8">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-[#5a5a72] tracking-wider mb-2">YOUR REFERRAL CODE</p>
              <div className="flex items-center gap-3">
                <code className="text-2xl font-mono font-bold text-[#D4AF37] tracking-wider">{data.referral_code}</code>
                <button
                  onClick={handleCopyCode}
                  data-testid="copy-referral-code"
                  className="p-2 rounded-lg bg-[#D4AF37]/10 text-[#D4AF37] hover:bg-[#D4AF37]/20 transition-colors"
                >
                  {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-[11px] text-[#5a5a72] mt-2">Share this code or link with other businesses</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCopyLink}
                data-testid="copy-referral-link"
                className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity"
              >
                <Link2 className="w-3.5 h-3.5" />
                Copy Invite Link
              </button>
              <button
                data-testid="share-referral"
                className="flex items-center gap-2 px-4 py-2.5 text-xs text-[#D4AF37] border border-[#D4AF37]/30 rounded-lg hover:bg-[#D4AF37]/10 transition-colors"
              >
                <Share2 className="w-3.5 h-3.5" />
                Share
              </button>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'TOTAL REFERRALS', value: data.total_referrals, icon: Users, color: '#D4AF37' },
            { label: 'ACTIVE', value: data.active_referrals, icon: TrendingUp, color: '#4ade80' },
            { label: 'PENDING', value: data.pending_referrals, icon: Clock, color: '#f59e0b' },
            { label: 'TOTAL EARNED', value: `$${data.total_earned}`, icon: DollarSign, color: '#D4AF37' }
          ].map((stat, idx) => (
            <div key={idx} className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                <span className="text-[9px] text-[#555] tracking-wider">{stat.label}</span>
              </div>
              <div className="text-2xl font-semibold font-mono" style={{ color: stat.color }}>{stat.value}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/80 backdrop-blur-sm p-1 rounded-lg border border-[#FF6B00]/20 w-fit">
          {[
            { id: 'overview', label: 'Overview', icon: Gift },
            { id: 'rewards', label: 'Reward Tiers', icon: Award },
            { id: 'history', label: 'Referral History', icon: Clock }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`referral-tab-${tab.id}`}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs transition-all ${
                activeTab === tab.id
                  ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30'
                  : 'text-[#666] hover:text-[#555]'
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="grid grid-cols-2 gap-6">
            {/* How It Works */}
            <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl p-6">
              <h3 className="text-xs text-[#555] tracking-wider mb-5">HOW IT WORKS</h3>
              <div className="space-y-5">
                {[
                  { step: 1, title: 'Share Your Code', desc: 'Send your unique referral code to other business owners', icon: Share2 },
                  { step: 2, title: 'They Sign Up', desc: 'When they register and activate their AUREM account', icon: Users },
                  { step: 3, title: 'Both Get Rewarded', desc: 'You earn credits and they get a welcome bonus', icon: Gift },
                  { step: 4, title: 'Tier Up', desc: 'More referrals unlock higher reward tiers', icon: TrendingUp }
                ].map((item) => (
                  <div key={item.step} className="flex items-start gap-4">
                    <div className="w-8 h-8 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/20 flex items-center justify-center text-xs font-bold text-[#D4AF37] flex-shrink-0">
                      {item.step}
                    </div>
                    <div>
                      <h4 className="text-xs font-medium text-[#1A1A2E]">{item.title}</h4>
                      <p className="text-[10px] text-[#5a5a72] mt-0.5">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Current Tier Progress */}
            <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl p-6">
              <h3 className="text-xs text-[#555] tracking-wider mb-5">YOUR PROGRESS</h3>
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ backgroundColor: `${currentTier.color}15` }}>
                  <Award className="w-8 h-8" style={{ color: currentTier.color }} />
                </div>
                <div>
                  <h4 className="text-lg font-semibold" style={{ color: currentTier.color }}>{currentTier.tier}</h4>
                  <p className="text-[11px] text-[#5a5a72]">{currentTier.perkText}</p>
                </div>
              </div>

              {nextTier && (
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] text-[#888]">Progress to {nextTier.tier}</span>
                    <span className="text-[10px] font-mono" style={{ color: nextTier.color }}>
                      {data.total_referrals}/{nextTier.min} referrals
                    </span>
                  </div>
                  <div className="w-full h-2 bg-[#1A1A1A] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min((data.total_referrals / nextTier.min) * 100, 100)}%`,
                        backgroundColor: nextTier.color
                      }}
                    />
                  </div>
                  <p className="text-[10px] text-[#555] mt-2">
                    {nextTier.min - data.total_referrals} more referrals to unlock {nextTier.tier}
                  </p>
                </div>
              )}

              <div className="p-4 bg-[#D4AF37]/5 border border-[#D4AF37]/10 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-[#D4AF37]" />
                  <span className="text-xs font-medium text-[#D4AF37]">Quick Tip</span>
                </div>
                <p className="text-[10px] text-[#888] leading-relaxed">
                  Businesses you refer get a 14-day extended trial + $25 starter credit. Higher tiers unlock bigger rewards for both you and your referrals.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'rewards' && (
          <div className="grid grid-cols-4 gap-4">
            {REWARD_TIERS.map(tier => {
              const isCurrent = tier.tier === data.current_tier;
              const isUnlocked = REWARD_TIERS.indexOf(tier) <= REWARD_TIERS.indexOf(currentTier);
              return (
                <div
                  key={tier.tier}
                  data-testid={`tier-card-${tier.tier.toLowerCase()}`}
                  className={`p-5 rounded-xl border transition-all ${
                    isCurrent
                      ? 'bg-white/80 backdrop-blur-sm border-[#D4AF37]/40 ring-1 ring-[#D4AF37]/20'
                      : 'bg-white/80 backdrop-blur-sm border-[#FF6B00]/20'
                  }`}
                >
                  {isCurrent && (
                    <div className="text-[9px] font-bold tracking-wider text-[#D4AF37] mb-3">CURRENT TIER</div>
                  )}
                  <Award className="w-8 h-8 mb-3" style={{ color: tier.color }} />
                  <h3 className="text-sm font-semibold text-[#1A1A2E]">{tier.tier}</h3>
                  <p className="text-2xl font-bold mt-1" style={{ color: tier.color }}>{tier.reward}</p>
                  <p className="text-[10px] text-[#5a5a72] mt-1">per referral</p>
                  <div className="mt-4 pt-4 border-t border-[#FF6B00]/20">
                    <p className="text-[10px] text-[#888]">{tier.min}+ referrals</p>
                    <p className="text-[10px] text-[#5a5a72] mt-1">{tier.perkText}</p>
                  </div>
                  {isUnlocked ? (
                    <div className="mt-4 w-full py-2 text-center text-[10px] font-medium text-[#4ade80] bg-[#4ade80]/10 rounded-lg">
                      Unlocked
                    </div>
                  ) : (
                    <div className="mt-4 w-full py-2 text-center text-[10px] text-[#555] bg-white/50 rounded-lg">
                      {tier.min - data.total_referrals} more to unlock
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-[#FF6B00]/20">
              <h3 className="text-xs text-[#555] tracking-wider">REFERRAL HISTORY</h3>
            </div>
            {data.referral_history && data.referral_history.length > 0 ? (
              <div className="divide-y divide-[#141414]">
                {data.referral_history.map((ref, idx) => (
                  <div key={idx} className="flex items-center justify-between px-4 py-3 hover:bg-white/40">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#D4AF37]/10 flex items-center justify-center text-[10px] font-semibold text-[#D4AF37]">
                        {(ref.name || 'R')[0]}
                      </div>
                      <div>
                        <p className="text-xs text-[#1A1A2E]">{ref.name || 'Referred Business'}</p>
                        <p className="text-[10px] text-[#5a5a72]">{ref.email || ''}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={`px-2 py-0.5 text-[10px] rounded-full ${
                        ref.status === 'active' ? 'bg-[#4ade80]/10 text-[#4ade80]' :
                        ref.status === 'pending' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' :
                        'bg-[#555]/10 text-[#555]'
                      }`}>
                        {ref.status}
                      </span>
                      <span className="text-[10px] text-[#555]">{ref.date || ''}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-12 text-center">
                <Users className="w-8 h-8 text-[#333] mx-auto mb-3" />
                <p className="text-sm text-[#555]">No referrals yet</p>
                <p className="text-[11px] text-[#444] mt-1">Share your code to start earning rewards</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
