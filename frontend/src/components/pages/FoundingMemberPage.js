import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Dna, Users, Award, Sparkles, Lock, Crown, Gift, 
  ChevronRight, CheckCircle, Star, Zap, FlaskConical,
  MessageSquare, TrendingUp, Share2, Copy, Twitter,
  Instagram, ArrowRight, Shield, Heart, Unlock
} from "lucide-react";
import MilestoneProgress from "../MilestoneProgress";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

const FoundingMemberPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const referrerCode = searchParams.get("ref") || "";
  const fromScan = searchParams.get("from_scan") || "";  // Bio-scan attribution
  const concern = searchParams.get("concern") || "";  // Primary concern from scan
  
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [position, setPosition] = useState(null);
  const [userReferralCode, setUserReferralCode] = useState(null);
  
  // Pricing data - fetched from admin settings (CORRECTED: Single discount, max 30%)
  const [pricing, setPricing] = useState({
    retailValue: 100,
    referralDiscount: 30,  // Single discount, max 30%
    finalPrice: 70.00      // $100 - 30% = $70
  });

  // Fetch pricing from backend on mount
  useEffect(() => {
    const fetchPricing = async () => {
      try {
        const res = await axios.get(`${API}/founding-member/pricing`);
        if (res.data) {
          setPricing({
            retailValue: res.data.retail_value || 100,
            referralDiscount: res.data.referral_discount_percent || 30,
            finalPrice: res.data.final_price || 70
          });
        }
      } catch (error) {
        console.log("Using default pricing");
      }
    };
    fetchPricing();
  }, []);

  // Founding Perks
  const foundingPerks = [
    {
      icon: FlaskConical,
      title: "Lifetime Beta Access",
      description: "Be the first to test new PDRN formulations before they hit the public shop. Your feedback shapes our R&D.",
      highlight: true
    },
    {
      icon: MessageSquare,
      title: "Direct-to-Lab Feedback",
      description: "Monthly surveys where you vote on the next 'Skin Concern' focus. Help us decide: Neck & Décolleté or Hand Longevity?",
      highlight: false
    },
    {
      icon: Lock,
      title: "Grandfathered Pricing",
      description: "Your Founding Member price is locked forever. Even when inflation hits, your discount stays the same.",
      highlight: true
    },
    {
      icon: Crown,
      title: "Priority Access",
      description: "First dibs on limited releases, exclusive bundles, and sold-out products before they're gone.",
      highlight: false
    },
    {
      icon: Users,
      title: "Referral Rewards",
      description: "Invite 3 friends to the Founding Circle, and your next Aura-Gen bottle is on us. No limits.",
      highlight: false
    },
    {
      icon: Star,
      title: "Founding Member Badge",
      description: "Exclusive badge in your account dashboard. Show off your early adopter status.",
      highlight: false
    }
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !name) {
      toast.error("Please enter your name and email");
      return;
    }

    setLoading(true);
    try {
      const res = await axios.post(`${API}/founding-member/join`, {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        referrer_code: referrerCode,
        from_scan: fromScan,  // Pass bio-scan attribution
        concern: concern  // Pass primary concern for remarketing
      });

      if (res.data.success) {
        setPosition(res.data.position);
        setUserReferralCode(res.data.referral_code);
        setSubmitted(true);
        
        // Store for persistence
        localStorage.setItem("founding_member_code", res.data.referral_code);
        localStorage.setItem("founding_member_email", email.trim().toLowerCase());
        
        toast.success("Welcome to the Founding Circle! 🎉");
      }
    } catch (error) {
      if (error.response?.data?.already_member) {
        setPosition(error.response.data.position);
        setUserReferralCode(error.response.data.referral_code);
        setSubmitted(true);
        toast.success("Welcome back, Founding Member!");
      } else {
        toast.error(error.response?.data?.detail || "Something went wrong");
      }
    }
    setLoading(false);
  };

  const shareUrl = `${window.location.origin}/founding-member?ref=${userReferralCode}`;

  const copyReferralLink = () => {
    navigator.clipboard.writeText(shareUrl);
    toast.success("Link copied!");
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0a] via-[#1a1a1a] to-[#0a0a0a]">
      <Helmet>
        <title>Become a Founding Member | ReRoots Aesthetics</title>
        <meta name="description" content="Join the ReRoots Founding Circle. Get lifetime beta access, grandfathered pricing, and exclusive perks. Be part of the biotech skincare revolution." />
        <meta name="keywords" content="ReRoots founding member, PDRN skincare membership, biotech skincare community, early access skincare" />
        <link rel="canonical" href="https://reroots.ca/founding-member" />
      </Helmet>

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 px-6 overflow-hidden">
        {/* Background Effects */}
        <div className="absolute inset-0 overflow-hidden">
          <div 
            className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl"
            style={{ background: "radial-gradient(circle, rgba(212, 175, 55, 0.1) 0%, transparent 70%)" }}
          />
          <div 
            className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full blur-3xl"
            style={{ background: "radial-gradient(circle, rgba(248, 165, 184, 0.1) 0%, transparent 70%)" }}
          />
        </div>

        <div className="max-w-4xl mx-auto text-center relative z-10">
          {/* Scan Attribution Banner */}
          {fromScan && (
            <div className="mb-6 bg-gradient-to-r from-cyan-500/20 to-purple-500/20 border border-cyan-500/40 rounded-2xl p-4 max-w-xl mx-auto">
              <div className="flex items-center justify-center gap-2 text-cyan-300">
                <Dna className="w-5 h-5" />
                <span className="font-semibold">Bio-Age Scan Verified</span>
              </div>
              <p className="text-white/70 text-sm mt-2">
                Your diagnostic subsidy has been applied. Claim your <span className="font-bold text-cyan-200">$30 off</span> below.
              </p>
            </div>
          )}
          
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-[#D4AF37]/10 border border-[#D4AF37]/30 text-[#D4AF37] px-4 py-2 rounded-full text-sm font-medium mb-8">
            <Crown className="w-4 h-4" />
            Exclusive Membership
          </div>

          <h1 
            className="text-4xl md:text-5xl lg:text-6xl font-semibold text-white mb-6 leading-tight"
            style={{ fontFamily: '"Playfair Display", serif' }}
          >
            Join the <span className="text-[#D4AF37]">Founding Circle</span>
          </h1>
          
          <p className="text-lg md:text-xl text-white/60 max-w-2xl mx-auto leading-relaxed mb-8">
            You're not just buying a serum. You're joining the inner circle of biotech skincare pioneers. 
            Shape the future of <span className="text-[#F8A5B8]">Skin Longevity</span> with us.
          </p>

          {/* Trust Indicators */}
          <div className="flex flex-wrap items-center justify-center gap-6 text-white/40 text-sm">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#D4AF37]" />
              <span>GMP Certified</span>
            </div>
            <div className="flex items-center gap-2">
              <Dna className="w-4 h-4 text-[#D4AF37]" />
              <span>Biotech Grade PDRN</span>
            </div>
            <div className="flex items-center gap-2">
              <span>🇨🇦</span>
              <span>Made in Canada</span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-12 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-start">
            
            {/* Left: Perks */}
            <div>
              <h2 className="text-2xl font-semibold text-white mb-8" style={{ fontFamily: '"Playfair Display", serif' }}>
                Founding Member <span className="text-[#D4AF37]">Perks</span>
              </h2>
              
              <div className="space-y-4">
                {foundingPerks.map((perk, idx) => (
                  <div 
                    key={idx}
                    className={`rounded-xl p-5 transition-all ${
                      perk.highlight 
                        ? 'bg-gradient-to-r from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/20' 
                        : 'bg-white/5 border border-white/5 hover:border-white/10'
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <div 
                        className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          perk.highlight ? 'bg-[#D4AF37]/20' : 'bg-white/10'
                        }`}
                      >
                        <perk.icon className={`w-5 h-5 ${perk.highlight ? 'text-[#D4AF37]' : 'text-white/70'}`} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-white mb-1">{perk.title}</h3>
                        <p className="text-white/50 text-sm leading-relaxed">{perk.description}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Signup Form or Success */}
            <div className="lg:sticky lg:top-8">
              {!submitted ? (
                <div 
                  className="rounded-2xl overflow-hidden"
                  style={{
                    background: "linear-gradient(145deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%)",
                    border: "1px solid rgba(212, 175, 55, 0.2)",
                    boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
                  }}
                >
                  {/* Pricing Breakdown - CORRECTED: Single discount, no stacking */}
                  <div 
                    className="p-6 border-b border-white/5"
                    style={{ background: "linear-gradient(135deg, rgba(212, 175, 55, 0.05) 0%, transparent 100%)" }}
                  >
                    <p className="text-[#D4AF37] text-xs uppercase tracking-wider font-medium mb-4">
                      Founding Member Pricing
                    </p>
                    <div className="space-y-3 text-sm">
                      <div className="flex justify-between">
                        <span className="text-white/50">Retail Value</span>
                        <span className="text-white line-through">${pricing.retailValue.toFixed(2)} CAD</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/50">
                          {referrerCode ? "Influencer Referral Discount" : "Founding Member Discount"}
                        </span>
                        <span className="text-green-400">-{pricing.referralDiscount}%</span>
                      </div>
                      {referrerCode && (
                        <div className="bg-[#F8A5B8]/10 rounded-lg p-2 border border-[#F8A5B8]/20">
                          <p className="text-[#F8A5B8] text-xs text-center">
                            <Gift className="w-3 h-3 inline mr-1" />
                            Referred by: <span className="font-mono font-bold">{referrerCode}</span>
                          </p>
                        </div>
                      )}
                      <div className="border-t border-white/10 pt-3 flex justify-between items-center">
                        <span className="text-white font-medium">Final Founding Member Entry</span>
                        <span 
                          className="text-2xl font-bold"
                          style={{
                            background: "linear-gradient(135deg, #D4AF37 0%, #E8C84B 100%)",
                            WebkitBackgroundClip: "text",
                            WebkitTextFillColor: "transparent"
                          }}
                          data-testid="founding-final-price"
                        >
                          ${pricing.finalPrice.toFixed(2)} CAD
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Form */}
                  <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                      <label className="text-white/50 text-xs uppercase tracking-wider mb-2 block">Full Name</label>
                      <Input
                        type="text"
                        placeholder="Your name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12"
                        data-testid="founding-name"
                      />
                    </div>
                    <div>
                      <label className="text-white/50 text-xs uppercase tracking-wider mb-2 block">Email Address</label>
                      <Input
                        type="email"
                        placeholder="your@email.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12"
                        data-testid="founding-email"
                      />
                    </div>
                    
                    <Button
                      type="submit"
                      disabled={loading}
                      className="w-full h-12 rounded-lg font-semibold text-base"
                      style={{
                        background: "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
                        color: "#0a0a0a"
                      }}
                      data-testid="join-founding-btn"
                    >
                      {loading ? "Securing Your Spot..." : "Join the Founding Circle"}
                    </Button>
                    
                    <p className="text-white/30 text-xs text-center">
                      Limited spots available. No spam, ever.
                    </p>
                  </form>
                </div>
              ) : (
                /* Success State - Viral Loop */
                <div 
                  className="rounded-2xl overflow-hidden text-center"
                  style={{
                    background: "linear-gradient(145deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%)",
                    border: "1px solid rgba(212, 175, 55, 0.3)",
                    boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
                  }}
                >
                  {/* Success Header */}
                  <div 
                    className="p-8"
                    style={{ background: "linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, transparent 100%)" }}
                  >
                    <div 
                      className="w-20 h-20 rounded-full flex flex-col items-center justify-center mx-auto mb-4"
                      style={{
                        background: "linear-gradient(135deg, rgba(212, 175, 55, 0.3) 0%, rgba(212, 175, 55, 0.1) 100%)",
                        border: "2px solid rgba(212, 175, 55, 0.5)"
                      }}
                    >
                      <Crown className="w-8 h-8 text-[#D4AF37]" />
                    </div>
                    <h3 className="text-2xl font-semibold text-white mb-2" style={{ fontFamily: '"Playfair Display", serif' }}>
                      Welcome to the Circle!
                    </h3>
                    <p className="text-white/50">
                      You're Founding Member <span className="text-[#D4AF37] font-bold">#{position}</span>
                    </p>
                  </div>

                  {/* Your Referral Link */}
                  <div className="p-6 border-t border-white/5">
                    {/* Milestone Unlock Progress */}
                    <div className="mb-6">
                      <MilestoneProgress 
                        referralCode={userReferralCode}
                        showShareLink={false}
                      />
                    </div>

                    <p className="text-white/70 text-sm mb-4">
                      <Gift className="w-4 h-4 inline mr-1 text-[#F8A5B8]" />
                      Refer 10 verified friends to <span className="text-[#D4AF37] font-semibold">unlock 30% OFF forever</span>!
                    </p>
                    
                    <div className="bg-white/5 rounded-lg p-4 mb-4">
                      <p className="text-white/50 text-xs uppercase tracking-wider mb-2">Your Referral Link</p>
                      <div className="flex gap-2">
                        <Input
                          readOnly
                          value={shareUrl}
                          className="bg-white/5 border-white/10 text-white text-sm font-mono"
                        />
                        <Button onClick={copyReferralLink} variant="outline" className="border-white/20 text-white hover:bg-white/10">
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>

                    {/* Share Buttons */}
                    <div className="flex gap-3 justify-center">
                      <Button
                        onClick={() => window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent("I just joined the @ReRootsCA Founding Circle! Join me and get exclusive biotech skincare perks:")}&url=${encodeURIComponent(shareUrl)}`, '_blank')}
                        className="bg-[#1DA1F2] hover:bg-[#1a8cd8] text-white"
                      >
                        <Twitter className="w-4 h-4 mr-2" />
                        Share
                      </Button>
                      <Button
                        onClick={() => window.open(`https://www.instagram.com/`, '_blank')}
                        className="bg-gradient-to-r from-[#833AB4] via-[#FD1D1D] to-[#FCAF45] text-white"
                      >
                        <Instagram className="w-4 h-4 mr-2" />
                        Share
                      </Button>
                    </div>

                    {/* CTA */}
                    <div className="mt-6 pt-6 border-t border-white/5">
                      <Link
                        to="/Bio-Age-Repair-Scan"
                        className="inline-flex items-center gap-2 text-[#D4AF37] hover:text-[#e8c84b] font-medium"
                      >
                        Take the Bio-Age Quiz
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="py-16 px-6 border-t border-white/5">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-white/30 text-sm uppercase tracking-wider mb-8">Trusted by Skincare Enthusiasts</p>
          <div className="flex flex-wrap justify-center gap-8 items-center">
            <div className="text-center">
              <p className="text-3xl font-bold text-[#D4AF37]">150+</p>
              <p className="text-white/50 text-sm">Founding Members</p>
            </div>
            <div className="w-px h-12 bg-white/10" />
            <div className="text-center">
              <p className="text-3xl font-bold text-[#D4AF37]">17%</p>
              <p className="text-white/50 text-sm">Active Complex</p>
            </div>
            <div className="w-px h-12 bg-white/10" />
            <div className="text-center">
              <p className="text-3xl font-bold text-[#D4AF37]">🇨🇦</p>
              <p className="text-white/50 text-sm">Made in Canada</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default FoundingMemberPage;
