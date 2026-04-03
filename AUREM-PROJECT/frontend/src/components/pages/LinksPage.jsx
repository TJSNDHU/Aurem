import React from 'react';
import { Helmet } from 'react-helmet-async';

const C = {
  bg: '#100A0D',
  text: '#F0E8EC',
  textDim: '#7A6070',
  textMuted: '#4A3040',
  pink: '#F8A5B8',
  purple: '#9878C4',
  green: '#5CB87A',
  blue: '#6AA8C8',
  gold: '#D0A040',
  border: 'rgba(255,255,255,0.07)',
};

const FD = "'Cormorant Garamond', Georgia, serif";
const FS = "'DM Sans', 'Inter', system-ui, sans-serif";

const LINKS = [
  {
    featured: true,
    icon: '🧬',
    iconBg: 'rgba(248,165,184,0.12)',
    title: 'Find Your PDRN Protocol',
    badge: 'Free',
    badgeBg: C.pink,
    sub: '87-second quiz → personalised ritual matched to your skin',
    href: '/quiz',
  },
  { divider: 'Shop' },
  {
    icon: '⚗️',
    iconBg: 'rgba(92,184,122,0.1)',
    title: 'AURA-GEN PDRN+TXA+ARGIRELINE',
    sub: '$99 · 37.25% actives · 28-day protocol',
    href: '/products/aura-gen-pdrn',
  },
  {
    icon: '✨',
    iconBg: 'rgba(152,120,196,0.1)',
    title: 'Precision Duo Bundle',
    badge: '35% OFF',
    badgeBg: C.purple,
    sub: '$149 · was $228.99 · dual-system biotech',
    href: '/products/bundle',
  },
  { divider: 'Learn' },
  {
    icon: '🔭',
    iconBg: 'rgba(106,168,200,0.1)',
    title: 'Free Bio-Age Skin Scan',
    sub: "AI-powered facial analysis — discover your skin's bio-age",
    href: '/Bio-Age-Repair-Scan',
  },
  {
    icon: '📖',
    iconBg: 'rgba(212,160,64,0.1)',
    title: 'The PDRN Science',
    sub: 'What polynucleotides actually do to your skin — the research',
    href: '/science',
  },
  {
    icon: '📬',
    iconBg: 'rgba(248,165,184,0.08)',
    title: 'Join the Waitlist',
    sub: 'NAD+ Rose-Gen Eye Concentration — coming soon',
    href: '/waitlist',
  },
];

export default function LinksPage() {
  return (
    <>
      <Helmet>
        <title>ReRoots — @reroots.ca</title>
        <meta name="description" content="Premium PDRN biotech skincare. Canadian made. Find your protocol." />
      </Helmet>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=DM+Sans:wght@300;400;500&display=swap');
        
        .links-page { 
          font-family: ${FS}; background: ${C.bg}; color: ${C.text}; min-height: 100vh;
          display: flex; align-items: flex-start; justify-content: center; padding: 2.5rem 1rem 3rem;
        }
        .links-page * { box-sizing: border-box; margin: 0; padding: 0; }
        .links-page::before {
          content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
          background: radial-gradient(ellipse 60% 40% at 50% 0%, rgba(248,165,184,0.07) 0%, transparent 70%),
                      radial-gradient(ellipse 40% 60% at 80% 80%, rgba(155,120,196,0.04) 0%, transparent 60%);
        }
        
        .links-container { position: relative; z-index: 1; width: 100%; max-width: 420px; }
        
        .links-profile { text-align: center; margin-bottom: 2.5rem; animation: fadeUp 0.5s ease both; }
        .links-avatar {
          width: 72px; height: 72px; border-radius: 50%;
          background: linear-gradient(135deg, ${C.pink}, ${C.purple});
          display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem;
          font-family: ${FD}; font-size: 1.3rem; letter-spacing: 0.15em; color: #fff; font-weight: 300;
        }
        .links-brand { font-family: ${FD}; font-size: 1.5rem; font-weight: 300; letter-spacing: 0.25em; color: ${C.text}; margin-bottom: 0.3rem; }
        .links-brand span { color: ${C.pink}; }
        .links-handle { font-size: 0.7rem; color: ${C.textDim}; letter-spacing: 0.1em; margin-bottom: 0.6rem; }
        .links-bio { font-size: 0.78rem; color: #9A8090; line-height: 1.65; max-width: 300px; margin: 0 auto; }
        
        .links-list { display: flex; flex-direction: column; gap: 0.75rem; }
        
        .link-card {
          display: flex; align-items: center; gap: 1rem; padding: 1rem 1.25rem;
          background: rgba(255,255,255,0.04); border: 1px solid ${C.border}; border-radius: 14px;
          text-decoration: none; color: ${C.text}; transition: all 0.2s;
          animation: fadeUp 0.5s ease both;
        }
        .link-card:hover { background: rgba(248,165,184,0.07); border-color: rgba(248,165,184,0.2); transform: translateY(-1px); }
        .link-card.featured { background: rgba(248,165,184,0.09); border-color: rgba(248,165,184,0.25); }
        .link-card.featured .link-title { color: ${C.pink}; }
        
        .link-icon {
          width: 40px; height: 40px; border-radius: 10px;
          display: flex; align-items: center; justify-content: center;
          font-size: 1.1rem; flex-shrink: 0;
        }
        .link-text { flex: 1; }
        .link-title { font-size: 0.85rem; font-weight: 500; color: ${C.text}; margin-bottom: 0.15rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
        .link-badge {
          display: inline-block; font-size: 0.52rem; letter-spacing: 0.1em; text-transform: uppercase;
          color: #1A0810; padding: 0.12rem 0.45rem; border-radius: 10px; font-weight: 600;
        }
        .link-sub { font-size: 0.65rem; color: ${C.textDim}; line-height: 1.4; }
        .link-arrow { font-size: 0.8rem; color: #5A4050; flex-shrink: 0; transition: transform 0.2s; }
        .link-card:hover .link-arrow { transform: translateX(3px); color: ${C.pink}; }
        
        .link-divider { display: flex; align-items: center; gap: 0.75rem; margin: 0.5rem 0; animation: fadeUp 0.5s ease both; }
        .link-divider::before, .link-divider::after { content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.05); }
        .link-divider-label { font-size: 0.55rem; letter-spacing: 0.18em; text-transform: uppercase; color: ${C.textMuted}; }
        
        .links-footer { text-align: center; margin-top: 2.5rem; animation: fadeUp 0.5s 0.5s ease both; }
        .links-footer p { font-size: 0.6rem; color: ${C.textMuted}; letter-spacing: 0.1em; line-height: 1.8; }
        .links-footer a { color: ${C.textDim}; text-decoration: none; }
        .links-footer a:hover { color: ${C.pink}; }
        
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        
        .link-card:nth-child(1) { animation-delay: 0.08s; }
        .link-card:nth-child(2) { animation-delay: 0.13s; }
        .link-card:nth-child(3) { animation-delay: 0.18s; }
        .link-card:nth-child(4) { animation-delay: 0.23s; }
        .link-card:nth-child(5) { animation-delay: 0.28s; }
        .link-card:nth-child(6) { animation-delay: 0.33s; }
        .link-card:nth-child(7) { animation-delay: 0.38s; }
      `}</style>

      <div className="links-page">
        <div className="links-container">
          
          {/* Profile */}
          <div className="links-profile">
            <div className="links-avatar">RR</div>
            <div className="links-brand">RE<span>ROOTS</span></div>
            <div className="links-handle">@reroots.ca</div>
            <p className="links-bio">
              Premium PDRN biotech skincare.<br/>
              37.25% active concentration.<br/>
              Made in Canada. 28-day science protocol.
            </p>
          </div>

          {/* Links */}
          <div className="links-list">
            {LINKS.map((item, i) => {
              if (item.divider) {
                return (
                  <div key={`divider-${i}`} className="link-divider">
                    <span className="link-divider-label">{item.divider}</span>
                  </div>
                );
              }
              
              return (
                <a
                  key={item.href}
                  href={item.href}
                  className={`link-card${item.featured ? ' featured' : ''}`}
                  data-testid={`link-${item.href.replace(/\//g, '-')}`}
                >
                  <div className="link-icon" style={{ background: item.iconBg }}>{item.icon}</div>
                  <div className="link-text">
                    <div className="link-title">
                      {item.title}
                      {item.badge && (
                        <span className="link-badge" style={{ background: item.badgeBg }}>{item.badge}</span>
                      )}
                    </div>
                    <div className="link-sub">{item.sub}</div>
                  </div>
                  <div className="link-arrow">→</div>
                </a>
              );
            })}
          </div>

          {/* Footer */}
          <div className="links-footer">
            <p>
              <a href="/">reroots.ca</a> · Toronto, Canada<br/>
              Results may vary. Cosmetic use only.<br/>
              <a href="/pages/privacy">Privacy</a>
            </p>
          </div>

        </div>
      </div>
    </>
  );
}
