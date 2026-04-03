/**
 * AUREM Protected Route Component
 * Requires admin authentication to access AUREM platform features
 */
import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Loader2, Shield } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export const AuremProtectedRoute = ({ children }) => {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const verifyAuth = async () => {
      const token = localStorage.getItem('platform_token');
      
      if (!token) {
        setLoading(false);
        setAuthenticated(false);
        return;
      }

      try {
        const res = await fetch(`${API_URL}/api/platform/auth/verify?token=${token}`);
        const data = await res.json();
        
        if (res.ok && data.valid) {
          setAuthenticated(true);
        } else {
          // Token invalid - clear storage
          localStorage.removeItem('platform_token');
          localStorage.removeItem('platform_user');
          setAuthenticated(false);
        }
      } catch (err) {
        console.error('Auth verification failed:', err);
        setAuthenticated(false);
      }

      setLoading(false);
    };

    verifyAuth();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#0a0a0f]">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="w-8 h-8 text-[#c9a84c]" />
          <span className="text-[#c9a84c] text-xl tracking-wider">AUREM</span>
        </div>
        <Loader2 className="h-8 w-8 animate-spin text-[#c9a84c]" />
        <p className="text-[#5a5a72] text-sm mt-4">Verifying access...</p>
      </div>
    );
  }

  if (!authenticated) {
    // Redirect to login, preserving the intended destination
    return <Navigate to="/platform/login" state={{ from: location }} replace />;
  }

  return children;
};

export const useAuth = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedUser = localStorage.getItem('platform_user');
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        setUser(null);
      }
    }
    setLoading(false);
  }, []);

  const logout = () => {
    localStorage.removeItem('platform_token');
    localStorage.removeItem('platform_user');
    setUser(null);
    window.location.href = '/platform/login';
  };

  const isAuthenticated = () => {
    return !!localStorage.getItem('platform_token');
  };

  return { user, loading, logout, isAuthenticated };
};

export default AuremProtectedRoute;
