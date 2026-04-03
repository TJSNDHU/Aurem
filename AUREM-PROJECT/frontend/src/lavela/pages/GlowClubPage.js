import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  ChevronLeft, 
  Sparkles, 
  Gift, 
  Star,
  Crown,
  Zap,
  Heart,
  Share2,
  CheckCircle
} from "lucide-react";
import "../styles/lavela-design-system.css";

// Glow Club - Loyalty Program for Gen Alpha/Z
const GlowClubPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  
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
  const [isJoined, setIsJoined] = useState(false);

  const handleJoin = (e) => {
    e.preventDefault();
    if (email) {
      setIsJoined(true);
    }
  };

  const benefits = [
    {
      icon: <Gift className="w-6 h-6" />,
      title: "Welcome Gift",
      desc: "Free mini ORO ROSA with your first order",
      points: null
    },
    {
      icon: <Star className="w-6 h-6" />,
      title: "Earn Points",
      desc: "1 point for every $1 spent",
      points: "1 pt/$1"
    },
    {
      icon: <Zap className="w-6 h-6" />,
      title: "Early Access",
      desc: "Be first to shop new launches",
      points: null
    },
    {
      icon: <Heart className="w-6 h-6" />,
      title: "Birthday Surprise",
      desc: "Special gift on your birthday",
      points: "Free"
    },
  ];

  const tiers = [
    {
      name: "Glow Starter",
      range: "0 - 499 pts",
      perks: ["1 pt per $1", "Birthday gift", "Early access to sales"],
      color: "from-[#FADBD8] to-[#F5B7B1]"
    },
    {
      name: "Glow Pro",
      range: "500 - 999 pts",
      perks: ["1.5 pts per $1", "Free shipping", "Exclusive discounts", "Monthly glow tips"],
      color: "from-[#E6BE8A] to-[#D4A574]"
    },
    {
      name: "Glow Queen",
      range: "1000+ pts",
      perks: ["2 pts per $1", "Free products", "VIP events", "First dibs on launches", "Personal skincare advisor"],
      color: "from-[#D4A574] to-[#C49B6A]"
    },
  ];

  const rewards = [
    { points: 100, reward: "$5 off", emoji: "🎁" },
    { points: 250, reward: "$15 off", emoji: "✨" },
    { points: 500, reward: "Free Mini Serum", emoji: "🧴" },
    { points: 1000, reward: "Full Size Product", emoji: "👑" },
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
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-[#E6BE8A] text-sm mb-6" style={{
              background: 'rgba(230, 190, 138, 0.15)',
              border: '1px solid rgba(230, 190, 138, 0.3)'
            }}>
              <Crown className="w-4 h-4" />
              Exclusive Membership
            </div>
            
            <h1 className="lavela-heading text-4xl sm:text-5xl md:text-6xl mb-4">
              The <span className="lavela-shimmer-text">Glow Club</span>
            </h1>
            
            <div className="lavela-divider-11 my-6"></div>
            
            <p className="text-lg text-[#E8C4B8] max-w-2xl mx-auto mb-8">
              Join 10,000+ members earning points, unlocking rewards, and getting exclusive access 
              to the best teen skincare. It&apos;s free to join!
            </p>

            {/* Join Form or Success */}
            {!isJoined ? (
              <form onSubmit={handleJoin} className="max-w-md mx-auto">
                <div className="flex flex-col sm:flex-row gap-3">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    className="flex-1 px-6 py-4 rounded-full text-[#2D2A2E] focus:outline-none text-center sm:text-left"
                    style={{
                      background: 'rgba(255, 255, 255, 0.9)',
                      border: '1px solid rgba(230, 190, 138, 0.3)'
                    }}
                    required
                    data-testid="glow-club-email"
                  />
                  <button 
                    type="submit"
                    className="lavela-btn-shimmer whitespace-nowrap"
                    data-testid="join-glow-club-submit"
                  >
                    <Sparkles className="w-4 h-4 inline mr-2" />
                    Join Free
                  </button>
                </div>
              </form>
            ) : (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="p-8 max-w-md mx-auto rounded-2xl"
                style={{
                  background: 'rgba(13, 77, 77, 0.5)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(230, 190, 138, 0.3)'
                }}
              >
                <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
                <h3 className="lavela-heading text-xl mb-2">Welcome to the Glow Club! ✨</h3>
                <p className="text-sm text-[#E8C4B8]">
                  Check your email for your welcome gift code!
                </p>
              </motion.div>
            )}
          </motion.div>
        </div>
      </section>

      {/* Benefits Grid */}
      <section className="py-16 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Member Perks</p>
            <h2 className="lavela-heading text-3xl sm:text-4xl">
              Why Join the <span className="lavela-shimmer-text">Glow Club</span>?
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {benefits.map((benefit, i) => (
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
                <div className="w-14 h-14 rounded-full flex items-center justify-center text-[#E6BE8A] mx-auto mb-4" style={{
                  background: 'linear-gradient(135deg, #0D4D4D 0%, #E8C4B8 100%)'
                }}>
                  {benefit.icon}
                </div>
                <h3 className="font-semibold text-[#E6BE8A] mb-2">{benefit.title}</h3>
                <p className="text-sm text-[#E8C4B8] mb-2">{benefit.desc}</p>
                {benefit.points && (
                  <span className="inline-block px-3 py-1 rounded-full text-xs text-[#E6BE8A] font-medium" style={{
                    background: 'rgba(230, 190, 138, 0.2)'
                  }}>
                    {benefit.points}
                  </span>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Membership Tiers */}
      <section className="py-16 px-4" style={{
        background: 'linear-gradient(180deg, rgba(232, 196, 184, 0.2) 0%, rgba(13, 77, 77, 0.3) 100%)'
      }}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Membership Tiers</p>
            <h2 className="lavela-heading text-3xl sm:text-4xl mb-4">
              Level Up Your <span className="lavela-shimmer-text">Glow</span>
            </h2>
            <p className="text-[#E8C4B8]">
              The more you shop, the more you earn!
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {tiers.map((tier, i) => (
              <motion.div
                key={i}
                className={`rounded-3xl overflow-hidden ${i === 2 ? 'md:-mt-4 md:mb-4' : ''}`}
                style={{
                  border: '1px solid rgba(230, 190, 138, 0.3)'
                }}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <div className={`bg-gradient-to-br ${tier.color} p-6 text-white text-center`}>
                  <h3 className="text-xl font-semibold mb-1">{tier.name}</h3>
                  <p className="text-sm opacity-80">{tier.range}</p>
                </div>
                <div className="p-6" style={{
                  background: 'rgba(13, 77, 77, 0.6)'
                }}>
                  <ul className="space-y-3">
                    {tier.perks.map((perk, j) => (
                      <li key={j} className="flex items-center gap-2 text-sm text-[#E8C4B8]">
                        <CheckCircle className="w-4 h-4 text-[#E6BE8A] flex-shrink-0" />
                        {perk}
                      </li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Rewards */}
      <section className="py-16 px-4" style={{
        background: 'rgba(13, 77, 77, 0.3)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-xs tracking-[0.3em] text-[#E6BE8A] uppercase mb-3">Redeem Points</p>
            <h2 className="lavela-heading text-3xl sm:text-4xl">
              Turn Points Into <span className="lavela-shimmer-text">Rewards</span>
            </h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {rewards.map((reward, i) => (
              <motion.div
                key={i}
                className="p-6 text-center hover:shadow-lg transition-shadow rounded-2xl"
                style={{
                  background: 'rgba(13, 77, 77, 0.5)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid rgba(230, 190, 138, 0.2)'
                }}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <span className="text-4xl block mb-3">{reward.emoji}</span>
                <p className="text-2xl font-bold lavela-shimmer-text mb-1">{reward.points}</p>
                <p className="text-xs text-[#E8C4B8] uppercase tracking-wider">points</p>
                <div className="mt-3 pt-3 border-t border-[#E6BE8A]/20">
                  <p className="text-sm font-medium text-[#E6BE8A]">{reward.reward}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Referral */}
      <section className="py-16 px-4" style={{
        background: 'linear-gradient(180deg, rgba(232, 196, 184, 0.2) 0%, rgba(13, 77, 77, 0.4) 100%)'
      }}>
        <div className="max-w-4xl mx-auto">
          <div className="p-8 sm:p-12 text-center rounded-3xl" style={{
            background: 'rgba(13, 77, 77, 0.5)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(230, 190, 138, 0.3)'
          }}>
            <Share2 className="w-12 h-12 text-[#E6BE8A] mx-auto mb-6" />
            <h2 className="lavela-heading text-2xl sm:text-3xl mb-4">
              Share the <span className="lavela-shimmer-text">Glow</span>
            </h2>
            <p className="text-[#E8C4B8] mb-6 max-w-xl mx-auto">
              Invite your friends and earn 100 points for each friend who makes their first purchase. 
              They get $10 off too!
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button className="lavela-btn-shimmer">
                Get Your Referral Link
              </button>
              <p className="text-sm text-[#E8C4B8]">
                <span className="font-bold text-[#E6BE8A]">100 pts</span> per referral
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-16 px-4 bg-gradient-to-br from-[#E6BE8A] to-[#D4A574] text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="lavela-heading-white text-3xl sm:text-4xl mb-6">
            Ready to Start Glowing?
          </h2>
          <p className="text-lg opacity-90 mb-8">
            Join the Glow Club today and get a free mini serum with your first order.
          </p>
          <button 
            onClick={() => navigate('/lavela/oro-rosa')}
            className="bg-white text-[#D4A574] font-semibold px-8 py-4 rounded-full hover:shadow-lg transition-all"
          >
            Shop Now & Earn Points
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

export default GlowClubPage;
