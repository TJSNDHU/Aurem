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
// iter 332b D-17 — /login surface deleted by founder request. The old
// FaceIDAuthWrapper page is gone; /login, /auth, /register all redirect
// to /my which renders the Luxe customer dashboard (with its own embedded
// auth overlay when no token is present).
import AuremDashboard from './platform/AuremDashboard';
import PlatformLanding from './platform/PlatformLanding';
import AdminMissionControl from './platform/AdminMissionControl';
import CustomSubscriptionBuilder from './platform/CustomSubscriptionBuilder';
import AdminPlanManager from './platform/AdminPlanManager';
import AdminLogin from './platform/AdminLogin';
import LuxeDashboardPreview from './platform/luxe/LuxeDashboardV2';
import LuxeServicesPreview from './platform/preview/LuxeServicesPreview';
import Admin2FAEnroll from './platform/Admin2FAEnroll';
import BoardroomPage from './platform/BoardroomPage';
import AdminShell from './platform/AdminShell';
import AdminDeveloperSignups from './platform/AdminDeveloperSignups';
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
import FreeSeoAudit from './platform/FreeSeoAudit';
import AdminRootCommand from './platform/AdminRootCommand';
import AuditLiveDashboard from './platform/admin/AuditLiveDashboard';
import AdminStemFix from './platform/AdminStemFix';
import AdminPillarsMap from './platform/AdminPillarsMap';
import AdminSidebarBlocks from './platform/AdminSidebarBlocks';
import AdminVanguard from './platform/AdminVanguard';
import SystemOverview from './platform/SystemOverview';
import SystemPulseLive from './platform/SystemPulseLive';
// CustomerSiteMonitor + CustomerBoardReport: dead code removed iter 323i along
// with CustomerPortal.jsx. /my/* routes now render LuxeDashboardPreview.
import AvatarManager from './platform/admin/AvatarManager';
import CustomerHealthPanel from './platform/admin/CustomerHealthPanel';
import AdminBrainPage from './platform/admin/AdminBrainPage';
import CouncilAuditPage from './platform/admin/CouncilAuditPage';
import DesignExtractStudio from './platform/admin/DesignExtractStudio';
import OraOptimizer from './platform/admin/OraOptimizer';
import OraCtoCockpit from './platform/admin/OraCtoCockpit';
import OraWatchdogCockpit from './platform/admin/OraWatchdogCockpit';
import VoiceProfileEditor from './platform/admin/VoiceProfileEditor';
import SkillsMarketplace from './platform/admin/SkillsMarketplace';
import MorningBriefMobile from './platform/admin/MorningBriefMobile';
import GitCommitGate from './platform/admin/GitCommitGate';
import OraChat from './platform/admin/OraChat';
import OraSettings from './platform/admin/OraSettings';
import OraAdminUnified from './platform/admin/OraAdminUnified';
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
import AdminSovereigntyScore from './platform/AdminSovereigntyScore';
import BrainGraphShare from './pages/BrainGraphShare';
// CustomerPortal removed (iter 323i) — /my routes now use LuxeDashboardPreview.
// Previous 870-line CustomerPortal.jsx was imported but never mounted.

// Lazy load components














import { AdminGuard } from './platform/RouteGuards';
























// AUTO-EAGER (iter 301): named-export pages converted to direct imports
import { LegalIndex, LegalDocument } from './platform/LegalPages';

// iter 331f — Developer Portal (10 pages)
import DevLanding   from './platform/developers/DevLanding';
import DevSignup    from './platform/developers/DevSignup';
import DevLogin     from './platform/developers/DevLogin';
import DevConnect   from './platform/developers/DevConnect';
import DevDashboard from './platform/developers/DevDashboard';
import DevAnalytics from './platform/developers/DevAnalytics';
import DevTokens    from './platform/developers/DevTokens';
import DevTerms     from './platform/developers/DevTerms';
import DevSettings  from './platform/developers/DevSettings';
import DevExamples  from './platform/developers/DevExamples';
import DevStatus    from './platform/developers/DevStatus';
import DevApiDocs   from './platform/developers/DevApiDocs';
import NewProjectFlow   from './platform/developers/NewProjectFlow';     // iter D-32
import ProjectWorkspace from './platform/developers/ProjectWorkspace';   // iter D-32

// iter 332b — Contact Sales + Enterprise Admin (4 pages) + SAML ACS landing
import ContactSales from './platform/ContactSales';
import EnterpriseAdminOverview from './platform/enterprise/EnterpriseAdminOverview';
import EnterpriseBranding from './platform/enterprise/EnterpriseBranding';
import EnterpriseDomain from './platform/enterprise/EnterpriseDomain';
import EnterpriseApiKeys from './platform/enterprise/EnterpriseApiKeys';
import EnterpriseCompliance from './platform/enterprise/EnterpriseCompliance';
import EnterpriseSSO from './platform/enterprise/EnterpriseSSO';
import SamlAcsLanding from './platform/SamlAcsLanding';
import EnterpriseSLA from './platform/EnterpriseSLA';
import TrustCenter from './platform/TrustCenter';
import { PlatformLogin, PlatformSignup } from './platform/PlatformAuth';
import AccountSecurity from './platform/AccountSecurity';
import ORAWidget from './components/ORAWidget';




// const SentinelOverwatch = lazy(() => import('./platform/SentinelOverwatch'));  // DEPRECATED iter 266 — superseded by AdminRootCommand
































// Loading Spinner
const LoadingSpinner = () => (
  <div className="min-h-screen bg-[#050505] flex items-center justify-center">
    <div className="text-center">
      <div className="relative size-16 mx-auto">
        <div className="size-16 border-2 border-[#D4AF37]/20 rounded-full"></div>
        <div className="absolute top-0 left-0 size-16 border-2 border-transparent border-t-[#D4AF37] rounded-full animate-spin"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <div className="size-3 bg-[#D4AF37] rounded-full animate-pulse"></div>
        </div>
      </div>
      <p className="mt-4 text-sm text-[#666]">Initializing AUREM…</p>
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
      <Route path="/login" element={<Navigate to="/my" replace />} />
      <Route path="/preview/luxe-dashboard" element={<LuxeDashboardPreview />} />
      <Route path="/preview/luxe-services" element={<LuxeServicesPreview />} />
      <Route path="/auth" element={<Navigate to="/my" replace />} />
      <Route path="/register" element={<Navigate to="/my" replace />} />
      
      {/* Pricing */}
      <Route path="/pricing" element={<PricingPage />} />

      {/* Public revenue funnel — free audit → paid auto-fix */}
      <Route path="/free-seo-audit" element={<FreeSeoAudit />} />
      
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

      {/* iter 331f — Developer Portal (10 pages) */}
      <Route path="/developers"           element={<DevLanding />} />
      <Route path="/developers/signup"    element={<DevSignup />} />
      <Route path="/developers/login"     element={<DevLogin />} />
      <Route path="/developers/signin"    element={<DevLogin />} />
      <Route path="/developers/connect"   element={<DevConnect />} />
      <Route path="/developers/dashboard" element={<DevDashboard />} />
      <Route path="/developers/analytics" element={<DevAnalytics />} />
      <Route path="/developers/tokens"    element={<DevTokens />} />
      <Route path="/developers/terms"     element={<DevTerms />} />
      <Route path="/developers/settings"  element={<DevSettings />} />
      <Route path="/developers/examples"  element={<DevExamples />} />
      <Route path="/developers/status"    element={<DevStatus />} />
      <Route path="/developers/docs"      element={<DevApiDocs />} />

      {/* iter D-32 — Watchdog-approved onboarding: build-first, deploy-last */}
      <Route path="/my/projects/new"        element={<NewProjectFlow />} />
      <Route path="/my/projects/:project_id" element={<ProjectWorkspace />} />
      <Route path="/my/projects"            element={<NewProjectFlow />} />

      {/* iter 332b — Contact Sales + Enterprise Admin */}
      <Route path="/enterprise"                   element={<ContactSales />} />
      <Route path="/enterprise/admin"             element={<EnterpriseAdminOverview />} />
      <Route path="/enterprise/admin/branding"    element={<EnterpriseBranding />} />
      <Route path="/enterprise/admin/domain"      element={<EnterpriseDomain />} />
      <Route path="/enterprise/admin/keys"        element={<EnterpriseApiKeys />} />
      <Route path="/enterprise/admin/compliance"  element={<EnterpriseCompliance />} />
      <Route path="/enterprise/admin/sso"          element={<EnterpriseSSO />} />
      <Route path="/saml/landing"                 element={<SamlAcsLanding />} />
      <Route path="/enterprise/sla"                element={<EnterpriseSLA />} />
      <Route path="/enterprise/security"          element={<TrustCenter />} />
      
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
        {/* iter 322ex — ORA unified admin surface. Single page hosts Chat /
            Cockpit / Console / Optimizer / Settings as tabs. Backend
            auto-routes tools via ora_agent.run_turn. Old URLs redirect
            here with the right tab pre-selected so existing bookmarks +
            sidebar links keep working. */}
        <Route path="/admin/ora" element={<OraAdminUnified />} />
        <Route path="/admin/ora-optimize" element={<Navigate to="/admin/ora?tab=optimizer" replace />} />
        <Route path="/admin/ora-cto" element={<Navigate to="/admin/ora?tab=cockpit" replace />} />
        {/* iter 326ii — Phase 3 watchdog cockpit + supporting admin surfaces */}
        <Route path="/admin/ora-watchdog" element={<OraWatchdogCockpit />} />
        <Route path="/admin/ora-voice" element={<VoiceProfileEditor />} />
        <Route path="/admin/ora-skills" element={<SkillsMarketplace />} />
        <Route path="/admin/morning-brief" element={<MorningBriefMobile />} />
        <Route path="/admin/git-gate" element={<GitCommitGate />} />
        <Route path="/admin/ora-chat" element={<Navigate to="/admin/ora?tab=chat" replace />} />
        <Route path="/admin/incident-ledger" element={<IncidentLedger />} />
        <Route path="/admin/ora-settings" element={<Navigate to="/admin/ora?tab=settings" replace />} />
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
        <Route path="/admin/sovereignty-score" element={<AdminSovereigntyScore />} />
        <Route path="/admin/developer-signups" element={<AdminDeveloperSignups />} />
      </Route>

      {/* Admin alias redirects (kept outside shell — they Navigate before shell mounts) */}
      <Route path="/admin/sentinel-client" element={<Navigate to="/admin/sentinel" replace />} />
      <Route path="/admin/repairs" element={<Navigate to="/admin/auto-fixer" replace />} />
      <Route path="/admin/command" element={<Navigate to="/admin/root-command" replace />} />
      <Route path="/admin/pillars" element={<Navigate to="/admin/pillars-map" replace />} />
      <Route path="/admin/command-blocks" element={<Navigate to="/admin/blocks" replace />} />
      <Route path="/admin/campaigns" element={<Navigate to="/admin/mission-control" replace />} />
      <Route path="/graph/share/:id" element={<BrainGraphShare />} />
      {/* /my/* routes mount LuxeDashboardPreview (iter 323i cleanup —
          CustomerPortal removed as dead code). */}
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
