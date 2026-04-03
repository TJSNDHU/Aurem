import React, { useState, useEffect } from "react";
import axios from "axios";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Helmet } from "react-helmet-async";

// API URL
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return window.location.origin;
};
const API = `${getBackendUrl()}/api`;

const AboutPage = () => {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/about-page`)
      .then(res => setContent(res.data))
      .catch(() => {
        // Default content if API fails
        setContent({
          hero_badge: "OUR STORY",
          hero_title: "Rooted in Science",
          hero_subtitle: "ReRoots was founded with a simple belief: skincare should be backed by science, not marketing hype.",
          mission_title: "Our Mission",
          mission_image: "https://images.unsplash.com/photo-1670444010821-e63091bddf1f?w=800",
          mission_text_1: "We combine cutting-edge biotechnology with time-tested natural ingredients to create skincare that delivers real, visible results.",
          mission_text_2: "Our flagship ingredient, PDRN (Polydeoxyribonucleotide), has been used in professional skincare for decades. We've harnessed this powerful bioactive compound and formulated it for daily skincare use.",
          mission_text_3: "Every product is developed in partnership with dermatologists and undergoes rigorous testing to ensure safety and efficacy.",
          values_title: "Our Values",
          value_1_title: "Science-First",
          value_1_description: "Every ingredient is selected based on scientific research, not trends.",
          value_2_title: "Transparency",
          value_2_description: "We share our full ingredient lists and the science behind our formulations.",
          value_3_title: "Sustainability",
          value_3_description: "Eco-conscious packaging and responsibly sourced ingredients."
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen pt-24 bg-[#FDF9F9] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      <Helmet>
        <title>About Reroots Aesthetics Inc. | Canadian Biotech Laboratory | Toronto</title>
        <meta name="description" content="Reroots Aesthetics Inc. is a Canadian biotech laboratory specializing in PDRN skincare. Based in Toronto, we develop the Aura-Gen 17% Active Recovery Complex. 93% visible improvement in clinical trials." />
        <link rel="canonical" href="https://reroots.ca/about" />
      </Helmet>
      
      {/* Hero - Updated for SEO/GEO with Entity Recognition */}
      <section className="py-24 bg-[#2D2A2E] text-white">
        <div className="max-w-4xl mx-auto px-6 md:px-12 text-center">
          <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] mb-4">🇨🇦 Made in Toronto, Canada</Badge>
          <h1 className="font-display text-4xl md:text-5xl font-bold mb-6">
            Reroots Aesthetics Inc.
          </h1>
          <p className="text-2xl text-[#F8A5B8] font-medium mb-4">
            Canadian Biotech Laboratory
          </p>
          <p className="text-xl text-white/70">
            Pioneering the future of regenerative skincare with science-backed formulations. 
            Home of the Aura-Gen 17% Active Recovery Complex.
          </p>
        </div>
      </section>

      {/* Entity Information Section - For AI Search Engines */}
      <section className="py-16 bg-gradient-to-b from-[#2D2A2E] to-[#1a1819]">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <div className="grid md:grid-cols-3 gap-8 text-center">
            <div className="p-6 rounded-2xl bg-white/5">
              <p className="text-4xl font-bold text-[#D4AF37]">17%</p>
              <p className="text-white/80 mt-2">Active Complex</p>
              <p className="text-xs text-white/50 mt-1">Industry-leading concentration</p>
            </div>
            <div className="p-6 rounded-2xl bg-white/5">
              <p className="text-4xl font-bold text-[#F8A5B8]">93%</p>
              <p className="text-white/80 mt-2">Visible Improvement</p>
              <p className="text-xs text-white/50 mt-1">Clinical trial results</p>
            </div>
            <div className="p-6 rounded-2xl bg-white/5">
              <p className="text-4xl font-bold text-[#D4AF37]">2026</p>
              <p className="text-white/80 mt-2">Toronto, Canada</p>
              <p className="text-xs text-white/50 mt-1">Lab-tested formulations</p>
            </div>
          </div>
        </div>
      </section>

      {/* Mission */}
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <img
              src={content?.mission_image || "https://images.unsplash.com/photo-1670444010821-e63091bddf1f?w=800"}
              alt="Science"
              className="w-full aspect-square object-cover rounded-sm"
            />
            <div className="space-y-6">
              <h2 className="font-display text-3xl font-bold text-[#2D2A2E]">{content?.mission_title || "Our Mission"}</h2>
              <p className="text-[#5A5A5A] text-lg">
                {content?.mission_text_1 || "We combine cutting-edge biotechnology with time-tested natural ingredients."}
              </p>
              <p className="text-[#5A5A5A]">
                {content?.mission_text_2 || "Our flagship ingredient, PDRN, has been used in professional skincare for decades."}
              </p>
              <p className="text-[#5A5A5A]">
                {content?.mission_text_3 || "Every product is developed in partnership with dermatologists."}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <h2 className="font-display text-3xl font-bold text-[#2D2A2E] text-center mb-16">{content?.values_title || "Our Values"}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                title: content?.value_1_title || "Science-First",
                description: content?.value_1_description || "Every ingredient is selected based on scientific research, not trends."
              },
              {
                title: content?.value_2_title || "Transparency",
                description: content?.value_2_description || "We share our full ingredient lists and the science behind our formulations."
              },
              {
                title: content?.value_3_title || "Sustainability",
                description: content?.value_3_description || "Eco-conscious packaging and responsibly sourced ingredients."
              }
            ].map((value, i) => (
              <div key={i} className="text-center p-8 border border-gray-100 hover:border-[#F8A5B8] transition-colors">
                <h3 className="font-display text-xl font-semibold text-[#2D2A2E] mb-4">{value.title}</h3>
                <p className="text-[#5A5A5A]">{value.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default AboutPage;
