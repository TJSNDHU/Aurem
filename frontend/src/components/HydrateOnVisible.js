import React, { useState, useEffect, useRef, Suspense, lazy } from 'react';

/**
 * HydrateOnVisible - Advanced lazy hydration for mobile performance
 * 
 * This component delays React hydration until the element enters the viewport.
 * On mobile, this is critical because:
 * - CPU is throttled 4x compared to desktop
 * - Each hydrated component adds to Total Blocking Time (TBT)
 * - Users don't need below-fold content to be interactive immediately
 * 
 * Usage:
 * <HydrateOnVisible>
 *   <HeavyComponent />
 * </HydrateOnVisible>
 */

// Lightweight placeholder that matches the estimated height
const HydrationPlaceholder = ({ height = 400, className = '' }) => (
  <div 
    className={`bg-gradient-to-b from-gray-50/50 to-transparent ${className}`}
    style={{ minHeight: height }}
    aria-hidden="true"
  />
);

// Main HydrateOnVisible component
export const HydrateOnVisible = ({ 
  children, 
  fallback = null,
  rootMargin = '200px', // Start hydrating 200px before visible
  threshold = 0,
  minHeight = 400,
  className = '',
  onHydrate = null // Callback when hydration starts
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [hasHydrated, setHasHydrated] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    // Skip IntersectionObserver on server or if already hydrated
    if (typeof window === 'undefined' || hasHydrated) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasHydrated) {
            setIsVisible(true);
            setHasHydrated(true);
            onHydrate?.();
            observer.disconnect();
          }
        });
      },
      {
        rootMargin,
        threshold,
      }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, [rootMargin, threshold, hasHydrated, onHydrate]);

  // Show placeholder until visible
  if (!isVisible) {
    return (
      <div ref={containerRef} className={className}>
        {fallback || <HydrationPlaceholder height={minHeight} />}
      </div>
    );
  }

  // Once visible, render the actual content
  return (
    <Suspense fallback={fallback || <HydrationPlaceholder height={minHeight} />}>
      {children}
    </Suspense>
  );
};

/**
 * withHydrateOnVisible - HOC version for class components or existing lazy components
 * 
 * Usage:
 * const LazyComponent = withHydrateOnVisible(
 *   lazy(() => import('./HeavyComponent')),
 *   { minHeight: 600 }
 * );
 */
export const withHydrateOnVisible = (Component, options = {}) => {
  const WrappedComponent = (props) => (
    <HydrateOnVisible {...options}>
      <Component {...props} />
    </HydrateOnVisible>
  );
  
  WrappedComponent.displayName = `HydrateOnVisible(${Component.displayName || Component.name || 'Component'})`;
  
  return WrappedComponent;
};

/**
 * useHydrateOnVisible - Hook version for more control
 * 
 * Usage:
 * const { ref, isHydrated } = useHydrateOnVisible();
 * 
 * return (
 *   <div ref={ref}>
 *     {isHydrated ? <HeavyContent /> : <Placeholder />}
 *   </div>
 * );
 */
export const useHydrateOnVisible = (options = {}) => {
  const { rootMargin = '200px', threshold = 0 } = options;
  const [isHydrated, setIsHydrated] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (typeof window === 'undefined' || isHydrated) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setIsHydrated(true);
          observer.disconnect();
        }
      },
      { rootMargin, threshold }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, [rootMargin, threshold, isHydrated]);

  return { ref, isHydrated };
};

export default HydrateOnVisible;
