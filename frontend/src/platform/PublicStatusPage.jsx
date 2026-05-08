/**
 * AUREM Public Status Page
 * Route: /status/:bin  (no auth required — shareable trust signal)
 */
import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const GOLD = '#C9A84C';
const OBSIDIAN = '#0D0D0D';
const GREEN = '#4ADE80';
const AMBER = '#F59E0B';
const RED = '#EF4444';
const PANEL = 'rgba(13,13,13,0.85)';
const BORDER = 'rgba(201,168,76,0.14)';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700;900&family=Cormorant+Garamond:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
* { box-sizing:border-box; }
.ps-root { min-height:100vh; background:${OBSIDIAN}; color:#E8E0D0; padding:48px 24px 80px; }
.ps-container { max-width:1100px; margin:0 auto; }
.ps-brand { font-family:'Cinzel Decorative',serif; color:${GOLD}; font-size:18px; letter-spacing:0.1em; margin-bottom:32px; }
.ps-biz { font-family:'Cinzel Decorative',serif; font-size:36px; color:#fff; letter-spacing:0.03em; margin-bottom:8px; line-height:1.1; }
.ps-sub { font-family:'Cormorant Garamond',serif; color:#999; font-size:18px; margin-bottom:40px; }
.ps-hero { text-align:center; padding:40px 20px; background:${PANEL}; border:1px solid ${BORDER}; border-radius:16px; backdrop-filter:blur(16px); margin-bottom:24px; }
.ps-hero-pct { font-family:'JetBrains Mono',monospace; font-size:72px; font-weight:700; line-height:1; }
.ps-hero-label { font-family:'JetBrains Mono',monospace; font-size:12px; letter-spacing:0.15em; color:#888; text-transform:uppercase; margin-top:12px; }
.ps-pill { display:inline-flex; align-items:center; gap:8px; padding:6px 16px; border-radius:999px; font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; letter-spacing:0.1em; margin-top:16px; }
.ps-pill-up { background:rgba(74,222,128,0.12); color:${GREEN}; border:1px solid rgba(74,222,128,0.3); }
.ps-pill-down { background:rgba(239,68,68,0.12); color:${RED}; border:1px solid rgba(239,68,68,0.3); }
.ps-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; margin-bottom:24px; }
.ps-card { background:${PANEL}; border:1px solid ${BORDER}; border-radius:14px; padding:20px; backdrop-filter:blur(16px); }
.ps-card-url { font-family:'JetBrains Mono',monospace; font-size:13px; color:${GOLD}; word-break:break-all; margin-bottom:6px; }
.ps-card-label { font-family:'Cormorant Garamond',serif; font-size:14px; color:#ccc; margin-bottom:12px; }
.ps-card-row { display:flex; justify-content:space-between; align-items:center; font-family:'JetBrains Mono',monospace; font-size:12px; margin-bottom:6px; }
.ps-card-row span:first-child { color:#888; letter-spacing:0.1em; text-transform:uppercase; font-size:10px; }
.ps-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; }
.ps-footer { text-align:center; margin-top:40px; padding:28px; background:${PANEL}; border:1px solid ${BORDER}; border-radius:14px; }
.ps-footer a { color:${GOLD}; text-decoration:none; font-family:'JetBrains Mono',monospace; font-size:12px; letter-spacing:0.1em; }
.ps-footer a:hover { text-decoration:underline; }
`;

export default function PublicStatusPage() {
  const { bin } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!bin) return;
    (async () => {
      try {
        const r = await fetch(`${API}/api/public/site-monitor/status/${encodeURIComponent(bin)}`);
        if (!r.ok) {
          if (r.status === 404) throw new Error('Status page not found — check the URL.');
          throw new Error(`HTTP ${r.status}`);
        }
        const j = await r.json();
        setData(j);
      } catch (e) {
        setError(e.message || 'Failed to load');
      } finally {
        setLoading(false);
      }
    })();
  }, [bin]);

  if (loading) return <div className="ps-root"><style>{CSS}</style><div style={{ textAlign: 'center', color: GOLD, paddingTop: '20vh' }}>Loading status…</div></div>;
  if (error || !data) return <div className="ps-root"><style>{CSS}</style><div className="ps-container"><div className="ps-card" style={{ borderColor: RED, color: RED, textAlign: 'center' }}>{error || 'Not found'}</div></div></div>;

  const uptime = data.overall_uptime_30d_pct;
  const allUp = data.open_incidents === 0;
  const uptimeColor = uptime == null ? '#888' : uptime >= 99 ? GREEN : uptime >= 95 ? AMBER : RED;

  return (
    <>
      <Helmet>
        <title>{data.business_name} — Status · AUREM</title>
        <meta name="description" content={`Live uptime status for ${data.business_name}. ${uptime != null ? uptime + '% uptime last 30 days.' : ''} Powered by AUREM.`} />
      </Helmet>
      <style>{CSS}</style>
      <div className="ps-root" data-testid="public-status-page">
        <div className="ps-container">
          <div className="ps-brand">AUREM · STATUS</div>

          <h1 className="ps-biz" data-testid="biz-name">{data.business_name}</h1>
          <p className="ps-sub">Live uptime monitoring by AUREM · {data.endpoints?.length || 0} services tracked</p>

          <div className="ps-hero">
            <div className="ps-hero-pct" style={{ color: uptimeColor }} data-testid="overall-uptime">
              {uptime != null ? `${uptime}%` : '—'}
            </div>
            <div className="ps-hero-label">Overall uptime · last 30 days</div>
            <div className={'ps-pill ' + (allUp ? 'ps-pill-up' : 'ps-pill-down')} data-testid="overall-status">
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: allUp ? GREEN : RED, display: 'inline-block' }} />
              {allUp ? 'ALL SYSTEMS OPERATIONAL' : `${data.open_incidents} INCIDENT(S) OPEN`}
            </div>
            <div style={{ marginTop: 12, fontSize: 12, color: '#666', fontFamily: "'JetBrains Mono',monospace" }}>
              {data.total_pings_30d?.toLocaleString()} checks completed in last 30 days
            </div>
          </div>

          <div className="ps-grid" data-testid="endpoints-grid">
            {(data.endpoints || []).map((e, i) => {
              const upColor = e.uptime_30d_pct == null ? '#888' : e.uptime_30d_pct >= 99 ? GREEN : e.uptime_30d_pct >= 95 ? AMBER : RED;
              return (
                <div key={i} className="ps-card">
                  <div className="ps-card-url">{e.url}</div>
                  {e.label && e.label !== e.url && <div className="ps-card-label">{e.label}</div>}
                  <div className="ps-card-row">
                    <span>UPTIME (30D)</span>
                    <span style={{ color: upColor, fontWeight: 700 }}>{e.uptime_30d_pct != null ? `${e.uptime_30d_pct}%` : '—'}</span>
                  </div>
                  <div className="ps-card-row">
                    <span>AVG LATENCY</span>
                    <span>{e.avg_latency_ms ? `${e.avg_latency_ms}ms` : '—'}</span>
                  </div>
                  <div className="ps-card-row">
                    <span>LAST CHECK</span>
                    <span style={{ fontSize: 11 }}>{e.last_check ? new Date(e.last_check).toLocaleTimeString() : '—'}</span>
                  </div>
                  <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', fontSize: 12 }}>
                    <span className="ps-dot" style={{ background: e.last_passed ? GREEN : e.last_passed === false ? RED : '#888' }} />
                    <span style={{ color: e.last_passed ? GREEN : e.last_passed === false ? RED : '#888' }}>
                      {e.last_passed ? 'UP' : e.last_passed === false ? 'DOWN' : 'NO DATA'}
                    </span>
                    <span style={{ marginLeft: 'auto', color: '#888', fontFamily: "'JetBrains Mono',monospace" }}>{e.last_status || '—'}</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="ps-footer">
            <Link to="/monitor-free">Want a status page for your site? Monitor free for 30 days →</Link>
            <div style={{ marginTop: 8, color: '#666', fontSize: 11, fontFamily: "'JetBrains Mono',monospace" }}>
              POWERED BY AUREM · aurem.live
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
