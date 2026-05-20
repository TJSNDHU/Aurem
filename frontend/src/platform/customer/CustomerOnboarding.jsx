/**
 * CustomerOnboarding — Smart one-click onboarding at /my/onboarding
 * =================================================================
 * Step 1: Customer enters website URL + city
 * Step 2: AUREM detects platform, socials, Google Places (parallel)
 * Step 3: Customer confirms/corrects in pre-filled smart form
 * Step 4: One click → all subsystems start
 */
import React, { useState } from 'react';
import { Loader2, Check, X, Edit3, Globe, Facebook, Instagram, AlertCircle, Sparkles, Share2, Copy } from 'lucide-react';
import { getPlatformToken } from '../../utils/secureTokenStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

const PLATFORM_LABELS = {
  wordpress: 'WordPress', shopify: 'Shopify', wix: 'Wix',
  squarespace: 'Squarespace', webflow: 'Webflow', framer: 'Framer',
  ghost: 'Ghost', woocommerce: 'WooCommerce', bigcommerce: 'BigCommerce',
  react: 'React / Custom', nextjs: 'Next.js', gatsby: 'Gatsby',
  custom: 'Custom / Other', no_website: 'No Website',
};

const CONNECTION_METHODS = {
  wordpress_plugin: 'WordPress Plugin (auto-install)',
  shopify_app: 'Shopify App',
  gtm: 'Google Tag Manager',
  manual_code: 'Manual code snippet',
  aurem_free_site: 'Build me a free AUREM site',
};

export default function CustomerOnboarding({ ctx }) {
  const [step, setStep] = useState(1);
  const [businessName, setBusinessName] = useState(ctx?.business_name || '');
  const [websiteUrl, setWebsiteUrl] = useState(ctx?.website || '');
  const [city, setCity] = useState(ctx?.city || '');
  const [detecting, setDetecting] = useState(false);
  const [detection, setDetection] = useState(null);

  // Correction state
  const [platform, setPlatform] = useState('custom');
  const [connection, setConnection] = useState('gtm');
  const [socials, setSocials] = useState({});
  const [newSocial, setNewSocial] = useState({ platform: '', url: '' });

  const [starting, setStarting] = useState(false);
  const [started, setStarted] = useState(null);

  const apiHeaders = () => ({
    'Content-Type':'application/json',
    Authorization: `Bearer ${getPlatformToken()}`,
  });

  const runDetect = async () => {
    if (!businessName.trim()) return alert('Business name required');
    setDetecting(true);
    try {
      const r = await fetch(`${API}/api/smart-onboarding/detect`, {
        method:'POST', headers: apiHeaders(),
        body: JSON.stringify({ business_name: businessName.trim(), website_url: websiteUrl.trim(), city: city.trim() }),
      });
      const d = await r.json();
      setDetection(d);
      setPlatform(d.website?.platform || 'custom');
      setConnection(d.recommended_connection || 'gtm');
      setSocials(d.social_media || {});
      setStep(2);
    } catch (e) { alert('Detection failed: ' + e.message); }
    setDetecting(false);
  };

  const startAurem = async () => {
    setStarting(true);
    try {
      const r = await fetch(`${API}/api/smart-onboarding/start`, {
        method:'POST', headers: apiHeaders(),
        body: JSON.stringify({
          business_name: businessName,
          website_url: websiteUrl,
          platform,
          connection_method: connection,
          social_media: socials,
          google_places: detection?.google_places || null,
        }),
      });
      const d = await r.json();
      if (!r.ok || !d.success) throw new Error(d.error || d.detail || 'Start failed');
      setStarted(d);
      setStep(3);
    } catch (e) { alert('Failed to start: ' + e.message); }
    setStarting(false);
  };

  const addSocial = () => {
    if (!newSocial.platform || !newSocial.url) return;
    setSocials(s => ({...s, [newSocial.platform]: newSocial.url}));
    setNewSocial({ platform: '', url: '' });
  };

  const removeSocial = (p) => setSocials(s => { const n={...s}; delete n[p]; return n; });

  return (
    <div data-testid="customer-onboarding" style={{maxWidth:680}}>
      <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:20}}>
        <Sparkles size={24} color="#D4AF37"/>
        <h1 style={title}>Smart Onboarding</h1>
      </div>
      <p style={sub}>AUREM finds everything automatically. You confirm, we start.</p>

      {/* ─── STEP 1: Kick off detection ─── */}
      {step === 1 && (
        <div data-testid="onboarding-step-1" style={card}>
          <h3 style={sectionH}>Tell us about your business</h3>
          <Field label="Business Name *" testid="onb-business-name" value={businessName} onChange={setBusinessName}/>
          <Field label="Website URL (optional)" testid="onb-website-url" value={websiteUrl} onChange={setWebsiteUrl} placeholder="https://your-site.com"/>
          <Field label="City" testid="onb-city" value={city} onChange={setCity} placeholder="Toronto"/>
          <button data-testid="onb-detect-btn" onClick={runDetect} disabled={detecting} style={{...primaryBtn, marginTop:14}}>
            {detecting ? <Loader2 size={14} style={{animation:'spin 1s linear infinite'}}/> : <Sparkles size={14}/>}
            {detecting ? 'Detecting...' : 'Detect Everything'}
          </button>
        </div>
      )}

      {/* ─── STEP 2: Smart form confirmation ─── */}
      {step === 2 && detection && (
        <div data-testid="onboarding-step-2">
          {/* Business identity */}
          <div style={card}>
            <h3 style={sectionH}>🎉 Welcome {businessName}!</h3>
            <p style={{fontSize:13,color:'#8A8070',marginBottom:16}}>Here's what we found about your business. Correct anything that's off.</p>

            {/* Website */}
            <Row
              label="Website"
              value={detection.website?.exists ? detection.website.url : '❌ No website found'}
              extra={detection.website?.exists ? `Platform: ${PLATFORM_LABELS[platform] || platform}` : 'AUREM can build you one free ↓'}
              badge={detection.website?.confidence || null}
              testid="detected-website"
            />

            {/* Platform override */}
            {detection.website?.exists && (
              <div data-testid="platform-correction" style={{marginTop:10,padding:12,borderRadius:10,background:'rgba(212,175,55,0.04)'}}>
                <label style={labelS}>Not right? Select correct platform:</label>
                <select data-testid="platform-select" value={platform} onChange={e=>setPlatform(e.target.value)} style={inputS}>
                  {Object.entries(PLATFORM_LABELS).map(([k,v])=><option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            )}

            {/* Google Places */}
            <div style={{marginTop:14}}>
              <Row
                label="Google Reviews"
                value={detection.google_places?.found ? `${detection.google_places.rating} ⭐ (${detection.google_places.review_count} reviews)` : 'Not linked yet'}
                extra={detection.google_places?.address || ''}
                testid="detected-places"
              />
            </div>

            {/* Social Media */}
            <div style={{marginTop:16,borderTop:'1px solid rgba(255,255,255,0.05)',paddingTop:16}}>
              <h4 style={{...sectionH, fontSize:13}}>Social Media</h4>
              {Object.keys(socials).length === 0 && <p style={{fontSize:12,color:'#8A8070'}}>No social accounts found, add any you have below.</p>}
              {Object.entries(socials).map(([p, url]) => (
                <div key={p} data-testid={`detected-social-${p}`} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
                  <span style={{fontSize:12,fontWeight:600,color:'#D4AF37',textTransform:'capitalize',minWidth:90}}>{p}</span>
                  <span style={{flex:1,fontSize:12,color:'#A89E88',overflow:'hidden',textOverflow:'ellipsis'}}>{url}</span>
                  <button data-testid={`remove-social-${p}`} onClick={()=>removeSocial(p)} style={iconBtn}><X size={12}/></button>
                </div>
              ))}
              <div style={{display:'flex',gap:6,marginTop:10}}>
                <select data-testid="add-social-platform" value={newSocial.platform} onChange={e=>setNewSocial(s=>({...s,platform:e.target.value}))} style={{...inputS,flex:'0 0 130px'}}>
                  <option value="">+ Add</option>
                  <option value="facebook">Facebook</option>
                  <option value="instagram">Instagram</option>
                  <option value="twitter">Twitter / X</option>
                  <option value="tiktok">TikTok</option>
                  <option value="youtube">YouTube</option>
                  <option value="linkedin">LinkedIn</option>
                </select>
                <input data-testid="add-social-url" placeholder="URL" value={newSocial.url} onChange={e=>setNewSocial(s=>({...s,url:e.target.value}))} style={{...inputS,flex:1}}/>
                <button data-testid="add-social-btn" onClick={addSocial} style={{...primaryBtn,padding:'8px 14px',fontSize:11}}>Add</button>
              </div>
            </div>

            {/* Connection method */}
            <div style={{marginTop:18,borderTop:'1px solid rgba(255,255,255,0.05)',paddingTop:16}}>
              <h4 style={{...sectionH, fontSize:13}}>How should AUREM connect to your website?</h4>
              <div style={{display:'grid',gap:6,marginTop:8}}>
                {Object.entries(CONNECTION_METHODS).map(([k,v]) => (
                  <label key={k} data-testid={`conn-${k}`} style={{display:'flex',alignItems:'center',gap:10,padding:'10px 12px',borderRadius:9,cursor:'pointer',border:`1px solid ${connection===k?'#D4AF37':'rgba(255,255,255,0.06)'}`,background:connection===k?'rgba(212,175,55,0.08)':'transparent'}}>
                    <input type="radio" name="conn" checked={connection===k} onChange={()=>setConnection(k)} style={{accentColor:'#D4AF37'}}/>
                    <span style={{fontSize:12.5,color:'#E8E0D0'}}>{v}</span>
                    {k === detection.recommended_connection && <span style={{fontSize:9,color:'#D4AF37',fontWeight:700,marginLeft:'auto',letterSpacing:'0.1em'}}>RECOMMENDED</span>}
                  </label>
                ))}
              </div>
            </div>

            <button data-testid="onb-start-btn" onClick={startAurem} disabled={starting} style={{...primaryBtn, marginTop:20, width:'100%', justifyContent:'center', padding:'14px 18px'}}>
              {starting ? <Loader2 size={14} style={{animation:'spin 1s linear infinite'}}/> : <Check size={14}/>}
              {starting ? 'Starting AUREM...' : '✅ Looks Good — Start AUREM'}
            </button>
          </div>
        </div>
      )}

      {/* ─── STEP 3: Success ─── */}
      {step === 3 && started && (
        <div data-testid="onboarding-step-3" style={{...card, textAlign:'center'}}>
          <div style={{width:64,height:64,borderRadius:'50%',background:'rgba(74,222,128,0.12)',border:'1.5px solid #4ADE80',display:'flex',alignItems:'center',justifyContent:'center',margin:'0 auto 18px'}}>
            <Check size={28} color="#4ADE80"/>
          </div>
          <h2 style={{fontFamily:"'Cinzel',serif",fontSize:22,fontWeight:700,color:'#FFF',marginBottom:8}}>AUREM is Live</h2>
          <p style={{fontSize:13,color:'#8A8070',lineHeight:1.6,marginBottom:20}}>Your AI agents are running. Check your dashboard for live activity.</p>
          <div data-testid="onboarding-actions-log" style={{background:'rgba(212,175,55,0.05)',border:'1px solid rgba(212,175,55,0.15)',borderRadius:10,padding:16,textAlign:'left',marginBottom:20}}>
            <div style={{fontSize:10,letterSpacing:'0.18em',color:'#D4AF37',fontWeight:700,marginBottom:10,textTransform:'uppercase'}}>What Just Started</div>
            <ul style={{margin:0,padding:0,listStyle:'none'}}>
              {(started.actions || []).map((a, i) => (
                <li key={i} style={{padding:'5px 0',fontSize:12,color:'#A89E88',display:'flex',gap:8,alignItems:'center'}}>
                  <Check size={13} color="#4ADE80"/> {a.replace(/_/g,' ')}
                </li>
              ))}
            </ul>
          </div>

          {/* Referral share — invite others, get rewarded */}
          <ReferralShare ctx={ctx} businessName={businessName}/>

          {/* Power Trial activated banner */}
          <div data-testid="onb-trial-banner" style={{marginTop:16,padding:14,borderRadius:10,background:'linear-gradient(135deg,rgba(34,197,94,0.08),rgba(212,175,55,0.05))',border:'1px solid rgba(34,197,94,0.3)',textAlign:'left'}}>
            <div style={{fontSize:10,letterSpacing:'0.2em',color:'#22C55E',fontWeight:800,textTransform:'uppercase',marginBottom:6}}>
              ⚡ Your 7-Day Power Trial is Active
            </div>
            <div style={{fontSize:11,color:'#C9C9D1',lineHeight:1.6,marginBottom:8}}>
              <b style={{color:'#FFF'}}>Unlocked now:</b> Scanner · ORA Chat 50 msgs · Friend Scanner 5/wk · Pixel monitoring · 1 free Social Reel
            </div>
            <div style={{fontSize:10,color:'#8A8070'}}>
              Pick 3+ add-ons → <span style={{color:'#22C55E',fontWeight:700}}>auto 15% bundle discount</span>
            </div>
          </div>

          <a href="/my/website" data-testid="onb-goto-dashboard" style={{...primaryBtn,textDecoration:'none',display:'inline-flex',marginTop:16}}>Go to My Website →</a>
        </div>
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function Field({ label, value, onChange, testid, placeholder }) {
  return (
    <div style={{marginBottom:10}}>
      <label style={labelS}>{label}</label>
      <input data-testid={testid} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} style={inputS}/>
    </div>
  );
}

function Row({ label, value, extra, badge, testid }) {
  return (
    <div data-testid={testid} style={{padding:'10px 0',borderBottom:'1px solid rgba(255,255,255,0.04)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
        <span style={{fontSize:10,letterSpacing:'0.18em',color:'#8A8070',textTransform:'uppercase',fontWeight:600}}>{label}</span>
        {badge && <span style={{fontSize:9,letterSpacing:'0.1em',color:badge==='high'?'#4ADE80':badge==='medium'?'#D4AF37':'#8A8070',textTransform:'uppercase',fontWeight:700}}>{badge}</span>}
      </div>
      <div style={{fontSize:13,color:'#E8E0D0',fontWeight:500,marginTop:3}}>{value}</div>
      {extra && <div style={{fontSize:11,color:'#8A8070',marginTop:2}}>{extra}</div>}
    </div>
  );
}

function ReferralShare({ ctx, businessName }) {
  const [copied, setCopied] = useState(false);
  const bin = (ctx?.bin || '').toLowerCase() || 'aurem';
  const refLink = `https://aurem.live/ref/${bin}`;
  const message =
`I just joined AUREM! 🎉
World's First AI Business Intelligence.
Get your free trial: ${refLink}`;

  const shareWA = () => {
    const url = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(url, '_blank', 'noopener');
  };
  const copyLink = async () => {
    try { await navigator.clipboard.writeText(message); setCopied(true); setTimeout(()=>setCopied(false), 2000); }
    catch { /* no clipboard */ }
  };

  return (
    <div data-testid="onb-referral-share" style={{
      background:'linear-gradient(135deg,rgba(74,222,128,0.08),rgba(212,175,55,0.06))',
      border:'1px solid rgba(74,222,128,0.25)',borderRadius:12,padding:16,textAlign:'left',
    }}>
      <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10}}>
        <Share2 size={16} color="#4ADE80"/>
        <div style={{fontSize:11,letterSpacing:'0.18em',color:'#4ADE80',fontWeight:700,textTransform:'uppercase'}}>Invite &amp; earn</div>
      </div>
      <p style={{fontSize:12.5,color:'#E8E0D0',lineHeight:1.6,marginBottom:12}}>
        Share AUREM with a business friend. When they subscribe, <strong style={{color:'#D4AF37'}}>you get one month free</strong>.
      </p>
      <div style={{background:'#08080F',border:'1px dashed rgba(255,255,255,0.08)',borderRadius:8,padding:'10px 12px',marginBottom:12,fontSize:11.5,color:'#A89E88',whiteSpace:'pre-line',lineHeight:1.55}}>
        {message}
      </div>
      <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
        <button data-testid="onb-share-whatsapp" onClick={shareWA} style={{
          display:'inline-flex',alignItems:'center',gap:6,padding:'9px 14px',background:'#25D366',border:'none',borderRadius:8,
          fontSize:11.5,fontWeight:700,letterSpacing:'0.06em',textTransform:'uppercase',color:'#0A0A00',cursor:'pointer',fontFamily:"'Jost',sans-serif",
        }}>
          <Share2 size={13}/> Share on WhatsApp
        </button>
        <button data-testid="onb-share-copy" onClick={copyLink} style={{
          display:'inline-flex',alignItems:'center',gap:6,padding:'9px 14px',background:'transparent',border:'1px solid rgba(212,175,55,0.3)',borderRadius:8,
          fontSize:11.5,fontWeight:700,letterSpacing:'0.06em',textTransform:'uppercase',color:'#D4AF37',cursor:'pointer',fontFamily:"'Jost',sans-serif",
        }}>
          <Copy size={13}/> {copied ? 'Copied!' : 'Copy Message'}
        </button>
      </div>
    </div>
  );
}

const title = { fontFamily:"'Cinzel',serif", fontSize:26, fontWeight:700, color:'#FFF', letterSpacing:'0.03em', margin:0 };
const sub = { fontSize:13, color:'#8A8070', marginBottom:24 };
const card = { background:'#0D0D17', border:'1px solid rgba(212,175,55,0.12)', borderRadius:14, padding:22 };
const sectionH = { fontFamily:"'Cinzel',serif", fontSize:14, fontWeight:700, color:'#D4AF37', letterSpacing:'0.1em', textTransform:'uppercase', margin:'0 0 14px' };
const labelS = { display:'block', fontSize:10, letterSpacing:'0.18em', textTransform:'uppercase', color:'#8A8070', fontWeight:600, marginBottom:5 };
const inputS = { width:'100%', padding:'10px 12px', background:'rgba(212,175,55,0.03)', border:'1px solid rgba(212,175,55,0.15)', borderRadius:8, color:'#E8E0D0', fontSize:13, fontFamily:"'Jost',sans-serif", outline:'none', boxSizing:'border-box' };
const primaryBtn = { display:'inline-flex',alignItems:'center',gap:8, padding:'10px 18px', background:'linear-gradient(135deg,#D4AF37,#B19A5E)', border:'none', borderRadius:9, fontSize:12, fontWeight:700, letterSpacing:'0.08em', textTransform:'uppercase', color:'#0A0A00', cursor:'pointer', fontFamily:"'Jost',sans-serif" };
const iconBtn = { padding:6, borderRadius:6, background:'transparent', border:'1px solid rgba(255,255,255,0.08)', color:'#8A8070', cursor:'pointer' };
