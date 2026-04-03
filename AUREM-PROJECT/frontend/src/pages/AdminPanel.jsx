import { useState, useRef, useEffect, useCallback, Component } from "react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import AdminLiveSupport from "../components/AdminLiveSupport";
import ProductSyncStatus from "../components/admin/ProductSyncStatus";
import AdminActionAI from "../components/admin/AdminActionAI";
import VoiceCallsDashboard from "../components/admin/VoiceCallsDashboard";
import AutoHealDashboard from "../components/admin/AutoHealDashboard";
import EmailCenter from "../components/admin/EmailCenter";
import ContentStudio from "../components/admin/ContentStudio";
import APIKeyManager from "../components/admin/APIKeyManager";
import CrashDashboard from "../components/admin/CrashDashboard";
import ComplianceMonitor from "../components/admin/ComplianceMonitor";
import SiteAuditDashboard from "../components/admin/SiteAuditDashboard";
import ProactiveOutreachDashboard from "../components/admin/ProactiveOutreachDashboard";
import CustomerAIInsights from "../components/admin/CustomerAIInsights";
import LanguageAnalytics from "../components/admin/LanguageAnalytics";
import PhoneManagement from "../components/admin/PhoneManagement";
import FraudDashboard from "../components/admin/FraudDashboard";

// Error Boundary to catch and display render errors
class AdminErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error, errorInfo) {
    console.error('AdminPanel Error:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', background: '#060608', color: '#f5f0e8', padding: 20, textAlign: 'center'
        }}>
          <h1 style={{ color: '#c9a86e', marginBottom: 16 }}>Admin Panel Error</h1>
          <p style={{ marginBottom: 16, opacity: 0.7 }}>Something went wrong loading the admin panel.</p>
          <p style={{ fontSize: 12, fontFamily: 'monospace', background: '#111', padding: 10, borderRadius: 8, maxWidth: 400 }}>
            {this.state.error?.message || 'Unknown error'}
          </p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              marginTop: 20, padding: '10px 20px', background: '#c9a86e', color: '#060608',
              border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ── API CONFIG ───────────────────────────────────────────────────────────── */
// Use production URL on reroots.ca, otherwise use env variable or origin
const getBaseUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // For localhost development
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    
    // For custom domains (reroots.ca, etc.) - ALWAYS use same origin
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    
    // For preview/staging environments
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};
const BASE_URL = getBaseUrl();
const getToken = () => localStorage.getItem("rr_token");

/* ── WhatsApp Low Stock Alert ─────────────────────────────────────────────── */
async function sendWhatsAppLowStockAlert(product, newStock) {
  try {
    const token = getToken();
    const message = `🚨 *LOW STOCK ALERT*\n\n📦 *${product.name}*\nSKU: ${product.sku}\n\n⚠️ Stock: ${newStock} units\n🎯 Reorder Point: ${product.reorder}\n\n_Action required: Restock soon to avoid stockouts._`;
    
    await fetch(`${BASE_URL}/api/whatsapp/send-alert`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message, alert_type: "low_stock", product_id: product.id })
    });
    console.log(`📱 WhatsApp alert sent for ${product.name}`);
  } catch (e) {
    console.log("WhatsApp alert skipped:", e.message);
  }
}

async function apiReq(method, path, body, isForm = false) {
  const token = getToken();
  const headers = isForm
    ? { Authorization: `Bearer ${token}` }
    : { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
  const res = await fetch(`${BASE_URL}${path}`, {
    method, headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });
  // Clone response to avoid "body stream already read" error
  const resClone = res.clone();
  try {
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || data?.message || `Error ${res.status}`);
    return data;
  } catch (parseError) {
    if (!res.ok) {
      const text = await resClone.text().catch(() => "");
      throw new Error(text || `Error ${res.status}`);
    }
    return {};
  }
}

async function uploadImage(base64, publicId = "") {
  const [header, b64data] = base64.split(",");
  const mime = header.match(/:(.*?);/)[1];
  const binary = atob(b64data);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  const blob = new Blob([arr], { type: mime });
  const fd = new FormData();
  fd.append("file", blob, `${publicId || "upload"}.${mime.split("/")[1]}`);
  if (publicId) fd.append("public_id", publicId);
  const res = await fetch(`${BASE_URL}/api/upload/image`, {
    method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: fd,
  });
  // Clone response to avoid "body stream already read" error
  const resClone = res.clone();
  try {
    const result = await res.json();
    if (!res.ok) throw new Error(result?.detail || "Upload failed");
    return result.url;
  } catch (parseError) {
    // If JSON parsing fails, try to get text from cloned response
    const text = await resClone.text().catch(() => "Unknown error");
    throw new Error(`Upload failed: ${text.substring(0, 100)}`);
  }
}

function normalizeProduct(p) {
  const stock = p.stock ?? 0;
  const reorder = p.reorder_point ?? p.reorder ?? 15;
  const status = stock <= 0 ? "Out" : stock < reorder * 0.7 ? "Critical" : stock <= reorder ? "Low" : "OK";
  return {
    id: p.id, name: p.name, subtitle: p.subtitle || "",
    sku: p.sku || "", price: p.price, cost: p.cost || 0,
    size: p.size || "", tag: p.tag || "",
    desc: p.description || p.desc || "",
    ingredients: p.ingredients || "",
    stock, reorder, batch: p.batch_code || p.batch || "",
    accent: p.accent_color || p.accent || "#6BAED6",
    accentDim: p.accent_dim || p.accentDim || "#2a4a6a",
    shape: p.bottle_shape || p.shape || "dropper",
    hue: p.background_hue || p.hue || "linear-gradient(160deg,#0a1020,#060c18)",
    image: p.image_url || p.image || null,
    images: p.images || p.gallery || [], // Multi-image gallery support
    rating: p.rating || 5.0, reviews: p.review_count || p.reviews || 0, status,
  };
}

function normalizeSubscriber(s) {
  return {
    id: s.id,
    name: s.name || `${s.first_name || ""} ${s.last_name || ""}`.trim(),
    email: s.email,
    skinType: s.skin_type || s.skinType || "",
    birthday: s.birthday || "",
    tier: s.tier || "Silver",
    offers: s.offers_opt_in ?? s.offers ?? true,
    signupDate: s.created_at ? new Date(s.created_at).toLocaleDateString("en-CA") : s.signupDate || "",
    status: (s.offers_opt_in ?? s.offers ?? true) ? "Active" : "Opted Out",
  };
}

const Styles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300&family=Tenor+Sans&display=swap');
    .rr-admin *{box-sizing:border-box;margin:0;padding:0;}
    .rr-admin ::-webkit-scrollbar{width:4px;}
    .rr-admin ::-webkit-scrollbar-thumb{background:rgba(201,168,110,0.18);border-radius:2px;}
    @keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    @keyframes shimmer{0%{background-position:-200% center}100%{background-position:200% center}}
    @keyframes pulse{0%,100%{opacity:.4}50%{opacity:1}}
    @keyframes floatBottle{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
    @keyframes slideIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
    @keyframes modalIn{from{opacity:0;transform:scale(0.96)}to{opacity:1;transform:scale(1)}}
    .rr-admin aside{width:200px!important;max-width:200px!important;overflow:hidden!important;}
    .rr-admin aside nav{width:100%!important;max-width:200px!important;}
    .rr-admin aside nav button{width:100%!important;max-width:200px!important;}
    .rr-admin .nav-item{transition:all .22s ease;border-left:2px solid transparent;}
    .rr-admin .nav-item:hover{background:rgba(201,168,110,0.05)!important;border-left-color:rgba(201,168,110,0.25)!important;}
    .rr-admin .nav-active{background:rgba(201,168,110,0.1)!important;border-left-color:#C9A86E!important;}
    .rr-admin .card{transition:border-color .3s,box-shadow .3s;}
    .rr-admin .card:hover{border-color:rgba(201,168,110,0.22)!important;box-shadow:0 8px 28px rgba(0,0,0,.4)!important;}
    .rr-admin .row-hover:hover{background:rgba(201,168,110,0.03)!important;}
    .rr-admin .btn{transition:all .22s cubic-bezier(.25,.46,.45,.94);cursor:pointer;}
    .rr-admin .btn:hover{opacity:.84;transform:translateY(-1px);}
    .rr-admin .inp{transition:border-color .22s,box-shadow .22s;}
    .rr-admin .inp:focus{border-color:rgba(201,168,110,0.5)!important;box-shadow:0 0 0 3px rgba(201,168,110,0.07)!important;}
    .rr-admin input,.rr-admin select,.rr-admin textarea{outline:none!important;}
    .rr-admin .upload-zone:hover{border-color:rgba(201,168,110,0.4)!important;background:rgba(201,168,110,0.04)!important;}
  `}</style>
);

const C={
  void:"#050507",noir:"#0b0b0e",surface:"#111116",card:"#18181f",lifted:"#1e1e27",
  border:"rgba(255,255,255,0.06)",borderGold:"rgba(201,168,110,0.18)",
  gold:"#C9A86E",goldBright:"#E2C98A",goldDeep:"#8A6B38",champagne:"#F5E8CC",
  text:"#EDE8DF",textSub:"#9A8E7E",textDim:"#524D45",
  green:"#5BB88A",red:"#C0614A",blue:"#6BAED6",purple:"#A88FD4",copper:"#C07A45",
};
const SERIF="'Cormorant Garamond',Georgia,serif";
const SANS="'Tenor Sans','Gill Sans',sans-serif";

/* ── SVG BOTTLES ─────────────────────────────────────────────────────────── */
const DropperBottle=({accent="#6BAED6",accentDim="#2a4a6a",size=100,label="TXA - PDRN",sub="AURA-GEN I"})=>(
  <svg width={size} height={size*160/140} viewBox="0 0 140 160" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="adb" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#1a2030"/><stop offset="50%" stopColor="#1e2840"/><stop offset="100%" stopColor="#111820"/></linearGradient>
      <linearGradient id="adc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={accentDim}/><stop offset="50%" stopColor={accent}/><stop offset="100%" stopColor={accentDim}/></linearGradient>
      <filter id="adg"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <radialGradient id="ada" cx="50%" cy="50%"><stop offset="0%" stopColor={accent} stopOpacity="0.2"/><stop offset="100%" stopColor={accent} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="70" cy="80" rx="60" ry="60" fill="url(#ada)"/>
    <ellipse cx="70" cy="150" rx="28" ry="6" fill={accent} opacity="0.1"/>
    <rect x="45" y="60" width="50" height="82" rx="7" fill="url(#adb)" stroke={accentDim} strokeWidth="0.6"/>
    <rect x="46" y="60" width="11" height="82" rx="5" fill="rgba(255,255,255,0.05)"/>
    <rect x="49" y="78" width="42" height="46" rx="2" fill={accent} opacity="0.07" stroke={accent} strokeWidth="0.3"/>
    <text x="70" y="96" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5.5" fill={accent} letterSpacing="2">{sub}</text>
    <line x1="56" y1="100" x2="84" y2="100" stroke={accent} strokeWidth="0.3" opacity="0.6"/>
    <text x="70" y="109" textAnchor="middle" fontFamily="Georgia,serif" fontSize="6.5" fill="rgba(255,255,255,0.85)">{label}</text>
    <line x1="56" y1="114" x2="84" y2="114" stroke={accent} strokeWidth="0.3" opacity="0.4"/>
    <text x="70" y="120" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="4" fill="rgba(255,255,255,0.3)" letterSpacing="1.5">REROOTS.CA</text>
    <rect x="57" y="44" width="26" height="19" rx="3" fill="#151e2e" stroke={accentDim} strokeWidth="0.5"/>
    <rect x="52" y="22" width="36" height="24" rx="5" fill="url(#adc)" opacity="0.95"/>
    <rect x="53" y="23" width="9" height="22" rx="4" fill="rgba(255,255,255,0.08)"/>
    <rect x="68" y="10" width="4" height="14" rx="2" fill={accentDim}/>
    <ellipse cx="70" cy="9" rx="4" ry="5" fill={accent} opacity="0.9" filter="url(#adg)"/>
    {[[35,70],[108,88],[32,108],[112,72],[36,128]].map(([x,y],i)=>(<circle key={i} cx={x} cy={y} r={1.2+i*0.2} fill={accent} opacity={0.15+i*0.04}/>))}
  </svg>
);
const JarProduct=({accent="#C9A86E",accentDim="#5a3e1a",size=100,label="ACCELERATOR",sub="AURA-GEN II"})=>(
  <svg width={size} height={size} viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="ajb" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#1c1208"/><stop offset="50%" stopColor="#221608"/><stop offset="100%" stopColor="#140e04"/></linearGradient>
      <linearGradient id="ajc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={accentDim}/><stop offset="50%" stopColor={accent}/><stop offset="100%" stopColor={accentDim}/></linearGradient>
      <radialGradient id="aja" cx="50%" cy="50%"><stop offset="0%" stopColor={accent} stopOpacity="0.16"/><stop offset="100%" stopColor={accent} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="80" cy="80" rx="65" ry="65" fill="url(#aja)"/>
    <ellipse cx="80" cy="150" rx="44" ry="7" fill={accent} opacity="0.1"/>
    <rect x="28" y="75" width="104" height="68" rx="9" fill="url(#ajb)" stroke={accentDim} strokeWidth="0.6"/>
    <rect x="29" y="75" width="18" height="68" rx="7" fill="rgba(255,255,255,0.04)"/>
    <rect x="36" y="86" width="88" height="46" rx="2" fill={accent} opacity="0.06" stroke={accent} strokeWidth="0.3"/>
    <text x="80" y="103" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5.5" fill={accent} letterSpacing="2">{sub}</text>
    <line x1="48" y1="107" x2="112" y2="107" stroke={accent} strokeWidth="0.3" opacity="0.6"/>
    <text x="80" y="118" textAnchor="middle" fontFamily="Georgia,serif" fontSize="7" fill="rgba(255,255,255,0.85)">{label}</text>
    <line x1="48" y1="123" x2="112" y2="123" stroke={accent} strokeWidth="0.3" opacity="0.4"/>
    <text x="80" y="129" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="4.5" fill="rgba(255,255,255,0.3)" letterSpacing="1.5">REROOTS.CA</text>
    <rect x="22" y="50" width="116" height="30" rx="8" fill="url(#ajc)" opacity="0.95"/>
    <rect x="23" y="51" width="22" height="28" rx="6" fill="rgba(255,255,255,0.07)"/>
    <text x="80" y="70" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5" fill="rgba(0,0,0,0.55)" letterSpacing="3">REROOTS</text>
    {[[22,92],[140,84],[20,116],[142,110]].map(([x,y],i)=>(<circle key={i} cx={x} cy={y} r={1.2+i*0.2} fill={accent} opacity={0.14+i*0.04}/>))}
  </svg>
);
const PumpBottle=({accent="#A88FD4",accentDim="#3a2a5a",size=100,label="RECOVERY",sub="AURA-GEN III"})=>(
  <svg width={size} height={size*160/140} viewBox="0 0 140 160" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="apb" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#0e0e1e"/><stop offset="50%" stopColor="#141426"/><stop offset="100%" stopColor="#0a0a14"/></linearGradient>
      <linearGradient id="apc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={accentDim}/><stop offset="50%" stopColor={accent}/><stop offset="100%" stopColor={accentDim}/></linearGradient>
      <filter id="apg"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <radialGradient id="apa" cx="50%" cy="50%"><stop offset="0%" stopColor={accent} stopOpacity="0.18"/><stop offset="100%" stopColor={accent} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="70" cy="80" rx="60" ry="60" fill="url(#apa)"/>
    <rect x="38" y="52" width="64" height="92" rx="12" fill="url(#apb)" stroke={accentDim} strokeWidth="0.6"/>
    <rect x="39" y="52" width="12" height="92" rx="8" fill="rgba(255,255,255,0.05)"/>
    <rect x="44" y="68" width="52" height="54" rx="2" fill={accent} opacity="0.06" stroke={accent} strokeWidth="0.3"/>
    <text x="70" y="85" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5.5" fill={accent} letterSpacing="2">{sub}</text>
    <line x1="52" y1="89" x2="88" y2="89" stroke={accent} strokeWidth="0.3" opacity="0.6"/>
    <text x="70" y="100" textAnchor="middle" fontFamily="Georgia,serif" fontSize="7" fill="rgba(255,255,255,0.85)">{label}</text>
    <line x1="52" y1="105" x2="88" y2="105" stroke={accent} strokeWidth="0.3" opacity="0.4"/>
    <text x="70" y="111" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="4.5" fill="rgba(255,255,255,0.3)" letterSpacing="1.5">REROOTS.CA</text>
    <rect x="60" y="34" width="20" height="22" rx="4" fill="#0d0d1a" stroke={accentDim} strokeWidth="0.5"/>
    <rect x="50" y="18" width="40" height="18" rx="6" fill="url(#apc)" opacity="0.95"/>
    <rect x="90" y="22" width="22" height="7" rx="3.5" fill={accentDim}/>
    <ellipse cx="113" cy="25.5" rx="3.5" ry="4.5" fill={accent} opacity="0.85" filter="url(#apg)"/>
    {[[28,70],[114,60],[26,100],[116,96]].map(([x,y],i)=>(<circle key={i} cx={x} cy={y} r={1.2+i*0.2} fill={accent} opacity={0.16+i*0.04}/>))}
  </svg>
);

const BottleFor=(p,size=80)=>{
  const nameL=p.name.split(" ")[0];
  const sub=p.subtitle||"AURA-GEN";
  if(p.shape==="dropper") return <DropperBottle accent={p.accent} accentDim={p.accentDim} size={size} label={nameL} sub={sub}/>;
  if(p.shape==="jar")     return <JarProduct    accent={p.accent} accentDim={p.accentDim} size={size} label={nameL} sub={sub}/>;
  return                         <PumpBottle    accent={p.accent} accentDim={p.accentDim} size={size} label={nameL} sub={sub}/>;
};

const ProductImg=({p,size=80})=>{
  if(p.image) return <img src={p.image} alt={p.name} style={{width:size,height:size,objectFit:"contain",borderRadius:6}}/>;
  return BottleFor(p,size);
};

/* ── HELPERS ─────────────────────────────────────────────────────────────── */
const GoldText=({children,size=16,weight=300,style:s})=>(
  <span style={{fontFamily:SERIF,fontSize:size,fontWeight:weight,
    background:`linear-gradient(105deg,${C.goldDeep},${C.goldBright} 45%,${C.gold} 65%,${C.goldBright})`,
    backgroundSize:"200% auto",WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",
    animation:"shimmer 4s linear infinite",...s}}>{children}</span>
);
const SL=({children,style:s})=>(<p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.22em",textTransform:"uppercase",color:C.textDim,...s}}>{children}</p>);
const Divider=({style:s})=>(
  <div style={{display:"flex",alignItems:"center",gap:10,...s}}>
    <div style={{flex:1,height:"0.5px",background:`linear-gradient(90deg,transparent,${C.goldDeep})`}}/>
    <div style={{width:3,height:3,borderRadius:"50%",background:C.gold,opacity:.5}}/>
    <div style={{flex:1,height:"0.5px",background:`linear-gradient(90deg,${C.goldDeep},transparent)`}}/>
  </div>
);
const Badge=({label,color,bg,border})=>(
  <span style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.12em",textTransform:"uppercase",
    padding:"3px 9px",borderRadius:2,color,background:bg,border:`0.5px solid ${border}`}}>{label}</span>
);
const StatCard=({label,value,sub,trend,color,delay=0})=>(
  <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:12,padding:"17px",
    animation:`fadeUp .5s ease ${delay}s both`,position:"relative",overflow:"hidden"}}>
    <div style={{position:"absolute",top:-20,right:-20,width:70,height:70,borderRadius:"50%",
      background:`radial-gradient(circle,${color}0a,transparent 70%)`}}/>
    <SL style={{marginBottom:9}}>{label}</SL>
    <p style={{fontFamily:SERIF,fontSize:24,fontWeight:300,color:C.text,lineHeight:1}}>{value}</p>
    {sub&&<p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:4}}>{sub}</p>}
    {trend!==undefined&&<p style={{fontFamily:SANS,fontSize:10,color:trend>=0?C.green:C.red,marginTop:5}}>
      {trend>=0?"↑":"↓"} {Math.abs(trend)}% vs last month</p>}
  </div>
);
const Ico=({n,size=18,color="currentColor",sw=1.3})=>{
  const d={
    dash:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    inv:<><path d="M20 7H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2zM16 3H8a2 2 0 00-2 2v2h12V5a2 2 0 00-2-2z"/></>,
    crm:<><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></>,
    orders:<><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="15" y2="11"/></>,
    accounting:<><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></>,
    ai:<><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></>,
    sub:<><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></>,
    support:<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><circle cx="12" cy="10" r="1"/><circle cx="8" cy="10" r="1"/><circle cx="16" cy="10" r="1"/></>,
    menu:<><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></>,
    bell:<><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"/></>,
    search:<><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>,
    warn:<><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></>,
    check:<polyline points="20,6 9,17 4,12"/>,
    edit:<><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></>,
    trash:<><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a1 1 0 011-1h4a1 1 0 011 1v2"/></>,
    plus:<><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>,
    img:<><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>,
    send:<><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></>,
    close:<><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    logo:<><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></>,
    offer:<><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></>,
    user:<><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z"/></>,
    copy:<><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></>,
    cart:<><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/></>,
    filter:<><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></>,
    gallery:<><rect x="3" y="3" width="18" height="18" rx="2"/><rect x="7" y="7" width="3" height="3" rx="0.5"/><rect x="14" y="7" width="3" height="3" rx="0.5"/><rect x="7" y="14" width="3" height="3" rx="0.5"/><rect x="14" y="14" width="3" height="3" rx="0.5"/></>,
    recover:<><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></>,
    trophy:<><path d="M6 9H4.5a2.5 2.5 0 010-5H6"/><path d="M18 9h1.5a2.5 2.5 0 000-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 1012 0V2Z"/></>,
    chart:<><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/><line x1="18" y1="20" x2="18" y2="16"/><line x1="14" y1="20" x2="14" y2="14"/><line x1="10" y1="20" x2="10" y2="18"/></>,
    share:<><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></>,
    external:<><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></>,
    sync:<><path d="M21.5 2v6h-6"/><path d="M2.5 22v-6h6"/><path d="M22 11.5A10 10 0 003.2 7.2"/><path d="M2 12.5a10 10 0 0018.8 4.3"/></>,
    terminal:<><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></>,
    phone:<><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></>,
    activity:<><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></>,
    mail:<><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></>,
    sparkles:<><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/><path d="M19 13l1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3z"/></>,
    key:<><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></>,
    shield:<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>,
    brain:<><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></>,
    globe:<><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">{d[n]}</svg>;
};
const CT=({active,payload,label})=>{
  if(!active||!payload?.length) return null;
  return(<div style={{background:C.lifted,border:`0.5px solid ${C.borderGold}`,borderRadius:8,padding:"9px 13px"}}>
    <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginBottom:4}}>{label}</p>
    {payload.map((p,i)=>(<p key={i} style={{fontFamily:SERIF,fontSize:13,color:p.color,fontWeight:300}}>
      {p.name==="rev"?"CA$":""}{typeof p.value==="number"?p.value.toLocaleString():p.value}</p>))}
  </div>);
};

/* ── DATA ────────────────────────────────────────────────────────────────── */
const INIT_PRODUCTS=[
  {id:1,name:"TXA + PDRN Serum",subtitle:"AURA-GEN I",price:89.99,size:"30 ml",sku:"AG-SER-001",tag:"Bestseller",
   desc:"Triple-penetration architecture. 5% TXA fused with 2% bio-active PDRN and Argireline complex.",
   ingredients:"PDRN 2%, TXA 5%, Argireline 3%, DMI, Liposomal Ceramide",
   stock:24,reorder:20,cost:28.50,rating:4.9,reviews:187,status:"Low",batch:"B2024-11",
   accent:C.blue,accentDim:"#2a4a6a",shape:"dropper",hue:"linear-gradient(160deg,#0a1020,#060c18)",image:null},
  {id:2,name:"Accelerator Rich Cream",subtitle:"AURA-GEN II",price:74.99,size:"50 ml",sku:"AG-CRM-002",tag:"New Formula",
   desc:"v4 corrected HLB emulsification. Barrier-restoring peptide matrix with multi-weight Hyaluronic Acid.",
   ingredients:"Niacinamide 4%, HA 1.5%, Peptide Complex, Shea, Ceramide NP",
   stock:18,reorder:15,cost:22.00,rating:4.8,reviews:94,status:"OK",batch:"B2024-11",
   accent:C.gold,accentDim:"#5a3e1a",shape:"jar",hue:"linear-gradient(160deg,#160f06,#0d0a04)",image:null},
  {id:3,name:"Active Recovery Complex",subtitle:"AURA-GEN III",price:99.99,size:"30 ml",sku:"AG-REC-003",tag:"Clinical",
   desc:"17% active concentration. Post-procedure intensive repair with EGF acceleration and Centella.",
   ingredients:"TXA 7%, PDRN 3%, Retinol 0.3%, EGF, Centella",
   stock:11,reorder:15,cost:34.00,rating:4.95,reviews:52,status:"Critical",batch:"B2024-10",
   accent:C.purple,accentDim:"#3a2a5a",shape:"pump",hue:"linear-gradient(160deg,#0a0a18,#060610)",image:null},
];
const INIT_SUBS=[
  {id:"S001",name:"Sophie Laurent",email:"sophie@example.com",skinType:"Dry",birthday:"1991-03-15",offers:true,tier:"Elite",signupDate:"2024-08-12",status:"Active"},
  {id:"S002",name:"Aria Chen",email:"aria@example.com",skinType:"Combination",birthday:"1996-07-22",offers:true,tier:"Diamond",signupDate:"2024-09-04",status:"Active"},
  {id:"S003",name:"Marcus Webb",email:"marcus@example.com",skinType:"Oily",birthday:"",offers:true,tier:"Gold",signupDate:"2024-10-18",status:"Active"},
  {id:"S004",name:"Priya Nair",email:"priya@example.com",skinType:"Sensitive",birthday:"1989-01-30",offers:false,tier:"Gold",signupDate:"2024-11-02",status:"Opted Out"},
  {id:"S005",name:"James Osei",email:"james@example.com",skinType:"Normal",birthday:"",offers:true,tier:"Silver",signupDate:"2025-01-09",status:"Active"},
];
const revenueData=[
  {m:"Oct",rev:4200},{m:"Nov",rev:6800},{m:"Dec",rev:11200},{m:"Jan",rev:8900},{m:"Feb",rev:9400},{m:"Mar",rev:12800},
];
const pieData=[{name:"Serum",value:187},{name:"Cream",value:94},{name:"Recovery",value:52}];
const PIE_COLORS=[C.blue,C.gold,C.purple];
const CRM_DATA=[
  {id:"C001",name:"Sophie Laurent",tier:"Elite",ltv:3210,orders:38,last:"1d ago",status:"Active",score:99},
  {id:"C002",name:"Aria Chen",tier:"Diamond",ltv:1284,orders:16,last:"2d ago",status:"Active",score:98},
  {id:"C003",name:"Marcus Webb",tier:"Gold",ltv:742,orders:9,last:"5d ago",status:"Active",score:82},
  {id:"C004",name:"Priya Nair",tier:"Gold",ltv:624,orders:7,last:"12d ago",status:"Active",score:74},
  {id:"C005",name:"James Osei",tier:"Silver",ltv:289,orders:4,last:"3w ago",status:"At Risk",score:41},
];
const ORDERS_DATA=[
  {id:"RR-20248",customer:"Sophie Laurent",productId:3,date:"Mar 09",total:99.99,status:"Processing",payment:"Stripe"},
  {id:"RR-20247",customer:"Aria Chen",productId:1,date:"Mar 08",total:89.99,status:"Shipped",payment:"PayPal"},
  {id:"RR-20246",customer:"Marcus Webb",productId:2,date:"Mar 07",total:74.99,status:"Delivered",payment:"Stripe"},
  {id:"RR-20245",customer:"Priya Nair",productId:1,date:"Mar 07",total:89.99,status:"Processing",payment:"Stripe"},
  {id:"RR-20244",customer:"James Osei",productId:2,date:"Mar 06",total:74.99,status:"Delivered",payment:"PayPal"},
];
const ACCOUNTING=[
  {date:"Mar 09",desc:"Sophie Laurent - RR-20248",type:"Revenue",amount:+99.99,cat:"Sales"},
  {date:"Mar 08",desc:"Aria Chen - RR-20247",type:"Revenue",amount:+89.99,cat:"Sales"},
  {date:"Mar 07",desc:"FlagShip Courier",type:"Expense",amount:-184.20,cat:"Shipping"},
  {date:"Mar 06",desc:"Cloudinary CDN",type:"Expense",amount:-29.00,cat:"Infrastructure"},
  {date:"Mar 05",desc:"RR-20243 Refund",type:"Refund",amount:-99.99,cat:"Refund"},
  {date:"Mar 04",desc:"Twilio SMS",type:"Expense",amount:-14.80,cat:"Infrastructure"},
  {date:"Mar 02",desc:"Marcus Webb",type:"Revenue",amount:+74.99,cat:"Sales"},
];

/* ══ MAIN SCREENS ═══════════════════════════════════════════════════════════ */

/* ── LOW STOCK ALERTS WIDGET ─────────────────────────────────────────────── */
const LowStockAlerts=({products,onQuickAdjust})=>{
  const lowStock=products.filter(p=>p.status==="Critical"||p.status==="Low"||p.status==="Out");
  if(lowStock.length===0) return null;
  
  return(
    <div className="card" style={{background:`linear-gradient(135deg,${C.red}08,${C.copper}05)`,border:`0.5px solid ${C.red}33`,borderRadius:13,padding:"18px",marginBottom:20,animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{width:32,height:32,borderRadius:"50%",background:`${C.red}22`,border:`0.5px solid ${C.red}44`,display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Ico n="warn" size={16} color={C.red}/>
          </div>
          <div>
            <p style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:C.text}}>Low Stock <span style={{color:C.red}}>Alert</span></p>
            <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:2}}>{lowStock.length} product{lowStock.length>1?"s":""} need attention</p>
          </div>
        </div>
        <Badge label="ACTION REQUIRED" color={C.red} bg={`${C.red}18`} border={`${C.red}44`}/>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))",gap:10}}>
        {lowStock.slice(0,6).map(p=>(
          <div key={p.id} style={{background:C.card,border:`0.5px solid ${p.status==="Out"?C.red:p.status==="Critical"?C.red:C.copper}33`,borderRadius:10,padding:"12px",display:"flex",alignItems:"center",gap:10}}>
            <div style={{flexShrink:0,background:p.hue,borderRadius:6,padding:2}}><ProductImg p={p} size={36}/></div>
            <div style={{flex:1,minWidth:0}}>
              <p style={{fontFamily:SERIF,fontSize:12,color:C.text,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{p.name}</p>
              <div style={{display:"flex",alignItems:"center",gap:6,marginTop:4}}>
                <span style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:p.status==="Out"?C.red:p.status==="Critical"?C.red:C.copper}}>{p.stock}</span>
                <Badge label={p.status} color={p.status==="Out"?C.red:p.status==="Critical"?C.red:C.copper} bg={`${p.status==="Out"?C.red:p.status==="Critical"?C.red:C.copper}15`} border={`${p.status==="Out"?C.red:p.status==="Critical"?C.red:C.copper}33`}/>
              </div>
            </div>
            <button onClick={()=>onQuickAdjust(p)} className="btn" style={{background:`${C.gold}18`,border:`0.5px solid ${C.borderGold}`,borderRadius:6,padding:"6px 10px",fontFamily:SANS,fontSize:8,letterSpacing:"0.08em",color:C.gold}}>
              +STOCK
            </button>
          </div>
        ))}
      </div>
      {lowStock.length>6&&<p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:10,textAlign:"center"}}>+{lowStock.length-6} more items need restocking</p>}
    </div>
  );
};

/* ── BULK STOCK UPDATE MODAL ─────────────────────────────────────────────── */
function BulkStockModal({product,onClose,onSave}){
  const [delta,setDelta]=useState(0);
  const [saving,setSaving]=useState(false);
  const [reason,setReason]=useState("restock");
  const inputRef=useRef(null);
  
  const newStock=Math.max(0,product.stock+delta);
  const willTriggerAlert=newStock<=product.reorder&&product.stock>product.reorder;
  
  useEffect(()=>{
    inputRef.current?.focus();
    const handleKey=(e)=>{
      if(e.key==="Escape") onClose();
      if(e.key==="Enter"&&!e.shiftKey) doSave();
    };
    window.addEventListener("keydown",handleKey);
    return ()=>window.removeEventListener("keydown",handleKey);
  },[]);
  
  const doSave=async()=>{
    if(delta===0) return onClose();
    setSaving(true);
    try{
      await apiReq("PUT",`/api/products/${product.id}`,{stock:newStock});
      
      // Trigger WhatsApp alert if stock hits reorder point
      if(newStock<=product.reorder&&newStock>0){
        await sendWhatsAppLowStockAlert(product,newStock);
      }
      
      onSave();
    }catch(e){
      alert("Update failed: "+e.message);
    }finally{setSaving(false);}
  };
  
  const presets=[+10,+25,+50,+100];
  
  return(
    <div style={{position:"fixed",inset:0,background:"rgba(5,5,7,0.9)",zIndex:2000,display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(16px)"}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:C.card,border:`0.5px solid ${C.borderGold}`,borderRadius:20,width:"100%",maxWidth:400,animation:"modalIn 0.25s ease both",boxShadow:"0 32px 80px rgba(0,0,0,0.6)"}}>
        <div style={{padding:"20px 24px",borderBottom:`0.5px solid ${C.border}`,display:"flex",alignItems:"center",gap:14}}>
          <div style={{background:product.hue,borderRadius:10,padding:6}}><ProductImg p={product} size={48}/></div>
          <div>
            <SL style={{marginBottom:4}}>Quick Stock Adjust</SL>
            <p style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:C.text}}>{product.name}</p>
          </div>
        </div>
        <div style={{padding:"24px"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:20,marginBottom:24}}>
            <button onClick={()=>setDelta(d=>d-10)} className="btn" style={{width:48,height:48,borderRadius:"50%",background:C.surface,border:`0.5px solid ${C.border}`,fontFamily:SERIF,fontSize:20,color:C.text}}>-10</button>
            <button onClick={()=>setDelta(d=>d-1)} className="btn" style={{width:40,height:40,borderRadius:"50%",background:C.surface,border:`0.5px solid ${C.border}`,fontFamily:SERIF,fontSize:18,color:C.text}}>-</button>
            <div style={{textAlign:"center",minWidth:80}}>
              <input ref={inputRef} type="number" value={delta} onChange={e=>setDelta(parseInt(e.target.value)||0)}
                style={{width:80,background:"transparent",border:"none",fontFamily:SERIF,fontSize:36,fontWeight:300,color:delta>0?C.green:delta<0?C.red:C.text,textAlign:"center"}}/>
              <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:2}}>{delta>0?"+":""}{delta} units</p>
            </div>
            <button onClick={()=>setDelta(d=>d+1)} className="btn" style={{width:40,height:40,borderRadius:"50%",background:C.surface,border:`0.5px solid ${C.border}`,fontFamily:SERIF,fontSize:18,color:C.text}}>+</button>
            <button onClick={()=>setDelta(d=>d+10)} className="btn" style={{width:48,height:48,borderRadius:"50%",background:C.surface,border:`0.5px solid ${C.border}`,fontFamily:SERIF,fontSize:20,color:C.text}}>+10</button>
          </div>
          
          <div style={{display:"flex",gap:8,justifyContent:"center",marginBottom:20}}>
            {presets.map(n=>(
              <button key={n} onClick={()=>setDelta(n)} className="btn" style={{padding:"8px 14px",background:delta===n?`${C.green}22`:C.surface,border:`0.5px solid ${delta===n?C.green:C.border}`,borderRadius:6,fontFamily:SANS,fontSize:10,color:delta===n?C.green:C.textSub}}>+{n}</button>
            ))}
          </div>
          
          <div style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:12,padding:"16px",marginBottom:20}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:10}}>
              <span style={{fontFamily:SANS,fontSize:10,color:C.textDim}}>Current Stock</span>
              <span style={{fontFamily:SERIF,fontSize:14,color:C.textSub}}>{product.stock}</span>
            </div>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:10}}>
              <span style={{fontFamily:SANS,fontSize:10,color:C.textDim}}>Change</span>
              <span style={{fontFamily:SERIF,fontSize:14,color:delta>0?C.green:delta<0?C.red:C.textDim}}>{delta>0?"+":""}{delta}</span>
            </div>
            <div style={{height:"0.5px",background:C.border,margin:"10px 0"}}/>
            <div style={{display:"flex",justifyContent:"space-between"}}>
              <span style={{fontFamily:SANS,fontSize:10,color:C.gold}}>New Stock</span>
              <span style={{fontFamily:SERIF,fontSize:20,fontWeight:300,color:newStock<=product.reorder?C.copper:C.green}}>{newStock}</span>
            </div>
          </div>
          
          {willTriggerAlert&&(
            <div style={{background:`${C.copper}12`,border:`0.5px solid ${C.copper}33`,borderRadius:8,padding:"10px 14px",marginBottom:16,display:"flex",alignItems:"center",gap:10}}>
              <Ico n="warn" size={16} color={C.copper}/>
              <p style={{fontFamily:SANS,fontSize:10,color:C.copper}}>This will trigger a low stock WhatsApp alert</p>
            </div>
          )}
          
          <div style={{display:"flex",gap:10}}>
            <button onClick={onClose} className="btn" style={{flex:1,padding:"14px",background:"transparent",border:`0.5px solid ${C.border}`,borderRadius:8,fontFamily:SANS,fontSize:10,letterSpacing:"0.12em",color:C.textDim}}>CANCEL</button>
            <button onClick={doSave} disabled={saving||delta===0} className="btn" style={{flex:2,padding:"14px",background:delta!==0?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,border:"none",borderRadius:8,fontFamily:SANS,fontSize:10,letterSpacing:"0.12em",color:delta!==0?C.void:C.textDim}}>
              {saving?"UPDATING...":"UPDATE STOCK"}
            </button>
          </div>
          <p style={{fontFamily:SANS,fontSize:8,color:C.textDim,textAlign:"center",marginTop:12}}>Press Enter to save • Esc to cancel</p>
        </div>
      </div>
    </div>
  );
}

const Dashboard=({products,onQuickAdjust})=>(
  <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
    <div style={{marginBottom:22}}>
      <SL>Overview</SL>
      <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Business <GoldText size={26}>Intelligence</GoldText></h2>
    </div>
    
    {/* Low Stock Alerts Widget */}
    <LowStockAlerts products={products} onQuickAdjust={onQuickAdjust}/>
    
    <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:13,marginBottom:22}}>
      {products.slice(0,9).map((p,i)=>(
        <div key={p.id} className="card" style={{background:p.hue,border:`0.5px solid ${p.accent}22`,borderRadius:13,padding:"18px",
          display:"flex",alignItems:"center",gap:13,animation:`fadeUp .5s ease ${i*0.08}s both`,position:"relative",overflow:"hidden"}}>
          <div style={{position:"absolute",inset:0,background:`radial-gradient(circle at 80% 50%,${p.accent}12,transparent 60%)`}}/>
          <div style={{flexShrink:0,animation:"floatBottle 3s ease-in-out infinite"}}><ProductImg p={p} size={60}/></div>
          <div>
            <SL style={{color:p.accent,marginBottom:4}}>{p.subtitle}</SL>
            <p style={{fontFamily:SERIF,fontSize:13,color:C.text,lineHeight:1.2}}>{p.name}</p>
            <p style={{fontFamily:SERIF,fontSize:18,fontWeight:300,color:p.accent,marginTop:5}}>{"CA$"}{p.price}</p>
            <p style={{fontFamily:SANS,fontSize:9,color:p.status==="Critical"?C.red:p.status==="Low"?C.copper:C.green,marginTop:3}}>* {p.stock} units - {p.status}</p>
          </div>
        </div>
      ))}
    </div>
    <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:11,marginBottom:20}}>
      <StatCard label="Revenue MTD" value="CA$12,800" sub="137 orders" trend={+36} color={C.gold} delay={0}/>
      <StatCard label="Active Customers" value="284" sub="47 VIP" trend={+12} color={C.blue} delay={.05}/>
      <StatCard label="Avg Order Value" value="CA$93.4" sub="Per order" trend={+8} color={C.green} delay={.1}/>
      <StatCard label="Refund Rate" value="1.2%" sub="Industry 3.1%" color={C.copper} delay={.15}/>
    </div>
    <div style={{display:"grid",gridTemplateColumns:"2fr 1fr",gap:13,marginBottom:20}}>
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"18px"}}>
        <div style={{display:"flex",justifyContent:"space-between",marginBottom:16}}>
          <div><SL style={{marginBottom:4}}>Revenue Trend</SL><p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>6-Month</p></div>
          <GoldText size={18} weight={300}>CA$53,300</GoldText>
        </div>
        <ResponsiveContainer width="100%" height={130}>
          <AreaChart data={revenueData} margin={{top:4,right:4,left:-20,bottom:0}}>
            <defs><linearGradient id="rg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={C.gold} stopOpacity={0.2}/><stop offset="95%" stopColor={C.gold} stopOpacity={0}/>
            </linearGradient></defs>
            <XAxis dataKey="m" tick={{fontFamily:SANS,fontSize:9,fill:C.textDim}} axisLine={false} tickLine={false}/>
            <YAxis tick={{fontFamily:SANS,fontSize:9,fill:C.textDim}} axisLine={false} tickLine={false} tickFormatter={v=>`$${v/1000}k`}/>
            <Tooltip content={<CT/>}/>
            <Area type="monotone" dataKey="rev" name="rev" stroke={C.gold} strokeWidth={1.5} fill="url(#rg)"/>
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"18px"}}>
        <SL style={{marginBottom:4}}>Sales Mix</SL>
        <p style={{fontFamily:SERIF,fontSize:14,color:C.text,marginBottom:12}}>By Product</p>
        <ResponsiveContainer width="100%" height={90}>
          <PieChart><Pie data={pieData} cx="50%" cy="50%" innerRadius={24} outerRadius={42} paddingAngle={3} dataKey="value">
            {pieData.map((_,i)=><Cell key={i} fill={PIE_COLORS[i]}/>)}
          </Pie><Tooltip content={<CT/>}/></PieChart>
        </ResponsiveContainer>
        <div style={{display:"flex",flexDirection:"column",gap:4,marginTop:6}}>
          {pieData.map((d,i)=>(<div key={d.name} style={{display:"flex",justifyContent:"space-between"}}>
            <div style={{display:"flex",alignItems:"center",gap:6}}><div style={{width:5,height:5,borderRadius:"50%",background:PIE_COLORS[i]}}/><span style={{fontFamily:SANS,fontSize:9,color:C.textSub}}>{d.name}</span></div>
            <span style={{fontFamily:SERIF,fontSize:12,color:C.text}}>{d.value}</span>
          </div>))}
        </div>
      </div>
    </div>
  </div>
);

/* ══ PRODUCT PERFORMANCE RANKING ═══════════════════════════════════════════ */
const ProductPerformance=({products})=>{
  const [sortBy,setSortBy]=useState("revenue");
  const [timeRange,setTimeRange]=useState("30d");
  
  // Calculate performance metrics for each product (mock data - would come from orders API)
  const getProductMetrics=(p)=>{
    // Mock performance data based on product properties
    const baseRevenue=p.price*(30-products.indexOf(p)*2+Math.random()*10);
    const unitsSold=Math.floor(baseRevenue/p.price);
    const margin=((p.price-p.cost)/p.price)*100;
    const velocity=unitsSold/4; // units per week
    const trend=Math.random()>0.3?Math.floor(Math.random()*30)+5:-Math.floor(Math.random()*15);
    
    return {
      ...p,
      revenue:Math.floor(baseRevenue),
      unitsSold,
      margin:margin.toFixed(1),
      velocity:velocity.toFixed(1),
      trend,
      score:Math.floor(baseRevenue/100+margin+velocity*2),
    };
  };
  
  const productsWithMetrics=products.map(getProductMetrics);
  
  // Sort products by selected metric
  const sortedProducts=[...productsWithMetrics].sort((a,b)=>{
    if(sortBy==="revenue") return b.revenue-a.revenue;
    if(sortBy==="margin") return parseFloat(b.margin)-parseFloat(a.margin);
    if(sortBy==="velocity") return parseFloat(b.velocity)-parseFloat(a.velocity);
    return b.score-a.score;
  });
  
  const top3=sortedProducts.slice(0,3);
  const rest=sortedProducts.slice(3);
  
  const medalColors=["#FFD700","#C0C0C0","#CD7F32"];
  const sortOptions=[
    {id:"revenue",label:"Revenue",icon:"accounting"},
    {id:"margin",label:"Margin %",icon:"accounting"},
    {id:"velocity",label:"Velocity",icon:"orders"},
  ];
  
  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:22}}>
        <div>
          <SL>Analytics</SL>
          <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Product <GoldText size={26}>Performance</GoldText></h2>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{display:"flex",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,overflow:"hidden"}}>
            {["7d","30d","90d"].map(t=>(
              <button key={t} onClick={()=>setTimeRange(t)} className="btn" style={{
                padding:"8px 14px",background:timeRange===t?`${C.gold}15`:"transparent",
                border:"none",borderRight:`0.5px solid ${C.border}`,
                fontFamily:SANS,fontSize:9,letterSpacing:"0.08em",color:timeRange===t?C.gold:C.textDim
              }}>{t.toUpperCase()}</button>
            ))}
          </div>
        </div>
      </div>
      
      {/* Sort Tabs */}
      <div style={{display:"flex",gap:10,marginBottom:22}}>
        {sortOptions.map(opt=>(
          <button key={opt.id} onClick={()=>setSortBy(opt.id)} data-testid={`sort-${opt.id}`} className="btn" style={{
            flex:1,padding:"14px 18px",background:sortBy===opt.id?`linear-gradient(135deg,${C.goldDeep}22,${C.gold}11)`:C.card,
            border:`0.5px solid ${sortBy===opt.id?C.gold:C.border}`,borderRadius:10,
            display:"flex",alignItems:"center",justifyContent:"center",gap:10
          }}>
            <div style={{width:32,height:32,borderRadius:"50%",background:sortBy===opt.id?`${C.gold}22`:C.surface,
              display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Ico n={opt.icon} size={14} color={sortBy===opt.id?C.gold:C.textDim}/>
            </div>
            <div style={{textAlign:"left"}}>
              <p style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.12em",color:sortBy===opt.id?C.gold:C.textDim,marginBottom:2}}>RANK BY</p>
              <p style={{fontFamily:SERIF,fontSize:14,color:sortBy===opt.id?C.text:C.textSub}}>{opt.label}</p>
            </div>
          </button>
        ))}
      </div>
      
      {/* Top 3 Podium */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1.3fr 1fr",gap:14,marginBottom:22,alignItems:"flex-end"}}>
        {/* 2nd Place */}
        <div className="card" style={{background:`linear-gradient(160deg,${C.card},${medalColors[1]}08)`,border:`0.5px solid ${medalColors[1]}33`,
          borderRadius:13,padding:"18px",textAlign:"center",animation:"fadeUp .5s ease .1s both"}}>
          <div style={{width:36,height:36,borderRadius:"50%",background:`${medalColors[1]}22`,border:`2px solid ${medalColors[1]}`,
            display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto 12px",
            fontFamily:SERIF,fontSize:16,color:medalColors[1]}}>2</div>
          <div style={{background:top3[1]?.hue||C.surface,borderRadius:10,padding:10,marginBottom:12}}>
            <ProductImg p={top3[1]} size={60}/>
          </div>
          <p style={{fontFamily:SERIF,fontSize:13,color:C.text,marginBottom:4}}>{top3[1]?.name}</p>
          <p style={{fontFamily:SERIF,fontSize:22,fontWeight:300,color:medalColors[1]}}>
            {sortBy==="revenue"?`CA$${top3[1]?.revenue}`:sortBy==="margin"?`${top3[1]?.margin}%`:`${top3[1]?.velocity}/wk`}
          </p>
          <Badge label={top3[1]?.trend>0?`+${top3[1]?.trend}%`:`${top3[1]?.trend}%`} 
            color={top3[1]?.trend>0?C.green:C.red} bg={`${top3[1]?.trend>0?C.green:C.red}15`} border={`${top3[1]?.trend>0?C.green:C.red}33`}/>
        </div>
        
        {/* 1st Place */}
        <div className="card" style={{background:`linear-gradient(160deg,${C.card},${medalColors[0]}12)`,border:`0.5px solid ${medalColors[0]}44`,
          borderRadius:13,padding:"22px",textAlign:"center",animation:"fadeUp .5s ease both",
          boxShadow:`0 8px 32px ${medalColors[0]}15`}}>
          <div style={{width:44,height:44,borderRadius:"50%",background:`linear-gradient(135deg,${medalColors[0]},${C.goldDeep})`,
            border:`2px solid ${medalColors[0]}`,display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto 14px",
            fontFamily:SERIF,fontSize:20,color:C.void,boxShadow:`0 4px 16px ${medalColors[0]}44`}}>1</div>
          <div style={{background:top3[0]?.hue||C.surface,borderRadius:12,padding:14,marginBottom:14}}>
            <div style={{animation:"floatBottle 3s ease-in-out infinite"}}><ProductImg p={top3[0]} size={80}/></div>
          </div>
          <p style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",color:C.gold,marginBottom:4}}>TOP PERFORMER</p>
          <p style={{fontFamily:SERIF,fontSize:16,color:C.text,marginBottom:6}}>{top3[0]?.name}</p>
          <p style={{fontFamily:SERIF,fontSize:32,fontWeight:300,color:medalColors[0]}}>
            {sortBy==="revenue"?`CA$${top3[0]?.revenue}`:sortBy==="margin"?`${top3[0]?.margin}%`:`${top3[0]?.velocity}/wk`}
          </p>
          <Badge label={top3[0]?.trend>0?`+${top3[0]?.trend}%`:`${top3[0]?.trend}%`} 
            color={top3[0]?.trend>0?C.green:C.red} bg={`${top3[0]?.trend>0?C.green:C.red}15`} border={`${top3[0]?.trend>0?C.green:C.red}33`}/>
        </div>
        
        {/* 3rd Place */}
        <div className="card" style={{background:`linear-gradient(160deg,${C.card},${medalColors[2]}08)`,border:`0.5px solid ${medalColors[2]}33`,
          borderRadius:13,padding:"18px",textAlign:"center",animation:"fadeUp .5s ease .2s both"}}>
          <div style={{width:36,height:36,borderRadius:"50%",background:`${medalColors[2]}22`,border:`2px solid ${medalColors[2]}`,
            display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto 12px",
            fontFamily:SERIF,fontSize:16,color:medalColors[2]}}>3</div>
          <div style={{background:top3[2]?.hue||C.surface,borderRadius:10,padding:10,marginBottom:12}}>
            <ProductImg p={top3[2]} size={60}/>
          </div>
          <p style={{fontFamily:SERIF,fontSize:13,color:C.text,marginBottom:4}}>{top3[2]?.name}</p>
          <p style={{fontFamily:SERIF,fontSize:22,fontWeight:300,color:medalColors[2]}}>
            {sortBy==="revenue"?`CA$${top3[2]?.revenue}`:sortBy==="margin"?`${top3[2]?.margin}%`:`${top3[2]?.velocity}/wk`}
          </p>
          <Badge label={top3[2]?.trend>0?`+${top3[2]?.trend}%`:`${top3[2]?.trend}%`} 
            color={top3[2]?.trend>0?C.green:C.red} bg={`${top3[2]?.trend>0?C.green:C.red}15`} border={`${top3[2]?.trend>0?C.green:C.red}33`}/>
        </div>
      </div>
      
      {/* Performance Comparison Chart */}
      <div style={{display:"grid",gridTemplateColumns:"2fr 1fr",gap:14,marginBottom:22}}>
        <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"18px"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
            <div>
              <SL style={{marginBottom:4}}>Performance Comparison</SL>
              <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>All Products</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={sortedProducts.slice(0,8)} margin={{top:4,right:4,left:-20,bottom:0}}>
              <XAxis dataKey="name" tick={{fontFamily:SANS,fontSize:8,fill:C.textDim}} axisLine={false} tickLine={false}
                tickFormatter={n=>n.length>12?n.slice(0,12)+"...":n}/>
              <YAxis tick={{fontFamily:SANS,fontSize:9,fill:C.textDim}} axisLine={false} tickLine={false}
                tickFormatter={v=>sortBy==="revenue"?`$${v}`:sortBy==="margin"?`${v}%`:v}/>
              <Tooltip content={<CT/>}/>
              <Bar dataKey={sortBy==="revenue"?"revenue":sortBy==="margin"?"margin":"velocity"} 
                fill={C.gold} radius={[4,4,0,0]}>
                {sortedProducts.slice(0,8).map((p,i)=>(
                  <Cell key={p.id} fill={i<3?medalColors[i]:C.blue}/>
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        {/* Key Insights */}
        <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"18px"}}>
          <SL style={{marginBottom:4}}>Key Insights</SL>
          <p style={{fontFamily:SERIF,fontSize:14,color:C.text,marginBottom:14}}>Performance Summary</p>
          
          <div style={{display:"flex",flexDirection:"column",gap:12}}>
            <div style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,padding:"12px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Total Revenue</span>
                <span style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:C.gold}}>
                  CA${productsWithMetrics.reduce((s,p)=>s+p.revenue,0).toLocaleString()}
                </span>
              </div>
            </div>
            <div style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,padding:"12px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Avg Margin</span>
                <span style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:C.green}}>
                  {(productsWithMetrics.reduce((s,p)=>s+parseFloat(p.margin),0)/productsWithMetrics.length).toFixed(1)}%
                </span>
              </div>
            </div>
            <div style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,padding:"12px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Units/Week</span>
                <span style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:C.blue}}>
                  {productsWithMetrics.reduce((s,p)=>s+parseFloat(p.velocity),0).toFixed(0)}
                </span>
              </div>
            </div>
            <div style={{background:`${C.gold}08`,border:`0.5px solid ${C.borderGold}`,borderRadius:8,padding:"12px"}}>
              <p style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.1em",color:C.gold,marginBottom:6}}>RECOMMENDATION</p>
              <p style={{fontFamily:SERIF,fontSize:11,color:C.text,lineHeight:1.5}}>
                Focus marketing on <span style={{color:C.gold}}>{top3[0]?.name}</span> - highest {sortBy} with strong momentum.
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Full Rankings Table */}
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
        <div style={{padding:"14px 20px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>Complete Rankings</p>
          <Badge label={`Sorted by ${sortBy}`} color={C.gold} bg={`${C.gold}15`} border={`${C.gold}33`}/>
        </div>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
            {["Rank","Product","Revenue","Margin","Velocity","Trend","Score"].map(h=>(
              <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {sortedProducts.map((p,i)=>(
              <tr key={p.id} className="row-hover" style={{borderBottom:i<sortedProducts.length-1?`0.5px solid ${C.border}`:"none"}}>
                <td style={{padding:"12px 14px"}}>
                  <div style={{width:28,height:28,borderRadius:"50%",
                    background:i<3?`${medalColors[i]}22`:C.surface,
                    border:`1.5px solid ${i<3?medalColors[i]:C.border}`,
                    display:"flex",alignItems:"center",justifyContent:"center",
                    fontFamily:SERIF,fontSize:12,color:i<3?medalColors[i]:C.textDim}}>{i+1}</div>
                </td>
                <td style={{padding:"12px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:10}}>
                    <div style={{flexShrink:0,background:p.hue,borderRadius:6,padding:2}}><ProductImg p={p} size={32}/></div>
                    <div>
                      <p style={{fontFamily:SERIF,fontSize:12,color:C.text}}>{p.name}</p>
                      <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:1}}>{p.sku}</p>
                    </div>
                  </div>
                </td>
                <td style={{padding:"12px 14px",fontFamily:SERIF,fontSize:14,fontWeight:sortBy==="revenue"?400:300,
                  color:sortBy==="revenue"?C.gold:C.text}}>CA${p.revenue}</td>
                <td style={{padding:"12px 14px",fontFamily:SERIF,fontSize:14,fontWeight:sortBy==="margin"?400:300,
                  color:sortBy==="margin"?C.green:C.textSub}}>{p.margin}%</td>
                <td style={{padding:"12px 14px",fontFamily:SERIF,fontSize:14,fontWeight:sortBy==="velocity"?400:300,
                  color:sortBy==="velocity"?C.blue:C.textSub}}>{p.velocity}/wk</td>
                <td style={{padding:"12px 14px"}}>
                  <Badge label={p.trend>0?`+${p.trend}%`:`${p.trend}%`} 
                    color={p.trend>0?C.green:C.red} bg={`${p.trend>0?C.green:C.red}15`} border={`${p.trend>0?C.green:C.red}33`}/>
                </td>
                <td style={{padding:"12px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:6}}>
                    <div style={{width:40,height:4,borderRadius:2,background:C.border,overflow:"hidden"}}>
                      <div style={{width:`${Math.min(100,p.score)}%`,height:"100%",
                        background:`linear-gradient(90deg,${C.goldDeep},${C.gold})`,borderRadius:2}}/>
                    </div>
                    <span style={{fontFamily:SERIF,fontSize:11,color:C.gold}}>{p.score}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ══ PRODUCT EDIT MODAL ═══════════════════════════════════════════════════════ */
function ProductEditModal({product,onClose,onSave,isNew=false}){
  const fileRef=useRef(null);
  const saveRef=useRef(null);
  const [form,setForm]=useState({
    name:product?.name||"",
    subtitle:product?.subtitle||"AURA-GEN",
    sku:product?.sku||"",
    price:product?.price||0,
    cost:product?.cost||0,
    size:product?.size||"30 ml",
    tag:product?.tag||"",
    desc:product?.desc||"",
    ingredients:product?.ingredients||"",
    stock:product?.stock||0,
    reorder:product?.reorder||15,
    batch:product?.batch||"",
    accent:product?.accent||C.blue,
    accentDim:product?.accentDim||"#2a4a6a",
    shape:product?.shape||"dropper",
    hue:product?.hue||"linear-gradient(160deg,#0a1020,#060c18)",
    image:product?.image||null,
    gallery:product?.images||[],
  });
  const [preview,setPreview]=useState(product?.image||null);
  const [uploading,setUploading]=useState(false);
  const [uploadProgress,setUploadProgress]=useState(0);
  const [saving,setSaving]=useState(false);
  const [dragActive,setDragActive]=useState(false);
  const [activeGalleryIdx,setActiveGalleryIdx]=useState(0);
  const [galleryUploading,setGalleryUploading]=useState(false);

  // Keyboard shortcuts: Esc to close, S to save (Ctrl/Cmd+S)
  useEffect(()=>{
    const handleKey=(e)=>{
      if(e.key==="Escape") onClose();
      if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="s"){
        e.preventDefault();
        saveRef.current?.click();
      }
    };
    window.addEventListener("keydown",handleKey);
    return ()=>window.removeEventListener("keydown",handleKey);
  },[onClose]);

  const handleFile=async(file)=>{
    if(!file) return;
    if(!file.type.startsWith("image/")){
      alert("Please select an image file (JPEG, PNG, WebP)");
      return;
    }
    if(file.size>5*1024*1024){
      alert("File must be under 5MB");
      return;
    }
    
    // Show preview immediately
    const reader=new FileReader();
    reader.onload=(e)=>setPreview(e.target.result);
    reader.readAsDataURL(file);
    
    // Upload to Cloudinary
    setUploading(true);
    setUploadProgress(0);
    const interval=setInterval(()=>setUploadProgress(p=>Math.min(p+10,90)),200);
    
    try{
      const url=await uploadImage(await fileToBase64(file),`product_${product?.id||Date.now()}`);
      setForm(f=>({...f,image:url}));
      setUploadProgress(100);
    }catch(e){
      alert("Upload failed: "+e.message);
      setPreview(product?.image||null);
    }finally{
      clearInterval(interval);
      setTimeout(()=>setUploading(false),500);
    }
  };

  const fileToBase64=(file)=>new Promise((res,rej)=>{
    const r=new FileReader();
    r.onload=()=>res(r.result);
    r.onerror=rej;
    r.readAsDataURL(file);
  });

  const handleDrag=(e)=>{e.preventDefault();e.stopPropagation();
    if(e.type==="dragenter"||e.type==="dragover") setDragActive(true);
    else if(e.type==="dragleave") setDragActive(false);
  };
  const handleDrop=(e)=>{e.preventDefault();e.stopPropagation();setDragActive(false);
    if(e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0]);
  };

  // Gallery handlers
  const handleGalleryUpload=async(file)=>{
    if(!file||!file.type.startsWith("image/")) return;
    if(file.size>5*1024*1024){alert("File must be under 5MB");return;}
    if(form.gallery.length>=6){alert("Maximum 6 gallery images");return;}
    
    setGalleryUploading(true);
    try{
      const url=await uploadImage(await fileToBase64(file),`gallery_${product?.id||Date.now()}_${form.gallery.length}`);
      setForm(f=>({...f,gallery:[...f.gallery,url]}));
    }catch(e){
      alert("Gallery upload failed: "+e.message);
    }
    setGalleryUploading(false);
  };

  const removeGalleryImage=(idx)=>{
    setForm(f=>({...f,gallery:f.gallery.filter((_,i)=>i!==idx)}));
    if(activeGalleryIdx>=form.gallery.length-1) setActiveGalleryIdx(Math.max(0,form.gallery.length-2));
  };

  const setMainFromGallery=(idx)=>{
    const url=form.gallery[idx];
    setForm(f=>({...f,image:url}));
    setPreview(url);
  };

  const doSave=async()=>{
    if(!form.name||!form.sku){alert("Name and SKU are required");return;}
    setSaving(true);
    try{
      const payload={
        name:form.name,subtitle:form.subtitle,sku:form.sku,
        price:parseFloat(form.price)||0,cost:parseFloat(form.cost)||0,
        size:form.size,tag:form.tag,description:form.desc,
        ingredients:form.ingredients,stock:parseInt(form.stock)||0,
        reorder_point:parseInt(form.reorder)||15,batch_code:form.batch,
        accent_color:form.accent,accent_dim:form.accentDim,
        bottle_shape:form.shape,background_hue:form.hue,
        image_url:form.image,
        images:form.gallery, // Gallery images
      };
      if(isNew){
        await apiReq("POST","/api/products",payload);
      }else{
        await apiReq("PUT",`/api/products/${product.id}`,payload);
      }
      onSave();
    }catch(e){
      alert("Save failed: "+e.message);
    }finally{setSaving(false);}
  };

  const shapes=[{v:"dropper",l:"Dropper Bottle"},{v:"jar",l:"Jar"},{v:"pump",l:"Pump Bottle"}];
  const accentPresets=[
    {c:C.blue,d:"#2a4a6a",n:"Blue"},
    {c:C.gold,d:"#5a3e1a",n:"Gold"},
    {c:C.purple,d:"#3a2a5a",n:"Purple"},
    {c:C.green,d:"#2a5a4a",n:"Green"},
    {c:C.copper,d:"#5a3a2a",n:"Copper"},
  ];

  return(
    <div style={{position:"fixed",inset:0,background:"rgba(5,5,7,0.92)",zIndex:2000,
      display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(20px)",padding:20,overflowY:"auto"}} 
      onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:C.card,border:`0.5px solid ${C.borderGold}`,borderRadius:20,
        width:"100%",maxWidth:720,maxHeight:"90vh",overflow:"hidden",animation:"modalIn 0.28s ease both",
        display:"flex",flexDirection:"column",boxShadow:"0 40px 100px rgba(0,0,0,0.7)"}}>
        {/* Header */}
        <div style={{padding:"22px 28px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center",flexShrink:0}}>
          <div>
            <SL style={{marginBottom:5}}>{isNew?"Create":"Edit"} Product</SL>
            <h3 style={{fontFamily:SERIF,fontSize:22,fontWeight:300,color:C.text}}>
              {isNew?"New":"Update"} <GoldText size={22} weight={300}>Product</GoldText>
            </h3>
          </div>
          <button onClick={onClose} className="btn" style={{background:"transparent",border:`0.5px solid ${C.border}`,borderRadius:8,width:40,height:40,display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Ico n="close" size={16} color={C.textDim}/>
          </button>
        </div>
        
        {/* Content */}
        <div style={{flex:1,overflowY:"auto",padding:"24px 28px"}}>
          <div style={{display:"grid",gridTemplateColumns:"280px 1fr",gap:28}}>
            {/* Image Upload Section */}
            <div>
              <SL style={{marginBottom:12}}>Product Image</SL>
              <div 
                className="upload-zone"
                onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
                onClick={()=>fileRef.current?.click()}
                style={{
                  width:"100%",aspectRatio:"1",borderRadius:16,
                  border:`2px dashed ${dragActive?C.gold:C.border}`,
                  background:dragActive?`${C.gold}08`:form.hue,
                  display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",
                  cursor:"pointer",position:"relative",overflow:"hidden",transition:"all 0.3s ease"
                }}>
                <input ref={fileRef} type="file" accept="image/*" style={{display:"none"}} onChange={e=>handleFile(e.target.files?.[0])}/>
                
                {preview?(
                  <img src={preview} alt="Preview" style={{width:"100%",height:"100%",objectFit:"contain",padding:16}}/>
                ):(
                  <div style={{animation:"floatBottle 3s ease-in-out infinite"}}>
                    {BottleFor({...form,name:form.name||"Product",subtitle:form.subtitle},100)}
                  </div>
                )}
                
                {/* Overlay on hover */}
                <div style={{position:"absolute",inset:0,background:"rgba(5,5,7,0.75)",opacity:0,transition:"opacity 0.2s",
                  display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:8,
                  ":hover":{opacity:1}}} className="upload-overlay">
                  <Ico n="img" size={28} color={C.gold}/>
                  <p style={{fontFamily:SANS,fontSize:10,color:C.text,letterSpacing:"0.1em",textTransform:"uppercase"}}>
                    {preview?"Replace Image":"Upload Image"}
                  </p>
                  <p style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Drag & drop or click</p>
                </div>
                
                {/* Upload Progress */}
                {uploading&&(
                  <div style={{position:"absolute",inset:0,background:"rgba(5,5,7,0.9)",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:12}}>
                    <div style={{width:"60%",height:4,background:C.border,borderRadius:2,overflow:"hidden"}}>
                      <div style={{width:`${uploadProgress}%`,height:"100%",background:`linear-gradient(90deg,${C.goldDeep},${C.gold})`,transition:"width 0.2s"}}/>
                    </div>
                    <p style={{fontFamily:SANS,fontSize:10,color:C.gold,letterSpacing:"0.12em"}}>{uploadProgress<100?"UPLOADING...":"DONE!"}</p>
                  </div>
                )}
              </div>
              
              <style>{`.upload-zone:hover .upload-overlay{opacity:1!important}`}</style>
              
              {/* Quick Tips */}
              <div style={{marginTop:14,background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:10,padding:"12px 14px"}}>
                <p style={{fontFamily:SANS,fontSize:8,color:C.textDim,letterSpacing:"0.12em",textTransform:"uppercase",marginBottom:8}}>Image Guidelines</p>
                <ul style={{fontFamily:SANS,fontSize:10,color:C.textSub,lineHeight:1.8,listStyle:"none"}}>
                  <li>• Formats: JPEG, PNG, WebP</li>
                  <li>• Max size: 5 MB</li>
                  <li>• Recommended: 1200×1200px</li>
                  <li>• Auto-optimized for web</li>
                </ul>
              </div>
              
              {/* Bottle Shape Selection */}
              <div style={{marginTop:18}}>
                <SL style={{marginBottom:10}}>SVG Bottle Shape (Fallback)</SL>
                <div style={{display:"flex",gap:8}}>
                  {shapes.map(s=>(
                    <button key={s.v} onClick={()=>setForm(f=>({...f,shape:s.v}))} className="btn"
                      style={{flex:1,padding:"10px 8px",background:form.shape===s.v?`${C.gold}15`:"transparent",
                        border:`0.5px solid ${form.shape===s.v?C.gold:C.border}`,borderRadius:8,
                        fontFamily:SANS,fontSize:8,letterSpacing:"0.08em",textTransform:"uppercase",
                        color:form.shape===s.v?C.gold:C.textDim}}>{s.l}</button>
                  ))}
                </div>
              </div>
              
              {/* Accent Color */}
              <div style={{marginTop:18}}>
                <SL style={{marginBottom:10}}>Accent Color</SL>
                <div style={{display:"flex",gap:8}}>
                  {accentPresets.map(a=>(
                    <button key={a.n} onClick={()=>setForm(f=>({...f,accent:a.c,accentDim:a.d}))} className="btn"
                      style={{width:32,height:32,borderRadius:"50%",background:a.c,
                        border:form.accent===a.c?`3px solid ${C.champagne}`:`2px solid ${C.border}`,
                        boxShadow:form.accent===a.c?`0 0 12px ${a.c}44`:"none"}}/>
                  ))}
                </div>
              </div>
              
              {/* Image Gallery */}
              <div style={{marginTop:18}}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
                  <SL><Ico n="gallery" size={12} color={C.gold} style={{marginRight:6}}/> Image Gallery</SL>
                  <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>{form.gallery.length}/6 angles</span>
                </div>
                <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8}}>
                  {form.gallery.map((url,idx)=>(
                    <div key={idx} style={{aspectRatio:"1",borderRadius:8,border:`0.5px solid ${idx===activeGalleryIdx?C.gold:C.border}`,
                      overflow:"hidden",position:"relative",background:C.surface,cursor:"pointer"}}
                      onClick={()=>setActiveGalleryIdx(idx)}>
                      <img src={url} alt={`Gallery ${idx+1}`} style={{width:"100%",height:"100%",objectFit:"cover"}}/>
                      <div style={{position:"absolute",top:4,right:4,display:"flex",gap:3}}>
                        <button onClick={(e)=>{e.stopPropagation();setMainFromGallery(idx);}} className="btn" title="Set as main"
                          style={{width:20,height:20,borderRadius:4,background:"rgba(5,5,7,0.8)",border:"none",
                            display:"flex",alignItems:"center",justifyContent:"center"}}>
                          <Ico n="check" size={10} color={form.image===url?C.gold:C.textDim}/>
                        </button>
                        <button onClick={(e)=>{e.stopPropagation();removeGalleryImage(idx);}} className="btn" title="Remove"
                          style={{width:20,height:20,borderRadius:4,background:"rgba(5,5,7,0.8)",border:"none",
                            display:"flex",alignItems:"center",justifyContent:"center"}}>
                          <Ico n="close" size={10} color={C.red}/>
                        </button>
                      </div>
                      {idx===0&&<div style={{position:"absolute",bottom:4,left:4,background:C.gold,borderRadius:3,
                        padding:"2px 6px",fontFamily:SANS,fontSize:7,letterSpacing:"0.08em",color:C.void}}>MAIN</div>}
                    </div>
                  ))}
                  {form.gallery.length<6&&(
                    <label style={{aspectRatio:"1",borderRadius:8,border:`2px dashed ${galleryUploading?C.gold:C.border}`,
                      display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",cursor:"pointer",
                      background:C.surface,transition:"border-color 0.2s"}}>
                      <input type="file" accept="image/*" style={{display:"none"}} 
                        onChange={e=>handleGalleryUpload(e.target.files?.[0])} disabled={galleryUploading}/>
                      {galleryUploading?(
                        <div style={{display:"flex",gap:3}}>
                          {[0,1,2].map(i=><div key={i} style={{width:4,height:4,borderRadius:"50%",background:C.gold,animation:`pulse 1s ${i*0.15}s ease-in-out infinite`}}/>)}
                        </div>
                      ):(
                        <>
                          <Ico n="plus" size={16} color={C.textDim}/>
                          <p style={{fontFamily:SANS,fontSize:7,color:C.textDim,marginTop:4,letterSpacing:"0.08em"}}>ADD ANGLE</p>
                        </>
                      )}
                    </label>
                  )}
                </div>
                <p style={{fontFamily:SANS,fontSize:8,color:C.textDim,marginTop:8}}>Add up to 6 images to show different angles. First image is main.</p>
              </div>
            </div>
            
            {/* Form Fields */}
            <div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:16}}>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Product Name *</label>
                  <input value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} placeholder="TXA + PDRN Serum"
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SERIF,fontSize:14,color:C.text}}/>
                </div>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Subtitle</label>
                  <input value={form.subtitle} onChange={e=>setForm(f=>({...f,subtitle:e.target.value}))} placeholder="AURA-GEN I"
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SERIF,fontSize:14,color:C.text}}/>
                </div>
              </div>
              
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:14,marginBottom:16}}>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>SKU *</label>
                  <input value={form.sku} onChange={e=>setForm(f=>({...f,sku:e.target.value}))} placeholder="AG-SER-001"
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SANS,fontSize:12,color:C.text}}/>
                </div>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Size</label>
                  <input value={form.size} onChange={e=>setForm(f=>({...f,size:e.target.value}))} placeholder="30 ml"
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SANS,fontSize:12,color:C.text}}/>
                </div>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Tag</label>
                  <input value={form.tag} onChange={e=>setForm(f=>({...f,tag:e.target.value}))} placeholder="Bestseller"
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SANS,fontSize:12,color:C.text}}/>
                </div>
              </div>
              
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr",gap:14,marginBottom:16}}>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Price (CA$)</label>
                  <input type="number" step="0.01" value={form.price} onChange={e=>setForm(f=>({...f,price:e.target.value}))}
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SERIF,fontSize:14,color:C.gold}}/>
                </div>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Cost (CA$)</label>
                  <input type="number" step="0.01" value={form.cost} onChange={e=>setForm(f=>({...f,cost:e.target.value}))}
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SERIF,fontSize:14,color:C.textSub}}/>
                </div>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Stock</label>
                  <input type="number" value={form.stock} onChange={e=>setForm(f=>({...f,stock:e.target.value}))}
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SERIF,fontSize:14,color:C.green}}/>
                </div>
                <div>
                  <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Reorder Point</label>
                  <input type="number" value={form.reorder} onChange={e=>setForm(f=>({...f,reorder:e.target.value}))}
                    className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                      padding:"12px 14px",fontFamily:SANS,fontSize:12,color:C.text}}/>
                </div>
              </div>
              
              <div style={{marginBottom:16}}>
                <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Description</label>
                <textarea value={form.desc} onChange={e=>setForm(f=>({...f,desc:e.target.value}))} rows={3}
                  placeholder="Product description..."
                  className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                    padding:"12px 14px",fontFamily:SERIF,fontSize:13,color:C.text,resize:"vertical",lineHeight:1.6}}/>
              </div>
              
              <div style={{marginBottom:16}}>
                <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Ingredients</label>
                <textarea value={form.ingredients} onChange={e=>setForm(f=>({...f,ingredients:e.target.value}))} rows={2}
                  placeholder="PDRN 2%, TXA 5%, Argireline 3%..."
                  className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                    padding:"12px 14px",fontFamily:SANS,fontSize:11,color:C.textSub,resize:"vertical",lineHeight:1.6}}/>
              </div>
              
              <div>
                <label style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,display:"block",marginBottom:6}}>Batch Code</label>
                <input value={form.batch} onChange={e=>setForm(f=>({...f,batch:e.target.value}))} placeholder="B2024-11"
                  className="inp" style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,
                    padding:"12px 14px",fontFamily:SANS,fontSize:11,color:C.textDim}}/>
              </div>
            </div>
          </div>
        </div>
        
        {/* Footer */}
        <div style={{padding:"18px 28px",borderTop:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center",flexShrink:0}}>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            {form.image&&<Badge label="Image Uploaded" color={C.green} bg={`${C.green}15`} border={`${C.green}33`}/>}
            {!form.image&&form.shape&&<Badge label={`SVG: ${form.shape}`} color={C.textSub} bg={`${C.textSub}15`} border={`${C.textSub}33`}/>}
          </div>
          <div style={{display:"flex",gap:12}}>
            <button className="btn" onClick={onClose} style={{background:"transparent",border:`0.5px solid ${C.border}`,
              borderRadius:6,padding:"12px 24px",fontFamily:SANS,fontSize:10,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim}}>Cancel <kbd style={{marginLeft:6,opacity:0.5,fontSize:8}}>Esc</kbd></button>
            <button ref={saveRef} className="btn" onClick={doSave} disabled={saving||uploading} style={{
              background:saving||uploading?`${C.gold}33`:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
              border:"none",borderRadius:6,padding:"12px 32px",fontFamily:SANS,fontSize:10,letterSpacing:"0.14em",
              textTransform:"uppercase",color:saving||uploading?C.textDim:C.void}}>
              {saving?"Saving...":(isNew?"Create Product":"Save Changes")} <kbd style={{marginLeft:6,opacity:0.7,fontSize:8}}>⌘S</kbd>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ══ INVENTORY SCREEN ═══════════════════════════════════════════════════════ */
const Inventory=({products,setProducts})=>{
  const [modal,setModal]=useState(null);
  const [stockModal,setStockModal]=useState(null);
  const [duplicating,setDuplicating]=useState(null);
  const stockColor=s=>s==="Critical"||s==="Out"?C.red:s==="Low"?C.copper:C.green;
  const margin=p=>(((p.price-p.cost)/p.price)*100).toFixed(0);

  // Listen for keyboard shortcut event from parent
  useEffect(()=>{
    const handleAddProduct=()=>setModal("add");
    window.addEventListener("admin-add-product",handleAddProduct);
    return ()=>window.removeEventListener("admin-add-product",handleAddProduct);
  },[]);

  const refreshProducts=async()=>{
    try{
      const data=await apiReq("GET","/api/products");
      setProducts(data.map(normalizeProduct));
    }catch{}
    setModal(null);
    setStockModal(null);
  };

  // Duplicate product
  const duplicateProduct=async(p)=>{
    setDuplicating(p.id);
    try{
      const newSku=`${p.sku}-COPY-${Date.now().toString(36).slice(-4).toUpperCase()}`;
      await apiReq("POST","/api/products",{
        name:`${p.name} (Copy)`,
        subtitle:p.subtitle,
        sku:newSku,
        price:p.price,
        cost:p.cost,
        size:p.size,
        tag:p.tag,
        description:p.desc,
        ingredients:p.ingredients,
        stock:0,
        reorder_point:p.reorder,
        batch_code:"",
        accent_color:p.accent,
        accent_dim:p.accentDim,
        bottle_shape:p.shape,
        background_hue:p.hue,
        image_url:p.image,
      });
      await refreshProducts();
    }catch(e){
      alert("Duplicate failed: "+e.message);
    }finally{
      setDuplicating(null);
    }
  };

  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:22}}>
        <div>
          <SL>Stock Management</SL>
          <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Inventory <GoldText size={26}>Control</GoldText></h2>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,padding:"8px 12px",display:"flex",alignItems:"center",gap:6}}>
            <kbd style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:3,padding:"2px 6px",fontFamily:SANS,fontSize:9,color:C.textDim}}>N</kbd>
            <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>New</span>
          </div>
          <button data-testid="add-product-btn" className="btn" onClick={()=>setModal("add")} style={{background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,border:"none",borderRadius:4,
            padding:"11px 18px",fontFamily:SANS,fontSize:10,letterSpacing:"0.15em",textTransform:"uppercase",color:C.void,
            display:"flex",alignItems:"center",gap:8}}>
            <Ico n="plus" size={14} color={C.void}/> Add Product
          </button>
        </div>
      </div>
      
      {/* Product Cards Grid */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:13,marginBottom:22}}>
        {products.slice(0,6).map((p,i)=>(
          <div key={p.id} className="card" style={{background:p.hue,border:`0.5px solid ${p.accent}22`,borderRadius:13,overflow:"hidden",animation:`fadeUp .5s ease ${i*0.08}s both`}}>
            <div style={{padding:"22px 18px 14px",display:"flex",justifyContent:"center",position:"relative",borderBottom:`0.5px solid ${p.accent}18`}}>
              <div style={{position:"absolute",inset:0,background:`radial-gradient(circle at 50% 40%,${p.accent}10,transparent 65%)`}}/>
              <div style={{animation:"floatBottle 3s ease-in-out infinite"}}><ProductImg p={p} size={86}/></div>
            </div>
            <div style={{padding:"14px"}}>
              <SL style={{color:p.accent,marginBottom:5}}>{p.subtitle}</SL>
              <p style={{fontFamily:SERIF,fontSize:13,color:C.text,marginBottom:9}}>{p.name}</p>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:7}}>
                <span style={{fontFamily:SERIF,fontSize:20,fontWeight:300,color:stockColor(p.status)}}>{p.stock}</span>
                <Badge label={p.status} color={stockColor(p.status)} bg={`${stockColor(p.status)}15`} border={`${stockColor(p.status)}33`}/>
              </div>
              <div style={{height:"3px",background:"rgba(255,255,255,0.07)",borderRadius:2,overflow:"hidden",marginBottom:9}}>
                <div style={{width:`${Math.min(100,(p.stock/30)*100)}%`,height:"100%",background:stockColor(p.status),borderRadius:2}}/>
              </div>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:12}}>
                <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Reorder: {p.reorder}</span>
                <span style={{fontFamily:SERIF,fontSize:11,color:C.green}}>{margin(p)}% margin</span>
              </div>
              <div style={{display:"flex",gap:6}}>
                <button data-testid={`quick-stock-${p.id}`} className="btn" onClick={()=>setStockModal(p)} style={{flex:1,background:`${C.green}18`,border:`0.5px solid ${C.green}33`,
                  borderRadius:4,padding:"8px",fontFamily:SANS,fontSize:8,letterSpacing:"0.08em",textTransform:"uppercase",color:C.green,
                  display:"flex",alignItems:"center",justifyContent:"center",gap:4}}>
                  <Ico n="plus" size={10} color={C.green}/>Stock
                </button>
                <button data-testid={`edit-${p.id}`} className="btn" onClick={()=>setModal(p)} style={{flex:1,background:`${p.accent}18`,border:`0.5px solid ${p.accent}33`,
                  borderRadius:4,padding:"8px",fontFamily:SANS,fontSize:8,letterSpacing:"0.08em",textTransform:"uppercase",color:p.accent,
                  display:"flex",alignItems:"center",justifyContent:"center",gap:4}}>
                  <Ico n="edit" size={10} color={p.accent}/>Edit
                </button>
                <button data-testid={`duplicate-${p.id}`} className="btn" onClick={()=>duplicateProduct(p)} disabled={duplicating===p.id} style={{background:`${C.blue}18`,border:`0.5px solid ${C.blue}33`,
                  borderRadius:4,padding:"8px",fontFamily:SANS,fontSize:8,color:C.blue,display:"flex",alignItems:"center",justifyContent:"center",width:34}}>
                  {duplicating===p.id?<span style={{fontSize:8}}>...</span>:<Ico n="copy" size={10} color={C.blue}/>}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Stock Ledger Table */}
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
        <div style={{padding:"14px 20px 11px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>Stock Ledger - {products.length} SKUs</p>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Shortcuts:</span>
            <kbd style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:3,padding:"2px 5px",fontFamily:SANS,fontSize:8,color:C.textDim}}>S</kbd>
            <span style={{fontFamily:SANS,fontSize:8,color:C.textDim}}>Save</span>
            <kbd style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:3,padding:"2px 5px",fontFamily:SANS,fontSize:8,color:C.textDim}}>Esc</kbd>
            <span style={{fontFamily:SANS,fontSize:8,color:C.textDim}}>Close</span>
          </div>
        </div>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
            {["Product","SKU","Stock","Cost","Price","Margin","Status","Actions"].map(h=>(
              <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {products.map((p,i)=>(
              <tr key={p.id} className="row-hover" style={{borderBottom:i<products.length-1?`0.5px solid ${C.border}`:"none"}}>
                <td style={{padding:"11px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:10}}>
                    <div style={{flexShrink:0,background:p.hue,borderRadius:6,padding:2}}><ProductImg p={p} size={32}/></div>
                    <div>
                      <p style={{fontFamily:SERIF,fontSize:12,color:C.text}}>{p.name}</p>
                      <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:1}}>{p.size}</p>
                    </div>
                  </div>
                </td>
                <td style={{padding:"11px 14px",fontFamily:SANS,fontSize:10,color:C.textSub}}>{p.sku}</td>
                <td style={{padding:"11px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:7}}>
                    <span style={{fontFamily:SERIF,fontSize:16,fontWeight:300,color:stockColor(p.status)}}>{p.stock}</span>
                    <div style={{width:32,height:2.5,borderRadius:2,background:C.border,overflow:"hidden"}}>
                      <div style={{width:`${Math.min(100,(p.stock/30)*100)}%`,height:"100%",background:stockColor(p.status),borderRadius:2}}/>
                    </div>
                  </div>
                </td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:12,color:C.textSub}}>{"CA$"}{p.cost}</td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:12,color:C.text}}>{"CA$"}{p.price}</td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:12,color:C.green}}>{margin(p)}%</td>
                <td style={{padding:"11px 14px"}}><Badge label={p.status} color={stockColor(p.status)} bg={`${stockColor(p.status)}15`} border={`${stockColor(p.status)}33`}/></td>
                <td style={{padding:"11px 14px"}}>
                  <div style={{display:"flex",gap:6}}>
                    <button data-testid={`table-stock-${p.id}`} className="btn" onClick={()=>setStockModal(p)} title="Quick Stock Adjust" style={{background:`${C.green}15`,border:`0.5px solid ${C.green}33`,
                      borderRadius:4,padding:"6px 10px",fontFamily:SANS,fontSize:8,letterSpacing:"0.08em",color:C.green,display:"flex",alignItems:"center",gap:4}}>
                      <Ico n="plus" size={9} color={C.green}/>
                    </button>
                    <button data-testid={`table-edit-${p.id}`} className="btn" onClick={()=>setModal(p)} title="Edit Product" style={{background:`${C.gold}15`,border:`0.5px solid ${C.borderGold}`,
                      borderRadius:4,padding:"6px 10px",fontFamily:SANS,fontSize:8,letterSpacing:"0.08em",color:C.gold,display:"flex",alignItems:"center",gap:4}}>
                      <Ico n="edit" size={9} color={C.gold}/>
                    </button>
                    <button data-testid={`table-dup-${p.id}`} className="btn" onClick={()=>duplicateProduct(p)} disabled={duplicating===p.id} title="Duplicate Product" style={{background:`${C.blue}15`,border:`0.5px solid ${C.blue}33`,
                      borderRadius:4,padding:"6px 10px",fontFamily:SANS,fontSize:8,color:C.blue,display:"flex",alignItems:"center"}}>
                      {duplicating===p.id?<span style={{fontSize:8}}>...</span>:<Ico n="copy" size={9} color={C.blue}/>}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Modals */}
      {modal&&modal!=="add"&&modal!=="stock"&&<ProductEditModal product={modal} onClose={()=>setModal(null)} onSave={refreshProducts} isNew={false}/>}
      {modal==="add"&&<ProductEditModal product={null} onClose={()=>setModal(null)} onSave={refreshProducts} isNew={true}/>}
      {stockModal&&<BulkStockModal product={stockModal} onClose={()=>setStockModal(null)} onSave={refreshProducts}/>}
    </div>
  );
};

/* ══ CRM SCREEN WITH SEGMENTATION ═══════════════════════════════════════════ */
const CRM=()=>{
  const [search,setSearch]=useState("");
  const [filters,setFilters]=useState({tier:"All",status:"All",ltv:"All",lastActive:"All"});
  const [showFilters,setShowFilters]=useState(false);
  
  const tierColor=t=>({Diamond:C.blue,Gold:C.gold,Silver:"#9CA3AF",Elite:C.purple}[t]||C.textDim);
  const statusColor=s=>({Active:C.green,"At Risk":C.copper,Churned:C.red}[s]||C.textDim);
  
  // Apply all filters
  const filtered=CRM_DATA.filter(c=>{
    if(search&&!c.name.toLowerCase().includes(search.toLowerCase())) return false;
    if(filters.tier!=="All"&&c.tier!==filters.tier) return false;
    if(filters.status!=="All"&&c.status!==filters.status) return false;
    if(filters.ltv!=="All"){
      if(filters.ltv==="High"&&c.ltv<1000) return false;
      if(filters.ltv==="Medium"&&(c.ltv<500||c.ltv>=1000)) return false;
      if(filters.ltv==="Low"&&c.ltv>=500) return false;
    }
    if(filters.lastActive!=="All"){
      const days=c.last.includes("d")?parseInt(c.last):c.last.includes("w")?parseInt(c.last)*7:30;
      if(filters.lastActive==="Recent"&&days>7) return false;
      if(filters.lastActive==="Moderate"&&(days<=7||days>21)) return false;
      if(filters.lastActive==="Inactive"&&days<=21) return false;
    }
    return true;
  });
  
  const activeFilters=Object.values(filters).filter(v=>v!=="All").length;
  
  const FilterDropdown=({label,value,options,onChange})=>(
    <div style={{position:"relative"}}>
      <p style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.1em",textTransform:"uppercase",color:C.textDim,marginBottom:6}}>{label}</p>
      <select value={value} onChange={e=>onChange(e.target.value)} style={{
        background:C.surface,border:`0.5px solid ${value!=="All"?C.gold:C.border}`,borderRadius:6,
        padding:"10px 30px 10px 12px",fontFamily:SANS,fontSize:11,color:value!=="All"?C.gold:C.text,
        cursor:"pointer",appearance:"none",width:"100%",
        backgroundImage:`url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L5 5L9 1' stroke='%23${value!=="All"?"C9A86E":"666"}' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E")`,
        backgroundRepeat:"no-repeat",backgroundPosition:"right 12px center"
      }}>
        {options.map(o=><option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
  
  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:22}}>
        <div>
          <SL>Customer Intelligence</SL>
          <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>CRM <GoldText size={26}>Dashboard</GoldText></h2>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <button onClick={()=>setShowFilters(s=>!s)} data-testid="crm-filters-btn" className="btn" style={{
            background:showFilters||activeFilters?`${C.gold}15`:"transparent",
            border:`0.5px solid ${showFilters||activeFilters?C.gold:C.border}`,borderRadius:4,
            padding:"8px 14px",display:"flex",alignItems:"center",gap:7}}>
            <Ico n="filter" size={13} color={showFilters||activeFilters?C.gold:C.textDim}/>
            <span style={{fontFamily:SANS,fontSize:10,letterSpacing:"0.08em",color:showFilters||activeFilters?C.gold:C.textDim}}>Filters</span>
            {activeFilters>0&&<span style={{background:C.gold,color:C.void,borderRadius:"50%",width:16,height:16,
              display:"flex",alignItems:"center",justifyContent:"center",fontFamily:SANS,fontSize:9}}>{activeFilters}</span>}
          </button>
          <div style={{display:"flex",alignItems:"center",gap:9,background:C.card,border:`0.5px solid ${C.border}`,borderRadius:4,padding:"8px 12px"}}>
            <Ico n="search" size={13} color={C.textDim}/>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search..."
              style={{background:"transparent",border:"none",fontFamily:SANS,fontSize:11,color:C.text,width:130}}/>
          </div>
        </div>
      </div>
      
      {/* Segmentation Filters Panel */}
      {showFilters&&(
        <div data-testid="crm-filters-panel" className="card" style={{background:C.card,border:`0.5px solid ${C.borderGold}`,borderRadius:13,padding:"18px",marginBottom:20,animation:"fadeUp .3s ease both"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <Ico n="filter" size={14} color={C.gold}/>
              <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>Customer <GoldText size={14}>Segmentation</GoldText></p>
            </div>
            {activeFilters>0&&<button onClick={()=>setFilters({tier:"All",status:"All",ltv:"All",lastActive:"All"})} className="btn" 
              style={{background:"transparent",border:`0.5px solid ${C.border}`,borderRadius:4,padding:"6px 12px",
                fontFamily:SANS,fontSize:9,letterSpacing:"0.08em",color:C.textDim}}>Clear All</button>}
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:14}}>
            <FilterDropdown label="Customer Tier" value={filters.tier} options={["All","Elite","Diamond","Gold","Silver"]} onChange={v=>setFilters(f=>({...f,tier:v}))}/>
            <FilterDropdown label="Status" value={filters.status} options={["All","Active","At Risk","Churned"]} onChange={v=>setFilters(f=>({...f,status:v}))}/>
            <FilterDropdown label="LTV Segment" value={filters.ltv} options={["All","High","Medium","Low"]} onChange={v=>setFilters(f=>({...f,ltv:v}))}/>
            <FilterDropdown label="Last Active" value={filters.lastActive} options={["All","Recent","Moderate","Inactive"]} onChange={v=>setFilters(f=>({...f,lastActive:v}))}/>
          </div>
          <div style={{marginTop:14,padding:"10px 14px",background:C.surface,borderRadius:8,display:"flex",alignItems:"center",gap:10}}>
            <span style={{fontFamily:SANS,fontSize:9,color:C.textDim,letterSpacing:"0.08em"}}>SEGMENT SIZE:</span>
            <span style={{fontFamily:SERIF,fontSize:18,fontWeight:300,color:C.gold}}>{filtered.length}</span>
            <span style={{fontFamily:SANS,fontSize:9,color:C.textSub}}>customers match filters</span>
            {activeFilters>0&&<span style={{marginLeft:"auto",fontFamily:SANS,fontSize:9,color:C.textDim}}>
              LTV Range: CA${Math.min(...filtered.map(c=>c.ltv)).toLocaleString()} - CA${Math.max(...filtered.map(c=>c.ltv)).toLocaleString()}
            </span>}
          </div>
        </div>
      )}
      
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:11,marginBottom:20}}>
        <StatCard label="Total Customers" value="284" sub="Registered" color={C.blue} delay={0}/>
        <StatCard label="VIP Accounts" value="47" sub="Gold tier+" color={C.gold} delay={.05}/>
        <StatCard label="Avg LTV" value="CA$524" sub="Per customer" color={C.green} delay={.1}/>
        <StatCard label="Churn Rate" value="2.1%" sub="Last 30d" color={C.red} delay={.15}/>
      </div>
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
        <div style={{padding:"14px 20px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>{activeFilters>0?`Filtered: ${filtered.length} customers`:`All Customers (${filtered.length})`}</p>
          {activeFilters>0&&<Badge label={`${activeFilters} filter${activeFilters>1?"s":""} active`} color={C.gold} bg={`${C.gold}15`} border={`${C.gold}33`}/>}
        </div>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
            {["Customer","Tier","LTV","Orders","Last Active","Score","Status"].map(h=>(
              <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {filtered.length===0?(
              <tr><td colSpan={7} style={{padding:"40px",textAlign:"center"}}>
                <Ico n="filter" size={24} color={C.textDim}/>
                <p style={{fontFamily:SERIF,fontSize:14,color:C.textSub,marginTop:12}}>No customers match your filters</p>
                <button onClick={()=>setFilters({tier:"All",status:"All",ltv:"All",lastActive:"All"})} className="btn" 
                  style={{marginTop:12,background:`${C.gold}15`,border:`0.5px solid ${C.borderGold}`,borderRadius:4,padding:"8px 16px",
                    fontFamily:SANS,fontSize:10,letterSpacing:"0.08em",color:C.gold}}>Clear Filters</button>
              </td></tr>
            ):filtered.map((c,i)=>(
              <tr key={c.id} className="row-hover" style={{borderBottom:i<filtered.length-1?`0.5px solid ${C.border}`:"none"}}>
                <td style={{padding:"11px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:9}}>
                    <div style={{width:28,height:28,borderRadius:"50%",background:`${tierColor(c.tier)}22`,
                      border:`0.5px solid ${tierColor(c.tier)}44`,display:"flex",alignItems:"center",justifyContent:"center"}}>
                      <span style={{fontFamily:SERIF,fontSize:11,color:tierColor(c.tier)}}>{c.name[0]}</span>
                    </div>
                    <p style={{fontFamily:SERIF,fontSize:13,color:C.text}}>{c.name}</p>
                  </div>
                </td>
                <td style={{padding:"11px 14px"}}><Badge label={c.tier} color={tierColor(c.tier)} bg={`${tierColor(c.tier)}15`} border={`${tierColor(c.tier)}33`}/></td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:13,color:C.text}}>{"CA$"}{c.ltv.toLocaleString()}</td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:13,color:C.textSub}}>{c.orders}</td>
                <td style={{padding:"11px 14px",fontFamily:SANS,fontSize:10,color:C.textDim}}>{c.last}</td>
                <td style={{padding:"11px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:6}}>
                    <div style={{width:34,height:2.5,borderRadius:2,background:C.border,overflow:"hidden"}}>
                      <div style={{width:`${c.score}%`,height:"100%",background:c.score>70?C.green:c.score>40?C.copper:C.red,borderRadius:2}}/>
                    </div>
                    <span style={{fontFamily:SERIF,fontSize:11,color:c.score>70?C.green:c.score>40?C.copper:C.red}}>{c.score}</span>
                  </div>
                </td>
                <td style={{padding:"11px 14px"}}><Badge label={c.status} color={statusColor(c.status)} bg={`${statusColor(c.status)}15`} border={`${statusColor(c.status)}33`}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ══ ABANDONED CART RECOVERY ═══════════════════════════════════════════════ */
const AbandonedCarts=({products})=>{
  const [carts,setCarts]=useState([]);
  const [loading,setLoading]=useState(true);
  const [filter,setFilter]=useState("All");
  const [sending,setSending]=useState(null);
  const [stats,setStats]=useState({total:0,last24h:0,last48h:0,last72h:0,recovered:0,value:0});
  
  // Fetch abandoned carts
  useEffect(()=>{
    const fetchCarts=async()=>{
      setLoading(true);
      try{
        const data=await apiReq("GET","/api/abandoned-carts");
        setCarts(data.carts||[]);
        setStats(data.stats||{total:0,last24h:0,last48h:0,last72h:0,recovered:0,value:0});
      }catch(e){
        console.log("Abandoned carts API not available, using mock data");
        // Mock data for demo
        const mockCarts=[
          {id:"AC001",email:"sarah@example.com",name:"Sarah Mitchell",items:[{name:"TXA + PDRN Serum",qty:1,price:89.99}],total:89.99,abandoned_at:"2h ago",step:"checkout",recovered:false},
          {id:"AC002",email:"mike@example.com",name:"Mike Chen",items:[{name:"Accelerator Rich Cream",qty:2,price:74.99}],total:149.98,abandoned_at:"5h ago",step:"cart",recovered:false},
          {id:"AC003",email:"emma@example.com",name:"Emma Wilson",items:[{name:"Recovery Serum",qty:1,price:64.99},{name:"TXA + PDRN Serum",qty:1,price:89.99}],total:154.98,abandoned_at:"18h ago",step:"shipping",recovered:false},
          {id:"AC004",email:"james@example.com",name:"James Brown",items:[{name:"Hydra-Barrier Moisturizer",qty:1,price:68}],total:68,abandoned_at:"1d ago",step:"payment",recovered:false},
          {id:"AC005",email:"lisa@example.com",name:"Lisa Park",items:[{name:"Cell Renewal Treatment Mask",qty:1,price:52}],total:52,abandoned_at:"2d ago",step:"cart",recovered:true},
        ];
        setCarts(mockCarts);
        setStats({total:5,last24h:2,last48h:3,last72h:4,recovered:1,value:514.93});
      }
      setLoading(false);
    };
    fetchCarts();
  },[]);
  
  // Send recovery email
  const sendRecoveryEmail=async(cart)=>{
    setSending(cart.id);
    try{
      await apiReq("POST","/api/abandoned-carts/send-recovery",{cart_id:cart.id,email:cart.email});
      setCarts(cs=>cs.map(c=>c.id===cart.id?{...c,recovery_sent:true}:c));
    }catch(e){
      // Mock success for demo
      setCarts(cs=>cs.map(c=>c.id===cart.id?{...c,recovery_sent:true}:c));
    }
    setSending(null);
  };
  
  const timeFilters=[
    {id:"All",label:"All Time"},
    {id:"24h",label:"Last 24h"},
    {id:"48h",label:"Last 48h"},
    {id:"72h",label:"Last 72h"},
  ];
  
  const stepColor=s=>({cart:C.textDim,shipping:C.blue,checkout:C.copper,payment:C.gold}[s]||C.textDim);
  
  const filteredCarts=carts.filter(c=>{
    if(filter==="All") return !c.recovered;
    const hours=c.abandoned_at.includes("h")?parseInt(c.abandoned_at):c.abandoned_at.includes("d")?parseInt(c.abandoned_at)*24:0;
    if(filter==="24h"&&hours>24) return false;
    if(filter==="48h"&&hours>48) return false;
    if(filter==="72h"&&hours>72) return false;
    return !c.recovered;
  });
  
  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:22}}>
        <div>
          <SL>Revenue Recovery</SL>
          <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Abandoned <GoldText size={26}>Cart Recovery</GoldText></h2>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          {timeFilters.map(f=>(
            <button key={f.id} onClick={()=>setFilter(f.id)} className="btn" style={{
              background:filter===f.id?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:"transparent",
              border:`0.5px solid ${filter===f.id?C.gold:C.border}`,borderRadius:2,
              padding:"6px 12px",fontFamily:SANS,fontSize:8,letterSpacing:"0.1em",
              color:filter===f.id?C.void:C.textDim}}>{f.label}</button>
          ))}
        </div>
      </div>
      
      {/* Stats Cards */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:11,marginBottom:22}}>
        <div className="card" style={{background:`linear-gradient(135deg,${C.copper}10,${C.red}05)`,border:`0.5px solid ${C.copper}33`,borderRadius:13,padding:"16px"}}>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
            <div style={{width:28,height:28,borderRadius:"50%",background:`${C.copper}22`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Ico n="cart" size={13} color={C.copper}/>
            </div>
            <SL style={{color:C.copper}}>Last 24h</SL>
          </div>
          <p style={{fontFamily:SERIF,fontSize:28,fontWeight:300,color:C.copper}}>{stats.last24h}</p>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:4}}>carts abandoned</p>
        </div>
        <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"16px"}}>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
            <div style={{width:28,height:28,borderRadius:"50%",background:`${C.blue}22`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Ico n="cart" size={13} color={C.blue}/>
            </div>
            <SL>Last 48h</SL>
          </div>
          <p style={{fontFamily:SERIF,fontSize:28,fontWeight:300,color:C.blue}}>{stats.last48h}</p>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:4}}>carts abandoned</p>
        </div>
        <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"16px"}}>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
            <div style={{width:28,height:28,borderRadius:"50%",background:`${C.textDim}22`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Ico n="cart" size={13} color={C.textDim}/>
            </div>
            <SL>Last 72h</SL>
          </div>
          <p style={{fontFamily:SERIF,fontSize:28,fontWeight:300,color:C.text}}>{stats.last72h}</p>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:4}}>carts abandoned</p>
        </div>
        <div className="card" style={{background:`linear-gradient(135deg,${C.green}10,${C.green}05)`,border:`0.5px solid ${C.green}33`,borderRadius:13,padding:"16px"}}>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
            <div style={{width:28,height:28,borderRadius:"50%",background:`${C.green}22`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Ico n="recover" size={13} color={C.green}/>
            </div>
            <SL style={{color:C.green}}>Recovered</SL>
          </div>
          <p style={{fontFamily:SERIF,fontSize:28,fontWeight:300,color:C.green}}>{stats.recovered}</p>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:4}}>carts converted</p>
        </div>
        <div className="card" style={{background:`linear-gradient(135deg,${C.gold}10,${C.gold}05)`,border:`0.5px solid ${C.borderGold}`,borderRadius:13,padding:"16px"}}>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
            <div style={{width:28,height:28,borderRadius:"50%",background:`${C.gold}22`,display:"flex",alignItems:"center",justifyContent:"center"}}>
              <Ico n="accounting" size={13} color={C.gold}/>
            </div>
            <SL style={{color:C.gold}}>Revenue at Risk</SL>
          </div>
          <p style={{fontFamily:SERIF,fontSize:28,fontWeight:300,color:C.gold}}>CA${stats.value.toFixed(0)}</p>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:4}}>potential recovery</p>
        </div>
      </div>
      
      {/* Abandoned Carts Table */}
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
        <div style={{padding:"14px 20px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>Abandoned Carts ({filteredCarts.length})</p>
          <Badge label="RECOVERABLE" color={C.gold} bg={`${C.gold}15`} border={`${C.gold}33`}/>
        </div>
        {loading?(
          <div style={{padding:"60px",textAlign:"center"}}>
            <div style={{display:"flex",justifyContent:"center",gap:5}}>
              {[0,1,2].map(i=><div key={i} style={{width:8,height:8,borderRadius:"50%",background:C.gold,animation:`pulse 1.2s ${i*0.2}s ease-in-out infinite`}}/>)}
            </div>
            <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:12}}>Loading abandoned carts...</p>
          </div>
        ):(
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
              {["Customer","Items","Cart Value","Abandoned","Stage","Recovery","Action"].map(h=>(
                <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {filteredCarts.length===0?(
                <tr><td colSpan={7} style={{padding:"50px",textAlign:"center"}}>
                  <Ico n="check" size={28} color={C.green}/>
                  <p style={{fontFamily:SERIF,fontSize:16,color:C.text,marginTop:14}}>No abandoned carts to recover!</p>
                  <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:6}}>All recent carts have been recovered or completed</p>
                </td></tr>
              ):filteredCarts.map((cart,i)=>(
                <tr key={cart.id} className="row-hover" style={{borderBottom:i<filteredCarts.length-1?`0.5px solid ${C.border}`:"none"}}>
                  <td style={{padding:"12px 14px"}}>
                    <p style={{fontFamily:SERIF,fontSize:13,color:C.text}}>{cart.name||cart.email.split("@")[0]}</p>
                    <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:2}}>{cart.email}</p>
                  </td>
                  <td style={{padding:"12px 14px"}}>
                    <div style={{maxWidth:180}}>
                      {cart.items.slice(0,2).map((item,j)=>(
                        <p key={j} style={{fontFamily:SANS,fontSize:10,color:C.textSub,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
                          {item.qty}x {item.name}
                        </p>
                      ))}
                      {cart.items.length>2&&<p style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>+{cart.items.length-2} more</p>}
                    </div>
                  </td>
                  <td style={{padding:"12px 14px",fontFamily:SERIF,fontSize:16,fontWeight:300,color:C.gold}}>CA${cart.total.toFixed(2)}</td>
                  <td style={{padding:"12px 14px",fontFamily:SANS,fontSize:10,color:C.textDim}}>{cart.abandoned_at}</td>
                  <td style={{padding:"12px 14px"}}>
                    <Badge label={cart.step.charAt(0).toUpperCase()+cart.step.slice(1)} color={stepColor(cart.step)} bg={`${stepColor(cart.step)}15`} border={`${stepColor(cart.step)}33`}/>
                  </td>
                  <td style={{padding:"12px 14px"}}>
                    {cart.recovery_sent?(
                      <span style={{fontFamily:SANS,fontSize:9,color:C.green,display:"flex",alignItems:"center",gap:4}}>
                        <Ico n="check" size={12} color={C.green}/>Sent
                      </span>
                    ):(
                      <span style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Pending</span>
                    )}
                  </td>
                  <td style={{padding:"12px 14px"}}>
                    <button 
                      data-testid={`recover-${cart.id}`}
                      onClick={()=>sendRecoveryEmail(cart)} 
                      disabled={sending===cart.id||cart.recovery_sent}
                      className="btn" 
                      style={{
                        background:cart.recovery_sent?`${C.green}15`:sending===cart.id?`${C.gold}33`:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
                        border:cart.recovery_sent?`0.5px solid ${C.green}33`:"none",
                        borderRadius:4,padding:"8px 14px",fontFamily:SANS,fontSize:9,letterSpacing:"0.08em",
                        color:cart.recovery_sent?C.green:sending===cart.id?C.textDim:C.void,
                        display:"flex",alignItems:"center",gap:6
                      }}>
                      {cart.recovery_sent?(<><Ico n="check" size={11} color={C.green}/>Sent</>):
                       sending===cart.id?"Sending...":(<><Ico n="send" size={11} color={C.void}/>Recover</>)}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

/* ══ ORDERS SCREEN ═══════════════════════════════════════════════════════ */
const OrdersPanel=({products})=>{
  const [filter,setFilter]=useState("All");
  const statuses=["All","Processing","Shipped","Delivered"];
  const statusColor=s=>({Processing:C.gold,Shipped:C.blue,Delivered:C.green,Refund:C.red}[s]||C.textDim);
  const filtered=filter==="All"?ORDERS_DATA:ORDERS_DATA.filter(o=>o.status===filter);
  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:22}}>
        <div><SL>Fulfilment</SL><h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Order <GoldText size={26}>Management</GoldText></h2></div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:11,marginBottom:18}}>
        <StatCard label="Total MTD" value="137" sub="March 2026" color={C.gold} delay={0}/>
        <StatCard label="Processing" value="2" sub="Awaiting ship" color={C.copper} delay={.05}/>
        <StatCard label="In Transit" value="1" sub="Via FlagShip" color={C.blue} delay={.1}/>
        <StatCard label="Refunds" value="1" sub="CA$99.99" color={C.red} delay={.15}/>
      </div>
      <div style={{display:"flex",gap:7,marginBottom:14}}>
        {statuses.map(s=>(<button key={s} onClick={()=>setFilter(s)} className="btn" style={{
          background:filter===s?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:"transparent",
          border:`0.5px solid ${filter===s?C.gold:C.border}`,borderRadius:2,
          padding:"6px 12px",fontFamily:SANS,fontSize:8,letterSpacing:"0.12em",textTransform:"uppercase",
          color:filter===s?C.void:C.textDim}}>{s}</button>))}
      </div>
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
            {["Order","Customer","Product","Date","Total","Payment","Status"].map(h=>(
              <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {filtered.map((o,i)=>{
              const prod=products.find(p=>p.id===o.productId)||products[0];
              return(<tr key={o.id} className="row-hover" style={{borderBottom:i<filtered.length-1?`0.5px solid ${C.border}`:"none"}}>
                <td style={{padding:"10px 14px",fontFamily:SANS,fontSize:10,color:C.gold}}>{o.id}</td>
                <td style={{padding:"10px 14px",fontFamily:SERIF,fontSize:13,color:C.text}}>{o.customer}</td>
                <td style={{padding:"10px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:9}}>
                    <div style={{background:prod?.hue||C.card,borderRadius:5,padding:1,border:`0.5px solid ${prod?.accent||C.border}22`}}>
                      <ProductImg p={prod||{}} size={30}/>
                    </div>
                    <span style={{fontFamily:SANS,fontSize:10,color:C.textSub}}>{prod?.name||"Product"}</span>
                  </div>
                </td>
                <td style={{padding:"10px 14px",fontFamily:SANS,fontSize:10,color:C.textDim}}>{o.date}</td>
                <td style={{padding:"10px 14px",fontFamily:SERIF,fontSize:13,color:C.text}}>{"CA$"}{o.total}</td>
                <td style={{padding:"10px 14px"}}><Badge label={o.payment} color={o.payment==="Stripe"?C.purple:C.blue} bg={`${o.payment==="Stripe"?C.purple:C.blue}15`} border={`${o.payment==="Stripe"?C.purple:C.blue}33`}/></td>
                <td style={{padding:"10px 14px"}}><Badge label={o.status} color={statusColor(o.status)} bg={`${statusColor(o.status)}15`} border={`${statusColor(o.status)}33`}/></td>
              </tr>);
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ══ ACCOUNTING SCREEN ═══════════════════════════════════════════════════ */
const Accounting=()=>{
  const revenue=ACCOUNTING.filter(t=>t.type==="Revenue").reduce((a,t)=>a+t.amount,0);
  const expenses=ACCOUNTING.filter(t=>t.type==="Expense").reduce((a,t)=>a+t.amount,0);
  const refunds=ACCOUNTING.filter(t=>t.type==="Refund").reduce((a,t)=>a+t.amount,0);
  const net=revenue+expenses+refunds;
  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",marginBottom:22}}>
        <div><SL>Financial Records</SL><h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Accounting <GoldText size={26}>Ledger</GoldText></h2></div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:11,marginBottom:20}}>
        <StatCard label="Revenue" value={`CA$${revenue.toFixed(2)}`} color={C.green} delay={0}/>
        <StatCard label="Expenses" value={`CA$${Math.abs(expenses).toFixed(2)}`} color={C.red} delay={.05}/>
        <StatCard label="Refunds" value={`CA$${Math.abs(refunds).toFixed(2)}`} color={C.copper} delay={.1}/>
        <StatCard label="Net P&L" value={`CA$${net.toFixed(2)}`} color={C.gold} delay={.15}/>
      </div>
      <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
            {["Date","Description","Category","Type","Amount"].map(h=>(
              <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {ACCOUNTING.map((t,i)=>(
              <tr key={i} className="row-hover" style={{borderBottom:i<ACCOUNTING.length-1?`0.5px solid ${C.border}`:"none"}}>
                <td style={{padding:"11px 14px",fontFamily:SANS,fontSize:10,color:C.textDim}}>{t.date}</td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:13,color:C.text}}>{t.desc}</td>
                <td style={{padding:"11px 14px"}}><Badge label={t.cat} color={t.cat==="Sales"?C.green:t.cat==="Refund"?C.red:C.textSub} bg={`${t.cat==="Sales"?C.green:t.cat==="Refund"?C.red:C.textSub}12`} border={`${t.cat==="Sales"?C.green:t.cat==="Refund"?C.red:C.textSub}33`}/></td>
                <td style={{padding:"11px 14px"}}><Badge label={t.type} color={t.type==="Revenue"?C.green:t.type==="Expense"?C.red:C.copper} bg={`${t.type==="Revenue"?C.green:t.type==="Expense"?C.red:C.copper}12`} border={`${t.type==="Revenue"?C.green:t.type==="Expense"?C.red:C.copper}33`}/></td>
                <td style={{padding:"11px 14px",fontFamily:SERIF,fontSize:15,fontWeight:300,color:t.amount>0?C.green:C.red}}>{t.amount>0?"+":""}{"CA$"}{Math.abs(t.amount).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr style={{borderTop:`0.5px solid ${C.borderGold}`}}>
            <td colSpan={4} style={{padding:"13px 14px",fontFamily:SANS,fontSize:8,letterSpacing:"0.15em",textTransform:"uppercase",color:C.textDim}}>Net Total</td>
            <td style={{padding:"13px 14px"}}><GoldText size={18} weight={300}>{"CA$"}{net.toFixed(2)}</GoldText></td>
          </tr></tfoot>
        </table>
      </div>
    </div>
  );
};

/* ── NAV ─────────────────────────────────────────────────────────────────── */
const SIGNAL_ENGINE_URL = "https://trade-alerts-75.preview.emergentagent.com";

const NAV=[
  // ══════════════════════════════════════════════════════════════
  // COMMERCE
  // ══════════════════════════════════════════════════════════════
  {id:"dash",label:"Dashboard",icon:"dash",group:"Commerce"},
  {id:"inv",label:"Inventory",icon:"inv",group:"Commerce"},
  {id:"sync",label:"Product Sync",icon:"sync",group:"Commerce"},
  {id:"orders",label:"Orders",icon:"orders",group:"Commerce"},
  {id:"acct",label:"Accounting",icon:"accounting",group:"Commerce"},
  
  // ══════════════════════════════════════════════════════════════
  // CUSTOMERS
  // ══════════════════════════════════════════════════════════════
  {id:"crm",label:"CRM",icon:"crm",group:"Customers"},
  {id:"sub",label:"Subscribers",icon:"sub",badge:5,group:"Customers"},
  {id:"aiinsights",label:"AI Insights",icon:"brain",group:"Customers"},
  {id:"languages",label:"Languages",icon:"globe",group:"Customers"},
  
  // ══════════════════════════════════════════════════════════════
  // MARKETING
  // ══════════════════════════════════════════════════════════════
  {id:"email",label:"Email Center",icon:"mail",group:"Marketing"},
  {id:"content",label:"Content Studio",icon:"sparkles",group:"Marketing"},
  {id:"compliance",label:"Compliance",icon:"shield",group:"Marketing"},
  {id:"outreach",label:"Proactive Outreach",icon:"send",group:"Marketing"},
  
  // ══════════════════════════════════════════════════════════════
  // AI & SUPPORT
  // ══════════════════════════════════════════════════════════════
  {id:"ai",label:"AI Hub",icon:"ai",group:"AI & Support"},
  {id:"adminai",label:"Admin Action AI",icon:"terminal",group:"AI & Support"},
  {id:"support",label:"Live Support",icon:"support",group:"AI & Support"},
  
  // ══════════════════════════════════════════════════════════════
  // BRANDS & VOICE
  // ══════════════════════════════════════════════════════════════
  {id:"voice",label:"Voice Calls",icon:"phone",group:"Brands"},
  {id:"phones",label:"Phone Numbers",icon:"phone",group:"Brands"},
  
  // ══════════════════════════════════════════════════════════════
  // SYSTEM
  // ══════════════════════════════════════════════════════════════
  {id:"autoheal",label:"System Health",icon:"activity",group:"System"},
  {id:"siteaudit",label:"Site Audit",icon:"shield",group:"System"},
  {id:"apikeys",label:"API Keys",icon:"key",group:"System"},
  {id:"crashes",label:"Crash Dashboard",icon:"shield",group:"System"},
  {id:"fraud",label:"Fraud Detection",icon:"shield",group:"System"},
  
  // ══════════════════════════════════════════════════════════════
  // EXTERNAL
  // ══════════════════════════════════════════════════════════════
  {id:"signal",label:"Signal Engine",icon:"chart",external:true,url:`${SIGNAL_ENGINE_URL}?install=true`,group:"External"},
];

export default function AdminPanel(){
  const [page,setPage]=useState("dash");
  const [sideOpen,setSideOpen]=useState(true);
  const [products,setProducts]=useState(INIT_PRODUCTS);
  const [subscribers,setSubscribers]=useState(INIT_SUBS);
  const [quickStockProduct,setQuickStockProduct]=useState(null);
  const [isLive,setIsLive]=useState(true);
  const [notifications,setNotifications]=useState([]);
  const [showNotifications,setShowNotifications]=useState(false);

  // Fetch live data on mount
  useEffect(()=>{
    apiReq("GET","/api/products")
      .then(data=>setProducts(data.map(normalizeProduct)))
      .catch(()=>{});
    apiReq("GET","/api/crm/subscribers")
      .then(data=>setSubscribers(data.map(normalizeSubscriber)))
      .catch(()=>{});
    // Fetch maintenance mode status
    apiReq("GET","/api/store-settings")
      .then(data=>setIsLive(!data.maintenance_mode))
      .catch(()=>{});
    // Fetch notifications
    fetchNotifications();
  },[]);

  const fetchNotifications=()=>{
    apiReq("GET","/api/admin/notifications")
      .then(data=>setNotifications(data?.notifications||data||[]))
      .catch(()=>setNotifications([]));
  };

  const toggleMaintenanceMode=async()=>{
    try{
      await apiReq("POST","/api/admin/maintenance-mode",{enabled:isLive});
      setIsLive(!isLive);
    }catch(e){
      alert("Failed to toggle maintenance mode");
    }
  };

  const markNotificationRead=async(id)=>{
    try{
      await apiReq("PUT",`/api/admin/notifications/mark-read`,{notification_ids:[id]});
      setNotifications(prev=>prev.map(n=>n.id===id?{...n,read:true}:n));
    }catch(e){}
  };

  // Keyboard shortcuts - N for new product, S for save (handled in modals), Esc for close (handled in modals)
  const handleKeyboardShortcuts=useCallback((e)=>{
    // Only trigger if no input/textarea is focused
    const isInputFocused=document.activeElement?.tagName==="INPUT"||document.activeElement?.tagName==="TEXTAREA";
    if(isInputFocused) return;
    
    // N - New product (only when on Inventory page)
    if(e.key.toLowerCase()==="n"&&page==="inv"){
      e.preventDefault();
      // Trigger add product modal - we'll use a custom event
      window.dispatchEvent(new CustomEvent("admin-add-product"));
    }
  },[page]);
  
  useEffect(()=>{
    window.addEventListener("keydown",handleKeyboardShortcuts);
    return ()=>window.removeEventListener("keydown",handleKeyboardShortcuts);
  },[handleKeyboardShortcuts]);

  // Refresh products after stock update
  const refreshProducts=async()=>{
    try{
      const data=await apiReq("GET","/api/products");
      setProducts(data.map(normalizeProduct));
    }catch{}
    setQuickStockProduct(null);
  };

  const screens={
    dash:<Dashboard products={products} onQuickAdjust={setQuickStockProduct}/>,
    perf:<ProductPerformance products={products}/>,
    inv:<Inventory products={products} setProducts={setProducts}/>,
    sync:<ProductSyncStatus/>,
    crm:<CRM/>,
    orders:<OrdersPanel products={products}/>,
    carts:<AbandonedCarts products={products}/>,
    acct:<Accounting/>,
    sub:<Subscribers subscribers={subscribers} setSubscribers={setSubscribers}/>,
    ai:<AIHub products={products} subscribers={subscribers}/>,
    adminai:<AdminActionAI/>,
    voice:<VoiceCallsDashboard/>,
    support:<AdminLiveSupport adminId={`admin-${Date.now()}`} apiBase={BASE_URL}/>,
    autoheal:<AutoHealDashboard/>,
    email:<EmailCenter/>,
    content:<ContentStudio/>,
    compliance:<ComplianceMonitor/>,
    apikeys:<APIKeyManager/>,
    crashes:<CrashDashboard/>,
    // NEW SCREENS
    siteaudit:<SiteAuditDashboard/>,
    outreach:<ProactiveOutreachDashboard/>,
    aiinsights:<CustomerAIInsights/>,
    languages:<LanguageAnalytics/>,
    phones:<PhoneManagement/>,
    fraud:<FraudDashboard/>,
  };

  // Clear cache function
  const clearCache = async () => {
    try {
      // Clear localStorage
      localStorage.clear();
      
      // Clear sessionStorage
      sessionStorage.clear();
      
      // Clear service worker caches
      if ('caches' in window) {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map(name => caches.delete(name)));
      }
      
      // Unregister service workers
      if ('serviceWorker' in navigator) {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map(reg => reg.unregister()));
      }
      
      // Show success message
      alert('✓ Cache cleared successfully!\n\nCleared:\n• LocalStorage\n• SessionStorage\n• Service Worker Cache\n• Service Worker Registrations\n\nPage will reload...');
      
      // Force reload without cache
      window.location.reload(true);
    } catch (error) {
      console.error('Cache clear error:', error);
      alert('Cache cleared (partial). Reloading...');
      window.location.reload(true);
    }
  };
  
  return(
    <AdminErrorBoundary>
    <div className="rr-admin" style={{display:"flex",height:"100vh",width:"100vw",background:C.void,fontFamily:SERIF,overflow:"hidden"}}>
      <Styles/>
      {/* SIDEBAR - Takes ~200px on desktop, shrinks on mobile */}
      <aside style={{
        width:sideOpen?200:50,
        minWidth:sideOpen?200:50,
        maxWidth:sideOpen?200:50,
        background:C.noir,
        borderRight:`0.5px solid ${C.border}`,
        display:"flex",
        flexDirection:"column",
        transition:"width .25s ease",
        height:"100vh",
        flexShrink:0,
        overflow:"hidden",
        position:"relative"
      }}>
        {/* Logo & Title - Fixed height */}
        <div style={{padding:"16px 14px",borderBottom:`0.5px solid ${C.border}`,display:"flex",alignItems:"center",gap:10,height:60,flexShrink:0}}>
          <div style={{width:28,height:28,borderRadius:"50%",background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
            display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
            <Ico n="logo" size={12} color={C.void}/>
          </div>
          {sideOpen&&<div>
            <p style={{fontFamily:SERIF,fontSize:13,fontWeight:400,color:C.text,lineHeight:1}}>ReRoots</p>
            <p style={{fontFamily:SANS,fontSize:7,letterSpacing:"0.15em",textTransform:"uppercase",color:C.textDim,marginTop:2}}>Admin Panel</p>
          </div>}
        </div>
        {/* Nav Items - Takes remaining space */}
        <nav style={{height:"calc(100vh - 110px)",padding:"12px 0",overflowY:"auto",overflowX:"hidden"}}>
          {/* Group nav items by their group property */}
          {(() => {
            const groups = {};
            NAV.forEach(n => {
              const group = n.group || 'Other';
              if (!groups[group]) groups[group] = [];
              groups[group].push(n);
            });
            
            return Object.entries(groups).map(([groupName, items]) => (
              <div key={groupName} style={{marginBottom: sideOpen ? 16 : 8}}>
                {sideOpen && (
                  <div style={{
                    padding: "8px 16px 4px",
                    fontFamily: SANS,
                    fontSize: 9,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: C.textDim,
                    opacity: 0.7
                  }}>
                    {groupName}
                  </div>
                )}
                {items.map(n => (
                  n.external ? (
                    <div key={n.id} style={{width:"100%",display:"flex",alignItems:"center",position:"relative",boxSizing:"border-box"}}>
                      <a 
                        href={n.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="nav-item"
                        data-testid="signal-engine-link"
                        style={{flex:1,display:"flex",alignItems:"center",gap:12,padding:"10px 16px",background:"transparent",border:"none",cursor:"pointer",textAlign:"left",textDecoration:"none",color:"inherit"}}
                      >
                        <Ico n={n.icon} size={15} color={C.gold}/>
                        {sideOpen&&<span style={{fontFamily:SANS,fontSize:10,letterSpacing:"0.05em",color:C.gold}}>{n.label}</span>}
                        {sideOpen&&<Ico n="external" size={11} color={C.textDim} style={{marginLeft:"auto"}}/>}
                      </a>
                    </div>
                  ) : (
                    <button key={n.id} onClick={()=>setPage(n.id)} className={`nav-item ${page===n.id?"nav-active":""}`}
                      style={{width:"100%",display:"flex",alignItems:"center",gap:12,padding:"10px 16px",background:"transparent",border:"none",cursor:"pointer",textAlign:"left",position:"relative",boxSizing:"border-box"}}>
                      <Ico n={n.icon} size={15} color={page===n.id?C.gold:C.textDim}/>
                      {sideOpen&&<span style={{fontFamily:SANS,fontSize:10,letterSpacing:"0.05em",color:page===n.id?C.gold:C.textSub}}>{n.label}</span>}
                      {sideOpen&&n.badge&&<span style={{marginLeft:"auto",background:C.gold,color:C.void,fontSize:8,fontFamily:SANS,padding:"2px 5px",borderRadius:10,fontWeight:500}}>{n.badge}</span>}
                    </button>
                  )
                ))}
              </div>
            ));
          })()}
        </nav>
        {/* Footer - Fixed at bottom */}
        {sideOpen&&<div style={{padding:"14px 16px",borderTop:`0.5px solid ${C.border}`,background:C.noir,height:50,flexShrink:0}}>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>Tj Sandhu · Founder</p>
          <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:2}}>reroots.ca</p>
        </div>}
      </aside>
      
      {/* MAIN CONTENT */}
      <main style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden",minWidth:0}}>
        {/* Header */}
        <header style={{height:56,background:C.noir,borderBottom:`0.5px solid ${C.border}`,
          display:"flex",alignItems:"center",justifyContent:"space-between",padding:"0 20px",flexShrink:0}}>
          <div style={{display:"flex",alignItems:"center",gap:14}}>
            <button className="btn" onClick={()=>setSideOpen(o=>!o)} style={{background:"transparent",border:"none",padding:4}}>
              <Ico n="menu" size={18} color={C.textDim}/>
            </button>
            <h1 style={{fontFamily:SERIF,fontSize:15,fontWeight:300,color:C.text}}>{NAV.find(n=>n.id===page)?.label}</h1>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:14}}>
            {/* Clear Cache Button */}
            <button onClick={clearCache} className="btn" 
              style={{display:"flex",alignItems:"center",gap:6,background:`${C.red}15`,border:`1px solid ${C.red}30`,borderRadius:3,padding:"5px 12px",cursor:"pointer"}}>
              <Ico n="trash" size={12} color={C.red}/>
              <span style={{fontFamily:SANS,fontSize:9,color:C.red,letterSpacing:"0.08em",fontWeight:500}}>CLEAR CACHE</span>
            </button>
            <button onClick={toggleMaintenanceMode} className="btn" style={{display:"flex",alignItems:"center",gap:6,background:isLive?`${C.green}15`:`${C.red}15`,border:`1px solid ${isLive?C.green:C.red}30`,borderRadius:3,padding:"5px 12px",cursor:"pointer"}}>
              <div style={{width:5,height:5,borderRadius:"50%",background:isLive?C.green:C.red,animation:isLive?"pulse 2s infinite":"none"}}/>
              <span style={{fontFamily:SANS,fontSize:9,color:isLive?C.green:C.red,letterSpacing:"0.1em",fontWeight:500}}>{isLive?"LIVE":"MAINTENANCE"}</span>
            </button>
            <div style={{position:"relative"}}>
              <button onClick={()=>setShowNotifications(!showNotifications)} className="btn" style={{background:"transparent",border:"none",position:"relative",padding:4,cursor:"pointer"}}>
                <Ico n="bell" size={18} color={C.textDim}/>
                {notifications.filter(n=>!n.read).length>0&&<div style={{position:"absolute",top:0,right:0,minWidth:14,height:14,borderRadius:"50%",background:C.red,border:`2px solid ${C.noir}`,display:"flex",alignItems:"center",justifyContent:"center"}}>
                  <span style={{fontFamily:SANS,fontSize:8,color:"#fff",fontWeight:600}}>{notifications.filter(n=>!n.read).length}</span>
                </div>}
              </button>
              {showNotifications&&<div style={{position:"absolute",top:"100%",right:0,marginTop:8,width:320,maxHeight:400,overflowY:"auto",background:C.noir,border:`1px solid ${C.border}`,borderRadius:6,boxShadow:"0 8px 32px rgba(0,0,0,0.4)",zIndex:1000}}>
                <div style={{padding:"12px 16px",borderBottom:`1px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <span style={{fontFamily:SANS,fontSize:11,color:C.text,letterSpacing:"0.05em"}}>NOTIFICATIONS</span>
                  <button onClick={()=>setShowNotifications(false)} style={{background:"transparent",border:"none",cursor:"pointer"}}><Ico n="x" size={14} color={C.textDim}/></button>
                </div>
                {notifications.length===0?<p style={{padding:20,textAlign:"center",color:C.textDim,fontFamily:SANS,fontSize:12}}>No notifications</p>:
                  notifications.map(n=>(
                    <div key={n.id} onClick={()=>markNotificationRead(n.id)} style={{padding:"12px 16px",borderBottom:`1px solid ${C.border}05`,cursor:"pointer",background:n.read?"transparent":`${C.gold}08`}}>
                      <p style={{fontFamily:SANS,fontSize:11,color:n.read?C.textDim:C.text,marginBottom:4}}>{n.title||n.message}</p>
                      <p style={{fontFamily:SANS,fontSize:9,color:C.textDim}}>{n.time||new Date(n.created_at).toLocaleString()}</p>
                    </div>
                  ))
                }
              </div>}
            </div>
            <a href="/" style={{display:"flex",alignItems:"center",gap:6,background:`${C.gold}15`,border:`1px solid ${C.gold}30`,borderRadius:3,padding:"5px 12px",textDecoration:"none",cursor:"pointer"}}>
              <Ico n="external-link" size={12} color={C.gold}/>
              <span style={{fontFamily:SANS,fontSize:9,color:C.gold,letterSpacing:"0.08em",fontWeight:500}}>VIEW SHOP</span>
            </a>
            <div style={{width:32,height:32,borderRadius:"50%",background:`linear-gradient(135deg,${C.goldDeep},${C.goldBright})`,
              display:"flex",alignItems:"center",justifyContent:"center",fontFamily:SERIF,fontSize:12,fontWeight:500,color:C.void}}>TJ</div>
          </div>
        </header>
        {/* Content */}
        <div style={{flex:1,overflowY:"auto",overflowX:"hidden"}}>{screens[page]}</div>
      </main>
      
      {/* Global Quick Stock Modal */}
      {quickStockProduct&&<BulkStockModal product={quickStockProduct} onClose={()=>setQuickStockProduct(null)} onSave={refreshProducts}/>}
    </div>
    </AdminErrorBoundary>
  );
}

/* ── SUBSCRIBERS ─────────────────────────────────────────────────────────── */
function Subscribers({subscribers,setSubscribers}){
  const [offerModal,setOfferModal]=useState(false);
  const [search,setSearch]=useState("");
  const [loadingId,setLoadingId]=useState(null);

  const toggleOffer=async(s)=>{
    setLoadingId(s.id);
    const newOffers=!s.offers;
    setSubscribers(subs=>subs.map(x=>x.id===s.id?{...x,offers:newOffers,status:newOffers?"Active":"Opted Out"}:x));
    try{
      await apiReq("PATCH",`/api/crm/subscribers/${s.id}`,{offers_opt_in:newOffers});
    }catch{
      setSubscribers(subs=>subs.map(x=>x.id===s.id?{...x,offers:s.offers,status:s.status}:x));
    }
    setLoadingId(null);
  };

  const filtered=subscribers.filter(s=>
    s.name.toLowerCase().includes(search.toLowerCase())||
    s.email.toLowerCase().includes(search.toLowerCase())
  );
  const active=subscribers.filter(s=>s.status==="Active").length;
  const optedOut=subscribers.filter(s=>s.status==="Opted Out").length;
  const withBirthday=subscribers.filter(s=>s.birthday).length;
  
  return(
    <div style={{padding:"26px 28px 40px",animation:"fadeUp .4s ease both"}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:22}}>
        <div>
          <SL>Email Marketing</SL>
          <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>Subscriber <GoldText size={26}>List</GoldText></h2>
        </div>
        <div style={{display:"flex",gap:10}}>
          <div style={{display:"flex",alignItems:"center",gap:8,background:C.card,border:`0.5px solid ${C.border}`,borderRadius:4,padding:"8px 12px"}}>
            <Ico n="search" size={13} color={C.textDim}/>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search subscribers..."
              style={{background:"transparent",border:"none",fontFamily:SANS,fontSize:11,color:C.text,width:150}}/>
          </div>
          <button className="btn" onClick={()=>setOfferModal(true)}
            style={{background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,border:"none",borderRadius:4,
              padding:"11px 18px",fontFamily:SANS,fontSize:10,letterSpacing:"0.15em",textTransform:"uppercase",color:C.void,
              display:"flex",alignItems:"center",gap:8}}>
            <Ico n="send" size={13} color={C.void}/> Send Offer
          </button>
        </div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:11,marginBottom:22}}>
        <StatCard label="Total Subscribers" value={subscribers.length.toString()} sub="Registered" color={C.blue} delay={0}/>
        <StatCard label="Active (Offers On)" value={active.toString()} sub="Receiving emails" color={C.green} delay={.05}/>
        <StatCard label="Opted Out" value={optedOut.toString()} sub="No marketing" color={C.red} delay={.1}/>
        <StatCard label="Birthday Data" value={withBirthday.toString()} sub="For birthday pts" color={C.gold} delay={.15}/>
      </div>
      {subscribers.length===0?(
        <div style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,padding:"48px",textAlign:"center"}}>
          <div style={{width:56,height:56,borderRadius:"50%",background:`${C.gold}10`,border:`0.5px solid ${C.borderGold}`,
            margin:"0 auto 16px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Ico n="sub" size={22} color={C.gold}/>
          </div>
          <p style={{fontFamily:SERIF,fontSize:18,fontWeight:300,color:C.text,marginBottom:8}}>No subscribers yet</p>
          <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,letterSpacing:"0.05em"}}>
            Signups from the customer app will appear here automatically
          </p>
        </div>
      ):(
        <div className="card" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,overflow:"hidden"}}>
          <div style={{padding:"13px 20px 11px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <p style={{fontFamily:SERIF,fontSize:14,color:C.text}}>Subscriber Roster - {filtered.length} records</p>
            <div style={{display:"flex",alignItems:"center",gap:6,background:`${C.green}10`,border:`0.5px solid ${C.green}22`,borderRadius:2,padding:"4px 10px"}}>
              <div style={{width:5,height:5,borderRadius:"50%",background:C.green,animation:"pulse 2s infinite"}}/>
              <span style={{fontFamily:SANS,fontSize:8,color:C.green,letterSpacing:"0.12em"}}>{active} ACTIVE</span>
            </div>
          </div>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr style={{borderBottom:`0.5px solid ${C.border}`}}>
              {["Name","Email","Skin Type","Tier","Offers","Status"].map(h=>(
                <th key={h} style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.12em",textTransform:"uppercase",color:C.textDim,padding:"10px 14px",textAlign:"left",fontWeight:400}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {filtered.map((s,i)=>(
                <tr key={s.id} className="row-hover" style={{borderBottom:i<filtered.length-1?`0.5px solid ${C.border}`:"none"}}>
                  <td style={{padding:"11px 14px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:9}}>
                      <div style={{width:28,height:28,borderRadius:"50%",background:`${C.gold}18`,border:`0.5px solid ${C.borderGold}`,
                        display:"flex",alignItems:"center",justifyContent:"center"}}>
                        <span style={{fontFamily:SERIF,fontSize:11,color:C.gold}}>{s.name[0]}</span>
                      </div>
                      <p style={{fontFamily:SERIF,fontSize:13,color:C.text}}>{s.name}</p>
                    </div>
                  </td>
                  <td style={{padding:"11px 14px",fontFamily:SANS,fontSize:10,color:C.textSub}}>{s.email}</td>
                  <td style={{padding:"11px 14px",fontFamily:SANS,fontSize:10,color:C.textDim}}>{s.skinType||"-"}</td>
                  <td style={{padding:"11px 14px"}}>{(()=>{const tc=({Elite:C.purple,Diamond:C.blue,Gold:C.gold,Silver:"#9CA3AF"})[s.tier]||"#9CA3AF";return <Badge label={s.tier} color={tc} bg={tc+"18"} border={tc+"33"}/>;})()}</td>
                  <td style={{padding:"11px 14px"}}>
                    <div style={{width:28,height:14,borderRadius:7,background:s.offers?C.green:C.border,position:"relative",cursor:loadingId===s.id?"not-allowed":"pointer",opacity:loadingId===s.id?0.5:1}}
                      onClick={()=>loadingId!==s.id&&toggleOffer(s)}>
                      <div style={{width:10,height:10,borderRadius:"50%",background:"white",position:"absolute",top:2,
                        left:s.offers?16:2,transition:"left .2s"}}/>
                    </div>
                  </td>
                  <td style={{padding:"11px 14px"}}><Badge label={s.status} color={s.status==="Active"?C.green:C.red} bg={`${s.status==="Active"?C.green:C.red}15`} border={`${s.status==="Active"?C.green:C.red}33`}/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {offerModal&&<OfferModal subscribers={subscribers} onClose={()=>setOfferModal(false)}/>}
    </div>
  );
}

/* ── OFFER MODAL ─────────────────────────────────────────────────────────── */
function OfferModal({subscribers,onClose}){
  const [subject,setSubject]=useState("");
  const [body,setBody]=useState("");
  const [discount,setDiscount]=useState("");
  const [sent,setSent]=useState(false);
  const [sending,setSending]=useState(false);
  const [sentCount,setSentCount]=useState(0);
  const active=subscribers.filter(s=>s.status==="Active");
  
  const doSend=async()=>{
    if(!subject||!body) return;
    setSending(true);
    try{
      const result=await apiReq("POST","/api/marketing/send-offer",{
        subject,
        body,
        discount_code:discount||null,
        recipient_filter:"active",
        template_tokens:["{{name}}","{{tier}}","{{points}}"],
      });
      setSentCount(result.sent_count??active.length);
      setSent(true);
    }catch(e){
      alert(e.message||"Send failed. Check SendGrid configuration.");
    }finally{setSending(false);}
  };
  
  if(sent) return(
    <div style={{position:"fixed",inset:0,background:"rgba(5,5,7,0.88)",zIndex:2000,
      display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(16px)"}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:C.card,border:`0.5px solid ${C.borderGold}`,borderRadius:20,
        padding:"48px 40px",maxWidth:440,width:"100%",textAlign:"center",animation:"modalIn 0.28s ease both"}}>
        <div style={{width:64,height:64,borderRadius:"50%",background:`${C.green}18`,border:`0.5px solid ${C.green}44`,
          margin:"0 auto 20px",display:"flex",alignItems:"center",justifyContent:"center"}}>
          <Ico n="check" size={28} color={C.green} sw={1.5}/>
        </div>
        <h3 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginBottom:8}}>Offer <GoldText size={26}>Sent!</GoldText></h3>
        <p style={{fontFamily:SANS,fontSize:12,color:C.textDim,marginBottom:4,letterSpacing:"0.05em"}}>{sentCount} subscribers notified via SendGrid</p>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:14,color:C.textSub,marginBottom:28}}>"{subject}"</p>
        <button className="btn" onClick={onClose} style={{background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,border:"none",borderRadius:4,
          padding:"13px 36px",fontFamily:SANS,fontSize:10,letterSpacing:"0.16em",textTransform:"uppercase",color:C.void}}>Done</button>
      </div>
    </div>
  );
  
  return(
    <div style={{position:"fixed",inset:0,background:"rgba(5,5,7,0.88)",zIndex:2000,
      display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(16px)",padding:24}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:C.card,border:`0.5px solid ${C.borderGold}`,borderRadius:20,
        width:"100%",maxWidth:560,animation:"modalIn 0.28s ease both",boxShadow:"0 32px 80px rgba(0,0,0,0.6)"}}>
        <div style={{padding:"22px 26px",borderBottom:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <div>
            <SL style={{marginBottom:5}}>Email Marketing</SL>
            <h3 style={{fontFamily:SERIF,fontSize:22,fontWeight:300,color:C.text}}>Send <GoldText size={22} weight={300}>Offer</GoldText></h3>
          </div>
          <button onClick={onClose} className="btn" style={{background:"transparent",border:`0.5px solid ${C.border}`,borderRadius:6,width:36,height:36,display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Ico n="close" size={15} color={C.textDim}/>
          </button>
        </div>
        <div style={{padding:"22px 26px"}}>
          <div style={{background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:8,padding:"13px 16px",marginBottom:18,
            display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <div style={{display:"flex",alignItems:"center",gap:10}}>
              <Ico n="sub" size={14} color={C.gold}/>
              <span style={{fontFamily:SANS,fontSize:11,color:C.text}}>{active.length} active subscribers</span>
            </div>
            <Badge label="Offer Enabled" color={C.green} bg={`${C.green}15`} border={`${C.green}33`}/>
          </div>
          <div style={{marginBottom:13}}>
            <SL style={{marginBottom:6}}>Subject Line</SL>
            <input value={subject} onChange={e=>setSubject(e.target.value)} placeholder="Exclusive offer for you, [name]..." className="inp"
              style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
                padding:"11px 14px",color:C.text,fontFamily:SERIF,fontSize:14,fontWeight:300}}/>
          </div>
          <div style={{marginBottom:13}}>
            <SL style={{marginBottom:6}}>Discount Code (optional)</SL>
            <input value={discount} onChange={e=>setDiscount(e.target.value.toUpperCase())} placeholder="GOLD20 / LAUNCH15..." className="inp"
              style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
                padding:"11px 14px",color:discount?C.gold:C.textDim,fontFamily:SANS,fontSize:13,letterSpacing:"0.1em"}}/>
          </div>
          <div style={{marginBottom:20}}>
            <SL style={{marginBottom:6}}>Message Body</SL>
            <textarea value={body} onChange={e=>setBody(e.target.value)} rows={5}
              placeholder="Write your offer message here... Personalization tokens: [name], [tier], [points]" className="inp"
              style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
                padding:"11px 14px",color:C.text,fontFamily:SERIF,fontSize:13,fontWeight:300,resize:"vertical"}}/>
          </div>
          {discount&&<div style={{background:`${C.gold}08`,border:`0.5px solid ${C.borderGold}`,borderRadius:8,
            padding:"11px 14px",marginBottom:18,display:"flex",alignItems:"center",gap:10}}>
            <Ico n="offer" size={14} color={C.gold}/>
            <span style={{fontFamily:SANS,fontSize:11,color:C.gold,letterSpacing:"0.08em"}}>Discount code <strong>{discount}</strong> will be included automatically</span>
          </div>}
          <div style={{display:"flex",gap:10}}>
            <button className="btn" onClick={onClose} style={{flex:1,background:"transparent",border:`0.5px solid ${C.border}`,
              borderRadius:4,padding:"13px",fontFamily:SANS,fontSize:10,letterSpacing:"0.14em",textTransform:"uppercase",color:C.textDim}}>Cancel</button>
            <button className="btn" onClick={doSend} disabled={sending||!subject||!body} style={{flex:2,
              background:subject&&body?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:`${C.gold}22`,
              border:"none",borderRadius:4,padding:"13px",fontFamily:SANS,fontSize:10,letterSpacing:"0.14em",
              textTransform:"uppercase",color:subject&&body?C.void:C.textDim}}>
              {sending?`Sending to ${active.length}...`:`Send to ${active.length} Subscribers`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── AI HUB ──────────────────────────────────────────────────────────────── */
function AIHub({products,subscribers}){
  const [msgs,setMsgs]=useState([{role:"assistant",content:"Welcome to the ReRoots Intelligence Hub. I have full context on your inventory, subscribers, CRM, and financials. What would you like to optimize today?"}]);
  const [input,setInput]=useState("");
  const [loading,setLoading]=useState(false);
  const endRef=useRef(null);
  useEffect(()=>endRef.current?.scrollIntoView({behavior:"smooth"}),[msgs]);
  
  const send=async()=>{
    if(!input.trim()||loading) return;
    const msg=input.trim();setInput("");
    setMsgs(m=>[...m,{role:"user",content:msg}]);setLoading(true);
    try{
      const ctx=`PRODUCTS: ${products.map(p=>`${p.name} ${p.stock}u(${p.status})`).join(", ")}. SUBSCRIBERS: ${subscribers.length} total, ${subscribers.filter(s=>s.status==="Active").length} active. CRM: 284 customers, avg LTV CA$524, churn 2.1%. FINANCIALS: Revenue CA$12,800 MTD, Net CA$128.`;
      const res=await fetch("https://api.anthropic.com/v1/messages",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({model:"claude-sonnet-4-20250514",max_tokens:1000,
          system:`You are the ReRoots AI Intelligence Hub for Reroots Aesthetics Inc. (reroots.ca) by Tj Sandhu. Data: ${ctx}. Think as COO+CMO+CFO. Sharp, data-driven, strategic. Reference specific numbers. Max 180 words.`,
          messages:[...msgs.map(m=>({role:m.role,content:m.content})),{role:"user",content:msg}]})});
      const data=await res.json();
      setMsgs(m=>[...m,{role:"assistant",content:data.content?.[0]?.text||"Please retry."}]);
    }catch{setMsgs(m=>[...m,{role:"assistant",content:"Connection error."}]);}
    setLoading(false);
  };
  
  const quickQ=["Restock priority?","Best retention offer?","Financial health summary","Top subscriber segment?"];
  
  return(
    <div style={{padding:"26px 28px 20px",display:"flex",flexDirection:"column",height:"calc(100vh - 56px)",animation:"fadeUp .4s ease both"}}>
      <div style={{marginBottom:18}}>
        <SL>Autonomous Business Intelligence</SL>
        <h2 style={{fontFamily:SERIF,fontSize:26,fontWeight:300,color:C.text,marginTop:4}}>AI <GoldText size={26}>Intelligence Hub</GoldText></h2>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:11,marginBottom:16}}>
        {products.map(p=>(
          <div key={p.id} style={{background:p.hue,border:`0.5px solid ${p.accent}22`,borderRadius:9,padding:"12px",display:"flex",alignItems:"center",gap:11}}>
            <div style={{flexShrink:0}}><ProductImg p={p} size={40}/></div>
            <div>
              <SL style={{color:p.accent,marginBottom:3}}>{p.subtitle}</SL>
              <p style={{fontFamily:SERIF,fontSize:11,color:C.text,lineHeight:1.2}}>{p.name}</p>
              <p style={{fontFamily:SANS,fontSize:9,color:p.status==="Critical"?C.red:p.status==="Low"?C.copper:C.green,marginTop:2}}>* {p.stock}u - {p.status}</p>
            </div>
          </div>
        ))}
      </div>
      <div style={{flex:1,background:C.card,border:`0.5px solid ${C.border}`,borderRadius:13,display:"flex",flexDirection:"column",overflow:"hidden"}}>
        <div style={{flex:1,overflowY:"auto",padding:"16px 20px",display:"flex",flexDirection:"column",gap:11}}>
          {msgs.map((m,i)=>(
            <div key={i} style={{display:"flex",justifyContent:m.role==="user"?"flex-end":"flex-start"}}>
              <div style={{maxWidth:"74%",padding:"12px 16px",
                borderRadius:m.role==="user"?"15px 15px 4px 15px":"15px 15px 15px 4px",
                background:m.role==="user"?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.lifted,
                border:m.role==="assistant"?`0.5px solid ${C.border}`:"none",
                color:m.role==="user"?C.void:C.text,fontFamily:SERIF,fontSize:13,lineHeight:1.7,fontWeight:300}}>{m.content}</div>
            </div>
          ))}
          {loading&&<div style={{display:"flex"}}><div style={{background:C.lifted,border:`0.5px solid ${C.border}`,
            borderRadius:"15px 15px 15px 4px",padding:"12px 18px",display:"flex",gap:5}}>
            {[0,1,2].map(i=><div key={i} style={{width:5,height:5,borderRadius:"50%",background:C.gold,animation:`pulse 1.2s ${i*0.2}s ease-in-out infinite`}}/>)}
          </div></div>}
          <div ref={endRef}/>
        </div>
        {msgs.length<=1&&<div style={{padding:"0 20px 10px",display:"flex",gap:7,flexWrap:"wrap"}}>
          {quickQ.map(q=>(<button key={q} className="btn" onClick={()=>setInput(q)} style={{background:"transparent",
            border:`0.5px solid ${C.borderGold}`,borderRadius:2,padding:"6px 12px",
            fontFamily:SANS,fontSize:9,letterSpacing:"0.07em",color:C.textSub}}>{q}</button>))}
        </div>}
        <div style={{padding:"11px 18px",borderTop:`0.5px solid ${C.border}`,display:"flex",gap:9}}>
          <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()}
            placeholder="Ask about inventory, subscribers, orders..."
            style={{flex:1,background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
              padding:"11px 14px",color:C.text,fontFamily:SERIF,fontSize:13,fontWeight:300}}/>
          <button className="btn" onClick={send} disabled={loading||!input.trim()} style={{
            background:input.trim()?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,
            border:"none",borderRadius:4,width:42,height:42,display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
            <Ico n="send" size={14} color={input.trim()?C.void:C.textDim}/>
          </button>
        </div>
      </div>
    </div>
  );
}
