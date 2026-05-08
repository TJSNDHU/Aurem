/**
 * Pillar Health Context — iter 292 (hardened iter 282y)
 * Single source of truth for AdminShell. All admin pages read this.
 *
 * iter 282y: previously a single failed fetch flipped EVERY pillar to "red",
 * blanking the entire admin console under PillarGate (e.g., expired JWT, 502,
 * network blip). Now we:
 *   • Cache last-known good state (per-pillar) and never overwrite green with
 *     red just because of a single failure.
 *   • Only escalate to red after 3 consecutive failures (~30s) AND no cached
 *     green within the last 60s.
 *   • Surface fetch-failure as "yellow" (admin still sees content with banner)
 *     during the warning window.
 */
import React, { createContext, useContext, useEffect, useRef, useState } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const POLL_MS = 10000;
const FAIL_THRESHOLD = 3;            // 3 consecutive misses → start degrading
const STICKY_GREEN_MS = 60_000;      // last green within 60s = stay yellow not red

const DEFAULT = { P1: 'loading', P2: 'loading', P3: 'loading', P4: 'loading', worst: 'loading' };

// iter 282al-29 — Auth failures (401/403) do NOT mean infra is degraded.
// Surface them as "auth" so the UI can prompt re-login instead of showing
// a misleading "P1 Infrastructure DEGRADED" banner.
const AUTH_STATE = { P1: 'auth', P2: 'auth', P3: 'auth', P4: 'auth', worst: 'auth' };

const PillarContext = createContext(DEFAULT);

export const PillarProvider = ({ token, children }) => {
  const [state, setState] = useState(DEFAULT);
  const lastGreenRef = useRef({ P1: 0, P2: 0, P3: 0, P4: 0 });
  const failCountRef = useRef(0);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/pillars/health`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        // iter 282al-29 — 401/403 = stale JWT, not infra failure.
        // Render a distinct "auth" state so AdminShell/PillarGate can
        // either redirect to login or show a sign-in prompt, rather
        // than falsely reporting "Infrastructure DEGRADED".
        if (r.status === 401 || r.status === 403) {
          if (!cancelled) setState(AUTH_STATE);
          return;
        }
        if (!r.ok) {
          // Treat HTTP failures the same as network errors below.
          throw new Error(`HTTP ${r.status}`);
        }
        const d = await r.json();
        if (cancelled) return;
        // Track each pillar's last-green timestamp for sticky-yellow.
        const now = Date.now();
        ['P1', 'P2', 'P3', 'P4'].forEach((p) => {
          if (d[p] === 'green') lastGreenRef.current[p] = now;
        });
        failCountRef.current = 0;
        setState(d);
      } catch {
        if (cancelled) return;
        failCountRef.current += 1;
        // Soft-degrade: don't blank the admin console on a single hiccup.
        // While under threshold OR within sticky-green window, fall back to
        // yellow per-pillar, never red.
        const now = Date.now();
        const inSticky = (p) => (now - (lastGreenRef.current[p] || 0)) < STICKY_GREEN_MS;
        const verdict = (p) => {
          if (failCountRef.current < FAIL_THRESHOLD) return 'yellow';
          return inSticky(p) ? 'yellow' : 'red';
        };
        const next = {
          P1: verdict('P1'),
          P2: verdict('P2'),
          P3: verdict('P3'),
          P4: verdict('P4'),
        };
        next.worst = ['red', 'yellow', 'green'].find((s) => Object.values(next).includes(s)) || 'yellow';
        setState(next);
      }
    };

    poll();
    const t = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, [token]);

  return <PillarContext.Provider value={state}>{children}</PillarContext.Provider>;
};

export const usePillarHealth = () => useContext(PillarContext);

export default PillarContext;
