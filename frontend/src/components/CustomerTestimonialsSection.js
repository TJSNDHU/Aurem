import React from "react";
// PERF: Use LazyMotionWrapper to avoid duplicate framer-motion bundles
import { m } from "@/components/LazyMotionWrapper";
import { Badge } from "@/components/ui/badge";

// Fade-in animation wrapper - lightweight, transform-only
const FadeInUp = ({ children, delay = 0 }) => (
  <m.div
    initial={{ opacity: 0, y: 30 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, margin: "-50px" }}
    transition={{ duration: 0.8, delay, ease: [0.25, 0.1, 0.25, 1] }}
  >
    {children}
  </m.div>
);

const CustomerTestimonialsSection = () => {
  const testimonials = [
    {
      name: "Dr. Sarah M.",
      role: "Dermatologist, Toronto",
      rating: 5,
      text: "Finally, a Canadian brand that understands clinical skincare. The 17% active complex in Aura-Gen delivers results I've only seen from in-office treatments. My patients are seeing visible improvement in pigmentation within 4-6 weeks.",
      verified: true,
      image: "👩‍⚕️"
    },
    {
      name: "Michelle K.",
      role: "Verified Buyer, Vancouver",
      rating: 5,
      text: "I was skeptical about the claims, but after 8 weeks of using Aura-Gen, my melasma has faded significantly. The PDRN technology is real. Worth every penny for something that actually works.",
      verified: true,
      image: "✨"
    },
    {
      name: "James L.",
      role: "Verified Buyer, Calgary",
      rating: 5,
      text: "As someone who's tried everything for post-acne marks, Aura-Gen is the first product that's made a noticeable difference. The Tranexamic Acid and PDRN combination is powerful. My skin texture has completely transformed.",
      verified: true,
      image: "💫"
    },
    {
      name: "Emily R.",
      role: "Medical Aesthetician, Montreal",
      rating: 5,
      text: "I recommend Aura-Gen to all my clients for at-home maintenance between treatments. The 17% concentration rivals professional-grade products. Made in Toronto with real science behind it.",
      verified: true,
      image: "🔬"
    }
  ];

  return (
    <section className="py-20 bg-gradient-to-b from-white to-[#FAF7F2] testimonials-section">
      <div className="max-w-6xl mx-auto px-6 md:px-12">
        <FadeInUp>
          <div className="text-center mb-12">
            <Badge className="bg-[#C9A86C]/20 text-[#C9A86C] hover:bg-[#C9A86C]/20 mb-4 font-clinical text-xs tracking-[0.25em] uppercase font-medium">
              Verified Reviews
            </Badge>
            <h2 className="font-luxury text-3xl md:text-4xl font-medium text-[#2D2A2E] mb-4">
              What Our <span className="italic text-[#C9A86C]">Community</span> Says
            </h2>
            <p className="font-clinical text-[#5A5A5A] max-w-lg mx-auto">
              Real results from real Canadians using Aura-Gen's 17% Active Recovery Complex
            </p>
          </div>
          
          {/* Testimonials Grid */}
          <div className="grid md:grid-cols-2 gap-6">
            {testimonials.map((testimonial, idx) => (
              <div 
                key={idx}
                className="bg-white rounded-2xl p-6 shadow-sm border border-[#F0EBE3] hover:shadow-md transition-shadow"
              >
                {/* Rating Stars */}
                <div className="flex gap-1 mb-3">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <svg key={i} className="w-4 h-4 text-[#C9A86C]" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  ))}
                </div>
                
                {/* Testimonial Text */}
                <p className="font-clinical text-[#5A5A5A] text-sm leading-relaxed mb-4">
                  "{testimonial.text}"
                </p>
                
                {/* Author */}
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#C9A86C]/20 to-[#D4AF37]/20 flex items-center justify-center text-lg">
                    {testimonial.image}
                  </div>
                  <div>
                    <p className="font-clinical font-semibold text-[#2D2A2E] text-sm flex items-center gap-2">
                      {testimonial.name}
                      {testimonial.verified && (
                        <svg className="w-4 h-4 text-[#C9A86C]" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      )}
                    </p>
                    <p className="font-clinical text-xs text-[#888]">{testimonial.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          
          {/* Trust Badges */}
          <div className="mt-10 flex flex-wrap justify-center gap-6 text-center">
            <div className="flex items-center gap-2 text-[#5A5A5A] font-clinical text-sm">
              <span className="text-lg">🇨🇦</span>
              <span>Made in Toronto, Canada</span>
            </div>
            <div className="flex items-center gap-2 text-[#5A5A5A] font-clinical text-sm">
              <span className="text-lg">🔬</span>
              <span>Lab-Tested Formulations</span>
            </div>
            <div className="flex items-center gap-2 text-[#5A5A5A] font-clinical text-sm">
              <span className="text-lg">✨</span>
              <span>93% Visible Improvement</span>
            </div>
          </div>
        </FadeInUp>
      </div>
    </section>
  );
};

export default CustomerTestimonialsSection;
