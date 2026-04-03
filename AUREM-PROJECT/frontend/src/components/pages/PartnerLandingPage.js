import React, { useState, useEffect, lazy, Suspense } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { 
  XCircle,
  Sparkles,
  Gift,
  Instagram,
  Bell,
  Loader2,
  Smartphone,
  X,
  Apple
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useCart } from "../../contexts";
import { optimizeImageUrl } from "@/lib/imageOptimization";

// Lazy load framer-motion
const MotionDiv = lazy(() => import('framer-motion').then(mod => ({ default: mod.motion.div })));
const AnimatePresence = lazy(() => import('framer-motion').then(mod => ({ default: mod.AnimatePresence })));

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const PartnerLandingPage = () => {
  const { partnerCode } = useParams();
  const { addToCart } = useCart();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAppPopup, setShowAppPopup] = useState(false);

  useEffect(() => {
    axios.get(`${API}/partner/${partnerCode}`)
      .then(res => {
        setData(res.data);
        // Store partner code in session for checkout
        sessionStorage.setItem('partner_code', res.data.influencer.partner_code);
        sessionStorage.setItem('partner_discount', res.data.influencer.discount);
        sessionStorage.setItem('partner_name', res.data.influencer.name);
        
        // Show app download popup after 3 seconds (only once per session)
        const hasSeenAppPopup = sessionStorage.getItem('seen_app_popup');
        if (!hasSeenAppPopup) {
          setTimeout(() => {
            setShowAppPopup(true);
            sessionStorage.setItem('seen_app_popup', 'true');
          }, 3000);
        }
      })
      .catch(err => {
        setError(err.response?.data?.detail || "Partner not found");
      })
      .finally(() => setLoading(false));
  }, [partnerCode]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5]">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF8F5] p-6">
        <div className="text-center">
          <XCircle className="h-16 w-16 text-red-400 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-[#2D2A2E] mb-2">Partner Not Found</h1>
          <p className="text-[#5A5A5A] mb-6">{error}</p>
          <Link to="/"><Button className="btn-primary">Visit Store</Button></Link>
        </div>
      </div>
    );
  }

  const { influencer, landing_page, products } = data;
  const discountText = `${influencer.discount}%`;

  return (
    <div className="min-h-screen bg-[#FAF8F5]">
      {/* Hero Section with integrated discount */}
      <section className="relative bg-gradient-to-br from-[#2D2A2E] to-[#1a1819] pt-4 pb-12 sm:py-20">
        {/* Floating Discount Badge - Top Right */}
        {landing_page.show_banner && (
          <div className="absolute top-4 right-4 sm:top-8 sm:right-8 z-10">
            <div className="bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] px-4 py-2 rounded-xl shadow-lg">
              <p className="text-xs font-bold uppercase tracking-wide">Your Code</p>
              <p className="text-lg sm:text-xl font-black">{influencer.partner_code}</p>
            </div>
            {/* Partner Login Link */}
            <Link 
              to="/partner-login" 
              className="block mt-2 text-center text-xs text-white/60 hover:text-[#D4AF37] transition-colors"
            >
              Partner? Login here →
            </Link>
          </div>
        )}
        
        <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-8 sm:pt-0">
          <div className="grid md:grid-cols-2 gap-8 md:gap-12 items-center">
            <div>
              {/* Discount Highlight Banner */}
              {landing_page.show_banner && (
                <div className="inline-flex items-center gap-2 bg-gradient-to-r from-[#D4AF37]/20 to-[#F4D03F]/10 border border-[#D4AF37]/30 px-4 py-2 rounded-full mb-4">
                  <Gift className="h-4 w-4 text-[#D4AF37]" />
                  <span className="text-sm text-[#D4AF37] font-bold">{discountText} OFF Applied!</span>
                </div>
              )}
              
              <div className="inline-flex items-center gap-2 bg-[#F8A5B8]/20 px-4 py-1.5 rounded-full mb-4">
                <Sparkles className="h-4 w-4 text-[#F8A5B8]" />
                <span className="text-sm text-[#F8A5B8] font-medium">EXCLUSIVE PARTNER ACCESS</span>
              </div>
              
              <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
                ReRoots x {influencer.name}
              </h1>
              <p className="text-lg sm:text-xl text-gray-300 mb-6">
                {landing_page.subheadline.replace('{discount}', influencer.discount).replace('{influencer_name}', influencer.name)}
              </p>
              <div className="flex flex-wrap gap-4">
                <Link to="/shop">
                  <Button className="bg-gradient-to-r from-[#D4AF37] via-[#F4D03F] to-[#D4AF37] text-[#2D2A2E] font-bold px-6 sm:px-8 py-5 sm:py-6 text-base sm:text-lg">
                    🌞 {landing_page.cta}
                  </Button>
                </Link>
                <a href={influencer.profile_url} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" className="border-white text-white hover:bg-white/10 px-4 sm:px-6 py-5 sm:py-6">
                    <Instagram className="h-5 w-5 mr-2" />
                    Follow @{influencer.social_handle?.replace('@', '')}
                  </Button>
                </a>
              </div>
            </div>
            {landing_page.show_photo && (
              <div className="relative">
                <div className="aspect-square bg-gradient-to-br from-[#F8A5B8]/20 to-[#D4AF37]/20 rounded-3xl overflow-hidden flex items-center justify-center">
                  <img 
                    src={optimizeImageUrl("https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/a4671ebm_1767158945864.jpg", 600, 80)} 
                    alt="ReRoots AURA-GEN Serum"
                    className="w-full h-full object-cover"
                    loading="eager"
                    fetchPriority="high"
                  />
                </div>
                <div className="absolute -bottom-4 -right-4 bg-[#D4AF37] text-[#2D2A2E] px-6 py-3 rounded-full font-bold text-xl shadow-lg">
                  {discountText} OFF
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Featured Products */}
      {products && products.length > 0 && (
        <section className="py-16">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="font-display text-3xl font-bold text-[#2D2A2E] text-center mb-12">
              Shop {influencer.name}&apos;s Picks
            </h2>
            <div className="grid md:grid-cols-4 gap-6">
              {products.map(product => (
                <Card key={product.id} className="group border-0 shadow-lg hover:shadow-xl transition-all">
                  <div className="aspect-square overflow-hidden rounded-t-lg">
                    <img 
                      src={product.images?.[0] || "https://via.placeholder.com/300"} 
                      alt={product.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                  </div>
                  <CardContent className="p-4">
                    <h3 className="font-semibold text-[#2D2A2E] mb-2 truncate">{product.name}</h3>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-[#888] line-through text-sm">${product.price}</span>
                      <span className="text-[#D4AF37] font-bold">${(product.price * (1 - influencer.discount/100)).toFixed(2)}</span>
                    </div>
                    <Button 
                      className="w-full bg-gradient-to-r from-[#D4AF37] to-[#F4D03F] text-[#2D2A2E] font-semibold"
                      onClick={() => {
                        addToCart(product.id);
                        toast.success("Added to cart with partner discount!");
                      }}
                    >
                      Add to Cart
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Download App Popup for Audience */}
      <Suspense fallback={null}>
        <AnimatePresence>
          {showAppPopup && (
            <MotionDiv
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
              onClick={() => setShowAppPopup(false)}
            >
              {/* Backdrop */}
              <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
              
              {/* Popup */}
              <MotionDiv
                initial={{ opacity: 0, y: 100, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 100, scale: 0.9 }}
                transition={{ type: "spring", damping: 25, stiffness: 300 }}
                className="relative w-full max-w-md rounded-t-3xl sm:rounded-3xl bg-white shadow-2xl overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Close button */}
                <button
                  onClick={() => setShowAppPopup(false)}
                  className="absolute top-4 right-4 w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors z-10"
                >
                  <X className="h-4 w-4 text-gray-600" />
                </button>
                
                {/* Header with gradient */}
                <div className="bg-gradient-to-br from-[#2D2A2E] to-[#1a1819] px-6 py-8 text-center">
                  <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Smartphone className="w-8 h-8 text-[#D4AF37]" />
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-2">Get the ReRoots App</h3>
                  <p className="text-white/70 text-sm">
                    Exclusive deals, early access & {influencer.discount}% off with {influencer.name}&apos;s code
                  </p>
                </div>
                
                {/* Content */}
                <div className="px-6 py-6 space-y-4">
                  {/* Benefits */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#D4AF37]/10 flex items-center justify-center">
                        <Gift className="w-4 h-4 text-[#D4AF37]" />
                      </div>
                      <span className="text-sm text-gray-700">Your {influencer.discount}% discount auto-applied</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#F8A5B8]/10 flex items-center justify-center">
                        <Bell className="w-4 h-4 text-[#F8A5B8]" />
                      </div>
                      <span className="text-sm text-gray-700">Get notified for flash sales & drops</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-50 flex items-center justify-center">
                        <Sparkles className="w-4 h-4 text-green-600" />
                      </div>
                      <span className="text-sm text-gray-700">Earn rewards with every purchase</span>
                    </div>
                  </div>
                  
                  {/* App Store Buttons */}
                  <div className="flex gap-3 pt-2">
                    <a 
                      href="#" 
                      className="flex-1 flex items-center justify-center gap-2 bg-black text-white py-3 px-4 rounded-xl hover:bg-gray-800 transition-colors"
                      onClick={(e) => {
                        e.preventDefault();
                        toast.info("App Store coming soon! 🚀");
                      }}
                    >
                      <Apple className="w-5 h-5" />
                      <div className="text-left">
                        <p className="text-[10px] opacity-70">Download on</p>
                        <p className="text-sm font-semibold -mt-0.5">App Store</p>
                      </div>
                    </a>
                    <a 
                      href="#" 
                      className="flex-1 flex items-center justify-center gap-2 bg-black text-white py-3 px-4 rounded-xl hover:bg-gray-800 transition-colors"
                      onClick={(e) => {
                        e.preventDefault();
                        toast.info("Google Play coming soon! 🚀");
                      }}
                    >
                      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M3.609 1.814L13.792 12 3.61 22.186a.996.996 0 01-.61-.92V2.734a1 1 0 01.609-.92zm10.89 10.893l2.302 2.302-10.937 6.333 8.635-8.635zm3.199-3.198l2.807 1.626a1 1 0 010 1.73l-2.808 1.626L15.206 12l2.492-2.491zM5.864 2.658L16.8 8.99l-2.302 2.302-8.634-8.634z"/>
                      </svg>
                      <div className="text-left">
                        <p className="text-[10px] opacity-70">Get it on</p>
                        <p className="text-sm font-semibold -mt-0.5">Google Play</p>
                      </div>
                    </a>
                  </div>
                  
                  {/* Continue Shopping Link */}
                  <button
                    onClick={() => setShowAppPopup(false)}
                    className="w-full text-center text-sm text-gray-500 hover:text-[#D4AF37] py-2"
                  >
                    Continue shopping on web →
                  </button>
                </div>
              </MotionDiv>
            </MotionDiv>
          )}
        </AnimatePresence>
      </Suspense>
    </div>
  );
};

export default PartnerLandingPage;
