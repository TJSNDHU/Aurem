import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sparkles, CheckCircle, ArrowRight, Shield, Beaker, Gift, Eye } from "lucide-react";
import MathCaptcha from "@/components/MathCaptcha";
import PhoneInput, { detectUserCountry, getCountryByCode, formatFullPhone } from "@/components/common/PhoneInput";

// Dynamic API URL for custom domains
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const API = getBackendUrl() + "/api";

const WaitlistPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const referrerCode = searchParams.get("ref") || "";
  
  // UTM tracking parameters
  const utmSource = searchParams.get("utm_source") || "";
  const utmMedium = searchParams.get("utm_medium") || "";
  const utmCampaign = searchParams.get("utm_campaign") || "";
  const utmContent = searchParams.get("utm_content") || "";
  
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [phoneCountryCode, setPhoneCountryCode] = useState("+1");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [referrer, setReferrer] = useState(null);
  const [captchaVerified, setCaptchaVerified] = useState(false);
  const [position, setPosition] = useState(null);
  const [userReferralCode, setUserReferralCode] = useState(null);
  
  // Preview mode state
  const [isPreview, setIsPreview] = useState(false);
  const [previewContent, setPreviewContent] = useState(null);

  // Auto-detect country code on mount
  useEffect(() => {
    const detectedCountry = detectUserCountry();
    const country = getCountryByCode(detectedCountry);
    setPhoneCountryCode(country.phoneCode);
  }, []);

  // Check for preview data
  useEffect(() => {
    const previewData = sessionStorage.getItem('preview_waitlist_page');
    if (previewData) {
      try {
        const parsed = JSON.parse(previewData);
        if (parsed._isPreview && Date.now() - parsed._timestamp < 5 * 60 * 1000) {
          setPreviewContent(parsed);
          setIsPreview(true);
          // Clear the preview data after use - use setTimeout to handle React StrictMode double-invocation
          setTimeout(() => {
            sessionStorage.removeItem('preview_waitlist_page');
          }, 100);
        }
      } catch (e) {
        console.error('Invalid preview data:', e);
      }
    }
  }, []);

  // Fetch referrer info if ref code is present
  useEffect(() => {
    if (referrerCode) {
      axios.get(`${API}/referral/status/${referrerCode}`)
        .then(res => {
          setReferrer(res.data);
        })
        .catch(() => {
          // Silent fail - just show generic page
        });
    }
  }, [referrerCode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error("Please enter your email");
      return;
    }
    
    if (!phone) {
      toast.error("Please enter your phone number");
      return;
    }
    
    if (!captchaVerified) {
      toast.error("Please solve the math problem to verify you're human");
      return;
    }
    
    setLoading(true);
    try {
      // Determine source based on UTM or referrer
      let source = "waitlist_page";
      if (utmSource) {
        source = utmSource === "reddit" ? `reddit:${utmMedium || "unknown"}` : utmSource;
      } else if (referrerCode) {
        source = "referral";
      }
      
      // Format full phone number with country code
      const fullPhone = formatFullPhone(phoneCountryCode, phone);
      const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
      
      const res = await axios.post(`${API}/waitlist`, {
        email: email.trim().toLowerCase(),
        name: fullName,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: fullPhone,
        phone_country_code: phoneCountryCode,
        referrer_code: referrerCode,
        source: source,
        utm_source: utmSource,
        utm_medium: utmMedium,
        utm_campaign: utmCampaign,
        utm_content: utmContent
      });
      
      // Store referral code for Mission Control
      if (res.data.referral_code) {
        localStorage.setItem("referral_code", res.data.referral_code);
        localStorage.setItem("waitlist_email", email.trim().toLowerCase());
        if (fullName) localStorage.setItem("waitlist_name", fullName);
        if (referrerCode) localStorage.setItem("referred_by", referrerCode);
        
        // Store position and referral code for display
        setPosition(res.data.position);
        setUserReferralCode(res.data.referral_code);
      }
      
      setSubmitted(true);
      toast.success("You're on the list! 🎉");
      
      // Redirect to Mission Control after 2 seconds
      setTimeout(() => {
        navigate(`/mission-control?code=${res.data.referral_code}`);
      }, 2000);
      
    } catch (error) {
      if (error.response?.data?.detail?.includes("already")) {
        toast.info("You're already on the waitlist!");
        setSubmitted(true);
        // Try to get their existing code
        const existingCode = error.response?.data?.referral_code;
        if (existingCode) {
          localStorage.setItem("referral_code", existingCode);
          setTimeout(() => {
            navigate(`/mission-control?code=${existingCode}`);
          }, 2000);
        }
      } else if (error.response?.data?.detail?.includes("Too many")) {
        toast.error("Too many signups from this location. Please try again later.");
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
    setLoading(false);
  };

  const referrerName = referrer?.name || "a Founding Member";
  
  // Preview content overrides
  const heroTitle = previewContent?.hero?.title || "The Founding Member";
  const heroSubtitle = previewContent?.hero?.subtitle || "Protocol";
  const heroDescription = previewContent?.hero?.description || "Access the future of PDRN Biotech.";
  const heroBadge = previewContent?.hero?.badge_text || "Biotech Research Protocol";
  const ctaButtonText = previewContent?.cta?.button_text || "Request Founding Member Access";

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Preview Banner */}
      {isPreview && (
        <div className="fixed top-0 left-0 right-0 z-[100] bg-gradient-to-r from-amber-500 to-orange-500 text-white py-2 px-4 text-center shadow-lg" data-testid="preview-banner">
          <p className="text-sm font-medium flex items-center justify-center gap-2">
            <Eye className="h-4 w-4" />
            <span>Preview Mode — Changes not saved yet</span>
            <button 
              onClick={() => window.close()}
              className="ml-4 px-3 py-1 bg-white/20 hover:bg-white/30 rounded text-xs font-semibold transition-colors"
            >
              Close Preview
            </button>
          </p>
        </div>
      )}
      
      <Helmet>
        <title>The Founding Member Protocol | ReRoots PDRN Biotech</title>
        <meta name="description" content="Access the future of PDRN Biotech. Limited to the first wave of Canadian researchers. Founding Member Beta Pricing available." />
        <link rel="canonical" href="https://reroots.ca/waitlist" />
      </Helmet>

      {/* Personalized Welcome Banner - Only show when referred */}
      {referrerCode && (
        <div 
          className="fixed top-12 left-0 right-0 z-40"
          style={{
            background: "linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(45, 42, 46, 0.95) 100%)",
            backdropFilter: "blur(12px)",
            borderBottom: "1px solid rgba(212, 175, 55, 0.3)"
          }}
        >
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-center gap-3">
            <Gift className="w-4 h-4 text-[#D4AF37]" />
            <p className="text-sm text-white/90 text-center">
              <span className="text-[#D4AF37] font-semibold">Welcome!</span> You've been invited by{" "}
              <span className="font-bold text-white">{referrerName}</span>{" "}
              to join the ReRoots Founding Member Protocol.{" "}
              <span className="text-[#F8A5B8] font-medium">Exclusive pricing is now available for you.</span>
            </p>
          </div>
        </div>
      )}
      
      {/* Premium Dark Background */}
      <div className="absolute inset-0 bg-[#0a0a0a]">
        {/* Subtle gradient overlay */}
        <div 
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 50% 0%, rgba(212, 175, 55, 0.08) 0%, transparent 50%)"
          }}
        />
        
        {/* Subtle grid pattern */}
        <div 
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(212, 175, 55, 0.5) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(212, 175, 55, 0.5) 1px, transparent 1px)`,
            backgroundSize: "60px 60px"
          }}
        />
        
        {/* Floating orbs */}
        <div className="absolute top-20 left-[10%] w-96 h-96 rounded-full bg-[#D4AF37]/5 blur-[100px]" />
        <div className="absolute bottom-20 right-[10%] w-80 h-80 rounded-full bg-[#F8A5B8]/5 blur-[100px]" />
      </div>

      {/* Content */}
      <div className={`relative z-10 min-h-screen flex items-center justify-center px-4 py-20 ${referrerCode ? 'pt-28' : ''} ${isPreview ? 'pt-16' : ''}`}>
        <div className="w-full max-w-2xl">
          
          {/* Top Badge */}
          <div className="flex justify-center mb-8">
            <div 
              className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full"
              style={{
                background: "linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(212, 175, 55, 0.05) 100%)",
                border: "1px solid rgba(212, 175, 55, 0.2)"
              }}
            >
              <Beaker className="w-4 h-4 text-[#D4AF37]" />
              <span className="text-[#D4AF37] text-xs font-medium tracking-[0.2em] uppercase">{heroBadge}</span>
            </div>
          </div>

          {/* Main Heading */}
          <h1 
            className="text-center text-4xl md:text-5xl lg:text-6xl font-bold mb-6 tracking-tight"
            style={{ 
              fontFamily: '"Playfair Display", serif',
              color: "white",
              lineHeight: 1.1
            }}
          >
            {heroTitle}
            <span 
              className="block mt-2"
              style={{ 
                background: "linear-gradient(135deg, #D4AF37 0%, #E8C84B 50%, #D4AF37 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent"
              }}
            >
              {heroSubtitle}
            </span>
          </h1>

          {/* Sub-headline */}
          <p 
            className="text-center text-lg md:text-xl mb-12 max-w-xl mx-auto"
            style={{ 
              color: "rgba(255,255,255,0.6)",
              fontFamily: "Manrope, sans-serif",
              lineHeight: 1.6
            }}
          >
            {heroDescription}<br />
            <span style={{ color: "rgba(248, 165, 184, 0.8)" }}>Limited to the first wave of Canadian researchers.</span>
          </p>

          {/* Premium Card */}
          <div 
            className="relative rounded-2xl overflow-hidden"
            style={{
              background: "linear-gradient(145deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)",
              border: "1px solid rgba(212, 175, 55, 0.15)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
            }}
          >
            {/* Gold accent line at top */}
            <div 
              className="h-[2px] w-full"
              style={{
                background: "linear-gradient(90deg, transparent 0%, #D4AF37 50%, transparent 100%)"
              }}
            />
            
            <div className="p-8 md:p-10">
              
              {/* Price Stack Section */}
              <div className="mb-10">
                <p className="text-center text-xs uppercase tracking-[0.2em] text-white/40 mb-6">
                  Founding Member Beta Pricing
                </p>
                
                {/* Price Breakdown Table */}
                <div 
                  className="rounded-xl overflow-hidden"
                  style={{
                    background: "rgba(0,0,0,0.3)",
                    border: "1px solid rgba(255,255,255,0.05)"
                  }}
                >
                  {/* Retail Value */}
                  <div className="flex justify-between items-center px-6 py-4 border-b border-white/5">
                    <span className="text-white/60 text-sm">Retail Value</span>
                    <span className="text-white font-medium">$100.00</span>
                  </div>
                  
                  {/* Founder's Subsidy */}
                  <div className="flex justify-between items-center px-6 py-4 border-b border-white/5">
                    <span className="text-white/60 text-sm">Founder's Launch Subsidy</span>
                    <span className="text-[#D4AF37] font-medium">-50%</span>
                  </div>
                  
                  {/* Influencer Referral */}
                  <div className="flex justify-between items-center px-6 py-4 border-b border-white/5">
                    <span className="text-white/60 text-sm">Influencer Referral</span>
                    <span className="text-[#D4AF37] font-medium">-50%</span>
                  </div>
                  
                  {/* First-Time Protocol */}
                  <div className="flex justify-between items-center px-6 py-4 border-b border-white/5">
                    <span className="text-white/60 text-sm">First-Time Protocol Access</span>
                    <span className="text-[#D4AF37] font-medium">-25%</span>
                  </div>
                  
                  {/* Final Price */}
                  <div 
                    className="flex justify-between items-center px-6 py-5"
                    style={{
                      background: "linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(212, 175, 55, 0.05) 100%)"
                    }}
                  >
                    <span className="text-white font-semibold">Final Founding Member Entry</span>
                    <div className="text-right">
                      <span 
                        className="text-2xl md:text-3xl font-bold"
                        style={{
                          background: "linear-gradient(135deg, #D4AF37 0%, #E8C84B 100%)",
                          WebkitBackgroundClip: "text",
                          WebkitTextFillColor: "transparent"
                        }}
                      >
                        $70
                      </span>
                      <span className="block text-xs text-white/40 mt-1">CAD</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Form Section */}
              {!submitted ? (
                <div>
                  <p className="text-center text-white/50 text-sm mb-6">
                    Reserve your Founding Member position
                  </p>
                  
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-4">
                      <Input
                        type="text"
                        placeholder="First name"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 px-4 focus:border-[#D4AF37] focus:ring-[#D4AF37]/20"
                        data-testid="waitlist-first-name"
                      />
                      <Input
                        type="text"
                        placeholder="Last name"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 px-4 focus:border-[#D4AF37] focus:ring-[#D4AF37]/20"
                        data-testid="waitlist-last-name"
                      />
                    </div>
                    
                    {/* Email field */}
                    <Input
                      type="email"
                      placeholder="Email address"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 px-4 focus:border-[#D4AF37] focus:ring-[#D4AF37]/20"
                      data-testid="waitlist-email"
                    />
                    
                    {/* Phone Number with Country Code */}
                    <PhoneInput
                      value={phone}
                      onChange={setPhone}
                      countryCode={phoneCountryCode}
                      onCountryCodeChange={setPhoneCountryCode}
                      placeholder="Phone number"
                      required
                      darkMode={true}
                      inputClassName="bg-white/5 border-white/10 text-white placeholder:text-white/30 rounded-lg h-12 focus:border-[#D4AF37] focus:ring-[#D4AF37]/20"
                      testId="waitlist-phone"
                    />
                    
                    {/* Math Captcha */}
                    <MathCaptcha onVerify={setCaptchaVerified} />
                    
                    <Button
                      type="submit"
                      disabled={loading || !captchaVerified}
                      className="w-full h-14 rounded-lg text-base font-semibold transition-all duration-300 hover:scale-[1.01] hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                      style={{
                        background: captchaVerified 
                          ? "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)"
                          : "linear-gradient(135deg, #666 0%, #444 100%)",
                        color: "#0a0a0a"
                      }}
                      data-testid="waitlist-submit"
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          Securing Position...
                        </span>
                      ) : (
                        <span className="flex items-center justify-center gap-2">
                          {ctaButtonText}
                          <ArrowRight className="w-5 h-5" />
                        </span>
                      )}
                    </Button>
                  </form>
                </div>
              ) : (
                <div className="text-center py-8">
                  {/* Position Badge */}
                  <div 
                    className="w-28 h-28 rounded-full flex flex-col items-center justify-center mx-auto mb-6 relative"
                    style={{ 
                      background: "linear-gradient(135deg, rgba(212, 175, 55, 0.3) 0%, rgba(212, 175, 55, 0.1) 100%)",
                      border: "2px solid rgba(212, 175, 55, 0.5)",
                      boxShadow: "0 0 30px rgba(212, 175, 55, 0.2)"
                    }}
                  >
                    <span className="text-[#D4AF37] text-xs uppercase tracking-wider font-semibold">You are</span>
                    <span 
                      className="text-3xl font-bold"
                      style={{
                        background: "linear-gradient(135deg, #D4AF37 0%, #E8C84B 100%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent"
                      }}
                    >
                      #{position || '—'}
                    </span>
                    <span className="text-white/50 text-xs">in line</span>
                  </div>
                  
                  <h3 className="text-white text-2xl font-semibold mb-3" style={{ fontFamily: '"Playfair Display", serif' }}>
                    Position Secured!
                  </h3>
                  <p className="text-white/50 max-w-sm mx-auto mb-6">
                    You're on the exclusive list for The Protocol launch.
                  </p>
                  
                  {/* Move Up Incentive */}
                  <div 
                    className="rounded-xl p-5 mb-6 max-w-md mx-auto"
                    style={{
                      background: "rgba(248, 165, 184, 0.1)",
                      border: "1px solid rgba(248, 165, 184, 0.2)"
                    }}
                  >
                    <p className="text-white/80 text-sm font-medium mb-3">
                      🚀 Want to move up 10 spots?
                    </p>
                    <p className="text-white/50 text-xs mb-4">
                      Share your unique link and jump ahead for every friend who joins!
                    </p>
                    
                    {/* Share Buttons */}
                    <div className="flex gap-2 justify-center">
                      <Button
                        onClick={() => {
                          const shareUrl = `${window.location.origin}/waitlist?ref=${userReferralCode}`;
                          window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent("I just secured my spot for @ReRootsCA's PDRN Protocol. Join me and get priority access!")}&url=${encodeURIComponent(shareUrl)}`, '_blank');
                        }}
                        className="bg-[#1DA1F2] hover:bg-[#1a8cd8] text-white text-xs px-4 py-2 rounded-lg"
                      >
                        Share on X
                      </Button>
                      <Button
                        onClick={() => {
                          const shareUrl = `${window.location.origin}/waitlist?ref=${userReferralCode}`;
                          navigator.clipboard.writeText(shareUrl);
                          toast.success("Link copied!");
                        }}
                        className="bg-white/10 hover:bg-white/20 text-white text-xs px-4 py-2 rounded-lg"
                      >
                        Copy Link
                      </Button>
                    </div>
                  </div>
                  
                  <p className="text-white/40 text-sm">
                    Redirecting to your dashboard...
                  </p>
                </div>
              )}

              {/* Trust Indicators */}
              <div className="mt-8 pt-6 border-t border-white/5">
                <div className="flex items-center justify-center gap-8 text-white/30 text-xs">
                  <span className="flex items-center gap-2">
                    <Shield className="w-3.5 h-3.5" />
                    Secure & Private
                  </span>
                  <span className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5" />
                    Limited Availability
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Legal Disclaimer */}
          <div className="mt-8 text-center">
            <p className="text-white/20 text-[10px] leading-relaxed max-w-lg mx-auto">
              *Founding Member Beta Pricing is a one-time subsidy for the first 1,000 units to establish Canadian skin-resilience case studies. 
              Standard retail pricing will apply after the beta program concludes. Final discount depends on referral source and eligibility.
            </p>
          </div>

          {/* Bottom Badge */}
          <div className="mt-10 flex justify-center">
            <p className="text-white/20 text-xs tracking-wider">
              ReRoots · Canadian Biotech Skincare · Est. 2025
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WaitlistPage;
