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
const TOKEN_KEYS = ['aurem_customer_token', 'aurem_admin_token', 'auth_token'];

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

const clearTokens = () => {
  if (typeof window === 'undefined') return;
  for (const k of TOKEN_KEYS) {
    try {
      localStorage.removeItem(k);
      sessionStorage.removeItem(k);
    } catch (_e) { /* ignore */ }
  }
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
      clearTokens();
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
    clearTokens();
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
