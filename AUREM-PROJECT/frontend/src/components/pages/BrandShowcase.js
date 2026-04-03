import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, Sparkles, Crown, X } from "lucide-react";

// Import the actual brand landing pages
import LaVelaLandingPage from "../../lavela/pages/LaVelaLandingPage";
import OroeLandingPage from "../../oroe/pages/OroeLandingPage";

// Brand Showcase - Split Screen with Sliding Overlay Panels
const BrandShowcase = () => {
  const [activePanel, setActivePanel] = useState(null); // null, 'lavela', 'oroe'

  const openPanel = (brand) => {
    setActivePanel(brand);
    // Prevent body scroll when panel is open
    document.body.style.overflow = 'hidden';
  };

  const closePanel = () => {
    setActivePanel(null);
    document.body.style.overflow = 'auto';
  };

  return (
    <div className="min-h-screen overflow-hidden relative">
      {/* Split Screen - Two Halves */}
      <div className="flex min-h-screen">
        
        {/* LEFT HALF - LA VELA BIANCA */}
        <motion.div 
          className="w-1/2 min-h-screen relative cursor-pointer group"
          onClick={() => openPanel('lavela')}
          whileHover={{ scale: 1.01 }}
          transition={{ duration: 0.3 }}
        >
          {/* Background */}
          <div className="absolute inset-0 bg-gradient-to-br from-[#FBFCFC] via-[#FDEDEC] to-[#FADBD8]" />
          
          {/* Hover Overlay */}
          <div className="absolute inset-0 bg-[#E6BE8A]/0 group-hover:bg-[#E6BE8A]/10 transition-colors duration-300" />
          
          {/* Content */}
          <div className="relative z-10 h-full flex flex-col items-center justify-center p-8 text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#E6BE8A]/10 text-[#E6BE8A] text-xs tracking-wider mb-6">
              <Sparkles className="w-3 h-3" />
              TEEN SKINCARE
            </div>

            {/* Brand Name */}
            <h1 
              className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-light mb-1"
              style={{ fontFamily: "'Cormorant Garamond', serif", color: '#2C3E50' }}
            >
              LA VELA
            </h1>
            <h1 
              className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-semibold mb-6"
              style={{ 
                fontFamily: "'Cormorant Garamond', serif",
                background: 'linear-gradient(90deg, #E6BE8A, #D4A574, #E6BE8A)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}
            >
              BIANCA
            </h1>

            {/* Tagline */}
            <p className="text-[#5D6D7E] text-sm sm:text-base mb-8 max-w-xs leading-relaxed">
              The future of teen glow. Ages 8-16.
            </p>

            {/* Product Preview */}
            <div className="mb-8">
              <div className="w-20 h-28 mx-auto rounded-2xl bg-gradient-to-b from-[#FADBD8] to-[#F5B7B1] shadow-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform duration-300">
                <span className="text-3xl">🧴</span>
              </div>
              <p className="text-xs text-[#E6BE8A] tracking-wider">ORO ROSA</p>
              <p className="text-lg font-semibold text-[#2C3E50]">$49</p>
            </div>

            {/* CTA Hint */}
            <div className="flex items-center gap-2 text-[#E6BE8A] text-sm group-hover:gap-3 transition-all">
              <ChevronLeft className="w-4 h-4 animate-pulse" />
              <span>Click to Enter</span>
            </div>
          </div>

          {/* Edge Glow */}
          <div className="absolute right-0 top-0 bottom-0 w-1 bg-gradient-to-b from-transparent via-[#D4AF37]/30 to-transparent" />
        </motion.div>

        {/* RIGHT HALF - OROÉ */}
        <motion.div 
          className="w-1/2 min-h-screen relative cursor-pointer group"
          onClick={() => openPanel('oroe')}
          whileHover={{ scale: 1.01 }}
          transition={{ duration: 0.3 }}
        >
          {/* Background */}
          <div className="absolute inset-0 bg-gradient-to-bl from-[#0A0A0A] via-[#1A1A1A] to-[#0A0A0A]" />
          
          {/* Hover Overlay */}
          <div className="absolute inset-0 bg-[#D4AF37]/0 group-hover:bg-[#D4AF37]/5 transition-colors duration-300" />
          
          {/* Content */}
          <div className="relative z-10 h-full flex flex-col items-center justify-center p-8 text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#D4AF37]/10 text-[#D4AF37] text-xs tracking-wider mb-6">
              <Crown className="w-3 h-3" />
              LUXURY SKINCARE
            </div>

            {/* Brand Name */}
            <h1 
              className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-light tracking-wider mb-6"
              style={{ 
                fontFamily: "'Cormorant Garamond', serif",
                background: 'linear-gradient(90deg, #D4AF37, #FFD700, #D4AF37)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}
            >
              OROÉ
            </h1>

            {/* Tagline */}
            <p className="text-[#FDF8F0]/60 text-sm sm:text-base mb-8 max-w-xs leading-relaxed">
              Where science meets splendor. Limited edition.
            </p>

            {/* Product Preview */}
            <div className="mb-8">
              <div className="w-20 h-28 mx-auto rounded-2xl bg-gradient-to-b from-[#D4AF37]/20 to-[#0A0A0A] border border-[#D4AF37]/30 shadow-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform duration-300">
                <span className="text-3xl">✨</span>
              </div>
              <p className="text-xs text-[#D4AF37] tracking-wider">LUMINOUS ELIXIR</p>
              <p className="text-lg font-semibold text-[#FDF8F0]">$155</p>
            </div>

            {/* CTA Hint */}
            <div className="flex items-center gap-2 text-[#D4AF37] text-sm group-hover:gap-3 transition-all">
              <span>Click to Enter</span>
              <ChevronRight className="w-4 h-4 animate-pulse" />
            </div>
          </div>

          {/* Edge Glow */}
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-transparent via-[#D4AF37]/30 to-transparent" />
        </motion.div>
      </div>

      {/* LA VELA BIANCA Overlay Panel - Slides from LEFT */}
      <AnimatePresence>
        {activePanel === 'lavela' && (
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'tween', duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
            className="fixed inset-0 z-50 bg-[#FBFCFC] overflow-y-auto"
          >
            {/* Close Button */}
            <button
              onClick={closePanel}
              className="fixed top-4 right-4 z-[60] w-12 h-12 rounded-full bg-[#E6BE8A]/10 backdrop-blur-sm flex items-center justify-center hover:bg-[#E6BE8A]/20 transition-colors group"
              data-testid="close-lavela-panel"
            >
              <X className="w-5 h-5 text-[#E6BE8A] group-hover:rotate-90 transition-transform" />
            </button>
            
            {/* Switch to OROÉ Button */}
            <button
              onClick={() => setActivePanel('oroe')}
              className="fixed top-4 left-4 z-[60] px-4 py-2 rounded-full bg-[#0A0A0A]/80 backdrop-blur-sm text-[#D4AF37] text-sm flex items-center gap-2 hover:bg-[#0A0A0A] transition-colors"
            >
              <span>OROÉ</span>
              <ChevronRight className="w-4 h-4" />
            </button>

            {/* Full Landing Page */}
            <LaVelaLandingPage />
          </motion.div>
        )}
      </AnimatePresence>

      {/* OROÉ Overlay Panel - Slides from RIGHT */}
      <AnimatePresence>
        {activePanel === 'oroe' && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
            className="fixed inset-0 z-50 bg-[#0A0A0A] overflow-y-auto"
          >
            {/* Close Button */}
            <button
              onClick={closePanel}
              className="fixed top-4 left-4 z-[60] w-12 h-12 rounded-full bg-[#D4AF37]/10 backdrop-blur-sm flex items-center justify-center hover:bg-[#D4AF37]/20 transition-colors group"
              data-testid="close-oroe-panel"
            >
              <X className="w-5 h-5 text-[#D4AF37] group-hover:rotate-90 transition-transform" />
            </button>
            
            {/* Switch to LA VELA BIANCA Button */}
            <button
              onClick={() => setActivePanel('lavela')}
              className="fixed top-4 right-4 z-[60] px-4 py-2 rounded-full bg-[#FBFCFC]/80 backdrop-blur-sm text-[#E6BE8A] text-sm flex items-center gap-2 hover:bg-[#FBFCFC] transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>LA VELA</span>
            </button>

            {/* Full Landing Page */}
            <OroeLandingPage />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Fonts now self-hosted via @fontsource - see index.css */}
    </div>
  );
};

export default BrandShowcase;
