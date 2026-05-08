/**
 * AdminImpersonationLog — Iteration 210
 * ======================================
 * /admin/impersonation-log
 *
 * CASL-compliance ledger of every impersonation event platform-wide.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Shield, RefreshCw, Loader2, UserCheck, Download } from 'lucide-react';
import { getPlatformToken } from '../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';
const C = {
  bg:'#06060C', panel:'#0D0D17', border:'rgba(212,175,55,0.12)',
  accent:'#D4AF37', good:'#4ADE80', warn:'#F59E0B', bad:'#EF4444',
  text:'#E8E0D0', textD:'#8A8070',
};

export default function AdminImpersonationLog() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const tok = getPlatformToken();
      const r = await fetch(`${API}/api/admin/customer-360/actions/impersonation-log?limit=200`, {
        headers: { Authorization: `Bearer ${tok}` },
      });
      if (!r.ok) { const d = await r.json().catch(()=>({})); setError(d.detail || `HTTP ${r.status}`); }
      else setData(await r.json());
    } catch (e) { setError(e.message); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const exportCSV = () => {
    if (!data || !data.log) return;
    const rows = [
      ['Timestamp (UTC)', 'Admin', 'Target', 'IP', 'TTL (min)', 'JTI'],
      ...data.log.map(r => [
        r.timestamp || '',
        r.admin_email || '',
        r.target_email || '',
        r.ip || '',
        (r.detail && r.detail.ttl_minutes) || '',
        (r.detail && r.detail.jti) || '',
      ]),
    ];
    const csv = rows.map(row => row.map(c => `"${String(c).replace(/"/g,'""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `aurem-impersonation-log-${new Date().toISOString().slice(0,10)}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading && !data) {
    return <div data-testid="imp-loading" style={{minHeight:'60vh',display:'flex',alignItems:'center',justifyContent:'center',color:C.textD,fontSize:13,fontFamily:"'Jost',sans-serif"}}>
      <Loader2 size={16} style={{animation:'spin 1s linear infinite',marginRight:10}}/> Loading impersonation log…
    </div>;
  }
  if (error) {
    return <div data-testid="imp-error" style={{padding:40,color:C.bad,fontFamily:"'Jost',sans-serif"}}>
      {error}<br/><Link to="/dashboard" style={{color:C.accent}}>← Dashboard</Link>
    </div>;
  }

  const rows = (data && data.log) || [];

  return (
    <div data-testid="admin-impersonation-log" style={{
      minHeight:'100vh',background:C.bg,color:C.text,fontFamily:"'Jost',sans-serif",padding:'28px 36px',
    }}>
      <div style={{marginBottom:22}}>
        <Link to="/dashboard" style={{fontSize:11,color:C.textD,letterSpacing:'0.2em',textTransform:'uppercase',textDecoration:'none'}}>← Dashboard</Link>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginTop:6,gap:16,flexWrap:'wrap'}}>
          <div>
            <div style={{fontSize:11,letterSpacing:'0.24em',color:C.accent,textTransform:'uppercase',fontWeight:700,display:'flex',alignItems:'center',gap:8}}>
              <Shield size={14}/> CASL Compliance
            </div>
            <h1 style={{fontFamily:"'Cinzel',serif",fontSize:28,fontWeight:700,color:'#FFF',margin:'4px 0'}}>Impersonation Log</h1>
            <p style={{fontSize:12,color:C.textD}}>Every admin login-as event, platform-wide. Total: <strong style={{color:C.text}}>{data?.total ?? 0}</strong></p>
          </div>
          <div style={{display:'flex',gap:8}}>
            <button data-testid="imp-export" onClick={exportCSV} disabled={!rows.length} style={btn}>
              <Download size={12}/> Export CSV
            </button>
            <button data-testid="imp-refresh" onClick={load} disabled={loading} style={btn}>
              <RefreshCw size={12} style={loading?{animation:'spin 1s linear infinite'}:{}}/> Refresh
            </button>
          </div>
        </div>
      </div>

      <div data-testid="imp-table-wrap" style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:14,overflow:'hidden'}}>
        {rows.length === 0 ? (
          <div style={{padding:40,textAlign:'center',color:C.textD,fontSize:13}}>
            <UserCheck size={28} color={C.textD} style={{marginBottom:10}}/>
            <div>No impersonation events recorded yet.</div>
            <div style={{fontSize:11,marginTop:6}}>This is the CASL-compliant audit trail — it will populate as admins use the Impersonate action.</div>
          </div>
        ) : (
          <table style={{width:'100%',borderCollapse:'collapse'}}>
            <thead>
              <tr style={{background:'rgba(212,175,55,0.04)'}}>
                <th style={th}>Timestamp (UTC)</th>
                <th style={th}>Admin</th>
                <th style={th}>Target Customer</th>
                <th style={th}>IP Address</th>
                <th style={th}>TTL</th>
                <th style={th}>Token ID</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} data-testid={`imp-row-${i}`} style={{borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                  <td style={td}>{(r.timestamp || '').slice(0,19).replace('T',' ')}</td>
                  <td style={{...td, color:C.accent, fontWeight:600}}>{r.admin_email || '—'}</td>
                  <td style={td}>
                    <Link to={`/admin/customer/${encodeURIComponent(r.target_email)}`} style={{color:C.text,textDecoration:'none',borderBottom:`1px dashed ${C.textD}`}}>
                      {r.target_email || '—'}
                    </Link>
                  </td>
                  <td style={{...td, color:C.textD, fontFamily:"'JetBrains Mono',monospace"}}>{r.ip || '—'}</td>
                  <td style={td}>{(r.detail && r.detail.ttl_minutes) ? `${r.detail.ttl_minutes}m` : '—'}</td>
                  <td style={{...td, color:C.textD, fontFamily:"'JetBrains Mono',monospace", fontSize:10.5}}>
                    {(r.detail && r.detail.jti) ? `${r.detail.jti.slice(0,8)}…${r.detail.jti.slice(-4)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p style={{fontSize:10.5,color:C.textD,marginTop:14,textAlign:'center',letterSpacing:'0.08em'}}>
        Retained per CASL &amp; internal audit policy · Every row includes admin identity + target + IP + unique token ID.
      </p>

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

const th = { textAlign:'left', padding:'10px 14px', fontSize:10, letterSpacing:'0.16em', color:C.textD, textTransform:'uppercase', fontWeight:700, borderBottom:`1px solid ${C.border}` };
const td = { padding:'9px 14px', fontSize:12, verticalAlign:'middle' };
const btn = {
  display:'inline-flex',alignItems:'center',gap:6,padding:'8px 14px',
  background:'transparent',border:`1px solid rgba(212,175,55,0.25)`,borderRadius:8,
  color:C.accent,fontSize:11,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',
  cursor:'pointer',fontFamily:"'Jost',sans-serif",
};
