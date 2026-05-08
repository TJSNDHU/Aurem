/**
 * AdminOpenFang — Iteration 215
 * ==============================
 * /admin/openfang
 *
 * Admin page for the OpenFang Lead Hand integration.
 *  - HMAC-signed webhook status (mode, replay window, plain-token fallback)
 *  - Recent imports (audit log) with auth mode badge
 *  - Recent leads imported via OpenFang (click → customer page)
 *  - HMAC signature generator (probe Legion node without leaking the secret)
 *
 * Data sources:
 *   GET  /api/openfang/status
 *   GET  /api/openfang/leads/recent?limit=25
 *   POST /api/openfang/verify-signature
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Webhook, RefreshCw, ShieldCheck, AlertTriangle, Copy, Check } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  bg: '#06060C', panel: '#0D0D17', border: 'rgba(212,175,55,0.12)',
  accent: '#D4AF37', good: '#4ADE80', warn: '#F59E0B', bad: '#EF4444',
  text: '#E8E0D0', textD: '#8A8070',
};

const btn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:'1px solid rgba(212,175,55,0.25)',borderRadius:8,
  color:C.accent,fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};

function Badge({ tone = 'neutral', children, testid }) {
  const map = {
    good: { bg: 'rgba(74,222,128,0.1)', color: C.good, border: 'rgba(74,222,128,0.35)' },
    warn: { bg: 'rgba(245,158,11,0.1)', color: C.warn, border: 'rgba(245,158,11,0.35)' },
    bad:  { bg: 'rgba(239,68,68,0.1)',  color: C.bad,  border: 'rgba(239,68,68,0.35)' },
    gold: { bg: 'rgba(212,175,55,0.1)', color: C.accent,border: 'rgba(212,175,55,0.35)' },
    neutral: { bg: 'rgba(138,128,112,0.08)', color: C.textD, border: 'rgba(138,128,112,0.2)' },
  };
  const s = map[tone] || map.neutral;
  return (
    <span data-testid={testid} style={{
      display:'inline-flex',padding:'2px 9px',borderRadius:20,fontSize:9.5,fontWeight:700,
      letterSpacing:'0.14em',textTransform:'uppercase',background:s.bg,color:s.color,
      border:`1px solid ${s.border}`,
    }}>{children}</span>
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

export default function AdminOpenFang() {
  const [status, setStatus] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [probeTs, setProbeTs] = useState(() => String(Math.floor(Date.now() / 1000)));
  const [probeBody, setProbeBody] = useState('{"business_name":"Acme Co","email":"test@acme.com"}');
  const [probeResult, setProbeResult] = useState(null);
  const [probing, setProbing] = useState(false);
  const [copied, setCopied] = useState('');

  const H = useMemo(() => ({ Authorization: `Bearer ${getPlatformToken() || ''}` }), []);

  const loadAll = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [st, ld] = await Promise.all([
        fetch(`${API}/api/openfang/status`, { headers: H }).then((r) => r.ok ? r.json() : null),
        fetch(`${API}/api/openfang/leads/recent?limit=25`, { headers: H }).then((r) => r.ok ? r.json() : { items: [] }),
      ]);
      setStatus(st);
      setLeads(ld?.items || []);
    } catch (e) {
      setError(String(e));
    }
    setLoading(false);
  }, [H]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const runProbe = async () => {
    setProbing(true); setError(''); setProbeResult(null);
    try {
      const r = await fetch(`${API}/api/openfang/verify-signature`, {
        method: 'POST',
        headers: { ...H, 'Content-Type': 'application/json' },
        body: JSON.stringify({ timestamp: probeTs, body: probeBody }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setProbeResult(await r.json());
    } catch (e) {
      setError(`Probe failed: ${e.message}`);
    }
    setProbing(false);
  };

  const copy = (key, val) => {
    try {
      navigator.clipboard.writeText(val);
      setCopied(key);
      setTimeout(() => setCopied(''), 1200);
    } catch { /* noop */ }
  };

  const configured = !!status?.configured;
  const hmacEnabled = !!status?.auth?.hmac_enabled;
  const plainAllowed = !!status?.auth?.plain_token_allowed;
  const statusTone = !configured ? 'neutral' : plainAllowed ? 'warn' : 'good';
  const statusLabel = !configured ? 'offline (secret unset)'
    : plainAllowed ? 'hmac + plain fallback' : 'hmac only';
  const total = status?.total_leads_from_openfang ?? 0;
  const modeCounts = status?.auth_mode_counts_last_100 || {};
  const imports = status?.last_imports || [];

  return (
    <div data-testid="admin-openfang" style={{
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
            <Webhook size={24} style={{verticalAlign:-2,marginRight:8,color:C.accent}}/>OpenFang Lead Hand
          </h1>
          <p style={{fontSize:12,color:C.textD,letterSpacing:'0.06em'}}>
            Inbound webhook · HMAC-SHA256 signed · replay-protected
          </p>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
          <Badge tone={statusTone} testid="openfang-status-badge">{statusLabel}</Badge>
          {status?.auth?.replay_window_s && (
            <Badge tone="neutral">± {status.auth.replay_window_s}s window</Badge>
          )}
          <button data-testid="openfang-refresh" onClick={loadAll} disabled={loading} style={btn}>
            <RefreshCw size={12} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
          </button>
        </div>
      </div>

      {/* Summary tiles */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:20}}>
        <Tile label="Total Leads"     value={total}                        color={C.text}/>
        <Tile label="HMAC Imports"    value={modeCounts.hmac || 0}         color={C.good} sub="last 100 imports"/>
        <Tile label="Plain Imports"   value={modeCounts.plain || 0}        color={plainAllowed ? C.warn : C.textD} sub="legacy fallback"/>
        <Tile label="Default Tenant"  value={status?.default_tenant || '—'} color={C.accent}/>
      </div>

      {error && (
        <div data-testid="openfang-error" style={{
          marginBottom:16,padding:'10px 14px',background:'rgba(239,68,68,0.08)',
          border:`1px solid ${C.bad}40`,borderRadius:10,color:C.bad,fontSize:12,
          display:'flex',alignItems:'center',gap:8,
        }}>
          <AlertTriangle size={14}/> {error}
        </div>
      )}

      {/* Recent Imports (audit log) */}
      <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 20px',marginBottom:16}}>
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.accent,letterSpacing:'0.18em',textTransform:'uppercase',margin:'0 0 12px'}}>
          Recent Webhook Batches
        </h3>
        {imports.length === 0 ? (
          <div style={{fontSize:12,color:C.textD}}>No imports yet.</div>
        ) : (
          <table data-testid="openfang-imports-table" style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
            <thead>
              <tr style={{color:C.textD,fontSize:10,letterSpacing:'0.14em',textTransform:'uppercase'}}>
                <th style={{textAlign:'left',padding:'8px 4px'}}>Timestamp</th>
                <th style={{textAlign:'left',padding:'8px 4px'}}>Run ID</th>
                <th style={{textAlign:'right',padding:'8px 4px'}}>Inserted</th>
                <th style={{textAlign:'right',padding:'8px 4px'}}>Dup</th>
                <th style={{textAlign:'right',padding:'8px 4px'}}>Failed</th>
                <th style={{textAlign:'left',padding:'8px 4px'}}>Auth Mode</th>
              </tr>
            </thead>
            <tbody>
              {imports.map((im, i) => (
                <tr key={i} data-testid={`openfang-import-row-${i}`} style={{borderTop:`1px solid ${C.border}`}}>
                  <td style={{padding:'8px 4px',color:C.text}}>{(im.ts || '').slice(0,19).replace('T',' ')}Z</td>
                  <td style={{padding:'8px 4px',color:C.accent,fontFamily:"'JetBrains Mono',monospace",fontSize:11}}>{im.run_id}</td>
                  <td style={{padding:'8px 4px',textAlign:'right',color:C.good,fontWeight:700}}>{im.inserted || 0}</td>
                  <td style={{padding:'8px 4px',textAlign:'right',color:C.warn}}>{im.duplicates || 0}</td>
                  <td style={{padding:'8px 4px',textAlign:'right',color:C.bad}}>{im.failed || 0}</td>
                  <td style={{padding:'8px 4px'}}>
                    <Badge tone={im.auth_mode === 'hmac' ? 'good' : im.auth_mode === 'plain' ? 'warn' : 'neutral'}>
                      {im.auth_mode || 'legacy'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Leads */}
      <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 20px',marginBottom:16}}>
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.accent,letterSpacing:'0.18em',textTransform:'uppercase',margin:'0 0 12px'}}>
          Recent Leads ({leads.length})
        </h3>
        {leads.length === 0 ? (
          <div style={{fontSize:12,color:C.textD}}>No OpenFang leads imported yet.</div>
        ) : (
          <div data-testid="openfang-leads-table" style={{display:'grid',gridTemplateColumns:'1fr',gap:8}}>
            {leads.map((l) => (
              <Link
                key={l.lead_id}
                to={`/admin/customer/${encodeURIComponent(l.email || l.business_name || l.lead_id)}`}
                data-testid={`openfang-lead-${l.lead_id}`}
                style={{
                  textDecoration:'none',color:C.text,padding:'10px 14px',
                  border:`1px solid ${C.border}`,borderRadius:10,
                  display:'grid',gridTemplateColumns:'1.5fr 1.5fr 1fr 1fr auto',gap:12,alignItems:'center',
                  fontSize:12,
                }}
              >
                <strong style={{color:C.text}}>{l.business_name || '—'}</strong>
                <span style={{color:C.textD}}>{l.email || l.phone || '—'}</span>
                <span style={{color:C.textD}}>{l.industry || '—'}</span>
                <span style={{color:C.textD,fontSize:10.5}}>
                  {l.city ? `${l.city}${l.region ? ', ' + l.region : ''}` : '—'}
                </span>
                <Badge tone={l.status === 'new' ? 'gold' : 'neutral'}>{l.status || 'new'}</Badge>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* HMAC Signature Probe */}
      <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 20px',marginBottom:16}}>
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.accent,letterSpacing:'0.18em',textTransform:'uppercase',margin:'0 0 6px',display:'flex',alignItems:'center',gap:8}}>
          <ShieldCheck size={14}/> Signature Probe
        </h3>
        <div style={{fontSize:11,color:C.textD,marginBottom:12}}>
          Legion node ke liye exact HMAC header compute karta hai — secret leak kiye bina. Use this to debug the Legion webhook pipe.
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 2fr',gap:10,marginBottom:10}}>
          <input
            data-testid="openfang-probe-ts"
            value={probeTs}
            onChange={(e) => setProbeTs(e.target.value)}
            placeholder="unix timestamp"
            style={{background:'#000',border:`1px solid ${C.border}`,borderRadius:8,padding:'8px 10px',color:C.text,fontFamily:"'JetBrains Mono',monospace",fontSize:12}}
          />
          <input
            data-testid="openfang-probe-body"
            value={probeBody}
            onChange={(e) => setProbeBody(e.target.value)}
            placeholder='raw JSON body (e.g. {"business_name":"Acme"})'
            style={{background:'#000',border:`1px solid ${C.border}`,borderRadius:8,padding:'8px 10px',color:C.text,fontFamily:"'JetBrains Mono',monospace",fontSize:12}}
          />
        </div>
        <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
          <button data-testid="openfang-probe-run" onClick={runProbe} disabled={probing} style={btn}>
            {probing ? <RefreshCw size={12} style={{animation:'spin 1s linear infinite'}}/> : <ShieldCheck size={12}/>} Compute
          </button>
          <button
            data-testid="openfang-probe-now"
            onClick={() => setProbeTs(String(Math.floor(Date.now()/1000)))}
            style={btn}
          >Use now()</button>
        </div>
        {probeResult && (
          <div data-testid="openfang-probe-result" style={{marginTop:12,padding:12,background:'#000',border:`1px solid ${C.border}`,borderRadius:10,fontFamily:"'JetBrains Mono',monospace",fontSize:11.5,color:C.good}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4,color:C.textD}}>
              <span>X-OpenFang-Signature</span>
              <button onClick={() => copy('sig', probeResult.header_X_OpenFang_Signature)} style={{...btn,padding:'3px 8px',fontSize:9}}>
                {copied === 'sig' ? <Check size={10}/> : <Copy size={10}/>} {copied === 'sig' ? 'copied' : 'copy'}
              </button>
            </div>
            <div style={{wordBreak:'break-all'}}>{probeResult.header_X_OpenFang_Signature}</div>
            <div style={{marginTop:8,color:C.textD}}>X-OpenFang-Timestamp</div>
            <div>{probeResult.header_X_OpenFang_Timestamp}</div>
            <div style={{marginTop:8,color:C.textD,fontSize:10}}>algo: {probeResult.algorithm}</div>
          </div>
        )}
      </div>

      {/* Curl example */}
      <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,padding:'16px 20px'}}>
        <h3 style={{fontFamily:"'Cinzel',serif",fontSize:12,fontWeight:700,color:C.accent,letterSpacing:'0.18em',textTransform:'uppercase',margin:'0 0 10px'}}>
          Legion Node Example
        </h3>
        <pre style={{fontFamily:"'JetBrains Mono',monospace",fontSize:11,color:C.textD,lineHeight:1.6,whiteSpace:'pre-wrap',margin:0}}>
{`TS=$(date +%s)
BODY='{"business_name":"Acme","email":"x@acme.com"}'
SIG=$(printf "%s.%s" "$TS" "$BODY" | \\
  openssl dgst -sha256 -hmac "$OPENFANG_WEBHOOK_SECRET" -hex | awk '{print $2}')

curl -X POST "${API}/api/openfang/leads" \\
  -H "X-OpenFang-Signature: sha256=$SIG" \\
  -H "X-OpenFang-Timestamp: $TS" \\
  -H "Content-Type: application/json" \\
  -d "$BODY"`}
        </pre>
      </div>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
