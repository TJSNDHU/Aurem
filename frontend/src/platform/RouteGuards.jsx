/**
 * AUREM Route Guards — Role-based access control
 * AdminGuard: Only admin / super_admin role can access /admin/* routes
 * TenantGuard: Any logged-in user accesses /dashboard/*
 *
 * iter 332b A-3 (2026-02-24) — Auth bug fix:
 *   • Adds JWT `exp` claim check so an expired token NEVER grants access.
 *     Without this, a stale token left in localStorage after the JWT
 *     expired would still pass the `is_admin` test, render the dashboard,
 *     and then every API call would 401 — which is exactly what the
 *     founder reported on production ("direct link lands on dashboard
 *     without asking for login", "logout moves to dashboard").
 *   • On expiry, clears the stale slot via `clearAdminAuth()` so the
 *     next visit to /admin/login shows the form cleanly.
 */
import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { getPlatformToken, clearAdminAuth, clearCustomerAuth } from '../utils/secureTokenStore';

function decodeToken(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

function isExpired(payload) {
  if (!payload || typeof payload.exp !== 'number') return false;
  const nowSec = Math.floor(Date.now() / 1000);
  return payload.exp < nowSec;
}

export const AdminGuard = ({ children }) => {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    const token = getPlatformToken();
    if (!token) {
      setStatus('no_token');
      return;
    }
    const payload = decodeToken(token);
    if (!payload) {
      // Corrupt token — wipe and bounce.
      try { clearAdminAuth(); } catch { /* ignore */ }
      setStatus('invalid');
      return;
    }
    if (isExpired(payload)) {
      // Stale JWT — wipe both possible slots so the next render doesn't
      // re-read the same dead token from a fallback slot.
      try { clearAdminAuth(); } catch { /* ignore */ }
      setStatus('expired');
      return;
    }
    if (payload.is_admin || payload.is_super_admin || payload.role === 'super_admin' || payload.role === 'admin') {
      setStatus('authorized');
    } else {
      setStatus('forbidden');
    }
  }, []);

  if (status === 'checking') return null;
  if (status === 'no_token' || status === 'invalid' || status === 'expired') {
    return <Navigate to="/admin/login" replace />;
  }
  if (status === 'forbidden') return <Navigate to="/dashboard" replace />;
  return children;
};

export const TenantGuard = ({ children }) => {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    const token = getPlatformToken();
    if (!token) {
      setStatus('no_token');
      return;
    }
    const payload = decodeToken(token);
    if (!payload) {
      try { clearCustomerAuth(); } catch { /* ignore */ }
      setStatus('invalid');
      return;
    }
    if (isExpired(payload)) {
      try { clearCustomerAuth(); } catch { /* ignore */ }
      setStatus('expired');
      return;
    }
    setStatus('authorized');
  }, []);

  if (status === 'checking') return null;
  if (status === 'no_token' || status === 'invalid' || status === 'expired') {
    return <Navigate to="/login" replace />;
  }
  return children;
};
