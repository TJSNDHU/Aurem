/**
 * useLivePolling — drop-in live data refresh for any dashboard widget
 * ─────────────────────────────────────────────────────────────────
 * Invoke ANY fetcher function on a cadence with smart defaults:
 *   • Stops polling when the tab is hidden (saves battery + API cost)
 *   • Resumes instantly on visibilitychange → shows fresh data the moment
 *     the user looks at the tab again
 *   • Re-fetches on window focus (switching back to the app)
 *   • Re-fetches on network reconnect
 *   • Configurable interval (default 15s)
 *   • Optional `onUpdate(data)` callback so hooks can stream new values
 *     into Zustand/global state
 *
 * Usage:
 *   const fetcher = useCallback(async () => {
 *     const r = await fetch(`${API}/api/foo`, { headers });
 *     return r.json();
 *   }, []);
 *   useLivePolling(fetcher, 15000, (data) => setState(data));
 *
 * The fetcher must be stable (wrapped in useCallback) — else the effect
 * re-subscribes every render.
 */
import { useEffect, useRef } from 'react';

export default function useLivePolling(
  fetcher,
  intervalMs = 15000,
  onUpdate = null,
  options = {}
) {
  const { pauseWhenHidden = true, refetchOnFocus = true, refetchOnReconnect = true } = options;
  const savedFetcher = useRef(fetcher);
  const savedOnUpdate = useRef(onUpdate);
  const timerRef = useRef(null);
  const inFlight = useRef(false);

  // Keep latest references without re-subscribing
  useEffect(() => { savedFetcher.current = fetcher; }, [fetcher]);
  useEffect(() => { savedOnUpdate.current = onUpdate; }, [onUpdate]);

  useEffect(() => {
    let cancelled = false;

    const runOnce = async () => {
      if (inFlight.current) return; // prevent overlap
      inFlight.current = true;
      try {
        const data = await savedFetcher.current?.();
        if (!cancelled && data !== undefined && savedOnUpdate.current) {
          savedOnUpdate.current(data);
        }
      } catch {
        // swallow — transient network; next tick will retry
      } finally {
        inFlight.current = false;
      }
    };

    const start = () => {
      if (timerRef.current) return;
      runOnce();
      timerRef.current = setInterval(runOnce, intervalMs);
    };

    const stop = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };

    const onVisibility = () => {
      if (!pauseWhenHidden) return;
      if (document.visibilityState === 'visible') {
        start();        // resume + immediate refresh
      } else {
        stop();
      }
    };

    const onFocus = () => { if (refetchOnFocus) runOnce(); };
    const onReconnect = () => { if (refetchOnReconnect) runOnce(); };

    // Start immediately if the tab is visible — else wait for visibility
    if (!pauseWhenHidden || document.visibilityState === 'visible') {
      start();
    }

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('focus', onFocus);
    window.addEventListener('online', onReconnect);

    return () => {
      cancelled = true;
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('online', onReconnect);
    };
  }, [intervalMs, pauseWhenHidden, refetchOnFocus, refetchOnReconnect]);
}
