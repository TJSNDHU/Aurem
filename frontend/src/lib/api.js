// API Configuration - Shared across all components
import axios from 'axios';

const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;

    // For localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }

    // For custom domains (aurem.live, aurem.live, etc.) — ALWAYS use same origin
    // so API calls go to the correct backend regardless of env var.
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }

    // For preview/staging environments, use env var if available
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }

    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

export const BACKEND_URL = getBackendUrl();
export const API = `${BACKEND_URL}/api`;

// ─────────────────────────────────────────────────────────────
// Auth-aware axios instance with graceful 401 handling.
//
// Why: Sentinel telemetry showed "Auth Expired" was the #1 user-facing
// error category (78 events). Most app components use plain `axios` or
// `fetch` directly and dump the raw 401 to a toast. This module exposes
// `apiClient` — a shared axios instance that:
//
//   1. Auto-attaches the platform JWT (localStorage / sessionStorage)
//   2. On 401, tries ONE silent refresh against /api/auth/admin/refresh
//   3. If refresh fails, fires an `aurem:auth-expired` window event so
//      the active layout (Luxe overlay, AdminConsole) can re-prompt
//      login WITHOUT a hard page reload.
//
// Components are encouraged to migrate to this client over time. Existing
// raw fetch/axios calls keep working — this is purely additive.
// ─────────────────────────────────────────────────────────────
// iter 326ll — ROLE-AWARE TOKEN ACCESS for the 401 interceptor.
// The OLD `TOKEN_KEYS = [...]` array combined with a blind
// `clearTokens()` wiped admin + customer + legacy slots on any 401 from
// `/api/auth/*`. That undid the iter 326o role separation: a single
// expired admin refresh fired by a background poller would silently
// kick out the customer session in the same browser. Net effect for
// the founder: "login and logout broken in production" — even though
// the backend was minting JWTs correctly.
//
// Fix: read tokens preferring the most recently-used slot; if we have
// to clear on a hard auth failure, clear ONLY the slot the failing
// request was using. Never touch the other role.
const ADMIN_TOKEN_KEY    = 'aurem_admin_token';
const CUSTOMER_TOKEN_KEY = 'aurem_customer_token';
const LEGACY_TOKEN_KEY   = 'auth_token';
const TOKEN_KEYS = [CUSTOMER_TOKEN_KEY, ADMIN_TOKEN_KEY, LEGACY_TOKEN_KEY];

const readToken = () => {
  if (typeof window === 'undefined') return null;
  for (const k of TOKEN_KEYS) {
    try {
      const t = localStorage.getItem(k) || sessionStorage.getItem(k);
      if (t) return t;
    } catch (_e) { /* ignore */ }
  }
  return null;
};

// Identify which slot a token came from so we can clear *only* that slot
// on a hard refresh failure. Falls back to the legacy slot.
const _readSlot = (key) => {
  try { return localStorage.getItem(key) || sessionStorage.getItem(key) || null; }
  catch { return null; }
};

const _detectActiveSlot = (token) => {
  if (!token) {
    // Pick whichever slot has SOMETHING — admin first only if no customer.
    if (_readSlot(CUSTOMER_TOKEN_KEY)) return CUSTOMER_TOKEN_KEY;
    if (_readSlot(ADMIN_TOKEN_KEY))    return ADMIN_TOKEN_KEY;
    return LEGACY_TOKEN_KEY;
  }
  // Match the actual JWT string against each slot to pinpoint origin.
  for (const k of TOKEN_KEYS) {
    if (_readSlot(k) === token) return k;
  }
  return LEGACY_TOKEN_KEY;
};

const _clearSingleSlot = (key) => {
  if (typeof window === 'undefined') return;
  try { localStorage.removeItem(key); }   catch (_e) { /* ignore */ }
  try { sessionStorage.removeItem(key); } catch (_e) { /* ignore */ }
};

const dispatchAuthExpired = () => {
  if (typeof window === 'undefined') return;
  try {
    window.dispatchEvent(new CustomEvent('aurem:auth-expired'));
  } catch (_e) { /* ignore */ }
};

export const apiClient = axios.create({
  baseURL: BACKEND_URL,
  timeout: 20000,
});

apiClient.interceptors.request.use((config) => {
  const tok = readToken();
  if (tok) {
    config.headers = config.headers || {};
    if (!config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${tok}`;
    }
  }
  return config;
});

let _refreshing = null;

apiClient.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error?.response?.status;
    const originalReq = error?.config;
    if (status !== 401 || !originalReq || originalReq._retried) {
      return Promise.reject(error);
    }
    // Skip refresh attempts for the auth endpoints themselves to avoid loops.
    if ((originalReq.url || '').includes('/api/auth/')) {
      // iter 326ll — only clear the slot the FAILING request used.
      // Never wipe both roles from one 401 (that's the regression that
      // broke prod login/logout).
      const failingTok = (originalReq.headers || {}).Authorization
        ? String(originalReq.headers.Authorization).replace(/^Bearer\s+/i, '')
        : null;
      const slot = _detectActiveSlot(failingTok);
      _clearSingleSlot(slot);
      dispatchAuthExpired();
      return Promise.reject(error);
    }

    originalReq._retried = true;
    try {
      // Coalesce concurrent refresh attempts into one request.
      if (!_refreshing) {
        _refreshing = axios
          .post(
            `${BACKEND_URL}/api/auth/admin/refresh`,
            {},
            { withCredentials: true, timeout: 8000 }
          )
          .then((r) => r?.data?.token || r?.data?.access_token || null)
          .catch(() => null)
          .finally(() => {
            const p = _refreshing;
            // Reset *after* downstream awaits read the value.
            setTimeout(() => { if (_refreshing === p) _refreshing = null; }, 0);
          });
      }
      const newTok = await _refreshing;
      if (newTok && typeof window !== 'undefined') {
        // Persist using whichever key the app is already using.
        try {
          for (const k of TOKEN_KEYS) {
            if (localStorage.getItem(k)) { localStorage.setItem(k, newTok); break; }
            if (sessionStorage.getItem(k)) { sessionStorage.setItem(k, newTok); break; }
          }
        } catch (_e) { /* ignore */ }
        originalReq.headers = originalReq.headers || {};
        originalReq.headers.Authorization = `Bearer ${newTok}`;
        return apiClient(originalReq);
      }
    } catch (_e) {
      /* fall through to graceful sign-out */
    }
    // iter 326ll — refresh path is over; clear ONLY the slot the
    // failing request used. Other role's token in the same browser
    // stays untouched.
    {
      const failingTok = (originalReq.headers || {}).Authorization
        ? String(originalReq.headers.Authorization).replace(/^Bearer\s+/i, '')
        : null;
      const slot = _detectActiveSlot(failingTok);
      _clearSingleSlot(slot);
    }
    dispatchAuthExpired();
    return Promise.reject(error);
  }
);

// ─── GLOBAL axios safety net ─────────────────────────────────
// Many components still use the raw `axios` import (LuxeAuthContext,
// admin pages, etc.). Install a SOFT interceptor on the default axios
// instance that, when it sees a 401 from any /api endpoint, dispatches
// the same `aurem:auth-expired` event so the active layout can re-prompt
// without showing a scary red error toast. We do NOT auto-retry here —
// that's apiClient's job — only the graceful sign-out signal.
axios.interceptors.response.use(
  (resp) => resp,
  (error) => {
    try {
      const status = error?.response?.status;
      const url = error?.config?.url || '';
      // 401 — auth expired
      if (
        status === 401 &&
        url.includes('/api/') &&
        !url.includes('/api/auth/login') &&
        !url.includes('/api/auth/admin/login') &&
        !url.includes('/api/platform/auth/login')
      ) {
        dispatchAuthExpired();
      }
      // iter 322 — 402 service_locked. Surface to UpgradeModal listener.
      if (status === 402 && url.includes('/api/')) {
        const detail = error?.response?.data?.detail || error?.response?.data || {};
        if (detail.error === 'service_locked') {
          try {
            window.dispatchEvent(new CustomEvent('aurem:service-locked', { detail }));
          } catch (_e) { /* ignore */ }
        }
      }
      // iter 322 — 429 quota_exceeded. Surface for upgrade-prompt UX.
      if (status === 429 && url.includes('/api/')) {
        const detail = error?.response?.data?.detail || error?.response?.data || {};
        if (detail.error === 'quota_exceeded') {
          try {
            window.dispatchEvent(new CustomEvent('aurem:quota-exceeded', { detail }));
          } catch (_e) { /* ignore */ }
        }
      }
    } catch (_e) { /* never throw from interceptor */ }
    return Promise.reject(error);
  }
);

export default apiClient;
