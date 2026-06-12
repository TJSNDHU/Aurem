/**
 * AdminSupplyChain — Security Posture cockpit (iter D-82c)
 * =======================================================
 * Surfaces the autonomous supply-chain / secret / SAST sweep + the
 * Council-gated auto-fix engine. All data is LIVE (no mock):
 *   GET  /api/admin/supply-chain/latest        — posture snapshot + findings
 *   GET  /api/admin/supply-chain/history       — recent sweep summaries
 *   GET  /api/admin/supply-chain/remediations  — applied-fix audit log
 *   POST /api/admin/supply-chain/scan          — trigger a fresh sweep
 *   POST /api/admin/supply-chain/autofix       — Council-gated auto-apply (no human)
 *   POST /api/admin/supply-chain/remediate     — suggest-only plan
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  ShieldCheck, RefreshCw, Play, Bot, AlertTriangle, KeyRound, Package,
  FileCode, CheckCircle2, XCircle, Clock, Loader2,
} from 'lucide-react';

const API = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');

const getAdminToken = () =>
  sessionStorage.getItem('platform_token') ||
  localStorage.getItem('platform_token') ||
  localStorage.getItem('aurem_admin_token') ||
  sessionStorage.getItem('aurem_admin_token') ||
  localStorage.getItem('token') ||
  '';

const api = async (path, method = 'GET') => {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: { Authorization: `Bearer ${getAdminToken()}` },
  });
  if (!r.ok) throw new Error(`${path} → HTTP ${r.status}`);
  return r.json();
};

const SEV = {
  critical: { c: '#E0574F', label: 'Critical' },
  high:     { c: '#F0A030', label: 'High' },
  medium:   { c: '#C9A227', label: 'Medium' },
  low:      { c: '#4A8FD4', label: 'Low' },
  info:     { c: '#7A7468', label: 'Info' },
};
const CAT_ICON = { SECRET: KeyRound, SCA: Package, SAST: FileCode };

const Card = ({ children, style }) => (
  <div style={{
    background: 'rgba(15,18,28,0.55)', border: '1px solid rgba(212,175,55,0.14)',
    borderRadius: 14, padding: 18, ...style,
  }}>{children}</div>
);

export default function AdminSupplyChain() {
  const [snap, setSnap] = useState(null);
  const [remediations, setRemediations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');
  const [catFilter, setCatFilter] = useState('ALL');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [latest, rem] = await Promise.all([
        api('/api/admin/supply-chain/latest'),
        api('/api/admin/supply-chain/remediations?limit=50').catch(() => ({ log: [] })),
      ]);
      setSnap(latest.snapshot || null);
      setRemediations(rem.log || []);
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const trigger = async (path, label) => {
    setBusy(label); setMsg('');
    try {
      const r = await api(path, 'POST');
      setMsg(r.message || `${label} started.`);
      // Background jobs — refresh after a delay.
      setTimeout(load, label === 'scan' ? 8000 : 5000);
    } catch (e) {
      setMsg(`${label} failed: ${e.message}`);
    } finally {
      setBusy('');
    }
  };

  const sev = snap?.by_severity || {};
  const cat = snap?.by_category || {};
  const byTool = snap?.by_tool || {};
  const findings = (snap?.findings || []).filter(f => catFilter === 'ALL' || f.category === catFilter);
  const score = snap?.posture_score ?? null;

  return (
    <div data-testid="admin-supply-chain" style={{ padding: 24, color: '#EDE8DF', maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShieldCheck style={{ width: 26, height: 26, color: '#4AD4A0' }} />
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Supply-Chain Security</h1>
            <p style={{ fontSize: 12, color: '#9A9388', margin: '2px 0 0' }}>
              Autonomous SAST · secret · dependency-CVE sweep with Council-gated auto-fix
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button data-testid="sc-refresh-btn" onClick={load} disabled={loading}
            style={btn('#4A8FD4')}>
            <RefreshCw style={{ width: 14, height: 14 }} /> Refresh
          </button>
          <button data-testid="sc-scan-btn" onClick={() => trigger('/api/admin/supply-chain/scan', 'scan')} disabled={!!busy}
            style={btn('#C9A227')}>
            {busy === 'scan' ? <Loader2 className="spin" style={{ width: 14, height: 14 }} /> : <Play style={{ width: 14, height: 14 }} />} Run Sweep
          </button>
          <button data-testid="sc-autofix-btn" onClick={() => trigger('/api/admin/supply-chain/autofix', 'autofix')} disabled={!!busy}
            style={btn('#4AD4A0')}>
            {busy === 'autofix' ? <Loader2 className="spin" style={{ width: 14, height: 14 }} /> : <Bot style={{ width: 14, height: 14 }} />} Council Auto-Fix
          </button>
        </div>
      </div>

      {msg && (
        <div data-testid="sc-msg" style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 10,
          background: 'rgba(74,143,212,0.12)', border: '1px solid rgba(74,143,212,0.3)', fontSize: 13 }}>
          {msg}
        </div>
      )}

      {loading && !snap ? (
        <Card><div style={{ display: 'flex', gap: 10, alignItems: 'center', color: '#9A9388' }}>
          <Loader2 className="spin" style={{ width: 16, height: 16 }} /> Loading posture…
        </div></Card>
      ) : !snap ? (
        <Card><div style={{ color: '#9A9388' }}>No sweep yet — click <b>Run Sweep</b> to start the first scan.</div></Card>
      ) : (
        <>
          {/* Posture score + severity */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 12, marginBottom: 16 }}>
            <Card style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: '#9A9388', letterSpacing: '0.1em' }}>POSTURE</div>
              <div data-testid="sc-score" style={{ fontSize: 40, fontWeight: 800, color: score >= 70 ? '#4AD4A0' : score >= 40 ? '#F0A030' : '#E0574F' }}>
                {score}<span style={{ fontSize: 16, color: '#7A7468' }}>/100</span>
              </div>
              <div style={{ fontSize: 11, color: '#7A7468' }}>{snap.total_findings} findings</div>
            </Card>
            {Object.entries(SEV).map(([k, v]) => (
              <Card key={k} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 11, color: v.c, letterSpacing: '0.1em' }}>{v.label.toUpperCase()}</div>
                <div style={{ fontSize: 32, fontWeight: 700 }}>{sev[k] || 0}</div>
              </Card>
            ))}
          </div>

          {/* Tool status */}
          <Card style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#9A9388', marginBottom: 10, letterSpacing: '0.1em' }}>SCANNERS</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {Object.entries(byTool).map(([tool, info]) => (
                <div key={tool} data-testid={`sc-tool-${tool}`} style={{ display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 12px', borderRadius: 999, fontSize: 12,
                  background: info.status === 'ok' ? 'rgba(74,212,160,0.1)' : 'rgba(224,87,79,0.1)',
                  border: `1px solid ${info.status === 'ok' ? 'rgba(74,212,160,0.3)' : 'rgba(224,87,79,0.3)'}` }}>
                  {info.status === 'ok' ? <CheckCircle2 style={{ width: 13, height: 13, color: '#4AD4A0' }} />
                    : <XCircle style={{ width: 13, height: 13, color: '#E0574F' }} />}
                  <b>{tool}</b><span style={{ color: '#7A7468' }}>{info.count} · {info.category}</span>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: '#7A7468', marginTop: 10 }}>
              Last sweep: {snap.scanned_at?.replace('T', ' ').slice(0, 19)} UTC · {snap.duration_s}s · trigger “{snap.trigger}”
            </div>
          </Card>

          {/* Findings */}
          <Card style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ fontSize: 12, color: '#9A9388', letterSpacing: '0.1em' }}>FINDINGS {snap.findings_truncated ? '(top 250)' : ''}</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {['ALL', 'SECRET', 'SCA', 'SAST'].map(c => (
                  <button key={c} data-testid={`sc-filter-${c}`} onClick={() => setCatFilter(c)}
                    style={{ ...pill(catFilter === c), fontSize: 11 }}>
                    {c}{c !== 'ALL' ? ` (${cat[c] || 0})` : ''}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ maxHeight: 420, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {findings.slice(0, 120).map((f, i) => {
                const Ic = CAT_ICON[f.category] || AlertTriangle;
                const sv = SEV[f.severity] || SEV.medium;
                return (
                  <div key={i} data-testid="sc-finding" style={{ display: 'flex', gap: 10, padding: '8px 10px', borderRadius: 8,
                    background: 'rgba(255,255,255,0.02)', borderLeft: `3px solid ${sv.c}` }}>
                    <Ic style={{ width: 15, height: 15, color: sv.c, flexShrink: 0, marginTop: 2 }} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.title}</div>
                      <div style={{ fontSize: 11, color: '#7A7468', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {f.tool} · {f.location} {f.fix ? `· ${f.fix}` : ''}
                      </div>
                    </div>
                    <span style={{ fontSize: 10, color: sv.c, fontWeight: 600, alignSelf: 'center' }}>{sv.label}</span>
                  </div>
                );
              })}
              {findings.length === 0 && <div style={{ color: '#7A7468', fontSize: 13 }}>No findings in this category.</div>}
            </div>
          </Card>

          {/* Remediation audit log */}
          <Card>
            <div style={{ fontSize: 12, color: '#9A9388', marginBottom: 12, letterSpacing: '0.1em' }}>
              COUNCIL FIX LOG <span style={{ color: '#7A7468' }}>({remediations.length})</span>
            </div>
            {remediations.length === 0 ? (
              <div style={{ color: '#7A7468', fontSize: 13 }}>No auto-fixes applied yet. Run Council Auto-Fix to let approved upgrades apply themselves.</div>
            ) : (
              <div style={{ maxHeight: 300, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {remediations.map((r, i) => {
                  const ok = (r.result || {}).success;
                  return (
                    <div key={i} data-testid="sc-remediation" style={{ display: 'flex', gap: 10, padding: '8px 10px', borderRadius: 8,
                      background: 'rgba(255,255,255,0.02)', fontSize: 12, alignItems: 'center' }}>
                      {ok ? <CheckCircle2 style={{ width: 14, height: 14, color: '#4AD4A0' }} />
                        : <XCircle style={{ width: 14, height: 14, color: '#E0574F' }} />}
                      <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        <b>{r.kind}</b> · {r.identifier}
                        {r.result?.from ? ` · ${r.result.from} → ${r.result.to}` : ''}
                      </span>
                      {r.verdict && <span style={{ fontSize: 10, color: '#9B6DD4' }}>{r.verdict}</span>}
                      <Clock style={{ width: 11, height: 11, color: '#7A7468' }} />
                      <span style={{ fontSize: 10, color: '#7A7468' }}>{(r.applied_at || '').slice(11, 19)}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </>
      )}
      <style>{`.spin{animation:scspin 1s linear infinite}@keyframes scspin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

const btn = (accent) => ({
  display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10,
  background: `${accent}1A`, border: `1px solid ${accent}55`, color: '#EDE8DF',
  fontSize: 12, cursor: 'pointer', fontWeight: 600,
});
const pill = (active) => ({
  padding: '5px 12px', borderRadius: 999, cursor: 'pointer',
  background: active ? 'rgba(212,175,55,0.18)' : 'transparent',
  border: `1px solid ${active ? 'rgba(212,175,55,0.5)' : 'rgba(255,255,255,0.12)'}`,
  color: active ? '#EDE8DF' : '#9A9388',
});
