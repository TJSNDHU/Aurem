import React, { useState, useEffect, useCallback, useRef , useMemo } from 'react';
import {
  Globe, ShoppingBag, Server, CreditCard, Monitor, Zap, FileText, Briefcase,
  Plus, Trash2, Upload, Download, RefreshCw, ChevronRight, AlertCircle,
  CheckCircle, X, Loader2, Link2, Search, Package, Users, Activity,
  Radio, Brain, Clock, Target, ArrowRight
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const PLATFORM_ICONS = {
  shopify: ShoppingBag, woocommerce: Globe, magento: Server,
  square: CreditCard, clover: Monitor, stripe: Zap,
  csv_manual: FileText, standalone: Briefcase, api_import: Link2,
};

const PLATFORM_COLORS = {
  shopify: '#96BF48', woocommerce: '#7B3FA0', magento: '#F26322',
  square: '#006AFF', clover: '#1EC760', stripe: '#635BFF',
  csv_manual: '#FF6B00', standalone: '#D4AF37',
};

const STATUS_BADGE = {
  supported: { bg: 'rgba(16,185,129,0.1)', color: '#10b981', label: 'Live' },
  coming_soon: { bg: 'rgba(245,158,11,0.1)', color: '#f59e0b', label: 'Coming Soon' },
  scaffold: { bg: 'rgba(59,130,246,0.1)', color: '#3b82f6', label: 'Scaffold' },
};

export default function UniversalConnector({ token }) {
  const [tab, setTab] = useState('overview');
  const [platforms, setPlatforms] = useState([]);
  const [connections, setConnections] = useState([]);
  const [products, setProducts] = useState({ products: [], total: 0, by_platform: {} });
  const [stats, setStats] = useState({});
  const [ucpManifest, setUcpManifest] = useState(null);
  const [oraActions, setOraActions] = useState([]);
  const [pulseStats, setPulseStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showAddConn, setShowAddConn] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showAddProduct, setShowAddProduct] = useState(false);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, cRes, sRes, prRes] = await Promise.all([
        fetch(`${API}/api/universal/platforms`),
        fetch(`${API}/api/universal/connections`, { headers }),
        fetch(`${API}/api/universal/stats`, { headers }),
        fetch(`${API}/api/universal/products?limit=50`, { headers }),
      ]);
      if (pRes.ok) setPlatforms((await pRes.json()).platforms || []);
      if (cRes.ok) setConnections((await cRes.json()).connections || []);
      if (sRes.ok) setStats(await sRes.json());
      if (prRes.ok) setProducts(await prRes.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [headers]);

  const fetchUCP = useCallback(async () => {
    try {
      const [mRes, aRes, pRes] = await Promise.all([
        fetch(`${API}/api/ucp/manifest`),
        fetch(`${API}/api/ora/actions`),
        fetch(`${API}/api/ora/pulse/stats`, { headers }),
      ]);
      if (mRes.ok) setUcpManifest(await mRes.json());
      if (aRes.ok) setOraActions((await aRes.json()).actions || []);
      if (pRes.ok) setPulseStats(await pRes.json());
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { if (tab === 'ucp' || tab === 'ora') fetchUCP(); }, [tab, fetchUCP]);

  const deleteConnection = async (id) => {
    await fetch(`${API}/api/universal/connections/${id}`, { method: 'DELETE', headers });
    fetchAll();
  };

  const deleteProduct = async (id) => {
    await fetch(`${API}/api/universal/products/${id}`, { method: 'DELETE', headers });
    fetchAll();
  };

  const tabs = [
    { id: 'overview', label: 'Hub Overview' },
    { id: 'connections', label: 'Platforms', badge: connections.length },
    { id: 'products', label: 'Product Catalog', badge: products.total },
    { id: 'ucp', label: 'UCP Protocol' },
    { id: 'ora', label: 'ORA Actions' },
  ];

  return (
    <div className="space-y-6" data-testid="universal-connector">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>Universal Connector</h1>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>
            Platform-agnostic commerce layer, connect any storefront, POS, or manual operation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowImport(true)} className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all" style={{ background: 'rgba(61,58,57,0.25)', color: '#FF6B00' }} data-testid="csv-import-btn">
            <Upload size={14} /> CSV Import
          </button>
          <button onClick={() => setShowAddConn(true)} className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] hover:opacity-90 transition-all" data-testid="add-platform-btn">
            <Plus size={14} /> Connect Platform
          </button>
          <button onClick={fetchAll} disabled={loading} className="p-2 rounded-xl transition-all" style={{ background: 'rgba(128,128,128,0.08)' }} data-testid="refresh-universal">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} style={{ color: 'var(--aurem-text-secondary)' }} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'rgba(128,128,128,0.06)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${tab === t.id ? 'shadow-sm' : ''}`}
            style={{ background: tab === t.id ? 'var(--aurem-card-bg, #fff)' : 'transparent', color: tab === t.id ? 'var(--aurem-text)' : 'var(--aurem-text-secondary)' }}
            data-testid={`tab-${t.id}`}>
            {t.label}
            {t.badge !== undefined && <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold" style={{ background: 'rgba(212,175,55,0.15)', color: '#D4AF37' }}>{t.badge}</span>}
          </button>
        ))}
      </div>

      {/* Modals */}
      {showImport && <CSVImportModal token={token} onClose={() => setShowImport(false)} onDone={() => { setShowImport(false); fetchAll(); }} />}
      {showAddConn && <AddConnectionModal token={token} platforms={platforms} onClose={() => setShowAddConn(false)} onDone={() => { setShowAddConn(false); fetchAll(); }} />}
      {showAddProduct && <AddProductModal token={token} onClose={() => setShowAddProduct(false)} onDone={() => { setShowAddProduct(false); fetchAll(); }} />}

      {/* ═══ HUB OVERVIEW ═══ */}
      {tab === 'overview' && (
        <div className="space-y-5">
          <div className="grid grid-cols-5 gap-4">
            {[
              { label: 'Platforms', value: stats.connections || 0, icon: Globe, color: '#D4AF37' },
              { label: 'Products', value: stats.products || 0, icon: Package, color: '#FF6B00' },
              { label: 'Customers', value: stats.customers || 0, icon: Users, color: '#3b82f6' },
              { label: 'Events', value: stats.events || 0, icon: Activity, color: '#8B5CF6' },
              { label: 'Invoices', value: stats.invoices || 0, icon: FileText, color: '#f59e0b' },
            ].map((m, i) => (
              <div key={i} className="aurem-glass-card p-4 rounded-2xl">
                <div className="flex items-center gap-2 mb-2">
                  <m.icon size={14} style={{ color: m.color }} />
                  <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>{m.label}</span>
                </div>
                <div className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>{m.value.toLocaleString()}</div>
              </div>
            ))}
          </div>

          {/* Products by Platform */}
          {Object.keys(stats.products_by_platform || {}).length > 0 && (
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--aurem-text)' }}>Products by Source</h3>
              <div className="flex gap-3 flex-wrap">
                {Object.entries(stats.products_by_platform).map(([platform, count]) => {
                  const Icon = PLATFORM_ICONS[platform] || Package;
                  const clr = PLATFORM_COLORS[platform] || '#888';
                  return (
                    <div key={platform} className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: `${clr}15` }}>
                      <Icon size={14} style={{ color: clr }} />
                      <span className="text-xs font-medium" style={{ color: clr }}>{platform}</span>
                      <span className="text-xs font-bold" style={{ color: 'var(--aurem-text)' }}>{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Supported Platforms Grid */}
          <div className="aurem-glass-card p-5 rounded-2xl">
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--aurem-text)' }}>Supported Platforms</h3>
            <div className="grid grid-cols-4 gap-3">
              {platforms.map(p => {
                const Icon = PLATFORM_ICONS[p.type] || Globe;
                const clr = PLATFORM_COLORS[p.type] || '#888';
                const badge = STATUS_BADGE[p.status] || STATUS_BADGE.scaffold;
                return (
                  <div key={p.type} className="flex items-center gap-3 p-3 rounded-xl transition-all hover:scale-[1.02]" style={{ background: `${clr}08`, border: `1px solid ${clr}20` }} data-testid={`platform-${p.type}`}>
                    <div className="size-9 rounded-lg flex items-center justify-center" style={{ background: `${clr}18` }}>
                      <Icon size={16} style={{ color: clr }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold" style={{ color: 'var(--aurem-text)' }}>{p.name}</div>
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase" style={{ background: badge.bg, color: badge.color }}>{badge.label}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ═══ CONNECTIONS TAB ═══ */}
      {tab === 'connections' && (
        <div className="space-y-4">
          {connections.length === 0 ? (
            <div className="aurem-glass-card p-12 rounded-2xl text-center">
              <Globe size={36} className="mx-auto mb-3" style={{ color: 'var(--aurem-text-secondary)', opacity: 0.4 }} />
              <p className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>No platforms connected yet</p>
              <p className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>Connect Shopify, upload a CSV, or start with standalone mode</p>
              <button onClick={() => setShowAddConn(true)} className="mt-4 px-6 py-2 rounded-lg text-sm font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355]" data-testid="add-first-platform">
                <Plus size={14} className="inline mr-1" /> Connect First Platform
              </button>
            </div>
          ) : (
            connections.map(c => {
              const Icon = PLATFORM_ICONS[c.platform_type] || Globe;
              const clr = PLATFORM_COLORS[c.platform_type] || '#888';
              return (
                <div key={c.id} className="aurem-glass-card p-4 rounded-2xl flex items-center gap-4" data-testid={`connection-${c.id}`}>
                  <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: `${clr}18` }}>
                    <Icon size={18} style={{ color: clr }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold" style={{ color: 'var(--aurem-text)' }}>{c.display_name}</div>
                    <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>
                      <span className="uppercase font-bold" style={{ color: clr }}>{c.platform_type}</span>
                      {c.shop_domain && <span>{c.shop_domain}</span>}
                      <span>{c.products_synced} products</span>
                      <span>{c.customers_synced} customers</span>
                    </div>
                  </div>
                  <span className="px-2 py-1 rounded text-[9px] font-bold uppercase" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>{c.status}</span>
                  <button onClick={() => deleteConnection(c.id)} className="p-1.5 rounded-lg hover:bg-red-50 transition-colors" data-testid={`delete-conn-${c.id}`}>
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ═══ PRODUCTS TAB ═══ */}
      {tab === 'products' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {Object.entries(products.by_platform || {}).map(([p, c]) => (
                <span key={p} className="px-2 py-1 rounded text-[10px] font-bold" style={{ background: `${PLATFORM_COLORS[p] || '#888'}15`, color: PLATFORM_COLORS[p] || '#888' }}>
                  {p}: {c}
                </span>
              ))}
            </div>
            <button onClick={() => setShowAddProduct(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium" style={{ background: 'rgba(61,58,57,0.25)', color: '#FF6B00' }} data-testid="add-manual-product">
              <Plus size={13} /> Add Product
            </button>
          </div>

          {products.products?.length === 0 ? (
            <div className="aurem-glass-card p-12 rounded-2xl text-center">
              <Package size={36} className="mx-auto mb-3" style={{ color: 'var(--aurem-text-secondary)', opacity: 0.4 }} />
              <p className="text-sm" style={{ color: 'var(--aurem-text)' }}>No products yet. Import a CSV or add manually.</p>
            </div>
          ) : (
            <div className="aurem-glass-card rounded-2xl overflow-hidden">
              <table className="w-full text-left">
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(128,128,128,0.15)' }}>
                    {['Product', 'SKU', 'Price', 'Stock', 'Category', 'Source', ''].map((h, i) => (
                      <th key={i} className="px-4 py-3 text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {products.products.map(p => {
                    const clr = PLATFORM_COLORS[p.source_platform] || '#888';
                    return (
                      <tr key={p.id} className="hover:bg-white/5 transition-colors" style={{ borderBottom: '1px solid rgba(128,128,128,0.08)' }} data-testid={`product-row-${p.id}`}>
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{p.name}</div>
                          <div className="text-[10px] truncate max-w-[200px]" style={{ color: 'var(--aurem-text-secondary)' }}>{p.description}</div>
                        </td>
                        <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--aurem-text-secondary)' }}>{p.sku || '—'}</td>
                        <td className="px-4 py-3 text-sm font-bold" style={{ color: '#FF6B00' }}>${p.price?.toFixed(2)}</td>
                        <td className="px-4 py-3 text-xs font-medium" style={{ color: p.inventory_quantity > 10 ? 'var(--aurem-text)' : '#ef4444' }}>{p.inventory_quantity}</td>
                        <td className="px-4 py-3 text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{p.category || '—'}</td>
                        <td className="px-4 py-3">
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: `${clr}15`, color: clr }}>{p.source_platform}</span>
                        </td>
                        <td className="px-4 py-3">
                          <button onClick={() => deleteProduct(p.id)} className="p-1 rounded hover:bg-red-50">
                            <Trash2 size={12} className="text-red-400" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═══ UCP PROTOCOL TAB ═══ */}
      {tab === 'ucp' && ucpManifest && (
        <div className="space-y-5">
          <div className="aurem-glass-card p-6 rounded-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="size-10 rounded-xl flex items-center justify-center" style={{ background: 'rgba(139,91,214,0.12)' }}>
                <Radio size={18} style={{ color: '#8B5CF6' }} />
              </div>
              <div>
                <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>Universal Commerce Protocol</h2>
                <p className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>v{ucpManifest.protocol_version} — Agent-to-Agent Commerce Layer</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="p-4 rounded-xl" style={{ background: 'rgba(128,128,128,0.04)', border: '1px solid rgba(128,128,128,0.1)' }}>
                <h3 className="text-xs font-bold mb-2 uppercase" style={{ color: '#8B5CF6' }}>Capabilities</h3>
                {Object.entries(ucpManifest.capabilities).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-1">
                    <span className="text-xs font-medium" style={{ color: 'var(--aurem-text)' }}>{k}</span>
                    <code className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(128,128,128,0.08)', color: 'var(--aurem-text-secondary)' }}>{v}</code>
                  </div>
                ))}
              </div>
              <div className="p-4 rounded-xl" style={{ background: 'rgba(128,128,128,0.04)', border: '1px solid rgba(128,128,128,0.1)' }}>
                <h3 className="text-xs font-bold mb-2 uppercase" style={{ color: '#FF6B00' }}>Agent Handlers</h3>
                {Object.entries(ucpManifest.agent_handlers).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-1">
                    <span className="text-xs font-medium" style={{ color: 'var(--aurem-text)' }}>{k}</span>
                    <code className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(128,128,128,0.08)', color: 'var(--aurem-text-secondary)' }}>{v}</code>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-lg font-mono text-xs" style={{ background: 'rgba(0,0,0,0.3)', color: '#10b981' }} data-testid="ucp-install-snippet">
              <div className="text-[10px] mb-1" style={{ color: '#888' }}>{'<!-- Install on any website -->'}</div>
              {'<script src="'}{API}{'/api/pixel/aurem-pixel.js" data-aurem-key="YOUR_API_KEY"></script>'}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="aurem-glass-card p-4 rounded-2xl">
              <h3 className="text-xs font-bold mb-2 uppercase" style={{ color: 'var(--aurem-text-secondary)' }}>Supported Payments</h3>
              <div className="flex flex-wrap gap-2">
                {ucpManifest.supported_payments.map(p => (
                  <span key={p} className="px-2 py-1 rounded text-[10px] font-bold" style={{ background: 'rgba(99,91,255,0.08)', color: '#635BFF' }}>{p}</span>
                ))}
              </div>
            </div>
            <div className="aurem-glass-card p-4 rounded-2xl">
              <h3 className="text-xs font-bold mb-2 uppercase" style={{ color: 'var(--aurem-text-secondary)' }}>Currencies</h3>
              <div className="flex flex-wrap gap-2">
                {ucpManifest.supported_currencies.map(c => (
                  <span key={c} className="px-2 py-1 rounded text-[10px] font-bold" style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37' }}>{c}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══ ORA ACTIONS TAB ═══ */}
      {tab === 'ora' && (
        <div className="space-y-5">
          {/* Pulse Stats */}
          {pulseStats && (
            <div className="aurem-glass-card p-5 rounded-2xl">
              <div className="flex items-center gap-2 mb-3">
                <Target size={14} style={{ color: '#ef4444' }} />
                <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-text)' }}>TTFA Pulse Monitor</h3>
                <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(239,68,68,0.08)', color: '#ef4444' }}>Target: {'<'}400ms</span>
              </div>
              <div className="grid grid-cols-5 gap-3">
                {[
                  { label: 'Avg TTFA', value: `${pulseStats.avg_ttfa_ms}ms`, color: pulseStats.avg_ttfa_ms < 400 ? '#10b981' : '#ef4444' },
                  { label: 'P50', value: `${pulseStats.p50_ms}ms` },
                  { label: 'P95', value: `${pulseStats.p95_ms}ms` },
                  { label: 'Samples', value: pulseStats.samples },
                  { label: 'Below Target', value: `${pulseStats.below_target_pct}%`, color: '#FF6B00' },
                ].map((s, i) => (
                  <div key={i} className="text-center">
                    <div className="text-lg font-bold" style={{ color: s.color || 'var(--aurem-text)' }}>{s.value}</div>
                    <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{s.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Catalog */}
          <div className="aurem-glass-card p-5 rounded-2xl">
            <div className="flex items-center gap-2 mb-4">
              <Brain size={16} style={{ color: '#D4AF37' }} />
              <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-text)' }}>ORA Action Vault</h3>
              <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>{oraActions.length} actions</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {oraActions.map(a => (
                <div key={a.id} className="p-3 rounded-xl transition-all hover:scale-[1.02]" style={{ background: 'rgba(128,128,128,0.04)', border: '1px solid rgba(128,128,128,0.1)' }} data-testid={`ora-action-${a.id}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>{a.engine}</span>
                    <span className="text-xs font-semibold" style={{ color: 'var(--aurem-text)' }}>{a.name}</span>
                  </div>
                  <p className="text-[10px] mb-2" style={{ color: 'var(--aurem-text-secondary)' }}>{a.description}</p>
                  <div className="flex flex-wrap gap-1">
                    {a.voice_triggers.slice(0, 3).map((t, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded text-[8px] font-mono" style={{ background: 'rgba(128,128,128,0.06)', color: 'var(--aurem-text-secondary)' }}>"{t}"</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* ADD CONNECTION MODAL                                       */
/* ═══════════════════════════════════════════════════════════ */
function AddConnectionModal({ token, platforms, onClose, onDone }) {
  const [type, setType] = useState('standalone');
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [saving, setSaving] = useState(false);
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const submit = async () => {
    if (!name.trim()) return;
    setSaving(true);
    const res = await fetch(`${API}/api/universal/connections`, {
      method: 'POST', headers,
      body: JSON.stringify({ platform_type: type, display_name: name, shop_domain: domain || null }),
    });
    if (res.ok) onDone();
    setSaving(false);
  };

  const inputCls = "w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#D4AF37]";
  const inputStyle = { background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' };

  return (
    <div className="aurem-glass-card p-6 rounded-2xl space-y-4" data-testid="add-connection-modal">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>Connect Platform</h2>
        <button onClick={onClose}><X size={18} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
      </div>
      <div>
        <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Platform Type</label>
        <select value={type} onChange={e => setType(e.target.value)} className={inputCls} style={inputStyle} data-testid="platform-type-select">
          {platforms.map(p => <option key={p.type} value={p.type}>{p.name} {p.status !== 'supported' ? `(${p.status})` : ''}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Display Name *</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="My Local Shop" className={inputCls} style={inputStyle} data-testid="connection-name-input" />
      </div>
      {type === 'shopify' && (
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Shop Domain</label>
          <input value={domain} onChange={e => setDomain(e.target.value)} placeholder="mystore.myshopify.com" className={inputCls} style={inputStyle} data-testid="shop-domain-input" />
        </div>
      )}
      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 rounded-lg text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>Cancel</button>
        <button onClick={submit} disabled={saving || !name.trim()} className="px-6 py-2 rounded-lg text-sm font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] disabled:opacity-50" data-testid="submit-connection-btn">
          {saving ? 'Connecting...' : 'Connect'}
        </button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* CSV IMPORT MODAL                                           */
/* ═══════════════════════════════════════════════════════════ */
function CSVImportModal({ token, onClose, onDone }) {
  const [step, setStep] = useState('upload');
  const [dataType, setDataType] = useState('products');
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [mapping, setMapping] = useState({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef();
  const headers = { 'Authorization': `Bearer ${token}` };

  const analyzeFile = async () => {
    if (!file) return;
    setImporting(true);
    const form = new FormData();
    form.append('file', file);
    form.append('data_type', dataType);
    form.append('use_ai', 'true');
    try {
      const res = await fetch(`${API}/api/universal/import/analyze`, { method: 'POST', headers, body: form });
      if (res.ok) {
        const data = await res.json();
        setAnalysis(data);
        setMapping(data.mapping);
        setStep('review');
      }
    } catch (e) { console.error(e); }
    setImporting(false);
  };

  const executeImport = async () => {
    setImporting(true);
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const res = await fetch(`${API}/api/universal/import/execute`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify({ csv_text: e.target.result, column_mapping: mapping, data_type: dataType }),
        });
        if (res.ok) {
          const data = await res.json();
          setResult(data);
          setStep('done');
        }
      } catch (err) { console.error(err); }
      setImporting(false);
    };
    reader.readAsText(file);
  };

  const downloadTemplate = async () => {
    const res = await fetch(`${API}/api/universal/templates/${dataType}`, { headers });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aurem_${dataType}_template.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  const inputCls = "w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#FF6B00]";
  const inputStyle = { background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' };
  const TARGETS = dataType === 'products' ? ['name','description','price','compare_at_price','sku','barcode','category','tags','inventory_quantity','weight','image_url','status'] : ['email','first_name','last_name','phone','company','total_spend','orders_count','tags','notes'];

  return (
    <div className="aurem-glass-card p-6 rounded-2xl space-y-4" data-testid="csv-import-modal">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>
          {step === 'upload' && 'CSV Import'}
          {step === 'review' && 'Review Column Mapping'}
          {step === 'done' && 'Import Complete'}
        </h2>
        <button onClick={onClose}><X size={18} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
      </div>

      {step === 'upload' && (
        <>
          <div className="flex gap-3">
            {['products', 'customers'].map(t => (
              <button key={t} onClick={() => setDataType(t)}
                className={`px-4 py-2 rounded-lg text-xs font-bold uppercase ${dataType === t ? 'shadow-sm' : ''}`}
                style={{ background: dataType === t ? 'rgba(61,58,57,0.25)' : 'transparent', color: dataType === t ? '#FF6B00' : 'var(--aurem-text-secondary)' }}
                data-testid={`type-${t}`}>
                {t}
              </button>
            ))}
          </div>
          <div className="p-6 rounded-xl text-center border-2 border-dashed cursor-pointer" style={{ borderColor: 'rgba(128,128,128,0.2)' }}
            onClick={() => fileRef.current?.click()} data-testid="csv-dropzone">
            <Upload size={24} className="mx-auto mb-2" style={{ color: 'var(--aurem-text-secondary)' }} />
            <p className="text-sm" style={{ color: 'var(--aurem-text)' }}>{file ? file.name : 'Click to upload CSV file'}</p>
            <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>AI will auto-detect your column headers</p>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={e => setFile(e.target.files[0])} data-testid="csv-file-input" />
          </div>
          <div className="flex items-center justify-between">
            <button onClick={downloadTemplate} className="flex items-center gap-1.5 text-xs font-medium" style={{ color: '#FF6B00' }} data-testid="download-template-btn">
              <Download size={13} /> Download Template
            </button>
            <button onClick={analyzeFile} disabled={!file || importing}
              className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: '#FF6B00' }} data-testid="analyze-csv-btn">
              {importing ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              {importing ? 'Analyzing...' : 'Analyze & Map Columns'}
            </button>
          </div>
        </>
      )}

      {step === 'review' && analysis && (
        <>
          <div className="flex items-center gap-3 mb-2">
            <span className="px-2 py-1 rounded text-[10px] font-bold" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>
              {analysis.match_method === 'ai' ? 'AI-Matched' : 'Auto-Matched'}
            </span>
            <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{analysis.row_count} rows detected</span>
          </div>

          <div className="space-y-2">
            {analysis.headers.map(h => (
              <div key={h} className="flex items-center gap-3">
                <span className="w-40 text-xs font-mono truncate" style={{ color: 'var(--aurem-text)' }}>{h}</span>
                <ArrowRight size={12} style={{ color: 'var(--aurem-text-secondary)' }} />
                <select value={mapping[h] || 'skip'} onChange={e => setMapping(prev => ({ ...prev, [h]: e.target.value === 'skip' ? undefined : e.target.value }))}
                  className="flex-1 px-2 py-1 rounded text-xs" style={{ ...inputStyle }} data-testid={`mapping-${h}`}>
                  <option value="skip">-- Skip --</option>
                  {TARGETS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            ))}
          </div>

          {analysis.sample_rows?.length > 0 && (
            <div className="p-3 rounded-lg overflow-x-auto" style={{ background: 'rgba(128,128,128,0.04)' }}>
              <div className="text-[10px] font-bold mb-1" style={{ color: 'var(--aurem-text-secondary)' }}>Preview (first row):</div>
              <div className="flex gap-3 text-[10px] font-mono" style={{ color: 'var(--aurem-text)' }}>
                {analysis.sample_rows[0]?.map((v, i) => <span key={i}>{analysis.headers[i]}: <b>{v}</b></span>)}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button onClick={() => setStep('upload')} className="px-4 py-2 rounded-lg text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>Back</button>
            <button onClick={executeImport} disabled={importing}
              className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: '#FF6B00' }} data-testid="execute-import-btn">
              {importing ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              {importing ? 'Importing...' : `Import ${analysis.row_count} ${dataType}`}
            </button>
          </div>
        </>
      )}

      {step === 'done' && result && (
        <div className="text-center py-6">
          <CheckCircle size={48} className="mx-auto mb-3 text-emerald-500" />
          <h3 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>Import Successful</h3>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>
            {result.imported} {result.type} imported into AUREM
          </p>
          <button onClick={onDone} className="mt-4 px-6 py-2 rounded-lg text-sm font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355]" data-testid="import-done-btn">
            Done
          </button>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* ADD PRODUCT MODAL                                          */
/* ═══════════════════════════════════════════════════════════ */
function AddProductModal({ token, onClose, onDone }) {
  const [name, setName] = useState('');
  const [price, setPrice] = useState(0);
  const [sku, setSku] = useState('');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [qty, setQty] = useState(0);
  const [saving, setSaving] = useState(false);
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#D4AF37]";
  const inputStyle = { background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' };

  const submit = async () => {
    if (!name.trim() || price <= 0) return;
    setSaving(true);
    const res = await fetch(`${API}/api/universal/products`, {
      method: 'POST', headers,
      body: JSON.stringify({ name, price, sku, category, description, inventory_quantity: qty }),
    });
    if (res.ok) onDone();
    setSaving(false);
  };

  return (
    <div className="aurem-glass-card p-6 rounded-2xl space-y-4" data-testid="add-product-modal">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>Add Product</h2>
        <button onClick={onClose}><X size={18} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Name *</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Product name" className={inputCls} style={inputStyle} data-testid="product-name-input" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Price ($) *</label>
          <input type="number" value={price} onChange={e => setPrice(parseFloat(e.target.value) || 0)} className={inputCls} style={inputStyle} data-testid="product-price-input" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>SKU</label>
          <input value={sku} onChange={e => setSku(e.target.value)} className={inputCls} style={inputStyle} data-testid="product-sku-input" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Category</label>
          <input value={category} onChange={e => setCategory(e.target.value)} className={inputCls} style={inputStyle} data-testid="product-category-input" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Stock</label>
          <input type="number" value={qty} onChange={e => setQty(parseInt(e.target.value) || 0)} className={inputCls} style={inputStyle} data-testid="product-qty-input" />
        </div>
      </div>
      <div>
        <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Description</label>
        <input value={description} onChange={e => setDescription(e.target.value)} className={inputCls} style={inputStyle} data-testid="product-desc-input" />
      </div>
      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 rounded-lg text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>Cancel</button>
        <button onClick={submit} disabled={saving || !name.trim() || price <= 0}
          className="px-6 py-2 rounded-lg text-sm font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] disabled:opacity-50"
          data-testid="submit-product-btn">
          {saving ? 'Adding...' : 'Add Product'}
        </button>
      </div>
    </div>
  );
}
