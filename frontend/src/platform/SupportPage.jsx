import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, HelpCircle, MessageSquare, Mail, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const FAQ_DATA = [
  {
    category: 'Getting Started',
    items: [
      {
        q: 'What is AUREM?',
        a: 'AUREM is an AI-powered autonomous business automation platform. It functions as your "Autonomous Revenue Executive" — handling customer recovery, store optimization, sales intelligence, and 24/7 monitoring through a team of specialized AI agents.',
      },
      {
        q: 'How do I connect my Shopify store?',
        a: 'Navigate to "Nexus Data Bridge" in the dashboard sidebar, then click "Shopify" under available connectors. Enter your store domain (e.g., your-store.myshopify.com) and authorize AUREM. Your customer and order data will begin syncing immediately.',
      },
      {
        q: 'Is my data secure?',
        a: 'Yes. AUREM uses AES-256 encryption at rest, TLS 1.3 in transit, and strict multi-tenant isolation. Each merchant\'s data is completely separated. We are GDPR compliant with full data deletion capabilities.',
      },
    ],
  },
  {
    category: 'AI Agents & Features',
    items: [
      {
        q: 'What AI agents does AUREM include?',
        a: 'AUREM deploys 6 specialized agents: Scout (research), Envoy (communication), Oracle (analysis), Closer (deal execution), Architect (strategy), and Critic (quality validation). They work together through the ORA Dispatcher.',
      },
      {
        q: 'How does abandoned cart recovery work?',
        a: 'AUREM\'s Recovery Engine automatically detects abandoned carts and sends personalized recovery messages via email, SMS, or WhatsApp. Each message includes a unique attribution-tracked link to measure conversion.',
      },
      {
        q: 'What is the ULTRAPLINIAN Scorer?',
        a: 'ULTRAPLINIAN is our 5-axis quality scoring system (Completeness, Structure, Data Integrity, Directness, Relevance). It rates every AI output on a 100-point scale, ensuring only high-quality responses reach merchants and customers.',
      },
      {
        q: 'What does ClawChief do?',
        a: 'ClawChief is AUREM\'s autonomous operations layer. It runs 24/7 heartbeat checks, monitors system health, triggers auto-healing when issues are detected, and maintains durable memory of all operations.',
      },
    ],
  },
  {
    category: 'Shopify Integration',
    items: [
      {
        q: 'What Shopify data does AUREM access?',
        a: 'AUREM requests read access to customers, orders, products, and themes. Write access is only for themes (to deploy SEO/accessibility fixes). We never modify your products, orders, or customer records.',
      },
      {
        q: 'How does the Theme App Extension work?',
        a: 'AUREM installs three theme extensions: ORA Pixel (behavior tracking), ORA Chat (AI shopping assistant), and ORA Recommendations (AI product suggestions). Enable them via Shopify\'s Theme Editor — no code injection.',
      },
      {
        q: 'How do I comply with GDPR/ADMT requirements?',
        a: 'AUREM handles GDPR automatically: customer data requests, deletion requests, and shop data removal are all processed via mandatory webhooks. Use the Compliance tab to generate your AI/ADMT disclosure snippet.',
      },
    ],
  },
  {
    category: 'Billing & Plans',
    items: [
      {
        q: 'What plans are available?',
        a: 'Starter ($49/mo) — 5 Agents, 1,000 ORA Messages. Professional ($149/mo) — Unlimited Agents, 10,000 messages, API access. Enterprise ($499/mo) — Unlimited everything, dedicated infrastructure, SLA guarantee.',
      },
      {
        q: 'Can I cancel anytime?',
        a: 'Yes. All subscriptions can be cancelled at any time. Your data is retained for 30 days after cancellation to allow for export, then permanently deleted.',
      },
    ],
  },
];

export default function SupportPage() {
  const [expandedFaq, setExpandedFaq] = useState({});
  const [contactForm, setContactForm] = useState({ name: '', email: '', subject: '', message: '' });
  const [sending, setSending] = useState(false);

  const toggleFaq = (catIdx, itemIdx) => {
    const key = `${catIdx}-${itemIdx}`;
    setExpandedFaq(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleContactSubmit = async (e) => {
    e.preventDefault();
    if (!contactForm.email || !contactForm.message) return;
    setSending(true);
    // Mock submission — in production wire to email service
    await new Promise(r => setTimeout(r, 800));
    toast.success('Message sent! We\'ll get back to you within 24 hours.');
    setContactForm({ name: '', email: '', subject: '', message: '' });
    setSending(false);
  };

  return (
    <div className="min-h-screen" style={{ background: 'var(--aurem-bg, #050505)', color: 'var(--aurem-heading, #F4F4F4)' }}>
      <div className="max-w-4xl mx-auto px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity" style={{ color: 'var(--aurem-accent, #D4AF37)' }} data-testid="support-back-link">
          <ArrowLeft className="w-4 h-4" /> Back to AUREM
        </Link>

        <div className="flex items-center gap-3 mb-2">
          <HelpCircle className="w-8 h-8" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
          <h1 className="text-3xl font-bold tracking-tight" data-testid="support-title">Help & Support</h1>
        </div>
        <p className="text-sm mb-12" style={{ color: 'var(--aurem-body-secondary, #888)' }}>
          Find answers to common questions or reach out to our team.
        </p>

        {/* FAQ Section */}
        <div className="space-y-8 mb-16" data-testid="faq-section">
          {FAQ_DATA.map((category, catIdx) => (
            <div key={catIdx}>
              <h2 className="text-base font-semibold mb-3" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
                {category.category}
              </h2>
              <div className="space-y-1">
                {category.items.map((item, itemIdx) => {
                  const key = `${catIdx}-${itemIdx}`;
                  const isOpen = expandedFaq[key];
                  return (
                    <div key={itemIdx} className="rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(212,175,55,0.08)' }}>
                      <button
                        onClick={() => toggleFaq(catIdx, itemIdx)}
                        className="w-full flex items-center justify-between p-4 text-left text-sm font-medium transition-colors hover:bg-white/[0.02]"
                        data-testid={`faq-${catIdx}-${itemIdx}`}
                        style={{ color: 'var(--aurem-heading, #F4F4F4)' }}
                      >
                        {item.q}
                        {isOpen ? <ChevronDown className="w-4 h-4 shrink-0 ml-2" /> : <ChevronRight className="w-4 h-4 shrink-0 ml-2" />}
                      </button>
                      {isOpen && (
                        <div className="px-4 pb-4 text-sm leading-relaxed" style={{ color: 'var(--aurem-body, #CCC)' }}>
                          {item.a}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Contact Section */}
        <div className="grid md:grid-cols-2 gap-8" data-testid="contact-section">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare className="w-5 h-5" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
              <h2 className="text-lg font-semibold">Contact Us</h2>
            </div>
            <form onSubmit={handleContactSubmit} className="space-y-3">
              <input
                type="text"
                placeholder="Your Name"
                value={contactForm.name}
                onChange={(e) => setContactForm(p => ({ ...p, name: e.target.value }))}
                data-testid="contact-name"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(212,175,55,0.12)', color: 'var(--aurem-heading)' }}
              />
              <input
                type="email"
                placeholder="Email Address *"
                required
                value={contactForm.email}
                onChange={(e) => setContactForm(p => ({ ...p, email: e.target.value }))}
                data-testid="contact-email"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(212,175,55,0.12)', color: 'var(--aurem-heading)' }}
              />
              <input
                type="text"
                placeholder="Subject"
                value={contactForm.subject}
                onChange={(e) => setContactForm(p => ({ ...p, subject: e.target.value }))}
                data-testid="contact-subject"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(212,175,55,0.12)', color: 'var(--aurem-heading)' }}
              />
              <textarea
                placeholder="How can we help? *"
                required
                rows={4}
                value={contactForm.message}
                onChange={(e) => setContactForm(p => ({ ...p, message: e.target.value }))}
                data-testid="contact-message"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none resize-none"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(212,175,55,0.12)', color: 'var(--aurem-heading)' }}
              />
              <button
                type="submit"
                disabled={sending}
                data-testid="contact-submit"
                className="w-full py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #B8962E)', color: '#050505' }}
              >
                {sending ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          </div>

          <div className="space-y-6">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Mail className="w-5 h-5" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
                <h2 className="text-lg font-semibold">Direct Contact</h2>
              </div>
              <div className="space-y-3">
                <a href="mailto:support@aurem.ai" data-testid="email-support" className="flex items-center gap-3 p-3 rounded-xl transition-colors hover:bg-white/[0.02]" style={{ border: '1px solid rgba(212,175,55,0.08)' }}>
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(212,175,55,0.1)' }}>
                    <Mail className="w-4 h-4" style={{ color: 'var(--aurem-accent)' }} />
                  </div>
                  <div>
                    <div className="text-sm font-medium">General Support</div>
                    <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>support@aurem.ai</div>
                  </div>
                </a>
                <a href="mailto:privacy@aurem.ai" className="flex items-center gap-3 p-3 rounded-xl transition-colors hover:bg-white/[0.02]" style={{ border: '1px solid rgba(212,175,55,0.08)' }}>
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(61,58,57,0.25)' }}>
                    <Mail className="w-4 h-4 text-green-500" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">Privacy & GDPR</div>
                    <div className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>privacy@aurem.ai</div>
                  </div>
                </a>
              </div>
            </div>

            <div className="p-4 rounded-xl" style={{ background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.12)' }}>
              <h3 className="text-sm font-semibold mb-2">Quick Links</h3>
              <div className="space-y-2">
                <Link to="/privacy" className="flex items-center gap-2 text-xs hover:underline" style={{ color: 'var(--aurem-body-secondary)' }}>
                  <ExternalLink className="w-3 h-3" /> Privacy Policy
                </Link>
                <Link to="/terms" className="flex items-center gap-2 text-xs hover:underline" style={{ color: 'var(--aurem-body-secondary)' }}>
                  <ExternalLink className="w-3 h-3" /> Terms of Service
                </Link>
              </div>
            </div>

            <div className="p-4 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.3)' }}>
              <h3 className="text-sm font-semibold mb-1">Response Time</h3>
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>
                We typically respond within 24 hours during business days. Priority support is available on Professional and Enterprise plans.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
