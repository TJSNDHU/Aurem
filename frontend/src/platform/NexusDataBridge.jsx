/**
 * AUREM Nexus Data Bridge — "Autonomous Executive" Data Infrastructure
 * Shopify Sync + Customer Vault + Enrichment + Attribution Proof
 * 
 * UI: Liquid Glassmorphism / Copper Wireframe / Scientific-Luxe
 */

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import {
  Database, Link2, ShoppingBag, Users, Search, Shield,
  ArrowRight, Loader2, CheckCircle, AlertTriangle, RefreshCw,
  Zap, Globe, TrendingUp, Lock, Eye, ChevronRight,
  Sparkles, Clock, DollarSign, Mail, Phone, Linkedin,
  Building2, UserPlus, Download, Filter, BarChart3,
  ExternalLink, XCircle, Activity
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ═══════════════════════════════════════════════════════════════ */
/* ═══ COPPER HELIX ANIMATION ═══ */
/* ═══════════════════════════════════════════════════════════════ */
const CopperHelix = ({ progress, syncing }) => {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const frameRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = 200;
    const h = canvas.height = 200;

    const draw = () => {
      frameRef.current += 0.02;
      ctx.clearRect(0, 0, w, h);

      const strands = 2;
      const points = 60;
      const amplitude = 40;
      const centerX = w / 2;
      const centerY = h / 2;

      for (let s = 0; s < strands; s++) {
        const offset = (s * Math.PI);
        ctx.beginPath();
        for (let i = 0; i < points; i++) {
          const t = (i / points) * Math.PI * 4 + frameRef.current;
          const x = centerX + Math.cos(t + offset) * amplitude;
          const y = 20 + (i / points) * (h - 40);

          const glow = syncing ? 0.4 + (progress / 100) * 0.6 : 0.2;
          const filled = i / points <= progress / 100;

          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);

          if (filled && i % 4 === 0) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(x, y, 2.5, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(212, 175, 55, ${glow})`;
            ctx.shadowColor = '#D4AF37';
            ctx.shadowBlur = syncing ? 8 : 2;
            ctx.fill();
            ctx.restore();
          }
        }
        ctx.strokeStyle = `rgba(184, 135, 89, ${syncing ? 0.5 : 0.15})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Cross-links
      for (let i = 0; i < points; i += 6) {
        const t = (i / points) * Math.PI * 4 + frameRef.current;
        const x1 = centerX + Math.cos(t) * amplitude;
        const x2 = centerX + Math.cos(t + Math.PI) * amplitude;
        const y = 20 + (i / points) * (h - 40);
        const filled = i / points <= progress / 100;

        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.strokeStyle = filled
          ? `rgba(212, 175, 55, ${syncing ? 0.4 : 0.1})`
          : 'rgba(100,100,100,0.05)';
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }

      if (syncing) {
        animRef.current = requestAnimationFrame(draw);
      }
    };

    draw();
    if (syncing) animRef.current = requestAnimationFrame(draw);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [progress, syncing]);

  return <canvas ref={canvasRef} width={200} height={200} className="mx-auto" />;
};

/* ═══════════════════════════════════════════════════════════════ */
/* ═══ ATTRIBUTION TIMELINE ═══ */
/* ═══════════════════════════════════════════════════════════════ */
const AttributionTimeline = ({ sale }) => {
  const chain = sale?.attribution_chain || {};
  const steps = [
    { label: 'Link Created', time: chain.link_created, icon: Link2, color: '#D4AF37' },
    { label: 'Link Clicked', time: chain.link_clicked, icon: Eye, color: '#64C8FF' },
    { label: 'Order Paid', time: chain.order_paid, icon: DollarSign, color: '#4ade80' },
  ];

  return (
    <div className="flex items-center gap-1 w-full" data-testid={`timeline-${sale?.sale_id}`}>
      {steps.map((step, i) => {
        const StepIcon = step.icon;
        const active = !!step.time;
        return (
          <React.Fragment key={i}>
            <div className={`flex flex-col items-center ${active ? '' : 'opacity-30'}`}>
              <div className="w-8 h-8 rounded-full flex items-center justify-center transition-all"
                style={{ background: active ? `${step.color}20` : 'rgba(100,100,100,0.05)', border: `1.5px solid ${active ? step.color : 'rgba(100,100,100,0.1)'}` }}>
                <StepIcon className="w-3.5 h-3.5" style={{ color: active ? step.color : '#888' }} />
              </div>
              <span className="text-[7px] mt-1 text-center" style={{ color: active ? step.color : '#888' }}>
                {step.label}
              </span>
              {step.time && (
                <span className="text-[6px] text-[#888]">
                  {new Date(step.time).toLocaleDateString()}
                </span>
              )}
            </div>
            {i < steps.length - 1 && (
              <div className="flex-1 h-px mx-1" style={{
                background: active && steps[i + 1]?.time
                  ? `linear-gradient(90deg, ${step.color}, ${steps[i + 1].color})`
                  : 'rgba(100,100,100,0.1)',
                boxShadow: active && steps[i + 1]?.time ? `0 0 4px ${step.color}40` : 'none'
              }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════ */
/* ═══ CUSTOMER ROW ═══ */
/* ═══════════════════════════════════════════════════════════════ */
const CustomerRow = ({ customer, onEnrich }) => {
  const enriched = customer.enrichment_status === 'enriched';
  const ed = customer.enriched_data?.person || {};

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-white/40 transition-all group border border-transparent hover:border-[#D4AF37]/10"
      data-testid={`customer-${customer.customer_id}`}>
      <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold"
        style={{ background: enriched ? 'rgba(74,222,128,0.1)' : 'rgba(212,175,55,0.1)', color: enriched ? '#4ade80' : '#D4AF37' }}>
        {(customer.first_name?.[0] || customer.email?.[0] || '?').toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-[#1A1A2E] truncate">
            {customer.first_name} {customer.last_name}
          </span>
          {enriched && <CheckCircle className="w-3 h-3 text-[#4ade80] flex-shrink-0" />}
          {customer.source === 'shopify_sync' && <ShoppingBag className="w-3 h-3 text-[#8B5CF6] flex-shrink-0" />}
          {customer.source === 'web_scrape' && <Globe className="w-3 h-3 text-[#64C8FF] flex-shrink-0" />}
        </div>
        <div className="text-[10px] text-[#888] truncate">{customer.email}</div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="text-[10px] font-bold text-[#1A1A2E]">${(customer.total_spend || 0).toFixed(2)}</div>
        {customer.company && <div className="text-[8px] text-[#888] truncate max-w-[100px]">{customer.company}</div>}
      </div>
      {!enriched && (
        <button onClick={() => onEnrich(customer.customer_id)}
          className="opacity-0 group-hover:opacity-100 px-2 py-1 rounded text-[8px] font-bold transition-all"
          style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}
          data-testid={`enrich-${customer.customer_id}`}>
          <Sparkles className="w-3 h-3" />
        </button>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════ */
/* ═══ MAIN COMPONENT ═══ */
/* ═══════════════════════════════════════════════════════════════ */
const NexusDataBridge = ({ token }) => {
  const [tab, setTab] = useState('vault');  // vault | shopify | enrichment | attribution
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Vault
  const [customers, setCustomers] = useState([]);
  const [customerStats, setCustomerStats] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [totalCustomers, setTotalCustomers] = useState(0);

  // Shopify
  const [shopDomain, setShopDomain] = useState('');
  const [connections, setConnections] = useState([]);
  const [syncProgress, setSyncProgress] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [syncJobs, setSyncJobs] = useState([]);

  // Enrichment
  const [enrichStatus, setEnrichStatus] = useState(null);
  const [enriching, setEnriching] = useState(false);

  // Attribution
  const [attrSummary, setAttrSummary] = useState(null);
  const [attrSales, setAttrSales] = useState([]);

  // CRM
  const [crmType, setCrmType] = useState('hubspot');
  const [crmConnections, setCrmConnections] = useState([]);
  const [crmSyncing, setCrmSyncing] = useState(false);
  const [crmSyncResult, setCrmSyncResult] = useState(null);

  const headers = useMemo(() => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }), [token]);

  /* ─── Load Data ─── */
  const fetchCustomers = useCallback(async () => {
    try {
      const q = searchQuery ? `&search=${encodeURIComponent(searchQuery)}` : '';
      const res = await fetch(`${API_URL}/api/customers/list?limit=50${q}`, { headers });
      const data = await res.json();
      if (res.ok) {
        setCustomers(data.customers || []);
        setTotalCustomers(data.total || 0);
      }
    } catch (e) { console.error(e); }
  }, [searchQuery, headers]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/customers/stats/overview`, { headers });
      const data = await res.json();
      if (res.ok) setCustomerStats(data);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify/connections`, { headers });
      const data = await res.json();
      if (res.ok) setConnections(data.connections || []);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchSyncJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify/sync-jobs`, { headers });
      const data = await res.json();
      if (res.ok) setSyncJobs(data.sync_jobs || []);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchEnrichStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/enrichment/status`, { headers });
      const data = await res.json();
      if (res.ok) setEnrichStatus(data);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchAttribution = useCallback(async () => {
    try {
      const [summRes, salesRes] = await Promise.all([
        fetch(`${API_URL}/api/attribution/summary`, { headers }),
        fetch(`${API_URL}/api/attribution/sales`, { headers }),
      ]);
      const summData = await summRes.json();
      const salesData = await salesRes.json();
      if (summRes.ok) setAttrSummary(summData);
      if (salesRes.ok) setAttrSales(salesData.sales || []);
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchCrmConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/crm-sync/connections`, { headers });
      const data = await res.json();
      if (res.ok) setCrmConnections(data.connections || []);
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => {
    fetchCustomers();
    fetchStats();
    fetchConnections();
    fetchEnrichStatus();
    fetchAttribution();
    fetchSyncJobs();
    fetchCrmConnections();
  }, [fetchAttribution, fetchConnections, fetchCrmConnections, fetchCustomers, fetchEnrichStatus, fetchStats, fetchSyncJobs]);

  useEffect(() => {
    const t = setTimeout(fetchCustomers, 300);
    return () => clearTimeout(t);
  }, [fetchCustomers]);

  /* ─── Shopify Connect ─── */
  const handleShopifyConnect = useCallback(async () => {
    if (!shopDomain.trim()) { setError('Enter a Shopify store domain'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/shopify/connect`, {
        method: 'POST', headers, body: JSON.stringify({ shop_domain: shopDomain.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Connection failed');
      if (data.auth_url) window.location.href = data.auth_url;
      else {
        fetchConnections();
        setShopDomain('');
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [shopDomain, headers, fetchConnections]);

  /* ─── Shopify Sync ─── */
  const handleSync = useCallback(async (connectionId) => {
    setSyncing(true); setSyncProgress(0); setSyncResult(null); setError('');
    const interval = setInterval(() => {
      setSyncProgress(prev => Math.min(prev + Math.random() * 15, 95));
    }, 200);

    try {
      const res = await fetch(`${API_URL}/api/shopify/sync-customers`, {
        method: 'POST', headers,
        body: JSON.stringify({ connection_id: connectionId, use_mock: true, mock_count: 500 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Sync failed');
      setSyncProgress(100);
      setSyncResult(data);
      fetchCustomers();
      fetchStats();
      fetchSyncJobs();
    } catch (e) { setError(e.message); }
    finally {
      clearInterval(interval);
      setTimeout(() => setSyncing(false), 1500);
    }
  }, [headers, fetchCustomers, fetchStats, fetchSyncJobs]);

  /* ─── Enrichment ─── */
  const handleEnrichSingle = useCallback(async (customerId) => {
    try {
      const res = await fetch(`${API_URL}/api/enrichment/enrich-contact`, {
        method: 'POST', headers, body: JSON.stringify({ customer_id: customerId }),
      });
      if (res.ok) {
        fetchCustomers();
        fetchEnrichStatus();
      }
    } catch (e) { console.error(e); }
  }, [headers, fetchCustomers, fetchEnrichStatus]);

  const handleBulkEnrich = useCallback(async () => {
    setEnriching(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/enrichment/bulk-enrich`, {
        method: 'POST', headers, body: JSON.stringify({ limit: 50 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Bulk enrichment failed');
      fetchCustomers();
      fetchEnrichStatus();
    } catch (e) { setError(e.message); }
    finally { setEnriching(false); }
  }, [headers, fetchCustomers, fetchEnrichStatus]);

  /* ─── CRM Connect & Sync ─── */
  const handleCrmConnect = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/crm-sync/connect`, {
        method: 'POST', headers, body: JSON.stringify({ crm_type: crmType }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'CRM connection failed');
      fetchCrmConnections();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [crmType, headers, fetchCrmConnections]);

  const handleCrmSync = useCallback(async (connectionId) => {
    setCrmSyncing(true); setCrmSyncResult(null); setError('');
    try {
      const res = await fetch(`${API_URL}/api/crm-sync/sync-contacts`, {
        method: 'POST', headers, body: JSON.stringify({ connection_id: connectionId, mock_count: 200 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'CRM sync failed');
      setCrmSyncResult(data);
      fetchCustomers(); fetchStats(); fetchCrmConnections();
    } catch (e) { setError(e.message); }
    finally { setCrmSyncing(false); }
  }, [headers, fetchCrmConnections, fetchCustomers, fetchStats]);

  /* ═══════════════════════════════════════════════════════════ */
  /* ═══ RENDER ═══ */
  /* ═══════════════════════════════════════════════════════════ */
  const tabs = [
    { id: 'vault', label: 'Customer Vault', icon: Database },
    { id: 'shopify', label: 'Shopify Bridge', icon: ShoppingBag },
    { id: 'crm', label: 'CRM Connect', icon: Building2 },
    { id: 'enrichment', label: 'Enrichment', icon: Sparkles },
    { id: 'attribution', label: 'Attribution Proof', icon: Link2 },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }}>
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="mb-6" data-testid="nexus-data-bridge-header">
          <h1 className="text-xl font-bold text-[#1A1A2E] tracking-wider mb-1">Nexus Data Bridge</h1>
          <p className="text-xs text-[#888]">Autonomous Executive — Tenant-Isolated Customer Vault + Shopify Sync + Forensic Enrichment</p>
        </div>

        {/* Stats Bar */}
        {customerStats && (
          <div className="grid grid-cols-4 gap-3 mb-5" data-testid="vault-stats">
            {[
              { label: 'Total Customers', value: customerStats.total_customers, icon: Users, color: '#D4AF37' },
              { label: 'Enriched', value: customerStats.enriched_customers, icon: Sparkles, color: '#4ade80' },
              { label: 'Enrichment Rate', value: `${customerStats.enrichment_rate}%`, icon: BarChart3, color: '#64C8FF' },
              { label: 'Sources', value: Object.keys(customerStats.sources || {}).length, icon: Database, color: '#B88759' },
            ].map((stat, i) => {
              const Icon = stat.icon;
              return (
                <div key={i} className="p-3.5 rounded-xl border border-white/30 bg-white/50 backdrop-blur-sm hover:border-[#D4AF37]/20 transition-all"
                  style={{ transitionDelay: `${i * 0.15}s` }}>
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="w-3.5 h-3.5" style={{ color: stat.color }} />
                    <span className="text-[8px] text-[#888] uppercase tracking-wider font-bold">{stat.label}</span>
                  </div>
                  <div className="text-lg font-bold text-[#1A1A2E]">{stat.value}</div>
                </div>
              );
            })}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-5 p-1 rounded-xl bg-white/30 backdrop-blur-sm border border-white/20" data-testid="data-bridge-tabs">
          {tabs.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.id} onClick={() => setTab(t.id)}
                data-testid={`tab-${t.id}`}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold transition-all ${
                  tab === t.id ? 'text-white shadow-lg' : 'text-[#888] hover:text-[#1A1A2E] hover:bg-white/40'
                }`}
                style={tab === t.id ? { background: 'linear-gradient(135deg, #1C1712, #2A2318)' } : {}}>
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50/80 border border-red-200/50 rounded-lg text-red-600 text-sm flex items-center gap-2" data-testid="data-bridge-error">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />{error}
            <button onClick={() => setError('')} className="ml-auto"><XCircle className="w-4 h-4" /></button>
          </div>
        )}

        {/* ═══ TAB: CUSTOMER VAULT ═══ */}
        {tab === 'vault' && (
          <div data-testid="vault-tab">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888]" />
                <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search customers by email, name, or company..."
                  className="w-full pl-10 pr-4 py-2.5 bg-white/60 border border-[#FF6B00]/15 rounded-lg text-sm text-[#1A1A2E] placeholder-[#aaa] focus:outline-none focus:border-[#D4AF37] focus:ring-1 focus:ring-[#D4AF37]/20"
                  data-testid="customer-search" />
              </div>
              <button onClick={() => { fetchCustomers(); fetchStats(); }}
                className="p-2.5 rounded-lg border border-[#FF6B00]/15 bg-white/60 hover:bg-white/80 transition-all"
                data-testid="refresh-vault-btn">
                <RefreshCw className="w-4 h-4 text-[#888]" />
              </button>
            </div>

            {/* Privacy Shield Badge */}
            <div className="mb-3 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#4ade80]/5 border border-[#4ade80]/10 text-[9px] text-[#FF6B00] font-bold">
              <Shield className="w-3 h-3" />
              PRIVACY SHIELD ACTIVE — All contacts tagged with tenant_id + unsubscribe tokens + GDPR/CCPA compliance
            </div>

            <div className="rounded-xl border border-white/30 bg-white/40 backdrop-blur-sm overflow-hidden" data-testid="customer-list">
              <div className="px-3 py-2 border-b border-white/20 flex items-center gap-2 text-[9px] text-[#888] uppercase tracking-wider font-bold">
                <Users className="w-3 h-3" />
                {totalCustomers} customers in vault
              </div>
              <div className="max-h-[400px] overflow-y-auto divide-y divide-white/10">
                {customers.length > 0 ? customers.map(c => (
                  <CustomerRow key={c.customer_id} customer={c} onEnrich={handleEnrichSingle} />
                )) : (
                  <div className="p-8 text-center text-sm text-[#888]">
                    No customers yet. Connect Shopify or import manually.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ═══ TAB: SHOPIFY BRIDGE ═══ */}
        {tab === 'shopify' && (
          <div data-testid="shopify-tab">
            {/* Connect Store */}
            <div className="p-5 rounded-2xl border border-[#D4AF37]/15 bg-white/50 backdrop-blur-sm mb-5">
              <div className="flex items-center gap-2 mb-3">
                <ShoppingBag className="w-5 h-5 text-[#8B5CF6]" />
                <h3 className="text-sm font-bold text-[#1A1A2E] tracking-wider">CONNECT SHOPIFY STORE</h3>
              </div>
              <p className="text-[10px] text-[#888] mb-3">
                Connect your Shopify store to sync customers into the Aurem Intelligence Hub.
                Read-only sync — we never modify your store data.
              </p>
              <div className="flex gap-3">
                <input type="text" value={shopDomain} onChange={e => setShopDomain(e.target.value)}
                  placeholder="my-store.myshopify.com"
                  className="flex-1 px-4 py-2.5 bg-white/60 border border-[#8B5CF6]/20 rounded-lg text-sm text-[#1A1A2E] placeholder-[#aaa] focus:outline-none focus:border-[#D4AF37]"
                  data-testid="shopify-domain-input" />
                <button onClick={handleShopifyConnect} disabled={loading}
                  data-testid="shopify-connect-btn"
                  className="px-5 py-2.5 text-white rounded-lg font-bold text-sm hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
                  style={{ background: 'linear-gradient(135deg, #8B5CF6, #6D28D9)' }}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
                  Connect
                </button>
              </div>
            </div>

            {/* Active Connections */}
            {connections.length > 0 && (
              <div className="mb-5">
                <h4 className="text-[10px] text-[#888] uppercase tracking-wider font-bold mb-2">Active Connections</h4>
                <div className="space-y-2">
                  {connections.map(conn => (
                    <div key={conn.connection_id}
                      className="flex items-center justify-between p-3.5 rounded-xl border border-white/30 bg-white/50 backdrop-blur-sm"
                      data-testid={`connection-${conn.connection_id}`}>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(139,92,246,0.1)' }}>
                          <ShoppingBag className="w-5 h-5 text-[#8B5CF6]" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#1A1A2E]">{conn.shop_domain}</div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-[7px] px-1.5 py-0.5 rounded-full font-bold ${
                              conn.status === 'connected' ? 'bg-[#4ade80]/10 text-[#4ade80]' : 'bg-red-100 text-red-500'
                            }`}>
                              {conn.status?.toUpperCase()}
                            </span>
                            {conn.mode === 'mock' && (
                              <span className="text-[7px] px-1.5 py-0.5 rounded-full font-bold bg-[#D4AF37]/10 text-[#D4AF37]">MOCK</span>
                            )}
                          </div>
                        </div>
                      </div>
                      {conn.status === 'connected' && (
                        <button onClick={() => handleSync(conn.connection_id)}
                          disabled={syncing}
                          data-testid={`sync-btn-${conn.connection_id}`}
                          className="px-4 py-2 rounded-lg font-bold text-xs transition-all disabled:opacity-50 flex items-center gap-2 text-white"
                          style={{ background: 'linear-gradient(135deg, #D4AF37, #8B7355)' }}>
                          {syncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                          {syncing ? 'Syncing...' : 'Sync Customers'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Helix Sync Animation */}
            {syncing && (
              <div className="p-6 rounded-2xl border border-[#D4AF37]/20 bg-gradient-to-br from-[#1C1712] to-[#211D17] mb-5 text-center"
                data-testid="sync-helix">
                <CopperHelix progress={syncProgress} syncing={syncing} />
                <div className="text-[#D4AF37] font-bold text-sm mt-2">Syncing Customer DNA...</div>
                <div className="text-[#6B5744] text-[10px] mt-1">{Math.round(syncProgress)}% complete</div>
                <div className="mt-3 h-1 bg-[#2A2318] rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${syncProgress}%`, background: 'linear-gradient(90deg, #D4AF37, #4ade80)' }} />
                </div>
              </div>
            )}

            {/* Sync Result */}
            {syncResult && !syncing && (
              <div className="p-4 rounded-xl border border-[#4ade80]/20 bg-[#4ade80]/5 mb-5" data-testid="sync-result">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-[#4ade80]" />
                  <span className="text-sm font-bold text-[#FF6B00]">Sync Complete</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#1A1A2E]">{syncResult.customers_found}</div>
                    <div className="text-[8px] text-[#888] uppercase">Found</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#4ade80]">{syncResult.customers_imported}</div>
                    <div className="text-[8px] text-[#888] uppercase">Imported</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#888]">{syncResult.customers_skipped}</div>
                    <div className="text-[8px] text-[#888] uppercase">Skipped</div>
                  </div>
                </div>
              </div>
            )}

            {/* Sync History */}
            {syncJobs.length > 0 && (
              <div>
                <h4 className="text-[10px] text-[#888] uppercase tracking-wider font-bold mb-2">Sync History</h4>
                <div className="space-y-1.5">
                  {syncJobs.slice(0, 5).map(job => (
                    <div key={job.sync_id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/30 text-[10px]">
                      <div className="flex items-center gap-2">
                        <Activity className="w-3 h-3 text-[#888]" />
                        <span className="text-[#1A1A2E] font-bold">{job.shop_domain}</span>
                      </div>
                      <span className="text-[#4ade80]">+{job.customers_imported} imported</span>
                      <span className="text-[#888]">{new Date(job.started_at).toLocaleDateString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty State */}
            {connections.length === 0 && !syncing && (
              <div className="text-center py-12">
                <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: 'linear-gradient(135deg, rgba(139,92,246,0.2), rgba(212,175,55,0.2))' }}>
                  <ShoppingBag className="w-8 h-8 text-[#8B5CF6]" />
                </div>
                <h3 className="text-base font-bold text-[#1A1A2E] mb-1">No Stores Connected</h3>
                <p className="text-xs text-[#888] max-w-md mx-auto">
                  Connect your Shopify store to sync your customer database into the Aurem Intelligence Hub.
                  All data is tenant-isolated and GDPR compliant.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ═══ TAB: CRM CONNECT ═══ */}
        {tab === 'crm' && (
          <div data-testid="crm-tab">
            {/* Connect CRM */}
            <div className="p-5 rounded-2xl border border-[#0EA5E9]/15 bg-white/50 backdrop-blur-sm mb-5">
              <div className="flex items-center gap-2 mb-3">
                <Building2 className="w-5 h-5 text-[#0EA5E9]" />
                <h3 className="text-sm font-bold text-[#1A1A2E] tracking-wider">CONNECT YOUR CRM</h3>
              </div>
              <p className="text-[10px] text-[#888] mb-4">
                Sync contacts from HubSpot or Salesforce into the Aurem Intelligence Hub.
                All data is tenant-isolated with full GDPR compliance.
              </p>
              <div className="flex gap-3 mb-4">
                <button onClick={() => setCrmType('hubspot')} data-testid="crm-hubspot-btn"
                  className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border-2 text-sm font-bold transition-all ${
                    crmType === 'hubspot' ? 'border-[#FF7A59] bg-[#FF7A59]/5 text-[#FF7A59]' : 'border-white/30 text-[#888] hover:border-[#FF7A59]/30'
                  }`}>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M18.16 5.67v3.57c-.82-.32-1.72-.55-2.75-.55-3.2 0-5.79 2.59-5.79 5.79s2.59 5.79 5.79 5.79c1.03 0 1.93-.23 2.75-.55v3.57c-.85.29-1.77.46-2.75.46-4.97 0-9-4.03-9-9s4.03-9 9-9c.98 0 1.9.17 2.75.46z"/><circle cx="15.41" cy="14.48" r="2.41"/></svg>
                  HubSpot
                </button>
                <button onClick={() => setCrmType('salesforce')} data-testid="crm-salesforce-btn"
                  className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border-2 text-sm font-bold transition-all ${
                    crmType === 'salesforce' ? 'border-[#00A1E0] bg-[#00A1E0]/5 text-[#00A1E0]' : 'border-white/30 text-[#888] hover:border-[#00A1E0]/30'
                  }`}>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15H9v-2h2v2zm0-4H9V7h2v6zm4 4h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
                  Salesforce
                </button>
              </div>
              <button onClick={handleCrmConnect} disabled={loading} data-testid="crm-connect-btn"
                className="w-full px-5 py-2.5 text-white rounded-lg font-bold text-sm hover:opacity-90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                style={{ background: crmType === 'hubspot' ? 'linear-gradient(135deg, #FF7A59, #FF5C35)' : 'linear-gradient(135deg, #00A1E0, #0070D2)' }}>
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
                Connect {crmType === 'hubspot' ? 'HubSpot' : 'Salesforce'}
              </button>
            </div>

            {/* Active CRM Connections */}
            {crmConnections.filter(c => c.status === 'connected').length > 0 && (
              <div className="mb-5">
                <h4 className="text-[10px] text-[#888] uppercase tracking-wider font-bold mb-2">Active CRM Connections</h4>
                <div className="space-y-2">
                  {crmConnections.filter(c => c.status === 'connected').map(conn => (
                    <div key={conn.connection_id}
                      className="flex items-center justify-between p-3.5 rounded-xl border border-white/30 bg-white/50 backdrop-blur-sm"
                      data-testid={`crm-connection-${conn.connection_id}`}>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                          style={{ background: conn.crm_type === 'hubspot' ? 'rgba(255,122,89,0.1)' : 'rgba(0,161,224,0.1)' }}>
                          <Building2 className="w-5 h-5" style={{ color: conn.crm_type === 'hubspot' ? '#FF7A59' : '#00A1E0' }} />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-[#1A1A2E]">
                            {conn.crm_type === 'hubspot' ? 'HubSpot' : 'Salesforce'} CRM
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[7px] px-1.5 py-0.5 rounded-full font-bold bg-[#4ade80]/10 text-[#4ade80]">CONNECTED</span>
                            {conn.mode === 'mock' && (
                              <span className="text-[7px] px-1.5 py-0.5 rounded-full font-bold bg-[#D4AF37]/10 text-[#D4AF37]">MOCK</span>
                            )}
                            {conn.contacts_synced > 0 && (
                              <span className="text-[8px] text-[#888]">{conn.contacts_synced} synced</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <button onClick={() => handleCrmSync(conn.connection_id)}
                        disabled={crmSyncing}
                        data-testid={`crm-sync-btn-${conn.connection_id}`}
                        className="px-4 py-2 rounded-lg font-bold text-xs transition-all disabled:opacity-50 flex items-center gap-2 text-white"
                        style={{ background: conn.crm_type === 'hubspot' ? 'linear-gradient(135deg, #FF7A59, #FF5C35)' : 'linear-gradient(135deg, #00A1E0, #0070D2)' }}>
                        {crmSyncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                        {crmSyncing ? 'Syncing...' : 'Sync Contacts'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* CRM Sync Result */}
            {crmSyncResult && (
              <div className="p-4 rounded-xl border border-[#4ade80]/20 bg-[#4ade80]/5 mb-5" data-testid="crm-sync-result">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-[#4ade80]" />
                  <span className="text-sm font-bold text-[#FF6B00]">CRM Sync Complete</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#1A1A2E]">{crmSyncResult.contacts_found}</div>
                    <div className="text-[8px] text-[#888] uppercase">Found</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#4ade80]">{crmSyncResult.contacts_imported}</div>
                    <div className="text-[8px] text-[#888] uppercase">Imported</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-bold text-[#888]">{crmSyncResult.contacts_skipped}</div>
                    <div className="text-[8px] text-[#888] uppercase">Skipped</div>
                  </div>
                </div>
              </div>
            )}

            {/* Empty State */}
            {crmConnections.filter(c => c.status === 'connected').length === 0 && (
              <div className="text-center py-12">
                <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: 'linear-gradient(135deg, rgba(14,165,233,0.2), rgba(212,175,55,0.2))' }}>
                  <Building2 className="w-8 h-8 text-[#0EA5E9]" />
                </div>
                <h3 className="text-base font-bold text-[#1A1A2E] mb-1">No CRM Connected</h3>
                <p className="text-xs text-[#888] max-w-md mx-auto">
                  Connect HubSpot or Salesforce to sync your B2B contacts, deals, and pipeline data
                  into the Aurem Intelligence Hub. All data is tenant-isolated.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ═══ TAB: ENRICHMENT ═══ */}
        {tab === 'enrichment' && (
          <div data-testid="enrichment-tab">
            {enrichStatus && (
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div className="p-5 rounded-2xl border border-[#D4AF37]/15 bg-gradient-to-br from-[#1C1712] to-[#211D17]">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles className="w-4 h-4 text-[#D4AF37]" />
                    <span className="text-[9px] text-[#6B5744] uppercase tracking-wider font-bold">Enrichment Engine</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">{enrichStatus.enrichment_rate}%</div>
                  <div className="text-[10px] text-[#888]">{enrichStatus.enriched} of {enrichStatus.total_customers} contacts enriched</div>
                  <div className="mt-3 h-1.5 bg-[#2A2318] rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{
                      width: `${enrichStatus.enrichment_rate}%`,
                      background: 'linear-gradient(90deg, #D4AF37, #4ade80)'
                    }} />
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-[7px] px-1.5 py-0.5 rounded-full font-bold bg-[#D4AF37]/10 text-[#D4AF37]">
                      {enrichStatus.mode?.toUpperCase()}
                    </span>
                    <span className="text-[8px] text-[#6B5744]">{enrichStatus.pending} pending</span>
                  </div>
                </div>

                <div className="p-5 rounded-2xl border border-white/20 bg-white/50 backdrop-blur-sm flex flex-col items-center justify-center">
                  <Sparkles className="w-8 h-8 text-[#D4AF37] mb-2" />
                  <h4 className="text-sm font-bold text-[#1A1A2E] mb-1">Apollo.io Forensic Miner</h4>
                  <p className="text-[9px] text-[#888] text-center mb-3">Auto-find emails, LinkedIn profiles, phone numbers, and company data</p>
                  <button onClick={handleBulkEnrich} disabled={enriching || enrichStatus.pending === 0}
                    data-testid="bulk-enrich-btn"
                    className="px-5 py-2.5 rounded-lg font-bold text-sm text-white transition-all disabled:opacity-50 flex items-center gap-2"
                    style={{ background: 'linear-gradient(135deg, #D4AF37, #B88759)' }}>
                    {enriching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    {enriching ? 'Enriching...' : `Enrich ${enrichStatus.pending} Contacts`}
                  </button>
                </div>
              </div>
            )}

            {/* Enriched Customer Preview */}
            <div className="rounded-xl border border-white/30 bg-white/40 backdrop-blur-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-white/20 flex items-center justify-between">
                <span className="text-[9px] text-[#888] uppercase tracking-wider font-bold flex items-center gap-2">
                  <Sparkles className="w-3 h-3 text-[#D4AF37]" />Recently Enriched
                </span>
              </div>
              <div className="max-h-[350px] overflow-y-auto divide-y divide-white/10">
                {customers.filter(c => c.enrichment_status === 'enriched').slice(0, 20).map(c => {
                  const person = c.enriched_data?.person || {};
                  const company = c.enriched_data?.company || {};
                  return (
                    <div key={c.customer_id} className="p-3 hover:bg-white/30 transition-all">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold bg-[#4ade80]/10 text-[#4ade80]">
                          {(c.first_name?.[0] || '?').toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-bold text-[#1A1A2E]">{c.first_name} {c.last_name}</div>
                          <div className="text-[9px] text-[#888]">{person.title} at {company.name}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          {person.linkedin_url && (
                            <a href={person.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-[#0A66C2] hover:opacity-70">
                              <Linkedin className="w-3.5 h-3.5" />
                            </a>
                          )}
                          {c.phone && <Phone className="w-3 h-3 text-[#888]" />}
                          <Mail className="w-3 h-3 text-[#888]" />
                        </div>
                        <div className="text-[8px] px-1.5 py-0.5 rounded-full font-bold bg-[#4ade80]/10 text-[#4ade80]">
                          {Math.round((c.enriched_data?.confidence_score || 0) * 100)}%
                        </div>
                      </div>
                    </div>
                  );
                })}
                {customers.filter(c => c.enrichment_status === 'enriched').length === 0 && (
                  <div className="p-8 text-center text-sm text-[#888]">
                    No enriched contacts yet. Click "Enrich" to start.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ═══ TAB: ATTRIBUTION PROOF ═══ */}
        {tab === 'attribution' && (
          <div data-testid="attribution-tab">
            {/* Summary Cards */}
            {attrSummary && (
              <div className="grid grid-cols-3 gap-3 mb-5">
                {[
                  { label: 'Links Sent', value: attrSummary.total_links_sent, icon: Link2, color: '#D4AF37' },
                  { label: 'Conversions', value: attrSummary.total_conversions, icon: CheckCircle, color: '#4ade80' },
                  { label: 'Commission Earned', value: `$${attrSummary.total_commission_earned}`, icon: DollarSign, color: '#64C8FF' },
                ].map((card, i) => {
                  const Icon = card.icon;
                  return (
                    <div key={i} className="p-4 rounded-xl border border-white/30 bg-white/50 backdrop-blur-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-3.5 h-3.5" style={{ color: card.color }} />
                        <span className="text-[8px] text-[#888] uppercase tracking-wider font-bold">{card.label}</span>
                      </div>
                      <div className="text-xl font-bold text-[#1A1A2E]">{card.value}</div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Attribution Info */}
            <div className="p-4 rounded-xl border border-[#D4AF37]/15 bg-[#D4AF37]/5 mb-5">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-[#D4AF37]" />
                <span className="text-xs font-bold text-[#1A1A2E]">Signed Token Attribution</span>
              </div>
              <p className="text-[10px] text-[#888]">
                Every recovery link carries a signed <span className="font-bold text-[#D4AF37]">aurem_ref</span> token (HMAC-SHA256, 30-day window).
                When a sale is confirmed, the system verifies the token signature, matches the attribution chain, and bills a commission.
                No "ghost" commissions — every charge has forensic proof.
              </p>
            </div>

            {/* Sales Timeline */}
            <div className="rounded-xl border border-white/30 bg-white/40 backdrop-blur-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-white/20 text-[9px] text-[#888] uppercase tracking-wider font-bold flex items-center gap-2">
                <TrendingUp className="w-3 h-3 text-[#4ade80]" />
                Attribution Timeline — Scan / Nudge / Sale
              </div>
              <div className="max-h-[400px] overflow-y-auto divide-y divide-white/10">
                {attrSales.length > 0 ? attrSales.map(sale => (
                  <div key={sale.sale_id} className="p-4 hover:bg-white/30 transition-all">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="text-xs font-bold text-[#1A1A2E]">Order #{sale.order_id}</div>
                        <div className="text-[9px] text-[#888]">{sale.order_email} via {sale.channel}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-bold text-[#4ade80]">+${sale.commission_amount}</div>
                        <div className="text-[8px] text-[#888]">of ${sale.order_total} sale</div>
                      </div>
                    </div>
                    <AttributionTimeline sale={sale} />
                  </div>
                )) : (
                  <div className="p-8 text-center text-sm text-[#888]">
                    No attributed sales yet. Create tracking links via the Comm Hub to start tracking conversions.
                  </div>
                )}
              </div>
            </div>

            {/* Channel Breakdown */}
            {attrSummary?.channel_breakdown && Object.keys(attrSummary.channel_breakdown).length > 0 && (
              <div className="mt-5 p-4 rounded-xl border border-white/30 bg-white/40 backdrop-blur-sm">
                <h4 className="text-[10px] text-[#888] uppercase tracking-wider font-bold mb-3 flex items-center gap-2">
                  <BarChart3 className="w-3 h-3" />Channel Performance
                </h4>
                <div className="space-y-2">
                  {Object.entries(attrSummary.channel_breakdown).map(([ch, stats]) => (
                    <div key={ch} className="flex items-center gap-3">
                      <span className="text-[10px] font-bold text-[#1A1A2E] w-16">{ch}</span>
                      <div className="flex-1 h-1.5 bg-[#f0f0f0] rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{
                          width: `${Math.max(5, (stats.converted / Math.max(stats.sent, 1)) * 100)}%`,
                          background: 'linear-gradient(90deg, #D4AF37, #4ade80)'
                        }} />
                      </div>
                      <span className="text-[9px] text-[#888]">{stats.sent} sent / {stats.converted} conv</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};

export default NexusDataBridge;
