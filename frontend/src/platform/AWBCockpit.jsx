/**
 * AWB Cockpit (iter 298) — /admin/awb-cockpit
 * Live counters + last 5 preview thumbnails for Auto Website Builder.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Globe, Loader2, Play, RefreshCw, ExternalLink, AlertTriangle, Check, Zap, Power, Mail, Edit, Server } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const GOLD = '#C9A227';

const STATUS_COLOR = {
  drafting: '#7A7468', drafted: '#7A7468',
  refined: '#4A8FD4',
  rendered: '#F59E0B',
  published: '#22C55E',
  deployed: '#22C55E',
  vetoed: '#EF4444', failed: '#EF4444',
};

export default function AWBCockpit() {
  const token = getPlatformToken();
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [batchSize, setBatchSize] = useState(3);
  const [error, setError] = useState(null);
  const [autopilot, setAutopilot] = useState(null);
  const [apToggling, setApToggling] = useState(false);
  const [tab, setTab] = useState('sites');  // 'sites' | 'domains'
  const [domains, setDomains] = useState([]);
  const [domainsLoading, setDomainsLoading] = useState(false);
  const [expiring, setExpiring] = useState({ '7d': [], '14d': [], '30d': [] });

  const loadDomains = useCallback(async () => {
    setDomainsLoading(true);
    try {
      const r = await fetch(`${API}/api/admin/platform/website-builder/domains`,
        { headers });
      if (r.ok) {
        const d = await r.json();
        setDomains(d.domains || []);
        setExpiring(d.expiring || { '7d': [], '14d': [], '30d': [] });
      }
    } catch { /* tolerate */ }
    setDomainsLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { if (tab === 'domains') loadDomains(); }, [tab, loadDomains]);

  const sendEditLink = async (site) => {
    const slug = site.slug || site.site_id;
    if (!window.confirm(`Send edit-link email to the customer for "${site.business_name || slug}"?`)) return;
    try {
      const r = await fetch(`${API}/api/edit/admin/send-link`, {
        method: 'POST', headers,
        body: JSON.stringify({ site_slug: slug }),
      });
      const d = await r.json();
      if (!r.ok) {
        // Ask for override email if no email on file
        if ((d.detail || '').includes('no email')) {
          const em = window.prompt('No email on file. Enter customer email:');
          if (!em) return;
          const r2 = await fetch(`${API}/api/edit/admin/send-link`, {
            method: 'POST', headers,
            body: JSON.stringify({ site_slug: slug, override_email: em }),
          });
          const d2 = await r2.json();
          alert(d2.sent ? `Sent to ${d2.email_to}` : `Failed: ${d2.detail || JSON.stringify(d2)}`);
          return;
        }
        alert(`Failed: ${d.detail || 'unknown'}`);
        return;
      }
      alert(d.sent
        ? `✓ Magic-link sent to ${d.email_to}`
        : `Recorded; copy this link manually:\n${d.link}`);
    } catch (e) { alert(`Error: ${e.message}`); }
  };

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/admin/platform/website-builder/cockpit`, { headers }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/api/admin/platform/website-builder/autopilot`, { headers }).then(r => r.ok ? r.json() : null),
    ])
      .then(([cockpit, ap]) => {
        if (cockpit) setData(cockpit);
        if (ap) setAutopilot(ap);
        setError(null);
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [load]);

  const runBatch = async () => {
    setRunning(true); setError(null);
    try {
      const r = await fetch(`${API}/api/admin/platform/website-builder/run-batch?limit=${batchSize}`, {
        method: 'POST', headers,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'batch failed');
      load();
    } catch (e) { setError(e.message); }
    setRunning(false);
  };

  const toggleAutopilot = async () => {
    if (!autopilot) return;
    setApToggling(true); setError(null);
    try {
      const r = await fetch(`${API}/api/admin/platform/website-builder/autopilot`, {
        method: 'POST', headers,
        body: JSON.stringify({
          enabled: !autopilot.enabled,
          batch_size: autopilot.batch_size || 5,
          interval_minutes: autopilot.interval_minutes || 30,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'toggle failed');
      setAutopilot(d);
    } catch (e) { setError(e.message); }
    setApToggling(false);
  };

  const c = data?.counters || {};
  const recent = data?.recent || [];
  const queue = data?.queue_size ?? 0;
  const cfReady = data?.cloudflare_ready;

  return (
    <div data-testid="awb-cockpit-page" style={pageStyle}>
      <header style={hdrStyle}>
        <Globe style={{ width: 20, height: 20, color: GOLD }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 26, fontWeight: 400 }}>
            Auto-Build Cockpit
          </div>
          <div style={hdrSubStyle}>
            AUTO WEBSITE BUILDER · COUNCIL → A2A → GEMINI → CLAUDE → CLOUDFLARE
          </div>
        </div>
        <button data-testid="awb-refresh" onClick={load} style={btnSec} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" style={{ width: 12, height: 12 }} /> : <RefreshCw style={{ width: 12, height: 12 }} />}
          REFRESH
        </button>
      </header>

      {/* CF + R2 status */}
      <div style={{ padding: '8px 24px', display: 'flex', gap: 16, flexWrap: 'wrap',
                    background: 'rgba(255,255,255,0.02)',
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    fontSize: 11, fontFamily: "'DM Mono',monospace" }}>
        <StatusChip label="CLOUDFLARE" ok={cfReady} />
        <StatusChip label="R2 STORAGE" ok={data?.r2_ready} />
        <StatusChip label="WORKER ROUTE" ok={cfReady && data?.r2_ready} />
        <span style={{ color: '#7A7468' }}>Sites publish to R2 + serve via Worker on {`{slug}.aurem.live`}</span>
      </div>

      {/* Auto-Pilot card */}
      {autopilot && (
        <div data-testid="awb-autopilot-card" style={{
          padding: '16px 24px', display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
          background: autopilot.enabled ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.02)',
          borderBottom: '1px solid rgba(201,162,39,0.12)',
        }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 18,
                          color: autopilot.enabled ? '#22C55E' : '#F2EDE4' }}>
              Auto-Pilot Mode {autopilot.enabled ? '· ON' : '· OFF'}
            </div>
            <div style={{ fontSize: 11, color: '#8A8279', marginTop: 4,
                          fontFamily: "'DM Mono',monospace", letterSpacing: 0.5 }}>
              Every {autopilot.interval_minutes ?? 30} min · batch of {autopilot.batch_size ?? 5} ·
              {autopilot.last_run_at
                ? ` last run ${new Date(autopilot.last_run_at).toLocaleTimeString()}`
                : ' never run'}
              {autopilot.last_run_summary
                ? ` (built ${autopilot.last_run_summary.built_n}, skipped ${autopilot.last_run_summary.skipped_n})` : ''}
            </div>
          </div>
          <button data-testid="awb-autopilot-toggle" onClick={toggleAutopilot} disabled={apToggling}
                  style={{ ...btnPri,
                          background: autopilot.enabled ? '#EF4444' : '#22C55E',
                          color: '#0A0A0A',
                          opacity: apToggling ? 0.5 : 1 }}>
            {apToggling ? <Loader2 className="animate-spin" style={{ width: 12, height: 12 }} />
                        : <Power style={{ width: 12, height: 12 }} />}
            {autopilot.enabled ? 'TURN OFF' : 'TURN ON'}
          </button>
        </div>
      )}

      {/* Counters */}
      <div data-testid="awb-counters" style={countersStyle}>
        <Counter label="Total" value={c.total ?? 0} color={GOLD} />
        <Counter label="Published" value={(c.published ?? 0) + (c.deployed ?? 0)} color={STATUS_COLOR.published} />
        <Counter label="Rendered" value={c.rendered ?? 0} color={STATUS_COLOR.rendered} />
        <Counter label="Drafted" value={c.drafted ?? 0} color={STATUS_COLOR.drafted} />
        <Counter label="Vetoed" value={c.vetoed ?? 0} color={STATUS_COLOR.vetoed} />
        <Counter label="Failed" value={c.failed ?? 0} color={STATUS_COLOR.failed} />
        <Counter label="Queue" value={queue} color="#4A8FD4" />
      </div>

      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: 6, padding: '12px 24px',
                    borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        {[['sites', 'Sites', Globe], ['domains', 'Domains', Server]].map(([k, lbl, Icon]) => (
          <button key={k} data-testid={`awb-tab-${k}`}
            onClick={() => setTab(k)}
            style={{ ...btnSec,
              padding: '8px 14px', fontSize: 11, letterSpacing: 1.4,
              background: tab === k ? 'rgba(201,162,39,0.18)' : 'transparent',
              color: tab === k ? GOLD : '#8A8279',
              border: `1px solid ${tab === k ? 'rgba(201,162,39,0.5)' : 'rgba(255,255,255,0.12)'}`,
            }}>
            <Icon style={{ width: 12, height: 12 }} /> {lbl.toUpperCase()}
          </button>
        ))}
      </div>

      {tab === 'sites' && (<>
      {/* Run batch */}
      <div style={runBoxStyle}>
        <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 18 }}>
          Run a batch
        </div>
        <p style={{ fontSize: 12, color: '#8A8279', margin: '4px 0 12px' }}>
          {queue} no-website lead{queue === 1 ? '' : 's'} eligible. Each run pipes through Council → A2A → Gemini draft → Claude refine → render → Cloudflare publish.
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input data-testid="awb-batch-size" type="number" min="1" max="20" value={batchSize}
                 onChange={e => setBatchSize(Math.max(1, Math.min(20, +e.target.value || 1)))}
                 style={inputStyle} />
          <button data-testid="awb-run-batch" onClick={runBatch} disabled={running || queue === 0}
                  style={{ ...btnPri, opacity: (running || queue === 0) ? 0.5 : 1 }}>
            {running ? <Loader2 className="animate-spin" style={{ width: 12, height: 12 }} /> : <Play style={{ width: 12, height: 12 }} />}
            {running ? 'BUILDING…' : 'RUN BATCH'}
          </button>
        </div>
      </div>

      {/* Recent thumbnails */}
      <section style={{ padding: '20px 24px' }}>
        <h3 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 18, margin: '0 0 14px' }}>
          Last 5 builds
        </h3>
        {recent.length === 0 && (
          <div style={{ color: '#7A7468', fontSize: 12, padding: 20,
                        textAlign: 'center', border: '1px dashed rgba(255,255,255,0.08)', borderRadius: 8 }}>
            Nothing built yet, fire a batch above.
          </div>
        )}
        <div data-testid="awb-recent-list" style={{ display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
          {recent.map((s, i) => (
            <SiteCard key={s.site_id || i} site={s} index={i}
              onSendEditLink={() => sendEditLink(s)} />
          ))}
        </div>
      </section>
      </>)}

      {tab === 'domains' && (
        <DomainsTab domains={domains} loading={domainsLoading}
          expiring={expiring} onRefresh={loadDomains} />
      )}

      {error && (
        <div data-testid="awb-error" style={{ margin: '0 24px 20px', padding: 12,
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#EF4444', fontSize: 12, borderRadius: 6,
              fontFamily: "'DM Mono',monospace" }}>
          ERROR · {error}
        </div>
      )}
    </div>
  );
}

const Counter = ({ label, value, color }) => (
  <div data-testid={`awb-counter-${label.toLowerCase()}`} style={counterStyle}>
    <div style={{ fontSize: 9, letterSpacing: 1.5, color: '#8A8279',
                  fontFamily: "'DM Mono',monospace", textTransform: 'uppercase' }}>{label}</div>
    <div style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 32, color, lineHeight: 1, marginTop: 4 }}>
      {value}
    </div>
  </div>
);

const StatusChip = ({ label, ok }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
                 padding: '2px 10px', borderRadius: 4,
                 background: ok ? 'rgba(34,197,94,0.10)' : 'rgba(239,68,68,0.08)',
                 border: '1px solid ' + (ok ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.35)'),
                 color: ok ? '#22C55E' : '#EF4444', letterSpacing: 1 }}>
    {ok ? <Check style={{ width: 10, height: 10 }} /> : <AlertTriangle style={{ width: 10, height: 10 }} />}
    {label}: {ok ? 'OK' : 'OFF'}
  </span>
);

const SiteCard = ({ site, index, onSendEditLink }) => {
  const status = (site.status || 'rendered').toLowerCase();
  // iter 322p — robust resolver: never double-prefix an already-absolute
  // preview_url (which used to render `${API}https://aurem.live/...` and
  // break the iframe thumbnail + the LIVE / EDIT LINK click-through).
  const previewURL = (() => {
    if (site.live_url) return site.live_url;
    if (site.public_url) return `${API}${site.public_url}`;
    const p = site.preview_url || '';
    if (!p) return null;
    return /^https?:\/\//i.test(p) ? p : `${API}${p}`;
  })();
  const customerPickerURL = site.slug ? `${API}/api/preview/${site.slug}` : null;
  const editCount = site.edit_count || 0;
  const lastEdited = site.last_edited
    ? new Date(site.last_edited).toLocaleDateString() : null;
  return (
    <div data-testid={`awb-site-card-${index}`} style={cardStyle}>
      <div style={{ aspectRatio: '16/10', background: '#0A0A0B', position: 'relative', overflow: 'hidden',
                    borderBottom: '1px solid rgba(201,162,39,0.12)' }}>
        {previewURL ? (
          <iframe src={previewURL} title={site.business_name}
                  style={{ width: '200%', height: '200%', transform: 'scale(0.5)',
                           transformOrigin: '0 0', border: 0, pointerEvents: 'none' }} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', color: '#7A7468', fontSize: 11 }}>no render</div>
        )}
        <span style={{ position: 'absolute', top: 8, right: 8, fontSize: 9,
                       fontFamily: "'DM Mono',monospace", letterSpacing: 1,
                       padding: '3px 8px', borderRadius: 3,
                       background: `${STATUS_COLOR[status] || '#7A7468'}25`,
                       color: STATUS_COLOR[status] || '#7A7468',
                       border: `1px solid ${STATUS_COLOR[status] || '#7A7468'}50` }}>
          {status.toUpperCase()}
        </span>
        {editCount > 0 && (
          <span data-testid={`awb-edit-badge-${index}`}
            style={{ position: 'absolute', top: 8, left: 8, fontSize: 9,
                     fontFamily: "'DM Mono',monospace", letterSpacing: 1,
                     padding: '3px 8px', borderRadius: 3,
                     background: 'rgba(201,162,39,0.18)', color: GOLD,
                     border: '1px solid rgba(201,162,39,0.4)',
                     display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <Edit style={{ width: 9, height: 9 }} />
            {editCount}× {lastEdited ? `· ${lastEdited}` : ''}
          </span>
        )}
      </div>
      <div style={{ padding: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {site.business_name || site.lead_id}
        </div>
        <div style={{ fontSize: 10, color: '#7A7468', fontFamily: "'DM Mono',monospace",
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {site.slug || site.site_id}
        </div>
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {site.live_url && (
            <a href={site.live_url} target="_blank" rel="noreferrer"
               style={btnLink} data-testid={`awb-open-live-${index}`}>
              <Zap style={{ width: 10, height: 10 }} /> LIVE
            </a>
          )}
          {customerPickerURL && (
            <a href={customerPickerURL} target="_blank" rel="noreferrer"
               style={btnLinkAlt} data-testid={`awb-open-picker-${index}`}>
              <ExternalLink style={{ width: 10, height: 10 }} /> THEMES
            </a>
          )}
          <button onClick={onSendEditLink} data-testid={`awb-send-edit-${index}`}
            style={{ ...btnLinkAlt, background: 'rgba(91,141,239,0.10)',
                     color: '#5B8DEF',
                     border: '1px solid rgba(91,141,239,0.4)',
                     cursor: 'pointer' }}>
            <Mail style={{ width: 10, height: 10 }} /> EDIT LINK
          </button>
        </div>
      </div>
    </div>
  );
};

const DomainsTab = ({ domains, loading, expiring, onRefresh }) => {
  const e = expiring || { '7d': [], '14d': [], '30d': [] };
  const showBanner = e['7d'].length || e['14d'].length || e['30d'].length;
  return (
  <section data-testid="awb-domains-tab" style={{ padding: '20px 24px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12,
                  marginBottom: 14 }}>
      <h3 style={{ fontFamily: "'Cormorant Garamond',serif", fontSize: 18,
                   margin: 0, flex: 1 }}>
        Customer Domains {loading ? '· loading…' : `(${domains.length})`}
      </h3>
      <button onClick={onRefresh} style={btnSec}
        data-testid="awb-domains-refresh">
        <RefreshCw style={{ width: 11, height: 11 }} /> REFRESH
      </button>
    </div>

    {showBanner && (
      <div data-testid="awb-domains-expiring-banner"
        style={{ marginBottom: 16, padding: 14, borderRadius: 8,
                 background: e['7d'].length
                   ? 'rgba(239,68,68,0.12)'
                   : (e['14d'].length ? 'rgba(245,158,11,0.12)'
                                       : 'rgba(91,141,239,0.10)'),
                 border: '1px solid ' + (e['7d'].length
                   ? 'rgba(239,68,68,0.4)'
                   : (e['14d'].length ? 'rgba(245,158,11,0.4)'
                                       : 'rgba(91,141,239,0.35)')),
                 color: e['7d'].length ? '#EF4444'
                          : (e['14d'].length ? '#F59E0B' : '#5B8DEF'),
                 fontSize: 12, lineHeight: 1.55,
                 fontFamily: "'DM Mono',monospace", letterSpacing: 0.6 }}>
        <AlertTriangle style={{ width: 13, height: 13, display: 'inline',
                                verticalAlign: 'middle', marginRight: 6 }} />
        EXPIRING SOON ·
        {e['7d'].length > 0 && <> {e['7d'].length} in ≤7d ({e['7d'].slice(0,3).join(', ')}{e['7d'].length>3?'…':''})</>}
        {e['14d'].length > 0 && <> · {e['14d'].length} in ≤14d</>}
        {e['30d'].length > 0 && <> · {e['30d'].length} in ≤30d</>}
        {' '}— enable auto-renew or contact owner.
      </div>
    )}

    {!loading && domains.length === 0 && (
      <div style={{ color: '#7A7468', fontSize: 12, padding: 20,
                    textAlign: 'center',
                    border: '1px dashed rgba(255,255,255,0.08)', borderRadius: 8 }}>
        No domains registered yet. Customers add a domain at checkout
        (+$29 CAD/yr) and it auto-registers via Cloudflare.
      </div>
    )}
    {domains.length > 0 && (
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: '#8A8279', textAlign: 'left',
                          fontFamily: "'DM Mono',monospace", fontSize: 9,
                          letterSpacing: 1.4 }}>
              <th style={th}>DOMAIN</th>
              <th style={th}>BUSINESS</th>
              <th style={th}>STATUS</th>
              <th style={th}>EXPIRES</th>
              <th style={th}>DAYS</th>
              <th style={th}>$ CAD</th>
            </tr>
          </thead>
          <tbody>
            {domains.map((d, i) => {
              const dleft = d.days_until_expiry;
              const dColor = dleft == null ? '#7A7468'
                : (dleft <= 7 ? '#EF4444'
                  : (dleft <= 14 ? '#F59E0B'
                    : (dleft <= 30 ? '#5B8DEF' : '#22C55E')));
              return (
              <tr key={i} data-testid={`awb-domain-row-${i}`}
                style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <td style={td}>
                  <a href={`https://${d.domain}`} target="_blank" rel="noreferrer"
                    style={{ color: GOLD, textDecoration: 'none' }}>
                    {d.domain}
                  </a>
                </td>
                <td style={td}>{d.business_name || d.lead_id || '—'}</td>
                <td style={td}>
                  <span style={{
                    color: d.status === 'active' ? '#22C55E'
                      : (d.status === 'manual_required' ? '#EF4444' : '#F59E0B'),
                    fontFamily: "'DM Mono',monospace", fontSize: 10,
                    letterSpacing: 1,
                  }}>{(d.status || '—').toUpperCase()}</span>
                </td>
                <td style={td}>{(d.expires_at || '').slice(0, 10) || '—'}</td>
                <td style={{ ...td, color: dColor, fontWeight: 600,
                              fontFamily: "'DM Mono',monospace" }}>
                  {dleft != null ? `${dleft}d` : '—'}
                </td>
                <td style={td}>${d.charged_cad || 29}</td>
              </tr>
            );})}
          </tbody>
        </table>
      </div>
    )}
  </section>
  );
};

const th = { padding: '8px 6px', fontWeight: 500 };
const td = { padding: '10px 6px', color: '#E8E0D0' };

// styles
const pageStyle = { minHeight: '100vh', background: '#0A0A0B', color: '#F2EDE4',
                    fontFamily: "'DM Sans',system-ui,sans-serif" };
const hdrStyle = { display: 'flex', alignItems: 'center', gap: 14, padding: '18px 24px',
                   borderBottom: '1px solid rgba(201,162,39,0.15)' };
const hdrSubStyle = { fontSize: 10, color: '#8A8279', fontFamily: "'DM Mono',monospace",
                      letterSpacing: 1.5, marginTop: 2 };
const countersStyle = { display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                        gap: 12, padding: '20px 24px',
                        borderBottom: '1px solid rgba(255,255,255,0.04)' };
const counterStyle = { padding: '14px 16px', background: 'rgba(255,255,255,0.02)',
                       border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8 };
const runBoxStyle = { padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.04)' };
const inputStyle = { width: 70, padding: '8px 10px', background: 'rgba(255,255,255,0.03)',
                     color: '#F2EDE4', border: '1px solid rgba(201,162,39,0.25)',
                     borderRadius: 6, fontSize: 13, outline: 'none' };
const cardStyle = { background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: 8, overflow: 'hidden' };
const btnPri = { padding: '8px 16px', borderRadius: 6, background: GOLD, color: '#0A0A0A',
                 fontWeight: 700, fontSize: 11, letterSpacing: 1, border: 'none',
                 cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 };
const btnSec = { padding: '6px 12px', borderRadius: 4, fontSize: 9, fontWeight: 600,
                 letterSpacing: 1.5, background: 'transparent', color: '#8A8279',
                 border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer',
                 fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 4 };
const btnLink = { padding: '4px 8px', fontSize: 9, fontFamily: "'DM Mono',monospace",
                  letterSpacing: 1, background: 'rgba(34,197,94,0.12)', color: '#22C55E',
                  border: '1px solid rgba(34,197,94,0.4)', borderRadius: 3,
                  textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 };
const btnLinkAlt = { ...btnLink, background: 'rgba(201,162,39,0.10)', color: GOLD,
                     border: '1px solid rgba(201,162,39,0.4)' };
