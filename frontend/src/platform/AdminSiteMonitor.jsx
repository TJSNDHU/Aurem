/**
 * AUREM Site Monitor — Admin Dashboard
 * Route: /admin/site-monitor
 * Super-admin only: aggregate MRR, active tenants, open incidents
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const GOLD = '#C9A84C';
const OBSIDIAN = '#0D0D0D';
const GREEN = '#4ADE80';
const AMBER = '#F59E0B';
const RED = '#EF4444';
const PANEL = 'rgba(13,13,13,0.85)';
const BORDER = 'rgba(201,168,76,0.14)';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cormorant+Garamond:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
.asm-root { min-height:100vh; background:${OBSIDIAN}; color:#E8E0D0; padding:32px 24px 80px; }
.asm-root * { box-sizing:border-box; }
.asm-card { background:${PANEL}; border:1px solid ${BORDER}; border-radius:14px; padding:20px; backdrop-filter:blur(12px); }
.asm-hdr { font-family:'Cinzel Decorative',serif; color:${GOLD}; letter-spacing:0.08em; }
.asm-mono { font-family:'JetBrains Mono',monospace; }
.asm-btn { background:transparent; border:1px solid ${GOLD}; color:${GOLD}; padding:8px 18px; border-radius:8px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:12px; letter-spacing:0.1em; transition:all 0.2s; }
.asm-btn:hover { background:${GOLD}; color:${OBSIDIAN}; }
.asm-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
.asm-stat { text-align:center; padding:18px; }
.asm-stat-value { font-family:'JetBrains Mono',monospace; font-size:30px; font-weight:700; color:${GOLD}; }
.asm-stat-label { font-size:10px; color:#888; letter-spacing:0.15em; text-transform:uppercase; margin-top:6px; }
.asm-table { width:100%; border-collapse:collapse; font-size:13px; }
.asm-table th { text-align:left; padding:10px 12px; color:#888; font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:0.1em; border-bottom:1px solid ${BORDER}; }
.asm-table td { padding:10px 12px; border-bottom:1px solid rgba(255,255,255,0.04); }
.asm-pill { display:inline-block; padding:3px 10px; border-radius:20px; font-size:10px; font-weight:700; letter-spacing:0.1em; font-family:'JetBrains Mono',monospace; }
`;

export default function AdminSiteMonitor() {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  const token = getPlatformToken();
  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchAll = useCallback(async () => {
    try {
      const [ovR, tR] = await Promise.all([
        fetch(`${API}/api/admin/site-monitor/overview`, { headers: authHeader }),
        fetch(`${API}/api/admin/site-monitor/tenants?limit=200`, { headers: authHeader }),
      ]);
      if (!ovR.ok) throw new Error(`Overview ${ovR.status}`);
      const ov = await ovR.json();
      const tj = await tR.json();
      setOverview(ov.overview);
      setTenants(tj.tenants || []);
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
    const id = setInterval(fetchAll, 30000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const scanNow = async () => {
    setScanning(true);
    try {
      await fetch(`${API}/api/admin/site-monitor/scan-now`, { method: 'POST', headers: authHeader });
      await fetchAll();
    } catch (e) { setError(e.message); }
    setScanning(false);
  };

  if (loading) {
    return <div className="asm-root"><style>{CSS}</style><div style={{ textAlign: 'center', color: GOLD, paddingTop: '20vh' }}>Loading…</div></div>;
  }

  return (
    <>
      <style>{CSS}</style>
      <div className="asm-root" data-testid="admin-site-monitor">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
          <div>
            <div className="asm-hdr" style={{ fontSize: 28 }}>Site Monitor · Admin</div>
            <div style={{ color: '#888', fontSize: 14, marginTop: 4, fontFamily: "'Cormorant Garamond',serif" }}>
              Aggregate metrics, active subscribers, and incidents across all tenants
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <Link to="/admin/mission-control" className="asm-btn" style={{ textDecoration: 'none' }}>← Mission Control</Link>
            <button className="asm-btn" onClick={scanNow} disabled={scanning} data-testid="scan-now-btn">
              {scanning ? 'Scanning…' : 'Scan All Now'}
            </button>
          </div>
        </div>

        {error && <div className="asm-card" style={{ borderColor: RED, color: RED, marginBottom: 16 }}>{error}</div>}

        {overview && (
          <div className="asm-grid" style={{ marginBottom: 20 }}>
            <div className="asm-card asm-stat" data-testid="stat-mrr">
              <div className="asm-stat-value">${overview.mrr_cad}</div>
              <div className="asm-stat-label">MRR (CAD)</div>
            </div>
            <div className="asm-card asm-stat" data-testid="stat-paid">
              <div className="asm-stat-value">{overview.active_paid_subs}</div>
              <div className="asm-stat-label">Paid Subscribers</div>
            </div>
            <div className="asm-card asm-stat" data-testid="stat-free">
              <div className="asm-stat-value" style={{ color: AMBER }}>{overview.active_free_trials}</div>
              <div className="asm-stat-label">Free Trials</div>
            </div>
            <div className="asm-card asm-stat" data-testid="stat-urls">
              <div className="asm-stat-value">{overview.active_endpoints}</div>
              <div className="asm-stat-label">URLs Watched</div>
            </div>
            <div className="asm-card asm-stat" data-testid="stat-pass">
              <div className="asm-stat-value" style={{ color: overview.recent_pass_rate_pct >= 99 ? GREEN : overview.recent_pass_rate_pct >= 90 ? AMBER : RED }}>
                {overview.recent_pass_rate_pct ?? '—'}%
              </div>
              <div className="asm-stat-label">Recent Pass Rate</div>
            </div>
            <div className="asm-card asm-stat" data-testid="stat-incidents">
              <div className="asm-stat-value" style={{ color: overview.open_incidents === 0 ? GREEN : RED }}>{overview.open_incidents}</div>
              <div className="asm-stat-label">Open Incidents</div>
            </div>
          </div>
        )}

        <div className="asm-card">
          <div className="asm-hdr" style={{ fontSize: 16, marginBottom: 12 }}>All Tenants ({tenants.length})</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="asm-table" data-testid="tenants-table">
              <thead><tr><th>Email</th><th>Tier</th><th>BIN</th><th>URLs</th><th>Joined</th></tr></thead>
              <tbody>
                {tenants.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', color: '#666', padding: 28 }}>No tenants yet.</td></tr>
                )}
                {tenants.map(t => (
                  <tr key={t.email} data-testid={`tenant-${t.email}`}>
                    <td className="asm-mono" style={{ fontSize: 12 }}>{t.email}</td>
                    <td>
                      <span className="asm-pill" style={{
                        background: t.plan_tier === 'paid' ? 'rgba(74,222,128,0.15)' : 'rgba(245,158,11,0.15)',
                        color: t.plan_tier === 'paid' ? GREEN : AMBER,
                      }}>{t.plan_tier || 'none'}</span>
                    </td>
                    <td className="asm-mono" style={{ fontSize: 11, color: '#888' }}>{t.bin || '—'}</td>
                    <td className="asm-mono">{t.urls}</td>
                    <td className="asm-mono" style={{ fontSize: 11, color: '#888' }}>{t.last_created ? new Date(t.last_created).toLocaleDateString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
