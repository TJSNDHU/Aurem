/* AdminAutoFixer.jsx — Pillar 3 Auto-Fix Orchestration Dashboard
 * ================================================================
 * End-to-end wired to real backend endpoints from /app/backend/routers/ai_repair_router.py:
 *   GET  /api/repair/pending   — list of fixes (all statuses, grouped by status)
 *   POST /api/repair/{fix_id}/approve
 *   POST /api/repair/{fix_id}/reject
 *   GET  /api/repair/history   — per-URL summary
 *
 * No mock data. No placeholders.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Loader2, CheckCircle, XCircle, Clock, Activity, ShieldCheck, Zap, Code, TrendingUp, AlertTriangle } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  pending:  { color: '#F59E0B', icon: Clock,        label: 'Pending Review' },
  approved: { color: '#3b82f6', icon: CheckCircle,  label: 'Approved' },
  deployed: { color: '#22C55E', icon: CheckCircle,  label: 'Deployed' },
  rejected: { color: '#EF4444', icon: XCircle,      label: 'Rejected' },
  failed:   { color: '#DC2626', icon: AlertTriangle,label: 'Failed' },
};

const CATEGORY_META = {
  seo:           { color: '#3b82f6', icon: TrendingUp,  label: 'SEO' },
  accessibility: { color: '#22C55E', icon: ShieldCheck, label: 'Accessibility' },
  geo:           { color: '#D4AF37', icon: Zap,         label: 'GEO / Schema' },
  performance:   { color: '#FF8A3D', icon: Activity,    label: 'Performance' },
  security:      { color: '#EF4444', icon: ShieldCheck, label: 'Security' },
};

function authHeaders() {
  // Use the same token storage as AdminLogin (secureTokenStore)
  // Priority: sessionStorage platform_token → localStorage platform_token → legacy fallbacks
  const token =
    sessionStorage.getItem('platform_token') ||
    localStorage.getItem('platform_token') ||
    localStorage.getItem('aurem_admin_token') ||
    sessionStorage.getItem('aurem_admin_token') ||
    localStorage.getItem('token') ||
    '';
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AdminAutoFixer() {
  const [loading, setLoading] = useState(true);
  const [fixes, setFixes] = useState([]);
  const [history, setHistory] = useState([]);
  const [activeTab, setActiveTab] = useState('pending');
  const [busyFixId, setBusyFixId] = useState(null);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [pendingRes, historyRes] = await Promise.all([
        fetch(`${API}/api/repair/pending`, { headers: authHeaders() }),
        fetch(`${API}/api/repair/history`, { headers: authHeaders() }),
      ]);
      if (!pendingRes.ok) throw new Error(`repair/pending HTTP ${pendingRes.status}`);
      const pendingData = await pendingRes.json();
      setFixes(Array.isArray(pendingData.fixes) ? pendingData.fixes : []);
      if (historyRes.ok) {
        const h = await historyRes.json();
        setHistory(Array.isArray(h.history) ? h.history : []);
      }
      setLastRefresh(new Date());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 15000);
    return () => clearInterval(iv);
  }, [load]);

  const handleApprove = async (fixId) => {
    setBusyFixId(fixId);
    try {
      const r = await fetch(`${API}/api/repair/${fixId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
      });
      if (!r.ok) throw new Error(`approve HTTP ${r.status}`);
      await load();
    } catch (e) {
      setError(`Approve failed: ${e.message}`);
    } finally {
      setBusyFixId(null);
    }
  };

  const handleReject = async (fixId) => {
    setBusyFixId(fixId);
    try {
      const r = await fetch(`${API}/api/repair/${fixId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
      });
      if (!r.ok) throw new Error(`reject HTTP ${r.status}`);
      await load();
    } catch (e) {
      setError(`Reject failed: ${e.message}`);
    } finally {
      setBusyFixId(null);
    }
  };

  // Grouping & stats
  const grouped = useMemo(() => {
    const buckets = { pending: [], approved: [], deployed: [], rejected: [], failed: [] };
    for (const f of fixes) {
      const s = f.status || 'pending';
      (buckets[s] || (buckets[s] = [])).push(f);
    }
    return buckets;
  }, [fixes]);

  const stats = useMemo(() => ({
    total:    fixes.length,
    pending:  grouped.pending.length,
    deployed: grouped.deployed.length,
    rejected: grouped.rejected.length,
    approved: grouped.approved.length,
  }), [fixes, grouped]);

  const totalHistoryDeployed = history.reduce((sum, h) => sum + (h.deployed || 0), 0);
  const uniqueUrls = history.length;

  const visibleList = grouped[activeTab] || [];

  if (loading) {
    return (
      <div style={STYLES.page}>
        <div style={STYLES.centerCard}>
          <Loader2 size={32} className="animate-spin" style={{ color: '#D4AF37' }} />
          <div style={{ marginTop: 12, color: '#94a3b8' }}>Loading auto-fix orchestration…</div>
        </div>
      </div>
    );
  }

  return (
    <div style={STYLES.page} data-testid="admin-auto-fixer-page">
      <div style={STYLES.header}>
        <div>
          <h1 style={STYLES.h1}>Auto-Fixer Command Center</h1>
          <div style={STYLES.subline}>
            Pillar 3 · Sentinel → Shannon RCA → Patch generation → Human approval → HMAC-signed deploy
            {lastRefresh && <span style={{ marginLeft: 12, opacity: 0.6 }}>
              · refreshed {lastRefresh.toLocaleTimeString()}</span>}
          </div>
        </div>
        <button
          onClick={load}
          data-testid="auto-fixer-refresh-btn"
          style={STYLES.refreshBtn}
        >
          <Activity size={14} /> Refresh
        </button>
      </div>

      {error && (
        <div data-testid="auto-fixer-error" style={STYLES.errorBanner}>
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {/* Stats grid */}
      <div style={STYLES.statGrid} data-testid="auto-fixer-stats">
        <StatCard label="All in Queue" value={stats.total}    color="#D4AF37" testid="stat-total" />
        <StatCard label="Pending Review" value={stats.pending}  color="#F59E0B" testid="stat-pending" />
        <StatCard label="Deployed"       value={stats.deployed} color="#22C55E" testid="stat-deployed" />
        <StatCard label="Rejected"       value={stats.rejected} color="#EF4444" testid="stat-rejected" />
        <StatCard label="Sites Monitored" value={uniqueUrls}    color="#3b82f6" testid="stat-urls" />
        <StatCard label="All-Time Fixes Deployed" value={totalHistoryDeployed} color="#a855f7" testid="stat-alltime" />
      </div>

      {/* Tabs */}
      <div style={STYLES.tabs} data-testid="auto-fixer-tabs">
        {['pending', 'approved', 'deployed', 'rejected', 'failed'].map((t) => {
          const meta = STATUS_META[t];
          const active = activeTab === t;
          const count = grouped[t]?.length || 0;
          return (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              data-testid={`auto-fixer-tab-${t}`}
              style={{
                ...STYLES.tab,
                ...(active ? STYLES.tabActive(meta.color) : {}),
              }}
            >
              <meta.icon size={14} style={{ color: meta.color }} />
              <span style={{ textTransform: 'capitalize' }}>{t}</span>
              <span style={STYLES.tabBadge}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* Fix list */}
      <div style={STYLES.list} data-testid="auto-fixer-list">
        {visibleList.length === 0 ? (
          <div style={STYLES.empty} data-testid="auto-fixer-empty">
            Nothing in <strong style={{ textTransform: 'capitalize' }}>{activeTab}</strong> queue right now.
          </div>
        ) : (
          visibleList.map((fix) => (
            <FixCard
              key={fix.fix_id}
              fix={fix}
              busy={busyFixId === fix.fix_id}
              onApprove={() => handleApprove(fix.fix_id)}
              onReject={() => handleReject(fix.fix_id)}
              showActions={activeTab === 'pending'}
            />
          ))
        )}
      </div>

      {/* Per-URL history */}
      {history.length > 0 && (
        <div style={STYLES.historySection} data-testid="auto-fixer-history">
          <h2 style={STYLES.h2}>Per-Site Repair History</h2>
          <div style={STYLES.historyGrid}>
            {history.map((h, i) => (
              <div key={i} style={STYLES.historyCard}>
                <div style={STYLES.historyUrl}>{h.url}</div>
                <div style={STYLES.historyStats}>
                  <span title="Total fixes"      style={{ color: '#D4AF37' }}>{h.total_fixes} total</span>
                  <span title="Deployed"         style={{ color: '#22C55E' }}>{h.deployed} deployed</span>
                  <span title="Pending"          style={{ color: '#F59E0B' }}>{h.pending} pending</span>
                  <span title="Rejected"         style={{ color: '#EF4444' }}>{h.rejected} rejected</span>
                </div>
                <div style={STYLES.historyCategories}>
                  {h.seo_fixes > 0 && <Pill color={CATEGORY_META.seo.color}>SEO · {h.seo_fixes}</Pill>}
                  {h.a11y_fixes > 0 && <Pill color={CATEGORY_META.accessibility.color}>A11Y · {h.a11y_fixes}</Pill>}
                  {h.geo_fixes > 0 && <Pill color={CATEGORY_META.geo.color}>GEO · {h.geo_fixes}</Pill>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color, testid }) {
  return (
    <div style={STYLES.statCard(color)} data-testid={testid}>
      <div style={STYLES.statValue(color)}>{value}</div>
      <div style={STYLES.statLabel}>{label}</div>
    </div>
  );
}

function Pill({ color, children }) {
  return (
    <span style={{
      fontSize: 11, padding: '3px 8px', borderRadius: 999,
      background: `${color}22`, color, fontWeight: 600,
      border: `1px solid ${color}44`,
    }}>{children}</span>
  );
}

function FixCard({ fix, busy, onApprove, onReject, showActions }) {
  const status = fix.status || 'pending';
  const statusMeta = STATUS_META[status] || STATUS_META.pending;
  const cat = fix.category || 'seo';
  const catMeta = CATEGORY_META[cat] || CATEGORY_META.seo;
  const CatIcon = catMeta.icon;
  return (
    <div style={STYLES.fixCard} data-testid={`fix-card-${fix.fix_id}`}>
      <div style={STYLES.fixHeader}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ ...STYLES.catChip, background: `${catMeta.color}22`, color: catMeta.color, borderColor: `${catMeta.color}44` }}>
            <CatIcon size={12} /> {catMeta.label}
          </span>
          <span style={{ fontWeight: 600, color: '#e2e8f0' }}>{fix.label || fix.fix_type}</span>
        </div>
        <span style={{ color: statusMeta.color, fontSize: 12, fontWeight: 600 }}>
          {statusMeta.label}
        </span>
      </div>

      <div style={STYLES.fixMeta}>
        <span data-testid={`fix-url-${fix.fix_id}`}>🌐 {fix.scan_url?.slice(0, 48) || 'unknown'}</span>
        {fix.severity && <span>· severity: <strong>{fix.severity}</strong></span>}
        <span>· {new Date(fix.created_at).toLocaleString()}</span>
        {fix.origin_status && <span>· origin: <strong>{fix.origin_status}</strong></span>}
      </div>

      {fix.fix_code && (
        <pre style={STYLES.codeBlock} data-testid={`fix-code-${fix.fix_id}`}>
          <code>{String(fix.fix_code).slice(0, 600)}</code>
        </pre>
      )}

      {showActions && (
        <div style={STYLES.fixActions}>
          <button
            onClick={onApprove}
            disabled={busy}
            data-testid={`fix-approve-${fix.fix_id}`}
            style={{ ...STYLES.approveBtn, opacity: busy ? 0.5 : 1 }}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
            Approve & Deploy
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            data-testid={`fix-reject-${fix.fix_id}`}
            style={{ ...STYLES.rejectBtn, opacity: busy ? 0.5 : 1 }}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

const STYLES = {
  page: {
    minHeight: '100vh', background: '#0B0D10', color: '#e2e8f0',
    padding: '32px 40px', fontFamily: 'ui-sans-serif, system-ui, sans-serif',
  },
  centerCard: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', minHeight: '60vh',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    marginBottom: 24, gap: 16,
  },
  h1: { fontSize: 28, fontWeight: 700, margin: 0, color: '#D4AF37', letterSpacing: -0.5 },
  h2: { fontSize: 18, fontWeight: 600, margin: '32px 0 16px', color: '#cbd5e1' },
  subline: { fontSize: 13, color: '#94a3b8', marginTop: 6 },
  refreshBtn: {
    background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155',
    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
    display: 'flex', gap: 6, alignItems: 'center', fontSize: 12, fontWeight: 600,
  },
  errorBanner: {
    padding: '10px 14px', background: '#7f1d1d', border: '1px solid #b91c1c',
    borderRadius: 8, color: '#fecaca', display: 'flex', gap: 8, alignItems: 'center',
    marginBottom: 20, fontSize: 13,
  },
  statGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))',
    gap: 12, marginBottom: 24,
  },
  statCard: (color) => ({
    background: '#0f1419', border: `1px solid ${color}33`, borderRadius: 12,
    padding: 16, transition: 'transform 0.15s',
  }),
  statValue: (color) => ({ fontSize: 32, fontWeight: 700, color, lineHeight: 1.1 }),
  statLabel: { fontSize: 12, color: '#94a3b8', marginTop: 6, textTransform: 'uppercase', letterSpacing: 0.4 },
  tabs: {
    display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap',
    borderBottom: '1px solid #1e293b', paddingBottom: 12,
  },
  tab: {
    background: 'transparent', color: '#94a3b8', border: '1px solid transparent',
    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
    display: 'flex', gap: 6, alignItems: 'center', fontSize: 13, fontWeight: 500,
  },
  tabActive: (color) => ({
    background: `${color}18`, color: '#e2e8f0', border: `1px solid ${color}66`,
  }),
  tabBadge: {
    background: '#1e293b', color: '#cbd5e1', padding: '1px 8px',
    borderRadius: 999, fontSize: 11, fontWeight: 700,
  },
  list: { display: 'flex', flexDirection: 'column', gap: 12 },
  empty: {
    padding: 40, textAlign: 'center', color: '#64748b',
    background: '#0f1419', border: '1px dashed #1e293b', borderRadius: 12,
  },
  fixCard: {
    background: '#0f1419', border: '1px solid #1e293b', borderRadius: 12, padding: 16,
  },
  fixHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10,
  },
  catChip: {
    fontSize: 11, padding: '3px 10px', borderRadius: 999, fontWeight: 600,
    display: 'flex', gap: 4, alignItems: 'center', border: '1px solid',
  },
  fixMeta: {
    fontSize: 12, color: '#64748b', marginBottom: 10,
    display: 'flex', gap: 10, flexWrap: 'wrap',
  },
  codeBlock: {
    background: '#000', border: '1px solid #1e293b', borderRadius: 8,
    padding: 12, fontSize: 12, overflow: 'auto', maxHeight: 180,
    color: '#93c5fd', fontFamily: 'ui-monospace, Menlo, monospace', margin: '8px 0',
  },
  fixActions: { display: 'flex', gap: 8, marginTop: 10 },
  approveBtn: {
    background: '#166534', color: '#d1fae5', border: '1px solid #22C55E55',
    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
    display: 'flex', gap: 6, alignItems: 'center', fontSize: 12, fontWeight: 600,
  },
  rejectBtn: {
    background: '#7f1d1d', color: '#fecaca', border: '1px solid #EF444455',
    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
    display: 'flex', gap: 6, alignItems: 'center', fontSize: 12, fontWeight: 600,
  },
  historySection: { marginTop: 40 },
  historyGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: 12,
  },
  historyCard: {
    background: '#0f1419', border: '1px solid #1e293b', borderRadius: 10, padding: 14,
  },
  historyUrl: {
    fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 8,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  historyStats: {
    display: 'flex', gap: 10, fontSize: 12, marginBottom: 8, flexWrap: 'wrap',
  },
  historyCategories: { display: 'flex', gap: 6, flexWrap: 'wrap' },
};
