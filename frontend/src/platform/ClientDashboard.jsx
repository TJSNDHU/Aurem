/**
 * AUREM Client Dashboard — Complete Client Portal
 * Tabs: Overview | Integrations | Billing | Settings
 * Features: BIN header, Activity Feed, Feature Gating, Onboarding Wizard
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity, Shield, TrendingUp, Globe, Zap, RefreshCw,
  MessageSquare, Mail, Phone, BarChart3, Clock, CheckCircle2,
  AlertTriangle, ArrowUpRight, Copy, Eye, EyeOff, Settings, LogOut,
  ChevronRight, CreditCard, Lock, Bell, BellOff, Wrench, Search,
  Rocket, DollarSign, Users, Star, ExternalLink, ChevronDown
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import WelcomeCard from './WelcomeCard';
import ConnectionWizard from './ConnectionWizard';
import LiveCampaignPipeline from './LiveCampaignPipeline';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ─── Score Ring ─── */
const ScoreRing = ({ score, size = 120 }) => {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? '#68DA8D' : score >= 60 ? '#FF6B00' : '#E05252';
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset} style={{ transition: 'stroke-dashoffset 1.2s ease' }} />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-3xl font-black" style={{ color }}>{score}</span>
        <span className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--aurem-body-secondary)' }}>/ 100</span>
      </div>
    </div>
  );
};

const StatCard = ({ icon: Icon, label, value, sub, accent }) => (
  <div className="rounded-2xl p-5 flex flex-col gap-3 relative overflow-hidden"
    style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)', backdropFilter: 'blur(16px)' }}
    data-testid={`stat-card-${label.toLowerCase().replace(/\s+/g, '-')}`}>
    <div className="flex items-center justify-between">
      <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: accent || 'rgba(104,218,141,0.12)' }}>
        <Icon size={18} style={{ color: accent ? '#fff' : '#68DA8D' }} />
      </div>
      {sub && <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full" style={{ background: 'rgba(212,163,115,0.1)', color: '#FF6B00' }}>{sub}</span>}
    </div>
    <div>
      <p className="text-2xl font-black" style={{ color: 'var(--aurem-heading)' }}>{value}</p>
      <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</p>
    </div>
  </div>
);

const CategoryBadge = ({ label, score }) => {
  const color = score >= 80 ? '#68DA8D' : score >= 60 ? '#FF6B00' : '#E05252';
  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)' }}>
      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="text-xs font-medium flex-1 capitalize" style={{ color: 'var(--aurem-body)' }}>{label}</span>
      <span className="text-sm font-bold" style={{ color }}>{score}</span>
    </div>
  );
};

const Sparkline = ({ data, width = 200, height = 48 }) => {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data, 100);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * (height - 8) - 4}`).join(' ');
  return (
    <svg width={width} height={height} className="opacity-80">
      <polyline points={points} fill="none" stroke="#68DA8D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

/* ─── Activity Icon ─── */
const ActivityIcon = ({ type }) => {
  const map = { scan: Search, message: Mail, lead: Users, voice: Phone, security: Shield, activity: Activity };
  const colors = { scan: '#68DA8D', message: '#4FC3F7', lead: '#FF6B00', voice: '#CE93D8', security: '#E05252', activity: '#D4AF37' };
  const Icon = map[type] || Activity;
  return <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: `${colors[type] || '#D4AF37'}15` }}><Icon size={14} style={{ color: colors[type] || '#D4AF37' }} /></div>;
};

/* ─── Time Ago ─── */
const timeAgo = (ts) => {
  if (!ts) return '';
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

/* ─── Floating Tab Rail (desktop) / Bottom Dock (mobile) ─── */
const FloatingTabRail = ({ tabs, activeTab, setActiveTab }) => (
  <>
    {/* Desktop: fixed vertical rail, left side */}
    <div
      className="hidden lg:flex fixed left-5 top-1/2 -translate-y-1/2 z-30 tab-rail flex-col gap-2 p-3"
      data-testid="floating-tab-rail"
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
            data-tooltip={tab.label}
            className={`tab-rail-btn ${isActive ? 'active' : ''}`}
            aria-label={tab.label}
            aria-current={isActive ? 'page' : undefined}
          >
            <tab.icon size={17} strokeWidth={2.2} />
          </button>
        );
      })}
    </div>

    {/* Mobile: fixed bottom dock */}
    <div
      className="lg:hidden fixed bottom-4 left-1/2 -translate-x-1/2 z-30 tab-rail flex gap-1 p-2"
      data-testid="floating-tab-dock-mobile"
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-mobile-${tab.id}`}
            className={`tab-rail-btn ${isActive ? 'active' : ''}`}
            aria-label={tab.label}
          >
            <tab.icon size={16} strokeWidth={2.2} />
          </button>
        );
      })}
    </div>
  </>
);

/* ─── Floating Glass Window (staggered entry, optional drag) ─── */
const GlassWindow = React.forwardRef(({
  children,
  testId,
  className = '',
  style = {},
  draggable = false,
  dragConstraints,
  delay = 0,
  padding = 'p-6',
}, ref) => (
  <motion.div
    ref={ref}
    data-testid={testId}
    className={`spatial-glass ${padding} ${className}`}
    style={style}
    initial={{ opacity: 0, y: 40, scale: 0.96 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    transition={{ type: 'spring', stiffness: 180, damping: 20, delay }}
    drag={draggable}
    dragConstraints={dragConstraints}
    dragElastic={0.08}
    dragMomentum={false}
    whileDrag={{ scale: 1.015, zIndex: 40, boxShadow: '0 48px 90px rgba(0,0,0,0.75)' }}
  >
    {children}
  </motion.div>
));
GlassWindow.displayName = 'GlassWindow';

/* ─── Locked Feature Card ─── */
const LockedFeature = ({ label, plan }) => (
  <div className="rounded-2xl p-5 relative overflow-hidden" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)', filter: 'blur(0.5px)', opacity: 0.6 }}
    data-testid={`locked-${label.toLowerCase().replace(/\s+/g, '-')}`}>
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Lock size={14} style={{ color: '#5A5468' }} />
        <span className="text-xs font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>{label}</span>
      </div>
      <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>{plan} Plan</span>
    </div>
    <a href="/pricing" className="mt-3 flex items-center gap-1 text-[10px] font-bold" style={{ color: '#D4AF37' }}>
      <ArrowUpRight size={10} /> Upgrade to Unlock
    </a>
  </div>
);

/* ═══════════════════════════════════════════════════════════════ */
/* ONBOARDING WIZARD                                               */
/* ═══════════════════════════════════════════════════════════════ */
const OnboardingWizard = ({ token, onComplete }) => {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ business_name: '', website_url: '', industry: 'general' });
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [binId, setBinId] = useState('');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const industries = ['General', 'SaaS', 'E-Commerce', 'Agency', 'Healthcare', 'Real Estate', 'Restaurant', 'Construction', 'Consulting', 'Other'];

  const saveStep1 = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/client/onboarding/step1`, { method: 'POST', headers, body: JSON.stringify(form) });
      setStep(2);
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const runFirstScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API_URL}/api/client/trigger-scan`, { method: 'POST', headers });
      if (res.ok) {
        const data = await res.json();
        setScanResult(data.result);
      }
    } catch (e) { console.error(e); }
    setScanning(false);
    setStep(4);
  };

  const finishOnboarding = async () => {
    try {
      const res = await fetch(`${API_URL}/api/client/onboarding/complete`, { method: 'POST', headers });
      if (res.ok) {
        const data = await res.json();
        setBinId(data.bin_id || '');
      }
    } catch (e) { console.error(e); }
    onComplete();
  };

  const stepConfig = [
    { num: 1, label: 'Business' },
    { num: 2, label: 'Channels' },
    { num: 3, label: 'First Scan' },
    { num: 4, label: 'Ready' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(5,5,7,0.95)', backdropFilter: 'blur(20px)' }} data-testid="onboarding-wizard">
      <div className="w-full max-w-lg mx-4">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8 justify-center">
          {stepConfig.map(s => (
            <div key={s.num} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${step >= s.num ? 'text-[#050507]' : ''}`}
                style={{ background: step >= s.num ? '#D4AF37' : 'rgba(255,255,255,0.06)', color: step >= s.num ? '#050507' : 'var(--aurem-body-secondary)' }}>
                {step > s.num ? <CheckCircle2 size={16} /> : s.num}
              </div>
              {s.num < 4 && <div className="w-12 h-0.5 rounded-full" style={{ background: step > s.num ? '#D4AF37' : 'rgba(255,255,255,0.06)' }} />}
            </div>
          ))}
        </div>

        <div className="rounded-2xl p-8" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}>
          {/* Step 1: Business Info */}
          {step === 1 && (
            <div className="space-y-5" data-testid="onboarding-step-1">
              <div className="text-center mb-6">
                <h2 className="text-xl font-black" style={{ color: 'var(--aurem-heading)' }}>Welcome to AUREM</h2>
                <p className="text-xs mt-2" style={{ color: 'var(--aurem-body-secondary)' }}>Let's set up your AI business automation</p>
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: 'var(--aurem-body-secondary)' }}>Business Name</label>
                <input type="text" value={form.business_name} onChange={e => setForm(f => ({ ...f, business_name: e.target.value }))}
                  placeholder="Polaris Built Inc." data-testid="onboard-business-name"
                  className="w-full px-4 py-3 rounded-xl text-sm outline-none" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }} />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: 'var(--aurem-body-secondary)' }}>Website URL</label>
                <input type="url" value={form.website_url} onChange={e => setForm(f => ({ ...f, website_url: e.target.value }))}
                  placeholder="https://yoursite.com" data-testid="onboard-website"
                  className="w-full px-4 py-3 rounded-xl text-sm outline-none" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }} />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1.5" style={{ color: 'var(--aurem-body-secondary)' }}>Industry</label>
                <div className="grid grid-cols-3 gap-2">
                  {industries.map(ind => (
                    <button key={ind} onClick={() => setForm(f => ({ ...f, industry: ind.toLowerCase() }))}
                      className="px-3 py-2 rounded-lg text-[10px] font-bold transition-all"
                      style={{ background: form.industry === ind.toLowerCase() ? 'rgba(212,175,55,0.15)' : 'rgba(255,255,255,0.03)',
                        color: form.industry === ind.toLowerCase() ? '#D4AF37' : 'var(--aurem-body-secondary)',
                        border: form.industry === ind.toLowerCase() ? '1px solid rgba(212,175,55,0.3)' : '1px solid rgba(255,255,255,0.06)' }}>
                      {ind}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={saveStep1} disabled={saving || !form.business_name || !form.website_url} data-testid="onboard-next-1"
                className="w-full py-3 rounded-xl text-sm font-bold tracking-wide flex items-center justify-center gap-2"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507', opacity: (!form.business_name || !form.website_url) ? 0.4 : 1 }}>
                {saving ? 'Saving...' : 'Continue'} <ChevronRight size={16} />
              </button>
            </div>
          )}

          {/* Step 2: Channels */}
          {step === 2 && (
            <div className="space-y-5" data-testid="onboarding-step-2">
              <div className="text-center mb-4">
                <h2 className="text-xl font-black" style={{ color: 'var(--aurem-heading)' }}>Connect Your Channels</h2>
                <p className="text-xs mt-2" style={{ color: 'var(--aurem-body-secondary)' }}>Set up email and WhatsApp (or skip for now)</p>
              </div>
              <ConnectionWizard tenantId="polaris-built-001" token={token} />
              <button onClick={() => setStep(3)} data-testid="onboard-next-2"
                className="w-full py-3 rounded-xl text-sm font-bold tracking-wide flex items-center justify-center gap-2"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507' }}>
                Continue to First Scan <ChevronRight size={16} />
              </button>
            </div>
          )}

          {/* Step 3: First Scan */}
          {step === 3 && (
            <div className="text-center space-y-6" data-testid="onboarding-step-3">
              <h2 className="text-xl font-black" style={{ color: 'var(--aurem-heading)' }}>Run Your First Scan</h2>
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>ORA will analyze your website for performance, security, SEO and accessibility</p>
              {scanning ? (
                <div className="py-8">
                  <div className="w-16 h-16 mx-auto rounded-full border-4 border-t-transparent animate-spin" style={{ borderColor: '#D4AF37', borderTopColor: 'transparent' }} />
                  <p className="text-xs mt-4 font-bold animate-pulse" style={{ color: '#D4AF37' }}>Scanning your website...</p>
                </div>
              ) : (
                <button onClick={runFirstScan} data-testid="onboard-scan-btn"
                  className="px-8 py-4 rounded-xl text-sm font-bold tracking-wide mx-auto flex items-center gap-2"
                  style={{ background: 'linear-gradient(135deg, #68DA8D, #3DA563)', color: '#050507' }}>
                  <Search size={18} /> Start Scan
                </button>
              )}
              <button onClick={() => setStep(4)} className="text-[10px] underline" style={{ color: 'var(--aurem-body-secondary)' }}>
                Skip for now
              </button>
            </div>
          )}

          {/* Step 4: Ready */}
          {step === 4 && (
            <div className="text-center space-y-6" data-testid="onboarding-step-4">
              <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #D4B977, #B19A5E)' }}>
                <CheckCircle2 size={32} style={{ color: '#050507' }} />
              </div>
              <h2 className="text-xl font-black" style={{ color: 'var(--aurem-heading)' }}>Your AUREM is Ready</h2>
              {scanResult && (
                <div className="rounded-xl p-4 text-left" style={{ background: 'rgba(104,218,141,0.06)', border: '1px solid rgba(104,218,141,0.15)' }}>
                  <p className="text-xs font-bold" style={{ color: '#68DA8D' }}>Scan Complete</p>
                  <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                    Score: {scanResult?.overall_score || 'Processing'}
                  </p>
                </div>
              )}
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                Install ORA on your phone: visit <strong style={{ color: '#FF6B00' }}>/ora</strong> in Safari/Chrome and "Add to Home Screen"
              </p>
              <button onClick={finishOnboarding} data-testid="onboard-done-btn"
                className="w-full py-3 rounded-xl text-sm font-bold tracking-wide"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507' }}>
                Go to Dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════ */
/* BILLING TAB                                                     */
/* ═══════════════════════════════════════════════════════════════ */
const BillingTab = ({ token }) => {
  const [sub, setSub] = useState(null);
  const [packages, setPackages] = useState({});
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/api/payments/subscription`, { headers }).then(r => r.ok ? r.json() : null),
      fetch(`${API_URL}/api/payments/config`, { headers }).then(r => r.ok ? r.json() : null),
      fetch(`${API_URL}/api/payments/history`, { headers }).then(r => r.ok ? r.json() : null),
    ]).then(([s, c, h]) => {
      if (s) setSub(s);
      if (c?.plans) setPackages(c.plans);
      if (h?.transactions) setHistory(h.transactions);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [token]);

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/payments/portal`, { method: 'POST', headers });
      if (res.ok) {
        const data = await res.json();
        if (data.url) window.open(data.url, '_blank');
      }
    } catch (e) { console.error(e); }
    setPortalLoading(false);
  };

  const startCheckout = async (pkgId) => {
    try {
      const res = await fetch(`${API_URL}/api/payments/checkout`, {
        method: 'POST', headers, body: JSON.stringify({ package_id: pkgId, origin_url: window.location.origin }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.checkout_url) window.open(data.checkout_url, '_blank');
      }
    } catch (e) { console.error(e); }
  };

  if (loading) return <div className="flex items-center justify-center p-12"><div className="animate-spin w-6 h-6 border-2 border-t-transparent rounded-full" style={{ borderColor: '#D4AF37', borderTopColor: 'transparent' }} /></div>;

  const currentPlan = sub?.plan || 'trial';

  return (
    <div className="space-y-6" data-testid="billing-tab">
      {/* Current Plan */}
      <div className="rounded-2xl p-6" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-[10px] uppercase tracking-[3px] font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Current Plan</p>
            <p className="text-2xl font-black mt-1" style={{ color: '#D4AF37' }}>{sub?.plan_label || 'Free Trial'}</p>
            {sub?.has_subscription && (
              <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                ${sub.amount}/{sub.currency?.toUpperCase()} • {sub.cancel_at_period_end ? 'Cancels' : 'Renews'} {sub.current_period_end ? new Date(sub.current_period_end * 1000).toLocaleDateString() : ''}
              </p>
            )}
          </div>
          {sub?.has_subscription && (
            <button onClick={openPortal} disabled={portalLoading} data-testid="manage-subscription-btn"
              className="px-4 py-2.5 rounded-xl text-xs font-bold flex items-center gap-1.5"
              style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.2)' }}>
              <ExternalLink size={12} /> {portalLoading ? 'Loading...' : 'Manage Subscription'}
            </button>
          )}
        </div>
      </div>

      {/* Plans */}
      <div>
        <p className="text-[10px] uppercase tracking-[3px] font-bold mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>Available Plans</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(packages).map(([id, pkg]) => {
            const isCurrent = currentPlan === id;
            return (
              <div key={id} className="rounded-2xl p-5 relative" data-testid={`plan-card-${id}`}
                style={{ background: 'var(--aurem-card-bg)', border: isCurrent ? '2px solid #D4AF37' : '1px solid var(--aurem-card-border)' }}>
                {isCurrent && <span className="absolute -top-2 right-4 px-2 py-0.5 rounded-full text-[9px] font-bold" style={{ background: '#D4AF37', color: '#050507' }}>CURRENT</span>}
                <p className="text-lg font-black" style={{ color: 'var(--aurem-heading)' }}>{pkg.name}</p>
                <p className="text-2xl font-black mt-1" style={{ color: '#D4AF37' }}>${pkg.amount}<span className="text-xs font-normal" style={{ color: 'var(--aurem-body-secondary)' }}>/mo</span></p>
                <ul className="mt-3 space-y-1.5">
                  {(pkg.features || []).map((f, i) => (
                    <li key={i} className="text-[10px] flex items-start gap-1.5" style={{ color: 'var(--aurem-body)' }}>
                      <CheckCircle2 size={10} className="mt-0.5 flex-shrink-0" style={{ color: '#68DA8D' }} /> {f}
                    </li>
                  ))}
                </ul>
                {!isCurrent && (
                  <button onClick={() => startCheckout(id)} data-testid={`upgrade-${id}-btn`}
                    className="w-full mt-4 py-2.5 rounded-xl text-xs font-bold tracking-wide"
                    style={{ background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507' }}>
                    {currentPlan === 'trial' ? 'Start Plan' : 'Switch Plan'}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Invoice History */}
      {history.length > 0 && (
        <div className="rounded-2xl p-6" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}>
          <p className="text-[10px] uppercase tracking-[3px] font-bold mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>Payment History</p>
          <div className="space-y-2">
            {history.slice(0, 10).map((tx, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)' }}>
                <div>
                  <p className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{tx.package_name || tx.plan || 'Payment'}</p>
                  <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{tx.created_at ? new Date(tx.created_at).toLocaleDateString() : ''}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold" style={{ color: '#68DA8D' }}>${tx.amount}</p>
                  <p className="text-[9px] font-bold uppercase" style={{ color: tx.status === 'paid' ? '#68DA8D' : '#FF6B00' }}>{tx.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════ */
/* SETTINGS TAB                                                    */
/* ═══════════════════════════════════════════════════════════════ */
const SettingsTab = ({ token, workspace }) => {
  const [form, setForm] = useState({
    business_name: workspace?.business_name || '',
    website: workspace?.website || '',
    business_description: workspace?.ai_context?.business_description || '',
    tone: workspace?.ai_context?.tone || 'Professional',
    services: (workspace?.ai_context?.services || []).join(', '),
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notifPrefs, setNotifPrefs] = useState({ scan_complete: true, repair_deployed: true, new_lead: true, ora_action_required: true, morning_brief: true });
  const [pushSupported, setPushSupported] = useState(false);
  const [pushGranted, setPushGranted] = useState(false);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    setPushSupported('Notification' in window && 'serviceWorker' in navigator);
    if ('Notification' in window) setPushGranted(Notification.permission === 'granted');
    fetch(`${API_URL}/api/client/notification-preferences`, { headers }).then(r => r.ok ? r.json() : null).then(d => { if (d) setNotifPrefs(d); }).catch(() => {});
  }, []);

  const saveProfile = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/client/profile`, {
        method: 'PUT', headers,
        body: JSON.stringify({ ...form, services: form.services.split(',').map(s => s.trim()).filter(Boolean) }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const enablePush = async () => {
    try {
      const perm = await Notification.requestPermission();
      setPushGranted(perm === 'granted');
      if (perm === 'granted') {
        const reg = await navigator.serviceWorker.ready;
        const vapidRes = await fetch(`${API_URL}/api/push/vapid-key`);
        const { public_key } = await vapidRes.json();
        const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: public_key });
        await fetch(`${API_URL}/api/push/subscribe`, { method: 'POST', headers, body: JSON.stringify({ endpoint: sub.endpoint, keys: { p256dh: btoa(String.fromCharCode(...new Uint8Array(sub.getKey('p256dh')))), auth: btoa(String.fromCharCode(...new Uint8Array(sub.getKey('auth')))) } }) });
      }
    } catch (e) { console.error('Push setup error:', e); }
  };

  const saveNotifPrefs = async () => {
    await fetch(`${API_URL}/api/client/notification-preferences`, { method: 'PUT', headers, body: JSON.stringify(notifPrefs) }).catch(() => {});
  };

  return (
    <div className="space-y-6" data-testid="settings-tab">
      {/* Business Profile */}
      <div className="rounded-2xl p-6" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}>
        <p className="text-[10px] uppercase tracking-[3px] font-bold mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>Business Profile</p>
        <div className="space-y-3">
          {[
            { key: 'business_name', label: 'Business Name', placeholder: 'Your Business' },
            { key: 'website', label: 'Website', placeholder: 'https://yoursite.com' },
            { key: 'business_description', label: 'Description', placeholder: 'What does your business do?', textarea: true },
            { key: 'services', label: 'Services (comma-separated)', placeholder: 'Web Design, SEO, Marketing' },
            { key: 'tone', label: 'Communication Tone', placeholder: 'Professional' },
          ].map(f => (
            <div key={f.key}>
              <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{f.label}</label>
              {f.textarea ? (
                <textarea value={form[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder} rows={3} data-testid={`setting-${f.key}`}
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }} />
              ) : (
                <input type="text" value={form[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder} data-testid={`setting-${f.key}`}
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }} />
              )}
            </div>
          ))}
          <button onClick={saveProfile} disabled={saving} data-testid="save-profile-btn"
            className="px-6 py-2.5 rounded-xl text-xs font-bold tracking-wide flex items-center gap-1.5"
            style={{ background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507', opacity: saving ? 0.6 : 1 }}>
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      <div className="rounded-2xl p-6" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}>
        <div className="flex items-center justify-between mb-4">
          <p className="text-[10px] uppercase tracking-[3px] font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Notifications</p>
          {pushSupported && !pushGranted && (
            <button onClick={enablePush} data-testid="enable-push-btn"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-bold"
              style={{ background: 'rgba(104,218,141,0.1)', color: '#68DA8D', border: '1px solid rgba(104,218,141,0.2)' }}>
              <Bell size={12} /> Enable Push Notifications
            </button>
          )}
          {pushGranted && <span className="text-[10px] font-bold flex items-center gap-1" style={{ color: '#68DA8D' }}><Bell size={12} /> Enabled</span>}
        </div>
        <div className="space-y-2">
          {[
            { key: 'scan_complete', label: 'Scan complete alerts' },
            { key: 'repair_deployed', label: 'Repair deployed alerts' },
            { key: 'new_lead', label: 'New lead alerts' },
            { key: 'ora_action_required', label: 'ORA action required' },
            { key: 'morning_brief', label: 'Daily morning brief' },
          ].map(p => (
            <label key={p.key} className="flex items-center justify-between py-2 px-3 rounded-xl cursor-pointer" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <span className="text-xs" style={{ color: 'var(--aurem-body)' }}>{p.label}</span>
              <input type="checkbox" checked={notifPrefs[p.key]} onChange={e => { setNotifPrefs(prev => ({ ...prev, [p.key]: e.target.checked })); setTimeout(saveNotifPrefs, 100); }}
                className="w-4 h-4 rounded accent-[#D4AF37]" data-testid={`notif-${p.key}`} />
            </label>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════ */
/* MAIN CLIENT DASHBOARD                                           */
/* ═══════════════════════════════════════════════════════════════ */
const ClientDashboard = ({ token, user, onLogout }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const [bizId, setBizId] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [binId, setBinId] = useState('');
  const [binCopied, setBinCopied] = useState(false);
  const [activity, setActivity] = useState([]);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [planFeatures, setPlanFeatures] = useState({});
  const dragBoundsRef = useRef(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/client/dashboard`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setData(await res.json());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    const headers = { Authorization: `Bearer ${token}` };
    fetchDashboard();
    // BIN ID
    fetch(`${API_URL}/api/client/bin-id`, { headers }).then(r => r.ok ? r.json() : null).then(d => { if (d?.bin_id) setBinId(d.bin_id); }).catch(() => {});
    // Activity feed
    fetch(`${API_URL}/api/client/activity`, { headers }).then(r => r.ok ? r.json() : null).then(d => { if (d?.events) setActivity(d.events); }).catch(() => {});
    // Welcome card
    fetch(`${API_URL}/api/business-id/welcome-status`, { headers }).then(r => r.ok ? r.json() : null).then(d => { if (d?.show_welcome_card) setShowWelcome(true); if (d?.business_id) setBizId(d.business_id); }).catch(() => {});
    // Onboarding check
    fetch(`${API_URL}/api/client/onboarding-status`, { headers }).then(r => r.ok ? r.json() : null).then(d => { if (d && !d.onboarding_complete && !d.has_scans) setShowOnboarding(true); }).catch(() => {});
    // Plan features
    fetch(`${API_URL}/api/payments/config`).then(r => r.ok ? r.json() : null).then(d => { if (d?.plans) setPlanFeatures(d.plans); }).catch(() => {});
  }, [fetchDashboard, token]);

  const triggerScan = async () => {
    setScanning(true);
    try { const res = await fetch(`${API_URL}/api/client/trigger-scan`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }); if (res.ok) await fetchDashboard(); } catch (err) { console.error(err); }
    finally { setScanning(false); }
  };

  const copyKey = () => { if (data?.api_key?.full_key) { navigator.clipboard.writeText(data.api_key.full_key); setCopied(true); setTimeout(() => setCopied(false), 2000); } };
  const copyBin = () => { navigator.clipboard.writeText(binId); setBinCopied(true); setTimeout(() => setBinCopied(false), 2000); };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center" data-testid="client-dashboard-loading">
      <div className="text-center">
        <div className="w-12 h-12 rounded-2xl mx-auto mb-3 flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #D4B977, #B19A5E)', animation: 'auremFloat 2s ease-in-out infinite' }}>
          <span className="text-base font-black text-[#0A0A00]">A</span>
        </div>
        <p className="text-xs tracking-[3px] font-bold" style={{ color: 'var(--aurem-heading)' }}>LOADING DASHBOARD</p>
      </div>
    </div>
  );

  // Show onboarding wizard if first time
  if (showOnboarding) return <OnboardingWizard token={token} onComplete={() => { setShowOnboarding(false); fetchDashboard(); }} />;

  const health = data?.health;
  const usage = data?.usage;
  const workspace = data?.workspace;
  const historyScores = (data?.scan_history || []).map(s => s.overall_score).reverse();
  const businessName = data?.user?.business_name || user?.business_name || 'Your Business';
  const planLabel = workspace?.plan ? workspace.plan.charAt(0).toUpperCase() + workspace.plan.slice(1) : 'Trial';
  const isTrial = !workspace?.plan || workspace?.plan === 'trial';
  const isStarter = workspace?.plan === 'starter';
  const lockedForStarter = isStarter || isTrial;

  const TABS = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'integrations', label: 'Integrations', icon: Settings },
    { id: 'billing', label: 'Billing', icon: CreditCard },
    { id: 'settings', label: 'Settings', icon: Bell },
  ];

  return (
    <div className="flex-1 overflow-auto spatial-bg lightning-bg relative" ref={dragBoundsRef} data-testid="client-dashboard">
      {/* Floating Tab Rail (desktop + mobile bottom-dock) */}
      <FloatingTabRail tabs={TABS} activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Frosted glass top bar — minimal strip */}
      <div className="sticky top-0 z-20 px-6 py-3 flex items-center justify-between"
        style={{
          background: 'rgba(5,5,5,0.55)',
          backdropFilter: 'blur(22px)',
          WebkitBackdropFilter: 'blur(22px)',
          borderBottom: '1px solid rgba(255,255,255,0.04)',
        }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center levitate"
            style={{ background: 'linear-gradient(135deg, #D4B977, #B19A5E)', boxShadow: '0 6px 20px rgba(212,185,119,0.45)' }}>
            <span className="text-xs font-black text-[#0A0A00]">A</span>
          </div>
          <div>
            <h1 className="text-sm font-bold text-glow-gold" style={{ color: 'var(--aurem-heading)' }} data-testid="client-business-name">{businessName}</h1>
            <div className="flex items-center gap-2">
              <p className="text-[10px] uppercase tracking-[2px]" style={{ color: 'var(--aurem-body-secondary)' }}>{planLabel} · Operator</p>
              {binId && (
                <button onClick={copyBin} className="flex items-center gap-1 text-[9px] font-mono font-bold px-1.5 py-0.5 rounded" data-testid="bin-id-badge"
                  style={{ background: 'rgba(255,107,0,0.08)', color: '#FF6B00', border: '1px solid rgba(255,107,0,0.18)' }}>
                  {binCopied ? 'Copied!' : binId} <Copy size={8} />
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a href="/ora" target="_blank" rel="noopener noreferrer" data-testid="client-ora-link"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:scale-[1.02]"
            style={{ background: 'rgba(255,107,0,0.12)', color: '#FF6B00', border: '1px solid rgba(255,107,0,0.2)', textDecoration: 'none' }}>
            <MessageSquare size={13} /> ORA
          </a>
          <button onClick={triggerScan} disabled={scanning} data-testid="trigger-scan-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:scale-[1.02]"
            style={{ background: scanning ? 'rgba(255,255,255,0.05)' : 'rgba(104,218,141,0.12)', color: '#68DA8D', border: '1px solid rgba(104,218,141,0.22)' }}>
            <RefreshCw size={13} className={scanning ? 'animate-spin' : ''} /> {scanning ? 'Scanning...' : 'Run Scan'}
          </button>
          <button onClick={onLogout} className="p-2 rounded-xl hover:bg-white/5 transition" data-testid="client-logout-btn"><LogOut size={16} style={{ color: 'var(--aurem-body-secondary)' }} /></button>
        </div>
      </div>

      <div className="px-6 pt-6 pb-24 lg:pl-28 lg:pr-8 space-y-6 max-w-[1500px] mx-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.28, ease: [0.25, 0.8, 0.25, 1] }}
          >
        {activeTab === 'integrations' ? <ConnectionWizard tenantId={data?.tenant_id || user?.tenant_id || ''} token={token} />
        : activeTab === 'billing' ? <BillingTab token={token} />
        : activeTab === 'settings' ? <SettingsTab token={token} workspace={workspace ? { ...workspace, ai_context: data?.ai_context } : null} />
        : (
        <div className="space-y-6">
          {/* Row 1: Health + Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <GlassWindow testId="health-score-card" draggable dragConstraints={dragBoundsRef} delay={0.05}
              className="lg:col-span-1 flex flex-col items-center justify-center relative overflow-hidden cursor-grab active:cursor-grabbing">
              <p className="text-[10px] uppercase tracking-[3px] font-bold mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>Website Health</p>
              <div className="relative" style={{ filter: `drop-shadow(0 0 24px ${(health?.overall_score || 0) >= 80 ? 'rgba(104,218,141,0.45)' : (health?.overall_score || 0) >= 60 ? 'rgba(255,107,0,0.45)' : 'rgba(224,82,82,0.45)'})` }}>
                <ScoreRing score={health?.overall_score || 0} size={140} />
              </div>
              <p className="text-xs mt-4 font-medium" style={{ color: 'var(--aurem-body-secondary)' }}>{workspace?.website || 'No website configured'}</p>
              {health?.scanned_at && <p className="text-[10px] mt-1 flex items-center gap-1" style={{ color: 'var(--aurem-body-secondary)' }}><Clock size={10} /> Last scan: {new Date(health.scanned_at).toLocaleString()}</p>}
            </GlassWindow>
            <GlassWindow testId="category-breakdown" delay={0.12} className="lg:col-span-2">
              <p className="text-[10px] uppercase tracking-[3px] font-bold mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>Scan Breakdown</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-5">
                {health?.scores ? Object.entries(health.scores).map(([cat, score]) => <CategoryBadge key={cat} label={cat} score={score} />) : <p className="text-xs col-span-2" style={{ color: 'var(--aurem-body-secondary)' }}>No scan data yet. Click "Run Scan" to start.</p>}
              </div>
              {historyScores.length >= 2 && <Sparkline data={historyScores} width={500} height={50} />}
            </GlassWindow>
          </div>

          {/* Row 2: Usage */}
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, type: 'spring', stiffness: 180, damping: 22 }}>
            <p className="text-[10px] uppercase tracking-[3px] font-bold mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>Usage This Period</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              {[
                { icon: MessageSquare, label: 'AI Messages', value: usage?.ai_messages || 0, sub: usage?.included_messages === -1 ? 'Unlimited' : `/ ${usage?.included_messages || 0}` },
                { icon: Mail,          label: 'Email Messages', value: usage?.gmail_messages || 0 },
                { icon: MessageSquare, label: 'WhatsApp', value: usage?.whatsapp_messages || 0 },
                { icon: Phone,         label: 'Voice Minutes', value: usage?.phone_minutes || 0 },
                { icon: Zap,           label: 'Actions Run', value: usage?.actions_executed || 0 },
              ].map((card, i) => (
                <motion.div
                  key={card.label}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.25 + i * 0.06, type: 'spring', stiffness: 200, damping: 22 }}
                >
                  <StatCard {...card} />
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Row 3: Live Campaign Pipeline (iter 278 — replaced warehouse robot) */}
          <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.32, type: 'spring', stiffness: 180, damping: 22 }}
            className="mb-5"
          >
            <LiveCampaignPipeline token={token} />
          </motion.div>

          {/* Row 4: Activity Feed */}
          {activity.length > 0 && (
            <GlassWindow testId="activity-feed" delay={0.4}>
              <p className="text-[10px] uppercase tracking-[3px] font-bold mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>Recent Activity</p>
              <div className="space-y-2">
                {activity.map((evt, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.45 + i * 0.04 }}
                    className="flex items-center gap-3 py-2 px-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)' }}
                  >
                    <ActivityIcon type={evt.icon} />
                    <p className="text-xs flex-1 truncate" style={{ color: 'var(--aurem-body)' }}>{evt.description}</p>
                    <span className="text-[10px] flex-shrink-0" style={{ color: 'var(--aurem-body-secondary)' }}>{timeAgo(evt.timestamp)}</span>
                  </motion.div>
                ))}
              </div>
            </GlassWindow>
          )}

          {/* Row 5: Pixel + API Key */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlassWindow testId="pixel-events-card" draggable dragConstraints={dragBoundsRef} delay={0.48} className="cursor-grab active:cursor-grabbing">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(212,163,115,0.12)' }}><Globe size={18} style={{ color: '#FF6B00' }} /></div>
                <div><p className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Tracking Pixel</p><p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Events captured from your website</p></div>
              </div>
              <p className="text-4xl font-black mb-1 text-glow-gold" style={{ color: 'var(--aurem-heading)' }}>{data?.pixel_events || 0}</p>
              <div className="mt-4 p-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--aurem-divider)' }}>
                <p className="text-[10px] font-bold mb-1.5" style={{ color: 'var(--aurem-body-secondary)' }}>INSTALL SNIPPET</p>
                <code className="text-[10px] break-all leading-relaxed" style={{ color: '#68DA8D' }}>{`<script src="${API_URL}/api/pixel/aurem-pixel.js" data-aurem-key="${data?.api_key?.full_key || 'YOUR_KEY'}"></script>`}</code>
              </div>
            </GlassWindow>
            <GlassWindow testId="api-key-card" draggable dragConstraints={dragBoundsRef} delay={0.54} className="cursor-grab active:cursor-grabbing">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(104,218,141,0.12)' }}><Shield size={18} style={{ color: '#68DA8D' }} /></div>
                <div><p className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>API Key</p><p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>For pixel and webhook integration</p></div>
              </div>
              {data?.api_key ? (
                <div className="flex items-center gap-2 mb-3">
                  <code className="text-sm font-mono flex-1 p-2.5 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--aurem-heading)', border: '1px solid var(--aurem-divider)' }}>{showKey ? data.api_key.full_key : data.api_key.key}</code>
                  <button onClick={() => setShowKey(!showKey)} className="p-2 rounded-lg hover:bg-white/5" data-testid="toggle-key-visibility">{showKey ? <EyeOff size={15} style={{ color: 'var(--aurem-body-secondary)' }} /> : <Eye size={15} style={{ color: 'var(--aurem-body-secondary)' }} />}</button>
                  <button onClick={copyKey} className="p-2 rounded-lg hover:bg-white/5" data-testid="copy-key-btn">{copied ? <CheckCircle2 size={15} style={{ color: '#68DA8D' }} /> : <Copy size={15} style={{ color: 'var(--aurem-body-secondary)' }} />}</button>
                </div>
              ) : <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No API key generated yet.</p>}
            </GlassWindow>
          </div>

          {/* Row 6: Feature Gating — locked cards for Starter/Trial */}
          {lockedForStarter && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
              <p className="text-[10px] uppercase tracking-[3px] font-bold mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>Unlock More</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-testid="locked-features">
                <LockedFeature label="Revenue Forecasting" plan="Growth" />
                <LockedFeature label="Deep Scout" plan="Growth" />
                <LockedFeature label="GEO Tracking" plan="Growth" />
                <LockedFeature label="Sentiment Analysis" plan="Growth" />
                <LockedFeature label="V2V Voice" plan="Growth" />
                <LockedFeature label="White Label" plan="Enterprise" />
              </div>
            </motion.div>
          )}

          {/* Row 7: Scan History */}
          {data?.scan_history?.length > 0 && (
            <GlassWindow testId="scan-history-table" delay={0.66}>
              <p className="text-[10px] uppercase tracking-[3px] font-bold mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>Scan History</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs"><thead><tr style={{ borderBottom: '1px solid var(--aurem-divider)' }}>{['Date', 'Score', 'Performance', 'Security', 'SEO', 'Accessibility', 'Issues', ''].map(h => <th key={h} className="text-left py-2 px-3 font-semibold" style={{ color: 'var(--aurem-body-secondary)' }}>{h}</th>)}</tr></thead><tbody>
                  {data.scan_history.map((scan, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--aurem-divider)' }}>
                      <td className="py-2.5 px-3" style={{ color: 'var(--aurem-body)' }}>{scan.scanned_at ? new Date(scan.scanned_at).toLocaleDateString() : '—'}</td>
                      <td className="py-2.5 px-3"><span className="font-bold" style={{ color: scan.overall_score >= 80 ? '#68DA8D' : scan.overall_score >= 60 ? '#FF6B00' : '#E05252' }}>{scan.overall_score}</span></td>
                      {['performance', 'security', 'seo', 'accessibility'].map(cat => <td key={cat} className="py-2.5 px-3" style={{ color: 'var(--aurem-body)' }}>{scan.scores?.[cat] ?? '—'}</td>)}
                      <td className="py-2.5 px-3">{scan.critical_count > 0 && <span className="text-[10px] font-bold mr-1" style={{ color: '#E05252' }}>{scan.critical_count}C</span>}{scan.warning_count > 0 && <span className="text-[10px] font-bold" style={{ color: '#FF6B00' }}>{scan.warning_count}W</span>}{scan.critical_count === 0 && scan.warning_count === 0 && <span style={{ color: '#68DA8D' }}>Clean</span>}</td>
                      <td className="py-2.5 px-3">
                        <a href={`${API_URL}/api/client/scan-report-pdf?scan_date=${scan.scanned_at?.slice(0,10) || ''}`}
                          target="_blank" rel="noopener noreferrer" data-testid={`pdf-download-${i}`}
                          className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg transition-all hover:opacity-80"
                          style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.15)', textDecoration: 'none', whiteSpace: 'nowrap' }}
                          onClick={(e) => { e.preventDefault(); fetch(`${API_URL}/api/client/scan-report-pdf?scan_date=${scan.scanned_at?.slice(0,10) || ''}`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.blob()).then(b => { const url = URL.createObjectURL(b); const a = document.createElement('a'); a.href = url; a.download = `scan-report-${scan.scanned_at?.slice(0,10)}.pdf`; a.click(); URL.revokeObjectURL(url); }).catch(() => {}); }}>
                          <ArrowUpRight size={10} /> PDF
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody></table>
              </div>
            </GlassWindow>
          )}
        </div>
        )}
          </motion.div>
        </AnimatePresence>
      </div>

      {bizId && <div data-testid="client-business-id-badge" className="fixed bottom-4 right-4 z-30 px-3 py-2 rounded-xl" style={{ background: 'rgba(10,10,20,0.9)', border: '1px solid rgba(255,107,0,0.15)', backdropFilter: 'blur(12px)' }}><span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, fontWeight: 700, color: '#FF6B00', letterSpacing: '0.05em' }}>{bizId}</span></div>}
      {showWelcome && <WelcomeCard token={token} onDismiss={() => setShowWelcome(false)} />}
    </div>
  );
};

export default ClientDashboard;
