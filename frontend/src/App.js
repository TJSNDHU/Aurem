/**
 * AUREM AI - Autonomous AI Workforce Platform
 * Complete Commercial AI System
 */

import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "./App.css";

// Lazy load components
const FaceIDAuthWrapper = lazy(() => import('./components/FaceIDAuthWrapper'));
const AuremDashboard = lazy(() => import('./platform/AuremDashboard'));
const PlatformLanding = lazy(() => import('./platform/PlatformLanding'));
const AdminMissionControl = lazy(() => import('./platform/AdminMissionControl'));
const CustomSubscriptionBuilder = lazy(() => import('./platform/CustomSubscriptionBuilder'));

// Loading Spinner
const LoadingSpinner = () => (
  <div className="min-h-screen bg-[#050505] flex items-center justify-center">
    <div className="text-center">
      <div className="relative w-16 h-16 mx-auto">
        <div className="w-16 h-16 border-2 border-[#D4AF37]/20 rounded-full"></div>
        <div className="absolute top-0 left-0 w-16 h-16 border-2 border-transparent border-t-[#D4AF37] rounded-full animate-spin"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <div className="w-3 h-3 bg-[#D4AF37] rounded-full animate-pulse"></div>
        </div>
      </div>
      <p className="mt-4 text-sm text-[#666]">Initializing AUREM...</p>
    </div>
  </div>
);

// Main App Component
function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#050505]">
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<PlatformLanding />} />
            <Route path="/platform" element={<PlatformLanding />} />
            <Route path="/auth" element={<FaceIDAuthWrapper />} />
            <Route path="/login" element={<Navigate to="/auth" replace />} />
            <Route path="/register" element={<Navigate to="/auth?mode=register" replace />} />
            
            {/* Dashboard */}
            <Route path="/dashboard" element={<AuremDashboard />} />
            <Route path="/dashboard/*" element={<AuremDashboard />} />
            
            {/* Admin Routes */}
            <Route path="/admin/mission-control" element={<AdminMissionControl />} />
            <Route path="/subscriptions/custom" element={<CustomSubscriptionBuilder />} />
            
            {/* Catch-all redirect */}
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
    </BrowserRouter>
  );
}

export default App;
