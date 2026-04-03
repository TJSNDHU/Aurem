import React, { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useBrand } from '@/contexts';

// Lazy load brand-specific pages
const HomePage = lazy(() => import('@/components/pages/HomePage'));
const ShopPage = lazy(() => import('@/components/pages/ShopPage'));

// LA VELA BIANCA Pages
const LaVelaLandingPage = lazy(() => import('@/lavela/pages/LaVelaLandingPage'));
const OroRosaPage = lazy(() => import('@/lavela/pages/OroRosaPage'));
const LaVelaAuthPage = lazy(() => import('@/lavela/pages/LaVelaAuthPage'));
const TheLabPage = lazy(() => import('@/lavela/pages/TheLabPage'));
const FounderPage = lazy(() => import('@/lavela/pages/FounderPage'));
const GlowClubPage = lazy(() => import('@/lavela/pages/GlowClubPage'));

// Loading fallback
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="animate-pulse text-center">
      <div className="w-12 h-12 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-4" 
           style={{ borderColor: 'var(--brand-primary)', borderTopColor: 'transparent' }} />
      <p className="text-gray-500">Loading...</p>
    </div>
  </div>
);

/**
 * BrandRouter - Routes requests based on current brand/domain
 * 
 * When accessing lavelabianca.com:
 * - "/" renders La Vela landing page
 * - "/shop" renders La Vela shop
 * 
 * When accessing reroots.ca:
 * - "/" renders ReRoots home page
 * - "/shop" renders ReRoots shop
 */
const BrandRouter = ({ children }) => {
  const { isLaVela, isReRoots, brandConfig } = useBrand();
  
  // If on La Vela domain, override root routes
  if (isLaVela()) {
    return (
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* La Vela Root Routes */}
          <Route path="/" element={<LaVelaLandingPage />} />
          <Route path="/shop" element={<OroRosaPage />} />
          <Route path="/oro-rosa" element={<OroRosaPage />} />
          <Route path="/the-lab" element={<TheLabPage />} />
          <Route path="/glow-club" element={<GlowClubPage />} />
          <Route path="/founder" element={<FounderPage />} />
          <Route path="/auth" element={<LaVelaAuthPage />} />
          <Route path="/login" element={<LaVelaAuthPage />} />
          
          {/* Redirect old La Vela paths for SEO */}
          <Route path="/la-vela-bianca" element={<Navigate to="/" replace />} />
          <Route path="/la-vela-bianca/*" element={<Navigate to="/" replace />} />
          
          {/* Pass through to main app routes for shared pages */}
          <Route path="/*" element={children} />
        </Routes>
      </Suspense>
    );
  }
  
  // Default: ReRoots routing (pass through to main app)
  return children;
};

export default BrandRouter;
