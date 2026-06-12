/**
 * AUREM Route Guards — Role-based access control
 * AdminGuard: Only admin / super_admin role can access /admin/* routes
 * TenantGuard: Any logged-in user accesses /dashboard/*
 *
 * iter 332b A-3 — JWT exp check (production auth bug fix)
 * iter 332b A-4 — Session-expired toast handoff via sessionStorage flag,
 *                  read once by AdminLogin / Login page on mount.
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

function flagSessionExpired(scope) {
  // sessionStorage so it doesn't leak across tabs/sessions; cleared by the
  // login page after it shows the toast once.
  try {
    sessionStorage.setItem('aurem_session_expired', scope || 'admin');
  } catch { /* ignore */ }
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
      try { clearAdminAuth(); } catch { /* ignore */ }
      flagSessionExpired('admin');
      setStatus('invalid');
      return;
    }
    if (isExpired(payload)) {
      try { clearAdminAuth(); } catch { /* ignore */ }
      flagSessionExpired('admin');
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
      flagSessionExpired('customer');
      setStatus('invalid');
      return;
    }
    if (isExpired(payload)) {
      try { clearCustomerAuth(); } catch { /* ignore */ }
      flagSessionExpired('customer');
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

// CustomerGuard — guards /my/* sub-pages. Mirrors TenantGuard but bounces to
// /my (LuxeDashboardPreview), whose LuxeAuthOverlay handles the login flow,
// instead of the tenant /login page. (iter D-82c — customer portal wiring.)
export const CustomerGuard = ({ children }) => {
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
      flagSessionExpired('customer');
      setStatus('invalid');
      return;
    }
    if (isExpired(payload)) {
      try { clearCustomerAuth(); } catch { /* ignore */ }
      flagSessionExpired('customer');
      setStatus('expired');
      return;
    }
    setStatus('authorized');
  }, []);

  if (status === 'checking') return null;
  if (status !== 'authorized') return <Navigate to="/my" replace />;
  return children;
};