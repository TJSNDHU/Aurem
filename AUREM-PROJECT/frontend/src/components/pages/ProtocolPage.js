import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link, useSearchParams } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { 
  Play, 
  Droplets, 
  Sun, 
  Moon, 
  Award, 
  Gift, 
  ChevronRight,
  Sparkles,
  Clock,
  Shield,
  Leaf,
  CheckCircle,
  Star,
  ArrowRight,
  Microscope
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ProtocolPage = () => {
  const [searchParams] = useSearchParams();
  const [tracked, setTracked] = useState(false);
  
  // Track QR code scan with UTM parameters
  useEffect(() => {
    if (!tracked) {
      const utm_source = searchParams.get('utm_source') || 'qr_code';
      const utm_medium = searchParams.get('utm_medium') || 'print';
      const utm_campaign = searchParams.get('utm_campaign') || 'thank_you_card';
      
      // Track the page view
      axios.post(`${API}/analytics/track`, {
        event: 'qr_code_scan',
        source: utm_source,
        medium: utm_medium,
        campaign: utm_campaign,
        page: '/protocol',
        timestamp: new Date().toISOString()
      }).catch(() => {});
      
      setTracked(true);
    }
  }, [searchParams, tracked]);

  const routineSteps = [
    {
      time: "Morning",
      icon: Sun,
      color: "#F59E0B",
      steps: [
        "Cleanse face gently with lukewarm water",
        "Apply 2-3 drops of AURA-GEN to fingertips",
        "Press gently onto face, starting from center outward",
        "Allow 60 seconds to absorb before sunscreen/makeup"
      ]
    },
    {
      time: "Evening",
      icon: Moon,
      color: "#6366F1",
      steps: [
        "Remove makeup and cleanse thoroughly",
        "Apply 3-4 drops of AURA-GEN (evening allows for deeper absorption)",
        "Massage in circular motions for 30 seconds",
        "Apply moisturizer if desired (optional with AURA-GEN)"
      ]
    }
  ];

  const recoveryTimeline = [
    { week: "Week 1-2", milestone: "Hydration boost, skin feels plumper" },
    { week: "Week 3-4", milestone: "Visible reduction in fine lines" },
    { week: "Week 5-8", milestone: "Improved skin tone and texture" },
    { week: "Week 9-12", milestone: "Significant regeneration visible" }
  ];

  return (
    <>
      <Helmet>
        <title>The AURA-GEN Recovery Protocol | Clinical-Grade Skincare Guide</title>
        <meta name="description" content="Your personalized guide to using AURA-GEN TXA+PDRN Bio-Regenerator. Learn the optimal morning and evening routine for maximum results." />
        <meta name="robots" content="noindex" /> {/* Hidden from search */}
      </Helmet>

      <div className="min-h-screen bg-gradient-to-b from-[#FAF7F2] to-white">
        {/* Hero Section */}
        <div className="relative overflow-hidden bg-gradient-to-br from-[#2D2A2E] via-[#3D3A3E] to-[#2D2A2E] text-white">
          <div className="absolute inset-0 opacity-10">
            <div className="absolute inset-0" style={{
              backgroundImage: `radial-gradient(circle at 30% 70%, #C9A86C 0%, transparent 50%),
                               radial-gradient(circle at 70% 30%, #F8A5B8 0%, transparent 50%)`
            }} />
          </div>
          
          <div className="max-w-4xl mx-auto px-4 py-16 relative z-10">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center"
            >
              <div className="inline-flex items-center gap-2 bg-[#C9A86C]/20 text-[#C9A86C] px-4 py-2 rounded-full text-sm font-medium mb-6">
                <Sparkles className="w-4 h-4" />
                Welcome to Your Skincare Journey
              </div>
              
              <h1 className="font-display text-4xl md:text-5xl font-bold mb-4">
                The AURA-GEN
                <span className="block text-[#C9A86C]">Recovery Protocol</span>
              </h1>
              
              <p className="text-lg text-white/80 max-w-2xl mx-auto mb-8">
                Your personalized guide to unlocking the full potential of clinical-grade 
                TXA + PDRN regeneration. Follow this protocol for optimal results.
              </p>

              <div className="flex flex-wrap justify-center gap-4">
                <div className="flex items-center gap-2 text-sm text-white/70">
                  <CheckCircle className="w-4 h-4 text-green-400" />
                  Batch Verified
                </div>
                <div className="flex items-center gap-2 text-sm text-white/70">
                  <Shield className="w-4 h-4 text-blue-400" />
                  Clinical Grade
                </div>
                <div className="flex items-center gap-2 text-sm text-white/70">
                  <Leaf className="w-4 h-4 text-green-400" />
                  Cruelty Free
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        {/* Video Section */}
        <div className="max-w-4xl mx-auto px-4 py-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="font-display text-2xl font-bold text-[#2D2A2E] text-center mb-6">
              How to Apply AURA-GEN
            </h2>
            
            <Card className="overflow-hidden border-2 border-[#C9A86C]/30 shadow-xl">
              <CardContent className="p-0">
                <div className="aspect-video bg-gradient-to-br from-[#2D2A2E] to-[#3D3A3E] relative">
                  {/* Replace with actual video embed */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-white">
                    <div className="w-20 h-20 rounded-full bg-[#C9A86C]/20 flex items-center justify-center mb-4 cursor-pointer hover:bg-[#C9A86C]/30 transition-colors">
                      <Play className="w-8 h-8 text-[#C9A86C]" fill="#C9A86C" />
                    </div>
                    <p className="text-white/60 text-sm">Application Tutorial Video</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* The 17% Recovery Routine */}
        <div className="max-w-4xl mx-auto px-4 py-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <div className="text-center mb-8">
              <h2 className="font-display text-2xl font-bold text-[#2D2A2E] mb-2">
                The 17% Recovery Routine
              </h2>
              <p className="text-[#5A5A5A]">
                Our clinical studies show a 17% improvement in skin regeneration markers 
                when following this optimal protocol.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {routineSteps.map((routine, idx) => (
                <Card 
                  key={routine.time}
                  className="border-2 overflow-hidden"
                  style={{ borderColor: `${routine.color}30` }}
                >
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3 mb-4">
                      <div 
                        className="w-12 h-12 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: `${routine.color}20` }}
                      >
                        <routine.icon className="w-6 h-6" style={{ color: routine.color }} />
                      </div>
                      <div>
                        <h3 className="font-bold text-lg text-[#2D2A2E]">{routine.time} Ritual</h3>
                        <p className="text-sm text-[#5A5A5A]">
                          {routine.time === "Morning" ? "2-3 drops" : "3-4 drops"}
                        </p>
                      </div>
                    </div>
                    
                    <ol className="space-y-3">
                      {routine.steps.map((step, stepIdx) => (
                        <li key={stepIdx} className="flex items-start gap-3">
                          <span 
                            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                            style={{ backgroundColor: routine.color }}
                          >
                            {stepIdx + 1}
                          </span>
                          <span className="text-sm text-[#5A5A5A]">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Dosage Guide */}
        <div className="bg-gradient-to-r from-[#C9A86C]/10 via-[#F8A5B8]/10 to-[#C9A86C]/10 py-12">
          <div className="max-w-4xl mx-auto px-4">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <h2 className="font-display text-2xl font-bold text-[#2D2A2E] text-center mb-8">
                <Droplets className="inline w-6 h-6 mr-2 text-[#C9A86C]" />
                Optimal Dosage Guide
              </h2>

              <div className="grid grid-cols-3 gap-4 text-center">
                <Card className="bg-white/80 border-[#C9A86C]/30">
                  <CardContent className="p-6">
                    <div className="text-4xl font-bold text-[#C9A86C] mb-2">2-3</div>
                    <div className="text-sm text-[#5A5A5A]">drops for<br/>morning use</div>
                  </CardContent>
                </Card>
                <Card className="bg-white/80 border-[#6366F1]/30">
                  <CardContent className="p-6">
                    <div className="text-4xl font-bold text-[#6366F1] mb-2">3-4</div>
                    <div className="text-sm text-[#5A5A5A]">drops for<br/>evening use</div>
                  </CardContent>
                </Card>
                <Card className="bg-white/80 border-green-500/30">
                  <CardContent className="p-6">
                    <div className="text-4xl font-bold text-green-600 mb-2">60</div>
                    <div className="text-sm text-[#5A5A5A]">seconds<br/>absorption time</div>
                  </CardContent>
                </Card>
              </div>
            </motion.div>
          </div>
        </div>

        {/* Recovery Timeline */}
        <div className="max-w-4xl mx-auto px-4 py-12">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <h2 className="font-display text-2xl font-bold text-[#2D2A2E] text-center mb-8">
              <Clock className="inline w-6 h-6 mr-2 text-[#C9A86C]" />
              Your Recovery Timeline
            </h2>

            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-gradient-to-b from-[#C9A86C] to-[#F8A5B8] hidden md:block" />
              
              <div className="space-y-6">
                {recoveryTimeline.map((item, idx) => (
                  <div 
                    key={item.week}
                    className={`flex items-center gap-6 ${idx % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'}`}
                  >
                    <Card className="flex-1 border-2 border-[#C9A86C]/20">
                      <CardContent className="p-4">
                        <div className="font-bold text-[#C9A86C] mb-1">{item.week}</div>
                        <p className="text-sm text-[#5A5A5A]">{item.milestone}</p>
                      </CardContent>
                    </Card>
                    <div className="w-4 h-4 rounded-full bg-[#C9A86C] hidden md:block flex-shrink-0" />
                    <div className="flex-1 hidden md:block" />
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* CTA Section - Register Batch / Join Founders Club */}
        <div className="bg-gradient-to-br from-[#2D2A2E] to-[#3D3A3E] text-white py-16">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
            >
              <Award className="w-16 h-16 text-[#C9A86C] mx-auto mb-6" />
              
              <h2 className="font-display text-3xl font-bold mb-4">
                Join the Founders Club
              </h2>
              
              <p className="text-white/80 max-w-xl mx-auto mb-8">
                Register your batch to unlock exclusive benefits: early access to new formulations, 
                personalized skin consultations, and rewards on every purchase.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button 
                  asChild
                  className="bg-[#C9A86C] hover:bg-[#B8975B] text-white px-8 py-6 text-lg"
                >
                  <Link to="/register?utm_source=protocol_page&utm_campaign=founders_club">
                    <Gift className="w-5 h-5 mr-2" />
                    Register Your Batch
                  </Link>
                </Button>
                
                <Button 
                  asChild
                  variant="outline"
                  className="border-white/30 text-white hover:bg-white/10 px-8 py-6 text-lg"
                >
                  <Link to="/waitlist?utm_source=protocol_page">
                    <Star className="w-5 h-5 mr-2" />
                    Join Founders Club
                  </Link>
                </Button>
              </div>

              <p className="text-white/50 text-sm mt-6">
                Already a member? <Link to="/login" className="text-[#C9A86C] underline">Sign in</Link> to track your progress.
              </p>
            </motion.div>
          </div>
        </div>

        {/* Product Verification */}
        <div className="max-w-4xl mx-auto px-4 py-12">
          <Card className="border-2 border-green-500/30 bg-green-50/50">
            <CardContent className="p-6 text-center">
              <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-4" />
              <h3 className="font-bold text-lg text-[#2D2A2E] mb-2">Product Authenticity Verified</h3>
              <p className="text-sm text-[#5A5A5A] mb-4">
                Thank you for purchasing authentic AURA-GEN. Your product has been verified 
                through our secure supply chain.
              </p>
              <Button 
                asChild
                variant="outline"
                className="border-green-500 text-green-700 hover:bg-green-50"
              >
                <Link to="/compare">
                  <Microscope className="w-4 h-4 mr-2" />
                  Compare with Other Products
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 py-8">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <p className="text-sm text-[#5A5A5A]">
              Questions about your skincare routine? Contact us at{' '}
              <a href="mailto:support@reroots.ca" className="text-[#C9A86C] underline">
                support@reroots.ca
              </a>
            </p>
            <div className="mt-4 flex justify-center gap-6">
              <Link to="/" className="text-sm text-[#5A5A5A] hover:text-[#C9A86C]">Home</Link>
              <Link to="/shop" className="text-sm text-[#5A5A5A] hover:text-[#C9A86C]">Shop</Link>
              <Link to="/faq" className="text-sm text-[#5A5A5A] hover:text-[#C9A86C]">FAQ</Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ProtocolPage;
