/**
 * LazyMotion Wrapper - Reduces framer-motion bundle by ~50%
 * 
 * Usage:
 * 1. Import { m } instead of { motion } from framer-motion
 * 2. Wrap components needing animations in <LazyMotionProvider>
 * 3. Use <m.div> instead of <motion.div>
 * 
 * This reduces initial bundle from ~34KB to ~4.6KB for framer-motion
 */
import React, { Suspense } from 'react';
import { LazyMotion, domAnimation, m, AnimatePresence } from 'framer-motion';

// Lazy load domMax only when needed (for drag, pan, layout animations)
const loadDomMax = () => import('framer-motion').then(mod => mod.domMax);

/**
 * LazyMotionProvider - Use this for basic animations (hover, tap, variants)
 * Only adds ~15KB compared to full ~34KB bundle
 */
export const LazyMotionProvider = ({ children, strict = true }) => (
  <LazyMotion features={domAnimation} strict={strict}>
    {children}
  </LazyMotion>
);

/**
 * LazyMotionProviderMax - Use this when you need drag/pan/layout animations
 * Lazy loads ~25KB of additional features only when needed
 */
export const LazyMotionProviderMax = ({ children, strict = true }) => (
  <LazyMotion features={loadDomMax} strict={strict}>
    {children}
  </LazyMotion>
);

// Re-export m components for easy use
export { m, AnimatePresence };

// Pre-built animated components for common use cases
export const MotionDiv = React.forwardRef((props, ref) => (
  <m.div ref={ref} {...props} />
));
MotionDiv.displayName = 'MotionDiv';

export const MotionButton = React.forwardRef((props, ref) => (
  <m.button ref={ref} {...props} />
));
MotionButton.displayName = 'MotionButton';

export const MotionSpan = React.forwardRef((props, ref) => (
  <m.span ref={ref} {...props} />
));
MotionSpan.displayName = 'MotionSpan';

export const MotionSection = React.forwardRef((props, ref) => (
  <m.section ref={ref} {...props} />
));
MotionSection.displayName = 'MotionSection';

export const MotionH1 = React.forwardRef((props, ref) => (
  <m.h1 ref={ref} {...props} />
));
MotionH1.displayName = 'MotionH1';

export const MotionP = React.forwardRef((props, ref) => (
  <m.p ref={ref} {...props} />
));
MotionP.displayName = 'MotionP';

export const MotionImg = React.forwardRef((props, ref) => (
  <m.img ref={ref} {...props} />
));
MotionImg.displayName = 'MotionImg';

export default LazyMotionProvider;
