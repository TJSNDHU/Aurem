/**
 * useAdminBrand - Hook for getting active brand in admin components
 * Reads from localStorage and provides brand-specific theming
 */
import { useState, useEffect } from 'react';

// Brand configurations
const BRAND_THEMES = {
  reroots: {
    id: 'reroots',
    name: 'ReRoots',
    fullName: 'REROOTS AESTHETICS INC.',
    shortName: 'REROOTS',
    tagline: 'Premium PDRN Skincare',
    colors: {
      bg: "#FDF9F9",
      surface: "#FFFFFF",
      surfaceAlt: "#FEF2F4",
      border: "#F0E8E8",
      borderLight: "#E8DEE0",
      gold: "#F8A5B8",
      goldDim: "#E8889A",
      goldFaint: "rgba(248,165,184,0.08)",
      green: "#72B08A",
      greenFaint: "rgba(114,176,138,0.08)",
      red: "#E07070",
      redFaint: "rgba(224,112,112,0.08)",
      amber: "#E8A860",
      amberFaint: "rgba(232,168,96,0.08)",
      blue: "#7AAEC8",
      blueFaint: "rgba(122,174,200,0.08)",
      teal: "#72B0B0",
      text: "#2D2A2E",
      textDim: "#8A8490",
      textMuted: "#C4BAC0",
      white: "#FFFFFF",
    }
  },
  lavela: {
    id: 'lavela',
    name: 'La Vela Bianca',
    fullName: 'LA VELA BIANCA INC.',
    shortName: 'LA VELA BIANCA',
    tagline: 'Luxury Teen Skincare',
    colors: {
      bg: "#0D4D4D",
      surface: "#1A6B6B",
      surfaceAlt: "#1A6B6B40",
      border: "#D4A57440",
      borderLight: "#D4A57430",
      gold: "#D4A574",
      goldDim: "#E6BE8A",
      goldFaint: "rgba(212,165,116,0.15)",
      green: "#72B08A",
      greenFaint: "rgba(114,176,138,0.15)",
      red: "#E07070",
      redFaint: "rgba(224,112,112,0.15)",
      amber: "#E8A860",
      amberFaint: "rgba(232,168,96,0.15)",
      blue: "#7AAEC8",
      blueFaint: "rgba(122,174,200,0.15)",
      teal: "#72B0B0",
      text: "#FDF8F5",
      textDim: "#D4A574",
      textMuted: "#E8C4B8",
      white: "#FDF8F5",
    }
  }
};

export const useAdminBrand = () => {
  const [activeBrand, setActiveBrand] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('admin_active_brand') || 'reroots';
    }
    return 'reroots';
  });

  useEffect(() => {
    // Listen for brand changes
    const checkBrand = () => {
      const current = localStorage.getItem('admin_active_brand') || 'reroots';
      if (current !== activeBrand) {
        setActiveBrand(current);
      }
    };

    // Check periodically for same-tab updates
    const interval = setInterval(checkBrand, 500);
    window.addEventListener('storage', checkBrand);

    return () => {
      clearInterval(interval);
      window.removeEventListener('storage', checkBrand);
    };
  }, [activeBrand]);

  const brand = BRAND_THEMES[activeBrand] || BRAND_THEMES.reroots;
  const isLaVela = activeBrand === 'lavela';
  const isReRoots = activeBrand === 'reroots';

  return {
    activeBrand,
    brand,
    isLaVela,
    isReRoots,
    colors: brand.colors,
    name: brand.name,
    fullName: brand.fullName,
    shortName: brand.shortName,
    tagline: brand.tagline,
  };
};

export const getAdminBrand = () => {
  const brandId = typeof window !== 'undefined' 
    ? localStorage.getItem('admin_active_brand') || 'reroots'
    : 'reroots';
  return BRAND_THEMES[brandId] || BRAND_THEMES.reroots;
};

export { BRAND_THEMES };
export default useAdminBrand;
