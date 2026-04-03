/**
 * AUREM AI - Autonomous AI Workforce Platform
 * Clean, standalone platform without ReRoots e-commerce
 */

import React, { useState, useEffect, lazy, Suspense, createContext, useContext } from "react";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import { Toaster, toast } from "sonner";
import axios from "axios";
import "./App.css";

// Lazy load platform components
const PlatformLanding = lazy(() => import('./platform/PlatformLanding'));
const PlatformAuth = lazy(() => import('./platform/PlatformAuth'));
const PlatformDashboard = lazy(() => import('./platform/PlatformDashboard'));
const AuremAI = lazy(() => import('./platform/AuremAI'));
const AuremLanding = lazy(() => import('./platform/AuremLanding'));
const AuremOnboarding = lazy(() => import('./platform/AuremOnboarding'));
const UnifiedInbox = lazy(() => import('./platform/UnifiedInbox'));
const VoiceCommand = lazy(() => import('./platform/VoiceCommand'));
const VoiceAnalytics = lazy(() => import('./platform/VoiceAnalytics'));
const WhatsAppIntegration = lazy(() => import('./platform/WhatsAppIntegration'));
const GmailIntegration = lazy(() => import('./platform/GmailIntegration'));
const BrainDebugger = lazy(() => import('./platform/BrainDebugger'));
const DeveloperPortal = lazy(() => import('./platform/DeveloperPortal'));
const OmniLive = lazy(() => import('./platform/OmniLive'));
const ZImageStudio = lazy(() => import('./platform/ZImageStudio'));
const OrchestratorCommandCenter = lazy(() => import('./pages/OrchestratorCommandCenter'));
const CommercialDashboard = lazy(() => import('./pages/CommercialDashboard'));

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Auth Context for AUREM Platform
const AuremAuthContext = createContext(null);

export const useAuremAuth = () => {
  const context = useContext(AuremAuthContext);
  if (!context) {
    throw new Error('useAuremAuth must be used within AuremAuthProvider');
  }
  return context;
};

// Loading Spinner
const LoadingSpinner = () => (
  <div className="min-h-screen bg-[#050505] flex items-center justify-center">
    <div className="relative">
      <div className="w-16 h-16 border-2 border-[#D4AF37]/20 rounded-full"></div>
      <div className="absolute top-0 left-0 w-16 h-16 border-2 border-transparent border-t-[#D4AF37] rounded-full animate-spin"></div>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
        <div className="w-3 h-3 bg-[#D4AF37] rounded-full animate-pulse"></div>
      </div>
    </div>
  </div>
);

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuremAuth();
  const location = useLocation();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  return children;
};

// Auth Provider
const AuremAuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [workspace, setWorkspace] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('platform_token');
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      // Get user data from localStorage (set by PlatformAuth)
      const userData = localStorage.getItem('platform_user');
      if (userData) {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
        setWorkspace({ name: parsedUser.company_name || 'AUREM Workspace' });
      }
    } catch (error) {
      localStorage.removeItem('platform_token');
      localStorage.removeItem('platform_user');
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API_URL}/api/aurem/auth/login`, { email, password });
      const { token, user: userData, workspace: wsData } = response.data;
      localStorage.setItem('aurem_token', token);
      setUser(userData);
      setWorkspace(wsData);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Login failed' };
    }
  };

  const register = async (data) => {
    try {
      const response = await axios.post(`${API_URL}/api/aurem/auth/register`, data);
      const { token, user: userData, workspace: wsData } = response.data;
      localStorage.setItem('aurem_token', token);
      setUser(userData);
      setWorkspace(wsData);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Registration failed' };
    }
  };

  const logout = () => {
    localStorage.removeItem('platform_token');
    localStorage.removeItem('platform_user');
    setUser(null);
    setWorkspace(null);
  };

  const value = {
    user,
    workspace,
    loading,
    login,
    register,
    logout,
    checkAuth
  };

  return (
    <AuremAuthContext.Provider value={value}>
      {children}
    </AuremAuthContext.Provider>
  );
};

// Main App Component
function App() {
  return (
    <BrowserRouter>
      <AuremAuthProvider>
        <div className="min-h-screen bg-[#050505]">
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<PlatformLanding />} />
              <Route path="/platform" element={<PlatformLanding />} />
              <Route path="/auth" element={<PlatformAuth />} />
              <Route path="/login" element={<Navigate to="/auth" replace />} />
              <Route path="/register" element={<Navigate to="/auth?mode=register" replace />} />
              
              {/* AUREM Landing & Marketing */}
              <Route path="/aurem" element={<AuremLanding />} />
              <Route path="/vanguard" element={<AuremLanding />} />
              
              {/* Protected Dashboard Routes */}
              <Route path="/dashboard" element={
                <ProtectedRoute>
                  <PlatformDashboard />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/ai" element={
                <ProtectedRoute>
                  <AuremAI />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/inbox" element={
                <ProtectedRoute>
                  <UnifiedInbox />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/voice" element={
                <ProtectedRoute>
                  <VoiceCommand />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/voice/analytics" element={
                <ProtectedRoute>
                  <VoiceAnalytics />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/whatsapp" element={
                <ProtectedRoute>
                  <WhatsAppIntegration />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/gmail" element={
                <ProtectedRoute>
                  <GmailIntegration />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/brain" element={
                <ProtectedRoute>
                  <BrainDebugger />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/developer" element={
                <ProtectedRoute>
                  <DeveloperPortal />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/live" element={
                <ProtectedRoute>
                  <OmniLive />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/studio" element={
                <ProtectedRoute>
                  <ZImageStudio />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/orchestrator" element={
                <ProtectedRoute>
                  <OrchestratorCommandCenter />
                </ProtectedRoute>
              } />
              
              <Route path="/dashboard/commercial" element={
                <ProtectedRoute>
                  <CommercialDashboard />
                </ProtectedRoute>
              } />
              
              {/* Onboarding */}
              <Route path="/onboarding" element={
                <ProtectedRoute>
                  <AuremOnboarding />
                </ProtectedRoute>
              } />
              
              {/* Catch-all redirect to landing */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          
          {/* Toast Notifications */}
          <Toaster 
            position="top-right"
            toastOptions={{
              style: {
                background: '#0A0A0A',
                border: '1px solid rgba(212, 175, 55, 0.2)',
                color: '#F4F4F4',
              },
            }}
          />
        </div>
      </AuremAuthProvider>
    </BrowserRouter>
  );
}

export default App;
