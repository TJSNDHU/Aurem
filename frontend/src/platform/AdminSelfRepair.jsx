/**
 * AdminSelfRepair — Iteration 216
 * ================================
 * /admin/self-repair
 *
 * One dashboard to watch every customer's Flame Score, its trend, and to
 * bridge any "unfixable" issues straight into the AUREM Builder.
 *
 * Backend endpoints used:
 *   GET  /api/self-repair/customers
 *   GET  /api/self-repair/customers/{tenant_id}/trend?days=30
 *   GET  /api/self-repair/unfixable
 *   POST /api/self-repair/unfixable/{fingerprint}/fix-with-builder
 *   POST /api/self-repair/unfixable/{fingerprint}/dismiss
 *   POST /api/self-repair/trigger
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Flame, RefreshCw, Play, AlertTriangle, Wrench, XCircle,
  TrendingUp, TrendingDown, Minus, ExternalLink,
} from 'lucide-react';
import {
  LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  bg: '#06060C', panel: '#0D0D17', border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

const TONE = {
  gold: { color: C.accent, bg: 'rgba(212,175,55,0.12)', border: 'rgba(212,175,55,0.4)' },
  good: { color: C.good,   bg: 'rgba(74,222,128,0.10)', border: 'rgba(74,222,128,0.35)' },
  warn: { color: C.warn,   bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.35)' },
  bad:  { color: C.bad,    bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.35)'  },
  neutral: { color: C.textD, bg: 'rgba(138,128,112,0.08)', border: 'rgba(138,128,112,0.2)' },
};

const btn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.25)',borderRadius:8,
  color:'#D4AF37',fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};

function Badge({ tone = 'neutral', children }) {
  const s = TONE[tone] || TONE.neutral;
  return (
    <span style={{
      display:'inline-flex',padding:'2px 9px',borderRadius:20,fontSize:9.5,fontWeight:700,
      letterSpacing:'0.14em',textTransform:'uppercase',background:s.bg,color:s.color,
      border:`1px solid ${s.border}`,
    }}>{children}</span>
  );
}

function Tile({ label, value, sub, color = C.text, testid }) {
  return (
    <div data-testid={testid} style={{
      background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'18px 20px',
    }}>
      <div style={{fontSize:10,letterSpacing:'0.2em',color:C.textD,fontWeight:700,textTransform:'uppercase',marginBottom:10}}>{label}</div>
      <div style={{fontSize:26,fontWeight:800,color,fontFamily:"'Cinzel',serif",lineHeight:1}}>{value}</div>
      {sub && <div style={{fontSize:11,color:C.textD,marginTop:6}}>{sub}</div>}
    </div>
  );
}

function DeltaIcon({ delta }) {
  if (delta == null) return <Minus size={12} style={{color:C.textD}}/>;
  if (delta > 0) return <TrendingUp size={12} style={{color:C.good}}/>;
  if (delta < 0) return <TrendingDown size={12} style={{color:C.bad}}/>;
  return <Minus size={12} style={{color:C.textD}}/>;
}

function FlameRing({ score, tone }) {
  const t = TONE[tone] || TONE.neutral;
  const pct = Math.max(0, Math.min(100, score));
  const R = 34;
  const CIRC = 2 * Math.PI * R;
  const dash = (pct / 100) * CIRC;
  return (
    <div style={{position:'relative',width:84,height:84,flexShrink:0}}>
      <svg width="84" height="84" viewBox="0 0 84 84">
        <circle cx="42" cy="42" r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6"/>
        <circle cx="42" cy="42" r={R} fill="none" stroke={t.color} strokeWidth="6"
          strokeDasharray={`${dash} ${CIRC - dash}`} strokeDashoffset={CIRC / 4}
          strokeLinecap="round" transform="rotate(-90 42 42)"
          style={{transition:'stroke-dasharray 600ms ease'}}/>
      </svg>
      <div style={{
        position:'absolute',inset:0,display:'flex',flexDirection:'column',
        alignItems:'center',justifyContent:'center',
      }}>
        <Flame size={14} style={{color:t.color,marginBottom:-2}}/>
        <div style={{fontSize:22,fontWeight:800,color:t.color,fontFamily:"'Cinzel',serif",lineHeight:1}}>{score}</div>
      </div>
    </div>
  );
}

function Sparkline({ data, color = C.accent }) {
  if (!data || data.length < 2) {
    return <div style={{fontSize:10,color:C.textD}}>not enough scans yet</div>;
  }
  const chartData = data.map((d, i) => ({ x: i, score: d.score }));
  return (
    <div style={{width:'100%',height:54}}>
      <ResponsiveContainer>
        <LineChart data={chartData} margin={{top:4,right:4,left:4,bottom:4}}>
          <Line type="monotone" dataKey="score" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false}/>
          <YAxis hide domain={[0, 100]}/>
          <XAxis hide/>
          <Tooltip
            contentStyle={{background:C.panel,border:`1px solid ${C.border}`,fontSize:11}}
            labelFormatter={() => ''}
            formatter={(v) => [`${v}/100`, 'score']}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function AdminSelfRepair() {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState([]);
  const [summary, setSummary] = useState({ count: 0, average_flame_score: 0, total_unfixable: 0 });
  const [unfixable, setUnfixable] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [busyFp, setBusyFp] = useState(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');

  const H = useMemo(() => ({ Authorization: `Bearer ${getPlatformToken() || ''}` }), []);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [cr, ur] = await Promise.all([
        fetch(`${API}/api/self-repair/customers`, { headers: H }),
        fetch(`${API}/api/self-repair/unfixable?limit=100`, { headers: H }),
      ]);
      if (!cr.ok) throw new Error(`customers HTTP ${cr.status}`);
      if (!ur.ok) throw new Error(`unfixable HTTP ${ur.status}`);
      const cd = await cr.json();
      const ud = await ur.json();
      setCustomers(cd.customers || []);
      setSummary({
        count: cd.count || 0,
        average_flame_score: cd.average_flame_score || 0,
        total_unfixable: cd.total_unfixable || 0,
      });
      setUnfixable(ud.items || []);
    } catch (e) {
      setError(String(e.message || e));
    }
    setLoading(false);
  }, [H]);

  useEffect(() => { load(); }, [load]);

  const triggerScan = async () => {
    setTriggering(true); setError('');
    try {
      const r = await fetch(`${API}/api/self-repair/trigger`, { method:'POST', headers: H });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e) {
      setError(`Scan trigger failed: ${e.message}`);
    }
    setTriggering(false);
  };

  const fixWithBuilder = async (fingerprint) => {
    setBusyFp(fingerprint); setError('');
    try {
      const r = await fetch(
        `${API}/api/self-repair/unfixable/${encodeURIComponent(fingerprint)}/fix-with-builder`,
        { method:'POST', headers: H },
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      await load();
      if (data?.build_id) navigate(`/admin/builder/${data.build_id}`);
    } catch (e) {
      setError(`Bridge to Builder failed: ${e.message}`);
    }
    setBusyFp(null);
  };

  const dismissIssue = async (fingerprint) => {
    setBusyFp(fingerprint); setError('');
    try {
      const r = await fetch(
        `${API}/api/self-repair/unfixable/${encodeURIComponent(fingerprint)}/dismiss`,
        { method:'POST', headers: H },
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e) {
      setError(`Dismiss failed: ${e.message}`);
    }
    setBusyFp(null);
  };

  const filtered = useMemo(() => {
    if (!filter) return customers;
    const f = filter.toLowerCase();
    return customers.filter(
      (c) => c.label?.toLowerCase().includes(f) || c.tenant_id?.toLowerCase().includes(f),
    );
  }, [customers, filter]);

  return (
    <div data-testid="admin-self-repair" style={{
      minHeight:'100vh',background:C.bg,color:C.text,
      fontFamily:"'Jost',sans-serif",padding:'28px 36px',
    }}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginBottom:24,flexWrap:'wrap',gap:16}}>
        <div>
          <Link to="/admin/control-center" style={{fontSize:11,color:C.textD,letterSpacing:'0.2em',textTransform:'uppercase',textDecoration:'none'}}>
            ← Control Center
          </Link>
          <h1 style={{fontFamily:"'Cinzel',serif",fontSize:32,fontWeight:700,color:'#FFF',letterSpacing:'0.04em',margin:'6px 0 4px'}}>
            <Flame size={24} style={{verticalAlign:-2,marginRight:8,color:C.accent}}/>Self-Repair Command
          </h1>
          <p style={{fontSize:12,color:C.textD,letterSpacing:'0.06em'}}>
            Flame Scores · Repair trends · Bridge unfixable issues straight to AUREM Builder
          </p>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
          <button data-testid="self-repair-trigger" onClick={triggerScan} disabled={triggering} style={btn}>
            {triggering
              ? <RefreshCw size={12} style={{animation:'spin 1s linear infinite'}}/>
              : <Play size={12}/>
            } Trigger Scan Cycle
          </button>
          <button data-testid="self-repair-refresh" onClick={load} disabled={loading} style={btn}>
            <RefreshCw size={12} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {/* Summary tiles */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:20}}>
        <Tile testid="tile-customers" label="Customers Monitored" value={summary.count} color={C.text}/>
        <Tile
          testid="tile-avg-flame"
          label="Avg Flame Score"
          value={`${summary.average_flame_score}/100`}
          color={
            summary.average_flame_score >= 75 ? C.good
            : summary.average_flame_score >= 60 ? C.warn : C.bad
          }
          sub={summary.average_flame_score >= 75 ? 'platform healthy' : 'needs attention'}
        />
        <Tile
          testid="tile-unfixable"
          label="Unfixable Queued"
          value={summary.total_unfixable}
          color={summary.total_unfixable > 0 ? C.warn : C.good}
          sub={summary.total_unfixable > 0 ? 'bridge to Builder' : 'queue clean'}
        />
        <Tile
          testid="tile-bridge"
          label="Builder Bridge"
          value="ACTIVE"
          color={C.accent}
          sub="fix-with-builder ready"
        />
      </div>

      {/* Error banner */}
      {error && (
        <div data-testid="self-repair-error" style={{
          marginBottom:16,padding:'10px 14px',background:'rgba(239,68,68,0.08)',
          border:`1px solid ${C.bad}40`,borderRadius:10,color:C.bad,fontSize:12,
          display:'flex',alignItems:'center',gap:8,
        }}>
          <AlertTriangle size={14}/> {error}
        </div>
      )}

      {/* Filter */}
      <div style={{marginBottom:14,display:'flex',gap:10,alignItems:'center',flexWrap:'wrap'}}>
        <input
          data-testid="self-repair-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter customers…"
          style={{
            flex:'0 0 260px',padding:'8px 12px',background:C.panel,
            border:`1px solid ${C.border}`,borderRadius:8,color:C.text,
            fontSize:12,fontFamily:"'Jost',sans-serif",outline:'none',
          }}
        />
        <span style={{fontSize:11,color:C.textD}}>
          {filtered.length} of {customers.length} shown
        </span>
      </div>

      {/* Customer cards */}
      <div data-testid="self-repair-customer-list" style={{
        display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(340px,1fr))',gap:14,marginBottom:32,
      }}>
        {loading ? (
          <div style={{padding:40,textAlign:'center',color:C.textD,fontSize:13}}>Loading customers…</div>
        ) : filtered.length === 0 ? (
          <div style={{
            padding:40,textAlign:'center',color:C.textD,fontSize:13,
            background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,gridColumn:'1/-1',
          }}>
            No customers match that filter.
          </div>
        ) : (
          filtered.map((c) => {
            const tone = TONE[c.flame_tone] || TONE.neutral;
            return (
              <div key={`${c.tenant_id}-${c.label}`}
                data-testid={`customer-card-${c.tenant_id}`}
                style={{
                  background:C.panel,border:`1px solid ${tone.border}`,
                  borderRadius:14,padding:'18px 20px',display:'flex',flexDirection:'column',gap:12,
                  opacity: c.inactive ? 0.65 : 1,
                }}>
                <div style={{display:'flex',gap:14,alignItems:'flex-start'}}>
                  <FlameRing score={c.flame_score || 0} tone={c.flame_tone}/>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap',marginBottom:4}}>
                      <span style={{fontSize:14,fontWeight:700,color:'#FFF',fontFamily:"'Cinzel',serif"}}>
                        {c.label}
                      </span>
                      {c.inactive && <Badge tone="neutral">inactive</Badge>}
                      {c.unfixable_queued > 0 && (
                        <Badge tone="warn">{c.unfixable_queued} unfixable</Badge>
                      )}
                    </div>
                    <div style={{fontSize:10.5,color:C.textD,marginBottom:6,wordBreak:'break-all'}}>
                      {c.site_url || c.tenant_id}
                    </div>
                    <div style={{display:'flex',alignItems:'center',gap:6,fontSize:10.5,color:C.textD}}>
                      <DeltaIcon delta={c.delta}/>
                      <span>
                        {c.delta == null ? 'no trend yet' :
                          c.delta === 0 ? 'flat vs prior' :
                          `${c.delta > 0 ? '+' : ''}${c.delta} vs prior`}
                      </span>
                      <span>·</span>
                      <span>{c.critical_count} crit · {c.warning_count} warn</span>
                    </div>
                  </div>
                </div>

                <Sparkline data={c.trend} color={tone.color}/>

                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8,flexWrap:'wrap'}}>
                  <span style={{fontSize:10,color:C.textD}}>
                    Last scan: {c.last_scanned_at ? c.last_scanned_at.slice(0,16).replace('T',' ') + 'Z' : '—'}
                  </span>
                  {c.site_url && (
                    <a href={c.site_url} target="_blank" rel="noreferrer"
                      data-testid={`customer-visit-${c.tenant_id}`}
                      style={{...btn, padding:'6px 10px',fontSize:10}}>
                      <ExternalLink size={11}/> Visit
                    </a>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Unfixable queue */}
      <div style={{marginBottom:10,display:'flex',justifyContent:'space-between',alignItems:'baseline',gap:10,flexWrap:'wrap'}}>
        <h2 style={{fontFamily:"'Cinzel',serif",fontSize:20,fontWeight:700,color:'#FFF',margin:0,letterSpacing:'0.04em'}}>
          Unfixable Queue
        </h2>
        <span style={{fontSize:11,color:C.textD,letterSpacing:'0.06em'}}>
          {unfixable.length} awaiting Builder · fire one up below
        </span>
      </div>

      <div data-testid="self-repair-unfixable-list" style={{display:'flex',flexDirection:'column',gap:10}}>
        {loading ? (
          <div style={{padding:30,textAlign:'center',color:C.textD,fontSize:13}}>Loading queue…</div>
        ) : unfixable.length === 0 ? (
          <div style={{
            padding:30,textAlign:'center',color:C.good,fontSize:13,
            background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,
          }}>
            ✓ All known issues are auto-fixable. Queue is clean.
          </div>
        ) : (
          unfixable.map((u) => (
            <div key={u.fingerprint}
              data-testid={`unfixable-${u.fingerprint}`}
              style={{
                background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'14px 18px',
                display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:16,flexWrap:'wrap',
              }}>
              <div style={{flex:1,minWidth:240}}>
                <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:4}}>
                  <Badge tone={u.severity === 'critical' ? 'bad' : 'warn'}>{u.severity || 'warning'}</Badge>
                  <Badge tone="neutral">{u.category || 'general'}</Badge>
                  {u.source === 'sentinel_auto' && (
                    <Badge tone="gold" data-testid={`sentinel-badge-${u.fingerprint}`}>SENTINEL</Badge>
                  )}
                  <span style={{fontSize:12,color:'#FFF',fontWeight:600}}>{u.label}</span>
                  <span style={{fontSize:10,color:C.textD}}>· {u.occurrences || 1}× seen</span>
                </div>
                <div style={{fontSize:13,color:C.text,marginBottom:4,lineHeight:1.4}}>
                  {u.issue}
                </div>
                {u.details && (
                  <div style={{fontSize:11,color:C.textD,marginBottom:4,lineHeight:1.4}}>
                    {String(u.details).slice(0,240)}
                  </div>
                )}
                {u.aurem_solution && (
                  <div style={{fontSize:11,color:C.good,marginTop:4,lineHeight:1.4}}>
                    Suggested: {String(u.aurem_solution).slice(0,240)}
                  </div>
                )}
              </div>
              <div style={{display:'flex',flexDirection:'column',gap:6,minWidth:160}}>
                <button
                  data-testid={`unfixable-fix-${u.fingerprint}`}
                  onClick={() => fixWithBuilder(u.fingerprint)}
                  disabled={busyFp === u.fingerprint}
                  style={{...btn, color:C.accent, borderColor:`${C.accent}55`}}
                >
                  <Wrench size={12}/> {busyFp === u.fingerprint ? 'Bridging…' : 'Fix with Builder'}
                </button>
                <button
                  data-testid={`unfixable-dismiss-${u.fingerprint}`}
                  onClick={() => dismissIssue(u.fingerprint)}
                  disabled={busyFp === u.fingerprint}
                  style={{...btn, color:C.bad, borderColor:`${C.bad}55`}}
                >
                  <XCircle size={12}/> Dismiss
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
