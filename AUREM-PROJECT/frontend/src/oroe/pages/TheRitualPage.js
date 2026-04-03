import React, { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import "../styles/oroe-design-system.css";

// The Ritual - Hidden VIP Experience
// Mobile-first design optimized for iPhone and luxury traveling customers
const TheRitualPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(0);
  const [showContent, setShowContent] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentStepProgress, setCurrentStepProgress] = useState(0);
  const timerRef = useRef(null);
  const progressRef = useRef(null);
  
  // Get personalization from URL params (from QR code)
  const bottleNumber = searchParams.get('bottle') || searchParams.get('b');
  const accessCode = searchParams.get('code') || searchParams.get('c');
  const productName = searchParams.get('product') || 'Luminous Elixir';
  
  // Ritual steps - optimized timing for mobile experience
  const ritualSteps = [
    {
      title: "Prepare Your Sanctuary",
      instruction: "Find a quiet moment. Dim the lights. This is your time.",
      duration: 5000,
      icon: "🕯️"
    },
    {
      title: "Warm The Elixir",
      instruction: "Place 2-3 drops in your palm. Gently rub your hands together to activate the golden essence.",
      duration: 7000,
      icon: "✨"
    },
    {
      title: "The Golden Touch",
      instruction: "Press your palms to your face. Hold for 10 seconds. Feel the warmth transfer.",
      duration: 10000,
      icon: "🙏"
    },
    {
      title: "Ascending Strokes",
      instruction: "Using upward motions, massage from chin to forehead. Let the gold particles illuminate your path.",
      duration: 8000,
      icon: "⬆️"
    },
    {
      title: "The Temple Points",
      instruction: "Gently press your temples, the center of your forehead, and along your cheekbones.",
      duration: 8000,
      icon: "💎"
    },
    {
      title: "Seal The Light",
      instruction: "Cup your face in your hands. Breathe deeply. The ritual is complete.",
      duration: 6000,
      icon: "🌟"
    }
  ];

  useEffect(() => {
    // Entrance animation - slightly faster on mobile
    setTimeout(() => setShowContent(true), 300);
    
    // Prevent zoom on double-tap (iOS)
    document.addEventListener('gesturestart', (e) => e.preventDefault());
    
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (progressRef.current) clearInterval(progressRef.current);
    };
  }, []);

  const startRitual = () => {
    setStep(1);
    setCurrentStepProgress(0);
    runStep(1);
  };

  const runStep = (stepNum) => {
    if (stepNum > ritualSteps.length) {
      setStep(ritualSteps.length + 1); // Completion state
      return;
    }
    
    const duration = ritualSteps[stepNum - 1].duration;
    const startTime = Date.now();
    
    // Smooth progress animation
    progressRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min((elapsed / duration) * 100, 100);
      setCurrentStepProgress(progress);
    }, 50);
    
    timerRef.current = setTimeout(() => {
      clearInterval(progressRef.current);
      setCurrentStepProgress(0);
      setStep(stepNum + 1);
      runStep(stepNum + 1);
    }, duration);
  };

  const skipStep = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (progressRef.current) clearInterval(progressRef.current);
    setCurrentStepProgress(0);
    
    if (step < ritualSteps.length) {
      setStep(step + 1);
      runStep(step + 1);
    } else {
      setStep(ritualSteps.length + 1);
    }
  };

  const restartRitual = () => {
    setStep(0);
    setCurrentStepProgress(0);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (progressRef.current) clearInterval(progressRef.current);
  };

  const currentRitual = step > 0 && step <= ritualSteps.length ? ritualSteps[step - 1] : null;
  const overallProgress = step > 0 ? ((step - 1) / ritualSteps.length) * 100 + (currentStepProgress / ritualSteps.length) : 0;

  return (
    <div className="min-h-screen min-h-[100dvh] bg-[#0A0A0A] text-[#FDF8F0] overflow-hidden touch-manipulation">
      {/* iOS Safe Area Support */}
      <style>{`
        @supports (padding: env(safe-area-inset-top)) {
          .safe-area-top { padding-top: env(safe-area-inset-top); }
          .safe-area-bottom { padding-bottom: env(safe-area-inset-bottom); }
        }
        
        /* Prevent text selection during ritual */
        .ritual-content { 
          -webkit-user-select: none; 
          user-select: none;
          -webkit-tap-highlight-color: transparent;
        }
        
        /* Smooth icon animation */
        @keyframes gentlePulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.1); opacity: 0.9; }
        }
        .icon-pulse { animation: gentlePulse 2s ease-in-out infinite; }
        
        /* Gold shimmer effect */
        @keyframes goldShimmer {
          0% { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
        .gold-shimmer {
          background: linear-gradient(90deg, #D4AF37 0%, #FFD700 25%, #D4AF37 50%, #B8860B 75%, #D4AF37 100%);
          background-size: 200% auto;
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: goldShimmer 3s linear infinite;
        }
      `}</style>

      {/* Ambient Background - Optimized for mobile GPU */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-b from-[#D4AF37]/5 via-transparent to-[#D4AF37]/5" />
        <div 
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            width: 'min(600px, 150vw)',
            height: 'min(600px, 150vw)',
            background: 'radial-gradient(circle, rgba(212,175,55,0.08) 0%, transparent 70%)',
            filter: 'blur(60px)',
          }}
        />
      </div>

      {/* Content */}
      <div 
        className={`ritual-content relative z-10 min-h-screen min-h-[100dvh] flex flex-col items-center justify-center px-6 py-8 safe-area-top safe-area-bottom transition-all duration-700 ${showContent ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'}`}
      >
        
        {/* Pre-Ritual State */}
        {step === 0 && (
          <div className="text-center w-full max-w-sm mx-auto space-y-6 sm:space-y-8">
            {/* Logo - Retina optimized */}
            <div className="mb-8 sm:mb-12">
              <img 
                src="/oroe-logo.png" 
                alt="OROÉ" 
                className="h-16 sm:h-20 w-auto mx-auto opacity-90"
                loading="eager"
                decoding="async"
              />
            </div>
            
            {/* Personalized Welcome - Only if bottle number present */}
            {bottleNumber && (
              <div className="mb-4 py-3 px-4 border border-[#D4AF37]/30 rounded-sm bg-[#D4AF37]/5">
                <p className="text-[10px] tracking-[0.3em] text-[#D4AF37]/70 uppercase mb-1">
                  Certificate #{bottleNumber}
                </p>
                <p className="text-xs text-[#FDF8F0]/50">
                  {productName}
                </p>
              </div>
            )}
            
            {/* Title */}
            <div className="space-y-3">
              <p className="text-[10px] sm:text-xs tracking-[0.4em] text-[#D4AF37]/70 uppercase">
                {bottleNumber ? 'Your Exclusive' : 'Welcome to'}
              </p>
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-display gold-shimmer">
                The Ritual
              </h1>
              <div className="w-16 sm:w-24 h-px bg-gradient-to-r from-transparent via-[#D4AF37]/50 to-transparent mx-auto" />
            </div>
            
            {/* Description - Mobile optimized line height */}
            <p className="text-base sm:text-lg text-[#FDF8F0]/60 leading-relaxed font-light px-2">
              You hold in your hands more than a serum—you hold a moment of transformation.
            </p>
            
            {/* Duration Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#D4AF37]/20 bg-[#D4AF37]/5">
              <span className="text-xs text-[#D4AF37]/70">⏱</span>
              <span className="text-xs text-[#D4AF37]/70">~45 seconds</span>
            </div>
            
            {/* Start Button - Large touch target for mobile */}
            <button
              onClick={startRitual}
              className="group relative w-full sm:w-auto px-10 sm:px-14 py-5 mt-4 overflow-hidden rounded-sm border border-[#D4AF37]/50 bg-transparent active:bg-[#D4AF37]/10 transition-all duration-300"
              data-testid="start-ritual-btn"
            >
              <span className="absolute inset-0 bg-gradient-to-r from-[#D4AF37]/0 via-[#D4AF37]/10 to-[#D4AF37]/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
              <span className="relative text-sm tracking-[0.25em] uppercase text-[#D4AF37] font-medium">
                Begin The Ritual
              </span>
            </button>
            
            {/* Return Link */}
            <button 
              onClick={() => navigate('/oroe')}
              className="text-xs text-[#FDF8F0]/30 hover:text-[#FDF8F0]/50 active:text-[#D4AF37]/50 transition-colors py-2"
            >
              Return to Maison
            </button>
          </div>
        )}

        {/* Active Ritual */}
        {step > 0 && step <= ritualSteps.length && (
          <div className="text-center w-full max-w-sm mx-auto space-y-8 sm:space-y-10">
            {/* Overall Progress Bar */}
            <div className="w-full px-4">
              <div className="h-1 bg-[#D4AF37]/20 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-[#D4AF37] to-[#B8860B] rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${overallProgress}%` }}
                />
              </div>
              <p className="text-[10px] sm:text-xs text-[#D4AF37]/50 mt-2 tracking-wider">
                Step {step} of {ritualSteps.length}
              </p>
            </div>

            {/* Step Icon - Large for mobile visibility */}
            <div className="text-6xl sm:text-7xl icon-pulse py-4">
              {currentRitual.icon}
            </div>

            {/* Step Content */}
            <div className="space-y-4 sm:space-y-6 px-2">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-display gold-shimmer">
                {currentRitual.title}
              </h2>
              <p className="text-base sm:text-lg text-[#FDF8F0]/70 leading-relaxed font-light">
                {currentRitual.instruction}
              </p>
            </div>

            {/* Step Timer Ring */}
            <div className="relative w-20 h-20 sm:w-24 sm:h-24 mx-auto">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 96 96">
                <circle
                  cx="48"
                  cy="48"
                  r="44"
                  stroke="currentColor"
                  strokeWidth="2"
                  fill="none"
                  className="text-[#D4AF37]/20"
                />
                <circle
                  cx="48"
                  cy="48"
                  r="44"
                  stroke="url(#goldGradientMobile)"
                  strokeWidth="3"
                  fill="none"
                  strokeLinecap="round"
                  className="transition-all duration-100 ease-linear"
                  style={{
                    strokeDasharray: 276,
                    strokeDashoffset: 276 - (276 * currentStepProgress / 100)
                  }}
                />
                <defs>
                  <linearGradient id="goldGradientMobile" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#D4AF37" />
                    <stop offset="100%" stopColor="#FFD700" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xs text-[#D4AF37]/60">
                  {Math.ceil((100 - currentStepProgress) / 100 * (currentRitual.duration / 1000))}s
                </span>
              </div>
            </div>

            {/* Skip Button - Mobile friendly */}
            <button
              onClick={skipStep}
              className="text-xs text-[#FDF8F0]/30 hover:text-[#FDF8F0]/50 active:text-[#D4AF37]/50 transition-colors py-2 px-4"
            >
              Skip to next →
            </button>
          </div>
        )}

        {/* Completion State */}
        {step > ritualSteps.length && (
          <div className="text-center w-full max-w-sm mx-auto space-y-6 sm:space-y-8 px-4">
            {/* Completion Icon */}
            <div className="text-6xl sm:text-7xl icon-pulse">✨</div>
            
            {/* Title */}
            <div className="space-y-3">
              <h2 className="text-2xl sm:text-3xl font-display gold-shimmer">
                The Ritual Is Complete
              </h2>
              <div className="w-16 sm:w-24 h-px bg-gradient-to-r from-transparent via-[#D4AF37]/50 to-transparent mx-auto" />
            </div>
            
            {/* Personalized completion message */}
            {bottleNumber ? (
              <div className="space-y-3">
                <p className="text-base sm:text-lg text-[#FDF8F0]/60 leading-relaxed font-light">
                  Certificate #{bottleNumber} has been honored with its first ritual.
                </p>
                <p className="text-sm text-[#FDF8F0]/40">
                  May your radiance grow with each application.
                </p>
              </div>
            ) : (
              <p className="text-base sm:text-lg text-[#FDF8F0]/60 leading-relaxed font-light">
                You have honored the golden light within. May your radiance grow with each dawn.
              </p>
            )}
            
            {/* Signature */}
            <div className="pt-6 border-t border-[#D4AF37]/20">
              <p className="text-[10px] tracking-[0.3em] text-[#D4AF37]/50 uppercase mb-1">
                Maison OROÉ
              </p>
              <p className="text-xs text-[#FDF8F0]/40 italic">
                "Where Science Meets Splendor"
              </p>
            </div>
            
            {/* Actions - Full width on mobile */}
            <div className="flex flex-col gap-3 pt-4">
              <button
                onClick={restartRitual}
                className="w-full px-6 py-4 text-sm tracking-[0.15em] uppercase text-[#D4AF37] border border-[#D4AF37]/50 rounded-sm active:bg-[#D4AF37]/10 transition-all"
              >
                Repeat Ritual
              </button>
              <button
                onClick={() => navigate('/oroe')}
                className="w-full px-6 py-4 text-sm tracking-[0.15em] uppercase bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A0A0A] rounded-sm active:opacity-90 transition-all font-medium"
              >
                Return to Maison
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TheRitualPage;
