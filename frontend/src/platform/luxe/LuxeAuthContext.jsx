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
const LuxeAuthCtx = createContext(null);

export const useLuxeAuth = () => {
  const ctx = useContext(LuxeAuthCtx);
  if (!ctx) throw new Error('useLuxeAuth must be used inside LuxeAuthProvider');
  return ctx;
};

export const LuxeAuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      localStorage.removeItem(TOKEN_KEY);
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

  const login = async ({ identifier, password }) => {
    setError(null);
    try {
      // Identifier can be email OR business_id (BIN). Backend accepts both.
      const looksLikeEmail = typeof identifier === 'string' && identifier.includes('@');
      const body = looksLikeEmail
        ? { email: identifier, password }
        : { business_id: identifier, password };
      const { data } = await axios.post(`${API}/api/platform/auth/login`, body, { timeout: 15000 });
      if (!data?.token) throw new Error(data?.detail || 'Login failed');
      localStorage.setItem(TOKEN_KEY, data.token);
      setToken(data.token);
      await fetchMe(data.token);
      return { ok: true };
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Login failed';
      setError(msg);
      return { ok: false, error: msg };
    }
  };

  const signup = async ({ email, password, full_name, company_name }) => {
    setError(null);
    try {
      const { data } = await axios.post(`${API}/api/platform/auth/register`, {
        email, password, full_name, company_name,
      }, { timeout: 15000 });
      if (!data?.token) throw new Error(data?.detail || 'Signup failed');
      localStorage.setItem(TOKEN_KEY, data.token);
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
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <LuxeAuthCtx.Provider value={{
      token, user, loading, error,
      login, signup, logout,
      refetchMe: () => fetchMe(token),
    }}>
      {children}
    </LuxeAuthCtx.Provider>
  );
};
