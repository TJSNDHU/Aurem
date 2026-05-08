/**
 * CustomerSettings — Profile, notifications, password
 */
import React, { useState, useEffect } from 'react';
import { Lock, Bell, User, Save } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';
import { Link, useLocation } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerSettings({ ctx, reload }) {
  const [pw1, setPw1] = useState('');
  const [pw2, setPw2] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [saving, setSaving] = useState(false);
  const location = useLocation();

  // Scroll to Pixel Install section if user arrived via hash (#pixel-install)
  // or via the "Add Pixel" CTA in the IdentityStrip.
  useEffect(() => {
    const target = location.hash?.replace('#', '') || '';
    const id = target || 'pixel-install';
    const t = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        el.style.boxShadow = '0 0 0 2px rgba(212,175,55,0.6), 0 14px 40px rgba(212,175,55,0.25)';
        setTimeout(() => { el.style.boxShadow = ''; }, 2400);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [location.hash]);

  const changePassword = async () => {
    setPwMsg('');
    if (pw1.length < 8) return setPwMsg('Password must be at least 8 characters');
    if (pw1 !== pw2) return setPwMsg('Passwords do not match');
    setSaving(true);
    try {
      const tok = getPlatformToken();
      const res = await fetch(`${API}/api/bin-auth/first-login/set-password`, {
        method:'POST',
        headers:{'Content-Type':'application/json', Authorization:`Bearer ${tok}`},
        body: JSON.stringify({ new_password: pw1 }),
      });
      if (!res.ok) {
        const j = await res.json().catch(()=>({}));
        throw new Error(j.detail || 'Failed');
      }
      setPwMsg('Password updated.');
      setPw1(''); setPw2('');
    } catch (e) { setPwMsg(e.message); }
    setSaving(false);
  };

  return (
    <div data-testid="customer-settings">
      <h1 style={title}>Settings</h1>
      <p style={sub}>Security and preferences. Your identity is shown in the top banner.</p>

      {/* Profile extras — Industry & City (BIN/Name/Email/Company are in the top IdentityStrip) */}
      <div style={card} data-testid="settings-profile-extras">
        <h3 style={sectionH}><User size={14} style={{verticalAlign:'-2px',marginRight:8}}/>Profile Details</h3>
        <Row label="Industry" value={ctx.industry || '—'}/>
        <Row label="City" value={ctx.city || '—'}/>
      </div>

      {/* Password */}
      <div style={{...card, marginTop:16}}>
        <h3 style={sectionH}><Lock size={14} style={{verticalAlign:'-2px',marginRight:8}}/>Change Password</h3>
        <div style={{marginBottom:10}}>
          <label style={labelS}>New Password</label>
          <input data-testid="settings-pw1" type="password" value={pw1} onChange={e=>setPw1(e.target.value)} style={inputS}/>
        </div>
        <div style={{marginBottom:12}}>
          <label style={labelS}>Confirm</label>
          <input data-testid="settings-pw2" type="password" value={pw2} onChange={e=>setPw2(e.target.value)} style={inputS}/>
        </div>
        <button data-testid="settings-pw-save" onClick={changePassword} disabled={saving} style={primaryBtn}>
          <Save size={13}/> {saving ? 'Saving…' : 'Update Password'}
        </button>
        {pwMsg && <div data-testid="settings-pw-msg" style={{fontSize:12,marginTop:10,color: pwMsg.includes('update')?'#4ADE80':'#EF4444'}}>{pwMsg}</div>}
      </div>

      {/* Referrals link */}
      <div style={{...card, marginTop:16}}>
        <h3 style={sectionH}>Referrals</h3>
        <p style={{fontSize:12,color:'#8A8070',marginBottom:12}}>Refer a friend, get a month free.</p>
        <Link to="/my/referrals" data-testid="settings-referrals" style={{display:'inline-block',padding:'10px 18px',borderRadius:9,background:'rgba(212,175,55,0.08)',border:'1px solid rgba(212,175,55,0.2)',color:'#D4AF37',fontSize:12,fontWeight:600,textDecoration:'none',letterSpacing:'0.08em',textTransform:'uppercase'}}>Open Referrals →</Link>
      </div>

      {/* API Keys section */}
      <ApiKeysSection />
    </div>
  );
}

function ApiKeysSection() {
  const [info, setInfo] = React.useState(null);
  const [showKey, setShowKey] = React.useState(false);
  const [regenerating, setRegenerating] = React.useState(false);
  const [copiedSnippet, setCopiedSnippet] = React.useState(false);
  const [copiedKey, setCopiedKey] = React.useState(false);

  const load = () => {
    const tok = getPlatformToken();
    fetch(`${API}/api/customer/api-key`, { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.ok ? r.json() : { has_key: false })
      .then(d => setInfo(d));
  };
  React.useEffect(load, []);

  const copy = (text, which) => {
    navigator.clipboard.writeText(text);
    if (which === 'snippet') { setCopiedSnippet(true); setTimeout(()=>setCopiedSnippet(false), 2000); }
    if (which === 'key') { setCopiedKey(true); setTimeout(()=>setCopiedKey(false), 2000); }
  };

  const regenerate = async () => {
    if (!window.confirm('Regenerate your API key? The old key will stop working immediately.')) return;
    setRegenerating(true);
    try {
      const tok = getPlatformToken();
      const res = await fetch(`${API}/api/customer/api-key/regenerate`, {
        method:'POST', headers:{'Content-Type':'application/json', Authorization:`Bearer ${tok}`},
        body: JSON.stringify({ confirm: true }),
      });
      const d = await res.json();
      if (d.success) { alert('New key generated! Copy the new snippet and replace it on your site.'); load(); }
    } catch (e) {} finally { setRegenerating(false); }
  };

  if (!info) return null;

  return (
    <div id="pixel-install" data-testid="api-keys-section" style={{...card, marginTop:16}}>
      <h3 style={sectionH}>API Key & Pixel Install</h3>
      {!info.has_key ? (
        <p style={{fontSize:12,color:'#8A8070',marginTop:10}}>{info.message || 'No API key yet.'}</p>
      ) : (
        <>
          <div style={{marginTop:12,marginBottom:14}}>
            <label style={{display:'block',fontSize:10,letterSpacing:'0.18em',textTransform:'uppercase',color:'#8A8070',fontWeight:600,marginBottom:6}}>Your API Key</label>
            <div style={{display:'flex',gap:8,alignItems:'center'}}>
              <input data-testid="api-key-display" readOnly value={showKey ? (info.key || info.key_preview) : info.key_preview} style={{flex:1,padding:'10px 12px',background:'rgba(0,0,0,0.3)',border:'1px solid rgba(212,175,55,0.15)',borderRadius:8,color:'#D4AF37',fontSize:12,fontFamily:"'JetBrains Mono',monospace"}}/>
              {info.retrievable && (
                <button data-testid="api-key-toggle" onClick={()=>setShowKey(!showKey)} style={{padding:'10px 14px',borderRadius:8,background:'transparent',border:'1px solid rgba(212,175,55,0.2)',color:'#8A8070',fontSize:11,cursor:'pointer'}}>{showKey?'Hide':'Show'}</button>
              )}
              {info.retrievable && (
                <button data-testid="api-key-copy" onClick={()=>copy(info.key,'key')} style={{padding:'10px 14px',borderRadius:8,background:'rgba(212,175,55,0.08)',border:'1px solid rgba(212,175,55,0.2)',color:'#D4AF37',fontSize:11,cursor:'pointer',fontWeight:600}}>{copiedKey?'Copied':'Copy'}</button>
              )}
            </div>
            <div style={{fontSize:10,color:'#5A5468',marginTop:6}}>
              Last ping: <span style={{color:info.connected?'#4ADE80':'#8A8070'}}>{info.connected ? new Date(info.last_used).toLocaleString() : 'Not yet installed'}</span>
              {' · '}Events: <strong style={{color:'#D4AF37'}}>{info.events_total || 0}</strong>
            </div>
          </div>

          <div style={{marginBottom:14}}>
            <label style={{display:'block',fontSize:10,letterSpacing:'0.18em',textTransform:'uppercase',color:'#8A8070',fontWeight:600,marginBottom:6}}>Install Snippet (paste before &lt;/head&gt;)</label>
            <div data-testid="pixel-snippet" style={{padding:14,borderRadius:10,background:'rgba(0,0,0,0.4)',border:'1px solid rgba(255,255,255,0.06)',fontFamily:"'JetBrains Mono',monospace",fontSize:11,color:'#8A8070',lineHeight:1.5,wordBreak:'break-all'}}>
              {info.snippet}
            </div>
            <button data-testid="pixel-snippet-copy" onClick={()=>copy(info.snippet,'snippet')} style={{marginTop:8,padding:'8px 14px',borderRadius:8,background:'rgba(212,175,55,0.08)',border:'1px solid rgba(212,175,55,0.2)',color:'#D4AF37',fontSize:11,cursor:'pointer',fontWeight:600}}>{copiedSnippet?'Copied ✓':'Copy install code'}</button>
          </div>

          {info.retrievable && (
            <button data-testid="api-key-regenerate" onClick={regenerate} disabled={regenerating} style={{padding:'8px 14px',borderRadius:8,background:'transparent',border:'1px solid rgba(239,68,68,0.3)',color:'#EF4444',fontSize:11,cursor:'pointer',fontWeight:600}}>
              {regenerating ? 'Regenerating…' : 'Regenerate Key'}
            </button>
          )}
        </>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',padding:'9px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
      <span style={{fontSize:11,color:'#8A8070',letterSpacing:'0.12em',textTransform:'uppercase'}}>{label}</span>
      <span style={{fontSize:13,color:'#E8E0D0',fontFamily:label==='Your BIN'?"'JetBrains Mono',monospace":"'Jost',sans-serif",fontWeight:label==='Your BIN'?700:400}}>{value}</span>
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
const sectionH = { fontFamily:"'Cinzel',serif", fontSize:14, fontWeight:700, color:'#D4AF37', letterSpacing:'0.1em', textTransform:'uppercase', margin:'0 0 14px' };
const labelS = { display:'block', fontSize:10, letterSpacing:'0.18em', textTransform:'uppercase', color:'#8A8070', fontWeight:600, marginBottom:5 };
const inputS = { width:'100%', padding:'10px 12px', background:'rgba(212,175,55,0.03)', border:'1px solid rgba(212,175,55,0.15)', borderRadius:8, color:'#E8E0D0', fontSize:13, fontFamily:"'Jost',sans-serif", outline:'none', boxSizing:'border-box' };
const primaryBtn = { display:'inline-flex',alignItems:'center',gap:8, padding:'10px 18px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:9, fontSize:12, fontWeight:700, letterSpacing:'0.1em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
