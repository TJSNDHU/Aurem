/**
 * AUREM — The AI Employee That Never Sleeps.
 * Landing Page: Dark Obsidian + Copper/Gold Glassmorphism
 * Designed for cold traffic. Plain business language.
 * A 50-year-old salon owner in Mississauga must understand every word.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { motion } from 'framer-motion';
import LiveChatWidget from '../components/LiveChatWidget';
import SevenDayTrialPromo from './SevenDayTrialPromo';
import '../theme/aurem-floating.css';
import {
  ArrowRight, Check, ChevronDown, Sparkles,
  Target, Users, FileText, Wrench, Brain, DollarSign, Mic,
  AlertTriangle, Clock, TrendingUp, Shield, BarChart3, Building2,
  Briefcase, Calculator, Search, Zap, BookOpen,
} from 'lucide-react';

const fadeUp = {
  hidden: { opacity: 1, y: 0 },
  visible: { opacity: 1, y: 0 },
};
const stagger = {
  hidden: { opacity: 1 },
  visible: { opacity: 1, transition: { staggerChildren: 0 } },
};
const scaleUp = {
  hidden: { opacity: 0, scale: 0.92 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.55 } },
};

/* Below-fold animations (used only for scroll-triggered content) */
const fadeUpScroll = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] } },
};
const staggerScroll = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.15 } },
};

const PlatformLanding = () => {
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState(null);

  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

  /* ──────── DATA ──────── */

  const painPoints = [
    { icon: Users, title: 'Leads slip through', body: "You're too busy to follow up on every inquiry. AUREM scores, enriches, and contacts every lead automatically." },
    { icon: DollarSign, title: 'Invoices go unpaid', body: "Chasing payments takes time you don't have. AUREM sends reminders and tracks every outstanding invoice for you." },
    { icon: Wrench, title: 'Your website breaks silently', body: 'SEO issues, broken pages, slow load times \u2014 costing you customers. AUREM scans and fixes them overnight.' },
  ];

  const capabilities = [
    { icon: Search, title: 'Lead Intelligence', body: 'Finds, scores, and follows up on leads automatically. Knows who to contact and when.' },
    { icon: Mic, title: 'ORA Voice AI', body: 'Answers customer questions by voice or chat. Responds in under 1 second.' },
    { icon: DollarSign, title: 'Invoice Automation', body: 'Sends reminders, tracks payments, flags overdue accounts. Zero manual work.' },
    { icon: FileText, title: 'Morning Brief', body: 'Every morning at 7 am: what happened overnight, what needs your attention, what AUREM already handled.' },
    { icon: Wrench, title: 'Website Repair', body: 'Scans your site for SEO issues, broken links, and slow pages. Fixes them automatically.' },
    { icon: TrendingUp, title: 'Economic Intelligence', body: 'Live Bank of Canada data \u2014 exchange rates, interest rates, economic calendar. Business context, not advice.' },
  ];

  const agents = [
    { step: '01', name: 'Scout', desc: 'Finds opportunities and problems', color: '#D4AF37' },
    { step: '02', name: 'Architect', desc: 'Plans the best response', color: '#4ade80' },
    { step: '03', name: 'Envoy', desc: 'Decides what action to take', color: '#D4AF37' },
    { step: '04', name: 'Closer', desc: 'Executes automatically', color: '#4ade80' },
    { step: '05', name: 'Learn', desc: 'Gets smarter every day', color: '#D4AF37' },
  ];

  const personas = [
    { icon: Building2, title: 'Independent businesses', body: 'Salons, clinics, contractors, retailers. One system replacing 3 tools and 10 hours of manual work per week.' },
    { icon: Briefcase, title: 'Agencies and consultants', body: 'Manage multiple client accounts from one dashboard. White-label available.' },
    { icon: Calculator, title: 'Accountants and bookkeepers', body: "Monitor your clients' financial health automatically. Catch problems before they become emergencies." },
  ];

  const trustStats = [
    { value: '100/100', label: 'System efficiency score' },
    { value: '37/37', label: 'Live tests passing' },
    { value: '0', label: 'Chaos test failures' },
    { value: '6', label: 'Legal compliance policies' },
    { value: '$0', label: 'Monthly AI inference cost' },
  ];

  const pricingPlans = [
    {
      name: 'Starter', price: 97, sub: 'Perfect for independent businesses', highlight: false,
      features: ['Lead scoring and follow-up', 'Invoice automation', 'Morning Brief', 'Website repair', '500 AI actions/month', 'ORA chat assistant'],
      cta: 'Start Free Trial',
    },
    {
      name: 'Growth', price: 297, sub: 'For growing businesses', highlight: true, badge: 'Most Popular',
      features: ['Everything in Starter, plus:', 'ORA voice AI (5 concurrent)', 'Economic Intelligence dashboard', '5,000 AI actions/month', '3 workspaces', 'Partner referral access'],
      cta: 'Start Free Trial',
    },
    {
      name: 'Enterprise', price: 997, sub: 'For agencies and accountants', highlight: false,
      features: ['Everything in Growth, plus:', 'Unlimited workspaces and actions', 'White-label (your brand, your domain)', '25 concurrent voice sessions', 'Dedicated onboarding', 'Priority support'],
      cta: 'Contact Sales',
    },
  ];

  const faqs = [
    { q: 'Do I need technical knowledge to use AUREM?', a: 'No. AUREM is set-and-forget. You log in, connect your business, and it runs. No coding, no configuration.' },
    { q: 'What does "$0 AI cost" mean?', a: 'AUREM uses free AI models internally. You pay the flat monthly subscription. No per-message or per-action fees ever.' },
    { q: 'Is my business data secure?', a: 'Yes. All data is encrypted, stored in Canada, and never sold or shared. PIPEDA compliant. Full audit trail.' },
    { q: 'Can I cancel anytime?', a: "Yes. Cancel before your next billing date and you won't be charged again. No contracts, no cancellation fees." },
    { q: 'What is the Economic Intelligence feature?', a: 'Live business context from the Bank of Canada \u2014 exchange rates, interest rates, economic calendar. Informational only. Not investment advice.' },
  ];

  /* ──────── SHARED STYLES ──────── */
  const glass = { background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.05)', backdropFilter: 'blur(8px)' };
  const goldGrad = 'linear-gradient(135deg, #D4AF37, #B88759)';
  const heading = { fontFamily: "'Cinzel', 'Playfair Display', Georgia, serif" };

  return (
    <div className="min-h-screen text-white" style={{ fontFamily: "'Inter', sans-serif", background: '#050507' }}>

      {/* NAV */}
      <header role="banner" aria-label="Site header">
      <nav
        className="fixed top-0 left-0 right-0 z-50 border-b border-[#D4AF37]/10"
        style={{ background: 'rgba(5,5,7,0.88)', backdropFilter: 'blur(20px)' }}>
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <div className="size-9 rounded-lg flex items-center justify-center relative" style={{ background: goldGrad }}>
              <Target className="w-[18px] h-[18px] text-[#050507]" />
              <div className="absolute -top-0.5 -right-0.5 size-2 rounded-full animate-pulse bg-[#4ade80]" />
            </div>
            <span className="text-base tracking-[0.25em] font-light" style={heading}>AUREM</span>
          </div>
          <div className="hidden md:flex items-center gap-7">
            <button onClick={() => scrollTo('features')} aria-label="Go to features section" className="text-[11px] text-[#9ca3af] hover:text-[#D4AF37] transition-colors tracking-wider uppercase">Features</button>
            <button onClick={() => scrollTo('pricing')} aria-label="Go to pricing section" className="text-[11px] text-[#9ca3af] hover:text-[#D4AF37] transition-colors tracking-wider uppercase">Pricing</button>
            <button onClick={() => scrollTo('about')} aria-label="Go to about section" className="text-[11px] text-[#9ca3af] hover:text-[#D4AF37] transition-colors tracking-wider uppercase">About</button>
            <button onClick={() => scrollTo('faq')} aria-label="Go to FAQ section" className="text-[11px] text-[#9ca3af] hover:text-[#D4AF37] transition-colors tracking-wider uppercase">FAQ</button>
            <button onClick={() => navigate('/login')} className="text-[11px] text-[#D4AF37] hover:text-[#F7E7CE] transition-colors tracking-wider uppercase" data-testid="nav-login-btn">
              Login &rarr;
            </button>
            <motion.button whileHover={{ scale: 1.03, boxShadow: '0 0 25px rgba(212,175,55,0.25)' }} whileTap={{ scale: 0.97 }}
              onClick={() => navigate('/platform/signup')}
              className="px-5 py-2 rounded-lg text-[11px] font-bold tracking-wider text-[#050507]"
              style={{ background: goldGrad }} data-testid="nav-signup-btn">
              Start Free Trial
            </motion.button>
          </div>
        </div>
      </nav>
      </header>

      {/* SEO Meta */}
      <Helmet>
        <title>AUREM | World's First Sovereign AI Workforce, ORA by AUREM</title>
        <meta name="description" content="AUREM is the world's first Sovereign AI Workforce. Six autonomous agents powered by ORA by AUREM hunt, qualify, and close leads in any language, 24/7. Multi-LLM ORA intelligence (GPT-4o, Claude Sonnet 4.5, Gemini 3, Llama 3.3). Sovereign data residency · CASL compliant · Built in Canada. Starting at $97 CAD/month." />
        <link rel="canonical" href="https://aurem.live/" />
      </Helmet>

      {/* ═══ HERO ═══ */}
      <section className="pt-36 pb-20 px-6 lg:px-8 relative overflow-hidden" style={{ minHeight: '100vh' }}>
        {/* Background robot image with vignette + grid overlay */}
        <div className="absolute inset-0" aria-hidden="true">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: 'url(/assets/aurem-hero-robot.jpg)',
              backgroundSize: 'cover',
              backgroundPosition: 'center right',
              backgroundRepeat: 'no-repeat',
              filter: 'brightness(0.72) saturate(1.1)',
            }}
          />
          {/* Left-side gradient darkening so hero copy stays readable */}
          <div
            className="absolute inset-0"
            style={{
              background:
                'linear-gradient(90deg, rgba(5,5,7,0.96) 0%, rgba(5,5,7,0.82) 28%, rgba(5,5,7,0.5) 55%, rgba(5,5,7,0.2) 100%)',
            }}
          />
          {/* Bottom fade-to-page */}
          <div
            className="absolute inset-x-0 bottom-0 h-40"
            style={{ background: 'linear-gradient(180deg, transparent 0%, #05050A 100%)' }}
          />
          {/* Gold grid */}
          <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(#D4AF37 1px, transparent 1px), linear-gradient(90deg, #D4AF37 1px, transparent 1px)', backgroundSize: '60px 60px' }} />
          {/* Gold accent glow */}
          <div className="absolute top-1/3 left-1/4 w-[500px] h-[500px] rounded-full blur-[200px]" style={{ background: 'rgba(212,175,55,0.06)' }} />
        </div>

        <div className="max-w-4xl mx-auto lg:mx-0 lg:ml-[8%] text-center lg:text-left relative">
          <motion.div variants={stagger} initial="hidden" animate="visible">
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 mb-4 px-3 py-1.5 rounded-full text-[10px] tracking-[0.2em]"
              style={{ background: 'linear-gradient(135deg, rgba(212,175,55,0.18), rgba(255,107,0,0.10))', border: '1px solid rgba(212,175,55,0.4)', color: '#F5E6A8', boxShadow: '0 0 24px rgba(212,175,55,0.25)' }}
              data-testid="hero-worlds-first-badge">
              <span style={{ fontSize: 13 }}>👑</span>
              WORLD'S FIRST · SOVEREIGN AI WORKFORCE
            </motion.div>
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 mb-6 px-3 py-1.5 rounded-full text-[10px] tracking-[0.2em] ml-2"
              style={{ background: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.22)', color: '#D4AF37' }}>
              <span className="size-1.5 rounded-full" style={{ background: '#68DA8D', boxShadow: '0 0 8px #68DA8D' }} />
              ORA BY AUREM · AVAILABLE 24/7 · 20+ LANGUAGES
            </motion.div>
            <motion.h1 variants={fadeUp} className="text-4xl sm:text-5xl lg:text-6xl mb-6 leading-[1.05] tracking-tight" style={heading} data-testid="hero-title">
              <span className="text-white">The Sovereign AI Workforce</span><br />
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: goldGrad }}>That Never Sleeps.</span>
            </motion.h1>

            <motion.p variants={fadeUp} className="text-base sm:text-lg text-[#c9c9d1] max-w-2xl mx-auto lg:mx-0 mb-10 leading-relaxed">
              <strong className="text-[#F5E6A8]">AUREM</strong> is the world's first <strong className="text-[#D4AF37]">Sovereign AI Workforce</strong> &mdash;
              six autonomous agents powered by <strong className="text-[#F5E6A8]">ORA by AUREM</strong> hunt, qualify, and close leads in any language, 24/7.
              Starting at <span className="text-[#D4AF37] font-semibold">$97 CAD/month</span>.
            </motion.p>

            <motion.div variants={fadeUp} className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4 mb-10">
              <motion.button whileHover={{ scale: 1.03, boxShadow: '0 0 40px rgba(212,175,55,0.45)' }} whileTap={{ scale: 0.97 }}
                onClick={() => navigate('/platform/signup')}
                className="px-8 py-3.5 rounded-lg text-sm font-bold flex items-center gap-3 tracking-wider text-[#050507]"
                style={{ background: goldGrad }} data-testid="hero-cta-btn">
                Start Free Trial <ArrowRight className="size-4" />
              </motion.button>
              <motion.button whileHover={{ borderColor: 'rgba(212,175,55,0.4)' }}
                onClick={() => navigate('/contact?topic=audit')}
                className="px-8 py-3.5 rounded-lg text-sm font-medium flex items-center gap-2 text-[#c9c9d1] hover:text-[#D4AF37] transition-all tracking-wider"
                style={{ border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(10,10,20,0.4)', backdropFilter: 'blur(8px)' }}
                data-testid="hero-audit-btn">
                Get a Free Audit <Sparkles className="size-4" />
              </motion.button>
            </motion.div>

            {/* Trust bar */}
            <motion.div variants={fadeUp}
              className="inline-flex flex-wrap items-center justify-center lg:justify-start gap-x-6 gap-y-1 px-6 py-2.5 rounded-full text-[10px] text-[#c9c9d1] tracking-wider"
              style={{ background: 'rgba(10,10,20,0.55)', border: '1px solid rgba(212,175,55,0.12)', backdropFilter: 'blur(12px)' }}
              data-testid="trust-bar">
              <span>100/100 system score</span>
              <span className="text-[#555]">&middot;</span>
              <span>37/37 live tests</span>
              <span className="text-[#555]">&middot;</span>
              <span>$0 monthly AI cost</span>
              <span className="text-[#555]">&middot;</span>
              <span>Bank of Canada data</span>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ═══ SITE MONITOR LEAD MAGNET ═══ */}
      <section className="py-16 px-6 lg:px-8 perf-cv" style={{ background: 'linear-gradient(180deg, #050507 0%, #080810 100%)' }} data-testid="site-monitor-strip">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="relative rounded-2xl overflow-hidden p-8 lg:p-10"
            style={{
              background: 'linear-gradient(135deg, rgba(212,175,55,0.05) 0%, rgba(5,5,7,0.8) 70%)',
              border: '1px solid rgba(212,175,55,0.2)',
              backdropFilter: 'blur(14px)',
            }}
          >
            {/* Accent glow */}
            <div className="absolute -top-20 -right-20 size-80 rounded-full blur-[140px] pointer-events-none" style={{ background: 'rgba(74,222,128,0.08)' }} />
            <div className="relative flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
              <div className="flex-1">
                <div className="inline-flex items-center gap-2 mb-3 px-2.5 py-1 rounded-full text-[10px] tracking-[0.2em]"
                  style={{ background: 'rgba(74,222,128,0.1)', border: '1px solid rgba(74,222,128,0.25)', color: '#68DA8D' }}>
                  <span className="size-1.5 rounded-full animate-pulse" style={{ background: '#68DA8D', boxShadow: '0 0 8px #68DA8D' }} />
                  NEW · 30-DAY FREE TRIAL
                </div>
                <h3 className="text-2xl sm:text-3xl text-white mb-2 leading-tight" style={heading}>
                  Is your website <span style={{ color: '#D4AF37' }}>alive</span> right now?
                </h3>
                <p className="text-sm text-[#c9c9d1] leading-relaxed mb-1 max-w-xl">
                  AUREM Site Monitor pings your site every 15 min and emails you the moment it goes down.
                  No credit card. Setup takes 20 seconds.
                </p>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[#9ca3af] tracking-wider mt-3">
                  <div className="flex items-center gap-1.5"><Check className="size-3 text-[#4ade80]" /><span>3 URLs monitored</span></div>
                  <div className="flex items-center gap-1.5"><Check className="size-3 text-[#4ade80]" /><span>Instant email alerts</span></div>
                  <div className="flex items-center gap-1.5"><Check className="size-3 text-[#4ade80]" /><span>Live uptime dashboard</span></div>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.04, boxShadow: '0 0 40px rgba(212,175,55,0.35)' }}
                whileTap={{ scale: 0.97 }}
                onClick={() => navigate('/monitor-free')}
                className="px-7 py-3.5 rounded-lg text-sm font-bold flex items-center gap-3 tracking-wider text-[#050507] whitespace-nowrap"
                style={{ background: goldGrad }}
                data-testid="site-monitor-cta-btn"
              >
                Start Free Monitoring <ArrowRight className="size-4" />
              </motion.button>
              {/* iter 281.5 — Phase 2.5 Repair Lead Magnet */}
              <motion.button
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => navigate('/repair-quote')}
                className="ml-3 px-5 py-3.5 rounded-lg text-sm font-semibold tracking-wider text-[#D4AF37] border border-[#D4AF37]/40 hover:border-[#D4AF37] whitespace-nowrap"
                data-testid="repair-quote-cta-btn"
              >
                Free Site Audit →
              </motion.button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ═══ PROBLEM ═══ */}
      <section className="py-20 px-6 lg:px-8 perf-cv">
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <h2 className="text-3xl text-white mb-3" style={heading}>Running a business is exhausting.</h2>
          </motion.div>
          <motion.div variants={staggerScroll} initial="hidden" whileInView="visible" viewport={{ once: true }} className="grid md:grid-cols-3 gap-4">
            {painPoints.map((p, i) => (
              <motion.div key={i} variants={scaleUp} whileHover={{ y: -4, borderColor: 'rgba(239,68,68,0.15)' }}
                className="p-6 rounded-xl transition-all" style={glass} data-testid={`pain-${i}`}>
                <div className="size-10 rounded-lg flex items-center justify-center mb-4" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.1)' }}>
                  <p.icon className="size-5 text-[#EF4444]" />
                </div>
                <h3 className="text-sm font-bold text-white mb-2">{p.title}</h3>
                <p className="text-xs text-[#9ca3af] leading-relaxed">{p.body}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ SOLUTION / FEATURES ═══ */}
      <section id="features" className="py-20 px-6 lg:px-8 perf-cv" style={{ background: 'linear-gradient(180deg, rgba(212,175,55,0.015) 0%, transparent 100%)' }}>
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <p className="text-[#D4AF37] text-[10px] tracking-[0.3em] uppercase mb-3 font-bold">What AUREM Does</p>
            <h2 className="text-3xl text-white mb-3" style={heading} data-testid="features-title">AUREM works while you sleep.</h2>
          </motion.div>
          <motion.div variants={staggerScroll} initial="hidden" whileInView="visible" viewport={{ once: true }} className="grid md:grid-cols-3 gap-4">
            {capabilities.map((c, i) => (
              <motion.div key={i} variants={scaleUp} whileHover={{ y: -4, borderColor: 'rgba(212,175,55,0.2)' }}
                className="p-6 rounded-xl transition-all group" style={glass} data-testid={`feature-${i}`}>
                <div className="size-10 rounded-lg flex items-center justify-center mb-4" style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.1)' }}>
                  <c.icon className="size-5 text-[#D4AF37]" />
                </div>
                <h3 className="text-sm font-bold text-white mb-2 group-hover:text-[#D4AF37] transition-colors">{c.title}</h3>
                <p className="text-xs text-[#9ca3af] leading-relaxed">{c.body}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how" className="py-20 px-6 lg:px-8" style={{ background: '#080810' }}>
        <div className="max-w-4xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <p className="text-[#D4AF37] text-[10px] tracking-[0.3em] uppercase mb-3 font-bold">How It Works</p>
            <h2 className="text-3xl text-white mb-3" style={heading}>Five agents. One system.</h2>
            <p className="text-sm text-[#9ca3af] max-w-lg mx-auto">
              AUREM observes your business, decides the best action, and executes &mdash; without being asked.
            </p>
          </motion.div>
          <motion.div variants={staggerScroll} initial="hidden" whileInView="visible" viewport={{ once: true }} className="space-y-3">
            {agents.map((a, i) => (
              <motion.div key={i} variants={fadeUpScroll} whileHover={{ x: 6 }}
                className="flex items-center gap-5 p-5 rounded-xl transition-all" style={glass} data-testid={`agent-${i}`}>
                <span className="text-[10px] font-bold tracking-[0.2em]" style={{ color: a.color }}>{a.step}</span>
                <div className="size-10 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: `${a.color}10`, border: `1px solid ${a.color}20` }}>
                  <div className="size-2 rounded-full animate-pulse" style={{ background: a.color }} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">{a.name}</h3>
                  <p className="text-xs text-[#9ca3af]">{a.desc}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ WHO IT'S FOR ═══ */}
      <section id="about" className="py-20 px-6 lg:px-8 perf-cv">
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <p className="text-[#D4AF37] text-[10px] tracking-[0.3em] uppercase mb-3 font-bold">Who It's For</p>
            <h2 className="text-3xl text-white mb-3" style={heading}>Built for Canadian business owners.</h2>
          </motion.div>
          <motion.div variants={staggerScroll} initial="hidden" whileInView="visible" viewport={{ once: true }} className="grid md:grid-cols-3 gap-4">
            {personas.map((p, i) => (
              <motion.div key={i} variants={scaleUp} whileHover={{ y: -4, borderColor: 'rgba(212,175,55,0.2)' }}
                className="p-6 rounded-xl transition-all" style={glass} data-testid={`persona-${i}`}>
                <div className="size-10 rounded-lg flex items-center justify-center mb-4" style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.1)' }}>
                  <p.icon className="size-5 text-[#D4AF37]" />
                </div>
                <h3 className="text-sm font-bold text-white mb-2">{p.title}</h3>
                <p className="text-xs text-[#9ca3af] leading-relaxed">{p.body}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ TRUST ═══ */}
      <section className="py-20 px-6 lg:px-8 perf-cv" style={{ background: '#080810' }}>
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <h2 className="text-3xl text-white mb-3" style={heading}>Enterprise-grade. Small business price.</h2>
          </motion.div>
          <motion.div variants={staggerScroll} initial="hidden" whileInView="visible" viewport={{ once: true }}
            className="flex flex-wrap items-center justify-center gap-6 mb-10">
            {trustStats.map((s, i) => (
              <motion.div key={i} variants={scaleUp} className="text-center px-6 py-4 rounded-xl" style={glass} data-testid={`trust-${i}`}>
                <div className="text-2xl font-bold" style={{ color: '#D4AF37', ...heading }}>{s.value}</div>
                <div className="text-[10px] text-[#9ca3af] mt-1 tracking-wider">{s.label}</div>
              </motion.div>
            ))}
          </motion.div>
          <p className="text-center text-xs text-[#9ca3af] max-w-xl mx-auto leading-relaxed">
            Built on the same autonomous agent architecture used by enterprise systems costing 10x more.
            PIPEDA compliant. CASL compliant. Bank of Canada powered.
          </p>
        </div>
      </section>

      {/* ═══ PRICING ═══ */}
      <section id="pricing" className="py-20 px-6 lg:px-8 perf-cv">
        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <p className="text-[#D4AF37] text-[10px] tracking-[0.3em] uppercase mb-3 font-bold">Pricing</p>
            <h2 className="text-3xl text-white mb-3" style={heading} data-testid="pricing-title">Simple pricing. No surprises.</h2>
            <p className="text-sm text-[#9ca3af]">Cancel anytime. No setup fees.</p>
          </motion.div>
          <motion.div variants={staggerScroll} initial="hidden" whileInView="visible" viewport={{ once: true }} className="grid md:grid-cols-3 gap-4">
            {pricingPlans.map((plan, i) => (
              <motion.div key={i} variants={scaleUp} whileHover={{ y: -5, borderColor: plan.highlight ? 'rgba(212,175,55,0.5)' : 'rgba(255,255,255,0.1)' }}
                className="p-7 rounded-xl transition-all relative overflow-hidden"
                style={{
                  ...(plan.highlight
                    ? { background: 'linear-gradient(135deg, rgba(212,175,55,0.07), rgba(5,5,7,0.95))', border: '1px solid rgba(212,175,55,0.3)' }
                    : glass),
                }}
                data-testid={`pricing-${plan.name.toLowerCase()}`}>
                {plan.highlight && <div className="absolute top-0 left-0 right-0 h-px" style={{ background: 'linear-gradient(90deg, transparent, #D4AF37, transparent)' }} />}
                {plan.badge && (
                  <div className="text-center mb-4">
                    <span className="px-3 py-1 rounded-full text-[8px] tracking-[0.2em] uppercase font-bold text-[#050507]" style={{ background: goldGrad }}>
                      {plan.badge}
                    </span>
                  </div>
                )}
                <h3 className="text-lg text-white mb-1" style={heading}>{plan.name}</h3>
                <p className="text-[11px] text-[#9ca3af] mb-4">{plan.sub}</p>
                <div className="flex items-baseline gap-1 mb-5">
                  <span className="text-3xl text-white" style={heading}>${plan.price}</span>
                  <span className="text-[#9ca3af] text-xs">CAD/month</span>
                </div>
                <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={() => plan.cta === 'Contact Sales' ? window.location.href = 'mailto:Pawandeep19may1985@gmail.com' : navigate('/platform/signup')}
                  className={`w-full py-3 rounded-lg text-xs font-bold tracking-wider mb-5 transition-all ${plan.highlight ? 'text-[#050507]' : 'text-[#D4AF37] hover:text-white'}`}
                  style={plan.highlight ? { background: goldGrad } : { background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.15)' }}
                  data-testid={`pricing-cta-${plan.name.toLowerCase()}`}>
                  {plan.cta}
                </motion.button>
                <div className="space-y-2.5">
                  {plan.features.map((f, fi) => (
                    <div key={fi} className="flex items-start gap-2 text-xs">
                      <Check className="size-3.5 text-[#4ade80] flex-shrink-0 mt-0.5" />
                      <span className="text-[#9ca3af]">{f}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══ FAQ ═══ */}
      <section id="faq" className="py-20 px-6 lg:px-8 perf-cv" style={{ background: '#080810' }}>
        <div className="max-w-2xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
            <h2 className="text-3xl text-white mb-3" style={heading} data-testid="faq-title">Frequently asked questions</h2>
          </motion.div>
          <div className="space-y-2">
            {faqs.map((faq, i) => (
              <div key={i} className="rounded-xl overflow-hidden transition-all" style={glass} data-testid={`faq-${i}`}>
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  aria-label={`Toggle FAQ: ${faq.q}`}
                  aria-expanded={openFaq === i}
                  className="w-full flex items-center justify-between p-5 text-left"
                >
                  <span className="text-sm text-white font-medium pr-4">{faq.q}</span>
                  <ChevronDown className={`size-4 text-[#D4AF37] flex-shrink-0 transition-transform ${openFaq === i ? 'rotate-180' : ''}`} />
                </button>
                {openFaq === i && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} className="px-5 pb-5">
                    <p className="text-xs text-[#9ca3af] leading-relaxed">{faq.a}</p>
                  </motion.div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-20 px-6 lg:px-8 perf-cv">
        <div className="max-w-3xl mx-auto">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}
            className="p-12 rounded-2xl text-center relative overflow-hidden" style={{ ...glass, borderColor: 'rgba(212,175,55,0.15)' }}>
            <div className="absolute inset-0">
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 size-72 rounded-full blur-[150px]" style={{ background: 'rgba(212,175,55,0.06)' }} />
            </div>
            <div className="relative">
              <h2 className="text-3xl text-white mb-3" style={heading}>
                Ready to stop doing everything yourself?
              </h2>
              <p className="text-sm text-[#9ca3af] mb-8 max-w-md mx-auto">
                Start your free trial today. No credit card required. See what AUREM handles for you in the first 24 hours.
              </p>
              <motion.button whileHover={{ scale: 1.04, boxShadow: '0 0 50px rgba(212,175,55,0.3)' }} whileTap={{ scale: 0.96 }}
                onClick={() => navigate('/platform/signup')}
                className="px-8 py-3.5 rounded-lg text-sm font-bold inline-flex items-center gap-3 tracking-wider text-[#050507]"
                style={{ background: goldGrad }} data-testid="cta-final-btn">
                Start Free Trial <ArrowRight className="size-4" />
              </motion.button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer role="contentinfo" aria-label="Site footer" className="py-10 px-6 lg:px-8 border-t border-white/5">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="size-7 rounded-md flex items-center justify-center" style={{ background: goldGrad }}>
                <Target className="size-3.5 text-[#050507]" />
              </div>
              <div>
                <span className="text-xs tracking-[0.2em]" style={heading}>AUREM</span>
                <span className="text-[#D4AF37] text-[8px] ml-1.5 tracking-[0.15em]">AI Platform</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-5 text-[10px] text-[#9ca3af] tracking-wider">
              <a href="/terms" className="hover:text-[#D4AF37] transition-colors" data-testid="footer-terms-link">Terms</a>
              <a href="/privacy" className="hover:text-[#D4AF37] transition-colors" data-testid="footer-privacy-link">Privacy</a>
              <a href="/refund" className="hover:text-[#D4AF37] transition-colors" data-testid="footer-refund-link">Refund</a>
              <a href="/contact" className="hover:text-[#D4AF37] transition-colors" data-testid="footer-contact-link">Contact</a>
              <a href="/legal/acceptable-use" className="hover:text-[#D4AF37] transition-colors" data-testid="footer-aup-link">Acceptable Use</a>
              <a href="/legal/cookies" className="hover:text-[#D4AF37] transition-colors" data-testid="footer-cookies-link">Cookies</a>
            </div>
          </div>
          <div className="mt-6 flex flex-col md:flex-row items-center justify-between gap-3">
            <span className="text-[10px] text-[#444]">Trusted by Canadian businesses.</span>
            <span className="text-[10px] text-[#333]" data-testid="footer-copyright">&copy; 2026 Polaris Built Inc. Mississauga, Ontario, Canada. All rights reserved.</span>
          </div>
        </div>
      </footer>
      <LiveChatWidget />
      <SevenDayTrialPromo />
    </div>
  );
};

export default PlatformLanding;
