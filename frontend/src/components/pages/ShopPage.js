import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import axios from "axios";
import { Sparkles, Crown, Dna, Heart, ArrowRight, Shield, Star, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API = `${process.env.REACT_APP_BACKEND_URL || ''}/api`;

// Default collection templates - prices and products will be updated dynamically
const DEFAULT_COLLECTIONS = [
  {
    id: "oroe",
    name: "OROÉ",
    tagline: "The Founders' Collection",
    founders: "Tejinder Sandhu & Pawandeep Kaur",
    description: "Ultra-luxury cellular rejuvenation for discerning skin. The science of cellular resurrection.",
    ageTarget: "35+ Mature Skin",
    heroProduct: "Luminous Elixir",
    price: "$159 CAD",
    keyIngredient: "EGF + PDRN Complex",
    icon: Crown,
    image: "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=800&q=80",
    gradient: "from-[#0A0A0A] via-[#1A1A1A] to-[#D4AF37]/20",
    textColor: "text-[#D4AF37]",
    borderColor: "border-[#D4AF37]",
    route: "/oroe",
    badges: ["Luxury", "Anti-Aging", "Cellular Repair"],
    stats: { batchSize: "50 units", nextRelease: "Monthly" }
  },
  {
    id: "reroots",
    name: "ReRoots",
    tagline: "The Gurnaman Singh Collection",
    founders: "Gurnaman Singh (18)",
    description: "Clinical-grade bio-active skincare for young adults seeking visible, science-backed results.",
    ageTarget: "18-35 Young Adults",
    heroProduct: "AURA-GEN TXA+PDRN Serum",
    price: "$155 CAD",
    keyIngredient: "Tranexamic Acid 5%",
    icon: Dna,
    image: "https://files.catbox.moe/jdjokm.jpg",
    gradient: "from-[#2D2A2E] via-[#D4AF37]/30 to-[#F8A5B8]/20",
    textColor: "text-[#D4AF37]",
    borderColor: "border-[#D4AF37]",
    route: "/products",
    badges: ["Bio-Active", "Brightening", "PDRN Science"],
    stats: { satisfaction: "98%", reviews: "2,847+" }
  },
  {
    id: "lavela",
    name: "LA VELA BIANCA",
    tagline: "The Anmol Singh Collection",
    founders: "Anmol Singh (15)",
    description: "Pediatric-safe, luxury skincare designed for young, developing skin. Gentle yet effective.",
    ageTarget: "8-18 Teen Skin",
    heroProduct: "ORO ROSA Serum",
    price: "$49 CAD",
    keyIngredient: "Centella Asiatica",
    icon: Heart,
    image: "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800&q=80",
    gradient: "from-[#0D4D4D] via-[#1A6B6B] to-[#E8C4B8]/30",
    textColor: "text-[#E8C4B8]",
    borderColor: "border-[#E8C4B8]",
    route: "/lavela",
    badges: ["Pediatric-Safe", "pH Balanced", "Teen Approved"],
    stats: { safetyTested: "100%", ageRange: "8-18" }
  }
];

const ShopPage = () => {
  const [hoveredCollection, setHoveredCollection] = useState(null);
  const [collections, setCollections] = useState(DEFAULT_COLLECTIONS);
  const [loading, setLoading] = useState(true);

  // Fetch actual product data to update prices and images
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        // Fetch products from all brands
        const [rerootsRes, oroeRes, lavelaRes] = await Promise.all([
          axios.get(`${API}/products?featured=true&limit=1`).catch(() => ({ data: [] })),
          axios.get(`${API}/oroe/products`).catch(() => ({ data: { products: [] } })),
          axios.get(`${API}/lavela/products`).catch(() => ({ data: { products: [] } }))
        ]);

        const updatedCollections = [...DEFAULT_COLLECTIONS];
        
        // Update ReRoots collection with actual featured product
        const rerootsProducts = Array.isArray(rerootsRes.data) ? rerootsRes.data : (rerootsRes.data?.products || []);
        if (rerootsProducts.length > 0) {
          const product = rerootsProducts[0];
          const rerootsIdx = updatedCollections.findIndex(c => c.id === 'reroots');
          if (rerootsIdx >= 0) {
            updatedCollections[rerootsIdx] = {
              ...updatedCollections[rerootsIdx],
              heroProduct: product.name || updatedCollections[rerootsIdx].heroProduct,
              price: `$${product.price?.toFixed(0) || '155'} CAD`,
              image: product.images?.[0] || product.image || updatedCollections[rerootsIdx].image
            };
          }
        }

        // Update OROÉ collection with actual product
        const oroeProducts = Array.isArray(oroeRes.data) ? oroeRes.data : (oroeRes.data?.products || []);
        if (oroeProducts.length > 0) {
          const product = oroeProducts[0];
          const oroeIdx = updatedCollections.findIndex(c => c.id === 'oroe');
          if (oroeIdx >= 0) {
            updatedCollections[oroeIdx] = {
              ...updatedCollections[oroeIdx],
              heroProduct: product.name || updatedCollections[oroeIdx].heroProduct,
              price: `$${product.price?.toFixed(0) || '159'} CAD`,
              image: product.images?.[0] || product.image || updatedCollections[oroeIdx].image
            };
          }
        }

        // Update LA VELA collection with actual product
        const lavelaProducts = Array.isArray(lavelaRes.data) ? lavelaRes.data : (lavelaRes.data?.products || []);
        if (lavelaProducts.length > 0) {
          const product = lavelaProducts[0];
          const lavelaIdx = updatedCollections.findIndex(c => c.id === 'lavela');
          if (lavelaIdx >= 0) {
            updatedCollections[lavelaIdx] = {
              ...updatedCollections[lavelaIdx],
              heroProduct: product.name || updatedCollections[lavelaIdx].heroProduct,
              price: `$${product.price?.toFixed(0) || '49'} CAD`,
              image: product.images?.[0] || product.image || updatedCollections[lavelaIdx].image
            };
          }
        }

        setCollections(updatedCollections);
      } catch (error) {
        console.error('Failed to fetch products for shop page:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FAF8F5] to-white">
      {/* Hero Section */}
      <section className="relative py-20 px-4 overflow-hidden bg-gradient-to-br from-[#2D2A2E] via-[#1a1819] to-[#2D2A2E]">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(212,175,55,0.5) 1px, transparent 0)',
            backgroundSize: '40px 40px'
          }}></div>
        </div>
        
        <div className="max-w-6xl mx-auto text-center relative z-10">
          <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] border-[#D4AF37]/30 mb-6">
            <Sparkles className="h-3 w-3 mr-1" />
            GENERATIONAL COLLECTIONS
          </Badge>
          
          <h1 className="text-4xl md:text-6xl font-bold text-white mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>
            Three Generations,<br />
            <span className="text-[#D4AF37]">One Philosophy</span>
          </h1>
          
          <p className="text-xl text-white/70 max-w-2xl mx-auto mb-8">
            A family legacy of Canadian-Italian skincare science. Each collection crafted for a specific life stage, 
            by the family members who understand that stage best.
          </p>
          
          <div className="flex flex-wrap justify-center gap-6 mb-12">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] flex items-center justify-center mx-auto mb-2">
                <Crown className="h-8 w-8 text-[#0A0A0A]" />
              </div>
              <p className="text-white/60 text-sm">Tejinder & Pawandeep</p>
              <p className="text-[#D4AF37] text-xs">Founders</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#D4AF37] to-[#F8A5B8] flex items-center justify-center mx-auto mb-2">
                <Dna className="h-8 w-8 text-white" />
              </div>
              <p className="text-white/60 text-sm">Gurnaman Singh</p>
              <p className="text-[#D4AF37] text-xs">Age 18</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#0D4D4D] to-[#E8C4B8] flex items-center justify-center mx-auto mb-2">
                <Heart className="h-8 w-8 text-white" />
              </div>
              <p className="text-white/60 text-sm">Anmol Singh</p>
              <p className="text-[#E8C4B8] text-xs">Age 15</p>
            </div>
          </div>
        </div>
      </section>

      {/* Collections Grid */}
      <section className="py-16 px-4">
        <div className="max-w-7xl mx-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37]" />
            </div>
          ) : (
          <div className="grid lg:grid-cols-3 gap-8">
            {collections.map((collection, idx) => {
              const IconComponent = collection.icon;
              return (
                <motion.div
                  key={collection.id}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.15 }}
                  onMouseEnter={() => setHoveredCollection(collection.id)}
                  onMouseLeave={() => setHoveredCollection(null)}
                  className={`relative rounded-3xl overflow-hidden transition-all duration-500 ${
                    hoveredCollection === collection.id ? 'scale-105 shadow-2xl' : 'shadow-lg'
                  }`}
                >
                  {/* Background Gradient */}
                  <div className={`absolute inset-0 bg-gradient-to-br ${collection.gradient}`} />
                  
                  {/* Content */}
                  <div className="relative z-10 p-8">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-6">
                      <div>
                        <div className={`w-12 h-12 rounded-xl bg-white/10 backdrop-blur-sm flex items-center justify-center mb-3 border ${collection.borderColor}/30`}>
                          <IconComponent className={`h-6 w-6 ${collection.textColor}`} />
                        </div>
                        <h2 className="text-3xl font-bold text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
                          {collection.name}
                        </h2>
                        <p className={`text-sm ${collection.textColor} italic`}>{collection.tagline}</p>
                      </div>
                      <Badge className={`bg-white/10 ${collection.textColor} border-white/20`}>
                        {collection.ageTarget}
                      </Badge>
                    </div>

                    {/* Image */}
                    <div className="relative h-48 rounded-2xl overflow-hidden mb-6 group">
                      <img 
                        src={collection.image} 
                        alt={collection.name}
                        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                      <div className="absolute bottom-4 left-4">
                        <p className="text-white font-semibold">{collection.heroProduct}</p>
                        <p className={`${collection.textColor} font-bold text-xl`}>{collection.price}</p>
                      </div>
                    </div>

                    {/* Description */}
                    <p className="text-white/70 text-sm mb-4 min-h-[60px]">
                      {collection.description}
                    </p>

                    {/* Key Ingredient */}
                    <div className={`flex items-center gap-2 p-3 rounded-xl bg-white/5 border ${collection.borderColor}/20 mb-4`}>
                      <Shield className={`h-4 w-4 ${collection.textColor}`} />
                      <span className="text-white/80 text-sm">Key: </span>
                      <span className={`${collection.textColor} font-semibold text-sm`}>{collection.keyIngredient}</span>
                    </div>

                    {/* Badges */}
                    <div className="flex flex-wrap gap-2 mb-6">
                      {collection.badges.map((badge, i) => (
                        <Badge key={i} variant="outline" className={`${collection.textColor} border-white/20 text-xs`}>
                          {badge}
                        </Badge>
                      ))}
                    </div>

                    {/* Founder Attribution */}
                    <div className="flex items-center gap-3 mb-6 p-3 bg-white/5 rounded-xl">
                      <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">
                        <Star className={`h-5 w-5 ${collection.textColor}`} />
                      </div>
                      <div>
                        <p className="text-white/60 text-xs">Created for</p>
                        <p className="text-white text-sm font-medium">{collection.founders}</p>
                      </div>
                    </div>

                    {/* CTA */}
                    <Link to={collection.route}>
                      <Button 
                        className={`w-full py-6 text-base font-semibold rounded-xl transition-all ${
                          collection.id === 'oroe' 
                            ? 'bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0A0A0A] hover:from-[#F4D03F] hover:to-[#D4AF37]'
                            : collection.id === 'lavela'
                            ? 'bg-gradient-to-r from-[#0D4D4D] to-[#1A8B8B] text-white hover:from-[#1A8B8B] hover:to-[#0D4D4D]'
                            : 'bg-gradient-to-r from-[#D4AF37] to-[#F8A5B8] text-white hover:from-[#F8A5B8] hover:to-[#D4AF37]'
                        }`}
                        data-testid={`shop-${collection.id}-btn`}
                      >
                        Shop {collection.name}
                        <ArrowRight className="ml-2 h-5 w-5" />
                      </Button>
                    </Link>
                  </div>
                </motion.div>
              );
            })}
          </div>
          )}
        </div>
      </section>

      {/* Family Story Section */}
      <section className="py-16 px-4 bg-gradient-to-br from-[#2D2A2E] to-[#1a1819]">
        <div className="max-w-4xl mx-auto text-center">
          <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] border-[#D4AF37]/30 mb-6">
            <Sparkles className="h-3 w-3 mr-1" />
            OUR STORY
          </Badge>
          
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>
            A Family Committed to <span className="text-[#D4AF37]">Every Generation</span>
          </h2>
          
          <p className="text-lg text-white/70 mb-8 leading-relaxed">
            What started as a passion project by Tejinder Sandhu and Pawandeep Kaur evolved into a family mission. 
            When our sons—Gurnaman (18) and Anmol (15)—needed skincare that actually worked for their age, 
            we realized there was a gap in the market. Three brands emerged, each inspired by a family member's 
            unique skin journey.
          </p>
          
          <div className="grid md:grid-cols-3 gap-6 mt-12">
            <div className="p-6 bg-white/5 rounded-2xl border border-[#D4AF37]/20">
              <p className="text-4xl font-bold text-[#D4AF37]">100%</p>
              <p className="text-white/60 text-sm mt-2">Canadian Formulated</p>
            </div>
            <div className="p-6 bg-white/5 rounded-2xl border border-[#D4AF37]/20">
              <p className="text-4xl font-bold text-[#D4AF37]">3</p>
              <p className="text-white/60 text-sm mt-2">Generational Collections</p>
            </div>
            <div className="p-6 bg-white/5 rounded-2xl border border-[#D4AF37]/20">
              <p className="text-4xl font-bold text-[#D4AF37]">8-65+</p>
              <p className="text-white/60 text-sm mt-2">Age Range Covered</p>
            </div>
          </div>
          
          <Link to="/Bio-Age-Repair-Scan">
            <Button className="mt-10 bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#0A0A0A] font-bold py-6 px-10 text-lg hover:from-[#F4D03F] hover:to-[#D4AF37]">
              Find Your Perfect Collection
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Comparison Quick Link */}
      <section className="py-12 px-4 bg-[#FAF8F5]">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-[#5A5A5A] mb-4">Not sure which collection is right for you?</p>
          <Link to="/compare" className="text-[#D4AF37] font-semibold hover:underline inline-flex items-center gap-2">
            View Full Comparison Table <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  );
};

export default ShopPage;
