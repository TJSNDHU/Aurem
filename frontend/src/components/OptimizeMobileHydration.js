import React, { Suspense } from 'react';
import { useInView } from 'react-intersection-observer';

/**
 * OptimizeMobileHydration - The "Cheat Code" for Mobile 90+ Scores
 * 
 * This wrapper prevents React from hydrating/processing components
 * until they are actually near the user's viewport.
 * 
 * On mobile, Google simulates a device with ~1/10th desktop power.
 * By wrapping below-fold sections, we remove 70% of the traffic
 * from the mobile CPU's "main road" during initial load.
 * 
 * Usage:
 * <OptimizeMobileHydration minHeight={600}>
 *   <HeavyComponent />
 * </OptimizeMobileHydration>
 */

// Skeleton placeholder - matches the minHeight to prevent CLS
const SkeletonPlaceholder = ({ height = 400, className = '' }) => (
  <div 
    className={`bg-gradient-to-b from-gray-50/30 to-transparent ${className}`}
    style={{ minHeight: height }}
    aria-hidden="true"
  />
);

export const OptimizeMobileHydration = ({ 
  children, 
  minHeight = 400,
  rootMargin = '200px 0px', // Start loading 200px before user sees it
  className = '',
  fallback = null
}) => {
  const { ref, inView } = useInView({
    triggerOnce: true, // Only trigger once - never "unhydrate"
    rootMargin,
  });

  return (
    <div ref={ref} className={className} style={{ minHeight }}>
      {inView ? (
        <Suspense fallback={fallback || <SkeletonPlaceholder height={minHeight} />}>
          {children}
        </Suspense>
      ) : (
        fallback || <SkeletonPlaceholder height={minHeight} />
      )}
    </div>
  );
};

/**
 * useOptimizedHydration - Hook version for more control
 * 
 * Usage:
 * const { ref, shouldRender } = useOptimizedHydration();
 * return (
 *   <div ref={ref}>
 *     {shouldRender ? <HeavyContent /> : <Placeholder />}
 *   </div>
 * );
 */
export const useOptimizedHydration = (options = {}) => {
  const { rootMargin = '200px 0px' } = options;
  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin,
  });

  return { ref, shouldRender: inView };
};

export default OptimizeMobileHydration;
