import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import axios from "axios";
import { ChevronLeft, Mail, Lock, User, Phone, Eye, EyeOff, Sparkles } from "lucide-react";
import "../styles/lavela-design-system.css";

// Get backend URL from environment
const getBackendUrl = () => {
  return process.env.REACT_APP_BACKEND_URL || window.location.origin;
};

const API = `${getBackendUrl()}/api`;

const LaVelaAuthPage = () => {
  const navigate = useNavigate();
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Force scroll to work
  useEffect(() => {
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    document.documentElement.style.overflow = 'auto';
    document.documentElement.style.height = 'auto';
    return () => {
      document.body.style.overflow = '';
      document.body.style.height = '';
      document.documentElement.style.overflow = '';
      document.documentElement.style.height = '';
    };
  }, []);
  
  // Form state
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: ""
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isLogin) {
        // Login
        const res = await axios.post(`${API}/lavela/auth/login`, {
          email: formData.email,
          password: formData.password
        });
        
        localStorage.setItem("lavela_token", res.data.token);
        localStorage.setItem("lavela_user", JSON.stringify(res.data.user));
        toast.success("Welcome back! ✨");
        navigate("/la-vela-bianca");
      } else {
        // Signup
        if (formData.password !== formData.confirmPassword) {
          toast.error("Passwords don't match");
          setLoading(false);
          return;
        }
        
        if (formData.password.length < 6) {
          toast.error("Password must be at least 6 characters");
          setLoading(false);
          return;
        }
        
        const res = await axios.post(`${API}/lavela/auth/signup`, {
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          password: formData.password
        });
        
        localStorage.setItem("lavela_token", res.data.token);
        localStorage.setItem("lavela_user", JSON.stringify(res.data.user));
        toast.success("Welcome to LA VELA BIANCA! 🌟");
        navigate("/la-vela-bianca");
      }
    } catch (error) {
      const message = error.response?.data?.detail || "Something went wrong";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen lavela-body overflow-y-auto" style={{
      background: 'linear-gradient(180deg, #0D4D4D 0%, #1A6B6B 25%, #D4A090 65%, #E8C4B8 100%)'
    }}>
      {/* Navigation - White Header */}
      <nav className="bg-white px-4 sm:px-6 py-2 border-b border-[#E6BE8A]/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Back Button - LEFT */}
          <button 
            onClick={() => navigate('/la-vela-bianca')}
            className="flex items-center gap-2 text-[#2D2A2E] hover:text-[#D4A574] transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
            <span className="text-sm">Back</span>
          </button>
          
          {/* Logo - CENTER */}
          <img 
            src="/lavela-header-logo.png" 
            alt="LA VELA BIANCA" 
            className="h-7 sm:h-8 absolute left-1/2 transform -translate-x-1/2"
          />
          
          {/* Empty div for spacing - RIGHT */}
          <div className="w-16"></div>
        </div>
      </nav>

      {/* Auth Form */}
      <section className="py-12 px-4">
        <div className="max-w-md mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Header */}
            <div className="text-center mb-8">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-[#E6BE8A] text-sm mb-4" style={{
                background: 'rgba(230, 190, 138, 0.15)',
                border: '1px solid rgba(230, 190, 138, 0.3)'
              }}>
                <Sparkles className="w-4 h-4" />
                {isLogin ? "Welcome Back" : "Join the Glow"}
              </div>
              
              <h1 className="lavela-heading text-3xl sm:text-4xl mb-2">
                {isLogin ? "Sign In" : "Create Account"}
              </h1>
              <p className="text-[#E8C4B8]">
                {isLogin 
                  ? "Access your LA VELA BIANCA account" 
                  : "Join 10,000+ members in the Glow Club"
                }
              </p>
            </div>

            {/* Form Card */}
            <div className="p-6 sm:p-8 rounded-3xl" style={{
              background: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(230, 190, 138, 0.3)'
            }}>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Name - Only for signup */}
                {!isLogin && (
                  <div>
                    <label className="block text-sm text-[#2D2A2E] mb-1 font-medium">Full Name</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#D4A574]" />
                      <input
                        type="text"
                        name="name"
                        value={formData.name}
                        onChange={handleChange}
                        placeholder="Your name"
                        className="w-full pl-10 pr-4 py-3 border border-[#E6BE8A]/30 rounded-xl focus:border-[#D4A574] focus:outline-none text-[#2D2A2E]"
                        required={!isLogin}
                        data-testid="lavela-auth-name"
                      />
                    </div>
                  </div>
                )}

                {/* Email */}
                <div>
                  <label className="block text-sm text-[#2D2A2E] mb-1 font-medium">Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#D4A574]" />
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleChange}
                      placeholder="your@email.com"
                      className="w-full pl-10 pr-4 py-3 border border-[#E6BE8A]/30 rounded-xl focus:border-[#D4A574] focus:outline-none text-[#2D2A2E]"
                      required
                      data-testid="lavela-auth-email"
                    />
                  </div>
                </div>

                {/* Phone - Only for signup */}
                {!isLogin && (
                  <div>
                    <label className="block text-sm text-[#2D2A2E] mb-1 font-medium">
                      Phone Number <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#D4A574]" />
                      <input
                        type="tel"
                        name="phone"
                        value={formData.phone}
                        onChange={handleChange}
                        placeholder="+1 (555) 123-4567"
                        required
                        className="w-full pl-10 pr-4 py-3 border border-[#E6BE8A]/30 rounded-xl focus:border-[#D4A574] focus:outline-none text-[#2D2A2E]"
                        data-testid="lavela-auth-phone"
                      />
                    </div>
                    <p className="text-xs text-[#5D6D7E] mt-1">Required for order updates & delivery notifications</p>
                  </div>
                )}

                {/* Password */}
                <div>
                  <label className="block text-sm text-[#2D2A2E] mb-1 font-medium">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#D4A574]" />
                    <input
                      type={showPassword ? "text" : "password"}
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      placeholder="••••••••"
                      className="w-full pl-10 pr-12 py-3 border border-[#E6BE8A]/30 rounded-xl focus:border-[#D4A574] focus:outline-none text-[#2D2A2E]"
                      required
                      minLength={6}
                      data-testid="lavela-auth-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[#5D6D7E] hover:text-[#D4A574]"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Confirm Password - Only for signup */}
                {!isLogin && (
                  <div>
                    <label className="block text-sm text-[#2D2A2E] mb-1 font-medium">Confirm Password</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#D4A574]" />
                      <input
                        type={showPassword ? "text" : "password"}
                        name="confirmPassword"
                        value={formData.confirmPassword}
                        onChange={handleChange}
                        placeholder="••••••••"
                        className="w-full pl-10 pr-4 py-3 border border-[#E6BE8A]/30 rounded-xl focus:border-[#D4A574] focus:outline-none text-[#2D2A2E]"
                        required={!isLogin}
                        data-testid="lavela-auth-confirm-password"
                      />
                    </div>
                  </div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="lavela-btn-shimmer w-full py-4 mt-4"
                  data-testid="lavela-auth-submit"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                      {isLogin ? "Signing in..." : "Creating account..."}
                    </span>
                  ) : (
                    isLogin ? "Sign In" : "Create Account"
                  )}
                </button>

                {/* Toggle Login/Signup */}
                <div className="text-center pt-4 border-t border-[#E6BE8A]/20 mt-4">
                  <p className="text-sm text-[#5D6D7E]">
                    {isLogin ? "Don't have an account?" : "Already have an account?"}
                    <button
                      type="button"
                      onClick={() => {
                        setIsLogin(!isLogin);
                        setFormData({ name: "", email: "", phone: "", password: "", confirmPassword: "" });
                      }}
                      className="ml-2 text-[#D4A574] font-medium hover:underline"
                      data-testid="lavela-auth-toggle"
                    >
                      {isLogin ? "Sign Up" : "Sign In"}
                    </button>
                  </p>
                </div>
              </form>
            </div>

            {/* Benefits for new users */}
            {!isLogin && (
              <div className="mt-8 p-6 rounded-2xl text-center" style={{
                background: 'rgba(13, 77, 77, 0.5)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(230, 190, 138, 0.2)'
              }}>
                <h3 className="text-[#E6BE8A] font-medium mb-3">Member Benefits</h3>
                <div className="grid grid-cols-2 gap-3 text-sm text-[#E8C4B8]">
                  <div className="flex items-center gap-2">
                    <span>✨</span> Earn Points
                  </div>
                  <div className="flex items-center gap-2">
                    <span>🎁</span> Exclusive Offers
                  </div>
                  <div className="flex items-center gap-2">
                    <span>🚚</span> Free Shipping
                  </div>
                  <div className="flex items-center gap-2">
                    <span>💎</span> VIP Access
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 text-white text-center" style={{
        background: '#0D4D4D'
      }}>
        <p className="text-sm opacity-80 mb-2">
          © 2026 LA VELA BIANCA. Canadian-Italian Skincare Technology.
        </p>
        <div className="flex items-center justify-center gap-4 text-sm opacity-60">
          <a href="https://instagram.com/La_Vela_Bianca" target="_blank" rel="noopener noreferrer" className="hover:opacity-100 transition-opacity flex items-center gap-1">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
            @La_Vela_Bianca
          </a>
          <span>•</span>
          <a href="mailto:lavelabianca.official@gmail.com" className="hover:opacity-100 transition-opacity">
            lavelabianca.official@gmail.com
          </a>
        </div>
      </footer>
    </div>
  );
};

export default LaVelaAuthPage;
