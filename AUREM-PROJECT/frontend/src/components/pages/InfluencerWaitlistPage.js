import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams, useParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Sparkles, CheckCircle, ArrowRight, Shield, Users, 
  Lock, Unlock, ChevronRight, Gift, Target
} from "lucide-react";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const InfluencerWaitlistPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { partnerCode } = useParams();
  const refCode = partnerCode || searchParams.get("ref") || "";
  
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [influencer, setInfluencer] = useState(null);
  const [userReferralCode, setUserReferralCode] = useState("");

  // Fetch influencer info
  useEffect(() => {
    if (refCode) {
      axios.get(`${API}/partner/info/${refCode.toUpperCase()}`)
        .then(res => {
          setInfluencer(res.data);
        })
        .catch(() => {
          // Use default if not found
          setInfluencer({
            name: "Our Partner",
            full_name: "Our Partner",
            photo_url: null
          });
        });
    }
  }, [refCode]);

  const influencerName = influencer?.full_name || influencer?.name || "Our Partner";

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error("Please enter your email");
      return;
    }
    
    setLoading(true);
    try {
      const res = await axios.post(`${API}/waitlist`, {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        referrer_code: refCode.toUpperCase(),
        source: `influencer_${refCode}`
      });
      
      if (res.data.referral_code) {
        setUserReferralCode(res.data.referral_code);
        localStorage.setItem("referral_code", res.data.referral_code);
        localStorage.setItem("waitlist_email", email.trim().toLowerCase());
        localStorage.setItem("referred_by", refCode.toUpperCase());
      }
      
      setSubmitted(true);
      toast.success("Protocol Access Confirmed! 🎉");
      
    } catch (error) {
      if (error.response?.data?.detail?.includes("already")) {
        toast.info("You're already registered!");
        setSubmitted(true);
        if (error.response?.data?.referral_code) {
          setUserReferralCode(error.response.data.referral_code);
        }
      } else if (error.response?.data?.detail?.includes("Too many")) {
        toast.error("Too many signups detected. Please try again later.");
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Helmet>
        <title>Founding Member Protocol | Invited by {influencerName} | ReRoots</title>
        <meta name="description" content={`You've been invited by ${influencerName} to join the ReRoots Founding Member Protocol with exclusive pricing.`} />
      </Helmet>

      {/* PERSONALIZED WELCOME BANNER - Glassmorphism */}
      <div 
        className="fixed top-0 left-0 right-0 z-50"
        style={{
          background: "rgba(45, 42, 46, 0.85)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(212, 175, 55, 0.2)"
        }}
      >
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-center gap-3">
          {/* Influencer Photo */}
          {influencer?.photo_url && (
            <img 
              src={influencer.photo_url} 
              alt={influencerName}
              className="w-8 h-8 rounded-full border-2 border-[#D4AF37] object-cover"
            />
          )}
          <p className="text-sm text-white/80 text-center">
            <span className="text-[#D4AF37]">Welcome.</span> You've been invited by{" "}
            <span className="font-semibold text-white">{influencerName}</span>{" "}
            to join the ReRoots Founding Member Protocol.{" "}
            <span className="text-[#F8A5B8]">Exclusive pricing is currently available for your profile.</span>
          </p>
        </div>
      </div>

      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-40 left-[10%] w-96 h-96 rounded-full bg-[#D4AF37]/5 blur-[100px]" />
        <div className="absolute bottom-20 right-[10%] w-80 h-80 rounded-full bg-[#F8A5B8]/5 blur-[100px]" />
        <div 
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(rgba(212, 175, 55, 0.5) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(212, 175, 55, 0.5) 1px, transparent 1px)`,
            backgroundSize: "60px 60px"
          }}
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 pt-20 min-h-screen flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl">
          
          {!submitted ? (
            <>
              {/* PRE-SIGNUP: Entry Form */}
              
              {/* Badge */}
              <div className="flex justify-center mb-6">
                <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] px-4 py-1.5">
                  <Shield className="w-3 h-3 mr-2" />
                  FOUNDING MEMBER PROTOCOL
                </Badge>
              </div>

              {/* Main Headline */}
              <h1 
                className="text-center text-4xl md:text-5xl font-bold mb-4"
                style={{ fontFamily: '"Playfair Display", serif' }}
              >
                Secure Your{" "}
                <span 
                  style={{
                    background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent"
                  }}
                >
                  Subsidized Entry.
                </span>
              </h1>

              {/* Sub-headline */}
              <p className="text-center text-white/70 text-lg mb-10 max-w-xl mx-auto leading-relaxed">
                Through our partnership with <span className="text-white font-semibold">{influencerName}</span>, 
                you have been granted access to the ReRoots PDRN Launch. By joining the waitlist today, 
                you lock in your Founding Member price of <span className="text-[#F8A5B8] font-bold">$100</span>—with 
                the opportunity to unlock the 30% Founding Member discount for a final price of{" "}
                <span className="text-[#D4AF37] font-bold">$70</span>.
              </p>

              {/* Entry Form Card */}
              <Card 
                className="border-0 overflow-hidden"
                style={{
                  background: "linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)",
                  border: "1px solid rgba(212, 175, 55, 0.2)"
                }}
              >
                <div className="h-1 bg-gradient-to-r from-transparent via-[#D4AF37] to-transparent" />
                <CardContent className="p-8">
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-4">
                      <Input
                        type="text"
                        placeholder="Your name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 focus:border-[#D4AF37]"
                      />
                      <Input
                        type="email"
                        placeholder="Email address"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 focus:border-[#D4AF37]"
                      />
                    </div>
                    
                    <Button
                      type="submit"
                      disabled={loading}
                      className="w-full h-14 rounded-lg text-lg font-bold"
                      style={{
                        background: "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
                        color: "#0a0a0a"
                      }}
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          Securing Access...
                        </span>
                      ) : (
                        <span className="flex items-center justify-center gap-2">
                          CLAIM MY PROTOCOL ACCESS
                          <ArrowRight className="w-5 h-5" />
                        </span>
                      )}
                    </Button>
                  </form>

                  {/* Trust Indicators */}
                  <div className="mt-6 flex items-center justify-center gap-6 text-white/30 text-xs">
                    <span className="flex items-center gap-1">
                      <Shield className="w-3 h-3" /> Secure
                    </span>
                    <span className="flex items-center gap-1">
                      <Sparkles className="w-3 h-3" /> Limited Spots
                    </span>
                    <span className="flex items-center gap-1">
                      <Gift className="w-3 h-3" /> Exclusive Pricing
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Price Preview */}
              <div className="mt-8 text-center">
                <p className="text-white/40 text-xs mb-2">FOUNDING MEMBER PRICING</p>
                <div className="flex items-center justify-center gap-4">
                  <span className="text-white/40 line-through">$100</span>
                  <ChevronRight className="w-4 h-4 text-white/20" />
                  <span className="text-[#D4AF37] font-bold text-xl">$70</span>
                </div>
                <p className="text-white/30 text-xs mt-2">Unlock the 30% discount with 10 referrals</p>
              </div>
            </>
          ) : (
            <>
              {/* POST-SIGNUP: Welcome & Mission */}
              
              <div className="text-center mb-8">
                <div 
                  className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
                  style={{ 
                    background: "linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.1) 100%)",
                    border: "2px solid #D4AF37"
                  }}
                >
                  <CheckCircle className="w-10 h-10 text-[#D4AF37]" />
                </div>
                
                <h2 
                  className="text-3xl md:text-4xl font-bold mb-3"
                  style={{ fontFamily: '"Playfair Display", serif' }}
                >
                  Welcome to the Protocol,{" "}
                  <span className="text-[#D4AF37]">{name || "Founding Member"}</span>.
                </h2>
                
                <p className="text-white/60 max-w-md mx-auto">
                  Your entry is confirmed. To honor our partnership with{" "}
                  <span className="text-white">{influencerName}</span>, we are offering you the chance to 
                  secure the <span className="text-[#D4AF37]">Deepest Founding Price</span> in our history.
                </p>
              </div>

              {/* The Logic Box */}
              <Card 
                className="border-0 overflow-hidden mb-8"
                style={{
                  background: "linear-gradient(145deg, rgba(45, 42, 46, 0.9) 0%, rgba(26, 24, 25, 0.9) 100%)",
                  border: "1px solid rgba(212, 175, 55, 0.3)"
                }}
              >
                <div className="h-1 bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37]" />
                <CardContent className="p-8">
                  <h3 className="text-center text-lg font-bold text-white mb-6 flex items-center justify-center gap-2">
                    <Target className="w-5 h-5 text-[#D4AF37]" />
                    YOUR REFERRAL MISSION
                  </h3>
                  
                  <div className="space-y-4">
                    {/* Current Price */}
                    <div className="flex justify-between items-center p-4 bg-white/5 rounded-lg">
                      <div className="flex items-center gap-3">
                        <Lock className="w-5 h-5 text-[#F8A5B8]" />
                        <span className="text-white/70">Current Price</span>
                      </div>
                      <span className="text-2xl font-bold text-[#F8A5B8]">$37.50</span>
                    </div>
                    
                    {/* Mission */}
                    <div className="flex justify-between items-center p-4 bg-white/5 rounded-lg">
                      <div className="flex items-center gap-3">
                        <Users className="w-5 h-5 text-[#D4AF37]" />
                        <span className="text-white/70">Your Mission</span>
                      </div>
                      <span className="text-white font-medium">Invite 10 colleagues to the ReRoots Waitlist</span>
                    </div>
                    
                    {/* Reward */}
                    <div className="flex justify-between items-center p-4 bg-[#D4AF37]/10 rounded-lg border border-[#D4AF37]/30">
                      <div className="flex items-center gap-3">
                        <Unlock className="w-5 h-5 text-[#D4AF37]" />
                        <span className="text-white/70">The Reward</span>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-bold text-[#D4AF37]">$70</span>
                        <span className="text-white/50 text-sm ml-1">(+ Tax)</span>
                      </div>
                    </div>
                  </div>
                  
                  <p className="text-center text-white/40 text-sm mt-6">
                    Your price instantly drops once your 10th referral is verified.
                  </p>
                </CardContent>
              </Card>

              {/* CTA to Mission Control */}
              <Button 
                className="w-full h-14 text-lg font-bold"
                style={{
                  background: "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
                  color: "#0a0a0a"
                }}
                onClick={() => navigate(`/mission-control?code=${userReferralCode}`)}
              >
                <Target className="w-5 h-5 mr-2" />
                GO TO MISSION CONTROL
                <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
              
              <p className="text-center text-white/30 text-xs mt-4">
                Get your unique referral link and start sharing
              </p>
            </>
          )}

          {/* Legal Disclaimer */}
          <div className="mt-10 text-center">
            <p className="text-white/20 text-[10px] leading-relaxed max-w-lg mx-auto">
              *Founding Member Beta Pricing is a one-time subsidy for the first 1,000 units to establish 
              Canadian skin-resilience case studies. Referrals must be verified to count toward your goal.
            </p>
          </div>

          {/* Footer */}
          <div className="mt-8 text-center">
            <p className="text-white/20 text-xs">
              ReRoots · Canadian Biotech Skincare · Est. 2025
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InfluencerWaitlistPage;
