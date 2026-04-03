import React, { useEffect } from 'react';
import { Helmet } from 'react-helmet-async';

const C = {
  dark: '#1A0F14',
  surface: '#221318',
  surface2: '#2D1A20',
  border: '#3A2028',
  pink: '#F8A5B8',
  pinkDim: '#D4788A',
  text: '#F5EAF0',
  textDim: '#9A7880',
  textMuted: '#5A3840',
  gold: '#C89040',
  green: '#5AB878',
};

const FD = "'Cormorant Garamond', Georgia, serif";
const FS = "'Inter', system-ui, sans-serif";

export default function FindYourRitualPage() {
  useEffect(() => {
    // Scroll-triggered reveals
    const observer = new IntersectionObserver(
      (entries) => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); }),
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <Helmet>
        <title>Find Your PDRN Protocol — ReRoots</title>
        <meta name="description" content="87 seconds. Discover exactly which PDRN ritual your skin needs. Backed by biotech science. Made in Canada." />
        <meta property="og:title" content="Find Your PDRN Protocol — ReRoots" />
        <meta property="og:description" content="87 seconds. Discover exactly which PDRN ritual your skin needs." />
      </Helmet>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400;1,500&family=Inter:wght@300;400;500&display=swap');
        
        .find-ritual-page { background: ${C.dark}; color: ${C.text}; font-family: ${FS}; min-height: 100vh; }
        .find-ritual-page * { box-sizing: border-box; margin: 0; padding: 0; }
        
        .glow-bg {
          position: fixed; top: -20vh; left: 50%; transform: translateX(-50%);
          width: 80vw; height: 80vw; max-width: 700px; max-height: 700px;
          background: radial-gradient(circle, rgba(248,165,184,0.08) 0%, transparent 70%);
          pointer-events: none; z-index: 0;
        }
        
        .fr-nav {
          padding: 1.5rem 2rem; display: flex; align-items: center; justify-content: space-between;
          border-bottom: 1px solid ${C.border}; position: relative; z-index: 1;
        }
        .fr-logo { font-family: ${FD}; font-size: 1.4rem; font-weight: 300; letter-spacing: 0.28em; color: ${C.text}; text-decoration: none; }
        .fr-logo span { color: ${C.pink}; }
        .fr-badge { font-size: 0.62rem; letter-spacing: 0.15em; color: ${C.textDim}; text-transform: uppercase; }
        
        .fr-hero {
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          padding: 5rem 1.5rem 4rem; text-align: center; max-width: 700px; margin: 0 auto; position: relative; z-index: 1;
        }
        
        .fr-eyebrow {
          display: inline-flex; align-items: center; gap: 0.5rem;
          font-size: 0.62rem; letter-spacing: 0.22em; text-transform: uppercase; color: ${C.pink}; font-weight: 500;
          margin-bottom: 2rem; padding: 0.4rem 1rem; border: 1px solid rgba(248,165,184,0.2);
          border-radius: 20px; background: rgba(248,165,184,0.05); animation: fadeUp 0.6s ease both;
        }
        .fr-eyebrow::before {
          content: ''; width: 5px; height: 5px; border-radius: 50%; background: ${C.pink}; animation: pulse 2s infinite;
        }
        
        .fr-hero h1 {
          font-family: ${FD}; font-size: clamp(2.8rem, 8vw, 5rem); font-weight: 300;
          line-height: 1.1; letter-spacing: 0.02em; color: ${C.text}; margin-bottom: 1.5rem; animation: fadeUp 0.6s 0.1s ease both;
        }
        .fr-hero h1 em { font-style: italic; color: ${C.pink}; }
        
        .fr-subtitle {
          font-size: 1rem; color: ${C.textDim}; line-height: 1.7; max-width: 460px;
          margin: 0 auto 2.5rem; font-weight: 300; animation: fadeUp 0.6s 0.2s ease both;
        }
        
        .fr-cta-wrap { animation: fadeUp 0.6s 0.3s ease both; margin-bottom: 3rem; }
        .fr-btn-cta {
          display: inline-flex; align-items: center; gap: 0.75rem; background: ${C.pink}; color: #1A0810;
          text-decoration: none; padding: 1.1rem 2.5rem; border-radius: 50px; font-family: ${FS};
          font-size: 0.9rem; font-weight: 600; letter-spacing: 0.04em; transition: all 0.25s;
          box-shadow: 0 8px 32px rgba(248,165,184,0.25); border: none; cursor: pointer;
        }
        .fr-btn-cta:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(248,165,184,0.35); }
        .fr-cta-note { font-size: 0.7rem; color: ${C.textMuted}; margin-top: 0.85rem; letter-spacing: 0.08em; }
        
        .fr-trust-row {
          display: flex; align-items: center; justify-content: center; gap: 2rem; flex-wrap: wrap;
          animation: fadeUp 0.6s 0.4s ease both;
        }
        .fr-trust-item { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; }
        .fr-trust-num { font-family: ${FD}; font-size: 1.8rem; font-weight: 300; color: ${C.pink}; line-height: 1; }
        .fr-trust-label { font-size: 0.6rem; letter-spacing: 0.15em; text-transform: uppercase; color: ${C.textMuted}; }
        .fr-trust-divider { width: 1px; height: 32px; background: ${C.border}; }
        
        .fr-section { padding: 5rem 1.5rem; max-width: 900px; margin: 0 auto; position: relative; z-index: 1; }
        .fr-section-label { text-align: center; font-size: 0.6rem; letter-spacing: 0.22em; text-transform: uppercase; color: ${C.textMuted}; margin-bottom: 3rem; }
        
        .fr-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
        .fr-step {
          text-align: center; padding: 2rem 1.5rem; background: ${C.surface}; border: 1px solid ${C.border};
          border-radius: 16px; transition: border-color 0.2s;
        }
        .fr-step:hover { border-color: rgba(248,165,184,0.3); }
        .fr-step-num { font-family: ${FD}; font-size: 3rem; font-weight: 300; color: rgba(248,165,184,0.15); line-height: 1; margin-bottom: 1rem; }
        .fr-step-icon { font-size: 1.5rem; margin-bottom: 0.75rem; display: block; }
        .fr-step h3 { font-family: ${FD}; font-size: 1.1rem; font-weight: 400; color: ${C.text}; margin-bottom: 0.5rem; }
        .fr-step p { font-size: 0.78rem; color: ${C.textDim}; line-height: 1.7; }
        
        .fr-science {
          padding: 4rem 1.5rem; background: ${C.surface}; border-top: 1px solid ${C.border};
          border-bottom: 1px solid ${C.border}; position: relative; z-index: 1;
        }
        .fr-science-inner { max-width: 900px; margin: 0 auto; }
        .fr-ingredients { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.85rem; margin-top: 2rem; }
        .fr-ing-card {
          background: ${C.surface2}; border: 1px solid ${C.border}; border-radius: 10px;
          padding: 1rem 1.1rem; transition: all 0.2s;
        }
        .fr-ing-card:hover { border-color: rgba(248,165,184,0.25); transform: translateY(-2px); }
        .fr-ing-name { font-size: 0.62rem; letter-spacing: 0.15em; text-transform: uppercase; color: ${C.pink}; font-weight: 500; margin-bottom: 0.3rem; }
        .fr-ing-conc { font-family: ${FD}; font-size: 1.1rem; color: ${C.text}; font-weight: 300; margin-bottom: 0.3rem; }
        .fr-ing-benefit { font-size: 0.65rem; color: ${C.textDim}; line-height: 1.5; }
        
        .fr-proof { padding: 5rem 1.5rem; max-width: 800px; margin: 0 auto; text-align: center; position: relative; z-index: 1; }
        .fr-proof blockquote {
          font-family: ${FD}; font-size: clamp(1.3rem, 3vw, 1.8rem); font-weight: 300;
          font-style: italic; color: ${C.text}; line-height: 1.6; margin-bottom: 1.25rem;
        }
        .fr-proof blockquote::before { content: '"'; color: ${C.pink}; }
        .fr-proof blockquote::after { content: '"'; color: ${C.pink}; }
        .fr-quote-attr { font-size: 0.7rem; color: ${C.textMuted}; letter-spacing: 0.15em; text-transform: uppercase; }
        
        .fr-bottom-cta {
          padding: 5rem 1.5rem; text-align: center; border-top: 1px solid ${C.border};
          background: linear-gradient(to bottom, ${C.dark}, ${C.surface}); position: relative; z-index: 1;
        }
        .fr-bottom-cta h2 {
          font-family: ${FD}; font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 300;
          color: ${C.text}; margin-bottom: 1rem;
        }
        .fr-bottom-cta p {
          font-size: 0.9rem; color: ${C.textDim}; margin-bottom: 2.5rem;
          max-width: 400px; margin-left: auto; margin-right: auto; line-height: 1.7;
        }
        
        .fr-footer {
          padding: 1.5rem 2rem; border-top: 1px solid ${C.border}; display: flex;
          align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem;
          position: relative; z-index: 1;
        }
        .fr-footer p { font-size: 0.65rem; color: ${C.textMuted}; letter-spacing: 0.08em; }
        .fr-footer a { color: ${C.textMuted}; text-decoration: none; transition: color 0.15s; margin-left: 1.5rem; }
        .fr-footer a:hover { color: ${C.pink}; }
        
        .reveal { opacity: 0; transform: translateY(16px); transition: opacity 0.6s ease, transform 0.6s ease; }
        .reveal.visible { opacity: 1; transform: translateY(0); }
        
        @keyframes fadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        
        @media (max-width: 640px) {
          .fr-nav { padding: 1.25rem 1rem; }
          .fr-hero { padding: 3.5rem 1.25rem 3rem; }
          .fr-steps { grid-template-columns: 1fr; gap: 0.75rem; }
          .fr-trust-row { gap: 1.25rem; }
          .fr-trust-divider { display: none; }
          .fr-footer { flex-direction: column; align-items: flex-start; }
        }
      `}</style>

      <div className="find-ritual-page">
        <div className="glow-bg" />
        
        {/* Nav */}
        <nav className="fr-nav">
          <a href="/" className="fr-logo">RE<span>ROOTS</span></a>
          <span className="fr-badge">Biotech Skincare · Canada</span>
        </nav>

        {/* Hero */}
        <section className="fr-hero">
          <div className="fr-eyebrow">Free Skin Protocol Quiz</div>
          <h1>Discover your<br/><em>PDRN ritual</em></h1>
          <p className="fr-subtitle">
            Six questions. Eighty-seven seconds. A personalised biotech protocol matched to your skin — with clinical-grade actives, not guesswork.
          </p>
          <div className="fr-cta-wrap">
            <a href="/quiz" className="fr-btn-cta" data-testid="find-ritual-cta">
              Find My Protocol <span>→</span>
            </a>
            <p className="fr-cta-note">Takes 87 seconds · Free · No commitment</p>
          </div>
          <div className="fr-trust-row">
            {[
              { num: '87%', label: 'Match accuracy' },
              { num: '37%', label: 'Active concentration' },
              { num: '28', label: 'Day protocol' },
              { num: '2%', label: 'PDRN concentration' },
            ].map((t, i) => (
              <React.Fragment key={t.label}>
                {i > 0 && <div className="fr-trust-divider" />}
                <div className="fr-trust-item">
                  <span className="fr-trust-num">{t.num}</span>
                  <span className="fr-trust-label">{t.label}</span>
                </div>
              </React.Fragment>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section className="fr-section">
          <p className="fr-section-label reveal">How it works</p>
          <div className="fr-steps">
            {[
              { num: '01', icon: '🧬', title: 'Answer 6 questions', desc: 'We ask about your skin concerns, age, sensitivities, and current routine. No fluff — just what matters for PDRN matching.' },
              { num: '02', icon: '⚗️', title: 'We match your actives', desc: 'Our algorithm matches your profile to the right PDRN + TXA + Argireline combination and builds your 28-day protocol.' },
              { num: '03', icon: '📧', title: 'Get your protocol', desc: 'Your full ritual guide — ingredient science, application method, what to expect on Day 7, Day 14, Day 21 — sent to your inbox.' },
            ].map((s, i) => (
              <div key={s.num} className="fr-step reveal" style={{ transitionDelay: `${i * 0.05}s` }}>
                <div className="fr-step-num">{s.num}</div>
                <span className="fr-step-icon">{s.icon}</span>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Science / ingredients */}
        <section className="fr-science">
          <div className="fr-science-inner">
            <p className="fr-section-label reveal" style={{ marginBottom: '.75rem' }}>What's inside</p>
            <p className="reveal" style={{ textAlign: 'center', fontSize: '.78rem', color: C.textDim, maxWidth: 440, margin: '0 auto', lineHeight: 1.7 }}>
              Clinical-grade actives. 37.25% total concentration. Health Canada compliant.
            </p>
            <div className="fr-ingredients">
              {[
                { name: 'PDRN', conc: '2.0%', benefit: 'Visibly supports cellular renewal via adenosine A2A receptor activation' },
                { name: 'Tranexamic Acid', conc: '5.0%', benefit: 'Helps visibly brighten the appearance of skin tone and dark spots' },
                { name: 'Argireline®', conc: '17%', benefit: 'Visibly softens expression lines — 3× standard cosmetic dose' },
                { name: 'Sodium Hyaluronate', conc: 'Multi-weight', benefit: 'Instantly plumps the look of skin — synergistic with PDRN' },
                { name: 'Panax Ginseng Berry', conc: 'Extract', benefit: 'Supports visibly energised, luminous-looking skin appearance' },
              ].map((ing, i) => (
                <div key={ing.name} className="fr-ing-card reveal" style={{ transitionDelay: `${i * 0.05}s` }}>
                  <div className="fr-ing-name">{ing.name}</div>
                  <div className="fr-ing-conc">{ing.conc}</div>
                  <div className="fr-ing-benefit">{ing.benefit}</div>
                </div>
              ))}
            </div>
            <p className="reveal" style={{ textAlign: 'center', fontSize: '.6rem', color: C.textMuted, marginTop: '1.5rem', letterSpacing: '.08em' }}>
              Results may vary. For cosmetic use only. Health Canada Cosmetic Regulations compliant.
            </p>
          </div>
        </section>

        {/* Social proof */}
        <section className="fr-proof">
          <blockquote className="reveal">
            Day 21 — I genuinely can't believe the difference. My skin looks like it did 5 years ago.
          </blockquote>
          <p className="fr-quote-attr reveal">ReRoots Customer · 28-Day PDRN Protocol</p>
          
          <div className="reveal" style={{ marginTop: '3rem', display: 'flex', justifyContent: 'center', gap: '2.5rem', flexWrap: 'wrap' }}>
            {[
              { val: '28 days', label: 'Full protocol' },
              { val: 'Day 21', label: 'Peak visible results' },
              { val: 'Canada', label: 'Made here' },
            ].map((s, i) => (
              <React.Fragment key={s.label}>
                {i > 0 && <div style={{ width: 1, background: C.border }} />}
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontFamily: FD, fontSize: '2rem', fontWeight: 300, color: C.pink }}>{s.val}</div>
                  <div style={{ fontSize: '.6rem', letterSpacing: '.15em', textTransform: 'uppercase', color: C.textMuted, marginTop: '.3rem' }}>{s.label}</div>
                </div>
              </React.Fragment>
            ))}
          </div>
        </section>

        {/* Bottom CTA */}
        <section className="fr-bottom-cta">
          <h2 className="reveal">Your skin is<br/><em style={{ fontStyle: 'italic', color: C.pink }}>waiting for this.</em></h2>
          <p className="reveal">87 seconds between you and a protocol built for exactly your skin. No generic routines. No guessing. Just science.</p>
          <div className="reveal">
            <a href="/quiz" className="fr-btn-cta" style={{ fontSize: '1rem', padding: '1.25rem 3rem' }}>
              Start the Quiz — It's Free <span>→</span>
            </a>
            <p className="fr-cta-note" style={{ marginTop: '1rem', fontSize: '.68rem' }}>Takes 87 seconds · Get your protocol instantly</p>
          </div>
        </section>

        {/* Footer */}
        <footer className="fr-footer">
          <p>© 2026 Reroots Aesthetics Inc. · Toronto, Canada</p>
          <div>
            <a href="/">Shop</a>
            <a href="/quiz">Take the Quiz</a>
            <a href="https://www.instagram.com/reroots.ca">Instagram</a>
            <a href="/pages/privacy">Privacy</a>
          </div>
        </footer>
      </div>
    </>
  );
}
