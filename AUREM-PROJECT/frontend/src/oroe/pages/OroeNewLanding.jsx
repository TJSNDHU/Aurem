/**
 * OROÉ Landing Page - New Design
 * ═══════════════════════════════════════════════════════════════════
 * Luxury Biotech Skincare | Polaris Built Inc.
 * Using ui-ux-pro-max design system
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useEffect, useRef } from 'react';
import '../styles/oroe-design-system.css';

// Hero Section
const Hero = () => (
  <section className="oroe-hero" style={{ background: 'var(--oroe-bg-deep)' }}>
    {/* Background Video/Image */}
    <div style={{
      position: 'absolute',
      inset: 0,
      background: `
        radial-gradient(ellipse at 30% 20%, rgba(212, 175, 55, 0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 70% 80%, rgba(212, 175, 55, 0.05) 0%, transparent 50%),
        var(--oroe-bg-deep)
      `,
    }} />
    
    {/* Content */}
    <div style={{
      position: 'relative',
      zIndex: 1,
      textAlign: 'center',
      maxWidth: '900px',
      padding: '0 24px',
    }}>
      <p className="oroe-caption" style={{ 
        color: 'var(--oroe-gold)',
        marginBottom: '24px',
        letterSpacing: '0.2em',
      }}>
        Polaris Built Inc.
      </p>
      
      <h1 className="oroe-h1" style={{ 
        color: 'var(--oroe-text-primary)',
        marginBottom: '16px',
      }}>
        OROÉ
      </h1>
      
      <p style={{
        fontFamily: 'var(--oroe-font-display)',
        fontSize: 'var(--oroe-text-2xl)',
        fontWeight: 300,
        fontStyle: 'italic',
        color: 'var(--oroe-gold)',
        marginBottom: '32px',
      }}>
        The Science of Timeless Skin
      </p>
      
      <p className="oroe-body" style={{ 
        color: 'var(--oroe-text-secondary)',
        maxWidth: '600px',
        margin: '0 auto 48px',
        lineHeight: 1.8,
      }}>
        Experience the transformative power of biotech PDRN. A luxury protocol 
        designed to reverse visible signs of aging and restore luminous, 
        youthful-looking skin.
      </p>
      
      <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap' }}>
        <a href="#products" className="oroe-btn oroe-btn-primary">
          Explore Collection
        </a>
        <a href="#science" className="oroe-btn oroe-btn-secondary">
          The Science
        </a>
      </div>
      
      {/* Scroll indicator */}
      <div style={{
        position: 'absolute',
        bottom: '40px',
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '8px',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--oroe-text-muted)', letterSpacing: '0.1em' }}>
          SCROLL
        </span>
        <div style={{
          width: '1px',
          height: '40px',
          background: 'linear-gradient(to bottom, var(--oroe-gold), transparent)',
        }} />
      </div>
    </div>
  </section>
);

// Product Card Component
const ProductCard = ({ name, tagline, description, accent, features, reverse }) => (
  <div style={{
    display: 'grid',
    gridTemplateColumns: reverse ? '1fr 1fr' : '1fr 1fr',
    gap: '80px',
    alignItems: 'center',
    direction: reverse ? 'rtl' : 'ltr',
  }}>
    {/* Image Placeholder */}
    <div style={{
      direction: 'ltr',
      aspectRatio: '4/5',
      background: `
        linear-gradient(135deg, var(--oroe-bg-elevated) 0%, var(--oroe-bg-card) 100%)
      `,
      borderRadius: 'var(--oroe-radius-md)',
      border: '1px solid var(--oroe-border-subtle)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Gold glow effect */}
      <div style={{
        position: 'absolute',
        width: '200px',
        height: '200px',
        background: `radial-gradient(circle, ${accent}20 0%, transparent 70%)`,
        filter: 'blur(40px)',
      }} />
      <span style={{ 
        color: 'var(--oroe-text-muted)', 
        fontSize: '14px',
        letterSpacing: '0.1em',
        zIndex: 1,
      }}>
        PRODUCT IMAGE
      </span>
    </div>
    
    {/* Content */}
    <div style={{ direction: 'ltr' }}>
      <p className="oroe-caption" style={{ color: accent, marginBottom: '16px' }}>
        {tagline}
      </p>
      
      <h2 className="oroe-h2" style={{ marginBottom: '24px' }}>
        {name}
      </h2>
      
      <p className="oroe-body" style={{ 
        color: 'var(--oroe-text-secondary)',
        marginBottom: '32px',
      }}>
        {description}
      </p>
      
      <ul style={{ 
        listStyle: 'none', 
        padding: 0, 
        margin: '0 0 40px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}>
        {features.map((feature, i) => (
          <li key={i} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: 'var(--oroe-text-secondary)',
            fontSize: '15px',
          }}>
            <span style={{ 
              color: accent,
              fontSize: '10px',
            }}>◆</span>
            {feature}
          </li>
        ))}
      </ul>
      
      <button className="oroe-btn oroe-btn-primary" style={{ borderColor: accent, color: accent }}>
        Learn More
      </button>
    </div>
  </div>
);

// Products Section
const Products = () => (
  <section id="products" className="oroe-section" style={{ background: 'var(--oroe-bg-base)' }}>
    <div className="oroe-container">
      {/* Section Header */}
      <div style={{ textAlign: 'center', marginBottom: '100px' }}>
        <p className="oroe-caption" style={{ color: 'var(--oroe-gold)', marginBottom: '16px' }}>
          The Collection
        </p>
        <h2 className="oroe-h2">Three Pillars of Transformation</h2>
      </div>
      
      {/* Age Reversal */}
      <div style={{ marginBottom: '120px' }}>
        <ProductCard
          name="Age Reversal"
          tagline="Cellular Regeneration"
          description="Our flagship PDRN serum penetrates deep into the dermis, activating cellular regeneration pathways. Visibly reduces fine lines and restores youthful elasticity within weeks."
          accent="var(--oroe-age-reversal)"
          features={[
            'Advanced PDRN Complex',
            'Peptide-rich formula',
            'Clinically proven results',
            'Suitable for all skin types',
          ]}
          reverse={false}
        />
      </div>
      
      {/* BrightShield */}
      <div style={{ marginBottom: '120px' }}>
        <ProductCard
          name="BrightShield"
          tagline="Luminosity Defense"
          description="A dual-action brightening system that fades hyperpigmentation while protecting against future damage. Reveals an even, radiant complexion with continued use."
          accent="var(--oroe-brightshield)"
          features={[
            'Vitamin C stabilized complex',
            'Melanin regulation technology',
            'UV damage repair',
            'Antioxidant protection',
          ]}
          reverse={true}
        />
      </div>
      
      {/* ClearTech */}
      <div>
        <ProductCard
          name="ClearTech"
          tagline="Precision Clarity"
          description="Advanced clarity technology targets texture irregularities and pore congestion. Micro-exfoliation reveals smoother, clearer skin without irritation."
          accent="var(--oroe-cleartech)"
          features={[
            'BHA micro-delivery system',
            'Pore-refining actives',
            'Non-irritating formula',
            'Oil-control technology',
          ]}
          reverse={false}
        />
      </div>
    </div>
  </section>
);

// Science Section
const Science = () => (
  <section id="science" className="oroe-section" style={{ background: 'var(--oroe-bg-elevated)' }}>
    <div className="oroe-container">
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr', 
        gap: '80px',
        alignItems: 'center',
      }}>
        {/* Content */}
        <div>
          <p className="oroe-caption" style={{ color: 'var(--oroe-gold)', marginBottom: '16px' }}>
            The Science
          </p>
          <h2 className="oroe-h2" style={{ marginBottom: '24px' }}>
            PDRN Technology
          </h2>
          <p className="oroe-body" style={{ 
            color: 'var(--oroe-text-secondary)',
            marginBottom: '32px',
          }}>
            Polydeoxyribonucleotide (PDRN) is a biologically active compound derived from 
            salmon DNA. When applied topically, it stimulates cellular repair mechanisms, 
            promoting collagen synthesis and tissue regeneration.
          </p>
          
          {/* Stats */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(3, 1fr)', 
            gap: '24px',
            marginTop: '48px',
          }}>
            {[
              { value: '94%', label: 'Saw visible improvement' },
              { value: '4 Weeks', label: 'To see results' },
              { value: '12+', label: 'Clinical studies' },
            ].map((stat, i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{
                  fontFamily: 'var(--oroe-font-display)',
                  fontSize: 'var(--oroe-text-2xl)',
                  color: 'var(--oroe-gold)',
                  marginBottom: '8px',
                }}>
                  {stat.value}
                </div>
                <div style={{
                  fontSize: '13px',
                  color: 'var(--oroe-text-muted)',
                  letterSpacing: '0.05em',
                }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Visual */}
        <div style={{
          aspectRatio: '1',
          background: `
            radial-gradient(circle at center, var(--oroe-gold-glow) 0%, transparent 50%),
            var(--oroe-bg-card)
          `,
          borderRadius: '50%',
          border: '1px solid var(--oroe-border-gold)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <span style={{ 
            fontFamily: 'var(--oroe-font-display)',
            fontSize: '48px',
            color: 'var(--oroe-gold)',
            opacity: 0.3,
          }}>
            PDRN
          </span>
        </div>
      </div>
    </div>
  </section>
);

// Ritual Section
const Ritual = () => (
  <section className="oroe-section" style={{ background: 'var(--oroe-bg-base)' }}>
    <div className="oroe-container">
      <div style={{ textAlign: 'center', marginBottom: '80px' }}>
        <p className="oroe-caption" style={{ color: 'var(--oroe-gold)', marginBottom: '16px' }}>
          The Ritual
        </p>
        <h2 className="oroe-h2">Your Evening Protocol</h2>
      </div>
      
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(3, 1fr)', 
        gap: '40px',
      }}>
        {[
          { step: '01', title: 'Cleanse', desc: 'Begin with a gentle cleanser to prepare your skin for maximum absorption.' },
          { step: '02', title: 'Apply', desc: 'Dispense 2-3 drops of your OROÉ serum and press gently into skin.' },
          { step: '03', title: 'Seal', desc: 'Follow with your preferred moisturizer to lock in the active ingredients.' },
        ].map((item, i) => (
          <div key={i} className="oroe-card" style={{
            textAlign: 'center',
            padding: '48px 32px',
            background: 'var(--oroe-bg-card)',
          }}>
            <div style={{
              fontFamily: 'var(--oroe-font-display)',
              fontSize: '48px',
              color: 'var(--oroe-gold)',
              opacity: 0.2,
              marginBottom: '16px',
            }}>
              {item.step}
            </div>
            <h3 style={{
              fontFamily: 'var(--oroe-font-display)',
              fontSize: 'var(--oroe-text-xl)',
              marginBottom: '16px',
            }}>
              {item.title}
            </h3>
            <p style={{
              color: 'var(--oroe-text-secondary)',
              fontSize: '15px',
              lineHeight: 1.7,
            }}>
              {item.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// Footer
const Footer = () => (
  <footer style={{
    background: 'var(--oroe-bg-deep)',
    borderTop: '1px solid var(--oroe-border-subtle)',
    padding: '80px 24px 40px',
  }}>
    <div className="oroe-container">
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '60px',
        flexWrap: 'wrap',
        gap: '40px',
      }}>
        {/* Brand */}
        <div>
          <h3 style={{
            fontFamily: 'var(--oroe-font-display)',
            fontSize: 'var(--oroe-text-2xl)',
            marginBottom: '8px',
          }}>
            OROÉ
          </h3>
          <p style={{ 
            color: 'var(--oroe-text-muted)', 
            fontSize: '14px',
          }}>
            The Science of Timeless Skin
          </p>
        </div>
        
        {/* Links */}
        <div style={{ display: 'flex', gap: '60px' }}>
          {[
            { title: 'Products', links: ['Age Reversal', 'BrightShield', 'ClearTech'] },
            { title: 'Company', links: ['About', 'Science', 'Contact'] },
          ].map((col, i) => (
            <div key={i}>
              <h4 style={{
                fontSize: '12px',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--oroe-text-muted)',
                marginBottom: '20px',
              }}>
                {col.title}
              </h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {col.links.map((link, j) => (
                  <li key={j} style={{ marginBottom: '12px' }}>
                    <a href="#" style={{
                      color: 'var(--oroe-text-secondary)',
                      textDecoration: 'none',
                      fontSize: '14px',
                      transition: 'color 0.2s',
                    }}>
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      
      {/* Bottom */}
      <div style={{
        borderTop: '1px solid var(--oroe-border-subtle)',
        paddingTop: '24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px',
      }}>
        <p style={{ 
          color: 'var(--oroe-text-muted)', 
          fontSize: '13px',
        }}>
          © 2025 Polaris Built Inc. All rights reserved.
        </p>
        <p style={{ 
          color: 'var(--oroe-text-muted)', 
          fontSize: '13px',
        }}>
          Made in Canada 🇨🇦
        </p>
      </div>
    </div>
  </footer>
);

// Main Page Component
const OroeNewLanding = () => {
  useEffect(() => {
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          target.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });
  }, []);

  return (
    <div className="oroe-page" style={{ minHeight: '100vh' }}>
      <Hero />
      <Products />
      <Science />
      <Ritual />
      <Footer />
    </div>
  );
};

export default OroeNewLanding;
