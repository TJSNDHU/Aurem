/**
 * useViewport — lightweight responsive hook for the Luxe portal.
 * Returns viewport size + breakpoint flags. Subscribes to resize/orientation.
 *
 * Breakpoints (matches industry standard, tuned for our luxe aesthetic):
 *   mobile:  < 768px   (phones, portrait tablets in some cases)
 *   tablet:  768–1023  (iPads portrait, small laptops)
 *   desktop: >= 1024
 */
import { useEffect, useState } from 'react';

const read = () => {
  if (typeof window === 'undefined') return { width: 1280, height: 800 };
  return { width: window.innerWidth, height: window.innerHeight };
};

export const useViewport = () => {
  const [vp, setVp] = useState(read);
  useEffect(() => {
    let raf = 0;
    const handler = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setVp(read()));
    };
    window.addEventListener('resize', handler);
    window.addEventListener('orientationchange', handler);
    return () => {
      window.removeEventListener('resize', handler);
      window.removeEventListener('orientationchange', handler);
      cancelAnimationFrame(raf);
    };
  }, []);
  const w = vp.width;
  return {
    width: w,
    height: vp.height,
    isMobile: w < 768,
    isTablet: w >= 768 && w < 1024,
    isDesktop: w >= 1024,
    isCompact: w < 1024, // mobile + tablet combined for some decisions
  };
};

export default useViewport;
