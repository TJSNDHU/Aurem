/**
 * LuxeV2Pages.jsx — iter 325o
 *
 * 6 merged customer-portal pages built on the V2 design system.
 *
 *  Live Health   — health scores + scan trigger + incident resolve
 *                  (merges old Live Health + Security + Analytics)
 *  CRM           — leads CRUD + send-email + CSV export (merges
 *                  Outreach + Voice as per-row actions)
 *  Campaign      — workflows toggle + create + delete
 *  ORA           — agents + live chat
 *  Profile       — identity edit + activate pipeline + scan-schedule
 *                  + 2FA toggle + sessions revoke
 *  Settings      — branding edit + voice status + api key + sign-out
 *
 * All save/edit actions are REAL — they POST/PATCH/DELETE against the
 * backend, surface toasts on success/error, and rollback locally on
 * failure. No mocks.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, ShieldAlert, Trash2, Send, Plus, Power,
  RefreshCw, Copy, Save, Eye, EyeOff, LogOut, AlertCircle,
} from 'lucide-react';

import { v2api } from './v2api';
import { useV2Toast } from './useV2Toast';

/* ─────────────────────────────────────────────────────────────────
 * Shared atoms
 * ─────────────────────────────────────────────────────────────────*/

const PageHeader = ({ title, subtitle, right }) => (
  <header data-testid={`page-header-${title.toLowerCase().replace(/\s+/g, '-')}`}
          style={{ display: 'flex', justifyContent: 'space-between',
                   alignItems: 'flex-end', gap: 12, marginBottom: 4 }}>
    <div>
      <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--dash-text)' }}>{title}</h2>
      {subtitle && <div style={{ marginTop: 4, fontSize: 13, color: 'var(--dash-text-muted)' }}>{subtitle}</div>}
    </div>
    {right}
  </header>
);

const Btn = ({ children, onClick, variant = 'primary', loading, disabled,
               testid, type = 'button' }) => {
  const styles = {
    primary:   { background: 'var(--dash-purple)', color: '#fff' },
    secondary: { background: 'var(--dash-card)', color: 'var(--dash-text)', border: '1px solid var(--dash-border)' },
    danger:    { background: 'rgba(255,69,58,0.14)', color: 'var(--dash-red)', border: '1px solid rgba(255,69,58,0.3)' },
    ghost:     { background: 'transparent', color: 'var(--dash-text-muted)' },
  }[variant] || {};
  return (
    <button type={type}
            data-testid={testid}
            disabled={disabled || loading}
            onClick={onClick}
            style={{
              padding: '8px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              border: '0', cursor: (disabled || loading) ? 'not-allowed' : 'pointer',
              opacity: (disabled || loading) ? 0.6 : 1,
              display: 'inline-flex', alignItems: 'center', gap: 6,
              transition: 'opacity 140ms ease',
              ...styles,
            }}>
      {loading && <RefreshCw size={12} style={{ animation: 'spin 0.8s linear infinite' }} />}
      {children}
    </button>
  );
};

const Input = ({ value, onChange, placeholder, type = 'text', testid, maxLen = 200 }) => (
  <input
    data-testid={testid}
    type={type}
    value={value || ''}
    onChange={(e) => onChange(e.target.value.slice(0, maxLen))}
    placeholder={placeholder}
    style={{
      width: '100%', padding: '9px 12px', borderRadius: 8,
      background: 'var(--dash-track)', color: 'var(--dash-text)',
      border: '1px solid var(--dash-border)',
      fontSize: 13, fontFamily: 'inherit',
      transition: 'border-color 140ms ease',
    }}
    onFocus={(e) => { e.target.style.borderColor = 'var(--dash-purple)'; }}
    onBlur={(e) => { e.target.style.borderColor = 'var(--dash-border)'; }}
  />
);

const EmptyState = ({ children }) => (
  <div data-testid="empty-state"
       style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--dash-text-faint)', fontSize: 13 }}>
    {children}
  </div>
);

const ErrorCard = ({ error }) => (
  <div data-testid="page-error" className="av2-card"
       style={{ display: 'flex', alignItems: 'flex-start', gap: 10,
                background: 'rgba(255,69,58,0.06)', borderColor: 'rgba(255,69,58,0.3)' }}>
    <AlertCircle size={16} color="var(--dash-red)" />
    <div>
      <div style={{ color: 'var(--dash-red)', fontWeight: 600, fontSize: 13 }}>API error</div>
      <div style={{ color: 'var(--dash-text-muted)', fontSize: 12, marginTop: 2 }}>{String(error)}</div>
    </div>
  </div>
);

const Spinner = () => (
  <div style={{ padding: 28, textAlign: 'center', color: 'var(--dash-text-faint)' }}>
    <RefreshCw size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
  </div>
);

/* ─────────────────────────────────────────────────────────────────
 * Hook: useApi — load + refresh + error state for a single GET
 * ─────────────────────────────────────────────────────────────────*/

const useApi = (path, deps = [], intervalMs = null) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    try {
      const { data: payload } = await v2api.get(path);
      if (mountedRef.current) {
        setData(payload);
        setError(null);
      }
    } catch (e) {
      if (mountedRef.current) setError(e.response?.data?.detail || e.message);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  useEffect(() => {
    mountedRef.current = true;
    reload();
    let id;
    if (intervalMs) id = setInterval(reload, intervalMs);
    return () => {
      mountedRef.current = false;
      if (id) clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload, intervalMs, ...deps]);

  return { data, loading, error, reload };
};

/* ═════════════════════════════════════════════════════════════════
 *  PAGE 1 — LIVE HEALTH (merges Live Health + Security + Analytics)
 * ═════════════════════════════════════════════════════════════════*/

export const LuxeLiveHealth = () => {
  const toast = useV2Toast();
  const scores = useApi('/api/repair/scores?url=https://aurem.live', [], 30000);
  const incidents = useApi('/api/incidents/list?limit=20', [], 30000);
  const [scanning, setScanning] = useState(false);
  const [resolvingId, setResolvingId] = useState(null);

  const runScan = async () => {
    setScanning(true);
    try {
      await v2api.post('/api/repair/trigger-scan');
      toast.success('Scan queued — refreshing in 5s');
      setTimeout(() => { scores.reload(); incidents.reload(); }, 5000);
    } catch (e) {
      toast.error(`Scan failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setScanning(false);
    }
  };

  const resolve = async (id) => {
    setResolvingId(id);
    try {
      await v2api.post(`/api/incidents/resolve/${id}`);
      toast.success('Incident resolved');
      incidents.reload();
    } catch (e) {
      toast.error(`Resolve failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setResolvingId(null);
    }
  };

  const s = scores.data || {};
  const items = incidents.data?.incidents || [];

  // /api/repair/scores returns nested objects per axis. Extract a single
  // number with sensible fallback so the tile renders cleanly.
  const num = (v) => {
    if (v == null) return 0;
    if (typeof v === 'number') return v;
    if (typeof v === 'object') return Number(v.score_after ?? v.score ?? v.value ?? 0);
    return Number(v) || 0;
  };
  const geo = num(s.geo ?? s.geo_score ?? s.geographic);
  const sec = num(s.sec ?? s.sec_score ?? s.security);
  const acc = num(s.acc ?? s.acc_score ?? s.accessibility);
  const seo = num(s.seo ?? s.seo_score);

  const Score = ({ label, value, color }) => (
    <div data-testid={`score-${label.toLowerCase()}`} className="av2-card"
         style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 11, color: 'var(--dash-text-muted)', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value ?? 0}</div>
      <div style={{ height: 3, background: 'var(--dash-track)', borderRadius: 3 }}>
        <div style={{ width: `${value ?? 0}%`, height: '100%', background: color, transition: 'width 400ms ease' }} />
      </div>
    </div>
  );

  return (
    <div data-testid="page-live-health" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader title="Live Health" subtitle="Real-time site health + incident log"
                  right={<Btn testid="scan-now-btn" onClick={runScan} loading={scanning}><Activity size={12}/> Scan Now</Btn>} />
      {scores.error && <ErrorCard error={scores.error} />}
      <div className="av2-grid-4">
        <Score label="GEO" value={geo} color="var(--dash-blue)" />
        <Score label="SEC" value={sec} color="var(--dash-amber)" />
        <Score label="ACC" value={acc} color="var(--dash-green)" />
        <Score label="SEO" value={seo} color="var(--dash-purple)" />
      </div>
      <section className="av2-card" data-testid="incidents-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Open Incidents</h3>
          <span style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>{items.length} active</span>
        </div>
        {incidents.loading ? <Spinner />
          : items.length === 0
            ? <EmptyState>No open incidents — all systems green.</EmptyState>
            : items.map((it) => (
                <div key={it.id} data-testid={`incident-row-${it.id}`}
                     style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0',
                              borderTop: '1px solid var(--dash-divider)' }}>
                  <span style={{
                    padding: '3px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                    background: it.severity === 'HIGH' ? 'rgba(255,69,58,0.18)' : it.severity === 'MED' ? 'rgba(255,159,10,0.18)' : 'rgba(52,199,89,0.18)',
                    color: it.severity === 'HIGH' ? 'var(--dash-red)' : it.severity === 'MED' ? 'var(--dash-amber)' : 'var(--dash-green)',
                  }}>{it.severity}</span>
                  <div style={{ flex: 1, fontSize: 12 }}>
                    <div style={{ color: 'var(--dash-text)' }}>{it.message}</div>
                    <div style={{ color: 'var(--dash-text-faint)', fontSize: 11 }}>{it.source} · {String(it.created_at).slice(0, 16)}</div>
                  </div>
                  <Btn variant="ghost" testid={`resolve-${it.id}`}
                       loading={resolvingId === it.id}
                       onClick={() => resolve(it.id)}>Resolve</Btn>
                </div>
              ))}
      </section>
    </div>
  );
};

/* ═════════════════════════════════════════════════════════════════
 *  PAGE 2 — CRM (leads CRUD + send-email + CSV export)
 * ═════════════════════════════════════════════════════════════════*/

const STATUSES = ['new', 'contacted', 'qualified', 'responded', 'closed', 'lost'];

export const LuxeCRM = () => {
  const toast = useV2Toast();
  const stats = useApi('/api/leads/stats');
  const scans = useApi('/api/customer/pipeline/scan-events?limit=200');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('date');
  const [page, setPage] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const PER = 10;

  const leads = useMemo(() => {
    const raw = (scans.data?.events || scans.data?.scans || scans.data || []);
    let list = Array.isArray(raw) ? raw : [];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((l) =>
        [l.email, l.name, l.business_name, l.domain, l.url]
          .some((v) => String(v || '').toLowerCase().includes(q)),
      );
    }
    const cmp = {
      name:   (a, b) => String(a.name || '').localeCompare(String(b.name || '')),
      date:   (a, b) => String(b.created_at || b.scanned_at || '').localeCompare(String(a.created_at || a.scanned_at || '')),
      status: (a, b) => String(a.status || 'new').localeCompare(String(b.status || 'new')),
      score:  (a, b) => (Number(b.score) || 0) - (Number(a.score) || 0),
    }[sort] || (() => 0);
    return [...list].sort(cmp);
  }, [scans.data, search, sort]);

  const total = leads.length;
  const pages = Math.max(1, Math.ceil(total / PER));
  const visible = leads.slice(page * PER, page * PER + PER);

  const setStatus = async (lead, status) => {
    setEditingId(null);
    const id = lead._id || lead.lead_id || lead.id;
    try {
      await v2api.patch(`/api/leads/${id}`, { status });
      toast.success(`Status → ${status}`);
      scans.reload();
    } catch (e) {
      toast.error(`Update failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const sendEmail = async (lead) => {
    const id = lead._id || lead.lead_id || lead.id;
    try {
      await v2api.post(`/api/leads/${id}/send-email`, {
        subject: 'Quick note from AUREM',
        body: `Hi ${lead.name || 'there'}, following up on our pipeline scan.`,
      });
      toast.success('Email queued');
    } catch (e) {
      toast.error(`Send failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const exportCsv = () => {
    const rows = ['name,email,domain,status,score'];
    leads.forEach((l) => rows.push(
      [l.name, l.email, l.domain || l.url, l.status || 'new', l.score || 0]
        .map((v) => `"${String(v || '').replace(/"/g, '""')}"`).join(','),
    ));
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `aurem-leads-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    toast.success(`Exported ${leads.length} leads`);
  };

  const Stat = ({ k, v, color }) => (
    <div data-testid={`stat-${k}`} className="av2-card">
      <div style={{ fontSize: 11, color: 'var(--dash-text-muted)' }}>{k}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{v}</div>
    </div>
  );
  const st = stats.data?.stats || {};

  return (
    <div data-testid="page-crm" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader title="CRM" subtitle={`${total} leads · ${st.qualified || 0} qualified`}
                  right={<Btn variant="secondary" testid="export-csv-btn" onClick={exportCsv}>Export CSV</Btn>} />
      {stats.error && <ErrorCard error={stats.error} />}
      <div className="av2-grid-4">
        <Stat k="Total Leads"     v={st.total_leads ?? 0}    color="var(--dash-blue)" />
        <Stat k="Qualified"       v={st.qualified ?? st.new_leads ?? 0} color="var(--dash-green)" />
        <Stat k="Conversion"      v={`${st.conversion_rate ?? 0}%`}     color="var(--dash-purple)" />
        <Stat k="Pipeline Value"  v={`$${(st.total_value ?? 0).toLocaleString()}`} color="var(--dash-amber)" />
      </div>

      <section className="av2-card" data-testid="leads-table-card">
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <Input testid="leads-search" value={search}
                 onChange={(v) => { setSearch(v); setPage(0); }}
                 placeholder="Search leads..." />
          <select data-testid="leads-sort"
                  value={sort} onChange={(e) => setSort(e.target.value)}
                  style={{ padding: '9px 12px', borderRadius: 8, background: 'var(--dash-track)',
                           color: 'var(--dash-text)', border: '1px solid var(--dash-border)', fontSize: 13 }}>
            <option value="date">Newest</option><option value="name">Name</option>
            <option value="status">Status</option><option value="score">Score</option>
          </select>
        </div>

        {scans.loading ? <Spinner />
          : visible.length === 0
            ? <EmptyState>No leads matching your filter.</EmptyState>
            : visible.map((l) => {
                const id = l._id || l.lead_id || l.id;
                return (
                  <div key={id} data-testid={`lead-row-${id}`}
                       style={{ display: 'flex', alignItems: 'center', gap: 12,
                                padding: '10px 0', borderTop: '1px solid var(--dash-divider)' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: 'var(--dash-text)', fontWeight: 500,
                                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {l.name || l.business_name || l.domain || l.url || 'Unknown'}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>
                        {l.email || l.contact_email || '—'}
                      </div>
                    </div>
                    {editingId === id ? (
                      <select data-testid={`status-select-${id}`}
                              autoFocus
                              defaultValue={l.status || 'new'}
                              onChange={(e) => setStatus(l, e.target.value)}
                              onBlur={() => setEditingId(null)}
                              style={{ padding: '4px 8px', borderRadius: 6, fontSize: 11,
                                       background: 'var(--dash-track)', color: 'var(--dash-text)',
                                       border: '1px solid var(--dash-border)' }}>
                        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    ) : (
                      <button data-testid={`status-badge-${id}`}
                              onClick={() => setEditingId(id)}
                              style={{
                                padding: '3px 8px', borderRadius: 6, fontSize: 10, fontWeight: 600,
                                background: 'var(--dash-track)', color: 'var(--dash-text-muted)',
                                border: '1px solid var(--dash-border)', cursor: 'pointer',
                                textTransform: 'uppercase',
                              }}>
                        {l.status || 'new'}
                      </button>
                    )}
                    <Btn variant="ghost" testid={`send-email-${id}`} onClick={() => sendEmail(l)}>
                      <Send size={12} /> Email
                    </Btn>
                  </div>
                );
              })}

        {/* Pagination */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--dash-divider)' }}>
          <span style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>
            Page {page + 1} / {pages}
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="ghost" testid="page-prev" disabled={page === 0}
                 onClick={() => setPage((p) => Math.max(0, p - 1))}>Prev</Btn>
            <Btn variant="ghost" testid="page-next" disabled={page + 1 >= pages}
                 onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}>Next</Btn>
          </div>
        </div>
      </section>
    </div>
  );
};

/* ═════════════════════════════════════════════════════════════════
 *  PAGE 3 — CAMPAIGN (workflows toggle / create / delete)
 * ═════════════════════════════════════════════════════════════════*/

export const LuxeCampaign = () => {
  const toast = useV2Toast();
  const wf = useApi('/api/automations/workflows');
  const [busyId, setBusyId] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState({ name: '', trigger: 'manual', action: 'send_email' });

  const workflows = wf.data?.workflows || wf.data?.items || (Array.isArray(wf.data) ? wf.data : []);

  const toggle = async (w) => {
    const id = w._id || w.id;
    setBusyId(id);
    try {
      await v2api.post(`/api/automations/workflows/${id}/toggle`);
      toast.success(`Workflow ${w.active ? 'paused' : 'activated'}`);
      wf.reload();
    } catch (e) {
      toast.error(`Toggle failed: ${e.response?.data?.detail || e.message}`);
    } finally { setBusyId(null); }
  };

  const remove = async (w) => {
    const id = w._id || w.id;
    if (!window.confirm(`Delete workflow "${w.name}"?`)) return;
    setBusyId(id);
    try {
      await v2api.delete(`/api/automations/workflows/${id}`);
      toast.success('Workflow deleted');
      wf.reload();
    } catch (e) {
      toast.error(`Delete failed: ${e.response?.data?.detail || e.message}`);
    } finally { setBusyId(null); }
  };

  const create = async () => {
    if (!draft.name.trim()) return toast.error('Name required');
    try {
      await v2api.post('/api/automations/workflows', draft);
      toast.success('Workflow created');
      setShowCreate(false);
      setDraft({ name: '', trigger: 'manual', action: 'send_email' });
      wf.reload();
    } catch (e) {
      toast.error(`Create failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div data-testid="page-campaign" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader title="Campaign" subtitle="Automation workflows + outbound queue"
                  right={<Btn testid="create-wf-btn" onClick={() => setShowCreate(true)}><Plus size={12}/> New Workflow</Btn>} />
      {wf.error && <ErrorCard error={wf.error} />}

      {showCreate && (
        <section className="av2-card" data-testid="create-workflow-form" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>New Workflow</div>
          <Input testid="wf-name" value={draft.name} onChange={(v) => setDraft({ ...draft, name: v })} placeholder="Workflow name" />
          <div style={{ display: 'flex', gap: 8 }}>
            <select value={draft.trigger} onChange={(e) => setDraft({ ...draft, trigger: e.target.value })}
                    style={{ flex: 1, padding: 9, borderRadius: 8, background: 'var(--dash-track)',
                             color: 'var(--dash-text)', border: '1px solid var(--dash-border)' }}>
              <option value="manual">Manual trigger</option>
              <option value="schedule">Schedule</option>
              <option value="webhook">Webhook</option>
            </select>
            <select value={draft.action} onChange={(e) => setDraft({ ...draft, action: e.target.value })}
                    style={{ flex: 1, padding: 9, borderRadius: 8, background: 'var(--dash-track)',
                             color: 'var(--dash-text)', border: '1px solid var(--dash-border)' }}>
              <option value="send_email">Send email</option>
              <option value="enrich_leads">Enrich leads</option>
              <option value="trigger_scan">Trigger scan</option>
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Btn variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Btn>
            <Btn testid="wf-save" onClick={create}>Create</Btn>
          </div>
        </section>
      )}

      <section className="av2-card" data-testid="workflows-card">
        {wf.loading ? <Spinner />
          : workflows.length === 0
            ? <EmptyState>No workflows yet. Create your first one above.</EmptyState>
            : workflows.map((w) => {
                const id = w._id || w.id;
                return (
                  <div key={id} data-testid={`workflow-row-${id}`}
                       style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0',
                                borderTop: '1px solid var(--dash-divider)' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: 'var(--dash-text)', fontWeight: 500 }}>{w.name || 'Untitled'}</div>
                      <div style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>
                        {w.trigger || 'manual'} → {w.action || '—'} · Last run {w.last_run ? String(w.last_run).slice(0, 16) : 'never'}
                      </div>
                    </div>
                    <Btn variant={w.active ? 'secondary' : 'ghost'}
                         loading={busyId === id}
                         testid={`toggle-${id}`}
                         onClick={() => toggle(w)}>
                      <Power size={12} /> {w.active ? 'Active' : 'Paused'}
                    </Btn>
                    <Btn variant="danger" testid={`delete-${id}`} onClick={() => remove(w)}><Trash2 size={12} /></Btn>
                  </div>
                );
              })}
      </section>
    </div>
  );
};

/* ═════════════════════════════════════════════════════════════════
 *  PAGE 4 — ORA (agents + live chat)
 * ═════════════════════════════════════════════════════════════════*/

export const LuxeORA = () => {
  const toast = useV2Toast();
  const agents = useApi('/api/aurem/agents/status', [], 15000);
  const health = useApi('/api/ora/health');
  const [msg, setMsg] = useState('');
  const [convo, setConvo] = useState([]);
  const [sending, setSending] = useState(false);

  const send = async () => {
    const text = msg.trim();
    if (!text) return;
    setMsg('');
    setConvo((c) => [...c, { role: 'user', content: text }]);
    setSending(true);
    try {
      const { data } = await v2api.post('/api/public/ora/chat', { text: text });
      setConvo((c) => [...c, { role: 'ora', content: data.reply || data.message || JSON.stringify(data) }]);
    } catch (e) {
      toast.error(`ORA chat error: ${e.response?.data?.detail || e.message}`);
      setConvo((c) => [...c, { role: 'ora', content: 'Error reaching ORA.' }]);
    } finally { setSending(false); }
  };

  const agentArr = agents.data?.agents || (Array.isArray(agents.data) ? agents.data : []);

  return (
    <div data-testid="page-ora" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader title="ORA" subtitle={`System health: ${health.data?.status || '—'}`}
                  right={<Btn variant="secondary" onClick={() => window.open('/ora', '_blank')}>Open Voice PWA</Btn>} />
      {agents.error && <ErrorCard error={agents.error} />}

      <div className="av2-grid-4">
        {agentArr.slice(0, 8).map((a) => (
          <div key={a.k || a.name} data-testid={`agent-tile-${a.k || a.name}`} className="av2-card">
            <div style={{ fontSize: 11, color: 'var(--dash-text-muted)', textTransform: 'uppercase' }}>{a.k || a.name}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--dash-purple)' }}>{a.n ?? a.tasks ?? 0}</div>
            <div style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>activity {a.v ?? a.activity_score ?? 0}</div>
          </div>
        ))}
      </div>

      <section className="av2-card" data-testid="ora-chat-card" style={{ minHeight: 280, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Chat with ORA</h3>
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8,
                      padding: 10, background: 'var(--dash-track)', borderRadius: 8, minHeight: 180 }}>
          {convo.length === 0
            ? <EmptyState>Ask ORA anything about your business.</EmptyState>
            : convo.map((m, i) => (
                <div key={i} data-testid={`chat-msg-${m.role}-${i}`}
                     style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                              padding: '6px 10px', borderRadius: 8, fontSize: 12, maxWidth: '75%',
                              background: m.role === 'user' ? 'var(--dash-purple)' : 'var(--dash-card)',
                              color: m.role === 'user' ? '#fff' : 'var(--dash-text)' }}>
                  {m.content}
                </div>
              ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Input testid="ora-chat-input" value={msg} onChange={setMsg} placeholder="Type a message..." />
          <Btn testid="ora-chat-send" loading={sending} onClick={send}><Send size={12} /></Btn>
        </div>
      </section>
    </div>
  );
};

/* ═════════════════════════════════════════════════════════════════
 *  PAGE 5 — PROFILE (identity + pipeline + scan-schedule + 2FA)
 * ═════════════════════════════════════════════════════════════════*/

const SCHED_OPTS = ['hourly', 'daily', 'weekly', 'monthly', 'manual'];

export const LuxeProfile = () => {
  const toast = useV2Toast();
  const me = useApi('/api/platform/auth/me');
  const subs = useApi('/api/customer/subscriptions');
  const schedule = useApi('/api/customer/scan-schedule');
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (me.data && Object.keys(draft).length === 0) setDraft(me.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me.data]);

  const save = async () => {
    setSaving(true);
    try {
      await v2api.patch('/api/platform/auth/me', {
        full_name: draft.full_name, company_name: draft.company_name,
        website_url: draft.website_url, phone: draft.phone,
      });
      toast.success('Profile saved');
      me.reload();
    } catch (e) {
      toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
    } finally { setSaving(false); }
  };

  const activate = async () => {
    if (!draft.website_url) return toast.error('Website URL required');
    try {
      await v2api.post('/api/onboarding/activate-pipeline', { website_url: draft.website_url });
      toast.success('Pipeline activated');
    } catch (e) {
      toast.error(`Activation failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const setSchedule = async (frequency) => {
    try {
      await v2api.post('/api/customer/scan-schedule', { frequency });
      toast.success(`Schedule → ${frequency}`);
      schedule.reload();
    } catch (e) {
      toast.error(`Schedule failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const scanNow = async () => {
    try {
      const bin = me.data?.business_id || 'self';
      await v2api.post(`/api/customer/diagnostic/run-now/${bin}`);
      toast.success('Diagnostic queued');
    } catch (e) {
      toast.error(`Scan failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const toggle2fa = async () => {
    try {
      const { data } = await v2api.post('/api/platform/auth/2fa/toggle');
      toast.success(`2FA ${data.two_fa_enabled ? 'enabled' : 'disabled'}`);
      me.reload();
    } catch (e) {
      toast.error(`2FA failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const revokeAll = async () => {
    if (!window.confirm('Sign out from all other devices?')) return;
    try {
      await v2api.delete('/api/platform/auth/sessions/all');
      toast.success('All sessions revoked');
    } catch (e) {
      toast.error(`Revoke failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const activeFreq = schedule.data?.frequency || schedule.data?.schedule || 'weekly';
  const subPlan = subs.data?.plan || subs.data?.tier || me.data?.plan || 'founder';

  return (
    <div data-testid="page-profile" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader title="Profile" subtitle={`${me.data?.email || ''} · plan: ${subPlan}`} />
      {me.error && <ErrorCard error={me.error} />}

      <section className="av2-card" data-testid="identity-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Identity</h3>
        <Input testid="profile-full-name" value={draft.full_name} onChange={(v) => setDraft({ ...draft, full_name: v })} placeholder="Full name" />
        <Input testid="profile-company"   value={draft.company_name} onChange={(v) => setDraft({ ...draft, company_name: v })} placeholder="Company / brand" />
        <Input testid="profile-website"   value={draft.website_url} onChange={(v) => setDraft({ ...draft, website_url: v })} placeholder="https://your-site.com" />
        <Input testid="profile-phone"     value={draft.phone} onChange={(v) => setDraft({ ...draft, phone: v })} placeholder="Phone" />
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="secondary" testid="activate-pipeline-btn" onClick={activate}>Save &amp; Activate Pipeline</Btn>
          <Btn testid="profile-save-btn" loading={saving} onClick={save}><Save size={12} /> Save</Btn>
        </div>
      </section>

      <section className="av2-card" data-testid="schedule-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>ORA Scan Schedule</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {SCHED_OPTS.map((f) => {
            const is = activeFreq === f;
            return (
              <button key={f} type="button"
                      data-testid={`sched-${f}`}
                      onClick={() => setSchedule(f)}
                      style={{
                        padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                        textTransform: 'capitalize', cursor: 'pointer',
                        background: is ? 'rgba(255,159,10,0.18)' : 'var(--dash-card)',
                        color: is ? 'var(--dash-amber)' : 'var(--dash-text-muted)',
                        border: `1px solid ${is ? 'rgba(255,159,10,0.4)' : 'var(--dash-border)'}`,
                      }}>
                {f}
              </button>
            );
          })}
          <Btn variant="ghost" testid="scan-now-profile" onClick={scanNow}>Scan Now</Btn>
        </div>
      </section>

      <section className="av2-card" data-testid="security-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Security</h3>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--dash-text)' }}>Two-factor authentication</div>
            <div style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>
              {me.data?.two_fa_enabled ? '✅ Enabled' : '❌ Disabled'}
            </div>
          </div>
          <Btn variant="secondary" testid="toggle-2fa" onClick={toggle2fa}>
            {me.data?.two_fa_enabled ? 'Disable' : 'Enable'} 2FA
          </Btn>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      paddingTop: 10, borderTop: '1px solid var(--dash-divider)' }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--dash-text)' }}>Active sessions</div>
            <div style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>Sign out from all other devices.</div>
          </div>
          <Btn variant="danger" testid="revoke-sessions-btn" onClick={revokeAll}>
            <ShieldAlert size={12} /> Revoke All
          </Btn>
        </div>
      </section>
    </div>
  );
};

/* ═════════════════════════════════════════════════════════════════
 *  PAGE 6 — SETTINGS (branding + voice + api key + sign-out)
 * ═════════════════════════════════════════════════════════════════*/

export const LuxeSettings = ({ onSignOut }) => {
  const toast = useV2Toast();
  const settings = useApi('/api/bin/ora/settings');
  const voice = useApi('/api/voice-agent/health');
  const cfg = useApi('/api/voice-agent/config');
  const session = useApi('/api/platform/auth/session');
  const [draft, setDraft] = useState({});
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings.data && Object.keys(draft).length === 0) setDraft(settings.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.data]);

  const saveBrand = async () => {
    setSaving(true);
    try {
      await v2api.patch('/api/bin/settings', {
        brand_name:     draft.brand_name,
        logo_url:       draft.logo_url,
        primary_colour: draft.primary_colour,
        custom_domain:  draft.custom_domain,
      });
      toast.success('Branding saved');
      settings.reload();
    } catch (e) {
      toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
    } finally { setSaving(false); }
  };

  const regenKey = async () => {
    if (!window.confirm('Regenerate API key? Existing integrations will stop working until updated.')) return;
    try {
      const { data } = await v2api.post('/api/platform/auth/api-key/regenerate');
      setApiKey(data.api_key);
      setShowKey(true);
      toast.success('API key regenerated');
    } catch (e) {
      toast.error(`Regen failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const copyEmbed = () => {
    const code = `<script src="https://aurem.live/embed/widget.js" data-tenant="${settings.data?.bin_id || ''}"></script>`;
    navigator.clipboard?.writeText(code);
    toast.success('Embed code copied');
  };

  const signOut = () => {
    ['aurem_customer_token', 'platform_token', 'token'].forEach((k) => window.localStorage.removeItem(k));
    if (onSignOut) onSignOut();
    window.location.href = '/login';
  };

  const masked = apiKey ? apiKey.slice(0, 12) + '••••••••••••••••••••' + apiKey.slice(-4) : 'sk_aurem_••••••••••••';

  return (
    <div data-testid="page-settings" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader title="Settings" subtitle="Branding · voice · API · session" />
      {settings.error && <ErrorCard error={settings.error} />}

      <section className="av2-card" data-testid="branding-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Branding</h3>
        <Input testid="brand-name"     value={draft.brand_name}     onChange={(v) => setDraft({ ...draft, brand_name: v })}     placeholder="Brand name" />
        <Input testid="brand-logo"     value={draft.logo_url}       onChange={(v) => setDraft({ ...draft, logo_url: v })}       placeholder="Logo URL" />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input data-testid="brand-color" type="color"
                 value={draft.primary_colour || '#5E54E8'}
                 onChange={(e) => setDraft({ ...draft, primary_colour: e.target.value })}
                 style={{ width: 40, height: 40, borderRadius: 8, border: '1px solid var(--dash-border)', background: 'transparent' }} />
          <Input testid="brand-domain" value={draft.custom_domain} onChange={(v) => setDraft({ ...draft, custom_domain: v })} placeholder="custom.domain.com" />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Btn testid="brand-save-btn" loading={saving} onClick={saveBrand}><Save size={12} /> Save Branding</Btn>
        </div>
      </section>

      <section className="av2-card" data-testid="voice-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Voice (Retell)</h3>
          <div style={{ fontSize: 11, color: 'var(--dash-text-muted)', marginTop: 4 }}>
            <span style={{ color: voice.data?.live ? 'var(--dash-green)' : 'var(--dash-red)' }}>●</span>{' '}
            {voice.data?.live ? 'LIVE' : 'OFFLINE'} · {voice.data?.minutes_used ?? 0} min used (30d)
            {cfg.data?.agent_id && ` · ${cfg.data.agent_id.slice(0, 18)}…`}
          </div>
        </div>
        <Btn variant="secondary" testid="voice-refresh-btn" onClick={() => voice.reload()}>
          <RefreshCw size={12} /> Refresh
        </Btn>
      </section>

      <section className="av2-card" data-testid="api-key-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>API Key</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code data-testid="api-key-display"
                style={{ flex: 1, padding: '8px 12px', borderRadius: 8, background: 'var(--dash-track)',
                         color: 'var(--dash-text)', fontSize: 12, fontFamily: 'monospace',
                         whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {showKey && apiKey ? apiKey : masked}
          </code>
          <Btn variant="ghost" testid="api-key-toggle-visibility"
               onClick={() => setShowKey((v) => !v)} disabled={!apiKey}>
            {showKey ? <EyeOff size={12} /> : <Eye size={12} />}
          </Btn>
          <Btn variant="secondary" testid="api-key-regen-btn" onClick={regenKey}>Regenerate</Btn>
        </div>
      </section>

      <section className="av2-card" data-testid="embed-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Booking Widget</h3>
          <div style={{ fontSize: 11, color: 'var(--dash-text-muted)', marginTop: 4 }}>
            Embed this snippet on your site to surface AUREM booking.
          </div>
        </div>
        <Btn variant="secondary" testid="copy-embed-btn" onClick={copyEmbed}><Copy size={12} /> Copy Embed</Btn>
      </section>

      <section className="av2-card" data-testid="session-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Session</h3>
          <div style={{ fontSize: 11, color: 'var(--dash-text-muted)', marginTop: 4 }}>
            Signed in as <strong>{session.data?.email || '—'}</strong>{' '}
            ({session.data?.role || '—'})
          </div>
        </div>
        <Btn variant="danger" testid="sign-out-btn" onClick={signOut}><LogOut size={12} /> Sign Out</Btn>
      </section>

      <style>{`@keyframes spin { from {transform: rotate(0)} to {transform: rotate(360deg)} }`}</style>
    </div>
  );
};
