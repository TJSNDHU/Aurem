/**
 * AUREM System Pulse Live Dashboard
 * Route: /admin/system-pulse-live
 * Shows: Live pulse status (10-min endpoint sweep) + Deep QA journey results (weekly)
 */
import React, { useState, useEffect, useCallback } from 'react';
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
.spulse-root { min-height:100vh; background:${OBSIDIAN}; color:#E8E0D0; padding:32px 24px 80px; }
.spulse-root * { box-sizing:border-box; }
.spulse-card { background:${PANEL}; border:1px solid ${BORDER}; border-radius:14px; padding:20px; backdrop-filter:blur(12px); }
.spulse-hdr { font-family:'Cinzel Decorative',serif; color:${GOLD}; letter-spacing:0.08em; }
.spulse-body { font-family:'Cormorant Garamond',serif; }
.spulse-mono { font-family:'JetBrains Mono',monospace; }
.spulse-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; vertical-align:middle; }
.spulse-pill { display:inline-block; padding:3px 10px; border-radius:20px; font-size:10px; font-weight:700; letter-spacing:0.1em; font-family:'JetBrains Mono',monospace; }
.spulse-btn { background:transparent; border:1px solid ${GOLD}; color:${GOLD}; padding:8px 18px; border-radius:8px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:12px; letter-spacing:0.1em; transition:all 0.2s; }
.spulse-btn:hover { background:${GOLD}; color:${OBSIDIAN}; }
.spulse-btn:disabled { opacity:0.4; cursor:not-allowed; }
.spulse-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; }
.spulse-stat { text-align:center; padding:18px; }
.spulse-stat-value { font-family:'JetBrains Mono',monospace; font-size:32px; font-weight:700; color:${GOLD}; }
.spulse-stat-label { font-size:11px; color:#999; letter-spacing:0.15em; text-transform:uppercase; margin-top:6px; }
.spulse-table { width:100%; border-collapse:collapse; font-size:13px; }
.spulse-table th { text-align:left; padding:10px 12px; color:#888; font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:0.1em; border-bottom:1px solid ${BORDER}; }
.spulse-table td { padding:10px 12px; border-bottom:1px solid rgba(255,255,255,0.04); }
.spulse-table tr:hover td { background:rgba(201,168,76,0.04); }
@keyframes spulse-pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.spulse-live { animation:spulse-pulse 2s ease-in-out infinite; }
`;

const statusColor = (passed, status) => {
  if (passed) return GREEN;
  if (status === 0) return RED;
  return AMBER;
};

const getAdminToken = () => getPlatformToken();

export default function SystemPulseLive() {
  const [loading, setLoading] = useState(true);
  const [latest, setLatest] = useState(null);
  const [endpoints, setEndpoints] = useState([]);
  const [history, setHistory] = useState([]);
  const [deep, setDeep] = useState(null);
  const [guardian, setGuardian] = useState(null);
  const [guardianActions, setGuardianActions] = useState([]);
  const [sovereign, setSovereign] = useState(null);
  const [running, setRunning] = useState(false);
  const [runningDeep, setRunningDeep] = useState(false);
  const [error, setError] = useState('');
  const [windowH, setWindowH] = useState(24);

  const token = getAdminToken();
  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchAll = useCallback(async () => {
    if (!token) {
      setError('Admin token missing — please re-login.');
      setLoading(false);
      return;
    }
    try {
      const [latestR, epR, histR, deepR, guardR, guardActR, sovR] = await Promise.all([
        fetch(`${API}/api/qa/pulse/latest`, { headers: authHeader }),
        fetch(`${API}/api/qa/pulse/endpoints?window_hours=${windowH}`, { headers: authHeader }),
        fetch(`${API}/api/qa/pulse/history?limit=30`, { headers: authHeader }),
        fetch(`${API}/api/qa/deep/latest`, { headers: authHeader }),
        fetch(`${API}/api/qa/guardian/status`, { headers: authHeader }),
        fetch(`${API}/api/qa/guardian/actions?limit=10`, { headers: authHeader }),
        fetch(`${API}/api/sovereign/telemetry-status`, { headers: authHeader }),
      ]);
      if (!latestR.ok) throw new Error(`Pulse ${latestR.status}`);
      const latestJ = await latestR.json();
      const epJ = await epR.json();
      const histJ = await histR.json();
      const deepJ = await deepR.json();
      const guardJ = guardR.ok ? await guardR.json() : null;
      const guardActJ = guardActR.ok ? await guardActR.json() : { actions: [] };
      const sovJ = sovR.ok ? await sovR.json() : null;
      setLatest(latestJ.run);
      setEndpoints(epJ.endpoints || []);
      setHistory(histJ.runs || []);
      setDeep(deepJ.run);
      setGuardian(guardJ);
      setGuardianActions(guardActJ.actions || []);
      setSovereign(sovJ);
      setError('');
    } catch (e) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [token, windowH]);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30000); // 30s auto-refresh
    return () => clearInterval(id);
  }, [fetchAll]);

  const triggerPulse = async () => {
    setRunning(true);
    try {
      await fetch(`${API}/api/qa/pulse/run-now`, { method: 'POST', headers: authHeader });
      await fetchAll();
    } catch (e) {
      setError(e.message || 'Pulse failed');
    }
    setRunning(false);
  };

  const triggerDeep = async () => {
    setRunningDeep(true);
    try {
      await fetch(`${API}/api/qa/deep/run-now?analyze=true`, { method: 'POST', headers: authHeader });
      await fetchAll();
    } catch (e) {
      setError(e.message || 'Deep QA failed');
    }
    setRunningDeep(false);
  };

  if (loading) {
    return (
      <>
        <style>{CSS}</style>
        <div className="spulse-root" style={{ textAlign: 'center', paddingTop: '20vh' }}>
          <div className="spulse-body" style={{ color: GOLD, fontSize: 20 }}>Loading System Pulse…</div>
        </div>
      </>
    );
  }

  const passRate = latest?.pass_rate ?? 0;
  const statusGlobal = passRate === 100 ? GREEN : passRate >= 80 ? AMBER : RED;

  return (
    <>
      <style>{CSS}</style>
      <div className="spulse-root" data-testid="system-pulse-live">
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
          <div>
            <div className="spulse-hdr" style={{ fontSize: 28 }}>System Pulse · Live</div>
            <div className="spulse-body" style={{ color: '#888', fontSize: 14, marginTop: 4 }}>
              Hybrid QA Bot — 10-min endpoint sweep + weekly journey simulation
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Link to="/admin/mission-control" className="spulse-btn" style={{ textDecoration: 'none' }} data-testid="back-mc-btn">← Mission Control</Link>
            <button className="spulse-btn" onClick={triggerPulse} disabled={running} data-testid="run-pulse-btn">
              {running ? 'Running…' : 'Run Pulse Now'}
            </button>
            <button className="spulse-btn" onClick={triggerDeep} disabled={runningDeep} data-testid="run-deep-btn">
              {runningDeep ? 'Running Deep QA…' : 'Run Deep QA'}
            </button>
          </div>
        </div>

        {error && (
          <div className="spulse-card" style={{ borderColor: RED, marginBottom: 16, color: RED }} data-testid="error-banner">{error}</div>
        )}

        {/* Top stats */}
        <div className="spulse-grid" style={{ marginBottom: 20 }}>
          <div className="spulse-card spulse-stat">
            <div className="spulse-stat-value" style={{ color: statusGlobal }} data-testid="stat-pass-rate">{passRate}%</div>
            <div className="spulse-stat-label">Pass Rate (latest)</div>
          </div>
          <div className="spulse-card spulse-stat">
            <div className="spulse-stat-value" data-testid="stat-passed">
              {latest?.passed ?? 0}<span style={{ color: '#555', fontSize: 22 }}>/{latest?.total ?? 0}</span>
            </div>
            <div className="spulse-stat-label">Endpoints Passing</div>
          </div>
          <div className="spulse-card spulse-stat">
            <div className="spulse-stat-value" data-testid="stat-latency">{latest?.avg_latency_ms ?? 0}<span style={{ fontSize: 18, color: '#777' }}>ms</span></div>
            <div className="spulse-stat-label">Avg Latency</div>
          </div>
          <div className="spulse-card spulse-stat">
            <div className="spulse-stat-value" data-testid="stat-last-run">
              {latest ? new Date(latest.finished_at).toLocaleTimeString() : '—'}
            </div>
            <div className="spulse-stat-label">Last Sweep <span className="spulse-live" style={{ color: GREEN }}>●</span></div>
          </div>
        </div>

        {/* Auto-Latency Guardian — iter 322f */}
        {guardian && (
          <div className="spulse-card" style={{ marginBottom: 20 }} data-testid="latency-guardian-panel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {(() => {
                  const dot = guardian.state === 'green' ? GREEN
                    : guardian.state === 'yellow' ? AMBER : RED;
                  const label = guardian.state === 'green'
                    ? `All endpoints under ${guardian.threshold_ms ?? 400}ms`
                    : guardian.state === 'yellow'
                      ? `Auto-fix running (${guardian.active_triages || 0})`
                      : `${guardian.alert_count || 0} need manual review`;
                  return (
                    <div data-testid="latency-guardian-pill"
                         style={{ display: 'flex', alignItems: 'center', gap: 10,
                                  padding: '8px 14px', borderRadius: 999,
                                  background: 'rgba(255,255,255,0.04)',
                                  border: `1px solid ${dot}` }}>
                      <span className="spulse-dot" style={{ background: dot, width: 8, height: 8, borderRadius: '50%' }} />
                      <span className="spulse-mono" style={{ color: dot, fontSize: 12, letterSpacing: '0.05em' }}>
                        AUTO-LATENCY GUARDIAN
                      </span>
                      <span style={{ color: '#bbb', fontSize: 12 }}>· {label}</span>
                    </div>
                  );
                })()}
              </div>
              <div className="spulse-mono" style={{ color: '#666', fontSize: 11 }}>
                Last 5 actions
              </div>
            </div>
            {guardianActions.length > 0 && (
              <div style={{ marginTop: 12 }} data-testid="latency-guardian-actions-row">
                {guardianActions.slice(0, 5).map((a, i) => {
                  const aColor = a.action_taken === 'alert_admin' ? RED
                    : a.action_taken && a.action_taken.startsWith('recovered') ? GREEN
                    : AMBER;
                  return (
                    <div key={i} style={{ display: 'flex', gap: 12, padding: '6px 0',
                                          borderTop: i ? '1px solid rgba(255,255,255,0.04)' : 'none',
                                          fontSize: 11, color: '#aaa' }}>
                      <span className="spulse-mono" style={{ color: '#666', minWidth: 70 }}>
                        {new Date(a.ts).toLocaleTimeString()}
                      </span>
                      <span className="spulse-mono" style={{ color: aColor, minWidth: 170 }}>
                        {a.action_taken}
                      </span>
                      <span className="spulse-mono" style={{ color: '#888', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {a.endpoint_id || a.path || '—'}
                      </span>
                      <span className="spulse-mono" style={{ color: '#666' }}>
                        {a.latency_before_ms ? `${Math.round(a.latency_before_ms)}ms` : ''}
                        {a.latency_after_ms != null ? ` → ${Math.round(a.latency_after_ms)}ms` : ''}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Sovereign Council Activity Feed — iter 322m Day 5 */}
        {sovereign && (
          <div className="spulse-card" style={{ marginBottom: 20 }} data-testid="sovereign-council-panel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {(() => {
                  const wd = sovereign.watchdog?.state || 'green';
                  const lg = sovereign.latency_guardian?.state || 'green';
                  const lint = sovereign.boundary_lint?.passed;
                  const dot = wd === 'red' || lg === 'red' || lint === false ? RED
                    : wd === 'yellow' || lg === 'yellow' ? AMBER : GREEN;
                  return (
                    <div data-testid="sovereign-council-pill"
                         style={{ display: 'flex', alignItems: 'center', gap: 10,
                                  padding: '8px 14px', borderRadius: 999,
                                  background: 'rgba(255,255,255,0.04)',
                                  border: `1px solid ${dot}` }}>
                      <span style={{ background: dot, width: 8, height: 8, borderRadius: '50%', display: 'inline-block' }} />
                      <span className="spulse-mono" style={{ color: dot, fontSize: 12, letterSpacing: '0.05em' }}>
                        SOVEREIGN COUNCIL
                      </span>
                      <span style={{ color: '#bbb', fontSize: 12 }}>· {sovereign.council_sessions_24h || 0} sessions / 24h</span>
                    </div>
                  );
                })()}
              </div>
              <div className="spulse-mono" style={{ color: '#666', fontSize: 11 }}>
                Memory Guard · Watchdog · Latency Guardian · Boundary Lint
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, fontSize: 11 }}>
              <div data-testid="sov-memory-guard">
                <div style={{ color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Memory Guard</div>
                <div style={{ color: '#ddd' }}>
                  {sovereign.memory_guard?.pending_review ?? 0} pending · {sovereign.memory_guard?.promoted_total ?? 0} promoted · req={sovereign.memory_guard?.required_stamps ?? 2}
                </div>
              </div>
              <div data-testid="sov-watchdog">
                <div style={{ color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Watchdog</div>
                <div style={{ color: sovereign.watchdog?.state === 'red' ? RED : sovereign.watchdog?.state === 'yellow' ? AMBER : GREEN }}>
                  {sovereign.watchdog?.state ?? '—'} · {sovereign.watchdog?.reason ?? ''}
                </div>
              </div>
              <div data-testid="sov-pillar-fulfiller">
                <div style={{ color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Pillar Fulfiller</div>
                <div style={{ color: '#ddd' }}>
                  {sovereign.pillar_fulfiller?.last_fulfilled_at
                    ? `P${sovereign.pillar_fulfiller.last_pillar} · ${sovereign.pillar_fulfiller.last_attempt_ok ? 'ok' : 'fail'} · ${new Date(sovereign.pillar_fulfiller.last_fulfilled_at).toLocaleTimeString()}`
                    : 'idle'}
                </div>
              </div>
              <div data-testid="sov-boundary-lint">
                <div style={{ color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Boundary Lint</div>
                <div style={{ color: sovereign.boundary_lint?.passed ? GREEN : RED }}>
                  {sovereign.boundary_lint?.passed ? '✓ clean' : '✗ violation'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Endpoint matrix */}
        <div className="spulse-card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div className="spulse-hdr" style={{ fontSize: 16 }}>Endpoint Matrix · last {windowH}h</div>
            <div style={{ display: 'flex', gap: 6 }}>
              {[1, 6, 24, 72, 168].map(h => (
                <button key={h} className="spulse-btn" style={{
                  padding: '4px 10px', fontSize: 10,
                  background: windowH === h ? GOLD : 'transparent',
                  color: windowH === h ? OBSIDIAN : GOLD,
                }} onClick={() => setWindowH(h)} data-testid={`window-${h}h-btn`}>{h}h</button>
              ))}
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="spulse-table" data-testid="endpoints-table">
              <thead>
                <tr>
                  <th>Status</th><th>Endpoint</th><th>Category</th><th>Uptime</th>
                  <th>Avg Latency</th><th>Runs</th><th>Last Code</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', color: '#666', padding: 20 }}>No data yet — run pulse to populate.</td></tr>
                )}
                {endpoints.map(e => {
                  const dotColor = e.uptime_pct >= 99 ? GREEN : e.uptime_pct >= 80 ? AMBER : RED;
                  return (
                    <tr key={e.endpoint_id} data-testid={`ep-${e.endpoint_id}`}>
                      <td><span className="spulse-dot" style={{ background: dotColor }} /></td>
                      <td className="spulse-mono" style={{ fontSize: 12 }}>{e.label}</td>
                      <td><span className="spulse-pill" style={{ background: 'rgba(201,168,76,0.1)', color: GOLD }}>{e.category}</span></td>
                      <td className="spulse-mono" style={{ color: dotColor }}>{e.uptime_pct}%</td>
                      <td className="spulse-mono">{e.avg_latency_ms}ms</td>
                      <td className="spulse-mono">{e.passed}/{e.total}</td>
                      <td className="spulse-mono" style={{ color: e.last_passed ? GREEN : RED }}>{e.last_status}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent failures */}
        {latest?.failures?.length > 0 && (
          <div className="spulse-card" style={{ marginBottom: 20, borderColor: RED }}>
            <div className="spulse-hdr" style={{ fontSize: 16, color: RED, marginBottom: 10 }}>⚠ Failures in Latest Sweep</div>
            <table className="spulse-table">
              <tbody>
                {latest.failures.map((f, i) => (
                  <tr key={i} data-testid={`failure-${f.id}`}>
                    <td className="spulse-mono" style={{ fontSize: 12, color: RED }}>{f.status_code || 'ERR'}</td>
                    <td>{f.label}</td>
                    <td className="spulse-mono" style={{ fontSize: 11, color: '#888' }}>{f.path}</td>
                    <td style={{ fontSize: 12, color: '#aaa' }}>{f.error || 'Unexpected status'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Deep QA */}
        <div className="spulse-card" style={{ marginBottom: 20 }}>
          <div className="spulse-hdr" style={{ fontSize: 16, marginBottom: 10 }}>Deep QA Agent · last journey run</div>
          {!deep ? (
            <div style={{ color: '#888', padding: 12 }}>No deep run yet. Click <b style={{ color: GOLD }}>Run Deep QA</b> above.</div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 14 }}>
                <div><span style={{ color: '#888' }}>Journeys:</span> <span className="spulse-mono">{(deep.journey_ids || []).join(', ')}</span></div>
                <div><span style={{ color: '#888' }}>Steps:</span> <span className="spulse-mono" style={{ color: deep.pass_rate === 100 ? GREEN : AMBER }}>{deep.passed_steps}/{deep.total_steps} ({deep.pass_rate}%)</span></div>
                <div><span style={{ color: '#888' }}>Finished:</span> <span className="spulse-mono">{new Date(deep.finished_at).toLocaleString()}</span></div>
              </div>
              {deep.rca && (
                <div style={{ background: 'rgba(239,68,68,0.05)', border: `1px solid ${RED}40`, borderRadius: 8, padding: 12, marginBottom: 12 }} data-testid="deep-rca">
                  <div style={{ color: RED, fontSize: 11, fontWeight: 700, letterSpacing: '0.15em', marginBottom: 6 }}>AI ROOT-CAUSE ANALYSIS</div>
                  <div className="spulse-body" style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6 }}>{deep.rca}</div>
                </div>
              )}
              <table className="spulse-table">
                <thead><tr><th>Journey</th><th>Step</th><th>Method</th><th>Code</th><th>Latency</th></tr></thead>
                <tbody>
                  {(deep.journeys || []).flatMap(j => (j.steps || []).map((s, i) => (
                    <tr key={`${j.journey_id}-${i}`}>
                      <td className="spulse-mono" style={{ fontSize: 11, color: '#888' }}>{j.journey_id}</td>
                      <td>{s.name}</td>
                      <td className="spulse-mono" style={{ fontSize: 11 }}>{s.method} {s.path}</td>
                      <td className="spulse-mono" style={{ color: s.passed ? GREEN : RED }}>{s.status_code}</td>
                      <td className="spulse-mono">{s.latency_ms}ms</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* History */}
        <div className="spulse-card">
          <div className="spulse-hdr" style={{ fontSize: 16, marginBottom: 10 }}>Recent Sweeps · last {history.length}</div>
          <table className="spulse-table" data-testid="history-table">
            <thead><tr><th>Finished</th><th>Pass</th><th>Fail</th><th>Pass Rate</th><th>Avg Latency</th></tr></thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td className="spulse-mono" style={{ fontSize: 12 }}>{new Date(h.finished_at).toLocaleString()}</td>
                  <td className="spulse-mono" style={{ color: GREEN }}>{h.passed}</td>
                  <td className="spulse-mono" style={{ color: h.failed > 0 ? RED : '#555' }}>{h.failed}</td>
                  <td className="spulse-mono" style={{ color: h.pass_rate === 100 ? GREEN : AMBER }}>{h.pass_rate}%</td>
                  <td className="spulse-mono">{h.avg_latency_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
