import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  ChevronLeft, 
  Shield, 
  FlaskConical, 
  Leaf, 
  Heart,
  Check,
  Award,
  Globe,
  Microscope
} from "lucide-react";
import "../styles/lavela-design-system.css";

// The Lab - Science & Safety Page
const TheLabPage = () => {
  const navigate = useNavigate();
  
  // Force scroll to work
  useEffect(() => {
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    document.documentElement.style.overflow = 'auto';
    document.documentElement.style.height = 'auto';
    return () => {
      document.body.style.overflow = '';
      document.body.style.height = '';
      document.documentElement.style.overflow = '';
      document.documentElement.style.height = '';
    };
  }, []);
  const safetyFeatures = [
    {
      icon: <Shield className="w-6 h-6" />,
      title: "Pediatric-Safe Formula",
      description: "Every ingredient is carefully selected to be gentle on young, developing skin. No harsh actives that could damage the skin barrier.",
      badge: "Ages 8-16"
    },
    {
      icon: <FlaskConical className="w-6 h-6" />,
      title: "pH Balanced (5.0-5.3)",
      description: "Matches your skin's natural pH level to maintain a healthy skin barrier and prevent irritation.",
      badge: "Skin-Identical"
    },
    {
      icon: <Leaf className="w-6 h-6" />,
      title: "Clean Ingredients",
      description: "Free from parabens, sulfates, phthalates, artificial fragrances, and over 50 other questionable ingredients.",
      badge: "Clean Beauty"
    },
    {
      icon: <Award className="w-6 h-6" />,
      title: "Dermatologist Tested",
      description: "Clinically tested by board-certified pediatric dermatologists to ensure safety and efficacy for teen skin.",
      badge: "Clinically Tested"
    },
  ];

  const forbiddenIngredients = [
    "Parabens", "Sulfates (SLS/SLES)", "Phthalates", "Artificial Fragrances",
    "Mineral Oil", "Formaldehyde", "Hydroquinone", "Retinol (too strong for teens)",
    "High-concentration Acids", "Alcohol Denat", "Synthetic Dyes", "PEGs"
  ];

  return (
    <div className="min-h-screen lavela-body overflow-y-auto" style={{
      background: 'linear-gradient(180deg, #0D4D4D 0%, #1A6B6B 25%, #D4A090 65%, #E8C4B8 100%)'
    }}>
      {/* Navigation - White Header */}
      <nav className="bg-white px-4 sm:px-6 py-2 border-b border-[#E6BE8A]/30 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Back Button - LEFT */}
          <button 
            onClick={() => navigate('/la-vela-bianca')}
            className="flex items-center gap-2 text-[#2D2A2E] hover:text-[#D4A574] transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
            <span className="text-sm">Back</span>
          </button>
          
          {/* Logo - CENTER */}
          <img 
            src="/lavela-header-logo.png" 
            alt="LA VELA BIANCA" 
            className="h-7 sm:h-8 absolute left-1/2 transform -translate-x-1/2"
          />
          
          {/* Empty div for spacing - RIGHT */}
          <div className="w-16"></div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-8 pb-16 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-4">Science & Safety</p>
            <h1 className="lavela-heading text-4xl sm:text-5xl md:text-6xl mb-4">
              The <span className="lavela-shimmer-text">Lab</span>
            </h1>
            <div className="lavela-divider-11 my-6"></div>
            <p className="text-lg text-[#E8C4B8] max-w-2xl mx-auto">
              Where Canadian precision meets Italian beauty innovation. 
              Every formula is designed specifically for young, developing skin.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Canadian-Italian Formula */}
      <section className="py-16 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">🇨🇦</span>
                <span className="text-2xl text-[#E6BE8A]">+</span>
                <span className="text-3xl">🇮🇹</span>
              </div>
              <h2 className="lavela-heading text-3xl sm:text-4xl mb-6">
                Canadian-Italian <span className="lavela-shimmer-text">Excellence</span>
              </h2>
              <p className="text-[#E8C4B8] mb-6 leading-relaxed">
                Our formulas combine <strong className="text-[#E6BE8A]">Canadian pharmaceutical-grade standards</strong> with 
                <strong className="text-[#E6BE8A]"> Italian skincare artistry</strong>. The result? Products that are both 
                rigorously safe and beautifully effective.
              </p>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style={{
                    background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)'
                  }}>
                    <Microscope className="w-5 h-5 text-[#E6BE8A]" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[#E6BE8A]">Research-Backed</h3>
                    <p className="text-sm text-[#E8C4B8]">Every ingredient backed by clinical studies</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style={{
                    background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)'
                  }}>
                    <Globe className="w-5 h-5 text-[#E6BE8A]" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[#E6BE8A]">Globally Sourced</h3>
                    <p className="text-sm text-[#E8C4B8]">Premium ingredients from trusted suppliers worldwide</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style={{
                    background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)'
                  }}>
                    <Heart className="w-5 h-5 text-[#E6BE8A]" />
                  </div>
                  <div>
                    <h3 className="font-medium text-[#E6BE8A]">Teen-First Design</h3>
                    <p className="text-sm text-[#E8C4B8]">Formulated specifically for ages 8-16</p>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="relative">
              <div className="aspect-square rounded-3xl overflow-hidden flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, rgba(13, 77, 77, 0.3) 0%, rgba(232, 196, 184, 0.3) 100%)',
                border: '1px solid rgba(230, 190, 138, 0.3)'
              }}>
                <div className="text-center p-8">
                  <span className="text-8xl mb-4 block">🔬</span>
                  <p className="text-sm text-[#E8C4B8]">Canadian Lab Standards</p>
                  <p className="text-sm text-[#E8C4B8]">Italian Formulation Artistry</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Safety Features */}
      <section className="py-16 px-4" style={{
        background: 'linear-gradient(180deg, rgba(232, 196, 184, 0.2) 0%, rgba(13, 77, 77, 0.3) 100%)'
      }}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Safety First</p>
            <h2 className="lavela-heading text-3xl sm:text-4xl mb-4">
              Why Parents <span className="lavela-shimmer-text">Trust Us</span>
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 gap-6">
            {safetyFeatures.map((feature, i) => (
              <motion.div
                key={i}
                className="p-6 rounded-2xl"
                style={{
                  background: 'rgba(13, 77, 77, 0.5)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(230, 190, 138, 0.2)'
                }}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full flex items-center justify-center text-[#E6BE8A] flex-shrink-0" style={{
                    background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)'
                  }}>
                    {feature.icon}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold text-[#E6BE8A]">{feature.title}</h3>
                      <span className="text-xs px-2 py-0.5 text-[#E6BE8A] rounded-full" style={{
                        background: 'rgba(230, 190, 138, 0.2)'
                      }}>
                        {feature.badge}
                      </span>
                    </div>
                    <p className="text-sm text-[#E8C4B8]">{feature.description}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* What We DON'T Use */}
      <section className="py-16 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Clean Promise</p>
            <h2 className="lavela-heading text-3xl sm:text-4xl mb-4">
              What We <span className="line-through text-[#E8C4B8]/50">Don&apos;t</span> Use
            </h2>
            <p className="text-[#E8C4B8]">
              Over 50+ ingredients banned from our formulas
            </p>
          </div>

          <div className="p-8 rounded-2xl" style={{
            background: 'rgba(13, 77, 77, 0.5)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(230, 190, 138, 0.2)'
          }}>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {forbiddenIngredients.map((ingredient, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-[#E8C4B8]">
                  <span className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 text-xs">✕</span>
                  {ingredient}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Key Ingredients Deep Dive */}
      <section className="py-16 px-4" style={{
        background: 'linear-gradient(180deg, rgba(232, 196, 184, 0.2) 0%, rgba(13, 77, 77, 0.3) 100%)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Star Ingredients</p>
            <h2 className="lavela-heading text-3xl sm:text-4xl mb-4">
              The <span className="lavela-shimmer-text">Science</span> Behind the Glow
            </h2>
          </div>

          <div className="space-y-6">
            {[
              {
                name: "PDRN (Polydeoxyribonucleotide)",
                origin: "Salmon DNA",
                benefit: "Regenerates and repairs skin cells, speeds healing of acne scars",
                safety: "Biocompatible with human skin, no allergenic risk",
                emoji: "🧬"
              },
              {
                name: "Glutathione",
                origin: "Master Antioxidant",
                benefit: "Brightens skin, reduces dark spots, provides 'glass skin' glow",
                safety: "Naturally produced by the body, completely safe",
                emoji: "✨"
              },
              {
                name: "Vitamin B12 (Cyanocobalamin)",
                origin: "Essential Vitamin",
                benefit: "Calms redness, energizes skin cells, gives the gel its pink color",
                safety: "Water-soluble vitamin, non-irritating",
                emoji: "🌸"
              },
              {
                name: "Hyaluronic Acid (Multi-weight)",
                origin: "Biotech Fermented",
                benefit: "Deep and surface hydration, plumps skin without clogging pores",
                safety: "Identical to skin's natural HA, perfect for teens",
                emoji: "💧"
              },
            ].map((ingredient, i) => (
              <motion.div
                key={i}
                className="p-6 rounded-2xl"
                style={{
                  background: 'rgba(13, 77, 77, 0.5)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(230, 190, 138, 0.2)'
                }}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <div className="flex items-start gap-4">
                  <span className="text-4xl">{ingredient.emoji}</span>
                  <div className="flex-1">
                    <h3 className="font-semibold text-[#E6BE8A] mb-1">{ingredient.name}</h3>
                    <p className="text-xs text-[#E6BE8A]/80 mb-2">Source: {ingredient.origin}</p>
                    <p className="text-sm text-[#E8C4B8] mb-2">
                      <strong className="text-[#E6BE8A]">What it does:</strong> {ingredient.benefit}
                    </p>
                    <p className="text-sm text-[#E8C4B8]">
                      <strong className="text-[#E6BE8A]">Why it&apos;s safe:</strong> {ingredient.safety}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 px-4 bg-gradient-to-br from-[#E6BE8A] to-[#D4A574] text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="lavela-heading-white text-3xl sm:text-4xl mb-6">
            Ready to Experience the Science?
          </h2>
          <p className="text-lg opacity-90 mb-8">
            Try ORO ROSA and see the difference research-backed skincare makes.
          </p>
          <button 
            onClick={() => navigate('/lavela/oro-rosa')}
            className="bg-white text-[#D4A574] font-semibold px-8 py-4 rounded-full hover:shadow-lg transition-all"
          >
            Shop ORO ROSA
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 text-white text-center" style={{
        background: '#0D4D4D'
      }}>
        <p className="text-sm opacity-80 mb-2">
          © 2026 LA VELA BIANCA. Canadian-Italian Skincare Technology.
        </p>
        
        {/* Pediatric Safety Disclaimer */}
        <div className="max-w-md mx-auto my-4 p-3 bg-white/10 border border-white/20 rounded-lg">
          <p className="text-white/80 text-xs leading-relaxed">
            <strong className="text-[#E6BE8A]">⚡ Safety Note:</strong> Formulated for young skin barriers. 
            We recommend a patch test for children under 10. Always use with daily SPF.
          </p>
        </div>
        
        <div className="flex items-center justify-center gap-4 text-sm opacity-60">
          <a href="https://instagram.com/La_Vela_Bianca" target="_blank" rel="noopener noreferrer" className="hover:opacity-100 transition-opacity flex items-center gap-1">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
            @La_Vela_Bianca
          </a>
          <span>•</span>
          <a href="mailto:lavelabianca.official@gmail.com" className="hover:opacity-100 transition-opacity">
            lavelabianca.official@gmail.com
          </a>
        </div>
      </footer>
    </div>
  );
};

export default TheLabPage;
