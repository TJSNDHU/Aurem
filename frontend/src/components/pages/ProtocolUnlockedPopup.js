import React, { useState, useEffect, useCallback } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sparkles, ChevronRight, Crown, Shield, Star, CheckCircle } from "lucide-react";

// Clinical Confetti Component - White and Silver sparkles
const ClinicalConfetti = ({ isActive }) => {
  const [particles, setParticles] = useState([]);

  useEffect(() => {
    if (isActive) {
      // Generate particles
      const newParticles = [];
      for (let i = 0; i < 80; i++) {
        newParticles.push({
          id: i,
          x: Math.random() * 100,
          delay: Math.random() * 0.5,
          duration: 2 + Math.random() * 2,
          size: 4 + Math.random() * 8,
          color: Math.random() > 0.3 
            ? (Math.random() > 0.5 ? '#ffffff' : '#e8e8e8')  // White/light grey
            : '#D4AF37', // Occasional gold sparkle
          rotation: Math.random() * 360,
          type: Math.random() > 0.7 ? 'star' : 'circle'
        });
      }
      setParticles(newParticles);
    }
  }, [isActive]);

  if (!isActive) return null;

  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
      {particles.map((particle) => (
        <div
          key={particle.id}
          className="absolute"
          style={{
            left: `${particle.x}%`,
            top: '-20px',
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            backgroundColor: particle.type === 'circle' ? particle.color : 'transparent',
            borderRadius: particle.type === 'circle' ? '50%' : '0',
            animation: `confettiFall ${particle.duration}s ease-out ${particle.delay}s forwards`,
            transform: `rotate(${particle.rotation}deg)`,
            boxShadow: particle.color === '#D4AF37' ? '0 0 6px rgba(212, 175, 55, 0.5)' : 'none'
          }}
        >
          {particle.type === 'star' && (
            <svg viewBox="0 0 24 24" fill={particle.color} className="w-full h-full">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
          )}
        </div>
      ))}
      <style>{`
        @keyframes confettiFall {
          0% {
            transform: translateY(0) rotate(0deg) scale(1);
            opacity: 1;
          }
          100% {
            transform: translateY(100vh) rotate(720deg) scale(0.5);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
};

const ProtocolUnlockedPopup = ({ 
  isOpen, 
  onClose, 
  retailPrice = 100.00,
  finalPrice = 70.00,  // FIXED: $70 Founding Member price
  userName = "Founding Member",
  onContinue
}) => {
  const [showConfetti, setShowConfetti] = useState(false);
  const [animationStage, setAnimationStage] = useState(0);

  useEffect(() => {
    if (isOpen) {
      // Start confetti after a brief delay
      setTimeout(() => setShowConfetti(true), 300);
      
      // Animate content in stages
      setTimeout(() => setAnimationStage(1), 100);
      setTimeout(() => setAnimationStage(2), 400);
      setTimeout(() => setAnimationStage(3), 700);
      setTimeout(() => setAnimationStage(4), 1000);
      
      // Stop confetti after 4 seconds
      setTimeout(() => setShowConfetti(false), 4000);
    } else {
      setAnimationStage(0);
      setShowConfetti(false);
    }
  }, [isOpen]);

  const taxAmount = (retailPrice * 0.13).toFixed(2);
  const totalSavings = (retailPrice - finalPrice).toFixed(2);
  const savingsPercent = Math.round((1 - finalPrice / retailPrice) * 100);

  return (
    <>
      <ClinicalConfetti isActive={showConfetti} />
      
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent 
          className="max-w-lg p-0 bg-transparent border-0 shadow-none overflow-hidden"
          style={{ maxHeight: '90vh' }}
        >
          {/* Accessibility: Hidden title for screen readers */}
          <DialogTitle className="sr-only">Protocol Unlocked - Voucher Activated</DialogTitle>
          
          {/* Glassmorphism Container */}
          <div 
            className="relative rounded-2xl overflow-hidden"
            style={{
              background: "rgba(10, 10, 10, 0.85)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              border: "1px solid rgba(212, 175, 55, 0.3)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 80px rgba(212, 175, 55, 0.15)"
            }}
          >
            {/* Golden Top Border */}
            <div 
              className="h-1 w-full"
              style={{
                background: "linear-gradient(90deg, transparent 0%, #D4AF37 50%, transparent 100%)"
              }}
            />

            {/* Background Glow Effect */}
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full bg-[#D4AF37]/10 blur-[80px]" />
            </div>

            <div className="relative z-10 p-8 text-center">
              
              {/* Protocol Badge */}
              <div 
                className={`transition-all duration-500 ${animationStage >= 1 ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'}`}
              >
                <div 
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-4"
                  style={{
                    background: "linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.1) 100%)",
                    border: "1px solid rgba(212, 175, 55, 0.3)"
                  }}
                >
                  <span className="text-lg">🧬</span>
                  <span className="text-[#D4AF37] text-xs font-bold tracking-[0.2em] uppercase">
                    Protocol Level: LEAD
                  </span>
                </div>
              </div>

              {/* Status Badge */}
              <div 
                className={`transition-all duration-500 delay-100 ${animationStage >= 1 ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'}`}
              >
                <Badge 
                  className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0a0a0a] font-bold px-4 py-1.5 text-sm mb-6"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Influencer Voucher ACTIVATED
                </Badge>
              </div>

              {/* Crown Icon */}
              <div 
                className={`transition-all duration-700 delay-200 ${animationStage >= 2 ? 'opacity-100 scale-100' : 'opacity-0 scale-50'}`}
              >
                <div 
                  className="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center"
                  style={{
                    background: "linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.05) 100%)",
                    border: "2px solid #D4AF37",
                    boxShadow: "0 0 30px rgba(212, 175, 55, 0.3)"
                  }}
                >
                  <Crown className="w-10 h-10 text-[#D4AF37]" />
                </div>
              </div>

              {/* Congratulations Message */}
              <div 
                className={`transition-all duration-500 delay-300 ${animationStage >= 2 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
              >
                <h2 
                  className="text-2xl md:text-3xl font-bold text-white mb-4"
                  style={{ fontFamily: '"Playfair Display", serif' }}
                >
                  Congratulations, <span className="text-[#D4AF37]">{userName}</span>.
                </h2>
                
                <p className="text-white/70 text-sm leading-relaxed mb-8 max-w-sm mx-auto">
                  You have successfully completed the referral mission. Your dedication to the 
                  ReRoots community has unlocked the <span className="text-[#D4AF37] font-semibold">maximum Founding Member subsidy</span>.
                </p>
              </div>

              {/* Price Reveal Card */}
              <div 
                className={`transition-all duration-700 delay-500 ${animationStage >= 3 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
              >
                <div 
                  className="rounded-xl overflow-hidden mb-6"
                  style={{
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(212, 175, 55, 0.2)"
                  }}
                >
                  {/* Retail Value */}
                  <div className="flex justify-between items-center px-5 py-3 border-b border-white/5">
                    <span className="text-white/50 text-sm">Retail Value</span>
                    <span className="text-white/50 line-through">${retailPrice.toFixed(2)}</span>
                  </div>
                  
                  {/* Your Exclusive Price */}
                  <div 
                    className="flex justify-between items-center px-5 py-4"
                    style={{ background: "linear-gradient(135deg, rgba(212, 175, 55, 0.1) 0%, rgba(212, 175, 55, 0.05) 100%)" }}
                  >
                    <div className="flex items-center gap-2">
                      <Star className="w-5 h-5 text-[#D4AF37]" />
                      <span className="text-white font-semibold">Your Exclusive Price</span>
                    </div>
                    <span 
                      className="text-3xl font-bold"
                      style={{
                        background: "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent"
                      }}
                    >
                      ${finalPrice.toFixed(2)}
                    </span>
                  </div>
                  
                  {/* Tax Note */}
                  <div className="px-5 py-2 border-t border-white/5">
                    <p className="text-white/40 text-xs text-center">
                      + ${taxAmount} HST (based on Retail Value)
                    </p>
                  </div>
                </div>

                {/* Total Savings Badge */}
                <div 
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-6"
                  style={{
                    background: "linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.05) 100%)",
                    border: "1px solid rgba(212, 175, 55, 0.3)"
                  }}
                >
                  <Sparkles className="w-4 h-4 text-[#D4AF37]" />
                  <span className="text-[#D4AF37] font-bold">
                    You Save ${totalSavings} ({savingsPercent}% OFF)
                  </span>
                </div>
              </div>

              {/* Next Step Message */}
              <div 
                className={`transition-all duration-500 delay-700 ${animationStage >= 4 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
              >
                <div 
                  className="rounded-lg p-4 mb-6"
                  style={{
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid rgba(255, 255, 255, 0.05)"
                  }}
                >
                  <div className="flex items-start gap-3">
                    <Shield className="w-5 h-5 text-[#D4AF37] flex-shrink-0 mt-0.5" />
                    <p className="text-white/60 text-sm text-left leading-relaxed">
                      Your profile has been flagged for <span className="text-white font-medium">Priority Shipment</span>. 
                      The moment we go live, your unique checkout link will be sent to your inbox. 
                      <span className="text-[#D4AF37]"> Stay tuned—the future of your skin is almost here.</span>
                    </p>
                  </div>
                </div>

                {/* CTA Button */}
                <Button
                  onClick={onContinue || onClose}
                  className="w-full h-14 text-lg font-bold rounded-xl transition-all duration-300 hover:scale-[1.02]"
                  style={{
                    background: "linear-gradient(135deg, #D4AF37 0%, #B8960F 100%)",
                    color: "#0a0a0a",
                    boxShadow: "0 4px 20px rgba(212, 175, 55, 0.3)"
                  }}
                >
                  <Crown className="w-5 h-5 mr-2" />
                  View My VIP Dashboard
                  <ChevronRight className="w-5 h-5 ml-2" />
                </Button>

                {/* VIP Status Note */}
                <p className="text-white/30 text-xs mt-4">
                  You are now in the <span className="text-[#D4AF37]">Top 1%</span> of Founding Members
                </p>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ProtocolUnlockedPopup;
