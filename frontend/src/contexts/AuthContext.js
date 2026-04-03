import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API } from "@/utils/api";

export const AuthContext = createContext(null);

// Auth Provider - Robust session persistence with cross-tab logout detection
export const AuthProvider = ({ children }) => {
  // Initialize user from cache immediately to prevent flash of logged-out state
  const [user, setUser] = useState(() => {
    try {
      const cachedUser = localStorage.getItem("reroots_user");
      const token = localStorage.getItem("reroots_token");
      if (cachedUser && token) {
        return JSON.parse(cachedUser);
      }
    } catch (e) {
      console.error("Failed to parse cached user on init");
    }
    return null;
  });
  const [loading, setLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);

  // Check auth on mount - validate token with backend
  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem("reroots_token");
    if (!token) {
      setUser(null);
      setLoading(false);
      setAuthChecked(true);
      return;
    }
    
    try {
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 10000 // 10 second timeout
      });
      // Update user and cache
      setUser(res.data);
      localStorage.setItem("reroots_user", JSON.stringify(res.data));
    } catch (error) {
      // Only clear session on confirmed auth errors (401/403)
      if (error.response && (error.response.status === 401 || error.response.status === 403)) {
        console.log("Auth token invalid, clearing session");
        localStorage.removeItem("reroots_token");
        localStorage.removeItem("reroots_remember_me");
        localStorage.removeItem("reroots_user");
        setUser(null);
      } else {
        // For network errors, timeouts, or server errors - keep the cached user
        console.warn("Auth check failed (network/server issue), keeping cached session:", error.message);
      }
    } finally {
      setLoading(false);
      setAuthChecked(true);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // CRITICAL: Cross-tab logout detection
  // When user logs out from ANY tab, ALL other tabs will detect and logout too
  useEffect(() => {
    const handleStorageChange = (event) => {
      // Detect when token is removed (logout from another tab)
      if (event.key === 'reroots_token' && event.newValue === null) {
        console.log('[Auth] Logout detected from another tab - logging out this tab');
        setUser(null);
        // Redirect to home page (not login with session_expired)
        if (window.location.pathname.includes('/admin')) {
          window.location.href = '/';
        }
      }
      
      // Detect logout trigger signal (for same-origin tabs)
      if (event.key === 'reroots_logout_signal') {
        console.log('[Auth] Logout signal received - logging out this tab');
        setUser(null);
        localStorage.removeItem("reroots_token");
        localStorage.removeItem("reroots_user");
        localStorage.removeItem("reroots_remember_me");
        if (window.location.pathname.includes('/admin')) {
          window.location.href = '/';
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Periodic auth check every 5 minutes (only if user is logged in)
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(() => {
      checkAuth();
    }, 5 * 60 * 1000); // 5 minutes
    return () => clearInterval(interval);
  }, [user, checkAuth]);

  // Additional check: Verify token exists on focus (when user switches back to tab)
  useEffect(() => {
    const handleFocus = () => {
      const token = localStorage.getItem("reroots_token");
      if (!token && user) {
        console.log('[Auth] Token missing on tab focus - logging out');
        setUser(null);
        if (window.location.pathname.includes('/admin')) {
          window.location.href = '/';
        }
      }
    };

    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [user]);

  const login = async (email, password, phone = null, rememberMe = false) => {
    const loginData = phone ? { phone, password } : { email, password };
    const res = await axios.post(`${API}/auth/login`, loginData);
    
    // Store token
    localStorage.setItem("reroots_token", res.data.token);
    
    // Cache user data for offline/network issues
    localStorage.setItem("reroots_user", JSON.stringify(res.data.user));
    
    // If "Remember Me" is checked, store a flag for longer session
    if (rememberMe) {
      localStorage.setItem("reroots_remember_me", "true");
    } else {
      localStorage.removeItem("reroots_remember_me");
    }
    
    setUser(res.data.user);
    return res.data.user;
  };

  const register = async (data) => {
    const res = await axios.post(`${API}/auth/register`, data);
    localStorage.setItem("reroots_token", res.data.token);
    localStorage.setItem("reroots_user", JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = () => {
    // Broadcast logout to all other tabs using a signal
    // This triggers the storage event in other tabs
    localStorage.setItem('reroots_logout_signal', Date.now().toString());
    
    // Clear all auth data
    localStorage.removeItem("reroots_token");
    localStorage.removeItem("reroots_remember_me");
    localStorage.removeItem("reroots_user");
    
    // Remove the signal after a brief delay
    setTimeout(() => {
      localStorage.removeItem('reroots_logout_signal');
    }, 100);
    
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading, authChecked }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
