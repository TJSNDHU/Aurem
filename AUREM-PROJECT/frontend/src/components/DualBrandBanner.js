import React, { useState } from "react";
// PERF: Use LazyMotionWrapper to avoid duplicate framer-motion bundles
import { m, AnimatePresence } from "@/components/LazyMotionWrapper";
import { X, ChevronLeft, ChevronRight, Sparkles, Crown, Copy, Check, Share2 } from "lucide-react";
import { toast } from "sonner";

// Lazy load the full landing pages using absolute paths
const LaVelaLandingPage = React.lazy(() => import("@/lavela/pages/LaVelaLandingPage"));
const OroeLandingPage = React.lazy(() => import("@/oroe/pages/OroeLandingPage"));

// Social Media Icons as SVG components
const TwitterIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);

const FacebookIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
  </svg>
);

const WhatsAppIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
  </svg>
);

const LinkedInIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
  </svg>
);

// Share Button Component
const ShareButtons = ({ brandUrl, brandName, theme = 'light' }) => {
  const [copied, setCopied] = useState(false);
  
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
  const fullUrl = `${baseUrl}${brandUrl}`;
  const shareText = `Check out ${brandName} - Premium Skincare`;
  
  const shareLinks = {
    twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(fullUrl)}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(fullUrl)}`,
    whatsapp: `https://wa.me/?text=${encodeURIComponent(`${shareText} ${fullUrl}`)}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(fullUrl)}`,
  };
  
  const handleShare = (e, platform) => {
    e.stopPropagation();
    window.open(shareLinks[platform], '_blank', 'width=600,height=400');
  };
  
  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      toast.success('Link copied!');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback
      const textArea = document.createElement('textarea');
      textArea.value = fullUrl;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      toast.success('Link copied!');
      setTimeout(() => setCopied(false), 2000);
    }
  };
  
  const isLight = theme === 'light';
  const iconClass = `w-3.5 h-3.5 ${isLight ? 'text-[#5D6D7E] group-hover:text-[#E6BE8A]' : 'text-white/50 group-hover:text-[#D4AF37]'}`;
  const btnClass = `group p-1.5 rounded-full ${isLight ? 'hover:bg-[#E6BE8A]/10' : 'hover:bg-[#D4AF37]/10'} transition-colors`;
  
  return (
    <div className="flex items-center gap-1 mt-2" onClick={(e) => e.stopPropagation()}>
      <button onClick={(e) => handleShare(e, 'twitter')} className={btnClass} title="Share on X">
        <TwitterIcon className={iconClass} />
      </button>
      <button onClick={(e) => handleShare(e, 'facebook')} className={btnClass} title="Share on Facebook">
        <FacebookIcon className={iconClass} />
      </button>
      <button onClick={(e) => handleShare(e, 'whatsapp')} className={btnClass} title="Share on WhatsApp">
        <WhatsAppIcon className={iconClass} />
      </button>
      <button onClick={(e) => handleShare(e, 'linkedin')} className={btnClass} title="Share on LinkedIn">
        <LinkedInIcon className={iconClass} />
      </button>
      <div className={`w-px h-4 mx-1 ${isLight ? 'bg-[#5D6D7E]/20' : 'bg-white/20'}`} />
      <button onClick={handleCopy} className={btnClass} title="Copy link">
        {copied ? (
          <Check className={`w-3.5 h-3.5 ${isLight ? 'text-green-500' : 'text-green-400'}`} />
        ) : (
          <Copy className={iconClass} />
        )}
      </button>
    </div>
  );
};

// Dual Brand Discovery Banner - Split button for OROÉ & LA VELA BIANCA
const DualBrandBanner = () => {
  const [activePanel, setActivePanel] = useState(null); // null, 'lavela', 'oroe'

  const openPanel = (brand) => {
    setActivePanel(brand);
    document.body.style.overflow = 'hidden';
  };

  const closePanel = () => {
    setActivePanel(null);
    document.body.style.overflow = 'auto';
  };

  return (
    <>
      {/* Split Brand Banner */}
      <div className="max-w-4xl mx-auto overflow-hidden rounded-xl border border-[#D4AF37]/20">
        <div className="flex">
          {/* LEFT - LA VELA BIANCA - Midnight to Dawn Theme */}
          <div
            onClick={() => openPanel('lavela')}
            className="flex-1 group relative p-4 sm:p-5 bg-gradient-to-br from-[#0D4D4D] via-[#1A6B6B] to-[#D4A090] hover:from-[#1A5C5C] hover:via-[#1A6B6B] hover:to-[#E8C4B8] transition-all duration-500 cursor-pointer"
            data-testid="discover-lavela-btn"
          >
            {/* Stars decoration */}
            <div className="absolute inset-0 overflow-hidden opacity-30">
              <div className="absolute top-2 left-4 w-1 h-1 rounded-full bg-[#F0E6D3]"></div>
              <div className="absolute top-4 left-12 w-1.5 h-1.5 rounded-full bg-[#E6BE8A]"></div>
              <div className="absolute top-6 right-8 w-1 h-1 rounded-full bg-[#F0E6D3]"></div>
              <div className="absolute bottom-4 left-8 w-1 h-1 rounded-full bg-[#F0E6D3]"></div>
              <div className="absolute bottom-6 right-12 w-1.5 h-1.5 rounded-full bg-[#E6BE8A]"></div>
            </div>
            
            {/* Content */}
            <div className="relative z-10 flex items-center gap-3 sm:gap-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-gradient-to-br from-[#E6BE8A] to-[#D4A574] flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform shadow-lg">
                <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
              </div>
              <div className="text-left">
                <p className="text-[8px] sm:text-[10px] tracking-[0.2em] text-[#E6BE8A] uppercase mb-0.5">Teen Skincare</p>
                <h4 className="text-sm sm:text-base font-semibold text-white group-hover:text-[#E6BE8A] transition-colors" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                  LA VELA BIANCA
                </h4>
                <p className="text-[10px] sm:text-xs text-[#F5DED6]/70 hidden sm:block">The New Era of Elite Glow</p>
                
                {/* Share Buttons */}
                <ShareButtons brandUrl="/la-vela-bianca" brandName="LA VELA BIANCA" theme="dark" />
              </div>
            </div>
            
            {/* Arrow */}
            <div className="absolute left-2 top-1/2 -translate-y-1/2 text-[#E6BE8A] opacity-50 group-hover:opacity-100 group-hover:-translate-x-1 transition-all">
              <ChevronLeft className="w-4 h-4" />
            </div>

            {/* Divider */}
            <div className="absolute right-0 top-2 bottom-2 w-px bg-gradient-to-b from-transparent via-[#D4AF37]/30 to-transparent" />
          </div>

          {/* RIGHT - OROÉ */}
          <div
            onClick={() => openPanel('oroe')}
            className="flex-1 group relative p-4 sm:p-5 bg-gradient-to-bl from-[#0A0A0A] via-[#1A1A1A] to-[#0A0A0A] hover:from-[#1A1A1A] hover:via-[#2A2A2A] hover:to-[#1A1A1A] transition-all duration-500 cursor-pointer"
            data-testid="discover-oroe-btn"
          >
            {/* Content */}
            <div className="flex items-center justify-end gap-3 sm:gap-4">
              <div className="text-right">
                <p className="text-[8px] sm:text-[10px] tracking-[0.2em] text-[#D4AF37]/60 uppercase mb-0.5">Luxury Collection</p>
                <h4 className="text-sm sm:text-base font-semibold text-[#D4AF37] group-hover:text-[#FFD700] transition-colors" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                  OROÉ
                </h4>
                <p className="text-[10px] sm:text-xs text-white/50 hidden sm:block">Where Science Meets Splendor</p>
                
                {/* Share Buttons */}
                <div className="flex justify-end">
                  <ShareButtons brandUrl="/oroe" brandName="OROÉ" theme="dark" />
                </div>
              </div>
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-gradient-to-br from-[#D4AF37] to-[#B8860B] flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
                <Crown className="w-4 h-4 sm:w-5 sm:h-5 text-[#0A0A0A]" />
              </div>
            </div>
            
            {/* Arrow */}
            <div className="absolute right-2 top-1/2 -translate-y-1/2 text-[#D4AF37] opacity-50 group-hover:opacity-100 group-hover:translate-x-1 transition-all">
              <ChevronRight className="w-4 h-4" />
            </div>
          </div>
        </div>
      </div>

      {/* LA VELA BIANCA Full Page Overlay - Slides from LEFT */}
      <AnimatePresence>
        {activePanel === 'lavela' && (
          <m.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'tween', duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
            className="fixed inset-0 z-[100] bg-[#FBFCFC] overflow-y-auto"
          >
            {/* Close Button */}
            <button
              onClick={closePanel}
              className="fixed top-4 right-4 z-[110] w-11 h-11 rounded-full bg-[#E6BE8A] flex items-center justify-center hover:bg-[#D4A574] transition-colors shadow-lg"
              data-testid="close-lavela-panel"
            >
              <X className="w-5 h-5 text-white" />
            </button>
            
            {/* Switch to OROÉ */}
            <button
              onClick={() => setActivePanel('oroe')}
              className="fixed bottom-4 right-4 z-[110] px-4 py-3 rounded-full bg-[#0A0A0A] text-[#D4AF37] text-sm font-medium flex items-center gap-2 hover:bg-[#1A1A1A] transition-colors shadow-lg"
            >
              <span>View OROÉ</span>
              <ChevronRight className="w-4 h-4" />
            </button>

            {/* Full Page Content */}
            <React.Suspense fallback={
              <div className="min-h-screen flex items-center justify-center">
                <div className="text-[#E6BE8A] animate-pulse">Loading...</div>
              </div>
            }>
              <LaVelaLandingPage />
            </React.Suspense>
          </m.div>
        )}
      </AnimatePresence>

      {/* OROÉ Full Page Overlay - Slides from RIGHT */}
      <AnimatePresence>
        {activePanel === 'oroe' && (
          <m.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
            className="fixed inset-0 z-[100] bg-[#0A0A0A] overflow-y-auto"
          >
            {/* Close Button */}
            <button
              onClick={closePanel}
              className="fixed top-4 left-4 z-[110] w-11 h-11 rounded-full bg-[#D4AF37] flex items-center justify-center hover:bg-[#B8860B] transition-colors shadow-lg"
              data-testid="close-oroe-panel"
            >
              <X className="w-5 h-5 text-[#0A0A0A]" />
            </button>
            
            {/* Switch to LA VELA BIANCA */}
            <button
              onClick={() => setActivePanel('lavela')}
              className="fixed bottom-4 left-4 z-[110] px-4 py-3 rounded-full bg-[#FBFCFC] text-[#E6BE8A] text-sm font-medium flex items-center gap-2 hover:bg-[#FDEDEC] transition-colors shadow-lg"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>View LA VELA</span>
            </button>

            {/* Full Page Content */}
            <React.Suspense fallback={
              <div className="min-h-screen flex items-center justify-center">
                <div className="text-[#D4AF37] animate-pulse">Loading...</div>
              </div>
            }>
              <OroeLandingPage />
            </React.Suspense>
          </m.div>
        )}
      </AnimatePresence>

      {/* Fonts now self-hosted via @fontsource - see index.css */}
    </>
  );
};

export default DualBrandBanner;
