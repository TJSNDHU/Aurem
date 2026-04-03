import React from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { motion } from "framer-motion";
import { 
  Sparkles, Crown, Dna, Heart, ArrowRight, Shield, Star, 
  Check, Users, Beaker, Award, Leaf
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// SEO-Optimized Landing Page for Family Skincare Keywords
const FamilySkinProtocolPage = () => {
  
  // Comprehensive JSON-LD Schema for this page
  const pageSchema = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "The Family Skin Protocol - From Gen Alpha to Golden Years",
    "description": "Complete family skincare guide featuring three generations of Canadian skincare science. Discover the right product for every age: LA VELA BIANCA for teens, ReRoots for young adults, OROÉ for mature skin.",
    "url": "https://reroots.ca/family-skin-protocol",
    "inLanguage": "en-CA",
    "isPartOf": {
      "@type": "WebSite",
      "name": "ReRoots Family of Brands",
      "url": "https://reroots.ca"
    },
    "about": {
      "@type": "Thing",
      "name": "Family Skincare Routine"
    },
    "mentions": [
      { "@type": "Brand", "name": "LA VELA BIANCA" },
      { "@type": "Brand", "name": "ReRoots" },
      { "@type": "Brand", "name": "OROÉ" }
    ]
  };

  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "The Family Skin Protocol: From Gen Alpha to Golden Years",
    "description": "A complete guide to family skincare with products for every generation",
    "author": {
      "@type": "Organization",
      "name": "ReRoots Family of Brands",
      "url": "https://reroots.ca"
    },
    "publisher": {
      "@type": "Organization",
      "name": "ReRoots Family of Brands",
      "logo": {
        "@type": "ImageObject",
        "url": "https://reroots.ca/logo.png"
      }
    },
    "datePublished": "2026-01-27",
    "dateModified": "2026-01-27",
    "mainEntityOfPage": "https://reroots.ca/family-skin-protocol"
  };

  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "What is the best skincare routine for a family?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "The best family skincare routine uses age-appropriate products for each family member. LA VELA BIANCA is designed for teens (8-18) with Centella Asiatica, ReRoots is formulated for young adults (18-35) with Tranexamic Acid, and OROÉ provides luxury anti-aging with EGF for mature skin (35+). All three brands are made in Canada by the same family."
        }
      },
      {
        "@type": "Question",
        "name": "Is it safe for teenagers to use skincare products?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes, when using age-appropriate formulas. LA VELA BIANCA is specifically designed for teens aged 8-18 with pediatric-safe, pH-balanced formulas (pH 5.0-5.3). We recommend a patch test for children under 10 and always using daily SPF protection."
        }
      },
      {
        "@type": "Question",
        "name": "What skincare ingredients are best for Gen Alpha?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Gen Alpha (born 2010+) benefits from gentle, non-irritating ingredients like Centella Asiatica, which calms inflammation and promotes healing without harsh actives like retinol. LA VELA BIANCA uses Centella as its key ingredient specifically for young, developing skin."
        }
      },
      {
        "@type": "Question",
        "name": "Why is PDRN skincare so expensive?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "PDRN (Polydeoxyribonucleotide) is a bio-active compound derived from salmon DNA that requires complex extraction processes. Higher concentrations (like the EGF + PDRN in OROÉ at $159 CAD) provide more intensive cellular rejuvenation benefits. Budget-friendly options like LA VELA BIANCA ($49 CAD) use different active ingredients suited for younger skin."
        }
      },
      {
        "@type": "Question",
        "name": "What is the difference between LA VELA BIANCA, ReRoots, and OROÉ?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "All three brands are part of the same Canadian family business: LA VELA BIANCA ($49 CAD) is teen skincare with Centella Asiatica for ages 8-18. ReRoots ($155 CAD) is bio-active PDRN skincare with Tranexamic Acid for ages 18-35. OROÉ ($159 CAD) is luxury anti-aging with EGF for ages 35+. Each is formulated for specific life stages."
        }
      }
    ]
  };

  const GENERATIONS = [
    {
      id: "genalpha",
      generation: "Gen Alpha & Gen Z",
      ages: "8-18",
      brand: "LA VELA BIANCA",
      tagline: "The Anmol Singh Collection",
      icon: Heart,
      color: "from-[#0D4D4D] to-[#E8C4B8]",
      textColor: "text-[#E8C4B8]",
      price: "$49 CAD",
      keyIngredient: "Centella Asiatica",
      concerns: ["Teen acne", "Redness", "Sensitivity", "First skincare routine"],
      whyThisAge: "Young skin needs gentle, non-irritating formulas that support the developing skin barrier without harsh actives like retinol.",
      heroProduct: "ORO ROSA Serum",
      route: "/lavela"
    },
    {
      id: "millennial",
      generation: "Millennials & Young Gen X",
      ages: "18-35",
      brand: "ReRoots",
      tagline: "The Gurnaman Singh Collection",
      icon: Dna,
      color: "from-[#D4AF37] to-[#F8A5B8]",
      textColor: "text-[#D4AF37]",
      price: "$155 CAD",
      keyIngredient: "Tranexamic Acid 5%",
      concerns: ["Dark spots", "Uneven tone", "Early fine lines", "Dullness"],
      whyThisAge: "This age group benefits from clinical-grade actives that target hyperpigmentation and maintain youthful radiance.",
      heroProduct: "AURA-GEN TXA+PDRN Serum",
      route: "/products"
    },
    {
      id: "mature",
      generation: "Gen X & Boomers",
      ages: "35+",
      brand: "OROÉ",
      tagline: "The Founders' Collection",
      icon: Crown,
      color: "from-[#1A1A1A] to-[#D4AF37]",
      textColor: "text-[#D4AF37]",
      price: "$159 CAD",
      keyIngredient: "EGF + PDRN Complex",
      concerns: ["Deep wrinkles", "Loss of elasticity", "Cellular aging", "Volume loss"],
      whyThisAge: "Mature skin requires intensive cellular rejuvenation with bio-active compounds that stimulate repair at the DNA level.",
      heroProduct: "Luminous Elixir",
      route: "/oroe"
    }
  ];

  return (
    <>
      {/* Comprehensive SEO Meta Tags */}
      <Helmet>
        <title>The Family Skin Protocol: From Gen Alpha to Golden Years | Complete Family Skincare Guide</title>
        <meta name="description" content="Discover the perfect skincare routine for your entire family. LA VELA BIANCA for teens (8-18), ReRoots for young adults (18-35), OROÉ for mature skin (35+). Canadian family-owned, science-backed formulas." />
        <meta name="keywords" content="family skincare routine, Gen Alpha skincare, teen skincare safe, best skincare for teenagers, family beauty routine, multi-generational skincare, Canadian skincare family, PDRN skincare Canada" />
        <link rel="canonical" href="https://reroots.ca/family-skin-protocol" />
        
        {/* Open Graph */}
        <meta property="og:type" content="article" />
        <meta property="og:title" content="The Family Skin Protocol: From Gen Alpha to Golden Years" />
        <meta property="og:description" content="Complete family skincare guide with products for every generation. Canadian family-owned science." />
        <meta property="og:image" content="https://images.unsplash.com/photo-1581579438747-1dc8d17bbce4?w=1200" />
        <meta property="og:url" content="https://reroots.ca/family-skin-protocol" />
        
        {/* Twitter */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="The Family Skin Protocol: Skincare for Every Generation" />
        <meta name="twitter:description" content="Discover age-appropriate skincare for your entire family - from Gen Alpha to Golden Years." />
        
        {/* Schema.org JSON-LD */}
        <script type="application/ld+json">{JSON.stringify(pageSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(articleSchema)}</script>
        <script type="application/ld+json">{JSON.stringify(faqSchema)}</script>
      </Helmet>

      <div className="min-h-screen bg-gradient-to-b from-[#FAF8F5] to-white">
        {/* Hero Section */}
        <section className="relative py-20 px-4 overflow-hidden bg-gradient-to-br from-[#2D2A2E] via-[#1a1819] to-[#2D2A2E]">
          <div className="absolute inset-0 opacity-5">
            <div className="absolute inset-0" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(212,175,55,0.5) 1px, transparent 0)',
              backgroundSize: '40px 40px'
            }}></div>
          </div>
          
          <div className="max-w-5xl mx-auto text-center relative z-10">
            <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] border-[#D4AF37]/30 mb-6">
              <Sparkles className="h-3 w-3 mr-1" />
              THE COMPLETE FAMILY GUIDE
            </Badge>
            
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>
              The Family Skin Protocol
            </h1>
            <p className="text-xl md:text-2xl text-[#D4AF37] mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
              From Gen Alpha to Golden Years
            </p>
            
            <p className="text-lg text-white/70 max-w-2xl mx-auto mb-8">
              A Canadian family's mission to create the perfect skincare for every generation. 
              Three brands, three life stages, one philosophy: science-backed formulas that work.
            </p>

            {/* Family Story Quick Stats */}
            <div className="flex flex-wrap justify-center gap-8 mt-10">
              <div className="text-center">
                <Users className="h-8 w-8 text-[#D4AF37] mx-auto mb-2" />
                <p className="text-2xl font-bold text-white">3</p>
                <p className="text-white/60 text-sm">Generations Covered</p>
              </div>
              <div className="text-center">
                <Beaker className="h-8 w-8 text-[#D4AF37] mx-auto mb-2" />
                <p className="text-2xl font-bold text-white">100%</p>
                <p className="text-white/60 text-sm">Canadian Formulated</p>
              </div>
              <div className="text-center">
                <Shield className="h-8 w-8 text-[#D4AF37] mx-auto mb-2" />
                <p className="text-2xl font-bold text-white">8-65+</p>
                <p className="text-white/60 text-sm">Age Range</p>
              </div>
              <div className="text-center">
                <Award className="h-8 w-8 text-[#D4AF37] mx-auto mb-2" />
                <p className="text-2xl font-bold text-white">1</p>
                <p className="text-white/60 text-sm">Family Legacy</p>
              </div>
            </div>
          </div>
        </section>

        {/* The Protocol - Generation by Generation */}
        <section className="py-16 px-4">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
                The Right Product for Every Life Stage
              </h2>
              <p className="text-[#5A5A5A] max-w-2xl mx-auto">
                Our family developed three distinct brands because we experienced firsthand that 
                one-size-fits-all skincare doesn't work. Here's our protocol.
              </p>
            </div>

            <div className="space-y-8">
              {GENERATIONS.map((gen, idx) => {
                const IconComponent = gen.icon;
                return (
                  <motion.div
                    key={gen.id}
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: idx * 0.1 }}
                    className={`rounded-3xl overflow-hidden bg-gradient-to-br ${gen.color} p-8 md:p-10`}
                  >
                    <div className="grid md:grid-cols-2 gap-8 items-center">
                      {/* Left: Generation Info */}
                      <div>
                        <div className="flex items-center gap-3 mb-4">
                          <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center">
                            <IconComponent className={`h-6 w-6 text-white`} />
                          </div>
                          <div>
                            <Badge className="bg-white/20 text-white border-white/30">
                              Ages {gen.ages}
                            </Badge>
                          </div>
                        </div>
                        
                        <h3 className="text-3xl font-bold text-white mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>
                          {gen.generation}
                        </h3>
                        <p className={`${gen.textColor} italic mb-4`}>{gen.tagline}</p>
                        
                        <p className="text-white/80 mb-6">
                          {gen.whyThisAge}
                        </p>

                        <div className="flex flex-wrap gap-2 mb-6">
                          {gen.concerns.map((concern, i) => (
                            <span key={i} className="text-xs bg-white/10 text-white/80 px-3 py-1 rounded-full">
                              {concern}
                            </span>
                          ))}
                        </div>

                        <Link to={gen.route}>
                          <Button className="bg-white text-gray-900 hover:bg-white/90">
                            Shop {gen.brand} <ArrowRight className="ml-2 h-4 w-4" />
                          </Button>
                        </Link>
                      </div>

                      {/* Right: Product Card */}
                      <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20">
                        <div className="text-center mb-4">
                          <h4 className="text-2xl font-bold text-white">{gen.brand}</h4>
                          <p className={`${gen.textColor} text-3xl font-bold mt-2`}>{gen.price}</p>
                        </div>
                        
                        <div className="space-y-3">
                          <div className="flex items-center gap-2">
                            <Check className="h-4 w-4 text-green-400" />
                            <span className="text-white/80 text-sm">Key: {gen.keyIngredient}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Check className="h-4 w-4 text-green-400" />
                            <span className="text-white/80 text-sm">Hero Product: {gen.heroProduct}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Check className="h-4 w-4 text-green-400" />
                            <span className="text-white/80 text-sm">Dermatologist Tested</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Check className="h-4 w-4 text-green-400" />
                            <span className="text-white/80 text-sm">Made in Canada 🇨🇦</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </section>

        {/* The Family Legacy Story */}
        <section className="py-16 px-4 bg-gradient-to-br from-[#FAF8F5] to-[#FDF9F9]">
          <div className="max-w-4xl mx-auto text-center">
            <Badge className="bg-[#D4AF37]/10 text-[#D4AF37] border-[#D4AF37]/30 mb-6">
              <Star className="h-3 w-3 mr-1" />
              OUR STORY
            </Badge>
            
            <h2 className="text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>
              Built by Tejinder Sandhu & Pawandeep Kaur
            </h2>
            
            <p className="text-lg text-[#5A5A5A] mb-8 leading-relaxed">
              When our sons—<strong>Gurnaman (18)</strong> and <strong>Anmol (15)</strong>—needed skincare that 
              actually worked for their age, we realized there was a gap in the market. Generic "anti-aging" 
              products weren't right for teens, and cheap drugstore brands weren't effective for our own 
              mature skin concerns. So we created three distinct brands, each formulated for a specific life stage.
            </p>

            <div className="grid md:grid-cols-3 gap-6 mt-10">
              <div className="p-6 bg-white rounded-2xl shadow-lg border border-gray-100">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#0D4D4D] to-[#E8C4B8] flex items-center justify-center mx-auto mb-4">
                  <Heart className="h-8 w-8 text-white" />
                </div>
                <h4 className="font-bold text-[#2D2A2E] mb-2">Anmol Singh</h4>
                <p className="text-[#5A5A5A] text-sm">Age 15 • Inspired LA VELA BIANCA</p>
                <p className="text-xs text-[#888] mt-2">"Finally, skincare that doesn't burn my face."</p>
              </div>
              
              <div className="p-6 bg-white rounded-2xl shadow-lg border border-gray-100">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#D4AF37] to-[#F8A5B8] flex items-center justify-center mx-auto mb-4">
                  <Dna className="h-8 w-8 text-white" />
                </div>
                <h4 className="font-bold text-[#2D2A2E] mb-2">Gurnaman Singh</h4>
                <p className="text-[#5A5A5A] text-sm">Age 18 • Inspired ReRoots</p>
                <p className="text-xs text-[#888] mt-2">"Clinical results without the clinical price tag."</p>
              </div>
              
              <div className="p-6 bg-white rounded-2xl shadow-lg border border-gray-100">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#1A1A1A] to-[#D4AF37] flex items-center justify-center mx-auto mb-4">
                  <Crown className="h-8 w-8 text-white" />
                </div>
                <h4 className="font-bold text-[#2D2A2E] mb-2">The Founders</h4>
                <p className="text-[#5A5A5A] text-sm">35+ • Created OROÉ</p>
                <p className="text-xs text-[#888] mt-2">"Luxury that actually delivers on its promise."</p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-16 px-4 bg-[#2D2A2E]">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-3xl font-bold text-white mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>
              Find Your Family's Perfect Protocol
            </h2>
            <p className="text-white/70 mb-8">
              Take our 2-minute Bio-Age Scan to get personalized recommendations for each family member.
            </p>
            
            <div className="flex flex-wrap justify-center gap-4">
              <Link to="/Bio-Age-Repair-Scan">
                <Button className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-bold px-8 py-6 text-lg">
                  <Sparkles className="mr-2 h-5 w-5" />
                  Start Bio-Age Scan
                </Button>
              </Link>
              <Link to="/shop">
                <Button variant="outline" className="border-white/30 text-white hover:bg-white/10 px-8 py-6 text-lg">
                  Browse All Collections
                </Button>
              </Link>
            </div>
          </div>
        </section>

        {/* FAQ Section for SEO */}
        <section className="py-16 px-4 bg-[#FAF8F5]">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-[#2D2A2E] text-center mb-10" style={{ fontFamily: "'Playfair Display', serif" }}>
              Frequently Asked Questions
            </h2>
            
            <div className="space-y-4">
              {[
                {
                  q: "What is the best skincare routine for a family?",
                  a: "The best family skincare routine uses age-appropriate products for each family member. LA VELA BIANCA is designed for teens (8-18) with Centella Asiatica, ReRoots is formulated for young adults (18-35) with Tranexamic Acid, and OROÉ provides luxury anti-aging with EGF for mature skin (35+)."
                },
                {
                  q: "Is it safe for teenagers to use skincare products?",
                  a: "Yes, when using age-appropriate formulas. LA VELA BIANCA is specifically designed for teens aged 8-18 with pediatric-safe, pH-balanced formulas (pH 5.0-5.3). We recommend a patch test for children under 10."
                },
                {
                  q: "What skincare ingredients are best for Gen Alpha?",
                  a: "Gen Alpha benefits from gentle, non-irritating ingredients like Centella Asiatica, which calms inflammation and promotes healing without harsh actives like retinol."
                },
                {
                  q: "Why is PDRN skincare so expensive?",
                  a: "PDRN requires complex extraction processes. Higher concentrations (like in OROÉ at $159) provide more intensive benefits. Budget-friendly options like LA VELA BIANCA ($49) use different actives suited for younger skin."
                }
              ].map((faq, idx) => (
                <div key={idx} className="bg-white p-6 rounded-xl border border-gray-100">
                  <h3 className="font-bold text-[#2D2A2E] mb-2">{faq.q}</h3>
                  <p className="text-[#5A5A5A] text-sm">{faq.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </>
  );
};

export default FamilySkinProtocolPage;
