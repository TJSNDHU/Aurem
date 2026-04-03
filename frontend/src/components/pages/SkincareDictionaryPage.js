import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { 
  Search, 
  BookOpen, 
  Sparkles, 
  ChevronRight,
  Dna,
  Droplets,
  Shield,
  Zap,
  Leaf,
  Sun,
  Clock,
  CheckCircle,
  ArrowRight,
  Filter
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

// Skincare Dictionary Data - SEO optimized ingredients and terms
const SKINCARE_DICTIONARY = [
  {
    id: 'pdrn',
    term: 'PDRN (Polydeoxyribonucleotide)',
    shortName: 'PDRN',
    category: 'regeneration',
    icon: Dna,
    description: 'A powerful regenerative compound derived from salmon DNA that stimulates cellular repair and tissue regeneration.',
    benefits: [
      'Accelerates wound healing by up to 30%',
      'Stimulates fibroblast proliferation',
      'Reduces inflammation and redness',
      'Promotes collagen synthesis'
    ],
    science: 'PDRN activates the A2A adenosine receptor, which triggers a cascade of regenerative cellular processes. Clinical studies show significant improvement in skin elasticity and hydration within 4-8 weeks.',
    foundIn: ['AURA-GEN TXA+PDRN Bio-Regenerator'],
    relatedTerms: ['DNA repair', 'Salmon DNA', 'Tissue regeneration'],
    seoKeywords: ['PDRN skincare', 'salmon DNA benefits', 'skin regeneration', 'anti-aging PDRN']
  },
  {
    id: 'txa',
    term: 'Tranexamic Acid (TXA)',
    shortName: 'TXA',
    category: 'brightening',
    icon: Sun,
    description: 'A synthetic amino acid that inhibits melanin production and reduces hyperpigmentation for a more even skin tone.',
    benefits: [
      'Reduces dark spots and melasma',
      'Inhibits UV-induced pigmentation',
      'Evens skin tone without irritation',
      'Safe for all skin types'
    ],
    science: 'TXA works by inhibiting plasminogen activator, which reduces the transfer of melanin to skin cells. Unlike hydroquinone, it does not cause rebound hyperpigmentation.',
    foundIn: ['AURA-GEN TXA+PDRN Bio-Regenerator'],
    relatedTerms: ['Melasma treatment', 'Hyperpigmentation', 'Skin brightening'],
    seoKeywords: ['tranexamic acid skincare', 'dark spot treatment', 'melasma solution', 'skin brightening ingredients']
  },
  {
    id: 'egf',
    term: 'EGF (Epidermal Growth Factor)',
    shortName: 'EGF',
    category: 'regeneration',
    icon: Zap,
    description: 'A naturally occurring protein that stimulates cell growth and wound healing by binding to specific receptors on skin cells.',
    benefits: [
      'Accelerates skin cell turnover',
      'Reduces appearance of fine lines',
      'Improves skin texture and firmness',
      'Enhances barrier function'
    ],
    science: 'EGF binds to EGFR receptors on keratinocytes and fibroblasts, triggering intracellular signaling that promotes cell division and migration. Nobel Prize-winning research has validated its regenerative properties.',
    foundIn: ['Premium clinical serums'],
    relatedTerms: ['Growth factors', 'Cell renewal', 'Anti-aging peptides'],
    seoKeywords: ['EGF skincare', 'epidermal growth factor', 'skin cell regeneration', 'anti-aging growth factor']
  },
  {
    id: 'hyaluronic-acid',
    term: 'Hyaluronic Acid (HA)',
    shortName: 'HA',
    category: 'hydration',
    icon: Droplets,
    description: 'A naturally occurring molecule that can hold up to 1000x its weight in water, providing deep hydration to the skin.',
    benefits: [
      'Intense hydration for all skin types',
      'Plumps fine lines and wrinkles',
      'Improves skin elasticity',
      'Non-comedogenic and gentle'
    ],
    science: 'HA exists naturally in skin but decreases with age. Low molecular weight HA penetrates deeper for hydration, while high molecular weight HA forms a protective barrier on the surface.',
    foundIn: ['Most hydrating serums and moisturizers'],
    relatedTerms: ['Hydration', 'Moisture retention', 'Plumping'],
    seoKeywords: ['hyaluronic acid benefits', 'skin hydration', 'HA serum', 'moisturizing ingredients']
  },
  {
    id: 'niacinamide',
    term: 'Niacinamide (Vitamin B3)',
    shortName: 'Niacinamide',
    category: 'barrier',
    icon: Shield,
    description: 'A versatile vitamin that strengthens the skin barrier, reduces inflammation, and minimizes pore appearance.',
    benefits: [
      'Strengthens skin barrier function',
      'Reduces sebum production',
      'Minimizes pore appearance',
      'Fades hyperpigmentation'
    ],
    science: 'Niacinamide increases ceramide production, essential for barrier function. It also inhibits melanosome transfer, reducing pigmentation without the irritation of stronger actives.',
    foundIn: ['Barrier repair products'],
    relatedTerms: ['Vitamin B3', 'Barrier repair', 'Pore minimizing'],
    seoKeywords: ['niacinamide benefits', 'vitamin B3 skincare', 'pore minimizer', 'barrier repair']
  },
  {
    id: 'retinol',
    term: 'Retinol (Vitamin A)',
    shortName: 'Retinol',
    category: 'anti-aging',
    icon: Clock,
    description: 'The gold standard in anti-aging, retinol accelerates cell turnover and stimulates collagen production.',
    benefits: [
      'Reduces fine lines and wrinkles',
      'Improves skin texture',
      'Unclogs pores and treats acne',
      'Stimulates collagen production'
    ],
    science: 'Retinol converts to retinoic acid in the skin, binding to nuclear receptors that regulate gene expression for cell renewal. Consistent use over 12 weeks shows measurable improvements.',
    foundIn: ['Anti-aging treatments'],
    relatedTerms: ['Vitamin A', 'Retinoid', 'Cell turnover'],
    seoKeywords: ['retinol benefits', 'vitamin A skincare', 'anti-aging retinol', 'wrinkle treatment']
  },
  {
    id: 'peptides',
    term: 'Peptides',
    shortName: 'Peptides',
    category: 'anti-aging',
    icon: Dna,
    description: 'Short chains of amino acids that signal skin to produce more collagen and repair damaged tissue.',
    benefits: [
      'Stimulates collagen synthesis',
      'Firms and tightens skin',
      'Reduces inflammation',
      'Improves skin elasticity'
    ],
    science: 'Signal peptides like Matrixyl communicate with skin cells to increase collagen production. Carrier peptides deliver trace minerals that aid in wound healing and enzyme function.',
    foundIn: ['Anti-aging serums and creams'],
    relatedTerms: ['Amino acids', 'Collagen boosters', 'Signal peptides'],
    seoKeywords: ['peptides skincare', 'collagen peptides', 'anti-aging peptides', 'skin firming']
  },
  {
    id: 'ceramides',
    term: 'Ceramides',
    shortName: 'Ceramides',
    category: 'barrier',
    icon: Shield,
    description: 'Lipid molecules that make up over 50% of the skin barrier, essential for moisture retention and protection.',
    benefits: [
      'Restores skin barrier function',
      'Locks in moisture',
      'Protects against environmental damage',
      'Soothes sensitive skin'
    ],
    science: 'Ceramides form the "mortar" between skin cells (the "bricks"). As we age, ceramide production decreases, leading to dryness and sensitivity. Topical ceramides help restore this protective layer.',
    foundIn: ['Barrier repair moisturizers'],
    relatedTerms: ['Skin barrier', 'Lipids', 'Moisture lock'],
    seoKeywords: ['ceramides benefits', 'skin barrier repair', 'ceramide moisturizer', 'dry skin treatment']
  },
  {
    id: 'vitamin-c',
    term: 'Vitamin C (L-Ascorbic Acid)',
    shortName: 'Vitamin C',
    category: 'brightening',
    icon: Sun,
    description: 'A powerful antioxidant that brightens skin, fights free radicals, and boosts collagen production.',
    benefits: [
      'Brightens dull skin',
      'Protects against UV damage',
      'Stimulates collagen synthesis',
      'Reduces hyperpigmentation'
    ],
    science: 'L-Ascorbic Acid neutralizes free radicals and inhibits tyrosinase, the enzyme responsible for melanin production. It also acts as a cofactor for collagen-producing enzymes.',
    foundIn: ['Brightening serums'],
    relatedTerms: ['Antioxidant', 'Brightening', 'Free radical protection'],
    seoKeywords: ['vitamin C serum', 'skin brightening', 'antioxidant skincare', 'L-ascorbic acid']
  },
  {
    id: 'salicylic-acid',
    term: 'Salicylic Acid (BHA)',
    shortName: 'Salicylic Acid',
    category: 'exfoliation',
    icon: Leaf,
    description: 'A beta-hydroxy acid that penetrates oil to unclog pores and treat acne from within.',
    benefits: [
      'Unclogs pores deeply',
      'Treats and prevents acne',
      'Reduces blackheads and whiteheads',
      'Anti-inflammatory properties'
    ],
    science: 'As an oil-soluble acid, salicylic acid can penetrate into pores to dissolve the debris and sebum that cause breakouts. It also has anti-inflammatory effects that reduce redness.',
    foundIn: ['Acne treatments and cleansers'],
    relatedTerms: ['BHA', 'Acne treatment', 'Pore cleansing'],
    seoKeywords: ['salicylic acid benefits', 'BHA skincare', 'acne treatment', 'pore unclogging']
  }
];

const CATEGORIES = [
  { id: 'all', label: 'All Ingredients', icon: BookOpen },
  { id: 'regeneration', label: 'Regeneration', icon: Dna },
  { id: 'brightening', label: 'Brightening', icon: Sun },
  { id: 'hydration', label: 'Hydration', icon: Droplets },
  { id: 'anti-aging', label: 'Anti-Aging', icon: Clock },
  { id: 'barrier', label: 'Barrier', icon: Shield },
  { id: 'exfoliation', label: 'Exfoliation', icon: Leaf }
];

const SkincareDictionaryPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [expandedTerm, setExpandedTerm] = useState(null);
  
  // Filter ingredients based on search and category
  const filteredIngredients = useMemo(() => {
    return SKINCARE_DICTIONARY.filter(item => {
      const matchesSearch = searchQuery === '' || 
        item.term.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.shortName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.seoKeywords.some(kw => kw.toLowerCase().includes(searchQuery.toLowerCase()));
      
      const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
      
      return matchesSearch && matchesCategory;
    });
  }, [searchQuery, selectedCategory]);

  // Generate structured data for SEO
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "DefinedTermSet",
    "name": "Skincare Ingredient Dictionary",
    "description": "Comprehensive guide to skincare ingredients including PDRN, TXA, EGF, and more",
    "hasDefinedTerm": SKINCARE_DICTIONARY.map(item => ({
      "@type": "DefinedTerm",
      "name": item.term,
      "description": item.description
    }))
  };

  return (
    <>
      <Helmet>
        <title>Skincare Dictionary | Ingredient Guide | ReRoots Clinical Skincare</title>
        <meta name="description" content="Learn about skincare ingredients like PDRN, Tranexamic Acid, EGF, Hyaluronic Acid, and more. Expert guide to understanding what's in your skincare products." />
        <meta name="keywords" content="skincare ingredients, PDRN benefits, tranexamic acid, EGF skincare, hyaluronic acid, niacinamide, retinol, peptides" />
        <link rel="canonical" href="https://reroots.ca/skincare-dictionary" />
        <script type="application/ld+json">{JSON.stringify(structuredData)}</script>
      </Helmet>

      <div className="min-h-screen bg-gradient-to-b from-[#FAF7F2] to-white">
        {/* Hero Section */}
        <div className="relative overflow-hidden bg-gradient-to-br from-[#2D2A2E] via-[#3D3A3E] to-[#2D2A2E] text-white">
          <div className="absolute inset-0 opacity-10">
            <div className="absolute inset-0" style={{
              backgroundImage: `radial-gradient(circle at 20% 80%, #C9A86C 0%, transparent 50%),
                               radial-gradient(circle at 80% 20%, #F8A5B8 0%, transparent 50%)`
            }} />
          </div>
          
          <div className="max-w-6xl mx-auto px-4 py-16 relative z-10">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center"
            >
              <div className="inline-flex items-center gap-2 bg-[#C9A86C]/20 text-[#C9A86C] px-4 py-2 rounded-full text-sm font-medium mb-6">
                <BookOpen className="w-4 h-4" />
                The Science Behind Beautiful Skin
              </div>
              
              <h1 className="font-display text-4xl md:text-5xl font-bold mb-4">
                Skincare
                <span className="block text-[#C9A86C]">Dictionary</span>
              </h1>
              
              <p className="text-lg text-white/80 max-w-2xl mx-auto mb-8">
                Your comprehensive guide to understanding skincare ingredients. 
                Learn what's in your products and how they work for your skin.
              </p>

              {/* Search Bar */}
              <div className="max-w-xl mx-auto relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search ingredients (e.g., PDRN, Hyaluronic Acid, Retinol...)"
                  className="pl-12 pr-4 py-6 text-lg bg-white/10 border-white/20 text-white placeholder:text-white/50 rounded-full"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </motion.div>
          </div>
        </div>

        {/* Category Filters */}
        <div className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-gray-200 py-4">
          <div className="max-w-6xl mx-auto px-4">
            <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
              <Filter className="w-4 h-4 text-[#5A5A5A] flex-shrink-0" />
              {CATEGORIES.map((cat) => (
                <Button
                  key={cat.id}
                  variant={selectedCategory === cat.id ? "default" : "outline"}
                  size="sm"
                  className={`whitespace-nowrap rounded-full ${
                    selectedCategory === cat.id 
                      ? 'bg-[#2D2A2E] text-white' 
                      : 'border-gray-300'
                  }`}
                  onClick={() => setSelectedCategory(cat.id)}
                >
                  <cat.icon className="w-4 h-4 mr-1" />
                  {cat.label}
                </Button>
              ))}
            </div>
          </div>
        </div>

        {/* Results Count */}
        <div className="max-w-6xl mx-auto px-4 py-6">
          <p className="text-sm text-[#5A5A5A]">
            Showing {filteredIngredients.length} of {SKINCARE_DICTIONARY.length} ingredients
          </p>
        </div>

        {/* Ingredients Grid */}
        <div className="max-w-6xl mx-auto px-4 pb-16">
          <div className="grid md:grid-cols-2 gap-6">
            {filteredIngredients.map((item, idx) => {
              const IconComponent = item.icon;
              const isExpanded = expandedTerm === item.id;
              
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                >
                  <Card 
                    className={`border-2 transition-all duration-300 cursor-pointer ${
                      isExpanded ? 'border-[#C9A86C] shadow-lg' : 'border-gray-200 hover:border-[#C9A86C]/50'
                    }`}
                    onClick={() => setExpandedTerm(isExpanded ? null : item.id)}
                  >
                    <CardContent className="p-6">
                      {/* Header */}
                      <div className="flex items-start gap-4 mb-4">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#C9A86C] to-[#B8956A] flex items-center justify-center flex-shrink-0">
                          <IconComponent className="w-6 h-6 text-white" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h2 className="font-bold text-lg text-[#2D2A2E]">{item.shortName}</h2>
                            <Badge variant="outline" className="text-xs capitalize">
                              {item.category}
                            </Badge>
                          </div>
                          <p className="text-sm text-[#5A5A5A]">{item.term}</p>
                        </div>
                        <ChevronRight 
                          className={`w-5 h-5 text-[#5A5A5A] transition-transform ${isExpanded ? 'rotate-90' : ''}`} 
                        />
                      </div>

                      {/* Description */}
                      <p className="text-[#5A5A5A] mb-4">{item.description}</p>

                      {/* Expanded Content */}
                      {isExpanded && (
                        <motion.div
                          initial={{ opacity: 0, scaleY: 0 }}
                          animate={{ opacity: 1, scaleY: 1 }}
                          exit={{ opacity: 0, scaleY: 0 }}
                          style={{ transformOrigin: 'top' }}
                          className="space-y-4 pt-4 border-t border-gray-200"
                        >
                          {/* Benefits */}
                          <div>
                            <h3 className="font-semibold text-[#2D2A2E] mb-2 flex items-center gap-2">
                              <CheckCircle className="w-4 h-4 text-green-500" />
                              Key Benefits
                            </h3>
                            <ul className="space-y-1">
                              {item.benefits.map((benefit, i) => (
                                <li key={i} className="text-sm text-[#5A5A5A] flex items-start gap-2">
                                  <span className="text-[#C9A86C]">•</span>
                                  {benefit}
                                </li>
                              ))}
                            </ul>
                          </div>

                          {/* Science */}
                          <div>
                            <h3 className="font-semibold text-[#2D2A2E] mb-2 flex items-center gap-2">
                              <Dna className="w-4 h-4 text-purple-500" />
                              The Science
                            </h3>
                            <p className="text-sm text-[#5A5A5A]">{item.science}</p>
                          </div>

                          {/* Found In */}
                          {item.foundIn.length > 0 && (
                            <div>
                              <h3 className="font-semibold text-[#2D2A2E] mb-2 flex items-center gap-2">
                                <Sparkles className="w-4 h-4 text-[#C9A86C]" />
                                Found In Our Products
                              </h3>
                              <div className="flex flex-wrap gap-2">
                                {item.foundIn.map((product, i) => (
                                  <Badge key={i} className="bg-[#C9A86C]/10 text-[#C9A86C] hover:bg-[#C9A86C]/20">
                                    {product}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Related Terms */}
                          <div className="flex flex-wrap gap-2 pt-2">
                            {item.relatedTerms.map((term, i) => (
                              <span 
                                key={i} 
                                className="text-xs bg-gray-100 text-[#5A5A5A] px-2 py-1 rounded cursor-pointer hover:bg-gray-200"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSearchQuery(term);
                                }}
                              >
                                #{term.replace(/\s+/g, '')}
                              </span>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </div>

          {/* No Results */}
          {filteredIngredients.length === 0 && (
            <div className="text-center py-12">
              <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-[#5A5A5A]">No ingredients found matching "{searchQuery}"</p>
              <Button 
                variant="outline" 
                className="mt-4"
                onClick={() => {
                  setSearchQuery('');
                  setSelectedCategory('all');
                }}
              >
                Clear Filters
              </Button>
            </div>
          )}
        </div>

        {/* CTA Section */}
        <div className="bg-gradient-to-br from-[#C9A86C]/10 to-[#F8A5B8]/10 py-16">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <h2 className="font-display text-2xl font-bold text-[#2D2A2E] mb-4">
              Experience Clinical-Grade Skincare
            </h2>
            <p className="text-[#5A5A5A] mb-8 max-w-xl mx-auto">
              Our AURA-GEN TXA+PDRN Bio-Regenerator combines the most advanced ingredients 
              for visible results in just 4-8 weeks.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button asChild className="bg-[#C9A86C] hover:bg-[#B8956A] text-white px-8">
                <Link to="/products/bio-regenerative-serums">
                  <Sparkles className="w-4 h-4 mr-2" />
                  Shop AURA-GEN
                </Link>
              </Button>
              <Button asChild variant="outline" className="border-[#2D2A2E]">
                <Link to="/compare">
                  <ArrowRight className="w-4 h-4 mr-2" />
                  Compare Products
                </Link>
              </Button>
            </div>
          </div>
        </div>

        {/* Footer Navigation */}
        <div className="border-t border-gray-200 py-8">
          <div className="max-w-6xl mx-auto px-4">
            <div className="flex flex-wrap justify-center gap-6 text-sm text-[#5A5A5A]">
              <Link to="/" className="hover:text-[#C9A86C]">Home</Link>
              <Link to="/shop" className="hover:text-[#C9A86C]">Shop</Link>
              <Link to="/Bio-Age-Repair-Scan" className="hover:text-[#C9A86C]">Skin Quiz</Link>
              <Link to="/compare" className="hover:text-[#C9A86C]">Compare Products</Link>
              <Link to="/protocol" className="hover:text-[#C9A86C]">Recovery Protocol</Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default SkincareDictionaryPage;
