/**
 * AdminLeadsMining — iter 282g / Task 3
 * ──────────────────────────────────────────────────────────────
 * Admin tool to run `tomba_local` email mining against a specific
 * `campaign_leads` row. Simple layout:
 *   • Search input (lead_id OR business_name)
 *   • Results table with "⛏ Mine Emails" button per row
 *   • Inline spinner + result count + expand to see discovered emails
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Image as ImageIcon, Loader2, Pickaxe, RefreshCw, Search, Upload, XCircle, CheckCircle2 } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const ORANGE = '#F97316';
const BORDER = 'rgba(249,115,22,0.22)';
const PANEL = 'rgba(13,13,23,0.72)';

export default function AdminLeadsMining() {
  const token = getPlatformToken();
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  const [query, setQuery] = useState('');
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState({});     // {lead_id: true}
  const [mining, setMining] = useState({});         // {lead_id: "running"}
  const [bulkJob, setBulkJob] = useState(null);     // {job_id, total, completed, succeeded, failed, status}
  const [bulkBusy, setBulkBusy] = useState(false);
  const [logoUploading, setLogoUploading] = useState({});  // {lead_id: true}
  const fileInputs = useRef({});  // {lead_id: HTMLInputElement}

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError('');
    try {
      const q = query ? `?q=${encodeURIComponent(query)}` : '?limit=25';
      const r = await fetch(`${API}/api/admin/platform/campaign-leads${q}`, { headers });
      if (r.ok) {
        const d = await r.json();
        setLeads(d.leads || d.results || d.rows || []);
      } else {
        setError(`Fetch failed: ${r.status}`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, query]);

  useEffect(() => { load(); }, [load]);

  const mine = async (leadId, websiteOverride) => {
    setMining(prev => ({ ...prev, [leadId]: 'running' }));
    try {
      const r = await fetch(`${API}/api/admin/leads/${leadId}/mine-emails`, {
        method: 'POST', headers,
        body: JSON.stringify(websiteOverride ? { website: websiteOverride } : {}),
      });
      if (!r.ok) {
        const t = await r.text();
        setMining(prev => ({ ...prev, [leadId]: `error: ${t.slice(0, 80)}` }));
        return;
      }
      pollStatus(leadId);
    } catch (e) {
      setMining(prev => ({ ...prev, [leadId]: `error: ${String(e)}` }));
    }
  };

  const pollStatus = async (leadId) => {
    let attempts = 0;
    const iv = setInterval(async () => {
      attempts += 1;
      try {
        const r = await fetch(`${API}/api/admin/leads/${leadId}/mine-emails/status`, { headers });
        if (r.ok) {
          const d = await r.json();
          const status = d.email_mining_status;
          if (status === 'complete' || status === 'failed' || attempts > 40) {
            clearInterval(iv);
            setMining(prev => ({ ...prev, [leadId]: status }));
            // Refresh that row in local state
            setLeads(prev => prev.map(l => l.lead_id === leadId ? {
              ...l,
              discovered_emails: d.discovered_emails || [],
              discovered_emails_count: d.discovered_emails_count || 0,
              email_mining_status: status,
              email_mining_error: d.email_mining_error,
            } : l));
            if (status === 'complete') setExpanded(prev => ({ ...prev, [leadId]: true }));
          }
        }
      } catch (_e) { /* keep polling */ }
    }, 2500);
  };

  // ─── Auto-Enrich All ──────────────────────────────────────────────────
  const startBulkMine = async () => {
    if (bulkBusy) return;
    if (!window.confirm('Enrich all unmined leads with emails? Runs at 1 req/sec, max 100 leads.')) return;
    setBulkBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/leads/mine-emails/bulk`, {
        method: 'POST', headers,
        body: JSON.stringify({ only_unmined: true, max_leads: 100 }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) {
        setError(`Bulk mine failed: ${d.detail || JSON.stringify(d).slice(0, 100)}`);
        setBulkBusy(false);
        return;
      }
      if (!d.job_id) {
        setError(d.message || 'Nothing to enrich');
        setBulkBusy(false);
        return;
      }
      setBulkJob({ job_id: d.job_id, total: d.total, completed: 0, succeeded: 0, failed: 0, status: 'running' });
      pollBulkStatus(d.job_id);
    } catch (e) {
      setError(String(e));
      setBulkBusy(false);
    }
  };

  const pollBulkStatus = async (jobId) => {
    let attempts = 0;
    const iv = setInterval(async () => {
      attempts += 1;
      try {
        const r = await fetch(`${API}/api/admin/leads/mine-emails/bulk/${jobId}`, { headers });
        if (r.ok) {
          const d = await r.json();
          setBulkJob({
            job_id: d.job_id, total: d.total, completed: d.completed || 0,
            succeeded: d.succeeded || 0, failed: d.failed || 0,
            status: d.status,
          });
          if (d.status === 'complete' || attempts > 600) {
            clearInterval(iv);
            setBulkBusy(false);
            // Reload leads to surface new emails
            load();
          }
        }
      } catch (_e) { /* keep polling */ }
    }, 3000);
  };

  // ─── Logo upload (Task 1) ────────────────────────────────────────────
  const onLogoPicked = async (leadId, fileEvt) => {
    const file = fileEvt.target.files?.[0];
    if (!file) return;
    setLogoUploading(prev => ({ ...prev, [leadId]: true }));
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch(`${API}/api/admin/leads/${leadId}/logo`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }, // no Content-Type — browser sets multipart boundary
        body: fd,
      });
      const d = await r.json();
      if (!r.ok || !d.ok) {
        setError(`Logo upload failed: ${d.detail || d.error || JSON.stringify(d).slice(0, 80)}`);
      } else {
        setLeads(prev => prev.map(l => l.lead_id === leadId
          ? { ...l, logo_url: d.logo_url } : l));
      }
    } catch (e) {
      setError(`Upload error: ${String(e)}`);
    } finally {
      setLogoUploading(prev => ({ ...prev, [leadId]: false }));
      // Reset the input so same-file re-upload works
      if (fileInputs.current[leadId]) fileInputs.current[leadId].value = '';
    }
  };

  const removeLogo = async (leadId) => {
    if (!window.confirm('Remove this lead\'s logo?')) return;
    try {
      const r = await fetch(`${API}/api/admin/leads/${leadId}/logo`, {
        method: 'DELETE', headers,
      });
      if (r.ok) {
        setLeads(prev => prev.map(l => l.lead_id === leadId
          ? { ...l, logo_url: null } : l));
      }
    } catch (e) {
      setError(String(e));
    }
  };

  if (!token) {
    return <div style={{ padding: 40, color: '#E8E0D0' }}>Please log in as admin.</div>;
  }

  return (
    <div data-testid="admin-leads-mining" style={{
      padding: '28px 32px 60px', minHeight: '100vh',
      color: '#E8E0D0', fontFamily: "'Jost', sans-serif",
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
        <Pickaxe size={22} style={{ color: ORANGE }} />
        <div>
          <div style={{ fontFamily: "'Cinzel', serif", fontSize: 22, color: '#FFF', letterSpacing: '0.04em' }}>
            Lead Email Mining
          </div>
          <div style={{ fontSize: 11, color: '#8A8070', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 4 }}>
            Tomba Local · Playwright + MX verify · $0 per mine
          </div>
        </div>
        <button onClick={load} data-testid="leads-mining-refresh" style={{
          marginLeft: 'auto', padding: '8px 14px', borderRadius: 8,
          background: 'transparent', border: `1px solid ${BORDER}`,
          color: ORANGE, cursor: 'pointer', fontSize: 12,
          display: 'inline-flex', alignItems: 'center', gap: 6,
        }}>
          <RefreshCw size={14} /> Refresh
        </button>
        <button
          onClick={startBulkMine}
          disabled={bulkBusy}
          data-testid="auto-enrich-all-btn"
          style={{
            padding: '9px 18px', borderRadius: 8,
            background: bulkBusy ? '#55460F' : ORANGE,
            border: 'none',
            color: bulkBusy ? '#FDBA74' : '#0A0A00',
            cursor: bulkBusy ? 'not-allowed' : 'pointer',
            fontWeight: 700, fontSize: 12, letterSpacing: '0.08em',
            display: 'inline-flex', alignItems: 'center', gap: 8,
          }}
        >
          {bulkBusy
            ? <><Loader2 size={13} className="animate-spin" /> ENRICHING…</>
            : <><Pickaxe size={13} /> AUTO-ENRICH ALL</>}
        </button>
      </div>

      {/* Bulk progress bar */}
      {bulkJob && (
        <div data-testid="bulk-progress" style={{
          marginBottom: 16, padding: 14, borderRadius: 12,
          background: PANEL, border: `1px solid ${BORDER}`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ fontSize: 12, color: '#E8E0D0', letterSpacing: '0.06em' }}>
              {bulkJob.status === 'complete' ? 'Bulk enrichment complete' : 'Bulk enrichment in progress'}
              {' · '}
              <span style={{ color: '#86EFAC' }}>{bulkJob.succeeded} ok</span>
              {' · '}
              <span style={{ color: '#FCA5A5' }}>{bulkJob.failed} failed</span>
              {' · '}
              <span style={{ color: '#8A8070' }}>{bulkJob.completed}/{bulkJob.total}</span>
            </div>
            <button
              onClick={() => setBulkJob(null)}
              data-testid="dismiss-bulk-progress"
              style={{
                background: 'transparent', border: 'none', color: '#8A8070',
                cursor: 'pointer', fontSize: 12,
              }}
            >dismiss</button>
          </div>
          <div style={{
            height: 6, borderRadius: 3, background: 'rgba(0,0,0,0.4)',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${bulkJob.total ? Math.round((bulkJob.completed / bulkJob.total) * 100) : 0}%`,
              background: bulkJob.status === 'complete'
                ? 'linear-gradient(90deg, #22C55E, #86EFAC)'
                : `linear-gradient(90deg, ${ORANGE}, #FDBA74)`,
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>
      )}

      {/* Search */}
      <div style={{
        display: 'flex', gap: 10, marginBottom: 20,
        background: PANEL, padding: 14, borderRadius: 12,
        border: `1px solid ${BORDER}`,
      }}>
        <Search size={16} style={{ color: ORANGE, marginTop: 10 }} />
        <input
          data-testid="leads-search"
          type="text"
          placeholder="Search by business name or lead_id"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') load(); }}
          style={{
            flex: 1, background: 'rgba(0,0,0,0.35)',
            border: `1px solid ${BORDER}`, color: '#E8E0D0',
            padding: '8px 12px', borderRadius: 8, fontSize: 13,
          }}
        />
        <button onClick={load} data-testid="leads-search-btn" style={{
          padding: '8px 18px', borderRadius: 8, background: ORANGE,
          color: '#0A0A00', border: 'none', cursor: 'pointer',
          fontWeight: 700, fontSize: 12, letterSpacing: '0.08em',
        }}>SEARCH</button>
      </div>

      {error && (
        <div style={{
          padding: 12, marginBottom: 14, borderRadius: 10,
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.3)',
          color: '#FCA5A5', fontSize: 13,
        }}>{error}</div>
      )}

      {loading && (
        <div style={{ color: '#8A8070', fontSize: 13, padding: 18 }}>Loading…</div>
      )}

      {!loading && leads.length === 0 && (
        <div data-testid="leads-empty" style={{
          padding: 40, textAlign: 'center', color: '#8A8070',
          background: PANEL, borderRadius: 12,
          border: `1px solid ${BORDER}`, fontSize: 13,
        }}>
          No leads match this search.
        </div>
      )}

      {/* Leads list */}
      {leads.map((lead) => {
        const status = mining[lead.lead_id] || lead.email_mining_status;
        const busy = status === 'running';
        const done = status === 'complete';
        const failed = status === 'failed' || (status || '').startsWith('error');
        const count = (lead.discovered_emails || []).length
          || lead.discovered_emails_count || 0;
        const bestContact = (lead.discovered_emails || [])[0] || null;
        return (
          <div key={lead.lead_id} data-testid={`lead-row-${lead.lead_id}`} style={{
            padding: 14, marginBottom: 10, borderRadius: 12,
            background: PANEL, border: `1px solid ${BORDER}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 260 }}>
                <div style={{ fontSize: 14, color: '#E8E0D0', fontWeight: 600 }}>
                  {lead.business_name || lead.lead_id}
                </div>
                <div style={{ fontSize: 11, color: '#8A8070', fontFamily: "'JetBrains Mono', monospace", marginTop: 4 }}>
                  {lead.website || lead.website_url || 'no website'}  · {lead.lead_id}
                </div>
                {done && (
                  <div style={{ fontSize: 11, color: '#86EFAC', marginTop: 4 }}>
                    <CheckCircle2 size={11} style={{ verticalAlign: 'middle' }} /> {count} email{count === 1 ? '' : 's'} found
                  </div>
                )}
                {failed && (
                  <div style={{ fontSize: 11, color: '#FCA5A5', marginTop: 4 }}>
                    <XCircle size={11} style={{ verticalAlign: 'middle' }} /> {lead.email_mining_error || 'failed'}
                  </div>
                )}
              </div>
              {/* Logo upload column (Task 1) */}
              <div
                data-testid={`logo-cell-${lead.lead_id}`}
                style={{
                  width: 92, height: 64, borderRadius: 8,
                  background: 'rgba(0,0,0,0.3)',
                  border: `1px solid ${lead.logo_url ? 'rgba(134,239,172,0.25)' : BORDER}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  position: 'relative', overflow: 'hidden', flexShrink: 0,
                }}
              >
                {lead.logo_url ? (
                  <>
                    <img
                      src={lead.logo_url}
                      alt={`${lead.business_name} logo`}
                      style={{ maxWidth: '90%', maxHeight: '85%', objectFit: 'contain' }}
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                    <button
                      data-testid={`remove-logo-${lead.lead_id}`}
                      onClick={() => removeLogo(lead.lead_id)}
                      title="Remove logo"
                      style={{
                        position: 'absolute', top: 2, right: 2,
                        background: 'rgba(0,0,0,0.7)', border: 'none',
                        color: '#FCA5A5', cursor: 'pointer',
                        width: 18, height: 18, borderRadius: 9,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, padding: 0,
                      }}
                    >×</button>
                  </>
                ) : logoUploading[lead.lead_id] ? (
                  <Loader2 size={18} className="animate-spin" style={{ color: ORANGE }} />
                ) : (
                  <button
                    data-testid={`upload-logo-${lead.lead_id}`}
                    onClick={() => fileInputs.current[lead.lead_id]?.click()}
                    title="Upload logo (png/jpg/webp/svg, max 2MB)"
                    style={{
                      background: 'transparent', border: 'none', color: '#8A8070',
                      cursor: 'pointer', display: 'flex', flexDirection: 'column',
                      alignItems: 'center', gap: 2, padding: 4,
                    }}
                  >
                    <Upload size={16} />
                    <span style={{ fontSize: 9, letterSpacing: '0.1em' }}>LOGO</span>
                  </button>
                )}
                <input
                  ref={(el) => { fileInputs.current[lead.lead_id] = el; }}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml"
                  onChange={(e) => onLogoPicked(lead.lead_id, e)}
                  style={{ display: 'none' }}
                  data-testid={`logo-file-${lead.lead_id}`}
                />
              </div>
              {/* Best Contact column */}
              <div
                data-testid={`best-contact-${lead.lead_id}`}
                style={{
                  minWidth: 220, padding: '8px 12px', borderRadius: 8,
                  background: 'rgba(0,0,0,0.3)',
                  border: `1px solid ${bestContact ? 'rgba(134,239,172,0.25)' : BORDER}`,
                }}
              >
                <div style={{
                  fontSize: 9, color: '#8A8070', letterSpacing: '0.18em',
                  textTransform: 'uppercase', marginBottom: 4,
                }}>Best Contact</div>
                {bestContact ? (
                  <>
                    <a
                      href={`mailto:${bestContact.email}`}
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 12, color: '#86EFAC', textDecoration: 'none',
                        wordBreak: 'break-all',
                      }}
                    >{bestContact.email}</a>
                    <div style={{ fontSize: 10, color: '#8A8070', marginTop: 2 }}>
                      score {(bestContact.score ?? 0).toFixed?.(2) || bestContact.score}
                      {bestContact.role ? ' · role' : ' · personal'}
                    </div>
                  </>
                ) : (
                  <div style={{ fontSize: 11, color: '#5A5248', fontStyle: 'italic' }}>
                    not enriched yet
                  </div>
                )}
              </div>
              <button
                data-testid={`mine-emails-${lead.lead_id}`}
                onClick={() => mine(lead.lead_id)}
                disabled={busy || !(lead.website || lead.website_url)}
                style={{
                  padding: '9px 18px', borderRadius: 8,
                  background: busy ? '#55460F' : (done ? 'rgba(34,197,94,0.15)' : ORANGE),
                  border: busy ? 'none' : (done ? '1px solid rgba(34,197,94,0.4)' : 'none'),
                  color: busy ? '#FDBA74' : (done ? '#86EFAC' : '#0A0A00'),
                  cursor: (busy || !(lead.website || lead.website_url)) ? 'not-allowed' : 'pointer',
                  fontWeight: 700, fontSize: 12, letterSpacing: '0.08em',
                  display: 'inline-flex', alignItems: 'center', gap: 8,
                  opacity: (lead.website || lead.website_url) ? 1 : 0.4,
                }}
              >
                {busy
                  ? <><Loader2 size={13} className="animate-spin" /> MINING…</>
                  : done
                    ? <><Pickaxe size={13} /> RE-MINE</>
                    : <><Pickaxe size={13} /> MINE EMAILS</>}
              </button>
              {count > 0 && (
                <button
                  data-testid={`toggle-emails-${lead.lead_id}`}
                  onClick={() => setExpanded(prev => ({ ...prev, [lead.lead_id]: !prev[lead.lead_id] }))}
                  style={{
                    padding: '9px 14px', borderRadius: 8,
                    background: 'transparent', border: `1px solid ${BORDER}`,
                    color: ORANGE, cursor: 'pointer', fontSize: 12,
                  }}
                >
                  {expanded[lead.lead_id] ? 'HIDE' : `VIEW ${count}`}
                </button>
              )}
            </div>

            {expanded[lead.lead_id] && (lead.discovered_emails || []).length > 0 && (
              <div data-testid={`lead-emails-${lead.lead_id}`} style={{
                marginTop: 12, padding: 12,
                background: 'rgba(0,0,0,0.3)', borderRadius: 8,
                border: `1px solid ${BORDER}`,
              }}>
                <div style={{ fontSize: 10, color: '#8A8070', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
                  Discovered emails · ranked by owner-score
                </div>
                {(lead.discovered_emails || []).map((e, idx) => (
                  <div key={idx} style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', padding: '6px 0',
                    borderBottom: idx === lead.discovered_emails.length - 1 ? 'none' : '1px solid rgba(249,115,22,0.08)',
                  }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#E8E0D0' }}>
                      {e.email}
                    </span>
                    <span style={{ fontSize: 10, color: e.score > 0.8 ? '#86EFAC' : e.score > 0.5 ? '#FDBA74' : '#8A8070' }}>
                      score {e.score?.toFixed?.(2) || e.score} {e.role ? '· role' : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
