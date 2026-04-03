import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { 
  ChevronDown, HelpCircle, Beaker, Shield, Truck, Clock, 
  Sparkles, Heart, AlertCircle, Package, CreditCard, RefreshCw
} from "lucide-react";

const FAQPage = () => {
  const [openIndex, setOpenIndex] = useState(null);

  const faqCategories = [
    {
      title: "About PDRN & Ingredients",
      icon: Beaker,
      faqs: [
        {
          question: "What is PDRN and how does it work?",
          answer: "PDRN (Polydeoxyribonucleotide) is a bioactive compound derived from salmon DNA that promotes cellular regeneration and tissue repair. It works by activating adenosine A2A receptors, which stimulates collagen production, improves blood circulation, and accelerates skin healing. PDRN has been used in medical settings for over 20 years and is now available in premium skincare formulations like ReRoots' AURA-GEN serum."
        },
        {
          question: "Is PDRN safe for sensitive skin?",
          answer: "Yes, PDRN is exceptionally well-tolerated by sensitive skin types. Because it's biocompatible with human tissue, it rarely causes irritation or allergic reactions. In clinical studies, PDRN showed no adverse effects even on compromised skin barriers. Our formulations are also fragrance-free, paraben-free, and dermatologist-tested to ensure safety for all skin types."
        },
        {
          question: "How is PDRN different from Retinol or Vitamin C?",
          answer: "Unlike Retinol (which can cause irritation, peeling, and sun sensitivity) or Vitamin C (which oxidizes quickly and may be unstable), PDRN works through a fundamentally different mechanism—cellular regeneration. PDRN doesn't thin the skin or cause photosensitivity. It can be used day and night, year-round, and actually helps repair damage that other actives might cause. Many dermatologists now recommend PDRN as a gentler yet more effective alternative."
        },
        {
          question: "What is Tranexamic Acid and why do you use it?",
          answer: "Tranexamic Acid (TXA) is a powerful brightening ingredient originally used in medical settings to reduce bleeding. In skincare, it inhibits melanin production at multiple levels, making it highly effective for treating melasma, dark spots, and post-inflammatory hyperpigmentation. It's considered safer and more stable than hydroquinone, and works synergistically with PDRN for enhanced brightening results."
        },
        {
          question: "Are your products vegan and cruelty-free?",
          answer: "Our products are 100% cruelty-free and never tested on animals. Regarding vegan status: our PDRN is derived from salmon DNA (specifically from salmon milt), which is a byproduct of the food industry. While this makes it non-vegan, it's sustainably sourced and provides unmatched biocompatibility that synthetic alternatives cannot replicate. We're transparent about this because we believe in ingredient integrity."
        }
      ]
    },
    {
      title: "Product Usage & Results",
      icon: Sparkles,
      faqs: [
        {
          question: "How long until I see results from AURA-GEN?",
          answer: "Most users notice improved skin texture and hydration within 1-2 weeks. Visible reduction in dark circles and hyperpigmentation typically appears around 4-6 weeks with consistent use. For anti-aging benefits like reduced fine lines and improved firmness, allow 8-12 weeks. Results compound over time—the longer you use PDRN, the more significant the cellular regeneration benefits become."
        },
        {
          question: "Can I use PDRN products with other actives?",
          answer: "Yes! PDRN is remarkably versatile and can be layered with most skincare actives including niacinamide, hyaluronic acid, peptides, and even retinol (though we recommend alternating nights if using retinol). The only caution is with very high-concentration acids (like strong chemical peels)—wait 30 minutes between application. PDRN actually helps soothe skin when used with potentially irritating actives."
        },
        {
          question: "What's the best routine for dark circles?",
          answer: "For optimal dark circle treatment: 1) Cleanse gently, 2) Apply AURA-GEN serum to the entire under-eye area and cheekbones (don't just dab—PDRN works on the whole eye contour), 3) Wait 1-2 minutes for absorption, 4) Follow with your moisturizer and SPF in the morning. Use morning AND night for accelerated results. The combination of PDRN + Tranexamic Acid addresses both pigmentation and vascular dark circles."
        },
        {
          question: "Should I use the serum morning, night, or both?",
          answer: "For best results, use twice daily—morning and night. Unlike retinol, PDRN doesn't cause photosensitivity, so it's perfectly safe (and beneficial) for daytime use. In the morning, it provides antioxidant protection and prepares skin for the day. At night, it supports your skin's natural repair cycle. Consistency is key to seeing cellular regeneration benefits."
        }
      ]
    },
    {
      title: "Shipping & Orders",
      icon: Truck,
      faqs: [
        {
          question: "Where do you ship to?",
          answer: "We currently ship across Canada with free shipping on orders over $75 CAD. We offer standard shipping (5-7 business days) and express shipping (2-3 business days). We're working on expanding to the United States and international markets—join our waitlist to be notified when we launch in your region."
        },
        {
          question: "How long does shipping take?",
          answer: "Standard shipping within Canada takes 5-7 business days. Express shipping takes 2-3 business days. Orders are processed within 24-48 hours on business days. You'll receive tracking information via email once your order ships. During sales or holidays, please allow an extra 1-2 days for processing."
        },
        {
          question: "Do you offer free shipping?",
          answer: "Yes! We offer free standard shipping on all orders over $75 CAD within Canada. For orders under $75, standard shipping is $8.99 and express shipping is $14.99. Founding Members and VIP customers receive free shipping on all orders regardless of order value."
        }
      ]
    },
    {
      title: "Returns & Refunds",
      icon: RefreshCw,
      faqs: [
        {
          question: "What is your return policy?",
          answer: "We offer a 30-day satisfaction guarantee. If you're not completely satisfied with your purchase, you can return unopened products within 30 days for a full refund. For opened products, we offer a one-time exchange or store credit if you've used less than 25% of the product. Please contact support@reroots.ca to initiate a return."
        },
        {
          question: "How do I request a refund?",
          answer: "Email us at support@reroots.ca with your order number and reason for return. We'll respond within 24-48 hours with return instructions. Once we receive your return, refunds are processed within 5-7 business days to your original payment method. We'll keep you updated at every step."
        },
        {
          question: "What if my order arrives damaged?",
          answer: "If your order arrives damaged, please take photos and email us at support@reroots.ca within 48 hours of delivery. We'll send a replacement immediately at no cost to you—no need to return the damaged item. Your satisfaction is our priority, and we stand behind the quality of our products and packaging."
        }
      ]
    },
    {
      title: "Safety & Quality",
      icon: Shield,
      faqs: [
        {
          question: "Are ReRoots products Health Canada approved?",
          answer: "Our products comply with all Health Canada regulations for cosmetic products. We follow Good Manufacturing Practices (GMP) and all our ingredients are approved for cosmetic use in Canada. Our formulations are developed with board-certified dermatologists and undergo rigorous safety and stability testing before release."
        },
        {
          question: "Can I use PDRN during pregnancy or breastfeeding?",
          answer: "While PDRN has an excellent safety profile, we recommend consulting with your healthcare provider before using any new skincare products during pregnancy or breastfeeding. As a precaution, some ingredients in our formulations (like certain peptides) haven't been extensively studied in pregnant populations. Your doctor can provide personalized guidance."
        },
        {
          question: "Do your products expire?",
          answer: "Yes, all skincare products have a shelf life. Our products are effective for 12 months after opening (look for the PAO symbol on packaging). Unopened products have a 2-year shelf life from manufacture date. Store in a cool, dry place away from direct sunlight for optimal potency. Our airless pump packaging helps maintain freshness and prevents contamination."
        },
        {
          question: "Are your products tested on animals?",
          answer: "Absolutely not. ReRoots is 100% cruelty-free. We never test on animals, and we don't work with suppliers or third parties who conduct animal testing. We use advanced in-vitro testing methods and human clinical trials to ensure product safety and efficacy. We're proud to be certified cruelty-free."
        }
      ]
    }
  ];

  // Flatten FAQs for schema
  const allFaqs = faqCategories.flatMap(cat => cat.faqs);

  // FAQ Schema for Google Rich Results
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": allFaqs.map(faq => ({
      "@type": "Question",
      "name": faq.question,
      "acceptedAnswer": {
        "@type": "Answer",
        "text": faq.answer
      }
    }))
  };

  return (
    <div className="min-h-screen bg-[#FAF8F5] pt-24 pb-16">
      <Helmet>
        <title>FAQ - Frequently Asked Questions | ReRoots Biotech Skincare</title>
        <meta name="description" content="Get answers to common questions about PDRN skincare, product usage, shipping, returns, and more. Learn how PDRN works, if it's safe for sensitive skin, and how to get the best results." />
        <meta name="keywords" content="PDRN FAQ, PDRN safety, PDRN vs retinol, skincare questions, ReRoots FAQ, dark circles treatment FAQ, Canadian skincare" />
        <link rel="canonical" href="https://reroots.ca/faq" />
        
        {/* FAQ Schema for Rich Results */}
        <script type="application/ld+json">
          {JSON.stringify(faqSchema)}
        </script>
      </Helmet>

      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-[#F8A5B8]/10 text-[#F8A5B8] px-4 py-2 rounded-full text-sm font-medium mb-4">
            <HelpCircle className="h-4 w-4" />
            Knowledge Base
          </div>
          <h1 className="font-luxury text-4xl md:text-5xl text-[#2D2A2E] mb-4">
            Frequently Asked <span className="text-[#F8A5B8]">Questions</span>
          </h1>
          <p className="text-[#2D2A2E]/70 max-w-2xl mx-auto">
            Everything you need to know about PDRN skincare, our products, and how to achieve your best skin.
          </p>
        </div>

        {/* Quick Links */}
        <div className="flex flex-wrap justify-center gap-3 mb-12">
          {faqCategories.map((category, idx) => (
            <a 
              key={idx}
              href={`#${category.title.toLowerCase().replace(/\s+/g, '-')}`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full border border-[#2D2A2E]/10 hover:border-[#F8A5B8] hover:text-[#F8A5B8] transition-colors text-sm"
            >
              <category.icon className="h-4 w-4" />
              {category.title}
            </a>
          ))}
        </div>

        {/* FAQ Categories */}
        <div className="space-y-10">
          {faqCategories.map((category, catIdx) => (
            <div key={catIdx} id={category.title.toLowerCase().replace(/\s+/g, '-')}>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-full bg-[#F8A5B8]/10 flex items-center justify-center">
                  <category.icon className="h-5 w-5 text-[#F8A5B8]" />
                </div>
                <h2 className="font-luxury text-2xl text-[#2D2A2E]">{category.title}</h2>
              </div>
              
              <div className="space-y-3">
                {category.faqs.map((faq, faqIdx) => {
                  const globalIdx = faqCategories.slice(0, catIdx).reduce((acc, c) => acc + c.faqs.length, 0) + faqIdx;
                  const isOpen = openIndex === globalIdx;
                  
                  return (
                    <div 
                      key={faqIdx}
                      className="bg-white rounded-xl border border-[#2D2A2E]/5 overflow-hidden"
                    >
                      <button
                        onClick={() => setOpenIndex(isOpen ? null : globalIdx)}
                        className="w-full flex items-center justify-between p-5 text-left hover:bg-[#FAF8F5]/50 transition-colors"
                        aria-expanded={isOpen}
                      >
                        <h3 className="font-semibold text-[#2D2A2E] pr-4">{faq.question}</h3>
                        <ChevronDown 
                          className={`h-5 w-5 text-[#F8A5B8] flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                        />
                      </button>
                      
                      <div 
                        className={`overflow-hidden transition-all duration-300 ${isOpen ? 'max-h-[500px]' : 'max-h-0'}`}
                      >
                        <div className="px-5 pb-5 text-[#5A5A5A] leading-relaxed">
                          {faq.answer}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Still Have Questions CTA */}
        <div className="mt-16 text-center bg-gradient-to-br from-[#2D2A2E] to-[#3D3A3E] rounded-2xl p-8 md:p-12">
          <h2 className="font-luxury text-2xl md:text-3xl text-white mb-4">
            Still Have Questions?
          </h2>
          <p className="text-white/70 mb-6 max-w-md mx-auto">
            Our skincare experts are here to help you find the perfect routine for your skin concerns.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              to="/contact"
              className="inline-flex items-center justify-center gap-2 bg-[#F8A5B8] hover:bg-[#e8959a] text-white px-6 py-3 rounded-full font-medium transition-colors"
            >
              Contact Us
            </Link>
            <Link 
              to="/skin-quiz"
              className="inline-flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 text-white px-6 py-3 rounded-full font-medium transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              Take Skin Quiz
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FAQPage;
