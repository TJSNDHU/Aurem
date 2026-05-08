import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Mail, MapPin, Send, CheckCircle2 } from 'lucide-react';

const EMAIL = 'ora@aurem.live';
const ENTITY = 'Polaris Built Inc.';
const ADDRESS = '7221 Sigsbee Drive, Mississauga, ON L4T 3L6, Canada';
const API = process.env.REACT_APP_BACKEND_URL || '';

export default function ContactPage() {
  const [params] = useSearchParams();
  const initialTopic = (params.get('topic') || 'quote').toLowerCase();
  const [topic, setTopic] = useState(
    ['quote', 'audit', 'support', 'partnership'].includes(initialTopic) ? initialTopic : 'quote'
  );
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [website, setWebsite] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  // If landing page prefilled a website via query param
  useEffect(() => {
    const w = params.get('website');
    if (w) setWebsite(w);
  }, [params]);

  const topicLabel = {
    quote: 'Website Repair Quote',
    audit: 'Free Audit Request',
    support: 'Support Request',
    partnership: 'Partnership / Other',
  }[topic] || 'General Enquiry';

  const mailtoHref = React.useMemo(() => {
    const body = [
      `Topic: ${topicLabel}`,
      `Name: ${name || '-'}`,
      `Email: ${email || '-'}`,
      `Website: ${website || '-'}`,
      '',
      'Message:',
      message || '-',
    ].join('\n');
    return `mailto:${EMAIL}?subject=${encodeURIComponent('[AUREM] ' + topicLabel)}&body=${encodeURIComponent(body)}`;
  }, [topicLabel, name, email, website, message]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/public/audit-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          email,
          website: website || null,
          message: message || null,
          topic,
          source: 'contact_form',
        }),
      });
      if (res.ok) {
        setSuccess(true);
      } else {
        // Fallback to mailto if backend rejects
        const data = await res.json().catch(() => ({}));
        setError(data.detail || 'Could not save. Opening your email client as fallback…');
        setTimeout(() => {
          window.location.href = mailtoHref;
        }, 1200);
      }
    } catch (err) {
      setError('Network issue. Opening your email client as fallback…');
      setTimeout(() => {
        window.location.href = mailtoHref;
      }, 1200);
    } finally {
      setSubmitting(false);
    }
  }

  const inputStyle = {
    width: '100%',
    padding: '12px 14px',
    borderRadius: 10,
    background: 'rgba(15,18,28,0.72)',
    border: '1px solid rgba(212,175,55,0.22)',
    color: '#E8E0D0',
    fontFamily: "'Jost', sans-serif",
    fontSize: 14,
    outline: 'none',
  };

  const labelStyle = {
    display: 'block',
    fontSize: 12,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    color: 'rgba(232,224,208,0.6)',
    marginBottom: 6,
  };

  return (
    <div
      className="min-h-screen relative"
      style={{
        color: 'var(--aurem-heading, #F4F4F4)',
        background: '#050505',
      }}
    >
      {/* ═══ Circuit-board background image (fixed, full-bleed) ═══ */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          backgroundImage: "url('/assets/aurem-circuit-bg.jpg')",
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          filter: 'brightness(0.88) saturate(1.05)',
        }}
      />
      {/* gradient veil for legibility — darker at center where content sits */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          background:
            'radial-gradient(ellipse at 60% 50%, rgba(5,5,8,0.88) 0%, rgba(5,5,8,0.65) 40%, rgba(5,5,8,0.35) 100%), linear-gradient(180deg, rgba(5,5,8,0.45) 0%, rgba(5,5,8,0.15) 50%, rgba(5,5,8,0.7) 100%)',
          pointerEvents: 'none',
        }}
      />

      {/* ═══ Floating-glass shimmer keyframes (page-local) ═══ */}
      <style>{`
        @keyframes auremShimmerContact {
          0%   { transform: translateX(-140%) rotate(10deg); opacity: 0; }
          18%  { opacity: 0.55; }
          55%  { opacity: 0.75; }
          100% { transform: translateX(140%) rotate(10deg); opacity: 0; }
        }
        @keyframes auremBreatheContact {
          0%,100% { box-shadow: 0 24px 60px rgba(0,0,0,0.55), 0 0 0 1px rgba(212,175,55,0.16) inset, 0 0 36px rgba(212,175,55,0.05); }
          50%     { box-shadow: 0 28px 70px rgba(0,0,0,0.6),  0 0 0 1px rgba(212,175,55,0.26) inset, 0 0 56px rgba(212,175,55,0.10); }
        }
        .aurem-floating-card {
          position: relative;
          overflow: hidden;
          border-radius: 18px;
          background: linear-gradient(155deg, rgba(15,18,28,0.62) 0%, rgba(10,10,14,0.56) 55%, rgba(18,14,10,0.62) 100%);
          backdrop-filter: blur(24px) saturate(155%);
          -webkit-backdrop-filter: blur(24px) saturate(155%);
          border: 1px solid rgba(212,175,55,0.22);
          animation: auremBreatheContact 6s ease-in-out infinite;
          isolation: isolate;
        }
        .aurem-floating-card::before {
          content: '';
          position: absolute;
          top: -60%;
          left: 0;
          width: 55%;
          height: 220%;
          pointer-events: none;
          background: linear-gradient(
            110deg,
            transparent 0%,
            rgba(212,175,55,0.00) 35%,
            rgba(247,231,206,0.20) 50%,
            rgba(212,175,55,0.07) 60%,
            transparent 80%
          );
          filter: blur(14px);
          animation: auremShimmerContact 5.8s ease-in-out infinite;
          animation-delay: 0.6s;
          z-index: 0;
        }
        .aurem-floating-card::after {
          content: '';
          position: absolute;
          inset: 0;
          pointer-events: none;
          border-radius: inherit;
          background:
            radial-gradient(120% 60% at 50% 0%, rgba(212,175,55,0.10) 0%, transparent 55%),
            radial-gradient(80% 50% at 10% 100%, rgba(247,231,206,0.05) 0%, transparent 60%);
          z-index: 0;
        }
        .aurem-floating-card > * { position: relative; z-index: 1; }
        .aurem-floating-card input:focus,
        .aurem-floating-card select:focus,
        .aurem-floating-card textarea:focus {
          box-shadow: 0 0 0 2px rgba(212,175,55,0.35), inset 0 0 0 1px rgba(212,175,55,0.40) !important;
          border-color: rgba(212,175,55,0.55) !important;
          outline: none !important;
        }
      `}</style>

      <div className="max-w-4xl mx-auto px-6 py-12 relative" style={{ zIndex: 1 }}>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm mb-8 hover:opacity-80 transition-opacity"
          style={{ color: 'var(--aurem-accent, #D4AF37)' }}
          data-testid="contact-back-link"
        >
          <ArrowLeft className="w-4 h-4" /> Back to AUREM
        </Link>

        <div className="flex items-center gap-3 mb-3">
          <Mail className="w-8 h-8" style={{ color: 'var(--aurem-accent, #D4AF37)' }} />
          <h1 className="text-3xl font-bold tracking-tight" data-testid="contact-title">
            {topic === 'audit' ? 'Get a Free Website Audit' : 'Talk to AUREM'}
          </h1>
        </div>

        <p className="mb-10 text-sm" style={{ color: 'var(--aurem-body-secondary, #888)', maxWidth: 620 }}>
          {topic === 'audit'
            ? 'Drop your website URL — our AI agent ORA will run a 60-point health scan (SEO, schema, performance, compliance) and email the report within 2 business hours. No credit card required.'
            : 'Send us a note — we reply within 2 business hours on weekdays.'}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-8">
          {success ? (
            <div
              className="md:col-span-3 aurem-floating-card"
              data-testid="contact-success"
              style={{ padding: 32, textAlign: 'center' }}
            >
              <CheckCircle2 className="w-14 h-14 mx-auto mb-4" style={{ color: '#D4AF37' }} />
              <h2 className="text-2xl font-bold mb-3" style={{ color: '#F4F4F4' }}>Request received</h2>
              <p className="text-sm mb-6" style={{ color: '#C9C9D1' }}>
                Thank you, <strong>{name || 'friend'}</strong>. We've logged your {topicLabel.toLowerCase()} and ORA is already looking into it.
                You'll hear from us at <strong style={{ color: '#D4AF37' }}>{email}</strong> within 2 business hours.
              </p>
              <Link
                to="/"
                className="inline-block px-6 py-3 rounded-xl text-sm font-medium transition-all hover:opacity-90"
                style={{ background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)', color: '#0A0A0F' }}
              >
                Back to Home
              </Link>
            </div>
          ) : (
            <form
              className="md:col-span-3 space-y-5"
              data-testid="contact-form"
              onSubmit={handleSubmit}
            >
              <div className="aurem-floating-card" style={{ padding: 24 }}>
                <div className="mb-5">
                  <label style={labelStyle}>I need help with</label>
                  <select
                    data-testid="contact-topic"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    style={inputStyle}
                  >
                    <option value="quote">Website Repair Quote</option>
                    <option value="audit">Free Audit Request</option>
                    <option value="support">Support for Existing Account</option>
                    <option value="partnership">Partnership / Other</option>
                  </select>
                </div>

                <div className="mb-5">
                  <label style={labelStyle}>Your Name</label>
                  <input
                    data-testid="contact-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    placeholder="Jane Doe"
                    style={inputStyle}
                  />
                </div>

                <div className="mb-5">
                  <label style={labelStyle}>Email</label>
                  <input
                    data-testid="contact-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="you@company.com"
                    style={inputStyle}
                  />
                </div>

                <div className="mb-5">
                  <label style={labelStyle}>{topic === 'audit' ? 'Website URL' : 'Website (optional)'}</label>
                  <input
                    data-testid="contact-website"
                    type="text"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                    required={topic === 'audit'}
                    placeholder="https://yourstore.myshopify.com"
                    style={inputStyle}
                  />
                </div>

                <div className="mb-6">
                  <label style={labelStyle}>{topic === 'audit' ? 'What should ORA focus on? (optional)' : 'How can we help?'}</label>
                  <textarea
                    data-testid="contact-message"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    rows={5}
                    placeholder={topic === 'audit' ? 'e.g. My mobile speed is slow, checkout is broken, SEO is dropping…' : "Describe what you'd like us to repair or audit…"}
                    style={{ ...inputStyle, resize: 'vertical', minHeight: 120 }}
                  />
                </div>

                {error && (
                  <p
                    className="text-xs mb-4"
                    data-testid="contact-error"
                    style={{ color: '#FF8A3D' }}
                  >
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  data-testid="contact-submit"
                  className="inline-flex items-center gap-2 justify-center w-full px-6 py-3 rounded-xl font-medium transition-all hover:opacity-90 disabled:opacity-60"
                  style={{
                    background: 'linear-gradient(135deg, #D4AF37 0%, #FF8A3D 100%)',
                    color: '#0A0A0F',
                    fontSize: 14,
                    letterSpacing: '0.04em',
                    boxShadow: '0 10px 30px rgba(212,175,55,0.25)',
                  }}
                >
                  <Send className="w-4 h-4" /> {submitting ? 'Sending…' : 'Send Message'}
                </button>

                <p className="text-xs mt-3 text-center" style={{ color: 'rgba(232,224,208,0.45)' }}>
                  Prefer to write directly?{' '}
                  <a
                    href={`mailto:${EMAIL}`}
                    data-testid="contact-direct-email"
                    style={{ color: 'var(--aurem-accent, #D4AF37)' }}
                  >
                    {EMAIL}
                  </a>
                </p>
              </div>
            </form>
          )}

          <aside className="md:col-span-2 space-y-6" data-testid="contact-details">
            <div className="aurem-floating-card" style={{ padding: 22 }}>
              <h3
                className="text-xs mb-3"
                style={{
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase',
                  color: 'var(--aurem-accent, #D4AF37)',
                }}
              >
                Direct Line
              </h3>
              <a
                href={`mailto:${EMAIL}`}
                className="text-base block mb-4 hover:opacity-80"
                style={{ color: '#F4F4F4', fontWeight: 600 }}
              >
                {EMAIL}
              </a>
              <p className="text-xs" style={{ color: 'rgba(232,224,208,0.55)' }}>
                Monitored by ORA + human team · 2-business-hour response target
              </p>
            </div>

            <div className="aurem-floating-card" style={{ padding: 22 }}>
              <h3
                className="text-xs mb-3"
                style={{
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase',
                  color: 'var(--aurem-accent, #D4AF37)',
                }}
              >
                Registered Office
              </h3>
              <div className="flex items-start gap-2">
                <MapPin
                  className="w-4 h-4 mt-1 flex-shrink-0"
                  style={{ color: 'rgba(212,175,55,0.7)' }}
                />
                <p className="text-sm leading-relaxed" style={{ color: '#E8E0D0' }}>
                  <strong>{ENTITY}</strong>
                  <br />
                  {ADDRESS}
                </p>
              </div>
            </div>

            <div className="text-xs space-y-1" style={{ color: 'rgba(232,224,208,0.55)' }}>
              <p>
                <Link to="/terms" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
                  Terms
                </Link>{' '}
                ·{' '}
                <Link to="/privacy" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
                  Privacy
                </Link>{' '}
                ·{' '}
                <Link to="/refund" style={{ color: 'var(--aurem-accent, #D4AF37)' }}>
                  Refund
                </Link>
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
