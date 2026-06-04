/**
 * useReliableSSE.js — iter D-63
 * ================================
 * Drop-in replacement for `new EventSource(url)` that survives pod
 * rotations (rolling deploys, K8s evictions, network blips).
 *
 * Why the native EventSource isn't enough
 * ---------------------------------------
 * Native EventSource DOES auto-reconnect by default — but only for
 * specific termination patterns (network errors). It does NOT
 * reconnect when the server returns 5xx, when the connection is
 * cleanly closed by the server, or when the page comes back from a
 * background tab. During rolling deploys we see all three modes.
 *
 * This hook layers on:
 *   - Manual exponential backoff (1s → 2s → 4s → … → 30s cap, with jitter)
 *   - Reconnect on document visibility change (tab refocus)
 *   - Reconnect on network online event
 *   - Last-Event-ID resume header (when server emits `id:` lines)
 *   - Hard ceiling on retries so a permanently-broken endpoint
 *     eventually surfaces an `onError` callback to the UI
 *
 * Usage
 * -----
 *   const { connected, lastEvent, retryCount, close } = useReliableSSE({
 *     url: `${API}/api/bugcatch/stream`,
 *     onMessage: (ev) => { ... },
 *     onError:   (err) => { ... },
 *     maxRetries: 50,            // soft cap; surfaces onError if exceeded
 *   });
 */
import { useEffect, useRef, useState, useCallback } from "react";

const DEFAULTS = {
  initialBackoffMs: 1000,
  maxBackoffMs: 30000,
  jitterMs: 500,
  maxRetries: 50,
};

export function useReliableSSE({
  url,
  onMessage,
  onError,
  withCredentials = false,
  maxRetries = DEFAULTS.maxRetries,
  enabled = true,
}) {
  const [connected, setConnected] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [lastEvent, setLastEvent] = useState(null);

  const esRef = useRef(null);
  const backoffRef = useRef(DEFAULTS.initialBackoffMs);
  const retryRef = useRef(0);
  const lastEventIdRef = useRef("");
  const timerRef = useRef(null);
  const aliveRef = useRef(true);

  const cleanup = useCallback(() => {
    if (esRef.current) {
      try { esRef.current.close(); } catch (_e) { /* ignore */ }
      esRef.current = null;
    }
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const open = useCallback(() => {
    if (!aliveRef.current || !enabled || !url) return;
    cleanup();

    // Append Last-Event-ID as query param if browser doesn't expose
    // header-based resume (most browsers do via the EventSource itself,
    // but we keep this belt-and-braces for picky proxies).
    let fullUrl = url;
    if (lastEventIdRef.current) {
      const sep = url.includes("?") ? "&" : "?";
      fullUrl = `${url}${sep}lastEventId=${encodeURIComponent(lastEventIdRef.current)}`;
    }

    let es;
    try {
      es = new EventSource(fullUrl, { withCredentials });
    } catch (e) {
      // Bad URL — surface immediately and stop.
      onError && onError({ kind: "construction", error: e });
      return;
    }
    esRef.current = es;

    es.onopen = () => {
      if (!aliveRef.current) return;
      setConnected(true);
      backoffRef.current = DEFAULTS.initialBackoffMs;  // reset
      retryRef.current = 0;
      setRetryCount(0);
    };

    es.onmessage = (ev) => {
      if (!aliveRef.current) return;
      if (ev.lastEventId) lastEventIdRef.current = ev.lastEventId;
      setLastEvent(ev);
      onMessage && onMessage(ev);
    };

    es.onerror = () => {
      if (!aliveRef.current) return;
      setConnected(false);
      cleanup();
      retryRef.current += 1;
      setRetryCount(retryRef.current);
      if (retryRef.current > maxRetries) {
        onError && onError({ kind: "max_retries_exceeded", retries: retryRef.current });
        return;
      }
      // Exponential backoff with jitter.
      const base = Math.min(backoffRef.current, DEFAULTS.maxBackoffMs);
      const jitter = Math.floor(Math.random() * DEFAULTS.jitterMs);
      const delay = base + jitter;
      backoffRef.current = Math.min(backoffRef.current * 2, DEFAULTS.maxBackoffMs);
      timerRef.current = setTimeout(open, delay);
    };
  }, [url, withCredentials, onMessage, onError, maxRetries, enabled, cleanup]);

  // Tab refocus → force reconnect if disconnected.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && !connected && enabled) {
        retryRef.current = 0;
        backoffRef.current = DEFAULTS.initialBackoffMs;
        open();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [connected, enabled, open]);

  // Browser regains network → force reconnect.
  useEffect(() => {
    const onOnline = () => {
      if (!connected && enabled) {
        retryRef.current = 0;
        backoffRef.current = DEFAULTS.initialBackoffMs;
        open();
      }
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [connected, enabled, open]);

  // Initial connect + cleanup on unmount.
  useEffect(() => {
    aliveRef.current = true;
    if (enabled && url) open();
    return () => {
      aliveRef.current = false;
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, enabled]);

  const closeNow = useCallback(() => {
    aliveRef.current = false;
    cleanup();
    setConnected(false);
  }, [cleanup]);

  return { connected, lastEvent, retryCount, close: closeNow };
}

export default useReliableSSE;
