import React, { useRef } from 'react';
// PERF: Use LazyMotionWrapper + direct framer-motion hooks for scroll-driven animations
import { m } from '@/components/LazyMotionWrapper';
import { useScroll, useTransform } from 'framer-motion';
import { TrendingUp, Droplets, Sparkles, Heart, Shield, Award } from 'lucide-react';

const clinicalStats = [
  {
    id: 1,
    value: 93,
    label: "Visible Improvement",
    description: "Participants reported visible improvement in overall skin appearance after 8 weeks",
    icon: TrendingUp,
    color: "from-emerald-500 to-green-600",
    bgColor: "bg-emerald-500/10",
    iconBg: "bg-emerald-500/20"
  },
  {
    id: 2,
    value: 89,
    label: "Texture Refinement",
    description: "Noticed smoother, more refined skin texture with reduced appearance of pores",
    icon: Sparkles,
    color: "from-amber-500 to-yellow-600",
    bgColor: "bg-amber-500/10",
    iconBg: "bg-amber-500/20"
  },
  {
    id: 3,
    value: 91,
    label: "Hydration Boost",
    description: "Experienced long-lasting hydration and improved skin barrier function",
    icon: Droplets,
    color: "from-blue-500 to-cyan-600",
    bgColor: "bg-blue-500/10",
    iconBg: "bg-blue-500/20"
  },
  {
    id: 4,
    value: 87,
    label: "Firmness & Elasticity",
    description: "Reported firmer, more elastic skin with visibly reduced fine lines",
    icon: Shield,
    color: "from-violet-500 to-purple-600",
    bgColor: "bg-violet-500/10",
    iconBg: "bg-violet-500/20"
  },
  {
    id: 5,
    value: 96,
    label: "Would Recommend",
    description: "Said they would recommend ReRoots to friends and family",
    icon: Heart,
    color: "from-rose-500 to-pink-600",
    bgColor: "bg-rose-500/10",
    iconBg: "bg-rose-500/20"
  }
];

const StickyClinicalProof = () => {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"]
  });

  return (
    <section 
      ref={containerRef} 
      className="relative bg-[#0a0a0a]"
      style={{ height: `${(clinicalStats.length + 1) * 100}vh` }}
    >
      {/* Sticky Container */}
      <div className="sticky top-0 h-screen overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#0a0a0a] via-[#111] to-[#0a0a0a]" />
        
        {/* Animated background particles */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-[#D4AF37]/5 blur-[120px] animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-[#F8A5B8]/5 blur-[100px] animate-pulse" style={{ animationDelay: '1s' }} />
        </div>

        {/* Header - Always visible */}
        <div className="relative z-10 pt-16 md:pt-24 px-6 md:px-12">
          <div className="max-w-6xl mx-auto text-center">
            <m.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <span className="inline-block px-4 py-1.5 bg-[#D4AF37]/10 text-[#D4AF37] rounded-full text-xs font-medium tracking-[0.2em] uppercase mb-6">
                Clinical Results
              </span>
              <h2 className="text-3xl md:text-5xl font-bold text-white mb-4" style={{ fontFamily: '"Playfair Display", serif' }}>
                Science You Can <span className="italic text-[#D4AF37]">See</span>
              </h2>
              <p className="text-white/60 max-w-xl mx-auto text-sm md:text-base">
                In a 12-week study with 150 participants, our bio-active PDRN formula showed remarkable results
              </p>
            </m.div>
          </div>
        </div>

        {/* Stats Cards - Scroll triggered */}
        <div className="relative z-10 flex items-center justify-center h-[60vh] px-6">
          {clinicalStats.map((stat, index) => {
            const start = index / clinicalStats.length;
            const end = (index + 1) / clinicalStats.length;
            
            return (
              <StatCard 
                key={stat.id} 
                stat={stat} 
                index={index}
                scrollProgress={scrollYProgress}
                start={start}
                end={end}
              />
            );
          })}
        </div>

        {/* Progress dots */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-2 z-20">
          {clinicalStats.map((_, index) => (
            <ProgressDot 
              key={index} 
              index={index} 
              scrollProgress={scrollYProgress}
              total={clinicalStats.length}
            />
          ))}
        </div>

        {/* Disclaimer */}
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2 text-center z-10">
          <p className="text-white/30 text-xs max-w-md">
            *Results from cosmetic appearance assessments. Individual results may vary.
          </p>
        </div>
      </div>
    </section>
  );
};

const StatCard = ({ stat, index, scrollProgress, start, end }) => {
  const Icon = stat.icon;
  
  // Calculate opacity and position based on scroll
  const opacity = useTransform(
    scrollProgress,
    [Math.max(0, start - 0.1), start, end - 0.05, end],
    [0, 1, 1, 0]
  );
  
  const y = useTransform(
    scrollProgress,
    [Math.max(0, start - 0.1), start, end - 0.05, end],
    [60, 0, 0, -60]
  );
  
  const scale = useTransform(
    scrollProgress,
    [Math.max(0, start - 0.1), start, end - 0.05, end],
    [0.9, 1, 1, 0.9]
  );

  return (
    <m.div
      style={{ opacity, y, scale }}
      className="absolute w-full max-w-md mx-auto"
    >
      <div className={`${stat.bgColor} backdrop-blur-xl rounded-3xl p-8 md:p-10 border border-white/10 shadow-2xl`}>
        {/* Icon */}
        <div className={`${stat.iconBg} w-16 h-16 rounded-2xl flex items-center justify-center mb-6`}>
          <Icon className="w-8 h-8 text-white" />
        </div>
        
        {/* Big number */}
        <div className="flex items-baseline gap-1 mb-4">
          <span 
            className={`text-7xl md:text-8xl font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`}
            style={{ fontFamily: '"JetBrains Mono", monospace' }}
          >
            {stat.value}
          </span>
          <span className="text-4xl md:text-5xl font-bold text-white/80">%</span>
        </div>
        
        {/* Label */}
        <h3 className="text-xl md:text-2xl font-semibold text-white mb-3" style={{ fontFamily: '"Playfair Display", serif' }}>
          {stat.label}
        </h3>
        
        {/* Description */}
        <p className="text-white/60 text-sm md:text-base leading-relaxed">
          {stat.description}
        </p>
      </div>
    </m.div>
  );
};

const ProgressDot = ({ index, scrollProgress, total }) => {
  const start = index / total;
  const end = (index + 1) / total;
  
  const scale = useTransform(
    scrollProgress,
    [start, (start + end) / 2, end],
    [1, 1.5, 1]
  );
  
  const backgroundColor = useTransform(
    scrollProgress,
    [start, (start + end) / 2, end],
    ['rgba(255,255,255,0.3)', '#D4AF37', 'rgba(255,255,255,0.3)']
  );

  return (
    <m.div
      style={{ scale, backgroundColor }}
      className="w-2 h-2 rounded-full"
    />
  );
};

export default StickyClinicalProof;
