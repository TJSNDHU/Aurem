/**
 * CustomerSocial — Postiz-backed social media control panel
 */
import React, { useEffect, useState } from 'react';
import { Share2, Calendar, Link2, Loader2, AlertCircle, Power } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerSocial({ ctx }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    const tok = getPlatformToken();
    fetch(`${API}/api/customer/social/status`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : { configured: false, enabled: false, accounts: [] })
      .then(d => setStatus(d))
      .catch(() => setStatus({ configured: false, enabled: false, accounts: [] }))
      .finally(() => setLoading(false));
  }, []);

  const toggleAuto = async () => {
    setToggling(true);
    const tok = getPlatformToken();
    try {
      const res = await fetch(`${API}/api/customer/social/toggle`, {
        method:'POST',
        headers:{ 'Content-Type':'application/json', Authorization:`Bearer ${tok}` },
        body: JSON.stringify({ enabled: !status.enabled }),
      });
      const d = await res.json();
      setStatus(s => ({ ...s, enabled: d.enabled }));
    } catch {}
    setToggling(false);
  };

  if (loading) return <div data-testid="social-loading" style={{color:'#8A8070'}}>Loading social settings…</div>;

  return (
    <div data-testid="customer-social">
      <h1 style={title}>Social Media</h1>
      <p style={sub}>AUREM auto-posts once daily to your connected accounts using Postiz.</p>

      {!status?.configured && (
        <div data-testid="social-setup-required" style={{...card, borderColor:'rgba(239,68,68,0.25)', background:'rgba(239,68,68,0.04)', marginBottom:16}}>
          <div style={{display:'flex',alignItems:'flex-start',gap:12}}>
            <AlertCircle size={20} color="#EF4444"/>
            <div>
              <div style={{fontSize:14,fontWeight:600,color:'#EF4444',marginBottom:4}}>Social posting not yet configured</div>
              <div style={{fontSize:12,color:'#A89E88',lineHeight:1.5}}>
                Admin needs to add <code style={code}>POSTIZ_API_KEY</code> to the environment before accounts can be connected.
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={card}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:14}}>
          <h3 style={sectionH}>Auto-posting</h3>
          <button data-testid="social-toggle" onClick={toggleAuto} disabled={toggling || !status?.configured} style={{
            padding:'8px 14px',borderRadius:20,border:`1px solid ${status?.enabled?'#4ADE80':'rgba(255,255,255,0.1)'}`,
            background:status?.enabled?'rgba(74,222,128,0.12)':'transparent',
            color:status?.enabled?'#4ADE80':'#8A8070', fontSize:11, fontWeight:700, cursor:toggling?'wait':'pointer',
            letterSpacing:'0.1em',textTransform:'uppercase'
          }}>
            <Power size={12} style={{verticalAlign:'-2px',marginRight:5}}/>{status?.enabled ? 'On' : 'Off'}
          </button>
        </div>
        <p style={{fontSize:12,color:'#8A8070',lineHeight:1.6,margin:0}}>
          When ON, AUREM drafts and posts one piece of content daily tuned to your business voice.
        </p>
      </div>

      <div style={{...card, marginTop:16}}>
        <h3 style={sectionH}>Connected Accounts</h3>
        {(status?.accounts || []).length === 0 ? (
          <p style={{fontSize:12,color:'#8A8070',margin:'12px 0 0'}}>No accounts connected yet.</p>
        ) : (
          <ul style={{margin:'12px 0 0',padding:0,listStyle:'none'}}>
            {status.accounts.map((a, i) => (
              <li key={i} data-testid={`social-account-${a.platform}`} style={{display:'flex',alignItems:'center',gap:10,padding:'10px 0',borderBottom:i<status.accounts.length-1?'1px solid rgba(255,255,255,0.04)':'none'}}>
                <Link2 size={14} color="#D4AF37"/>
                <span style={{fontSize:13,color:'#E8E0D0',textTransform:'capitalize'}}>{a.platform}</span>
                <span style={{fontSize:11,color:'#8A8070',marginLeft:'auto'}}>{a.handle || a.username || ''}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

const title = { fontFamily:"'Cinzel',serif", fontSize:26, fontWeight:700, color:'#FFF', letterSpacing:'0.03em', marginBottom:4 };
const sub = { fontSize:13, color:'#8A8070', marginBottom:20 };
const card = {
  borderRadius: 18,
  padding: 22,
  background: 'rgba(15,18,28,0.55)',
  backdropFilter: 'blur(22px) saturate(150%)',
  WebkitBackdropFilter: 'blur(22px) saturate(150%)',
  border: '1px solid rgba(212,175,55,0.14)',
  boxShadow: '0 16px 44px rgba(0,0,0,0.35), inset 0 1px 0 rgba(212,175,55,0.08)',
};
const sectionH = { fontFamily:"'Cinzel',serif", fontSize:14, fontWeight:700, color:'#D4AF37', letterSpacing:'0.1em', textTransform:'uppercase', margin:0 };
const code = { background:'rgba(212,175,55,0.1)', padding:'2px 6px', borderRadius:4, color:'#D4AF37', fontFamily:"'JetBrains Mono',monospace", fontSize:11 };
