/**
 * Customer Health Panel — Admin Diagnostics
 * ==========================================
 * - Top: BIN search + "Run Now" + auto-scan badge
 * - Tenant list (status / failed checks)
 * - Detail view: every check 🟢/🔴, repair history,
 *   manual fix buttons, force-full-repair button
 *
 * Backend: /api/admin/diagnostics/{summary,all,run/:bid,fix/:bid,
 *           customer/:bid, fix-action/:bid/:action, repair-log/:bid}
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  Activity, Search, Play, Wrench, RefreshCw, AlertTriangle,
  CheckCircle2, XCircle, Clock, Database, Shield, Globe, ChevronRight,
} from 'lucide-react';

const API = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

const getAdminToken = () =>
  sessionStorage.getItem('platform_token') ||
  localStorage.getItem('platform_token') ||
  localStorage.getItem('aurem_admin_token') ||
  sessionStorage.getItem('aurem_admin_token') ||
  localStorage.getItem('token') ||
  '';

const STATUS_STYLE = {
  healthy:   { color: '#4AD4A0', label: 'HEALTHY',  icon: CheckCircle2 },
  degraded:  { color: '#F0A030', label: 'DEGRADED', icon: AlertTriangle },
  critical:  { color: '#E0524A', label: 'CRITICAL', icon: XCircle },
  error:     { color: '#7A7468', label: 'ERROR',    icon: XCircle },
  unknown:   { color: '#7A7468', label: 'UNKNOWN',  icon: Clock },
};

const CHECK_LABELS = {
  db_user:         { label: 'DB · platform_users',     group: 'DB'    },
  db_billing:      { label: 'DB · aurem_billing',      group: 'DB'    },
  db_workspace:    { label: 'DB · aurem_workspaces',   group: 'DB'    },
  db_onboarding:   { label: 'DB · aurem_onboarding',   group: 'DB'    },
  db_tenant:       { label: 'DB · tenant_customers',   group: 'DB'    },
  stripe_seeded:   { label: 'Stripe customer seeded',  group: 'DB'    },
  jwt_works:       { label: 'JWT mint + decode',       group: 'AUTH'  },
  bin_valid:       { label: 'BIN matches platform_users', group: 'AUTH' },
  route_my:        { label: '/my route',               group: 'ROUTE' },
  route_onboarding:{ label: '/api/onboarding/status',  group: 'ROUTE' },
  route_billing:   { label: '/api/aurem-billing/status', group: 'ROUTE' },
  route_bin:       { label: '/api/business-id/mine',   group: 'ROUTE' },
  pixel_seeded:    { label: 'Pixel key present',       group: 'PIXEL' },
  blast_active:    { label: 'Blast/outreach activity', group: 'PIXEL' },
};

const MANUAL_FIXES = [
  { action: 'reseed_from_legacy',     label: 'Reseed from Legacy Users', highlight: true },
  { action: 'seed_billing_record',    label: 'Seed Billing'      },
  { action: 'create_workspace',       label: 'Create Workspace'  },
  { action: 'init_onboarding',        label: 'Init Onboarding'   },
  { action: 'seed_tenant_record',     label: 'Seed Tenant'       },
  { action: 'create_stripe_customer', label: 'Create Stripe'     },
  { action: 'reset_auth_tokens',      label: 'Reset Tokens'      },
];


// ─── helpers ────────────────────────────────────────────────────
const authedFetch = (url, opts = {}) => {
  const token = getAdminToken();
  return fetch(`${API}${url}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
  });
};

const fmtTime = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch { return iso; }
};


// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════
export default function CustomerHealthPanel() {
  const [summary, setSummary] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [filter, setFilter]   = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState('');

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3500);
  };

  const loadSummary = useCallback(async () => {
    try {
      const r = await authedFetch('/api/admin/diagnostics/summary');
      if (r.ok) setSummary(await r.json());
    } catch (e) { /* noop */ }
  }, []);

  const loadTenants = useCallback(async () => {
    setLoading(true);
    try {
      const q = statusFilter ? `?status=${statusFilter}&limit=300` : '?limit=300';
      const r = await authedFetch(`/api/admin/diagnostics/all${q}`);
      if (r.ok) {
        const j = await r.json();
        setTenants(j.tenants || []);
      }
    } catch (e) { /* noop */ }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => {
    loadSummary();
    loadTenants();
  }, [loadSummary, loadTenants]);

  const runOne = async (bid) => {
    if (!bid) return;
    setScanning(true);
    try {
      const r = await authedFetch(`/api/admin/diagnostics/run/${bid}`,
        { method: 'POST' });
      if (r.ok) {
        const j = await r.json();
        showToast(`✓ ${bid}: ${j.status || 'checked'} (${(j.failed || []).length} failures)`);
        await loadDetail(bid);
        await loadTenants();
      } else {
        showToast(`✗ ${bid}: ${r.status}`);
      }
    } catch (e) {
      showToast(`✗ ${e.message}`);
    }
    setScanning(false);
  };

  const runAll = async () => {
    setScanning(true);
    showToast('Scanning all tenants…');
    try {
      const r = await authedFetch('/api/admin/diagnostics/run-all',
        { method: 'POST' });
      if (r.ok) {
        const j = await r.json();
        showToast(`✓ Scanned ${j.scanned} tenants`);
        await loadSummary();
        await loadTenants();
      } else {
        showToast(`✗ Scan failed: ${r.status}`);
      }
    } catch (e) {
      showToast(`✗ ${e.message}`);
    }
    setScanning(false);
  };

  const loadDetail = async (bid) => {
    try {
      const r = await authedFetch(`/api/admin/diagnostics/customer/${bid}`);
      if (r.ok) setSelected(await r.json());
    } catch (e) { /* noop */ }
  };

  const triggerRepair = async (bid) => {
    if (!bid) return;
    setBusy(true);
    showToast(`Repairing ${bid}…`);
    try {
      const r = await authedFetch(`/api/admin/diagnostics/fix/${bid}`,
        { method: 'POST' });
      if (r.ok) {
        const j = await r.json();
        showToast(`✓ ${bid}: ${j.outcome || j.post_status} — applied ${(j.applied || []).length} fixes`);
        await loadDetail(bid);
        await loadTenants();
      } else {
        showToast(`✗ Repair failed: ${r.status}`);
      }
    } catch (e) {
      showToast(`✗ ${e.message}`);
    }
    setBusy(false);
  };

  const manualFix = async (bid, action) => {
    setBusy(true);
    try {
      const r = await authedFetch(
        `/api/admin/diagnostics/fix-action/${bid}/${action}`,
        { method: 'POST' }
      );
      if (r.ok) {
        const j = await r.json();
        showToast(j.applied ? `✓ ${action} applied` : `✗ ${action} failed`);
        await loadDetail(bid);
        await loadTenants();
      } else {
        showToast(`✗ ${action}: ${r.status}`);
      }
    } catch (e) {
      showToast(`✗ ${e.message}`);
    }
    setBusy(false);
  };

  const filtered = tenants.filter(t =>
    !filter || (t.business_id || '').toLowerCase().includes(filter.toLowerCase())
    || (t.email || '').toLowerCase().includes(filter.toLowerCase())
  );

  const counts = (summary && summary.counts) || {};

  // ─── render ────────────────────────────────────────────────────
  return (
    <div data-testid="customer-health-panel" style={{
      padding: '32px 40px', maxWidth: 1480, margin: '0 auto',
      fontFamily: 'Inter, system-ui, sans-serif', color: '#0F1115',
    }}>
      {toast && (
        <div data-testid="health-toast" style={{
          position: 'fixed', top: 84, right: 32, zIndex: 1000,
          padding: '12px 18px', background: '#0F1115', color: '#F0A030',
          borderRadius: 8, fontSize: 13, fontWeight: 600,
          boxShadow: '0 8px 30px rgba(0,0,0,.25)',
        }}>
          {toast}
        </div>
      )}

      <header style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <Activity size={22} style={{ color: '#F0A030' }} />
          <h1 style={{
            fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', margin: 0,
          }}>Customer Health</h1>
        </div>
        <p style={{ color: '#7A7468', fontSize: 14, margin: 0 }}>
          Auto-scan every 30 min · Detect → Diagnose → Council → Fix → Verify
        </p>
      </header>

      {/* ─── SUMMARY STRIP ─── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
        gap: 14, marginBottom: 24,
      }}>
        <SummaryCard label="Scanned" value={summary?.scanned ?? '—'}
                     icon={Database} color="#4A8FD4" />
        <SummaryCard label="Healthy"  value={counts.healthy ?? 0}
                     icon={CheckCircle2} color="#4AD4A0" />
        <SummaryCard label="Degraded" value={counts.degraded ?? 0}
                     icon={AlertTriangle} color="#F0A030" />
        <SummaryCard label="Critical" value={counts.critical ?? 0}
                     icon={XCircle} color="#E0524A" />
        <SummaryCard label="Last Scan"
                     value={summary?.checked_at ? fmtTime(summary.checked_at) : '—'}
                     icon={Clock} color="#7A7468" small />
      </div>

      {/* ─── SEARCH BAR ─── */}
      <div style={{
        display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16,
        flexWrap: 'wrap',
      }}>
        <div style={{ position: 'relative', flex: '1 1 320px', minWidth: 280 }}>
          <Search size={16} style={{
            position: 'absolute', top: 13, left: 12, color: '#7A7468',
          }} />
          <input
            data-testid="health-bin-input"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by BIN or email (e.g. RERO-3DEJ)"
            style={{
              width: '100%', padding: '12px 14px 12px 36px',
              border: '1px solid #E5E2DD', borderRadius: 8,
              fontSize: 14, outline: 'none', background: '#FAF9F6',
            }}
          />
        </div>
        <select
          data-testid="health-status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{
            padding: '12px 14px', border: '1px solid #E5E2DD',
            borderRadius: 8, fontSize: 14, background: '#FAF9F6',
          }}>
          <option value="">All status</option>
          <option value="healthy">Healthy</option>
          <option value="degraded">Degraded</option>
          <option value="critical">Critical</option>
        </select>
        <button
          data-testid="health-run-bin-btn"
          onClick={() => runOne(filter.trim())}
          disabled={!filter.trim() || scanning}
          style={btnPrimary(scanning)}>
          <Play size={14} />
          Run on BIN
        </button>
        <button
          data-testid="health-run-all-btn"
          onClick={runAll}
          disabled={scanning}
          style={btnSecondary(scanning)}>
          <RefreshCw size={14} />
          Scan All
        </button>
      </div>

      {/* ─── TENANT LIST ─── */}
      <div style={{
        display: 'grid', gridTemplateColumns: selected ? '1fr 1.4fr' : '1fr',
        gap: 20,
      }}>
        <div style={cardStyle()}>
          <div style={listHeader()}>
            <span>Tenant</span>
            <span>Status</span>
            <span>Failed</span>
            <span>Last Check</span>
            <span></span>
          </div>
          {loading && <div style={{ padding: 24, color: '#7A7468' }}>Loading…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ padding: 24, color: '#7A7468' }}>
              No tenant data — click "Scan All" to populate.
            </div>
          )}
          {filtered.map((t) => (
            <TenantRow
              key={t.business_id}
              tenant={t}
              active={selected?.business_id === t.business_id}
              onClick={() => loadDetail(t.business_id)} />
          ))}
        </div>

        {selected && (
          <DetailPane
            data={selected}
            busy={busy || scanning}
            onClose={() => setSelected(null)}
            onRunNow={() => runOne(selected.business_id)}
            onRepair={() => triggerRepair(selected.business_id)}
            onManualFix={(action) => manualFix(selected.business_id, action)} />
        )}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════
function SummaryCard({ label, value, icon: Icon, color, small }) {
  return (
    <div data-testid={`health-card-${label.toLowerCase().replace(/\W+/g, '-')}`}
         style={{
      padding: 18, background: '#FFFFFF', border: '1px solid #ECE9E2',
      borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: 8,
        background: `${color}18`, display: 'grid', placeItems: 'center',
      }}>
        <Icon size={18} style={{ color }} />
      </div>
      <div>
        <div style={{ fontSize: 11, color: '#7A7468', textTransform: 'uppercase',
                       letterSpacing: '0.08em', fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: small ? 13 : 22, fontWeight: 700, color: '#0F1115',
                       marginTop: 2 }}>{value}</div>
      </div>
    </div>
  );
}

function TenantRow({ tenant, active, onClick }) {
  const meta = STATUS_STYLE[tenant.status] || STATUS_STYLE.unknown;
  const Icon = meta.icon;
  const failedCount = (tenant.failed || []).length;
  return (
    <div
      data-testid={`tenant-row-${tenant.business_id}`}
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '1.4fr 1fr 0.8fr 1.2fr 24px',
        alignItems: 'center', gap: 8,
        padding: '14px 18px',
        borderBottom: '1px solid #F2EFE9',
        cursor: 'pointer',
        background: active ? '#FAF6EC' : 'transparent',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = '#FAF9F6'; }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}>
      <div>
        <div style={{ fontWeight: 600, fontSize: 14, color: '#0F1115' }}>
          {tenant.business_id}
        </div>
        <div style={{ fontSize: 12, color: '#7A7468', marginTop: 2 }}>
          {tenant.email || '—'}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon size={14} style={{ color: meta.color }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: meta.color }}>
          {meta.label}
        </span>
      </div>
      <div style={{ fontSize: 13, color: failedCount > 0 ? '#E0524A' : '#7A7468' }}>
        {failedCount > 0 ? `${failedCount} ✕` : '—'}
      </div>
      <div style={{ fontSize: 12, color: '#7A7468' }}>
        {fmtTime(tenant.checked_at)}
      </div>
      <ChevronRight size={16} style={{ color: '#C9C5BD' }} />
    </div>
  );
}

function DetailPane({ data, busy, onClose, onRunNow, onRepair, onManualFix }) {
  const cur = data.current || {};
  const checks = cur.checks || {};
  const meta = STATUS_STYLE[cur.status] || STATUS_STYLE.unknown;
  const StatusIcon = meta.icon;
  const groups = ['DB', 'AUTH', 'ROUTE', 'PIXEL'];

  return (
    <div data-testid="health-detail-pane" style={cardStyle()}>
      <div style={{
        padding: 18, borderBottom: '1px solid #ECE9E2',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 12, color: '#7A7468', marginBottom: 2 }}>
            BUSINESS ID
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#0F1115' }}>
            {data.business_id}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusIcon size={14} style={{ color: meta.color }} />
          <span style={{
            padding: '5px 10px', borderRadius: 6,
            background: `${meta.color}18`, color: meta.color,
            fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
          }}>{meta.label}</span>
          <button
            onClick={onClose}
            data-testid="health-detail-close"
            style={{
              marginLeft: 8, padding: '6px 10px', fontSize: 12,
              background: 'transparent', border: '1px solid #E5E2DD',
              borderRadius: 6, cursor: 'pointer',
            }}>Close</button>
        </div>
      </div>

      {/* ─── Action buttons ─── */}
      <div style={{ padding: 18, display: 'flex', gap: 10, flexWrap: 'wrap',
                     borderBottom: '1px solid #ECE9E2' }}>
        <button
          data-testid="health-detail-run-btn"
          onClick={onRunNow} disabled={busy}
          style={btnPrimary(busy)}>
          <Play size={14} />
          Run Check Now
        </button>
        <button
          data-testid="health-detail-repair-btn"
          onClick={onRepair} disabled={busy}
          style={{ ...btnSecondary(busy), background: '#F0A030', color: '#0F1115',
                    borderColor: '#F0A030' }}>
          <Wrench size={14} />
          Force Full Repair
        </button>
      </div>

      {/* ─── Check grid ─── */}
      <div style={{ padding: 18, borderBottom: '1px solid #ECE9E2' }}>
        {groups.map((g) => (
          <div key={g} style={{ marginBottom: 14 }}>
            <div style={{
              fontSize: 11, fontWeight: 700, color: '#7A7468',
              letterSpacing: '0.1em', marginBottom: 8,
            }}>{g}</div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 8,
            }}>
              {Object.entries(CHECK_LABELS)
                .filter(([k, v]) => v.group === g)
                .map(([k, v]) => {
                  const passed = !!checks[k];
                  return (
                    <div key={k}
                         data-testid={`health-check-${k}`}
                         style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '8px 12px', background: '#FAF9F6',
                          borderRadius: 6, fontSize: 13,
                          border: `1px solid ${passed ? '#D6EFE3' : '#F4D2CE'}`,
                    }}>
                      {passed
                        ? <CheckCircle2 size={14} style={{ color: '#4AD4A0' }} />
                        : <XCircle size={14} style={{ color: '#E0524A' }} />}
                      <span style={{ color: passed ? '#0F1115' : '#7A2E2A' }}>
                        {v.label}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        ))}
      </div>

      {/* ─── Manual Fix Buttons ─── */}
      <div style={{ padding: 18, borderBottom: '1px solid #ECE9E2' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#7A7468',
                        letterSpacing: '0.1em', marginBottom: 10 }}>
          MANUAL FIX BUTTONS
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {MANUAL_FIXES.map((mf) => (
            <button
              key={mf.action}
              data-testid={`health-manual-fix-${mf.action}`}
              onClick={() => onManualFix(mf.action)}
              disabled={busy}
              style={{
                padding: '8px 12px', fontSize: 12, fontWeight: 600,
                background: mf.highlight ? '#0F1115' : '#FFFFFF',
                color: mf.highlight ? '#F0A030' : '#0F1115',
                border: `1px solid ${mf.highlight ? '#0F1115' : '#E5E2DD'}`,
                borderRadius: 6, cursor: busy ? 'not-allowed' : 'pointer',
                opacity: busy ? 0.6 : 1,
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
              <Wrench size={12} />
              {mf.label}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Repair history ─── */}
      <div style={{ padding: 18 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#7A7468',
                        letterSpacing: '0.1em', marginBottom: 10 }}>
          REPAIR HISTORY (last 20)
        </div>
        {(data.repairs || []).length === 0 && (
          <div style={{ fontSize: 13, color: '#7A7468' }}>No repair attempts yet.</div>
        )}
        {(data.repairs || []).map((r, i) => (
          <div key={i}
               data-testid={`health-repair-row-${i}`}
               style={{
            padding: '10px 12px', background: '#FAF9F6',
            borderRadius: 6, marginBottom: 6, fontSize: 12,
            display: 'grid', gridTemplateColumns: '1fr auto auto',
            gap: 10, alignItems: 'center',
          }}>
            <div>
              <div style={{ fontWeight: 600, color: '#0F1115' }}>
                {r.fix_name}
              </div>
              <div style={{ color: '#7A7468', marginTop: 2 }}>
                {r.description}
              </div>
            </div>
            <div style={{
              padding: '3px 8px', borderRadius: 4, fontWeight: 600,
              fontSize: 10, letterSpacing: '0.05em',
              color: outcomeColor(r.outcome).color,
              background: outcomeColor(r.outcome).bg,
            }}>{(r.outcome || '').toUpperCase()}</div>
            <div style={{ color: '#7A7468' }}>{fmtTime(r.ts)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


// ─── styling helpers ──────────────────────────────────────────
const cardStyle = () => ({
  background: '#FFFFFF', border: '1px solid #ECE9E2',
  borderRadius: 10, overflow: 'hidden',
});

const listHeader = () => ({
  display: 'grid',
  gridTemplateColumns: '1.4fr 1fr 0.8fr 1.2fr 24px',
  gap: 8, padding: '12px 18px', background: '#FAF9F6',
  fontSize: 11, color: '#7A7468', fontWeight: 700,
  letterSpacing: '0.08em', textTransform: 'uppercase',
  borderBottom: '1px solid #ECE9E2',
});

const btnPrimary = (busy) => ({
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '11px 16px', background: '#0F1115', color: '#F0A030',
  border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600,
  cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1,
});

const btnSecondary = (busy) => ({
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '11px 16px', background: '#FFFFFF', color: '#0F1115',
  border: '1px solid #0F1115', borderRadius: 8, fontSize: 13, fontWeight: 600,
  cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1,
});

const outcomeColor = (outcome) => {
  if (!outcome) return { color: '#7A7468', bg: '#F2EFE9' };
  if (outcome.includes('verified') || outcome.includes('approved')
      || outcome === 'auto_applied' || outcome === 'manual_applied') {
    return { color: '#4AD4A0', bg: '#E1F4EC' };
  }
  if (outcome.includes('rejected') || outcome.includes('failed')) {
    return { color: '#E0524A', bg: '#FCE8E5' };
  }
  return { color: '#F0A030', bg: '#FCEFD6' };
};
