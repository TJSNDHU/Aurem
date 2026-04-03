import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { X, Gift, Sparkles } from "lucide-react";
import axios from "axios";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

/**
 * ReferralStickyBar - Shows a personalized bar when visitor arrives via referral link
 * Displays: "You've been invited by [Partner Name]. Enjoy 15% off!"
 * Persists across page navigation via sessionStorage
 */
const ReferralStickyBar = () => {
  const location = useLocation();
  const [visible, setVisible] = useState(false);
  const [referrerName, setReferrerName] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [discountPercent, setDiscountPercent] = useState(15);
  const [dismissed, setDismissed] = useState(false);

  // Hide on admin pages and PWA
  const hiddenPaths = ['/admin', '/new-admin', '/reroots-admin', '/app', '/checkout', '/pwa'];
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));

  useEffect(() => {
    // Check if already dismissed this session
    if (sessionStorage.getItem("referral_bar_dismissed")) {
      return;
    }

    // Check for referral code in URL
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = urlParams.get("ref") || urlParams.get("referrer_code");
    
    // Also check sessionStorage for previously captured referral
    const storedRef = sessionStorage.getItem("referral_code");
    const storedName = sessionStorage.getItem("referrer_name");
    
    const codeToUse = refCode || storedRef;
    
    if (codeToUse) {
      // Store in sessionStorage for persistence
      sessionStorage.setItem("referral_code", codeToUse);
      
      if (storedName) {
        // Use cached name
        setReferrerName(storedName);
        setDiscountCode(codeToUse);
        setVisible(true);
      } else {
        // Fetch referrer info from API
        fetchReferrerInfo(codeToUse);
      }
    }
  }, []);

  const fetchReferrerInfo = async (code) => {
    try {
      const res = await axios.get(`${API}/referrer-info/${code}`);
      if (res.data.name) {
        setReferrerName(res.data.name);
        setDiscountCode(res.data.discount_code || code);
        setDiscountPercent(res.data.discount_percent || 15);
        sessionStorage.setItem("referrer_name", res.data.name);
        setVisible(true);
      }
    } catch (error) {
      // If API fails, show generic message
      setReferrerName("a ReRoots Partner");
      setDiscountCode(code);
      sessionStorage.setItem("referrer_name", "a ReRoots Partner");
      setVisible(true);
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    setVisible(false);
    sessionStorage.setItem("referral_bar_dismissed", "true");
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(discountCode);
    // Show a mini toast or change button text
  };

  if (!visible || dismissed || shouldHide) return null;

  return (
    <div 
      className="fixed top-0 left-0 right-0 z-[9999] bg-gradient-to-r from-[#2D2A2E] via-[#3D3A3E] to-[#2D2A2E] text-white py-3 px-4 shadow-lg"
      style={{
        animation: "slideDown 0.3s ease-out"
      }}
    >
      <style>{`
        @keyframes slideDown {
          from { transform: translateY(-100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        @keyframes pulse-gold {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>
      
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1">
          {/* Icon */}
          <div 
            className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
            style={{
              background: "linear-gradient(135deg, rgba(212, 175, 55, 0.3) 0%, rgba(212, 175, 55, 0.1) 100%)",
              border: "1px solid rgba(212, 175, 55, 0.5)"
            }}
          >
            <Gift className="w-4 h-4 text-[#D4AF37]" />
          </div>
          
          {/* Message */}
          <div className="flex-1 min-w-0">
            <p className="text-sm md:text-base">
              <span className="text-white/70">You've been invited by </span>
              <span className="font-semibold text-[#D4AF37]">{referrerName}</span>
              <span className="text-white/70"> to become a Founding Member. </span>
              <span className="hidden sm:inline text-white/70">Enjoy </span>
              <span className="font-bold text-[#F8A5B8]">{discountPercent}% off</span>
              <span className="hidden sm:inline text-white/70"> your first order!</span>
            </p>
          </div>
          
          {/* Discount Code Badge */}
          <button
            onClick={handleCopyCode}
            className="hidden md:flex items-center gap-2 bg-[#D4AF37]/20 hover:bg-[#D4AF37]/30 border border-[#D4AF37]/50 rounded-full px-4 py-1.5 transition-colors group"
            title="Click to copy code"
          >
            <span className="text-xs text-white/70">Code:</span>
            <span 
              className="font-mono font-bold text-[#D4AF37]"
              style={{ animation: "pulse-gold 2s infinite" }}
            >
              {discountCode}
            </span>
            <Sparkles className="w-3 h-3 text-[#D4AF37] opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        </div>
        
        {/* Close Button */}
        <button
          onClick={handleDismiss}
          className="p-1.5 hover:bg-white/10 rounded-full transition-colors flex-shrink-0"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4 text-white/50 hover:text-white" />
        </button>
      </div>
    </div>
  );
};

export default ReferralStickyBar;
