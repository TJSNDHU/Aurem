/**
 * AUREM Legal Pages — Policy Display + Index
 * Company: Polaris Built Inc.
 * Clean, minimal, dark theme. No sidebar.
 */
import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Target, FileText, Shield, Scale, CreditCard, Cookie, AlertTriangle, ArrowLeft, ExternalLink } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const POLICY_META = {
  'terms': { icon: Scale, label: 'Terms of Service', color: '#D4AF37' },
  'privacy': { icon: Shield, label: 'Privacy Policy', color: '#3B82F6' },
  'acceptable-use': { icon: AlertTriangle, label: 'Acceptable Use Policy', color: '#F59E0B' },
  'economic-intelligence': { icon: FileText, label: 'Economic Intelligence Disclaimer', color: '#22C55E' },
  'refunds': { icon: CreditCard, label: 'Refund Policy', color: '#A855F7' },
  'cookies': { icon: Cookie, label: 'Cookie Policy', color: '#EC4899' },
};

const LegalHeader = () => (
  <header className="py-6 px-8 border-b border-white/5">
    <div className="max-w-4xl mx-auto flex items-center justify-between">
      <Link to="/" className="flex items-center gap-3">
        <div className="size-8 rounded-md flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)' }}>
          <Target className="size-4 text-[#050507]" />
        </div>
        <span className="text-sm tracking-[0.2em]" style={{ fontFamily: "'Cinzel', 'Playfair Display', serif" }}>AUREM</span>
      </Link>
      <Link to="/legal" className="text-[10px] tracking-wider text-[#666] hover:text-[#D4AF37] transition-colors" data-testid="legal-index-link">
        ALL POLICIES
      </Link>
    </div>
  </header>
);

const LegalFooter = () => (
  <footer className="py-8 px-8 border-t border-white/5 mt-12">
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-wrap items-center justify-center gap-4 text-[10px] text-[#444] tracking-wider mb-4">
        <Link to="/legal/terms" className="hover:text-[#D4AF37] transition-colors">Terms</Link>
        <span className="text-[#222]">|</span>
        <Link to="/legal/privacy" className="hover:text-[#D4AF37] transition-colors">Privacy</Link>
        <span className="text-[#222]">|</span>
        <Link to="/legal/acceptable-use" className="hover:text-[#D4AF37] transition-colors">Acceptable Use</Link>
        <span className="text-[#222]">|</span>
        <Link to="/legal/cookies" className="hover:text-[#D4AF37] transition-colors">Cookies</Link>
        <span className="text-[#222]">|</span>
        <Link to="/legal/economic-intelligence" className="hover:text-[#D4AF37] transition-colors">Economic Disclaimer</Link>
      </div>
      <p className="text-center text-[10px] text-[#333]" data-testid="legal-footer-copyright">
        &copy; 2026 Polaris Built Inc. Mississauga, Ontario, Canada. All rights reserved.
      </p>
    </div>
  </footer>
);

// ─── Legal Index Page (/legal) ───
export const LegalIndex = () => {
  const [docs, setDocs] = useState([]);

  useEffect(() => {
    fetch(`${API_URL}/api/legal/documents`)
      .then(r => r.json())
      .then(d => setDocs(d.documents || []))
      .catch(() => {});
  }, []);

  const slugs = ['terms', 'privacy', 'acceptable-use', 'economic-intelligence', 'refunds', 'cookies'];

  return (
    <div className="min-h-screen" style={{ background: '#050507', color: '#E8E6E1', fontFamily: "'Inter', sans-serif" }} data-testid="legal-index-page">
      <LegalHeader />
      <main className="max-w-4xl mx-auto px-8 py-12">
        <h1 className="text-2xl font-bold mb-2" style={{ fontFamily: "'Cinzel', 'Playfair Display', serif", color: '#D4AF37' }}
          data-testid="legal-index-title">
          Legal & Compliance
        </h1>
        <p className="text-sm text-[#666] mb-10">Polaris Built Inc., Governing policies for the AUREM AI Platform</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {slugs.map(slug => {
            const meta = POLICY_META[slug] || {};
            const Icon = meta.icon || FileText;
            const doc = docs.find(d => d.slug === slug);
            return (
              <Link
                key={slug}
                to={`/legal/${slug}`}
                data-testid={`legal-card-${slug}`}
                className="group p-6 rounded-xl border transition-all hover:scale-[1.01]"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <div className="flex items-start gap-4">
                  <div className="size-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{
                    background: `${meta.color}10`,
                    border: `1px solid ${meta.color}20`,
                  }}>
                    <Icon className="size-5" style={{ color: meta.color }} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold mb-1 group-hover:text-[#D4AF37] transition-colors" style={{ color: '#E8E6E1' }}>
                      {doc?.title || meta.label}
                    </h3>
                    <p className="text-[10px] text-[#555]">
                      {doc?.effective_date ? `Effective: ${doc.effective_date}` : ''} {doc?.version ? `| v${doc.version}` : ''}
                    </p>
                    <div className="flex items-center gap-1 mt-2 text-[9px] text-[#444] group-hover:text-[#D4AF37] transition-colors">
                      <span>Read full policy</span>
                      <ExternalLink className="size-2.5" />
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </main>
      <LegalFooter />
    </div>
  );
};

// ─── Individual Legal Page (/legal/:slug) ───
export const LegalDocument = () => {
  const { slug } = useParams();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/legal/${slug}`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { setDoc(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [slug]);

  const meta = POLICY_META[slug] || {};

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#050507' }}>
        <div className="animate-spin size-6 border-2 border-[#D4AF37] border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#050507', color: '#E8E6E1' }}>
        <div className="text-center">
          <h2 className="text-lg font-bold mb-2">Document not found</h2>
          <Link to="/legal" className="text-[#D4AF37] text-sm">Back to Legal Index</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: '#050507', color: '#E8E6E1', fontFamily: "'Inter', sans-serif" }}
      data-testid={`legal-page-${slug}`}>
      <LegalHeader />
      <main className="max-w-3xl mx-auto px-8 py-12">
        <Link to="/legal" className="inline-flex items-center gap-1.5 text-[10px] text-[#555] hover:text-[#D4AF37] transition-colors mb-8 tracking-wider"
          data-testid="legal-back-link">
          <ArrowLeft className="size-3" /> ALL POLICIES
        </Link>

        <div className="mb-8">
          <h1 className="text-xl font-bold mb-2" style={{ fontFamily: "'Cinzel', 'Playfair Display', serif", color: '#D4AF37' }}
            data-testid="legal-doc-title">
            {doc.title}
          </h1>
          <div className="flex items-center gap-4 text-[10px] text-[#555]">
            <span>Effective: {doc.effective_date}</span>
            <span>Version: {doc.version}</span>
            <span>{doc.company}</span>
            <span>{doc.jurisdiction}</span>
          </div>
        </div>

        <article className="prose prose-invert max-w-none" data-testid="legal-doc-content">
          {doc.content.split('\n\n').map((paragraph, i) => {
            const trimmed = paragraph.trim();
            if (!trimmed) return null;
            // Section headers (numbered or all-caps lines)
            if (/^\d+\.\s+[A-Z]/.test(trimmed) || /^[A-Z\s\u2014\u2013\-]{10,}$/.test(trimmed)) {
              return (
                <h2 key={i} className="text-sm font-bold mt-8 mb-3" style={{ color: '#C9A84C', fontFamily: "'Cinzel', serif" }}>
                  {trimmed}
                </h2>
              );
            }
            // Bullet points
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
              return (
                <ul key={i} className="space-y-1 mb-4">
                  {trimmed.split('\n').filter(l => l.trim()).map((line, li) => (
                    <li key={li} className="text-[13px] leading-relaxed text-[#999] flex items-start gap-2">
                      <span className="text-[#D4AF37] mt-1">&bull;</span>
                      <span>{line.replace(/^[-*]\s*/, '')}</span>
                    </li>
                  ))}
                </ul>
              );
            }
            return (
              <p key={i} className="text-[13px] leading-relaxed text-[#999] mb-4">
                {trimmed}
              </p>
            );
          })}
        </article>

        <div className="mt-12 pt-6 border-t border-white/5">
          <p className="text-[10px] text-[#444]">
            Last updated: {doc.last_updated?.slice(0, 10) || doc.effective_date} | {doc.company} | {doc.jurisdiction}
          </p>
        </div>
      </main>
      <LegalFooter />
    </div>
  );
};

export default LegalIndex;
