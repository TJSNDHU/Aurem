import React, { createContext, useContext, useState, useEffect } from 'react';
import { brandConfig, allBrandConfigs, detectBrand, getBrandCSSVariables } from '@/brandConfig';

// Create context
const BrandContext = createContext(null);

// Custom hook
export const useBrand = () => {
  const context = useContext(BrandContext);
  if (!context) {
    throw new Error('useBrand must be used within a BrandProvider');
  }
  return context;
};

// Provider component
export const BrandProvider = ({ children }) => {
  const [currentBrand, setCurrentBrand] = useState(() => detectBrand());
  const [config, setConfig] = useState(brandConfig);
  
  // Re-detect brand on route changes (for SPA navigation between brand sections)
  useEffect(() => {
    const handleRouteChange = () => {
      const detectedBrand = detectBrand();
      if (detectedBrand !== currentBrand) {
        setCurrentBrand(detectedBrand);
        setConfig(allBrandConfigs[detectedBrand]);
        applyBrandTheme(allBrandConfigs[detectedBrand]);
      }
    };
    
    // Listen for popstate (back/forward navigation)
    window.addEventListener('popstate', handleRouteChange);
    
    return () => {
      window.removeEventListener('popstate', handleRouteChange);
    };
  }, [currentBrand]);
  
  // Apply theme to document
  const applyBrandTheme = (brandConf) => {
    // Remove all brand classes
    document.documentElement.classList.remove('brand-reroots', 'brand-lavela', 'theme-reroots', 'theme-lavela');
    
    // Add current brand classes
    document.documentElement.classList.add(`brand-${brandConf.id}`);
    document.documentElement.classList.add(`theme-${brandConf.id}`);
    
    // Apply CSS variables
    const cssVars = getBrandCSSVariables(brandConf);
    Object.entries(cssVars).forEach(([key, value]) => {
      document.documentElement.style.setProperty(key, value);
    });
    
    // Update favicon
    const favicon = document.querySelector('link[rel="icon"]');
    if (favicon && brandConf.favicon) {
      favicon.href = brandConf.favicon;
    }
    
    // Update theme-color meta
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.setAttribute('content', brandConf.colors.primary);
    }
    
    // Update document title
    if (brandConf.seo?.title) {
      document.title = brandConf.seo.title;
    }
    
    console.log(`[Brand] Switched to: ${brandConf.name} (${brandConf.id})`);
  };
  
  // Initial theme application
  useEffect(() => {
    applyBrandTheme(config);
  }, []);
  
  // Switch brand manually (for admin/testing)
  const switchBrand = (brandId) => {
    if (allBrandConfigs[brandId]) {
      setCurrentBrand(brandId);
      setConfig(allBrandConfigs[brandId]);
      applyBrandTheme(allBrandConfigs[brandId]);
    }
  };
  
  // Helper functions
  const isBrand = (brandId) => currentBrand === brandId;
  const isReRoots = () => currentBrand === 'reroots';
  const isLaVela = () => currentBrand === 'lavela';
  const getAllBrands = () => Object.values(allBrandConfigs);
  
  const value = {
    currentBrand,
    brandConfig: config,
    switchBrand,
    isBrand,
    isReRoots,
    isLaVela,
    getAllBrands,
    BRAND_CONFIGS: allBrandConfigs,
  };
  
  return (
    <BrandContext.Provider value={value}>
      {children}
    </BrandContext.Provider>
  );
};

export { allBrandConfigs as BRAND_CONFIGS };
export default BrandContext;
