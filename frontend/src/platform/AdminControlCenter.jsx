/**
 * AdminControlCenter — Iteration 206
 * ====================================
 * /admin/control-center
 *
 * One-screen NASA mission-control aggregating every stats endpoint:
 *  - System Audit verdict + red flags
 *  - Wiring Audit coverage
 *  - DB indexes status
 *  - Redis cache hit rate
 *  - Pixel buffer batching efficiency
 *  - Agents status (4)
 *  - Scheduler jobs (19)
 *  - Recent nightly runs
 *
 * Auto-refreshes every 30 seconds.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, Database, Zap, Clock, Radio, TrendingUp, AlertTriangle,
  CheckCircle2, RefreshCw, Gauge, Layers, Send, Cpu, GitBranch,
} from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const REFRESH_MS = 30000;

const C = {
  bg: '#06060C', panel: '#0D0D17', border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

function Badge({ tone = 'neutral', children }) {
  const map = {
    good: { bg: 'rgba(74,222,128,0.1)', color: C.good, border: 'rgba(74,222,128,0.35)' },
    warn: { bg: 'rgba(245,158,11,0.1)', color: C.warn, border: 'rgba(245,158,11,0.35)' },
    bad:  { bg: 'rgba(239,68,68,0.1)',  color: C.bad,  border: 'rgba(239,68,68,0.35)' },
    gold: { bg: 'rgba(212,175,55,0.1)', color: C.accent,border: 'rgba(212,175,55,0.35)' },
    neutral: { bg: 'rgba(138,128,112,0.08)', color: C.textD, border: 'rgba(138,128,112,0.2)' },
  };
  const s = map[tone] || map.neutral;
  return <span style={{display:'inline-flex',padding:'2px 9px',borderRadius:20,fontSize:9.5,fontWeight:700,letterSpacing:'0.14em',textTransform:'uppercase',background:s.bg,color:s.color,border:`1px solid ${s.border}`}}>{children}</span>;
}

function Tile({ icon: Icon, label, value, sub, tone, testid }) {
  const color = tone === 'good' ? C.good : tone === 'bad' ? C.bad : tone === 'warn' ? C.warn : C.accent;
  return (
    <div data-testid={testid} style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'18px 20px'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
        {Icon && <Icon size={15} color={C.accent}/>}
        <span style={{fontSize:10,letterSpacing:'0.2em',color:C.textD,fontWeight:700,textTransform:'uppercase'}}>{label}</span>
      </div>
      <div style={{fontSize:30,fontWeight:800,color,fontFamily:"'Cinzel',serif",lineHeight:1}}>{value}</div>
      {sub && <div style={{fontSize:11,color:C.textD,marginTop:6,letterSpacing:'0.04em'}}>{sub}</div>}
    </div>
  );
}

function Card({ title, icon: Icon, action, children, testid, span = 1 }) {
  return (
    <div data-testid={testid} style={{gridColumn:`span ${span}`,background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 20px'}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          {Icon && <Icon size={14} color={C.accent}/>}
          <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.accent,letterSpacing:'0.18em',textTransform:'uppercase',margin:0}}>{title}</h3>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function AdminControlCenter() {
  const [state, setState] = useState({ loading: true, lastRefresh: null });
  const [system, setSystem] = useState(null);
  const [wiring, setWiring] = useState(null);
  const [indexes, setIndexes] = useState(null);
  const [cache, setCache] = useState(null);
  const [buffer, setBuffer] = useState(null);
  const [anomaly, setAnomaly] = useState(null);
  const [anomalyRunning, setAnomalyRunning] = useState(false);
  const [telegram, setTelegram] = useState(null);
  const [builder, setBuilder] = useState(null);
  const [evolver, setEvolver] = useState(null);
  const [legion, setLegion] = useState(null);
  const [tenants, setTenants] = useState(null);  // Iter 320: onboarding 3-number summary
  const [breakers, setBreakers] = useState(null);  // Iter 3: circuit breaker dots
  const [hotReplies, setHotReplies] = useState(null);  // Iter 3: Closer-flagged hot leads

  const runAnomalyNow = useCallback(async () => {
    setAnomalyRunning(true);
    try {
      const tok = getPlatformToken();
      await fetch(`${API}/api/admin/anomaly/run-now`, {
        method: 'POST', headers: { Authorization: `Bearer ${tok}` },
      });
      // Re-fetch anomaly state
      const r = await fetch(`${API}/api/admin/anomaly/status`, { headers: { Authorization: `Bearer ${tok}` }});
      if (r.ok) setAnomaly(await r.json());
    } catch (e) { console.warn(e); }
    setAnomalyRunning(false);
  }, []);

  const loadAll = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }));
    try {
      const tok = getPlatformToken();
      const H = { Authorization: `Bearer ${tok}` };
      const [sy, wi, ix, ca, bu, an, tg, bd, ev, lg, tn, br, hr] = await Promise.all([
        fetch(`${API}/api/admin/system-audit`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/wiring-audit`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/db-indexes/status`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/cache/stats`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/pixel-buffer/stats`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/anomaly/status`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/telegram/status`).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/builder/stats`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/evolver/status`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/legion/health`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/mission-control/tenants-summary`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/breakers/status`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/mission-control/hot-replies?hours=48&limit=10`, { headers: H }).then((r) => r.ok ? r.json() : null),
      ]);
      setSystem(sy); setWiring(wi); setIndexes(ix); setCache(ca); setBuffer(bu); setAnomaly(an);
      setTelegram(tg); setBuilder(bd); setEvolver(ev); setLegion(lg); setTenants(tn);
      setBreakers(br); setHotReplies(hr);
    } catch (e) { console.warn(e); }
    setState({ loading: false, lastRefresh: new Date() });
  }, []);

  useEffect(() => {
    loadAll();
    const t = setInterval(loadAll, REFRESH_MS);
    return () => clearInterval(t);
  }, [loadAll]);

  const verdict = system?.verdict || 'unknown';
  const verdictTone = verdict === 'healthy' ? 'good' : verdict === 'degraded' ? 'warn' : verdict === 'critical' ? 'bad' : 'neutral';
  const cacheHitRate = cache?.hit_rate_pct ?? 0;
  const cacheTone = cacheHitRate >= 70 ? 'good' : cacheHitRate >= 40 ? 'warn' : cacheHitRate > 0 ? 'bad' : 'neutral';
  const coverage = wiring?.summary?.pct ?? 0;
  const coverageTone = coverage >= 95 ? 'good' : coverage >= 80 ? 'warn' : 'bad';
  const pixelBuffered = buffer?.buffered ?? 0;
  const pixelFlushed = buffer?.flushed ?? 0;
  const efficiency = pixelBuffered > 0 && pixelFlushed > 0
    ? Math.max(0, Math.round((1 - (pixelFlushed / (pixelBuffered || 1))) * 100))
    : 0;
  const nowStr = state.lastRefresh ? state.lastRefresh.toISOString().slice(11, 19) + 'Z' : '—';

  return (
    <div data-testid="admin-control-center" style={{
      minHeight:'100vh',background:C.bg,color:C.text,fontFamily:"'Jost',sans-serif",padding:'28px 36px',
    }}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginBottom:24,flexWrap:'wrap',gap:16}}>
        <div>
          <Link to="/dashboard" style={{fontSize:11,color:C.textD,letterSpacing:'0.2em',textTransform:'uppercase',textDecoration:'none'}}>← Dashboard</Link>
          <h1 style={{fontFamily:"'Cinzel',serif",fontSize:32,fontWeight:700,color:'#FFF',letterSpacing:'0.04em',margin:'6px 0 4px'}}>Control Center</h1>
          <p style={{fontSize:12,color:C.textD,letterSpacing:'0.06em'}}>AUREM mission-control · auto-refresh every 30s · last {nowStr}</p>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          {telegram && (() => {
            const tone = telegram.ok ? 'good'
              : telegram.configured ? 'warn' : 'bad';
            const label = telegram.ok ? `TG · ${telegram.bot?.username || 'live'}`
              : telegram.configured ? 'TG · unreachable' : 'TG · off';
            return (
              <span data-testid="cc-telegram-chip">
                <Badge tone={tone}>
                  <Send size={9} style={{marginRight:4,verticalAlign:-1}}/>{label}
                </Badge>
              </span>
            );
          })()}
          <Badge tone={verdictTone}>{verdict}</Badge>
          <button data-testid="cc-refresh" onClick={loadAll} disabled={state.loading} style={btn}>
            <RefreshCw size={12} style={state.loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {/* Top-row mission tiles */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:16}}>
        <Tile icon={Gauge}     label="System Verdict"  value={verdict.toUpperCase()} sub={`${(system?.red_flags || []).length} red flags`} tone={verdictTone} testid="cc-tile-verdict"/>
        <Tile icon={TrendingUp}label="Wiring Coverage" value={`${coverage}%`}        sub={`${wiring?.summary?.ok_or_wired || 0}/${wiring?.summary?.total || 0} features`} tone={coverageTone} testid="cc-tile-coverage"/>
        <Tile icon={Database}  label="DB Indexes"      value={indexes?.plain_count ?? '—'} sub={`+ ${indexes?.ttl_count ?? 0} TTL · ${indexes?.elapsed_ms ?? 0}ms`} tone="good" testid="cc-tile-indexes"/>
        <Tile icon={Layers}    label="Cache Hit Rate"  value={`${cacheHitRate}%`}    sub={`${cache?.total_lookups || 0} lookups · ${cache?.errors || 0} errors`} tone={cacheTone} testid="cc-tile-cache"/>
        <Tile icon={Radio}     label="Pixel Buffer"    value={buffer?.buffer_size ?? 0} sub={`${pixelFlushed} flushed · ${buffer?.direct_writes ?? 0} direct`} tone="good" testid="cc-tile-buffer"/>
      </div>

      {/* Onboarding 3-number widget (Iter 320) — the numbers the founder watches */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:12,marginBottom:16}}>
        <Tile
          icon={Activity}
          label="Total Tenants"
          value={tenants?.total_tenants ?? '—'}
          sub="AUREM signups"
          tone={tenants?.total_tenants > 0 ? 'good' : 'neutral'}
          testid="cc-tile-tenants-total"
        />
        <Tile
          icon={CheckCircle2}
          label="Pixel Installed"
          value={tenants?.pixel_installed_count ?? '—'}
          sub={tenants ? `${tenants.install_rate_pct}% install rate` : '—'}
          tone={(tenants?.install_rate_pct ?? 0) >= 50 ? 'good' : (tenants?.install_rate_pct ?? 0) >= 20 ? 'warn' : 'bad'}
          testid="cc-tile-tenants-pixel"
        />
        <Tile
          icon={Clock}
          label="Pending Onboarding"
          value={tenants?.pending_onboarding_count ?? '—'}
          sub={(tenants?.pending_onboarding_count ?? 0) > 0 ? 'reminder cron active' : 'queue clear'}
          tone={(tenants?.pending_onboarding_count ?? 0) > 5 ? 'bad' : (tenants?.pending_onboarding_count ?? 0) > 0 ? 'warn' : 'good'}
          testid="cc-tile-tenants-pending"
        />
      </div>

      {/* Iter 3 — Circuit Breakers + Hot Replies */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:16}}>
        {/* Circuit Breakers — 6 coloured dots */}
        <div data-testid="cc-breakers-widget" style={{background:'rgba(26,20,12,0.6)',border:'1px solid rgba(212,175,55,0.2)',borderRadius:10,padding:16}}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10}}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <Radio size={16} color="#D4AF37"/>
              <span style={{fontSize:13,fontWeight:600,color:'#F5F2EB'}}>Circuit Breakers</span>
            </div>
            <span style={{fontSize:11,color: (breakers?.all_healthy) ? '#7ED957' : '#E06A4E', fontWeight:600}}>
              {breakers == null ? '—' : breakers.all_healthy ? 'ALL HEALTHY' : `${(breakers.breakers||[]).filter(b=>b.state!=='closed').length} TRIPPED`}
            </span>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10}}>
            {(breakers?.breakers || []).map((b) => {
              const dotColor = b.state === 'closed' ? '#7ED957' : b.state === 'half-open' ? '#E6B85C' : '#E06A4E';
              return (
                <div key={b.name} data-testid={`cc-breaker-${b.name}`} style={{display:'flex',alignItems:'center',gap:8,fontSize:12,color:'#D4C9A8'}}>
                  <span style={{width:10,height:10,borderRadius:'50%',background:dotColor,boxShadow:`0 0 6px ${dotColor}`,flexShrink:0}} />
                  <span style={{flex:1,overflow:'hidden',textOverflow:'ellipsis'}}>{b.name}</span>
                  <span style={{fontSize:10,opacity:0.7}}>{b.fail_count ?? 0}/{b.fail_max ?? '—'}</span>
                </div>
              );
            })}
            {breakers == null && (
              <div style={{gridColumn:'1 / -1',fontSize:12,color:'#888',textAlign:'center',padding:8}}>Loading…</div>
            )}
          </div>
        </div>

        {/* Hot Replies — Closer-flagged inbound replies */}
        <div data-testid="cc-hot-replies-widget" style={{background:'rgba(26,20,12,0.6)',border:'1px solid rgba(224,106,78,0.25)',borderRadius:10,padding:16}}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10}}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <TrendingUp size={16} color="#E06A4E"/>
              <span style={{fontSize:13,fontWeight:600,color:'#F5F2EB'}}>Hot Replies (48h)</span>
            </div>
            <span data-testid="cc-hot-replies-count" style={{fontSize:11,color:'#E06A4E',fontWeight:700,background:'rgba(224,106,78,0.15)',padding:'2px 8px',borderRadius:999}}>
              {hotReplies?.count ?? 0}
            </span>
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:6,maxHeight:220,overflowY:'auto'}}>
            {(hotReplies?.replies || []).length === 0 && (
              <div style={{fontSize:12,color:'#888',textAlign:'center',padding:12}}>
                No hot replies yet · Closer is watching
              </div>
            )}
            {(hotReplies?.replies || []).map((r) => (
              <div key={r.event_id} data-testid={`cc-hot-reply-${r.lead_id}`} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 10px',background:'rgba(224,106,78,0.08)',borderRadius:6,fontSize:12}}>
                <span style={{fontSize:11,fontWeight:700,color:'#E06A4E',minWidth:28}}>{r.score}</span>
                <div style={{flex:1,overflow:'hidden'}}>
                  <div style={{color:'#F5F2EB',fontWeight:600,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.business_name || r.lead_id}</div>
                  <div style={{color:'#8B8070',fontSize:10,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{(r.reason || '').slice(0, 90)}</div>
                </div>
                <span style={{fontSize:10,color:'#D4AF37',textTransform:'uppercase',fontWeight:600}}>{r.intent || 'hot'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(360px,1fr))',gap:14}}>

        {/* Red flags */}
        <Card title="Red Flags" icon={AlertTriangle} testid="cc-card-flags">
          {(system?.red_flags || []).length === 0 ? (
            <div style={{display:'flex',alignItems:'center',gap:8,color:C.good,fontSize:13}}>
              <CheckCircle2 size={15}/> All subsystems nominal
            </div>
          ) : (
            <ul style={{margin:0,padding:'0 0 0 16px',fontSize:12,color:C.text,lineHeight:1.7}}>
              {system.red_flags.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          )}
        </Card>

        {/* Agents */}
        <Card title="4-Agent Autonomous System" icon={Zap} testid="cc-card-agents">
          {(system?.agents || []).map((a) => {
            // iter D-81d — derive badge tone from actual agent state.
            // Previously hardcoded tone="bad" which painted all 4 agents
            // red even when system verdict was "healthy" — pure visual
            // contradiction. Real states:
            //   active + cap not reached → LIVE (green)
            //   active + cap reached     → CAPPED (neutral)
            //   paused                   → PAUSED (neutral)
            //   any other status         → DOWN  (bad)
            const isActive = a.status === 'active' || a.status === 'running';
            const isPaused = a.paused === true || a.status === 'paused';
            const isCapped = a.cap_reached === true;
            let badgeTone = 'bad';
            let badgeLabel = (a.status || 'unknown').toUpperCase();
            if (isPaused) { badgeTone = 'neutral'; badgeLabel = 'PAUSED'; }
            else if (isActive && isCapped) { badgeTone = 'neutral'; badgeLabel = 'CAPPED'; }
            else if (isActive) { badgeTone = 'good'; badgeLabel = 'LIVE'; }
            return (
              <div key={a.agent_id} data-testid={`cc-agent-${a.agent_id}`} style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'7px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                <div>
                  <div style={{fontSize:12.5,color:'#FFF',fontWeight:600}}>{a.emoji} {a.name}</div>
                  <div style={{fontSize:10.5,color:C.textD,marginTop:2}}>{a.sent_today}/{a.daily_cap} today · {a.current_task}</div>
                </div>
                <div style={{display:'flex',gap:5}}>
                  <Badge tone={badgeTone}>{badgeLabel}</Badge>
                </div>
              </div>
            );
          })}
        </Card>

        {/* Scheduler */}
        <Card title="Scheduler" icon={Clock} testid="cc-card-scheduler">
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10}}>
            <Badge tone={system?.scheduler?.running ? 'good' : 'bad'}>
              {system?.scheduler?.running ? 'Running' : 'Stopped'}
            </Badge>
            <span style={{fontSize:11,color:C.textD}}>{(system?.scheduler?.jobs || []).length} jobs</span>
          </div>
          <div style={{maxHeight:200,overflowY:'auto'}}>
            {(system?.scheduler?.jobs || []).map((j, i) => (
              <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',fontSize:11,borderBottom:'1px solid rgba(255,255,255,0.03)'}}>
                <span style={{color:C.text,fontFamily:"'JetBrains Mono',monospace"}}>{j.id}</span>
                <span style={{color:C.textD}}>{j.next_run ? j.next_run.slice(5,16).replace('T',' ') : '—'}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Cache + Redis health */}
        <Card title="Redis Cache" icon={Layers} testid="cc-card-cache">
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,fontSize:12}}>
            <Stat label="Hits"   value={cache?.hits ?? 0}   color={C.good}/>
            <Stat label="Misses" value={cache?.misses ?? 0} color={C.textD}/>
            <Stat label="Errors" value={cache?.errors ?? 0} color={cache?.errors > 0 ? C.bad : C.textD}/>
          </div>
          <div style={{marginTop:12,fontSize:11,color:C.textD}}>
            {cache?.total_lookups > 0 ? (
              <>Hit rate: <strong style={{color:cacheTone === 'good' ? C.good : cacheTone === 'warn' ? C.warn : C.textD}}>{cacheHitRate}%</strong> · {cache.sets} sets</>
            ) : 'No cache activity yet.'}
          </div>
          <div style={{marginTop:6,fontSize:10.5,color:C.textD}}>
            Fallback safe, if Redis down, every call routes direct to MongoDB.
          </div>
        </Card>

        {/* Pixel buffer */}
        <Card title="Pixel Event Buffer" icon={Radio} testid="cc-card-buffer">
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
            <Stat label="Buffered"      value={buffer?.buffered ?? 0}       color={C.text}/>
            <Stat label="Flushed"       value={pixelFlushed}                 color={C.good}/>
            <Stat label="Direct Writes" value={buffer?.direct_writes ?? 0}   color={C.warn}/>
            <Stat label="Flush Failures"value={buffer?.flush_failures ?? 0}  color={buffer?.flush_failures > 0 ? C.bad : C.textD}/>
          </div>
          <div style={{marginTop:12,fontSize:11,color:C.textD}}>
            Batch size: {buffer?.batch_size ?? 100} · Max: {buffer?.max_buffer ?? 1000}
            {efficiency > 0 && <> · Write saving: <strong style={{color:C.good}}>~{efficiency}%</strong></>}
          </div>
        </Card>

        {/* Integrations */}
        <Card title="Integration Secrets" icon={Database} testid="cc-card-integrations">
          {['required', 'optional'].map((bucket) => (
            <div key={bucket} style={{marginBottom:10}}>
              <div style={{fontSize:10,letterSpacing:'0.18em',color:C.textD,fontWeight:700,textTransform:'uppercase',marginBottom:4}}>{bucket}</div>
              <div style={{display:'flex',flexWrap:'wrap',gap:5}}>
                {(system?.integrations?.[bucket] || []).map((r, i) => (
                  <Badge key={i} tone={r.present ? 'good' : (bucket === 'required' ? 'bad' : 'neutral')}>
                    {r.name}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </Card>

        {/* Nightly jobs history — health check */}
        <Card title="Last Health Check" icon={Activity} testid="cc-card-health">
          {(() => {
            const h = system?.health_check || {};
            const tone = h.overall === 'PASS' ? 'good' : h.overall === 'FAIL' ? 'bad' : 'warn';
            return (
              <>
                <div style={{display:'flex',gap:10,alignItems:'center',marginBottom:10}}>
                  <Badge tone={tone}>{h.overall || 'not run'}</Badge>
                  {h.ran_at && <span style={{fontSize:11,color:C.textD}}>at {h.ran_at.slice(11,19)}Z</span>}
                </div>
                <div style={{maxHeight:160,overflowY:'auto'}}>
                  {(h.checklist || []).map((c, i) => (
                    <div key={i} style={{display:'flex',alignItems:'center',gap:8,padding:'4px 0',fontSize:11.5}}>
                      {c.ok ? <CheckCircle2 size={12} color={C.good}/> : <AlertTriangle size={12} color={C.bad}/>}
                      <span style={{color:c.ok ? C.text : C.bad}}>{c.step}</span>
                    </div>
                  ))}
                </div>
              </>
            );
          })()}
        </Card>

        {/* Anomaly detector — last fires + WA alert status */}
        <Card title="Anomaly Detector" icon={AlertTriangle} testid="cc-card-anomaly"
          action={<button data-testid="cc-anomaly-run" onClick={runAnomalyNow} disabled={anomalyRunning} style={{...btn, padding:'5px 10px', fontSize:10}}>
            {anomalyRunning ? <RefreshCw size={10} style={{animation:'spin 1s linear infinite'}}/> : <Zap size={10}/>} Run Now
          </button>}
        >
          {(() => {
            const recent = anomaly?.recent_alerts || [];
            const st = anomaly?.state || {};
            return (
              <>
                <div style={{display:'flex',gap:10,marginBottom:10,flexWrap:'wrap'}}>
                  <Badge tone={recent.length === 0 ? 'good' : 'warn'}>
                    {recent.length === 0 ? 'All Clear' : `${recent.length} alerts`}
                  </Badge>
                  {st.last_run_at && <span style={{fontSize:11,color:C.textD}}>ran {st.last_run_at.slice(11,19)}Z</span>}
                </div>
                {recent.length === 0 ? (
                  <p style={{fontSize:11.5,color:C.textD,lineHeight:1.6}}>
                    Watching for: cache hit-rate drop ≥ 20pp, pixel flush failures, system verdict degradation.
                    <br/>Alerts via WhatsApp · 60 min cooldown per anomaly type.
                  </p>
                ) : (
                  <div style={{maxHeight:160,overflowY:'auto'}}>
                    {recent.map((a, i) => (
                      <div key={i} data-testid={`cc-anomaly-row-${i}`} style={{padding:'6px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <span style={{fontSize:11.5,color:C.warn,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.08em'}}>{a.kind}</span>
                          <span style={{fontSize:10.5,color:C.textD}}>{(a.fired_at||'').slice(11,19)}Z</span>
                        </div>
                        <div style={{fontSize:10.5,color:C.text,marginTop:2}}>{JSON.stringify(a.detail || {})}</div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            );
          })()}
        </Card>
      </div>

      {/* AUREM Builder + Evolver row */}
      <div style={{marginTop:14,display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(360px,1fr))',gap:14}}>
        <Card title="AUREM Builder" icon={Cpu} testid="cc-card-builder">
          {(() => {
            const total = builder?.total ?? 0;
            const success = builder?.success ?? 0;
            const successTone = builder?.success_rate_pct >= 90 ? 'good'
              : builder?.success_rate_pct >= 70 ? 'warn'
              : total > 0 ? 'bad' : 'neutral';
            const last = builder?.last_build;
            const lastTone = !last ? 'neutral'
              : last.status === 'success' ? 'good'
              : last.status === 'queued' || last.status === 'running' ? 'gold'
              : 'bad';
            return (
              <>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,marginBottom:12}}>
                  <Stat label="Total"   value={total} color={C.text}/>
                  <Stat label="Success" value={success} color={C.good}/>
                  <Stat label="Cost Today" value={`$${(builder?.cost_today_usd ?? 0).toFixed(3)}`} color={C.accent}/>
                </div>
                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10,flexWrap:'wrap'}}>
                  <Badge tone={successTone}>{(builder?.success_rate_pct ?? 0)}% success rate</Badge>
                  {last && <Badge tone={lastTone}>{last.status}</Badge>}
                </div>
                {last ? (
                  <Link
                    to={`/admin/builder/${last.build_id}`}
                    data-testid="cc-last-build-link"
                    style={{display:'block',textDecoration:'none',padding:'8px 10px',margin:'-4px',borderRadius:8,transition:'background 0.18s ease',cursor:'pointer'}}
                    onMouseEnter={(e)=>{e.currentTarget.style.background='rgba(212,175,55,0.08)';}}
                    onMouseLeave={(e)=>{e.currentTarget.style.background='transparent';}}
                  >
                    <div style={{fontSize:11.5,color:C.text,lineHeight:1.6}}>
                      <div style={{color:C.textD,fontSize:10,letterSpacing:'0.14em',textTransform:'uppercase',marginBottom:4}}>Last build →</div>
                      <div style={{fontSize:12,color:C.text}}>{(last.description || '').slice(0, 140)}{(last.description || '').length > 140 ? '…' : ''}</div>
                      <div style={{fontSize:10.5,color:C.textD,marginTop:4}}>
                        {last.files?.length || 0} files · {last.duration_s || 0}s · {last.admin || '—'}
                        {last.started_at && ` · ${last.started_at.slice(11,19)}Z`}
                      </div>
                    </div>
                  </Link>
                ) : (
                  <p style={{fontSize:11.5,color:C.textD,lineHeight:1.6}}>
                    No builds yet. ORA: <code style={{color:C.accent}}>Build endpoint /api/builder-test returning build status</code>.
                  </p>
                )}
              </>
            );
          })()}
        </Card>

        <Card title="EvoMap Evolver" icon={GitBranch} testid="cc-card-evolver"
          action={<Link to="/admin/evolver" style={{...btn, padding:'5px 10px', fontSize:10, textDecoration:'none'}}>
            <GitBranch size={10}/> Genes
          </Link>}
        >
          {(() => {
            const configured = !!evolver?.configured;
            const reachable = !!evolver?.reachable;
            const tone = reachable ? 'good' : configured ? 'warn' : 'neutral';
            const label = reachable ? 'online'
              : configured ? 'unreachable' : 'offline (EVOLVER_URL unset)';
            return (
              <>
                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10,flexWrap:'wrap'}}>
                  <Badge tone={tone}>{label}</Badge>
                  {evolver?.strategy && <Badge tone="gold">{evolver.strategy}</Badge>}
                  {evolver?.review_mode && <Badge tone="neutral">review mode</Badge>}
                  {evolver?.allow_self_modify && <Badge tone="bad">self-modify ON</Badge>}
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,marginBottom:10}}>
                  <Stat label="Genes"    value={evolver?.genes_total ?? 0}    color={C.text}/>
                  <Stat label="Pending"  value={evolver?.genes_pending ?? 0}  color={evolver?.genes_pending > 0 ? C.warn : C.textD}/>
                  <Stat label="Approved" value={evolver?.genes_approved ?? 0} color={C.good}/>
                </div>
                {evolver?.last_run?.ts ? (
                  <div style={{fontSize:11,color:C.textD}}>
                    Last review <strong style={{color:C.text}}>{evolver.last_run.ts.slice(0,16).replace('T',' ')}Z</strong>
                    {' · '}
                    <span style={{color:evolver.last_run.kind === 'review_run_success' ? C.good : C.warn}}>
                      {evolver.last_run.kind === 'review_run_success' ? 'success' : 'offline'}
                    </span>
                  </div>
                ) : (
                  <div style={{fontSize:11,color:C.textD,lineHeight:1.6}}>
                    Nightly review at 2:45 AM. Set <code style={{color:C.accent}}>EVOLVER_URL</code> in backend/.env to wire Legion.
                  </div>
                )}
              </>
            );
          })()}
        </Card>

        <Card title="Legion Nodes" icon={Layers} testid="cc-card-legion"
          span={2}
          action={(() => {
            const verdict = legion?.verdict || 'offline';
            const tone = verdict === 'healthy' ? 'good'
              : verdict === 'degraded' ? 'warn' : 'neutral';
            return <Badge tone={tone}>{verdict}</Badge>;
          })()}
        >
          {legion ? (
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:10}}>
              {(legion.nodes || []).map((n) => {
                const tone = n.state === 'online' ? 'good'
                  : n.state === 'idle' ? 'gold'
                  : n.state === 'unreachable' || n.state === 'error' ? 'bad'
                  : 'neutral';
                const routeFor = {
                  evolver: '/admin/evolver',
                  openfang: '/admin/openfang',
                  sandbox: '/admin/control-center',
                  carbonyl: '/admin/control-center',
                  voice: '/admin/voice',
                  social: '/admin/social',
                  n8n: '/admin/control-center',
                };
                const to = routeFor[n.key] || '/admin/control-center';
                return (
                  <Link
                    key={n.key}
                    to={to}
                    data-testid={`cc-legion-node-${n.key}`}
                    style={{
                      textDecoration:'none',color:C.text,padding:'12px 14px',
                      border:`1px solid ${C.border}`,borderRadius:10,background:'#06060C',
                      display:'flex',flexDirection:'column',gap:6,transition:'background 0.18s',
                    }}
                    onMouseEnter={(e)=>{e.currentTarget.style.background='rgba(212,175,55,0.05)';}}
                    onMouseLeave={(e)=>{e.currentTarget.style.background='#06060C';}}
                  >
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8}}>
                      <strong style={{fontSize:12,fontFamily:"'Cinzel',serif",color:C.text}}>{n.name}</strong>
                      <Badge tone={tone}>{n.state}</Badge>
                    </div>
                    <div style={{fontSize:10,color:C.textD,letterSpacing:'0.12em',textTransform:'uppercase'}}>
                      ENV · <code style={{color:C.accent,fontSize:10}}>{n.url_env}</code>
                    </div>
                    {n.key === 'openfang' && typeof n.recent_imports_7d === 'number' && (
                      <div style={{fontSize:10.5,color:C.textD}}>
                        {n.recent_imports_7d} imports · last 7d
                      </div>
                    )}
                    {n.key === 'evolver' && n.detail?.genes_pending > 0 && (
                      <div style={{fontSize:10.5,color:C.warn}}>
                        {n.detail.genes_pending} gene(s) pending review
                      </div>
                    )}
                    {n.key === 'sandbox' && n.detail?.mode && (
                      <div style={{fontSize:10.5,color:C.textD}}>mode: {n.detail.mode}</div>
                    )}
                  </Link>
                );
              })}
            </div>
          ) : (
            <div style={{fontSize:11.5,color:C.textD}}>Loading Legion health…</div>
          )}
        </Card>
      </div>

      {/* Quick-link footer */}
      <div style={{marginTop:24,display:'flex',gap:10,flexWrap:'wrap'}}>
        <Link to="/admin/system-audit"  style={footerBtn}>System Audit</Link>
        <Link to="/admin/wiring-audit"  style={footerBtn}>Wiring Audit</Link>
        <Link to="/admin/boardroom"     style={footerBtn}>Boardroom · P&L</Link>
        <Link to="/dashboard"           style={footerBtn}>Full Dashboard</Link>
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div>
      <div style={{fontSize:9,letterSpacing:'0.18em',color:'#8A8070',fontWeight:700,textTransform:'uppercase'}}>{label}</div>
      <div style={{fontSize:20,fontWeight:800,color,fontFamily:"'Cinzel',serif",marginTop:3,lineHeight:1}}>{value}</div>
    </div>
  );
}

const btn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.25)',borderRadius:8,
  color:'#D4AF37',fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};
const footerBtn = {
  ...btn, textDecoration:'none',
};
