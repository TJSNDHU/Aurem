/**
 * AdminBuilderDetail — Iteration 213
 * ==================================
 * /admin/builder/:buildId
 *
 * Drill-down from the Live Activity Marquee, the AUREM Builder card,
 * and ORA BUILD intent history. Shows every file Claude wrote, security
 * scan verdict, syntax/import errors, self-repair attempts, raw notes, and
 * the test command the admin can run.
 */
import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Cpu, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Clock,
  FileCode, Terminal, ExternalLink,
} from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  bg: '#06060C', panel: '#0D0D17', border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

const statusTone = (s) =>
  s === 'success' ? 'good' : s === 'failed' ? 'bad'
    : s === 'queued' || s === 'running' ? 'gold' : 'neutral';

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
  cursor:'pointer',fontFamily:"'Jost',sans-serif",textDecoration:'none',
};

export default function AdminBuilderDetail() {
  const { buildId } = useParams();
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const H = useMemo(() => ({ Authorization: `Bearer ${getPlatformToken() || ''}` }), []);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const r = await fetch(`${API}/api/admin/builder/status/${buildId}`, { headers: H });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setDoc(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    }
    setLoading(false);
  }, [H, buildId]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh while queued/running
  useEffect(() => {
    if (!doc || (doc.status !== 'queued' && doc.status !== 'running')) return undefined;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [doc, load]);

  return (
    <div data-testid="admin-builder-detail" style={{
      minHeight:'100vh',background:C.bg,color:C.text,
      fontFamily:"'Jost',sans-serif",padding:'28px 36px',
    }}>
      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginBottom:24,flexWrap:'wrap',gap:16}}>
        <div>
          <Link to="/admin/control-center" style={{fontSize:11,color:C.textD,letterSpacing:'0.2em',textTransform:'uppercase',textDecoration:'none'}}>
            ← Control Center
          </Link>
          <h1 style={{fontFamily:"'Cinzel',serif",fontSize:30,fontWeight:700,color:'#FFF',letterSpacing:'0.04em',margin:'6px 0 4px'}}>
            <Cpu size={22} style={{verticalAlign:-2,marginRight:8,color:C.accent}}/>Build Detail
          </h1>
          <code style={{fontSize:12,color:C.accent,fontFamily:"'JetBrains Mono',monospace"}}>{buildId}</code>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
          {doc && <Badge tone={statusTone(doc.status)}>{doc.status}</Badge>}
          <button data-testid="builder-refresh" onClick={load} disabled={loading} style={btn}>
            <RefreshCw size={12} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div style={{marginBottom:16,padding:'10px 14px',background:'rgba(239,68,68,0.08)',
          border:`1px solid ${C.bad}40`,borderRadius:10,color:C.bad,fontSize:12,
          display:'flex',alignItems:'center',gap:8}}>
          <AlertTriangle size={14}/> {error}
        </div>
      )}

      {!doc ? (
        <div style={{padding:40,textAlign:'center',color:C.textD,fontSize:13}}>
          {loading ? 'Loading…' : 'Build not found'}
        </div>
      ) : (
        <>
          {/* Meta tiles */}
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:20}}>
            <Tile label="Files Written" value={doc.files?.length || 0} color={C.text}/>
            <Tile
              label="Successful Files"
              value={(doc.files || []).filter(f => f.ok).length}
              color={C.good}
            />
            <Tile label="Duration" value={`${doc.duration_s || 0}s`} color={C.accent}/>
            <Tile label="Cost" value={`$${(doc.cost_estimate_usd || 0).toFixed(4)}`} color={C.accent}/>
          </div>

          {/* Request panel */}
          <Section title="REQUEST">
            <Row label="Admin" value={doc.admin || '—'}/>
            <Row label="Model" value={doc.model || '—'}/>
            <Row label="Started" value={doc.started_at ? doc.started_at.replace('T',' ').slice(0,19) + 'Z' : '—'}/>
            {doc.finished_at && <Row label="Finished" value={doc.finished_at.replace('T',' ').slice(0,19) + 'Z'}/>}
            <div style={{marginTop:10}}>
              <div style={{fontSize:10,color:C.textD,letterSpacing:'0.14em',textTransform:'uppercase',marginBottom:6}}>Description</div>
              <div style={{fontSize:13,color:C.text,background:'rgba(0,0,0,0.3)',padding:'10px 14px',borderRadius:8,fontFamily:"'JetBrains Mono',monospace",whiteSpace:'pre-wrap',lineHeight:1.5}}>
                {doc.description}
              </div>
            </div>
          </Section>

          {/* Files */}
          <Section title={`FILES (${doc.files?.length || 0})`} icon={FileCode}>
            {!doc.files || doc.files.length === 0 ? (
              <p style={{color:C.textD,fontSize:12,margin:0}}>No files emitted.</p>
            ) : (
              <div style={{display:'flex',flexDirection:'column',gap:10}}>
                {doc.files.map((f, idx) => {
                  const tone = f.ok ? 'good'
                    : f.security_issues?.length ? 'bad'
                    : f.syntax_error ? 'warn'
                    : f.import_error ? 'warn'
                    : 'neutral';
                  return (
                    <div key={idx} data-testid={`builder-file-${idx}`} style={{
                      padding:'12px 14px',background:'rgba(0,0,0,0.3)',borderRadius:8,
                      border:`1px solid ${C.border}`,
                    }}>
                      <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:6}}>
                        <Badge tone={tone}>{f.ok ? 'OK' : 'FAIL'}</Badge>
                        <code style={{fontSize:12,color:C.text,fontFamily:"'JetBrains Mono',monospace",wordBreak:'break-all'}}>{f.path}</code>
                        {f.written && <Badge tone="neutral">written</Badge>}
                        {f.repair_attempts > 0 && <Badge tone="gold">{f.repair_attempts} repair{f.repair_attempts > 1 ? 's' : ''}</Badge>}
                      </div>
                      {f.security_issues?.length > 0 && (
                        <div style={{fontSize:11,color:C.bad,marginTop:4}}>
                          🛡 security: {f.security_issues.join(', ')}
                        </div>
                      )}
                      {f.syntax_error && (
                        <div style={{fontSize:11,color:C.warn,marginTop:4,fontFamily:"'JetBrains Mono',monospace"}}>
                          ⚠ syntax: {String(f.syntax_error).slice(0, 300)}
                        </div>
                      )}
                      {f.import_error && (
                        <div style={{fontSize:11,color:C.warn,marginTop:4,fontFamily:"'JetBrains Mono',monospace"}}>
                          ↪ import: {String(f.import_error).slice(0, 300)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Section>

          {/* Test command */}
          {doc.test_command && (
            <Section title="TEST COMMAND" icon={Terminal}>
              <code style={{
                display:'block',padding:'12px 14px',background:'#000',borderRadius:8,
                fontFamily:"'JetBrains Mono',monospace",fontSize:12,color:C.good,
                border:`1px solid ${C.border}`,whiteSpace:'pre-wrap',wordBreak:'break-all',
              }}>
                {doc.test_command}
              </code>
            </Section>
          )}

          {/* Notes */}
          {doc.notes && doc.notes.length > 0 && (
            <Section title="MANUAL NOTES" icon={AlertTriangle}>
              <ul style={{margin:0,paddingLeft:20,lineHeight:1.7,fontSize:12,color:C.text}}>
                {doc.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </Section>
          )}

          {/* Error box (if any) */}
          {doc.error && (
            <Section title="ERROR">
              <div style={{
                padding:'12px 14px',background:'rgba(239,68,68,0.06)',
                border:`1px solid ${C.bad}40`,borderRadius:8,color:C.bad,fontSize:12,
                fontFamily:"'JetBrains Mono',monospace",whiteSpace:'pre-wrap',
              }}>
                {doc.error}
              </div>
            </Section>
          )}

          {/* Link to evolver if anything was genes-linked */}
          <div style={{display:'flex',gap:10,marginTop:24}}>
            <Link to="/admin/evolver" style={btn}>
              <ExternalLink size={12}/> Evolver Genes
            </Link>
            <Link to="/admin/control-center" style={btn}>
              <Clock size={12}/> Recent Builds
            </Link>
          </div>
        </>
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function Tile({ label, value, color }) {
  return (
    <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 18px'}}>
      <div style={{fontSize:10,letterSpacing:'0.2em',color:C.textD,fontWeight:700,textTransform:'uppercase',marginBottom:8}}>{label}</div>
      <div style={{fontSize:22,fontWeight:800,color,fontFamily:"'Cinzel',serif",lineHeight:1}}>{value}</div>
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div style={{
      background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'18px 22px',marginBottom:16,
    }}>
      <div style={{fontSize:11,letterSpacing:'0.22em',color:C.accent,fontWeight:700,textTransform:'uppercase',marginBottom:14,display:'flex',alignItems:'center',gap:8}}>
        {Icon && <Icon size={13}/>}{title}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{display:'flex',gap:12,fontSize:12,marginBottom:6}}>
      <span style={{color:C.textD,minWidth:90,letterSpacing:'0.1em',textTransform:'uppercase',fontSize:10}}>{label}</span>
      <span style={{color:C.text,fontFamily:"'JetBrains Mono',monospace"}}>{value}</span>
    </div>
  );
}
