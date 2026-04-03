import React, { useState, useEffect, lazy, Suspense } from 'react';
import { Check, X, Sparkles, Shield, Clock, Truck, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

// Dynamic Batch Status Component with real-time inventory
const BatchStatusBar = ({ productId }) => {
  const [batchData, setBatchData] = useState({
    total: 1000,
    remaining: 653,
    batchNumber: '001',
    bottledDate: 'January 2026'
  });

  useEffect(() => {
    // Fetch real inventory count
    const fetchBatchStatus = async () => {
      try {
        const res = await axios.get(`${API}/api/products/${productId}`);
        if (res.data?.stock !== undefined) {
          setBatchData(prev => ({
            ...prev,
            remaining: Math.min(res.data.stock, prev.total)
          }));
        }
      } catch (e) {
        // Use default values
      }
    };
    
    if (productId) {
      fetchBatchStatus();
      // Poll every 30 seconds for real-time updates
      const interval = setInterval(fetchBatchStatus, 30000);
      return () => clearInterval(interval);
    }
  }, [productId]);

  const percentRemaining = (batchData.remaining / batchData.total) * 100;

  return (
    <div className="bg-gradient-to-br from-[#2D2A2E] to-[#1a1819] text-white rounded-2xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-display text-lg font-bold" role="heading" aria-level="4">BATCH #{batchData.batchNumber} STATUS</p>
        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
          LIVE
        </Badge>
      </div>
      
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Total Units:</span>
          <span className="font-semibold">{batchData.total.toLocaleString()}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Bottled:</span>
          <span className="font-semibold">{batchData.bottledDate}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Remaining:</span>
          <span className="font-bold text-[#F8A5B8]">{batchData.remaining} units</span>
        </div>
      </div>
      
      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-[#F8A5B8] to-[#D4AF37] rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${percentRemaining}%` }}
          />
        </div>
        <p className="text-xs text-gray-400 text-center">
          {Math.round(100 - percentRemaining)}% claimed • {batchData.remaining} bottles left
        </p>
      </div>
      
      <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-400/10 rounded-lg p-3">
        <Clock className="h-4 w-4 shrink-0" />
        <span>When this batch sells out, the next one takes 3-4 weeks to press and stabilize.</span>
      </div>
    </div>
  );
};

// Sticky CTA Component
export const StickyCTA = ({ price, onBuyNow, visible }) => {
  if (!visible) return null;
  
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-md border-t border-gray-200 shadow-2xl transform transition-transform duration-300">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <div className="hidden sm:block">
          <p className="text-sm font-semibold text-[#2D2A2E]">AURA-GEN PDRN + TXA + ARGIRELINE 17.0%</p>
          <p className="text-xs text-gray-500">Active Recovery Complex • Free shipping</p>
        </div>
        <div className="flex items-center gap-3 flex-1 sm:flex-none">
          <span className="font-display text-xl font-bold text-[#2D2A2E]">${price} CAD</span>
          <Button 
            onClick={onBuyNow}
            className="flex-1 sm:flex-none bg-gradient-to-r from-[#F8A5B8] to-[#E991A5] hover:from-[#E991A5] hover:to-[#F8A5B8] text-white font-bold px-6 py-2 rounded-full shadow-lg"
          >
            Buy Now
          </Button>
        </div>
      </div>
    </div>
  );
};

// Main Reverse Hook Content Component
const AuraGenReverseHook = ({ product, onBuyNow, formatPrice }) => {
  const price = product?.price || 99;
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);
  const [showShareMenu, setShowShareMenu] = useState(false);
  const videoRef = React.useRef(null);
  
  // Video URLs - Use local compressed version for better mobile performance
  const AURA_GEN_VIDEO_URL = "/videos/aura-gen-unboxing.mp4";
  const AURA_GEN_VIDEO_MOBILE = "/videos/aura-gen-unboxing-mobile.mp4";
  const AURA_GEN_VIDEO_THUMB = "/videos/aura-gen-video-thumb.jpg";
  
  // Share handlers
  const shareToWhatsApp = () => {
    const text = encodeURIComponent("Check out AURA-GEN PDRN + TXA + ARGIRELINE 17.0% - The future of regenerative beauty 🧬✨ https://reroots.ca/products/prod-aura-gen");
    window.open(`https://wa.me/?text=${text}`, '_blank');
  };
  
  const shareToInstagram = () => {
    // Instagram doesn't have direct share API, copy link instead
    navigator.clipboard.writeText("https://reroots.ca/products/prod-aura-gen");
    alert("Link copied! Open Instagram and paste in your story or DM.");
  };
  
  const shareToFacebook = () => {
    const url = encodeURIComponent("https://reroots.ca/products/prod-aura-gen");
    window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, '_blank');
  };
  
  const shareToTwitter = () => {
    const text = encodeURIComponent("17.0% actives. We put our numbers in the name. Most brands hide theirs. 🧬 AURA-GEN by @rerootscanada");
    const url = encodeURIComponent("https://reroots.ca/products/prod-aura-gen");
    window.open(`https://twitter.com/intent/tweet?text=${text}&url=${url}`, '_blank');
  };
  
  const copyLink = () => {
    navigator.clipboard.writeText("https://reroots.ca/products/prod-aura-gen");
    toast.success("Link copied! Share it with someone who deserves better skincare.");
    setShowShareMenu(false);
  };

  return (
    <div className="space-y-12 py-8">
      
      {/* SECTION 1: Hero Hook - Optimized Product Title for SEO/GEO */}
      <div className="text-center space-y-4 border-b border-gray-100 pb-8">
        <Badge className="bg-[#D4AF37]/10 text-[#D4AF37] border-[#D4AF37]/30 mb-2">
          🇨🇦 Made in Toronto, Canada
        </Badge>
        <h1 className="font-display text-2xl md:text-4xl font-bold text-[#2D2A2E]">
          Aura-Gen | 17% Active Recovery Complex
        </h1>
        <p className="text-lg md:text-xl text-[#F8A5B8] font-medium">
          Advanced PDRN + TXA + Argireline Serum
        </p>
        <p className="text-sm text-[#5A5A5A]">
          By Reroots Aesthetics Inc. — Canadian Biotech Laboratory
        </p>
        <div className="max-w-2xl mx-auto pt-4">
          <p className="text-[#5A5A5A] italic text-base md:text-lg">
            &quot;Most brands hide their percentages in a lab report. We put ours in the name. 
            If they aren&apos;t showing you their numbers, they&apos;re hiding their results.&quot;
          </p>
        </div>
        
        {/* Share This Page - Prominent Share Buttons */}
        <div className="pt-6">
          <p className="text-sm text-gray-500 mb-3">Share with someone who deserves better skincare:</p>
          <div className="flex items-center justify-center gap-3 flex-wrap" role="group" aria-label="Share options">
            <button 
              onClick={shareToWhatsApp}
              aria-label="Share on WhatsApp"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#25D366] text-white text-sm font-medium hover:scale-105 transition-transform shadow-md"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
              </svg>
              <span>WhatsApp</span>
            </button>
            <button 
              onClick={shareToInstagram}
              aria-label="Share on Instagram"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-[#833AB4] via-[#FD1D1D] to-[#F77737] text-white text-sm font-medium hover:scale-105 transition-transform shadow-md"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
              </svg>
              <span>Instagram</span>
            </button>
            <button 
              onClick={shareToFacebook}
              aria-label="Share on Facebook"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#1877F2] text-white text-sm font-medium hover:scale-105 transition-transform shadow-md"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
              </svg>
              <span>Facebook</span>
            </button>
            <button 
              onClick={shareToTwitter}
              aria-label="Share on X (formerly Twitter)"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#000] text-white text-sm font-medium hover:scale-105 transition-transform shadow-md"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
              <span>X</span>
            </button>
            <button 
              onClick={copyLink}
              aria-label="Copy link to clipboard"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 text-gray-700 text-sm font-medium hover:scale-105 transition-transform shadow-md border border-gray-200"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              <span>Copy Link</span>
            </button>
          </div>
        </div>
      </div>

      {/* SECTION 2: The Price Confrontation */}
      <section className="space-y-6">
        <h2 className="font-display text-2xl md:text-3xl font-bold text-[#2D2A2E]">
          Let&apos;s talk about the elephant in your skincare drawer.
        </h2>
        
        <div className="prose prose-lg text-[#5A5A5A] space-y-4">
          <p>
            You&apos;ve spent $150... $200... maybe $300 on serums that promised 
            &quot;visible results in 4 weeks.&quot;
          </p>
          <p>
            You followed the routine religiously. Morning. Night. Layering. Waiting.
          </p>
          <p className="font-semibold text-[#2D2A2E]">And what did you get?</p>
          <p>
            A 2-3% active formula diluted with 90% water, fillers, and fragrance 
            designed to smell luxurious—not perform.
          </p>
          
          <div className="bg-gray-50 rounded-xl p-6 space-y-2 text-sm not-prose">
            <p className="text-[#2D2A2E] font-semibold mb-3">Where your money actually went:</p>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>The fancy box?</span>
                <span className="text-red-500 font-medium">$40 of your money</span>
              </div>
              <div className="flex justify-between">
                <span>The influencer campaign?</span>
                <span className="text-red-500 font-medium">Another $30</span>
              </div>
              <div className="flex justify-between">
                <span>The actual formula?</span>
                <span className="text-red-500 font-medium">Maybe $15 worth of actives</span>
              </div>
            </div>
            <p className="pt-3 border-t border-gray-200 mt-3 text-[#2D2A2E] font-medium">
              You weren&apos;t buying skincare. You were buying marketing.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 3: The Math Reveal */}
      <section className="space-y-6">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E]">
          Here&apos;s what the industry doesn&apos;t want you to calculate:
        </h2>
        
        <div className="grid gap-4">
          {/* Clinic Option */}
          <div className="bg-red-50 border border-red-100 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-[#2D2A2E]">CLINIC PDRN FACIAL</h4>
              <span className="text-red-600 font-bold">$300-500/session</span>
            </div>
            <ul className="space-y-1 text-sm text-gray-600">
              <li className="flex items-center gap-2"><X className="h-4 w-4 text-red-500" /> Requires appointment</li>
              <li className="flex items-center gap-2"><X className="h-4 w-4 text-red-500" /> Results fade in 2-3 weeks</li>
              <li className="flex items-center gap-2"><X className="h-4 w-4 text-red-500" /> Need 4-6 sessions minimum</li>
            </ul>
          </div>

          {/* Luxury Serum Option */}
          <div className="bg-orange-50 border border-orange-100 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-[#2D2A2E]">&quot;LUXURY&quot; STORE SERUM</h4>
              <span className="text-orange-600 font-bold">$150-220/bottle</span>
            </div>
            <ul className="space-y-1 text-sm text-gray-600">
              <li className="flex items-center gap-2"><X className="h-4 w-4 text-orange-500" /> 2-5% active ingredients</li>
              <li className="flex items-center gap-2"><X className="h-4 w-4 text-orange-500" /> 12-18 month shelf life (degraded)</li>
              <li className="flex items-center gap-2"><X className="h-4 w-4 text-orange-500" /> 60% of cost = packaging + marketing</li>
            </ul>
          </div>

          {/* AURA-GEN Option */}
          <div className="bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-300 rounded-xl p-5 space-y-3 relative overflow-hidden">
            <div className="absolute top-0 right-0 bg-green-500 text-white text-xs font-bold px-3 py-1 rounded-bl-lg">
              BEST VALUE
            </div>
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-[#2D2A2E]">AURA-GEN</h4>
              <span className="text-green-600 font-bold text-xl">Under $100</span>
            </div>
            <ul className="space-y-1 text-sm text-gray-700">
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> <strong>17% active complex</strong> (5x industry standard)</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> Fresh-batched (max 90 days from bottling)</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> Direct-to-you (no retail markup)</li>
            </ul>
          </div>
        </div>

        <div className="text-center space-y-2 py-4">
          <p className="text-lg font-semibold text-[#2D2A2E]">Read those numbers again.</p>
          <p className="text-2xl font-display font-bold text-[#F8A5B8]">We&apos;re not cheaper. We&apos;re smarter.</p>
        </div>
      </section>

      {/* SECTION 4: Ingredient Authority - Updated with Technical Names */}
      <section className="space-y-6 bg-[#FAF8F5] -mx-6 px-6 py-8 rounded-none md:rounded-2xl md:mx-0">
        <div className="text-center space-y-2">
          <h2 className="font-display text-xl font-bold text-[#2D2A2E]">
            WHAT&apos;S ACTUALLY IN YOUR BOTTLE
          </h2>
          <p className="text-sm text-gray-500">(Warning: No fluff. Just science.)</p>
        </div>

        <div className="space-y-4">
          {/* PDRN - The Cellular Architect */}
          <div className="bg-white rounded-xl p-5 border border-gray-100 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-[#2D2A2E]">PDRN (2.0%)</h4>
                <p className="text-sm text-[#D4AF37]">The &quot;Cellular Architect&quot; — Salmon DNA</p>
              </div>
              <Badge className="bg-[#D4AF37]/10 text-[#D4AF37] border-[#D4AF37]/30">2.0%</Badge>
            </div>
            <p className="text-sm text-gray-600">
              The same polydeoxyribonucleotide used in $400 clinic facials. Signals your skin 
              to regenerate at the cellular level. Not &quot;hydrate.&quot; Not &quot;plump.&quot; 
              <strong> Actually rebuild.</strong>
            </p>
            <div className="flex justify-between text-xs pt-2 border-t border-gray-100">
              <span className="text-gray-400">Others offer: 0.5-1%</span>
              <span className="text-green-600 font-semibold">You get: 2.0% clinical-grade</span>
            </div>
          </div>

          {/* TXA - The Pigment Precision */}
          <div className="bg-white rounded-xl p-5 border border-gray-100 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-[#2D2A2E]">TXA (5.0%)</h4>
                <p className="text-sm text-[#F8A5B8]">The &quot;Pigment Precision&quot; — Tranexamic Acid</p>
              </div>
              <Badge className="bg-[#F8A5B8]/10 text-[#F8A5B8] border-[#F8A5B8]/30">5.0%</Badge>
            </div>
            <p className="text-sm text-gray-600">
              Dermatologist-preferred for melasma, dark spots, and post-inflammatory 
              hyperpigmentation. Works at the melanin pathway level—not just surface exfoliation.
            </p>
            <div className="flex justify-between text-xs pt-2 border-t border-gray-100">
              <span className="text-gray-400">Others offer: 1-3%</span>
              <span className="text-green-600 font-semibold">You get: 5.0% targeted concentration</span>
            </div>
          </div>

          {/* ARGIRELINE - The Surface Smoother */}
          <div className="bg-white rounded-xl p-5 border border-gray-100 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-[#2D2A2E]">ARGIRELINE (10.0%)</h4>
                <p className="text-sm text-[#8B5CF6]">The &quot;Surface Smoother&quot; — Acetyl Hexapeptide-8</p>
              </div>
              <Badge className="bg-[#8B5CF6]/10 text-[#8B5CF6] border-[#8B5CF6]/30">10.0%</Badge>
            </div>
            <p className="text-sm text-gray-600">
              Nicknamed &quot;Botox in a bottle&quot; <span className="text-gray-400">(we can&apos;t legally say 
              that, but dermatologists do)</span>. Relaxes micro-muscle tension that creates expression lines.
            </p>
            <div className="flex justify-between text-xs pt-2 border-t border-gray-100">
              <span className="text-gray-400">Others offer: 2-5%</span>
              <span className="text-green-600 font-semibold">You get: 10.0% (maximum efficacy)</span>
            </div>
          </div>
        </div>

        <div className="text-center space-y-2 pt-4">
          <p className="text-3xl font-display font-bold text-[#2D2A2E]">TOTAL: 17.0% ACTIVE RECOVERY COMPLEX</p>
          <p className="text-sm text-gray-500">
            (The industry average? 3-5%. Now you know why their &quot;results&quot; take 6 months.)
          </p>
        </div>
      </section>

      {/* SECTION 5: Fresh Batch Story */}
      <section className="space-y-6">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E]">
          WHY WE CAN&apos;T BE ON STORE SHELVES
        </h2>
        <p className="text-sm text-gray-500">(And why that&apos;s the point)</p>

        <div className="prose text-[#5A5A5A] space-y-4">
          <p>
            Traditional skincare sits in warehouses for 6-18 months before reaching your bathroom.
          </p>
          <p>
            Every week on that shelf, the actives degrade. That $180 serum? By the time you open it, 
            you&apos;re getting maybe <strong>60% of the advertised potency</strong>.
          </p>
          <p className="font-semibold text-[#2D2A2E]">We built AURA-GEN differently.</p>
        </div>

        <div className="bg-[#2D2A2E] text-white rounded-xl p-6 space-y-4">
          <h4 className="font-display font-bold text-center">THE FRESH BATCH MODEL</h4>
          <ul className="space-y-3">
            <li className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#F8A5B8]/20 flex items-center justify-center shrink-0">
                <Sparkles className="h-4 w-4 text-[#F8A5B8]" />
              </div>
              <span>1,000 units per batch</span>
            </li>
            <li className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#D4AF37]/20 flex items-center justify-center shrink-0">
                <Shield className="h-4 w-4 text-[#D4AF37]" />
              </div>
              <span>Cold-press stabilized</span>
            </li>
            <li className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center shrink-0">
                <Truck className="h-4 w-4 text-green-400" />
              </div>
              <span>Ships within 30 days of bottling</span>
            </li>
            <li className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0">
                <RefreshCw className="h-4 w-4 text-blue-400" />
              </div>
              <span>No warehouse. No retail partner. No markup.</span>
            </li>
          </ul>
          <p className="text-center text-sm text-gray-400 pt-2 border-t border-gray-700">
            When this batch sells out, we press the next one. Fresh actives. Full potency. Every bottle.
          </p>
        </div>

        <div className="text-center py-4">
          <p className="text-lg font-semibold text-[#2D2A2E]">This is why we&apos;re under $100.</p>
          <div className="flex flex-col gap-1 mt-2 text-gray-500">
            <span>No Sephora placement fee.</span>
            <span>No department store margin.</span>
            <span>No influencer budget baked into your bottle.</span>
          </div>
          <p className="text-xl font-display font-bold text-[#F8A5B8] mt-4">
            Just formula, directly to your face.
          </p>
        </div>

        {/* FROM THE LAB TO YOUR VANITY - Video Sub-section */}
        <div className="mt-8 pt-8 border-t border-gray-200">
          <div className="text-center mb-6">
            <h4 className="font-display text-xl font-bold text-[#2D2A2E] mb-2">
              FROM THE LAB TO YOUR VANITY
            </h4>
            <p className="text-sm text-[#5A5A5A] max-w-lg mx-auto">
              We don&apos;t spend money on celebrity faces. We spend it on the box you see here—engineered 
              to keep your 17.0% active complex stable and potent from the first pump to the last.
            </p>
          </div>
          
          <div className="relative max-w-sm mx-auto">
          {/* Video Container */}
            <div className="relative rounded-2xl overflow-hidden shadow-2xl bg-[#2D2A2E] aspect-[9/16]">
              <video
                ref={videoRef}
                src={AURA_GEN_VIDEO_URL}
                poster={AURA_GEN_VIDEO_THUMB}
                className="w-full h-full object-cover"
                playsInline
                loop
                preload="metadata"
                muted
                onClick={() => {
                  if (videoRef.current) {
                    if (isVideoPlaying) {
                      videoRef.current.pause();
                    } else {
                      videoRef.current.play();
                    }
                    setIsVideoPlaying(!isVideoPlaying);
                  }
                }}
                onPlay={() => setIsVideoPlaying(true)}
                onPause={() => setIsVideoPlaying(false)}
              />
              
              {/* Play Button Overlay */}
              {!isVideoPlaying && (
                <div 
                  className="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer"
                  onClick={() => {
                    if (videoRef.current) {
                      videoRef.current.play();
                      setIsVideoPlaying(true);
                    }
                  }}
                >
                  <div className="w-20 h-20 rounded-full bg-white/90 flex items-center justify-center shadow-xl hover:scale-110 transition-transform">
                    <svg className="w-8 h-8 text-[#F8A5B8] ml-1" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z"/>
                    </svg>
                  </div>
                </div>
              )}
              
              {/* Video Badge */}
              <div className="absolute top-4 left-4">
                <Badge className="bg-[#D4AF37] text-white border-0">
                  17.0% ACTIVE COMPLEX
                </Badge>
              </div>
            </div>
            
            {/* Share Buttons */}
            <div className="mt-4 flex items-center justify-center gap-2" role="group" aria-label="Video share options">
              <p className="text-sm text-gray-500 mr-2">Share:</p>
              <button 
                onClick={shareToWhatsApp}
                className="w-9 h-9 rounded-full bg-[#25D366] text-white flex items-center justify-center hover:scale-110 transition-transform"
                aria-label="Share on WhatsApp"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
              </button>
              <button 
                onClick={shareToInstagram}
                className="w-9 h-9 rounded-full bg-gradient-to-br from-[#833AB4] via-[#FD1D1D] to-[#F77737] text-white flex items-center justify-center hover:scale-110 transition-transform"
                aria-label="Share on Instagram"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                </svg>
              </button>
              <button 
                onClick={shareToFacebook}
                className="w-9 h-9 rounded-full bg-[#1877F2] text-white flex items-center justify-center hover:scale-110 transition-transform"
                aria-label="Share on Facebook"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
              </button>
              <button 
                onClick={shareToTwitter}
                className="w-9 h-9 rounded-full bg-[#1DA1F2] text-white flex items-center justify-center hover:scale-110 transition-transform"
                aria-label="Share on X"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
                </svg>
              </button>
              <button 
                onClick={copyLink}
                className="w-9 h-9 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center hover:scale-110 transition-transform"
                aria-label="Copy link to clipboard"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 6: Objection Crusher */}
      <section className="bg-gray-50 -mx-6 px-6 py-8 rounded-none md:rounded-2xl md:mx-0 space-y-6">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] text-center">
          &quot;BUT IF IT&apos;S SO GOOD, WHY ISN&apos;T IT MORE EXPENSIVE?&quot;
        </h2>
        
        <p className="text-center text-[#5A5A5A]">Because expensive ≠ effective.</p>

        <div className="bg-white rounded-xl p-5 space-y-3">
          <p className="font-semibold text-[#2D2A2E] mb-3">Here&apos;s what you&apos;re NOT paying for with AURA-GEN:</p>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-3">
              <X className="h-4 w-4 text-red-500 shrink-0" />
              <span><strong>$40</strong> — Luxury packaging designed for Instagram</span>
            </div>
            <div className="flex items-center gap-3">
              <X className="h-4 w-4 text-red-500 shrink-0" />
              <span><strong>$35</strong> — Retail partner margin (Sephora takes 40%)</span>
            </div>
            <div className="flex items-center gap-3">
              <X className="h-4 w-4 text-red-500 shrink-0" />
              <span><strong>$25</strong> — Influencer seeding &amp; PR boxes</span>
            </div>
            <div className="flex items-center gap-3">
              <X className="h-4 w-4 text-red-500 shrink-0" />
              <span><strong>$20</strong> — Warehouse storage for 12+ months</span>
            </div>
            <div className="flex items-center gap-3">
              <X className="h-4 w-4 text-red-500 shrink-0" />
              <span><strong>$15</strong> — Celebrity endorsement amortization</span>
            </div>
          </div>
          <div className="pt-3 border-t border-gray-100 mt-3">
            <p className="text-[#2D2A2E] font-medium">
              That&apos;s <strong>$135 of &quot;luxury tax&quot;</strong> on every prestige serum.
            </p>
            <p className="text-[#2D2A2E] mt-2">We deleted those line items. You get the formula. That&apos;s it.</p>
          </div>
        </div>

        <p className="text-center text-xl font-display font-bold text-[#2D2A2E]">
          Under $100 isn&apos;t cheap. It&apos;s efficient.
        </p>
      </section>

      {/* SECTION 7: Social Proof */}
      <section className="space-y-6">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] text-center">
          WHAT 17% ACTIVES ACTUALLY LOOK LIKE
        </h2>

        <div className="space-y-4">
          <div className="bg-white border border-gray-100 rounded-xl p-5 space-y-3">
            <div className="flex gap-1">
              {[...Array(5)].map((_, i) => (
                <Sparkles key={i} className="h-4 w-4 text-[#F8A5B8] fill-[#F8A5B8]" />
              ))}
            </div>
            <p className="text-[#5A5A5A] italic">
              &quot;I&apos;ve used La Mer, SK-II, and Augustinus Bader. AURA-GEN outperformed all of them in 3 weeks. 
              I&apos;m genuinely annoyed I wasted so much money.&quot;
            </p>
            <div className="text-sm">
              <p className="font-semibold text-[#2D2A2E]">— Sarah M., Toronto</p>
              <p className="text-gray-400 text-xs">Previously spent: $2,400/year on skincare</p>
            </div>
          </div>

          <div className="bg-white border border-gray-100 rounded-xl p-5 space-y-3">
            <div className="flex gap-1">
              {[...Array(5)].map((_, i) => (
                <Sparkles key={i} className="h-4 w-4 text-[#F8A5B8] fill-[#F8A5B8]" />
              ))}
            </div>
            <p className="text-[#5A5A5A] italic">
              &quot;My aesthetician asked what I changed. When I told her the price, she didn&apos;t believe me. 
              Now she recommends it to her clients.&quot;
            </p>
            <div className="text-sm">
              <p className="font-semibold text-[#2D2A2E]">— Dr. Jennifer K., Vancouver</p>
              <p className="text-gray-400 text-xs">Dermatology Resident</p>
            </div>
          </div>

          <div className="bg-white border border-gray-100 rounded-xl p-5 space-y-3">
            <div className="flex gap-1">
              {[...Array(5)].map((_, i) => (
                <Sparkles key={i} className="h-4 w-4 text-[#F8A5B8] fill-[#F8A5B8]" />
              ))}
            </div>
            <p className="text-[#5A5A5A] italic">
              &quot;The melasma on my cheeks—nothing worked for 5 years. 8 weeks with AURA-GEN. 
              I cried when I saw my skin.&quot;
            </p>
            <div className="text-sm">
              <p className="font-semibold text-[#2D2A2E]">— Michelle T., Calgary</p>
              <p className="text-gray-400 text-xs">Skin concern: Post-pregnancy hyperpigmentation</p>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 8: The Ritual */}
      <section className="space-y-6 bg-gradient-to-br from-[#FDF9F9] to-white -mx-6 px-6 py-8 rounded-none md:rounded-2xl md:mx-0">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] text-center">
          YOUR NEW 2-MINUTE RITUAL
        </h2>
        <p className="text-center text-gray-500 text-sm">
          This isn&apos;t a 12-step K-beauty routine. It&apos;s a 2-minute protocol that actually works.
        </p>

        <div className="bg-[#2D2A2E] text-white rounded-xl p-6 space-y-4">
          <h4 className="font-semibold text-[#F8A5B8] uppercase tracking-wider text-sm">
            Night Ritual (When your skin rebuilds)
          </h4>
          
          <div className="space-y-4">
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-[#F8A5B8] text-[#2D2A2E] flex items-center justify-center font-bold shrink-0">1</div>
              <div>
                <p className="font-semibold">CLEANSE</p>
                <p className="text-sm text-gray-400">Remove the day. Any gentle cleanser works.</p>
              </div>
            </div>
            
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-[#F8A5B8] text-[#2D2A2E] flex items-center justify-center font-bold shrink-0">2</div>
              <div>
                <p className="font-semibold">APPLY AURA-GEN</p>
                <p className="text-sm text-gray-400">4-5 drops. Press into damp skin. Don&apos;t rub—let the actives penetrate.</p>
              </div>
            </div>
            
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-[#F8A5B8] text-[#2D2A2E] flex items-center justify-center font-bold shrink-0">3</div>
              <div>
                <p className="font-semibold">SEAL (Optional)</p>
                <p className="text-sm text-gray-400">Light moisturizer if needed. That&apos;s it.</p>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-700 space-y-1 text-center">
            <p className="text-sm text-gray-400">Total time: Under 2 minutes</p>
            <p className="text-sm text-[#F8A5B8]">Results timeline: Visible changes in 14-21 days</p>
          </div>
        </div>

        <div className="text-center space-y-2">
          <p className="text-[#5A5A5A]">You&apos;ll feel the difference on Day 1.</p>
          <p className="text-[#5A5A5A]">You&apos;ll see it by Week 3.</p>
          <p className="font-semibold text-[#2D2A2E]">You&apos;ll wonder why you ever paid $200 for less.</p>
        </div>
      </section>

      {/* SECTION 9: Batch Status */}
      <section className="space-y-4">
        <BatchStatusBar productId={product?.id} />
      </section>

      {/* SECTION 10: Risk Reversal */}
      <section className="space-y-6">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] text-center">
          THE &quot;SKEPTIC&apos;S GUARANTEE&quot;
        </h2>

        <div className="text-center text-[#5A5A5A] space-y-2">
          <p>We get it. You&apos;ve been burned before.</p>
          <p>$150 serums that did nothing. &quot;Holy grail&quot; products that broke you out.</p>
          <p>Promises that never showed up on your face.</p>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-200 rounded-xl p-6 space-y-4">
          <h4 className="font-display font-bold text-center text-green-800 text-lg">
            30-DAY &quot;PROVE IT&quot; GUARANTEE
          </h4>
          
          <p className="text-center text-green-700">Use AURA-GEN for 30 days.</p>
          
          <div className="space-y-2">
            <p className="text-sm text-green-800 font-medium">If you don&apos;t see visible improvement in:</p>
            <ul className="space-y-1 text-sm text-green-700">
              <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Skin texture</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Dark spots / hyperpigmentation</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Fine lines around eyes and forehead</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Overall radiance and tone</li>
            </ul>
          </div>

          <p className="text-center font-semibold text-green-800">
            Email us. Full refund. No return shipping. No &quot;store credit&quot; nonsense. Actual money back.
          </p>

          <div className="text-center pt-3 border-t border-green-200">
            <p className="text-sm text-green-600">
              We&apos;ve processed <strong>11 refunds</strong> out of <strong>2,847 orders</strong>.
            </p>
            <p className="text-lg font-bold text-green-800">That&apos;s a 99.6% satisfaction rate.</p>
            <p className="text-sm text-green-600 mt-1">We&apos;re betting you won&apos;t need it.</p>
          </div>
        </div>
      </section>

      {/* SECTION 11: Final CTA */}
      <section className="space-y-6">
        <p className="text-center font-semibold text-[#2D2A2E]">You have two choices right now:</p>

        <div className="grid md:grid-cols-2 gap-4">
          {/* Option A */}
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5 space-y-3">
            <h4 className="font-bold text-gray-500">OPTION A: Keep scrolling</h4>
            <ul className="space-y-2 text-sm text-gray-500">
              <li>→ Go back to your $150 serum</li>
              <li>→ Wait another 6 months for &quot;visible results&quot;</li>
              <li>→ Wonder if there&apos;s something better</li>
            </ul>
          </div>

          {/* Option B */}
          <div className="bg-gradient-to-br from-[#F8A5B8]/10 to-[#D4AF37]/10 border-2 border-[#F8A5B8] rounded-xl p-5 space-y-3">
            <h4 className="font-bold text-[#2D2A2E]">OPTION B: Try the math</h4>
            <ul className="space-y-2 text-sm text-[#5A5A5A]">
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> 17% actives (vs industry 3-5%)</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> Under $100 (vs $150-300)</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> Fresh-batched (vs 12-month shelf)</li>
              <li className="flex items-center gap-2"><Check className="h-4 w-4 text-green-600" /> 30-day guarantee (vs hope)</li>
            </ul>
            <div className="pt-2 text-sm text-[#2D2A2E]">
              <p>Worst case: You get your money back.</p>
              <p className="font-semibold">Best case: You never overpay for skincare again.</p>
            </div>
          </div>
        </div>

        {/* Big CTA Button */}
        <div className="bg-gradient-to-br from-[#2D2A2E] to-[#1a1819] rounded-2xl p-6 text-center space-y-4">
          <Button 
            onClick={onBuyNow}
            className="w-full bg-gradient-to-r from-[#F8A5B8] to-[#D4AF37] hover:from-[#D4AF37] hover:to-[#F8A5B8] text-[#2D2A2E] font-bold text-sm sm:text-lg py-6 rounded-full shadow-xl hover:shadow-2xl transition-all duration-300 px-4"
          >
            <span className="block sm:hidden">SECURE YOUR BOTTLE</span>
            <span className="hidden sm:block">JOIN THE 1,000 — SECURE YOUR BOTTLE</span>
          </Button>
          
          <div className="space-y-1">
            <p className="text-white font-display text-base sm:text-xl leading-tight">
              <span className="block sm:inline">AURA-GEN</span>
              <span className="block sm:inline sm:ml-1">PDRN + TXA + ARGIRELINE</span>
              <span className="block sm:inline sm:ml-1">17.0%</span>
            </p>
            <p className="text-sm text-gray-300">Active Recovery Complex</p>
            <p className="text-3xl font-bold text-[#F8A5B8]">${price} CAD</p>
          </div>

          <div className="flex flex-wrap justify-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1"><Truck className="h-3 w-3" /> Free shipping across Canada</span>
            <span className="flex items-center gap-1"><Check className="h-3 w-3" /> Ships within 48 hours</span>
            <span className="flex items-center gap-1"><Shield className="h-3 w-3" /> 30-day money-back guarantee</span>
          </div>

          <p className="text-xs text-gray-500">
            Secure checkout • FSA/HSA eligible • No subscription required
          </p>
          <p className="text-sm text-gray-400 italic">
            &quot;I just want to try it once&quot; — Perfect. No strings attached.
          </p>
        </div>
      </section>

      {/* SECTION 12: FAQ Accordion */}
      <section className="space-y-4">
        <h2 className="font-display text-xl font-bold text-[#2D2A2E] text-center">
          STILL THINKING? FAIR.
        </h2>

        <Accordion type="single" collapsible className="space-y-2">
          <AccordionItem value="sensitive" className="border border-gray-100 rounded-xl px-4 bg-white">
            <AccordionTrigger className="text-left font-semibold text-[#2D2A2E] hover:no-underline">
              Is this safe for sensitive skin?
            </AccordionTrigger>
            <AccordionContent className="text-[#5A5A5A]">
              Yes. No fragrance, no essential oils, no dyes. Dermatologist-formulated for all skin types 
              including rosacea-prone and sensitive skin.
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="retinol" className="border border-gray-100 rounded-xl px-4 bg-white">
            <AccordionTrigger className="text-left font-semibold text-[#2D2A2E] hover:no-underline">
              Can I use this with retinol?
            </AccordionTrigger>
            <AccordionContent className="text-[#5A5A5A]">
              Yes, but alternate nights for the first 2 weeks. AURA-GEN (Mon/Wed/Fri), Retinol (Tue/Thu/Sat).
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="brand" className="border border-gray-100 rounded-xl px-4 bg-white">
            <AccordionTrigger className="text-left font-semibold text-[#2D2A2E] hover:no-underline">
              Why haven&apos;t I heard of this brand?
            </AccordionTrigger>
            <AccordionContent className="text-[#5A5A5A]">
              Because we spend $0 on influencers and $0 on PR. Every dollar goes into the formula. 
              You found us because someone with good skin told you about us.
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="expensive" className="border border-gray-100 rounded-xl px-4 bg-white">
            <AccordionTrigger className="text-left font-semibold text-[#2D2A2E] hover:no-underline">
              What if I&apos;m already using expensive skincare?
            </AccordionTrigger>
            <AccordionContent className="text-[#5A5A5A]">
              Perfect. Use AURA-GEN on one side of your face for 2 weeks. Compare. We&apos;ll wait.
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="results" className="border border-gray-100 rounded-xl px-4 bg-white">
            <AccordionTrigger className="text-left font-semibold text-[#2D2A2E] hover:no-underline">
              When will I see results?
            </AccordionTrigger>
            <AccordionContent className="text-[#5A5A5A]">
              <ul className="space-y-1">
                <li>Texture improvement: 7-10 days</li>
                <li>Brightness/radiance: 14-21 days</li>
                <li>Dark spots fading: 4-6 weeks</li>
                <li>Fine line reduction: 6-8 weeks</li>
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>

      {/* Final Footer Line */}
      <div className="text-center py-6 border-t border-gray-100">
        <p className="font-display text-lg font-bold text-[#2D2A2E]">
          AURA-GEN PDRN + TXA + ARGIRELINE 17.0% — The math always wins.
        </p>
        <p className="text-xs text-gray-400 mt-2">
          © 2026 ReRoots Biotech Skincare | Toronto, Canada<br />
          Health Canada Compliant • Cruelty-Free • Fresh-Batched
        </p>
      </div>
    </div>
  );
};

export default AuraGenReverseHook;
export { BatchStatusBar };
