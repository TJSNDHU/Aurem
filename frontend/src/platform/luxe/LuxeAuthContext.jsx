/**
 * LuxeAuthContext — customer-side auth provider for /my Luxe portal.
 * Uses BACKEND_URL helper from lib/api.js so production (aurem.live) calls
 * same-origin and avoids stale build-time URLs.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../../lib/api';

const API = BACKEND_URL;
const TOKEN_KEY = 'aurem_customer_token';
const REMEMBER_KEY = 'aurem_customer_remember';
const LuxeAuthCtx = createContext(null);

// Storage helpers — when "remember me" is checked we persist to localStorage
// (survives browser restart). Otherwise we use sessionStorage (cleared when
// the tab closes), so a shared/public computer doesn't leak the session.
const readToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  } catch { return null; }
};
const writeToken = (tok, remember) => {
  try {
    // Always clear the other store first to avoid stale tokens.
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    if (remember) {
      localStorage.setItem(TOKEN_KEY, tok);
      localStorage.setItem(REMEMBER_KEY, '1');
    } else {
      sessionStorage.setItem(TOKEN_KEY, tok);
      localStorage.removeItem(REMEMBER_KEY);
    }
  } catch (_e) { /* private mode etc. — silent fail */ }
};
const clearToken = () => {
  try {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REMEMBER_KEY);
  } catch (_e) { /* noop */ }
};
const readRememberPreference = () => {
  try { return localStorage.getItem(REMEMBER_KEY) === '1'; }
  catch { return false; }
};

export const useLuxeAuth = () => {
  const ctx = useContext(LuxeAuthCtx);
  if (!ctx) throw new Error('useLuxeAuth must be used inside LuxeAuthProvider');
  return ctx;
};

export const LuxeAuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => readToken());
  const [user, setUser]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Default to true: a brand-new visitor signing in expects to stay signed in.
  // Returning visitors restore their previous preference from localStorage.
  const [rememberPreference, setRememberPreference] = useState(
    () => readRememberPreference() || true
  );

  const fetchMe = useCallback(async (tok) => {
    if (!tok) return null;
    try {
      const { data } = await axios.get(`${API}/api/platform/me`, {
        headers: { Authorization: `Bearer ${tok}` }, timeout: 12000,
      });
      setUser(data);
      return data;
    } catch (_e) {
      // Token invalid / backend down — clear so user re-auths.
      clearToken();
      setToken(null);
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      if (token) await fetchMe(token);
      setLoading(false);
    })();
  }, [token, fetchMe]);

  // Listen for the global auth-expired event fired by the shared apiClient
  // 401 interceptor. When any API call comes back with a 401 and refresh
  // also fails, we transparently log the user out so the LuxeAuthOverlay
  // re-prompts — no scary red error toast, no broken page state.
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const onExpired = () => {
      clearToken();
      setToken(null);
      setUser(null);
      setError('Session expired. Please sign in again.');
    };
    window.addEventListener('aurem:auth-expired', onExpired);
    return () => window.removeEventListener('aurem:auth-expired', onExpired);
  }, []);

  const login = async ({ identifier, password, remember = true }) => {
    setError(null);
    try {
      // Identifier can be email OR business_id (BIN). Backend accepts both.
      const looksLikeEmail = typeof identifier === 'string' && identifier.includes('@');
      const body = looksLikeEmail
        ? { email: identifier, password }
        : { business_id: identifier, password };
      const { data } = await axios.post(`${API}/api/platform/auth/login`, body, { timeout: 15000 });
      if (!data?.token) throw new Error(data?.detail || 'Login failed');
      writeToken(data.token, remember);
      setRememberPreference(remember);
      setToken(data.token);
      await fetchMe(data.token);
      return { ok: true };
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Login failed';
      setError(msg);
      return { ok: false, error: msg };
    }
  };

  const signup = async ({ email, password, full_name, company_name, remember = true }) => {
    setError(null);
    try {
      const { data } = await axios.post(`${API}/api/platform/auth/register`, {
        email, password, full_name, company_name,
      }, { timeout: 15000 });
      if (!data?.token) throw new Error(data?.detail || 'Signup failed');
      writeToken(data.token, remember);
      setRememberPreference(remember);
      setToken(data.token);
      await fetchMe(data.token);
      return { ok: true };
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Signup failed';
      setError(msg);
      return { ok: false, error: msg };
    }
  };

  const logout = () => {
    clearToken();
    setToken(null);
    setUser(null);
  };

  return (
    <LuxeAuthCtx.Provider value={{
      token, user, loading, error,
      rememberPreference,
      login, signup, logout,
      refetchMe: () => fetchMe(token),
    }}>
      {children}
    </LuxeAuthCtx.Provider>
  );
};
