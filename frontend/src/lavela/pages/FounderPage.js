import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ChevronLeft, Sparkles, Heart, Star } from "lucide-react";
import "../styles/lavela-design-system.css";

// Founder Page - The Master 11 Story
const FounderPage = () => {
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
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-4">Our Story</p>
            <h1 className="lavela-heading text-4xl sm:text-5xl md:text-6xl mb-4">
              The <span className="lavela-shimmer-text">Founder</span>
            </h1>
            <div className="lavela-divider-11 my-6"></div>
          </motion.div>
        </div>
      </section>

      {/* Founder Story */}
      <section className="py-16 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Photo Placeholder */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="relative"
            >
              <div className="aspect-[3/4] rounded-3xl overflow-hidden flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)',
                border: '1px solid rgba(230, 190, 138, 0.3)'
              }}>
                <div className="text-center p-8">
                  <span className="text-8xl block mb-4">👤</span>
                  <p className="text-[#E8C4B8]">Anmol Singh</p>
                  <p className="text-[#E8C4B8]/60 text-xs">Founder & Visionary</p>
                </div>
              </div>
              
              {/* The 11 Badge */}
              <div className="absolute -bottom-6 -right-6 w-24 h-24 rounded-full shadow-lg flex items-center justify-center" style={{
                background: 'rgba(13, 77, 77, 0.9)',
                border: '2px solid rgba(230, 190, 138, 0.5)'
              }}>
                <div className="text-center">
                  <span className="text-3xl font-bold lavela-shimmer-text">11</span>
                  <p className="text-[8px] text-[#E8C4B8] uppercase tracking-wider">Master</p>
                </div>
              </div>
            </motion.div>

            {/* Story */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <h2 className="lavela-heading text-3xl mb-6">
                Anmol <span className="lavela-shimmer-text">Singh</span>
              </h2>
              
              <div className="space-y-4 text-[#E8C4B8] leading-relaxed">
                <p>
                  &quot;I created LA VELA BIANCA because I saw a gap in the market. Teenagers were either 
                  using products designed for adults—too harsh, too strong—or cheap products that 
                  did nothing. There was no middle ground.&quot;
                </p>
                
                <p>
                  &quot;As someone who struggled with skin issues as a teen, I understood the emotional 
                  impact it has. Skincare isn&apos;t just about looking good—it&apos;s about feeling confident 
                  during some of the most formative years of your life.&quot;
                </p>
                
                <p>
                  &quot;The name <strong className="text-[#E6BE8A]">LA VELA BIANCA</strong> means &apos;The White Sail&apos; in Italian. It represents 
                  a new beginning, a fresh start, and the journey toward clear, glowing skin.&quot;
                </p>
              </div>

              <div className="mt-8 p-6 rounded-2xl" style={{
                background: 'rgba(13, 77, 77, 0.5)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(230, 190, 138, 0.2)'
              }}>
                <h3 className="font-medium text-[#E6BE8A] mb-3 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#E6BE8A]" />
                  The &quot;Master 11&quot; Philosophy
                </h3>
                <p className="text-sm text-[#E8C4B8]">
                  The number 11 appears throughout our brand—in our logo, our dividers, our 
                  thinking. It represents balance, intuition, and the duality of science and 
                  beauty. Two parallel lines, working together in harmony.
                </p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-16 px-4" style={{
        background: 'linear-gradient(180deg, rgba(232, 196, 184, 0.2) 0%, rgba(13, 77, 77, 0.3) 100%)'
      }}>
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Our Mission</p>
          <h2 className="lavela-heading text-3xl sm:text-4xl mb-8">
            Empowering the <span className="lavela-shimmer-text">Glow Generation</span>
          </h2>

          <div className="grid sm:grid-cols-3 gap-6">
            {[
              {
                icon: <Heart className="w-6 h-6" />,
                title: "Safe for Teens",
                desc: "Products designed specifically for young, developing skin"
              },
              {
                icon: <Star className="w-6 h-6" />,
                title: "Real Results",
                desc: "Science-backed formulas that actually work"
              },
              {
                icon: <Sparkles className="w-6 h-6" />,
                title: "Confidence",
                desc: "Helping teens feel beautiful in their own skin"
              },
            ].map((item, i) => (
              <motion.div
                key={i}
                className="p-6 text-center rounded-2xl"
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
                <div className="w-12 h-12 rounded-full flex items-center justify-center text-[#E6BE8A] mx-auto mb-4" style={{
                  background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)'
                }}>
                  {item.icon}
                </div>
                <h3 className="font-medium text-[#E6BE8A] mb-2">{item.title}</h3>
                <p className="text-sm text-[#E8C4B8]">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Quote */}
      <section className="py-16 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-3xl mx-auto text-center">
          <div className="lavela-divider-11 mb-8"></div>
          <blockquote className="lavela-heading text-2xl sm:text-3xl mb-6 italic">
            &quot;Every teenager deserves to feel confident in their own skin. 
            That&apos;s not a luxury—it&apos;s a right.&quot;
          </blockquote>
          <p className="text-[#E6BE8A] font-medium">— Anmol Singh, Founder</p>
          <div className="lavela-divider-11 mt-8"></div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 px-4 bg-gradient-to-br from-[#E6BE8A] to-[#D4A574] text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="lavela-heading-white text-3xl sm:text-4xl mb-6">
            Join Our Journey
          </h2>
          <p className="text-lg opacity-90 mb-8">
            Experience the difference of skincare made with intention.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button 
              onClick={() => navigate('/lavela/oro-rosa')}
              className="bg-white text-[#D4A574] font-semibold px-8 py-4 rounded-full hover:shadow-lg transition-all"
            >
              Shop ORO ROSA
            </button>
            <button 
              onClick={() => navigate('/lavela/glow-club')}
              className="border-2 border-white text-white font-semibold px-8 py-4 rounded-full hover:bg-white/10 transition-all"
            >
              Join Glow Club
            </button>
          </div>
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

export default FounderPage;
