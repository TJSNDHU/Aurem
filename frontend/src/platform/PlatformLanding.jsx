/**
 * AUREM - Autonomous AI Workforce
 * Company: Polaris Built Inc.
 * Theme: "Obsidian Executive" with Framer Motion
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Phone, MessageSquare, Mail, Globe, Users, ChevronRight, Check,
  Play, ArrowRight, TrendingUp, Clock, Shield, Award,
  BarChart3, Zap, Brain, Target, Eye, Radio, Crosshair
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Animation variants for "heavy, weighted" feel
const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.8, ease: [0.25, 0.46, 0.45, 0.94] }
  }
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.15, delayChildren: 0.2 }
  }
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: { 
    opacity: 1, 
    scale: 1,
    transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }
  }
};

const PlatformLanding = () => {
  const navigate = useNavigate();
  const [tiers, setTiers] = useState({});
  const [billingCycle, setBillingCycle] = useState('monthly');
  const [auremData, setAuremData] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [tiersRes, auremRes] = await Promise.all([
        fetch(`${API_URL}/api/platform/tiers`),
        fetch(`${API_URL}/api/aurem/system`)
      ]);
      if (tiersRes.ok) setTiers((await tiersRes.json()).tiers || {});
      if (auremRes.ok) setAuremData(await auremRes.json());
    } catch (err) {
      console.error('Failed to fetch data');
    }
  };

  const vanguardAgents = [
    { id: 'scout', name: 'The Scout', role: 'OBSERVE', icon: Eye, desc: 'Scrapes LinkedIn, Google Maps, News for triggers', color: '#D4AF37' },
    { id: 'architect', name: 'The Architect', role: 'ORIENT', icon: Brain, desc: 'Analyzes data to find the perfect hook', color: '#009874' },
    { id: 'envoy', name: 'The Envoy', role: 'DECIDE', icon: Radio, desc: 'Chooses optimal channel, crafts message', color: '#D4AF37' },
    { id: 'closer', name: 'The Closer', role: 'ACT', icon: Crosshair, desc: 'Executes outreach, books meetings', color: '#009874' }
  ];

  const stats = [
    { value: '$7.84B', label: 'Market Opportunity', sub: '2026' },
    { value: '46%', label: 'Annual Growth', sub: 'CAGR' },
    { value: '340%', label: 'Lead Conversion', sub: 'Improvement' },
    { value: '24/7', label: 'Autonomous', sub: 'Operation' }
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-[#F4F4F4]" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Navigation */}
      <motion.nav 
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="fixed top-0 left-0 right-0 z-50 bg-[#050505]/90 backdrop-blur-xl border-b border-[#D4AF37]/10"
      >
        <div className="max-w-7xl mx-auto px-8 py-5 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-10 h-10 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
                <Target className="w-5 h-5 text-[#050505]" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-[#009874] rounded-full animate-pulse"></div>
            </div>
            <div>
              <span className="text-lg tracking-[0.2em] font-light" style={{ fontFamily: "'Playfair Display', serif" }}>POLARIS BUILT</span>
              <span className="text-[#D4AF37] text-xs ml-2 tracking-widest">AUREM</span>
            </div>
          </div>
          <div className="flex items-center gap-8">
            <a href="#vanguard" className="text-sm text-[#666] hover:text-[#D4AF37] transition-colors tracking-wide">Vanguard</a>
            <a href="#ooda" className="text-sm text-[#666] hover:text-[#D4AF37] transition-colors tracking-wide">OODA</a>
            <a href="#pricing" className="text-sm text-[#666] hover:text-[#D4AF37] transition-colors tracking-wide">Investment</a>
            <button 
              onClick={() => navigate('/platform/login')}
              className="text-sm text-[#D4AF37] hover:text-[#F7E7CE] transition-colors tracking-wide"
            >
              Command Center
            </button>
            <motion.button 
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate('/auth')}
              className="px-6 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded text-sm font-medium tracking-wide"
            >
              Deploy AUREM
            </motion.button>
          </div>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className="pt-40 pb-24 px-8 relative overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: 'linear-gradient(#D4AF37 1px, transparent 1px), linear-gradient(90deg, #D4AF37 1px, transparent 1px)',
            backgroundSize: '60px 60px'
          }}></div>
        </div>

        <div className="max-w-7xl mx-auto relative">
          <motion.div 
            variants={staggerContainer}
            initial="hidden"
            animate="visible"
            className="grid lg:grid-cols-2 gap-16 items-center"
          >
            <div>
              <motion.div variants={fadeInUp} className="inline-flex items-center gap-2 px-4 py-2 bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded text-sm text-[#D4AF37] mb-8">
                <Radio className="w-4 h-4 animate-pulse" />
                AUREM v1.0 • Autonomous AI Workforce
              </motion.div>
              
              <motion.h1 
                variants={fadeInUp}
                className="text-5xl lg:text-6xl mb-8 leading-tight tracking-tight" 
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                Hunt. Qualify.<br />
                <span className="text-[#D4AF37]">Close.</span><br />
                <span className="text-[#009874]">Autonomously.</span>
              </motion.h1>
              
              <motion.p variants={fadeInUp} className="text-lg text-[#666] max-w-lg mb-10 leading-relaxed">
                AUREM Vanguard is your elite AI swarm. Four autonomous agents working in perfect 
                OODA synchronization to acquire, qualify, and close leads—while you sleep.
              </motion.p>
              
              <motion.div variants={fadeInUp} className="flex items-center gap-4">
                <motion.button 
                  whileHover={{ scale: 1.03, boxShadow: '0 0 30px rgba(212, 175, 55, 0.3)' }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/platform/signup')}
                  className="px-8 py-4 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded text-sm font-semibold flex items-center gap-3 tracking-wide"
                >
                  Initialize Vanguard
                  <ArrowRight className="w-4 h-4" />
                </motion.button>
                <motion.button 
                  whileHover={{ borderColor: 'rgba(212, 175, 55, 0.5)' }}
                  className="px-8 py-4 border border-[#222] text-[#666] rounded text-sm font-medium flex items-center gap-2 hover:text-[#D4AF37] transition-all tracking-wide"
                >
                  <Play className="w-4 h-4" />
                  Watch Swarm
                </motion.button>
              </motion.div>
            </div>

            {/* Stats Cards */}
            <motion.div 
              variants={staggerContainer}
              className="grid grid-cols-2 gap-4"
            >
              {stats.map((stat, i) => (
                <motion.div 
                  key={i}
                  variants={scaleIn}
                  whileHover={{ borderColor: 'rgba(212, 175, 55, 0.4)', y: -2 }}
                  className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515] transition-all"
                >
                  <div className="text-3xl font-light text-[#F4F4F4] mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
                    {stat.value}
                  </div>
                  <div className="text-sm text-[#666]">{stat.label}</div>
                  <div className="text-xs text-[#D4AF37]/60 mt-1">{stat.sub}</div>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Vanguard Agents Section */}
      <section id="vanguard" className="py-24 px-8 bg-gradient-to-b from-[#050505] to-[#0A0A0A]">
        <div className="max-w-7xl mx-auto">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <p className="text-[#D4AF37] text-xs tracking-[0.3em] uppercase mb-4">The Swarm</p>
            <h2 className="text-4xl mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
              AUREM Vanguard Agents
            </h2>
            <p className="text-[#666] max-w-2xl mx-auto">
              Four elite AI agents, each mastering one phase of the OODA loop. 
              Together, they form an unstoppable acquisition swarm.
            </p>
          </motion.div>

          <motion.div 
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="grid md:grid-cols-4 gap-4"
          >
            {vanguardAgents.map((agent, i) => (
              <motion.div
                key={agent.id}
                variants={scaleIn}
                whileHover={{ y: -8, borderColor: agent.color }}
                className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515] transition-all group relative overflow-hidden"
              >
                {/* Glow effect */}
                <div 
                  className="absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity"
                  style={{ background: `radial-gradient(circle at center, ${agent.color}, transparent 70%)` }}
                ></div>
                
                <div className="relative">
                  <div className="flex items-center justify-between mb-4">
                    <div 
                      className="w-12 h-12 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${agent.color}15`, border: `1px solid ${agent.color}30` }}
                    >
                      <agent.icon className="w-5 h-5" style={{ color: agent.color }} />
                    </div>
                    <span className="text-[10px] tracking-[0.2em]" style={{ color: agent.color }}>{agent.role}</span>
                  </div>
                  
                  <h3 className="text-lg mb-2 group-hover:text-[#D4AF37] transition-colors" style={{ fontFamily: "'Playfair Display', serif" }}>
                    {agent.name}
                  </h3>
                  <p className="text-xs text-[#555] leading-relaxed">{agent.desc}</p>
                  
                  <div className="mt-4 pt-4 border-t border-[#151515]">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: agent.color }}></div>
                      <span className="text-[10px] text-[#444]">Agent Online</span>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* OODA Loop Section */}
      <section id="ooda" className="py-24 px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div 
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <p className="text-[#D4AF37] text-xs tracking-[0.3em] uppercase mb-4">Methodology</p>
            <h2 className="text-4xl mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
              The OODA Protocol
            </h2>
            <p className="text-[#666] max-w-2xl mx-auto">
              Military-grade decision framework. Now weaponized for business acquisition.
            </p>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="relative max-w-3xl mx-auto"
          >
            {/* OODA Circle */}
            <div className="aspect-square relative">
              {/* Outer rings */}
              <div className="absolute inset-0 rounded-full border border-[#151515]"></div>
              <div className="absolute inset-[15%] rounded-full border border-[#151515]"></div>
              <div className="absolute inset-[30%] rounded-full border border-[#D4AF37]/20"></div>
              <div className="absolute inset-[45%] rounded-full bg-[#D4AF37]/5 border border-[#D4AF37]/30"></div>
              
              {/* Center pulse */}
              <motion.div 
                animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <div className="w-8 h-8 rounded-full bg-[#D4AF37]"></div>
              </motion.div>
              
              {/* OODA Labels */}
              {[
                { label: 'OBSERVE', angle: -90, agent: 'Scout', color: '#D4AF37' },
                { label: 'ORIENT', angle: 0, agent: 'Architect', color: '#009874' },
                { label: 'DECIDE', angle: 90, agent: 'Envoy', color: '#D4AF37' },
                { label: 'ACT', angle: 180, agent: 'Closer', color: '#009874' }
              ].map((item, i) => {
                const rad = (item.angle * Math.PI) / 180;
                const x = 50 + 45 * Math.cos(rad);
                const y = 50 + 45 * Math.sin(rad);
                return (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.2 }}
                    className="absolute text-center"
                    style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}
                  >
                    <div className="text-xs tracking-[0.2em] mb-1" style={{ color: item.color }}>{item.label}</div>
                    <div className="text-[10px] text-[#444]">{item.agent}</div>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-8 bg-gradient-to-b from-[#0A0A0A] to-[#050505]">
        <div className="max-w-7xl mx-auto">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <p className="text-[#D4AF37] text-xs tracking-[0.3em] uppercase mb-4">Investment</p>
            <h2 className="text-4xl mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
              Deploy Your Swarm
            </h2>
            <p className="text-[#666] mb-8">14-day evaluation. Full capabilities. No commitment.</p>
            
            <div className="inline-flex items-center bg-[#0A0A0A] border border-[#151515] rounded p-1">
              <button
                onClick={() => setBillingCycle('monthly')}
                className={`px-6 py-2 rounded text-sm tracking-wide transition-all ${
                  billingCycle === 'monthly' ? 'bg-[#D4AF37] text-[#050505]' : 'text-[#555]'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingCycle('yearly')}
                className={`px-6 py-2 rounded text-sm tracking-wide transition-all ${
                  billingCycle === 'yearly' ? 'bg-[#D4AF37] text-[#050505]' : 'text-[#555]'
                }`}
              >
                Annual (Save 17%)
              </button>
            </div>
          </motion.div>

          <motion.div 
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="grid md:grid-cols-3 gap-6"
          >
            {Object.entries(tiers).map(([id, tier], i) => (
              <motion.div 
                key={id}
                variants={scaleIn}
                whileHover={{ y: -4, borderColor: i === 2 ? '#D4AF37' : '#222' }}
                className={`p-8 rounded-lg border transition-all ${
                  i === 2 
                    ? 'bg-gradient-to-b from-[#D4AF37]/10 to-[#0A0A0A] border-[#D4AF37]/40' 
                    : 'bg-[#0A0A0A] border-[#151515]'
                }`}
              >
                {i === 2 && (
                  <div className="text-center mb-4">
                    <span className="px-3 py-1 bg-[#D4AF37] text-[#050505] text-[10px] tracking-[0.2em] uppercase">
                      Recommended
                    </span>
                  </div>
                )}
                <h3 className="text-xl mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>{tier.name}</h3>
                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-4xl" style={{ fontFamily: "'Playfair Display', serif" }}>
                    ${billingCycle === 'yearly' ? Math.round(tier.price_yearly / 12) : tier.price_monthly}
                  </span>
                  <span className="text-[#444] text-sm">/month</span>
                </div>
                <p className="text-sm text-[#444] mb-6">{tier.description}</p>
                
                <motion.button 
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => navigate('/auth')}
                  className={`w-full py-3 rounded text-sm font-medium tracking-wide mb-6 transition-all ${
                    i === 2 
                      ? 'bg-[#D4AF37] text-[#050505]' 
                      : 'bg-[#151515] text-[#666] hover:bg-[#1A1A1A]'
                  }`}
                >
                  Deploy Now
                </motion.button>

                <div className="space-y-3">
                  <div className="text-sm text-[#555]">
                    <span className="text-[#F4F4F4]">{tier.crew_executions?.toLocaleString()}</span> swarm missions
                  </div>
                  {tier.features?.slice(0, 5).map((feature, fi) => (
                    <div key={fi} className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-[#009874]" />
                      <span className="text-[#555]">{feature}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-8">
        <div className="max-w-4xl mx-auto">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="p-16 bg-gradient-to-r from-[#0A0A0A] to-[#0F0F0F] rounded-lg border border-[#D4AF37]/20 text-center relative overflow-hidden"
          >
            {/* Background glow */}
            <div className="absolute inset-0 opacity-20">
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-[#D4AF37] rounded-full blur-[150px]"></div>
            </div>
            
            <div className="relative">
              <h2 className="text-4xl mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
                Ready to Unleash AUREM?
              </h2>
              <p className="text-[#666] mb-8 max-w-lg mx-auto">
                Join the enterprises already deploying autonomous AI swarms. 
                Begin your 14-day evaluation today.
              </p>
              <motion.button 
                whileHover={{ scale: 1.05, boxShadow: '0 0 40px rgba(212, 175, 55, 0.4)' }}
                whileTap={{ scale: 0.95 }}
                onClick={() => navigate('/auth')}
                className="px-10 py-4 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded text-sm font-semibold inline-flex items-center gap-3 tracking-wide"
              >
                Initialize Vanguard Swarm
                <ArrowRight className="w-4 h-4" />
              </motion.button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-8 border-t border-[#151515]">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
              <Target className="w-4 h-4 text-[#050505]" />
            </div>
            <div>
              <span className="text-sm tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>POLARIS BUILT</span>
              <span className="text-[#D4AF37] text-xs ml-2">Inc.</span>
            </div>
          </div>
          <div className="flex items-center gap-8 text-xs text-[#444]">
            <a href="#" className="hover:text-[#D4AF37]">Privacy</a>
            <a href="#" className="hover:text-[#D4AF37]">Terms</a>
            <a href="#" className="hover:text-[#D4AF37]">Security</a>
          </div>
          <div className="text-xs text-[#333]">
            © 2026 Polaris Built Inc. AUREM Engine.
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PlatformLanding;
