import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Dna, Users, DollarSign, Link2, Download, Image, Copy, 
  TrendingUp, Eye, ShoppingBag, Award, ChevronRight, 
  ExternalLink, FileImage, Play, LogOut, BarChart3,
  FileText, Video, MessageSquare, Beaker, Sparkles,
  Instagram, Send, CheckCircle2, Folder
} from "lucide-react";
import MilestoneProgress from "../MilestoneProgress";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const PartnerDashboard = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const codeFromUrl = searchParams.get("code");
  
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginCode, setLoginCode] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  
  // Partner data
  const [partner, setPartner] = useState(null);
  const [stats, setStats] = useState({
    clicks: 0,
    signups: 0,
    sales: 0,
    commission: 0,
    conversionRate: 0
  });
  const [activeResourceTab, setActiveResourceTab] = useState("white-papers");
  
  // ============ PARTNER ASSET PORTAL DATA ============
  
  // Scientific White Papers
  const whitePapers = [
    {
      id: "wp-1",
      title: "The Science of PDRN",
      subtitle: "Polydeoxyribonucleotide in Skin Regeneration",
      description: "Comprehensive 12-page guide covering PDRN's mechanism of action, clinical studies, and benefits for skin longevity.",
      filename: "ReRoots-PDRN-Science-Guide.pdf",
      pages: 12,
      icon: Dna,
      color: "purple"
    },
    {
      id: "wp-2",
      title: "NAD+ & Cellular Energy",
      subtitle: "The Longevity Molecule in Skincare",
      description: "Explore how NAD+ precursors support cellular repair and why it's essential for skin health beyond age 30.",
      filename: "ReRoots-NAD-Plus-Guide.pdf",
      pages: 8,
      icon: Sparkles,
      color: "blue"
    },
    {
      id: "wp-3",
      title: "17% Active Recovery Complex",
      subtitle: "Our Proprietary Biotech Formula",
      description: "Technical breakdown of our signature blend: PDRN, NAD+, Tranexamic Acid, and supporting actives.",
      filename: "ReRoots-17-Percent-Active-Complex.pdf",
      pages: 10,
      icon: Beaker,
      color: "green"
    },
    {
      id: "wp-4",
      title: "Clinical Results Summary",
      subtitle: "Before & After Documentation",
      description: "28-day study results showing texture improvement, hydration levels, and user satisfaction scores.",
      filename: "ReRoots-Clinical-Results-2024.pdf",
      pages: 6,
      icon: BarChart3,
      color: "amber"
    }
  ];

  // Brand Media Assets
  const brandMedia = [
    {
      id: "bm-1",
      title: "AURA-GEN Hero Shot",
      type: "image",
      format: "PNG",
      dimensions: "3000x3000",
      description: "High-resolution product photography for hero banners and ads.",
      thumbnail: "/aura-gen.png"
    },
    {
      id: "bm-2",
      title: "AURA-GEN Serum Texture",
      type: "image",
      format: "PNG",
      dimensions: "2000x2000",
      description: "Close-up texture shot showing serum consistency.",
      thumbnail: "/aura-gen-texture.png"
    },
    {
      id: "bm-3",
      title: "Product Flat Lay Collection",
      type: "image",
      format: "PNG",
      dimensions: "4000x2500",
      description: "Full product range arranged for lifestyle content.",
      thumbnail: null
    },
    {
      id: "bm-4",
      title: "Lab B-Roll Footage",
      type: "video",
      format: "MP4",
      duration: "45 sec",
      description: "GMP laboratory footage for Reels and Stories.",
      thumbnail: null
    },
    {
      id: "bm-5",
      title: "Serum Application Demo",
      type: "video",
      format: "MP4",
      duration: "30 sec",
      description: "Professional application technique video.",
      thumbnail: null
    },
    {
      id: "bm-6",
      title: "ReRoots Logo Pack",
      type: "zip",
      format: "ZIP",
      description: "All logo variations (dark, light, icon) in PNG and SVG.",
      thumbnail: null
    }
  ];

  // Social Toolkits
  const socialToolkits = [
    {
      id: "st-1",
      platform: "Instagram",
      icon: Instagram,
      title: "Instagram Caption Templates",
      templates: [
        {
          type: "Product Intro",
          caption: `Finally, skincare that speaks science. 🧬

I've partnered with @reroots_ca because their 17% Active Recovery Complex isn't just another serum — it's biotech-grade PDRN formulated in a GMP Canadian lab.

My followers get {DISCOUNT}% off with code {CODE}

The difference? You'll feel it in 2 weeks. 

#ReRootsPartner #PDRNSerum #SkinLongevity`
        },
        {
          type: "Results Post",
          caption: `Week 4 update: The texture transformation is REAL ✨

This isn't magic — it's science. PDRN (Polydeoxyribonucleotide) triggers your skin's natural repair mechanisms.

Grab yours at reroots.ca with my code {CODE} for {DISCOUNT}% off.

Who else is on the skin longevity journey?

#SkinResults #CleanBeauty #ReRootsPartner`
        },
        {
          type: "Story Hook",
          caption: `POV: You discover your skin can actually repair itself at the cellular level 🔬

Swipe up to try AURA-GEN with my code {CODE} →`
        }
      ]
    },
    {
      id: "st-2",
      platform: "WhatsApp",
      icon: Send,
      title: "WhatsApp Campaign Messages",
      templates: [
        {
          type: "10-Referral Campaign",
          caption: `Hey! 👋 I've been using this biotech serum from ReRoots and my skin has never looked better.

Here's the deal: If you take their free Bio-Age Scan (2 min quiz), you'll get personalized recommendations AND help me unlock a 30% lifetime discount!

Take the scan here: {REFERRAL_LINK}

It's free and actually interesting — they show you your "skin age" 🧬`
        },
        {
          type: "Friend Referral",
          caption: `Okay I have to share this because you asked about my skincare routine...

It's called AURA-GEN by ReRoots. Canadian biotech brand using pharmaceutical-grade PDRN (the stuff they use in Korean clinics).

Use my code {CODE} for {DISCOUNT}% off: reroots.ca

Let me know what you think! 💕`
        },
        {
          type: "Follow-up",
          caption: `Hey! Did you end up trying that serum I mentioned?

Just checking in — I know the Bio-Age Scan I sent was cool. Let me know if you have any Qs!`
        }
      ]
    },
    {
      id: "st-3",
      platform: "TikTok",
      icon: Play,
      title: "TikTok Script Ideas",
      templates: [
        {
          type: "Hook Video",
          caption: `[HOOK] "The ingredient Korean dermatologists have been using for years just hit Canada"

[BODY] Show AURA-GEN, talk about PDRN, show texture

[CTA] "Link in bio, code {CODE} for {DISCOUNT}% off"`
        },
        {
          type: "GRWM Style",
          caption: `[HOOK] "POV: You finally understand why your $200 serums weren't working"

[BODY] Apply serum, explain 17% active complex, show results

[CTA] "This is AURA-GEN by ReRoots — code in bio"`
        }
      ]
    }
  ];

  const copyToClipboard = (text, label) => {
    // Replace placeholders with partner's actual values
    const processedText = text
      .replace(/{CODE}/g, partner?.discount_code || partner?.code || "PARTNER")
      .replace(/{DISCOUNT}/g, partner?.customer_discount || "50")
      .replace(/{REFERRAL_LINK}/g, `${window.location.origin}/Bio-Age-Repair-Scan?ref=${partner?.code}`);
    
    navigator.clipboard.writeText(processedText);
    toast.success(`${label} copied!`);
  };

  const downloadAsset = (filename, title) => {
    // In production, this would trigger actual download
    toast.success(`Downloading ${title}...`);
    // window.open(`/assets/${filename}`, '_blank');
  };

  // Check for existing session
  useEffect(() => {
    const savedEmail = localStorage.getItem("partner_email");
    const savedCode = localStorage.getItem("partner_code");
    
    if (savedEmail && savedCode) {
      verifyPartner(savedEmail, savedCode);
    } else if (codeFromUrl) {
      setLoginCode(codeFromUrl);
      setLoading(false);
    } else {
      setLoading(false);
    }
  }, [codeFromUrl]);

  const verifyPartner = async (email, code) => {
    try {
      const res = await axios.post(`${API}/partner/verify`, { email, code });
      if (res.data.valid) {
        setPartner(res.data.partner);
        setStats(res.data.stats || stats);
        setIsLoggedIn(true);
        localStorage.setItem("partner_email", email);
        localStorage.setItem("partner_code", code);
      } else {
        localStorage.removeItem("partner_email");
        localStorage.removeItem("partner_code");
      }
    } catch (error) {
      console.error("Partner verification failed:", error);
      localStorage.removeItem("partner_email");
      localStorage.removeItem("partner_code");
    }
    setLoading(false);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!loginEmail || !loginCode) {
      toast.error("Please enter your email and partner code");
      return;
    }
    
    setLoginLoading(true);
    try {
      const res = await axios.post(`${API}/partner/verify`, { 
        email: loginEmail.trim().toLowerCase(), 
        code: loginCode.trim().toUpperCase() 
      });
      
      if (res.data.valid) {
        setPartner(res.data.partner);
        setStats(res.data.stats || stats);
        setIsLoggedIn(true);
        localStorage.setItem("partner_email", loginEmail.trim().toLowerCase());
        localStorage.setItem("partner_code", loginCode.trim().toUpperCase());
        toast.success("Welcome back, Partner!");
      } else {
        toast.error("Invalid email or partner code");
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Login failed. Please check your credentials.");
    }
    setLoginLoading(false);
  };

  const handleLogout = () => {
    localStorage.removeItem("partner_email");
    localStorage.removeItem("partner_code");
    setIsLoggedIn(false);
    setPartner(null);
    toast.success("Logged out successfully");
  };

  const copyReferralLink = () => {
    const link = `${window.location.origin}/shop?ref=${partner?.code}`;
    navigator.clipboard.writeText(link);
    toast.success("Referral link copied!");
  };

  const copyDiscountCode = () => {
    navigator.clipboard.writeText(partner?.discount_code || partner?.code);
    toast.success("Discount code copied!");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <Dna className="w-12 h-12 text-[#D4AF37] animate-pulse mx-auto mb-4" />
          <p className="text-white/50">Loading Partner Portal...</p>
        </div>
      </div>
    );
  }

  // Login Screen
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#0a0a0a] via-[#1a1a1a] to-[#0a0a0a] flex items-center justify-center px-6">
        <Helmet>
          <title>Partner Portal | ReRoots Aesthetics</title>
          <meta name="description" content="Access your ReRoots Partner Dashboard. Track your referrals, commissions, and download brand assets." />
        </Helmet>

        <div 
          className="w-full max-w-md rounded-2xl overflow-hidden"
          style={{
            background: "linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)",
            border: "1px solid rgba(212, 175, 55, 0.2)",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
          }}
        >
          {/* Header */}
          <div 
            className="p-8 text-center"
            style={{
              background: "linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(212, 175, 55, 0.05) 100%)",
              borderBottom: "1px solid rgba(212, 175, 55, 0.1)"
            }}
          >
            <div 
              className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ 
                background: "linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.1) 100%)",
                border: "1px solid rgba(212, 175, 55, 0.3)"
              }}
            >
              <Dna className="w-8 h-8 text-[#D4AF37]" />
            </div>
            <h1 className="text-2xl font-semibold text-white mb-2" style={{ fontFamily: '"Playfair Display", serif' }}>
              Partner Portal
            </h1>
            <p className="text-white/50 text-sm">
              Access your dashboard with your partner credentials
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleLogin} className="p-8 space-y-4">
            <div>
              <label className="text-white/50 text-xs uppercase tracking-wider mb-2 block">Email Address</label>
              <Input
                type="email"
                placeholder="your@email.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12"
                data-testid="partner-email"
              />
            </div>
            <div>
              <label className="text-white/50 text-xs uppercase tracking-wider mb-2 block">Partner Code</label>
              <Input
                type="text"
                placeholder="PARTNER-XXXX"
                value={loginCode}
                onChange={(e) => setLoginCode(e.target.value.toUpperCase())}
                className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 font-mono"
                data-testid="partner-code"
              />
            </div>
            <Button
              type="submit"
              disabled={loginLoading}
              className="w-full h-12 rounded-lg font-semibold"
              style={{
                background: "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
                color: "#0a0a0a"
              }}
              data-testid="partner-login-btn"
            >
              {loginLoading ? "Verifying..." : "Access Dashboard"}
            </Button>
          </form>

          {/* Footer */}
          <div className="px-8 pb-8 text-center">
            <p className="text-white/30 text-xs">
              Not a partner yet?{" "}
              <a href="/become-partner" className="text-[#D4AF37] hover:underline">
                Apply now
              </a>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Dashboard Screen
  return (
    <div className="min-h-screen bg-[#FAF8F5]">
      <Helmet>
        <title>Partner Dashboard | ReRoots Aesthetics</title>
      </Helmet>

      {/* Header */}
      <div className="bg-[#2D2A2E] text-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-[#D4AF37]/20 flex items-center justify-center">
              <Dna className="w-5 h-5 text-[#D4AF37]" />
            </div>
            <div>
              <h1 className="font-semibold">Partner Dashboard</h1>
              <p className="text-white/50 text-sm">{partner?.name || partner?.email}</p>
            </div>
          </div>
          <Button
            onClick={handleLogout}
            variant="ghost"
            className="text-white/70 hover:text-white hover:bg-white/10"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Welcome Banner */}
        <div 
          className="rounded-2xl p-6 mb-8"
          style={{
            background: "linear-gradient(135deg, #2D2A2E 0%, #3D3A3E 100%)"
          }}
        >
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <p className="text-[#D4AF37] text-sm font-medium mb-1">
                <Award className="w-4 h-4 inline mr-1" />
                {partner?.tier || "Partner"}
              </p>
              <h2 className="text-white text-2xl font-semibold" style={{ fontFamily: '"Playfair Display", serif' }}>
                Welcome back, {partner?.name?.split(" ")[0] || "Partner"}
              </h2>
              <p className="text-white/50 text-sm mt-1">
                Your commission rate: <span className="text-[#D4AF37] font-semibold">{partner?.commission_rate || 15}%</span>
              </p>
            </div>
            <div className="flex gap-3">
              <Button
                onClick={copyReferralLink}
                className="bg-[#D4AF37] hover:bg-[#b8960f] text-[#0a0a0a] font-semibold"
              >
                <Link2 className="w-4 h-4 mr-2" />
                Copy Referral Link
              </Button>
              <Button
                onClick={copyDiscountCode}
                variant="outline"
                className="border-white/20 text-white hover:bg-white/10"
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy Discount Code
              </Button>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl p-5 border border-[#2D2A2E]/5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                <Eye className="w-5 h-5 text-blue-500" />
              </div>
              <span className="text-[#5A5A5A] text-sm">Link Clicks</span>
            </div>
            <p className="text-3xl font-bold text-[#2D2A2E]">{stats.clicks}</p>
          </div>
          
          <div className="bg-white rounded-xl p-5 border border-[#2D2A2E]/5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
                <Users className="w-5 h-5 text-purple-500" />
              </div>
              <span className="text-[#5A5A5A] text-sm">Signups</span>
            </div>
            <p className="text-3xl font-bold text-[#2D2A2E]">{stats.signups}</p>
          </div>
          
          <div className="bg-white rounded-xl p-5 border border-[#2D2A2E]/5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                <ShoppingBag className="w-5 h-5 text-green-500" />
              </div>
              <span className="text-[#5A5A5A] text-sm">Sales</span>
            </div>
            <p className="text-3xl font-bold text-[#2D2A2E]">{stats.sales}</p>
          </div>
          
          <div className="bg-white rounded-xl p-5 border border-[#2D2A2E]/5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-[#D4AF37]/10 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-[#D4AF37]" />
              </div>
              <span className="text-[#5A5A5A] text-sm">Commission</span>
            </div>
            <p className="text-3xl font-bold text-[#D4AF37]">${stats.commission.toFixed(2)}</p>
          </div>
        </div>

        {/* Milestone Progress - Unlock 30% Discount */}
        {partner?.code && (
          <MilestoneProgress 
            referralCode={partner.code}
            showShareLink={true}
          />
        )}

        {/* Two Column Layout */}
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Your Links */}
          <div className="bg-white rounded-xl border border-[#2D2A2E]/5 shadow-sm overflow-hidden">
            <div className="p-5 border-b border-[#2D2A2E]/5">
              <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                <Link2 className="w-5 h-5 text-[#D4AF37]" />
                Your Partner Links
              </h3>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="text-[#5A5A5A] text-xs uppercase tracking-wider mb-2 block">Referral Link</label>
                <div className="flex gap-2">
                  <Input
                    readOnly
                    value={`${window.location.origin}/shop?ref=${partner?.code}`}
                    className="bg-[#FAF8F5] font-mono text-sm"
                  />
                  <Button onClick={copyReferralLink} variant="outline" size="sm">
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <div>
                <label className="text-[#5A5A5A] text-xs uppercase tracking-wider mb-2 block">Discount Code (15% Off)</label>
                <div className="flex gap-2">
                  <Input
                    readOnly
                    value={partner?.discount_code || partner?.code}
                    className="bg-[#FAF8F5] font-mono text-sm font-bold"
                  />
                  <Button onClick={copyDiscountCode} variant="outline" size="sm">
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Talking Points */}
          <div className="bg-white rounded-xl border border-[#2D2A2E]/5 shadow-sm overflow-hidden">
            <div className="p-5 border-b border-[#2D2A2E]/5">
              <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-[#D4AF37]" />
                The Science You're Sharing
              </h3>
            </div>
            <div className="p-5">
              <p className="text-[#5A5A5A] text-sm mb-4">
                Key talking points for your audience:
              </p>
              <ul className="space-y-3 text-sm">
                <li className="flex items-start gap-2">
                  <span className="text-[#D4AF37]">✓</span>
                  <span><strong>17% Active Recovery Complex</strong> - Not just PDRN, a synergistic biotech blend</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#D4AF37]">✓</span>
                  <span><strong>GMP-Certified Canadian Lab</strong> - Pharmaceutical-grade manufacturing</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#D4AF37]">✓</span>
                  <span><strong>Skin Longevity, Not Just Anti-Aging</strong> - Our philosophy is different</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[#D4AF37]">✓</span>
                  <span><strong>Results in 2-4 Weeks</strong> - Visible texture improvement</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* ============ PARTNER ASSET PORTAL - RESOURCES TAB ============ */}
        <div className="mt-8 bg-white rounded-xl border border-[#2D2A2E]/5 shadow-sm overflow-hidden" data-testid="partner-asset-portal">
          <div className="p-5 border-b border-[#2D2A2E]/5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[#D4AF37]/10 flex items-center justify-center">
                  <Folder className="w-5 h-5 text-[#D4AF37]" />
                </div>
                <div>
                  <h3 className="font-semibold text-[#2D2A2E]">Partner Resources</h3>
                  <p className="text-xs text-[#5A5A5A]">Everything you need to represent ReRoots professionally</p>
                </div>
              </div>
            </div>
          </div>

          <Tabs value={activeResourceTab} onValueChange={setActiveResourceTab} className="w-full">
            <div className="px-5 pt-4 border-b border-[#2D2A2E]/5">
              <TabsList className="bg-[#FAF8F5] p-1 rounded-lg">
                <TabsTrigger 
                  value="white-papers" 
                  className="data-[state=active]:bg-white data-[state=active]:text-[#2D2A2E] data-[state=active]:shadow-sm rounded-md px-4 py-2"
                  data-testid="tab-white-papers"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  Scientific Papers
                </TabsTrigger>
                <TabsTrigger 
                  value="brand-media" 
                  className="data-[state=active]:bg-white data-[state=active]:text-[#2D2A2E] data-[state=active]:shadow-sm rounded-md px-4 py-2"
                  data-testid="tab-brand-media"
                >
                  <Image className="w-4 h-4 mr-2" />
                  Brand Media
                </TabsTrigger>
                <TabsTrigger 
                  value="social-toolkits" 
                  className="data-[state=active]:bg-white data-[state=active]:text-[#2D2A2E] data-[state=active]:shadow-sm rounded-md px-4 py-2"
                  data-testid="tab-social-toolkits"
                >
                  <MessageSquare className="w-4 h-4 mr-2" />
                  Social Toolkits
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Scientific White Papers Tab */}
            <TabsContent value="white-papers" className="p-5 m-0">
              <div className="grid md:grid-cols-2 gap-4">
                {whitePapers.map((paper) => {
                  const Icon = paper.icon;
                  return (
                    <div
                      key={paper.id}
                      className="group border border-[#2D2A2E]/10 rounded-xl p-5 hover:border-[#D4AF37]/30 hover:bg-[#D4AF37]/5 transition-all cursor-pointer"
                      onClick={() => downloadAsset(paper.filename, paper.title)}
                      data-testid={`paper-${paper.id}`}
                    >
                      <div className="flex items-start gap-4">
                        <div className={`w-12 h-12 rounded-xl bg-${paper.color}-50 flex items-center justify-center flex-shrink-0`}>
                          <Icon className={`w-6 h-6 text-${paper.color}-500`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-[#2D2A2E] group-hover:text-[#D4AF37] transition-colors">
                            {paper.title}
                          </h4>
                          <p className="text-xs text-[#D4AF37] font-medium mt-0.5">{paper.subtitle}</p>
                          <p className="text-sm text-[#5A5A5A] mt-2 line-clamp-2">{paper.description}</p>
                          <div className="flex items-center gap-3 mt-3">
                            <span className="text-xs text-[#5A5A5A] bg-[#FAF8F5] px-2 py-1 rounded">
                              PDF • {paper.pages} pages
                            </span>
                            <span className="text-xs text-[#D4AF37] font-medium flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <Download className="w-3 h-3" /> Download
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </TabsContent>

            {/* Brand Media Tab */}
            <TabsContent value="brand-media" className="p-5 m-0">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-[#5A5A5A]">High-resolution assets for your content</p>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="text-[#D4AF37] border-[#D4AF37]/30 hover:bg-[#D4AF37]/10"
                  onClick={() => toast.success("Downloading all brand assets...")}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download All
                </Button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {brandMedia.map((asset) => (
                  <div
                    key={asset.id}
                    className="group border border-[#2D2A2E]/10 rounded-xl overflow-hidden hover:border-[#D4AF37]/30 transition-all cursor-pointer"
                    onClick={() => downloadAsset(asset.id, asset.title)}
                    data-testid={`media-${asset.id}`}
                  >
                    <div className="aspect-video bg-gradient-to-br from-[#FAF8F5] to-[#F0EDE8] flex items-center justify-center relative">
                      {asset.type === 'image' && (
                        <FileImage className="w-10 h-10 text-[#5A5A5A]/30" />
                      )}
                      {asset.type === 'video' && (
                        <div className="relative">
                          <Video className="w-10 h-10 text-[#5A5A5A]/30" />
                          <div className="absolute -bottom-1 -right-1 bg-red-500 text-white text-[8px] px-1 rounded">
                            {asset.duration}
                          </div>
                        </div>
                      )}
                      {asset.type === 'zip' && (
                        <Folder className="w-10 h-10 text-[#5A5A5A]/30" />
                      )}
                      {/* Hover overlay */}
                      <div className="absolute inset-0 bg-[#D4AF37]/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <Download className="w-8 h-8 text-[#D4AF37]" />
                      </div>
                    </div>
                    <div className="p-3">
                      <h4 className="font-medium text-sm text-[#2D2A2E] truncate">{asset.title}</h4>
                      <p className="text-xs text-[#5A5A5A] mt-1">
                        {asset.format} {asset.dimensions && `• ${asset.dimensions}`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>

            {/* Social Toolkits Tab */}
            <TabsContent value="social-toolkits" className="p-5 m-0">
              <p className="text-sm text-[#5A5A5A] mb-4">
                Pre-written captions with your code <span className="font-mono bg-[#D4AF37]/10 text-[#D4AF37] px-2 py-0.5 rounded">{partner?.code || "PARTNER"}</span> auto-inserted
              </p>
              
              <div className="space-y-6">
                {socialToolkits.map((toolkit) => {
                  const Icon = toolkit.icon;
                  return (
                    <div key={toolkit.id} className="border border-[#2D2A2E]/10 rounded-xl overflow-hidden" data-testid={`toolkit-${toolkit.id}`}>
                      <div className="px-5 py-3 bg-[#FAF8F5] border-b border-[#2D2A2E]/5 flex items-center gap-3">
                        <Icon className="w-5 h-5 text-[#D4AF37]" />
                        <h4 className="font-semibold text-[#2D2A2E]">{toolkit.title}</h4>
                      </div>
                      <div className="p-4 space-y-3">
                        {toolkit.templates.map((template, idx) => (
                          <div 
                            key={idx}
                            className="bg-[#FAF8F5]/50 rounded-lg p-4 border border-[#2D2A2E]/5 hover:border-[#D4AF37]/20 transition-colors"
                          >
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs font-medium text-[#D4AF37] bg-[#D4AF37]/10 px-2 py-1 rounded">
                                {template.type}
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-[#5A5A5A] hover:text-[#D4AF37] h-8"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  copyToClipboard(template.caption, template.type);
                                }}
                              >
                                <Copy className="w-4 h-4 mr-1" />
                                Copy
                              </Button>
                            </div>
                            <pre className="text-sm text-[#5A5A5A] whitespace-pre-wrap font-sans leading-relaxed">
                              {template.caption
                                .replace(/{CODE}/g, partner?.code || "PARTNER")
                                .replace(/{DISCOUNT}/g, partner?.customer_discount || "50")
                                .replace(/{REFERRAL_LINK}/g, `reroots.ca/scan?ref=${partner?.code || "PARTNER"}`)}
                            </pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Support Section */}
        <div className="mt-8 text-center">
          <p className="text-[#5A5A5A] text-sm">
            Need help? Contact partner support at{" "}
            <a href="mailto:partners@reroots.ca" className="text-[#D4AF37] hover:underline">
              partners@reroots.ca
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default PartnerDashboard;
