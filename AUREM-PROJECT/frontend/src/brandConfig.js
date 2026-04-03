/**
 * Brand Configuration for Multi-Tenant Architecture
 * 
 * This file defines all brand-specific settings for:
 * - reroots.ca (ReRoots Aesthetics - Adult skincare)
 * - lavelabianca.com (La Vela Bianca - Teen skincare)
 * 
 * Brand is detected at RUNTIME from window.location.hostname
 * No environment variable needed - works with single deployment + multiple domains
 */

const BRAND_CONFIGS = {
  reroots: {
    id: 'reroots',
    name: 'ReRoots Aesthetics',
    tagline: 'Premium PDRN Skincare',
    shortName: 'ReRoots',
    
    // Visual Identity
    logo: '/reroots-logo.png',
    favicon: '/favicon.ico',
    
    // Color Palette
    colors: {
      primary: '#F8A5B8',         // Rose pink
      primaryHover: '#E88DA0',    // Darker pink
      secondary: '#4a7c59',       // Forest green
      accent: '#D4AF37',          // Gold
      background: '#FDF9F9',      // Soft pink tint
      backgroundAlt: '#FCE8EC',   // Lighter pink
      text: '#2D2A2E',            // Charcoal
      textMuted: '#5A5A5A',       // Gray
      textLight: '#FFFFFF',       // White
      border: 'rgba(248, 165, 184, 0.2)',
      success: '#4a7c59',
      error: '#e74c3c',
    },
    
    // Gradients
    gradients: {
      primary: 'linear-gradient(135deg, #F8A5B8 0%, #E88DA0 100%)',
      hero: 'linear-gradient(135deg, #FDF9F9 0%, #FCE8EC 100%)',
      card: 'linear-gradient(180deg, #FFFFFF 0%, #FDF9F9 100%)',
    },
    
    // Typography
    fonts: {
      heading: "'Playfair Display', serif",
      body: "'Inter', -apple-system, sans-serif",
      accent: "'Cormorant Garamond', serif",
    },
    
    // Target Audience
    audience: {
      type: 'adults',
      ageRange: '25-65',
      concerns: ['anti-aging', 'regeneration', 'luxury'],
    },
    
    // Routes
    routes: {
      home: '/',
      shop: '/shop',
      products: '/products',
      admin: '/admin',
      login: '/login',
      account: '/account',
    },
    
    // Features
    features: {
      loyaltyProgram: true,
      loyaltyName: 'Roots',
      whatsappAI: true,
      skinQuiz: true,
      partnerProgram: true,
      bioAgeScan: true,
    },
    
    // Social Links
    social: {
      instagram: 'https://instagram.com/reroots.ca',
      facebook: 'https://facebook.com/reroots.ca',
      tiktok: null,
    },
    
    // Contact
    contact: {
      email: 'hello@reroots.ca',
      phone: '+1 (647) 123-4567',
      whatsapp: '+16471234567',
    },
    
    // SEO
    seo: {
      title: 'ReRoots | Premium PDRN Skincare',
      description: 'Experience the future of skincare with ReRoots PDRN technology. Canadian-made, science-backed formulations for visible regeneration.',
      keywords: 'PDRN, skincare, anti-aging, Canadian skincare, regeneration, luxury skincare',
      ogImage: '/og-image-reroots.jpg',
    },
    
    // Product Categories
    productCategories: ['pdrn', 'serum', 'moisturizer', 'anti-aging', 'regeneration'],
  },
  
  lavela: {
    id: 'lavela',
    name: 'La Vela Bianca',
    tagline: 'Clean light for your skin',
    shortName: 'La Vela',
    
    // Visual Identity
    logo: '/lavela-icon.png',
    favicon: '/lavela-favicon.ico',
    
    // Color Palette - Midnight to Dawn
    colors: {
      primary: '#0D4D4D',         // Deep teal
      primaryHover: '#1A6B6B',    // Lighter teal
      secondary: '#D4A574',       // Rose gold
      accent: '#E8C4B8',          // Soft rose
      background: '#0D4D4D',      // Deep teal bg
      backgroundAlt: '#1A6B6B',   // Lighter teal
      text: '#FDF8F5',            // Cream white
      textMuted: '#E8C4B8',       // Rose for muted
      textLight: '#FFFFFF',       // White
      border: 'rgba(212, 165, 116, 0.3)',
      success: '#4a7c59',
      error: '#e74c3c',
    },
    
    // Gradients - Midnight to Dawn theme
    gradients: {
      primary: 'linear-gradient(135deg, #0D4D4D 0%, #1A6B6B 40%, #D4A090 80%, #E8C4B8 100%)',
      hero: 'linear-gradient(180deg, #0D4D4D 0%, #1A6B6B 30%, #D4A090 70%, #E8C4B8 100%)',
      card: 'linear-gradient(180deg, rgba(26, 107, 107, 0.5) 0%, rgba(13, 77, 77, 0.8) 100%)',
    },
    
    // Typography
    fonts: {
      heading: "'Playfair Display', serif",
      body: "'Montserrat', sans-serif",
      accent: "'Cormorant Garamond', serif",
    },
    
    // Target Audience
    audience: {
      type: 'teens',
      ageRange: '8-18',
      concerns: ['acne', 'gentle', 'pediatric-safe', 'first-skincare'],
    },
    
    // Routes
    routes: {
      home: '/',
      shop: '/shop',
      products: '/products',
      admin: '/admin',
      login: '/auth',
      account: '/account',
      lab: '/the-lab',
      glowClub: '/glow-club',
    },
    
    // Features
    features: {
      loyaltyProgram: true,
      loyaltyName: 'Glow Points',
      whatsappAI: false,
      skinQuiz: true,
      partnerProgram: true,
      glowClub: true,
      theLab: true,    // Science education for teens
    },
    
    // Social Links
    social: {
      instagram: 'https://instagram.com/lavelabianca',
      facebook: null,
      tiktok: 'https://tiktok.com/@lavelabianca',
    },
    
    // Contact
    contact: {
      email: 'Anmol@lavelabianca.com',
      phone: null,
      whatsapp: null,
    },
    
    // SEO
    seo: {
      title: 'La Vela Bianca | Luxury Teen Skincare',
      description: 'Premium pediatric-safe skincare for teens aged 8-18. Canadian-Italian technology with Centella Asiatica. Clean light for your skin.',
      keywords: 'teen skincare, pediatric safe, gentle skincare, acne, teens, clean beauty, Centella Asiatica',
      ogImage: '/og-image-lavela.jpg',
    },
    
    // Product Categories
    productCategories: ['teen-skincare', 'gentle', 'acne', 'hydration', 'first-skincare'],
  },
};

/**
 * Detect brand from hostname at RUNTIME
 * No environment variable needed - works with single deployment
 */
const detectBrandFromHostname = () => {
  // Check if we're in a browser environment
  if (typeof window === 'undefined') {
    return 'reroots'; // Default for SSR/build
  }
  
  const hostname = window.location.hostname.toLowerCase();
  const pathname = window.location.pathname.toLowerCase();
  
  // Check hostname for La Vela
  if (hostname.includes('lavelabianca') || hostname.includes('lavela')) {
    return 'lavela';
  }
  
  // Also check pathname for development/preview (e.g., /la-vela-bianca routes)
  if (pathname.startsWith('/la-vela-bianca') || pathname.startsWith('/lavela')) {
    return 'lavela';
  }
  
  // Check for explicit env var override (useful for local development)
  if (process.env.REACT_APP_BRAND === 'lavela') {
    return 'lavela';
  }
  
  // Default to ReRoots
  return 'reroots';
};

// Detect active brand at runtime
const activeBrandId = detectBrandFromHostname();

// Export active brand config
export const brandConfig = BRAND_CONFIGS[activeBrandId] || BRAND_CONFIGS.reroots;

// Export all configs for reference
export const allBrandConfigs = BRAND_CONFIGS;

// Helper functions
export const isBrand = (brandId) => activeBrandId === brandId;
export const isReRoots = () => activeBrandId === 'reroots';
export const isLaVela = () => activeBrandId === 'lavela';
export const getActiveBrandId = () => activeBrandId;
export const detectBrand = detectBrandFromHostname; // Export for re-detection if needed

// CSS variable generator for brand theming
export const getBrandCSSVariables = (config = brandConfig) => ({
  '--brand-primary': config.colors.primary,
  '--brand-primary-hover': config.colors.primaryHover,
  '--brand-secondary': config.colors.secondary,
  '--brand-accent': config.colors.accent,
  '--brand-bg': config.colors.background,
  '--brand-bg-alt': config.colors.backgroundAlt,
  '--brand-text': config.colors.text,
  '--brand-text-muted': config.colors.textMuted,
  '--brand-border': config.colors.border,
  '--font-heading': config.fonts.heading,
  '--font-body': config.fonts.body,
});

export default brandConfig;
