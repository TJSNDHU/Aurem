/**
 * AdminEvolver — Iteration 212
 * ============================
 * /admin/evolver
 *
 * Visual approve/reject UI for EvoMap Evolver genes.
 * Backend: /api/admin/evolver/status, /genes, /genes/{id}/approve|reject, /run-review
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { GitBranch, CheckCircle2, XCircle, RefreshCw, Play, AlertTriangle } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  bg: '#06060C', panel: '#0D0D17', border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

const STATUS_TABS = [
  { key: 'pending_review', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
  { key: '', label: 'All' },
];

function Badge({ tone = 'neutral', children }) {
  const map = {
    good: { bg: 'rgba(74,222,128,0.1)', color: C.good, border: 'rgba(74,222,128,0.35)' },
    warn: { bg: 'rgba(245,158,11,0.1)', color: C.warn, border: 'rgba(245,158,11,0.35)' },
    bad:  { bg: 'rgba(239,68,68,0.1)',  color: C.bad,  border: 'rgba(239,68,68,0.35)' },
    gold: { bg: 'rgba(212,175,55,0.1)', color: C.accent,border: 'rgba(212,175,55,0.35)' },
    neutral: { bg: 'rgba(138,128,112,0.08)', color: C.textD, border: 'rgba(138,128,112,0.2)' },
  };
  const s = map[tone] || map.neutral;
  return (
    <span style={{
      display:'inline-flex',padding:'2px 9px',borderRadius:20,fontSize:9.5,fontWeight:700,
      letterSpacing:'0.14em',textTransform:'uppercase',background:s.bg,color:s.color,
      border:`1px solid ${s.border}`,
    }}>{children}</span>
  );
}

const btn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.25)',borderRadius:8,
  color:'#D4AF37',fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};

export default function AdminEvolver() {
  const [status, setStatus] = useState(null);
  const [genes, setGenes] = useState([]);
  const [tab, setTab] = useState('pending_review');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [reviewRunning, setReviewRunning] = useState(false);
  const [error, setError] = useState('');
  const cardRefs = useRef({});

  const H = useMemo(() => ({ Authorization: `Bearer ${getPlatformToken() || ''}` }), []);

  const loadAll = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [st, gn] = await Promise.all([
        fetch(`${API}/api/admin/evolver/status`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/evolver/genes${tab ? `?status=${tab}` : ''}&limit=100`, { headers: H })
          .then((r) => r.ok ? r.json() : { items: [] }),
      ]);
      setStatus(st);
      setGenes(gn?.items || []);
    } catch (e) {
      setError(String(e));
    }
    setLoading(false);
  }, [H, tab]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const setGeneStatus = async (geneId, action) => {
    setBusyId(geneId);
    try {
      const r = await fetch(`${API}/api/admin/evolver/genes/${geneId}/${action}`, {
        method: 'POST', headers: H,
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await loadAll();
    } catch (e) {
      setError(`Failed to ${action}: ${e.message}`);
    }
    setBusyId(null);
  };

  const runReview = async () => {
    setReviewRunning(true); setError('');
    try {
      const r = await fetch(`${API}/api/admin/evolver/run-review`, { method: 'POST', headers: H });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await loadAll();
    } catch (e) {
      setError(`Run review failed: ${e.message}`);
    }
    setReviewRunning(false);
  };

  const toneForStatus = status?.reachable ? 'good'
    : status?.configured ? 'warn' : 'neutral';
  const statusLabel = status?.reachable ? 'online'
    : status?.configured ? 'unreachable' : 'offline (EVOLVER_URL unset)';

  return (
    <div data-testid="admin-evolver" style={{
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
            <GitBranch size={24} style={{verticalAlign:-2,marginRight:8,color:C.accent}}/>EvoMap Evolver
          </h1>
          <p style={{fontSize:12,color:C.textD,letterSpacing:'0.06em'}}>
            Gene approval gate · AUREM never auto-applies without your sign-off
          </p>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
          <Badge tone={toneForStatus}>{statusLabel}</Badge>
          {status?.strategy && <Badge tone="gold">{status.strategy}</Badge>}
          {status?.review_mode && <Badge tone="neutral">review mode</Badge>}
          {status?.allow_self_modify && <Badge tone="bad">self-modify ON</Badge>}
          <button data-testid="evolver-run-review" onClick={runReview} disabled={reviewRunning} style={btn}>
            {reviewRunning ? <RefreshCw size={12} style={{animation:'spin 1s linear infinite'}}/> : <Play size={12}/>} Run Review
          </button>
          <button data-testid="evolver-refresh" onClick={loadAll} disabled={loading} style={btn}>
            <RefreshCw size={12} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {/* Summary tiles */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:20}}>
        <Tile label="Genes Total"    value={status?.genes_total ?? 0}    color={C.text}/>
        <Tile label="Pending Review" value={status?.genes_pending ?? 0}  color={status?.genes_pending > 0 ? C.warn : C.textD}/>
        <Tile label="Approved"       value={status?.genes_approved ?? 0} color={C.good}/>
        <Tile
          label="Last Review"
          value={status?.last_run?.ts ? status.last_run.ts.slice(11,19) + 'Z' : '—'}
          color={C.accent}
          sub={status?.last_run?.ts ? status.last_run.ts.slice(0,10) : 'no runs yet'}
        />
      </div>

      {/* Error banner */}
      {error && (
        <div data-testid="evolver-error" style={{
          marginBottom:16,padding:'10px 14px',background:'rgba(239,68,68,0.08)',
          border:`1px solid ${C.bad}40`,borderRadius:10,color:C.bad,fontSize:12,
          display:'flex',alignItems:'center',gap:8,
        }}>
          <AlertTriangle size={14}/> {error}
        </div>
      )}

      {/* Tabs */}
      <div style={{display:'flex',gap:8,marginBottom:16,flexWrap:'wrap'}}>
        {STATUS_TABS.map((t) => {
          const active = tab === t.key;
          return (
            <button
              key={t.key || 'all'}
              data-testid={`evolver-tab-${t.key || 'all'}`}
              onClick={() => setTab(t.key)}
              style={{...btn,
                background: active ? 'rgba(212,175,55,0.12)' : 'transparent',
                borderColor: active ? C.accent : 'rgba(212,175,55,0.25)',
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Gene list */}
      <div data-testid="evolver-gene-list" style={{display:'flex',flexDirection:'column',gap:12}}>
        {loading ? (
          <div style={{padding:40,textAlign:'center',color:C.textD,fontSize:13}}>Loading genes…</div>
        ) : genes.length === 0 ? (
          <div style={{
            padding:40,textAlign:'center',color:C.textD,fontSize:13,
            background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,
          }}>
            No genes in this bucket. {!status?.configured && <><br/>Set <code style={{color:C.accent}}>EVOLVER_URL</code> in backend/.env to wire Legion Evolver.</>}
          </div>
        ) : (
          genes.map((g) => (
            <div key={g.gene_id} data-testid={`evolver-gene-${g.gene_id}`}
              ref={(el) => { if (el) cardRefs.current[g.gene_id] = el; }}
              style={{
                background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 20px',
              }}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:16,flexWrap:'wrap',marginBottom:10}}>
                <div style={{flex:1,minWidth:240}}>
                  <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4,flexWrap:'wrap'}}>
                    <code style={{fontSize:11,color:C.accent,fontFamily:"'JetBrains Mono',monospace"}}>{g.gene_id}</code>
                    <Badge tone={g.status === 'approved' ? 'good' : g.status === 'rejected' ? 'bad' : g.status === 'retired' ? 'neutral' : 'warn'}>
                      {g.status}
                    </Badge>
                    {g.source && <Badge tone="neutral">{g.source}</Badge>}
                    {typeof g.confidence === 'number' && (
                      <Badge tone={g.confidence >= 0.8 ? 'good' : g.confidence >= 0.5 ? 'warn' : 'bad'}>
                        {Math.round(g.confidence * 100)}% confidence
                      </Badge>
                    )}
                  </div>
                  {g.pattern && (
                    <div style={{fontSize:13,color:C.text,marginBottom:6}}>
                      <strong style={{color:C.textD,fontSize:10,letterSpacing:'0.14em',textTransform:'uppercase',marginRight:6}}>Pattern</strong>
                      {String(g.pattern).slice(0,280)}
                    </div>
                  )}
                  {g.diagnosis && (
                    <div style={{fontSize:12,color:C.textD,marginBottom:4}}>
                      <strong style={{color:C.textD,fontSize:10,letterSpacing:'0.14em',textTransform:'uppercase',marginRight:6}}>Diagnosis</strong>
                      {String(g.diagnosis).slice(0,300)}
                    </div>
                  )}
                  {g.remediation && (
                    <div style={{fontSize:12,color:C.good,marginTop:6,lineHeight:1.5}}>
                      <strong style={{color:C.textD,fontSize:10,letterSpacing:'0.14em',textTransform:'uppercase',marginRight:6}}>Remediation</strong>
                      {String(g.remediation).slice(0,400)}
                    </div>
                  )}
                  {g.created_at && (
                    <div style={{fontSize:10.5,color:C.textD,marginTop:8}}>
                      Created {g.created_at.slice(0,16).replace('T',' ')}Z
                      {g.updated_by && <> · updated by {g.updated_by}</>}
                    </div>
                  )}
                </div>
                <div style={{display:'flex',flexDirection:'column',gap:6,minWidth:140}}>
                  <button
                    data-testid={`evolver-approve-${g.gene_id}`}
                    onClick={() => setGeneStatus(g.gene_id, 'approve')}
                    disabled={busyId === g.gene_id || g.status === 'approved'}
                    style={{...btn, color:C.good, borderColor:`${C.good}55`}}
                  >
                    <CheckCircle2 size={12}/> Approve
                  </button>
                  <button
                    data-testid={`evolver-reject-${g.gene_id}`}
                    onClick={() => setGeneStatus(g.gene_id, 'reject')}
                    disabled={busyId === g.gene_id || g.status === 'rejected'}
                    style={{...btn, color:C.bad, borderColor:`${C.bad}55`}}
                  >
                    <XCircle size={12}/> Reject
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function Tile({ label, value, sub, color }) {
  return (
    <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'18px 20px'}}>
      <div style={{fontSize:10,letterSpacing:'0.2em',color:C.textD,fontWeight:700,textTransform:'uppercase',marginBottom:10}}>{label}</div>
      <div style={{fontSize:26,fontWeight:800,color,fontFamily:"'Cinzel',serif",lineHeight:1}}>{value}</div>
      {sub && <div style={{fontSize:11,color:C.textD,marginTop:6}}>{sub}</div>}
    </div>
  );
}
