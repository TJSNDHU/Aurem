import React, { useState, useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  ChevronLeft, 
  Shield, 
  Check, 
  Leaf, 
  Heart,
  ShoppingBag,
  Minus,
  Plus,
  Star,
  Play,
  Info,
  Sparkles
} from "lucide-react";
import { CartContext } from "@/contexts";
import { toast } from "sonner";
import "../styles/lavela-design-system.css";

// ORO ROSA Product Page - The Bouncy Pink Gel Experience
const OroRosaPage = () => {
  const navigate = useNavigate();
  const [quantity, setQuantity] = useState(1);
  const [activeTab, setActiveTab] = useState('benefits');
  const [showVideo, setShowVideo] = useState(false);
  const [addingToCart, setAddingToCart] = useState(false);
  
  // Get cart context
  const cartContext = useContext(CartContext);
  const addToCart = cartContext?.addToCart;
  
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

  // Product info
  const product = {
    id: "69ab89acdf93caa6c1cda7c8", // ORO ROSA product ID from database
    name: "ORO ROSA",
    subtitle: "Rose Gold Bio-Regenerative Serum",
    price: 49,
    currency: "CAD",
    size: "30ml",
    rating: 4.9,
    reviews: 2847,
  };

  // Handle Add to Cart
  const handleAddToCart = async () => {
    if (!addToCart) {
      toast.error("Cart not available");
      return;
    }
    setAddingToCart(true);
    try {
      await addToCart(product.id, quantity);
    } catch (error) {
      console.error("Failed to add to cart:", error);
    }
    setAddingToCart(false);
  };

  // Handle Buy Now (add to cart and go to checkout)
  const handleBuyNow = async () => {
    if (!addToCart) {
      toast.error("Cart not available");
      return;
    }
    setAddingToCart(true);
    try {
      await addToCart(product.id, quantity);
      navigate('/checkout');
    } catch (error) {
      console.error("Failed to process:", error);
      toast.error("Failed to process. Please try again.");
    }
    setAddingToCart(false);
  };

  // Simplified science for teens
  const scienceExplained = [
    {
      icon: "🧬",
      name: "PDRN",
      nickname: "The Healer",
      emoji: "🩹➡️✨",
      explanation: "Think of it as a repair kit for your skin! It fixes tiny damages and helps your skin bounce back faster.",
      forTeens: "Perfect for: Acne scars, uneven texture"
    },
    {
      icon: "💎",
      name: "Glutathione",
      nickname: "The Glow Molecule",
      emoji: "😴➡️✨",
      explanation: "The ultimate brightening ingredient! It helps fade dark spots and gives you that 'I just had 10 hours of sleep' glow.",
      forTeens: "Perfect for: Dull skin, dark spots"
    },
    {
      icon: "💧",
      name: "Hyaluronic Acid",
      nickname: "The Hydrator",
      emoji: "🏜️➡️💦",
      explanation: "Like a tall glass of water for your face! It holds 1000x its weight in water to keep skin plump and bouncy.",
      forTeens: "Perfect for: Dry or dehydrated skin"
    },
    {
      icon: "🌸",
      name: "Vitamin B12",
      nickname: "The Pink Power",
      emoji: "😫➡️💪",
      explanation: "That's what makes our gel PINK! It energizes your skin cells and calms redness.",
      forTeens: "Perfect for: Tired, irritated skin"
    },
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
          
          {/* Cart - RIGHT */}
          <button className="relative p-2">
            <ShoppingBag className="w-5 h-5 text-[#2D2A2E]" />
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-[#D4A574] rounded-full text-[10px] text-white flex items-center justify-center">
              0
            </span>
          </button>
        </div>
      </nav>

      {/* Animated Ingredients Ticker - Subtle on white */}
      <div className="relative overflow-hidden py-1.5" style={{
        background: 'rgba(255, 255, 255, 0.95)',
        borderBottom: '1px solid rgba(212, 165, 116, 0.15)'
      }}>
        {/* Animated scrolling content */}
        <div className="flex animate-marquee whitespace-nowrap">
          {[...Array(3)].map((_, setIndex) => (
            <div key={setIndex} className="flex items-center gap-6 mx-6">
              <span className="flex items-center gap-1.5 text-[#0D4D4D]/70">
                <span className="text-xs">🧬</span>
                <span className="text-[10px] font-medium uppercase tracking-wide">PDRN</span>
                <span className="text-[9px] text-[#D4A574]">The Healer</span>
              </span>
              <span className="text-[#D4A574]/40 text-[8px]">✦</span>
              <span className="flex items-center gap-1.5 text-[#0D4D4D]/70">
                <span className="text-xs">💎</span>
                <span className="text-[10px] font-medium uppercase tracking-wide">Glutathione</span>
                <span className="text-[9px] text-[#D4A574]">Glow Molecule</span>
              </span>
              <span className="text-[#D4A574]/40 text-[8px]">✦</span>
              <span className="flex items-center gap-1.5 text-[#0D4D4D]/70">
                <span className="text-xs">💧</span>
                <span className="text-[10px] font-medium uppercase tracking-wide">Hyaluronic</span>
                <span className="text-[9px] text-[#D4A574]">Hydrator</span>
              </span>
              <span className="text-[#D4A574]/40 text-[8px]">✦</span>
              <span className="flex items-center gap-1.5 text-[#0D4D4D]/70">
                <span className="text-xs">🌸</span>
                <span className="text-[10px] font-medium uppercase tracking-wide">Vitamin B12</span>
                <span className="text-[9px] text-[#D4A574]">Pink Power</span>
              </span>
              <span className="text-[#D4A574]/40 text-[8px]">✦</span>
              <span className="flex items-center gap-1.5 text-[#0D4D4D]/70">
                <span className="text-xs">🌿</span>
                <span className="text-[10px] font-medium uppercase tracking-wide">Centella</span>
                <span className="text-[9px] text-[#D4A574]">Calming</span>
              </span>
              <span className="text-[#D4A574]/40 text-[8px]">✦</span>
              <span className="flex items-center gap-1.5 text-[#0D4D4D]/70">
                <span className="text-xs">✨</span>
                <span className="text-[10px] font-medium uppercase tracking-wide">Niacinamide</span>
                <span className="text-[9px] text-[#D4A574]">Refiner</span>
              </span>
              <span className="text-[#D4A574]/40 text-[8px]">✦</span>
            </div>
          ))}
        </div>
        
        {/* Gradient fade edges */}
        <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-white to-transparent z-10"></div>
        <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-white to-transparent z-10"></div>
      </div>

      {/* Product Hero */}
      <section className="pt-4 pb-8 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-8 items-start">
            {/* Product Image */}
            <div className="relative">
              <motion.div 
                className="sticky top-24"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6 }}
              >
                {/* Main Product Display */}
                <div className="relative aspect-square rounded-3xl overflow-hidden" style={{
                  background: 'linear-gradient(135deg, rgba(13, 77, 77, 0.3) 0%, rgba(232, 196, 184, 0.3) 100%)',
                  border: '1px solid rgba(230, 190, 138, 0.2)'
                }}>
                  {/* Glow Effect */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-48 h-48 rounded-full bg-[#E6BE8A]/20 blur-3xl lavela-glow-pulse"></div>
                  </div>
                  
                  {/* Product Visual */}
                  <div className="relative z-10 h-full flex flex-col items-center justify-center p-4">
                    <img 
                      src="/oro-rosa-product.png" 
                      alt="ORO ROSA Serum" 
                      className="max-h-80 w-auto object-contain"
                      loading="lazy"
                      decoding="async"
                    />
                    <p className="text-xs text-[#E8C4B8] mt-2">30ml / 1 fl oz</p>
                  </div>

                  {/* Video Play Button */}
                  <button 
                    onClick={() => setShowVideo(true)}
                    className="absolute bottom-4 right-4 flex items-center gap-2 px-4 py-2 rounded-full bg-white/90 backdrop-blur-sm text-sm font-medium text-[#2D2A2E] hover:bg-white transition-colors"
                  >
                    <Play className="w-4 h-4 text-[#E6BE8A]" />
                    Watch Gel Texture
                  </button>
                </div>

                {/* Thumbnail Strip */}
                <div className="flex gap-2 mt-4 justify-center">
                  {[1, 2, 3, 4].map((_, i) => (
                    <button 
                      key={i}
                      className={`w-16 h-16 rounded-xl ${i === 0 ? 'ring-2 ring-[#E6BE8A]' : 'opacity-60'} bg-gradient-to-br from-[#FADBD8] to-[#FDEDEC] flex items-center justify-center`}
                    >
                      <span className="text-xl">{['🧴', '💧', '✨', '📦'][i]}</span>
                    </button>
                  ))}
                </div>
              </motion.div>
            </div>

            {/* Product Info */}
            <div className="space-y-6">
              {/* Badges */}
              <div className="flex flex-wrap gap-2">
                <span className="lavela-safety-badge">
                  <Shield className="w-3 h-3 text-[#E6BE8A]" />
                  Pediatric-Safe
                </span>
                <span className="lavela-safety-badge">
                  <Check className="w-3 h-3 text-[#E6BE8A]" />
                  pH 5.0-5.3
                </span>
              </div>

              {/* Title */}
              <div>
                <p className="text-xs tracking-[0.2em] text-[#E6BE8A] uppercase mb-1">The Hero Product</p>
                <h1 className="lavela-heading text-4xl sm:text-5xl mb-2">
                  ORO <span className="lavela-shimmer-text">ROSA</span>
                </h1>
                <p className="text-lg text-[#E8C4B8]">{product.subtitle}</p>
              </div>

              {/* Rating */}
              <div className="flex items-center gap-3">
                <div className="flex gap-0.5">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="w-4 h-4 fill-[#E6BE8A] text-[#E6BE8A]" />
                  ))}
                </div>
                <span className="text-sm text-[#E8C4B8]">
                  {product.rating} ({product.reviews.toLocaleString()} reviews)
                </span>
              </div>

              {/* Price */}
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-bold lavela-shimmer-text">${product.price}</span>
                <span className="text-[#E8C4B8]">{product.currency}</span>
                <span className="text-sm text-[#E8C4B8] ml-2">/ {product.size}</span>
              </div>

              {/* Quick Benefits */}
              <div className="p-4 rounded-2xl" style={{
                background: 'rgba(13, 77, 77, 0.4)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(230, 190, 138, 0.2)'
              }}>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { emoji: "✨", text: "Glass Skin Glow" },
                    { emoji: "🩹", text: "Heals Blemishes" },
                    { emoji: "💧", text: "Deep Hydration" },
                    { emoji: "🌸", text: "Calms Redness" },
                  ].map((benefit, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-lg">{benefit.emoji}</span>
                      <span className="text-sm text-[#E8C4B8]">{benefit.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quantity & Add to Cart */}
              <div className="space-y-4">
                {/* Quantity Selector */}
                <div className="flex items-center gap-4">
                  <span className="text-sm text-[#E8C4B8]">Quantity:</span>
                  <div className="flex items-center gap-3 bg-[#0D4D4D]/50 rounded-full px-4 py-2">
                    <button 
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="w-8 h-8 rounded-full bg-white flex items-center justify-center hover:bg-[#E6BE8A] hover:text-white transition-colors"
                    >
                      <Minus className="w-4 h-4" />
                    </button>
                    <span className="w-8 text-center font-medium">{quantity}</span>
                    <button 
                      onClick={() => setQuantity(quantity + 1)}
                      className="w-8 h-8 rounded-full bg-white flex items-center justify-center hover:bg-[#E6BE8A] hover:text-white transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Add to Cart Button */}
                <button 
                  onClick={handleAddToCart}
                  disabled={addingToCart}
                  className="lavela-btn-shimmer w-full flex items-center justify-center gap-2 py-5 disabled:opacity-50"
                  data-testid="add-to-cart-btn"
                >
                  <ShoppingBag className="w-5 h-5" />
                  {addingToCart ? "Adding..." : `Add to Cart - $${(product.price * quantity).toFixed(2)}`}
                </button>

                {/* Express Checkout */}
                <div className="flex gap-2">
                  <button 
                    onClick={handleBuyNow}
                    disabled={addingToCart}
                    className="flex-1 py-3 rounded-full bg-black text-white text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                    data-testid="buy-now-btn"
                  >
                     {addingToCart ? "Processing..." : "Pay"}
                  </button>
                  <button 
                    onClick={handleBuyNow}
                    disabled={addingToCart}
                    className="flex-1 py-3 rounded-full bg-white border border-[#D5DBDB] text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                    data-testid="google-pay-btn"
                  >
                    <span className="text-[#4285F4]">G</span> Pay
                  </button>
                </div>
              </div>

              {/* Trust Badges */}
              <div className="flex flex-wrap gap-4 pt-4 border-t border-[#E6BE8A]/30">
                <div className="flex items-center gap-2 text-xs text-[#E8C4B8]">
                  <Check className="w-4 h-4 text-green-400" />
                  Free shipping over $50
                </div>
                <div className="flex items-center gap-2 text-xs text-[#E8C4B8]">
                  <Check className="w-4 h-4 text-green-400" />
                  30-day returns
                </div>
              </div>
              
              {/* Pediatric Safety Disclaimer */}
              <div className="mt-4 p-3 bg-[#0D4D4D]/30 border border-[#E6BE8A]/20 rounded-lg">
                <p className="text-[#E8C4B8]/80 text-xs leading-relaxed flex items-start gap-2">
                  <Shield className="w-4 h-4 text-[#E6BE8A] shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#E6BE8A]">Safety Note:</strong> Formulated for young skin barriers. 
                    We recommend a patch test for children under 10. Always use with daily SPF.
                  </span>
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* The 11 Divider */}
      <div className="lavela-divider-11 max-w-xl mx-auto"></div>

      {/* Interactive Science Section - Simplified for Teens */}
      <section className="py-12 px-4" style={{
        background: 'linear-gradient(180deg, rgba(13, 77, 77, 0.3) 0%, rgba(232, 196, 184, 0.2) 100%)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">The Science</p>
            <h2 className="lavela-heading text-2xl sm:text-3xl md:text-4xl mb-4">
              What's Inside <span className="lavela-shimmer-text">ORO ROSA</span>
            </h2>
            <p className="text-[#E8C4B8]">
              No confusing ingredient lists. Here's what actually matters:
            </p>
          </div>

          {/* Ingredient Cards */}
          <div className="grid sm:grid-cols-2 gap-4">
            {scienceExplained.map((item, i) => (
              <motion.div
                key={i}
                className="p-6 rounded-2xl hover:shadow-lg transition-shadow"
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
                  <span className="text-4xl">{item.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-[#E6BE8A]">{item.name}</h3>
                      <span className="text-xs px-2 py-0.5 bg-[#0D4D4D] rounded-full text-[#E6BE8A]">
                        {item.nickname}
                      </span>
                    </div>
                    
                    {/* Emoji Explanation */}
                    <p className="text-2xl my-2">{item.emoji}</p>
                    
                    <p className="text-sm text-[#E8C4B8] mb-3">
                      {item.explanation}
                    </p>
                    
                    <p className="text-xs text-[#E6BE8A] font-medium">
                      {item.forTeens}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Safety Callout */}
          <div className="mt-8 p-6 text-center rounded-2xl" style={{
            background: 'rgba(13, 77, 77, 0.4)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(230, 190, 138, 0.2)'
          }}>
            <div className="flex flex-wrap justify-center gap-6">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-[#E6BE8A]" />
                <span className="text-sm text-[#E8C4B8]">Pediatric Dermatologist Approved</span>
              </div>
              <div className="flex items-center gap-2">
                <Leaf className="w-5 h-5 text-[#E6BE8A]" />
                <span className="text-sm text-[#E8C4B8]">No Harsh Chemicals</span>
              </div>
              <div className="flex items-center gap-2">
                <Heart className="w-5 h-5 text-[#E6BE8A]" />
                <span className="text-sm text-[#E8C4B8]">Safe for Ages 8-16</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How to Use */}
      <section className="py-12 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Application</p>
          <h2 className="lavela-heading text-2xl sm:text-3xl md:text-4xl mb-12">
            How to Get Your <span className="lavela-shimmer-text">Glow</span>
          </h2>

          <div className="grid sm:grid-cols-3 gap-8">
            {[
              { step: "1", emoji: "🧴", title: "Pump", desc: "2-3 drops of the bouncy pink gel" },
              { step: "2", emoji: "🙌", title: "Warm", desc: "Rub between your palms to activate" },
              { step: "3", emoji: "✨", title: "Press", desc: "Gently press into clean skin" },
            ].map((item, i) => (
              <motion.div
                key={i}
                className="text-center"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.2 }}
              >
                <div className="relative inline-block mb-4">
                  <div className="w-20 h-20 rounded-full flex items-center justify-center text-4xl lavela-float" style={{ 
                    background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)',
                    animationDelay: `${i * 0.3}s` 
                  }}>
                    {item.emoji}
                  </div>
                  <span className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-[#E6BE8A] text-white text-sm font-bold flex items-center justify-center">
                    {item.step}
                  </span>
                </div>
                <h3 className="lavela-heading text-xl mb-2">{item.title}</h3>
                <p className="text-sm text-[#E8C4B8]">{item.desc}</p>
              </motion.div>
            ))}
          </div>

          <p className="mt-8 text-sm text-[#E8C4B8]">
            Use morning and night after cleansing for best results 🌅🌙
          </p>
        </div>
      </section>

      {/* Reviews Preview */}
      <section className="py-12 px-4" style={{
        background: 'linear-gradient(180deg, rgba(232, 196, 184, 0.2) 0%, rgba(13, 77, 77, 0.3) 100%)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Reviews</p>
            <h2 className="lavela-heading text-2xl sm:text-3xl">
              <span className="lavela-shimmer-text">{product.rating}</span> out of 5
            </h2>
            <p className="text-sm text-[#E8C4B8]">Based on {product.reviews.toLocaleString()} reviews</p>
          </div>

          {/* Sample Reviews */}
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { name: "Olivia, 13", text: "OMG the texture is SO satisfying! My skin looks like glass now ✨", rating: 5 },
              { name: "Ava, 15", text: "Finally something that doesn't make my acne worse. Actually helps!", rating: 5 },
            ].map((review, i) => (
              <div key={i} className="p-6 rounded-2xl" style={{
                background: 'rgba(13, 77, 77, 0.5)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(230, 190, 138, 0.2)'
              }}>
                <div className="flex gap-0.5 mb-2">
                  {[...Array(review.rating)].map((_, j) => (
                    <Star key={j} className="w-4 h-4 fill-[#E6BE8A] text-[#E6BE8A]" />
                  ))}
                </div>
                <p className="text-[#E8C4B8] mb-3">&quot;{review.text}&quot;</p>
                <p className="text-xs text-[#E6BE8A] font-medium">— {review.name}</p>
              </div>
            ))}
          </div>

          <div className="text-center mt-6">
            <button 
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              className="text-sm text-[#E6BE8A] font-medium hover:underline cursor-pointer"
            >
              Read all {product.reviews.toLocaleString()} reviews →
            </button>
          </div>
        </div>
      </section>

      {/* Sticky Add to Cart - Mobile */}
      <div className="fixed bottom-0 left-0 right-0 p-4 md:hidden z-40" style={{
        background: 'rgba(13, 77, 77, 0.95)',
        backdropFilter: 'blur(10px)',
        borderTop: '1px solid rgba(230, 190, 138, 0.3)'
      }}>
        <button 
          onClick={handleAddToCart}
          disabled={addingToCart}
          className="lavela-btn-shimmer w-full flex items-center justify-center gap-2 py-4 cursor-pointer disabled:opacity-50"
          data-testid="mobile-add-to-cart-btn"
        >
          <ShoppingBag className="w-5 h-5" />
          {addingToCart ? "Adding..." : `Add to Cart - $${product.price}`}
        </button>
      </div>

      {/* Bottom Padding for Mobile Sticky Bar */}
      <div className="h-24 md:hidden"></div>
    </div>
  );
};

export default OroRosaPage;
