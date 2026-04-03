import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { 
  ChevronRight, ChevronDown, Beaker, Dna, Sparkles, 
  FlaskConical, Shield, Leaf, Zap, Award, Heart, Target,
  BookOpen, ExternalLink
} from "lucide-react";

const ScienceGlossaryPage = () => {
  const [openTerms, setOpenTerms] = useState(new Set(['pdrn'])); // PDRN open by default

  // Glossary terms with AEO-optimized definitions
  const glossaryTerms = [
    {
      id: "pdrn",
      term: "PDRN (Polydeoxyribonucleotide)",
      definition: "A bio-active molecule derived from salmon DNA that mimics the skin's natural renewal process.",
      benefit: "In cosmetics, it enhances the appearance of skin resilience and supports a smoother, more youthful-looking texture.",
      icon: Dna,
      relatedProduct: {
        name: "AURA-GEN Serum",
        url: "/products/prod-aura-gen"
      },
      category: "Active Ingredient"
    },
    {
      id: "nad",
      term: "NAD+ (Nicotinamide Adenine Dinucleotide)",
      definition: "A critical coenzyme found in all living cells, essential for energy metabolism.",
      benefit: "Topical NAD+ helps revitalize the appearance of tired, aging skin and supports the skin's natural barrier.",
      icon: Zap,
      relatedProduct: {
        name: "OROÉ Black Label",
        url: "/oroe"
      },
      category: "Coenzyme"
    },
    {
      id: "tranexamic-acid",
      term: "Tranexamic Acid",
      definition: "A potent amino acid derivative used in advanced skincare.",
      benefit: "Specifically targets the appearance of surface dullness and uneven skin tone, resulting in a more luminous complexion.",
      icon: Sparkles,
      relatedProduct: {
        name: "AURA-GEN Serum",
        url: "/products/prod-aura-gen"
      },
      category: "Active Ingredient"
    },
    {
      id: "biotech-skincare",
      term: "Biotech Skincare",
      definition: "The intersection of laboratory science and nature, where natural ingredients are refined or 'grown' in controlled environments to ensure high purity and potency.",
      benefit: "Guaranteed consistency and higher efficacy than traditional botanical extracts.",
      icon: FlaskConical,
      relatedProduct: {
        name: "All ReRoots Products",
        url: "/shop"
      },
      category: "Industry Term"
    },
    {
      id: "skin-longevity",
      term: "Skin Longevity",
      definition: "A holistic approach to skincare focused on maintaining the skin's health, resilience, and appearance over time, rather than just 'anti-aging.'",
      benefit: "Results in a consistently healthy-looking glow at any age.",
      icon: Heart,
      relatedProduct: {
        name: "Bio-Age Skin Quiz",
        url: "/Bio-Age-Repair-Scan"
      },
      category: "Philosophy"
    },
    {
      id: "argireline",
      term: "Argireline (Acetyl Hexapeptide-8)",
      definition: "A widely acclaimed peptide known for its 'line-refining' properties.",
      benefit: "Visibly reduces the appearance of expression lines, particularly around the eyes and forehead.",
      icon: Target,
      relatedProduct: {
        name: "AURA-GEN Serum",
        url: "/products/prod-aura-gen"
      },
      category: "Peptide"
    },
    {
      id: "fibroblasts",
      term: "Fibroblasts",
      definition: "The most common type of cell found in connective tissue.",
      benefit: "In the context of biotech skincare, products are formulated to support the environment in which fibroblasts thrive, maintaining a firm, plump skin appearance.",
      icon: Beaker,
      relatedProduct: {
        name: "Science of PDRN",
        url: "/science"
      },
      category: "Cell Biology"
    },
    {
      id: "gmp-certified",
      term: "GMP-Certified (Good Manufacturing Practice)",
      definition: "An international standard that ensures products are consistently produced and controlled according to quality standards.",
      benefit: "Guarantees that ReRoots products meet strict safety and purity benchmarks.",
      icon: Award,
      relatedProduct: {
        name: "About ReRoots",
        url: "/about"
      },
      category: "Quality Standard"
    },
    {
      id: "sodium-dna",
      term: "Sodium DNA",
      definition: "The salt form of DNA (often PDRN) used for its high stability in topical serums.",
      benefit: "Acts as a powerful skin-conditioning agent that improves hydration and surface smoothness.",
      icon: Dna,
      relatedProduct: {
        name: "AURA-GEN Serum",
        url: "/products/prod-aura-gen"
      },
      category: "Ingredient Form"
    },
    {
      id: "bio-active-complex",
      term: "Bio-Active Complex",
      definition: "A synergistic blend of ingredients that work together to trigger a specific aesthetic result.",
      benefit: "ReRoots' 17% Active Recovery Complex is a bio-active blend designed for maximum skin restoration.",
      icon: Leaf,
      relatedProduct: {
        name: "AURA-GEN 17% Complex",
        url: "/products/prod-aura-gen"
      },
      category: "Formulation"
    }
  ];

  // Generate DefinedTerm schema for each glossary term
  const definedTermsSchema = {
    "@context": "https://schema.org",
    "@type": "DefinedTermSet",
    "name": "ReRoots Biotech Skincare Glossary",
    "description": "A comprehensive glossary of biotech skincare terms including PDRN, NAD+, Tranexamic Acid, and more.",
    "hasDefinedTerm": glossaryTerms.map(term => ({
      "@type": "DefinedTerm",
      "name": term.term,
      "description": term.definition,
      "inDefinedTermSet": "https://reroots.ca/science-glossary"
    }))
  };

  // FAQ Schema for additional AEO optimization
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": glossaryTerms.map(term => ({
      "@type": "Question",
      "name": `What is ${term.term.split(' (')[0]}?`,
      "acceptedAnswer": {
        "@type": "Answer",
        "text": `${term.definition} ${term.benefit}`
      }
    }))
  };

  const toggleTerm = (termId) => {
    setOpenTerms(prev => {
      const newSet = new Set(prev);
      if (newSet.has(termId)) {
        newSet.delete(termId);
      } else {
        newSet.add(termId);
      }
      return newSet;
    });
  };

  // Get unique categories
  const categories = [...new Set(glossaryTerms.map(t => t.category))];

  return (
    <div className="min-h-screen bg-[#FAF8F5]">
      <Helmet>
        <title>Science Glossary: PDRN, NAD+, Tranexamic Acid & Biotech Skincare Terms | ReRoots</title>
        <meta name="description" content="Learn about PDRN, NAD+, Tranexamic Acid, Argireline, and other biotech skincare ingredients. Comprehensive glossary of scientific terms used in ReRoots products." />
        <meta name="keywords" content="PDRN definition, what is PDRN, NAD+ skincare, Tranexamic Acid benefits, Argireline peptide, biotech skincare glossary, skin longevity, GMP certified skincare, Sodium DNA, bio-active complex" />
        <link rel="canonical" href="https://reroots.ca/science-glossary" />
        
        {/* Open Graph */}
        <meta property="og:title" content="Biotech Skincare Glossary | ReRoots Science" />
        <meta property="og:description" content="Understand the science behind PDRN, NAD+, and other biotech skincare ingredients." />
        <meta property="og:type" content="article" />
        <meta property="og:url" content="https://reroots.ca/science-glossary" />
        
        {/* DefinedTermSet Schema */}
        <script type="application/ld+json">
          {JSON.stringify(definedTermsSchema)}
        </script>
        
        {/* FAQ Schema for AEO */}
        <script type="application/ld+json">
          {JSON.stringify(faqSchema)}
        </script>
      </Helmet>

      {/* Breadcrumb Navigation */}
      <div className="bg-white border-b border-[#2D2A2E]/5">
        <div className="max-w-4xl mx-auto px-6 py-3">
          <nav className="flex items-center gap-2 text-sm text-[#5A5A5A]">
            <Link to="/" className="hover:text-[#F8A5B8] transition-colors">Home</Link>
            <ChevronRight className="h-4 w-4" />
            <Link to="/science" className="hover:text-[#F8A5B8] transition-colors">Science</Link>
            <ChevronRight className="h-4 w-4" />
            <span className="text-[#2D2A2E] font-medium">Glossary</span>
          </nav>
        </div>
      </div>

      {/* Hero Section */}
      <section className="pt-16 pb-12 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-[#F8A5B8]/10 text-[#F8A5B8] px-4 py-2 rounded-full text-sm font-medium mb-6">
            <BookOpen className="h-4 w-4" />
            Educational Resource
          </div>
          <h1 className="font-luxury text-4xl md:text-5xl text-[#2D2A2E] mb-6 leading-tight">
            Biotech Skincare <span className="text-[#F8A5B8]">Glossary</span>
          </h1>
          <p className="text-lg text-[#5A5A5A] max-w-2xl mx-auto leading-relaxed">
            Understand the science behind our formulations. From PDRN to NAD+, 
            learn what makes biotech skincare different from traditional products.
          </p>
        </div>
      </section>

      {/* Quick Navigation */}
      <section className="pb-8 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex flex-wrap justify-center gap-2">
            {glossaryTerms.map(term => (
              <button
                key={term.id}
                onClick={() => {
                  setOpenTerms(new Set([term.id]));
                  document.getElementById(term.id)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }}
                className="px-3 py-1.5 bg-white rounded-full border border-[#2D2A2E]/10 text-sm text-[#5A5A5A] hover:border-[#F8A5B8] hover:text-[#F8A5B8] transition-colors"
              >
                {term.term.split(' (')[0]}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Glossary Terms - Accordion Style */}
      <section className="pb-16 px-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {glossaryTerms.map((term, idx) => {
            const isOpen = openTerms.has(term.id);
            const TermIcon = term.icon;
            
            return (
              <div 
                key={term.id}
                id={term.id}
                className="bg-white rounded-2xl border border-[#2D2A2E]/5 overflow-hidden shadow-sm"
                data-testid={`glossary-term-${term.id}`}
              >
                {/* Accordion Header */}
                <button
                  onClick={() => toggleTerm(term.id)}
                  className="w-full flex items-center justify-between p-5 text-left hover:bg-[#FAF8F5]/50 transition-colors"
                  aria-expanded={isOpen}
                  aria-controls={`content-${term.id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#F8A5B8]/10 to-[#D4AF37]/10 flex items-center justify-center">
                      <TermIcon className="h-6 w-6 text-[#F8A5B8]" />
                    </div>
                    <div>
                      <span className="text-xs text-[#F8A5B8] font-medium uppercase tracking-wider">
                        {term.category}
                      </span>
                      <h2 className="font-semibold text-[#2D2A2E] text-lg">
                        {term.term}
                      </h2>
                    </div>
                  </div>
                  <ChevronDown 
                    className={`h-5 w-5 text-[#5A5A5A] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                  />
                </button>
                
                {/* Accordion Content */}
                <div 
                  id={`content-${term.id}`}
                  className={`overflow-hidden transition-all duration-300 ${isOpen ? 'max-h-[500px]' : 'max-h-0'}`}
                >
                  <div className="px-5 pb-5 pt-0">
                    <div className="pl-16 space-y-4">
                      {/* Definition */}
                      <div>
                        <h3 className="text-sm font-semibold text-[#2D2A2E] uppercase tracking-wider mb-2">
                          Definition
                        </h3>
                        <p className="text-[#5A5A5A] leading-relaxed">
                          {term.definition}
                        </p>
                      </div>
                      
                      {/* Benefit */}
                      <div className="bg-[#FAF8F5] rounded-xl p-4 border-l-4 border-[#F8A5B8]">
                        <h3 className="text-sm font-semibold text-[#2D2A2E] uppercase tracking-wider mb-2">
                          Benefit
                        </h3>
                        <p className="text-[#5A5A5A] leading-relaxed">
                          {term.benefit}
                        </p>
                      </div>
                      
                      {/* Related Product Link */}
                      <div className="pt-2">
                        <Link 
                          to={term.relatedProduct.url}
                          className="inline-flex items-center gap-2 text-[#F8A5B8] hover:text-[#e8959a] font-medium text-sm transition-colors"
                        >
                          <ExternalLink className="h-4 w-4" />
                          Learn more: {term.relatedProduct.name}
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-6 bg-gradient-to-br from-[#2D2A2E] to-[#3D3A3E]">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="font-luxury text-3xl md:text-4xl text-white mb-4">
            Ready to Experience <span className="text-[#F8A5B8]">Biotech Skincare</span>?
          </h2>
          <p className="text-white/70 mb-8 max-w-2xl mx-auto">
            Now that you understand the science, discover how these powerful 
            ingredients come together in our formulations.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              to="/Bio-Age-Repair-Scan"
              className="inline-flex items-center justify-center gap-2 bg-[#F8A5B8] hover:bg-[#e8959a] text-[#2D2A2E] px-8 py-4 rounded-full font-semibold transition-all shadow-lg hover:shadow-xl"
              data-testid="take-quiz-cta"
            >
              <Beaker className="h-5 w-5" />
              Take the Bio-Age Quiz
            </Link>
            <Link 
              to="/shop"
              className="inline-flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 text-white px-8 py-4 rounded-full font-semibold transition-all"
            >
              Browse Products
            </Link>
          </div>
        </div>
      </section>

      {/* Related Resources */}
      <section className="py-12 px-6 bg-white border-t border-[#2D2A2E]/5">
        <div className="max-w-4xl mx-auto">
          <h3 className="font-semibold text-[#2D2A2E] mb-6 text-center">Related Resources</h3>
          <div className="grid md:grid-cols-3 gap-4">
            <Link 
              to="/science"
              className="flex items-center gap-3 p-4 bg-[#FAF8F5] rounded-xl hover:bg-[#F8A5B8]/5 transition-colors"
            >
              <FlaskConical className="h-5 w-5 text-[#F8A5B8]" />
              <span className="text-[#2D2A2E] font-medium">Science of PDRN</span>
            </Link>
            <Link 
              to="/pdrn-comparison-guide"
              className="flex items-center gap-3 p-4 bg-[#FAF8F5] rounded-xl hover:bg-[#F8A5B8]/5 transition-colors"
            >
              <Target className="h-5 w-5 text-[#F8A5B8]" />
              <span className="text-[#2D2A2E] font-medium">PDRN Comparison Guide</span>
            </Link>
            <Link 
              to="/faq"
              className="flex items-center gap-3 p-4 bg-[#FAF8F5] rounded-xl hover:bg-[#F8A5B8]/5 transition-colors"
            >
              <BookOpen className="h-5 w-5 text-[#F8A5B8]" />
              <span className="text-[#2D2A2E] font-medium">FAQ</span>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default ScienceGlossaryPage;
