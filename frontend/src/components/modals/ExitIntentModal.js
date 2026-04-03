import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { X, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ExitIntentModal = () => {
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(false);
  const [hasShown, setHasShown] = useState(false);
  const [exitModalEnabled, setExitModalEnabled] = useState(false);
  
  // Hide on OROÉ and LA VELA BIANCA pages
  const hiddenPaths = ['/oroe', '/ritual', '/la-vela-bianca', '/lavela'];
  const shouldHideOnPath = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));
  
  // Check if exit modal is enabled in admin settings
  useEffect(() => {
    const checkSettings = async () => {
      try {
        const res = await fetch(`${API}/store-settings`);
        const data = await res.json();
        setExitModalEnabled(data.exit_modal_enabled === true);
      } catch {
        setExitModalEnabled(false);
      }
    };
    checkSettings();
  }, []);
  
  useEffect(() => {
    // Don't register exit intent on hidden paths or if disabled
    if (shouldHideOnPath || !exitModalEnabled) return;
    
    const shown = sessionStorage.getItem('exit_intent_shown');
    if (shown) {
      setHasShown(true);
      return;
    }
    
    const handleMouseLeave = (e) => {
      if (e.clientY <= 5 && !hasShown) {
        setIsVisible(true);
        setHasShown(true);
        sessionStorage.setItem('exit_intent_shown', 'true');
      }
    };
    
    const timer = setTimeout(() => {
      document.addEventListener('mouseleave', handleMouseLeave);
    }, 5000);
    
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [hasShown, shouldHideOnPath, exitModalEnabled]);
  
  const handleClose = () => {
    setIsVisible(false);
  };
  
  // Hide on brand-specific pages or if disabled
  if (shouldHideOnPath || !isVisible || !exitModalEnabled) return null;
  
  return (
    <div 
      className="fixed inset-0 z-[70] flex items-center justify-center p-4 animate-in fade-in duration-300"
      onClick={handleClose}
    >
      <div className="absolute inset-0 bg-[#2D2A2E]/50" />
      
      <div
        className="relative w-full max-w-md rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(212, 175, 55, 0.20)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/80 hover:bg-white flex items-center justify-center transition-colors z-10"
          data-testid="exit-modal-close"
        >
          <X className="h-4 w-4 text-[#2D2A2E]" />
        </button>
        
        <div className="p-8 text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-[#D4AF37]/20 to-[#F8A5B8]/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <Sparkles className="w-8 h-8 text-[#D4AF37]" />
          </div>
          
          <h2 className="font-luxury text-2xl md:text-3xl font-medium text-[#2D2A2E] mb-4">
            Don't miss the future
            <br />
            <span className="italic text-[#D4AF37]">of your skin.</span>
          </h2>
          
          <p className="font-clinical text-[#5A5A5A] mb-6 leading-relaxed">
            Join our Founding Member program and save up to 81% 
            on premium PDRN biotech skincare.
          </p>
          
          {/* Founding Member Benefits */}
          <div className="bg-[#FDF9F9] border border-[#D4AF37]/20 rounded-xl p-4 mb-6 text-left">
            <p className="font-clinical text-xs text-[#888] uppercase tracking-wider mb-3 text-center">Founding Member Benefits</p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-[#D4AF37]">✓</span>
                <span className="text-[#5A5A5A]">50% Founder's Launch Subsidy</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[#F8A5B8]">✓</span>
                <span className="text-[#5A5A5A]">50% Referral Voucher (unlock with 10 referrals)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[#D4AF37]">✓</span>
                <span className="text-[#5A5A5A]">25% First-Time Access Discount</span>
              </div>
            </div>
          </div>
          
          <Link to="/waitlist" onClick={handleClose}>
            <Button 
              className="w-full bg-[#F8A5B8] hover:bg-[#e8899c] text-[#2D2A2E] rounded-full py-6 text-lg font-semibold font-clinical shadow-lg"
              data-testid="exit-modal-join-btn"
            >
              Join as Founding Member
            </Button>
          </Link>
          
          <button 
            onClick={handleClose}
            className="mt-4 font-clinical text-sm text-[#888] hover:text-[#5A5A5A] transition-colors"
            data-testid="exit-modal-later-btn"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExitIntentModal;
