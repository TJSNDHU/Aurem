/**
 * AUREM - Authentication Pages
 * Company: Polaris Built Inc.
 * Theme: "Obsidian Executive" with Framer Motion
 */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Target, Mail, Lock, Building, User, ArrowRight, Loader2, Eye, EyeOff, Shield, Radio } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Login Page
export const PlatformLogin = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API_URL}/api/platform/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      const data = await res.json();

      if (res.ok) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        navigate('/dashboard');
      } else {
        setError(data.detail || 'Authentication failed');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#050505] flex" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#0A0A0A] to-[#050505] border-r border-[#151515] flex-col justify-between p-12 relative overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: 'linear-gradient(#D4AF37 1px, transparent 1px), linear-gradient(90deg, #D4AF37 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}></div>
        </div>

        <div className="relative">
          <Link to="/platform" className="inline-flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
                <Target className="w-5 h-5 text-[#050505]" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-[#009874] rounded-full animate-pulse"></div>
            </div>
            <div>
              <span className="text-lg tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>POLARIS BUILT</span>
              <span className="text-[#D4AF37] text-xs ml-2">AUREM</span>
            </div>
          </Link>
        </div>
        
        <div className="relative">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-4xl text-[#F4F4F4] mb-4 leading-tight" 
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Access Your<br />
            <span className="text-[#D4AF37]">Command Center</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-[#555] leading-relaxed max-w-md"
          >
            Monitor your AI swarms. Track acquisitions. 
            Watch AUREM hunt, qualify, and close—autonomously.
          </motion.p>
        </div>

        <div className="relative flex items-center gap-2 text-[#333]">
          <Shield className="w-4 h-4 text-[#009874]" />
          <span className="text-xs tracking-wide">Enterprise-grade security. SOC 2 compliant.</span>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="w-full max-w-md"
        >
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-8">
            <Link to="/platform" className="inline-flex items-center gap-3">
              <div className="w-10 h-10 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
                <Target className="w-5 h-5 text-[#050505]" />
              </div>
              <span className="text-lg tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM</span>
            </Link>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-2xl text-[#F4F4F4] mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>Sign In</h2>
            <p className="text-sm text-[#444]">Access AUREM Command Center</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}

            <div>
              <label className="block text-xs text-[#444] tracking-[0.15em] uppercase mb-2">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#333]" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@company.com"
                  required
                  className="w-full pl-12 pr-4 py-3.5 bg-[#0A0A0A] border border-[#151515] rounded text-[#F4F4F4] placeholder-[#333] focus:border-[#D4AF37]/50 focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#444] tracking-[0.15em] uppercase mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#333]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="w-full pl-12 pr-12 py-3.5 bg-[#0A0A0A] border border-[#151515] rounded text-[#F4F4F4] placeholder-[#333] focus:border-[#D4AF37]/50 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#333] hover:text-[#555] transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded font-medium flex items-center justify-center gap-2 disabled:opacity-50 transition-all tracking-wide"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  Access Command Center
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </motion.button>

            <p className="text-center text-sm text-[#444]">
              New operator?{' '}
              <Link to="/platform/signup" className="text-[#D4AF37] hover:text-[#F7E7CE] transition-colors">
                Request access
              </Link>
            </p>
          </form>
        </motion.div>
      </div>
    </div>
  );
};

// Signup Page
export const PlatformSignup = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    company_name: '',
    full_name: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/platform/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await res.json();

      if (res.ok) {
        localStorage.setItem('platform_token', data.token);
        localStorage.setItem('platform_user', JSON.stringify(data));
        navigate('/dashboard');
      } else {
        setError(data.detail || 'Registration failed');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#050505] flex" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#0A0A0A] to-[#050505] border-r border-[#151515] flex-col justify-between p-12 relative overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: 'linear-gradient(#D4AF37 1px, transparent 1px), linear-gradient(90deg, #D4AF37 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}></div>
        </div>

        <div className="relative">
          <Link to="/platform" className="inline-flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
                <Target className="w-5 h-5 text-[#050505]" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-[#009874] rounded-full animate-pulse"></div>
            </div>
            <div>
              <span className="text-lg tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>POLARIS BUILT</span>
              <span className="text-[#D4AF37] text-xs ml-2">AUREM</span>
            </div>
          </Link>
        </div>
        
        <div className="relative">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-4xl text-[#F4F4F4] mb-4 leading-tight" 
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Deploy Your<br />
            <span className="text-[#D4AF37]">AI Swarm</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-[#555] leading-relaxed max-w-md mb-8"
          >
            AUREM Vanguard hunts, qualifies, and closes leads autonomously.
            14-day evaluation. Full swarm capabilities.
          </motion.p>
          
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="space-y-3"
          >
            {[
              '4 Elite AI Agents (Scout, Architect, Envoy, Closer)',
              'OODA-based decision framework',
              'Voice, WhatsApp, Email channels',
              'Real-time swarm monitoring'
            ].map((feature, i) => (
              <div key={i} className="flex items-center gap-3 text-sm text-[#666]">
                <div className="w-1.5 h-1.5 rounded-full bg-[#D4AF37]"></div>
                {feature}
              </div>
            ))}
          </motion.div>
        </div>

        <div className="relative flex items-center gap-2 text-[#333]">
          <Shield className="w-4 h-4 text-[#009874]" />
          <span className="text-xs tracking-wide">Enterprise-grade security. SOC 2 compliant.</span>
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="w-full max-w-md"
        >
          <div className="lg:hidden text-center mb-8">
            <Link to="/platform" className="inline-flex items-center gap-3">
              <div className="w-10 h-10 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
                <Target className="w-5 h-5 text-[#050505]" />
              </div>
              <span className="text-lg tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM</span>
            </Link>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-2xl text-[#F4F4F4] mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>Deploy AUREM</h2>
            <p className="text-sm text-[#444]">Initialize your autonomous AI swarm</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm"
              >
                {error}
              </motion.div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-[#444] tracking-[0.15em] uppercase mb-2">Operator Name</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#333]" />
                  <input
                    type="text"
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="John Smith"
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-[#0A0A0A] border border-[#151515] rounded text-[#F4F4F4] placeholder-[#333] focus:border-[#D4AF37]/50 focus:outline-none transition-colors text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs text-[#444] tracking-[0.15em] uppercase mb-2">Organization</label>
                <div className="relative">
                  <Building className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#333]" />
                  <input
                    type="text"
                    name="company_name"
                    value={formData.company_name}
                    onChange={handleChange}
                    placeholder="Acme Inc."
                    required
                    className="w-full pl-12 pr-4 py-3.5 bg-[#0A0A0A] border border-[#151515] rounded text-[#F4F4F4] placeholder-[#333] focus:border-[#D4AF37]/50 focus:outline-none transition-colors text-sm"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#444] tracking-[0.15em] uppercase mb-2">Work Email</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#333]" />
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="operator@company.com"
                  required
                  className="w-full pl-12 pr-4 py-3.5 bg-[#0A0A0A] border border-[#151515] rounded text-[#F4F4F4] placeholder-[#333] focus:border-[#D4AF37]/50 focus:outline-none transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#444] tracking-[0.15em] uppercase mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#333]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Min. 8 characters"
                  required
                  minLength={8}
                  className="w-full pl-12 pr-12 py-3.5 bg-[#0A0A0A] border border-[#151515] rounded text-[#F4F4F4] placeholder-[#333] focus:border-[#D4AF37]/50 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-[#333] hover:text-[#555] transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02, boxShadow: '0 0 30px rgba(212, 175, 55, 0.2)' }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] text-[#050505] rounded font-medium flex items-center justify-center gap-2 disabled:opacity-50 transition-all tracking-wide"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  Initialize Swarm
                  <Radio className="w-4 h-4" />
                </>
              )}
            </motion.button>

            <p className="text-center text-xs text-[#333]">
              By deploying, you agree to our Terms of Service.
            </p>

            <p className="text-center text-sm text-[#444]">
              Existing operator?{' '}
              <Link to="/platform/login" className="text-[#D4AF37] hover:text-[#F7E7CE] transition-colors">
                Access Command Center
              </Link>
            </p>
          </form>
        </motion.div>
      </div>
    </div>
  );
};

export default PlatformLogin;
