/**
 * AUREM Shopify App Manager — Enhanced Onboarding + 3-Pillar War Room
 * 
 * Tabs:
 * 1. War Room — Connection pulse, sync status, pillar toggles
 * 2. ORA Pixel — Event analytics from Web Pixel
 * 3. Store Connect — Install flow + store management
 * 4. Compliance — GDPR webhooks + ADMT disclosure
 * 5. Extensions — Theme extension code + deployment guide
 */
import React, { useState, useCallback, useEffect, useMemo, useRef, Suspense, lazy } from 'react';
import {
  ShoppingBag, Shield, Code, Check, Copy, RefreshCw,
  AlertTriangle, Loader2, ExternalLink, Eye, Lock, Zap,
  Globe, Download, Settings, CheckCircle, XCircle, Activity,
  Terminal, Wifi, WifiOff, Radio, MessageSquare, BarChart3,
  Package, ArrowUpRight, Mic, Brain, Layers, Heart, Wrench,
  CreditCard, DollarSign, TrendingUp
} from 'lucide-react';
// Lazy-loaded — Three.js bundle (~600KB) only loads when the Pulse helix
// view is actually rendered. Cuts initial JS shipped to non-Shopify pages.
const ForensicMinerHelix = lazy(() => import('./ForensicMinerHelix'));

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const ShopifyAppManager = ({ token }) => {
  const [tab, setTab] = useState('warroom');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // War Room
  const [syncStatus, setSyncStatus] = useState(null);
  const [connections, setConnections] = useState([]);
  const [selectedShop, setSelectedShop] = useState(null);
  const [shopStatus, setShopStatus] = useState(null);

  // Pixel Analytics
  const [pixelData, setPixelData] = useState(null);
  const [pixelDays, setPixelDays] = useState(7);

  // Store Connect
  const [shopDomain, setShopDomain] = useState('');
  const [installResult, setInstallResult] = useState(null);

  // Compliance
  const [complianceStatus, setComplianceStatus] = useState(null);
  const [storeName, setStoreName] = useState('');
  const [storeUrl, setStoreUrl] = useState('');
  const [snippet, setSnippet] = useState('');
  const [snippetCopied, setSnippetCopied] = useState(false);

  // Listing
  const [listingContent, setListingContent] = useState(null);
  const [submissionChecklist, setSubmissionChecklist] = useState(null);

  // Billing
  const [billingPlans, setBillingPlans] = useState([]);

  // Pulse Scanner
  const [pulseData, setPulseData] = useState(null);
  const [pulseLoading, setPulseLoading] = useState(false);
  const [fixLog, setFixLog] = useState([]);
  const [fixing, setFixing] = useState(false);

  // Recovery Stats
  const [recoveryStats, setRecoveryStats] = useState(null);
  const [recoveryHistory, setRecoveryHistory] = useState([]);

  // AURA Chat
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Forensic Miner
  const [minerNiche, setMinerNiche] = useState('skincare');
  const [minerLimit, setMinerLimit] = useState(5);
  const [minerResults, setMinerResults] = useState(null);
  const [minerLoading, setMinerLoading] = useState(false);
  const [minerHistory, setMinerHistory] = useState([]);
  const [outreachQueue, setOutreachQueue] = useState({});
  const [queuingDomain, setQueuingDomain] = useState(null);
  const [minerView, setMinerView] = useState('helix');

  const headers = useMemo(() => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }), [token]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify-app/sync/status`, { headers });
      if (res.ok) setSyncStatus(await res.json());
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify-app/connections`, { headers });
      if (res.ok) {
        const d = await res.json();
        setConnections(d.connections || []);
      }
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchPixelAnalytics = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify-app/pixel/analytics?days=${pixelDays}`, { headers });
      if (res.ok) setPixelData(await res.json());
    } catch (e) { console.error(e); }
  }, [pixelDays, headers]);

  const fetchCompliance = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify-app/compliance/status`, { headers });
      if (res.ok) setComplianceStatus(await res.json());
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchShopStatus = useCallback(async (domain) => {
    try {
      const res = await fetch(`${API_URL}/api/shopify-app/connections/${encodeURIComponent(domain)}/status`, { headers });
      if (res.ok) setShopStatus(await res.json());
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => {
    fetchSyncStatus();
    fetchConnections();
    fetchPixelAnalytics();
    fetchCompliance();
  }, [fetchConnections, fetchPixelAnalytics, fetchCompliance, fetchSyncStatus]);

  useEffect(() => { fetchPixelAnalytics(); }, [pixelDays]);
  useEffect(() => { if (tab === 'pulse' && !pulseData) fetchPulseScan(); }, [tab]);
  useEffect(() => { if (tab === 'recovery' || tab === 'billing') fetchRecoveryStats(); }, [tab]);

  const fetchPulseScan = async (shop) => {
    setPulseLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/shopify/pulse/scan`, { method: 'POST', headers, body: JSON.stringify({ shop: shop || selectedShop || 'demo-store' }) });
      if (res.ok) setPulseData(await res.json());
    } catch (e) { console.error(e); }
    setPulseLoading(false);
  };

  const fetchRecoveryStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/shopify/pulse/recovery/stats`, { headers });
      if (res.ok) setRecoveryStats(await res.json());
    } catch (e) { console.error(e); }
  };

  const runAltTextFix = async () => {
    setFixing(true);
    setFixLog([]);
    try {
      const res = await fetch(`${API_URL}/api/shopify/pulse/fix/alt-text`, { method: 'POST', headers, body: JSON.stringify({ shop: selectedShop || 'demo-store' }) });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const evt = JSON.parse(line.slice(6));
              setFixLog(prev => [...prev, evt]);
            } catch {}
          }
        }
      }
    } catch (e) { setFixLog(prev => [...prev, { type: 'error', message: String(e) }]); }
    setFixing(false);
  };

  const sendAuraChat = async () => {
    if (!chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setChatLoading(true);
    try {
      const context = `Shop: ${selectedShop || 'demo'}. Health: ${pulseData?.health_score || 'unknown'}. Revenue at risk: $${pulseData?.revenue_at_risk_monthly || 0}. Recovered: ${recoveryStats?.recovered || 0}.`;
      const res = await fetch(`${API_URL}/api/ai/chat`, { method: 'POST', headers, body: JSON.stringify({ message: `[Shopify Store Context: ${context}] ${userMsg}`, session_id: 'shopify-aura' }) });
      if (res.ok) {
        const d = await res.json();
        setChatMessages(prev => [...prev, { role: 'aura', text: d.response || d.message || 'No response' }]);
      }
    } catch (e) { setChatMessages(prev => [...prev, { role: 'aura', text: 'Connection error — try again.' }]); }
    setChatLoading(false);
  };

  const handleConnect = async () => {
    if (!shopDomain.trim()) { setError('Enter shop domain'); return; }
    setLoading(true); setError('');
    try {
      const domain = shopDomain.includes('.myshopify.com') ? shopDomain.trim() : `${shopDomain.trim()}.myshopify.com`;
      const res = await fetch(`${API_URL}/api/shopify-app/connections`, {
        method: 'POST', headers, body: JSON.stringify({ shop_domain: domain })
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || 'Connection failed');
      setInstallResult(d);
      setShopDomain('');
      fetchConnections();
      fetchSyncStatus();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleGenerateSnippet = async () => {
    if (!storeName.trim()) { setError('Enter store name'); return; }
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/shopify-app/compliance/generate-snippet`, {
        method: 'POST', headers, body: JSON.stringify({ store_name: storeName.trim(), store_url: storeUrl.trim() })
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || 'Failed');
      setSnippet(d.snippet_html || '');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const PillarStatus = ({ name, icon: Icon, active, color, desc }) => (
    <div className="flex items-center gap-3 py-3" data-testid={`pillar-${name.toLowerCase()}`}>
      <div className="size-9 rounded-xl flex items-center justify-center" style={{ background: `${color}15` }}>
        <Icon size={16} style={{ color }} />
      </div>
      <div className="flex-1">
        <div className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{name}</div>
        <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{desc}</div>
      </div>
      <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/5 text-[#666]'}`}>
        <span className={`size-1.5 rounded-full ${active ? 'bg-emerald-400' : 'bg-[#555]'}`} style={active ? { boxShadow: '0 0 6px #4ade80' } : {}} />
        {active ? 'ACTIVE' : 'STANDBY'}
      </div>
    </div>
  );

  const StatCard = ({ label, value, icon: Icon, color }) => (
    <div className="aurem-glass-card p-4 rounded-xl">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} style={{ color }} />
        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>{label}</span>
      </div>
      <div className="text-xl font-black" style={{ color: 'var(--aurem-text)' }}>{typeof value === 'number' ? value.toLocaleString() : value}</div>
    </div>
  );

  const runMinerScan = useCallback(async () => {
    setMinerLoading(true); setMinerResults(null);
    try {
      const res = await fetch(`${API_URL}/api/forensic-miner/scan`, { method: 'POST', headers, body: JSON.stringify({ niche: minerNiche, limit: minerLimit, auto_outreach: false }) });
      if (res.ok) setMinerResults(await res.json());
      else setError('Miner scan failed');
    } catch (e) { setError(e.message); }
    setMinerLoading(false);
  }, [minerNiche, minerLimit, headers]);

  const fetchMinerHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/forensic-miner/history?limit=5`, { headers });
      if (res.ok) { const d = await res.json(); setMinerHistory(d.scans || []); }
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => { if (tab === 'miner') fetchMinerHistory(); }, [tab]);

  const queueOutreach = useCallback(async (store) => {
    setQueuingDomain(store.domain);
    try {
      const res = await fetch(`${API_URL}/api/forensic-miner/queue-outreach`, {
        method: 'POST', headers,
        body: JSON.stringify({
          domain: store.domain,
          email: store.emails?.[0]?.email || '',
          phone: store.phones?.[0] || '',
          health_score: store.score || 0,
          issues: store.issues || [],
          scan_id: minerResults?.scan_id || '',
        }),
      });
      if (res.ok) {
        const d = await res.json();
        setOutreachQueue(prev => ({ ...prev, [store.domain]: d.status || 'queued' }));
      } else { setError('Failed to queue outreach'); }
    } catch (e) { setError(e.message); }
    setQueuingDomain(null);
  }, [headers, minerResults]);

  const getStoreStatus = useCallback((store) => {
    if (outreachQueue[store.domain]) return 'outreach_sent';
    if (store.emails?.length > 0) return 'email_found';
    return 'scanned';
  }, [outreachQueue]);

  const tabs = [
    { id: 'warroom', label: 'War Room', icon: Radio },
    { id: 'pulse', label: 'Pulse', icon: Heart },
    { id: 'recovery', label: 'Recovery', icon: TrendingUp },
    { id: 'miner', label: 'Forensic Miner', icon: Wrench },
    { id: 'pixel', label: 'ORA Pixel', icon: Eye },
    { id: 'connect', label: 'Store Connect', icon: Globe },
    { id: 'compliance', label: 'Compliance', icon: Shield },
    { id: 'billing', label: 'Billing', icon: CreditCard },
    { id: 'aura', label: 'AURA Chat', icon: MessageSquare },
    { id: 'extensions', label: 'Extensions', icon: Layers },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'transparent' }} data-testid="shopify-app-manager">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black tracking-wider" style={{ color: 'var(--aurem-text)' }}>Shopify Command Center</h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>3-Pillar Storefront Integration: Pixel + Chat + Recommendations</p>
          </div>
          <button onClick={() => { fetchSyncStatus(); fetchConnections(); fetchPixelAnalytics(); }} className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold" style={{ background: '#FF6B0018', color: '#FF6B00' }} data-testid="refresh-shopify">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'rgba(128,128,128,0.1)' }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
              className={`flex items-center gap-1.5 flex-1 justify-center py-2.5 rounded-lg text-[11px] font-bold transition-all ${tab === t.id ? 'shadow-sm' : ''}`}
              style={{ background: tab === t.id ? 'var(--aurem-card, rgba(255,255,255,0.9))' : 'transparent', color: tab === t.id ? '#D4AF37' : 'var(--aurem-text-secondary)' }}>
              <t.icon size={13} /> {t.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="p-3 rounded-xl text-sm flex items-center gap-2" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
            <AlertTriangle size={14} />{error}
            <button onClick={() => setError('')} className="ml-auto"><XCircle size={14} /></button>
          </div>
        )}

        {/* ═══ WAR ROOM ═══ */}
        {tab === 'warroom' && (
          <div className="space-y-5">
            {/* Hardware Node Pulse */}
            <div className="aurem-glass-card p-5 rounded-2xl" data-testid="hardware-pulse">
              <div className="flex items-center gap-3 mb-4">
                <div className="relative">
                  <Wifi size={18} style={{ color: '#4ade80' }} />
                  <span className="absolute -top-0.5 -right-0.5 size-2.5 bg-emerald-400 rounded-full" style={{ boxShadow: '0 0 8px #4ade80', animation: 'pulse 2s infinite' }} />
                </div>
                <div>
                  <div className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-text)' }}>HARDWARE NODE</div>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{syncStatus?.hardware_node?.location || 'Local Node'} — {syncStatus?.hardware_node?.uptime || '99.97%'} uptime</div>
                </div>
                <div className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400">
                  <span className="size-2 rounded-full bg-emerald-400" style={{ boxShadow: '0 0 6px #4ade80' }} />
                  CONNECTED
                </div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <StatCard label="Stores" value={syncStatus?.connected_stores || 0} icon={ShoppingBag} color="#D4AF37" />
                <StatCard label="Products" value={syncStatus?.total_products_synced || 0} icon={Package} color="#8B5CF6" />
                <StatCard label="Pixel Events" value={syncStatus?.total_pixel_events || 0} icon={Eye} color="#3b82f6" />
                <StatCard label="Chats" value={syncStatus?.total_chat_sessions || 0} icon={MessageSquare} color="#FF6B00" />
              </div>
            </div>

            {/* 3 Pillars Status */}
            <div className="aurem-glass-card p-5 rounded-2xl" data-testid="pillars-status">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>3-PILLAR STATUS</h3>
              <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
                <PillarStatus name="ORA Pixel" icon={Eye} active={(syncStatus?.total_pixel_events || 0) > 0} color="#3b82f6" desc="Web Pixels API — Behavior tracking sandbox" />
                <PillarStatus name="ORA Chat" icon={Mic} active={(syncStatus?.total_chat_sessions || 0) > 0} color="#D4AF37" desc="App Embed Block — AI voice + text assistant" />
                <PillarStatus name="ORA Recs" icon={Brain} active={(syncStatus?.total_products_synced || 0) > 0} color="#8B5CF6" desc="App Block — AI product recommendations via App Proxy" />
              </div>
            </div>

            {/* Connected Stores */}
            {connections.length > 0 && (
              <div className="aurem-glass-card p-5 rounded-2xl" data-testid="connected-stores">
                <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>CONNECTED STORES</h3>
                <div className="space-y-2">
                  {connections.map(c => (
                    <button key={c.id} onClick={() => { setSelectedShop(c.shop_domain); fetchShopStatus(c.shop_domain); }}
                      className="w-full flex items-center gap-3 p-3 rounded-xl transition-all hover:bg-white/5"
                      style={{ border: selectedShop === c.shop_domain ? '1px solid #D4AF3744' : '1px solid rgba(128,128,128,0.1)' }}>
                      <Globe size={14} style={{ color: '#D4AF37' }} />
                      <span className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{c.shop_domain}</span>
                      <span className="ml-auto text-[10px] font-bold" style={{ color: c.status === 'active' ? '#4ade80' : '#888' }}>{c.status?.toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══ ORA PIXEL ═══ */}
        {tab === 'pixel' && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-black" style={{ color: 'var(--aurem-text)' }}>Pixel Analytics</h3>
              <div className="flex gap-1 ml-auto">
                {[7, 14, 30].map(d => (
                  <button key={d} onClick={() => setPixelDays(d)} className="px-3 py-1 rounded-lg text-[10px] font-bold transition-all"
                    style={{ background: pixelDays === d ? '#D4AF3720' : 'transparent', color: pixelDays === d ? '#D4AF37' : 'var(--aurem-text-secondary)' }}>{d}d</button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-4 gap-3">
              <StatCard label="Total Events" value={pixelData?.total_events || 0} icon={Activity} color="#3b82f6" />
              <StatCard label="Products Viewed" value={pixelData?.unique_products || 0} icon={Eye} color="#8B5CF6" />
              <StatCard label="Cart Value" value={`$${pixelData?.total_cart_value || 0}`} icon={ShoppingBag} color="#D4AF37" />
              <StatCard label="Checkouts" value={pixelData?.events_by_type?.checkout_completed || 0} icon={CheckCircle} color="#FF6B00" />
            </div>

            {/* Event Breakdown */}
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>EVENT BREAKDOWN</h3>
              <div className="space-y-2">
                {Object.entries(pixelData?.events_by_type || {}).sort(([,a],[,b]) => b - a).map(([type, count]) => {
                  const max = Math.max(...Object.values(pixelData?.events_by_type || { _: 1 }));
                  return (
                    <div key={type} className="flex items-center gap-3">
                      <span className="text-[10px] font-mono w-36 shrink-0" style={{ color: 'var(--aurem-text-secondary)' }}>{type}</span>
                      <div className="flex-1 h-5 rounded-lg overflow-hidden" style={{ background: 'rgba(128,128,128,0.1)' }}>
                        <div className="h-full rounded-lg" style={{ width: `${(count/max)*100}%`, background: '#D4AF37' }} />
                      </div>
                      <span className="text-xs font-bold w-12 text-right" style={{ color: 'var(--aurem-text)' }}>{count}</span>
                    </div>
                  );
                })}
                {Object.keys(pixelData?.events_by_type || {}).length === 0 && (
                  <div className="text-center py-6">
                    <Eye size={24} className="mx-auto mb-2" style={{ color: 'var(--aurem-text-secondary)', opacity: 0.4 }} />
                    <p className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>No pixel events yet. Deploy the ORA Pixel extension to start tracking.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Top Products */}
            {pixelData?.top_products?.length > 0 && (
              <div className="aurem-glass-card p-5 rounded-2xl">
                <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>TOP VIEWED PRODUCTS</h3>
                <div className="space-y-2">
                  {pixelData.top_products.map((p, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5">
                      <span className="text-[10px] font-black w-5" style={{ color: '#D4AF37' }}>#{i+1}</span>
                      <span className="text-xs flex-1" style={{ color: 'var(--aurem-text)' }}>{p.title}</span>
                      <span className="text-xs font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>{p.views} views</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}


        {/* ═══ PULSE SCANNER ═══ */}
        {tab === 'pulse' && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-black" style={{ color: 'var(--aurem-text)' }}>Store Health Scanner</h3>
              <button onClick={() => fetchPulseScan()} disabled={pulseLoading} className="ml-auto flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold" style={{ background: '#4ade8018', color: '#4ade80' }} data-testid="run-pulse-scan">
                {pulseLoading ? <Loader2 size={13} className="animate-spin" /> : <Heart size={13} />}
                {pulseLoading ? 'Scanning...' : 'Run Scan'}
              </button>
            </div>

            {pulseData && (
              <>
                {/* Score + Revenue at Risk */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="aurem-glass-card p-6 rounded-2xl text-center" data-testid="pulse-health-score">
                    <div className="relative size-28 mx-auto mb-3">
                      <svg viewBox="0 0 100 100" className="size-full -rotate-90">
                        <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(128,128,128,0.1)" strokeWidth="8" />
                        <circle cx="50" cy="50" r="42" fill="none" strokeWidth="8" strokeLinecap="round"
                          stroke={pulseData.health_score >= 80 ? '#4ade80' : pulseData.health_score >= 50 ? '#f59e0b' : '#ef4444'}
                          strokeDasharray={2 * Math.PI * 42} strokeDashoffset={2 * Math.PI * 42 * (1 - pulseData.health_score / 100)}
                          style={{ transition: 'stroke-dashoffset 1s ease' }} />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-3xl font-black" style={{ color: pulseData.health_score >= 80 ? '#4ade80' : pulseData.health_score >= 50 ? '#f59e0b' : '#ef4444' }}>{pulseData.health_score}</span>
                        <span className="text-[9px] tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>/100</span>
                      </div>
                    </div>
                    <p className="text-[10px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>HEALTH SCORE</p>
                  </div>
                  <div className="aurem-glass-card p-6 rounded-2xl text-center flex flex-col items-center justify-center" data-testid="pulse-revenue-risk">
                    <DollarSign size={28} style={{ color: '#D4AF37', marginBottom: 8 }} />
                    <p className="text-3xl font-black" style={{ color: '#D4AF37' }}>${pulseData.revenue_at_risk_monthly?.toLocaleString()}</p>
                    <p className="text-[10px] font-bold mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>MONTHLY REVENUE AT RISK</p>
                  </div>
                </div>

                {/* Issues List */}
                <div className="aurem-glass-card p-5 rounded-2xl" data-testid="pulse-issues">
                  <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>ISSUES FOUND</h3>
                  <div className="space-y-2">
                    {(pulseData.issues || []).map((issue, i) => (
                      <div key={i} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: issue.severity === 'high' ? 'rgba(239,68,68,0.06)' : issue.severity === 'medium' ? 'rgba(245,158,11,0.06)' : 'rgba(128,128,128,0.04)', border: `1px solid ${issue.severity === 'high' ? 'rgba(239,68,68,0.15)' : issue.severity === 'medium' ? 'rgba(245,158,11,0.15)' : 'rgba(128,128,128,0.1)'}` }}>
                        <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: issue.severity === 'high' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)' }}>
                          <AlertTriangle size={14} style={{ color: issue.severity === 'high' ? '#ef4444' : '#f59e0b' }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{issue.type?.replace(/_/g, ' ').toUpperCase()}</p>
                          <p className="text-[10px] truncate" style={{ color: 'var(--aurem-text-secondary)' }}>{issue.description}</p>
                        </div>
                        <span className="text-xs font-black" style={{ color: issue.severity === 'high' ? '#ef4444' : '#f59e0b' }}>{issue.count || issue.value}</span>
                        {issue.fix_available && (
                          <button onClick={runAltTextFix} disabled={fixing} className="px-3 py-1.5 rounded-lg text-[10px] font-bold flex items-center gap-1" style={{ background: '#4ade8015', color: '#4ade80', border: '1px solid rgba(74,222,128,0.2)' }} data-testid={`fix-btn-${i}`}>
                            <Wrench size={10} /> {fixing ? 'Fixing...' : 'Auto-Fix'}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Fix Log */}
                {fixLog.length > 0 && (
                  <div className="aurem-glass-card p-5 rounded-2xl" data-testid="fix-log">
                    <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>FIX LOG</h3>
                    <div className="p-3 rounded-xl font-mono text-[10px] max-h-64 overflow-auto space-y-1" style={{ background: 'rgba(10,10,20,0.8)', color: '#8B8B8B' }}>
                      {fixLog.map((evt, i) => (
                        <div key={i} style={{ color: evt.type === 'fix' ? '#4ade80' : evt.type === 'error' ? '#ef4444' : evt.type === 'complete' ? '#D4AF37' : '#8B8B8B' }}>
                          {evt.type === 'fix' && `[FIXED] ${evt.product} → "${evt.alt_text}"`}
                          {evt.type === 'error' && `[ERROR] ${evt.product}: ${evt.error}`}
                          {evt.type === 'complete' && `[DONE] Fixed ${evt.fixed}, Errors: ${evt.errors}`}
                          {evt.type === 'info' && `[INFO] ${evt.message}`}
                          {evt.type === 'start' && `[START] ${evt.message}`}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {pulseData.mode === 'scaffold' && (
                  <div className="p-3 rounded-xl text-[10px]" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)', color: '#f59e0b' }}>
                    <AlertTriangle size={12} className="inline mr-1" /> Simulated scan, connect a real Shopify store for live data.
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ═══ FORENSIC MINER ═══ */}
        {tab === 'miner' && (
          <div className="space-y-5" data-testid="forensic-miner-tab">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-black" style={{ color: 'var(--aurem-text)' }}>Forensic Miner</h3>
              <span className="text-[9px] px-2 py-0.5 rounded-full font-bold" style={{ background: '#D4AF3718', color: '#D4AF37' }}>Lead Discovery</span>
            </div>

            {/* Scan Controls */}
            <div className="aurem-glass-card p-4 space-y-3">
              <div className="flex gap-3 items-end">
                <div className="flex-1">
                  <label className="text-[10px] font-bold mb-1 block" style={{ color: 'var(--aurem-text-secondary)' }}>Niche</label>
                  <select value={minerNiche} onChange={e => setMinerNiche(e.target.value)} data-testid="miner-niche"
                    className="w-full px-3 py-2 rounded-lg text-xs" style={{ background: 'rgba(128,128,128,0.1)', color: 'var(--aurem-text)', border: '1px solid rgba(128,128,128,0.2)' }}>
                    {['beauty','skincare','fashion','health','fitness','food','tech','pets'].map(n => <option key={n} value={n}>{n.charAt(0).toUpperCase()+n.slice(1)}</option>)}
                  </select>
                </div>
                <div style={{ width: 80 }}>
                  <label className="text-[10px] font-bold mb-1 block" style={{ color: 'var(--aurem-text-secondary)' }}>Limit</label>
                  <input type="number" value={minerLimit} onChange={e => setMinerLimit(Math.min(50, Math.max(1, parseInt(e.target.value)||1)))} data-testid="miner-limit"
                    className="w-full px-3 py-2 rounded-lg text-xs" style={{ background: 'rgba(128,128,128,0.1)', color: 'var(--aurem-text)', border: '1px solid rgba(128,128,128,0.2)' }} />
                </div>
                <button onClick={runMinerScan} disabled={minerLoading} data-testid="miner-scan-btn"
                  className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold" style={{ background: minerLoading ? '#66666630' : '#D4AF3718', color: '#D4AF37' }}>
                  {minerLoading ? <Loader2 size={13} className="animate-spin" /> : <Wrench size={13} />}
                  {minerLoading ? 'Scanning...' : 'Scan Niche'}
                </button>
              </div>
            </div>

            {/* Results */}
            {minerResults && (
              <div className="space-y-3">
                <div className="grid grid-cols-4 gap-3">
                  {[
                    { label: 'Domains Found', val: minerResults.domains_found, color: '#3b82f6' },
                    { label: 'Stores Enriched', val: minerResults.stores_enriched, color: '#22c55e' },
                    { label: 'Emails Found', val: minerResults.emails_found, color: '#D4AF37' },
                    { label: 'Avg Health', val: `${minerResults.avg_health_score}/100`, color: '#f59e0b' },
                  ].map((m, i) => (
                    <div key={i} className="aurem-glass-card p-3 text-center">
                      <div className="text-lg font-black" style={{ color: m.color }}>{m.val}</div>
                      <div className="text-[9px] font-bold mt-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>{m.label}</div>
                    </div>
                  ))}
                </div>

                {/* View Toggle */}
                <div className="flex items-center gap-2">
                  <button onClick={() => setMinerView('helix')} data-testid="miner-view-helix"
                    className="px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all"
                    style={{ background: minerView === 'helix' ? '#B8733320' : 'transparent', color: minerView === 'helix' ? '#B87333' : 'var(--aurem-text-secondary)', border: `1px solid ${minerView === 'helix' ? '#B8733340' : 'rgba(128,128,128,0.15)'}` }}>
                    3D Helix
                  </button>
                  <button onClick={() => setMinerView('list')} data-testid="miner-view-list"
                    className="px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all"
                    style={{ background: minerView === 'list' ? '#D4AF3720' : 'transparent', color: minerView === 'list' ? '#D4AF37' : 'var(--aurem-text-secondary)', border: `1px solid ${minerView === 'list' ? '#D4AF3740' : 'rgba(128,128,128,0.15)'}` }}>
                    List View
                  </button>
                </div>

                {/* 3D Copper Helix */}
                {minerView === 'helix' && (
                  <Suspense fallback={
                    <div data-testid="forensic-helix-loading" style={{
                      minHeight: 460, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', color: '#7a7a7a', fontSize: 12,
                      fontFamily: 'monospace', letterSpacing: '0.08em',
                    }}>
                      ⬡ Loading 3D forensic helix…
                    </div>
                  }><ForensicMinerHelix
                    stores={minerResults.stores || []}
                    outreachStatus={outreachQueue}
                    onQueueOutreach={queueOutreach}
                    queuingDomain={queuingDomain}
                  /></Suspense>
                )}

                {/* Store List */}
                {minerView === 'list' && (
                <div className="space-y-2">
                  {minerResults.stores?.map((store, i) => {
                    const status = getStoreStatus(store);
                    const statusCfg = {
                      scanned: { label: 'Scanned', bg: '#3b82f618', color: '#3b82f6' },
                      email_found: { label: 'Email Found', bg: '#D4AF3718', color: '#D4AF37' },
                      outreach_sent: { label: 'Outreach Sent', bg: '#22c55e18', color: '#22c55e' },
                    }[status];
                    return (
                    <div key={i} className="aurem-glass-card p-3" data-testid={`miner-store-${i}`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Globe size={13} style={{ color: '#D4AF37' }} />
                          <span className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{store.domain}</span>
                          {store.organization && <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(128,128,128,0.1)', color: 'var(--aurem-text-secondary)' }}>{store.organization}</span>}
                          <span className="text-[8px] font-bold px-2 py-0.5 rounded-full" style={{ background: statusCfg.bg, color: statusCfg.color }} data-testid={`miner-status-${i}`}>{statusCfg.label}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: store.score >= 70 ? '#22c55e18' : store.score >= 40 ? '#f59e0b18' : '#ef444418', color: store.score >= 70 ? '#22c55e' : store.score >= 40 ? '#f59e0b' : '#ef4444' }}>
                            {store.score}/100
                          </div>
                          {status !== 'outreach_sent' && store.emails?.length > 0 && (
                            <button onClick={() => queueOutreach(store)} disabled={queuingDomain === store.domain}
                              data-testid={`queue-outreach-${i}`}
                              className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-[10px] font-bold transition-all hover:opacity-80"
                              style={{ background: '#D4AF3718', color: '#D4AF37', border: '1px solid #D4AF3730' }}>
                              {queuingDomain === store.domain ? <Loader2 size={10} className="animate-spin" /> : <MessageSquare size={10} />}
                              Queue Outreach
                            </button>
                          )}
                          {status === 'outreach_sent' && (
                            <span className="flex items-center gap-1 text-[10px] font-bold px-3 py-1 rounded-lg" style={{ background: '#22c55e18', color: '#22c55e' }}>
                              <CheckCircle size={10} /> Queued
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-3 text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>
                        {store.emails?.length > 0 && <span><strong>Emails:</strong> {store.emails.map(e => e.email).join(', ')}</span>}
                        {store.phones?.length > 0 && <span><strong>Phone:</strong> {store.phones[0]}</span>}
                        {Object.keys(store.social || {}).length > 0 && <span><strong>Social:</strong> {Object.entries(store.social).map(([k,v]) => `${k}: @${v}`).join(', ')}</span>}
                      </div>
                      {store.issues?.length > 0 && (
                        <div className="flex gap-1 mt-2 flex-wrap">
                          {store.issues.map((issue, j) => (
                            <span key={j} className="text-[8px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(239,68,68,0.08)', color: '#ef4444' }}>{issue.replace(/_/g, ' ')}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
                )}
              </div>
            )}

            {/* History */}
            {minerHistory.length > 0 && !minerResults && (
              <div className="aurem-glass-card p-4">
                <h4 className="text-[10px] font-bold mb-2" style={{ color: 'var(--aurem-text-secondary)' }}>RECENT SCANS</h4>
                {minerHistory.map((s, i) => (
                  <div key={i} className="flex justify-between py-1.5 text-[10px]" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}>
                    <span style={{ color: 'var(--aurem-text)' }}>{s.niche} ({s.zone || 'com'})</span>
                    <span style={{ color: 'var(--aurem-text-secondary)' }}>{s.stores_enriched} stores | avg {s.avg_health_score}/100</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ═══ RECOVERY ═══ */}
        {tab === 'recovery' && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-black" style={{ color: 'var(--aurem-text)' }}>Cart Recovery Dashboard</h3>
              <button onClick={fetchRecoveryStats} className="ml-auto flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold" style={{ background: '#D4AF3718', color: '#D4AF37' }} data-testid="refresh-recovery">
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="aurem-glass-card p-5 rounded-2xl text-center" data-testid="stat-abandoned">
                <ShoppingBag size={20} className="mx-auto mb-2" style={{ color: '#ef4444' }} />
                <p className="text-2xl font-black" style={{ color: '#ef4444' }}>{recoveryStats?.abandoned || 0}</p>
                <p className="text-[10px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>ABANDONED</p>
              </div>
              <div className="aurem-glass-card p-5 rounded-2xl text-center" data-testid="stat-recovered">
                <CheckCircle size={20} className="mx-auto mb-2" style={{ color: '#4ade80' }} />
                <p className="text-2xl font-black" style={{ color: '#4ade80' }}>{recoveryStats?.recovered || 0}</p>
                <p className="text-[10px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>RECOVERED</p>
              </div>
              <div className="aurem-glass-card p-5 rounded-2xl text-center" data-testid="stat-revenue">
                <DollarSign size={20} className="mx-auto mb-2" style={{ color: '#D4AF37' }} />
                <p className="text-2xl font-black" style={{ color: '#D4AF37' }}>${recoveryStats?.revenue_recovered || 0}</p>
                <p className="text-[10px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>REVENUE SAVED</p>
              </div>
            </div>

            <div className="aurem-glass-card p-5 rounded-2xl">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-text)' }}>COMMISSION EARNED</h3>
                <span className="text-xs font-bold px-3 py-1 rounded-full" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>$2 per recovery</span>
              </div>
              <p className="text-3xl font-black" style={{ color: '#D4AF37' }}>${recoveryStats?.commission_earned || '0.00'}</p>
              <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>Recovery rate: {recoveryStats?.recovery_rate || 0}%</p>
            </div>

            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>RECOVERY SEQUENCE</h3>
              <div className="space-y-2">
                {[
                  { time: 'Hour 1', channel: 'WhatsApp', icon: MessageSquare, color: '#4ade80', desc: 'Personalized message with cart items' },
                  { time: 'Hour 4', channel: 'Email', icon: Globe, color: '#3b82f6', desc: 'Branded recovery email with checkout link' },
                  { time: 'Hour 24', channel: 'SMS', icon: Zap, color: '#f59e0b', desc: 'Final SMS reminder with urgency' },
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: `${step.color}08`, border: `1px solid ${step.color}20` }}>
                    <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${step.color}15` }}>
                      <step.icon size={14} style={{ color: step.color }} />
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{step.time} — {step.channel}</p>
                      <p className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{step.desc}</p>
                    </div>
                    <CheckCircle size={14} style={{ color: step.color }} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ═══ AURA CHAT ═══ */}
        {tab === 'aura' && (
          <div className="space-y-4">
            <div className="aurem-glass-card rounded-2xl overflow-hidden flex flex-col" style={{ height: '500px' }}>
              <div className="p-4 flex items-center gap-3" style={{ borderBottom: '1px solid rgba(128,128,128,0.1)' }}>
                <div className="size-8 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #D4B977, #B19A5E)' }}>
                  <span className="text-xs font-black text-[#0A0A00]">A</span>
                </div>
                <div>
                  <p className="text-xs font-black" style={{ color: 'var(--aurem-text)' }}>AURA, Store Assistant</p>
                  <p className="text-[9px]" style={{ color: 'var(--aurem-text-secondary)' }}>Ask about your store's health, recovery, and revenue</p>
                </div>
              </div>

              <div className="flex-1 overflow-auto p-4 space-y-3" data-testid="aura-chat-messages">
                {chatMessages.length === 0 && (
                  <div className="text-center py-12">
                    <Brain size={32} className="mx-auto mb-3" style={{ color: '#D4AF3740' }} />
                    <p className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>Ask AURA anything about your Shopify store</p>
                    <div className="flex flex-wrap gap-2 justify-center mt-4">
                      {['What issues does my store have?', 'How many carts were recovered?', 'How can I improve my score?'].map(q => (
                        <button key={q} onClick={() => { setChatInput(q); }} className="px-3 py-1.5 rounded-lg text-[10px]" style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.15)' }}>{q}</button>
                      ))}
                    </div>
                  </div>
                )}
                {chatMessages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className="max-w-[80%] px-4 py-2.5 rounded-2xl text-xs leading-relaxed" style={{
                      background: m.role === 'user' ? 'rgba(212,175,55,0.15)' : 'rgba(128,128,128,0.08)',
                      color: 'var(--aurem-text)',
                      borderBottomRightRadius: m.role === 'user' ? '4px' : '16px',
                      borderBottomLeftRadius: m.role === 'user' ? '16px' : '4px',
                    }}>{m.text}</div>
                  </div>
                ))}
                {chatLoading && <div className="flex justify-start"><div className="px-4 py-2.5 rounded-2xl" style={{ background: 'rgba(128,128,128,0.08)' }}><Loader2 size={14} className="animate-spin" style={{ color: '#D4AF37' }} /></div></div>}
              </div>

              <div className="p-4 flex gap-2" style={{ borderTop: '1px solid rgba(128,128,128,0.1)' }}>
                <input type="text" value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendAuraChat()}
                  placeholder="Ask AURA about your store..." className="flex-1 px-4 py-2.5 rounded-xl text-xs bg-transparent focus:outline-none"
                  style={{ border: '1px solid rgba(128,128,128,0.2)', color: 'var(--aurem-text)' }} data-testid="aura-chat-input" />
                <button onClick={sendAuraChat} disabled={chatLoading || !chatInput.trim()} className="px-4 py-2.5 rounded-xl text-xs font-bold" style={{ background: '#D4AF37', color: '#050505' }} data-testid="aura-chat-send">
                  Send
                </button>
              </div>
            </div>
          </div>
        )}


        {/* ═══ STORE CONNECT ═══ */}
        {tab === 'connect' && (
          <div className="space-y-5">
            <div className="aurem-glass-card p-5 rounded-2xl">
              <div className="flex items-center gap-2 mb-3">
                <Globe size={16} style={{ color: '#D4AF37' }} />
                <h3 className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-text)' }}>CONNECT SHOPIFY STORE</h3>
              </div>
              <p className="text-[10px] mb-4" style={{ color: 'var(--aurem-text-secondary)' }}>
                Enter your Shopify store domain to establish the AUREM connection. Once connected, deploy the 3 Pillars via Theme Editor.
              </p>
              <div className="flex gap-3">
                <div className="flex-1 flex items-stretch rounded-xl overflow-hidden" style={{ border: '1px solid rgba(128,128,128,0.2)' }}>
                  <span className="flex items-center px-3 text-[10px] font-bold" style={{ color: 'var(--aurem-text-secondary)', background: 'rgba(128,128,128,0.06)' }}>https://</span>
                  <input type="text" value={shopDomain} onChange={e => setShopDomain(e.target.value)}
                    placeholder="store-name.myshopify.com" onKeyDown={e => e.key === 'Enter' && handleConnect()}
                    className="flex-1 px-3 py-2.5 bg-transparent text-sm focus:outline-none" style={{ color: 'var(--aurem-text)' }}
                    data-testid="connect-shop-input" />
                </div>
                <button onClick={handleConnect} disabled={loading} data-testid="connect-btn"
                  className="px-5 py-2.5 rounded-xl font-bold text-sm text-white flex items-center gap-2 disabled:opacity-50"
                  style={{ background: '#D4AF37' }}>
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                  Connect
                </button>
              </div>
              {installResult && (
                <div className="mt-3 p-3 rounded-xl text-[10px]" style={{ background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)' }}>
                  <CheckCircle size={12} className="inline mr-1 text-emerald-400" />
                  <span className="font-bold text-emerald-400">{installResult.message || `Connected: ${installResult.shop_domain}`}</span>
                </div>
              )}
            </div>

            {/* Connected Stores List */}
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>CONNECTED STORES ({connections.length})</h3>
              {connections.length === 0 ? (
                <div className="text-center py-8">
                  <ShoppingBag size={28} className="mx-auto mb-2" style={{ color: 'var(--aurem-text-secondary)', opacity: 0.3 }} />
                  <p className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>No stores connected yet</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {connections.map(c => (
                    <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl" style={{ border: '1px solid rgba(128,128,128,0.1)' }}>
                      <span className="size-2 rounded-full bg-emerald-400" style={{ boxShadow: '0 0 6px #4ade80' }} />
                      <span className="text-xs font-bold flex-1" style={{ color: 'var(--aurem-text)' }}>{c.shop_domain}</span>
                      <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{c.connected_at?.slice(0, 10)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Onboarding Steps */}
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-4" style={{ color: 'var(--aurem-text)' }}>DEPLOYMENT CHECKLIST</h3>
              {[
                { step: 1, label: 'Connect Store', desc: 'Enter your .myshopify.com domain above', done: connections.length > 0 },
                { step: 2, label: 'Deploy Extensions', desc: 'Push ORA Pixel + Chat + Recs via Shopify CLI', done: false },
                { step: 3, label: 'Enable in Theme Editor', desc: 'Open Theme Editor > App Embeds > Enable AUREM Vision', done: false },
                { step: 4, label: 'Generate ADMT Disclosure', desc: 'Required for AI compliance (Compliance tab)', done: complianceStatus?.ai_disclosure_generated },
                { step: 5, label: 'Privacy & Terms Published', desc: 'Legal pages linked in app manifest', done: !!complianceStatus?.legal_pages?.privacy_policy },
                { step: 6, label: 'Support Page Active', desc: 'Help center with FAQ + contact form', done: !!complianceStatus?.legal_pages?.support },
                { step: 7, label: 'Submit to Shopify App Store', desc: 'Upload listing content + screenshots in Partner Dashboard', done: false },
              ].map(s => (
                <div key={s.step} className="flex items-center gap-3 py-2.5">
                  <div className={`size-6 rounded-full flex items-center justify-center text-[10px] font-black ${s.done ? 'bg-emerald-400 text-[#0A0A14]' : 'text-[#666]'}`}
                    style={!s.done ? { border: '1px solid rgba(128,128,128,0.2)' } : {}}>
                    {s.done ? <Check size={12} /> : s.step}
                  </div>
                  <div className="flex-1">
                    <div className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{s.label}</div>
                    <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{s.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ COMPLIANCE ═══ */}
        {tab === 'compliance' && (
          <div className="space-y-5">
            {/* Readiness */}
            <div className="aurem-glass-card p-5 rounded-2xl">
              <div className="flex items-center gap-2 mb-4">
                <Shield size={16} style={{ color: '#8B5CF6' }} />
                <h3 className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-text)' }}>APP STORE COMPLIANCE</h3>
              </div>
              {complianceStatus && (
                <div className="space-y-2">
                  {[
                    { label: 'GDPR: customers/data_request', ok: complianceStatus.gdpr_webhooks?.customers_data_request, detail: 'Returns stored data on request' },
                    { label: 'GDPR: customers/redact', ok: complianceStatus.gdpr_webhooks?.customers_redact, detail: 'Deletes customer data on request' },
                    { label: 'GDPR: shop/redact', ok: complianceStatus.gdpr_webhooks?.shop_redact, detail: 'Purges all data on app uninstall' },
                    { label: 'Theme App Extensions', ok: complianceStatus.theme_app_extension, detail: 'No ScriptTags — Liquid App Blocks only' },
                    { label: 'GraphQL API v2026-04', ok: complianceStatus.graphql_api_version === '2026-04', detail: '100% GraphQL (REST deprecated)' },
                    { label: 'No ScriptTags', ok: !complianceStatus.script_tags_used, detail: 'Storefront uses Theme App Extensions only' },
                    { label: 'AI/ADMT Disclosure', ok: complianceStatus.ai_disclosure_generated, detail: 'Required by 2026 CCPA/GDPR' },
                    { label: 'Privacy Policy', ok: !!complianceStatus.legal_pages?.privacy_policy, detail: complianceStatus.legal_pages?.privacy_policy || '/privacy', link: '/privacy' },
                    { label: 'Terms of Service', ok: !!complianceStatus.legal_pages?.terms_of_service, detail: complianceStatus.legal_pages?.terms_of_service || '/terms', link: '/terms' },
                    { label: 'Support/Help Page', ok: !!complianceStatus.legal_pages?.support, detail: complianceStatus.legal_pages?.support || '/support', link: '/support' },
                    { label: 'OAuth Nonce Validation', ok: complianceStatus.oauth_hardened?.nonce_validation, detail: 'CSRF protection on install flow' },
                    { label: 'OAuth Token Exchange', ok: complianceStatus.oauth_hardened?.token_exchange, detail: complianceStatus.oauth_hardened?.token_exchange ? 'Active' : 'Needs SHOPIFY_API_KEY + SECRET' },
                    { label: 'Webhook HMAC Enforcement', ok: complianceStatus.oauth_hardened?.hmac_enforcement, detail: 'Rejects unsigned webhooks in production' },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid rgba(128,128,128,0.06)' }}>
                      {item.ok ? <CheckCircle size={14} className="text-emerald-400 shrink-0" /> : <XCircle size={14} className="shrink-0" style={{ color: '#666' }} />}
                      <div className="flex-1">
                        <span className="text-[11px] font-bold" style={{ color: 'var(--aurem-text)' }}>
                          {item.link ? <a href={item.link} target="_blank" rel="noopener noreferrer" className="hover:underline">{item.label}</a> : item.label}
                        </span>
                        <div className="text-[9px]" style={{ color: 'var(--aurem-text-secondary)' }}>{item.detail}</div>
                      </div>
                      <span className={`text-[8px] px-2 py-0.5 rounded-full font-bold ${item.ok ? 'bg-emerald-400/10 text-emerald-400' : 'text-[#666]'}`}
                        style={!item.ok ? { background: 'rgba(128,128,128,0.1)' } : {}}>
                        {item.ok ? 'READY' : 'PENDING'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ADMT Generator */}
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>ADMT DISCLOSURE GENERATOR</h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <input placeholder="Store Name" value={storeName} onChange={e => setStoreName(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm bg-transparent" style={{ border: '1px solid rgba(128,128,128,0.2)', color: 'var(--aurem-text)' }} data-testid="compliance-store-name" />
                <input placeholder="Store URL" value={storeUrl} onChange={e => setStoreUrl(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm bg-transparent" style={{ border: '1px solid rgba(128,128,128,0.2)', color: 'var(--aurem-text)' }} data-testid="compliance-store-url" />
              </div>
              <button onClick={handleGenerateSnippet} disabled={loading} className="px-5 py-2 rounded-xl text-xs font-bold text-white" style={{ background: '#8B5CF6' }} data-testid="generate-snippet-btn">
                {loading ? <Loader2 size={13} className="animate-spin inline mr-1" /> : null}Generate ADMT Snippet
              </button>
              {snippet && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>Generated HTML</span>
                    <button onClick={() => { navigator.clipboard.writeText(snippet); setSnippetCopied(true); setTimeout(() => setSnippetCopied(false), 2000); }}
                      className="flex items-center gap-1 text-[10px] font-bold" style={{ color: '#D4AF37' }}>
                      {snippetCopied ? <Check size={11} /> : <Copy size={11} />}{snippetCopied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <pre className="p-4 rounded-xl text-[10px] leading-relaxed overflow-auto max-h-48 font-mono"
                    style={{ background: 'rgba(10,10,20,0.8)', color: '#8B8B8B', border: '1px solid rgba(128,128,128,0.1)' }}>{snippet}</pre>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ APP LISTING ═══ */}
        {tab === 'listing' && (
          <div className="space-y-5">
            <div className="aurem-glass-card p-5 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-black tracking-wider" style={{ color: 'var(--aurem-text)' }}>SHOPIFY APP STORE LISTING</h3>
                <button
                  onClick={async () => {
                    try {
                      const [contentRes, checkRes] = await Promise.all([
                        fetch(`${API_URL}/api/shopify-listing/content`, { headers }),
                        fetch(`${API_URL}/api/shopify-listing/submission-checklist`, { headers }),
                      ]);
                      if (contentRes.ok) setListingContent(await contentRes.json());
                      if (checkRes.ok) setSubmissionChecklist(await checkRes.json());
                    } catch {}
                  }}
                  data-testid="fetch-listing-btn"
                  className="text-[9px] font-bold px-3 py-1.5 rounded-lg" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>
                  Load Content
                </button>
              </div>

              {listingContent ? (
                <div className="space-y-4">
                  <div className="p-3 rounded-xl" style={{ background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.12)' }}>
                    <div className="text-[9px] font-bold mb-1" style={{ color: '#D4AF37' }}>APP NAME</div>
                    <div className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{listingContent.app_name}</div>
                  </div>
                  <div className="p-3 rounded-xl" style={{ background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.12)' }}>
                    <div className="text-[9px] font-bold mb-1" style={{ color: '#D4AF37' }}>TAGLINE</div>
                    <div className="text-[11px]" style={{ color: 'var(--aurem-text)' }}>{listingContent.tagline}</div>
                  </div>
                  <div className="p-3 rounded-xl" style={{ background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.12)' }}>
                    <div className="text-[9px] font-bold mb-1" style={{ color: '#D4AF37' }}>FEATURES ({listingContent.features_list?.length})</div>
                    <div className="grid grid-cols-2 gap-1 mt-2">
                      {listingContent.features_list?.map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[9px]" style={{ color: 'var(--aurem-text-secondary)' }}>
                          <CheckCircle size={10} className="text-emerald-400 shrink-0" /> {f}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl" style={{ background: 'rgba(212,175,55,0.04)', border: '1px solid rgba(212,175,55,0.12)' }}>
                    <div className="text-[9px] font-bold mb-1" style={{ color: '#D4AF37' }}>CATEGORIES</div>
                    <div className="flex gap-2 mt-1">
                      {listingContent.categories?.map((c, i) => (
                        <span key={i} className="text-[9px] px-2 py-1 rounded-full" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>{c}</span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-center py-8" style={{ color: 'var(--aurem-text-secondary)' }}>Click "Load Content" to view generated listing</p>
              )}
            </div>

            {submissionChecklist && (
              <div className="aurem-glass-card p-5 rounded-2xl">
                <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>
                  SUBMISSION CHECKLIST ({submissionChecklist.ready_count}/{submissionChecklist.total} READY)
                </h3>
                <div className="space-y-1">
                  {submissionChecklist.checklist?.map((item, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5" style={{ borderBottom: '1px solid rgba(128,128,128,0.06)' }}>
                      {item.status === 'ready' ? <CheckCircle size={12} className="text-emerald-400 shrink-0" /> : <XCircle size={12} className="shrink-0" style={{ color: '#666' }} />}
                      <span className="text-[10px] flex-1" style={{ color: 'var(--aurem-text)' }}>{item.item}</span>
                      <span className={`text-[8px] px-2 py-0.5 rounded-full font-bold ${item.status === 'ready' ? 'bg-emerald-400/10 text-emerald-400' : 'text-[#666]'}`}
                        style={item.status !== 'ready' ? { background: 'rgba(128,128,128,0.1)' } : {}}>
                        {item.status === 'ready' ? 'READY' : 'PENDING'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══ BILLING ═══ */}
        {tab === 'billing' && (
          <div className="space-y-5">
            {/* Commission Tracking */}
            <div className="aurem-glass-card p-5 rounded-2xl" data-testid="commission-tracking">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>COMMISSION TRACKING</h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-4 rounded-xl text-center" style={{ background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.15)' }}>
                  <p className="text-xl font-black" style={{ color: '#4ade80' }}>{recoveryStats?.recovered || 0}</p>
                  <p className="text-[9px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>RECOVERIES</p>
                </div>
                <div className="p-4 rounded-xl text-center" style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.15)' }}>
                  <p className="text-xl font-black" style={{ color: '#D4AF37' }}>${recoveryStats?.commission_earned || '0.00'}</p>
                  <p className="text-[9px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>EARNED ($2/recovery)</p>
                </div>
                <div className="p-4 rounded-xl text-center" style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)' }}>
                  <p className="text-xl font-black" style={{ color: '#3b82f6' }}>${recoveryStats?.revenue_recovered || 0}</p>
                  <p className="text-[9px] font-bold" style={{ color: 'var(--aurem-text-secondary)' }}>MERCHANT SAVED</p>
                </div>
              </div>
            </div>

            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>SHOPIFY BILLING API</h3>
              <p className="text-[11px] mb-4" style={{ color: 'var(--aurem-text-secondary)' }}>
                Shopify requires apps to use their Billing API (GraphQL <code>appSubscriptionCreate</code>) for merchant charges.
                This replaces external payment processors for in-app purchases.
              </p>
              <button
                onClick={async () => {
                  try {
                    const res = await fetch(`${API_URL}/api/shopify-billing/plans`, { headers });
                    if (res.ok) { const d = await res.json(); setBillingPlans(d.plans || []); }
                  } catch {}
                }}
                data-testid="fetch-billing-plans-btn"
                className="text-[9px] font-bold px-3 py-1.5 rounded-lg mb-4" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>
                Load Plans
              </button>

              {billingPlans.length > 0 && (
                <div className="grid grid-cols-3 gap-3">
                  {billingPlans.map((plan) => (
                    <div key={plan.id} className="p-4 rounded-xl text-center" style={{ border: '1px solid rgba(212,175,55,0.12)', background: plan.id === 'professional' ? 'rgba(212,175,55,0.04)' : 'transparent' }}>
                      <div className="text-[11px] font-bold mb-1" style={{ color: 'var(--aurem-text)' }}>{plan.name}</div>
                      <div className="text-lg font-black mb-1" style={{ color: '#D4AF37' }}>${plan.price}<span className="text-[9px] font-normal">/mo</span></div>
                      <div className="text-[8px] mb-3" style={{ color: 'var(--aurem-text-secondary)' }}>{plan.trial_days}-day free trial</div>
                      <div className="space-y-1 text-left">
                        {plan.features?.map((f, i) => (
                          <div key={i} className="flex items-center gap-1 text-[8px]" style={{ color: 'var(--aurem-text-secondary)' }}>
                            <Check size={8} className="text-emerald-400 shrink-0" /> {f}
                          </div>
                        ))}
                      </div>
                      <button
                        className="w-full mt-3 py-1.5 rounded-lg text-[9px] font-bold transition-all"
                        style={{ background: plan.id === 'professional' ? 'linear-gradient(135deg, #D4AF37, #B88759)' : 'rgba(128,128,128,0.1)', color: plan.id === 'professional' ? '#050505' : 'var(--aurem-text-secondary)' }}>
                        {plan.id === 'professional' ? 'RECOMMENDED' : 'Select'}
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4 p-3 rounded-xl" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(61,58,57,0.3)' }}>
                <div className="text-[9px] font-bold mb-1" style={{ color: '#FF6B00' }}>HOW IT WORKS</div>
                <ol className="text-[9px] space-y-1 list-decimal list-inside" style={{ color: 'var(--aurem-text-secondary)' }}>
                  <li>Merchant selects a plan in your Shopify app</li>
                  <li>AUREM calls <code>appSubscriptionCreate</code> GraphQL mutation</li>
                  <li>Shopify returns a <code>confirmation_url</code></li>
                  <li>Merchant approves charge on Shopify's hosted page</li>
                  <li>Shopify handles billing, invoicing, and payouts to you</li>
                </ol>
              </div>
            </div>
          </div>
        )}

        {/* ═══ EXTENSIONS ═══ */}
        {tab === 'extensions' && (
          <div className="space-y-5">
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>SHOPIFY THEME EXTENSIONS</h3>
              <p className="text-[11px] mb-4" style={{ color: 'var(--aurem-text-secondary)' }}>
                These extensions are deployed to your Shopify app via the Shopify CLI. Merchants enable them in their Theme Editor.
              </p>
              <div className="space-y-3">
                {[
                  { name: 'ORA Pixel', type: 'Web Pixel Extension', desc: 'Tracks page views, product views, add-to-cart, and checkouts in Shopify\'s secure sandbox. Zero performance impact.', file: 'extensions/ora-pixel/', icon: Eye, color: '#3b82f6' },
                  { name: 'ORA Chat Widget', type: 'App Embed Block', desc: 'Floating glassmorphism chat bubble with voice input. Connects to AUREM V2V engine via WebSocket + text fallback.', file: 'extensions/ora-chat/', icon: MessageSquare, color: '#D4AF37' },
                  { name: 'ORA Recommendations', type: 'App Block (Section)', desc: 'Drag-and-drop "Recommended For You" section. Fetches AI-powered product cards via App Proxy.', file: 'extensions/ora-recommendations/', icon: Brain, color: '#8B5CF6' },
                ].map((ext, i) => (
                  <div key={i} className="p-4 rounded-xl" style={{ border: '1px solid rgba(128,128,128,0.1)' }}>
                    <div className="flex items-center gap-3 mb-2">
                      <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${ext.color}15` }}>
                        <ext.icon size={15} style={{ color: ext.color }} />
                      </div>
                      <div className="flex-1">
                        <div className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{ext.name}</div>
                        <div className="text-[9px] font-bold" style={{ color: ext.color }}>{ext.type}</div>
                      </div>
                    </div>
                    <p className="text-[10px] mb-2" style={{ color: 'var(--aurem-text-secondary)' }}>{ext.desc}</p>
                    <code className="text-[9px] font-mono px-2 py-1 rounded" style={{ background: 'rgba(128,128,128,0.1)', color: 'var(--aurem-text-secondary)' }}>
                      shopify-extension/{ext.file}
                    </code>
                  </div>
                ))}
              </div>
            </div>

            {/* Deployment Guide */}
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-xs font-black tracking-wider mb-3" style={{ color: 'var(--aurem-text)' }}>DEPLOYMENT GUIDE</h3>
              <div className="p-4 rounded-xl font-mono text-[10px] leading-loose overflow-auto" style={{ background: 'rgba(10,10,20,0.8)', color: '#8B8B8B' }}>
                <div><span style={{ color: '#4ade80' }}># 1. Install Shopify CLI</span></div>
                <div>npm install -g @shopify/cli @shopify/theme</div>
                <div style={{ marginTop: 8 }}><span style={{ color: '#4ade80' }}># 2. Login to Shopify Partner Dashboard</span></div>
                <div>shopify auth login</div>
                <div style={{ marginTop: 8 }}><span style={{ color: '#4ade80' }}># 3. Deploy extensions to your app</span></div>
                <div>cd shopify-extension</div>
                <div>shopify app deploy</div>
                <div style={{ marginTop: 8 }}><span style={{ color: '#4ade80' }}># 4. Merchant enables in Theme Editor:</span></div>
                <div><span style={{ color: '#D4AF37' }}>Theme Editor {'>'} App Embeds {'>'} Toggle ON:</span></div>
                <div>  - ORA Chat Widget</div>
                <div>  - ORA Pixel (auto-enabled)</div>
                <div><span style={{ color: '#D4AF37' }}>Theme Editor {'>'} Add Section {'>'}</span></div>
                <div>  - AUREM Recommended For You</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ShopifyAppManager;
