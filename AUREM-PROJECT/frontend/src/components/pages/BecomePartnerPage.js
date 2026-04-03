import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Check, Sparkles, Trophy, Users, Gift, DollarSign, Package, Shield, Beaker, MapPin, User, MessageCircle, Instagram, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// API URL - same logic as main App.js
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    return window.location.origin;
  }
  return window.location.origin;
};
const API = `${getBackendUrl()}/api`;

const BecomePartnerPage = () => {
  const [programInfo, setProgramInfo] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    phone: "",
    date_of_birth: "",
    country: "Canada",
    partner_tier: "reroots", // NEW: Partner tier selection
    primary_platform: "instagram",
    social_handle: "",
    follower_count: "",
    engagement_rate: "",
    content_niche: "skincare",
    profile_url: "",
    why_partner: "",
    content_ideas: "",
    previous_brands: "",
    // Social media connections
    instagram_connected: false,
    instagram_username: "",
    tiktok_connected: false,
    tiktok_username: "",
    // Terms acceptance
    agree_terms: false,
    agree_privacy: false,
    agree_marketing: false
  });

  // Partner tier configurations
  const PARTNER_TIERS = {
    oroe: {
      name: "OROÉ Luxury Partner",
      tagline: "The Founders' Collection",
      icon: "👑",
      color: "from-[#1A1A1A] to-[#D4AF37]",
      borderColor: "border-[#D4AF37]",
      commission: "25%",
      customerDiscount: "15%",
      bonus: "$1,000",
      idealFor: "Luxury Spas, Aesthetic Nurses, Dermatologists",
      ageTarget: "35+ Premium Market",
      productPrice: "$159 CAD",
      requirements: "10K+ followers, luxury/medical aesthetic focus",
      perks: ["Exclusive spa samples", "VIP launch access", "Co-branded certificates"]
    },
    reroots: {
      name: "ReRoots Gold Partner",
      tagline: "The Gurnaman Singh Collection",
      icon: "🧬",
      color: "from-[#D4AF37] to-[#F8A5B8]",
      borderColor: "border-[#D4AF37]",
      commission: "15%",
      customerDiscount: "20%",
      bonus: "$500",
      idealFor: "Skincare Influencers, Beauty Bloggers",
      ageTarget: "18-35 Young Adults",
      productPrice: "$155 CAD",
      requirements: "5K+ followers, skincare/beauty niche",
      perks: ["Free product samples", "Affiliate dashboard", "Monthly bonuses"]
    },
    lavela: {
      name: "LA VELA BIANCA Ambassador",
      tagline: "The Anmol Singh Collection",
      icon: "🌸",
      color: "from-[#0D4D4D] to-[#E8C4B8]",
      borderColor: "border-[#E8C4B8]",
      commission: "12%",
      customerDiscount: "25%",
      bonus: "$250",
      idealFor: "Teen Influencers, Skincare Moms, School Communities",
      ageTarget: "8-18 Teen Market",
      productPrice: "$49 CAD",
      requirements: "2K+ followers, teen/family content",
      perks: ["Volume bonuses", "School partnership kit", "Parent referral rewards"]
    }
  };

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/partner-program`).catch(() => ({ data: {} })),
      axios.get(`${API}/partner-leaderboard`).catch(() => ({ data: { leaderboard: [] } }))
    ]).then(([programRes, leaderboardRes]) => {
      setProgramInfo(programRes.data);
      setLeaderboard(leaderboardRes.data?.leaderboard || []);
    }).finally(() => setLoading(false));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate terms acceptance
    if (!formData.agree_terms || !formData.agree_privacy) {
      toast.error("Please agree to the Terms of Use and Privacy Policy");
      return;
    }
    
    // Validate at least one social account is connected
    if (!formData.instagram_connected && !formData.tiktok_connected) {
      toast.error("Please connect at least one social media account (Instagram or TikTok)");
      return;
    }
    
    setSubmitting(true);
    try {
      await axios.post(`${API}/partner-application`, formData);
      setSubmitted(true);
      toast.success("Application submitted successfully!");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to submit application");
    }
    setSubmitting(false);
  };

  // Social media connection handler (simplified - just validates username)
  const connectSocialMedia = (platform) => {
    if (platform === 'instagram') {
      const username = prompt("Enter your Instagram username (without @):");
      if (username && username.trim()) {
        setFormData({
          ...formData,
          instagram_connected: true,
          instagram_username: username.trim().replace('@', ''),
          social_handle: username.trim().replace('@', ''),
          primary_platform: 'instagram'
        });
        toast.success(`Instagram @${username.trim().replace('@', '')} connected!`);
      }
    } else if (platform === 'tiktok') {
      const username = prompt("Enter your TikTok username (without @):");
      if (username && username.trim()) {
        setFormData({
          ...formData,
          tiktok_connected: true,
          tiktok_username: username.trim().replace('@', ''),
          social_handle: formData.social_handle || username.trim().replace('@', ''),
          primary_platform: formData.instagram_connected ? formData.primary_platform : 'tiktok'
        });
        toast.success(`TikTok @${username.trim().replace('@', '')} connected!`);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5]">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  if (submitted) {
    const thankYouMsg = programInfo?.thank_you_messages?.partner_application || 
      "Thank you for applying to become a ReRoots Partner! We're excited to review your application. Our team will get back to you within 48-72 hours with the next steps.";
    
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center p-6">
        <div className="max-w-md text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
            <Check className="h-10 w-10 text-[#2D2A2E]" />
          </div>
          <h1 className="font-display text-3xl font-bold text-[#2D2A2E] mb-4">Application Received!</h1>
          <p className="text-[#5A5A5A] mb-6">{thankYouMsg}</p>
          <Link to="/">
            <Button className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-bold hover:from-[#F4D03F] hover:to-[#D4AF37]">
              Back to Store
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const inf = programInfo?.influencer_program || {};

  return (
    <div className="min-h-screen bg-[#FAF8F5]">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-[#2D2A2E] via-[#1a1819] to-[#2D2A2E] py-16 overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(212,175,55,0.5) 1px, transparent 0)', backgroundSize: '30px 30px'}}></div>
        </div>
        
        <div className="max-w-6xl mx-auto px-6 relative z-10">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="relative flex justify-center">
              <div className="relative">
                <img 
                  src="https://files.catbox.moe/jdjokm.jpg" 
                  alt="AURA-GEN TXA+PDRN Bio-Regenerator"
                  className="w-80 h-80 object-cover rounded-2xl shadow-2xl border-2 border-[#D4AF37]/30"
                />
                <div className="absolute -top-4 -right-4 bg-gradient-to-br from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] px-4 py-3 rounded-xl shadow-lg transform rotate-12">
                  <p className="text-xs font-bold uppercase tracking-wide">Founder's</p>
                  <p className="text-2xl font-black">50% OFF</p>
                </div>
              </div>
            </div>
            
            <div className="text-center md:text-left">
              <div className="inline-flex items-center gap-2 bg-[#D4AF37]/20 px-4 py-1.5 rounded-full mb-6">
                <Sparkles className="h-4 w-4 text-[#D4AF37]" />
                <span className="text-sm text-[#D4AF37] font-medium tracking-wide">GOLD PARTNER PROGRAM</span>
              </div>
              
              <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
                {inf.program_name || "Become a ReRoots Gold Partner"}
              </h1>
              
              <p className="text-lg text-gray-300 mb-6">
                Join our elite community of beauty influencers. Earn premium commissions while sharing professional-strength skincare with your audience.
              </p>
              
              <div className="flex flex-wrap gap-4 mb-8 justify-center md:justify-start">
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full">
                  <MapPin className="h-4 w-4 text-[#D4AF37]" />
                  <span className="text-white text-sm font-medium">Formulated in Canada</span>
                </div>
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full">
                  <Beaker className="h-4 w-4 text-[#F8A5B8]" />
                  <span className="text-white text-sm font-medium">PDRN Science</span>
                </div>
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full">
                  <Shield className="h-4 w-4 text-green-400" />
                  <span className="text-white text-sm font-medium">Professional-Strength</span>
                </div>
              </div>
              
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="text-center p-4 bg-white/5 rounded-xl border border-[#D4AF37]/20">
                  <p className="text-3xl font-bold text-[#D4AF37]">{inf.commission_rate || 15}%</p>
                  <p className="text-xs text-gray-400 mt-1">Commission</p>
                </div>
                <div className="text-center p-4 bg-white/5 rounded-xl border border-[#F8A5B8]/20">
                  <p className="text-3xl font-bold text-[#F8A5B8]">{inf.customer_discount_value || 20}%</p>
                  <p className="text-xs text-gray-400 mt-1">Customer Discount</p>
                </div>
                <div className="text-center p-4 bg-white/5 rounded-xl border border-green-500/20">
                  <p className="text-3xl font-bold text-green-400">$500</p>
                  <p className="text-xs text-gray-400 mt-1">Monthly Bonus</p>
                </div>
              </div>
              
              <a href="#apply-form">
                <Button className="w-full md:w-auto px-12 py-6 text-lg font-bold bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] hover:from-[#F4D03F] hover:via-[#D4AF37] hover:to-[#F4D03F] shadow-lg shadow-[#D4AF37]/30 transition-all hover:scale-105">
                  Apply for Gold Status
                </Button>
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Partner Tier Selection - NEW SECTION */}
      <section className="py-16 bg-gradient-to-b from-[#2D2A2E] to-[#FAF8F5]">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 bg-white/10 px-4 py-1.5 rounded-full mb-4">
              <Users className="h-4 w-4 text-[#D4AF37]" />
              <span className="text-sm text-[#D4AF37] font-medium uppercase tracking-wide">CHOOSE YOUR PATH</span>
            </div>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-white mb-4">
              Select Your Partner Tier
            </h2>
            <p className="text-gray-400 max-w-2xl mx-auto">
              Three brands, three opportunities. Choose the tier that matches your audience best.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {Object.entries(PARTNER_TIERS).map(([key, tier]) => (
              <div 
                key={key}
                onClick={() => setFormData({...formData, partner_tier: key})}
                className={`relative cursor-pointer rounded-2xl p-6 transition-all duration-300 hover:scale-105 ${
                  formData.partner_tier === key 
                    ? `bg-gradient-to-br ${tier.color} border-2 ${tier.borderColor} shadow-2xl` 
                    : 'bg-white/10 border border-white/20 hover:border-white/40'
                }`}
              >
                {formData.partner_tier === key && (
                  <div className="absolute -top-3 -right-3 bg-green-500 rounded-full p-1">
                    <Check className="h-4 w-4 text-white" />
                  </div>
                )}
                
                <div className="text-center mb-4">
                  <span className="text-4xl">{tier.icon}</span>
                  <h3 className="text-xl font-bold text-white mt-2">{tier.name}</h3>
                  <p className="text-sm text-white/70 italic">{tier.tagline}</p>
                </div>

                <div className="space-y-3 mb-6">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-white/70">Commission:</span>
                    <span className="text-white font-bold text-lg">{tier.commission}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-white/70">Customer Discount:</span>
                    <span className="text-white font-semibold">{tier.customerDiscount}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-white/70">Monthly Bonus:</span>
                    <span className="text-green-400 font-semibold">{tier.bonus}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-white/70">Product Price:</span>
                    <span className="text-white">{tier.productPrice}</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/20">
                  <p className="text-xs text-white/60 mb-2">
                    <strong className="text-white/80">Ideal For:</strong> {tier.idealFor}
                  </p>
                  <p className="text-xs text-white/60">
                    <strong className="text-white/80">Target:</strong> {tier.ageTarget}
                  </p>
                </div>

                {formData.partner_tier === key && (
                  <div className="mt-4 bg-black/20 rounded-lg p-3">
                    <p className="text-xs text-white/80 font-medium mb-2">✨ Partner Perks:</p>
                    <ul className="text-xs text-white/70 space-y-1">
                      {tier.perks.map((perk, i) => (
                        <li key={i} className="flex items-center gap-1">
                          <Check className="h-3 w-3 text-green-400" /> {perk}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Leaderboard Section */}
      <section className="py-16 bg-gradient-to-b from-[#FDF9F9] to-white">
        <div className="max-w-4xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 bg-[#D4AF37]/10 px-4 py-1.5 rounded-full mb-4">
              <Trophy className="h-4 w-4 text-[#D4AF37]" />
              <span className="text-sm text-[#D4AF37] font-medium uppercase">{programInfo?.leaderboard_settings?.reset_period || "MONTHLY"} COMPETITION</span>
            </div>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-4">
              Founder's Leaderboard
            </h2>
            <p className="text-[#5A5A5A] max-w-2xl mx-auto">
              Top 3 partners who generate the most referral loops win a <span className="text-[#D4AF37] font-bold">${programInfo?.leaderboard_settings?.first_prize || 500} Gold Bonus</span>!
            </p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-6 mb-8">
            {[0, 1, 2].map((idx) => {
              const place = leaderboard[idx];
              const prizes = [
                { prize: programInfo?.leaderboard_settings?.first_prize || 500, medal: "🥇", bg: "from-[#D4AF37]/20 to-[#F4D03F]/20", border: "border-[#D4AF37]", text: "text-[#D4AF37]" },
                { prize: programInfo?.leaderboard_settings?.second_prize || 250, medal: "🥈", bg: "from-gray-100 to-gray-200", border: "border-gray-300", text: "text-gray-600" },
                { prize: programInfo?.leaderboard_settings?.third_prize || 100, medal: "🥉", bg: "from-[#CD7F32]/20 to-[#CD7F32]/10", border: "border-[#CD7F32]/50", text: "text-[#CD7F32]" }
              ][idx];
              
              return (
                <div key={idx} className={`relative bg-gradient-to-br ${prizes.bg} rounded-2xl p-6 border-2 ${prizes.border} shadow-lg transform hover:scale-105 transition-all`}>
                  <div className={`absolute -top-4 left-1/2 -translate-x-1/2 ${idx === 0 ? 'bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E]' : idx === 1 ? 'bg-gradient-to-r from-gray-400 to-gray-500 text-white' : 'bg-gradient-to-r from-[#CD7F32] to-[#B87333] text-white'} px-4 py-1 rounded-full text-sm font-bold`}>
                    {prizes.medal} {idx + 1}{idx === 0 ? 'st' : idx === 1 ? 'nd' : 'rd'} Place
                  </div>
                  <div className="text-center pt-4">
                    <div className={`w-16 h-16 ${idx === 0 ? 'w-20 h-20' : ''} bg-gradient-to-br ${idx === 0 ? 'from-[#D4AF37] to-[#F4D03F]' : idx === 1 ? 'from-gray-400 to-gray-500' : 'from-[#CD7F32] to-[#B87333]'} rounded-full mx-auto mb-4 flex items-center justify-center text-2xl shadow-lg`}>
                      {place?.avatar || (idx === 0 ? "👑" : idx === 1 ? "⭐" : "💫")}
                    </div>
                    <h3 className="font-bold text-[#2D2A2E]">{place?.name || "Awaiting Partner"}</h3>
                    <p className="text-sm text-[#5A5A5A] mb-2">@{place?.handle || "---"}</p>
                    <div className={`${idx === 0 ? 'bg-[#D4AF37]/20' : idx === 1 ? 'bg-gray-100' : 'bg-[#CD7F32]/10'} rounded-lg py-2 px-4`}>
                      <p className={`text-xl font-bold ${prizes.text}`}>{place?.referrals || 0}</p>
                      <p className="text-xs text-[#5A5A5A]">Referral Loops</p>
                    </div>
                    <p className={`${prizes.text} font-medium mt-3`}>${prizes.prize} Bonus</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="font-display text-3xl font-bold text-[#2D2A2E] mb-4">Why Partner With ReRoots?</h2>
          </div>
          
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-[#FDF9F9] rounded-xl p-6 text-center hover:shadow-lg transition-shadow border border-[#F8A5B8]/20">
              <div className="w-14 h-14 bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                <DollarSign className="h-7 w-7 text-[#2D2A2E]" />
              </div>
              <h3 className="font-bold text-[#2D2A2E] mb-2">Premium Commission</h3>
              <p className="text-[#5A5A5A] text-sm">Earn {inf.commission_rate || 15}% on every sale</p>
            </div>
            <div className="bg-[#FDF9F9] rounded-xl p-6 text-center hover:shadow-lg transition-shadow border border-[#F8A5B8]/20">
              <div className="w-14 h-14 bg-gradient-to-br from-[#F8A5B8] to-[#ffb6c1] rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                <Gift className="h-7 w-7 text-white" />
              </div>
              <h3 className="font-bold text-[#2D2A2E] mb-2">Exclusive Discounts</h3>
              <p className="text-[#5A5A5A] text-sm">Give followers {inf.customer_discount_value || 20}% off</p>
            </div>
            <div className="bg-[#FDF9F9] rounded-xl p-6 text-center hover:shadow-lg transition-shadow border border-[#F8A5B8]/20">
              <div className="w-14 h-14 bg-gradient-to-br from-green-400 to-green-500 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                <Package className="h-7 w-7 text-white" />
              </div>
              <h3 className="font-bold text-[#2D2A2E] mb-2">Free Products</h3>
              <p className="text-[#5A5A5A] text-sm">Receive product samples</p>
            </div>
          </div>
        </div>
      </section>

      {/* Application Form */}
      <section id="apply-form" className="py-16 bg-[#FAF8F5]">
        <div className="max-w-2xl mx-auto px-6">
          <Card className="border-0 shadow-xl overflow-hidden">
            <div className="bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] p-4 text-center">
              <h2 className="text-[#2D2A2E] font-bold text-xl">Gold Partner Application</h2>
            </div>
            <CardHeader className="text-center pb-2">
              <CardTitle className="font-display text-2xl">Apply for Gold Status</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-4">
                  <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                    <User className="h-4 w-4 text-[#F8A5B8]" />
                    Personal Information
                  </h3>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label>Full Name *</Label>
                      <Input value={formData.full_name} onChange={(e) => setFormData({...formData, full_name: e.target.value})} required />
                    </div>
                    <div>
                      <Label>Email *</Label>
                      <Input type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} required />
                    </div>
                    <div>
                      <Label>Date of Birth *</Label>
                      <Input 
                        type="date" 
                        value={formData.date_of_birth} 
                        onChange={(e) => setFormData({...formData, date_of_birth: e.target.value})} 
                        max={new Date(new Date().setFullYear(new Date().getFullYear() - 13)).toISOString().split('T')[0]}
                        required 
                      />
                      <p className="text-xs text-gray-500 mt-1">Must be at least 13 years old</p>
                    </div>
                    <div>
                      <Label>Phone</Label>
                      <Input value={formData.phone} onChange={(e) => setFormData({...formData, phone: e.target.value})} />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Country</Label>
                      <Select value={formData.country} onValueChange={(v) => setFormData({...formData, country: v})}>
                        <SelectTrigger className="w-full"><SelectValue placeholder="Select country" /></SelectTrigger>
                        <SelectContent>
                          {["Canada", "United States", "United Kingdom", "Australia", "India", "Other"].map(c => (
                            <SelectItem key={c} value={c}>{c}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                <Separator />

                <div className="space-y-4">
                  <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                    <Instagram className="h-4 w-4 text-[#F8A5B8]" />
                    Social Media
                  </h3>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <Label>Primary Platform *</Label>
                      <Select value={formData.primary_platform} onValueChange={(v) => setFormData({...formData, primary_platform: v})}>
                        <SelectTrigger className="w-full"><SelectValue placeholder="Select platform" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="instagram">Instagram</SelectItem>
                          <SelectItem value="tiktok">TikTok</SelectItem>
                          <SelectItem value="youtube">YouTube</SelectItem>
                          <SelectItem value="twitter">Twitter/X</SelectItem>
                          <SelectItem value="blog">Blog/Website</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Username *</Label>
                      <Input value={formData.social_handle} onChange={(e) => setFormData({...formData, social_handle: e.target.value})} required />
                    </div>
                    <div>
                      <Label>Follower Count *</Label>
                      <Input type="number" value={formData.follower_count} onChange={(e) => setFormData({...formData, follower_count: e.target.value})} required />
                    </div>
                    <div>
                      <Label>Engagement Rate (%)</Label>
                      <Input type="number" step="0.1" value={formData.engagement_rate} onChange={(e) => setFormData({...formData, engagement_rate: e.target.value})} />
                    </div>
                    <div className="md:col-span-2">
                      <Label>Profile URL *</Label>
                      <Input type="url" value={formData.profile_url} onChange={(e) => setFormData({...formData, profile_url: e.target.value})} required />
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Connect Social Media Accounts - NEW SECTION */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                    <Instagram className="h-4 w-4 text-[#F8A5B8]" />
                    Connect Your Social Media *
                  </h3>
                  <p className="text-sm text-gray-500">Connect at least one Instagram or TikTok account to continue</p>
                  
                  <div className="grid grid-cols-2 gap-4">
                    {/* Instagram Connect */}
                    <div 
                      onClick={() => !formData.instagram_connected && connectSocialMedia('instagram')}
                      className={`relative p-4 rounded-xl border-2 cursor-pointer transition-all ${
                        formData.instagram_connected 
                          ? 'border-green-500 bg-green-50' 
                          : 'border-dashed border-pink-300 hover:border-pink-500 hover:bg-pink-50'
                      }`}
                    >
                      {formData.instagram_connected && (
                        <div className="absolute -top-2 -right-2 bg-green-500 rounded-full p-1">
                          <Check className="h-3 w-3 text-white" />
                        </div>
                      )}
                      <div className="flex flex-col items-center gap-2">
                        <div className="w-12 h-12 bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500 rounded-xl flex items-center justify-center">
                          <Instagram className="h-6 w-6 text-white" />
                        </div>
                        <span className="font-medium text-sm">Instagram</span>
                        {formData.instagram_connected ? (
                          <span className="text-xs text-green-600">@{formData.instagram_username}</span>
                        ) : (
                          <span className="text-xs text-gray-500">Click to connect</span>
                        )}
                      </div>
                    </div>
                    
                    {/* TikTok Connect */}
                    <div 
                      onClick={() => !formData.tiktok_connected && connectSocialMedia('tiktok')}
                      className={`relative p-4 rounded-xl border-2 cursor-pointer transition-all ${
                        formData.tiktok_connected 
                          ? 'border-green-500 bg-green-50' 
                          : 'border-dashed border-gray-300 hover:border-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      {formData.tiktok_connected && (
                        <div className="absolute -top-2 -right-2 bg-green-500 rounded-full p-1">
                          <Check className="h-3 w-3 text-white" />
                        </div>
                      )}
                      <div className="flex flex-col items-center gap-2">
                        <div className="w-12 h-12 bg-black rounded-xl flex items-center justify-center">
                          <svg className="h-6 w-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z"/>
                          </svg>
                        </div>
                        <span className="font-medium text-sm">TikTok</span>
                        {formData.tiktok_connected ? (
                          <span className="text-xs text-green-600">@{formData.tiktok_username}</span>
                        ) : (
                          <span className="text-xs text-gray-500">Click to connect</span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {!formData.instagram_connected && !formData.tiktok_connected && (
                    <p className="text-xs text-orange-600 flex items-center gap-1">
                      <Shield className="h-3 w-3" />
                      Connect at least one account to verify your reach
                    </p>
                  )}
                </div>

                <Separator />

                <div className="space-y-4">
                  <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                    <MessageCircle className="h-4 w-4 text-[#F8A5B8]" />
                    Tell Us More
                  </h3>
                  <div>
                    <Label>Why partner with ReRoots? *</Label>
                    <Textarea value={formData.why_partner} onChange={(e) => setFormData({...formData, why_partner: e.target.value})} rows={3} required />
                  </div>
                  <div>
                    <Label>Content Ideas</Label>
                    <Textarea value={formData.content_ideas} onChange={(e) => setFormData({...formData, content_ideas: e.target.value})} rows={2} />
                  </div>
                  <div>
                    <Label>Previous Brands</Label>
                    <Input value={formData.previous_brands} onChange={(e) => setFormData({...formData, previous_brands: e.target.value})} />
                  </div>
                </div>

                <Separator />

                {/* Terms & Conditions - NEW SECTION */}
                <div className="space-y-4 bg-gray-50 p-4 rounded-xl">
                  <h3 className="font-semibold text-[#2D2A2E] flex items-center gap-2">
                    <Shield className="h-4 w-4 text-[#F8A5B8]" />
                    Terms & Agreements
                  </h3>
                  
                  <div className="space-y-3">
                    <label className="flex items-start gap-3 cursor-pointer group">
                      <input 
                        type="checkbox" 
                        checked={formData.agree_terms}
                        onChange={(e) => setFormData({...formData, agree_terms: e.target.checked})}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-[#D4AF37] focus:ring-[#D4AF37]"
                      />
                      <span className="text-sm text-gray-700 group-hover:text-gray-900">
                        I agree to the <a href="/terms" target="_blank" className="text-[#D4AF37] underline hover:text-[#B8960F]">Terms of Use</a> *
                      </span>
                    </label>
                    
                    <label className="flex items-start gap-3 cursor-pointer group">
                      <input 
                        type="checkbox" 
                        checked={formData.agree_privacy}
                        onChange={(e) => setFormData({...formData, agree_privacy: e.target.checked})}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-[#D4AF37] focus:ring-[#D4AF37]"
                      />
                      <span className="text-sm text-gray-700 group-hover:text-gray-900">
                        I have read and understood the <a href="/privacy" target="_blank" className="text-[#D4AF37] underline hover:text-[#B8960F]">Privacy Policy</a> *
                      </span>
                    </label>
                    
                    <label className="flex items-start gap-3 cursor-pointer group">
                      <input 
                        type="checkbox" 
                        checked={formData.agree_marketing}
                        onChange={(e) => setFormData({...formData, agree_marketing: e.target.checked})}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-[#D4AF37] focus:ring-[#D4AF37]"
                      />
                      <span className="text-sm text-gray-700 group-hover:text-gray-900">
                        I agree to receive news, updates, and promotional offers from ReRoots
                      </span>
                    </label>
                  </div>
                  
                  {(!formData.agree_terms || !formData.agree_privacy) && (
                    <p className="text-xs text-orange-600">* Required to proceed</p>
                  )}
                </div>

                <Button 
                  type="submit" 
                  className={`w-full font-bold py-6 text-lg ${
                    formData.partner_tier === 'oroe' 
                      ? 'bg-gradient-to-r from-[#1A1A1A] to-[#D4AF37] text-white' 
                      : formData.partner_tier === 'lavela'
                      ? 'bg-gradient-to-r from-[#0D4D4D] to-[#E8C4B8] text-white'
                      : 'bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E]'
                  }`}
                  disabled={submitting || !formData.agree_terms || !formData.agree_privacy || (!formData.instagram_connected && !formData.tiktok_connected)}
                >
                  {submitting ? <><Loader2 className="h-5 w-5 animate-spin mr-2" /> Submitting...</> : `Apply for ${PARTNER_TIERS[formData.partner_tier]?.name || 'Partner'} Status`}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
};

export default BecomePartnerPage;
