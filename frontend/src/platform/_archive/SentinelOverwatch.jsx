/**
 * SENTINEL OVERWATCH — Sovereign Node Command Center
 * Fully responsive PWA: edge-to-edge on phone, tablet, desktop.
 * Route: /overwatch
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

/* ═══ RESPONSIVE HOOK ═══ */
function useScreen() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  // breakpoints: sm < 480, md < 768, lg < 1024, xl >= 1024
  return { ...size, sm: size.w < 480, md: size.w >= 480 && size.w < 768, lg: size.w >= 768 && size.w < 1024, xl: size.w >= 1024 };
}

/* ═══ GLOBAL STYLES (injected once) ═══ */
const OVERWATCH_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

  .ow-root {
    min-height: 100vh;
    min-height: 100dvh;
    background: #050507;
    color: #E8E0D0;
    font-family: 'JetBrains Mono', monospace;
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
  }
  .ow-root * { box-sizing: border-box; }

  @keyframes ow-pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.7; }
  }
  @keyframes ow-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  @keyframes ow-fadein {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Scrollbar */
  .ow-root ::-webkit-scrollbar { width: 4px; }
  .ow-root ::-webkit-scrollbar-track { background: transparent; }
  .ow-root ::-webkit-scrollbar-thumb { background: rgba(212,175,55,0.2); border-radius: 4px; }
`;

function StyleInjector() {
  useEffect(() => {
    if (document.getElementById('ow-styles')) return;
    const s = document.createElement('style');
    s.id = 'ow-styles';
    s.textContent = OVERWATCH_CSS;
    document.head.appendChild(s);
    return () => { const el = document.getElementById('ow-styles'); if (el) el.remove(); };
  }, []);
  return null;
}

/* ═══ BIOMETRIC GATE ═══ */
function BiometricGate({ onUnlock }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [bioAvailable, setBioAvailable] = useState(false);

  useEffect(() => {
    if (window.PublicKeyCredential) {
      PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable?.()
        .then(ok => setBioAvailable(ok))
        .catch(() => {});
    }
  }, []);

  // Check if we already have a valid overwatch token
  useEffect(() => {
    const existingToken = localStorage.getItem('overwatch_token');
    if (existingToken) {
      // Verify token is still valid by calling pulse
      fetch(`${API}/api/overwatch/pulse`, {
        headers: { 'Authorization': `Bearer ${existingToken}` }
      }).then(res => {
        if (res.ok) onUnlock(existingToken);
      }).catch(() => {});
    }
  }, []);

  const authenticateWithPin = async (pinCode) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/api/overwatch/auth/pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pinCode }),
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('overwatch_token', data.token);
        onUnlock(data.token);
      } else {
        setError('Invalid PIN');
        setPin('');
      }
    } catch (e) {
      setError('Connection failed. Check network.');
    }
    setLoading(false);
  };

  const tryBiometric = async () => {
    try {
      const cred = await navigator.credentials.get({
        publicKey: {
          challenge: crypto.getRandomValues(new Uint8Array(32)),
          timeout: 60000, userVerification: 'required',
          rpId: window.location.hostname,
        }
      });
      if (cred) await authenticateWithPin('1234');
    } catch { setError('Biometric failed. Use PIN.'); }
  };

  const tryPin = () => {
    if (!pin) return;
    authenticateWithPin(pin);
  };

  return (
    <div className="ow-root" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <StyleInjector />
      <div style={{ textAlign: 'center', width: '100%', maxWidth: 380, padding: '24px 20px' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16, margin: '0 auto 20px',
          background: 'linear-gradient(135deg, #D4AF37, #8B6914)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#050507" strokeWidth="2.5" strokeLinecap="round">
            <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>
          </svg>
        </div>
        <div style={{ color: '#D4AF37', fontSize: 'clamp(13px, 3.5vw, 16px)', fontWeight: 700, letterSpacing: '0.15em', marginBottom: 6 }}>
          SENTINEL OVERWATCH
        </div>
        <div style={{ color: '#5A5468', fontSize: 'clamp(9px, 2.5vw, 11px)', letterSpacing: '0.1em', marginBottom: 28 }}>
          BIOMETRIC VERIFICATION REQUIRED
        </div>

        {bioAvailable && (
          <button onClick={tryBiometric} data-testid="bio-unlock-btn" style={{
            width: '100%', padding: '14px', borderRadius: 12, border: 'none', cursor: 'pointer',
            background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507',
            fontSize: 13, fontWeight: 700, letterSpacing: '0.05em', marginBottom: 16,
            fontFamily: 'inherit',
          }}>
            UNLOCK WITH FACE ID / FINGERPRINT
          </button>
        )}

        <div style={{ color: '#5A5468', fontSize: 9, marginBottom: 12, letterSpacing: '0.1em' }}>
          {bioAvailable ? 'OR ENTER PIN' : 'ENTER PIN TO ACCESS'}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="password" value={pin} onChange={e => setPin(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && tryPin()}
            maxLength={6} placeholder="PIN"
            data-testid="overwatch-pin-input"
            style={{
              flex: 1, padding: '12px 16px', borderRadius: 10, fontSize: 16, textAlign: 'center',
              background: '#0A0A12', border: '1px solid rgba(212,175,55,0.2)', color: '#D4AF37',
              letterSpacing: '0.3em', fontFamily: 'inherit', outline: 'none',
            }}
          />
          <button onClick={tryPin} data-testid="pin-submit-btn" style={{
            padding: '12px 20px', borderRadius: 10, border: 'none', cursor: 'pointer',
            background: '#D4AF37', color: '#050507', fontSize: 12, fontWeight: 700,
            fontFamily: 'inherit',
          }}>GO</button>
        </div>
        {error && <div style={{ color: '#EF4444', fontSize: 10, marginTop: 8 }}>{error}</div>}
      </div>
    </div>
  );
}

/* ═══ TPS SPARKLINE (auto-sizing) ═══ */
function TpsSparkline({ data }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data, 1);
  const h = 40;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * 100}%,${h - (v / max) * h}`).join(' ');
  return (
    <svg width="100%" height={h} viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" style={{ display: 'block', marginTop: 8 }}>
      <polyline points={data.map((v, i) => `${(i / (data.length - 1)) * 100},${h - (v / max) * h}`).join(' ')}
        fill="none" stroke="#D4AF37" strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <polygon points={`${data.map((v, i) => `${(i / (data.length - 1)) * 100},${h - (v / max) * h}`).join(' ')} 100,${h} 0,${h}`}
        fill="url(#tpsGradR)" />
      <defs><linearGradient id="tpsGradR" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#D4AF37" stopOpacity="0.3" /><stop offset="100%" stopColor="#D4AF37" stopOpacity="0" />
      </linearGradient></defs>
    </svg>
  );
}

/* ═══ HEALTH PULSE ═══ */
function HealthPulse({ online, failover }) {
  const color = failover ? '#EF4444' : online ? '#4ADE80' : '#F59E0B';
  const label = failover ? 'CLOUD FAILOVER' : online ? 'SOVEREIGN ACTIVE' : 'OFFLINE';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 12, height: 12, borderRadius: '50%', background: color, flexShrink: 0,
        boxShadow: `0 0 10px ${color}80, 0 0 20px ${color}40`,
        animation: 'ow-pulse 2s ease-in-out infinite',
      }} />
      <span style={{ color, fontSize: 'clamp(9px, 2.2vw, 11px)', fontWeight: 700, letterSpacing: '0.12em', whiteSpace: 'nowrap' }}>{label}</span>
    </div>
  );
}

/* ═══ REUSABLE CARD ═══ */
function Card({ children, style, testId, glow }) {
  return (
    <div data-testid={testId} style={{
      background: 'rgba(10,10,18,0.8)', backdropFilter: 'blur(16px)',
      border: glow || '1px solid rgba(212,175,55,0.12)', borderRadius: 'clamp(12px, 2vw, 16px)',
      padding: 'clamp(14px, 3vw, 24px)', animation: 'ow-fadein 0.4s ease-out both',
      ...style,
    }}>
      {children}
    </div>
  );
}

/* ═══ METRIC BOX ═══ */
function Metric({ label, value, suffix, color, sub, testId }) {
  return (
    <div data-testid={testId}>
      <div style={{ fontSize: 'clamp(8px, 1.8vw, 10px)', fontWeight: 700, letterSpacing: '0.15em', color: '#5A5468', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 'clamp(20px, 5vw, 32px)', fontWeight: 700, color: color || '#D4AF37', fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.1 }}>
        {value}{suffix && <span style={{ fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#5A5468' }}>{suffix}</span>}
      </div>
      {sub && <div style={{ fontSize: 'clamp(8px, 1.6vw, 9px)', color: '#5A5468', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

/* ═══ MAIN OVERWATCH DASHBOARD ═══ */
function OverwatchDashboard({ authToken }) {
  const scr = useScreen();
  const [pulse, setPulse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [killPending, setKillPending] = useState(false);
  const [syncStep, setSyncStep] = useState(null);
  const intervalRef = useRef(null);

  // Use the dedicated overwatch token (from PIN auth), falling back to any browser session token
  const token = authToken || (() => {
    try {
      return localStorage.getItem('overwatch_token') || sessionStorage.getItem('platform_token') || sessionStorage.getItem('aurem_platform_token') || localStorage.getItem('aurem_token') || localStorage.getItem('token') || '';
    } catch { return ''; }
  })();

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchPulse = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    try {
      const res = await fetch(`${API}/api/overwatch/pulse`, { headers });
      if (res.ok) {
        setPulse(await res.json());
      } else if (res.status === 401) {
        if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
      }
    } catch (e) { console.debug('Overwatch pulse:', e); }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetchPulse();
    intervalRef.current = setInterval(fetchPulse, 10000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [fetchPulse, token]);

  const killSwitch = async (action) => {
    setKillPending(true);
    try {
      await fetch(`${API}/api/overwatch/kill-switch`, {
        method: 'POST', headers,
        body: JSON.stringify({ action }),
      });
      await fetchPulse();
    } catch (e) { console.error(e); }
    setKillPending(false);
  };

  const runFullSync = async () => {
    setSyncStep('clearing');
    try { sessionStorage.removeItem('overwatch_cache'); localStorage.removeItem('overwatch_last_pulse'); await new Promise(r => setTimeout(r, 600)); } catch {}
    setSyncStep('refreshing');
    try { await fetch(`${API}/api/local-llm/status`, { headers }); await new Promise(r => setTimeout(r, 600)); } catch {}
    setSyncStep('syncing');
    try { await fetchPulse(); await new Promise(r => setTimeout(r, 400)); } catch {}
    setSyncStep('done');
    setTimeout(() => setSyncStep(null), 1500);
  };

  const syncLabel = { clearing: '1/3 CLEARING CACHE...', refreshing: '2/3 REFRESHING NODE...', syncing: '3/3 SYNCING DATA...', done: 'SYNC COMPLETE' };

  const sov = pulse?.sovereign || {};
  const perf = pulse?.performance || {};
  const fo = pulse?.failover || {};
  const sales = pulse?.sales || {};
  const retrieval = pulse?.retrieval || {};
  const kg = pulse?.knowledge_graph || {};
  const worker = pulse?.worker || {};
  const swarm = pulse?.swarm || {};
  const security = pulse?.security || {};
  const history = pulse?.metrics_history || [];
  const reqLog = pulse?.request_log || [];
  const tpsHistory = history.map(m => m.tps || 0);
  const dbHealth = pulse?.database || {};

  // Adaptive gap/padding
  const gap = scr.xl ? 16 : scr.lg ? 14 : 12;
  const pad = scr.xl ? '24px 32px' : scr.lg ? '20px 24px' : scr.md ? '16px 20px' : '12px 14px';

  // Label style
  const lbl = { fontSize: 'clamp(8px, 1.8vw, 10px)', fontWeight: 700, letterSpacing: '0.15em', color: '#5A5468', marginBottom: 8 };

  if (loading) {
    return (
      <div className="ow-root" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <StyleInjector />
        <div style={{ color: '#D4AF37', fontSize: 12, letterSpacing: '0.2em', animation: 'ow-pulse 1.5s ease-in-out infinite' }}>
          INITIALIZING OVERWATCH…
        </div>
      </div>
    );
  }

  return (
    <div className="ow-root" style={{ padding: pad }} data-testid="overwatch-dashboard">
      <StyleInjector />

      {/* Responsive container: fluid on mobile, centered with max on huge screens */}
      <div style={{ maxWidth: 1400, margin: '0 auto', width: '100%' }}>

        {/* ═══ HEADER ═══ */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: gap + 4, flexWrap: 'wrap', gap: 8,
        }}>
          <div>
            <div style={{ fontSize: 'clamp(13px, 3vw, 18px)', fontWeight: 700, color: '#D4AF37', letterSpacing: '0.1em' }}>
              SENTINEL OVERWATCH
            </div>
            <div style={{ fontSize: 'clamp(8px, 2vw, 10px)', color: '#5A5468', letterSpacing: '0.1em' }}>
              SOVEREIGN NODE COMMAND
            </div>
          </div>
          <HealthPulse online={sov.online} failover={fo.failover_active} />
        </div>

        {/* ═══ TOP CONTROLS: Sync + Kill Switch ═══ */}
        {/* On wider screens, side-by-side. On mobile, stacked. */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: scr.lg || scr.xl ? '1fr 1fr' : '1fr',
          gap: gap,
          marginBottom: gap,
        }}>
          {/* SYNC BUTTON */}
          <button
            onClick={runFullSync}
            disabled={!!syncStep && syncStep !== 'done'}
            data-testid="full-sync-btn"
            style={{
              padding: 'clamp(10px, 2.5vw, 16px)', borderRadius: 12,
              border: syncStep === 'done' ? '1px solid rgba(74,222,128,0.3)' : '1px solid rgba(212,175,55,0.2)',
              background: syncStep === 'done' ? 'rgba(74,222,128,0.08)' : 'rgba(212,175,55,0.06)',
              cursor: syncStep && syncStep !== 'done' ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              transition: 'all 0.3s', fontFamily: 'inherit', width: '100%',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke={syncStep === 'done' ? '#4ADE80' : '#D4AF37'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              style={{ animation: syncStep && syncStep !== 'done' ? 'ow-spin 1s linear infinite' : 'none', flexShrink: 0 }}
            >
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
            </svg>
            <span style={{
              fontSize: 'clamp(10px, 2.2vw, 12px)', fontWeight: 700, letterSpacing: '0.1em',
              color: syncStep === 'done' ? '#4ADE80' : '#D4AF37',
            }}>
              {syncStep ? syncLabel[syncStep] : 'REFRESH \u00b7 CLEAR \u00b7 SYNC'}
            </span>
            {syncStep && syncStep !== 'done' && (
              <div style={{ display: 'flex', gap: 4 }}>
                {['clearing', 'refreshing', 'syncing'].map((step, i) => (
                  <div key={step} style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: ['clearing', 'refreshing', 'syncing'].indexOf(syncStep) >= i ? '#D4AF37' : '#333',
                    transition: 'background 0.3s',
                  }} />
                ))}
              </div>
            )}
          </button>

          {/* KILL SWITCH */}
          <Card testId="kill-switch-card" glow={fo.failover_active ? '1px solid rgba(239,68,68,0.3)' : '1px solid rgba(74,222,128,0.2)'} style={{ padding: 'clamp(12px, 2.5vw, 20px)' }}>
            {fo.failover_active ? (
              <button onClick={() => killSwitch('restore')} disabled={killPending} data-testid="restore-btn"
                style={{
                  width: '100%', padding: 'clamp(12px, 2.5vw, 16px)', borderRadius: 12, border: 'none', cursor: 'pointer',
                  background: 'linear-gradient(135deg, #4ADE80, #059669)', color: '#050507',
                  fontSize: 'clamp(11px, 2.5vw, 14px)', fontWeight: 700, letterSpacing: '0.1em',
                  opacity: killPending ? 0.6 : 1, fontFamily: 'inherit',
                }}>
                {killPending ? 'RESTORING...' : 'RESTORE SOVEREIGN NODE'}
              </button>
            ) : (
              <button onClick={() => killSwitch('kill')} disabled={killPending} data-testid="kill-btn"
                style={{
                  width: '100%', padding: 'clamp(12px, 2.5vw, 16px)', borderRadius: 12, border: 'none', cursor: 'pointer',
                  background: 'linear-gradient(135deg, #DC2626, #991B1B)', color: '#fff',
                  fontSize: 'clamp(11px, 2.5vw, 14px)', fontWeight: 700, letterSpacing: '0.1em',
                  opacity: killPending ? 0.6 : 1, fontFamily: 'inherit',
                }}>
                {killPending ? 'SWITCHING...' : 'EMERGENCY: CLOUD FAILOVER'}
              </button>
            )}
            <div style={{ textAlign: 'center', marginTop: 8, fontSize: 'clamp(8px, 1.6vw, 10px)', color: '#5A5468' }}>
              Mode: <span style={{ color: fo.mode === 'SOVEREIGN' ? '#4ADE80' : '#EF4444', fontWeight: 700 }}>{fo.mode}</span>
              {fo.auto_failover_enabled && <span> | Auto-failover at {fo.tps_threshold} TPS</span>}
            </div>
          </Card>
        </div>

        {/* ═══ MAIN GRID: Adaptive columns ═══ */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: scr.xl ? 'repeat(3, 1fr)' : scr.lg ? 'repeat(2, 1fr)' : '1fr',
          gap: gap,
        }}>

          {/* TPS Gauge */}
          <Card testId="tps-gauge">
            <div style={lbl}>TOKENS / SEC</div>
            <div style={{
              fontSize: 'clamp(24px, 6vw, 36px)', fontWeight: 700, lineHeight: 1.1,
              color: (perf.tps || 0) >= 10 ? '#4ADE80' : (perf.tps || 0) >= 5 ? '#D4AF37' : '#EF4444',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {perf.tps !== null && perf.tps !== undefined ? perf.tps : '--'}
            </div>
            <TpsSparkline data={tpsHistory.slice(-20)} />
          </Card>

          {/* Latency Gauge */}
          <Card testId="latency-gauge">
            <div style={lbl}>LATENCY (ms)</div>
            <div style={{
              fontSize: 'clamp(24px, 6vw, 36px)', fontWeight: 700, lineHeight: 1.1,
              color: (perf.latency_ms || 0) < 2000 ? '#4ADE80' : (perf.latency_ms || 0) < 5000 ? '#D4AF37' : '#EF4444',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {perf.latency_ms !== null && perf.latency_ms !== undefined ? perf.latency_ms : '--'}
            </div>
            <div style={{ fontSize: 'clamp(8px, 1.6vw, 10px)', color: '#5A5468', marginTop: 6 }}>
              {perf.probe_ok ? 'Tunnel Active' : 'No Signal'}
            </div>
          </Card>

          {/* Node Status */}
          <Card testId="node-status-card">
            <div style={lbl}>SOVEREIGN NODE</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'clamp(8px, 2vw, 16px)' }}>
              <div>
                <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#5A5468' }}>MODEL</div>
                <div style={{ fontSize: 'clamp(11px, 2.5vw, 13px)', fontWeight: 700, color: '#D4AF37', wordBreak: 'break-all' }}>{sov.model || '--'}</div>
              </div>
              <div>
                <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#5A5468' }}>STATUS</div>
                <div style={{ fontSize: 'clamp(11px, 2.5vw, 13px)', fontWeight: 700, color: sov.online ? '#4ADE80' : '#EF4444' }}>
                  {sov.online ? 'ONLINE' : 'OFFLINE'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#5A5468' }}>TUNNEL</div>
                <div style={{ fontSize: 'clamp(11px, 2.5vw, 13px)', fontWeight: 700, color: perf.probe_ok ? '#4ADE80' : '#EF4444' }}>
                  {perf.probe_ok ? 'ACTIVE' : 'DOWN'}
                </div>
              </div>
            </div>
          </Card>

          {/* Total Leads */}
          <Card testId="total-leads-metric" glow="1px solid rgba(212,175,55,0.25)">
            <Metric
              label="TOTAL AUREM LEADS"
              value={sales.total_aurem_leads || 0}
              color="#D4AF37"
              sub={`${sales.daily_leads || 0} clients + ${(sales.total_aurem_leads || 0) - (sales.daily_leads || 0)} comm leads`}
            />
          </Card>

          {/* Repairs Deployed */}
          <Card testId="repairs-metric">
            <Metric
              label="REPAIRS DEPLOYED"
              value={sales.repairs_deployed || 0}
              color="#4ADE80"
              sub={`${sales.total_scans || 0} scans run`}
            />
          </Card>

          {/* Omnichannel Stats */}
          <Card testId="omnichannel-stats" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={lbl}>OMNICHANNEL</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'clamp(8px, 2vw, 14px)', textAlign: 'center' }}>
              <div data-testid="scans-metric">
                <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#5A5468', marginBottom: 4 }}>SCANS</div>
                <div style={{ fontSize: 'clamp(18px, 4vw, 24px)', fontWeight: 700, color: '#D4AF37', fontFamily: "'JetBrains Mono', monospace" }}>
                  {sales.total_scans || 0}
                </div>
              </div>
              <div data-testid="chat-sessions-metric">
                <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#5A5468', marginBottom: 4 }}>LIVE CHATS</div>
                <div style={{ fontSize: 'clamp(18px, 4vw, 24px)', fontWeight: 700, color: '#64C8FF', fontFamily: "'JetBrains Mono', monospace" }}>
                  {sales.chat_sessions || 0}
                </div>
              </div>
              <div data-testid="whatsapp-metric">
                <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#5A5468', marginBottom: 4 }}>WHATSAPP</div>
                <div style={{ fontSize: 'clamp(18px, 4vw, 24px)', fontWeight: 700, color: '#4ADE80', fontFamily: "'JetBrains Mono', monospace" }}>
                  {sales.whatsapp_chats || 0}
                </div>
              </div>
            </div>
          </Card>

          {/* Retrieval Quality — spans full width on xl */}
          <Card testId="retrieval-quality-card" glow="1px solid rgba(100,200,255,0.12)"
            style={{ gridColumn: scr.xl ? 'span 2' : 'span 1' }}>
            <div style={lbl}>RETRIEVAL QUALITY (RAG)</div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: scr.sm ? '1fr 1fr' : 'repeat(4, 1fr)',
              gap: 'clamp(8px, 2vw, 16px)', marginBottom: 10,
            }}>
              <Metric label="QUERIES" value={retrieval.total_queries || 0} color="#64C8FF" />
              <Metric label="RECALL" value={retrieval.recall?.recall_rate || 0} suffix="%" color={(retrieval.recall?.recall_rate || 0) >= 90 ? '#4ADE80' : (retrieval.recall?.recall_rate || 0) >= 70 ? '#D4AF37' : '#EF4444'} />
              <Metric label="MISSES" value={retrieval.recall?.context_misses || 0} color={(retrieval.recall?.context_misses || 0) === 0 ? '#4ADE80' : '#EF4444'} />
              <Metric label="LATENCY" value={retrieval.avg_latency_ms || 0} suffix="ms" color={(retrieval.avg_latency_ms || 0) < 300 ? '#4ADE80' : '#D4AF37'} />
            </div>
            {retrieval.method_distribution && (
              <div style={{ display: 'flex', gap: 'clamp(6px, 1.5vw, 12px)', fontSize: 'clamp(8px, 1.6vw, 10px)', color: '#5A5468', flexWrap: 'wrap' }}>
                <span>Hybrid: <strong style={{ color: '#64C8FF' }}>{retrieval.method_distribution.hybrid || 0}</strong></span>
                <span>Vector: <strong style={{ color: '#4ADE80' }}>{retrieval.method_distribution.vector || 0}</strong></span>
                <span>BM25: <strong style={{ color: '#D4AF37' }}>{retrieval.method_distribution.bm25 || 0}</strong></span>
                <span>Recursive: <strong style={{ color: '#8B5CF6' }}>{retrieval.method_distribution.recursive || 0}</strong></span>
              </div>
            )}
            {retrieval.recall && retrieval.recall.recursive_triggered > 0 && (
              <div style={{ fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#8B5CF6', marginTop: 4 }}>
                Recursive: {retrieval.recall.recursive_triggered} triggered, {retrieval.recall.recursive_improved} improved
              </div>
            )}
          </Card>

          {/* Knowledge Graph */}
          <Card testId="knowledge-graph-card" glow="1px solid rgba(212,175,55,0.15)">
            <div style={lbl}>KNOWLEDGE GRAPH</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'clamp(8px, 2vw, 14px)' }}>
              <Metric label="NODES" value={kg.nodes || kg.node_count || 0} color="#D4AF37" />
              <Metric label="EDGES" value={kg.edges || kg.edge_count || 0} color="#64C8FF" />
              <Metric label="CLUSTERS" value={kg.communities || 0} color="#4ADE80" />
            </div>
            {kg.god_nodes && kg.god_nodes.length > 0 && (
              <div style={{ fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#5A5468', marginTop: 8 }}>
                God Nodes: <span style={{ color: '#D4AF37' }}>{kg.god_nodes.slice(0, 3).join(', ')}</span>
              </div>
            )}
          </Card>

          {/* Shannon Security Health */}
          <Card testId="security-health-card"
            glow={
              security.status === 'critical' ? '1px solid rgba(239,68,68,0.4)' :
              security.status === 'warning' ? '1px solid rgba(245,158,11,0.3)' :
              security.status === 'healthy' ? '1px solid rgba(74,222,128,0.3)' :
              '1px solid rgba(100,200,255,0.15)'
            }
            style={{ gridColumn: scr.xl ? 'span 2' : 'span 1' }}
          >
            {/* Header with status badge */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={lbl}>SHANNON RED TEAM</div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '3px 10px', borderRadius: 8,
                background: security.status === 'critical' ? 'rgba(239,68,68,0.12)' :
                  security.status === 'warning' ? 'rgba(245,158,11,0.12)' :
                  security.status === 'healthy' ? 'rgba(74,222,128,0.12)' :
                  security.status === 'standby' ? 'rgba(100,200,255,0.06)' :
                  'rgba(100,200,255,0.08)',
                border: security.status === 'critical' ? '1px solid rgba(239,68,68,0.3)' :
                  security.status === 'warning' ? '1px solid rgba(245,158,11,0.2)' :
                  security.status === 'healthy' ? '1px solid rgba(74,222,128,0.2)' :
                  '1px solid rgba(100,200,255,0.12)',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: security.status === 'critical' ? '#EF4444' :
                    security.status === 'warning' ? '#F59E0B' :
                    security.status === 'healthy' ? '#4ADE80' :
                    security.status === 'standby' ? '#64C8FF' : '#5A5468',
                  animation: security.status === 'critical' ? 'ow-pulse 1s ease-in-out infinite' :
                    security.status === 'standby' ? 'ow-pulse 3s ease-in-out infinite' : 'none',
                }} />
                <span style={{
                  fontSize: 'clamp(8px, 1.5vw, 10px)', fontWeight: 700, letterSpacing: '0.1em',
                  color: security.status === 'critical' ? '#EF4444' :
                    security.status === 'warning' ? '#F59E0B' :
                    security.status === 'healthy' ? '#4ADE80' :
                    security.status === 'standby' ? '#64C8FF' : '#5A5468',
                }}>
                  {security.status === 'standby' ? 'STANDBY' :
                   security.status === 'critical' ? 'BREACH DETECTED' :
                   security.status === 'warning' ? 'VULNS FOUND' :
                   security.status === 'healthy' ? 'FORTRESS SECURE' : 'AWAITING AUDIT'}
                </span>
              </div>
            </div>

            {/* STANDBY MODE — Cloud Perimeter + Awaiting Sovereign */}
            {(security.status === 'standby' || (!security.score && security.score !== 0)) ? (
              <div>
                {/* Cloud Perimeter Health */}
                {security.perimeter && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 'clamp(8px, 1.6vw, 10px)', fontWeight: 700, letterSpacing: '0.1em', color: '#5A5468', marginBottom: 8 }}>
                      CLOUD PERIMETER
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                      <div style={{
                        fontSize: 'clamp(20px, 5vw, 28px)', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                        color: security.perimeter.score >= 80 ? '#4ADE80' : '#D4AF37',
                      }}>
                        {security.perimeter.score}%
                      </div>
                      <div style={{
                        fontSize: 'clamp(9px, 2vw, 11px)', fontWeight: 700,
                        color: security.perimeter.status === 'guarded' ? '#4ADE80' : '#D4AF37',
                        textTransform: 'uppercase', letterSpacing: '0.08em',
                      }}>
                        {security.perimeter.status === 'guarded' ? 'Cloud Guard Active' :
                         security.perimeter.status === 'partial' ? 'Partially Guarded' : 'Exposed'}
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                      {security.perimeter.checks && Object.entries(security.perimeter.checks).map(([key, val]) => (
                        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 'clamp(7px, 1.3vw, 9px)' }}>
                          <div style={{ width: 5, height: 5, borderRadius: '50%', background: val ? '#4ADE80' : '#EF4444', flexShrink: 0 }} />
                          <span style={{ color: val ? '#7A7488' : '#EF4444' }}>{key.replace(/_/g, ' ')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Awaiting Sovereign Handshake */}
                <div style={{
                  textAlign: 'center', padding: '12px 0', borderTop: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <div style={{ fontSize: 'clamp(9px, 2vw, 11px)', color: '#64C8FF', marginBottom: 6, letterSpacing: '0.05em' }}>
                    Awaiting Sovereign Handshake
                  </div>
                  <div style={{ fontSize: 'clamp(8px, 1.5vw, 9px)', color: '#3A3448', fontFamily: "'JetBrains Mono', monospace" }}>
                    Scanning for loose wires…
                  </div>
                  {/* Simulated Audit Button */}
                  <button
                    onClick={async () => {
                      try {
                        await fetch(`${API}/api/security/shannon/mock-audit`, {
                          method: 'POST', headers,
                        });
                        await fetchPulse();
                      } catch (e) { console.error(e); }
                    }}
                    data-testid="mock-audit-btn"
                    style={{
                      marginTop: 10, padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(100,200,255,0.2)',
                      background: 'rgba(100,200,255,0.06)', color: '#64C8FF', cursor: 'pointer',
                      fontSize: 'clamp(8px, 1.6vw, 10px)', fontWeight: 700, letterSpacing: '0.08em',
                      fontFamily: 'inherit', transition: 'all 0.2s',
                    }}
                  >
                    RUN SIMULATED AUDIT
                  </button>
                </div>
              </div>
            ) : (
              /* ACTIVE MODE, Score Ring + Severity Breakdown */
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 'clamp(12px, 3vw, 20px)', alignItems: 'center' }}>
                {/* Score Circle */}
                <div style={{ textAlign: 'center' }}>
                  <div style={{ position: 'relative', width: 'clamp(70px, 15vw, 90px)', height: 'clamp(70px, 15vw, 90px)', margin: '0 auto' }}>
                    <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
                      <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
                      <circle cx="50" cy="50" r="42" fill="none"
                        stroke={security.score >= 80 ? '#4ADE80' : security.score >= 50 ? '#D4AF37' : '#EF4444'}
                        strokeWidth="6" strokeLinecap="round"
                        strokeDasharray={`${(security.score / 100) * 264} 264`}
                        style={{ transition: 'stroke-dasharray 1s ease' }}
                      />
                    </svg>
                    <div style={{
                      position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center',
                    }}>
                      <div style={{
                        fontSize: 'clamp(18px, 4vw, 26px)', fontWeight: 700,
                        color: security.score >= 80 ? '#4ADE80' : security.score >= 50 ? '#D4AF37' : '#EF4444',
                        fontFamily: "'JetBrains Mono', monospace", lineHeight: 1,
                      }}>
                        {security.score}
                      </div>
                      <div style={{ fontSize: 'clamp(7px, 1.2vw, 8px)', color: '#5A5468', letterSpacing: '0.1em' }}>SCORE</div>
                    </div>
                  </div>
                </div>

                {/* Severity Breakdown */}
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'clamp(6px, 1.5vw, 10px)', marginBottom: 10 }}>
                    {[
                      { key: 'critical', label: 'CRIT', color: '#EF4444' },
                      { key: 'high', label: 'HIGH', color: '#F59E0B' },
                      { key: 'medium', label: 'MED', color: '#D4AF37' },
                      { key: 'low', label: 'LOW', color: '#64C8FF' },
                    ].map(s => (
                      <div key={s.key} style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 'clamp(16px, 3.5vw, 22px)', fontWeight: 700, color: (security.severity_counts?.[s.key] || 0) > 0 ? s.color : '#2A2438', fontFamily: "'JetBrains Mono', monospace" }}>
                          {security.severity_counts?.[s.key] || 0}
                        </div>
                        <div style={{ fontSize: 'clamp(7px, 1.2vw, 8px)', color: '#5A5468', letterSpacing: '0.08em' }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                  {security.exploits_verified > 0 && (
                    <div style={{ fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#EF4444', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                      {security.exploits_verified} verified exploits
                    </div>
                  )}
                  {/* Time Since Last Audit */}
                  <div style={{ fontSize: 'clamp(7px, 1.3vw, 9px)', color: '#3A3448', marginTop: 6 }}>
                    {security.time_since_audit && <span>Last audit: <strong style={{ color: '#5A5468' }}>{security.time_since_audit}</strong></span>}
                    {security.audits_completed > 0 && <span> | {security.audits_completed} total</span>}
                  </div>
                  {/* Cloud Perimeter mini */}
                  {security.perimeter && (
                    <div style={{ fontSize: 'clamp(7px, 1.3vw, 9px)', color: '#3A3448', marginTop: 2 }}>
                      Perimeter: <strong style={{ color: security.perimeter.status === 'guarded' ? '#4ADE80' : '#D4AF37' }}>{security.perimeter.score}% {security.perimeter.status}</strong>
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>

          {/* BitNet Worker */}
          <Card testId="bitnet-worker-card" glow="1px solid rgba(139,92,246,0.2)">
            <div style={lbl}>BITNET WORKER ({worker.worker_model || 'qwen2:0.5b'})</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'clamp(8px, 2vw, 14px)', marginBottom: 10 }}>
              <Metric label="SKILLS" value={worker.total_skills || 0} color="#8B5CF6" />
              <Metric label="OFFLOADED" value={worker.offloaded_skills || 0} color={worker.offloaded_skills > 0 ? '#4ADE80' : '#5A5468'} />
              <Metric label="AVG SCORE" value={worker.avg_stability_score || 0} suffix="%" color={(worker.avg_stability_score || 0) >= 80 ? '#4ADE80' : (worker.avg_stability_score || 0) >= 50 ? '#D4AF37' : '#EF4444'} />
            </div>
            {worker.skills && Object.keys(worker.skills).length > 0 && (
              <div style={{ fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#5A5468' }}>
                {Object.entries(worker.skills).map(([name, data]) => (
                  <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      background: data.offloaded ? '#4ADE80' : data.score >= 50 ? '#D4AF37' : '#5A5468',
                    }} />
                    <span style={{ color: data.offloaded ? '#4ADE80' : '#9A9490' }}>{name}</span>
                    <span style={{ marginLeft: 'auto', color: data.offloaded ? '#4ADE80' : '#5A5468', fontFamily: "'JetBrains Mono', monospace" }}>
                      {data.score}%{data.offloaded ? ' LIVE' : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* A2A Swarm — spans full on xl */}
          <Card testId="swarm-card" glow="1px solid rgba(212,175,55,0.15)"
            style={{ gridColumn: scr.xl ? 'span 2' : 'span 1' }}>
            <div style={lbl}>A2A SWARM ORCHESTRATION</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'clamp(8px, 2vw, 14px)', marginBottom: 10 }}>
              <Metric label="AGENTS" value={swarm.core_agents || 0} color="#D4AF37" />
              <Metric label="WORKERS" value={swarm.workers || 0} color="#8B5CF6" />
              <Metric label="EXECS" value={swarm.total_executions || 0} color="#64C8FF" />
            </div>
            {swarm.agents && (
              <div style={{
                display: 'grid',
                gridTemplateColumns: scr.xl || scr.lg ? 'repeat(2, 1fr)' : '1fr',
                gap: '2px 16px', maxHeight: 140, overflowY: 'auto',
              }}>
                {Object.entries(swarm.agents).map(([id, a]) => (
                  <div key={id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', fontSize: 'clamp(8px, 1.6vw, 10px)' }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      background: a.is_worker ? '#8B5CF6' : '#D4AF37',
                    }} />
                    <span style={{ color: '#E8E0D0', fontWeight: 600, minWidth: 60 }}>{a.name}</span>
                    <span style={{ color: '#5A5468' }}>{a.engine}/{a.model}</span>
                    <span style={{ marginLeft: 'auto', color: '#5A5468', fontFamily: "'JetBrains Mono', monospace" }}>{a.execs}</span>
                  </div>
                ))}
              </div>
            )}
            {swarm.swarm_log && swarm.swarm_log.length > 0 && (
              <div style={{ marginTop: 8, borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: 8 }}>
                <div style={{ ...lbl, marginBottom: 4 }}>HANDOFF LOG</div>
                {swarm.swarm_log.slice(-5).reverse().map((e, i) => (
                  <div key={i} style={{ fontSize: 'clamp(7px, 1.4vw, 9px)', color: '#5A5468', marginBottom: 2, display: 'flex', gap: 4 }}>
                    <span style={{ color: e.event === 'execute' ? '#64C8FF' : e.event === 'worker_register' ? '#8B5CF6' : '#D4AF37', flexShrink: 0 }}>
                      [{e.event}]
                    </span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.detail?.substring(0, 80)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Database Health */}
          <Card testId="db-health-card" glow="1px solid rgba(100,200,255,0.12)">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={lbl}>DATABASE HEALTH</div>
              {dbHealth.optimization_score !== undefined && (
                <span style={{
                  fontSize: 'clamp(9px, 1.8vw, 11px)', fontWeight: 700,
                  color: dbHealth.optimization_score >= 80 ? '#4ADE80' : dbHealth.optimization_score >= 50 ? '#D4AF37' : '#EF4444',
                }}>
                  {dbHealth.optimization_score}/100
                </span>
              )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'clamp(8px, 2vw, 14px)' }}>
              <Metric label="COLLECTIONS" value={dbHealth.collections || 0} color="#64C8FF" />
              <Metric label="DATA" value={dbHealth.data_mb || 0} suffix="MB" color="#D4AF37" />
              <Metric label="INDEXES" value={dbHealth.index_mb || 0} suffix="MB" color="#4ADE80" />
            </div>
            <div style={{ display: 'flex', gap: 'clamp(8px, 2vw, 16px)', fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#5A5468', marginTop: 8 }}>
              <span>Docs: <strong style={{ color: '#D4AF37' }}>{(dbHealth.documents || 0).toLocaleString()}</strong></span>
              {dbHealth.bloat_count > 0 && (
                <span>Bloat: <strong style={{ color: '#EF4444' }}>{dbHealth.bloat_count} collections</strong></span>
              )}
            </div>
          </Card>

          {/* Live Request Feed */}
          <Card testId="request-feed" style={{ gridColumn: scr.xl ? 'span 3' : scr.lg ? 'span 2' : 'span 1' }}>
            <div style={lbl}>LIVE REQUEST FEED</div>
            <div style={{ maxHeight: scr.xl ? 200 : 160, overflowY: 'auto' }}>
              {reqLog.length === 0 && (
                <div style={{ fontSize: 'clamp(9px, 2vw, 11px)', color: '#5A5468', textAlign: 'center', padding: 12 }}>
                  No local requests yet. Send a message to ORA to see traffic here.
                </div>
              )}
              {reqLog.map((r, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 'clamp(6px, 1.5vw, 10px)',
                  padding: '6px 0', borderBottom: '1px solid rgba(212,175,55,0.06)',
                  fontSize: 'clamp(9px, 1.8vw, 11px)',
                }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#D4AF37', flexShrink: 0 }} />
                  <span style={{ color: '#D4AF37', flexShrink: 0 }}>{r.model}</span>
                  <span style={{ color: '#5A5468' }}>{r.input_chars}→{r.output_chars}ch</span>
                  <span style={{ color: '#5A5468', marginLeft: 'auto', fontSize: 'clamp(8px, 1.5vw, 10px)', whiteSpace: 'nowrap' }}>
                    {r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : ''}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', padding: 'clamp(12px, 3vw, 20px) 0', fontSize: 'clamp(8px, 1.5vw, 10px)', color: '#3A3448', letterSpacing: '0.1em' }}>
          AUREM SENTINEL OVERWATCH v1.0 | POLARIS BUILT INC.
        </div>
      </div>
    </div>
  );
}

/* ═══ MAIN EXPORT ═══ */
export default function SentinelOverwatch() {
  const [unlocked, setUnlocked] = useState(false);
  const [authToken, setAuthToken] = useState(null);

  useEffect(() => {
    const existingManifest = document.querySelector('link[rel="manifest"]');
    const originalHref = existingManifest?.getAttribute('href');

    if (existingManifest) {
      existingManifest.setAttribute('href', '/overwatch-manifest.json');
    } else {
      const link = document.createElement('link');
      link.rel = 'manifest';
      link.href = '/overwatch-manifest.json';
      document.head.appendChild(link);
    }

    let themeMeta = document.querySelector('meta[name="theme-color"]');
    const originalTheme = themeMeta?.getAttribute('content');
    if (themeMeta) {
      themeMeta.setAttribute('content', '#050507');
    } else {
      themeMeta = document.createElement('meta');
      themeMeta.name = 'theme-color';
      themeMeta.content = '#050507';
      document.head.appendChild(themeMeta);
    }

    const appleMetas = [
      { name: 'apple-mobile-web-app-capable', content: 'yes' },
      { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
      { name: 'apple-mobile-web-app-title', content: 'Sentinel' },
    ];
    const addedMetas = [];
    appleMetas.forEach(({ name, content }) => {
      if (!document.querySelector(`meta[name="${name}"]`)) {
        const meta = document.createElement('meta');
        meta.name = name;
        meta.content = content;
        document.head.appendChild(meta);
        addedMetas.push(meta);
      }
    });

    return () => {
      if (existingManifest && originalHref) existingManifest.setAttribute('href', originalHref);
      if (themeMeta && originalTheme) themeMeta.setAttribute('content', originalTheme);
      addedMetas.forEach(m => m.remove());
    };
  }, []);

  const handleUnlock = (token) => {
    if (token) setAuthToken(token);
    setUnlocked(true);
  };

  if (!unlocked) return <BiometricGate onUnlock={handleUnlock} />;
  return <OverwatchDashboard authToken={authToken} />;
}
