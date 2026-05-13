/**
 * AUREM AI - Autonomous AI Workforce Platform
 * Complete Commercial AI System
 */

import React, { Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { HelmetProvider } from "react-helmet-async";
import { ThemeProvider, useTheme } from "./theme/ThemeContext";
import { AccessibilityWrapper } from "./components/AccessibilityWrapper";
import "./theme/theme.css";
import "./theme/unified-theme.css";
import "./App.css";
// Eager imports for landing routes — lazy() hangs in some envs (webpack chunk
// not resolving), keeping the splash forever. These pages are tiny enough.
import AuremHomepage from "./platform/AuremHomepage";
import BuildLog from "./platform/BuildLog";
import CustomerEditPortal from "./pages/CustomerEditPortal";
// AUTO-EAGER (iter 301): converted from lazy() because chunk-split hangs in this env
import FaceIDAuthWrapper from './components/FaceIDAuthWrapper';
import AuremDashboard from './platform/AuremDashboard';
import PlatformLanding from './platform/PlatformLanding';
import AdminMissionControl from './platform/AdminMissionControl';
import CustomSubscriptionBuilder from './platform/CustomSubscriptionBuilder';
import AdminPlanManager from './platform/AdminPlanManager';
import AdminLogin from './platform/AdminLogin';
import LuxeDashboardPreview from './platform/preview/LuxeDashboardPreview';
import LuxeServicesPreview from './platform/preview/LuxeServicesPreview';
import Admin2FAEnroll from './platform/Admin2FAEnroll';
import BoardroomPage from './platform/BoardroomPage';
import AdminShell from './platform/AdminShell';
import UpgradeModal from './components/UpgradeModal';
import TrialBanner from './components/TrialBanner';
import MyBilling from './pages/MyBilling';
import AdminSSOT from './platform/AdminSSOT';
import AdminConsole from './platform/AdminConsole';
import AdminAntigravitySkills from './platform/AdminAntigravitySkills';
import AdminMemoir from './platform/AdminMemoir';
import AWBCockpit from './platform/AWBCockpit';
import AdminDiagnostics from './platform/AdminDiagnostics';
import LeadsDashboard from './platform/LeadsDashboard';
import PanicSettings from './platform/PanicSettings';
import AnalyticsDashboard from './platform/AnalyticsDashboard';
import PanicAlerts from './platform/PanicAlerts';
import ClientReport from './platform/ClientReport';
import AuremReport from './platform/AuremReport';
import OnboardingWelcome from './platform/OnboardingWelcome';
import OnboardingPixelStep from './platform/OnboardingPixelStep';
import AuremSampleWebsite from './platform/AuremSampleWebsite';
import FuturisticDemo from './platform/FuturisticDemo';
import Demo from './platform/Demo';
import SharedReportPage from './platform/SharedReportPage';
import PrivacyPolicy from './platform/PrivacyPolicy';
import PublicStatus from './platform/PublicStatus';
import TermsOfService from './platform/TermsOfService';
import RefundPolicy from './platform/RefundPolicy';
import AcceptableUsePolicy from './platform/AcceptableUsePolicy';
import ContactPage from './platform/ContactPage';
import ForgotPassword from './platform/ForgotPassword';
import ForgotPin from './platform/ForgotPin';
import ResetPassword from './platform/ResetPassword';
import VerifyEmail from './platform/VerifyEmail';
import GoogleAuthCallback from './platform/GoogleAuthCallback';
import SupportPage from './platform/SupportPage';
import OraPWA from './platform/OraPWA';
import SentinelErrorBoundary from './platform/SentinelErrorBoundary';
import PricingPage from './platform/PricingPage';
import RepairQuote from './pages/RepairQuote';
import ShareableReport from './pages/ShareableReport';
import AdminBusinessIds from './platform/AdminBusinessIds';
import FrameworkMap from './platform/FrameworkMap';
import SystemOverviewPublic from './platform/SystemOverviewPublic';
import SEOAuditPage from './platform/SEOAuditPage';
import AdminRootCommand from './platform/AdminRootCommand';
import AuditLiveDashboard from './platform/admin/AuditLiveDashboard';
import AdminStemFix from './platform/AdminStemFix';
import AdminPillarsMap from './platform/AdminPillarsMap';
import AdminSidebarBlocks from './platform/AdminSidebarBlocks';
import AdminVanguard from './platform/AdminVanguard';
import SystemOverview from './platform/SystemOverview';
import SystemPulseLive from './platform/SystemPulseLive';
// CustomerSiteMonitor + CustomerBoardReport are now lazy-loaded INSIDE
// CustomerPortal (see CustomerPortal.jsx). They were previously standalone
// /my/monitor and /my/board-report routes which bypassed the portal's auth
// context + sidebar chrome — causing them to render as "blank" full-page
// components. Imports removed to drop dead code from the App.js bundle.
import AvatarManager from './platform/admin/AvatarManager';
import CustomerHealthPanel from './platform/admin/CustomerHealthPanel';
import AdminBrainPage from './platform/admin/AdminBrainPage';
import CouncilAuditPage from './platform/admin/CouncilAuditPage';
import DesignExtractStudio from './platform/admin/DesignExtractStudio';
import OraOptimizer from './platform/admin/OraOptimizer';
import OraCtoCockpit from './platform/admin/OraCtoCockpit';
import GitCommitGate from './platform/admin/GitCommitGate';
import OraChat from './platform/admin/OraChat';
import OraSettings from './platform/admin/OraSettings';
import FounderSaves from './platform/admin/FounderSaves';
import IncidentLedger from './platform/admin/IncidentLedger';
import DesignExtractPublic from './platform/DesignExtractPublic';
import MonitorFreeLanding from './platform/MonitorFreeLanding';
import AdminSiteMonitor from './platform/AdminSiteMonitor';
import PublicStatusPage from './platform/PublicStatusPage';
import AdminSystemAudit from './platform/AdminSystemAudit';
import AdminWiringAudit from './platform/AdminWiringAudit';
import AdminControlCenter from './platform/AdminControlCenter';
import AdminCustomer360 from './platform/AdminCustomer360';
import AdminImpersonationLog from './platform/AdminImpersonationLog';
import AdminEvolver from './platform/AdminEvolver';
import AdminSelfRepair from './platform/AdminSelfRepair';
import AdminBuilderDetail from './platform/AdminBuilderDetail';
import AdminOpenFang from './platform/AdminOpenFang';
import AdminShortcuts from './platform/AdminShortcuts';
import SystemStatusChip from './platform/SystemStatusChip';
import AdminSentinelClient from './platform/AdminSentinelClient';
import AdminAutoFixer from './platform/AdminAutoFixer';
import AdminCaseStudy from './platform/AdminCaseStudy';
import AdminHunterTest from './platform/AdminHunterTest';
import AdminBrainGraph from './platform/AdminBrainGraph';
import AdminLinksHub from './platform/AdminLinksHub';
import AdminBrowserAgent from './platform/AdminBrowserAgent';
import AdminLeadsMining from './platform/AdminLeadsMining';
import AdminDailyLog from './platform/AdminDailyLog';
import BrainGraphShare from './pages/BrainGraphShare';
import CustomerPortal from './platform/CustomerPortal';

// Lazy load components














import { AdminGuard } from './platform/RouteGuards';
























// AUTO-EAGER (iter 301): named-export pages converted to direct imports
import { LegalIndex, LegalDocument } from './platform/LegalPages';
import { PlatformLogin, PlatformSignup } from './platform/PlatformAuth';
import AccountSecurity from './platform/AccountSecurity';
import ORAWidget from './components/ORAWidget';




// const SentinelOverwatch = lazy(() => import('./platform/SentinelOverwatch'));  // DEPRECATED iter 266 — superseded by AdminRootCommand
































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

// Themed Toast wrapper
function ThemedToaster() {
  const { theme } = useTheme();
  return (
    <Toaster 
      position="top-right"
      toastOptions={{
        style: theme === 'light' ? {
          background: '#FFFFFF',
          border: '1px solid rgba(184, 150, 46, 0.2)',
          color: '#1A1A1A',
        } : {
          background: '#0A0A0A',
          border: '1px solid rgba(212, 175, 55, 0.2)',
          color: '#F4F4F4',
        },
      }}
    />
  );
}

// Main App Component
function AppRouter() {
  const location = window.location;
  // CRITICAL: Check URL fragment for session_id synchronously during render
  // This prevents race conditions with Google OAuth callback
  if (location.hash?.includes('session_id=')) {
    return <GoogleAuthCallback />;
  }
  return (
    <>
      <Suspense fallback={null}><AdminShortcuts /></Suspense>
      <Suspense fallback={null}><SystemStatusChip /></Suspense>
      <Routes>
      {/* Public Routes */}
      <Route path="/" element={<AuremHomepage />} />
      <Route path="/build-log" element={<BuildLog />} />
      <Route path="/report/:slug" element={<AuremReport />} />
      <Route path="/report/audit/:tenantId" element={<ClientReport />} />
      <Route path="/welcome" element={<OnboardingWelcome />} />
      <Route path="/onboarding/pixel" element={<OnboardingPixelStep />} />
      <Route path="/sample/:slug" element={<AuremSampleWebsite />} />
      <Route path="/edit" element={<CustomerEditPortal />} />
      <Route path="/platform" element={<PlatformLanding />} />
      <Route path="/login" element={<FaceIDAuthWrapper />} />
      <Route path="/preview/luxe-dashboard" element={<LuxeDashboardPreview />} />
      <Route path="/preview/luxe-services" element={<LuxeServicesPreview />} />
      <Route path="/auth" element={<Navigate to="/login" replace />} />
      <Route path="/register" element={<Navigate to="/auth?mode=register" replace />} />
      
      {/* Pricing */}
      <Route path="/pricing" element={<PricingPage />} />
      
      {/* Legal & Compliance */}
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/status" element={<PublicStatus />} />
      <Route path="/terms" element={<TermsOfService />} />
      <Route path="/refund" element={<RefundPolicy />} />
      <Route path="/acceptable-use" element={<AcceptableUsePolicy />} />
      <Route path="/contact" element={<ContactPage />} />
      <Route path="/support" element={<SupportPage />} />
      <Route path="/legal" element={<LegalIndex />} />
      <Route path="/legal/:slug" element={<LegalDocument />} />
      
      {/* Platform Auth */}
      <Route path="/platform/login" element={<PlatformLogin />} />
      <Route path="/platform/signup" element={<PlatformSignup />} />
      <Route path="/account/security" element={<AccountSecurity />} />
      <Route path="/signup" element={<Navigate to="/platform/signup" replace />} />
      
      {/* Auth Recovery */}
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/forgot-pin" element={<ForgotPin />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      
      {/* Dashboard */}
      <Route path="/dashboard" element={<AuremDashboard />} />
      <Route path="/dashboard/*" element={<AuremDashboard />} />
      
      {/* Admin Routes */}
      <Route path="/admin" element={<Navigate to="/admin/boardroom" replace />} />
      <Route path="/admin/login" element={<AdminLogin />} />

      {/* All authenticated admin pages share AdminShell (left sidebar + HUD).
          Existing pages render inside <Outlet /> — zero rewrites needed. */}
      <Route element={<AdminGuard><AdminShell /></AdminGuard>}>
        <Route path="/admin/2fa" element={<Admin2FAEnroll />} />
        <Route path="/admin/ssot" element={<AdminSSOT />} />
        <Route path="/admin/console" element={<AdminConsole />} />
        <Route path="/admin/skills-library" element={<AdminAntigravitySkills />} />
        <Route path="/admin/memoir" element={<AdminMemoir />} />
        <Route path="/admin/awb-cockpit" element={<AWBCockpit />} />
        <Route path="/admin/boardroom" element={<BoardroomPage />} />
        <Route path="/admin/mission-control" element={<AdminMissionControl />} />
        <Route path="/admin/system-overview" element={<SystemOverview />} />
        <Route path="/admin/system-pulse-live" element={<SystemPulseLive />} />
        <Route path="/admin/sentinel" element={<AdminDiagnostics />} />
        <Route path="/admin/auto-fixer" element={<Navigate to="/admin/sentinel" replace />} />
        <Route path="/admin/root-command" element={<AdminRootCommand />} />
        <Route path="/admin/audit-live" element={<AuditLiveDashboard />} />
        <Route path="/admin/stem-fix" element={<AdminStemFix />} />
        <Route path="/admin/pillars-map" element={<AdminPillarsMap />} />
        <Route path="/admin/blocks" element={<AdminSidebarBlocks />} />
        <Route path="/admin/vanguard" element={<AdminVanguard />} />
        <Route path="/admin/case-study" element={<AdminCaseStudy />} />
        <Route path="/admin/hunter-test" element={<AdminHunterTest />} />
        <Route path="/admin/brain-graph" element={<AdminBrainGraph />} />
        <Route path="/admin/avatar-manager" element={<AvatarManager />} />
        <Route path="/admin/customer-health" element={<CustomerHealthPanel />} />
        <Route path="/admin/brain" element={<AdminBrainPage />} />
        <Route path="/admin/council-audit" element={<CouncilAuditPage />} />
        <Route path="/admin/design-extract" element={<DesignExtractStudio />} />
        <Route path="/admin/ora-optimize" element={<OraOptimizer />} />
        <Route path="/admin/ora-cto" element={<OraCtoCockpit />} />
        <Route path="/admin/git-gate" element={<GitCommitGate />} />
        <Route path="/admin/ora-chat" element={<OraChat />} />
        <Route path="/admin/incident-ledger" element={<IncidentLedger />} />
        <Route path="/admin/ora-settings" element={<OraSettings />} />
        <Route path="/admin/founder-saves" element={<FounderSaves />} />
        <Route path="/design-extract" element={<DesignExtractPublic />} />
        <Route path="/admin/links" element={<AdminLinksHub />} />
        <Route path="/admin/site-monitor" element={<AdminSiteMonitor />} />
        <Route path="/admin/system-audit" element={<AdminSystemAudit />} />
        <Route path="/admin/wiring-audit" element={<AdminWiringAudit />} />
        <Route path="/admin/control-center" element={<AdminControlCenter />} />
        <Route path="/admin/customer/:identifier" element={<AdminCustomer360 />} />
        <Route path="/admin/impersonation-log" element={<AdminImpersonationLog />} />
        <Route path="/admin/evolver" element={<AdminEvolver />} />
        <Route path="/admin/self-repair" element={<AdminSelfRepair />} />
        <Route path="/admin/builder/:buildId" element={<AdminBuilderDetail />} />
        <Route path="/admin/openfang" element={<AdminOpenFang />} />
        <Route path="/admin/plans" element={<AdminPlanManager />} />
        <Route path="/admin/analytics" element={<AnalyticsDashboard />} />
        <Route path="/admin/business-ids" element={<AdminBusinessIds />} />
        <Route path="/admin/browser-agent" element={<AdminBrowserAgent />} />
        <Route path="/admin/leads-mining" element={<AdminLeadsMining />} />
        <Route path="/admin/daily-log" element={<AdminDailyLog />} />
      </Route>

      {/* Admin alias redirects (kept outside shell — they Navigate before shell mounts) */}
      <Route path="/admin/sentinel-client" element={<Navigate to="/admin/sentinel" replace />} />
      <Route path="/admin/repairs" element={<Navigate to="/admin/auto-fixer" replace />} />
      <Route path="/admin/command" element={<Navigate to="/admin/root-command" replace />} />
      <Route path="/admin/pillars" element={<Navigate to="/admin/pillars-map" replace />} />
      <Route path="/admin/command-blocks" element={<Navigate to="/admin/blocks" replace />} />
      <Route path="/admin/campaigns" element={<Navigate to="/admin/mission-control" replace />} />
      <Route path="/graph/share/:id" element={<BrainGraphShare />} />
      {/* Note: /my/monitor and /my/board-report are now rendered INSIDE
          CustomerPortal via its <Route path="*"> child — see CustomerPortal.jsx.
          Keeping them out of the sidebar wrapper made every /my/* sub-route
          look "blank" because CustomerPortal's auth + chrome never mounted. */}
      <Route path="/monitor-free" element={<MonitorFreeLanding />} />
      <Route path="/repair-quote" element={<RepairQuote />} />
      <Route path="/r/:quote_id" element={<ShareableReport />} />
      <Route path="/status/:bin" element={<PublicStatusPage />} />
      <Route path="/subscriptions/custom" element={<CustomSubscriptionBuilder />} />
      
      {/* Leads Dashboard (Phase A) */}
      <Route path="/leads" element={<LeadsDashboard />} />
      <Route path="/settings/panic" element={<PanicSettings />} />
      <Route path="/alerts/panic" element={<PanicAlerts />} />
      <Route path="/demo/futuristic" element={<FuturisticDemo />} />
      <Route path="/demo" element={<Demo />} />
      
      {/* Public Shared Report */}
      <Route path="/report/:shareId" element={<SharedReportPage />} />
      
      {/* Framework Map */}
      <Route path="/framework" element={<FrameworkMap />} />

      {/* SEO Audit — public lead magnet */}
      <Route path="/audit" element={<SEOAuditPage />} />

      {/* Public read-only System Overview (shareable) */}
      <Route path="/share/system-overview" element={<SystemOverviewPublic />} />
      
      {/* Sentinel Overwatch — DEPRECATED iter 266, redirects to Root Command */}
      <Route path="/overwatch" element={<Navigate to="/admin/root-command" replace />} />
      
      {/* ORA AI PWA Shell — wrapped in SentinelErrorBoundary so any
          future runtime error surfaces a self-repair card instead of
          a white screen (iter 282al-30). */}
      <Route path="/ora" element={<SentinelErrorBoundary><OraPWA /></SentinelErrorBoundary>} />
      <Route path="/ora/*" element={<SentinelErrorBoundary><OraPWA /></SentinelErrorBoundary>} />
      <Route path="/app" element={<SentinelErrorBoundary><OraPWA /></SentinelErrorBoundary>} />

      {/* Customer Portal — 8-item dedicated experience (isolated from /dashboard admin) */}
      <Route path="/my" element={<LuxeDashboardPreview />} />
      <Route path="/my/billing" element={<MyBilling />} />
      <Route path="/my/*" element={<LuxeDashboardPreview />} />
      
      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  );
}

function App() {
  return (
    <HelmetProvider>
      <ThemeProvider>
        <BrowserRouter>
          <AccessibilityWrapper>
            <div className="min-h-screen" style={{backgroundColor:'transparent'}}>
              <Suspense fallback={<LoadingSpinner />}>
                <AppRouter />
              </Suspense>
              
              {/* Toast Notifications */}
              <ThemedToaster />

              {/* Persistent draggable ORA support widget — survives route changes */}
              <ORAWidget />

              {/* iter 322 — Trial countdown banner (auto-hidden on paid plans) */}
              <TrialBanner />

              {/* iter 322 — Upgrade modal listens for service-locked + quota-exceeded events */}
              <UpgradeModal />
            </div>
          </AccessibilityWrapper>
        </BrowserRouter>
      </ThemeProvider>
    </HelmetProvider>
  );
}

export default App;
