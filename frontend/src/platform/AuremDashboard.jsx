/**
 * AUREM Intelligence Dashboard
 * Complete AI Platform Interface
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useLocation, Navigate } from 'react-router-dom';
import { useTheme } from '../theme/ThemeContext';
import '../theme/aurem-green.css';
import { 
  MessageSquare, Zap, BarChart3, Users, Settings, CreditCard, 
  Mail, MessageCircle, Globe, Send, Mic, MicOff,
  Sparkles, Activity, Brain, Rocket, Shield, Code, LogOut,
  ChevronRight, Plus, Play, Pause, RefreshCw, Check, X,
  TrendingUp, Clock, Target, Phone, PhoneCall, Building2, Key,
  Gift, Inbox, Lock, Database, ShoppingBag, Ghost, Eye, Crown, FileText, Layers, Handshake,
  Search, AlertTriangle, DollarSign, MoreVertical, Image, Video, MapPin, Network, Film,
  GripVertical, CheckCircle2, ChevronDown, Link2, ShieldCheck, LayoutGrid
} from 'lucide-react';

// Voice component
import AuremVoice from '../components/AuremVoice';
// iter 279 — live Pillars health indicator on sidebar
import CorePulseDot from './CorePulseDot';
// System status bar
import SystemStatusBar from '../components/SystemStatusBar';
// Circuit breaker dashboard
import CircuitBreakerDashboard from '../components/CircuitBreakerDashboard';
// ORA Voice Wake-Word (Floating)
import VoiceWakeWord from '../components/VoiceWakeWord';
// ORA Forensic Uploader (Floating)
import ForensicUploader from '../components/ForensicUploader';
// GitHub Lead Miner
import GitHubLeadMiner from '../components/GitHubLeadMiner';
// API Keys Manager
import APIKeysManager from './APIKeysManager';
// Mission Control Dashboard
import MissionControl from './MissionControl';
import SystemOverview from './SystemOverview';
// Customer Scanner
import CustomerScanner from './CustomerScanner';
// Iter 288.3 — Unified Customers tab
import AdminCustomersOnePane from './AdminCustomersOnePane';
// Website Intelligence
import WebsiteIntelligence from './WebsiteIntelligence';
// Voice Sales Agent
import VoiceSalesAgent from './VoiceSalesAgent';
// Invisible Coach
import InvisibleCoach from './InvisibleCoach';
// Sales Pipeline Dashboard
import SalesPipelineDashboard from './SalesPipelineDashboard';
// Gmail Integration
import GmailIntegration from './GmailIntegration';
// WhatsApp Integration
import WhatsAppIntegration from './WhatsAppIntegration';
// CRM Connect
import CRMConnect from './CRMConnect';
// API Gateway
import APIGateway from './APIGateway';
// Settings
import SettingsPage from './SettingsPage';
// Usage & Billing
import UsageBilling from './UsageBilling';
// Sidebar Add-ons: ORA Command Bar + Sovereign Node Status
import { OraCommandBar, SovereignNodeStatus } from './SidebarAddons';
// Revenue Automation (Phase E)
import RevenueAutomation from './RevenueAutomation';
// Enterprise Features (Phase F)
import EnterpriseFeatures from './EnterpriseFeatures';
// Heavy admin tabs — lazy to keep main.js small (PSI flagged 580 KB unused)
const AcquisitionEngine = React.lazy(() => import('./AcquisitionEngine'));
const ORARepairEngine = React.lazy(() => import('./ORARepairEngine'));
const ShopifyAppManager = React.lazy(() => import('./ShopifyAppManager'));
// Client Manager
import ClientManager from './ClientManager';
import AdminCommandHub from './AdminCommandHub';
import AdminLinksHub from './AdminLinksHub';
import AdminAutoFixer from './AdminAutoFixer';
import AdminDevConsole from './AdminDevConsole';
import AdminSentinelClient from './AdminSentinelClient';
// Customer Detail
import CustomerDetail from './CustomerDetail';
// Analytics Hub
import AnalyticsHub from './AnalyticsHub';
// Agent Swarm
import AgentSwarm from './AgentSwarm';
// Business Management
import BusinessManagement from '../components/BusinessManagement';
// Partner Referral Portal
import PartnerReferralPortal from './PartnerReferralPortal';
// Omnichannel Comm Hub
import OmnichannelHub from './OmnichannelHub';
// Proximity Blast (Geofenced Lead Discovery)
import { ProximityBlast } from './ProximityBlast';
// Secret Vault
import SecretVault from './SecretVault';
// Voice Analytics Dashboard
import VoiceAnalytics from './VoiceAnalytics';
import AutomationEngine from './AutomationEngine';
import ServiceGuard from '../components/ServiceGuard';
import SentinelErrorBoundary from './SentinelErrorBoundary';
// System Pulse HUD
import SystemPulseHUD from './SystemPulseHUD';
import '../platform/system-pulse.css';
// Nexus Integration Hub
import NexusPage from './NexusPage';
// Intelligence Hub (Autonomous Executive)
import IntelligenceHub from './IntelligenceHub';
// Nexus Data Bridge (Shopify Sync + Customer Vault + Enrichment + Attribution)
import NexusDataBridge from './NexusDataBridge';
// Training Dashboard (AI Training Center)
import TrainingDashboard from './TrainingDashboard';
// Universal Connector (Phase F)
import UniversalConnector from './UniversalConnector';
// Phase G: Ghost Mode + GEO
import GhostModePanel from './GhostModePanel';
import GEODashboard from './GEODashboard';
// Quick Start Wizard (Onboarding)
import QuickStartWizard from '../components/QuickStartWizard';
import WelcomeCard from './WelcomeCard';
// Subscription Architecture
import SuperAdminDashboard from './SuperAdminDashboard';
import SecurityDashboard from './SecurityDashboard';
import ApiKeysSettings from './ApiKeysSettings';
// Client Dashboard (non-super-admin tenant view)
// ClientDashboard import removed in iter 282g — non-admin users now
// redirect to /my (CustomerPortal) instead of rendering ClientDashboard.
// SOC 2 Compliance Dashboard
import SOC2ComplianceDashboard from './SOC2ComplianceDashboard';
// Sentinel Self-Healing Dashboard
import SentinelDashboard from './SentinelDashboard';  // DEPRECATED iter 266 — kept for import safety, replaced at mount
import AdminRootCommand from './AdminRootCommand';
// Site Health Leaderboard
import SiteHealthLeaderboard from './SiteHealthLeaderboard';
// Tenant Optimization (Gates 1 & 4)
import TenantOptimization from './TenantOptimization';
// Pipeline Monitor (10-stage autonomous flow)
import PipelineDashboard from './PipelineDashboard';
// Demo Mode (investor presentations)
import DemoMode from './DemoMode';
// Smart Approval Queue
import ApprovalQueue from './ApprovalQueue';
// Morning Brief
import MorningBrief from './MorningBrief';
// Auto Modularization Engine
import ModularizationEngine from './ModularizationEngine';
// Memory Dashboard (Three-Tier Memory + ASK_USER + Plans)
import MemoryDashboard from './MemoryDashboard';
// OpenClaw Command Center (5 enterprise features)
import OpenClawDashboard from './OpenClawDashboard';
// AgenticPay Negotiation Engine
import NegotiationDashboard from './NegotiationDashboard';
import LeadEnrichmentDashboard from './LeadEnrichmentDashboard';
import DeepScoutDashboard from './DeepScoutDashboard';
import SentinelAnomalyDashboard from './SentinelAnomalyDashboard';
import ASIEvolveDashboard from './ASIEvolveDashboard';
import RevenueForecastDashboard from './RevenueForecastDashboard';
// Global Pulse — Economic Intelligence Hub
import GlobalPulseDashboard from './GlobalPulseDashboard';
// Economic Ticker Bar
import EconomicTicker from './EconomicTicker';
// Knowledge Documents (Multi-Agent RAG)
import KnowledgeDocuments from './KnowledgeDocuments';
// Campaign Dashboard (Outbound Acquisition)
import CampaignDashboard from './CampaignDashboard';
import AgentCommandCenter from './ORACommandConsole'; // iter 285 — legacy merged into ORACommandConsole
import ORACommandConsole from './ORACommandConsole';
import PageShell from './PageShell';
// Agent Observatory (Production Monitoring)
import AgentObservatory from './AgentObservatory';
// Dark Scout Intelligence (Layer 3 OSINT)
import DarkScoutDashboard from './DarkScoutDashboard';
import AutonomyLog from './AutonomyLog';
import VideoMarketing from './VideoMarketing';
// Dashboard Feeds — 5 live panels (Email History, Call Logs, Hot Leads, Fallback Monitor)
import EmailHistoryFeed from './feeds/EmailHistoryFeed';
import CallLogsFeed from './feeds/CallLogsFeed';
import HotLeadsFeed from './feeds/HotLeadsFeed';
import FallbackMonitorFeed from './feeds/FallbackMonitorFeed';
import LeadPipelineKanban from './feeds/LeadPipelineKanban';
import { getPlatformToken, getPlatformUser, clearCustomerAuth } from '../utils/secureTokenStore';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

// ═══════════════════════════════════════════════════════════════════════════════
// SIDEBAR COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

const SidebarBizId = ({ token }) => {
  const [bid, setBid] = React.useState('');
  React.useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/api/business-id/mine`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.business_id) setBid(d.business_id); })
      .catch(() => {});
  }, [token]);
  if (!bid) return null;
  return (
    <div className="px-3 pt-2 border-t border-white/[0.06] relative z-10" data-testid="sidebar-business-id">
      <div className="text-[8px] font-bold tracking-[2px] text-white/60 mb-1">BUSINESS ID</div>
      <div className="text-[10px] font-mono font-bold text-[#FF6B00] tracking-wider">{bid}</div>
    </div>
  );
};

// ───────────────────────────────────────────────────────────────
// WIRED_ITEMS — sidebar IDs that route to a real, working page.
// Any id not in this set is a "Coming Soon" placeholder and is
// HIDDEN in clean mode, visible with 🚧 badge when Beta Mode is ON.
// ───────────────────────────────────────────────────────────────
const WIRED_ITEMS = new Set([
  'acquisition-engine', 'agent-observatory', 'agent-swarm', 'ai-conversation',
  'analytics-hub', 'api-gateway', 'api-keys', 'asi-evolve', 'automation-engine',
  'autonomy-log', 'business-management', 'call-logs', 'call-logs-voice',
  'campaign-dashboard', 'circuit-breakers', 'client-manager', 'command-hub', 'crm-connect',
  'customer-detail', 'customer-scanner', 'dark-scout', 'deep-scout',
  'email-history', 'enterprise', 'fallback-monitor', 'geo-dashboard',
  'ghost-mode', 'github-leads', 'global-pulse', 'gmail-channel', 'hot-leads',
  'intelligence-hub', 'invisible-coach', 'knowledge-docs', 'lead-enrichment',
  'memory-system', 'mission-control', 'modularization', 'morning-brief',
  'negotiation', 'nexus', 'nexus-data-bridge', 'omnichannel-hub', 'openclaw',
  'ora-repair', 'partner-referral', 'pipeline-kanban', 'pipeline-monitor',
  'proximity-blast', 'revenue-automation', 'revenue-forecast', 'sales-pipeline',
  'secret-vault', 'security-dashboard', 'sentinel', 'sentinel-anomaly',
  'settings', 'shopify-app', 'site-health', 'smart-approvals',
  'soc2-compliance', 'super-admin', 'system-overview', 'system-pulse',
  'tenant-optimization', 'training-center', 'universal-connector',
  'usage-billing', 'video-marketing', 'voice-analytics', 'voice-sales-agent',
  'website-intelligence', 'whatsapp-flows', 'agent-command-center',
  // iter 272 — admin dashboards
  'admin-links',
  // iter 258 — Pillar 3 Auto-Fixer dashboard
  'auto-fixer',
  // iter 279 — AUREM Core Pulse quick links
  'pillars-map-link', 'command-blocks-link', 'vanguard-link',
  // Admin section core items (always visible)
  'overview', 'framework-map',
]);

// ═════════════════════════════════════════════════════════════════════
// ROLE-BASED SCOPE (who sees what)
// ═════════════════════════════════════════════════════════════════════
// Items in this set are ADMIN-ONLY — hidden from paying subscribers (clients).
// Clients see only their own B2B automation surface (scout, campaigns, CRM, content,
// websites-builder, voice, shopify, their settings + their vault).
//
// Admin-only domains:
//   • Platform ops (Morning Brief aggregates, System Pulse, Sentinel, Circuit Breakers,
//     ASI-Evolve, Self-Audit, Self-Repair, Rollback, Modularization, Nexus, Overwatch,
//     Fallback Monitor, Pipeline Monitor, Agent Observatory)
//   • Cross-tenant views (All Customers list, Active Client Sites, Site Health Monitor,
//     Website Intelligence, Nightly Sync, Campaign Analytics roll-up)
//   • AUREM's own revenue (MRR dashboard, subscriptions, Stripe plans, referrals,
//     partner network, enterprise, revenue engine, AgenticPay)
//   • Platform security posture (PentAGI, red team, OWASP, fraud detection, compliance,
//     SOC 2, panic settings/alerts, security audit log, Shannon security)
//   • B2B acquisition tooling (Forensic Miner, GitHub Leads for finding AUREM clients)
//   • Super-admin / platform mgmt (Super Admin, Admin Plans, Business IDs,
//     System Overview, Framework Map)
//   • Platform intelligence (Global Pulse, World Monitor, Competitor, Market Insights,
//     GEO, Intelligence Hub, News Digest, Anomaly Detection)
const ADMIN_ONLY_IDS = new Set([
  // Morning Brief — aggregates across all tenants
  'smart-approvals', 'revenue-snapshot', 'system-pulse', 'brief-history', 'brief-settings',
  // Scout & Hunt — admin-side acquisition
  'forensic-miner', 'github-leads',
  // Websites — cross-tenant + self-healing
  'active-client-sites', 'website-intelligence', 'site-health', 'nightly-sync-status',
  // Revenue — AUREM MRR, not client revenue
  'mrr-dashboard', 'subscriptions', 'payment-history', 'stripe-plans', 'revenue-forecast',
  'revenue-automation', 'negotiation', 'referrals', 'partner-referral', 'enterprise',
  // CRM — cross-tenant "All Customers" = AUREM subscriber list
  'client-manager', 'crm-connect', 'command-hub',
  // Intelligence — platform telemetry
  'business-reports', 'global-pulse', 'world-monitor', 'competitor-analysis',
  'google-scan-results', 'market-insights', 'geo-dashboard', 'agent-observatory',
  'intelligence-hub', 'news-digest', 'sentinel-anomaly', 'pipeline-monitor',
  // Automation & System — 100% platform infra
  'mission-control', 'autonomy-log', 'autonomy-log-view', 'agent-swarm', 'ooda-pipeline',
  'self-audit', 'ora-repair', 'sentinel', 'sentinel-client', 'circuit-breakers', 'system-pulse-full',
  'fallback-monitor', 'overwatch', 'asi-evolve', 'rollback-backups', 'modularization',
  'nexus', 'universal-connector', 'api-gateway', 'nexus-data-bridge',
  // Security — platform posture (vault 11.6 stays client-visible)
  'shannon-security', 'pentagi-scans', 'red-team', 'security-audit-log', 'owasp-checks',
  'fraud-detection', 'compliance', 'soc2-compliance', 'panic-settings', 'panic-alerts',
  // Settings — super-admin surface
  'super-admin', 'admin-plans', 'business-id', 'system-overview', 'framework-map',
]);

const decodeRoleFromToken = (tok) => {
  try {
    const p = JSON.parse(atob(tok.split('.')[1]));
    return {
      isAdmin: !!(p.is_admin || p.is_super_admin || p.role === 'admin' || p.role === 'super_admin'),
      isSuper: !!(p.is_super_admin || p.role === 'super_admin'),
      email: p.email,
    };
  } catch { return { isAdmin: false, isSuper: false, email: null }; }
};

const Sidebar = ({ activeItem, onItemClick, user, onLogout, token, onLaunchDemo, onMobileClose, isMobile }) => {
  const { theme, setManualTheme, isAuto, setAutoMode } = useTheme();
  const [planUsage, setPlanUsage] = useState(null);
  const [viralStatus, setViralStatus] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [sidebarOrder, setSidebarOrder] = useState(null);
  const [dragItem, setDragItem] = useState(null);
  const [dragOverItem, setDragOverItem] = useState(null);
  // Beta mode — show all items incl. "Coming Soon". Default OFF (clean client view).
  const [betaMode, setBetaMode] = useState(() => {
    try { return localStorage.getItem('aurem_beta_mode') === 'true'; } catch { return false; }
  });

  const toggleBetaMode = () => {
    const next = !betaMode;
    setBetaMode(next);
    try { localStorage.setItem('aurem_beta_mode', String(next)); } catch (err) { void err; }
  };

  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/plan/my-usage`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setPlanUsage(d); })
      .catch(() => {});
    fetch(`${API}/api/viral-gate/status`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setViralStatus(d); })
      .catch(() => {});
    // Load saved sidebar order
    try {
      const saved = localStorage.getItem('aurem_sidebar_order');
      if (saved) setSidebarOrder(JSON.parse(saved));
    } catch {}
    // Also try DB
    fetch(`${API}/api/settings/sidebar-order`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.order) { setSidebarOrder(d.order); localStorage.setItem('aurem_sidebar_order', JSON.stringify(d.order)); } })
      .catch(() => {});
  }, [token]);

  // Sentinel heartbeat — per-sidebar-item health dots. Background poll every 60s.
  // Non-blocking, fails silent if endpoint isn't reachable.
  const [heartbeat, setHeartbeat] = useState({});
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const pull = () => {
      fetch(`${API}/api/sentinel/heartbeat`, { headers: { 'Authorization': `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.status && !cancelled) setHeartbeat(d.status); })
        .catch(() => {});
    };
    pull();
    const t = setInterval(pull, 60000);
    return () => { cancelled = true; clearInterval(t); };
  }, [token, API]);
  const [moreToolsOpen, setMoreToolsOpen] = useState(false);
  // Default: first 3 sections open (Morning Brief, Scout & Hunt, Campaign HQ), rest collapsed
  const [collapsedSections, setCollapsedSections] = useState(() => {
    try {
      const saved = localStorage.getItem('aurem_sidebar_collapsed');
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    // Open: 0, 1, 2, 3 (Brief, Scout, Campaign, Websites). Rest collapsed.
    return {};
  });
  const toggleSection = (title) => {
    setCollapsedSections((prev) => {
      const next = { ...prev, [title]: !prev[title] };
      try { localStorage.setItem('aurem_sidebar_collapsed', JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  // 14-section sidebar — every item gets a data-testid and a render target.
  // Items without a dedicated view fall through to a placeholder in renderContent.
  const navSections = [
    {
      title: '☀️ Morning Brief', items: [
        { id: 'morning-brief',          label: '1.1 Today\'s Brief',          icon: FileText },
        { id: 'smart-approvals',        label: '1.4 Pending Approvals',       icon: Check },
        { id: 'system-pulse',           label: '1.6 System Health Score',     icon: Activity },
      ],
    },
    {
      title: '🔍 Scout & Hunt', items: [
        // Dark Scout + Deep Scout + Lead Enrichment merged into ORA Command Console
        // (see ⬡ ORA Command Console → ScoutDrawer + Lead Pipeline → Enrich button)
        { id: 'github-leads',           label: '2.7 GitHub Leads',            icon: Code },
      ],
    },
    {
      title: '📣 Campaign HQ', items: [
        { id: 'agent-command-center',   label: '⬡ ORA Command Console',    icon: Rocket },
        { id: 'campaign-dashboard',     label: '3.1 Active Campaigns',        icon: Rocket },
        { id: 'hot-leads',              label: '3.4 Hot Leads (Live)',        icon: Eye },
        { id: 'proximity-blast',        label: '3.6 Proximity Blast',         icon: MapPin },
        { id: 'acquisition-engine',     label: '3.7 Acquisition Engine',      icon: Rocket },
        { id: 'pipeline-kanban',        label: '3.11 Pipeline Kanban',        icon: Layers },
      ],
    },
    {
      title: '🌐 Websites', items: [
        { id: 'website-intelligence',   label: '4.5 Website Intelligence',    icon: Brain },
        { id: 'site-health',            label: '4.6 Site Health Monitor',     icon: Activity },
      ],
    },
    {
      title: '💰 Revenue', items: [
        { id: 'revenue-forecast',       label: '5.5 Revenue Forecast',        icon: TrendingUp },
        { id: 'revenue-automation',     label: '5.6 Revenue Engine',          icon: Zap },
        { id: 'negotiation',            label: '5.7 AgenticPay',              icon: Handshake },
        { id: 'partner-referral',       label: '5.9 Partner Network',         icon: Users },
        { id: 'enterprise',             label: '5.10 Enterprise Plans',       icon: Shield },
      ],
    },
    {
      title: '👥 CRM', items: [
        { id: 'command-hub',            label: '6.0 ⭐ Command Hub',          icon: Crown },
        { id: 'admin-links',            label: '6.0.1 🔗 Admin Links Hub',   icon: Link2 },
        { id: 'auto-fixer',              label: '6.0.2 🛠️ Auto-Fixer (Pillar 3)', icon: ShieldCheck },
        { id: 'customers-one-pane',     label: '6.1 👥 Customers (Live)',     icon: Users },
        { id: 'email-history',          label: '6.3 Email History',           icon: Mail },
        { id: 'call-logs',              label: '6.5 Call Logs',               icon: Phone },
        { id: 'crm-connect',            label: '6.7 Client Manager',          icon: Globe },
        { id: 'sales-pipeline',         label: '6.8 Sales Pipeline',          icon: TrendingUp },
        { id: 'omnichannel-hub',        label: '6.10 Comm Hub',               icon: Inbox },
        { id: 'whatsapp-flows',         label: '6.12 WhatsApp Flows',         icon: MessageCircle },
        { id: 'gmail-channel',          label: '6.13 Gmail Channel',          icon: Mail },
      ],
    },
    {
      title: '🧠 Intelligence', items: [
        { id: 'global-pulse',           label: '7.2 Global Pulse',            icon: Globe },
        { id: 'geo-dashboard',          label: '7.7 GEO Dashboard',           icon: Globe },
        { id: 'agent-observatory',      label: '7.8 Agent Observatory',       icon: Eye },
        { id: 'intelligence-hub',       label: '7.9 Intelligence Hub',        icon: Zap },
        { id: 'sentinel-anomaly',       label: '7.11 Anomaly Detection',      icon: AlertTriangle },
        { id: 'pipeline-monitor',       label: '7.12 Pipeline Monitor',       icon: Activity },
      ],
    },
    {
      title: '⚡ Automation & System', items: [
        { id: 'ai-conversation',        label: '8.1 ORA Chat',                icon: MessageSquare },
        { id: 'mission-control',        label: '8.2 Mission Control',         icon: Crown },
        { id: 'autonomy-log',           label: '8.3 Autonomy Ops',            icon: Zap },
        { id: 'agent-swarm',            label: '8.5 Agent Swarm',             icon: Users },
        { id: 'ora-repair',             label: '8.8 Self-Repair Engine',      icon: Sparkles },
        { id: 'sentinel',               label: '8.9 Sentinel Health',         icon: Activity },
        { id: 'circuit-breakers',       label: '8.10 Circuit Breakers',       icon: Shield },
        { id: 'sentinel-client',        label: '8.11b Sentinel Client',       icon: AlertTriangle },
        { id: 'fallback-monitor',       label: '8.12 Fallback Monitor',       icon: Shield },
        { id: 'asi-evolve',             label: '8.14 ASI-Evolve',             icon: Brain },
        { id: 'modularization',         label: '8.16 Modularization',         icon: Layers },
        { id: 'nexus',                  label: '8.17 Nexus',                  icon: Zap },
        { id: 'universal-connector',    label: '8.18 Universal Hub',          icon: Globe },
        { id: 'api-gateway',            label: '8.19 API Gateway',            icon: Code },
        { id: 'nexus-data-bridge',      label: '8.20 Data Bridge',            icon: Database },
      ],
    },
    {
      title: '🎨 Content & Media', items: [
        { id: 'video-marketing',        label: '9.2 Video Generation',        icon: Film },
        { id: 'invisible-coach',        label: '9.7 Invisible Coach',         icon: Shield },
      ],
    },
    {
      title: '🔧 Skills & Tools', items: [
        { id: 'knowledge-docs',         label: '10.7 Knowledge Docs',         icon: FileText },
        { id: 'training-center',        label: '10.8 AI Training',            icon: Brain },
        { id: 'openclaw',               label: '10.9 OpenClaw Center',        icon: Crown },
        { id: 'ghost-mode',             label: '10.12 Ghost Mode',            icon: Ghost },
        { id: 'memory-system',          label: '10.13 Memory & Plans',        icon: Brain },
        { id: 'tenant-optimization',    label: '10.14 Optimization',          icon: Zap },
      ],
    },
    {
      title: '🛡️ Security', items: [
        { id: 'secret-vault',           label: '11.6 Secret Vault',           icon: Lock },
        { id: 'soc2-compliance',        label: '11.9 SOC 2',                  icon: Lock },
      ],
    },
    {
      title: '🔊 Voice & Comms', items: [
        { id: 'call-logs-voice',        label: '12.2 Call Logs',              icon: Phone },
        { id: 'voice-analytics',        label: '12.3 Voice Analytics',        icon: BarChart3 },
        { id: 'voice-sales-agent',      label: '12.5 Voice Sales Agent',      icon: PhoneCall },
      ],
    },
    {
      title: '🛒 Shopify', items: [
        { id: 'shopify-app',            label: '13.2 Shopify App (Pulse)',    icon: ShoppingBag },
      ],
    },
    {
      title: '⚙️ Settings', items: [
        { id: 'api-keys',               label: '14.1 API Keys',               icon: Key },
        { id: 'business-management',    label: '14.5 Business Settings',      icon: Building2 },
        { id: 'usage-billing',          label: '14.6 Usage & Billing',        icon: CreditCard },
        { id: 'super-admin',            label: '14.7 Super Admin',            icon: Crown },
        { id: 'system-overview',        label: '14.10 System Overview',       icon: Layers },
        { id: 'settings',               label: '14.12 General',               icon: Settings },
      ],
    },
    // iter 279 — AUREM CORE PULSE section (live Pillars health indicator)
    {
      title: '🫀 AUREM Core Pulse', items: [
        { id: 'pillars-map-link',       label: 'Pillars Map (Live Health)',   icon: Activity, external: '/admin/pillars-map' },
        { id: 'command-blocks-link',    label: 'Command Blocks',              icon: LayoutGrid, external: '/admin/command-blocks' },
        { id: 'vanguard-link',          label: 'Vanguard SKU',                icon: Shield,     external: '/admin/vanguard' },
      ],
    },
  ];

  const moreToolsItems = [];

  // Role-gated: hide ADMIN-ONLY items from non-admin (paying client) users.
  const { isAdmin } = useMemo(() => decodeRoleFromToken(token || ''), [token]);

  // Apply saved order AND filter by Beta Mode (hide "Coming Soon" in clean mode)
  // AND filter by role (admin-only items hidden from clients).
  const getOrderedItems = (sectionTitle, items) => {
    // Role filter first — admin-only items removed for non-admin users.
    const roleFiltered = isAdmin ? items : items.filter(i => !ADMIN_ONLY_IDS.has(i.id));
    // Beta OFF → only show WIRED items; Beta ON → show everything
    const visible = betaMode ? roleFiltered : roleFiltered.filter(i => WIRED_ITEMS.has(i.id));
    if (!sidebarOrder || !sidebarOrder[sectionTitle]) return visible;
    const order = sidebarOrder[sectionTitle];
    const ordered = [];
    for (const id of order) {
      const item = visible.find(i => i.id === id);
      if (item) ordered.push(item);
    }
    for (const item of visible) {
      if (!order.includes(item.id)) ordered.push(item);
    }
    return ordered;
  };

  const handleDragStart = (sectionTitle, idx) => { setDragItem({ section: sectionTitle, idx }); };
  const handleDragOver = (e, sectionTitle, idx) => { e.preventDefault(); setDragOverItem({ section: sectionTitle, idx }); };

  // Beta-mode counts — aggregate live vs hidden across all sections
  const { liveCount, hiddenCount } = (() => {
    let live = 0, hidden = 0;
    for (const sec of navSections) {
      for (const it of sec.items) {
        if (WIRED_ITEMS.has(it.id)) live++; else hidden++;
      }
    }
    return { liveCount: live, hiddenCount: hidden };
  })();
  const handleDrop = (sectionTitle) => {
    if (!dragItem || !dragOverItem || dragItem.section !== sectionTitle) { setDragItem(null); setDragOverItem(null); return; }
    const section = navSections.find(s => s.title === sectionTitle);
    if (!section) return;
    const items = getOrderedItems(sectionTitle, section.items);
    const reordered = [...items];
    const [moved] = reordered.splice(dragItem.idx, 1);
    reordered.splice(dragOverItem.idx, 0, moved);
    const newOrder = { ...sidebarOrder, [sectionTitle]: reordered.map(i => i.id) };
    setSidebarOrder(newOrder);
    localStorage.setItem('aurem_sidebar_order', JSON.stringify(newOrder));
    fetch(`${API}/api/settings/sidebar-order`, {
      method: 'POST', headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ order: newOrder }),
    }).catch(() => {});
    setDragItem(null);
    setDragOverItem(null);
  };

  return (
    <aside className="w-[220px] h-screen flex flex-col py-5 aurem-sidebar relative overflow-hidden" data-testid="sidebar">
      {/* Mobile close button — only renders via prop flag, sits inline above logo */}
      {isMobile && onMobileClose && (
        <button
          onClick={onMobileClose}
          data-testid="sidebar-mobile-close"
          className="absolute top-3 right-3 z-20 size-8 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)' }}
          aria-label="Close menu"
        >
          <X className="size-4 text-white/70" />
        </button>
      )}
      {/* Ambient glow */}
      <div className="absolute top-0 right-0 w-20 h-full pointer-events-none" style={{ background: 'linear-gradient(90deg, transparent, rgba(212,163,115,0.04))' }} />

      {/* Logo */}
      <div className="text-center mb-6 px-4 relative z-10" style={{ animation: 'auremFadeSlideDown 0.5s ease both' }}>
        <div className="size-11 rounded-xl mx-auto mb-2 flex items-center justify-center relative" style={{
          background: 'linear-gradient(135deg, #FF6B00, #CC5500)',
          boxShadow: '0 0 22px rgba(212,163,115,0.4)',
          animation: 'auremFloat 4s ease-in-out infinite',
        }}>
          <span className="text-[15px] font-black text-[#1A3026]">A</span>
          <div className="absolute inset-0 rounded-xl" style={{ boxShadow: '0 0 18px rgba(212,163,115,0.2)', animation: 'auremGlowPulse 3s ease-in-out infinite' }} />
        </div>
        <div className="text-[14px] font-bold tracking-[3px] text-white">AUREM <span className="text-[#FF6B00]" style={{ textShadow: '0 0 10px rgba(212,163,115,0.3)' }}>ORA</span></div>
        <div className="text-[8px] text-white/65 tracking-[2px] mt-0.5">COMMAND CENTER</div>
        {/* Demo & Edit buttons under logo */}
        <div className="flex items-center gap-1.5 mt-2 justify-center">
          {onLaunchDemo && (
            <button onClick={onLaunchDemo} data-testid="sidebar-demo-btn"
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[9px] font-bold tracking-wider transition-all hover:scale-[1.03]"
              style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)', color: '#0A0A00' }}>
              <Play className="size-2.5" /> DEMO
            </button>
          )}
          <button onClick={() => setEditMode(!editMode)} data-testid="sidebar-edit-btn"
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[9px] font-bold tracking-wider transition-all hover:scale-[1.03]"
            style={{ background: editMode ? 'rgba(74,222,128,0.15)' : 'rgba(255,255,255,0.06)', color: editMode ? '#4ade80' : 'rgba(255,255,255,0.5)', border: editMode ? '1px solid rgba(74,222,128,0.3)' : '1px solid rgba(255,255,255,0.08)' }}>
            {editMode ? <CheckCircle2 className="size-2.5" /> : <GripVertical className="size-2.5" />}
            {editMode ? 'DONE' : 'EDIT'}
          </button>
        </div>
      </div>

      {/* ORA Command Bar — top of sidebar, under logo */}
      <OraCommandBar />

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-1 px-2.5 aurem-scroll relative z-10" role="navigation" aria-label="Main navigation" style={{ minHeight: '220px' }}>
        {navSections.map((section, idx) => {
          // Pre-compute visible items so we can hide sections that end up empty after role/beta filtering
          const visibleItems = getOrderedItems(section.title, section.items);
          if (visibleItems.length === 0) return null;
          // Admins/super-admins get CRM section (contains Command Hub) FORCE-expanded — overrides stored preference
          // because Command Hub is the primary admin control center (user reported "features not working"
          // due to CRM being collapsed). Non-admin users: sections 4+ default collapsed as before.
          let isPrivileged = !!(user?.is_admin || user?.is_super_admin);
          if (!isPrivileged) {
            try {
              const stored = getPlatformUser();
              isPrivileged = !!(stored?.is_admin || stored?.is_super_admin);
            } catch { /* ignore */ }
          }
          const isAdminCrm = isPrivileged && section.title.includes('CRM');
          const defaultOpen = idx < 4 || isAdminCrm;
          const storedCollapse = collapsedSections[section.title];
          // Admin CRM: always open unless user has just toggled it closed this session (stored === true).
          // For the specific case of stale persisted collapse on CRM, prefer open.
          let isOpen;
          if (isAdminCrm && storedCollapse === undefined) {
            isOpen = true;
          } else {
            isOpen = storedCollapse === undefined ? defaultOpen : !storedCollapse;
          }
          return (
            <div key={idx} className="mb-2">
              <button
                onClick={() => toggleSection(section.title)}
                data-testid={`section-toggle-${idx}`}
                className="w-full flex items-center justify-between px-3 py-1 mb-0.5 rounded text-[9px] font-bold tracking-[2px] uppercase text-white/70 hover:text-white hover:bg-white/5 transition-all"
              >
                <span className="truncate flex items-center gap-1.5">
                  {section.title}
                  {/* iter 279 — live Red/Green dot for AUREM Core Pulse section */}
                  {section.title.includes('Core Pulse') ? (
                    <CorePulseDot />
                  ) : null}
                </span>
                <span className="flex items-center gap-1">
                  <span className="text-[8px] text-white/45">{visibleItems.length}</span>
                  <ChevronRight className={`size-3 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                </span>
              </button>
              {isOpen && (
                <ul className="space-y-0.5"
                  onDragOver={editMode ? (e) => e.preventDefault() : undefined}
                  onDrop={editMode ? () => handleDrop(section.title) : undefined}>
                  {visibleItems.map((item, itemIdx) => {
                    const Icon = item.icon;
                    const isActive = activeItem === item.id;
                    const isDraggedOver = editMode && dragOverItem?.section === section.title && dragOverItem?.idx === itemIdx;
                    const isWired = WIRED_ITEMS.has(item.id);
                    return (
                      <li key={item.id}
                        draggable={editMode}
                        onDragStart={editMode ? () => handleDragStart(section.title, itemIdx) : undefined}
                        onDragOver={editMode ? (e) => handleDragOver(e, section.title, itemIdx) : undefined}
                        style={isDraggedOver ? { borderTop: '2px solid #D4AF37' } : {}}
                      >
                        <button
                          onClick={() => !editMode && onItemClick(item.id)}
                          data-testid={`nav-${item.id}`}
                          className={`aurem-sidebar-nav-item w-full flex items-center gap-2.5 px-3 py-1.5 rounded-xl text-[11px] font-medium relative ${
                            isActive ? 'active' : (isWired ? 'text-white/60 hover:text-white' : 'text-white/30 hover:text-white/50')
                          } ${editMode ? 'cursor-grab active:cursor-grabbing' : ''}`}
                        >
                          {editMode && <GripVertical className="size-3 flex-shrink-0 text-white/60" />}
                          <Icon className={`w-[14px] h-[14px] flex-shrink-0 ${isActive ? 'drop-shadow-[0_0_4px_rgba(27,94,58,0.4)]' : ''} ${!isWired ? 'opacity-50' : ''}`} />
                          {/* Sentinel heartbeat dot — green healthy, amber degraded, red error. */}
                          {heartbeat[item.id] && (
                            <span
                              data-testid={`heartbeat-${item.id}`}
                              title={`Sentinel: ${heartbeat[item.id]}`}
                              className="size-1.5 rounded-full flex-shrink-0"
                              style={{
                                background: heartbeat[item.id] === 'error' ? '#EF4444'
                                  : heartbeat[item.id] === 'degraded' ? '#F59E0B' : '#4ADE80',
                                boxShadow: heartbeat[item.id] === 'error'
                                  ? '0 0 6px #EF4444' : 'none',
                                animation: heartbeat[item.id] === 'error'
                                  ? 'sentinelPulse 1.2s ease-in-out infinite' : 'none',
                              }}
                            />
                          )}
                          <span className="truncate flex-1 text-left">{item.label}</span>
                          {!isWired && !editMode && (
                            <span className="text-[8px] flex-shrink-0" title="Coming Soon — placeholder page">🚧</span>
                          )}
                          {item.premium && !editMode && (
                            <span className="text-[7px] px-1.5 py-0.5 rounded-full bg-white/10 text-white/60 font-bold tracking-wider">PRO</span>
                          )}
                          {isActive && !editMode && <ChevronRight className="size-3 ml-auto" />}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </nav>

      {/* MORE TOOLS — hidden when empty (14-section nav covers everything) */}
      {moreToolsItems.length > 0 && (
      <div className="px-1 mb-2 relative z-10">
        <button
          onClick={() => setMoreToolsOpen(!moreToolsOpen)}
          data-testid="more-tools-toggle"
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-[9px] font-bold tracking-[1.5px] uppercase transition-all hover:bg-white/5"
          style={{ color: 'rgba(255,255,255,0.65)' }}
        >
          <ChevronDown
            className="size-3 transition-transform duration-200"
            style={{ transform: moreToolsOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
          />
          MORE TOOLS
          <span className="ml-auto text-[8px] px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.6)' }}>
            {moreToolsItems.length}
          </span>
        </button>
        {moreToolsOpen && (
          <ul className="space-y-0.5 mt-1 max-h-[280px] overflow-y-auto aurem-scroll">
            {moreToolsItems.map((item, i) => {
              const Icon = item.icon;
              const isActive = activeItem === item.id;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => onItemClick(item.id)}
                    data-testid={`nav-${item.id}`}
                    className={`aurem-sidebar-nav-item w-full flex items-center gap-2.5 px-3 py-1.5 rounded-xl text-[10px] font-medium ${
                      isActive ? 'active' : 'text-white/65 hover:text-white/70'
                    }`}
                    style={{ animation: `auremSlideInLeft 0.2s ease ${i * 0.02}s both` }}
                  >
                    <Icon className="size-3 flex-shrink-0" />
                    <span className="truncate flex-1 text-left">{item.label}</span>
                    {isActive && <ChevronRight className="size-3 ml-auto" />}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      )}

      {/* ORA Desktop Link */}
      <div className="px-3 pb-2 relative z-10">
        <a
          href="/ora"
          target="_blank"
          rel="noopener noreferrer"
          data-testid="sidebar-ora-desktop"
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[11px] font-medium transition-all hover:scale-[1.01]"
          style={{
            background: 'linear-gradient(135deg, rgba(255,107,0,0.08), rgba(255,107,0,0.04))',
            border: '1px solid rgba(255,107,0,0.15)',
            color: '#FF6B00',
            textDecoration: 'none',
          }}
        >
          <MessageSquare className="w-[14px] h-[14px] flex-shrink-0" />
          <span className="truncate flex-1 text-left">ORA Assistant</span>
          <span className="text-[7px] px-1.5 py-0.5 rounded-full bg-[#FF6B00]/10 text-[#FF6B00] font-bold tracking-wider">LIVE</span>
        </a>
      </div>

      {/* Beta Mode toggle — show/hide "Coming Soon" items */}
      <div className="px-3 pb-2 relative z-10">
        <button
          onClick={toggleBetaMode}
          data-testid="sidebar-beta-mode-toggle"
          title={betaMode
            ? `Beta Mode ON — all ${liveCount + hiddenCount} items visible (${hiddenCount} 🚧 coming soon)`
            : `Beta Mode OFF — showing ${liveCount} working items. ${hiddenCount} placeholders hidden.`}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[10px] font-medium transition-all"
          style={{
            background: betaMode
              ? 'linear-gradient(135deg, rgba(255,107,0,0.15), rgba(255,107,0,0.05))'
              : 'rgba(255,255,255,0.04)',
            border: betaMode ? '1px solid rgba(255,107,0,0.35)' : '1px solid rgba(255,255,255,0.08)',
            color: betaMode ? '#FF6B00' : 'rgba(255,255,255,0.6)',
          }}
        >
          <span className="text-[12px] flex-shrink-0">{betaMode ? '👁️‍🗨️' : '👁️'}</span>
          <span className="truncate flex-1 text-left">Beta Mode: {betaMode ? 'ON' : 'OFF'}</span>
          <span
            className="text-[8px] px-1.5 py-0.5 rounded-full font-bold tracking-wider flex-shrink-0"
            style={{
              background: betaMode ? 'rgba(255,107,0,0.2)' : 'rgba(255,255,255,0.08)',
              color: betaMode ? '#FFB76B' : 'rgba(255,255,255,0.55)',
            }}
          >
            {betaMode ? `${liveCount + hiddenCount} all` : `${liveCount} live`}
          </span>
        </button>
      </div>

      {/* Framework Map Link */}
      <div className="px-3 pb-2 relative z-10">
        <a
          href="/framework"
          data-testid="sidebar-framework-map"
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[11px] font-medium transition-all hover:scale-[1.01]"
          style={{
            background: 'linear-gradient(135deg, rgba(201,168,76,0.08), rgba(201,168,76,0.04))',
            border: '1px solid rgba(201,168,76,0.15)',
            color: '#C9A84C',
            textDecoration: 'none',
          }}
        >
          <Network className="w-[14px] h-[14px] flex-shrink-0" />
          <span className="truncate flex-1 text-left">Empire HUD</span>
          <span className="text-[7px] px-1.5 py-0.5 rounded-full bg-[#C9A84C]/10 text-[#C9A84C] font-bold tracking-wider">MAP</span>
        </a>
      </div>

      {/* Usage Widget */}
      {planUsage && (
        <div className="px-3 pt-3 pb-1 border-t border-white/[0.06] relative z-10" data-testid="sidebar-usage-widget">
          <h4 className="text-[8px] font-bold tracking-[2px] text-white/60 uppercase mb-2">PLAN USAGE</h4>
          <div className="space-y-2">
            {/* Actions */}
            <div>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[9px] text-white/50 font-medium">Actions</span>
                <span className="text-[9px] font-mono text-white/70" data-testid="usage-actions-count">
                  {planUsage.actions_used} / {planUsage.actions_limit === 'unlimited' ? '\u221E' : planUsage.actions_limit}
                </span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  data-testid="usage-actions-bar"
                  style={{
                    width: `${planUsage.actions_limit === 'unlimited' ? 5 : Math.min(planUsage.usage_pct, 100)}%`,
                    background: planUsage.usage_pct >= 80 ? '#ef4444' : planUsage.usage_pct >= 50 ? '#f59e0b' : '#FF6B00',
                    boxShadow: `0 0 6px ${planUsage.usage_pct >= 80 ? 'rgba(239,68,68,0.4)' : 'rgba(255,107,0,0.3)'}`,
                  }}
                />
              </div>
            </div>
            {/* Leads Enriched */}
            <div>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[9px] text-white/50 font-medium">Leads</span>
                <span className="text-[9px] font-mono text-white/70" data-testid="usage-leads-count">
                  {planUsage.leads_enriched} / {(() => {
                    const lim = planUsage.features ? null : null;
                    if (planUsage.tier === 'enterprise') return '\u221E';
                    if (planUsage.tier === 'growth') return '500';
                    return '50';
                  })()}
                </span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  data-testid="usage-leads-bar"
                  style={{
                    width: `${planUsage.tier === 'enterprise' ? 5 : Math.min((planUsage.leads_enriched / (planUsage.tier === 'growth' ? 500 : 50)) * 100, 100)}%`,
                    background: '#D4B977',
                    boxShadow: '0 0 6px rgba(212,185,119,0.3)',
                  }}
                />
              </div>
            </div>
            {/* Plan badge */}
            <div className="flex items-center justify-between">
              <span className="text-[9px] px-2 py-0.5 rounded-full font-bold tracking-wider" style={{
                background: planUsage.tier === 'enterprise' ? 'rgba(212,175,55,0.15)' : planUsage.tier === 'growth' ? 'rgba(255,107,0,0.12)' : 'rgba(255,255,255,0.08)',
                color: planUsage.tier === 'enterprise' ? '#D4B977' : planUsage.tier === 'growth' ? '#FF6B00' : '#888',
              }} data-testid="usage-tier-badge">
                {planUsage.plan_name?.toUpperCase() || planUsage.tier?.toUpperCase()}
              </span>
              <span className="text-[9px] font-mono text-white/65">{planUsage.month}</span>
            </div>
          </div>
          {/* Upgrade nudge for Starter / Trial */}
          {(planUsage.tier === 'starter' || planUsage.tier === 'trial' || planUsage.tier === 'free') && (
            <button
              onClick={() => onItemClick('usage-billing')}
              data-testid="sidebar-upgrade-nudge"
              className="w-full mt-2 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-[9px] font-bold tracking-wider transition-all hover:scale-[1.02]"
              style={{
                background: 'linear-gradient(135deg, rgba(255,107,0,0.12), rgba(212,175,55,0.08))',
                border: '1px solid rgba(255,107,0,0.2)',
                color: '#FF6B00',
              }}
              title="Unlock 10x actions, V2V voice, deep scout, and revenue forecasting with Growth"
            >
              <Rocket className="size-3" />
              UPGRADE TO GROWTH
            </button>
          )}
        </div>
      )}

      {/* Viral Gate — 7-Day Taste Trial */}
      {viralStatus && viralStatus.phase === 'trial_active' && (
        <div className="px-3 pt-2 border-t border-white/[0.06] relative z-10" data-testid="sidebar-viral-trial">
          <div className="flex items-center gap-2 mb-1.5">
            <Brain className="size-3 text-[#4ade80]" />
            <span className="text-[8px] font-bold tracking-[2px] text-[#4ade80]/60 uppercase">SOCIAL BRAIN TRIAL</span>
          </div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] text-white/50">Days Remaining</span>
            <span className="text-[9px] font-mono font-bold text-[#4ade80]" data-testid="trial-days-remaining">
              {viralStatus.trial_days_remaining} / {viralStatus.trial_days}
            </span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              data-testid="trial-progress-bar"
              style={{
                width: `${(viralStatus.trial_days_remaining / viralStatus.trial_days) * 100}%`,
                background: viralStatus.trial_days_remaining <= 2 ? '#ef4444' : 'linear-gradient(90deg, #4ade80, #22c55e)',
                boxShadow: '0 0 6px rgba(74,222,128,0.3)',
              }}
            />
          </div>
          <p className="text-[8px] text-white/60 mt-1">Full Social Brain access active</p>
        </div>
      )}
      {viralStatus && viralStatus.phase === 'review_required' && (
        <div className="px-3 pt-2 border-t border-white/[0.06] relative z-10" data-testid="sidebar-viral-review-required">
          <div className="flex items-center gap-2 mb-1.5">
            <Lock className="size-3 text-[#f59e0b]" />
            <span className="text-[8px] font-bold tracking-[2px] text-[#f59e0b]/80 uppercase">REVIEW TO UNLOCK</span>
          </div>
          <p className="text-[9px] text-white/50 mb-1.5 leading-relaxed">
            Your 7-day trial has ended. Leave a Google review to keep Social Brain active permanently.
          </p>
          <button
            onClick={() => onItemClick('settings')}
            data-testid="sidebar-review-unlock-btn"
            className="w-full flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[8px] font-bold tracking-wider transition-all hover:scale-[1.02]"
            style={{
              background: 'linear-gradient(135deg, rgba(212,185,119,0.12), rgba(255,107,0,0.08))',
              border: '1px solid rgba(212,185,119,0.2)',
              color: '#D4B977',
            }}
          >
            <Sparkles className="size-2.5" />
            LEAVE REVIEW
          </button>
        </div>
      )}
      {viralStatus && viralStatus.phase === 'not_started' && (
        <div className="px-3 pt-2 border-t border-white/[0.06] relative z-10" data-testid="sidebar-viral-not-started">
          <div className="flex items-center gap-2 mb-1.5">
            <Brain className="size-3 text-[#D4B977]" />
            <span className="text-[8px] font-bold tracking-[2px] text-white/60 uppercase">SOCIAL BRAIN</span>
          </div>
          <p className="text-[9px] text-white/65 mb-1.5">7-day free trial available</p>
          <button
            onClick={() => {
              fetch(`${process.env.REACT_APP_BACKEND_URL}/api/viral-gate/start-trial`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } })
                .then(r => r.ok ? r.json() : null)
                .then(d => { if (d) setViralStatus(d); });
            }}
            data-testid="sidebar-start-trial-btn"
            className="w-full flex items-center justify-center gap-1 px-2 py-1 rounded-lg text-[8px] font-bold tracking-wider transition-all hover:scale-[1.02]"
            style={{
              background: 'rgba(255,107,0,0.08)',
              border: '1px solid rgba(255,107,0,0.15)',
              color: '#FF6B00',
            }}
          >
            <Rocket className="size-2.5" />
            START FREE TRIAL
          </button>
        </div>
      )}
      {viralStatus && viralStatus.phase === 'unlocked' && (
        <div className="px-3 pt-2 border-t border-white/[0.06] relative z-10" data-testid="sidebar-viral-unlocked">
          <div className="flex items-center gap-2">
            <div className="size-1.5 rounded-full bg-[#4ade80]" style={{ boxShadow: '0 0 6px rgba(74,222,128,0.5)' }} />
            <span className="text-[8px] font-bold tracking-[2px] text-[#4ade80]/60">SOCIAL BRAIN UNLOCKED</span>
          </div>
        </div>
      )}

      {/* Theme Toggle */}
      <div className="px-3 pt-2 border-t border-white/[0.06] relative z-10">
        <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <button
            onClick={() => { if (!isAuto) setAutoMode(); }}
            data-testid="theme-auto-btn"
            className={`flex-1 flex items-center justify-center gap-1 px-1 py-1.5 rounded-md text-[10px] font-medium transition-all ${isAuto ? 'bg-[#FF6B00]/20 text-[#FF6B00]' : 'text-white/65 hover:text-white/70'}`}
          >
            <Clock className="size-3" />
            Auto
          </button>
          <button
            onClick={() => setManualTheme('light')}
            data-testid="theme-light-btn"
            className={`flex-1 flex items-center justify-center gap-1 px-1 py-1.5 rounded-md text-[10px] font-medium transition-all ${!isAuto && theme === 'light' ? 'bg-white/10 text-white/80' : 'text-white/65 hover:text-white/70'}`}
          >
            <svg className="size-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
            Light
          </button>
          <button
            onClick={() => setManualTheme('dark')}
            data-testid="theme-dark-btn"
            className={`flex-1 flex items-center justify-center gap-1 px-1 py-1.5 rounded-md text-[10px] font-medium transition-all ${!isAuto && theme === 'dark' ? 'bg-white/10 text-white/80' : 'text-white/65 hover:text-white/70'}`}
          >
            <svg className="size-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            Dark
          </button>
        </div>
      </div>

      {/* Business ID Footer */}
      <SidebarBizId token={token} />

      {/* Status + Logout */}
      <div className="px-3 pt-3 relative z-10">
        {/* Pulse Rings */}
        <div className="relative size-14 mx-auto mb-2">
          {[0, 0.6, 1.2].map((d, i) => (
            <div key={i} className="absolute rounded-full border animate-ping" style={{ inset: `${i*4}px`, borderColor: 'rgba(74,222,128,0.2)', animationDuration: '2.5s', animationDelay: `${d}s` }} />
          ))}
          <div className="absolute inset-[18px] rounded-full flex items-center justify-center" style={{ background: 'rgba(74,222,128,0.12)' }}>
            <div className="size-2 rounded-full bg-[#4ade80]" style={{ boxShadow: '0 0 10px rgba(74,222,128,0.6)' }} />
          </div>
        </div>
        <div className="text-center text-[8px] font-bold tracking-[2px] aurem-badge-online mb-3">ALL SYSTEMS ONLINE</div>

        <div className="text-[10px] text-white/60 mb-1.5 truncate px-1 text-center">
          {user?.email || 'admin@aurem.live'}
        </div>
        <button
          onClick={onLogout}
          data-testid="logout-btn"
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-[11px] text-white/65 hover:text-[#FF6B00] hover:bg-white/5 transition-all"
        >
          <LogOut className="size-3.5" />
          <span>Disconnect</span>
        </button>
      </div>

      {/* Sovereign Node Status — bottom of sidebar */}
      <SovereignNodeStatus />
    </aside>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// RIGHT PANEL - METRICS
// ═══════════════════════════════════════════════════════════════════════════════

const MetricsPanel = ({ metrics, onRefresh }) => {
  const displayMetrics = [
    { label: 'VOICE CALLS', value: metrics?.voice_calls_7d ?? 0, color: '#FF6B00' },
    { label: 'UPTIME', value: `${metrics?.uptime ?? 99.9}%`, color: '#4ade80' },
    { label: 'TOTAL LEADS', value: metrics?.total_leads ?? 0, color: '#D4B977' },
    { label: 'API KEYS', value: metrics?.api_keys ?? 0, color: '#FF6B00' },
  ];

  return (
    <div className="aurem-glass-card p-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[10px] font-bold tracking-[1.5px]" style={{ color: 'var(--aurem-heading)' }}>PLATFORM METRICS</h3>
        {onRefresh && (
          <button 
            onClick={onRefresh}
            data-testid="sync-metrics-btn"
            className="p-1 rounded-lg hover:bg-[rgba(61,58,57,0.25)] transition-colors"
            title="Sync metrics"
          >
            <RefreshCw className="size-3.5 text-[#FF6B00]" />
          </button>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {displayMetrics.map((metric, idx) => (
          <div key={idx} className="p-2.5 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.25)' }}>
            <div className="text-lg font-bold font-mono" style={{ color: metric.color }}>{metric.value}</div>
            <div className="text-[9px] uppercase tracking-wider font-medium" style={{ color: 'var(--aurem-body-secondary)' }}>{metric.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AgentSwarmStatus = ({ agents }) => {
  const statusColors = {
    'SCANNING': '#FF6B00',
    'BUILDING': '#D4B977',
    'ACTIVE': '#FF6B00',
    'ENGAGING': '#D4B977',
    'LIVE': '#FF6B00',
    'MANAGING': '#FF6B00',
    'STANDBY': '#888',
  };

  const displayAgents = (agents || []).map(a => ({
    ...a,
    color: statusColors[a.status] || '#888'
  }));

  if (displayAgents.length === 0) {
    return (
      <div className="aurem-glass-card p-3">
        <h3 className="text-[10px] font-bold tracking-[1.5px] mb-3" style={{ color: 'var(--aurem-heading)' }}>AGENT SWARM STATUS</h3>
        <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Loading agents…</p>
      </div>
    );
  }

  return (
    <div className="aurem-glass-card p-3">
      <h3 className="text-[10px] font-bold tracking-[1.5px] mb-3" style={{ color: 'var(--aurem-heading)' }}>AGENT SWARM STATUS</h3>
      <div className="space-y-2">
        {displayAgents.map((agent, idx) => (
          <div key={idx} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div className="size-2 rounded-full" style={{
                backgroundColor: agent.color || (agent.status === 'STANDBY' ? '#888' : '#4ade80'),
                boxShadow: agent.status !== 'STANDBY' ? `0 0 6px ${agent.color || '#4ade80'}40` : 'none'
              }} />
              <span className="font-medium" style={{ color: 'var(--aurem-heading)' }}>{agent.name}</span>
            </div>
            <span className="text-[10px] tracking-wider font-medium" style={{ color: 'var(--aurem-body-secondary)' }}>{agent.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const CapabilitiesBadges = ({ capabilities }) => {
  const defaultCapabilities = [
    ['AUTOMATION', 'CRM ORA', 'WHATSAPP'],
    ['ANALYTICS', 'MULTI-AGENT', 'VOICE ORA'],
    ['API OPS', 'GROWTH', 'LLM ROUTING'],
    ['REPORTING']
  ];

  return (
    <div className="aurem-glass-card p-3">
      <h3 className="text-[10px] font-bold tracking-[1.5px] mb-3" style={{ color: 'var(--aurem-heading)' }}>CAPABILITIES</h3>
      <div className="space-y-2">
        {defaultCapabilities.map((row, idx) => (
          <div key={idx} className="flex flex-wrap gap-1">
            {row.map((cap, cidx) => (
              <span key={cidx} className="px-2 py-0.5 text-[9px] rounded-full font-medium" style={{
                background: 'rgba(61,58,57,0.15)',
                color: '#FF6B00',
                border: '1px solid rgba(255,107,0,0.1)',
              }}>
                {cap}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

const LiveActivityFeed = ({ activities }) => {
  const iconMap = {
    phone: Phone, zap: Zap, message: MessageCircle, shield: Shield, activity: Activity
  };
  
  const displayActivities = (activities || []).map(a => ({
    icon: iconMap[a.icon] || Activity,
    text: a.action || a.text || 'System activity',
    time: a.time || 'Recently',
    color: a.agent === 'Scout' ? '#FF6B00' : a.agent === 'Closer' ? '#D4B977' : a.agent === 'Envoy' ? '#4ade80' : '#888'
  }));

  if (displayActivities.length === 0) {
    return (
      <div className="aurem-glass-card p-3">
        <h3 className="text-[10px] font-bold tracking-[1.5px] mb-3" style={{ color: 'var(--aurem-heading)' }}>LIVE ACTIVITY</h3>
        <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No recent activity</p>
      </div>
    );
  }

  return (
    <div className="aurem-glass-card p-3">
      <h3 className="text-[10px] font-bold tracking-[1.5px] mb-3" style={{ color: 'var(--aurem-heading)' }}>LIVE ACTIVITY</h3>
      <div className="space-y-3">
        {displayActivities.map((activity, idx) => {
          const Icon = activity.icon || Activity;
          return (
            <div key={idx} className="flex gap-2 text-xs" style={{ animation: `auremFadeSlideIn 0.3s ease ${idx * 0.1}s both` }}>
              <div className="size-6 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: `${activity.color}12` }}>
                <Icon className="size-3.5" style={{ color: activity.color }} />
              </div>
              <div>
                <p className="leading-tight font-medium" style={{ color: 'var(--aurem-heading)' }}>{activity.text}</p>
                <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{activity.time}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// VIBE METHODOLOGY PANEL
// ═══════════════════════════════════════════════════════════════════════════════

const VibeMethodologyPanel = () => {
  const [expanded, setExpanded] = useState(false);

  const mapping = [
    { concept: 'Context Management', manual: 'Manual .md files', aurem: 'Auto-updating MEMORY.md + SOUL.md', icon: Brain },
    { concept: 'Tool Selection', manual: 'Human picks Claude/Gemini', aurem: 'AutoTune + Agent Factory', icon: Zap },
    { concept: 'QA / Review', manual: 'Human runs 5-round loop', aurem: 'Critic Agent (5-Point QA)', icon: Shield },
    { concept: 'Tone Control', manual: 'Manual prompt editing', aurem: 'STM Hedge Reducer', icon: Target },
    { concept: 'Execution Loop', manual: 'Copy-paste between tools', aurem: 'ORA Dispatcher + OpenRouter', icon: RefreshCw },
  ];

  return (
    <div className="aurem-glass-card p-3" data-testid="vibe-methodology-panel">
      <button
        onClick={() => setExpanded(!expanded)}
        data-testid="vibe-methodology-toggle"
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <div className="size-6 rounded-lg flex items-center justify-center" style={{
            background: 'linear-gradient(135deg, rgba(212,175,55,0.15), rgba(45,122,74,0.10))',
          }}>
            <Sparkles className="size-3.5 text-[#D4B977]" />
          </div>
          <h3 className="text-[10px] font-bold tracking-[1.5px]" style={{ color: 'var(--aurem-heading)' }}>
            VIBE METHODOLOGY
          </h3>
        </div>
        <ChevronRight className={`size-3 transition-transform ${expanded ? 'rotate-90' : ''}`} style={{ color: 'var(--aurem-body-secondary)' }} />
      </button>

      {expanded && (
        <div className="mt-3 space-y-2" style={{ animation: 'auremFadeSlideIn 0.2s ease both' }}>
          <p className="text-[10px] leading-relaxed mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>
            AUREM automates the Vibe Coding workflow. What others do manually, your agents run 24/7.
          </p>

          {mapping.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={idx} className="p-2 rounded-lg" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.15)' }}>
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="size-3 text-[#FF6B00]" />
                  <span className="text-[10px] font-bold" style={{ color: 'var(--aurem-heading)' }}>{item.concept}</span>
                </div>
                <div className="flex items-center gap-1 text-[9px]">
                  <span className="px-1.5 py-0.5 rounded" style={{ background: 'rgba(136,136,136,0.1)', color: 'var(--aurem-body-secondary)' }}>{item.manual}</span>
                  <ChevronRight className="size-2.5 text-[#D4B977]" />
                  <span className="px-1.5 py-0.5 rounded font-medium" style={{ background: 'rgba(61,58,57,0.15)', color: '#FF6B00' }}>{item.aurem}</span>
                </div>
              </div>
            );
          })}

          <div className="pt-2 mt-2" style={{ borderTop: '1px solid rgba(61,58,57,0.15)' }}>
            <p className="text-[9px] italic" style={{ color: 'var(--aurem-body-secondary)' }}>
              "Ideas are human. Middle work is accelerated by agents. Polish is human again."
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// G0DM0D3 PANEL (ULTRAPLINIAN + PARSELTONGUE)
// ═══════════════════════════════════════════════════════════════════════════════

const G0DM0D3Panel = ({ token }) => {
  const [expanded, setExpanded] = useState(false);
  const [testInput, setTestInput] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [mode, setMode] = useState('ultra'); // 'ultra' or 'parsel'

  const runTest = async () => {
    if (!testInput.trim() || testing) return;
    setTesting(true);
    setTestResult(null);
    try {
      const endpoint = mode === 'ultra' ? '/api/critic/ultraplinian' : '/api/critic/parseltongue';
      const body = mode === 'ultra'
        ? { content: testInput, query: '' }
        : { text: testInput, technique: 'random', intensity: 'medium' };
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (res.ok) setTestResult(await res.json());
    } catch (e) { console.error('G0DM0D3 test error:', e); }
    setTesting(false);
  };

  return (
    <div className="aurem-glass-card p-3" data-testid="g0dm0d3-panel">
      <button
        onClick={() => setExpanded(!expanded)}
        data-testid="g0dm0d3-toggle"
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <div className="size-6 rounded-lg flex items-center justify-center" style={{
            background: 'linear-gradient(135deg, rgba(220,38,38,0.12), rgba(168,85,247,0.12))',
          }}>
            <Shield className="size-3.5 text-red-500" />
          </div>
          <h3 className="text-[10px] font-bold tracking-[1.5px]" style={{ color: 'var(--aurem-heading)' }}>
            G0DM0D3
          </h3>
        </div>
        <ChevronRight className={`size-3 transition-transform ${expanded ? 'rotate-90' : ''}`} style={{ color: 'var(--aurem-body-secondary)' }} />
      </button>

      {expanded && (
        <div className="mt-3 space-y-2" style={{ animation: 'auremFadeSlideIn 0.2s ease both' }}>
          <div className="flex gap-1">
            <button
              onClick={() => { setMode('ultra'); setTestResult(null); }}
              data-testid="g0dm0d3-tab-ultra"
              className={`flex-1 text-[9px] font-bold py-1 rounded-md transition-all ${mode === 'ultra' ? 'text-white' : ''}`}
              style={mode === 'ultra' ? { background: 'linear-gradient(135deg, #FF6B00, #1B5E3A)' } : { background: 'rgba(255,107,0,0.05)', color: 'var(--aurem-body-secondary)' }}
            >
              ULTRAPLINIAN
            </button>
            <button
              onClick={() => { setMode('parsel'); setTestResult(null); }}
              data-testid="g0dm0d3-tab-parsel"
              className={`flex-1 text-[9px] font-bold py-1 rounded-md transition-all ${mode === 'parsel' ? 'text-white' : ''}`}
              style={mode === 'parsel' ? { background: 'linear-gradient(135deg, #DC2626, #9333EA)' } : { background: 'rgba(220,38,38,0.06)', color: 'var(--aurem-body-secondary)' }}
            >
              PARSELTONGUE
            </button>
          </div>

          <p className="text-[9px] leading-relaxed" style={{ color: 'var(--aurem-body-secondary)' }}>
            {mode === 'ultra'
              ? '5-axis quality scorer: Completeness, Structure, Data Integrity, Directness, Relevance. 100-point composite.'
              : 'Adversarial red-team engine: 6 perturbation techniques (leetspeak, Unicode, ZWJ, mixed case, phonetic, random) across 3 intensity levels.'}
          </p>

          <div className="flex gap-1">
            <input
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              placeholder={mode === 'ultra' ? 'Paste content to score...' : 'Enter text to perturb...'}
              aria-label="Content testing input"
              data-testid="g0dm0d3-input"
              className="flex-1 text-[10px] px-2 py-1.5 rounded-lg border-0 outline-none"
              style={{ background: 'rgba(255,107,0,0.05)', color: 'var(--aurem-heading)' }}
              onKeyDown={(e) => e.key === 'Enter' && runTest()}
            />
            <button
              onClick={runTest}
              disabled={testing || !testInput.trim()}
              data-testid="g0dm0d3-run"
              className="px-2 py-1.5 rounded-lg text-[9px] font-bold text-white transition-all disabled:opacity-40"
              style={{ background: mode === 'ultra' ? '#FF6B00' : '#DC2626' }}
            >
              {testing ? '...' : 'RUN'}
            </button>
          </div>

          {testResult && mode === 'ultra' && (
            <div className="p-2 rounded-lg space-y-1" data-testid="g0dm0d3-ultra-result" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(45,122,74,0.10)' }}>
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  testResult.grade === 'EXCELLENT' ? 'bg-emerald-500/15 text-emerald-600' :
                  testResult.grade === 'GOOD' ? 'bg-green-500/15 text-green-600' :
                  testResult.grade === 'MEDIOCRE' ? 'bg-amber-500/15 text-amber-600' :
                  testResult.grade === 'POOR' ? 'bg-orange-500/15 text-orange-600' :
                  'bg-red-500/15 text-red-600'
                }`}>
                  {testResult.total}/100 {testResult.grade}
                </span>
                <span className={`text-[9px] font-bold ${testResult.envoy_pass ? 'text-green-500' : 'text-red-500'}`}>
                  ENVOY: {testResult.envoy_pass ? 'PASS' : 'FAIL'}
                </span>
              </div>
              {testResult.axes && Object.entries(testResult.axes).map(([axis, data]) => (
                <div key={axis} className="flex items-center gap-2">
                  <span className="text-[8px] w-16 truncate" style={{ color: 'var(--aurem-body-secondary)' }}>{axis}</span>
                  <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(61,58,57,0.25)' }}>
                    <div className="h-full rounded-full transition-all" style={{ width: `${(data.score / data.max) * 100}%`, background: data.score / data.max > 0.7 ? '#FF6B00' : data.score / data.max > 0.4 ? '#D4B977' : '#DC2626' }} />
                  </div>
                  <span className="text-[8px] font-mono w-8 text-right" style={{ color: 'var(--aurem-heading)' }}>{data.score}/{data.max}</span>
                </div>
              ))}
            </div>
          )}

          {testResult && mode === 'parsel' && (
            <div className="p-2 rounded-lg space-y-1" data-testid="g0dm0d3-parsel-result" style={{ background: 'rgba(220,38,38,0.04)', border: '1px solid rgba(220,38,38,0.10)' }}>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  testResult.triggers_transformed > 0 ? 'bg-red-500/15 text-red-600' : 'bg-green-500/15 text-green-600'
                }`}>
                  {testResult.triggers_transformed > 0 ? 'SENSITIVE' : 'CLEAN'} ({testResult.triggers_transformed} triggers)
                </span>
              </div>
              {testResult.transformed !== testResult.original && (
                <div className="text-[9px] font-mono p-1.5 rounded break-all" style={{ background: 'rgba(0,0,0,0.04)', color: 'var(--aurem-heading)' }}>
                  {testResult.transformed}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════

const ChatInterface = ({ user, token }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState({});
  const [msgHeights, setMsgHeights] = useState([]);
  const [showActionHub, setShowActionHub] = useState(false);
  const [showFeatureLocked, setShowFeatureLocked] = useState(false);
  const [heartbeatActive, setHeartbeatActive] = useState(false);
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const actionHubRef = useRef(null);
  const recognitionRef = useRef(null);
  const heartbeatTimerRef = useRef(null);

  // ═══════════════════════════════════════
  // Hunt Live Progress — subscribe to SSE feed
  // ═══════════════════════════════════════
  // activeHunt is keyed by hunt_id; contains {step, status, message, timeline:[], summary:{}}
  const [activeHunt, setActiveHunt] = useState(null);
  const sseRef = useRef(null);

  useEffect(() => {
    // Generate/reuse a per-session client_id
    let clientId = sessionStorage.getItem('aurem_sse_client_id');
    if (!clientId) {
      clientId = `ora_${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem('aurem_sse_client_id', clientId);
    }

    const url = `${API_URL}/api/admin/events/${clientId}`;
    const es = new EventSource(url);
    sseRef.current = es;

    es.onmessage = (evt) => {
      let payload;
      try { payload = JSON.parse(evt.data); } catch { return; }
      if (payload?.type !== 'hunt_progress') return;

      const d = payload.data || {};
      const huntId = d.hunt_id;
      if (!huntId) return;

      // ═══ Dopamine: chime + haptic when a HIGH-confidence lead locks ═══
      if (d.step === 'verify' && d.status === 'ok' && d.data?.confidence === 'HIGH') {
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(880, ctx.currentTime);           // A5
          osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.18); // up to E6
          gain.gain.setValueAtTime(0.0001, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.3);
          osc.connect(gain); gain.connect(ctx.destination);
          osc.start(); osc.stop(ctx.currentTime + 0.32);
        } catch { /* audio blocked — silent fallback */ }
        if (navigator.vibrate) {
          try { navigator.vibrate([40, 30, 40]); } catch { /* noop */ }
        }
      }

      setActiveHunt((prev) => {
        const base = prev && prev.hunt_id === huntId
          ? prev
          : { hunt_id: huntId, timeline: [], summary: {}, startedAt: Date.now() };
        const newTimeline = [
          ...base.timeline,
          {
            step: d.step,
            status: d.status,
            message: d.message,
            data: d.data || {},
            ts: payload.timestamp,
          },
        ].slice(-60);  // keep the last 60 events only
        const nextSummary = d.step === 'hunt' && d.data?.summary
          ? d.data.summary
          : base.summary;
        const finished = d.step === 'hunt' && d.status === 'complete';
        return {
          ...base,
          timeline: newTimeline,
          summary: nextSummary,
          lastMessage: d.message,
          finished,
          total: d.data?.total || base.total,
          done: d.data?.done || base.done,
        };
      });
    };

    es.onerror = () => {
      // Auto-reconnect happens natively; just log quietly
    };

    return () => {
      try { es.close(); } catch { /* noop */ }
      sseRef.current = null;
    };
  }, []);

  // Close action hub on outside click
  useEffect(() => {
    const handler = (e) => {
      if (actionHubRef.current && !actionHubRef.current.contains(e.target)) setShowActionHub(false);
    };
    if (showActionHub) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showActionHub]);

  const handleFileUpload = (type) => {
    setShowActionHub(false);
    const accept = type === 'document'
      ? '.pdf,.doc,.docx,.txt,.csv,.md,.json,.xlsx,.xls'
      : type === 'image'
        ? 'image/*'
        : 'video/*,audio/*';
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = accept;
    inp.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // 1. Show user message + optimistic "uploading" indicator
      const sizeKB = Math.round(file.size / 1024);
      setMessages(prev => [
        ...prev,
        { role: 'user', content: `[Uploaded ${type}: ${file.name} — ${sizeKB}KB]`,
          attachment: { type, name: file.name, size: file.size } },
        { role: 'assistant', content: `Uploading "${file.name}" (${sizeKB}KB)…`, _uploading: true },
      ]);

      // 2. ACTUALLY send the file to the backend training endpoint
      const form = new FormData();
      form.append('file', file);
      form.append('language', 'English');
      form.append('purpose', 'knowledge_base');

      try {
        const resp = await fetch(`${API_URL}/api/ora/training/upload`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: form,
        });
        if (!resp.ok) {
          // Real error — show the actual reason, no BS excuses
          let detail = `upload failed (HTTP ${resp.status})`;
          try {
            const err = await resp.json();
            detail = err?.detail || detail;
          } catch { /* non-JSON body */ }
          setMessages(prev => {
            const copy = [...prev];
            copy[copy.length - 1] = {
              role: 'assistant',
              content: `Couldn't upload "${file.name}": ${detail}`,
            };
            return copy;
          });
          return;
        }
        const data = await resp.json();
        // Real success — include the file_id so user can track it
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            role: 'assistant',
            content:
              `Got it. "${data.filename}" is saved to my knowledge base `
              + `(file_id: ${data.file_id}, ${Math.round((data.file_size || file.size) / 1024)}KB). `
              + `I'll index it in the background — you can reference it in any question.`,
          };
          return copy;
        });
      } catch (err) {
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            role: 'assistant',
            content: `Upload network error: ${err.message}. `
              + `Check your connection and try again — I'll preserve the file attachment.`,
          };
          return copy;
        });
      }
    };
    inp.click();
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  };

  // Auto-scroll to bottom whenever messages change or while streaming
  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Pretext: measure message heights when messages change
  useEffect(() => {
    const measure = async () => {
      try {
        const { measureMessages } = await import('./pretext-chat');
        const containerWidth = chatContainerRef.current?.offsetWidth || 700;
        const measurements = await measureMessages(messages, containerWidth);
        setMsgHeights(measurements);
      } catch {
        // Pretext not available, fall back to normal rendering
      }
    };
    if (messages.length > 0) measure();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);
    setHeartbeatActive(false);

    // Proactive Heartbeat: if response > 1500ms, show keep-alive animation
    const startTime = Date.now();
    heartbeatTimerRef.current = setTimeout(() => {
      setHeartbeatActive(true);
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'heartbeat') return prev;
        return [...prev, { role: 'heartbeat', content: 'I\'m optimizing the results for you, one moment...' }];
      });
    }, 1500);

    try {
      const response = await fetch(`${API_URL}/api/aurem/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: currentInput,
          session_id: sessionId
        })
      });

      // Clear heartbeat timer
      clearTimeout(heartbeatTimerRef.current);
      setHeartbeatActive(false);

      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id);
        // Check for FEATURE_LOCKED / REVIEW_REQUIRED gate
        if (data.intent?.gate === 'FEATURE_LOCKED' || data.intent?.gate === 'REVIEW_REQUIRED') {
          setShowFeatureLocked(true);
        }
        // Remove heartbeat message if present, then add real response
        setMessages(prev => {
          const filtered = prev.filter(m => m.role !== 'heartbeat');
          return [...filtered, {
            role: 'assistant',
            content: data.response,
            intent: data.intent,
            autotune: data.autotune,
            ultraplinian: data.ultraplinian,
            data_freshness: data.data_freshness,
          }];
        });
      } else {
        throw new Error('Chat failed');
      }
    } catch (error) {
      clearTimeout(heartbeatTimerRef.current);
      setHeartbeatActive(false);
      console.error('Chat error:', error);
      // Remove heartbeat, replace with AI status message (no generic errors)
      setMessages(prev => {
        const filtered = prev.filter(m => m.role !== 'heartbeat');
        return [...filtered, {
          role: 'assistant',
          content: "I'm optimizing the results for you, one moment\u2026 The analysis is taking a bit longer. Please try again."
        }];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async (messageIdx, rating) => {
    if (feedbackGiven[messageIdx]) return;
    const msg = messages[messageIdx];
    if (!msg || msg.role !== 'assistant') return;

    setFeedbackGiven(prev => ({ ...prev, [messageIdx]: rating }));

    try {
      await fetch(`${API_URL}/api/highsignal/autotune/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          context: msg.intent?.intent || 'CONVERSATIONAL',
          rating: rating,
          params_used: msg.autotune?.params || { temperature: 0.7, top_p: 0.9 },
          response_text: msg.content,
        }),
      });
    } catch (err) {
      console.error('Feedback error:', err);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 min-w-0" style={{ background: 'transparent' }} data-testid="chat-interface">
      {/* Header */}
      <header className="px-6 py-4 flex items-center justify-between flex-shrink-0" role="banner" aria-label="Site header" style={{ borderBottom: '1px solid rgba(61,58,57,0.3)', background: 'rgba(16,16,16,0.8)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)', fontFamily: 'Cinzel, Georgia, serif' }}>ORA Intelligence</h1>
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Commercial ORA Platform, Multi-Agent Architecture</p>
          </div>
          {(() => { try { const p = JSON.parse(atob((getPlatformToken()||'').split('.')[1])); return p.is_admin; } catch { return false; } })() && (
            <button
              data-testid="go-mission-control"
              onClick={() => window.location.href = '/admin/mission-control'}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
              style={{ background: 'linear-gradient(135deg, #FF6B00, #D4AF37)', color: '#FFF', boxShadow: '0 2px 8px rgba(255,107,0,0.25)' }}
            >
              <Shield className="size-3" />
              Mission Control
            </button>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--aurem-body-secondary)] font-mono">ORA-{Math.random().toString(36).substr(2, 6).toUpperCase()}</span>
        </div>
      </header>

      {/* Voice Modal */}
      {showVoiceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-lg mx-4" style={{ maxHeight: '85vh' }}>
            <AuremVoice token={token} onClose={() => setShowVoiceModal(false)} />
          </div>
        </div>
      )}

      {/* Chat Content */}
      <div ref={chatContainerRef} className="flex-1 overflow-y-auto min-h-0 p-6 aurem-scroll">
        {messages.length === 0 ? (
          <div className="max-w-3xl mx-auto pt-4" data-testid="ora-chat-empty">
            {/* Agent status strip */}
            <div
              className="mb-6 flex items-center justify-between p-3 rounded-xl border"
              style={{
                background: 'linear-gradient(180deg, rgba(255,107,0,0.04), rgba(0,0,0,0.35))',
                borderColor: 'rgba(255,107,0,0.18)',
              }}
              data-testid="ora-agent-strip"
            >
              <div className="flex items-center gap-3">
                {[
                  { key: 'scout',    label: 'Scout',    dot: '#4ADE80' },
                  { key: 'oracle',   label: 'Oracle',   dot: '#FFB347' },
                  { key: 'envoy',    label: 'Envoy',    dot: '#60A5FA' },
                  { key: 'closer',   label: 'Closer',   dot: '#F472B6' },
                ].map((a) => (
                  <div key={a.key} className="flex items-center gap-1.5" data-testid={`agent-pill-${a.key}`}>
                    <span
                      className="size-1.5 rounded-full"
                      style={{
                        background: a.dot,
                        boxShadow: `0 0 6px ${a.dot}`,
                        animation: 'pulse 2s ease-in-out infinite',
                      }}
                    />
                    <span className="text-[11px] font-semibold tracking-wide" style={{ color: 'var(--aurem-heading)' }}>
                      {a.label}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="size-1.5 rounded-full" style={{ background: '#FF6B00', boxShadow: '0 0 6px #FF6B00' }} />
                <span className="text-[10px] tracking-[1.5px] font-bold" style={{ color: '#FF6B00' }}>
                  OODA ACTIVE
                </span>
              </div>
            </div>

            {/* ORA greeting bubble */}
            <div className="flex justify-start" style={{ animation: 'auremFadeSlideIn 0.4s ease both' }}>
              <div
                className="max-w-[80%] rounded-2xl rounded-tl-sm px-4 py-3 border"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  borderColor: 'rgba(255,107,0,0.18)',
                  color: 'var(--aurem-heading)',
                }}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <Sparkles className="size-3.5" style={{ color: '#FF6B00' }} />
                  <span className="text-[10px] tracking-[2px] font-bold" style={{ color: '#FF6B00' }}>ORA</span>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--aurem-body)' }}>
                  ORA online, OODA pipeline active. How can I assist?
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {[
                    'Scout Toronto auto shops',
                    'Verify Tim Hortons',
                    'Show campaign stats',
                    'Who replied',
                  ].map((suggest, i) => (
                    <button
                      key={i}
                      onClick={() => setInput(suggest)}
                      data-testid={`ora-suggestion-${i}`}
                      className="px-2.5 py-1 rounded-full text-[10px] transition-all hover:scale-[1.03]"
                      style={{
                        background: 'rgba(255,107,0,0.08)',
                        border: '1px solid rgba(255,107,0,0.22)',
                        color: 'var(--aurem-heading)',
                      }}
                    >
                      {suggest}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`} style={{ animation: `auremFadeSlideIn 0.3s ease both` }}>
                {/* Heartbeat Keep-Alive Message */}
                {msg.role === 'heartbeat' ? (
                  <div className="max-w-[80%] p-4 rounded-2xl aurem-glass-card" data-testid="heartbeat-message" style={{
                    border: '1px solid rgba(255,107,0,0.15)',
                    animation: 'pulse 2s ease-in-out infinite',
                  }}>
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1">
                        <div className="size-1.5 rounded-full bg-[#FF6B00] animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="size-1.5 rounded-full bg-[#FF6B00] animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="size-1.5 rounded-full bg-[#FF6B00] animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <p className="text-xs italic" style={{ color: '#FF6B00' }}>{msg.content}</p>
                    </div>
                  </div>
                ) : (
                <div className={`max-w-[80%] p-4 rounded-2xl ${
                  msg.role === 'user' 
                    ? 'text-white' 
                    : 'aurem-glass-card'
                }`} style={msg.role === 'user' ? {
                  background: 'linear-gradient(135deg, #FF6B00, #1B5E3A)',
                  boxShadow: '0 4px 15px rgba(255,107,0,0.12)'
                } : {}}>
                  <p className="whitespace-pre-wrap" style={{ color: msg.role === 'user' ? undefined : 'var(--aurem-heading)' }}>{msg.content}</p>
                  {msg.role === 'assistant' && (
                    <div className="mt-2 pt-2 space-y-1.5" style={{ borderTop: '1px solid rgba(45,122,74,0.10)' }}>
                      {/* Live Data Freshness Indicator */}
                      {msg.data_freshness && msg.data_freshness.sources && msg.data_freshness.sources.length > 0 && (
                        <div className="flex items-center gap-1.5 flex-wrap" data-testid={`freshness-${idx}`}>
                          <span className="size-1.5 rounded-full bg-[#4ade80] animate-pulse" />
                          <span className="text-[9px] text-[#FF6B00] font-medium">
                            Live data
                          </span>
                          <span className="text-[9px] text-[var(--aurem-body-secondary)]">&middot;</span>
                          <span className="text-[9px] text-[var(--aurem-body-secondary)]">{msg.data_freshness.context_age}</span>
                          {msg.data_freshness.web_searched && (
                            <>
                              <span className="text-[9px] text-[var(--aurem-body-secondary)]">&middot;</span>
                              <span className="text-[9px] text-blue-500 font-medium">web searched</span>
                            </>
                          )}
                          {msg.data_freshness.sources.map((src, si) => (
                            <span key={si} className="text-[8px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,107,0,0.05)', color: '#888' }}>
                              {src.replace('_', ' ')}
                            </span>
                          ))}
                        </div>
                      )}
                      {msg.ultraplinian && (
                        <div className="flex items-center gap-2 flex-wrap" data-testid={`ultra-score-${idx}`}>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            msg.ultraplinian.grade === 'EXCELLENT' ? 'bg-emerald-500/15 text-emerald-600' :
                            msg.ultraplinian.grade === 'GOOD' ? 'bg-green-500/15 text-green-600' :
                            msg.ultraplinian.grade === 'MEDIOCRE' ? 'bg-amber-500/15 text-amber-600' :
                            msg.ultraplinian.grade === 'POOR' ? 'bg-orange-500/15 text-orange-600' :
                            'bg-red-500/15 text-red-600'
                          }`}>
                            ULTRA {msg.ultraplinian.total}/100 {msg.ultraplinian.grade}
                          </span>
                          {msg.ultraplinian.axes && Object.entries(msg.ultraplinian.axes).map(([axis, data]) => (
                            <span key={axis} className="text-[8px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(255,107,0,0.05)', color: 'var(--aurem-body-secondary)' }}>
                              {axis.charAt(0).toUpperCase()}{axis.slice(1,4)}:{data.score}/{data.max}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleFeedback(idx, 1)}
                            data-testid={`feedback-up-${idx}`}
                            className={`p-1.5 rounded-lg transition-all text-xs ${
                              feedbackGiven[idx] === 1
                                ? 'bg-[#FF6B00]/15 text-[#FF6B00]'
                                : feedbackGiven[idx] === -1
                                  ? 'opacity-30 cursor-not-allowed text-[var(--aurem-body-secondary)]'
                                  : 'text-[var(--aurem-body-secondary)] hover:text-[#FF6B00] hover:bg-[#FF6B00]/8'
                            }`}
                            disabled={!!feedbackGiven[idx]}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/></svg>
                          </button>
                          <button
                            onClick={() => handleFeedback(idx, -1)}
                            data-testid={`feedback-down-${idx}`}
                            className={`p-1.5 rounded-lg transition-all text-xs ${
                              feedbackGiven[idx] === -1
                                ? 'bg-red-500/15 text-red-500'
                                : feedbackGiven[idx] === 1
                                  ? 'opacity-30 cursor-not-allowed text-[var(--aurem-body-secondary)]'
                                  : 'text-[var(--aurem-body-secondary)] hover:text-red-500 hover:bg-red-500/8'
                            }`}
                            disabled={!!feedbackGiven[idx]}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"/></svg>
                          </button>
                          {feedbackGiven[idx] && (
                            <span className="text-[10px] ml-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                              {feedbackGiven[idx] === 1 ? 'Vibe locked' : 'Noted'}
                            </span>
                          )}
                        </div>
                        {msg.intent && (
                          <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                            {msg.intent.intent} ({Math.round(msg.intent.confidence * 100)}%)
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  {msg.role === 'user' && msg.intent && (
                    <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,107,0,0.1)' }}>
                      <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        Intent: {msg.intent.intent} ({Math.round(msg.intent.confidence * 100)}%)
                      </span>
                    </div>
                  )}
                </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="aurem-glass-card p-4">
                  <div className="flex items-center gap-2">
                    <div className="size-2 bg-[#FF6B00] rounded-full animate-bounce" />
                    <div className="size-2 bg-[#FF6B00] rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="size-2 bg-[#FF6B00] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />

            {/* ═══ Hunt Live Progress Panel — driven by SSE hunt_progress events ═══ */}
            {activeHunt && (
              <div
                data-testid="hunt-live-panel"
                className="aurem-glass-card p-4 rounded-2xl space-y-3"
                style={{
                  border: '1px solid rgba(255,107,0,0.4)',
                  boxShadow: '0 4px 20px rgba(255,107,0,0.12)',
                  animation: 'auremFadeSlideIn 0.3s ease both',
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-flex size-2.5 rounded-full"
                      style={{
                        background: activeHunt.finished ? '#1B5E3A' : '#FF6B00',
                        animation: activeHunt.finished ? 'none' : 'pulse 1s ease-in-out infinite',
                      }}
                    />
                    <span className="text-sm font-semibold" style={{ color: 'var(--aurem-heading)' }}>
                      {activeHunt.finished ? 'Hunt Complete' : 'Hunt In Progress'}
                    </span>
                    <span className="text-xs opacity-60">
                      {activeHunt.hunt_id}
                    </span>
                  </div>
                  {activeHunt.total > 0 && (
                    <div className="text-xs font-mono" style={{ color: 'var(--aurem-heading)' }}>
                      {activeHunt.done || 0}/{activeHunt.total}
                    </div>
                  )}
                </div>

                {/* Progress bar */}
                {activeHunt.total > 0 && (
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(27,94,58,0.1)' }}>
                    <div
                      data-testid="hunt-progress-bar"
                      className="h-full transition-all duration-500"
                      style={{
                        width: `${Math.round(((activeHunt.done || 0) / activeHunt.total) * 100)}%`,
                        background: 'linear-gradient(90deg, #FF6B00, #1B5E3A)',
                      }}
                    />
                  </div>
                )}

                {/* Scrollable timeline */}
                <div
                  className="space-y-1 max-h-56 overflow-y-auto aurem-scroll text-xs font-mono"
                  data-testid="hunt-timeline"
                >
                  {activeHunt.timeline.slice(-20).map((e, i) => {
                    const emoji = e.status === 'ok' ? '✅'
                      : e.status === 'fail' ? '❌'
                      : e.status === 'skipped' ? '⚠️'
                      : e.status === 'started' ? '🔄'
                      : e.status === 'complete' ? '🏁'
                      : e.status === 'progress' ? '📊'
                      : '•';
                    const color = e.status === 'ok' ? '#1B5E3A'
                      : e.status === 'fail' ? '#B00020'
                      : e.status === 'skipped' ? '#B8860B'
                      : 'var(--aurem-heading)';
                    return (
                      <div key={i} className="flex items-start gap-2" style={{ color }}>
                        <span className="flex-shrink-0">{emoji}</span>
                        <span className="break-words">{e.message}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Final summary */}
                {activeHunt.finished && activeHunt.summary && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-2" style={{ borderTop: '1px solid rgba(61,58,57,0.1)' }}>
                    <div><strong>{activeHunt.summary.scouted || 0}</strong> scouted</div>
                    <div><strong>{activeHunt.summary.verified_high || 0}</strong> HIGH</div>
                    <div><strong>{activeHunt.summary.websites_built || 0}</strong> sites</div>
                    <div><strong>{(activeHunt.summary.emails_sent || 0) + (activeHunt.summary.wa_sent || 0) + (activeHunt.summary.sms_sent || 0) + (activeHunt.summary.calls_made || 0)}</strong> outreach</div>
                  </div>
                )}

                {activeHunt.finished && (
                  <button
                    onClick={() => setActiveHunt(null)}
                    data-testid="hunt-dismiss-btn"
                    className="text-xs opacity-60 hover:opacity-100 underline"
                  >
                    dismiss
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input Area — sticky to bottom of chat column */}
      <div className="p-4 flex-shrink-0 sticky bottom-0 z-10" style={{ borderTop: '1px solid rgba(61,58,57,0.25)', background: 'rgba(255,255,255,0.4)', backdropFilter: 'blur(10px)' }}>
        <div className="flex items-center gap-3 aurem-glass-card p-2 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            placeholder="Ask ORA anything about your business..."
            aria-label="Chat with ORA AI assistant"
            data-testid="chat-input"
            className="flex-1 bg-transparent px-3 py-2 outline-none text-sm"
            style={{ color: 'var(--aurem-heading)' }}
          />
          <button 
            onClick={() => {
              const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
              if (!SpeechRecognition) {
                alert('Speech recognition not supported in this browser. Please use Chrome.');
                return;
              }
              if (isListening) {
                recognitionRef.current?.stop();
                setIsListening(false);
                return;
              }
              const recognition = new SpeechRecognition();
              recognition.continuous = false;
              recognition.interimResults = true;
              recognition.lang = 'en-US';
              recognitionRef.current = recognition;
              
              recognition.onstart = () => setIsListening(true);
              recognition.onresult = (event) => {
                const transcript = Array.from(event.results)
                  .map(result => result[0].transcript)
                  .join('');
                setInput(transcript);
              };
              recognition.onerror = (e) => {
                console.error('Speech error:', e.error);
                setIsListening(false);
              };
              recognition.onend = () => setIsListening(false);
              recognition.start();
            }}
            data-testid="mic-btn"
            className={`p-2 transition-colors ${isListening ? 'text-red-500 animate-pulse' : 'text-[var(--aurem-body-secondary)] hover:text-[#FF6B00]'}`}
          >
            <Mic className="size-5" />
          </button>
          <button 
            onClick={handleSendMessage}
            disabled={isLoading || !input.trim()}
            data-testid="send-btn"
            className="p-2 rounded-xl text-white hover:opacity-90 transition-opacity disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #FF6B00, #1B5E3A)', boxShadow: '0 4px 12px rgba(255,107,0,0.12)' }}
          >
            <Send className="size-5" />
          </button>
          {/* 3 Dots Action Hub */}
          <div className="relative" ref={actionHubRef}>
            <button
              onClick={() => setShowActionHub(!showActionHub)}
              data-testid="action-hub-btn"
              className="p-2 rounded-xl transition-all hover:bg-white/10"
              style={{ color: 'var(--aurem-body-secondary)' }}
              title="Attach files"
            >
              <MoreVertical className="size-5" />
            </button>
            {showActionHub && (
              <div
                className="absolute bottom-full right-0 mb-2 w-48 rounded-xl overflow-hidden"
                style={{
                  background: 'rgba(16,16,18,0.85)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  animation: 'auremFadeSlideIn 0.15s ease both',
                }}
                data-testid="action-hub-menu"
              >
                <button
                  onClick={() => handleFileUpload('document')}
                  data-testid="action-hub-document"
                  className="w-full flex items-center gap-3 px-4 py-3 text-xs text-white/70 hover:text-[#FF6B00] hover:bg-white/5 transition-all"
                >
                  <FileText className="size-4 text-[#FF6B00]" />
                  <span className="font-medium">Document</span>
                  <span className="ml-auto text-[9px] text-white/60">PDF / Docs</span>
                </button>
                <button
                  onClick={() => handleFileUpload('image')}
                  data-testid="action-hub-image"
                  className="w-full flex items-center gap-3 px-4 py-3 text-xs text-white/70 hover:text-[#D4B977] hover:bg-white/5 transition-all"
                >
                  <Image className="size-4 text-[#D4B977]" />
                  <span className="font-medium">Image</span>
                  <span className="ml-auto text-[9px] text-white/60">Screenshots</span>
                </button>
                <button
                  onClick={() => handleFileUpload('video')}
                  data-testid="action-hub-video"
                  className="w-full flex items-center gap-3 px-4 py-3 text-xs text-white/70 hover:text-[#4ade80] hover:bg-white/5 transition-all"
                >
                  <Video className="size-4 text-[#4ade80]" />
                  <span className="font-medium">Video</span>
                  <span className="ml-auto text-[9px] text-white/60">Bug reports</span>
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center justify-center gap-4 mt-2 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
          <span>ENTER to send</span>
          <span>SHIFT+ENTER new line</span>
        </div>
      </div>

      {/* Feature Locked Modal */}
      {showFeatureLocked && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}>
          <div
            className="max-w-md mx-4 rounded-2xl p-8 text-center"
            style={{
              background: 'rgba(16,16,18,0.9)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(212,185,119,0.2)',
              boxShadow: '0 0 60px rgba(212,185,119,0.08)',
              animation: 'auremFadeSlideIn 0.2s ease both',
            }}
            data-testid="feature-locked-modal"
          >
            <div className="size-14 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{
              background: 'linear-gradient(135deg, rgba(212,185,119,0.15), rgba(255,107,0,0.10))',
              border: '1px solid rgba(212,185,119,0.2)',
            }}>
              <Lock className="size-7 text-[#D4B977]" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2" style={{ fontFamily: 'Cinzel, Georgia, serif' }}>Social Brain, Review Required</h3>
            <p className="text-xs text-white/50 leading-relaxed mb-6">
              Your 7-day Social Brain trial has ended. To keep this powerful feature active permanently, 
              please leave a 5-star Google Review. You can also upload a screenshot via the attachment menu.
            </p>
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="px-3 py-1.5 rounded-lg text-[10px] font-bold" style={{ background: 'rgba(212,185,119,0.08)', color: '#D4B977', border: '1px solid rgba(212,185,119,0.15)' }}>
                <Sparkles className="size-3 inline mr-1" /> 1 Google Review
              </div>
            </div>
            <button
              onClick={() => setShowFeatureLocked(false)}
              data-testid="feature-locked-close"
              className="w-full py-2.5 rounded-xl text-xs font-bold tracking-wider text-[#050507] transition-all hover:scale-[1.02]"
              style={{ background: 'linear-gradient(135deg, #D4B977, #A08028)', boxShadow: '0 4px 16px rgba(212,185,119,0.2)' }}
            >
              GOT IT
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// PIXEL GATE BANNER — iter 290 (P0)
// ═══════════════════════════════════════════════════════════════════════════════

const PixelGateBanner = ({ user }) => {
  const [status, setStatus] = React.useState(null);
  const tenantId = user?.tenant_id || user?.user?.tenant_id || user?.business_id || '';

  React.useEffect(() => {
    if (!tenantId) return;
    const API = process.env.REACT_APP_BACKEND_URL || '';
    fetch(`${API}/api/onboarding/tenant/${tenantId}/pixel/status`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setStatus(d); })
      .catch(() => {});
  }, [tenantId]);

  if (!tenantId || !status || status.pixel_installed) return null;

  return (
    <div data-testid="pixel-gate-banner"
      style={{ padding: '10px 20px', background: 'rgba(245,158,11,0.12)',
               borderBottom: '1px solid rgba(245,158,11,0.4)',
               display: 'flex', alignItems: 'center', gap: 12, zIndex: 50,
               position: 'relative' }}>
      <span style={{ fontSize: 18 }}>⚠️</span>
      <div style={{ flex: 1, color: '#F59E0B', fontWeight: 600, fontSize: 13 }}>
        Pixel not detected, fixes paused until you install the AUREM pixel.
      </div>
      <a href={`/onboarding/pixel?tenant_id=${encodeURIComponent(tenantId)}`}
        data-testid="pixel-gate-cta"
        style={{ padding: '7px 14px', borderRadius: 6, background: '#F59E0B',
                 color: '#0A0A0A', fontWeight: 700, fontSize: 12,
                 textDecoration: 'none' }}>
        Install now →
      </a>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

const AuremDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [activeItem, setActiveItem] = useState('mission-control');
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState(null);
  const [agents, setAgents] = useState(null);
  const [activities, setActivities] = useState(null);
  const [showDemo, setShowDemo] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);

  // Mobile drawer state — left sidebar & right chat-aside both off-canvas on <768px.
  // Opening one auto-closes the other so the center content is always readable.
  const [isMobile, setIsMobile] = useState(false);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)');
    const sync = () => {
      const m = mq.matches;
      setIsMobile(m);
      // Default: closed on mobile, open on desktop
      setLeftOpen(!m);
      setRightOpen(false);
    };
    sync();
    mq.addEventListener?.('change', sync);
    return () => mq.removeEventListener?.('change', sync);
  }, []);
  const openLeft  = () => { setLeftOpen(true);  setRightOpen(false); };
  const openRight = () => { setRightOpen(true); setLeftOpen(false); };
  const closeAll  = () => { setLeftOpen(false); setRightOpen(false); };

  const checkAuth = useCallback(async () => {
    const storedToken = getPlatformToken();
    const storedUser = getPlatformUser();
    
    if (!storedToken) {
      navigate('/login');
      return;
    }

    try {
      if (storedUser) {
        setUser(storedUser);
      }
      setToken(storedToken);
    } catch (error) {
      navigate('/login');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (token) {
      fetchMetrics();
      fetchAgentStatus();
      fetchActivities();
      // Check welcome card status
      fetch(`${API_URL}/api/business-id/welcome-status`, { headers: { 'Authorization': `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.show_welcome_card) setShowWelcome(true); })
        .catch(() => {});
    }
  }, [token]);

  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/metrics`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  };

  const fetchAgentStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/agents/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setAgents(data.agents);
      }
    } catch (error) {
      console.error('Failed to fetch agents:', error);
    }
  };

  const fetchActivities = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/activity/feed`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setActivities(data.activities);
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    }
  };

  const handleNavClick = (itemId) => {
    // iter 279 — AUREM Core Pulse links navigate out to /admin/* pages
    const externalTargets = {
      'pillars-map-link':   '/admin/pillars-map',
      'command-blocks-link': '/admin/command-blocks',
      'vanguard-link':       '/admin/vanguard',
    };
    if (externalTargets[itemId]) {
      navigate(externalTargets[itemId]);
      return;
    }
    setSelectedCustomerId(null);
    setActiveItem(itemId);
    // On mobile, auto-close the left drawer after navigation so the content is visible
    if (window.matchMedia && window.matchMedia('(max-width: 767px)').matches) {
      setLeftOpen(false);
    }
  };

  const handleViewCustomer = (tenantId) => {
    setSelectedCustomerId(tenantId);
    setActiveItem('customer-detail');
  };

  // Reset scroll position when page changes
  useEffect(() => {
    const resetAll = () => {
      try { window.scrollTo({ top: 0, left: 0, behavior: "auto" }); } catch { /* ignore */ }
      // Widened selector: also catches [data-scroll-root] and any overflow-hidden
      // parent that Chrome silently scrolled (happens when children mount with
      // minHeight:100vh larger than parent — e.g. ORA Command Console).
      const all = document.querySelectorAll('[data-scroll-root], .flex-1.overflow-auto, .flex-1.overflow-y-auto, .flex-1.overflow-hidden, main, [data-content-area]');
      all.forEach((el) => { if (el && el.scrollTop !== 0) el.scrollTop = 0; });
    };
    resetAll();
    // Run several times across frames to beat any late layout that re-scrolls.
    const r1 = requestAnimationFrame(resetAll);
    const r2 = requestAnimationFrame(() => requestAnimationFrame(resetAll));
    const t1 = setTimeout(resetAll, 50);
    const t2 = setTimeout(resetAll, 200);
    return () => {
      cancelAnimationFrame(r1); cancelAnimationFrame(r2);
      clearTimeout(t1); clearTimeout(t2);
    };
  }, [activeItem, selectedCustomerId]);

  const handleLogout = () => {
    // iter 326o — clear ONLY the customer slot. Admin session (in another
    // tab on the same browser) must survive a customer logout.
    clearCustomerAuth();
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 relative">
        <div className="aurem-bg-container"><div className="geometric-overlay"></div></div>
        <div className="text-center relative z-10" style={{ animation: 'auremFadeSlideIn 0.5s ease both' }}>
          <div className="size-14 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{
            background: 'linear-gradient(135deg, #D4B977, #B19A5E)',
            boxShadow: '0 0 28px rgba(212,185,119,0.25)',
            animation: 'auremFloat 2s ease-in-out infinite',
          }}>
            <span className="text-lg font-black text-[#0A0A00]">A</span>
          </div>
          <p className="text-sm font-bold tracking-[3px]" style={{ color: 'var(--aurem-heading)' }}>AUREM ORA</p>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>Initializing systems…</p>
        </div>
      </div>
    );
  }

  // Non-admin (paying client) users see the simplified Client Portal.
  // Admins + super-admins get the full 14-section AUREM ORA dashboard (with
  // admin-only items filtered inside Sidebar via ADMIN_ONLY_IDS).
  const tokenRole = decodeRoleFromToken(token || '');
  const isAdminUser = (
    user?.is_super_admin === true ||
    user?.user?.is_super_admin === true ||
    user?.is_admin === true ||
    user?.user?.is_admin === true ||
    tokenRole.isAdmin
  );
  // iter 282g — Customer UX unification (P0 from /app/memory/CUSTOMER_UX_AUDIT.md).
  // Non-admin users landing on /dashboard get redirected to /my where the
  // full 10-item customer portal lives. This eliminates the dual-portal
  // fork and the admin-chrome (shimmer/PixelGateBanner) bleed that was
  // visible on the legacy ClientDashboard surface.
  if (!isAdminUser) {
    return <Navigate to="/my" replace data-testid="dashboard-customer-redirect" />;
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden admin-dashboard-bg ora-cmd-bg" data-testid="aurem-dashboard" style={{backgroundImage:`url('${process.env.REACT_APP_BACKEND_URL || ''}/api/static/admin-dashboard-bg.jpg')`}}>
      {/* Golden shimmer overlay — premium futuristic sweep */}
      <div aria-hidden="true" className="admin-shimmer ora-shimmer" />

      {/* Fixed Veridian Oasis Background (retained as low-opacity overlay) */}
      <div className="aurem-bg-container" style={{opacity:0.15}}>
        <div className="geometric-overlay"></div>
      </div>

      {/* System Status Bar */}
      <div className="relative z-10">
        <SystemStatusBar token={token} />
      </div>

      {/* Demo Mode Button — REMOVED from floating position, now in sidebar */}

      {/* Demo Mode Overlay */}
      {showDemo && <DemoMode token={token} onClose={() => setShowDemo(false)} />}

      {/* Welcome Card Modal */}
      {showWelcome && <WelcomeCard token={token} onDismiss={() => setShowWelcome(false)} />}
      
      {/* ORA Voice Wake-Word — re-enabled in iter 281.3 (Phase 2.3) with "Hey ORA" + chime + waveform */}
      <VoiceWakeWord token={token} />
      
      {/* ORA Forensic Uploader - Disabled per user request */}
      {/* <ForensicUploader token={token} /> */}
      
      <main role="main" aria-label="Main content" className="flex flex-1 overflow-hidden relative z-10" data-content-area>
        {/* Mobile backdrop — closes any open drawer when tapped */}
        {isMobile && (leftOpen || rightOpen) && (
          <div
            onClick={closeAll}
            data-testid="mobile-drawer-backdrop"
            className="fixed inset-0 z-30 md:hidden"
            style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(2px)' }}
          />
        )}

        {/* Floating edge toggle buttons (mobile only). Show "closed" side's tab. */}
        {isMobile && !leftOpen && (
          <button
            onClick={openLeft}
            data-testid="mobile-open-left"
            aria-label="Open menu"
            className="fixed top-1/2 left-0 z-40 -translate-y-1/2 md:hidden"
            style={{
              width: 28, height: 64, borderTopRightRadius: 12, borderBottomRightRadius: 12,
              background: 'rgba(212,175,55,0.18)',
              border: '1px solid rgba(212,175,55,0.45)', borderLeft: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            }}
          >
            <ChevronRight className="size-4 text-[#D4AF37]" />
          </button>
        )}
        {isMobile && !rightOpen && activeItem === 'ai-conversation' && (
          <button
            onClick={openRight}
            data-testid="mobile-open-right"
            aria-label="Open ORA panel"
            className="fixed top-1/2 right-0 z-40 -translate-y-1/2 md:hidden"
            style={{
              width: 28, height: 64, borderTopLeftRadius: 12, borderBottomLeftRadius: 12,
              background: 'rgba(212,175,55,0.18)',
              border: '1px solid rgba(212,175,55,0.45)', borderRight: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            }}
          >
            <ChevronRight className="size-4 text-[#D4AF37] rotate-180" />
          </button>
        )}

        {/* Sidebar (desktop: static; mobile: off-canvas drawer) */}
        <div
          className={`transition-transform duration-300 ease-out md:static md:translate-x-0 md:z-auto ${
            isMobile
              ? `fixed inset-y-0 left-0 z-40 ${leftOpen ? 'translate-x-0' : '-translate-x-full'}`
              : ''
          }`}
        >
          <Sidebar
            activeItem={activeItem}
            onItemClick={handleNavClick}
            user={user}
            onLogout={handleLogout}
            token={token}
            onLaunchDemo={() => setShowDemo(true)}
            isMobile={isMobile}
            onMobileClose={() => setLeftOpen(false)}
          />
        </div>

        {/* Main Content Area with Economic Ticker */}
        <div className="flex-1 flex flex-col overflow-hidden admin-content-glass" data-scroll-root>
          <EconomicTicker token={token} />
        <SentinelErrorBoundary>
        {activeItem === 'system-overview' ? (
          <div className="flex-1 overflow-auto"><SystemOverview /></div>
        ) : activeItem === 'command-hub' ? (
          <ServiceGuard name="Command Hub">
            <div className="flex-1 overflow-auto"><AdminCommandHub token={token} /></div>
          </ServiceGuard>
        ) : activeItem === 'sentinel-client' ? (
          <ServiceGuard name="Sentinel · Client Errors">
            <div className="flex-1 overflow-auto"><AdminSentinelClient /></div>
          </ServiceGuard>
        ) : activeItem === 'mission-control' ? (
          <ServiceGuard name="Mission Control">
            <div className="flex-1 overflow-auto">
              <QuickStartWizard token={token} onNavigate={handleNavClick} />
              <MissionControl onNavigate={handleNavClick} token={token} />
            </div>
          </ServiceGuard>
        ) : activeItem === 'intelligence-hub' ? (
          <ServiceGuard name="Intelligence Hub"><div className="flex-1 overflow-auto"><IntelligenceHub token={token} /></div></ServiceGuard>
        ) : activeItem === 'nexus-data-bridge' ? (
          <ServiceGuard name="Nexus Data Bridge"><div className="flex-1 overflow-auto"><NexusDataBridge token={token} /></div></ServiceGuard>
        ) : activeItem === 'customer-scanner' ? (
          <ServiceGuard name="Customer Scanner"><div className="flex-1 overflow-auto"><CustomerScanner token={token} /></div></ServiceGuard>
        ) : activeItem === 'website-intelligence' ? (
          <ServiceGuard name="Website Intelligence"><div className="flex-1 overflow-auto p-6"><WebsiteIntelligence token={token} /></div></ServiceGuard>
        ) : activeItem === 'sales-pipeline' ? (
          <ServiceGuard name="Sales Pipeline"><div className="flex-1 overflow-auto"><SalesPipelineDashboard token={token} /></div></ServiceGuard>
        ) : activeItem === 'ora-repair' ? (
          <ServiceGuard name="ORA Repair Engine"><div className="flex-1 overflow-auto"><React.Suspense fallback={<div className="p-8 text-sm text-gray-500">Loading repair engine…</div>}><ORARepairEngine token={token} /></React.Suspense></div></ServiceGuard>
        ) : activeItem === 'voice-sales-agent' ? (
          <ServiceGuard name="Voice Sales Agent"><div className="flex-1 overflow-auto"><VoiceSalesAgent token={token} /></div></ServiceGuard>
        ) : activeItem === 'invisible-coach' ? (
          <ServiceGuard name="Invisible Coach"><div className="flex-1 overflow-auto"><InvisibleCoach token={token} /></div></ServiceGuard>
        ) : activeItem === 'sentinel' ? (
          <ServiceGuard name="Sentinel"><AdminRootCommand /></ServiceGuard>
        ) : activeItem === 'autonomy-log' ? (
          <AutonomyLog token={token} />
        ) : activeItem === 'video-marketing' ? (
          <VideoMarketing token={token} />
        ) : activeItem === 'pipeline-monitor' ? (
          <ServiceGuard name="Pipeline Monitor"><PipelineDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'memory-system' ? (
          <ServiceGuard name="Memory System"><MemoryDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'openclaw' ? (
          <ServiceGuard name="OpenClaw Center"><OpenClawDashboard token={token} tenantId={user?.id || user?.tenant_id || 'default'} /></ServiceGuard>
        ) : activeItem === 'negotiation' ? (
          <ServiceGuard name="AgenticPay"><NegotiationDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'knowledge-docs' ? (
          <ServiceGuard name="Knowledge Docs"><KnowledgeDocuments token={token} /></ServiceGuard>
        ) : activeItem === 'smart-approvals' ? (
          <ServiceGuard name="Smart Approvals"><ApprovalQueue token={token} /></ServiceGuard>
        ) : activeItem === 'morning-brief' ? (
          <ServiceGuard name="Morning Brief"><MorningBrief token={token} /></ServiceGuard>
        ) : activeItem === 'global-pulse' ? (
          <ServiceGuard name="Global Pulse"><div className="flex-1 overflow-auto p-6"><GlobalPulseDashboard token={token} /></div></ServiceGuard>
        ) : activeItem === 'tenant-optimization' ? (
          <ServiceGuard name="Tenant Optimization"><TenantOptimization token={token} /></ServiceGuard>
        ) : activeItem === 'site-health' ? (
          <ServiceGuard name="Site Health"><SiteHealthLeaderboard token={token} /></ServiceGuard>
        ) : activeItem === 'circuit-breakers' ? (
          <ServiceGuard name="Circuit Breakers"><div className="flex-1 overflow-auto"><CircuitBreakerDashboard token={token} /></div></ServiceGuard>
        ) : activeItem === 'modularization' ? (
          <ServiceGuard name="Modularization Engine"><ModularizationEngine token={token} /></ServiceGuard>
        ) : activeItem === 'github-leads' ? (
          <ServiceGuard name="GitHub Leads"><div className="flex-1 overflow-auto"><GitHubLeadMiner token={token} /></div></ServiceGuard>
        ) : activeItem === 'nexus' ? (
          <ServiceGuard name="Nexus"><NexusPage token={token} /></ServiceGuard>
        ) : activeItem === 'api-keys' ? (
          <ServiceGuard name="API Keys"><div className="flex-1 overflow-auto"><APIKeysManager token={token} user={user} /></div></ServiceGuard>
        ) : activeItem === 'gmail-channel' ? (
          <ServiceGuard name="Gmail Channel"><div className="flex-1 overflow-auto" style={{background:'transparent'}}><GmailIntegration businessId={user?.id || 'default'} /></div></ServiceGuard>
        ) : activeItem === 'crm-connect' ? (
          <ServiceGuard name="CRM Connect"><CRMConnect token={token} user={user} /></ServiceGuard>
        ) : activeItem === 'whatsapp-flows' ? (
          <ServiceGuard name="WhatsApp Flows"><div className="flex-1 overflow-auto" style={{background:'transparent'}}><WhatsAppIntegration businessId={user?.id || 'default'} /></div></ServiceGuard>
        ) : activeItem === 'api-gateway' ? (
          <ServiceGuard name="API Gateway"><APIGateway token={token} /></ServiceGuard>
        ) : activeItem === 'settings' ? (
          <ServiceGuard name="Settings"><SettingsPage token={token} user={user} /></ServiceGuard>
        ) : activeItem === 'usage-billing' ? (
          <ServiceGuard name="Usage & Billing"><UsageBilling token={token} user={user} /></ServiceGuard>
        ) : activeItem === 'super-admin' ? (
          <ServiceGuard name="Super Admin"><SuperAdminDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'security-dashboard' ? (
          <ServiceGuard name="Security"><SecurityDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'soc2-compliance' ? (
          <ServiceGuard name="SOC 2 Compliance"><SOC2ComplianceDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'revenue-automation' ? (
          <ServiceGuard name="Revenue Automation"><RevenueAutomation token={token} /></ServiceGuard>
        ) : activeItem === 'lead-enrichment' ? (
          // Legacy route, moved to per-lead Enrich buttons in Lead Pipeline
          <ServiceGuard name="Leads"><LeadsDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'proximity-blast' ? (
          <ServiceGuard name="Proximity Blast"><div className="flex-1 overflow-auto p-6"><ProximityBlast token={token} /></div></ServiceGuard>
        ) : activeItem === 'sentinel-anomaly' ? (
          <ServiceGuard name="Sentinel Anomaly"><SentinelAnomalyDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'agent-observatory' ? (
          <ServiceGuard name="Agent Observatory"><AgentObservatory token={token} /></ServiceGuard>
        ) : activeItem === 'asi-evolve' ? (
          <ServiceGuard name="ASI-Evolve"><ASIEvolveDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'revenue-forecast' ? (
          <ServiceGuard name="Revenue Forecast"><RevenueForecastDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'enterprise' ? (
          <ServiceGuard name="Enterprise"><EnterpriseFeatures token={token} user={user} /></ServiceGuard>
        ) : activeItem === 'acquisition-engine' ? (
          <ServiceGuard name="Acquisition Engine"><React.Suspense fallback={<div className="p-8 text-sm text-gray-500">Loading acquisition engine…</div>}><AcquisitionEngine token={token} user={user} /></React.Suspense></ServiceGuard>
        ) : activeItem === 'automation-engine' ? (
          <ServiceGuard name="Automation Engine"><AutomationEngine token={token} /></ServiceGuard>
        ) : activeItem === 'customers-one-pane' ? (
          <ServiceGuard name="Customers (Unified)"><AdminCustomersOnePane token={token} /></ServiceGuard>
        ) : activeItem === 'client-manager' ? (
          <ServiceGuard name="Client Manager"><ClientManager token={token} user={user} onViewCustomer={handleViewCustomer} /></ServiceGuard>
        ) : activeItem === 'customer-detail' && selectedCustomerId ? (
          <ServiceGuard name="Customer Detail"><CustomerDetail token={token} tenantId={selectedCustomerId} onBack={() => { setSelectedCustomerId(null); setActiveItem('customers-one-pane'); }} /></ServiceGuard>
        ) : activeItem === 'campaign-dashboard' ? (
          <ServiceGuard name="Campaign Dashboard"><CampaignDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'agent-command-center' ? (
          <ServiceGuard name="ORA Command Console"><PageShell><ORACommandConsole /></PageShell></ServiceGuard>
        ) : activeItem === 'command-console' ? (
          <ServiceGuard name="ORA Command Console"><PageShell><ORACommandConsole /></PageShell></ServiceGuard>
        ) : activeItem === 'deep-scout' ? (
          // Legacy route, redirect to unified Console
          <ServiceGuard name="ORA Command Console"><PageShell><ORACommandConsole /></PageShell></ServiceGuard>
        ) : activeItem === 'dark-scout' ? (
          // Legacy route, redirect to unified Console
          <ServiceGuard name="ORA Command Console"><PageShell><ORACommandConsole /></PageShell></ServiceGuard>
        ) : activeItem === 'legacy-agent-center' ? (
          // iter 285, legacy AgentCommandCenter merged into ORACommandConsole
          <ServiceGuard name="ORA Command Console"><PageShell><ORACommandConsole /></PageShell></ServiceGuard>
        ) : activeItem === 'system-pulse' ? (
          <ServiceGuard name="System Pulse"><SystemPulseHUD token={token} /></ServiceGuard>
        ) : activeItem === 'analytics-hub' ? (
          <ServiceGuard name="Analytics Hub"><AnalyticsHub token={token} /></ServiceGuard>
        ) : activeItem === 'voice-analytics' ? (
          <ServiceGuard name="Voice Analytics"><VoiceAnalytics token={token} /></ServiceGuard>
        ) : activeItem === 'agent-swarm' ? (
          <ServiceGuard name="Agent Swarm"><AgentSwarm token={token} /></ServiceGuard>
        ) : activeItem === 'business-management' ? (
          <ServiceGuard name="Business Management"><div className="flex-1 overflow-auto" style={{background:'transparent'}}><BusinessManagement /></div></ServiceGuard>
        ) : activeItem === 'partner-referral' ? (
          <ServiceGuard name="Partner Referral"><PartnerReferralPortal token={token} user={user} /></ServiceGuard>
        ) : activeItem === 'training-center' ? (
          <ServiceGuard name="AI Training"><TrainingDashboard token={token} /></ServiceGuard>
        ) : activeItem === 'omnichannel-hub' ? (
          <ServiceGuard name="Omnichannel Hub"><OmnichannelHub token={token} /></ServiceGuard>
        ) : activeItem === 'secret-vault' ? (
          <ServiceGuard name="Secret Vault"><SecretVault token={token} /></ServiceGuard>
        ) : activeItem === 'shopify-app' ? (
          <ServiceGuard name="Shopify App"><div className="flex-1 overflow-auto"><React.Suspense fallback={<div className="p-8 text-sm text-gray-500">Loading Shopify manager…</div>}><ShopifyAppManager token={token} /></React.Suspense></div></ServiceGuard>
        ) : activeItem === 'universal-connector' ? (
          <ServiceGuard name="Universal Hub"><div className="flex-1 overflow-auto p-6"><UniversalConnector token={token} /></div></ServiceGuard>
        ) : activeItem === 'ghost-mode' ? (
          <ServiceGuard name="Ghost Mode"><div className="flex-1 overflow-auto p-6"><GhostModePanel token={token} /></div></ServiceGuard>
        ) : activeItem === 'geo-dashboard' ? (
          <ServiceGuard name="GEO Dashboard"><div className="flex-1 overflow-auto p-6"><GEODashboard token={token} /></div></ServiceGuard>
        ) : activeItem === 'ai-conversation' ? (
          <ServiceGuard name="ORA Chat">
            <div className="flex flex-1 min-h-0 overflow-hidden relative" data-testid="ora-chat-layout">
              <ChatInterface user={user} token={token} />
              <aside
                data-testid="ora-chat-right-aside"
                className={`w-64 border-l flex-shrink-0 overflow-y-auto p-3 space-y-3 aurem-scroll transition-transform duration-300 ease-out md:static md:translate-x-0 md:z-auto ${
                  isMobile
                    ? `fixed inset-y-0 right-0 z-40 ${rightOpen ? 'translate-x-0' : 'translate-x-full'}`
                    : ''
                }`}
                style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(255,255,255,0.3)', backdropFilter: 'blur(8px)' }}
              >
                {isMobile && rightOpen && (
                  <button
                    onClick={() => setRightOpen(false)}
                    data-testid="ora-right-mobile-close"
                    className="sticky top-0 ml-auto mb-2 size-8 rounded-full flex items-center justify-center"
                    style={{ background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.2)' }}
                    aria-label="Close panel"
                  >
                    <X className="size-4 text-white/80" />
                  </button>
                )}
                <VibeMethodologyPanel />
                <G0DM0D3Panel token={token} />
                <MetricsPanel metrics={metrics} onRefresh={() => { fetchMetrics(); fetchAgentStatus(); fetchActivities(); }} />
                <AgentSwarmStatus agents={agents} />
                <CapabilitiesBadges />
                <LiveActivityFeed activities={activities} />
              </aside>
            </div>
          </ServiceGuard>
        ) : activeItem === 'email-history' ? (
          <ServiceGuard name="Email History"><EmailHistoryFeed token={token} /></ServiceGuard>
        ) : activeItem === 'call-logs' || activeItem === 'call-logs-voice' ? (
          <ServiceGuard name="Call Logs"><CallLogsFeed token={token} /></ServiceGuard>
        ) : activeItem === 'hot-leads' ? (
          <ServiceGuard name="Hot Leads"><HotLeadsFeed token={token} /></ServiceGuard>
        ) : activeItem === 'fallback-monitor' ? (
          <ServiceGuard name="Fallback Monitor"><FallbackMonitorFeed token={token} /></ServiceGuard>
        ) : activeItem === 'pipeline-kanban' ? (
          <ServiceGuard name="Pipeline Kanban"><LeadPipelineKanban token={token} /></ServiceGuard>
        ) : activeItem === 'admin-links' ? (
          <div className="flex-1 overflow-auto"><AdminLinksHub /></div>
        ) : activeItem === 'auto-fixer' ? (
          <div className="flex-1 overflow-auto"><AdminAutoFixer /></div>
        ) : (
          <div className="flex-1 flex items-center justify-center" style={{ background: 'transparent' }}>
            <div className="text-center aurem-glass-card p-12">
              <Shield className="size-12 text-[#FF6B00] mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--aurem-heading)' }}>
                {activeItem.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
              </h2>
              <p style={{ color: 'var(--aurem-body-secondary)' }}>Coming soon…</p>
            </div>
          </div>
        )}

        {/* Dashboard Legal Footer */}
        <footer role="contentinfo" aria-label="Site footer" className="px-6 py-3 mt-auto border-t" style={{ borderColor: 'rgba(255,255,255,0.04)' }} data-testid="dashboard-legal-footer">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3 text-[9px] tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>
              <a href="/legal/terms" target="_blank" rel="noopener noreferrer" className="hover:text-[#C9A84C] transition-colors">Terms</a>
              <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
              <a href="/legal/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-[#C9A84C] transition-colors">Privacy</a>
              <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
              <a href="/legal/acceptable-use" target="_blank" rel="noopener noreferrer" className="hover:text-[#C9A84C] transition-colors">Acceptable Use</a>
              <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
              <a href="/legal/cookies" target="_blank" rel="noopener noreferrer" className="hover:text-[#C9A84C] transition-colors">Cookies</a>
              <span style={{ color: 'rgba(255,255,255,0.1)' }}>|</span>
              <a href="/legal/economic-intelligence" target="_blank" rel="noopener noreferrer" className="hover:text-[#C9A84C] transition-colors">Economic Disclaimer</a>
            </div>
            <span className="text-[8px]" style={{ color: 'rgba(255,255,255,0.55)' }}>AUREM provides business intelligence. Not financial advice.</span>
          </div>
        </footer>

        </SentinelErrorBoundary>
        </div>
      </main>
      {/* Global Admin Dev Console — floating F12-style observability overlay */}
      <AdminDevConsole token={token} isAdmin={isAdminUser} />
    </div>
  );
};

export default AuremDashboard;
