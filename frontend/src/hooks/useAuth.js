// src/hooks/useAuth.js
// ─────────────────────────────────────────────────────────
// Drop-in auth hook for ReRoots admin
// Handles login, logout, role checks, route protection
// ─────────────────────────────────────────────────────────

import { useState, useEffect, createContext, useContext } from 'react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on load
    const token = localStorage.getItem('reroots_token');
    if (token) {
      fetchMe(token);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchMe = async (token) => {
    try {
      const res = await fetch(`${API}/auth/rbac/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser({ ...data, token });
      } else {
        localStorage.removeItem('reroots_token');
      }
    } catch (e) {
      localStorage.removeItem('reroots_token');
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const res = await fetch(`${API}/auth/rbac/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    localStorage.setItem('reroots_token', data.token);
    setUser({ ...data.user, token: data.token });
    return data;
  };

  const loginWithGoogle = async (googleToken) => {
    const res = await fetch(`${API}/auth/rbac/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ googleToken })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Google login failed');
    localStorage.setItem('reroots_token', data.token);
    setUser({ ...data.user, token: data.token });
    return data;
  };

  const logout = async () => {
    const token = localStorage.getItem('reroots_token');
    if (token) {
      await fetch(`${API}/auth/rbac/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      }).catch(() => {});
    }
    localStorage.removeItem('reroots_token');
    setUser(null);
  };

  // Check if user can access a section
  const canAccess = (section) => {
    if (!user) return false;
    return user.permissions?.sections?.includes(section) ?? false;
  };

  // Check if section is read-only for this user
  const isReadOnly = (section) => {
    if (!user) return true;
    return user.permissions?.readOnly?.includes(section) ?? false;
  };

  // Get auth header for API calls
  const authHeader = () => ({
    Authorization: `Bearer ${user?.token || localStorage.getItem('reroots_token') || ''}`
  });

  return (
    <AuthContext.Provider value={{
      user, loading,
      login, loginWithGoogle, logout,
      canAccess, isReadOnly, authHeader,
      isOwner: user?.role === 'owner',
      isLoggedIn: !!user
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

// ─── Protected Route Component ───────────────────────────
// Usage: <ProtectedRoute section="accounting-gst"><Accounting /></ProtectedRoute>

export function ProtectedRoute({ section, children }) {
  const { user, loading, canAccess } = useAuth();

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', background:'#FDF9F9' }}>
      <div style={{ fontFamily:'Georgia,serif', color:'#C4BAC0', letterSpacing:'0.3em', fontSize:'0.75rem' }}>
        LOADING...
      </div>
    </div>
  );

  if (!user) {
    window.location.href = '/login';
    return null;
  }

  if (section && !canAccess(section)) {
    return (
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'60vh', flexDirection:'column', gap:'1rem' }}>
        <div style={{ fontFamily:'Georgia,serif', fontSize:'1.4rem', color:'#2D2A2E' }}>Access Restricted</div>
        <div style={{ fontFamily:'monospace', fontSize:'0.75rem', color:'#8A8490' }}>
          Your role ({user.role}) does not have access to this section.
        </div>
      </div>
    );
  }

  return children;
}

export default useAuth;
