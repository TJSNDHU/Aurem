/**
 * AUREM Usage & Billing Dashboard
 * Real usage metering, subscription plans ($97/$297/$997), and billing management
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import {
  CreditCard, BarChart3, TrendingUp, Clock, Shield, Zap,
  RefreshCw, CheckCircle, AlertCircle, ArrowUpRight, Download,
  ChevronRight, Star, Crown, Sparkles, Activity, Users, MessageSquare,
  ExternalLink, X, Gauge, Mic, FileText, Globe, Ghost, Eye
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: 97,
    currency: 'CAD',
    period: '/month',
    color: '#D4AF37',
    icon: Star,
    features: ['1 workspace, 1 brand', '500 AI actions/month', 'ORA voice (text only)', 'Morning Brief', 'Invoice suite', 'Email support'],
    limits: { actions: 500, workspaces: 1, brands: 1, v2v: 0 },
  },
  {
    id: 'growth',
    name: 'Growth',
    price: 297,
    currency: 'CAD',
    period: '/month',
    color: '#8B5CF6',
    icon: Crown,
    popular: true,
    features: ['3 workspaces, 3 brands', '5,000 AI actions/month', 'ORA V2V voice (5 concurrent)', 'All Starter features', 'GEO Dashboard', 'UCP Protocol', 'Priority support'],
    limits: { actions: 5000, workspaces: 3, brands: 3, v2v: 5 },
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 997,
    currency: 'CAD',
    period: '/month',
    color: '#D4AF37',
    icon: Sparkles,
    features: ['Unlimited workspaces', 'Unlimited AI actions', 'ORA V2V (25 concurrent)', 'All Growth features', 'White-label option', 'Custom AI training', 'Dedicated onboarding'],
    limits: { actions: -1, workspaces: -1, brands: -1, v2v: 25 },
  }
];

const ACTION_ICONS = {
  llm_call: MessageSquare,
  v2v_session: Mic,
  invoice_sent: FileText,
  webhook_processed: Globe,
  ghost_action: Ghost,
  geo_check: Eye,
};

export default function UsageBilling({ token, user }) {
  const [quota, setQuota] = useState(null);
  const [usageHistory, setUsageHistory] = useState([]);
  const [currentUsage, setCurrentUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [upgrading, setUpgrading] = useState(null);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchAll = useCallback(async () => {
    try {
      const [quotaRes, usageRes, historyRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/usage/quota`, { headers }),
        fetch(`${API_URL}/api/usage/current`, { headers }),
        fetch(`${API_URL}/api/usage/history`, { headers }),
      ]);
      if (quotaRes.status === 'fulfilled' && quotaRes.value.ok) setQuota(await quotaRes.value.json());
      if (usageRes.status === 'fulfilled' && usageRes.value.ok) setCurrentUsage(await usageRes.value.json());
      if (historyRes.status === 'fulfilled' && historyRes.value.ok) {
        const d = await historyRes.value.json();
        setUsageHistory(d.history || []);
      }
    } catch {} finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  // iter 271 — live refresh every 15s (pauses in background)
  useLivePolling(fetchAll, 15000);

  const handleUpgrade = async (planId) => {
    setUpgrading(planId);
    try {
      const res = await fetch(`${API_URL}/api/subscription/checkout`, {
        method: 'POST', headers,
        body: JSON.stringify({ plan: planId }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else if (data.mock) {
        await fetchAll();
      }
    } catch (err) { console.error('Upgrade failed:', err); }
    setUpgrading(null);
  };

  const currentPlan = quota?.plan || 'trial';
  const currentTier = PLANS.find(p => p.id === currentPlan);
  const used = quota?.used || 0;
  const limit = quota?.limit || 50;
  const pct = limit > 0 ? Math.min(Math.round((used / limit) * 100), 100) : 0;
  const breakdown = currentUsage?.breakdown || {};

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="usage-billing-loading">
        <div className="flex items-center gap-3 text-[#888]">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading billing data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto" data-testid="usage-billing">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-[#FF6B00] tracking-wider mb-1">Usage & Billing</h1>
            <p className="text-xs text-[#888]">Monitor usage, manage your subscription</p>
          </div>
          <div className="flex gap-2">
            {['overview', 'plans', 'history'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                data-testid={`tab-${tab}`}
                className={`px-3 py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                  activeTab === tab ? 'bg-[#FF6B00]/20 text-[#FF6B00]' : 'text-[#666] hover:text-[#FF6B00]'
                }`}>{tab.charAt(0).toUpperCase() + tab.slice(1)}</button>
            ))}
          </div>
        </div>

        {activeTab === 'overview' && (
          <>
            {/* Stripe Placeholder Warning */}
            <div className="p-3.5 rounded-xl mb-4 flex items-center gap-3" style={{ background: 'rgba(255,107,107,0.06)', border: '1px solid rgba(255,107,107,0.15)' }} data-testid="stripe-warning">
              <AlertCircle className="w-5 h-5 text-[#FF6B6B] flex-shrink-0" />
              <div>
                <span className="text-xs font-bold text-[#FF6B6B]">Stripe: Test placeholder — payments not functional</span>
                <p className="text-[10px] text-[#888] mt-0.5">Add a real Stripe API key in Settings to enable live payment processing.</p>
              </div>
            </div>

            {/* Current Plan Banner */}
            <div className="p-5 border border-[#FF6B00]/20 rounded-xl mb-6" style={{ background: 'rgba(212,163,115,0.03)' }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: (currentTier?.color || '#FF6B00') + '15' }}>
                    {currentTier ? <currentTier.icon className="w-6 h-6" style={{ color: currentTier.color }} /> : <Zap className="w-6 h-6 text-[#888]" />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-semibold text-white">{currentTier?.name || 'Trial'} Plan</h2>
                      <span className="px-2 py-0.5 text-[10px] rounded-full font-medium bg-[#4ade80]/10 text-[#4ade80]">Active</span>
                    </div>
                    <p className="text-xs text-[#888] mt-0.5">
                      {currentTier ? `$${currentTier.price} CAD/month` : 'Free trial — 50 actions'}
                    </p>
                  </div>
                </div>
                {currentPlan !== 'enterprise' && (
                  <button onClick={() => setActiveTab('plans')} data-testid="upgrade-btn"
                    className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-[#1A3026] rounded-lg transition-all"
                    style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)' }}>
                    <ArrowUpRight className="w-3.5 h-3.5" /> Upgrade
                  </button>
                )}
              </div>
            </div>

            {/* Usage Meter */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="col-span-2 p-5 border border-white/5 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)' }}>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-medium text-white">AI Actions This Period</h3>
                  <span className="text-xs text-[#888]">{limit === -1 ? 'Unlimited' : `${used.toLocaleString()} / ${limit.toLocaleString()}`}</span>
                </div>
                {/* Progress bar */}
                <div className="w-full h-3 rounded-full bg-white/5 mb-3 overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-700"
                    data-testid="usage-bar"
                    style={{
                      width: limit === -1 ? '5%' : `${pct}%`,
                      background: pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : 'linear-gradient(90deg, #FF6B00, #8B5CF6)',
                    }} />
                </div>
                <div className="flex justify-between text-[10px] text-[#666]">
                  <span>{pct}% used</span>
                  <span>{limit === -1 ? 'No limit' : `${Math.max(0, limit - used).toLocaleString()} remaining`}</span>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="p-5 border border-white/5 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)' }}>
                <h3 className="text-sm font-medium text-white mb-3">Action Breakdown</h3>
                <div className="space-y-2.5">
                  {Object.entries(breakdown).length > 0 ? Object.entries(breakdown).map(([type, count]) => {
                    const Icon = ACTION_ICONS[type] || Activity;
                    return (
                      <div key={type} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Icon className="w-3.5 h-3.5 text-[#FF6B00]" />
                          <span className="text-[10px] text-[#888]">{type.replace(/_/g, ' ')}</span>
                        </div>
                        <span className="text-xs font-medium text-white">{count}</span>
                      </div>
                    );
                  }) : (
                    <p className="text-[10px] text-[#666]">No actions recorded yet this period</p>
                  )}
                </div>
              </div>
            </div>

            {/* Stripe Status */}
            <div className="p-4 border border-white/5 rounded-xl flex items-center gap-3" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <CreditCard className="w-4 h-4 text-[#888]" />
              <span className="text-xs text-[#888]">Payment provider: </span>
              <span className="text-xs font-medium text-[#f59e0b]">Stripe (Mock Mode)</span>
              <span className="text-[10px] text-[#666] ml-auto">Add your Stripe key in Settings &gt; API Keys to enable live payments</span>
            </div>
          </>
        )}

        {activeTab === 'plans' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {PLANS.map(plan => {
              const isCurrent = currentPlan === plan.id;
              return (
                <div key={plan.id} data-testid={`plan-card-${plan.id}`}
                  className={`relative p-6 border rounded-xl transition-all ${
                    plan.popular ? 'border-[#8B5CF6]/40' : 'border-white/10'
                  } ${isCurrent ? 'ring-1 ring-[#FF6B00]/50' : ''}`}
                  style={{ background: 'rgba(255,255,255,0.02)' }}>
                  {plan.popular && (
                    <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-3 py-0.5 text-[9px] font-bold tracking-wider text-white rounded-full" style={{ background: 'linear-gradient(90deg, #8B5CF6, #FF6B00)' }}>
                      MOST POPULAR
                    </div>
                  )}
                  <div className="mb-4">
                    <plan.icon className="w-8 h-8 mb-3" style={{ color: plan.color }} />
                    <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                    <div className="flex items-baseline gap-1 mt-1">
                      <span className="text-2xl font-bold text-white">${plan.price}</span>
                      <span className="text-xs text-[#888]">CAD{plan.period}</span>
                    </div>
                  </div>
                  <ul className="space-y-2 mb-6">
                    {plan.features.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-[#aaa]">
                        <CheckCircle className="w-3.5 h-3.5 text-[#4ade80] mt-0.5 flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  {isCurrent ? (
                    <div className="w-full py-2.5 text-center text-xs font-medium text-[#FF6B00] border border-[#FF6B00]/30 rounded-lg">
                      Current Plan
                    </div>
                  ) : (
                    <button onClick={() => handleUpgrade(plan.id)}
                      disabled={upgrading === plan.id}
                      data-testid={`upgrade-to-${plan.id}`}
                      className="w-full py-2.5 text-xs font-medium text-[#1A3026] rounded-lg transition-all hover:opacity-90 disabled:opacity-50"
                      style={{ background: `linear-gradient(135deg, ${plan.color}, ${plan.color}cc)` }}>
                      {upgrading === plan.id ? 'Processing...' : `Upgrade to ${plan.name}`}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="border border-white/5 rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)' }}>
            <div className="p-4 border-b border-white/5">
              <h3 className="text-sm font-medium text-white">Usage History</h3>
            </div>
            {usageHistory.length > 0 ? (
              <div className="divide-y divide-white/5">
                {usageHistory.map((h, i) => (
                  <div key={i} className="px-4 py-3 flex items-center justify-between">
                    <div>
                      <span className="text-xs font-medium text-white">{h.period}</span>
                      <span className="text-[10px] text-[#888] ml-3">Tenant: {h.tenant_id}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs text-[#FF6B00] font-medium">{h.total_actions?.toLocaleString()} actions</span>
                      <div className="flex gap-2">
                        {Object.entries(h.breakdown || {}).map(([k, v]) => (
                          <span key={k} className="text-[9px] text-[#666] px-1.5 py-0.5 bg-white/5 rounded">{k}: {v}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-[#666]">No usage history yet</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
