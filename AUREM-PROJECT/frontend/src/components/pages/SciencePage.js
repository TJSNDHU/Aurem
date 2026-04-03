import React from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// SEO Component (inline for this page)
const SEO = ({ title, description, keywords, url }) => {
  const siteName = "ReRoots | Canadian Biotech Skincare";
  const fullTitle = title ? `${title} | ReRoots` : siteName;
  // Always use production URL for canonical - critical for SEO
  const siteUrl = "https://reroots.ca";
  const fullUrl = `${siteUrl}${url || ""}`;

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      {keywords && <meta name="keywords" content={keywords} />}
      <link rel="canonical" href={fullUrl} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={fullUrl} />
      <meta property="og:type" content="website" />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
    </Helmet>
  );
};

// Floating Molecule Component
const FloatingMolecule = ({ className, delay = 0, duration = 20, size = "md" }) => {
  const sizes = {
    sm: "w-8 h-8",
    md: "w-12 h-12", 
    lg: "w-16 h-16",
    xl: "w-20 h-20"
  };
  
  return (
    <div 
      className={`absolute opacity-20 ${sizes[size]} ${className}`}
      style={{
        animation: `float ${duration}s ease-in-out infinite`,
        animationDelay: `${delay}s`
      }}
    >
      {/* DNA Helix Shape */}
      <svg viewBox="0 0 40 40" fill="none" className="w-full h-full">
        <path 
          d="M20 5 Q30 12 20 20 Q10 28 20 35" 
          stroke="#D4AF37" 
          strokeWidth="1.5" 
          strokeLinecap="round"
          fill="none"
        />
        <path 
          d="M20 5 Q10 12 20 20 Q30 28 20 35" 
          stroke="#F8A5B8" 
          strokeWidth="1.5" 
          strokeLinecap="round"
          fill="none"
        />
        {/* Connection points */}
        <circle cx="15" cy="10" r="2" fill="#D4AF37" opacity="0.8"/>
        <circle cx="25" cy="10" r="2" fill="#F8A5B8" opacity="0.8"/>
        <circle cx="25" cy="20" r="2" fill="#D4AF37" opacity="0.8"/>
        <circle cx="15" cy="20" r="2" fill="#F8A5B8" opacity="0.8"/>
        <circle cx="15" cy="30" r="2" fill="#D4AF37" opacity="0.8"/>
        <circle cx="25" cy="30" r="2" fill="#F8A5B8" opacity="0.8"/>
        {/* Horizontal bonds */}
        <line x1="15" y1="10" x2="25" y2="10" stroke="white" strokeWidth="0.5" opacity="0.5"/>
        <line x1="15" y1="20" x2="25" y2="20" stroke="white" strokeWidth="0.5" opacity="0.5"/>
        <line x1="15" y1="30" x2="25" y2="30" stroke="white" strokeWidth="0.5" opacity="0.5"/>
      </svg>
    </div>
  );
};

// Simple Atom/Molecule dot
const FloatingAtom = ({ className, delay = 0, duration = 15 }) => (
  <div 
    className={`absolute ${className}`}
    style={{
      animation: `floatSlow ${duration}s ease-in-out infinite`,
      animationDelay: `${delay}s`
    }}
  >
    <div className="relative">
      <div className="w-3 h-3 rounded-full bg-gradient-to-br from-[#D4AF37] to-[#D4AF37]/50 opacity-40" />
      <div className="absolute -top-1 -left-1 w-2 h-2 rounded-full bg-[#F8A5B8] opacity-30" />
    </div>
  </div>
);

const SciencePage = () => {
  return (
    <div className="min-h-screen bg-white">
      <SEO 
        title="The Science of PDRN: The Future of Skin Vitality" 
        description="What is PDRN skincare? Learn about Polydeoxyribonucleotide - the bio-active Salmon DNA molecule supporting skin vitality in Canada. ReRoots delivers professional-strength PDRN in topical serums."
        keywords="PDRN, Polydeoxyribonucleotide, what is PDRN skincare Canada, salmon DNA skincare, biorejuvenation, skin vitality, A2A adenosine receptors, ReRoots biotech"
        url="/science-of-pdrn"
      />
      
      {/* Floating Animation Keyframes */}
      <style>{`
        @keyframes float {
          0%, 100% { 
            transform: translateY(0px) rotate(0deg); 
            opacity: 0.15;
          }
          25% { 
            transform: translateY(-20px) rotate(5deg); 
            opacity: 0.25;
          }
          50% { 
            transform: translateY(-10px) rotate(-3deg); 
            opacity: 0.2;
          }
          75% { 
            transform: translateY(-25px) rotate(3deg); 
            opacity: 0.18;
          }
        }
        @keyframes floatSlow {
          0%, 100% { 
            transform: translate(0px, 0px); 
            opacity: 0.3;
          }
          33% { 
            transform: translate(10px, -15px); 
            opacity: 0.5;
          }
          66% { 
            transform: translate(-5px, -10px); 
            opacity: 0.4;
          }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.1); }
        }
      `}</style>
      
      {/* Hero with Floating Molecules */}
      <section className="bg-[#2D2A2E] text-white py-24 md:py-32 relative overflow-hidden">
        {/* Floating Molecules Background */}
        <div className="absolute inset-0 pointer-events-none">
          <FloatingMolecule className="top-[10%] left-[5%]" delay={0} duration={18} size="lg" />
          <FloatingMolecule className="top-[20%] right-[10%]" delay={3} duration={22} size="md" />
          <FloatingMolecule className="bottom-[15%] left-[15%]" delay={5} duration={20} size="sm" />
          <FloatingMolecule className="bottom-[25%] right-[5%]" delay={8} duration={25} size="xl" />
          <FloatingMolecule className="top-[50%] left-[3%]" delay={2} duration={19} size="md" />
          <FloatingMolecule className="top-[40%] right-[15%]" delay={6} duration={21} size="sm" />
          
          {/* Floating Atoms */}
          <FloatingAtom className="top-[15%] left-[25%]" delay={1} duration={12} />
          <FloatingAtom className="top-[30%] right-[25%]" delay={4} duration={14} />
          <FloatingAtom className="bottom-[20%] left-[30%]" delay={7} duration={16} />
          <FloatingAtom className="bottom-[35%] right-[20%]" delay={2} duration={13} />
          <FloatingAtom className="top-[60%] left-[8%]" delay={9} duration={15} />
          <FloatingAtom className="top-[70%] right-[8%]" delay={5} duration={11} />
          
          {/* Subtle gradient overlay for depth */}
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#2D2A2E]/50" />
        </div>
        
        <div className="max-w-4xl mx-auto px-6 md:px-12 text-center relative z-10">
          <Badge className="bg-[#F8A5B8]/20 text-[#F8A5B8] hover:bg-[#F8A5B8]/20 mb-4">BIOTECH SCIENCE</Badge>
          <h1 className="font-display text-4xl md:text-5xl font-bold mb-6">
            The Science of <span className="text-[#F8A5B8]">PDRN</span>
            <span className="block text-2xl md:text-3xl mt-2 text-white/80">The Future of Skin Vitality</span>
          </h1>
          <p className="text-white/80 text-lg max-w-2xl mx-auto">
            Discover why <strong>Polydeoxyribonucleotide</strong> from Salmon DNA is transforming how Canada approaches skincare.
          </p>
        </div>
      </section>

      {/* What is PDRN */}
      <section className="py-20 bg-white">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="font-display text-3xl font-bold text-[#2D2A2E] mb-8">What is PDRN?</h2>
              <div className="prose prose-lg max-w-none">
                <p className="text-[#5A5A5A] text-lg mb-6">
                  <strong className="text-[#2D2A2E]">Polydeoxyribonucleotide (PDRN)</strong> is a bio-active molecule composed of deoxyribonucleotide polymers. Sourced from <strong>Salmon DNA</strong>, PDRN is a powerhouse ingredient in professional skincare and "<strong>biorejuvenation</strong>."
                </p>
                <div className="bg-[#FDF9F9] border-l-4 border-[#F8A5B8] p-6 my-8 rounded-r-lg">
                  <p className="text-[#2D2A2E] text-lg italic mb-0">
                    Because Salmon DNA is remarkably similar to human DNA, it is highly <strong>biocompatible</strong>, meaning your skin recognizes it and can use it immediately to support your skin's natural vitality.
                  </p>
                </div>
              </div>
            </div>
            {/* DNA Molecular Structure Diagram */}
            <div className="flex justify-center">
              <div className="relative">
                <img 
                  src="https://static.prod-images.emergentagent.com/jobs/a28d3b5a-50b1-43fb-9c53-db6eee578709/images/a0dbc7b8e797db2450bb500a655187be23dd995b6d27f03df1fe44f91710fee8.png" 
                  alt="DNA Double Helix Structure - The foundation of PDRN technology"
                  className="w-64 h-64 object-contain opacity-90"
                />
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-sm">
                  <span className="text-xs font-mono text-[#5A5A5A] tracking-wider">DNA DOUBLE HELIX</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Skin Layers Diagram Section */}
      <section className="py-16 bg-gradient-to-b from-white to-[#FDF9F9]">
        <div className="max-w-5xl mx-auto px-6 md:px-12">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Skin Layer Diagram */}
            <div className="order-2 md:order-1 flex justify-center">
              <div className="relative">
                <img 
                  src="https://static.prod-images.emergentagent.com/jobs/a28d3b5a-50b1-43fb-9c53-db6eee578709/images/5ec290c337b9391796fcfbda3af1dbdaacfaded388deeb30945c1cd88c879e4b.png" 
                  alt="Cross-section of skin layers showing how PDRN penetrates"
                  className="w-72 h-72 object-contain rounded-2xl shadow-lg"
                />
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-sm">
                  <span className="text-xs font-mono text-[#5A5A5A] tracking-wider">SKIN LAYER PENETRATION</span>
                </div>
              </div>
            </div>
            {/* Content */}
            <div className="order-1 md:order-2">
              <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] hover:bg-[#D4AF37]/20 mb-4 font-mono text-xs tracking-[0.1em]">DERMAL SCIENCE</Badge>
              <h2 className="font-display text-2xl font-bold text-[#2D2A2E] mb-4">Deep Cellular Action</h2>
              <p className="text-[#5A5A5A] text-lg mb-6">
                PDRN doesn't just sit on the surface. Its low molecular weight allows it to penetrate through the <strong className="text-[#2D2A2E]">epidermis</strong> into the <strong className="text-[#2D2A2E]">dermis</strong>, where it activates fibroblasts and promotes collagen synthesis at the cellular level.
              </p>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-[#F8A5B8]"></div>
                  <span className="text-sm text-[#5A5A5A]"><strong className="text-[#2D2A2E]">Epidermis:</strong> Surface protection & barrier</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-[#D4AF37]"></div>
                  <span className="text-sm text-[#5A5A5A]"><strong className="text-[#2D2A2E]">Dermis:</strong> Collagen & elastin production</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-[#2D2A2E]"></div>
                  <span className="text-sm text-[#5A5A5A]"><strong className="text-[#2D2A2E]">Subcutaneous:</strong> Support structure</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How PDRN Works - Three Pillars */}
      <section className="py-20 bg-[#FDF9F9]">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <h2 className="font-display text-3xl font-bold text-[#2D2A2E] mb-4">How PDRN Works: The Three Pillars of Skin Vitality</h2>
          <p className="text-[#5A5A5A] text-lg mb-12">
            Unlike traditional ingredients that simply sit on the surface, PDRN acts as a <strong>cell-signaling messenger</strong>. It "wakes up" dormant skin cells to behave like younger, healthier versions of themselves through three primary mechanisms:
          </p>
          
          <div className="grid gap-8">
            {/* Pillar 1 */}
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100">
              <div className="flex items-start gap-6">
                <div className="w-16 h-16 bg-gradient-to-br from-[#F8A5B8] to-[#F8A5B8]/70 rounded-xl flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-white">1</span>
                </div>
                <div>
                  <h3 className="font-display text-xl font-bold text-[#2D2A2E] mb-3">DNA Synthesis & Cellular Proliferation</h3>
                  <p className="text-[#5A5A5A]">
                    PDRN provides the "<strong>building blocks</strong>" for DNA. It supports your skin's natural renewal process, helping to promote a revitalized appearance ideal for addressing <strong>uneven texture</strong>, <strong>dullness</strong>, and <strong>signs of aging</strong>.
                  </p>
                </div>
              </div>
            </div>

            {/* Pillar 2 */}
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100">
              <div className="flex items-start gap-6">
                <div className="w-16 h-16 bg-gradient-to-br from-[#F8A5B8] to-[#F8A5B8]/70 rounded-xl flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-white">2</span>
                </div>
                <div>
                  <h3 className="font-display text-xl font-bold text-[#2D2A2E] mb-3">Angiogenesis (Improved Circulation)</h3>
                  <p className="text-[#5A5A5A]">
                    PDRN promotes the formation of new <strong>micro-vessels</strong>. This increases blood flow to the skin, delivering more oxygen and nutrients, which results in that "lit-from-within" glow often referred to as the <strong className="text-[#F8A5B8]">Glass Skin</strong> effect.
                  </p>
                </div>
              </div>
            </div>

            {/* Pillar 3 */}
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100">
              <div className="flex items-start gap-6">
                <div className="w-16 h-16 bg-gradient-to-br from-[#F8A5B8] to-[#F8A5B8]/70 rounded-xl flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-white">3</span>
                </div>
                <div>
                  <h3 className="font-display text-xl font-bold text-[#2D2A2E] mb-3">Anti-Inflammatory Action</h3>
                  <p className="text-[#5A5A5A]">
                    By binding to <strong>A2A adenosine receptors</strong>, PDRN actively shuts down inflammatory pathways. This makes it an effective solution for <strong>redness</strong>, <strong>rosacea</strong>, and <strong>sensitivity</strong> caused by environmental stress.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Comparison Table */}
      <section className="py-20 bg-white">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <h2 className="font-display text-3xl font-bold text-[#2D2A2E] mb-8">ReRoots PDRN vs. Traditional Skincare</h2>
          
          <div className="overflow-hidden rounded-xl border border-gray-200">
            <table className="w-full">
              <thead>
                <tr className="bg-[#2D2A2E] text-white">
                  <th className="px-6 py-4 text-left font-display font-bold">Feature</th>
                  <th className="px-6 py-4 text-left font-display font-bold">Traditional Skincare</th>
                  <th className="px-6 py-4 text-left font-display font-bold bg-[#F8A5B8]/20">ReRoots PDRN Skincare</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr className="bg-white">
                  <td className="px-6 py-4 font-medium text-[#2D2A2E]">Primary Goal</td>
                  <td className="px-6 py-4 text-[#5A5A5A]">Surface Hydration</td>
                  <td className="px-6 py-4 text-[#2D2A2E] font-medium bg-[#FDF9F9]">Cellular Vitality</td>
                </tr>
                <tr className="bg-gray-50">
                  <td className="px-6 py-4 font-medium text-[#2D2A2E]">Mechanism</td>
                  <td className="px-6 py-4 text-[#5A5A5A]">Temporary Moisture</td>
                  <td className="px-6 py-4 text-[#2D2A2E] font-medium bg-[#FDF9F9]">DNA-Level Support</td>
                </tr>
                <tr className="bg-white">
                  <td className="px-6 py-4 font-medium text-[#2D2A2E]">Long-term Benefit</td>
                  <td className="px-6 py-4 text-[#5A5A5A]">Maintenance</td>
                  <td className="px-6 py-4 text-[#2D2A2E] font-medium bg-[#FDF9F9]">Structural Transformation</td>
                </tr>
                <tr className="bg-gray-50">
                  <td className="px-6 py-4 font-medium text-[#2D2A2E]">Source</td>
                  <td className="px-6 py-4 text-[#5A5A5A]">Plant or Synthetic</td>
                  <td className="px-6 py-4 text-[#2D2A2E] font-medium bg-[#FDF9F9]">Bio-identical Salmon DNA</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Why Canada */}
      <section className="py-20 bg-[#2D2A2E] text-white relative overflow-hidden">
        {/* Background Molecular Pattern */}
        <div className="absolute top-0 right-0 w-96 h-96 opacity-10">
          <img 
            src="https://static.prod-images.emergentagent.com/jobs/a28d3b5a-50b1-43fb-9c53-db6eee578709/images/5360b528cb2a287e7abcbcf63c329ceaf72636bfc83cc249ce5a91d9891ca7fd.png" 
            alt=""
            className="w-full h-full object-contain"
          />
        </div>
        <div className="max-w-4xl mx-auto px-6 md:px-12 relative z-10">
          <h2 className="font-display text-3xl font-bold mb-6">Why Canada is Choosing ReRoots Biotech</h2>
          <p className="text-white/80 text-lg mb-8">
            In the past, PDRN was primarily available through expensive <strong className="text-white">professional treatments</strong> in aesthetic clinics. ReRoots has pioneered a way to deliver <strong className="text-white">professional-strength PDRN</strong> in a high-concentration topical serum—giving you salon-quality results from the comfort of your home.
          </p>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-6 border border-white/10">
              <div className="w-12 h-12 rounded-full bg-[#F8A5B8]/20 flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-[#F8A5B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </div>
              <h3 className="font-display font-bold mb-2">Professional Strength</h3>
              <p className="text-white/70 text-sm">Same concentration used in professional beauty treatments</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-6 border border-white/10">
              <div className="w-12 h-12 rounded-full bg-[#D4AF37]/20 flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-[#D4AF37]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-display font-bold mb-2">Canadian Made</h3>
              <p className="text-white/70 text-sm">Formulated and shipped from Canada</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-lg p-6 border border-white/10">
              <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-display font-bold mb-2">Accessible Pricing</h3>
              <p className="text-white/70 text-sm">Fraction of the cost of professional treatments</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-gradient-to-r from-[#F8A5B8]/20 to-[#F8A5B8]/10">
        <div className="max-w-4xl mx-auto px-6 md:px-12 text-center">
          <h2 className="font-display text-3xl font-bold text-[#2D2A2E] mb-4">Experience the Science</h2>
          <p className="text-[#5A5A5A] mb-8 max-w-xl mx-auto text-lg">
            Ready to transform your skincare routine with scientifically formulated PDRN technology?
          </p>
          <Link to="/products" className="inline-block">
            <Button className="bg-[#2D2A2E] hover:bg-[#2D2A2E]/90 text-white rounded-full px-10 py-6 text-lg font-bold shadow-lg hover:shadow-xl transition-all">
              Shop the AURA-GEN PDRN Serum →
            </Button>
          </Link>
          <p className="mt-4 text-sm text-[#5A5A5A]">Free shipping on orders over $75 across Canada</p>
        </div>
      </section>
    </div>
  );
};

export default SciencePage;
