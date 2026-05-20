/**
 * CustomerSettings — Profile, notifications, password
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Lock, Bell, User, Save, Palette, Phone, CalendarCheck } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';
import { Link, useLocation } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function CustomerSettings({ ctx, reload }) {
  const [pw1, setPw1] = useState('');
  const [pw2, setPw2] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [saving, setSaving] = useState(false);
  const location = useLocation();
  const { hash } = location;

  // Scroll to Pixel Install section if user arrived via hash (#pixel-install)
  // or via the "Add Pixel" CTA in the IdentityStrip.
  useEffect(() => {
    const target = hash?.replace('#', '') || '';
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
  }, [hash]);

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

      {/* iter 322as — A: White-label Branding */}
      <BrandingSection ctx={ctx} />

      {/* iter 322as — C: Inbound Voice (Retell) */}
      <VoiceSection />

      {/* iter 322as — B: Booking calendar setup */}
      <BookingSection ctx={ctx} />
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

// ─────────────────────────────────────────────────────────────────
// iter 322as — A. White-Label Branding (lightweight customer view)
// ─────────────────────────────────────────────────────────────────
function BrandingSection({ ctx }) {
  const tok = getPlatformToken();
  const tenantId = ctx?.bin || ctx?.business_id || '';
  const [branding, setBranding] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    if (!tenantId) { setLoading(false); return; }
    try {
      const r = await fetch(`${API}/api/admin/branding/${tenantId}`, { headers:{ Authorization:`Bearer ${tok}` }});
      const j = await r.json();
      if (r.ok && j?.branding) setBranding(j.branding);
      else setErr(j?.detail || 'Branding unavailable');
    } catch (e) { setErr(e.message); }
    setLoading(false);
  }, [tok, tenantId]);
  useEffect(()=>{ load(); }, [load]);

  const save = async () => {
    if (!branding) return;
    setSaving(true); setErr('');
    try {
      const r = await fetch(`${API}/api/admin/branding/${tenantId}`, {
        method:'POST',
        headers:{ Authorization:`Bearer ${tok}`, 'Content-Type':'application/json' },
        body: JSON.stringify({
          brand_name: branding.brand_name || '',
          logo_url: branding.logo_url || '',
          primary_color: branding.primary_color || '#D4A373',
          domain: branding.domain || '',
        }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || j?.error || `HTTP ${r.status}`);
      setBranding(j.branding);
      setSavedAt(Date.now());
    } catch (e) { setErr(e.message); }
    setSaving(false);
  };

  return (
    <div id="branding" style={{...card, marginTop:16}} data-testid="customer-branding-section">
      <h3 style={sectionH}><Palette size={14} style={{verticalAlign:'-2px',marginRight:8}}/>Branding (White-Label)</h3>
      <p style={{...sub, marginTop:-12, marginBottom:14}}>
        Customise the look of your customer-facing dashboard. Enterprise plan unlocks custom domains.
      </p>

      {err && <div style={{fontSize:12, color:'#EF4444', marginBottom:10}} data-testid="customer-branding-error">{err}</div>}
      {loading ? (
        <div style={{fontSize:12, color:'#8A8070'}}>Loading…</div>
      ) : (
        <>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
            <Field label="Brand name" testid="cust-brand-name"
              value={branding?.brand_name || ''}
              onChange={v=>setBranding({...branding, brand_name:v})}/>
            <Field label="Logo URL" testid="cust-brand-logo"
              value={branding?.logo_url || ''}
              placeholder="https://cdn.example.com/logo.png"
              onChange={v=>setBranding({...branding, logo_url:v})}/>
            <div>
              <label style={labelS}>Primary colour</label>
              <div style={{display:'flex', gap:8, alignItems:'center'}}>
                <input type="color" data-testid="cust-brand-color"
                  value={branding?.primary_color || '#D4AF37'}
                  onChange={e=>setBranding({...branding, primary_color:e.target.value})}
                  style={{width:42, height:36, padding:0, border:'none', background:'transparent'}}/>
                <input data-testid="cust-brand-color-hex" value={branding?.primary_color || ''}
                  onChange={e=>setBranding({...branding, primary_color:e.target.value})}
                  style={inputS}/>
              </div>
            </div>
            <Field label="Custom domain (CNAME)" testid="cust-brand-domain"
              value={branding?.domain || ''} placeholder="ai.yourcompany.com"
              onChange={v=>setBranding({...branding, domain:v})}/>
          </div>
          <button data-testid="cust-brand-save" onClick={save} disabled={saving}
            style={{...primaryBtn, marginTop:14, opacity:saving?0.6:1}}>
            <Save size={13}/> {saving ? 'Saving…' : 'Save branding'}
          </button>
          {savedAt && <span style={{fontSize:12, marginLeft:10, color:'#4ADE80'}} data-testid="cust-brand-saved">✓ Saved</span>}
        </>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────
// iter 322as — C. Inbound Voice (Retell) — customer view
// ─────────────────────────────────────────────────────────────────
function VoiceSection() {
  const tok = getPlatformToken();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(()=>{
    setLoading(true);
    fetch(`${API}/api/customer/voice-agent/status`, { headers:{ Authorization:`Bearer ${tok}` }})
      .then(r => r.ok ? r.json() : null)
      .then(setStatus)
      .catch(()=>{})
      .finally(()=>setLoading(false));
  }, [tok]);
  useEffect(()=>{ load(); }, [load]);

  const live = !!(status?.retell_ready || status?.retell_key_set);
  const provisioned = !!status?.provisioned;

  return (
    <div id="voice" style={{...card, marginTop:16}} data-testid="customer-voice-section">
      <h3 style={sectionH}><Phone size={14} style={{verticalAlign:'-2px',marginRight:8}}/>Inbound Voice (ORA Answers Your Phone)</h3>
      <div style={{padding:'12px 14px', borderRadius:10,
        background: live ? 'rgba(74,222,128,0.06)' : 'rgba(245,158,11,0.06)',
        border: `1px solid ${live ? 'rgba(74,222,128,0.25)' : 'rgba(245,158,11,0.25)'}`,
        display:'flex', alignItems:'center', gap:10, flexWrap:'wrap'}}>
        <span style={{width:10, height:10, borderRadius:'50%',
          background: live ? '#4ADE80' : '#F59E0B',
          boxShadow:`0 0 10px ${live ? '#4ADE80' : '#F59E0B'}88`}}/>
        <div style={{flex:1, minWidth:200}}>
          <div style={{fontSize:13, color:'#E8E0D0', fontWeight:600}} data-testid="customer-voice-status">
            {loading ? 'Checking…' : live ? '🟢 Inbound voice is live' : '🔴 Not configured yet'}
          </div>
          <div style={{...sub, margin:0, marginTop:3, fontSize:11.5}}>
            {live
              ? (provisioned
                ? `Minutes used this month: ${status?.month_usage?.minutes_used ?? 0} / ${status?.month_usage?.minutes_included ?? '—'}`
                : 'Retell is ready — subscribe to the Voice Agent add-on to start answering calls.')
              : 'Add your Retell API key (Settings → Env Variables → RETELL_API_KEY) to let ORA answer your business line 24×7.'}
          </div>
        </div>
        <button onClick={load} data-testid="customer-voice-refresh"
          style={{padding:'8px 12px', borderRadius:8, background:'transparent',
                  border:'1px solid rgba(212,175,55,0.25)', color:'#D4AF37', fontSize:11, cursor:'pointer'}}>
          Refresh
        </button>
      </div>

      {!live && (
        <ol style={{fontSize:12, color:'#8A8070', lineHeight:1.8, marginTop:12, marginLeft:18}}>
          <li>Sign in to <a href="https://www.retellai.com" target="_blank" rel="noreferrer" style={{color:'#D4AF37'}}>retellai.com</a> and generate an API key.</li>
          <li>Open Emergent → Settings → Env Variables → add <code style={{color:'#D4AF37'}}>RETELL_API_KEY</code>.</li>
          <li>Redeploy. ORA will start answering inbound calls.</li>
        </ol>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────
// iter 322as — B. Booking calendar setup
// ─────────────────────────────────────────────────────────────────
function BookingSection({ ctx }) {
  const tok = getPlatformToken();
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/customer/api-key`, { headers:{ Authorization:`Bearer ${tok}` }})
      .then(r => r.ok ? r.json() : null)
      .then(setInfo)
      .catch(()=>{})
      .finally(()=>setLoading(false));
  }, [tok]);

  const apiKey = info?.key || info?.key_preview || 'sk_aurem_live_xxxxx';
  const widgetScript = `<script src="${window.location.origin}/widget.js" data-api-key="${apiKey}"></script>`;
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(widgetScript);
    setCopied(true);
    setTimeout(()=>setCopied(false), 1800);
  };

  return (
    <div id="booking" style={{...card, marginTop:16}} data-testid="customer-booking-section">
      <h3 style={sectionH}><CalendarCheck size={14} style={{verticalAlign:'-2px',marginRight:8}}/>Booking Calendar</h3>
      <p style={{...sub, marginTop:-10, marginBottom:14}}>
        The AUREM widget includes a built-in booking modal. Visitors pick a service, date and slot, and the booking
        lands in your <code style={{color:'#D4AF37'}}>bookings</code> collection — same one your dashboard reads.
      </p>

      <div style={{padding:'10px 14px', borderRadius:10, background:'rgba(0,0,0,0.4)',
                   border:'1px solid rgba(255,255,255,0.06)', fontFamily:"'JetBrains Mono',monospace",
                   fontSize:11.5, color:'#8A8070', wordBreak:'break-all'}} data-testid="booking-snippet">
        {loading ? 'Loading API key…' : widgetScript}
      </div>
      <div style={{display:'flex', gap:8, marginTop:10, flexWrap:'wrap'}}>
        <button data-testid="booking-copy-btn" onClick={copy} disabled={loading}
          style={{...primaryBtn, opacity: loading?0.5:1}}>
          {copied ? 'Copied ✓' : 'Copy embed code'}
        </button>
        <Link to="/my/integrations" data-testid="booking-integrations-link"
          style={{padding:'10px 18px', borderRadius:9, background:'rgba(212,175,55,0.08)',
                  border:'1px solid rgba(212,175,55,0.2)', color:'#D4AF37',
                  fontSize:12, fontWeight:600, textDecoration:'none', letterSpacing:'0.08em',
                  textTransform:'uppercase', display:'inline-flex', alignItems:'center'}}>
          Open Integrations →
        </Link>
      </div>

      <div style={{marginTop:14, fontSize:11.5, color:'#8A8070'}}>
        <strong style={{color:'#D4AF37'}}>Default services:</strong> Initial Consultation (30 min) ·
        Follow-up (20 min) · Standard Service (60 min) · Premium Session (90 min).
        Customise per-BIN by writing to <code>tenant_booking_services</code>.
      </div>
    </div>
  );
}


// ── small helper ──
function Field({ label, value, onChange, placeholder, testid }) {
  return (
    <div>
      <label style={labelS}>{label}</label>
      <input data-testid={testid} value={value || ''} placeholder={placeholder || ''}
        onChange={e=>onChange(e.target.value)} style={inputS}/>
    </div>
  );
}

function _Row() { return null; }

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
