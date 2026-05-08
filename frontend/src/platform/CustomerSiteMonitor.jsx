/**
 * AUREM Site Monitor — Customer Dashboard
 * Route: /my/monitor
 * For: Paid subscribers + free-tier trialists (authenticated platform users)
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getPlatformToken } from '../utils/secureTokenStore';
import '../styles/portal-global.css';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const GOLD = '#F97316';
const OBSIDIAN = '#050510';
const GREEN = '#22C55E';
const AMBER = '#FDBA74';
const RED = '#FCA5A5';
const PANEL = 'rgba(255,255,255,0.03)';
const BORDER = 'rgba(255,255,255,0.06)';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=JetBrains+Mono:wght@400;500&family=Jost:wght@400;500;600&display=swap');
.sm-root { min-height:100vh; padding:32px 24px 80px; font-family:'Jost',sans-serif; }
.sm-root * { box-sizing:border-box; }
.sm-card { background:${PANEL}; border:1px solid ${BORDER}; border-radius:20px; padding:22px; backdrop-filter:blur(20px) saturate(180%); -webkit-backdrop-filter:blur(20px) saturate(180%); box-shadow:0 8px 32px rgba(0,0,0,0.5), inset 0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 0 rgba(255,255,255,0.08); transition:all 0.3s cubic-bezier(.4,0,.2,1); }
.sm-card:hover { transform:translateY(-4px); border-color:rgba(249,115,22,0.18); box-shadow:0 20px 60px rgba(0,0,0,0.6), 0 0 20px rgba(249,115,22,0.08); }
.sm-hdr { font-family:'Cinzel',serif; color:${GOLD}; letter-spacing:0.08em; text-shadow:0 0 14px rgba(249,115,22,0.4); }
.sm-mono { font-family:'JetBrains Mono',monospace; }
.sm-body { font-family:'Jost',sans-serif; }
.sm-btn { background:transparent; border:1px solid rgba(249,115,22,0.3); color:${GOLD}; padding:10px 20px; border-radius:10px; cursor:pointer; font-family:'Jost',sans-serif; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; font-weight:600; transition:all 0.2s; }
.sm-btn:hover { background:rgba(249,115,22,0.08); border-color:${GOLD}; transform:translateY(-2px); }
.sm-btn-solid { background:linear-gradient(135deg,#F97316 0%,#C9A227 100%); color:#000; border:none; box-shadow:0 4px 20px rgba(249,115,22,0.3); font-weight:800; }
.sm-btn-solid:hover { transform:translateY(-2px); box-shadow:0 8px 30px rgba(249,115,22,0.5); }
.sm-input { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); color:#F0EAE0; padding:10px 14px; border-radius:8px; font-family:'JetBrains Mono',monospace; font-size:13px; width:100%; }
.sm-input:focus { outline:none; border-color:rgba(249,115,22,0.4); background:rgba(255,255,255,0.06); }
.sm-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }
.sm-stat { text-align:center; padding:22px; }
.sm-stat-value { font-family:'Cinzel',serif; font-size:36px; font-weight:600; color:${GOLD}; text-shadow:0 0 20px rgba(249,115,22,0.4); line-height:1.1; }
.sm-stat-label { font-size:10px; color:rgba(255,255,255,0.4); letter-spacing:0.15em; text-transform:uppercase; margin-top:8px; }
.sm-table { width:100%; border-collapse:collapse; font-size:13px; }
.sm-table th { text-align:left; padding:10px 12px; color:rgba(255,255,255,0.4); font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:0.1em; border-bottom:1px solid ${BORDER}; }
.sm-table td { padding:10px 12px; border-bottom:1px solid rgba(255,255,255,0.04); }
.sm-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.sm-pill { display:inline-block; padding:3px 10px; border-radius:20px; font-size:10px; font-weight:700; letter-spacing:0.1em; font-family:'JetBrains Mono',monospace; }
`;

const TIER_INFO = {
  none: { label: 'No Plan', color: '#888', cta: 'Start Free Trial or Subscribe' },
  free: { label: 'Free Trial', color: AMBER, cta: 'Upgrade to Paid' },
  paid: { label: 'Paid', color: GREEN, cta: null },
};

export default function CustomerSiteMonitor() {
  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState(null);
  const [data, setData] = useState({ endpoints: [], summary: {} });
  const [incidents, setIncidents] = useState([]);
  const [newUrl, setNewUrl] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  const token = getPlatformToken();
  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchAll = useCallback(async () => {
    try {
      const [planR, epR, incR] = await Promise.all([
        fetch(`${API}/api/site-monitor/me/plan`, { headers: authHeader }),
        fetch(`${API}/api/site-monitor/me/endpoints`, { headers: authHeader }),
        fetch(`${API}/api/site-monitor/me/incidents?limit=20`, { headers: authHeader }),
      ]);
      if (!planR.ok) throw new Error(`Plan ${planR.status}`);
      const planJ = await planR.json();
      const epJ = await epR.json();
      const incJ = await incR.json();
      setPlan(planJ.plan);
      setData(epJ);
      setIncidents(incJ.incidents || []);
      setError('');
    } catch (e) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 60000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const addUrl = async () => {
    if (!newUrl || newUrl.length < 4) { setError('Enter a valid URL'); return; }
    setAdding(true);
    setError('');
    setInfo('');
    try {
      const r = await fetch(`${API}/api/site-monitor/me/endpoints`, {
        method: 'POST',
        headers: { ...authHeader, 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newUrl, label: newLabel }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setInfo(`Added ${j.endpoint.url}`);
      setNewUrl('');
      setNewLabel('');
      fetchAll();
    } catch (e) {
      setError(e.message);
    }
    setAdding(false);
  };

  const removeUrl = async (endpointId) => {
    if (!window.confirm('Stop monitoring this URL?')) return;
    try {
      const r = await fetch(`${API}/api/site-monitor/me/endpoints/${endpointId}`, {
        method: 'DELETE', headers: authHeader,
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      fetchAll();
    } catch (e) { setError(e.message); }
  };

  const upgrade = async (serviceId) => {
    try {
      const r = await fetch(`${API}/api/site-monitor/me/upgrade`, {
        method: 'POST',
        headers: { ...authHeader, 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_id: serviceId, origin_url: window.location.origin }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      if (j.url) window.location.href = j.url;
    } catch (e) { setError(e.message); }
  };

  if (loading) {
    return <div className="sm-root"><style>{CSS}</style><div className="sm-body" style={{ textAlign: 'center', color: GOLD, paddingTop: '20vh' }}>Loading Site Monitor…</div></div>;
  }

  const tier = plan?.tier || 'none';
  const tierInfo = TIER_INFO[tier];
  const limits = plan?.limits || {};
  const maxUrls = limits.max_urls === -1 ? '∞' : limits.max_urls;
  const activeUrls = data.endpoints?.filter(e => e.active).length || 0;
  const summary = data.summary || {};

  return (
    <>
      <style>{CSS}</style>
      <div className="portal-shell" style={{minHeight:'100vh',color:'#F0EAE0'}}>
        <div className="portal-circuit" aria-hidden="true" />
        <div className="sm-root" data-testid="customer-site-monitor">
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
          <div>
            <div className="sm-hdr" style={{ fontSize: 28 }}>Site Monitor</div>
            <div className="sm-body" style={{ color: '#888', fontSize: 14, marginTop: 4 }}>
              24×7 uptime tracking for your websites · {tier !== 'none' ? `${plan.service_name}` : 'Not active'}
            </div>
          </div>
          <Link to="/my" className="sm-btn" style={{ textDecoration: 'none' }} data-testid="back-portal-btn">← My Portal</Link>
        </div>

        {error && <div className="sm-card" style={{ borderColor: RED, color: RED, marginBottom: 16 }} data-testid="error-banner">{error}</div>}
        {info && <div className="sm-card" style={{ borderColor: GREEN, color: GREEN, marginBottom: 16 }} data-testid="info-banner">{info}</div>}

        {/* Plan / Stats */}
        <div className="sm-grid" style={{ marginBottom: 20 }}>
          <div className="sm-card sm-stat" data-testid="stat-plan">
            <div className="sm-stat-value" style={{ color: tierInfo.color, fontSize: 22 }}>{tierInfo.label}</div>
            <div className="sm-stat-label">Plan · {limits.check_interval_min ? `${limits.check_interval_min} min checks` : '—'}</div>
          </div>
          <div className="sm-card sm-stat" data-testid="stat-urls">
            <div className="sm-stat-value">{activeUrls}<span style={{ color: '#555', fontSize: 18 }}>/{maxUrls}</span></div>
            <div className="sm-stat-label">URLs Monitored</div>
          </div>
          <div className="sm-card sm-stat" data-testid="stat-uptime">
            <div className="sm-stat-value" style={{ color: summary.avg_uptime_pct >= 99 ? GREEN : summary.avg_uptime_pct >= 80 ? AMBER : RED }}>
              {summary.avg_uptime_pct != null ? `${summary.avg_uptime_pct}%` : '—'}
            </div>
            <div className="sm-stat-label">Uptime (24h)</div>
          </div>
          <div className="sm-card sm-stat" data-testid="stat-incidents">
            <div className="sm-stat-value" style={{ color: incidents.length === 0 ? GREEN : RED }}>{incidents.length}</div>
            <div className="sm-stat-label">Recent Incidents</div>
          </div>
        </div>

        {/* Plan CTA */}
        {tier === 'none' && (
          <div className="sm-card" style={{ marginBottom: 20, borderColor: GOLD }} data-testid="no-plan-cta">
            <div className="sm-hdr" style={{ fontSize: 16, marginBottom: 8 }}>Activate Site Monitor</div>
            <div className="sm-body" style={{ color: '#ccc', marginBottom: 12 }}>Choose a plan to start watching your websites 24/7.</div>
            <div className="sm-grid">
              {[
                { id: 'site_monitor_lite', name: 'Lite', price: 29, urls: 5, features: ['Email alerts', '10-min checks'] },
                { id: 'site_monitor_pro', name: 'Pro', price: 99, urls: 25, features: ['Email + WhatsApp', '5-min checks', 'Status page'] },
                { id: 'site_monitor_enterprise', name: 'Enterprise', price: 249, urls: '∞', features: ['AI RCA', '1-min checks', 'White-label', 'Priority SLA'] },
              ].map(p => (
                <div key={p.id} className="sm-card" style={{ padding: 16 }}>
                  <div className="sm-hdr" style={{ fontSize: 14 }}>{p.name}</div>
                  <div style={{ fontSize: 24, color: GOLD, fontFamily: "'JetBrains Mono',monospace", margin: '6px 0' }}>${p.price}<span style={{ fontSize: 12, color: '#888' }}>/mo CAD</span></div>
                  <div style={{ fontSize: 11, color: '#888' }}>{p.urls} URLs</div>
                  <ul style={{ fontSize: 12, color: '#ccc', paddingLeft: 16, margin: '8px 0' }}>
                    {p.features.map(f => <li key={f}>{f}</li>)}
                  </ul>
                  <button className="sm-btn sm-btn-solid" onClick={() => upgrade(p.id)} data-testid={`upgrade-${p.id}`}>Subscribe</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {tier === 'free' && (
          <div className="sm-card" style={{ marginBottom: 20, borderColor: AMBER }} data-testid="free-trial-banner">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <div className="sm-hdr" style={{ fontSize: 14, color: AMBER }}>FREE TRIAL ACTIVE</div>
                <div className="sm-body" style={{ color: '#ccc', fontSize: 13 }}>Ends {plan.trial_ends_at ? new Date(plan.trial_ends_at).toLocaleDateString() : '—'}. Upgrade to unlock more URLs + WhatsApp alerts.</div>
              </div>
              <button className="sm-btn sm-btn-solid" onClick={() => upgrade('site_monitor_lite')} data-testid="upgrade-from-free">Upgrade — $29/mo</button>
            </div>
          </div>
        )}

        {/* Add URL */}
        {tier !== 'none' && (
          <div className="sm-card" style={{ marginBottom: 20 }}>
            <div className="sm-hdr" style={{ fontSize: 14, marginBottom: 12 }}>Add URL to Monitor</div>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr auto', gap: 10, alignItems: 'center' }}>
              <input className="sm-input" placeholder="https://yourdomain.com/checkout" value={newUrl} onChange={e => setNewUrl(e.target.value)} data-testid="new-url-input" />
              <input className="sm-input" placeholder="Label (optional)" value={newLabel} onChange={e => setNewLabel(e.target.value)} data-testid="new-label-input" />
              <button className="sm-btn sm-btn-solid" onClick={addUrl} disabled={adding} data-testid="add-url-btn">{adding ? 'Adding…' : '+ Add'}</button>
            </div>
          </div>
        )}

        {/* Endpoints matrix */}
        <div className="sm-card" style={{ marginBottom: 20 }}>
          <div className="sm-hdr" style={{ fontSize: 14, marginBottom: 12 }}>Monitored URLs ({data.endpoints?.length || 0})</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="sm-table" data-testid="endpoints-table">
              <thead><tr><th></th><th>Label / URL</th><th>Uptime</th><th>Avg Latency</th><th>Last Check</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {(!data.endpoints || data.endpoints.length === 0) && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', color: '#666', padding: 28 }}>No URLs yet. Add one above to start monitoring.</td></tr>
                )}
                {data.endpoints?.map(e => {
                  const upOk = e.uptime_pct >= 99;
                  const dotColor = e.uptime_pct == null ? '#555' : upOk ? GREEN : e.uptime_pct >= 80 ? AMBER : RED;
                  return (
                    <tr key={e.endpoint_id} data-testid={`ep-${e.endpoint_id}`}>
                      <td><span className="sm-dot" style={{ background: dotColor }} /></td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{e.label || e.url}</div>
                        <div className="sm-mono" style={{ fontSize: 11, color: '#888' }}>{e.method} {e.url}</div>
                      </td>
                      <td className="sm-mono" style={{ color: dotColor }}>{e.uptime_pct != null ? `${e.uptime_pct}%` : '—'}</td>
                      <td className="sm-mono">{e.avg_latency_ms ? `${e.avg_latency_ms}ms` : '—'}</td>
                      <td className="sm-mono" style={{ fontSize: 11 }}>{e.last_ts ? new Date(e.last_ts).toLocaleTimeString() : '—'}</td>
                      <td className="sm-mono" style={{ color: e.last_passed ? GREEN : e.last_passed === false ? RED : '#888' }}>{e.last_status || '—'}</td>
                      <td><button className="sm-btn" style={{ padding: '4px 10px', fontSize: 10 }} onClick={() => removeUrl(e.endpoint_id)} data-testid={`del-${e.endpoint_id}`}>Remove</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Incidents */}
        <div className="sm-card" style={{ marginBottom: 20 }}>
          <div className="sm-hdr" style={{ fontSize: 14, marginBottom: 12 }}>Recent Incidents</div>
          {incidents.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#4ADE80', padding: 16 }}>No incidents — all clear 🟢</div>
          ) : (
            <table className="sm-table" data-testid="incidents-table">
              <thead><tr><th>URL</th><th>Started</th><th>Duration</th><th>Status</th><th>Code</th></tr></thead>
              <tbody>
                {incidents.map(inc => (
                  <tr key={inc.incident_id}>
                    <td className="sm-mono" style={{ fontSize: 12 }}>{inc.url}</td>
                    <td className="sm-mono" style={{ fontSize: 12 }}>{new Date(inc.started_at).toLocaleString()}</td>
                    <td className="sm-mono">{inc.duration_s ? `${Math.floor(inc.duration_s / 60)}m ${inc.duration_s % 60}s` : 'ongoing'}</td>
                    <td>
                      <span className="sm-pill" style={{ background: inc.status === 'open' ? 'rgba(239,68,68,0.15)' : 'rgba(74,222,128,0.15)', color: inc.status === 'open' ? RED : GREEN }}>
                        {inc.status}
                      </span>
                    </td>
                    <td className="sm-mono" style={{ color: RED }}>{inc.status_code}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Trust Badge + Public Status Page (PAID tier only) */}
        {tier === 'paid' && plan?.service_id && plan.service_id !== 'site_monitor_lite' && (
          <TrustBadgePanel bin={plan.bin || ''} />
        )}
        </div>
      </div>
    </>
  );
}

function TrustBadgePanel({ bin: propBin }) {
  const [copied, setCopied] = useState('');
  const token = getPlatformToken();
  const [bin, setBin] = useState(propBin);

  // Fallback: decode bin from token if not in plan
  useEffect(() => {
    if (!bin && token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setBin(payload.bin || payload.business_id || payload.tenant_id || payload.email);
      } catch {}
    }
  }, [bin, token]);

  const badgeSnippet = `<script src="${API}/api/static/aurem-badge.js" data-bin="${bin}" async></script>`;
  const statusUrl = `${window.location.origin}/status/${encodeURIComponent(bin)}`;

  const copy = async (text, key) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(''), 2000);
    } catch {}
  };

  return (
    <div className="sm-card" style={{ marginTop: 20, borderColor: 'rgba(201,168,76,0.3)' }} data-testid="trust-badge-panel">
      <div className="sm-hdr" style={{ fontSize: 14, marginBottom: 12 }}>
        <span style={{ background: 'linear-gradient(90deg,#C9A84C,#F59E0B)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Trust Signals — Embed on Your Site
        </span>
      </div>
      <div className="sm-body" style={{ color: '#ccc', fontSize: 14, marginBottom: 16 }}>
        Show your customers you're serious about uptime. Embed a live "Monitored by AUREM" badge on your site, or share your public status page.
      </div>

      {/* Badge snippet */}
      <div style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 11, color: '#888', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 8 }}>
          🪄 Live Trust Badge — paste into your site's <code style={{ background: '#1a1a1a', padding: '2px 6px', borderRadius: 4, color: GOLD }}>&lt;body&gt;</code>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <pre style={{ flex: 1, background: 'rgba(0,0,0,0.5)', padding: 12, borderRadius: 8, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: '#E8E0D0', overflowX: 'auto', margin: 0, border: '1px solid rgba(201,168,76,0.1)' }} data-testid="badge-snippet">
            {badgeSnippet}
          </pre>
          <button className="sm-btn" onClick={() => copy(badgeSnippet, 'badge')} style={{ minWidth: 90 }} data-testid="copy-badge-btn">
            {copied === 'badge' ? '✓ COPIED' : 'COPY'}
          </button>
        </div>
        <div style={{ fontSize: 11, color: '#666', marginTop: 6 }}>
          Shows a floating pill at bottom-right with live uptime %. Auto-updates every 5 min.
        </div>
      </div>

      {/* Public status page URL */}
      <div>
        <div style={{ fontSize: 11, color: '#888', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 8 }}>
          🌐 Public Status Page — share this link
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input className="sm-input" readOnly value={statusUrl} style={{ flex: 1 }} data-testid="status-url-input" />
          <button className="sm-btn" onClick={() => copy(statusUrl, 'url')} style={{ minWidth: 90 }} data-testid="copy-url-btn">
            {copied === 'url' ? '✓ COPIED' : 'COPY'}
          </button>
          <a href={statusUrl} target="_blank" rel="noopener noreferrer" className="sm-btn sm-btn-solid" style={{ textDecoration: 'none' }} data-testid="view-status-btn">VIEW →</a>
        </div>
        <div style={{ fontSize: 11, color: '#666', marginTop: 6 }}>
          Read-only page, no login required. Perfect for client proposals + sales calls.
        </div>
      </div>
    </div>
  );
}
