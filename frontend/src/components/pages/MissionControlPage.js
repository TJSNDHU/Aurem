import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Copy, Share2, CheckCircle, Lock, Unlock, Users, 
  Clock, AlertTriangle, Sparkles, Target, Trophy, 
  ChevronRight, Crown, Star, Shield, Ticket, QrCode
} from "lucide-react";
import ProtocolUnlockedPopup from "./ProtocolUnlockedPopup";
import ViralShareToolkit from "@/components/ViralShareToolkit";
import ReferralLeaderboard from "@/components/ReferralLeaderboard";
import RedditLaunchToolkit from "@/components/RedditLaunchToolkit";
import LoyaltyPointsWidget from "@/components/LoyaltyPointsWidget";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const MissionControlPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const referralCode = searchParams.get("code") || localStorage.getItem("referral_code");
  
  const [loading, setLoading] = useState(true);
  const [userData, setUserData] = useState(null);
  const [referrals, setReferrals] = useState([]);
  const [copied, setCopied] = useState(false);
  const [spotsRemaining, setSpotsRemaining] = useState(847);
  const [showUnlockedPopup, setShowUnlockedPopup] = useState(false);
  const [hasSeenPopup, setHasSeenPopup] = useState(false);

  // Pricing constants - FIXED: $70 Founding Member price
  const RETAIL_PRICE = 100;
  const BASE_PRICE = 100.00;
  const UNLOCKED_PRICE = 70.00;  // 30% off = $70
  const REFERRAL_GOAL = 10;
  const TAX_RATE = 0.13;

  useEffect(() => {
    fetchUserData();
  }, [referralCode]);

  // Check if we should show the unlock popup
  useEffect(() => {
    if (userData && !loading && !hasSeenPopup) {
      const voucherStatus = userData.voucher_unlocked || (userData.referral_count >= REFERRAL_GOAL);
      const popupKey = `seen_unlock_popup_${referralCode}`;
      const alreadySeen = localStorage.getItem(popupKey);
      
      if (voucherStatus && !alreadySeen) {
        // Show popup after a brief delay for dramatic effect
        setTimeout(() => {
          setShowUnlockedPopup(true);
          localStorage.setItem(popupKey, 'true');
        }, 500);
      }
      setHasSeenPopup(true);
    }
  }, [userData, loading, hasSeenPopup, referralCode]);

  const fetchUserData = async () => {
    if (!referralCode) {
      navigate("/waitlist");
      return;
    }

    setLoading(true);
    try {
      const res = await axios.get(`${API}/referral/status/${referralCode}`);
      setUserData(res.data);
      setReferrals(res.data.referrals || []);
      setSpotsRemaining(res.data.spots_remaining || 847);
    } catch (error) {
      console.error("Failed to fetch user data:", error);
      setUserData({
        email: localStorage.getItem("waitlist_email") || "user@example.com",
        name: localStorage.getItem("waitlist_name") || "Founding Member",
        referral_code: referralCode,
        referral_count: 0,
        verified: true,
        voucher_unlocked: false
      });
    }
    setLoading(false);
  };

  const referralCount = userData?.referral_count || userData?.verified_referrals || 0;
  const voucherUnlocked = userData?.voucher_unlocked || referralCount >= REFERRAL_GOAL;
  const currentPrice = voucherUnlocked ? UNLOCKED_PRICE : BASE_PRICE;
  const progressPercent = Math.min((referralCount / REFERRAL_GOAL) * 100, 100);
  const referralsNeeded = Math.max(0, REFERRAL_GOAL - referralCount);
  const userName = userData?.name || "Founding Member";

  const referralLink = `${window.location.origin}/waitlist?ref=${referralCode}`;
  
  const copyLink = () => {
    navigator.clipboard.writeText(referralLink);
    setCopied(true);
    toast.success("Referral link copied!");
    setTimeout(() => setCopied(false), 2000);
  };

  const shareOnTwitter = () => {
    const text = `I just joined the ReRoots Founding Member waitlist! Get almost 80% off premium PDRN skincare. Use my link:`;
    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(referralLink)}`, "_blank");
  };

  const shareOnWhatsApp = () => {
    const text = `Hey! I found this amazing Canadian skincare brand. Join the waitlist with my link and we both save: ${referralLink}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank");
  };

  const shareViaEmail = () => {
    const subject = "Join ReRoots - Get 80% OFF Premium PDRN Skincare";
    const body = `Hey!\n\nI just discovered this amazing Canadian biotech skincare brand called ReRoots. They're launching their PDRN serum and I got us both an exclusive deal!\n\nUse my link to join: ${referralLink}\n\nYou'll get Founding Member pricing (almost 80% off) + if you refer 10 friends, we both get an extra 50% discount.\n\nTrust me, you don't want to miss this! 🧬✨`;
    window.open(`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`, "_blank");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-[#D4AF37]"></div>
      </div>
    );
  }

  // ============ VIP SUCCESS STATE ============
  if (voucherUnlocked) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white">
        <Helmet>
          <title>VIP Status Confirmed | ReRoots Founding Member</title>
          <meta name="description" content="Your $70 Founding Member price is secured. You're in the Top 1% of Founding Members." />
        </Helmet>

        {/* Protocol Unlocked Popup */}
        <ProtocolUnlockedPopup 
          isOpen={showUnlockedPopup}
          onClose={() => setShowUnlockedPopup(false)}
          retailPrice={RETAIL_PRICE}
          finalPrice={UNLOCKED_PRICE}
          userName={userName}
          onContinue={() => setShowUnlockedPopup(false)}
        />

        {/* Background Effects */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-20 left-[10%] w-96 h-96 rounded-full bg-[#D4AF37]/8 blur-[100px]" />
          <div className="absolute bottom-20 right-[10%] w-80 h-80 rounded-full bg-[#D4AF37]/5 blur-[100px]" />
        </div>

        <div className="relative z-10 max-w-4xl mx-auto px-4 py-12">
          
          {/* VIP Header */}
          <div className="text-center mb-10">
            <Badge 
              className="mb-4 px-4 py-1.5"
              style={{
                background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                color: "#0a0a0a",
                fontWeight: "bold"
              }}
            >
              <Crown className="w-4 h-4 mr-2" />
              VIP FOUNDING MEMBER
            </Badge>
            <h1 
              className="text-3xl md:text-4xl font-bold mb-2" 
              style={{ fontFamily: '"Playfair Display", serif' }}
            >
              Welcome Back, <span className="text-[#D4AF37]">{userName}</span>
            </h1>
            <p className="text-white/60">Your exclusive access is confirmed</p>
          </div>

          {/* Golden Ticket / VIP Badge Card */}
          <Card 
            className="mb-8 overflow-hidden border-0"
            style={{
              background: "linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.05) 100%)",
              border: "2px solid #D4AF37"
            }}
          >
            <CardContent className="p-8 text-center">
              {/* Golden Ticket Visual */}
              <div 
                className="inline-flex items-center justify-center w-24 h-24 rounded-full mb-6"
                style={{
                  background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                  boxShadow: "0 0 40px rgba(212, 175, 55, 0.4)"
                }}
              >
                <Ticket className="w-12 h-12 text-[#0a0a0a]" />
              </div>

              <div className="space-y-2 mb-6">
                <p className="text-[#D4AF37] text-sm uppercase tracking-[0.2em] font-medium">
                  Top 1% Founding Member
                </p>
                <h2 
                  className="text-2xl font-bold text-white"
                  style={{ fontFamily: '"Playfair Display", serif' }}
                >
                  Your $70 Founding Member Price is Secured
                </h2>
                <p className="text-white/60 text-sm max-w-md mx-auto">
                  Your spot in the first production run is guaranteed. The moment we go live, 
                  your unique checkout link will be delivered to your inbox.
                </p>
              </div>

              {/* Price Display */}
              <div 
                className="inline-flex items-center gap-4 px-6 py-3 rounded-full"
                style={{
                  background: "rgba(0, 0, 0, 0.3)",
                  border: "1px solid rgba(212, 175, 55, 0.3)"
                }}
              >
                <span className="text-white/50 line-through text-lg">${RETAIL_PRICE}</span>
                <ChevronRight className="w-4 h-4 text-white/30" />
                <span 
                  className="text-3xl font-bold"
                  style={{
                    background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent"
                  }}
                >
                  ${UNLOCKED_PRICE.toFixed(2)}
                </span>
                <Badge className="bg-[#D4AF37] text-[#0a0a0a] font-bold">
                  LOCKED IN
                </Badge>
              </div>

              {/* Savings */}
              <p className="text-[#D4AF37] text-sm mt-4">
                <Sparkles className="w-4 h-4 inline mr-1" />
                You're saving ${(RETAIL_PRICE - UNLOCKED_PRICE).toFixed(2)} (81% OFF)
              </p>
            </CardContent>
          </Card>

          {/* Achievement Stats */}
          <Card className="mb-8 bg-[#1a1a1a] border-[#333]">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-[#D4AF37]">
                <Trophy className="w-5 h-5" />
                Mission Completed
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Gold Progress Bar */}
              <div className="relative mb-4">
                <div className="h-4 bg-[#2a2a2a] rounded-full overflow-hidden">
                  <div 
                    className="h-full rounded-full transition-all duration-1000"
                    style={{ 
                      width: '100%',
                      background: 'linear-gradient(90deg, #D4AF37, #F4D03F, #D4AF37)',
                      backgroundSize: '200% 100%',
                      animation: 'shimmer 2s ease-in-out infinite'
                    }}
                  />
                </div>
                {/* Milestone markers */}
                <div className="absolute top-0 left-0 w-full h-4 flex justify-between px-1">
                  {[...Array(10)].map((_, i) => (
                    <div 
                      key={i} 
                      className="w-0.5 h-full bg-white/20"
                    />
                  ))}
                </div>
                <style>{`
                  @keyframes shimmer {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                  }
                `}</style>
              </div>

              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-[#D4AF37]" />
                  <span className="text-2xl font-bold text-[#D4AF37]">{referralCount}</span>
                  <span className="text-white/50">/ {REFERRAL_GOAL} verified referrals</span>
                </div>
                <Badge 
                  className="font-bold"
                  style={{
                    background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                    color: "#0a0a0a"
                  }}
                >
                  <Trophy className="w-3 h-3 mr-1" />
                  GOAL ACHIEVED
                </Badge>
              </div>

              {/* Referral List */}
              {referrals.length > 0 && (
                <div className="mt-6 space-y-2">
                  <p className="text-sm text-white/50 mb-3">Your Referrals:</p>
                  {referrals.slice(0, 5).map((ref, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 bg-[#2a2a2a] rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${ref.verified ? 'bg-[#D4AF37]' : 'bg-yellow-400'}`} />
                        <span className="text-sm text-white/70">
                          {ref.referee_email?.replace(/(.{3}).*(@.*)/, '$1***$2') || `Referral ${idx + 1}`}
                        </span>
                      </div>
                      <Badge className={ref.verified ? 'bg-[#D4AF37]/20 text-[#D4AF37]' : 'bg-yellow-500/20 text-yellow-400'}>
                        {ref.verified ? 'Verified' : 'Pending'}
                      </Badge>
                    </div>
                  ))}
                  {referrals.length > 5 && (
                    <p className="text-xs text-white/40 text-center">+ {referrals.length - 5} more</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Priority Notice */}
          <Card 
            className="mb-8 border-0"
            style={{
              background: "linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(212, 175, 55, 0.02) 100%)",
              border: "1px solid rgba(212, 175, 55, 0.2)"
            }}
          >
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div 
                  className="p-3 rounded-full flex-shrink-0"
                  style={{ background: "rgba(212, 175, 55, 0.2)" }}
                >
                  <Shield className="w-6 h-6 text-[#D4AF37]" />
                </div>
                <div>
                  <h3 className="font-bold text-[#D4AF37] mb-2">Priority Shipment Confirmed</h3>
                  <p className="text-white/70 text-sm leading-relaxed">
                    You're in the <span className="text-white font-semibold">first {spotsRemaining.toLocaleString()} units</span> of 
                    our production run. When we launch, you'll receive your exclusive checkout link via email. 
                    Your $70 Founding Member price is permanently locked.
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-[#D4AF37]" />
                    <span className="text-xs text-white/50">Launch notification coming soon</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Continue Sharing Section - Using Viral Toolkit */}
          <Card className="mb-8 bg-[#1a1a1a] border-[#333]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white/80">
                <Share2 className="w-5 h-5 text-[#D4AF37]" />
                Keep Sharing (Optional)
              </CardTitle>
              <CardDescription>
                Help more friends discover the future of skincare
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Viral Share Toolkit Button */}
              <ViralShareToolkit
                referralCode={referralCode}
                referralLink={referralLink}
                userName={userName}
                referralCount={referralCount}
                isVIP={true}
                currentPrice={UNLOCKED_PRICE}
                goalPrice={UNLOCKED_PRICE}
              />
              
              {/* Reddit Launch Toolkit */}
              <RedditLaunchToolkit
                referralCode={referralCode}
                referralLink={referralLink}
                userName={userName}
                isVIP={true}
              />
              
              {/* Quick Copy Link */}
              <div className="flex gap-2">
                <Input 
                  readOnly 
                  value={referralLink}
                  className="bg-[#2a2a2a] border-[#444] text-white/80 flex-1"
                />
                <Button 
                  onClick={copyLink}
                  className={copied ? "bg-green-600" : "bg-[#D4AF37] hover:bg-[#B8960F] text-[#0a0a0a]"}
                >
                  {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Referral Leaderboard */}
          <ReferralLeaderboard currentUserCode={referralCode} />

          {/* Footer */}
          <div className="text-center">
            <p className="text-white/30 text-xs">
              ReRoots · Canadian Biotech Skincare · Founding Member Program
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ============ ACTIVE MISSION STATE (Not yet unlocked) ============
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Helmet>
        <title>Mission Control | ReRoots Founding Member</title>
        <meta name="description" content="Track your referral progress and unlock the full Founding Member discount." />
      </Helmet>

      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-[10%] w-96 h-96 rounded-full bg-[#D4AF37]/5 blur-[100px]" />
        <div className="absolute bottom-20 right-[10%] w-80 h-80 rounded-full bg-[#F8A5B8]/5 blur-[100px]" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-4 py-12">
        
        {/* Header */}
        <div className="text-center mb-10">
          <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] mb-4">
            <Target className="w-3 h-3 mr-1" />
            MISSION CONTROL
          </Badge>
          <h1 className="text-3xl md:text-4xl font-bold mb-2" style={{ fontFamily: '"Playfair Display", serif' }}>
            Your Founding Member Status
          </h1>
          <p className="text-white/60">Track your progress to unlock the maximum discount</p>
        </div>

        {/* STATUS HEADER */}
        <Card className="mb-8 bg-gradient-to-r from-[#1a1a1a] to-[#2a2a2a] border-[#333]">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
              
              {/* Status */}
              <div>
                <p className="text-white/50 text-sm uppercase tracking-wider mb-1">Protocol Access</p>
                <div className="flex items-center gap-2">
                  <Lock className="w-5 h-5 text-[#F8A5B8]" />
                  <span className="text-xl font-bold text-[#F8A5B8]">Partially Subsidized</span>
                </div>
              </div>

              {/* Current Price */}
              <div className="text-center">
                <p className="text-white/50 text-sm uppercase tracking-wider mb-1">Your Current Price</p>
                <p className="text-3xl font-bold text-[#F8A5B8]">
                  ${currentPrice.toFixed(2)}
                </p>
                <p className="text-xs text-white/40">+ ${(currentPrice * TAX_RATE).toFixed(2)} tax</p>
              </div>

              {/* Goal */}
              <div className="text-right">
                <p className="text-white/50 text-sm uppercase tracking-wider mb-1">Goal Price</p>
                <p className="text-3xl font-bold text-[#D4AF37]">${UNLOCKED_PRICE.toFixed(2)}</p>
                <p className="text-xs text-white/40">Unlock the Influencer Voucher</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* PROGRESS TRACKER */}
        <Card className="mb-8 bg-[#1a1a1a] border-[#333] overflow-hidden">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-[#D4AF37]" />
              Referral Progress
            </CardTitle>
            <CardDescription>
              Refer {referralsNeeded} more friends to unlock the $70 Founding Member price
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Progress Bar - Pink gradient for incomplete */}
            <div className="relative mb-4">
              <div className="h-4 bg-[#2a2a2a] rounded-full overflow-hidden">
                <div 
                  className="h-full transition-all duration-1000 ease-out rounded-full"
                  style={{ 
                    width: `${progressPercent}%`,
                    background: 'linear-gradient(90deg, #F8A5B8, #FFB6C1)'
                  }}
                />
              </div>
              {/* Milestone markers */}
              <div className="absolute top-0 left-0 w-full h-4 flex justify-between px-1">
                {[...Array(10)].map((_, i) => (
                  <div 
                    key={i} 
                    className={`w-0.5 h-full ${i < referralCount ? 'bg-white/30' : 'bg-white/10'}`}
                  />
                ))}
              </div>
            </div>

            {/* Stats */}
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-[#F8A5B8]">
                  {referralCount}
                </span>
                <span className="text-white/50">/ {REFERRAL_GOAL} verified referrals</span>
              </div>
              
              <Badge className="bg-white/10 text-white/60">
                <Lock className="w-3 h-3 mr-1" />
                {referralsNeeded} more to unlock
              </Badge>
            </div>

            {/* Referral List */}
            {referrals.length > 0 && (
              <div className="mt-6 space-y-2">
                <p className="text-sm text-white/50 mb-3">Your Referrals:</p>
                {referrals.slice(0, 5).map((ref, idx) => (
                  <div key={idx} className="flex items-center justify-between p-2 bg-[#2a2a2a] rounded-lg">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${ref.verified ? 'bg-green-400' : 'bg-yellow-400'}`} />
                      <span className="text-sm text-white/70">
                        {ref.referee_email?.replace(/(.{3}).*(@.*)/, '$1***$2') || `Referral ${idx + 1}`}
                      </span>
                    </div>
                    <Badge className={ref.verified ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}>
                      {ref.verified ? 'Verified' : 'Pending'}
                    </Badge>
                  </div>
                ))}
                {referrals.length > 5 && (
                  <p className="text-xs text-white/40 text-center">+ {referrals.length - 5} more</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* SHARE SECTION - Using Viral Toolkit */}
        <Card className="mb-8 bg-[#1a1a1a] border-[#333]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Share2 className="w-5 h-5 text-[#D4AF37]" />
              Share Your Referral Link
            </CardTitle>
            <CardDescription>
              Each verified sign-up counts toward your goal
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Viral Share Toolkit Button */}
            <ViralShareToolkit
              referralCode={referralCode}
              referralLink={referralLink}
              userName={userName}
              referralCount={referralCount}
              isVIP={false}
              currentPrice={currentPrice}
              goalPrice={UNLOCKED_PRICE}
            />
            
            {/* Reddit Launch Toolkit */}
            <RedditLaunchToolkit
              referralCode={referralCode}
              referralLink={referralLink}
              userName={userName}
              isVIP={false}
            />
            
            {/* Quick Copy Link */}
            <div className="flex gap-2">
              <Input 
                readOnly 
                value={referralLink}
                className="bg-[#2a2a2a] border-[#444] text-white/80 flex-1"
              />
              <Button 
                onClick={copyLink}
                className={copied ? "bg-green-600" : "bg-[#D4AF37] hover:bg-[#B8960F] text-[#0a0a0a]"}
              >
                {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* LOYALTY POINTS WIDGET */}
        <div className="mb-8">
          <LoyaltyPointsWidget showRedeem={false} />
        </div>

        {/* MARKETING PROGRAMS - Quick Launch */}
        <Card className="mb-8 bg-gradient-to-br from-[#1a1a1a] to-[#0d0d0d] border-[#333]">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-white">
              <Sparkles className="w-5 h-5 text-[#C9A86C]" />
              Marketing Programs
            </CardTitle>
            <CardDescription className="text-white/50">
              Share these programs on social media to grow your audience
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Bio-Age Quiz */}
            <div className="p-4 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border border-cyan-500/30 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-500 flex items-center justify-center">
                    <Target className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h4 className="font-bold text-white">Bio-Age & Repair Scan</h4>
                    <p className="text-xs text-cyan-300">Viral quiz • Earn $5/referral</p>
                  </div>
                </div>
                <Badge className="bg-green-500/20 text-green-300 border-green-500/30">Active</Badge>
              </div>
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-white"
                  onClick={() => window.open('/Bio-Age-Repair-Scan', '_blank')}
                >
                  Open Quiz
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-cyan-500/50 text-cyan-300 hover:bg-cyan-500/20"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/Bio-Age-Repair-Scan`);
                    toast.success('Quiz link copied! Share on social media');
                  }}
                >
                  <Copy className="w-4 h-4 mr-1" /> Copy Link
                </Button>
              </div>
              <p className="text-xs text-white/50 mt-2">
                Share: <code className="bg-black/30 px-2 py-0.5 rounded text-cyan-300">{window.location.origin}/Bio-Age-Repair-Scan</code>
              </p>
            </div>

            {/* Founding Members Waitlist */}
            <div className="p-4 bg-gradient-to-r from-[#D4AF37]/10 to-[#F4D03F]/5 border border-[#D4AF37]/30 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] flex items-center justify-center">
                    <Crown className="w-5 h-5 text-[#0a0a0a]" />
                  </div>
                  <div>
                    <h4 className="font-bold text-white">Founding Members</h4>
                    <p className="text-xs text-[#D4AF37]">VIP waitlist • 81% discount</p>
                  </div>
                </div>
                <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] border-[#D4AF37]/30">VIP</Badge>
              </div>
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  className="flex-1 bg-[#D4AF37] hover:bg-[#B8960F] text-[#0a0a0a]"
                  onClick={() => window.open('/waitlist', '_blank')}
                >
                  Open Waitlist
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-[#D4AF37]/50 text-[#D4AF37] hover:bg-[#D4AF37]/20"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/waitlist`);
                    toast.success('Waitlist link copied!');
                  }}
                >
                  <Copy className="w-4 h-4 mr-1" /> Copy Link
                </Button>
              </div>
            </div>

            {/* Referral Program */}
            <div className="p-4 bg-gradient-to-r from-pink-500/10 to-rose-500/5 border border-pink-500/30 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
                    <Users className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h4 className="font-bold text-white">Referral Program</h4>
                    <p className="text-xs text-pink-300">Earn 10% commission</p>
                  </div>
                </div>
                <Badge className="bg-pink-500/20 text-pink-300 border-pink-500/30">Active</Badge>
              </div>
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  className="flex-1 bg-pink-500 hover:bg-pink-600 text-white"
                  onClick={() => navigate('/shop')}
                >
                  Shop & Share
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-pink-500/50 text-pink-300 hover:bg-pink-500/20"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/shop`);
                    toast.success('Shop link copied!');
                  }}
                >
                  <Copy className="w-4 h-4 mr-1" /> Copy Link
                </Button>
              </div>
            </div>

            {/* Partner Program - Influencer Partnership */}
            <div className="p-4 bg-gradient-to-r from-purple-500/10 to-violet-500/5 border border-purple-500/30 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-violet-500 flex items-center justify-center">
                    <Star className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h4 className="font-bold text-white">Partner Program</h4>
                    <p className="text-xs text-purple-300">Influencer partnerships • Exclusive perks</p>
                  </div>
                </div>
                <Badge className="bg-purple-500/20 text-purple-300 border-purple-500/30">Apply</Badge>
              </div>
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  className="flex-1 bg-purple-500 hover:bg-purple-600 text-white"
                  onClick={() => navigate('/partner-program')}
                >
                  Become a Partner
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-purple-500/50 text-purple-300 hover:bg-purple-500/20"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/partner-program`);
                    toast.success('Partner program link copied!');
                  }}
                >
                  <Copy className="w-4 h-4 mr-1" /> Copy Link
                </Button>
              </div>
            </div>

            {/* QR Code Generator */}
            <div className="p-4 bg-gradient-to-r from-emerald-500/10 to-teal-500/5 border border-emerald-500/30 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                    <QrCode className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h4 className="font-bold text-white">QR Code Generator</h4>
                    <p className="text-xs text-emerald-300">Free QR codes • Any link</p>
                  </div>
                </div>
                <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">Free</Badge>
              </div>
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white"
                  onClick={() => navigate('/qr-generator')}
                >
                  Generate QR Code
                </Button>
              </div>
            </div>

            {/* Social Media Tips */}
            <div className="mt-4 p-3 bg-white/5 rounded-lg">
              <p className="text-xs text-white/70 flex items-start gap-2">
                <Share2 className="w-4 h-4 text-[#C9A86C] shrink-0 mt-0.5" />
                <span>
                  <strong className="text-white">Pro tip:</strong> Share the Bio-Age Quiz on Instagram Stories, 
                  TikTok bio, or Facebook groups. Each friend who completes it earns you $5!
                </span>
              </p>
            </div>
          </CardContent>
        </Card>

        {/* REFERRAL LEADERBOARD */}
        <ReferralLeaderboard currentUserCode={referralCode} compact={false} />

        {/* URGENCY WIDGET */}
        <Card className="mb-8 border-2 border-[#D4AF37]/50 bg-gradient-to-r from-[#D4AF37]/10 to-[#F4D03F]/5">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-[#D4AF37]/20 rounded-full">
                <AlertTriangle className="w-6 h-6 text-[#D4AF37]" />
              </div>
              <div>
                <h3 className="font-bold text-[#D4AF37] mb-2">Limited Availability</h3>
                <p className="text-white/70 text-sm leading-relaxed">
                  Only <span className="font-bold text-white">{spotsRemaining.toLocaleString()}</span> Founding Member kits available at this price. 
                  Complete your {REFERRAL_GOAL} referrals to secure your place in the first shipment.
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[#D4AF37]" />
                  <span className="text-xs text-white/50">Limited time offer</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* CTA */}
        <div className="space-y-3">
          <Button 
            variant="outline"
            className="w-full h-14 text-lg font-bold border-[#F8A5B8] text-[#F8A5B8] hover:bg-[#F8A5B8]/10"
            onClick={() => navigate("/shop")}
          >
            Shop Now at ${BASE_PRICE.toFixed(2)}
            <ChevronRight className="w-5 h-5 ml-2" />
          </Button>
          <p className="text-center text-xs text-white/40">
            Or keep sharing to unlock the full discount!
          </p>
        </div>

        {/* Footer */}
        <div className="mt-12 text-center">
          <p className="text-white/30 text-xs">
            ReRoots · Canadian Biotech Skincare · Founding Member Program
          </p>
        </div>
      </div>
    </div>
  );
};

export default MissionControlPage;
