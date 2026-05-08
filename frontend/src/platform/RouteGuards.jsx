/**
 * AUREM Route Guards — Role-based access control
 * AdminGuard: Only super_admin role can access /admin/* routes
 * TenantGuard: Only tenant/non-admin users access /dashboard/*
 */
import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { getPlatformToken } from '../utils/secureTokenStore';

function decodeToken(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
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
      setStatus('invalid');
      return;
    }
    if (payload.is_admin || payload.is_super_admin || payload.role === 'super_admin' || payload.role === 'admin') {
      setStatus('authorized');
    } else {
      setStatus('forbidden');
    }
  }, []);

  if (status === 'checking') return null;
  if (status === 'no_token' || status === 'invalid') return <Navigate to="/admin/login" replace />;
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
      setStatus('invalid');
      return;
    }
    setStatus('authorized');
  }, []);

  if (status === 'checking') return null;
  if (status === 'no_token' || status === 'invalid') return <Navigate to="/login" replace />;
  return children;
};
