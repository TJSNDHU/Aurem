import React, { useState } from "react";
import { X, Sparkles, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

const PromoPopup = ({ settings }) => {
  const [isVisible, setIsVisible] = useState(true);
  
  // Check if promo banner is enabled from admin settings
  const promoEnabled = settings?.promo_banner_enabled;
  
  if (!promoEnabled || !isVisible) return null;

  return (
    <>
      {/* Desktop: Tilted badge on left corner */}
      <div 
        className="absolute z-50 hidden md:block"
        style={{
          top: '-20px',
          left: '-60px',
        }}
      >
        <div 
          className="relative transform -rotate-12 hover:scale-105 transition-all duration-300"
          style={{
            filter: 'drop-shadow(0 10px 20px rgba(0,0,0,0.3))'
          }}
        >
          {/* Close button */}
          <button 
            onClick={(e) => { e.stopPropagation(); setIsVisible(false); }}
            className="absolute -top-2 -right-2 bg-black/80 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-black z-10"
          >
            <X className="h-3 w-3" />
          </button>
          
          {/* Badge - Gold gradient for founding member */}
          <Link to="/waitlist">
            <div 
              className="px-6 py-4 rounded-2xl cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, #D4AF37 0%, #F4D03F 50%, #C9A86C 100%)',
              }}
            >
              <div className="text-center text-[#2D2A2E]">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <Sparkles className="h-4 w-4" />
                  <p className="text-xs font-bold tracking-wider">FOUNDING</p>
                </div>
                <p className="text-xs font-bold tracking-wider mb-1">MEMBER</p>
                <p className="text-3xl font-black mb-1">
                  81%
                </p>
                <p className="text-xs font-bold tracking-wider">MAX SAVINGS</p>
                <div className="bg-black/10 rounded-lg px-3 py-1 mt-2">
                  <p className="text-xs font-semibold">Join Now →</p>
                </div>
              </div>
            </div>
          </Link>
        </div>
      </div>

      {/* Mobile: Clean horizontal banner at bottom */}
      <div className="md:hidden mt-4">
        <Link to="/waitlist">
          <div 
            className="relative flex items-center justify-between px-4 py-3 rounded-xl"
            style={{
              background: 'linear-gradient(135deg, #D4AF37 0%, #F4D03F 50%, #C9A86C 100%)',
            }}
          >
            {/* Close button */}
            <button 
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setIsVisible(false); }}
              className="absolute -top-2 -right-2 bg-black/80 text-white rounded-full w-5 h-5 flex items-center justify-center hover:bg-black z-10"
            >
              <X className="h-3 w-3" />
            </button>
            
            <div className="flex items-center gap-3">
              <div className="p-2 bg-black/10 rounded-lg">
                <Sparkles className="h-5 w-5 text-[#2D2A2E]" />
              </div>
              <div>
                <p className="text-xs font-bold text-[#2D2A2E] tracking-wide">FOUNDING MEMBER</p>
                <p className="text-lg font-black text-[#2D2A2E]">Up to 81% OFF</p>
              </div>
            </div>
            
            <div className="flex items-center gap-1 bg-[#2D2A2E] text-white px-3 py-2 rounded-lg">
              <span className="text-xs font-bold">Join</span>
              <ChevronRight className="h-4 w-4" />
            </div>
          </div>
        </Link>
      </div>
    </>
  );
};

export default PromoPopup;
