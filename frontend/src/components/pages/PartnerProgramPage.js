import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Star, CheckCircle, Users, Gift, Percent, 
  Instagram, Youtube, Twitter, ArrowRight, Sparkles,
  DollarSign, Package, Award, Heart, Phone
} from "lucide-react";
import PhoneInput, { detectUserCountry, getCountryByCode, formatFullPhone } from "@/components/common/PhoneInput";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const PartnerProgramPage = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    instagram: "",
    tiktok: "",
    youtube: "",
    followers: "",
    niche: "",
    message: ""
  });
  const [phoneCountryCode, setPhoneCountryCode] = useState("+1");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // Auto-detect country code on mount
  useEffect(() => {
    const detectedCountry = detectUserCountry();
    const country = getCountryByCode(detectedCountry);
    setPhoneCountryCode(country.phoneCode);
  }, []);

  const benefits = [
    { icon: Percent, title: "Up to 30% Commission", desc: "Earn on every sale from your audience" },
    { icon: Package, title: "Free Products", desc: "Monthly product drops for content creation" },
    { icon: Gift, title: "Exclusive Discounts", desc: "Special codes for your followers" },
    { icon: Award, title: "Early Access", desc: "Be first to try new launches" },
    { icon: DollarSign, title: "Performance Bonuses", desc: "Extra rewards for top performers" },
    { icon: Heart, title: "Brand Collaboration", desc: "Co-create products with us" }
  ];

  const tiers = [
    { 
      name: "Micro Influencer", 
      followers: "1K - 10K", 
      commission: "15%",
      perks: ["Free starter kit", "Personal discount code", "Monthly check-ins"],
      color: "from-cyan-500 to-blue-500"
    },
    { 
      name: "Rising Star", 
      followers: "10K - 50K", 
      commission: "20%",
      perks: ["All Micro perks", "Quarterly product drops", "Featured on our socials"],
      color: "from-purple-500 to-pink-500"
    },
    { 
      name: "Brand Ambassador", 
      followers: "50K+", 
      commission: "30%",
      perks: ["All Rising Star perks", "Priority support", "Co-branded campaigns", "Revenue share options"],
      color: "from-amber-500 to-orange-500"
    }
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.first_name || !formData.last_name || !formData.email) {
      toast.error("Please fill in your first name, last name, and email");
      return;
    }
    
    if (!formData.phone) {
      toast.error("Please enter your phone number");
      return;
    }

    setSubmitting(true);
    try {
      // Format phone with country code and include full_name for compatibility
      const fullPhone = formatFullPhone(phoneCountryCode, formData.phone);
      const payload = {
        ...formData,
        full_name: `${formData.first_name} ${formData.last_name}`.trim(),
        phone: fullPhone,
        phone_country_code: phoneCountryCode
      };
      await axios.post(`${API}/partner-applications`, payload);
      setSubmitted(true);
      toast.success("Application submitted! We'll be in touch within 48 hours.");
    } catch (error) {
      console.error("Error submitting application:", error);
      toast.error("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f0f1a] py-12 px-4">
        <Helmet>
          <title>Application Received | ReRoots Partner Program</title>
        </Helmet>
        <div className="max-w-lg mx-auto text-center">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-r from-green-500 to-emerald-500 flex items-center justify-center">
            <CheckCircle className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-4">Application Received!</h1>
          <p className="text-white/70 mb-8">
            Thank you for your interest in partnering with ReRoots. Our team will review your application and get back to you within 48 hours.
          </p>
          <Button 
            onClick={() => navigate("/")}
            className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
          >
            Back to Home
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f0f1a]">
      <Helmet>
        <title>Partner Program | ReRoots Biotech Skincare</title>
        <meta name="description" content="Join the ReRoots Partner Program. Earn up to 30% commission, get free products, and grow with Canada's leading biotech skincare brand." />
      </Helmet>

      {/* Hero Section */}
      <div className="relative py-16 px-4 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-pink-500/10" />
        <div className="max-w-4xl mx-auto text-center relative">
          <Badge className="mb-4 bg-purple-500/20 text-purple-300 border-purple-500/30">
            <Star className="w-3 h-3 mr-1" /> Influencer Partnership
          </Badge>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Become a ReRoots Partner
          </h1>
          <p className="text-xl text-white/70 mb-8 max-w-2xl mx-auto">
            Join our exclusive partner program and earn while sharing products you love. 
            Get free skincare, exclusive commissions, and grow your brand with us.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <div className="flex items-center gap-2 text-white/80">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span>Up to 30% Commission</span>
            </div>
            <div className="flex items-center gap-2 text-white/80">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span>Free Products</span>
            </div>
            <div className="flex items-center gap-2 text-white/80">
              <CheckCircle className="w-5 h-5 text-green-400" />
              <span>Exclusive Perks</span>
            </div>
          </div>
        </div>
      </div>

      {/* Benefits Grid */}
      <div className="max-w-6xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold text-white text-center mb-8">Partner Benefits</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {benefits.map((benefit, idx) => (
            <Card key={idx} className="bg-white/5 border-white/10 hover:border-purple-500/50 transition-all">
              <CardContent className="p-6 text-center">
                <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <benefit.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="font-bold text-white mb-2">{benefit.title}</h3>
                <p className="text-sm text-white/60">{benefit.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Tiers Section */}
      <div className="max-w-6xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold text-white text-center mb-8">Partnership Tiers</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {tiers.map((tier, idx) => (
            <Card key={idx} className={`bg-gradient-to-br ${tier.color} border-0 relative overflow-hidden`}>
              {idx === 2 && (
                <div className="absolute top-3 right-3">
                  <Badge className="bg-white/20 text-white">Most Popular</Badge>
                </div>
              )}
              <CardContent className="p-6">
                <h3 className="text-xl font-bold text-white mb-1">{tier.name}</h3>
                <p className="text-white/80 text-sm mb-4">{tier.followers} followers</p>
                <div className="text-4xl font-bold text-white mb-4">{tier.commission}</div>
                <p className="text-white/70 text-sm mb-4">Commission Rate</p>
                <ul className="space-y-2">
                  {tier.perks.map((perk, perkIdx) => (
                    <li key={perkIdx} className="flex items-center gap-2 text-white/90 text-sm">
                      <CheckCircle className="w-4 h-4 text-white" />
                      {perk}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Application Form */}
      <div className="max-w-2xl mx-auto px-4 py-12">
        <Card className="bg-white/5 border-white/10">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl text-white">Apply to Partner</CardTitle>
            <CardDescription className="text-white/60">
              Fill out the form below and we'll get back to you within 48 hours
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-white/70 mb-1 block">First Name *</label>
                  <Input
                    placeholder="First name"
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                    required
                    data-testid="partner-first-name"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/70 mb-1 block">Last Name *</label>
                  <Input
                    placeholder="Last name"
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                    required
                    data-testid="partner-last-name"
                  />
                </div>
              </div>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-white/70 mb-1 block">Email *</label>
                  <Input
                    type="email"
                    placeholder="your@email.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                    required
                    data-testid="partner-email"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/70 mb-1 block flex items-center gap-1">
                    <Phone className="w-4 h-4" /> Phone Number *
                  </label>
                  <PhoneInput
                    value={formData.phone}
                    onChange={(val) => setFormData({ ...formData, phone: val })}
                    countryCode={phoneCountryCode}
                    onCountryCodeChange={setPhoneCountryCode}
                    placeholder="Phone number"
                    required
                    darkMode={true}
                    inputClassName="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                    testId="partner-phone"
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm text-white/70 mb-1 block flex items-center gap-1">
                    <Instagram className="w-4 h-4" /> Instagram
                  </label>
                  <Input
                    placeholder="@username"
                    value={formData.instagram}
                    onChange={(e) => setFormData({ ...formData, instagram: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/70 mb-1 block">TikTok</label>
                  <Input
                    placeholder="@username"
                    value={formData.tiktok}
                    onChange={(e) => setFormData({ ...formData, tiktok: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/70 mb-1 block flex items-center gap-1">
                    <Youtube className="w-4 h-4" /> YouTube
                  </label>
                  <Input
                    placeholder="Channel name"
                    value={formData.youtube}
                    onChange={(e) => setFormData({ ...formData, youtube: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-white/70 mb-1 block">Total Followers</label>
                  <Input
                    placeholder="e.g., 15,000"
                    value={formData.followers}
                    onChange={(e) => setFormData({ ...formData, followers: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/70 mb-1 block">Content Niche</label>
                  <Input
                    placeholder="e.g., Skincare, Beauty, Lifestyle"
                    value={formData.niche}
                    onChange={(e) => setFormData({ ...formData, niche: e.target.value })}
                    className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-white/70 mb-1 block">Why do you want to partner with ReRoots?</label>
                <Textarea
                  placeholder="Tell us about yourself and why you're interested..."
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  className="bg-white/10 border-white/20 text-white placeholder:text-white/40 min-h-[100px]"
                />
              </div>

              <Button
                type="submit"
                disabled={submitting}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 h-12 text-lg font-bold"
              >
                {submitting ? "Submitting..." : "Submit Application"}
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Back to Home */}
      <div className="text-center pb-12">
        <Button
          variant="ghost"
          onClick={() => navigate("/")}
          className="text-white/60 hover:text-white"
        >
          ← Back to Home
        </Button>
      </div>
    </div>
  );
};

export default PartnerProgramPage;
