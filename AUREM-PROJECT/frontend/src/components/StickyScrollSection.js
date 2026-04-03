import React, { useEffect, useRef, useState } from 'react';
// PERF: Use LazyMotionWrapper + direct framer-motion hooks for scroll-driven animations
import { m } from '@/components/LazyMotionWrapper';
import { useScroll, useTransform } from 'framer-motion';
import { Dna, Droplets, Sparkles, Shield, FlaskConical } from 'lucide-react';

const ingredients = [
  {
    id: 1,
    name: "PDRN",
    fullName: "Polydeoxyribonucleotide",
    concentration: "2%",
    tagline: "Salmon DNA Technology",
    description: "Activates cellular regeneration at the DNA level. Stimulates collagen production and accelerates skin repair.",
    benefits: ["Cellular Regeneration", "DNA Repair", "Collagen Boost"],
    color: "from-rose-500/20 to-pink-600/20",
    borderColor: "border-rose-500/30",
    iconBg: "bg-rose-500/20",
    icon: Dna,
    image: "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=400&q=80"
  },
  {
    id: 2,
    name: "Tranexamic Acid",
    fullName: "TXA",
    concentration: "5%",
    tagline: "Pigmentation Eraser",
    description: "Clinically proven to reduce hyperpigmentation by inhibiting melanin production. Fades dark spots in 8-12 weeks.",
    benefits: ["Dark Spot Correction", "Even Skin Tone", "Melasma Treatment"],
    color: "from-amber-500/20 to-yellow-600/20",
    borderColor: "border-amber-500/30",
    iconBg: "bg-amber-500/20",
    icon: Droplets,
    image: "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=400&q=80"
  },
  {
    id: 3,
    name: "Argireline",
    fullName: "Acetyl Hexapeptide-3",
    concentration: "10%",
    tagline: "Botox in a Bottle",
    description: "Relaxes facial muscles to reduce expression lines. Clinically shown to decrease wrinkle depth by 30% in 28 days.",
    benefits: ["Wrinkle Reduction", "Expression Lines", "Non-Invasive"],
    color: "from-violet-500/20 to-purple-600/20",
    borderColor: "border-violet-500/30",
    iconBg: "bg-violet-500/20",
    icon: Sparkles,
    image: "https://images.unsplash.com/photo-1596755389378-c31d21fd1273?w=400&q=80"
  },
  {
    id: 4,
    name: "Niacinamide",
    fullName: "Vitamin B3",
    concentration: "4%",
    tagline: "Barrier Protector",
    description: "Strengthens the skin barrier, reduces inflammation, and minimizes pore appearance for smoother, healthier skin.",
    benefits: ["Barrier Strength", "Pore Minimizing", "Anti-Inflammatory"],
    color: "from-emerald-500/20 to-teal-600/20",
    borderColor: "border-emerald-500/30",
    iconBg: "bg-emerald-500/20",
    icon: Shield,
    image: "https://images.unsplash.com/photo-1608248597279-f99d160bfcbc?w=400&q=80"
  }
];

const IngredientCard = ({ ingredient, index, progress }) => {
  const Icon = ingredient.icon;
  
  // Calculate transforms based on scroll progress
  const cardProgress = useTransform(
    progress,
    [index * 0.2, (index + 1) * 0.2, (index + 2) * 0.2],
    [100, 0, -100]
  );
  
  const opacity = useTransform(
    progress,
    [index * 0.2, (index + 0.5) * 0.2, (index + 1.5) * 0.2, (index + 2) * 0.2],
    [0, 1, 1, 0]
  );
  
  const scale = useTransform(
    progress,
    [index * 0.2, (index + 0.5) * 0.2, (index + 1.5) * 0.2, (index + 2) * 0.2],
    [0.8, 1, 1, 0.9]
  );
  
  const rotateX = useTransform(
    progress,
    [index * 0.2, (index + 0.5) * 0.2, (index + 1.5) * 0.2, (index + 2) * 0.2],
    [15, 0, 0, -10]
  );

  return (
    <m.div
      style={{
        y: cardProgress,
        opacity,
        scale,
        rotateX,
        transformPerspective: 1000,
      }}
      className={`absolute inset-0 flex items-center justify-center px-4 md:px-8`}
    >
      <div 
        className={`relative w-full max-w-5xl mx-auto bg-gradient-to-br ${ingredient.color} backdrop-blur-xl rounded-3xl border ${ingredient.borderColor} overflow-hidden shadow-2xl`}
      >
        {/* Glow effect */}
        <div className="absolute -inset-1 bg-gradient-to-r from-[#D4AF37]/20 via-[#F8A5B8]/20 to-[#D4AF37]/20 rounded-3xl blur-xl opacity-50" />
        
        <div className="relative grid md:grid-cols-2 gap-6 md:gap-12 p-6 md:p-12">
          {/* Left: Content */}
          <div className="flex flex-col justify-center space-y-4 md:space-y-6">
            {/* Badge */}
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 md:w-14 md:h-14 rounded-2xl ${ingredient.iconBg} flex items-center justify-center`}>
                <Icon className="w-6 h-6 md:w-7 md:h-7 text-white" />
              </div>
              <div>
                <span className="text-[#D4AF37] font-semibold text-sm tracking-wider">{ingredient.concentration}</span>
                <p className="text-white/60 text-xs">{ingredient.tagline}</p>
              </div>
            </div>
            
            {/* Title */}
            <div>
              <h3 className="text-3xl md:text-5xl font-luxury font-bold text-white mb-1">
                {ingredient.name}
              </h3>
              <p className="text-white/50 text-sm md:text-base font-light">{ingredient.fullName}</p>
            </div>
            
            {/* Description */}
            <p className="text-white/80 text-base md:text-lg leading-relaxed">
              {ingredient.description}
            </p>
            
            {/* Benefits */}
            <div className="flex flex-wrap gap-2 md:gap-3">
              {ingredient.benefits.map((benefit, i) => (
                <span 
                  key={i}
                  className="px-3 md:px-4 py-1.5 md:py-2 bg-white/10 backdrop-blur-sm rounded-full text-white/90 text-xs md:text-sm border border-white/10"
                >
                  {benefit}
                </span>
              ))}
            </div>
          </div>
          
          {/* Right: Visual */}
          <div className="relative flex items-center justify-center">
            {/* Animated circles */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-48 h-48 md:w-64 md:h-64 rounded-full border border-white/10 animate-pulse" />
              <div className="absolute w-36 h-36 md:w-48 md:h-48 rounded-full border border-white/20 animate-ping" style={{ animationDuration: '3s' }} />
            </div>
            
            {/* Molecule/Icon display */}
            <div className={`relative w-32 h-32 md:w-48 md:h-48 rounded-full ${ingredient.iconBg} flex items-center justify-center shadow-2xl`}>
              <Icon className="w-16 h-16 md:w-24 md:h-24 text-white/80" />
              
              {/* Floating particles */}
              {[...Array(6)].map((_, i) => (
                <m.div
                  key={i}
                  className="absolute w-2 h-2 md:w-3 md:h-3 rounded-full bg-white/40"
                  animate={{
                    x: [0, Math.random() * 60 - 30],
                    y: [0, Math.random() * 60 - 30],
                    opacity: [0.4, 0.8, 0.4],
                    scale: [1, 1.5, 1],
                  }}
                  transition={{
                    duration: 3 + Math.random() * 2,
                    repeat: Infinity,
                    repeatType: "reverse",
                    delay: i * 0.3,
                  }}
                  style={{
                    left: `${30 + Math.random() * 40}%`,
                    top: `${30 + Math.random() * 40}%`,
                  }}
                />
              ))}
            </div>
          </div>
        </div>
        
        {/* Card number */}
        <div className="absolute bottom-4 right-6 md:bottom-6 md:right-8 text-white/20 text-6xl md:text-8xl font-bold">
          0{index + 1}
        </div>
      </div>
    </m.div>
  );
};

// Progress bar for each ingredient
const ProgressBar = ({ index, scrollYProgress }) => {
  const height = useTransform(
    scrollYProgress,
    [index * 0.25, (index + 1) * 0.25],
    ["0%", "100%"]
  );
  
  return (
    <m.div className="w-2 h-8 md:h-12 rounded-full bg-white/10 overflow-hidden">
      <m.div
        className="w-full bg-[#D4AF37] rounded-full"
        style={{ height }}
      />
    </m.div>
  );
};

// Progress indicator component
const ProgressIndicator = ({ scrollYProgress }) => {
  return (
    <div className="absolute right-4 md:right-8 top-1/2 -translate-y-1/2 flex flex-col gap-2">
      {ingredients.map((_, index) => (
        <ProgressBar key={index} index={index} scrollYProgress={scrollYProgress} />
      ))}
    </div>
  );
};

const StickyScrollSection = () => {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"]
  });

  return (
    <section className="relative bg-[#1a1a1a]">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-gradient-to-b from-[#1a1a1a] via-[#1a1a1a] to-transparent pt-16 pb-8 md:pt-24 md:pb-12">
        <div className="max-w-4xl mx-auto text-center px-4">
          <m.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#D4AF37]/10 rounded-full mb-4 md:mb-6"
          >
            <FlaskConical className="w-4 h-4 text-[#D4AF37]" />
            <span className="text-[#D4AF37] text-sm font-medium tracking-wider">17% ACTIVE COMPLEX</span>
          </m.div>
          
          <m.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="text-3xl md:text-5xl lg:text-6xl font-luxury font-bold text-white mb-3 md:mb-4"
          >
            The Science Inside
          </m.h2>
          
          <m.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="text-white/60 text-base md:text-lg max-w-2xl mx-auto"
          >
            Four clinically-proven actives working in synergy to regenerate, brighten, and protect your skin.
          </m.p>
        </div>
      </div>
      
      {/* Sticky scroll container */}
      <div 
        ref={containerRef}
        className="relative"
        style={{ height: `${ingredients.length * 100}vh` }}
      >
        <div className="sticky top-0 h-screen overflow-hidden">
          {ingredients.map((ingredient, index) => (
            <IngredientCard
              key={ingredient.id}
              ingredient={ingredient}
              index={index}
              progress={scrollYProgress}
            />
          ))}
          
          {/* Progress indicator */}
          <ProgressIndicator scrollYProgress={scrollYProgress} />
        </div>
      </div>
      
      {/* Bottom fade */}
      <div className="h-32 bg-gradient-to-b from-[#1a1a1a] to-[#FDF9F9]" />
    </section>
  );
};

export default StickyScrollSection;
