/**
 * LazyMotion Configuration
 * Reduces framer-motion bundle size by ~70% by only loading used features
 * 
 * Usage:
 * import { LazyMotionProvider, m } from '@/lib/lazyMotion';
 * 
 * // Wrap your app or component
 * <LazyMotionProvider>
 *   <m.div animate={{ opacity: 1 }} />
 * </LazyMotionProvider>
 */

import { LazyMotion, domAnimation, m } from 'framer-motion';

// domAnimation includes: animate, exit, initial, style, variants
// It excludes heavy features: drag, layout, layoutId, useScroll (saves ~70KB)

export const LazyMotionProvider = ({ children }) => (
  <LazyMotion features={domAnimation} strict>
    {children}
  </LazyMotion>
);

// Export 'm' component (lightweight version of 'motion')
export { m, domAnimation };

// Re-export commonly used hooks that don't need full motion
export { AnimatePresence, useAnimation, useInView } from 'framer-motion';
