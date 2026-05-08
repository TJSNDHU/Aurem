/**
 * AUREM Motion System — Reusable animation variants and components
 * Uses framer-motion (motion) for smooth, $997/month-tier UI polish.
 */

import React from 'react';
import { motion, AnimatePresence } from 'motion/react';

/* ═══════════════════════════════════════
 * ANIMATION VARIANTS
 * ═══════════════════════════════════════ */

/** Staggered children container — wraps grid/list items */
export const staggerContainer = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.1,
    },
  },
};

/** Individual card fade-in + slide-up */
export const cardVariant = {
  hidden: { opacity: 0, y: 16, scale: 0.97 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: 'spring', stiffness: 300, damping: 24 },
  },
};

/** Sidebar nav item entrance */
export const sidebarItemVariant = {
  hidden: { opacity: 0, x: -12 },
  show: {
    opacity: 1,
    x: 0,
    transition: { type: 'spring', stiffness: 400, damping: 28 },
  },
};

/** Page transition (content area) */
export const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
};

/** Modal overlay entrance */
export const modalOverlay = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.2 } },
  exit: { opacity: 0, transition: { duration: 0.15 } },
};

/** Modal content entrance */
export const modalContent = {
  initial: { opacity: 0, scale: 0.95, y: 10 },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 350, damping: 25 },
  },
  exit: { opacity: 0, scale: 0.97, y: 5, transition: { duration: 0.15 } },
};

/** List item (for episode list, plan steps, etc.) */
export const listItemVariant = {
  hidden: { opacity: 0, x: -8 },
  show: {
    opacity: 1,
    x: 0,
    transition: { type: 'spring', stiffness: 350, damping: 25 },
  },
};

/** Counter / number tick animation */
export const numberVariant = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 400, damping: 20 },
  },
};

/* ═══════════════════════════════════════
 * REUSABLE MOTION COMPONENTS
 * ═══════════════════════════════════════ */

/** Animated card wrapper — use in place of <div> for dashboard cards */
export const MotionCard = React.forwardRef(({ children, className, style, delay = 0, ...props }, ref) => (
  <motion.div
    ref={ref}
    className={className}
    style={style}
    variants={cardVariant}
    initial="hidden"
    animate="show"
    whileHover={{ y: -2, boxShadow: '0 8px 30px rgba(0,0,0,0.12)', transition: { duration: 0.2 } }}
    whileTap={{ scale: 0.98 }}
    transition={{ delay }}
    {...props}
  >
    {children}
  </motion.div>
));
MotionCard.displayName = 'MotionCard';

/** Stagger grid container — wraps a grid of MotionCards */
export const StaggerGrid = ({ children, className, style, ...props }) => (
  <motion.div
    className={className}
    style={style}
    variants={staggerContainer}
    initial="hidden"
    animate="show"
    {...props}
  >
    {children}
  </motion.div>
);

/** Animated page wrapper — wraps each dashboard section content */
export const PageTransition = ({ children, className, pageKey }) => (
  <AnimatePresence mode="wait">
    <motion.div
      key={pageKey}
      className={className}
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {children}
    </motion.div>
  </AnimatePresence>
);

/** Sidebar nav button with motion */
export const MotionNavItem = ({ children, isActive, onClick, className, style, ...props }) => (
  <motion.button
    className={className}
    style={style}
    onClick={onClick}
    variants={sidebarItemVariant}
    whileHover={{ x: 3, backgroundColor: 'rgba(61,58,57,0.15)', transition: { duration: 0.15 } }}
    whileTap={{ scale: 0.97 }}
    {...props}
  >
    {children}
  </motion.button>
);

/** Animated badge / pill — for status indicators */
export const MotionBadge = ({ children, className, style }) => (
  <motion.span
    className={className}
    style={style}
    initial={{ opacity: 0, scale: 0.8 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
  >
    {children}
  </motion.span>
);

/** Animated number counter */
export const AnimatedNumber = ({ value, className, style }) => (
  <motion.span
    className={className}
    style={style}
    key={value}
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
  >
    {value}
  </motion.span>
);

/** Expandable section with smooth height animation */
export const ExpandSection = ({ isOpen, children }) => (
  <AnimatePresence>
    {isOpen && (
      <motion.div
        initial={{ height: 0, opacity: 0 }}
        animate={{ height: 'auto', opacity: 1, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] } }}
        exit={{ height: 0, opacity: 0, transition: { duration: 0.2 } }}
        style={{ overflow: 'hidden' }}
      >
        {children}
      </motion.div>
    )}
  </AnimatePresence>
);

export { AnimatePresence, motion };
