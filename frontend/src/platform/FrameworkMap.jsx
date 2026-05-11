/**
 * AUREM Operational Framework — Interactive Architecture Map
 * Shows all 11 layers with connection lines between dependent modules.
 * Route: /framework
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronLeft } from 'lucide-react';

const LAYERS = [
  {
    id: 'L0', title: 'INFRASTRUCTURE\n& SECURITY', color: '#4A7C6F',
    modules: [
      { id: 'jwt_auth', name: 'JWT Dual Auth', files: 'platform_auth_router.py\nauth_inline.py', status: 'LIVE' },
      { id: 'kill_switch', name: 'Kill Switch', files: 'kill_switch.py\ncircuit_breaker.py', status: 'LIVE' },
      { id: 'soc2', name: 'SOC2 Compliance', files: 'soc2_compliance_router.py\nsecurity_audit_router.py', status: 'LIVE' },
      { id: 'vault', name: 'Secret Vault', files: 'vault_router.py\nhmac_signing.py', status: 'LIVE' },
      { id: 'crash_protect', name: 'Crash Protection', files: 'crash_protection.py\nsecurity_gate.py', status: 'LIVE' },
    ]
  },
  {
    id: 'L1', title: 'IDENTITY\n& ACCESS', color: '#6B8E5B',
    modules: [
      { id: 'business_ids', name: 'Business IDs', files: 'business_id_router.py\nadmin_business_id_router.py', status: 'LIVE' },
      { id: 'team_connect', name: 'Team Connect', files: 'business_id_router.py\nteam_connections (DB)', status: 'LIVE' },
      { id: 'welcome_pkg', name: 'Welcome Package', files: 'welcome_package.py\nwelcome_email.html', status: 'LIVE' },
      { id: 'google_oauth', name: 'Google OAuth (Emergent)', files: 'google_oauth_callback.py\nGoogleAuthButton.js', status: 'LIVE' },
      { id: 'biometric', name: 'WebAuthn / PIN', files: 'biometric_secure.py\nbiometric_auth.py', status: 'LIVE' },
    ]
  },
  {
    id: 'L2', title: 'ORA — AI\nASSISTANT', color: '#C9A84C',
    modules: [
      { id: 'ora_pwa', name: 'ORA PWA / Desktop', files: 'OraPWA.jsx\nOraDesktopSidebar.jsx', status: 'LIVE' },
      { id: 'ora_context', name: 'Context Loader', files: 'ora_context.py\nora_context_router.py', status: 'LIVE' },
      { id: 'ora_repair', name: 'Repair Engine', files: 'ora_repair_engine.py\nORARepairEngine.jsx', status: 'LIVE' },
      { id: 'voice_layer', name: 'Voice Layer', files: 'voice_layer_router.py\nvoice_wake_word.py', status: 'LIVE' },
      { id: 'ora_dispatch', name: 'ORA Dispatcher', files: 'ora_dispatcher.py\nora_action_router.py', status: 'LIVE' },
    ]
  },
  {
    id: 'L3', title: 'INTELLIGENCE\n& ANALYSIS', color: '#5B8EAE',
    modules: [
      { id: 'ooda_loop', name: 'OODA Loop', files: 'ooda_loop_router.py\nagent_pipeline.py', status: 'LIVE' },
      { id: 'sentinel', name: 'Sentinel Anomaly', files: 'services/sentinel_anomaly.py\nflow_coordinator.py', status: 'LIVE' },
      { id: 'global_pulse', name: 'Global Pulse', files: 'global_pulse.py\nGlobalPulseDashboard.jsx', status: 'LIVE' },
      { id: 'morning_brief', name: 'Morning Brief', files: 'morning_brief_router.py\nMorningBrief.jsx', status: 'LIVE' },
      { id: 'deep_scout', name: 'Deep Scout', files: 'deep_scout_router.py\nDeepScoutDashboard.jsx', status: 'LIVE' },
    ]
  },
  {
    id: 'L4', title: 'SALES\n& CRM', color: '#AE6B5B',
    modules: [
      { id: 'sales_pipeline', name: 'Sales Pipeline', files: 'sales_pipeline.py\nSalesPipelineDashboard.jsx', status: 'LIVE' },
      { id: 'voice_sales', name: 'Voice Sales Agent', files: 'voice_sales_agent.py\nVoiceSalesAgent.jsx', status: 'LIVE' },
      { id: 'lead_enrich', name: 'Lead Enrichment', files: 'lead_enrichment.py\nlead_capture_service.py', status: 'LIVE' },
      { id: 'crm_connect', name: 'CRM Connect', files: 'crm_router.py\ncrm_sync_engine.py', status: 'LIVE' },
      { id: 'negotiation', name: 'Negotiation Engine', files: 'negotiation_engine.py\nproactive_outreach.py', status: 'LIVE' },
    ]
  },
  {
    id: 'L5', title: 'AUTOMATION\n& ACTIONS', color: '#8E5BAE',
    modules: [
      { id: 'approval_queue', name: 'Approval Queue', files: 'approval_router.py\nApprovalQueue.jsx', status: 'LIVE' },
      { id: 'agent_exec', name: 'Agent Execution', files: 'agent_execution_router.py\nagent_harness_router.py', status: 'LIVE' },
      { id: 'pipeline_engine', name: 'Pipeline Engine', files: 'pipeline_router.py\nPipelineDashboard.jsx', status: 'LIVE' },
      { id: 'orchestrator', name: 'Orchestrator Brain', files: 'orchestrator.py\norchestrator_brain_router.py', status: 'LIVE' },
      { id: 'automation', name: 'Automation Engine', files: 'automations_router.py\ncron_schedulers.py', status: 'LIVE' },
    ]
  },
  {
    id: 'L6', title: 'NOTIFICATIONS\n& COMMS', color: '#5B6BAE',
    modules: [
      { id: 'push_7type', name: '7-Type Push', files: 'notification_triggers.py\nOraNotificationPanel.jsx', status: 'LIVE' },
      { id: 'email_svc', name: 'Email Service', files: 'email_service.py\nemail_ai.py', status: 'LIVE' },
      { id: 'omni_hub', name: 'Omni-Hub', files: 'unified_inbox_router.py\nOmnichannelHub.jsx', status: 'LIVE' },
      { id: 'whatsapp', name: 'WhatsApp', files: 'whatsapp_webhook_router.py\nwhatsapp_ai_assistant.py', status: 'LIVE' },
      { id: 'panic_alerts', name: 'Panic Alerts', files: 'panic_alert_service.py\nPanicAlerts.jsx', status: 'LIVE' },
    ]
  },
  {
    id: 'L7', title: 'BILLING &\nSUBSCRIPTIONS', color: '#AE8E5B',
    modules: [
      { id: 'stripe', name: 'Stripe Payments', files: 'stripe_payment_router.py\ntoon_stripe_service.py', status: 'STUB' },
      { id: 'sub_mgr', name: 'Subscription Mgr', files: 'subscription_manager.py\nsubscription_router.py', status: 'LIVE' },
      { id: 'usage_meter', name: 'Usage Metering', files: 'usage_metering_service.py\nUsageBilling.jsx', status: 'LIVE' },
      { id: 'revenue_eng', name: 'Revenue Engine', files: 'revenue_engine.py\nRevenueAutomation.jsx', status: 'LIVE' },
    ]
  },
  {
    id: 'L8', title: 'DATA &\nMEMORY', color: '#5BAEB0',
    modules: [
      { id: 'working_mem', name: 'Working Memory', files: 'memory_router.py\nmemory_tiers.py', status: 'LIVE' },
      { id: 'session_mem', name: 'Session Memory', files: 'session_memory_router.py\nstm_service.py', status: 'LIVE' },
      { id: 'rag_kb', name: 'RAG Knowledge', files: 'rag_knowledge_base.py\nrag_router.py', status: 'LIVE' },
      { id: 'vector_search', name: 'Vector Search', files: 'vector_search.py\nembeddings.py', status: 'LIVE' },
      { id: 'nexus_bridge', name: 'Nexus Data Bridge', files: 'nexus_router.py\nNexusDataBridge.jsx', status: 'LIVE' },
    ]
  },
  {
    id: 'L9', title: 'COMPLIANCE\n& LEGAL', color: '#7B9E6B',
    modules: [
      { id: 'legal_pages', name: 'Legal Pages (6)', files: 'legal_router.py\nLegalPages.jsx', status: 'LIVE' },
      { id: 'compliance_mon', name: 'Compliance Monitor', files: 'compliance_monitor.py\ncompliance_scheduler.py', status: 'LIVE' },
      { id: 'brand_guard', name: 'Brand Guard', files: 'brand_guard.py\nspec_compliance.py', status: 'LIVE' },
      { id: 'fraud_prev', name: 'Fraud Prevention', files: 'fraud_prevention.py\nhoneypot_router.py', status: 'LIVE' },
      { id: 'tos_enforce', name: 'ToS Enforcement', files: 'Terms acceptance\non signup flow', status: 'LIVE' },
    ]
  },
  {
    id: 'L10', title: 'ADMIN &\nOPERATIONS', color: '#9E6B7B',
    modules: [
      { id: 'admin_mc', name: 'Mission Control', files: 'AdminMissionControl.jsx\nadmin_mission_control_router.py', status: 'LIVE' },
      { id: 'system_pulse', name: 'System Pulse HUD', files: 'system_pulse_router.py\nSystemPulseHUD.jsx', status: 'LIVE' },
      { id: 'self_healing', name: 'Self-Healing AI', files: 'self_healing_ai.py\nself_repair_loop.py', status: 'LIVE' },
      { id: 'genetic_repair', name: 'Genetic Repair', files: 'genetic_repair.py\nauto_repair.py', status: 'LIVE' },
      { id: 'tenant_opt', name: 'Tenant Optimization', files: 'tenant_optimization_router.py\nTenantOptimization.jsx', status: 'LIVE' },
    ]
  },
  {
    id: 'L11', title: 'AUREM LIVE\nFUNNEL', color: '#FF6B00',
    modules: [
      { id: 'accurate_scout', name: 'Accurate Scout', files: 'services/accurate_scout.py\nroutes/accurate_scout_router.py', status: 'LIVE' },
      { id: 'ora_cmd_center', name: 'ORA Command Center', files: 'services/ora_command_center.py\nplatform/ChatInterface.jsx', status: 'LIVE' },
      { id: 'dashboard_feeds', name: 'Dashboard Feeds', files: 'routers/dashboard_feeds_router.py\nplatform/feeds/*.jsx', status: 'LIVE' },
      { id: 'flame_score', name: 'Flame Score', files: 'routers/dashboard_feeds_router.py\nfeeds/HotLeadsFeed.jsx', status: 'LIVE' },
      { id: 'flame_dialer', name: 'Flame Auto-Dialer', files: 'services/flame_auto_dialer.py', status: 'LIVE' },
      { id: 'lifecycle', name: 'Lead Lifecycle', files: 'services/lead_lifecycle.py\nrouters/lead_lifecycle_router.py', status: 'LIVE' },
      { id: 'drip', name: 'Drip Sequencer (6h)', files: 'services/drip_sequencer.py\nregistry.py (cron)', status: 'LIVE' },
      { id: 'kanban', name: 'Pipeline Kanban', files: 'feeds/LeadPipelineKanban.jsx', status: 'LIVE' },
      { id: 'resend_hook', name: 'Resend Webhook', files: '/api/lifecycle/webhook/resend', status: 'LIVE' },
      { id: 'whapi_hook', name: 'WHAPI Webhook', files: '/api/lifecycle/webhook/whapi', status: 'LIVE' },
      { id: 'voicemail_blitz', name: 'Voicemail Blitz', files: 'services/drip_sequencer.py\nfire_voicemail_blitz()', status: 'LIVE' },
      { id: 'morning_digest', name: 'Morning Digest', files: 'services/morning_digest.py\nregistry.py (7 AM)', status: 'LIVE' },
      { id: 'friend_scanner', name: 'Friend Scanner Viral', files: 'trial_and_friend_router.py\n/api/customer/friend-scan', status: 'LIVE' },
      { id: 'shopify_oauth', name: 'Shopify OAuth 1-Click', files: 'shopify_oauth_router.py\nShopifyAppManager.jsx', status: 'LIVE' },
      { id: 'wordpress_plugin', name: 'WordPress Plugin', files: 'static/plugins/aurem-pixel.zip\n/api/plugins/wordpress', status: 'LIVE' },
      { id: 'retell_metered', name: 'Retell Metered Billing', files: 'voice_agent_router.py\ndb.voice_call_logs', status: 'LIVE' },
    ]
  },
];

// Connection definitions: [sourceModuleId, targetModuleId, type]
// type: 'data' (blue), 'auth' (gold), 'trigger' (orange), 'memory' (teal)
const CONNECTIONS = [
  // Auth flows
  ['jwt_auth', 'business_ids', 'auth'],
  ['jwt_auth', 'ora_pwa', 'auth'],
  ['jwt_auth', 'admin_mc', 'auth'],
  ['jwt_auth', 'approval_queue', 'auth'],
  ['biometric', 'jwt_auth', 'auth'],
  ['google_oauth', 'jwt_auth', 'auth'],
  // Business ID flows
  ['business_ids', 'welcome_pkg', 'data'],
  ['business_ids', 'team_connect', 'data'],
  ['business_ids', 'ora_context', 'data'],
  ['business_ids', 'admin_mc', 'data'],
  // ORA flows
  ['ora_context', 'ora_pwa', 'data'],
  ['ora_context', 'working_mem', 'memory'],
  ['ora_context', 'morning_brief', 'data'],
  ['ora_context', 'global_pulse', 'data'],
  ['ora_dispatch', 'agent_exec', 'trigger'],
  ['ora_dispatch', 'approval_queue', 'trigger'],
  ['ora_pwa', 'push_7type', 'trigger'],
  ['ora_pwa', 'voice_layer', 'data'],
  ['ora_repair', 'self_healing', 'trigger'],
  // Intelligence flows
  ['ooda_loop', 'sales_pipeline', 'data'],
  ['ooda_loop', 'sentinel', 'trigger'],
  ['ooda_loop', 'pipeline_engine', 'trigger'],
  ['sentinel', 'panic_alerts', 'trigger'],
  ['sentinel', 'push_7type', 'trigger'],
  ['global_pulse', 'morning_brief', 'data'],
  ['deep_scout', 'lead_enrich', 'data'],
  ['morning_brief', 'push_7type', 'trigger'],
  // Sales flows
  ['sales_pipeline', 'lead_enrich', 'data'],
  ['sales_pipeline', 'crm_connect', 'data'],
  ['voice_sales', 'sales_pipeline', 'data'],
  ['lead_enrich', 'crm_connect', 'data'],
  ['negotiation', 'sales_pipeline', 'data'],
  // Automation flows
  ['approval_queue', 'push_7type', 'trigger'],
  ['pipeline_engine', 'orchestrator', 'data'],
  ['orchestrator', 'agent_exec', 'trigger'],
  ['automation', 'orchestrator', 'data'],
  // Notification flows
  ['push_7type', 'ora_pwa', 'trigger'],
  ['email_svc', 'welcome_pkg', 'data'],
  ['omni_hub', 'whatsapp', 'data'],
  ['omni_hub', 'email_svc', 'data'],
  // Billing flows
  ['sub_mgr', 'usage_meter', 'data'],
  ['revenue_eng', 'sub_mgr', 'data'],
  ['stripe', 'sub_mgr', 'data'],
  ['hybrid_storefront', 'stripe', 'trigger'],
  ['hybrid_storefront', 'sub_mgr', 'data'],
  // Retell AI
  ['retell_ai', 'ora_dispatch', 'trigger'],
  ['retell_ai', 'retell_metered', 'data'],
  ['retell_metered', 'usage_meter', 'data'],
  // Memory flows
  ['working_mem', 'session_mem', 'memory'],
  ['rag_kb', 'vector_search', 'memory'],
  ['rag_kb', 'ora_context', 'memory'],
  ['nexus_bridge', 'working_mem', 'memory'],
  // Compliance flows
  ['compliance_mon', 'brand_guard', 'data'],
  ['fraud_prev', 'sentinel', 'trigger'],
  ['tos_enforce', 'legal_pages', 'data'],
  // Admin flows
  ['admin_mc', 'system_pulse', 'data'],
  ['self_healing', 'genetic_repair', 'trigger'],
  ['system_pulse', 'sentinel', 'data'],
  ['tenant_opt', 'usage_meter', 'data'],
  // ═══ L11 AUREM LIVE FUNNEL — the lead's entire journey ═══
  // Cross-layer entry: scout/CRM feed into Accurate Scout
  ['deep_scout', 'accurate_scout', 'data'],
  ['lead_enrich', 'accurate_scout', 'data'],
  // Accurate Scout verifies → lifecycle starts at 'new'
  ['accurate_scout', 'lifecycle', 'data'],
  // Lifecycle → Kanban visual
  ['lifecycle', 'kanban', 'data'],
  // Website visit + dashboard → flame score
  ['dashboard_feeds', 'flame_score', 'data'],
  // Flame score → Auto-dialer when INFERNO
  ['flame_score', 'flame_dialer', 'trigger'],
  // Flame Dialer → Voicemail blitz on fail
  ['flame_dialer', 'voicemail_blitz', 'trigger'],
  // Flame Dialer lifecycle update
  ['flame_dialer', 'lifecycle', 'trigger'],
  // Lifecycle auto-starts drip on called_no_response
  ['lifecycle', 'drip', 'trigger'],
  // Drip uses Twilio/Resend/WHAPI channels (existing L6 → L11)
  ['drip', 'email_svc', 'trigger'],
  ['drip', 'whatsapp', 'trigger'],
  ['drip', 'twilio', 'trigger'],
  // Voicemail blitz → 3 channels
  ['voicemail_blitz', 'email_svc', 'trigger'],
  ['voicemail_blitz', 'whatsapp', 'trigger'],
  ['voicemail_blitz', 'twilio', 'trigger'],
  // Engagement webhooks → auto-advance lifecycle
  ['resend_hook', 'lifecycle', 'trigger'],
  ['whapi_hook', 'lifecycle', 'trigger'],
  // Stripe payment → lifecycle 'won'
  ['stripe', 'lifecycle', 'trigger'],
  // ORA Command Center orchestrates
  ['ora_cmd_center', 'accurate_scout', 'trigger'],
  ['ora_cmd_center', 'flame_dialer', 'trigger'],
  ['ora_cmd_center', 'lifecycle', 'trigger'],
  // Morning Digest reads from lifecycle + flame + dialer
  ['lifecycle', 'morning_digest', 'data'],
  ['flame_score', 'morning_digest', 'data'],
  ['flame_dialer', 'morning_digest', 'data'],
  ['morning_digest', 'whatsapp', 'trigger'],
  // New L11 viral + install flows
  ['friend_scanner', 'hybrid_storefront', 'trigger'],
  ['friend_scanner', 'accurate_scout', 'data'],
  ['shopify_oauth', 'dashboard_feeds', 'data'],
  ['shopify_oauth', 'lifecycle', 'trigger'],
  ['wordpress_plugin', 'accurate_scout', 'data'],
  ['wordpress_plugin', 'dashboard_feeds', 'data'],
];

const TYPE_COLORS = {
  auth: '#C9A84C',
  data: '#5B8EAE',
  trigger: '#FF6B00',
  memory: '#5BAEB0',
};

const MODULE_W = 130;
const MODULE_H = 72;
const COL_GAP = 16;
const ROW_GAP = 12;
const HEADER_H = 50;
const TOP_PAD = 80;
const LEFT_PAD = 40;

export default function FrameworkMap() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null);
  const [positions, setPositions] = useState({});
  const [dim, setDim] = useState({ w: 0, h: 0 });
  const [pulse, setPulse] = useState({ nodes: [], summary: {} });
  const [liveMetrics, setLiveMetrics] = useState({});  // L11 per-node counters
  const [flashingNodes, setFlashingNodes] = useState({});  // node_id → {until_ts, label}
  const [eventFeed, setEventFeed] = useState([]);  // right-side ticker feed (last 12)
  const eventsSeenRef = useRef(new Set());         // dedupe by `${node_id}:${at}:${kind}`
  const [keyModal, setKeyModal] = useState(null);
  const [keyValue, setKeyValue] = useState('');
  const [injecting, setInjecting] = useState(false);

  // Sovereign Node (Ollama) state
  const [sovereignPanel, setSovereignPanel] = useState(false);
  const [sovereignUrl, setSovereignUrl] = useState('');
  const [sovereignModel, setSovereignModel] = useState('');
  const [sovereignEnabled, setSovereignEnabled] = useState(true);
  const [sovereignStatus, setSovereignStatus] = useState(null);
  const [sovereignSaving, setSovereignSaving] = useState(false);
  const [sovereignTesting, setSovereignTesting] = useState(false);
  const [sovereignTestResult, setSovereignTestResult] = useState(null);

  // XTTS Voice state
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [voiceStats, setVoiceStats] = useState(null);

  const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;
  const token = (() => {
    try {
      // Try secure store first, then localStorage fallbacks
      return sessionStorage.getItem('aurem_platform_token') || localStorage.getItem('aurem_token') || localStorage.getItem('token') || '';
    } catch { return ''; }
  })();

  // Fetch live pulse
  const fetchPulse = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/empire/pulse`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPulse(data);
      }
      // Silently ignore 401 — don't spam when token is invalid
    } catch (e) { console.debug('Pulse fetch:', e); }
  }, [API_URL, token]);

  // Fetch L11 live metrics (counters per funnel node)
  const fetchLiveMetrics = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/empire/live-metrics`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) setLiveMetrics((await res.json()).nodes || {});
    } catch (e) { console.debug('Live metrics fetch:', e); }
  }, [API_URL, token]);

  // Fetch recent LIVE EVENTS — trigger 1.5s node flashes + ticker entries
  const fetchRecentEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/empire/recent-events?seconds=30`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      const now = Date.now();
      const newFlashes = {};
      const newFeed = [];
      for (const ev of (data.events || [])) {
        const id = `${ev.node_id}:${ev.at}:${ev.kind}`;
        if (eventsSeenRef.current.has(id)) continue;
        eventsSeenRef.current.add(id);
        newFlashes[ev.node_id] = { until: now + 1500, label: ev.label, kind: ev.kind };
        newFeed.push({ ...ev, receivedAt: now });
      }
      if (eventsSeenRef.current.size > 500) {
        eventsSeenRef.current = new Set(Array.from(eventsSeenRef.current).slice(-250));
      }
      if (Object.keys(newFlashes).length > 0) {
        setFlashingNodes(prev => ({ ...prev, ...newFlashes }));
      }
      if (newFeed.length > 0) {
        setEventFeed(prev => [...newFeed, ...prev].slice(0, 12));
      }
    } catch (e) { console.debug('Recent events fetch:', e); }
  }, [API_URL, token]);

  // Decay expired flashes
  useEffect(() => {
    const iv = setInterval(() => {
      const now = Date.now();
      setFlashingNodes(prev => {
        let changed = false;
        const next = { ...prev };
        for (const [k, v] of Object.entries(prev)) {
          if (v.until < now) { delete next[k]; changed = true; }
        }
        return changed ? next : prev;
      });
    }, 500);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (!token) return;
    fetchPulse();
    fetchLiveMetrics();
    fetchRecentEvents();
    const iv1 = setInterval(fetchPulse, 30000);
    const iv2 = setInterval(fetchLiveMetrics, 15000);
    const iv3 = setInterval(fetchRecentEvents, 3000);
    return () => { clearInterval(iv1); clearInterval(iv2); clearInterval(iv3); };
  }, [fetchPulse, fetchLiveMetrics, fetchRecentEvents, token]);

  // ══════════════════════════════════════════════
  // SSE subscription — near-instant flashes from Hunt Live pipeline
  // (complements the 3s poll; catches events the poll window would miss)
  // ══════════════════════════════════════════════
  useEffect(() => {
    let clientId = sessionStorage.getItem('aurem_sse_client_id');
    if (!clientId) {
      clientId = `hud_${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem('aurem_sse_client_id', clientId);
    }
    const es = new EventSource(`${API_URL}/api/admin/events/${clientId}`);
    es.onmessage = (evt) => {
      let p; try { p = JSON.parse(evt.data); } catch { return; }
      if (p?.type !== 'hud_node_flash') return;
      const nodeId = p.data?.node;
      const business = p.data?.business;
      if (!nodeId) return;
      const now = Date.now();
      setFlashingNodes(prev => ({
        ...prev,
        [nodeId]: { until: now + 1500, label: business || p.data?.step, kind: 'hunt' },
      }));
      // Also push into event feed
      setEventFeed(prev => [{
        node_id: nodeId,
        label: business || 'hunt',
        kind: p.data?.step || 'hunt',
        at: p.timestamp,
        receivedAt: now,
      }, ...prev].slice(0, 12));
    };
    es.onerror = () => { /* EventSource auto-reconnects */ };
    return () => { try { es.close(); } catch { /* noop */ } };
  }, [API_URL]);

  // Map pulse data to module IDs
  const getNodeStatus = useCallback((modId) => {
    const node = pulse.nodes?.find(n => n.id === modId);
    if (node) return node.status;
    return null;
  }, [pulse]);

  const getNodeBlockedInfo = useCallback((modId) => {
    return pulse.nodes?.find(n => n.id === modId && n.status === 'blocked') || null;
  }, [pulse]);

  const STATUS_BADGE = {
    live: { color: '#4ADE80', bg: 'rgba(74,222,128,0.12)', border: 'rgba(74,222,128,0.3)', label: 'LIVE' },
    blocked: { color: '#EF4444', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', label: 'BLOCKED' },
    degraded: { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', label: 'DEGRADED' },
  };

  const injectKey = async (keyName) => {
    if (!keyValue.trim()) return;
    setInjecting(true);
    try {
      await fetch(`${API_URL}/api/admin/empire/inject-key`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: keyName, value: keyValue.trim() }),
      });
      setKeyModal(null);
      setKeyValue('');
      fetchPulse();
    } catch (e) { console.error(e); }
    setInjecting(false);
  };

  // ── SOVEREIGN NODE (OLLAMA) FUNCTIONS ──
  const fetchSovereignConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/local-llm/config`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSovereignUrl(data.ollama_url || '');
        setSovereignModel(data.model || '');
        setSovereignEnabled(data.enabled !== false);
        setSovereignStatus(data.last_status);
      }
    } catch (e) { console.debug('Sovereign config fetch:', e); }
  }, [API_URL, token]);

  const saveSovereignConfig = async () => {
    setSovereignSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/local-llm/config`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ollama_url: sovereignUrl.trim(),
          model: sovereignModel.trim(),
          enabled: sovereignEnabled,
        }),
      });
      if (res.ok) {
        setSovereignStatus('saved');
        setSovereignTestResult(null);
      }
    } catch (e) { console.error(e); }
    setSovereignSaving(false);
  };

  const testSovereignConnection = async () => {
    setSovereignTesting(true);
    setSovereignTestResult(null);
    try {
      const res = await fetch(`${API_URL}/api/local-llm/test`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'Hello, identify yourself in one sentence.' }),
      });
      if (res.ok) {
        const data = await res.json();
        setSovereignTestResult(data);
        setSovereignStatus(data.success ? 'online' : 'offline');
      }
    } catch (e) {
      setSovereignTestResult({ success: false, error: 'Connection failed' });
      setSovereignStatus('offline');
    }
    setSovereignTesting(false);
  };

  useEffect(() => {
    if (sovereignPanel) {
      fetchSovereignConfig();
      // Also fetch voice config
      (async () => {
        try {
          const res = await fetch(`${API_URL}/api/sovereign-voice/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (res.ok) setVoiceStatus(await res.json());
        } catch {}
        try {
          const res = await fetch(`${API_URL}/api/sovereign-voice/stats`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (res.ok) setVoiceStats(await res.json());
        } catch {}
      })();
    }
  }, [sovereignPanel, fetchSovereignConfig]);

  // Calculate positions
  useEffect(() => {
    const colW = MODULE_W + COL_GAP;
    const totalW = LEFT_PAD * 2 + LAYERS.length * colW;
    const maxRows = Math.max(...LAYERS.map(l => l.modules.length));
    const totalH = TOP_PAD + HEADER_H + maxRows * (MODULE_H + ROW_GAP) + 120;

    const pos = {};
    LAYERS.forEach((layer, ci) => {
      const x = LEFT_PAD + ci * colW;
      layer.modules.forEach((mod, ri) => {
        const y = TOP_PAD + HEADER_H + ri * (MODULE_H + ROW_GAP);
        pos[mod.id] = { x, y, cx: x + MODULE_W / 2, cy: y + MODULE_H / 2, col: ci, row: ri };
      });
    });
    setPositions(pos);
    setDim({ w: totalW, h: totalH });
  }, []);

  const getConnectionPath = useCallback((fromId, toId) => {
    const from = positions[fromId];
    const to = positions[toId];
    if (!from || !to) return '';

    const fx = from.cx;
    const fy = from.cy;
    const tx = to.cx;
    const ty = to.cy;

    // Determine exit/entry sides
    if (from.col < to.col) {
      // Left to right
      const sx = from.x + MODULE_W + 2;
      const sy = fy;
      const ex = to.x - 2;
      const ey = ty;
      const mx = (sx + ex) / 2;
      return `M${sx},${sy} C${mx},${sy} ${mx},${ey} ${ex},${ey}`;
    } else if (from.col > to.col) {
      // Right to left
      const sx = from.x - 2;
      const sy = fy;
      const ex = to.x + MODULE_W + 2;
      const ey = ty;
      const mx = (sx + ex) / 2;
      return `M${sx},${sy} C${mx},${sy} ${mx},${ey} ${ex},${ey}`;
    } else {
      // Same column (vertical)
      const sx = fx + 20;
      const sy = from.y + MODULE_H + 2;
      const ex = tx + 20;
      const ey = to.y - 2;
      return `M${sx},${sy} C${sx},${(sy + ey) / 2} ${ex},${(sy + ey) / 2} ${ex},${ey}`;
    }
  }, [positions]);

  const isRelated = useCallback((modId) => {
    if (!hovered && !selected) return false;
    const active = selected || hovered;
    return CONNECTIONS.some(([f, t]) =>
      (f === active && t === modId) || (t === active && f === modId)
    ) || modId === active;
  }, [hovered, selected]);

  const isConnectionActive = useCallback(([f, t]) => {
    const active = selected || hovered;
    if (!active) return false;
    return f === active || t === active;
  }, [hovered, selected]);

  if (dim.w === 0) return null;

  return (
    <div ref={containerRef} style={{ background: '#050507', minHeight: '100vh', color: '#E8E0D0', overflow: 'auto' }}>
      <style>{`
        @keyframes flowDash { from { stroke-dashoffset: 20; } to { stroke-dashoffset: 0; } }
        .fwk-conn { transition: opacity 0.3s, stroke-width 0.3s; }
        .fwk-conn.active { animation: flowDash 1s linear infinite; }
        .fwk-mod { transition: transform 0.2s, box-shadow 0.2s, opacity 0.3s; cursor: pointer; }
        .fwk-mod:hover { transform: scale(1.06); }
        .fwk-mod.dimmed { opacity: 0.2; }
        .fwk-mod.highlighted { box-shadow: 0 0 20px rgba(201,168,76,0.4); transform: scale(1.04); }
        .fwk-legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
      `}</style>

      {/* Back button */}
      <a href="/dashboard" style={{ position: 'fixed', top: 16, left: 16, zIndex: 100, display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#9A9490', textDecoration: 'none', fontSize: 12, fontFamily: "'Jost',sans-serif" }}>
        <ChevronLeft size={14} /> Dashboard
      </a>

      {/* 🔴 LIVE EVENT TICKER — bottom-left, fixed */}
      <div
        data-testid="live-event-ticker"
        style={{
          position: 'fixed', bottom: 16, left: 16, zIndex: 100,
          width: 340, maxHeight: 260, overflowY: 'auto',
          borderRadius: 12,
          background: 'rgba(10,10,20,0.92)',
          border: '1px solid rgba(255,107,0,0.3)',
          backdropFilter: 'blur(14px)',
          fontFamily: "'Jost',sans-serif",
          boxShadow: eventFeed.length > 0 ? '0 0 30px rgba(255,23,68,0.25)' : 'none',
          transition: 'box-shadow 0.4s',
        }}
      >
        <div style={{
          padding: '8px 14px', borderBottom: '1px solid rgba(255,255,255,0.08)',
          fontSize: 10, letterSpacing: '0.2em', color: '#FF6B00', fontWeight: 700,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: eventFeed.length > 0 ? '#FF1744' : '#4ADE80',
            boxShadow: eventFeed.length > 0 ? '0 0 12px #FF1744' : 'none',
            animation: eventFeed.length > 0 ? 'flowDash 1s linear infinite' : 'none',
          }} />
          LIVE EVENT FEED — L11
          <span style={{ marginLeft: 'auto', color: '#6A6070', fontSize: 9 }}>
            {eventFeed.length > 0 ? `${eventFeed.length} event${eventFeed.length === 1 ? '' : 's'}` : 'idle'}
          </span>
        </div>
        {eventFeed.length === 0 && (
          <div style={{ padding: '14px', fontSize: 10, color: '#6A6070', fontStyle: 'italic', textAlign: 'center' }}>
            Waiting for real-time events…<br />
            (flame alerts · auto-dials · drip steps · webhooks · transitions)
          </div>
        )}
        {eventFeed.map((ev, i) => {
          const age = Math.round((Date.now() - ev.receivedAt) / 1000);
          const NODE_TITLES = {
            flame_score: '🔥 Flame Score', flame_dialer: '☎️ Auto-Dialer',
            morning_digest: '☕ Morning Digest', dashboard_feeds: '👀 Live Viewer',
            drip: '💧 Drip Step', resend_hook: '📧 Resend',
            whapi_hook: '💬 WhatsApp', voicemail_blitz: '📣 Blitz',
            lifecycle: '🏆 Lifecycle', kanban: '📊 Kanban',
            accurate_scout: '🎯 Accurate Scout', ora_cmd_center: '🤖 ORA Cmd',
          };
          return (
            <div key={i}
              data-testid={`live-event-row-${i}`}
              style={{
                padding: '6px 14px',
                borderBottom: i < eventFeed.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                fontSize: 10,
                animation: i === 0 && age < 2 ? 'flowDash 0.6s ease-out' : 'none',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ color: '#FFB76B', fontWeight: 700 }}>
                  {NODE_TITLES[ev.node_id] || ev.node_id}
                </span>
                <span style={{ color: '#6A6070', fontSize: 9 }}>{age}s ago</span>
              </div>
              {ev.business && (
                <div style={{ color: '#E8E0D0', fontSize: 10 }}>{(ev.business || '').slice(0, 36)}</div>
              )}
              {ev.label && (
                <div style={{ color: '#9A9490', fontSize: 9, fontStyle: 'italic' }}>{(ev.label || '').slice(0, 50)}</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 100, padding: '10px 16px', borderRadius: 12, background: 'rgba(10,10,20,0.95)', border: '1px solid rgba(255,255,255,0.08)', backdropFilter: 'blur(12px)', display: 'flex', gap: 16, fontSize: 10, fontFamily: "'Jost',sans-serif", alignItems: 'center' }}>
        <span><span className="fwk-legend-dot" style={{ background: TYPE_COLORS.auth }} />Auth</span>
        <span><span className="fwk-legend-dot" style={{ background: TYPE_COLORS.data }} />Data</span>
        <span><span className="fwk-legend-dot" style={{ background: TYPE_COLORS.trigger }} />Trigger</span>
        <span><span className="fwk-legend-dot" style={{ background: TYPE_COLORS.memory }} />Memory</span>
        <span style={{ color: '#6A6070', cursor: 'pointer' }} onClick={() => { setSelected(null); setHovered(null); }}>Clear</span>
        <span style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: 12 }}>
          <button
            onClick={() => setSovereignPanel(true)}
            data-testid="sovereign-node-btn"
            style={{
              padding: '4px 12px', borderRadius: 8, fontSize: 10, fontWeight: 700,
              background: 'linear-gradient(135deg, #4ADE80, #059669)',
              color: '#050507', border: 'none', cursor: 'pointer',
              fontFamily: "'Jost',sans-serif", letterSpacing: '0.05em',
            }}
          >SOVEREIGN NODE</button>
        </span>
      </div>

      <svg
        ref={svgRef}
        width={dim.w}
        height={dim.h}
        style={{ display: 'block', margin: '0 auto' }}
        onClick={(e) => { if (e.target === svgRef.current) setSelected(null); }}
      >
        {/* Title */}
        <text x={dim.w / 2} y={30} textAnchor="middle" style={{ fontFamily: "'Cinzel',serif", fontSize: 18, fontWeight: 700, fill: '#C9A84C', letterSpacing: '0.1em' }}>
          AUREM EMPIRE HUD — SOVEREIGN ARCHITECTURE
        </text>
        <text x={dim.w / 2} y={48} textAnchor="middle" style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, fill: '#6A6070', letterSpacing: '0.2em' }}>
          {pulse.summary?.total || 0} NODES · {pulse.summary?.live || 0} LIVE · {pulse.summary?.blocked || 0} BLOCKED · {pulse.summary?.health_pct || 0}% HEALTH
        </text>

        {/* Layer Headers */}
        {LAYERS.map((layer, ci) => {
          const x = LEFT_PAD + ci * (MODULE_W + COL_GAP);
          return (
            <g key={layer.id}>
              <rect x={x} y={TOP_PAD - 6} width={MODULE_W} height={HEADER_H} rx={8}
                fill={layer.color} fillOpacity={0.12}
                stroke={layer.color} strokeOpacity={0.3} strokeWidth={1} />
              {layer.title.split('\n').map((line, li) => (
                <text key={li} x={x + MODULE_W / 2} y={TOP_PAD + 10 + li * 14} textAnchor="middle"
                  style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 700, fill: layer.color, letterSpacing: '0.1em' }}>
                  {line}
                </text>
              ))}
              <text x={x + MODULE_W / 2} y={TOP_PAD + 38} textAnchor="middle"
                style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 8, fill: '#6A6070' }}>
                {layer.id}
              </text>
            </g>
          );
        })}

        {/* Connections (behind modules) */}
        <g>
          {CONNECTIONS.map(([fromId, toId, type], i) => {
            const path = getConnectionPath(fromId, toId);
            if (!path) return null;
            const active = isConnectionActive([fromId, toId, type]);
            const anyActive = selected || hovered;
            // L11 funnel nodes — mark visually
            const L11_IDS = new Set(['accurate_scout','ora_cmd_center','dashboard_feeds','flame_score','flame_dialer','lifecycle','drip','kanban','resend_hook','whapi_hook','voicemail_blitz','morning_digest']);
            const isL11 = L11_IDS.has(fromId) || L11_IDS.has(toId);
            return (
              <g key={i}>
                <path
                  id={`conn-path-${i}`}
                  d={path}
                  fill="none"
                  stroke={isL11 ? '#FF6B00' : (TYPE_COLORS[type] || '#6A6070')}
                  strokeWidth={active ? 2.5 : (isL11 ? 1.3 : 1)}
                  strokeOpacity={anyActive ? (active ? 0.9 : 0.04) : (isL11 ? 0.35 : 0.15)}
                  strokeDasharray={active ? '6 4' : (isL11 ? '3 4' : 'none')}
                  className={`fwk-conn ${active ? 'active' : ''} ${isL11 ? 'l11' : ''}`}
                  markerEnd={active ? `url(#arrow-${type})` : ''}
                />
                {/* L11 animated pulse dot traveling along the path */}
                {isL11 && (
                  <circle r={2.4} fill="#FFAB00" opacity={0.9}>
                    <animateMotion
                      dur={`${3 + (i % 5) * 0.6}s`}
                      repeatCount="indefinite"
                      path={path}
                      rotate="auto"
                    />
                  </circle>
                )}
              </g>
            );
          })}
        </g>

        {/* Arrow markers */}
        <defs>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <marker key={type} id={`arrow-${type}`} viewBox="0 0 10 10" refX={9} refY={5}
              markerWidth={6} markerHeight={6} orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
            </marker>
          ))}
        </defs>

        {/* Module Cards */}
        {LAYERS.map((layer, ci) =>
          layer.modules.map((mod) => {
            const pos = positions[mod.id];
            if (!pos) return null;
            const related = isRelated(mod.id);
            const anyActive = selected || hovered;
            const isActive = mod.id === (selected || hovered);

            return (
              <g
                key={mod.id}
                className={`fwk-mod ${anyActive && !related ? 'dimmed' : ''} ${related && !isActive ? 'highlighted' : ''}`}
                onMouseEnter={() => setHovered(mod.id)}
                onMouseLeave={() => setHovered(null)}
                onClick={(e) => { e.stopPropagation(); setSelected(selected === mod.id ? null : mod.id); }}
              >
                {/* Card background */}
                <rect x={pos.x} y={pos.y} width={MODULE_W} height={MODULE_H} rx={10}
                  fill={isActive ? layer.color : '#0C0C14'}
                  fillOpacity={isActive ? 0.2 : 0.95}
                  stroke={isActive ? layer.color : related ? '#C9A84C' : 'rgba(255,255,255,0.06)'}
                  strokeWidth={isActive ? 2 : related ? 1.5 : 0.5}
                />
                {/* Glow effect for active */}
                {isActive && (
                  <rect x={pos.x - 2} y={pos.y - 2} width={MODULE_W + 4} height={MODULE_H + 4} rx={12}
                    fill="none" stroke={layer.color} strokeOpacity={0.25} strokeWidth={4}
                    filter="url(#glow)" />
                )}
                {/* Module name */}
                <text x={pos.x + MODULE_W / 2} y={pos.y + 18} textAnchor="middle"
                  style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, fontWeight: 600, fill: isActive ? '#FFF' : '#E8E0D0' }}>
                  {mod.name}
                </text>
                {/* Files */}
                {mod.files.split('\n').map((file, fi) => (
                  <text key={fi} x={pos.x + MODULE_W / 2} y={pos.y + 32 + fi * 10} textAnchor="middle"
                    style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 7, fill: isActive ? 'rgba(255,255,255,0.7)' : '#5A5468' }}>
                    {file.length > 22 ? file.slice(0, 20) + '...' : file}
                  </text>
                ))}
                {/* Status badge — live pulse or static fallback */}
                {(() => {
                  const liveStatus = getNodeStatus(mod.id);
                  const st = liveStatus ? STATUS_BADGE[liveStatus] : (mod.status === 'LIVE' ? STATUS_BADGE.live : STATUS_BADGE.degraded);
                  const label = liveStatus ? st.label : mod.status;
                  const blockedInfo = getNodeBlockedInfo(mod.id);
                  // L11 live metric — render tiny chip above the status badge
                  const m = liveMetrics[mod.id];
                  let metricText = null;
                  if (m) {
                    if (mod.id === 'accurate_scout') metricText = `${m.high_confidence || 0} HIGH · ${m.total_verified || 0} total`;
                    else if (mod.id === 'ora_cmd_center') metricText = `${m.commands_24h || 0} cmds/24h`;
                    else if (mod.id === 'dashboard_feeds') metricText = `${m.live_viewers || 0} live now`;
                    else if (mod.id === 'flame_score') metricText = `${m.alerts_24h || 0} alerts · top ${m.top_score || 0}`;
                    else if (mod.id === 'flame_dialer') metricText = `${m.dials_24h || 0} dials/24h`;
                    else if (mod.id === 'lifecycle' || mod.id === 'kanban') metricText = `${m.active || 0} active leads`;
                    else if (mod.id === 'drip') metricText = `${m.steps_24h || 0} steps/24h`;
                    else if (mod.id === 'resend_hook') metricText = `${m.events_24h || 0} events/24h`;
                    else if (mod.id === 'whapi_hook') metricText = `${m.events_24h || 0} events/24h`;
                    else if (mod.id === 'voicemail_blitz') metricText = `${m.fired_24h || 0} fired/24h`;
                    else if (mod.id === 'morning_digest') metricText = m.last_ok ? `${m.total_sent || 0} sent · OK` : `${m.total_sent || 0} sent`;
                  }
                  // LIVE EVENT flash
                  const flash = flashingNodes[mod.id];
                  return (
                    <g>
                      {/* 🔴 LIVE EVENT PING — super-bright flash + expanding ring */}
                      {flash && (
                        <g className="aurem-event-flash">
                          {/* Soft halo behind the module */}
                          <rect x={pos.x - 4} y={pos.y - 4} width={MODULE_W + 8} height={MODULE_H + 8} rx={8}
                            fill="none" stroke="#FFAB00" strokeWidth={2} opacity={0.9}>
                            <animate attributeName="stroke-opacity" values="1;0" dur="1.5s" fill="freeze" />
                            <animate attributeName="stroke-width" values="2;6" dur="1.5s" fill="freeze" />
                          </rect>
                          {/* Inner bright glow rect */}
                          <rect x={pos.x} y={pos.y} width={MODULE_W} height={MODULE_H} rx={6}
                            fill="#FFAB00" opacity={0.35}>
                            <animate attributeName="opacity" values="0.45;0" dur="1.5s" fill="freeze" />
                          </rect>
                          {/* Expanding ring from center */}
                          <circle cx={pos.x + MODULE_W / 2} cy={pos.y + MODULE_H / 2} r={4}
                            fill="none" stroke="#FF1744" strokeWidth={2} opacity={1}>
                            <animate attributeName="r" values="4;50" dur="1.5s" fill="freeze" />
                            <animate attributeName="stroke-opacity" values="1;0" dur="1.5s" fill="freeze" />
                          </circle>
                          {/* Label floating above */}
                          {flash.label && (
                            <g transform={`translate(${pos.x + MODULE_W / 2}, ${pos.y - 6})`}>
                              <rect x={-45} y={-11} width={90} height={13} rx={6}
                                fill="#FF1744" opacity={0.95}>
                                <animate attributeName="opacity" values="1;0" dur="1.5s" fill="freeze" />
                              </rect>
                              <text x={0} y={-2} textAnchor="middle"
                                style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 7, fontWeight: 800, fill: '#fff' }}>
                                <animate attributeName="fill-opacity" values="1;0" dur="1.5s" fill="freeze" />
                                {(flash.label || 'LIVE EVENT').slice(0, 20)}
                              </text>
                            </g>
                          )}
                        </g>
                      )}
                      {/* Pulse ring for live nodes */}
                      {liveStatus === 'live' && !flash && (
                        <circle cx={pos.x + MODULE_W - 10} cy={pos.y + 10} r={3} fill={st.color} opacity={0.8}>
                          <animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.8;0.3;0.8" dur="2s" repeatCount="indefinite" />
                        </circle>
                      )}
                      {/* Red lock icon for blocked */}
                      {liveStatus === 'blocked' && (
                        <text x={pos.x + MODULE_W - 12} y={pos.y + 13} style={{ fontSize: 10, fill: '#EF4444', cursor: 'pointer' }}
                          onClick={(e) => { e.stopPropagation(); if (blockedInfo?.blocked_keys?.[0]) setKeyModal(blockedInfo); }}>
                          &#x1F512;
                        </text>
                      )}
                      {/* L11 live metric chip — only for funnel nodes */}
                      {metricText && (
                        <>
                          <rect x={pos.x + 4} y={pos.y + MODULE_H - 30} width={MODULE_W - 8} height={11} rx={5}
                            fill="rgba(255,107,0,0.12)" stroke="rgba(255,107,0,0.35)" strokeWidth={0.5} />
                          <text x={pos.x + MODULE_W / 2} y={pos.y + MODULE_H - 22} textAnchor="middle"
                            style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 7, fontWeight: 700, fill: '#FFB76B' }}>
                            {metricText.length > 22 ? metricText.slice(0, 20) + '…' : metricText}
                          </text>
                        </>
                      )}
                      <rect x={pos.x + MODULE_W / 2 - 18} y={pos.y + MODULE_H - 16} width={36} height={12} rx={6}
                        fill={st.bg} stroke={st.border} strokeWidth={0.5} />
                      <text x={pos.x + MODULE_W / 2} y={pos.y + MODULE_H - 8} textAnchor="middle"
                        style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 7, fontWeight: 700, fill: st.color }}>
                        {label}
                      </text>
                    </g>
                  );
                })()}
              </g>
            );
          })
        )}

        {/* Glow filter */}
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Footer */}
        <text x={dim.w / 2} y={dim.h - 30} textAnchor="middle"
          style={{ fontFamily: "'Cinzel',serif", fontSize: 12, fontWeight: 700, fill: '#C9A84C', letterSpacing: '0.08em' }}>
          AUREM — SOVEREIGN BANK LINK — POLARIS BUILT INC. 2026
        </text>
      </svg>

      {/* Info Panel (when selected) */}
      {selected && positions[selected] && (() => {
        const mod = LAYERS.flatMap(l => l.modules).find(m => m.id === selected);
        const layer = LAYERS.find(l => l.modules.some(m => m.id === selected));
        const inbound = CONNECTIONS.filter(([, t]) => t === selected).map(([f, , type]) => ({ id: f, type }));
        const outbound = CONNECTIONS.filter(([f]) => f === selected).map(([, t, type]) => ({ id: t, type }));
        const getModName = (id) => LAYERS.flatMap(l => l.modules).find(m => m.id === id)?.name || id;
        return (
          <div style={{
            position: 'fixed', bottom: 20, left: '50%', transform: 'translateX(-50%)',
            zIndex: 200, padding: '16px 24px', borderRadius: 16,
            background: 'rgba(10,10,20,0.98)', border: `1px solid ${layer?.color || '#C9A84C'}40`,
            backdropFilter: 'blur(24px)', maxWidth: 600, width: '90%',
            boxShadow: `0 20px 60px rgba(0,0,0,0.8), 0 0 30px ${layer?.color || '#C9A84C'}10`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
              <div>
                <div style={{ fontFamily: "'Cinzel',serif", fontSize: 16, fontWeight: 700, color: layer?.color || '#C9A84C' }}>{mod?.name}</div>
                <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#6A6070', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
                  {layer?.title?.replace('\n', ' ')} · {layer?.id}
                </div>
              </div>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: mod?.status === 'LIVE' ? '#4ADE80' : '#FFB347', padding: '2px 10px', borderRadius: 8, background: mod?.status === 'LIVE' ? 'rgba(74,222,128,0.1)' : 'rgba(255,179,71,0.1)' }}>
                {mod?.status}
              </div>
            </div>
            <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#8A8070', marginBottom: 12 }}>
              {mod?.files?.split('\n').join(' · ')}
            </div>
            <div style={{ display: 'flex', gap: 24 }}>
              {inbound.length > 0 && (
                <div>
                  <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 700, color: '#6A6070', letterSpacing: '0.15em', marginBottom: 6 }}>RECEIVES FROM</div>
                  {inbound.map((c, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: TYPE_COLORS[c.type] }} />
                      <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#E8E0D0', cursor: 'pointer' }}
                        onClick={() => setSelected(c.id)}>{getModName(c.id)}</span>
                    </div>
                  ))}
                </div>
              )}
              {outbound.length > 0 && (
                <div>
                  <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, fontWeight: 700, color: '#6A6070', letterSpacing: '0.15em', marginBottom: 6 }}>SENDS TO</div>
                  {outbound.map((c, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: TYPE_COLORS[c.type] }} />
                      <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#E8E0D0', cursor: 'pointer' }}
                        onClick={() => setSelected(c.id)}>{getModName(c.id)}</span>
                    </div>
                  ))}
                </div>
              )}
              {inbound.length === 0 && outbound.length === 0 && (
                <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#5A5468' }}>Standalone module</div>
              )}
            </div>
          </div>
        );
      })()}

      {/* Key Injection Modal */}
      {keyModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', zIndex: 300,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setKeyModal(null)}>
          <div style={{
            background: '#0C0C14', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 16, padding: '28px 32px', maxWidth: 480, width: '90%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
          }} onClick={e => e.stopPropagation()} data-testid="key-injection-modal">
            <div style={{ fontFamily: "'Cinzel',serif", fontSize: 16, fontWeight: 700, color: '#EF4444', marginBottom: 4 }}>
              KEY INJECTION — {keyModal.key_provider || keyModal.name}
            </div>
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#6A6070', marginBottom: 16 }}>
              Get your key from: <span style={{ color: '#C9A84C' }}>{keyModal.key_url}</span>
            </div>
            {(keyModal.blocked_keys || []).map((k, i) => (
              <div key={i} style={{ marginBottom: 12 }}>
                <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#9A9490', marginBottom: 4 }}>{k}</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="password" placeholder={`Paste ${k} here...`}
                    value={keyValue} onChange={e => setKeyValue(e.target.value)}
                    style={{
                      flex: 1, padding: '8px 12px', borderRadius: 8, fontSize: 12,
                      background: '#050507', border: '1px solid rgba(239,68,68,0.2)',
                      color: '#E8E0D0', fontFamily: "'JetBrains Mono',monospace",
                    }}
                    data-testid="key-input"
                  />
                  <button
                    onClick={() => injectKey(k)}
                    disabled={injecting || !keyValue.trim()}
                    style={{
                      padding: '8px 20px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                      background: injecting ? '#333' : 'linear-gradient(135deg, #D4AF37, #A08028)',
                      color: '#050507', border: 'none', cursor: 'pointer',
                      fontFamily: "'Jost',sans-serif", letterSpacing: '0.05em',
                    }}
                    data-testid="inject-key-btn"
                  >
                    {injecting ? 'INJECTING...' : 'INJECT'}
                  </button>
                </div>
              </div>
            ))}
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, color: '#5A5468', marginTop: 12 }}>
              Key will be persisted to .env and activated immediately. Node will turn GREEN on next pulse.
            </div>
          </div>
        </div>
      )}

      {/* ═══ SOVEREIGN NODE PANEL ═══ */}
      {sovereignPanel && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.88)', zIndex: 300,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setSovereignPanel(false)}>
          <div style={{
            background: '#0C0C14', border: '1px solid rgba(74,222,128,0.3)',
            borderRadius: 16, padding: '28px 32px', maxWidth: 520, width: '92%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
          }} onClick={e => e.stopPropagation()} data-testid="sovereign-node-panel">

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 12,
                background: 'linear-gradient(135deg, #4ADE80, #059669)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 20,
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#050507" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="4" width="16" height="16" rx="2" />
                  <rect x="9" y="9" width="6" height="6" />
                  <line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" />
                  <line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" />
                  <line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" />
                  <line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" />
                </svg>
              </div>
              <div>
                <div style={{ fontFamily: "'Cinzel',serif", fontSize: 16, fontWeight: 700, color: '#4ADE80' }}>
                  SOVEREIGN NODE
                </div>
                <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#6A6070', letterSpacing: '0.1em' }}>
                  LOCAL LLM ENGINE — HYBRID MODE
                </div>
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <div style={{
                  padding: '4px 10px', borderRadius: 20, fontSize: 9, fontWeight: 700,
                  fontFamily: "'JetBrains Mono',monospace", letterSpacing: '0.1em',
                  background: sovereignStatus === 'online' ? 'rgba(74,222,128,0.15)' : 'rgba(239,68,68,0.15)',
                  color: sovereignStatus === 'online' ? '#4ADE80' : '#EF4444',
                  border: `1px solid ${sovereignStatus === 'online' ? 'rgba(74,222,128,0.3)' : 'rgba(239,68,68,0.3)'}`,
                }}>
                  {sovereignStatus === 'online' ? 'ONLINE' : sovereignStatus === 'saved' ? 'SAVED' : 'OFFLINE'}
                </div>
              </div>
            </div>

            {/* Mode Badge */}
            <div style={{
              padding: '8px 14px', borderRadius: 10, marginBottom: 16,
              background: 'rgba(201,168,76,0.08)', border: '1px solid rgba(201,168,76,0.2)',
              fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#C9A84C',
            }}>
              <strong>HYBRID MODE:</strong> ORA Chat routes to your local GPU ($0). Deep analysis + voice uses cloud GPT-4o as fallback.
            </div>

            {/* Ollama URL */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#9A9490', marginBottom: 6, letterSpacing: '0.05em' }}>
                OLLAMA URL (Ngrok Tunnel)
              </div>
              <input
                type="text"
                value={sovereignUrl}
                onChange={e => setSovereignUrl(e.target.value)}
                placeholder="https://your-tunnel.ngrok-free.dev"
                style={{
                  width: '100%', padding: '10px 14px', borderRadius: 10, fontSize: 13,
                  background: '#050507', border: '1px solid rgba(74,222,128,0.2)',
                  color: '#E8E0D0', fontFamily: "'JetBrains Mono',monospace",
                  boxSizing: 'border-box',
                }}
                data-testid="sovereign-url-input"
              />
            </div>

            {/* Model Name */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#9A9490', marginBottom: 6, letterSpacing: '0.05em' }}>
                MODEL NAME
              </div>
              <input
                type="text"
                value={sovereignModel}
                onChange={e => setSovereignModel(e.target.value)}
                placeholder="llama3.1"
                style={{
                  width: '100%', padding: '10px 14px', borderRadius: 10, fontSize: 13,
                  background: '#050507', border: '1px solid rgba(74,222,128,0.2)',
                  color: '#E8E0D0', fontFamily: "'JetBrains Mono',monospace",
                  boxSizing: 'border-box',
                }}
                data-testid="sovereign-model-input"
              />
            </div>

            {/* Enabled Toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <button
                onClick={() => setSovereignEnabled(!sovereignEnabled)}
                data-testid="sovereign-toggle"
                style={{
                  width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
                  background: sovereignEnabled ? '#4ADE80' : '#333',
                  position: 'relative', transition: 'background 0.2s',
                }}
              >
                <div style={{
                  width: 18, height: 18, borderRadius: '50%', background: '#fff',
                  position: 'absolute', top: 3,
                  left: sovereignEnabled ? 23 : 3, transition: 'left 0.2s',
                }} />
              </button>
              <span style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: sovereignEnabled ? '#4ADE80' : '#6A6070' }}>
                {sovereignEnabled ? 'Sovereign Node Active' : 'Sovereign Node Disabled'}
              </span>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
              <button
                onClick={saveSovereignConfig}
                disabled={sovereignSaving || !sovereignUrl.trim() || !sovereignModel.trim()}
                data-testid="sovereign-save-btn"
                style={{
                  flex: 1, padding: '10px 16px', borderRadius: 10, fontSize: 12, fontWeight: 700,
                  background: sovereignSaving ? '#333' : 'linear-gradient(135deg, #4ADE80, #059669)',
                  color: '#050507', border: 'none', cursor: 'pointer',
                  fontFamily: "'Jost',sans-serif", letterSpacing: '0.05em',
                  opacity: (!sovereignUrl.trim() || !sovereignModel.trim()) ? 0.5 : 1,
                }}
              >
                {sovereignSaving ? 'SAVING...' : 'SAVE CONFIG'}
              </button>
              <button
                onClick={testSovereignConnection}
                disabled={sovereignTesting || !sovereignUrl.trim()}
                data-testid="sovereign-test-btn"
                style={{
                  flex: 1, padding: '10px 16px', borderRadius: 10, fontSize: 12, fontWeight: 700,
                  background: sovereignTesting ? '#333' : 'linear-gradient(135deg, #C9A84C, #A08028)',
                  color: '#050507', border: 'none', cursor: 'pointer',
                  fontFamily: "'Jost',sans-serif", letterSpacing: '0.05em',
                  opacity: !sovereignUrl.trim() ? 0.5 : 1,
                }}
              >
                {sovereignTesting ? 'TESTING...' : 'TEST CONNECTION'}
              </button>
            </div>

            {/* Test Result */}
            {sovereignTestResult && (
              <div style={{
                padding: '12px 14px', borderRadius: 10, marginBottom: 12,
                background: sovereignTestResult.success ? 'rgba(74,222,128,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${sovereignTestResult.success ? 'rgba(74,222,128,0.25)' : 'rgba(239,68,68,0.25)'}`,
              }} data-testid="sovereign-test-result">
                {sovereignTestResult.success ? (
                  <>
                    <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, fontWeight: 700, color: '#4ADE80', marginBottom: 6 }}>
                      HANDSHAKE SUCCESSFUL — {sovereignTestResult.model} ({sovereignTestResult.cost})
                    </div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#9A9490', lineHeight: '1.5', background: '#0A0A12', padding: '8px 10px', borderRadius: 6 }}>
                      {sovereignTestResult.response}
                    </div>
                  </>
                ) : (
                  <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 11, color: '#EF4444' }}>
                    CONNECTION FAILED: {sovereignTestResult.error}
                    {sovereignTestResult.available_models && (
                      <div style={{ marginTop: 6, color: '#C9A84C', fontSize: 10 }}>
                        Available models: {sovereignTestResult.available_models.join(', ')}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Info */}
            <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 9, color: '#5A5468', lineHeight: '1.6' }}>
              Config persists to DB. When your Ngrok tunnel restarts, update the URL here.
              ORA Chat will route through your local GPU at $0/request. Cloud LLM remains as safety net.
            </div>

            {/* ═══ XTTS VOICE SECTION ═══ */}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', marginTop: 20, paddingTop: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: 'linear-gradient(135deg, #8B5CF6, #6D28D9)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
                    <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
                    <path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
                  </svg>
                </div>
                <div>
                  <div style={{ fontFamily: "'Cinzel',serif", fontSize: 14, fontWeight: 700, color: '#8B5CF6' }}>
                    SOVEREIGN VOICE
                  </div>
                  <div style={{ fontFamily: "'Jost',sans-serif", fontSize: 10, color: '#6A6070', letterSpacing: '0.1em' }}>
                    XTTS v2 — LOCAL VOICE CLONING
                  </div>
                </div>
                <div style={{ marginLeft: 'auto' }}>
                  <div style={{
                    padding: '4px 10px', borderRadius: 20, fontSize: 9, fontWeight: 700,
                    fontFamily: "'JetBrains Mono',monospace", letterSpacing: '0.1em',
                    background: voiceStatus?.online ? 'rgba(139,92,246,0.15)' : 'rgba(100,100,100,0.15)',
                    color: voiceStatus?.online ? '#8B5CF6' : '#6A6070',
                    border: voiceStatus?.online ? '1px solid rgba(139,92,246,0.3)' : '1px solid rgba(100,100,100,0.2)',
                  }}>
                    {voiceStatus?.online ? 'ACTIVE' : 'STANDBY'}
                  </div>
                </div>
              </div>

              {/* Voice Config */}
              <div style={{
                padding: '12px 14px', borderRadius: 10, marginBottom: 12,
                background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.15)',
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: '#6A6070', marginBottom: 4 }}>ENGINE</div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: '#8B5CF6', fontWeight: 700 }}>
                      {voiceStatus?.engine || 'xtts_v2'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: '#6A6070', marginBottom: 4 }}>SERVER</div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: voiceStatus?.online ? '#4ADE80' : '#6A6070', fontWeight: 700 }}>
                      {voiceStatus?.server_url || 'localhost:5002'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: '#6A6070', marginBottom: 4 }}>SPEAKER</div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: '#E8E0D0' }}>
                      {voiceStatus?.speaker || 'ORA'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 9, color: '#6A6070', marginBottom: 4 }}>LANGUAGE</div>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: '#E8E0D0' }}>
                      {voiceStatus?.language || 'en'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Voice Stats */}
              {voiceStats && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 12 }}>
                  <div style={{ textAlign: 'center', padding: '8px', borderRadius: 8, background: 'rgba(139,92,246,0.05)' }}>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 16, fontWeight: 700, color: '#8B5CF6' }}>
                      {voiceStats.total_requests || 0}
                    </div>
                    <div style={{ fontSize: 8, color: '#6A6070', letterSpacing: '0.1em' }}>REQUESTS</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: '8px', borderRadius: 8, background: 'rgba(74,222,128,0.05)' }}>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 16, fontWeight: 700, color: '#4ADE80' }}>
                      {voiceStats.success_count || 0}
                    </div>
                    <div style={{ fontSize: 8, color: '#6A6070', letterSpacing: '0.1em' }}>SUCCESS</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: '8px', borderRadius: 8, background: 'rgba(201,168,76,0.05)' }}>
                    <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 16, fontWeight: 700, color: '#C9A84C' }}>
                      {voiceStats.avg_first_byte_ms ? `${voiceStats.avg_first_byte_ms}ms` : '--'}
                    </div>
                    <div style={{ fontSize: 8, color: '#6A6070', letterSpacing: '0.1em' }}>AVG LATENCY</div>
                  </div>
                </div>
              )}

              {/* Setup Instructions */}
              <div style={{
                padding: '10px 12px', borderRadius: 8,
                background: '#050507', border: '1px solid rgba(139,92,246,0.1)',
                fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: '#5A5468',
                lineHeight: '1.8',
              }} data-testid="voice-setup-instructions">
                <div style={{ color: '#8B5CF6', fontWeight: 700, marginBottom: 4 }}>LEGION SETUP:</div>
                <div>1. Record 6s voice sample → save as <span style={{ color: '#C9A84C' }}>ora_voice.wav</span></div>
                <div>2. <span style={{ color: '#C9A84C' }}>python tts_server.py</span> (starts XTTS on port 5002)</div>
                <div>3. <span style={{ color: '#C9A84C' }}>ngrok http 5002</span> (tunnel for cloud access)</div>
                <div>4. Set <span style={{ color: '#C9A84C' }}>XTTS_STREAMING_CHUNK_SIZE=16</span> for low latency</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
