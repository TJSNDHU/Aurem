import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { 
  Sparkles, Lock, Mail, Eye, EyeOff, ArrowRight, 
  Trophy, DollarSign, Users, TrendingUp, Loader2,
  MessageSquare, ExternalLink, Copy, CheckCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const InfluencerPortalPage = () => {
  const navigate = useNavigate();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loginLoading, setLoginLoading] = useState(false);
  const [partnerData, setPartnerData] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const [credentials, setCredentials] = useState({
    email: "",
    password: ""
  });

  // Check if user is already logged in as a partner
  useEffect(() => {
    const token = localStorage.getItem("reroots_token");
    if (token) {
      checkPartnerStatus(token);
    } else {
      setLoading(false);
    }
  }, []);

  const checkPartnerStatus = async (token) => {
    try {
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.data.is_partner && res.data.partner_code) {
        // User is a partner, fetch their dashboard data
        const partnerRes = await axios.get(`${API}/partner/dashboard`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setPartnerData({ ...res.data, ...partnerRes.data });
        setIsLoggedIn(true);
      } else {
        // User is logged in but not a partner
        setIsLoggedIn(false);
      }
    } catch (error) {
      console.error("Auth check failed:", error);
      localStorage.removeItem("reroots_token");
      setIsLoggedIn(false);
    }
    setLoading(false);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!credentials.email || !credentials.password) {
      toast.error("Please enter your email and password");
      return;
    }

    setLoginLoading(true);
    try {
      const res = await axios.post(`${API}/auth/login`, credentials);
      
      if (res.data.token) {
        localStorage.setItem("reroots_token", res.data.token);
        
        // Check if this user is a partner
        if (res.data.user?.is_partner) {
          toast.success("Welcome back, Partner! 🎉");
          checkPartnerStatus(res.data.token);
        } else {
          toast.error("This account is not registered as a partner");
          localStorage.removeItem("reroots_token");
        }
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Login failed");
    }
    setLoginLoading(false);
  };

  const copyCode = () => {
    if (partnerData?.partner_code) {
      navigator.clipboard.writeText(partnerData.partner_code);
      setCopied(true);
      toast.success("Partner code copied!");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const copyLink = () => {
    const link = `${window.location.origin}/partner/${partnerData?.partner_code?.toLowerCase()}`;
    navigator.clipboard.writeText(link);
    toast.success("Referral link copied!");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5]">
        <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37]" />
      </div>
    );
  }

  // ============ PARTNER DASHBOARD VIEW ============
  if (isLoggedIn && partnerData) {
    return (
      <div className="min-h-screen bg-[#FAF8F5]">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#2D2A2E] to-[#1a1819] py-12">
          <div className="max-w-6xl mx-auto px-6">
            <div className="flex items-center justify-between">
              <div>
                <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] mb-2">
                  <Sparkles className="w-3 h-3 mr-1" />
                  PARTNER PORTAL
                </Badge>
                <h1 className="text-3xl font-bold text-white">
                  Welcome back, {partnerData.name || "Partner"}!
                </h1>
                <p className="text-white/60 mt-1">Manage your referrals and earnings</p>
              </div>
              <Button
                variant="outline"
                className="border-white/20 text-white hover:bg-white/10"
                onClick={() => {
                  localStorage.removeItem("reroots_token");
                  setIsLoggedIn(false);
                  setPartnerData(null);
                }}
              >
                Sign Out
              </Button>
            </div>
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card className="bg-white border-[#D4AF37]/20">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Total Earnings</p>
                    <p className="text-2xl font-bold text-[#D4AF37]">
                      ${(partnerData.total_earnings || 0).toFixed(2)}
                    </p>
                  </div>
                  <DollarSign className="w-8 h-8 text-[#D4AF37]/30" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white border-[#F8A5B8]/20">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Total Sales</p>
                    <p className="text-2xl font-bold text-[#F8A5B8]">
                      {partnerData.total_sales || 0}
                    </p>
                  </div>
                  <TrendingUp className="w-8 h-8 text-[#F8A5B8]/30" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white border-green-200">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Commission Rate</p>
                    <p className="text-2xl font-bold text-green-600">
                      {partnerData.custom_commission || 10}%
                    </p>
                  </div>
                  <Trophy className="w-8 h-8 text-green-200" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white border-purple-200">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Customer Discount</p>
                    <p className="text-2xl font-bold text-purple-600">
                      {partnerData.custom_discount || 50}% OFF
                    </p>
                  </div>
                  <Users className="w-8 h-8 text-purple-200" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Partner Code Section */}
          <Card className="mb-8 border-2 border-[#D4AF37]/30 bg-gradient-to-r from-[#D4AF37]/5 to-white">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[#D4AF37]" />
                Your Partner Code
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 p-4 bg-[#2D2A2E] rounded-xl">
                    <span className="text-2xl font-bold text-[#D4AF37] tracking-wider">
                      {partnerData.partner_code}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="ml-auto text-white hover:text-[#D4AF37]"
                      onClick={copyCode}
                    >
                      {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </Button>
                  </div>
                  <p className="text-sm text-gray-500 mt-2">
                    Share this code with your audience. They get {partnerData.custom_discount || 50}% OFF!
                  </p>
                </div>
                <div className="flex-1">
                  <Button
                    className="w-full h-full bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E] font-bold"
                    onClick={copyLink}
                  >
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Copy Referral Link
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => navigate("/login")}>
              <CardContent className="p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-[#F8A5B8]/10 flex items-center justify-center">
                  <MessageSquare className="w-6 h-6 text-[#F8A5B8]" />
                </div>
                <div>
                  <h3 className="font-semibold text-[#2D2A2E]">Chat with Admin</h3>
                  <p className="text-sm text-gray-500">Get support or discuss opportunities</p>
                </div>
                <ArrowRight className="w-5 h-5 text-gray-400 ml-auto" />
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => window.open(`/partner/${partnerData.partner_code?.toLowerCase()}`, '_blank')}>
              <CardContent className="p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-[#D4AF37]/10 flex items-center justify-center">
                  <ExternalLink className="w-6 h-6 text-[#D4AF37]" />
                </div>
                <div>
                  <h3 className="font-semibold text-[#2D2A2E]">Preview Your Landing Page</h3>
                  <p className="text-sm text-gray-500">See what your audience sees</p>
                </div>
                <ArrowRight className="w-5 h-5 text-gray-400 ml-auto" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  // ============ LOGIN VIEW ============
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#2D2A2E] to-[#1a1819] flex items-center justify-center p-4">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#D4AF37]/10 rounded-full blur-[100px]" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-[#F8A5B8]/10 rounded-full blur-[100px]" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 bg-[#D4AF37]/20 px-4 py-2 rounded-full mb-4">
            <Sparkles className="w-4 h-4 text-[#D4AF37]" />
            <span className="text-sm text-[#D4AF37] font-medium">PARTNER PORTAL</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Welcome Back, Partner</h1>
          <p className="text-white/60">Sign in to access your dashboard</p>
        </div>

        {/* Login Card */}
        <Card className="bg-white/10 backdrop-blur-xl border-white/10">
          <CardContent className="p-6">
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="text-sm text-white/70 mb-1 block">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    type="email"
                    placeholder="partner@example.com"
                    value={credentials.email}
                    onChange={(e) => setCredentials({ ...credentials, email: e.target.value })}
                    className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/30"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-white/70 mb-1 block">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={credentials.password}
                    onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                    className="pl-10 pr-10 bg-white/5 border-white/10 text-white placeholder:text-white/30"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/60"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loginLoading}
                className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-bold hover:opacity-90"
              >
                {loginLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    Sign In
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 pt-6 border-t border-white/10 text-center">
              <p className="text-white/50 text-sm mb-3">Not a partner yet?</p>
              <Link to="/become-partner">
                <Button variant="outline" className="border-[#F8A5B8] text-[#F8A5B8] hover:bg-[#F8A5B8]/10">
                  <Trophy className="w-4 h-4 mr-2" />
                  Apply to Become a Partner
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-white/30 text-xs mt-6">
          ReRoots Partner Program · <Link to="/forgot-password" className="text-[#D4AF37] hover:underline">Forgot Password?</Link>
        </p>
      </div>
    </div>
  );
};

export default InfluencerPortalPage;
