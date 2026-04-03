import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import axios from "axios";
import { 
  Sparkles, Trophy, Gift, DollarSign, Package, Shield, 
  Beaker, MapPin, Heart, ChevronDown, ArrowRight, Loader2, Eye
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// API URL
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    return window.location.origin;
  }
  return window.location.origin;
};
const API = `${getBackendUrl()}/api`;

const InfluencerLandingPage = () => {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isPreview, setIsPreview] = useState(false);

  useEffect(() => {
    // Check for preview data in sessionStorage first
    const previewData = sessionStorage.getItem('preview_influencer_page');
    if (previewData) {
      try {
        const parsed = JSON.parse(previewData);
        // Check if preview is recent (within 5 minutes)
        if (parsed._isPreview && Date.now() - parsed._timestamp < 5 * 60 * 1000) {
          setContent(parsed);
          setIsPreview(true);
          setLoading(false);
          // Clear the preview data after use - use setTimeout to handle React StrictMode double-invocation
          setTimeout(() => {
            sessionStorage.removeItem('preview_influencer_page');
          }, 100);
          return;
        }
      } catch (e) {
        console.error('Invalid preview data:', e);
      }
      // Clear invalid/expired preview data
      sessionStorage.removeItem('preview_influencer_page');
    }

    // Fetch live content from API
    axios.get(`${API}/influencer-page`)
      .then(res => setContent(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5]">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  const hero = content?.hero || {};
  const about = content?.about || {};
  const benefits = content?.benefits || {};
  const products = content?.featured_products || [];
  const cta = content?.cta || {};
  const programInfo = content?.program_info || {};

  // SEO Schema for Partner Program
  const partnerProgramSchema = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "ReRoots Influencer Partner Program",
    "description": "Join the ReRoots Influencer Partner Program. Earn commissions promoting premium Canadian PDRN biotech skincare. Apply today!",
    "url": "https://reroots.ca/influencer",
    "mainEntity": {
      "@type": "Organization",
      "name": "ReRoots Skincare",
      "description": "Premium Canadian PDRN Biotech Skincare"
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF8F5]">
      {/* Preview Banner */}
      {isPreview && (
        <div className="fixed top-0 left-0 right-0 z-[100] bg-gradient-to-r from-amber-500 to-orange-500 text-white py-2 px-4 text-center shadow-lg" data-testid="preview-banner">
          <p className="text-sm font-medium flex items-center justify-center gap-2">
            <Eye className="h-4 w-4" />
            <span>Preview Mode — Changes not saved yet</span>
            <button 
              onClick={() => window.close()}
              className="ml-4 px-3 py-1 bg-white/20 hover:bg-white/30 rounded text-xs font-semibold transition-colors"
            >
              Close Preview
            </button>
          </p>
        </div>
      )}
      {/* SEO Meta Tags */}
      <Helmet>
        <title>Join ReRoots Influencer Program | Earn Commissions | Canadian Skincare Partner</title>
        <meta name="description" content="Become a ReRoots Partner! Earn 10% commission on every sale. Give your audience 50% OFF premium PDRN biotech skincare. Join our influencer program today - Made in Canada." />
        <meta name="keywords" content="ReRoots influencer program, skincare affiliate, beauty influencer, PDRN skincare partner, Canadian skincare brand, influencer commission, beauty brand partnership" />
        
        {/* Open Graph */}
        <meta property="og:title" content="Join ReRoots Influencer Partner Program" />
        <meta property="og:description" content="Earn commissions promoting premium Canadian PDRN biotech skincare. Give your audience 50% OFF!" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://reroots.ca/influencer" />
        
        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="ReRoots Influencer Program - Earn Commissions" />
        <meta name="twitter:description" content="Partner with ReRoots and earn 10% on every sale. Premium Canadian PDRN skincare." />
        
        {/* Canonical URL */}
        <link rel="canonical" href="https://reroots.ca/influencer" />
        
        {/* Schema.org JSON-LD */}
        <script type="application/ld+json">
          {JSON.stringify(partnerProgramSchema)}
        </script>
      </Helmet>

      {/* Custom Header for Influencer Page */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-gradient-to-r from-[#2D2A2E] to-[#1a1819] shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          {/* Logo - Same as main website */}
          <Link to="/" className="flex items-center gap-2">
            <div className="rounded-lg p-2" style={{ backgroundColor: 'rgba(255, 255, 255, 0.9)' }}>
              <img 
                src="https://customer-assets.emergentagent.com/job_a381cf1d-579d-4c54-9ee9-c2aab86c5628/artifacts/2n6enhsj_1769103145313.png" 
                alt="ReRoots Beauty Enhancer" 
                className="h-12 w-auto object-contain"
                style={{ mixBlendMode: 'multiply' }}
              />
            </div>
          </Link>
          
          {/* CTA Buttons */}
          <div className="flex items-center gap-4">
            <Link to="/partner-login" className="text-white/70 hover:text-[#D4AF37] text-sm transition-colors hidden sm:block">
              Partner Login
            </Link>
            <Link to="/become-partner">
              <button className="bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] px-6 sm:px-8 py-2.5 rounded-full font-bold shadow-lg hover:shadow-xl transition-all hover:scale-105 flex items-center gap-2 text-sm">
                <Sparkles className="h-4 w-4" />
                Join Now
              </button>
            </Link>
          </div>
        </div>
      </header>

      {/* Spacer for fixed header */}
      <div className="h-20"></div>

      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-[#2D2A2E] via-[#1a1819] to-[#2D2A2E] py-20 overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(212,175,55,0.5) 1px, transparent 0)', backgroundSize: '30px 30px'}}></div>
        </div>
        
        <div className="max-w-6xl mx-auto px-6 relative z-10">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Hero Image */}
            <div className="relative flex justify-center order-2 md:order-1">
              <div className="relative">
                <img 
                  src={hero.image || "https://files.catbox.moe/jdjokm.jpg"}
                  alt="ReRoots Products"
                  className="w-80 h-80 object-cover rounded-2xl shadow-2xl border-2 border-[#D4AF37]/30"
                />
                <div className="absolute -top-4 -right-4 bg-gradient-to-br from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] px-4 py-3 rounded-xl shadow-lg transform rotate-12">
                  <p className="text-xs font-bold uppercase tracking-wide">Earn Up To</p>
                  <p className="text-2xl font-black">{programInfo.commission_rate || 15}%</p>
                </div>
              </div>
            </div>
            
            {/* Hero Content */}
            <div className="text-center md:text-left order-1 md:order-2">
              <div className="inline-flex items-center gap-2 bg-[#D4AF37]/20 px-4 py-1.5 rounded-full mb-6">
                <Sparkles className="h-4 w-4 text-[#D4AF37]" />
                <span className="text-sm text-[#D4AF37] font-medium tracking-wide">
                  {hero.badge_text || "GOLD PARTNER PROGRAM"}
                </span>
              </div>
              
              <h1 className="font-display text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
                {hero.title || "Join the ReRoots Family"}
              </h1>
              
              <p className="text-xl text-[#F8A5B8] font-medium mb-4">
                {hero.subtitle || "Partner with Canada's Premier Medical-Grade Skincare Brand"}
              </p>
              
              <p className="text-lg text-gray-300 mb-8">
                {hero.description || "Become an influencer partner and earn while sharing science-backed skincare with your audience."}
              </p>
              
              <div className="flex flex-wrap gap-4 mb-8 justify-center md:justify-start">
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full">
                  <DollarSign className="h-4 w-4 text-[#D4AF37]" />
                  <span className="text-white text-sm font-medium">{programInfo.commission_rate || 15}% Commission</span>
                </div>
                <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full">
                  <Gift className="h-4 w-4 text-[#F8A5B8]" />
                  <span className="text-white text-sm font-medium">{programInfo.customer_discount || 20}% For Your Audience</span>
                </div>
              </div>
              
              <Link to="/become-partner">
                <Button className="w-full md:w-auto px-12 py-6 text-lg font-bold bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] hover:from-[#F4D03F] hover:via-[#D4AF37] hover:to-[#F4D03F] shadow-lg shadow-[#D4AF37]/30 transition-all hover:scale-105">
                  Apply for Gold Status <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
        
        {/* Scroll indicator */}
        <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 animate-bounce">
          <ChevronDown className="h-8 w-8 text-[#D4AF37]/50" />
        </div>
      </section>

      {/* About Section */}
      <section className="py-20 bg-white">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-4">
              {about.title || "About ReRoots"}
            </h2>
            <p className="text-lg text-[#5A5A5A] max-w-3xl mx-auto">
              {about.description || "ReRoots is a Canadian skincare brand specializing in medical-grade formulations powered by PDRN technology. Our products are developed by dermatologists and backed by clinical research to deliver real results."}
            </p>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {(about.highlights || [
              {icon: "beaker", text: "PDRN Science Technology"},
              {icon: "maple-leaf", text: "Formulated in Canada"},
              {icon: "shield", text: "Medical-Grade Quality"},
              {icon: "heart", text: "Cruelty-Free & Vegan"}
            ]).map((item, idx) => (
              <div key={idx} className="text-center p-6 bg-[#FAF8F5] rounded-2xl hover:shadow-lg transition-shadow">
                <div className="w-14 h-14 bg-gradient-to-br from-[#F8A5B8]/20 to-[#D4AF37]/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  {item.icon === 'beaker' && <Beaker className="h-7 w-7 text-[#F8A5B8]" />}
                  {item.icon === 'maple-leaf' && <MapPin className="h-7 w-7 text-red-500" />}
                  {item.icon === 'shield' && <Shield className="h-7 w-7 text-[#D4AF37]" />}
                  {item.icon === 'heart' && <Heart className="h-7 w-7 text-[#F8A5B8]" />}
                </div>
                <p className="font-medium text-[#2D2A2E]">{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Products Section */}
      {products.length > 0 && (
        <section className="py-20 bg-gradient-to-b from-[#FAF8F5] to-white">
          <div className="max-w-6xl mx-auto px-6">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 bg-[#F8A5B8]/10 px-4 py-1.5 rounded-full mb-4">
                <Package className="h-4 w-4 text-[#F8A5B8]" />
                <span className="text-sm text-[#F8A5B8] font-medium">OUR COLLECTION</span>
              </div>
              <h2 className="font-display text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-4">
                {content?.products?.title || "Our Featured Products"}
              </h2>
              <p className="text-[#5A5A5A]">
                Share these premium skincare products with your audience
              </p>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              {products.map((product, idx) => (
                <Card key={idx} className="group overflow-hidden hover:shadow-xl transition-all duration-300 border-0 bg-white">
                  <div className="relative aspect-square overflow-hidden">
                    <img 
                      src={product.images?.[0] || product.image || "https://via.placeholder.com/300"} 
                      alt={product.name}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                    />
                    {product.sale_price && (
                      <div className="absolute top-2 left-2 bg-[#F8A5B8] text-white text-xs font-bold px-2 py-1 rounded">
                        SALE
                      </div>
                    )}
                  </div>
                  <CardContent className="p-4">
                    <h3 className="font-medium text-[#2D2A2E] text-sm mb-1 line-clamp-2">{product.name}</h3>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#D4AF37]">
                        ${product.sale_price || product.price}
                      </span>
                      {product.sale_price && (
                        <span className="text-xs text-gray-400 line-through">${product.price}</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            
            {/* View All Products button - hidden for now, can be activated later
            <div className="text-center mt-8">
              <Link to="/shop">
                <Button variant="outline" className="border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37] hover:text-[#2D2A2E]">
                  View All Products <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
            */}
          </div>
        </section>
      )}

      {/* Benefits Section */}
      <section className="py-20 bg-gradient-to-br from-[#2D2A2E] to-[#1a1819]">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 bg-[#D4AF37]/20 px-4 py-1.5 rounded-full mb-4">
              <Trophy className="h-4 w-4 text-[#D4AF37]" />
              <span className="text-sm text-[#D4AF37] font-medium">PARTNER PERKS</span>
            </div>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-white mb-4">
              {benefits.title || "Partner Benefits"}
            </h2>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {(benefits.items || [
              {title: "High Commission", description: "Earn up to 15% commission on every sale", icon: "dollar-sign"},
              {title: "Exclusive Discounts", description: "Give your audience 20% off with your unique code", icon: "gift"},
              {title: "Free Products", description: "Receive complimentary products to try and review", icon: "package"},
              {title: "Monthly Bonuses", description: "Top performers earn up to $500 monthly bonus", icon: "trophy"}
            ]).map((item, idx) => (
              <div key={idx} className="p-6 bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 hover:border-[#D4AF37]/50 transition-all group">
                <div className="w-12 h-12 bg-gradient-to-br from-[#D4AF37] to-[#F4D03F] rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  {item.icon === 'dollar-sign' && <DollarSign className="h-6 w-6 text-[#2D2A2E]" />}
                  {item.icon === 'gift' && <Gift className="h-6 w-6 text-[#2D2A2E]" />}
                  {item.icon === 'package' && <Package className="h-6 w-6 text-[#2D2A2E]" />}
                  {item.icon === 'trophy' && <Trophy className="h-6 w-6 text-[#2D2A2E]" />}
                </div>
                <h3 className="text-lg font-bold text-white mb-2">{item.title}</h3>
                <p className="text-gray-400 text-sm">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-[#FAF8F5]">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-4">
            {cta.title || "Ready to Join?"}
          </h2>
          <p className="text-lg text-[#5A5A5A] mb-8">
            {cta.description || "Apply now and start your journey as a ReRoots Gold Partner"}
          </p>
          
          <Link to="/become-partner">
            <Button className="px-12 py-6 text-lg font-bold bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] hover:from-[#F4D03F] hover:via-[#D4AF37] hover:to-[#F4D03F] shadow-lg shadow-[#D4AF37]/30 transition-all hover:scale-105">
              <Sparkles className="h-5 w-5 mr-2" />
              {cta.button_text || "Apply Now"}
            </Button>
          </Link>
        </div>
      </section>

      {/* Mobile CTA */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 p-4 bg-white border-t shadow-lg">
        <Link to="/become-partner">
          <Button className="w-full py-4 text-lg font-bold bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E]">
            <Sparkles className="h-5 w-5 mr-2" />
            Apply Now
          </Button>
        </Link>
      </div>
    </div>
  );
};

export default InfluencerLandingPage;
