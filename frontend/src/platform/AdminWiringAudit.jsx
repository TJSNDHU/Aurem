/**
 * AdminWiringAudit — Iteration 203
 * =================================
 * /admin/wiring-audit
 *
 * Automated probe of every admin + customer feature.
 * Each row shows:
 *   ✅ ok      — backend responds 2xx
 *   🟡 wired   — route exists but auth/validation required (healthy)
 *   ❌ missing — 404 (not wired)
 *   ⚠️  error  — 5xx or network failure
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, RefreshCw, Loader2 } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

const COLORS = {
  bg: '#08080F', panel: '#0D0D17', border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

function StatusIcon({ status }) {
  if (status === 'ok')      return <CheckCircle2 size={16} color={COLORS.good}/>;
  if (status === 'wired')   return <CheckCircle2 size={16} color={COLORS.accent}/>;
  if (status === 'missing') return <XCircle size={16} color={COLORS.bad}/>;
  if (status === 'error')   return <AlertTriangle size={16} color={COLORS.warn}/>;
  return <HelpCircle size={16} color={COLORS.textD}/>;
}

function Row({ item, idx }) {
  const badge = {
    ok:      { label: '✅ OK',      color: COLORS.good },
    wired:   { label: '🟡 WIRED',   color: COLORS.accent },
    missing: { label: '❌ MISSING', color: COLORS.bad },
    error:   { label: '⚠️  ERROR',  color: COLORS.warn },
  }[item.status] || { label: '—', color: COLORS.textD };
  return (
    <tr data-testid={`wiring-row-${idx}`} style={{borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
      <td style={td}><StatusIcon status={item.status}/></td>
      <td style={{...td, color:COLORS.text, fontWeight:600}}>{item.feature}</td>
      <td style={{...td, color:COLORS.textD}}>{item.panel}</td>
      <td style={{...td, color:badge.color, fontSize:10, letterSpacing:'0.1em', fontWeight:700}}>{badge.label}</td>
      <td style={{...td, color:COLORS.textD, fontFamily:"'JetBrains Mono',monospace", fontSize:11}}>
        {item.probe} <span style={{color:'#555'}}>· {item.http}</span>
      </td>
      <td style={{...td, color:COLORS.textD, fontSize:10}}>{item.component}</td>
    </tr>
  );
}

export default function AdminWiringAudit() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState([]);
  const [runningNightly, setRunningNightly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tok = getPlatformToken();
      const [r1, r2] = await Promise.all([
        fetch(`${API}/api/admin/wiring-audit`, { headers:{ Authorization: `Bearer ${tok}` }}),
        fetch(`${API}/api/admin/wiring-audit/history?limit=14`, { headers:{ Authorization: `Bearer ${tok}` }}),
      ]);
      if (r1.ok) setData(await r1.json());
      if (r2.ok) {
        const d = await r2.json();
        setHistory(d.history || []);
      }
    } catch (e) { console.warn(e); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const runNightlyNow = async () => {
    setRunningNightly(true);
    try {
      const tok = getPlatformToken();
      await fetch(`${API}/api/admin/wiring-audit/run-nightly`, {
        method:'POST', headers:{ Authorization: `Bearer ${tok}` },
      });
      await load();
    } catch (e) { alert('Failed: ' + e.message); }
    setRunningNightly(false);
  };

  if (loading && !data) return (
    <div data-testid="wiring-loading" style={{minHeight:'60vh',display:'flex',alignItems:'center',justifyContent:'center',color:COLORS.textD,fontSize:13,fontFamily:"'Jost',sans-serif"}}>
      <Loader2 size={18} style={{animation:'spin 1s linear infinite',marginRight:10}}/> Probing every feature…
    </div>
  );
  if (!data) return <div data-testid="wiring-error" style={{padding:40,color:COLORS.bad,fontFamily:"'Jost',sans-serif"}}>Admin access required.</div>;

  const s = data.summary || {};
  return (
    <div data-testid="admin-wiring-audit" style={{minHeight:'100vh',background:COLORS.bg,color:COLORS.text,fontFamily:"'Jost',sans-serif",padding:'32px 40px'}}>
      <div style={{marginBottom:24}}>
        <Link to="/dashboard" style={{fontSize:11,color:COLORS.textD,letterSpacing:'0.15em',textTransform:'uppercase',textDecoration:'none'}}>← Dashboard</Link>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginTop:6,flexWrap:'wrap',gap:16}}>
          <div>
            <h1 style={{fontFamily:"'Cinzel',serif",fontSize:30,fontWeight:700,color:'#FFF',letterSpacing:'0.03em',margin:0}}>Wiring Audit</h1>
            <p style={{fontSize:13,color:COLORS.textD,marginTop:4}}>Every feature probed for correct panel assignment — {s.generated_at?.slice(0,19)}Z</p>
          </div>
          <button data-testid="wiring-refresh" onClick={load} disabled={loading} style={iconBtn}>
            <RefreshCw size={13} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Re-probe
          </button>
          <button data-testid="wiring-run-nightly" onClick={runNightlyNow} disabled={runningNightly} style={{...iconBtn, marginLeft:8}}>
            {runningNightly ? <Loader2 size={13} style={{animation:'spin 1s linear infinite'}}/> : <RefreshCw size={13}/>} Run Nightly (alerts on &lt; 95%)
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:12,marginBottom:24}}>
        <SumCard label="Coverage" value={`${s.pct}%`} tone="good" testid="wiring-pct"/>
        <SumCard label="OK / Wired" value={s.ok_or_wired} tone="good" testid="wiring-ok"/>
        <SumCard label="Missing" value={s.missing} tone={s.missing > 0 ? 'bad' : 'good'} testid="wiring-missing"/>
        <SumCard label="Errors" value={s.error} tone={s.error > 0 ? 'warn' : 'good'} testid="wiring-errors"/>
        <SumCard label="Total" value={s.total} tone="neutral" testid="wiring-total"/>
      </div>

      {/* Admin panel table */}
      <Section title="Admin Panel" subtitle="/dashboard + /admin/*" rows={data.admin || []} prefix="admin" testid="wiring-admin"/>
      <div style={{height:24}}/>
      <Section title="Customer Portal" subtitle="/my/*" rows={data.customer || []} prefix="cust" testid="wiring-customer"/>
      <div style={{height:24}}/>

      {/* Nightly audit history */}
      <div data-testid="wiring-history" style={{background:COLORS.panel,border:`1px solid ${COLORS.border}`,borderRadius:14,padding:'18px 22px'}}>
        <div style={{display:'flex',alignItems:'baseline',gap:10,marginBottom:12}}>
          <h3 style={{fontFamily:"'Cinzel',serif",fontSize:15,fontWeight:700,color:COLORS.accent,letterSpacing:'0.12em',textTransform:'uppercase',margin:0}}>Nightly History</h3>
          <span style={{fontSize:11,color:COLORS.textD}}>Last 14 runs · WA alert fires when coverage &lt; 95%</span>
        </div>
        {history.length === 0 ? (
          <p style={{fontSize:12,color:COLORS.textD}}>No nightly runs yet. Cron fires at 03:15 AM daily, or click “Run Nightly” above to trigger now.</p>
        ) : (
          <div style={{overflowX:'auto'}}>
            <table style={{width:'100%',borderCollapse:'collapse'}}>
              <thead>
                <tr>
                  <th style={th}>Ran At (UTC)</th>
                  <th style={th}>Coverage</th>
                  <th style={th}>OK/Total</th>
                  <th style={th}>Missing</th>
                  <th style={th}>Errors</th>
                  <th style={th}>Alerted</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const below = (h.coverage_pct || 0) < (h.threshold || 95);
                  return (
                    <tr key={i} data-testid={`wiring-history-row-${i}`} style={{borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                      <td style={td}>{(h.ran_at||'').slice(0,19).replace('T',' ')}</td>
                      <td style={{...td, color: below?COLORS.bad:COLORS.good, fontWeight:700}}>{h.coverage_pct}%</td>
                      <td style={td}>{h.ok_or_wired}/{h.total}</td>
                      <td style={td}>{(h.missing || []).length}</td>
                      <td style={td}>{(h.errors  || []).length}</td>
                      <td style={td}>{h.alerted ? <span style={{color:COLORS.warn,fontSize:11,fontWeight:700}}>📱 Sent</span> : <span style={{color:COLORS.textD,fontSize:11}}>—</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function SumCard({ label, value, tone, testid }) {
  const color = tone === 'good' ? COLORS.good : tone === 'bad' ? COLORS.bad : tone === 'warn' ? COLORS.warn : COLORS.accent;
  return (
    <div data-testid={testid} style={{background:COLORS.panel,border:`1px solid ${COLORS.border}`,borderRadius:12,padding:'14px 18px'}}>
      <div style={{fontSize:10,letterSpacing:'0.18em',color:COLORS.textD,fontWeight:600,textTransform:'uppercase'}}>{label}</div>
      <div style={{fontSize:24,fontWeight:800,color,fontFamily:"'Cinzel',serif",marginTop:4}}>{value}</div>
    </div>
  );
}

function Section({ title, subtitle, rows, prefix, testid }) {
  return (
    <div data-testid={testid} style={{background:COLORS.panel,border:`1px solid ${COLORS.border}`,borderRadius:14,padding:'18px 22px',overflow:'hidden'}}>
      <div style={{display:'flex',alignItems:'baseline',gap:10,marginBottom:12}}>
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:15,fontWeight:700,color:COLORS.accent,letterSpacing:'0.12em',textTransform:'uppercase',margin:0}}>{title}</h3>
        <span style={{fontSize:11,color:COLORS.textD}}>{subtitle}</span>
      </div>
      <div style={{overflowX:'auto'}}>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead>
            <tr>
              <th style={th}></th>
              <th style={th}>Feature</th>
              <th style={th}>Panel / Route</th>
              <th style={th}>Status</th>
              <th style={th}>Backend Probe</th>
              <th style={th}>Component</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => <Row key={i} idx={`${prefix}-${i}`} item={r}/>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const th = {
  textAlign: 'left', padding: '8px 10px', fontSize: 10, letterSpacing: '0.16em',
  color: COLORS.textD, textTransform: 'uppercase', fontWeight: 700,
  borderBottom: '1px solid rgba(255,255,255,0.06)',
};
const td = { padding: '9px 10px', fontSize: 12.5, verticalAlign: 'middle' };
const iconBtn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.2)',borderRadius:8,
  color:'#D4AF37',fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};
