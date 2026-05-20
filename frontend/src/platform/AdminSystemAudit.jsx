/**
 * AdminSystemAudit — Iteration 202
 * =================================
 * Living Audit Dashboard at /admin/system-audit
 *
 * Honest, real-time state of all AUREM subsystems:
 * - Last nightly health check result
 * - All 4 agents (dry-run/live, paused, caps, stats)
 * - Scheduler jobs + next-run times
 * - Integration secrets present/missing
 * - Pixel summary + recent errors
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, CheckCircle2, XCircle, AlertTriangle, Clock, Shield, Zap,
  RefreshCw, PlayCircle, Loader2, Radio, Database, Key,
} from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

const COLORS = {
  bg:     '#08080F',
  panel:  '#0D0D17',
  border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37',
  good:   '#4ADE80',
  warn:   '#F59E0B',
  bad:    '#EF4444',
  text:   '#E8E0D0',
  textD:  '#8A8070',
};

function Badge({ kind, children, testid }) {
  const map = {
    healthy: { bg: 'rgba(74,222,128,0.1)', color: COLORS.good, border: 'rgba(74,222,128,0.3)' },
    degraded:{ bg: 'rgba(245,158,11,0.1)', color: COLORS.warn, border: 'rgba(245,158,11,0.3)' },
    critical:{ bg: 'rgba(239,68,68,0.1)',  color: COLORS.bad,  border: 'rgba(239,68,68,0.3)' },
    dry:     { bg: 'rgba(212,175,55,0.1)', color: COLORS.accent, border: 'rgba(212,175,55,0.3)' },
    live:    { bg: 'rgba(239,68,68,0.1)',  color: COLORS.bad,  border: 'rgba(239,68,68,0.3)' },
    paused:  { bg: 'rgba(138,128,112,0.1)',color: COLORS.textD,border: 'rgba(138,128,112,0.3)' },
    ok:      { bg: 'rgba(74,222,128,0.08)',color: COLORS.good, border: 'rgba(74,222,128,0.25)' },
    missing: { bg: 'rgba(239,68,68,0.08)', color: COLORS.bad,  border: 'rgba(239,68,68,0.25)' },
  };
  const s = map[kind] || map.ok;
  return (
    <span data-testid={testid} style={{
      display:'inline-flex',alignItems:'center',padding:'3px 10px',borderRadius:20,
      fontSize:10,fontWeight:700,letterSpacing:'0.12em',textTransform:'uppercase',
      background:s.bg, color:s.color, border:`1px solid ${s.border}`,
    }}>{children}</span>
  );
}

function Card({ title, icon:Icon, children, testid, action }) {
  return (
    <div data-testid={testid} style={{
      background:COLORS.panel,border:`1px solid ${COLORS.border}`,borderRadius:14,padding:'20px 22px',
    }}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:14}}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          {Icon && <Icon size={16} color={COLORS.accent}/>}
          <h3 style={{fontFamily:"'Cinzel',serif",fontSize:13,fontWeight:700,color:COLORS.accent,letterSpacing:'0.14em',textTransform:'uppercase',margin:0}}>{title}</h3>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function AdminSystemAudit() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [toggling, setToggling] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tok = getPlatformToken();
      const r = await fetch(`${API}/api/admin/system-audit`, { headers: { Authorization: `Bearer ${tok}` } });
      if (r.ok) setData(await r.json());
    } catch (e) { console.warn(e); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const runHealthCheck = async () => {
    setRunning(true);
    try {
      const tok = getPlatformToken();
      await fetch(`${API}/api/admin/system-audit/run-health-check`, {
        method:'POST', headers: { Authorization: `Bearer ${tok}` },
      });
      await load();
    } catch (e) { alert('Failed: ' + e.message); }
    setRunning(false);
  };

  const toggleAgent = async (agentId, action) => {
    setToggling(agentId + ':' + action);
    try {
      const tok = getPlatformToken();
      // action in {'pause','resume'}
      const r = await fetch(`${API}/api/agents/${agentId}/${action}`, {
        method:'POST', headers: { Authorization: `Bearer ${tok}`, 'Content-Type':'application/json' },
      });
      if (!r.ok) throw new Error('failed');
      await load();
    } catch (e) { alert('Toggle failed'); }
    setToggling(null);
  };

  if (loading && !data) {
    return <div data-testid="audit-loading" style={{minHeight:'60vh',display:'flex',alignItems:'center',justifyContent:'center',color:COLORS.textD,fontSize:13}}>Loading system audit…</div>;
  }
  if (!data) {
    return <div data-testid="audit-error" style={{padding:40,color:COLORS.bad}}>Failed to load system audit. Admin access required.</div>;
  }

  const hc = data.health_check || {};
  const checklist = hc.checklist || [];

  return (
    <div data-testid="admin-system-audit" style={{minHeight:'100vh',background:COLORS.bg,color:COLORS.text,fontFamily:"'Jost',sans-serif",padding:'32px 40px'}}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginBottom:28,gap:20,flexWrap:'wrap'}}>
        <div>
          <Link to="/dashboard" style={{fontSize:11,color:COLORS.textD,letterSpacing:'0.15em',textTransform:'uppercase',textDecoration:'none'}}>← Dashboard</Link>
          <h1 style={{fontFamily:"'Cinzel',serif",fontSize:30,fontWeight:700,color:'#FFF',letterSpacing:'0.03em',margin:'6px 0 4px'}}>System Audit</h1>
          <p style={{fontSize:13,color:COLORS.textD}}>Honest real-time state of all AUREM subsystems — generated {data.generated_at?.slice(0,19)}Z</p>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:12}}>
          <Badge kind={data.verdict} testid="audit-verdict">{data.verdict}</Badge>
          <button data-testid="audit-refresh" onClick={load} disabled={loading} style={iconBtn}>
            <RefreshCw size={13} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {/* Red flags */}
      {data.red_flags && data.red_flags.length > 0 && (
        <div data-testid="audit-red-flags" style={{
          background:'rgba(239,68,68,0.08)',border:'1px solid rgba(239,68,68,0.3)',borderRadius:12,padding:'14px 18px',marginBottom:20,
        }}>
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
            <AlertTriangle size={16} color={COLORS.bad}/>
            <div style={{fontSize:11,letterSpacing:'0.14em',color:COLORS.bad,fontWeight:700,textTransform:'uppercase'}}>Red Flags</div>
          </div>
          <ul style={{margin:0,padding:'0 0 0 20px',fontSize:13,color:COLORS.text}}>
            {data.red_flags.map((f,i) => <li key={i} style={{padding:'3px 0'}}>{f}</li>)}
          </ul>
        </div>
      )}

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(360px,1fr))',gap:16}}>
        {/* Health Check */}
        <Card title="Nightly Health Check" icon={Activity} testid="audit-card-health"
          action={<button data-testid="audit-run-health" onClick={runHealthCheck} disabled={running} style={smallBtn}>
            {running ? <Loader2 size={11} style={{animation:'spin 1s linear infinite'}}/> : <PlayCircle size={11}/>} Run Now
          </button>}>
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12}}>
            <Badge kind={hc.overall === 'PASS' ? 'ok' : hc.overall === 'FAIL' ? 'missing' : 'degraded'}>
              {hc.overall || 'not run'}
            </Badge>
            {hc.ran_at && <span style={{fontSize:11,color:COLORS.textD}}>at {hc.ran_at.slice(11,19)}Z</span>}
          </div>
          {checklist.length === 0 ? (
            <p style={{fontSize:12,color:COLORS.textD}}>No check data yet, press “Run Now”.</p>
          ) : (
            <ul style={{margin:0,padding:0,listStyle:'none'}}>
              {checklist.map((c,i) => (
                <li key={i} style={{display:'flex',alignItems:'center',gap:10,padding:'6px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                  {c.ok ? <CheckCircle2 size={14} color={COLORS.good}/> : <XCircle size={14} color={COLORS.bad}/>}
                  <span style={{fontSize:12.5,color:c.ok?COLORS.text:COLORS.bad}}>{c.step}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Agents */}
        <Card title="4-Agent Autonomous System" icon={Zap} testid="audit-card-agents">
          {(data.agents || []).length === 0 && <p style={{fontSize:12,color:COLORS.textD}}>No agents registered.</p>}
          {(data.agents || []).map((a) => (
            <div key={a.agent_id} data-testid={`audit-agent-${a.agent_id}`} style={{padding:'10px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8}}>
                <div style={{flex:1}}>
                  <div style={{fontSize:13.5,fontWeight:600,color:'#FFF'}}>{a.emoji} {a.name}</div>
                  <div style={{fontSize:11,color:COLORS.textD,marginTop:2}}>{a.job}</div>
                </div>
                <div style={{display:'flex',gap:6,alignItems:'center',flexWrap:'wrap'}}>
                  <Badge kind="live">LIVE</Badge>
                  {a.paused && <Badge kind="paused">Paused</Badge>}
                </div>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:10,marginTop:8}}>
                <div style={{fontSize:11,color:COLORS.textD}}>
                  Sent today: <strong style={{color:a.cap_reached?COLORS.bad:COLORS.text}}>{a.sent_today}</strong> / {a.daily_cap}
                </div>
                <div style={{flex:1}}/>
                <button
                  data-testid={`audit-agent-${a.agent_id}-toggle-pause`}
                  onClick={() => toggleAgent(a.agent_id, a.paused ? 'resume' : 'pause')}
                  disabled={toggling === a.agent_id + ':pause' || toggling === a.agent_id + ':resume'}
                  style={smallBtn}
                >
                  {a.paused ? 'Resume' : 'Pause'}
                </button>
              </div>
            </div>
          ))}
        </Card>

        {/* Scheduler */}
        <Card title="Scheduler" icon={Clock} testid="audit-card-scheduler">
          <Badge kind={data.scheduler?.running ? 'ok' : 'missing'}>
            {data.scheduler?.running ? 'Running' : 'Not running'}
          </Badge>
          <ul style={{margin:'12px 0 0',padding:0,listStyle:'none',maxHeight:260,overflowY:'auto'}}>
            {(data.scheduler?.jobs || []).map((j,i) => (
              <li key={i} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid rgba(255,255,255,0.04)',fontSize:12}}>
                <span style={{color:COLORS.text,fontFamily:"'JetBrains Mono',monospace"}}>{j.id}</span>
                <span style={{color:COLORS.textD}}>{j.next_run ? j.next_run.slice(5,16).replace('T',' ') : '—'}</span>
              </li>
            ))}
          </ul>
        </Card>

        {/* Integrations */}
        <Card title="Integration Secrets" icon={Key} testid="audit-card-integrations">
          <div style={{fontSize:11,letterSpacing:'0.14em',color:COLORS.textD,fontWeight:700,textTransform:'uppercase',marginBottom:8}}>Required</div>
          {(data.integrations?.required || []).map((r,i) => (
            <div key={i} data-testid={`audit-int-req-${r.name}`} style={{display:'flex',justifyContent:'space-between',padding:'5px 0',fontSize:12}}>
              <span style={{color:COLORS.text}}>{r.name}</span>
              <Badge kind={r.present ? 'ok' : 'missing'}>{r.present ? 'set' : 'missing'}</Badge>
            </div>
          ))}
          <div style={{fontSize:11,letterSpacing:'0.14em',color:COLORS.textD,fontWeight:700,textTransform:'uppercase',margin:'14px 0 8px'}}>Optional</div>
          {(data.integrations?.optional || []).map((r,i) => (
            <div key={i} data-testid={`audit-int-opt-${r.name}`} style={{display:'flex',justifyContent:'space-between',padding:'5px 0',fontSize:12}}>
              <span style={{color:COLORS.text}}>{r.name}</span>
              <Badge kind={r.present ? 'ok' : 'degraded'}>{r.present ? 'set' : 'optional'}</Badge>
            </div>
          ))}
        </Card>

        {/* Pixel */}
        <Card title="Live Pixel" icon={Radio} testid="audit-card-pixel">
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            <div>
              <div style={{fontSize:10,letterSpacing:'0.14em',color:COLORS.textD,textTransform:'uppercase',fontWeight:600}}>Active Keys</div>
              <div style={{fontSize:26,fontWeight:800,color:'#FFF',fontFamily:"'Cinzel',serif"}}>{data.pixel?.active_keys ?? 0}</div>
            </div>
            <div>
              <div style={{fontSize:10,letterSpacing:'0.14em',color:COLORS.textD,textTransform:'uppercase',fontWeight:600}}>Reports 24h</div>
              <div style={{fontSize:26,fontWeight:800,color:'#FFF',fontFamily:"'Cinzel',serif"}}>{data.pixel?.reports_24h ?? 0}</div>
            </div>
          </div>
        </Card>

        {/* Recent errors */}
        <Card title="Recent Errors" icon={Shield} testid="audit-card-errors">
          {(data.recent_errors || []).length === 0 ? (
            <p style={{fontSize:12,color:COLORS.textD}}>No recent errors. Clean slate.</p>
          ) : (
            <ul style={{margin:0,padding:0,listStyle:'none'}}>
              {data.recent_errors.map((e,i) => (
                <li key={i} style={{padding:'8px 0',borderBottom:'1px solid rgba(255,255,255,0.04)',fontSize:12}}>
                  <div style={{color:COLORS.bad,fontWeight:600}}>{e.event_type}</div>
                  <div style={{color:COLORS.textD,marginTop:2}}>{(e.timestamp||'').slice(0,19)} {e.email && '· '+e.email}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

const iconBtn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.2)',borderRadius:8,
  color:'#D4AF37',fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};
const smallBtn = {
  display:'inline-flex',alignItems:'center',gap:5,padding:'5px 10px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.22)',borderRadius:6,
  color:'#D4AF37',fontSize:10,fontWeight:700,letterSpacing:'0.1em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};
