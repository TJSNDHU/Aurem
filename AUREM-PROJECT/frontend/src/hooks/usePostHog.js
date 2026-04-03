/**
 * PostHog Safety Hook for Partytown
 * 
 * Since Partytown runs PostHog in a Web Worker, the posthog object
 * might not be immediately available. This hook provides a safe way
 * to track events without crashing the app.
 * 
 * Usage:
 * const { capture, identify, isReady } = usePostHog();
 * capture('button_clicked', { button_name: 'Shop Now' });
 */

import { useEffect, useState, useCallback } from 'react';

export const usePostHog = () => {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Check every 100ms if Partytown has finished booting PostHog
    const checkReady = () => {
      if (window.posthog && typeof window.posthog.capture === 'function') {
        setIsReady(true);
        return true;
      }
      return false;
    };

    // Check immediately
    if (checkReady()) return;

    // Poll until ready (max 10 seconds)
    const interval = setInterval(() => {
      if (checkReady()) {
        clearInterval(interval);
      }
    }, 100);

    const timeout = setTimeout(() => {
      clearInterval(interval);
      console.warn('PostHog did not initialize within 10 seconds');
    }, 10000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, []);

  // Safe capture function
  const capture = useCallback((eventName, properties = {}) => {
    if (window.posthog && typeof window.posthog.capture === 'function') {
      window.posthog.capture(eventName, properties);
    } else if (process.env.NODE_ENV === 'development') {
      console.log(`[PostHog Queue] ${eventName}`, properties);
    }
  }, []);

  // Safe identify function
  const identify = useCallback((userId, properties = {}) => {
    if (window.posthog && typeof window.posthog.identify === 'function') {
      window.posthog.identify(userId, properties);
    }
  }, []);

  // Safe reset function (for logout)
  const reset = useCallback(() => {
    if (window.posthog && typeof window.posthog.reset === 'function') {
      window.posthog.reset();
    }
  }, []);

  return { capture, identify, reset, isReady };
};

// Simple capture function for one-off usage (doesn't need hook)
export const captureEvent = (eventName, properties = {}) => {
  if (window.posthog && typeof window.posthog.capture === 'function') {
    window.posthog.capture(eventName, properties);
  }
};

export default usePostHog;
