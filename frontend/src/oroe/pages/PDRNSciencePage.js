import React, { useEffect, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { 
  ArrowLeft, Dna, Microscope, Sparkles, Shield, Droplets, 
  Sun, Zap, FlaskConical, Atom, ChevronDown, ExternalLink
} from 'lucide-react';

/**
 * PDRN Science Deep-Dive Page
 * "The Science of Cellular Resurrection"
 * Medical journal meets high-fashion magazine aesthetic
 * Canadian Health Canada compliant copy
 */
const PDRNSciencePage = () => {
  const [activeSection, setActiveSection] = useState(null);
  const [scrollProgress, setScrollProgress] = useState(0);

  // Scroll progress with RAF throttling
  useEffect(() => {
    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
          const progress = (window.scrollY / totalHeight) * 100;
          setScrollProgress(progress);
          ticking = false;
        });
        ticking = true;
      }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <>
      <Helmet>
        <title>The Science of Cellular Resurrection | OROÉ</title>
        <meta name="description" content="Discover the biotech science behind PDRN, Argireline®, and our 5-Phase Radiance Matrix. Clinical-grade formulations for transformative skincare results." />
      </Helmet>
      
      <div className="min-h-screen bg-[#0A0A0A] text-white overflow-x-hidden">
        {/* Progress Bar */}
        <div className="fixed top-0 left-0 right-0 z-[60] h-[2px] bg-[#0A0A0A]">
          <div 
            className="h-full bg-gradient-to-r from-[#D4AF37] to-[#B8860B] transition-all duration-150"
            style={{ width: `${scrollProgress}%` }}
          />
        </div>

        {/* Navigation Header */}
        <header className="fixed top-0 left-0 right-0 z-50 bg-[#0A0A0A]/95 backdrop-blur-md border-b border-[#D4AF37]/20">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link to="/oroe" className="flex items-center gap-2 text-[#D4AF37] hover:text-[#B8860B] transition-colors group">
              <ArrowLeft className="h-5 w-5 group-hover:-translate-x-1 transition-transform" />
              <span className="text-sm tracking-wider">RETURN TO MAISON</span>
            </Link>
            <div className="text-center">
              <h1 className="text-xl font-serif tracking-[0.4em] text-[#D4AF37]">OROÉ</h1>
              <p className="text-[8px] tracking-[0.3em] text-[#D4AF37]/50 uppercase">Laboratoire Suisse</p>
            </div>
            <div className="w-32"></div>
          </div>
        </header>

        {/* Hero Section */}
        <section className="relative pt-32 pb-24 px-6 overflow-hidden">
          {/* Background DNA Helix Animation */}
          <div className="absolute inset-0 opacity-5">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px]">
              <Dna className="w-full h-full text-[#D4AF37] animate-spin" style={{ animationDuration: '60s' }} />
            </div>
          </div>
          
          <div className="max-w-4xl mx-auto text-center relative z-10">
            {/* Journal Badge */}
            <div className="inline-flex items-center gap-3 mb-8 px-6 py-3 rounded-full bg-[#D4AF37]/5 border border-[#D4AF37]/30">
              <FlaskConical className="h-4 w-4 text-[#D4AF37]" />
              <span className="text-xs text-[#D4AF37] tracking-[0.2em] uppercase">Clinical Biotech Research</span>
              <span className="text-[#D4AF37]/30">|</span>
              <span className="text-xs text-[#D4AF37]/70">Vol. I • 2025</span>
            </div>
            
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-serif text-white mb-6 leading-[1.1]">
              The Science of<br />
              <span className="bg-gradient-to-r from-[#D4AF37] via-[#F4E4BA] to-[#D4AF37] bg-clip-text text-transparent">
                Cellular Resurrection
              </span>
            </h1>
            
            <p className="text-lg md:text-xl text-[#D4AF37]/60 max-w-2xl mx-auto leading-relaxed font-light">
              A comprehensive analysis of bio-active complexes engineered for 
              transformative skin conditioning at the cellular level.
            </p>

            {/* Scroll Indicator */}
            <div className="mt-16 flex flex-col items-center gap-2 animate-bounce">
              <span className="text-xs text-[#D4AF37]/40 tracking-wider">EXPLORE</span>
              <ChevronDown className="h-5 w-5 text-[#D4AF37]/40" />
            </div>
          </div>
        </section>

        {/* Section I: PDRN */}
        <section className="py-24 px-6 border-t border-[#D4AF37]/10 relative">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-[#D4AF37] via-[#D4AF37]/50 to-transparent" />
          
          <div className="max-w-6xl mx-auto">
            <div className="grid lg:grid-cols-2 gap-16 items-center">
              {/* Content */}
              <div className="order-2 lg:order-1">
                <div className="flex items-center gap-4 mb-6">
                  <span className="text-6xl font-serif text-[#D4AF37]/20">I</span>
                  <div>
                    <p className="text-xs text-[#D4AF37] tracking-[0.3em] uppercase mb-1">Primary Complex</p>
                    <h2 className="text-2xl md:text-3xl font-serif text-white">
                      PDRN: The Cellular Support Complex
                    </h2>
                  </div>
                </div>

                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/30 mb-8">
                  <Atom className="h-4 w-4 text-[#D4AF37]" />
                  <span className="text-sm text-[#D4AF37] font-medium">2.0% Concentration</span>
                </div>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-gradient-to-br from-[#D4AF37]/5 to-transparent border border-[#D4AF37]/20">
                    <h3 className="text-sm text-[#D4AF37] tracking-wider uppercase mb-3 flex items-center gap-2">
                      <Microscope className="h-4 w-4" /> The Molecule
                    </h3>
                    <p className="text-[#D4AF37]/70 leading-relaxed">
                      <strong className="text-white">Polydeoxyribonucleotide (PDRN)</strong> is a bio-active DNA fragment 
                      known for its intensive skin-conditioning properties. Derived through advanced biotechnology, 
                      it represents the pinnacle of cellular skincare science.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-gradient-to-br from-[#D4AF37]/5 to-transparent border border-[#D4AF37]/20">
                    <h3 className="text-sm text-[#D4AF37] tracking-wider uppercase mb-3 flex items-center gap-2">
                      <Zap className="h-4 w-4" /> Mechanism
                    </h3>
                    <p className="text-[#D4AF37]/70 leading-relaxed">
                      It supports the skin's natural recovery processes. By fostering an optimal environment 
                      for skin vitality, it helps the skin appear <strong className="text-white">rejuvenated and revitalized</strong> at 
                      a foundational level.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-gradient-to-r from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/30">
                    <h3 className="text-sm text-[#D4AF37] tracking-wider uppercase mb-3 flex items-center gap-2">
                      <Sparkles className="h-4 w-4" /> The OROÉ Edge
                    </h3>
                    <p className="text-[#D4AF37]/70 leading-relaxed">
                      While standard formulations use lower concentrations, our <strong className="text-white">Luminous Elixir 
                      is optimized at 2.0%</strong>, delivering a high-potency topical treatment inspired by 
                      professional Swiss protocols.
                    </p>
                  </div>
                </div>
              </div>

              {/* Visual */}
              <div className="order-1 lg:order-2 relative">
                <div className="aspect-square rounded-2xl bg-gradient-to-br from-[#D4AF37]/20 via-[#0A0A0A] to-[#D4AF37]/10 border border-[#D4AF37]/30 flex items-center justify-center relative overflow-hidden">
                  {/* Molecular Structure Visualization */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="relative">
                      <Dna className="h-48 w-48 text-[#D4AF37]/30" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-24 h-24 rounded-full bg-[#D4AF37]/10 animate-pulse" />
                      </div>
                    </div>
                  </div>
                  {/* Label */}
                  <div className="absolute bottom-6 left-6 right-6">
                    <div className="bg-[#0A0A0A]/80 backdrop-blur-sm rounded-lg p-4 border border-[#D4AF37]/20">
                      <p className="text-xs text-[#D4AF37]/50 uppercase tracking-wider mb-1">Molecular Weight</p>
                      <p className="text-lg text-[#D4AF37] font-mono">50-1500 kDa</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section II: Argireline */}
        <section className="py-24 px-6 bg-gradient-to-b from-[#0A0A0A] via-[#0D0D0D] to-[#0A0A0A] relative">
          <div className="absolute right-0 top-0 bottom-0 w-1 bg-gradient-to-b from-transparent via-[#D4AF37]/50 to-[#D4AF37]" />
          
          <div className="max-w-6xl mx-auto">
            <div className="grid lg:grid-cols-2 gap-16 items-center">
              {/* Visual */}
              <div className="relative">
                <div className="aspect-[4/3] rounded-2xl bg-gradient-to-br from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/20 p-8 flex flex-col justify-between">
                  {/* Timeline Visualization */}
                  <div className="flex items-center justify-between mb-8">
                    <span className="text-xs text-[#D4AF37]/50 uppercase tracking-wider">Day 1</span>
                    <div className="flex-1 h-[2px] mx-4 bg-gradient-to-r from-[#D4AF37]/20 via-[#D4AF37] to-[#D4AF37]/20" />
                    <span className="text-xs text-[#D4AF37] uppercase tracking-wider font-semibold">Day 7</span>
                  </div>
                  
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <p className="text-6xl font-serif text-[#D4AF37] mb-2">10%</p>
                      <p className="text-sm text-[#D4AF37]/70">Active Concentration</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mt-8">
                    {['Forehead Lines', "Crow's Feet", 'Expression Lines'].map((area, idx) => (
                      <div key={idx} className="text-center p-3 rounded-lg bg-[#D4AF37]/5 border border-[#D4AF37]/10">
                        <p className="text-xs text-[#D4AF37]/70">{area}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Content */}
              <div>
                <div className="flex items-center gap-4 mb-6">
                  <span className="text-6xl font-serif text-[#D4AF37]/20">II</span>
                  <div>
                    <p className="text-xs text-[#D4AF37] tracking-[0.3em] uppercase mb-1">Advanced Peptide</p>
                    <h2 className="text-2xl md:text-3xl font-serif text-white">
                      Argireline<sup>®</sup> Amplified
                    </h2>
                  </div>
                </div>

                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/30 mb-8">
                  <Shield className="h-4 w-4 text-[#D4AF37]" />
                  <span className="text-sm text-[#D4AF37] font-medium">10% Concentration</span>
                </div>

                <div className="space-y-6">
                  <div className="p-6 rounded-xl bg-gradient-to-br from-[#D4AF37]/5 to-transparent border border-[#D4AF37]/20">
                    <h3 className="text-sm text-[#D4AF37] tracking-wider uppercase mb-3">
                      The Advanced Smoothing Solution
                    </h3>
                    <p className="text-[#D4AF37]/70 leading-relaxed">
                      A breakthrough <strong className="text-white">hexapeptide</strong> engineered to improve the look of facial contours. 
                      This sophisticated molecule represents decades of peptide research condensed into one powerful active.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-gradient-to-br from-[#D4AF37]/5 to-transparent border border-[#D4AF37]/20">
                    <h3 className="text-sm text-[#D4AF37] tracking-wider uppercase mb-3">How It Works</h3>
                    <p className="text-[#D4AF37]/70 leading-relaxed">
                      It targets the appearance of expression lines caused by repeated facial movements. By smoothing 
                      the skin's surface, it <strong className="text-white">visibly reduces the look of "crow's feet" and forehead 
                      lines within 7 days</strong>.
                    </p>
                  </div>

                  <div className="p-6 rounded-xl bg-gradient-to-r from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/30">
                    <h3 className="text-sm text-[#D4AF37] tracking-wider uppercase mb-3">Long-term Efficacy</h3>
                    <p className="text-[#D4AF37]/70 leading-relaxed">
                      At a <strong className="text-white">10% concentration</strong>, it enhances skin firmness and promotes a smoother, 
                      more youthful-looking skin texture over time.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section III: 5-Phase Radiance Matrix */}
        <section className="py-24 px-6 border-t border-[#D4AF37]/10">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-16">
              <div className="flex items-center justify-center gap-4 mb-6">
                <span className="text-6xl font-serif text-[#D4AF37]/20">III</span>
              </div>
              <p className="text-xs text-[#D4AF37] tracking-[0.3em] uppercase mb-3">Biotech Correction</p>
              <h2 className="text-3xl md:text-4xl font-serif text-white mb-4">
                The 5-Phase Radiance Matrix
              </h2>
              <p className="text-[#D4AF37]/60 max-w-2xl mx-auto">
                We utilize Biotech Correction to enhance luminosity without harsh chemicals.
              </p>
            </div>

            {/* 5-Phase Grid */}
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Phase 1 */}
              <div 
                className="group p-8 rounded-2xl bg-gradient-to-br from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/20 hover:border-[#D4AF37]/50 transition-all duration-300 cursor-pointer"
                onMouseEnter={() => setActiveSection(1)}
                onMouseLeave={() => setActiveSection(null)}
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="text-4xl font-serif text-[#D4AF37]/30 group-hover:text-[#D4AF37]/50 transition-colors">01</span>
                  <div className="w-12 h-12 rounded-full bg-[#D4AF37]/10 flex items-center justify-center group-hover:bg-[#D4AF37]/20 transition-colors">
                    <Sun className="h-6 w-6 text-[#D4AF37]" />
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">Tranexamic Acid</h3>
                <p className="text-sm text-[#D4AF37] mb-4">5% Concentration</p>
                <p className="text-[#D4AF37]/70 text-sm leading-relaxed">
                  Visibly clarifies the complexion and targets the appearance of uneven skin tone and dark spots.
                </p>
              </div>

              {/* Phase 2 */}
              <div 
                className="group p-8 rounded-2xl bg-gradient-to-br from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/20 hover:border-[#D4AF37]/50 transition-all duration-300 cursor-pointer"
                onMouseEnter={() => setActiveSection(2)}
                onMouseLeave={() => setActiveSection(null)}
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="text-4xl font-serif text-[#D4AF37]/30 group-hover:text-[#D4AF37]/50 transition-colors">02</span>
                  <div className="w-12 h-12 rounded-full bg-[#D4AF37]/10 flex items-center justify-center group-hover:bg-[#D4AF37]/20 transition-colors">
                    <Shield className="h-6 w-6 text-[#D4AF37]" />
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">Niacinamide</h3>
                <p className="text-sm text-[#D4AF37] mb-4">Barrier Support</p>
                <p className="text-[#D4AF37]/70 text-sm leading-relaxed">
                  Supports the skin's natural moisture barrier for improved resilience and long-term skin health.
                </p>
              </div>

              {/* Phase 3 */}
              <div 
                className="group p-8 rounded-2xl bg-gradient-to-br from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/20 hover:border-[#D4AF37]/50 transition-all duration-300 cursor-pointer"
                onMouseEnter={() => setActiveSection(3)}
                onMouseLeave={() => setActiveSection(null)}
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="text-4xl font-serif text-[#D4AF37]/30 group-hover:text-[#D4AF37]/50 transition-colors">03</span>
                  <div className="w-12 h-12 rounded-full bg-[#D4AF37]/10 flex items-center justify-center group-hover:bg-[#D4AF37]/20 transition-colors">
                    <Droplets className="h-6 w-6 text-[#D4AF37]" />
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">Glucosamine</h3>
                <p className="text-sm text-[#D4AF37] mb-4">Deep Hydration</p>
                <p className="text-[#D4AF37]/70 text-sm leading-relaxed">
                  Provides deep surface hydration for a plump, dewy look that lasts throughout the day.
                </p>
              </div>

              {/* Phase 4 - Featured */}
              <div 
                className="group p-8 rounded-2xl bg-gradient-to-br from-[#D4AF37]/20 via-[#D4AF37]/10 to-transparent border border-[#D4AF37]/40 hover:border-[#D4AF37]/60 transition-all duration-300 cursor-pointer lg:col-span-1"
                onMouseEnter={() => setActiveSection(4)}
                onMouseLeave={() => setActiveSection(null)}
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="text-4xl font-serif text-[#D4AF37]/50 group-hover:text-[#D4AF37]/70 transition-colors">04</span>
                  <div className="w-12 h-12 rounded-full bg-[#D4AF37]/20 flex items-center justify-center group-hover:bg-[#D4AF37]/30 transition-colors">
                    <Sparkles className="h-6 w-6 text-[#D4AF37]" />
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">24K Gold Mica</h3>
                <p className="text-sm text-[#D4AF37] mb-4">The Golden Hue</p>
                <p className="text-[#D4AF37]/70 text-sm leading-relaxed">
                  Offers a physical veil against environmental stressors while providing an immediate 
                  <strong className="text-white"> "Glass Skin" glow</strong>.
                </p>
              </div>

              {/* Phase 5 */}
              <div 
                className="group p-8 rounded-2xl bg-gradient-to-br from-[#D4AF37]/10 to-transparent border border-[#D4AF37]/20 hover:border-[#D4AF37]/50 transition-all duration-300 cursor-pointer lg:col-span-2"
                onMouseEnter={() => setActiveSection(5)}
                onMouseLeave={() => setActiveSection(null)}
              >
                <div className="flex items-center justify-between mb-6">
                  <span className="text-4xl font-serif text-[#D4AF37]/30 group-hover:text-[#D4AF37]/50 transition-colors">05</span>
                  <div className="w-12 h-12 rounded-full bg-[#D4AF37]/10 flex items-center justify-center group-hover:bg-[#D4AF37]/20 transition-colors">
                    <FlaskConical className="h-6 w-6 text-[#D4AF37]" />
                  </div>
                </div>
                <div className="lg:flex lg:items-start lg:gap-8">
                  <div className="lg:flex-1">
                    <h3 className="text-xl font-semibold text-white mb-2">Superoxide Dismutase</h3>
                    <p className="text-sm text-[#D4AF37] mb-4">Premier Antioxidant Enzyme</p>
                    <p className="text-[#D4AF37]/70 text-sm leading-relaxed">
                      A premier antioxidant enzyme that helps protect the skin's surface from oxidative stress 
                      caused by environmental pollutants. This powerful defender works at the molecular level.
                    </p>
                  </div>
                  <div className="hidden lg:block lg:w-px lg:h-24 lg:bg-[#D4AF37]/20" />
                  <div className="mt-4 lg:mt-0 lg:w-48 text-right">
                    <p className="text-xs text-[#D4AF37]/50 uppercase tracking-wider">Protection Level</p>
                    <p className="text-2xl font-serif text-[#D4AF37]">Maximum</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Compliance Table Section */}
        <section className="py-24 px-6 bg-gradient-to-b from-[#0A0A0A] to-[#080808] border-t border-[#D4AF37]/10">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-12">
              <p className="text-xs text-[#D4AF37]/50 tracking-[0.3em] uppercase mb-3">Regulatory Standards</p>
              <h2 className="text-2xl md:text-3xl font-serif text-white mb-4">
                Health Canada Compliant Formulation
              </h2>
              <p className="text-[#D4AF37]/60 max-w-2xl mx-auto text-sm">
                Our claims are carefully crafted to meet Canadian cosmetic regulations while accurately 
                representing the transformative potential of our formulation.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-[#D4AF37]/30">
                    <th className="text-left py-4 px-6 text-xs text-[#D4AF37] uppercase tracking-wider">Clinical Terminology</th>
                    <th className="text-left py-4 px-6 text-xs text-[#D4AF37] uppercase tracking-wider">Cosmetic Claim</th>
                    <th className="text-left py-4 px-6 text-xs text-[#D4AF37]/50 uppercase tracking-wider hidden md:table-cell">Compliance Note</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#D4AF37]/10">
                  <tr className="hover:bg-[#D4AF37]/5 transition-colors">
                    <td className="py-4 px-6 text-[#D4AF37]/50 text-sm line-through">Repair DNA strands</td>
                    <td className="py-4 px-6 text-white text-sm">Supports skin's natural recovery</td>
                    <td className="py-4 px-6 text-[#D4AF37]/40 text-xs hidden md:table-cell">Cosmetic claim (support vs repair)</td>
                  </tr>
                  <tr className="hover:bg-[#D4AF37]/5 transition-colors">
                    <td className="py-4 px-6 text-[#D4AF37]/50 text-sm line-through">Blocks dark spots</td>
                    <td className="py-4 px-6 text-white text-sm">Targets the appearance of dark spots</td>
                    <td className="py-4 px-6 text-[#D4AF37]/40 text-xs hidden md:table-cell">Appearance claim (not physiological)</td>
                  </tr>
                  <tr className="hover:bg-[#D4AF37]/5 transition-colors">
                    <td className="py-4 px-6 text-[#D4AF37]/50 text-sm line-through">Stops neurotransmitters</td>
                    <td className="py-4 px-6 text-white text-sm">Targets the appearance of expression lines</td>
                    <td className="py-4 px-6 text-[#D4AF37]/40 text-xs hidden md:table-cell">No nervous system claims</td>
                  </tr>
                  <tr className="hover:bg-[#D4AF37]/5 transition-colors">
                    <td className="py-4 px-6 text-[#D4AF37]/50 text-sm line-through">Stabilize PDRN potency</td>
                    <td className="py-4 px-6 text-white text-sm">Intensive skin-conditioning</td>
                    <td className="py-4 px-6 text-[#D4AF37]/40 text-xs hidden md:table-cell">PDRN as skin conditioner</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24 px-6 border-t border-[#D4AF37]/10 relative overflow-hidden">
          {/* Background Glow */}
          <div className="absolute inset-0 flex items-center justify-center opacity-20">
            <div className="w-96 h-96 rounded-full bg-[#D4AF37] blur-[120px]" />
          </div>
          
          <div className="max-w-3xl mx-auto text-center relative z-10">
            <Sparkles className="h-12 w-12 text-[#D4AF37] mx-auto mb-8" />
            <h2 className="text-3xl md:text-4xl font-serif text-white mb-6">
              Experience the Science
            </h2>
            <p className="text-[#D4AF37]/60 mb-10 max-w-xl mx-auto">
              Join the exclusive waitlist for the OROÉ Luminous Elixir and discover 
              the transformative power of clinical-grade biotech skincare.
            </p>
            <Link 
              to="/oroe"
              className="inline-flex items-center gap-3 px-10 py-5 bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A0A0A] font-semibold rounded-full hover:opacity-90 transition-all duration-300 hover:scale-105 group"
            >
              Request Access to the Maison
              <ExternalLink className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </section>

        {/* Legal Disclaimer Footer */}
        <footer className="py-12 px-6 border-t border-[#D4AF37]/10 bg-[#050505]">
          <div className="max-w-5xl mx-auto">
            {/* Disclaimer */}
            <div className="mb-8 p-6 rounded-xl bg-[#D4AF37]/5 border border-[#D4AF37]/10">
              <p className="text-xs text-[#D4AF37]/50 leading-relaxed text-center">
                Individual results may vary. This product is a cosmetic intended for topical use to improve 
                the appearance of the skin. It is not intended to diagnose, treat, cure, or prevent any disease 
                or medical condition. Consult with a professional for specific skin concerns.
              </p>
            </div>

            {/* Footer Links */}
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="text-center md:text-left">
                <p className="text-xl font-serif tracking-[0.3em] text-[#D4AF37] mb-1">OROÉ</p>
                <p className="text-xs text-[#D4AF37]/40">Laboratoire Suisse • Est. 2025</p>
              </div>
              <div className="flex items-center gap-6">
                <Link to="/oroe" className="text-xs text-[#D4AF37]/50 hover:text-[#D4AF37] transition-colors uppercase tracking-wider">
                  Maison
                </Link>
                <Link to="/oroe/ritual" className="text-xs text-[#D4AF37]/50 hover:text-[#D4AF37] transition-colors uppercase tracking-wider">
                  The Ritual
                </Link>
              </div>
              <p className="text-xs text-[#D4AF37]/30">
                © 2025 Polaris Built Inc. All rights reserved.
              </p>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
};

export default PDRNSciencePage;
