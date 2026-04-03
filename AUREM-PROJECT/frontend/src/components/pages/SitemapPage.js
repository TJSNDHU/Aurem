import React from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { 
  ShoppingBag, Sparkles, FlaskConical, Users, FileText, 
  HelpCircle, Mail, MapPin, ChevronRight 
} from "lucide-react";

const SitemapPage = () => {
  const sections = [
    {
      title: "Shop",
      icon: ShoppingBag,
      links: [
        { name: "All Products", url: "/products" },
        { name: "AURA-GEN Serum", url: "/products/prod-aura-gen" },
        { name: "Dark Circles Solutions", url: "/shop/dark-circles" },
        { name: "Pigmentation Solutions", url: "/shop/pigmentation" },
        { name: "Anti-Aging Solutions", url: "/shop/anti-aging" },
        { name: "Hydration Solutions", url: "/shop/hydration" },
      ]
    },
    {
      title: "Programs & Tools",
      icon: Sparkles,
      links: [
        { name: "Skin Quiz", url: "/skin-quiz" },
        { name: "Bio-Age Repair Scan", url: "/Bio-Age-Repair-Scan" },
        { name: "Product Comparison Tool", url: "/molecular-auditor" },
        { name: "Founding Member Program", url: "/waitlist" },
        { name: "QR Code Generator", url: "/qr-generator" },
      ]
    },
    {
      title: "Partner With Us",
      icon: Users,
      links: [
        { name: "Influencer Program", url: "/influencer" },
        { name: "Become a Partner", url: "/become-partner" },
        { name: "Partner Login", url: "/partner-login" },
      ]
    },
    {
      title: "Learn",
      icon: FlaskConical,
      links: [
        { name: "About ReRoots", url: "/about" },
        { name: "Science of PDRN", url: "/science" },
        { name: "Science Glossary", url: "/science-glossary" },
        { name: "PDRN Comparison Guide", url: "/pdrn-comparison-guide" },
        { name: "Blog & Articles", url: "/blog" },
      ]
    },
    {
      title: "Customer Support",
      icon: HelpCircle,
      links: [
        { name: "FAQ", url: "/faq" },
        { name: "Contact Us", url: "/contact" },
        { name: "Shipping Policy", url: "/shipping-policy" },
        { name: "Return Policy", url: "/return-policy" },
        { name: "Track My Order", url: "/account" },
        { name: "Wishlist", url: "/wishlist" },
      ]
    },
    {
      title: "Legal",
      icon: FileText,
      links: [
        { name: "Privacy Policy", url: "/privacy" },
        { name: "Terms of Service", url: "/terms" },
      ]
    },
  ];

  return (
    <div className="min-h-screen bg-[#FAF8F5] pt-24 pb-16">
      <Helmet>
        <title>Sitemap | ReRoots Biotech Skincare</title>
        <meta name="description" content="Complete sitemap of ReRoots.ca - Find all pages including products, skin concerns, programs, science, and support pages." />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="https://reroots.ca/sitemap" />
      </Helmet>

      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="font-luxury text-4xl md:text-5xl text-[#2D2A2E] mb-4">
            Site<span className="text-[#F8A5B8]">map</span>
          </h1>
          <p className="text-[#2D2A2E]/70 max-w-2xl mx-auto">
            Explore all pages on ReRoots.ca - your guide to Canadian biotech skincare
          </p>
        </div>

        {/* Sitemap Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {sections.map((section) => (
            <div 
              key={section.title}
              className="bg-white rounded-2xl p-6 shadow-sm border border-[#2D2A2E]/5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-full bg-[#F8A5B8]/10 flex items-center justify-center">
                  <section.icon className="h-5 w-5 text-[#F8A5B8]" />
                </div>
                <h2 className="font-semibold text-lg text-[#2D2A2E]">{section.title}</h2>
              </div>
              <ul className="space-y-2">
                {section.links.map((link) => (
                  <li key={link.url}>
                    <Link 
                      to={link.url}
                      className="flex items-center gap-2 text-[#2D2A2E]/70 hover:text-[#F8A5B8] transition-colors py-1 group"
                    >
                      <ChevronRight className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                      <span>{link.name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Contact Info */}
        <div className="mt-12 text-center">
          <div className="inline-flex items-center gap-6 text-[#2D2A2E]/60 text-sm">
            <a href="mailto:support@reroots.ca" className="flex items-center gap-2 hover:text-[#F8A5B8] transition-colors">
              <Mail className="h-4 w-4" />
              support@reroots.ca
            </a>
            <span className="flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              Toronto, Canada
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SitemapPage;
