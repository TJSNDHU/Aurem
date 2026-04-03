import { useState, useEffect, useRef } from "react";
import SupportChat from "../components/SupportChat";
import SupportMode from "../components/SupportMode";

/* ── API CONFIG ───────────────────────────────────────────────────────────── */
// Use production URL on reroots.ca, otherwise use env variable or origin
const getBaseUrl = () => {
  if (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) {
    return 'https://reroots.ca';
  }
  return process.env.REACT_APP_BACKEND_URL || window.location.origin;
};
const BASE_URL = getBaseUrl();
const getToken = () => localStorage.getItem("rr_token");
const setToken = (t) => localStorage.setItem("rr_token", t);
const clearToken = () => localStorage.removeItem("rr_token");

async function apiReq(method, path, body) {
  const token = getToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || data?.message || `Error ${res.status}`);
  return data;
}

function normalizeUser(u) {
  return {
    id: u.id,
    name: u.name || `${u.first_name || ""} ${u.last_name || ""}`.trim(),
    email: u.email,
    role: u.role || (u.is_admin ? "admin" : "customer"),
    tier: u.tier || "Silver",
    points: u.loyalty_points ?? u.points ?? 500,
    skinType: u.skin_type || u.skinType || "",
    birthday: u.birthday || "",
    offers: u.offers_opt_in ?? u.offers ?? true,
  };
}

const Styles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Tenor+Sans&display=swap');
    .rr-app *{box-sizing:border-box;margin:0;padding:0;}
    .rr-app ::-webkit-scrollbar{width:0;}
    @keyframes silkIn{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
    @keyframes shimmer{0%{background-position:-200% center}100%{background-position:200% center}}
    @keyframes glowPulse{0%,100%{opacity:.35}50%{opacity:.85}}
    @keyframes dotBounce{0%,80%,100%{transform:scale(.55);opacity:.4}40%{transform:scale(1);opacity:1}}
    @keyframes slideUp{from{transform:translateY(100%);opacity:0}to{transform:translateY(0);opacity:1}}
    @keyframes floatBottle{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
    @keyframes fadeIn{from{opacity:0}to{opacity:1}}
    @keyframes scaleIn{from{opacity:0;transform:scale(0.95)}to{opacity:1;transform:scale(1)}}
    .rr-app .lbtn{transition:all .28s cubic-bezier(.25,.46,.45,.94);}
    .rr-app .lbtn:active{transform:scale(0.97)!important;}
    .rr-app .lbtn:hover{opacity:.87;}
    .rr-app .chov{transition:border-color .3s,box-shadow .3s,transform .28s;}
    .rr-app .chov:hover{border-color:rgba(201,168,110,0.28)!important;box-shadow:0 14px 40px rgba(0,0,0,.5)!important;transform:translateY(-2px);}
    .rr-app .inp{transition:border-color .25s,box-shadow .25s;}
    .rr-app .inp:focus{border-color:rgba(201,168,110,0.5)!important;box-shadow:0 0 0 3px rgba(201,168,110,0.08)!important;}
    .rr-app input:focus,.rr-app textarea:focus{outline:none!important;}
    .rr-app button{-webkit-tap-highlight-color:transparent;}
  `}</style>
);

const C={
  void:"#060608",noir:"#0d0d10",surface:"#18181f",card:"#1e1e27",
  border:"rgba(255,255,255,0.07)",borderGold:"rgba(201,168,110,0.22)",
  gold:"#C9A86E",goldBright:"#E2C98A",goldDeep:"#8A6B38",champagne:"#F5E8CC",
  text:"#F0EBE0",textSub:"#A89880",textDim:"#5C5548",
  green:"#5BB88A",blue:"#6BAED6",copper:"#C07A45",purple:"#A88FD4",red:"#C0614A",
};
const SERIF="'Cormorant Garamond',Georgia,serif";
const SANS="'Tenor Sans','Gill Sans',sans-serif";

/* ── SVG BOTTLES ──────────────────────────────────────────────────────────── */
const DropperBottle=({accent="#6BAED6",accentDim="#2a4a6a",size=130})=>(
  <svg width={size} height={size*160/140} viewBox="0 0 140 160" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="db" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#1a2030"/><stop offset="50%" stopColor="#1e2840"/><stop offset="100%" stopColor="#111820"/></linearGradient>
      <linearGradient id="dc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={accentDim}/><stop offset="50%" stopColor={accent}/><stop offset="100%" stopColor={accentDim}/></linearGradient>
      <filter id="dglow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <radialGradient id="da" cx="50%" cy="50%"><stop offset="0%" stopColor={accent} stopOpacity="0.22"/><stop offset="100%" stopColor={accent} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="70" cy="80" rx="60" ry="60" fill="url(#da)"/>
    <ellipse cx="70" cy="150" rx="28" ry="6" fill={accent} opacity="0.12"/>
    <rect x="45" y="60" width="50" height="82" rx="7" fill="url(#db)" stroke={accentDim} strokeWidth="0.6"/>
    <rect x="46" y="60" width="11" height="82" rx="5" fill="rgba(255,255,255,0.05)"/>
    <rect x="49" y="78" width="42" height="46" rx="2" fill={accent} opacity="0.07" stroke={accent} strokeWidth="0.3"/>
    <text x="70" y="96" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5.5" fill={accent} letterSpacing="2.5">AURA-GEN I</text>
    <line x1="56" y1="100" x2="84" y2="100" stroke={accent} strokeWidth="0.3" opacity="0.6"/>
    <text x="70" y="109" textAnchor="middle" fontFamily="Georgia,serif" fontSize="7" fill="rgba(255,255,255,0.85)">TXA - PDRN</text>
    <line x1="56" y1="114" x2="84" y2="114" stroke={accent} strokeWidth="0.3" opacity="0.4"/>
    <text x="70" y="120" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="4" fill="rgba(255,255,255,0.35)" letterSpacing="1.5">REROOTS.CA</text>
    <rect x="57" y="44" width="26" height="19" rx="3" fill="#151e2e" stroke={accentDim} strokeWidth="0.5"/>
    <rect x="52" y="22" width="36" height="24" rx="5" fill="url(#dc)" opacity="0.95"/>
    <rect x="53" y="23" width="9" height="22" rx="4" fill="rgba(255,255,255,0.08)"/>
    <rect x="68" y="10" width="4" height="14" rx="2" fill={accentDim}/>
    <ellipse cx="70" cy="9" rx="4" ry="5" fill={accent} opacity="0.9" filter="url(#dglow)"/>
    {[[35,70],[108,88],[32,108],[112,72],[36,128]].map(([x,y],i)=>(
      <circle key={i} cx={x} cy={y} r={1.2+i*0.2} fill={accent} opacity={0.15+i*0.04}/>
    ))}
  </svg>
);
const JarProduct=({accent="#C9A86E",accentDim="#5a3e1a",size=130})=>(
  <svg width={size} height={size} viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="jb" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#1c1208"/><stop offset="50%" stopColor="#221608"/><stop offset="100%" stopColor="#140e04"/></linearGradient>
      <linearGradient id="jc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={accentDim}/><stop offset="50%" stopColor={accent}/><stop offset="100%" stopColor={accentDim}/></linearGradient>
      <radialGradient id="ja" cx="50%" cy="50%"><stop offset="0%" stopColor={accent} stopOpacity="0.16"/><stop offset="100%" stopColor={accent} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="80" cy="80" rx="65" ry="65" fill="url(#ja)"/>
    <ellipse cx="80" cy="150" rx="44" ry="7" fill={accent} opacity="0.12"/>
    <rect x="28" y="75" width="104" height="68" rx="9" fill="url(#jb)" stroke={accentDim} strokeWidth="0.6"/>
    <rect x="29" y="75" width="18" height="68" rx="7" fill="rgba(255,255,255,0.04)"/>
    <rect x="36" y="86" width="88" height="46" rx="2" fill={accent} opacity="0.06" stroke={accent} strokeWidth="0.3"/>
    <text x="80" y="103" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5.5" fill={accent} letterSpacing="2.5">AURA-GEN II</text>
    <line x1="48" y1="107" x2="112" y2="107" stroke={accent} strokeWidth="0.3" opacity="0.6"/>
    <text x="80" y="118" textAnchor="middle" fontFamily="Georgia,serif" fontSize="7.5" fill="rgba(255,255,255,0.85)">ACCELERATOR</text>
    <line x1="48" y1="123" x2="112" y2="123" stroke={accent} strokeWidth="0.3" opacity="0.4"/>
    <text x="80" y="129" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="4.5" fill="rgba(255,255,255,0.35)" letterSpacing="1.5">RICH CREAM v4</text>
    <rect x="22" y="50" width="116" height="30" rx="8" fill="url(#jc)" opacity="0.95"/>
    <rect x="23" y="51" width="22" height="28" rx="6" fill="rgba(255,255,255,0.07)"/>
    <line x1="24" y1="64" x2="136" y2="64" stroke="rgba(255,255,255,0.14)" strokeWidth="0.5"/>
    <text x="80" y="70" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5" fill="rgba(0,0,0,0.55)" letterSpacing="3">REROOTS</text>
    {[[22,92],[140,84],[20,116],[142,110]].map(([x,y],i)=>(<circle key={i} cx={x} cy={y} r={1.2+i*0.2} fill={accent} opacity={0.14+i*0.04}/>))}
  </svg>
);
const PumpBottle=({accent="#A88FD4",accentDim="#3a2a5a",size=130})=>(
  <svg width={size} height={size*160/140} viewBox="0 0 140 160" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="pb" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#0e0e1e"/><stop offset="50%" stopColor="#141426"/><stop offset="100%" stopColor="#0a0a14"/></linearGradient>
      <linearGradient id="pc" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={accentDim}/><stop offset="50%" stopColor={accent}/><stop offset="100%" stopColor={accentDim}/></linearGradient>
      <filter id="pglow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <radialGradient id="pa" cx="50%" cy="50%"><stop offset="0%" stopColor={accent} stopOpacity="0.2"/><stop offset="100%" stopColor={accent} stopOpacity="0"/></radialGradient>
    </defs>
    <ellipse cx="70" cy="80" rx="60" ry="60" fill="url(#pa)"/>
    <ellipse cx="70" cy="152" rx="30" ry="6" fill={accent} opacity="0.12"/>
    <rect x="38" y="52" width="64" height="92" rx="12" fill="url(#pb)" stroke={accentDim} strokeWidth="0.6"/>
    <rect x="39" y="52" width="12" height="92" rx="8" fill="rgba(255,255,255,0.05)"/>
    <rect x="44" y="68" width="52" height="54" rx="2" fill={accent} opacity="0.06" stroke={accent} strokeWidth="0.3"/>
    <text x="70" y="85" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="5.5" fill={accent} letterSpacing="2.5">AURA-GEN III</text>
    <line x1="52" y1="89" x2="88" y2="89" stroke={accent} strokeWidth="0.3" opacity="0.6"/>
    <text x="70" y="100" textAnchor="middle" fontFamily="Georgia,serif" fontSize="7" fill="rgba(255,255,255,0.85)">RECOVERY</text>
    <line x1="52" y1="105" x2="88" y2="105" stroke={accent} strokeWidth="0.3" opacity="0.4"/>
    <text x="70" y="111" textAnchor="middle" fontFamily="'Tenor Sans',sans-serif" fontSize="4.5" fill="rgba(255,255,255,0.35)" letterSpacing="1.5">COMPLEX 17%</text>
    <rect x="60" y="34" width="20" height="22" rx="4" fill="#0d0d1a" stroke={accentDim} strokeWidth="0.5"/>
    <rect x="50" y="18" width="40" height="18" rx="6" fill="url(#pc)" opacity="0.95"/>
    <rect x="90" y="22" width="22" height="7" rx="3.5" fill={accentDim}/>
    <ellipse cx="113" cy="25.5" rx="3.5" ry="4.5" fill={accent} opacity="0.85" filter="url(#pglow)"/>
    {[[28,70],[114,60],[26,100],[116,96]].map(([x,y],i)=>(<circle key={i} cx={x} cy={y} r={1.2+i*0.2} fill={accent} opacity={0.16+i*0.04}/>))}
  </svg>
);

/* ── SHARED COMPONENTS ───────────────────────────────────────────────────── */

// Dynamic greeting based on time
const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  if (hour < 21) return "Good evening";
  return "Good night";
};

// Real-time status bar component
const StatusBar = () => {
  const [time, setTime] = useState(new Date());
  const [battery, setBattery] = useState({ level: 100, charging: false });
  
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    
    // Get battery status if available
    if (navigator.getBattery) {
      navigator.getBattery().then(bat => {
        setBattery({ level: Math.round(bat.level * 100), charging: bat.charging });
        bat.addEventListener('levelchange', () => setBattery(b => ({ ...b, level: Math.round(bat.level * 100) })));
        bat.addEventListener('chargingchange', () => setBattery(b => ({ ...b, charging: bat.charging })));
      }).catch(() => {});
    }
    
    return () => clearInterval(timer);
  }, []);
  
  const formatTime = (d) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  const batteryColor = battery.level > 20 ? C.green : C.red;
  
  return (
    <div style={{background:C.void,padding:"10px 24px 4px",display:"flex",justifyContent:"space-between",alignItems:"center",flexShrink:0}}>
      <span style={{fontFamily:SANS,fontSize:10,color:C.textDim}}>{formatTime(time)}</span>
      <div style={{display:"flex",gap:4,alignItems:"center"}}>
        {/* Network signal bars */}
        {[2,3,4,5,4].map((h,i)=><div key={i} style={{width:3,height:h,background:C.textDim,borderRadius:1}}/>)}
        {/* Battery indicator */}
        <div style={{width:17,height:8,border:`0.5px solid ${C.textDim}`,borderRadius:2,marginLeft:5,position:"relative"}}>
          <div style={{position:"absolute",top:1.5,left:1.5,width:`${battery.level * 0.7}%`,height:"calc(100% - 3px)",background:batteryColor,borderRadius:1}}/>
        </div>
        {battery.charging && <span style={{fontSize:8,color:C.green}}>⚡</span>}
      </div>
    </div>
  );
};

const GoldText=({children,size=28,weight=300,style:s})=>(
  <span style={{fontFamily:SERIF,fontSize:size,fontWeight:weight,
    background:`linear-gradient(105deg,${C.goldDeep},${C.goldBright} 40%,${C.gold} 60%,${C.champagne} 80%,${C.gold})`,
    backgroundSize:"200% auto",WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",
    animation:"shimmer 4s linear infinite",...s}}>{children}</span>
);
const SL=({children,style:s})=>(<p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.25em",textTransform:"uppercase",color:C.textDim,...s}}>{children}</p>);
const Divider=({style:s})=>(
  <div style={{display:"flex",alignItems:"center",gap:12,...s}}>
    <div style={{flex:1,height:"0.5px",background:`linear-gradient(90deg,transparent,${C.goldDeep})`}}/>
    <div style={{width:4,height:4,borderRadius:"50%",background:C.gold,opacity:.5}}/>
    <div style={{flex:1,height:"0.5px",background:`linear-gradient(90deg,${C.goldDeep},transparent)`}}/>
  </div>
);
const Icon=({n,size=20,color="currentColor",sw=1.3})=>{
  const p={
    home:<><path d="M3 12L12 3l9 9M5 10v9a1 1 0 001 1h4v-5h4v5h4a1 1 0 001-1v-9"/></>,
    shop:<><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4zM3 6h18M16 10a4 4 0 01-8 0"/></>,
    profile:<><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z"/></>,
    orders:<><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="15" y2="11"/></>,
    ai:<><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></>,
    loyalty:<polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"/>,
    star:<polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" fill={color} stroke="none"/>,
    send:<><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></>,
    cart:<><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/></>,
    eye:<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>,
    eyeoff:<><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></>,
    close:<><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    check:<polyline points="20,6 9,17 4,12" fill="none" stroke={color} strokeWidth={sw}/>,
    back:<polyline points="15 18 9 12 15 6"/>,
    mail:<><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22,4 12,13 2,4"/></>,
    user:<><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z"/></>,
    drop:<><path d="M12 2.69l5.66 5.66a8 8 0 11-11.31 0z"/></>,
    cake:<><path d="M20 21v-8a2 2 0 00-2-2H6a2 2 0 00-2 2v8"/><path d="M4 21h16"/><path d="M2 21h20"/><path d="M7 13v-2"/><path d="M12 13v-2"/><path d="M17 13v-2"/><path d="M7 8c0-1 1-2 2-2s2 1 2 2-1 2-2 2-2-1-2-2"/><path d="M13 8c0-1 1-2 2-2s2 1 2 2-1 2-2 2-2-1-2-2"/></>,
    settings:<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></>,
    chevronRight:<polyline points="9 18 15 12 9 6"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">{p[n]}</svg>;
};
const Ring=({value,size=72,sw=2,color=C.gold,children})=>{
  const r=(size-sw*2)/2,circ=2*Math.PI*r;
  return(
    <div style={{position:"relative",width:size,height:size,display:"flex",alignItems:"center",justifyContent:"center"}}>
      <svg width={size} height={size} style={{position:"absolute",transform:"rotate(-90deg)"}}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={C.border} strokeWidth={sw}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={sw}
          strokeDasharray={circ} strokeDashoffset={circ-(value/100)*circ} strokeLinecap="round"
          style={{transition:"stroke-dashoffset 1.4s cubic-bezier(0.4,0,0.2,1)"}}/>
      </svg>
      <div style={{position:"relative",zIndex:1}}>{children}</div>
    </div>
  );
};

/* ── AUTH SCREENS ─────────────────────────────────────────────────────────── */
const SKIN_TYPES=["Normal","Dry","Oily","Combination","Sensitive","Mature"];

const WelcomeScreen=({onLogin,onSignup})=>(
  <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",position:"relative",overflow:"hidden",
    background:"linear-gradient(160deg,#060608 0%,#0a0c12 50%,#060608 100%)"}}>
    <div style={{position:"absolute",top:-80,right:-60,width:280,height:280,borderRadius:"50%",
      background:`radial-gradient(circle,${C.gold}0a,transparent 70%)`,animation:"glowPulse 4s ease-in-out infinite"}}/>
    <div style={{position:"absolute",bottom:100,left:-80,width:240,height:240,borderRadius:"50%",
      background:`radial-gradient(circle,${C.blue}08,transparent 70%)`,animation:"glowPulse 5s ease-in-out 1s infinite"}}/>
    <div style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"60px 36px 40px"}}>
      <div style={{animation:"silkIn 0.6s ease 0.1s both"}}>
        <div style={{
          width: 100,
          height: 100,
          borderRadius: "50%",
          margin: "0 auto 28px",
          background: "radial-gradient(135deg, #1a1408, #0d0a04)",
          border: "1px solid rgba(201,168,110,0.3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 0 50px rgba(201,168,110,0.2), inset 0 0 20px rgba(201,168,110,0.05)",
          overflow: "hidden"
        }}>
          <img
            src={`${window.location.origin}/logo.png?v=2`}
            alt="ReRoots"
            style={{ width: "80%", height: "80%", objectFit: "contain" }}
            onError={(e) => { 
              // Try relative path as fallback
              if (!e.target.dataset.fallback) {
                e.target.dataset.fallback = "1";
                e.target.src = "/logo.png";
              } else {
                e.target.style.display = "none";
              }
            }}
          />
        </div>
        <p style={{fontFamily:SANS,fontSize:10,letterSpacing:"0.4em",textTransform:"uppercase",color:C.textDim,textAlign:"center",marginBottom:10}}>Biotech Skincare</p>
        <h1 style={{fontFamily:SERIF,fontSize:54,fontWeight:300,textAlign:"center",lineHeight:0.92,color:C.text}}>
          Re<GoldText size={54} weight={300}>Roots</GoldText>
        </h1>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:15,color:C.textDim,textAlign:"center",marginTop:14,letterSpacing:"0.04em"}}>
          Science that honours your skin's intelligence
        </p>
      </div>
      <div style={{display:"flex",gap:16,alignItems:"flex-end",margin:"44px 0",animation:"silkIn 0.6s ease 0.3s both"}}>
        <div style={{opacity:.6,animation:"floatBottle 3.2s ease-in-out infinite"}}><DropperBottle size={80}/></div>
        <div style={{animation:"floatBottle 3.8s ease-in-out 0.5s infinite"}}><JarProduct size={90}/></div>
        <div style={{opacity:.6,animation:"floatBottle 3.4s ease-in-out 0.2s infinite"}}><PumpBottle size={80}/></div>
      </div>
      <div style={{width:"100%",animation:"silkIn 0.6s ease 0.5s both"}}>
        <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,textAlign:"center",letterSpacing:"0.12em",marginBottom:28}}>
          JOIN 2,800+ MEMBERS - EARN POINTS - PERSONALIZED PROTOCOLS
        </p>
        <button className="lbtn" onClick={onSignup} style={{
          width:"100%",background:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
          border:"none",borderRadius:4,padding:"19px",marginBottom:14,
          fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
          Create Account
        </button>
        <button className="lbtn" onClick={onLogin} style={{
          width:"100%",background:"transparent",
          border:`0.5px solid ${C.borderGold}`,borderRadius:4,padding:"18px",
          fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.gold,cursor:"pointer"}}>
          Sign In
        </button>
      </div>
    </div>
    <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,textAlign:"center",padding:"0 0 28px",letterSpacing:"0.1em"}}>
      reroots.ca - Canada
    </p>
  </div>
);

const InputField=({label,type="text",value,onChange,placeholder,icon})=>{
  const [show,setShow]=useState(false);
  return(
    <div style={{marginBottom:14}}>
      <p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.2em",textTransform:"uppercase",color:C.textDim,marginBottom:7}}>{label}</p>
      <div style={{position:"relative"}}>
        {icon&&<div style={{position:"absolute",left:14,top:"50%",transform:"translateY(-50%)",pointerEvents:"none"}}>
          <Icon n={icon} size={15} color={C.textDim}/>
        </div>}
        <input
          type={type==="password"&&show?"text":type}
          value={value} onChange={onChange} placeholder={placeholder}
          className="inp"
          style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
            padding:`14px ${type==="password"?46:16}px 14px ${icon?44:16}px`,
            color:C.text,fontFamily:SERIF,fontSize:14,fontWeight:300}}/>
        {type==="password"&&(
          <button onClick={()=>setShow(s=>!s)} style={{position:"absolute",right:14,top:"50%",
            transform:"translateY(-50%)",background:"none",border:"none",cursor:"pointer",padding:4}}>
            <Icon n={show?"eyeoff":"eye"} size={15} color={C.textDim}/>
          </button>
        )}
      </div>
    </div>
  );
};

const LoginScreen=({onBack,onSuccess,onForgotPassword})=>{
  const [email,setEmail]=useState("");
  const [pass,setPass]=useState("");
  const [loading,setLoading]=useState(false);
  const [googleLoading,setGoogleLoading]=useState(false);
  const [err,setErr]=useState("");
  const [googleClientId,setGoogleClientId]=useState(null);
  const [googleScriptLoaded,setGoogleScriptLoaded]=useState(false);
  const [googleConfigLoaded,setGoogleConfigLoaded]=useState(false);
  
  // Load Google Identity Services script
  useEffect(()=>{
    if(!document.getElementById('google-identity-script')){
      const script=document.createElement('script');
      script.id='google-identity-script';
      script.src='https://accounts.google.com/gsi/client';
      script.async=true;
      script.defer=true;
      script.onload=()=>setGoogleScriptLoaded(true);
      script.onerror=()=>console.log('Google script failed to load');
      document.head.appendChild(script);
    }else{
      setGoogleScriptLoaded(true);
    }
  },[]);
  
  // Fetch Google client ID
  useEffect(()=>{
    const fetchGoogleConfig=async()=>{
      try{
        const res=await fetch(`${BASE_URL}/api/auth/google/config`);
        const d=await res.json();
        if(d.client_id){
          setGoogleClientId(d.client_id);
        }
      }catch(e){
        console.log('Google config fetch failed:',e);
      }finally{
        setGoogleConfigLoaded(true);
      }
    };
    fetchGoogleConfig();
  },[]);
  
  const submit=async()=>{
    if(!email||!pass){setErr("Please fill in all fields.");return;}
    setLoading(true);setErr("");
    try{
      const data=await apiReq("POST","/api/auth/login",{email,password:pass});
      setToken(data.token || data.access_token);
      onSuccess(normalizeUser(data.user));
    }catch(e){
      setErr(e.message||"Invalid email or password.");
    }finally{setLoading(false);}
  };
  
  const handleGoogleSuccess=async(credentialResponse)=>{
    setGoogleLoading(true);setErr("");
    try{
      const res=await fetch(`${BASE_URL}/api/auth/google/verify-token`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({credential:credentialResponse.credential,is_admin:false})
      });
      const data=await res.json();
      if(!res.ok)throw new Error(data.detail||"Google login failed");
      setToken(data.token);
      onSuccess(normalizeUser(data.user));
    }catch(e){
      setErr(e.message||"Google sign-in failed");
    }finally{setGoogleLoading(false);}
  };
  
  return(
    <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",background:C.void,overflow:"hidden"}}>
      <div style={{padding:"54px 28px 0",animation:"silkIn 0.5s ease both"}}>
        <button onClick={onBack} style={{background:"none",border:"none",cursor:"pointer",marginBottom:32,display:"flex",alignItems:"center",gap:8}}>
          <Icon n="back" size={18} color={C.textDim}/>
          <span style={{fontFamily:SANS,fontSize:10,color:C.textDim,letterSpacing:"0.12em"}}>BACK</span>
        </button>
        <SL style={{marginBottom:10}}>Welcome back</SL>
        <h2 style={{fontFamily:SERIF,fontSize:38,fontWeight:300,color:C.text,lineHeight:1,marginBottom:8}}>Sign <GoldText size={38} weight={300}>In</GoldText></h2>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:14,color:C.textDim,marginBottom:36}}>Continue your biotech skin journey</p>
        <Divider style={{marginBottom:24}}/>
        
        {/* Google Sign-in Button */}
        <div style={{marginBottom:20}}>
          <button onClick={()=>{
            if(!googleClientId){setErr("Google Sign-In not available");return;}
            setGoogleLoading(true);setErr("");
            // Load Google Sign-In
            if(window.google?.accounts?.id){
              window.google.accounts.id.initialize({
                client_id:googleClientId,
                callback:(response)=>{
                  handleGoogleSuccess(response);
                }
              });
              window.google.accounts.id.prompt((notification)=>{
                if(notification.isNotDisplayed()||notification.isSkippedMoment()){
                  // Fallback - open Google OAuth in popup
                  const width=500,height=600;
                  const left=(window.innerWidth-width)/2;
                  const top=(window.innerHeight-height)/2;
                  const popup=window.open(
                    `https://accounts.google.com/o/oauth2/v2/auth?client_id=${googleClientId}&redirect_uri=${encodeURIComponent(window.location.origin+'/auth/callback')}&response_type=code&scope=email%20profile&prompt=select_account`,
                    'googleLogin',
                    `width=${width},height=${height},left=${left},top=${top}`
                  );
                  // Check if popup was blocked
                  if(!popup){
                    setErr("Please allow popups for Google Sign-In");
                    setGoogleLoading(false);
                  }
                }
              });
            }else{
              // Google script not loaded yet - use popup fallback
              const width=500,height=600;
              const left=(window.innerWidth-width)/2;
              const top=(window.innerHeight-height)/2;
              window.open(
                `https://accounts.google.com/o/oauth2/v2/auth?client_id=${googleClientId}&redirect_uri=${encodeURIComponent(window.location.origin+'/auth/callback')}&response_type=code&scope=email%20profile&prompt=select_account`,
                'googleLogin',
                `width=${width},height=${height},left=${left},top=${top}`
              );
            }
            setTimeout(()=>setGoogleLoading(false),5000); // Reset loading after 5s
          }} disabled={googleLoading||!googleConfigLoaded||!googleClientId} className="lbtn" style={{
            width:"100%",display:"flex",alignItems:"center",justifyContent:"center",gap:12,
            background:C.surface,border:`1px solid ${C.border}`,borderRadius:4,padding:"16px",cursor:googleClientId?"pointer":"not-allowed",opacity:(googleConfigLoaded&&googleClientId)?1:0.5}}>
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <span style={{fontFamily:SANS,fontSize:11,letterSpacing:"0.1em",color:C.text}}>
              {googleLoading?"SIGNING IN...":!googleConfigLoaded?"LOADING...":googleClientId?"SIGN IN WITH GOOGLE":"UNAVAILABLE"}
            </span>
          </button>
        </div>
        
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:20}}>
          <div style={{flex:1,height:1,background:C.border}}/>
          <span style={{fontFamily:SANS,fontSize:9,color:C.textDim,letterSpacing:"0.15em"}}>OR</span>
          <div style={{flex:1,height:1,background:C.border}}/>
        </div>
        
        <InputField label="Email Address" type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" icon="mail"/>
        <InputField label="Password" type="password" value={pass} onChange={e=>setPass(e.target.value)} placeholder="Your password" icon="eye"/>
        {err&&<p style={{fontFamily:SANS,fontSize:11,color:C.red,marginBottom:14,letterSpacing:"0.04em"}}>{err}</p>}
        <button className="lbtn" onClick={submit} disabled={loading} style={{
          width:"100%",marginTop:8,
          background:loading?C.surface:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
          border:"none",borderRadius:4,padding:"19px",
          fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
          {loading?"Signing in...":"Sign In"}
        </button>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:13,color:C.textDim,textAlign:"center",marginTop:18}}>
          Forgot password? <span onClick={onForgotPassword} style={{color:C.gold,cursor:"pointer",textDecoration:"underline"}}>Reset via email</span>
        </p>
      </div>
    </div>
  );
};

// Forgot Password Screen
const ForgotPasswordScreen=({onBack,onSuccess})=>{
  const [email,setEmail]=useState("");
  const [loading,setLoading]=useState(false);
  const [sent,setSent]=useState(false);
  const [err,setErr]=useState("");
  
  const submit=async()=>{
    if(!email){setErr("Please enter your email address.");return;}
    setLoading(true);setErr("");
    try{
      await apiReq("POST","/api/auth/forgot-password",{email});
      setSent(true);
    }catch(e){
      setErr(e.message||"Failed to send reset email. Please try again.");
    }finally{setLoading(false);}
  };
  
  if(sent){
    return(
      <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",background:C.void,overflow:"hidden"}}>
        <div style={{padding:"54px 28px 0",animation:"silkIn 0.5s ease both",textAlign:"center"}}>
          <div style={{width:80,height:80,borderRadius:"50%",background:`${C.gold}15`,margin:"0 auto 24px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Icon n="mail" size={32} color={C.gold}/>
          </div>
          <SL style={{marginBottom:10}}>Check your inbox</SL>
          <h2 style={{fontFamily:SERIF,fontSize:32,fontWeight:300,color:C.text,lineHeight:1.2,marginBottom:16}}>Reset Link <GoldText size={32} weight={300}>Sent</GoldText></h2>
          <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:14,color:C.textDim,marginBottom:36,maxWidth:280,margin:"0 auto 36px"}}>
            We've sent a password reset link to <span style={{color:C.gold}}>{email}</span>. Please check your email.
          </p>
          <button onClick={onBack} className="lbtn" style={{
            width:"100%",maxWidth:280,margin:"0 auto",display:"block",
            background:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
            border:"none",borderRadius:4,padding:"19px",
            fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
            Back to Sign In
          </button>
        </div>
      </div>
    );
  }
  
  return(
    <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",background:C.void,overflow:"hidden"}}>
      <div style={{padding:"54px 28px 0",animation:"silkIn 0.5s ease both"}}>
        <button onClick={onBack} style={{background:"none",border:"none",cursor:"pointer",marginBottom:32,display:"flex",alignItems:"center",gap:8}}>
          <Icon n="back" size={18} color={C.textDim}/>
          <span style={{fontFamily:SANS,fontSize:10,color:C.textDim,letterSpacing:"0.12em"}}>BACK</span>
        </button>
        <SL style={{marginBottom:10}}>Password Recovery</SL>
        <h2 style={{fontFamily:SERIF,fontSize:34,fontWeight:300,color:C.text,lineHeight:1,marginBottom:8}}>Forgot <GoldText size={34} weight={300}>Password?</GoldText></h2>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:14,color:C.textDim,marginBottom:36}}>Enter your email and we'll send you a reset link</p>
        <Divider style={{marginBottom:32}}/>
        <InputField label="Email Address" type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" icon="mail"/>
        {err&&<p style={{fontFamily:SANS,fontSize:11,color:C.red,marginBottom:14,letterSpacing:"0.04em"}}>{err}</p>}
        <button className="lbtn" onClick={submit} disabled={loading} style={{
          width:"100%",marginTop:8,
          background:loading?C.surface:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
          border:"none",borderRadius:4,padding:"19px",
          fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
          {loading?"Sending...":"Send Reset Link"}
        </button>
      </div>
    </div>
  );
};

// Reset Password Screen (for when user clicks reset link)
const ResetPasswordScreen=({token,onSuccess,onBack})=>{
  const [password,setPassword]=useState("");
  const [confirmPassword,setConfirmPassword]=useState("");
  const [loading,setLoading]=useState(false);
  const [success,setSuccess]=useState(false);
  const [err,setErr]=useState("");
  
  const submit=async()=>{
    if(!password||!confirmPassword){setErr("Please fill in all fields.");return;}
    if(password.length<8){setErr("Password must be at least 8 characters.");return;}
    if(password!==confirmPassword){setErr("Passwords do not match.");return;}
    setLoading(true);setErr("");
    try{
      await apiReq("POST","/api/auth/reset-password",{token,new_password:password});
      setSuccess(true);
    }catch(e){
      setErr(e.message||"Failed to reset password. The link may have expired.");
    }finally{setLoading(false);}
  };
  
  if(success){
    return(
      <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",background:C.void,overflow:"hidden"}}>
        <div style={{padding:"54px 28px 0",animation:"silkIn 0.5s ease both",textAlign:"center"}}>
          <div style={{width:80,height:80,borderRadius:"50%",background:`${C.green}15`,margin:"0 auto 24px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Icon n="check" size={32} color={C.green}/>
          </div>
          <SL style={{marginBottom:10}}>Success!</SL>
          <h2 style={{fontFamily:SERIF,fontSize:32,fontWeight:300,color:C.text,lineHeight:1.2,marginBottom:16}}>Password <GoldText size={32} weight={300}>Reset</GoldText></h2>
          <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:14,color:C.textDim,marginBottom:36}}>
            Your password has been successfully reset. You can now sign in with your new password.
          </p>
          <button onClick={onBack} className="lbtn" style={{
            width:"100%",maxWidth:280,margin:"0 auto",display:"block",
            background:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
            border:"none",borderRadius:4,padding:"19px",
            fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
            Sign In
          </button>
        </div>
      </div>
    );
  }
  
  return(
    <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",background:C.void,overflow:"hidden"}}>
      <div style={{padding:"54px 28px 0",animation:"silkIn 0.5s ease both"}}>
        <SL style={{marginBottom:10}}>Almost there</SL>
        <h2 style={{fontFamily:SERIF,fontSize:34,fontWeight:300,color:C.text,lineHeight:1,marginBottom:8}}>Create New <GoldText size={34} weight={300}>Password</GoldText></h2>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:14,color:C.textDim,marginBottom:36}}>Enter your new password below</p>
        <Divider style={{marginBottom:32}}/>
        <InputField label="New Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="At least 8 characters" icon="eye"/>
        <InputField label="Confirm Password" type="password" value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} placeholder="Confirm your password" icon="eye"/>
        {err&&<p style={{fontFamily:SANS,fontSize:11,color:C.red,marginBottom:14,letterSpacing:"0.04em"}}>{err}</p>}
        <button className="lbtn" onClick={submit} disabled={loading} style={{
          width:"100%",marginTop:8,
          background:loading?C.surface:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
          border:"none",borderRadius:4,padding:"19px",
          fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
          {loading?"Resetting...":"Reset Password"}
        </button>
      </div>
    </div>
  );
};

const SignupScreen=({onBack,onSuccess})=>{
  const [step,setStep]=useState(1);
  const [form,setForm]=useState({firstName:"",lastName:"",email:"",password:"",skinType:"",birthday:"",offers:true});
  const [loading,setLoading]=useState(false);
  const [err,setErr]=useState("");
  const set=(k)=>(e)=>setForm(f=>({...f,[k]:e.target.value}));
  const nextStep=()=>{
    if(step===1&&(!form.firstName||!form.email||!form.password)){setErr("Please fill in required fields.");return;}
    setErr("");setStep(2);
  };
  const submit=async()=>{
    if(!form.skinType){setErr("Please select your skin type.");return;}
    setLoading(true);setErr("");
    try{
      const data=await apiReq("POST","/api/auth/register",{
        first_name:form.firstName,
        last_name:form.lastName,
        email:form.email,
        password:form.password,
        skin_type:form.skinType,
        birthday:form.birthday||null,
        offers_opt_in:form.offers,
      });
      setToken(data.token || data.access_token);
      onSuccess(normalizeUser(data.user));
    }catch(e){
      setErr(e.message||"Signup failed. Please try again.");
    }finally{setLoading(false);}
  };
  return(
    <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",background:C.void,overflow:"hidden"}}>
      <div style={{padding:"54px 28px 0",animation:"silkIn 0.5s ease both",maxWidth:480,width:"100%",margin:"0 auto"}}>
        <button onClick={step===1?onBack:()=>setStep(1)} style={{background:"none",border:"none",cursor:"pointer",marginBottom:28,display:"flex",alignItems:"center",gap:8}}>
          <Icon n="back" size={18} color={C.textDim}/>
          <span style={{fontFamily:SANS,fontSize:10,color:C.textDim,letterSpacing:"0.12em"}}>BACK</span>
        </button>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:28}}>
          {[1,2].map(s=>(
            <div key={s} style={{display:"flex",alignItems:"center",gap:10}}>
              <div style={{width:24,height:24,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",
                background:s<=step?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,
                border:`0.5px solid ${s<=step?C.gold:C.border}`}}>
                {s<step?<Icon n="check" size={12} color={C.void} sw={2}/>:
                  <span style={{fontFamily:SANS,fontSize:9,color:s===step?C.void:C.textDim}}>{s}</span>}
              </div>
              <span style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.12em",color:s===step?C.gold:C.textDim}}>
                {s===1?"ACCOUNT":"SKIN PROFILE"}
              </span>
              {s<2&&<div style={{flex:1,height:"0.5px",background:step>1?C.gold:C.border,width:30}}/>}
            </div>
          ))}
        </div>
        <SL style={{marginBottom:8}}>Join ReRoots</SL>
        <h2 style={{fontFamily:SERIF,fontSize:34,fontWeight:300,color:C.text,lineHeight:1,marginBottom:6}}>
          {step===1?"Create Your ":"Your Skin "}
          <GoldText size={34} weight={300}>{step===1?"Account":"Profile"}</GoldText>
        </h2>
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:13,color:C.textDim,marginBottom:28}}>
          {step===1?"500 welcome points on signup":"Personalized recommendations await"}
        </p>
        <Divider style={{marginBottom:24}}/>
        {step===1&&(
          <>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:0}}>
              <div>
                <p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.2em",textTransform:"uppercase",color:C.textDim,marginBottom:7}}>First Name *</p>
                <input value={form.firstName} onChange={set("firstName")} placeholder="Jane" className="inp"
                  style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
                    padding:"14px",color:C.text,fontFamily:SERIF,fontSize:14,fontWeight:300}}/>
              </div>
              <div>
                <p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.2em",textTransform:"uppercase",color:C.textDim,marginBottom:7}}>Last Name</p>
                <input value={form.lastName} onChange={set("lastName")} placeholder="Smith" className="inp"
                  style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
                    padding:"14px",color:C.text,fontFamily:SERIF,fontSize:14,fontWeight:300}}/>
              </div>
            </div>
            <div style={{marginTop:14}}>
              <InputField label="Email Address *" type="email" value={form.email} onChange={set("email")} placeholder="you@example.com" icon="mail"/>
              <InputField label="Password *" type="password" value={form.password} onChange={set("password")} placeholder="Min. 8 characters" icon="eye"/>
            </div>
            {err&&<p style={{fontFamily:SANS,fontSize:11,color:C.red,marginBottom:14}}>{err}</p>}
            <button className="lbtn" onClick={nextStep} style={{
              width:"100%",marginTop:4,
              background:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
              border:"none",borderRadius:4,padding:"19px",
              fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
              Continue
            </button>
          </>
        )}
        {step===2&&(
          <>
            <p style={{fontFamily:SANS,fontSize:10,color:C.textSub,marginBottom:16,letterSpacing:"0.05em"}}>Select your skin type *</p>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:9,marginBottom:20}}>
              {SKIN_TYPES.map(t=>(
                <button key={t} onClick={()=>setForm(f=>({...f,skinType:t}))} style={{
                  background:form.skinType===t?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,
                  border:`0.5px solid ${form.skinType===t?C.gold:C.border}`,borderRadius:4,padding:"12px 8px",
                  fontFamily:SANS,fontSize:9,letterSpacing:"0.1em",textTransform:"uppercase",
                  color:form.skinType===t?C.void:C.textSub,cursor:"pointer"}}>
                  {t}
                </button>
              ))}
            </div>
            <div style={{marginBottom:16}}>
              <p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.2em",textTransform:"uppercase",color:C.textDim,marginBottom:7}}>Birthday (optional - 500 birthday pts)</p>
              <input type="date" value={form.birthday} onChange={set("birthday")} className="inp"
                style={{width:"100%",background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:4,
                  padding:"14px",color:form.birthday?C.text:C.textDim,fontFamily:SANS,fontSize:12}}/>
            </div>
            <div style={{display:"flex",alignItems:"flex-start",gap:12,marginBottom:24,
              background:C.surface,border:`0.5px solid ${C.border}`,borderRadius:6,padding:"14px"}}>
              <button onClick={()=>setForm(f=>({...f,offers:!f.offers}))} style={{
                width:20,height:20,borderRadius:3,border:`0.5px solid ${form.offers?C.gold:C.border}`,
                background:form.offers?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,
                display:"flex",alignItems:"center",justifyContent:"center",cursor:"pointer",flexShrink:0,marginTop:1}}>
                {form.offers&&<Icon n="check" size={11} color={C.void} sw={2.5}/>}
              </button>
              <p style={{fontFamily:SANS,fontSize:11,color:C.textSub,lineHeight:1.6}}>
                Send me exclusive member offers, new formula launches, and personalized skincare recommendations
              </p>
            </div>
            {err&&<p style={{fontFamily:SANS,fontSize:11,color:C.red,marginBottom:14}}>{err}</p>}
            <button className="lbtn" onClick={submit} disabled={loading} style={{
              width:"100%",
              background:loading?C.surface:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
              border:"none",borderRadius:4,padding:"19px",
              fontFamily:SANS,fontSize:12,letterSpacing:"0.22em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
              {loading?"Creating account...":"Complete Signup - 500 pts"}
            </button>
          </>
        )}
        <p style={{fontFamily:SERIF,fontStyle:"italic",fontSize:12,color:C.textDim,textAlign:"center",marginTop:18,marginBottom:40}}>
          By signing up you agree to our privacy policy. reroots.ca
        </p>
      </div>
    </div>
  );
};

/* ── MAIN APP SCREENS ────────────────────────────────────────────────────── */
const PRODUCTS=[
  {id:1,name:"TXA + PDRN Serum",subtitle:"AURA-GEN I",price:89.99,size:"30 ml",tag:"Bestseller",
   desc:"Triple-penetration architecture. 5% TXA fused with 2% bio-active PDRN and Argireline complex.",
   ingredients:["PDRN 2%","TXA 5%","Argireline 3%","DMI","Liposomal Ceramide"],
   stock:24,rating:4.9,reviews:187,accent:C.blue,accentDim:"#2a4a6a",shape:"dropper",
   hue:"linear-gradient(160deg,#0a1020 0%,#060c18 100%)"},
  {id:2,name:"Accelerator Rich Cream",subtitle:"AURA-GEN II",price:74.99,size:"50 ml",tag:"New Formula",
   desc:"v4 corrected HLB emulsification. Barrier-restoring peptide matrix with multi-weight Hyaluronic Acid.",
   ingredients:["Niacinamide 4%","HA 1.5%","Peptide Complex","Shea","Ceramide NP"],
   stock:18,rating:4.8,reviews:94,accent:C.gold,accentDim:"#5a3e1a",shape:"jar",
   hue:"linear-gradient(160deg,#160f06 0%,#0d0a04 100%)"},
  {id:3,name:"Active Recovery Complex",subtitle:"AURA-GEN III",price:99.99,size:"30 ml",tag:"Clinical",
   desc:"17% active concentration. Post-procedure intensive repair with EGF acceleration and Centella.",
   ingredients:["TXA 7%","PDRN 3%","Retinol 0.3%","EGF","Centella"],
   stock:11,rating:4.95,reviews:52,accent:C.purple,accentDim:"#3a2a5a",shape:"pump",
   hue:"linear-gradient(160deg,#0a0a18 0%,#060610 100%)"},
];
const METRICS=[
  {label:"Hydration",value:78,trend:"+12%",color:C.blue},
  {label:"Barrier",value:85,trend:"+8pts",color:C.green},
  {label:"Radiance",value:72,trend:"+15%",color:C.gold},
  {label:"Texture",value:68,trend:"+5%",color:C.copper},
];
const ORDERS_DATA=[
  {id:"RR-20241",name:"TXA + PDRN Serum",status:"Delivered",date:"28 Feb",total:"CA$89.99",step:4,pid:1},
  {id:"RR-20238",name:"Accelerator Cream",status:"In Transit",date:"06 Mar",total:"CA$74.99",step:3,pid:2},
  {id:"RR-20245",name:"Recovery Complex",status:"Processing",date:"09 Mar",total:"CA$99.99",step:1,pid:3},
];

const BottleFor=(p,size=130)=>{
  if(p.shape==="dropper") return <DropperBottle accent={p.accent} accentDim={p.accentDim} size={size}/>;
  if(p.shape==="jar")     return <JarProduct    accent={p.accent} accentDim={p.accentDim} size={size}/>;
  return                         <PumpBottle    accent={p.accent} accentDim={p.accentDim} size={size}/>;
};

const ProductSheet=({p,onClose,onAdd})=>{
  if(!p) return null;
  return(
    <div style={{position:"fixed",inset:0,background:"rgba(6,6,8,0.92)",zIndex:1000,
      display:"flex",alignItems:"flex-end",justifyContent:"center",backdropFilter:"blur(14px)"}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:C.card,width:"100%",maxWidth:480,
        borderRadius:"28px 28px 0 0",border:`0.5px solid ${C.borderGold}`,borderBottom:"none",
        padding:"28px 26px 38px",animation:"slideUp 0.38s cubic-bezier(0.32,0.72,0,1)"}}>
        <div style={{width:36,height:3,borderRadius:2,background:C.textDim,margin:"0 auto 20px"}}/>
        <div style={{background:p.hue,borderRadius:18,padding:"20px 12px 14px",marginBottom:18,
          display:"flex",justifyContent:"center",position:"relative",overflow:"hidden"}}>
          <div style={{position:"absolute",inset:0,background:`radial-gradient(circle at 50% 40%,${p.accent}12,transparent 70%)`}}/>
          <div style={{animation:"floatBottle 3s ease-in-out infinite"}}>
            {p.image_url || p.image 
              ? <img src={p.image_url || p.image} alt={p.name} style={{width:140,height:140,objectFit:"contain"}} onError={(e)=>{e.target.style.display='none';e.target.nextSibling.style.display='block';}}/> 
              : null}
            <div style={{display:p.image_url||p.image?'none':'block'}}>{BottleFor(p,140)}</div>
          </div>
        </div>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:8}}>
          <div>
            <SL>{p.subtitle}</SL>
            <h2 style={{fontFamily:SERIF,fontSize:24,fontWeight:300,color:C.text,lineHeight:1.1,marginTop:4}}>{p.name}</h2>
            <p style={{fontFamily:SANS,color:C.textSub,fontSize:11,marginTop:4}}>{p.size}</p>
          </div>
          <span style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.12em",padding:"4px 10px",borderRadius:2,
            color:p.accent,background:`${p.accent}15`,border:`0.5px solid ${p.accent}44`}}>{p.tag.toUpperCase()}</span>
        </div>
        <Divider style={{margin:"14px 0"}}/>
        <p style={{fontFamily:SERIF,fontStyle:"italic",color:C.textSub,fontSize:13,lineHeight:1.7,marginBottom:16}}>{p.desc}</p>
        <SL style={{marginBottom:9}}>Active Compounds</SL>
        <div style={{display:"flex",flexWrap:"wrap",gap:6,marginBottom:18}}>
          {(Array.isArray(p.ingredients) ? p.ingredients : (typeof p.ingredients === 'string' ? p.ingredients.split(',').map(s=>s.trim()) : [])).map(i=>(
            <span key={i} style={{fontFamily:SANS,fontSize:10,letterSpacing:"0.05em",padding:"4px 11px",borderRadius:2,
              border:`0.5px solid ${C.borderGold}`,color:C.textSub,background:"rgba(201,168,110,0.04)"}}>{i}</span>
          ))}
        </div>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",marginBottom:20}}>
          <GoldText size={32} weight={300}>{"CA$"}{p.price}</GoldText>
          <div style={{display:"flex",alignItems:"center",gap:3}}>
            {[1,2,3,4,5].map(s=><Icon key={s} n="star" size={11} color={s<=Math.floor(p.rating)?C.gold:"rgba(255,255,255,0.1)"}/>)}
            <span style={{fontFamily:SANS,color:C.textDim,fontSize:10,marginLeft:4}}>{p.rating}</span>
          </div>
        </div>
        <button className="lbtn" onClick={()=>{onAdd(p);onClose();}} style={{
          width:"100%",background:`linear-gradient(135deg,${C.goldDeep},${C.gold} 50%,${C.goldBright})`,
          border:"none",borderRadius:4,padding:"17px",
          fontFamily:SANS,fontSize:11,letterSpacing:"0.2em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>
          Add to Collection
        </button>
      </div>
    </div>
  );
};

const Home=({user,cart,setTab})=>(
  <div style={{padding:"0 24px 110px"}}>
    <div style={{paddingTop:26,paddingBottom:24,display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
      <div>
        <p style={{fontFamily:SANS,fontSize:9,letterSpacing:"0.3em",textTransform:"uppercase",color:C.textDim}}>{getGreeting()}</p>
        <h1 style={{fontFamily:SERIF,fontSize:30,fontWeight:300,color:C.text,marginTop:4,lineHeight:1}}>
          <GoldText size={30} weight={300}>{user.name.split(" ")[0]}</GoldText>
        </h1>
        <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:4,letterSpacing:"0.06em"}}>{user.tier} Member - {user.points} pts</p>
      </div>
      <button className="lbtn" onClick={()=>setTab("shop")} style={{position:"relative",background:"transparent",
        border:`0.5px solid ${C.borderGold}`,borderRadius:3,width:44,height:44,cursor:"pointer",
        display:"flex",alignItems:"center",justifyContent:"center"}}>
        <Icon n="cart" size={18} color={C.gold}/>
        {cart.length>0&&<span style={{position:"absolute",top:-5,right:-5,width:17,height:17,
          background:C.gold,borderRadius:"50%",fontSize:9,fontFamily:SANS,color:C.void,
          display:"flex",alignItems:"center",justifyContent:"center",fontWeight:700}}>{cart.length}</span>}
      </button>
    </div>
    <div style={{background:"linear-gradient(160deg,#0a1020,#060c18)",border:`0.5px solid ${C.blue}22`,
      borderRadius:20,padding:"22px",marginBottom:18,display:"flex",alignItems:"center",justifyContent:"space-between",
      animation:"silkIn 0.5s ease both",position:"relative",overflow:"hidden"}}>
      <div style={{position:"absolute",right:-20,top:-20,width:180,height:180,background:`radial-gradient(circle,${C.blue}10,transparent 70%)`}}/>
      <div>
        <SL style={{color:C.blue,marginBottom:8}}>Featured Formula</SL>
        <p style={{fontFamily:SERIF,fontSize:19,fontWeight:300,color:C.text,lineHeight:1.2}}>TXA + PDRN<br/>Serum</p>
        <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:5}}>5% TXA - 2% PDRN - Argireline</p>
        <button className="lbtn" onClick={()=>setTab("shop")} style={{marginTop:13,background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
          border:"none",borderRadius:3,padding:"9px 18px",fontFamily:SANS,fontSize:9,
          letterSpacing:"0.16em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>Shop Now</button>
      </div>
      <div style={{animation:"floatBottle 3.5s ease-in-out infinite",flexShrink:0}}>
        <DropperBottle accent={C.blue} accentDim="#2a4a6a" size={110}/>
      </div>
    </div>
    <div style={{background:"linear-gradient(145deg,#1a1508,#231c0a)",border:`0.5px solid ${C.borderGold}`,
      borderRadius:16,padding:"20px",marginBottom:16,position:"relative",overflow:"hidden",animation:"silkIn 0.5s ease 0.1s both"}}>
      <div style={{position:"absolute",top:-40,right:-40,width:160,height:160,borderRadius:"50%",
        background:`radial-gradient(circle,${C.gold}12,transparent 65%)`,animation:"glowPulse 3s ease-in-out infinite"}}/>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div>
          <SL style={{marginBottom:6}}>{user.tier} Tier - Loyalty</SL>
          <GoldText size={40} weight={300}>{user.points.toLocaleString()}</GoldText>
          <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,marginTop:3}}>points - 2x multiplier active</p>
        </div>
        <Icon n="loyalty" size={24} color={C.gold}/>
      </div>
      <Divider style={{margin:"14px 0 10px"}}/>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div style={{flex:1,height:"2px",background:C.surface,borderRadius:2,overflow:"hidden",marginRight:12}}>
          <div style={{width:`${Math.min(100,(user.points/4000)*100)}%`,height:"100%",background:`linear-gradient(90deg,${C.goldDeep},${C.goldBright})`,borderRadius:2}}/>
        </div>
        <span style={{fontFamily:SANS,fontSize:10,color:C.textDim,whiteSpace:"nowrap"}}>
          {(4000-Math.min(4000,user.points)).toLocaleString()} to Diamond
        </span>
      </div>
    </div>
    <SL style={{marginBottom:12}}>Skin Intelligence</SL>
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10,marginBottom:16}}>
      {METRICS.map((m,i)=>(
        <div key={m.label} className="chov" style={{background:C.card,border:`0.5px solid ${C.border}`,
          borderRadius:12,padding:"14px",display:"flex",alignItems:"center",gap:10,
          animation:`silkIn 0.5s ease ${0.15+i*0.07}s both`}}>
          <Ring value={m.value} size={50} sw={2} color={m.color}>
            <span style={{fontFamily:SERIF,fontSize:12,color:C.text}}>{m.value}</span>
          </Ring>
          <div>
            <p style={{fontFamily:SANS,fontSize:10,color:C.textSub}}>{m.label}</p>
            <p style={{fontFamily:SERIF,fontSize:12,color:m.color,marginTop:2,fontStyle:"italic"}}>{m.trend}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
);

const Shop=({cart,setCart})=>{
  const [sel,setSel]=useState(null);
  const [flash,setFlash]=useState(false);
  const [products,setProducts]=useState(PRODUCTS);
  const [loadingProducts,setLoadingProducts]=useState(true);
  
  useEffect(()=>{
    const fetchProducts=async()=>{
      try{
        const data=await apiReq("GET","/api/products");
        if(data&&data.length>0){
          // Filter products for dark store visibility
          const filteredData = data.filter(p => {
            const visibility = p.brand_visibility || 'both';
            return visibility === 'both' || visibility === 'dark_only';
          });
          // Map API products to display format, merging with defaults for styling
          const mapped=filteredData.map((p,i)=>({
            id:p.id||p._id||i,
            name:p.name||"Product",
            subtitle:p.subtitle||p.category||"AURA-GEN",
            price:p.price||0,
            size:p.size||p.volume||"",
            tag:p.tag||p.badge||"New",
            desc:p.description||p.short_description||"",
            ingredients:p.ingredients||p.key_ingredients||[],
            stock:p.stock||p.quantity||0,
            rating:p.rating||4.8,
            reviews:p.reviews_count||0,
            image_url:p.image_url||p.image||p.images?.[0]||null,
            accent:PRODUCTS[i%PRODUCTS.length]?.accent||C.gold,
            accentDim:PRODUCTS[i%PRODUCTS.length]?.accentDim||"#5a3e1a",
            shape:PRODUCTS[i%PRODUCTS.length]?.shape||"pump",
            hue:PRODUCTS[i%PRODUCTS.length]?.hue||"linear-gradient(160deg,#160f06 0%,#0d0a04 100%)"
          }));
          setProducts(mapped);
        }
      }catch(e){
        console.log("Using default products");
      }finally{
        setLoadingProducts(false);
      }
    };
    fetchProducts();
  },[]);
  
  const add=p=>{setCart(c=>[...c,p]);setFlash(true);setTimeout(()=>setFlash(false),2200);};
  const remove=idx=>{setCart(c=>c.filter((_,i)=>i!==idx));};
  
  // Checkout modal state
  const [showCheckout, setShowCheckout] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState('cart'); // 'cart', 'shipping', 'payment', 'success'
  const [shippingInfo, setShippingInfo] = useState({name:'',address:'',city:'',postal:'',phone:''});
  const [processing, setProcessing] = useState(false);
  
  const handleCheckout = async () => {
    if (checkoutStep === 'cart') {
      setCheckoutStep('shipping');
    } else if (checkoutStep === 'shipping') {
      if (!shippingInfo.name || !shippingInfo.address || !shippingInfo.city || !shippingInfo.postal) {
        alert('Please fill in all shipping fields');
        return;
      }
      setCheckoutStep('payment');
    } else if (checkoutStep === 'payment') {
      setProcessing(true);
      // Simulate payment processing
      setTimeout(() => {
        setProcessing(false);
        setCheckoutStep('success');
        // Clear cart after success
        setTimeout(() => {
          setCart([]);
          setShowCheckout(false);
          setCheckoutStep('cart');
        }, 3000);
      }, 2000);
    }
  };
  
  const subtotal = cart.reduce((a,p)=>a+p.price,0);
  const shipping = subtotal > 50 ? 0 : 9.99;
  const tax = subtotal * 0.13;
  const total = subtotal + shipping + tax;
  
  return(
    <div style={{padding:"0 24px 110px"}}>
      <div style={{paddingTop:26,paddingBottom:8}}>
        <SL>Skincare Collection</SL>
        <h1 style={{fontFamily:SERIF,fontSize:30,fontWeight:300,color:C.text,marginTop:5}}>
          AURA-GEN <GoldText size={30} weight={300}>Series</GoldText>
        </h1>
      </div>
      <Divider style={{margin:"14px 0 18px"}}/>
      {flash&&<div style={{background:"rgba(91,184,138,0.08)",border:"0.5px solid rgba(91,184,138,0.3)",borderRadius:8,
        padding:"11px 16px",marginBottom:14,display:"flex",alignItems:"center",gap:10,animation:"silkIn 0.3s ease"}}>
        <Icon n="check" size={14} color={C.green}/><span style={{fontFamily:SANS,fontSize:11,color:C.green}}>Added to your collection</span>
      </div>}
      {cart.length>0&&<div style={{background:C.card,border:`0.5px solid ${C.borderGold}`,borderRadius:10,padding:"13px 16px",
        marginBottom:16,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div style={{display:"flex",alignItems:"center",gap:9}}>
          <Icon n="cart" size={15} color={C.gold}/>
          <span style={{fontFamily:SANS,fontSize:11,color:C.text}}>{cart.length} item{cart.length>1?"s":""} - {"CA$"}{subtotal.toFixed(2)}</span>
        </div>
        <button onClick={()=>setShowCheckout(true)} className="lbtn" style={{background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,border:"none",borderRadius:3,
          padding:"8px 16px",fontFamily:SANS,fontSize:9,letterSpacing:"0.14em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>Checkout</button>
      </div>}
      
      {/* Checkout Modal */}
      {showCheckout && (
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.9)",zIndex:2000,display:"flex",flexDirection:"column",overflow:"auto"}}>
          <div style={{padding:"16px 20px",borderBottom:`1px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
            <h2 style={{fontFamily:SERIF,fontSize:18,color:C.text,margin:0}}>
              {checkoutStep==='cart'&&'Your Cart'}
              {checkoutStep==='shipping'&&'Shipping'}
              {checkoutStep==='payment'&&'Payment'}
              {checkoutStep==='success'&&'Order Confirmed'}
            </h2>
            {checkoutStep!=='success'&&<button onClick={()=>{setShowCheckout(false);setCheckoutStep('cart');}} style={{background:"none",border:"none",color:C.textDim,fontSize:20,cursor:"pointer"}}>×</button>}
          </div>
          
          <div style={{flex:1,padding:"20px",overflowY:"auto"}}>
            {checkoutStep==='cart'&&(
              <>
                {cart.map((item,idx)=>(
                  <div key={idx} style={{display:"flex",gap:12,marginBottom:16,paddingBottom:16,borderBottom:`1px solid ${C.border}`}}>
                    <div style={{width:60,height:60,borderRadius:8,background:C.card,overflow:"hidden"}}>
                      {item.image&&<img src={item.image} alt={item.name} style={{width:"100%",height:"100%",objectFit:"cover"}}/>}
                    </div>
                    <div style={{flex:1}}>
                      <p style={{fontFamily:SANS,fontSize:12,color:C.text,marginBottom:4}}>{item.name}</p>
                      <p style={{fontFamily:SERIF,fontSize:14,color:C.gold}}>CA${item.price.toFixed(2)}</p>
                    </div>
                    <button onClick={()=>remove(idx)} style={{background:"none",border:"none",color:C.red,fontSize:16,cursor:"pointer",alignSelf:"center"}}>×</button>
                  </div>
                ))}
                <div style={{marginTop:20,padding:16,background:C.card,borderRadius:10}}>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.textDim}}>Subtotal</span>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.text}}>CA${subtotal.toFixed(2)}</span>
                  </div>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.textDim}}>Shipping</span>
                    <span style={{fontFamily:SANS,fontSize:12,color:shipping===0?C.green:C.text}}>{shipping===0?'FREE':'CA$'+shipping.toFixed(2)}</span>
                  </div>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:12}}>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.textDim}}>Tax (13%)</span>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.text}}>CA${tax.toFixed(2)}</span>
                  </div>
                  <Divider style={{margin:"12px 0"}}/>
                  <div style={{display:"flex",justifyContent:"space-between"}}>
                    <span style={{fontFamily:SERIF,fontSize:16,color:C.text}}>Total</span>
                    <span style={{fontFamily:SERIF,fontSize:18,color:C.gold}}>CA${total.toFixed(2)}</span>
                  </div>
                </div>
              </>
            )}
            
            {checkoutStep==='shipping'&&(
              <div style={{display:"flex",flexDirection:"column",gap:12}}>
                <input value={shippingInfo.name} onChange={e=>setShippingInfo(s=>({...s,name:e.target.value}))} placeholder="Full Name" style={{padding:"14px",background:C.card,border:`1px solid ${C.border}`,borderRadius:8,color:C.text,fontFamily:SANS,fontSize:13}}/>
                <input value={shippingInfo.address} onChange={e=>setShippingInfo(s=>({...s,address:e.target.value}))} placeholder="Street Address" style={{padding:"14px",background:C.card,border:`1px solid ${C.border}`,borderRadius:8,color:C.text,fontFamily:SANS,fontSize:13}}/>
                <div style={{display:"flex",gap:12}}>
                  <input value={shippingInfo.city} onChange={e=>setShippingInfo(s=>({...s,city:e.target.value}))} placeholder="City" style={{flex:1,padding:"14px",background:C.card,border:`1px solid ${C.border}`,borderRadius:8,color:C.text,fontFamily:SANS,fontSize:13}}/>
                  <input value={shippingInfo.postal} onChange={e=>setShippingInfo(s=>({...s,postal:e.target.value}))} placeholder="Postal Code" style={{flex:1,padding:"14px",background:C.card,border:`1px solid ${C.border}`,borderRadius:8,color:C.text,fontFamily:SANS,fontSize:13}}/>
                </div>
                <input value={shippingInfo.phone} onChange={e=>setShippingInfo(s=>({...s,phone:e.target.value}))} placeholder="Phone (optional)" style={{padding:"14px",background:C.card,border:`1px solid ${C.border}`,borderRadius:8,color:C.text,fontFamily:SANS,fontSize:13}}/>
                
                <div style={{marginTop:12,padding:16,background:C.card,borderRadius:10}}>
                  <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,marginBottom:8}}>Shipping Method</p>
                  <div style={{display:"flex",gap:10}}>
                    <div style={{flex:1,padding:12,background:shipping===0?`${C.gold}15`:C.surface,border:`1px solid ${shipping===0?C.gold:C.border}`,borderRadius:8,textAlign:"center"}}>
                      <p style={{fontFamily:SANS,fontSize:11,color:C.text}}>Standard</p>
                      <p style={{fontFamily:SANS,fontSize:10,color:C.textDim}}>3-5 days</p>
                      <p style={{fontFamily:SERIF,fontSize:14,color:C.green,marginTop:4}}>{subtotal>50?'FREE':'CA$9.99'}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {checkoutStep==='payment'&&(
              <div style={{display:"flex",flexDirection:"column",gap:12}}>
                <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,marginBottom:8}}>Payment Method</p>
                <div style={{padding:16,background:`${C.gold}10`,border:`1px solid ${C.gold}`,borderRadius:10,display:"flex",alignItems:"center",gap:12}}>
                  <div style={{width:40,height:28,background:C.gold,borderRadius:4,display:"flex",alignItems:"center",justifyContent:"center"}}>
                    <Icon n="cart" size={16} color={C.void}/>
                  </div>
                  <div>
                    <p style={{fontFamily:SANS,fontSize:12,color:C.text}}>Pay with Card</p>
                    <p style={{fontFamily:SANS,fontSize:10,color:C.textDim}}>Visa, Mastercard, Amex</p>
                  </div>
                </div>
                
                <div style={{marginTop:16,padding:16,background:C.card,borderRadius:10}}>
                  <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,marginBottom:12}}>Order Summary</p>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.text}}>{cart.length} item(s)</span>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.text}}>CA${subtotal.toFixed(2)}</span>
                  </div>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.textDim}}>Shipping</span>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.green}}>{shipping===0?'FREE':'CA$'+shipping.toFixed(2)}</span>
                  </div>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:12}}>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.textDim}}>Tax</span>
                    <span style={{fontFamily:SANS,fontSize:12,color:C.text}}>CA${tax.toFixed(2)}</span>
                  </div>
                  <Divider style={{margin:"12px 0"}}/>
                  <div style={{display:"flex",justifyContent:"space-between"}}>
                    <span style={{fontFamily:SERIF,fontSize:16,color:C.text}}>Total</span>
                    <span style={{fontFamily:SERIF,fontSize:20,color:C.gold}}>CA${total.toFixed(2)}</span>
                  </div>
                </div>
                
                <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,textAlign:"center",marginTop:8}}>
                  By completing this order, you agree to our Terms of Service and Privacy Policy.
                </p>
              </div>
            )}
            
            {checkoutStep==='success'&&(
              <div style={{textAlign:"center",paddingTop:40}}>
                <div style={{width:70,height:70,borderRadius:"50%",background:`linear-gradient(135deg,${C.green},#22a55e)`,margin:"0 auto 20px",display:"flex",alignItems:"center",justifyContent:"center"}}>
                  <Icon n="check" size={32} color="white" sw={2.5}/>
                </div>
                <h3 style={{fontFamily:SERIF,fontSize:22,color:C.text,marginBottom:8}}>Thank You!</h3>
                <p style={{fontFamily:SANS,fontSize:13,color:C.textDim,marginBottom:24}}>Your order has been placed successfully.</p>
                <p style={{fontFamily:SANS,fontSize:11,color:C.gold}}>Order #RR{Date.now().toString().slice(-6)}</p>
                <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:16}}>You will receive an email confirmation shortly.</p>
              </div>
            )}
          </div>
          
          {checkoutStep!=='success'&&(
            <div style={{padding:"16px 20px",borderTop:`1px solid ${C.border}`}}>
              <button onClick={handleCheckout} disabled={processing||cart.length===0} style={{
                width:"100%",padding:"16px",
                background:processing?C.card:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
                border:"none",borderRadius:8,
                fontFamily:SANS,fontSize:12,letterSpacing:"0.1em",textTransform:"uppercase",
                color:processing?C.textDim:C.void,cursor:processing?"wait":"pointer"
              }}>
                {processing?'Processing...':(
                  checkoutStep==='cart'?'Continue to Shipping':
                  checkoutStep==='shipping'?'Continue to Payment':
                  `Pay CA$${total.toFixed(2)}`
                )}
              </button>
              {checkoutStep!=='cart'&&(
                <button onClick={()=>setCheckoutStep(checkoutStep==='payment'?'shipping':'cart')} style={{
                  width:"100%",marginTop:10,padding:"12px",background:"transparent",
                  border:`1px solid ${C.border}`,borderRadius:8,
                  fontFamily:SANS,fontSize:11,color:C.textDim,cursor:"pointer"
                }}>Back</button>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Combo Offers Section */}
      <div style={{marginBottom:20}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
          <SL>Combo Deals</SL>
          <span style={{fontFamily:SANS,fontSize:9,color:C.gold,letterSpacing:"0.1em"}}>SAVE UP TO 20%</span>
        </div>
        <div style={{display:"flex",gap:10,overflowX:"auto",paddingBottom:8,scrollSnapType:"x mandatory"}}>
          {[
            {id:"combo1",name:"Starter Kit",items:["TXA+PDRN Serum","Accelerator Cream"],originalPrice:174,salePrice:149,discount:"15%",color:C.gold},
            {id:"combo2",name:"Complete Routine",items:["TXA+PDRN Serum","Accelerator Cream","Recovery Complex"],originalPrice:274,salePrice:219,discount:"20%",color:C.copper},
            {id:"combo3",name:"Glow Duo",items:["TXA+PDRN Serum","Recovery Complex"],originalPrice:199,salePrice:169,discount:"15%",color:C.blue}
          ].map((combo,i)=>(
            <div key={combo.id} onClick={()=>{
              // Add all items from combo to cart
              const comboItems = combo.items.map(itemName => {
                const product = products.find(p => p.name.includes(itemName.split(" ")[0]));
                return product || {id:combo.id+i,name:itemName,price:combo.salePrice/combo.items.length};
              });
              setCart(c=>[...c,...comboItems]);
              setFlash(true);
              setTimeout(()=>setFlash(false),2200);
            }} style={{
              minWidth:160,flexShrink:0,scrollSnapAlign:"start",
              background:`linear-gradient(145deg,${combo.color}15,${C.card})`,
              border:`0.5px solid ${combo.color}44`,borderRadius:14,padding:14,cursor:"pointer",
              animation:`silkIn 0.4s ease ${i*0.1}s both`
            }} className="chov">
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:10}}>
                <span style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.12em",textTransform:"uppercase",
                  color:combo.color,background:`${combo.color}22`,padding:"3px 8px",borderRadius:3}}>
                  {combo.discount} OFF
                </span>
              </div>
              <p style={{fontFamily:SERIF,fontSize:15,fontWeight:300,color:C.text,marginBottom:6}}>{combo.name}</p>
              <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginBottom:10,lineHeight:1.5}}>
                {combo.items.join(" + ")}
              </p>
              <div style={{display:"flex",alignItems:"baseline",gap:8}}>
                <span style={{fontFamily:SERIF,fontSize:18,color:combo.color}}>CA${combo.salePrice}</span>
                <span style={{fontFamily:SANS,fontSize:11,color:C.textDim,textDecoration:"line-through"}}>CA${combo.originalPrice}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      <SL style={{marginBottom:12}}>All Products</SL>
      <div style={{display:"flex",flexDirection:"column",gap:12}}>
        {loadingProducts?<p style={{textAlign:"center",color:C.textDim,padding:20}}>Loading products...</p>:
        products.map((p,i)=>(
          <div key={p.id} className="chov" onClick={()=>setSel(p)} style={{
            background:C.card,border:`0.5px solid ${C.border}`,borderRadius:18,overflow:"hidden",cursor:"pointer",
            animation:`silkIn 0.5s ease ${i*0.1}s both`}}>
            <div style={{background:p.hue,padding:"20px 18px 14px",display:"flex",alignItems:"center",
              justifyContent:"space-between",position:"relative",overflow:"hidden"}}>
              <div style={{position:"absolute",inset:0,background:`radial-gradient(circle at 70% 50%,${p.accent}10,transparent 60%)`}}/>
              <div>
                <SL style={{color:p.accent,opacity:.85,marginBottom:6}}>{p.subtitle}</SL>
                <p style={{fontFamily:SERIF,fontSize:19,fontWeight:300,color:C.text,lineHeight:1.15}}>{p.name}</p>
                <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:3}}>{p.size}</p>
                <div style={{marginTop:9,display:"inline-block",padding:"3px 9px",border:`0.5px solid ${p.accent}44`,borderRadius:2}}>
                  <span style={{fontFamily:SANS,fontSize:7.5,color:p.accent,letterSpacing:"0.12em"}}>{p.tag.toUpperCase()}</span>
                </div>
              </div>
              <div style={{flexShrink:0,animation:"floatBottle 3s ease-in-out infinite"}}>
                {p.image_url || p.image 
                  ? <img src={p.image_url || p.image} alt={p.name} style={{width:100,height:100,objectFit:"contain"}} onError={(e)=>{e.target.style.display='none';e.target.nextSibling.style.display='block';}}/> 
                  : null}
                <div style={{display:p.image_url||p.image?'none':'block'}}>{BottleFor(p,100)}</div>
              </div>
            </div>
            <div style={{padding:"14px 18px 16px"}}>
              <p style={{fontFamily:SERIF,fontStyle:"italic",color:C.textSub,fontSize:12,lineHeight:1.65,marginBottom:12}}>{p.desc}</p>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end"}}>
                <GoldText size={20} weight={300}>{"CA$"}{p.price}</GoldText>
                <div style={{display:"flex",alignItems:"center",gap:2}}>
                  {[1,2,3,4,5].map(s=><Icon key={s} n="star" size={10} color={s<=Math.floor(p.rating)?C.gold:"rgba(255,255,255,0.08)"}/>)}
                  <span style={{fontFamily:SANS,color:C.textDim,fontSize:9,marginLeft:3}}>{p.rating}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <ProductSheet p={sel} onClose={()=>setSel(null)} onAdd={add}/>
    </div>
  );
};

const OrdersScreen=()=>{
  const steps=["Placed","Processing","Shipped","Delivered"];
  const ss={"Delivered":{color:C.green,bg:"rgba(91,184,138,0.08)",bdr:"rgba(91,184,138,0.2)"},
    "In Transit":{color:C.blue,bg:"rgba(107,174,214,0.08)",bdr:"rgba(107,174,214,0.2)"},
    "Processing":{color:C.gold,bg:"rgba(201,168,110,0.08)",bdr:"rgba(201,168,110,0.2)"}};
  return(
    <div style={{padding:"0 24px 110px"}}>
      <div style={{paddingTop:26,paddingBottom:8}}>
        <SL>Purchase History</SL>
        <h1 style={{fontFamily:SERIF,fontSize:30,fontWeight:300,color:C.text,marginTop:5}}>My <GoldText size={30} weight={300}>Orders</GoldText></h1>
      </div>
      <Divider style={{margin:"14px 0 20px"}}/>
      <div style={{display:"flex",flexDirection:"column",gap:13}}>
        {ORDERS_DATA.map((o,i)=>{
          const s=ss[o.status];
          const prod=PRODUCTS.find(p=>p.id===o.pid)||PRODUCTS[i];
          return(
            <div key={o.id} className="chov" style={{background:C.card,border:`0.5px solid ${C.border}`,
              borderRadius:16,overflow:"hidden",animation:`silkIn 0.5s ease ${i*0.1}s both`}}>
              <div style={{background:prod.hue,padding:"14px 18px",display:"flex",alignItems:"center",gap:12,
                borderBottom:`0.5px solid ${C.border}`}}>
                <div style={{flexShrink:0}}>{BottleFor(prod,48)}</div>
                <div style={{flex:1}}>
                  <p style={{fontFamily:SANS,fontSize:8,color:C.textDim,letterSpacing:"0.18em",textTransform:"uppercase"}}>{o.id}</p>
                  <p style={{fontFamily:SERIF,fontSize:14,color:C.text,marginTop:3}}>{o.name}</p>
                  <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:1}}>{o.date} - {o.total}</p>
                </div>
                <span style={{fontFamily:SANS,fontSize:8,letterSpacing:"0.1em",textTransform:"uppercase",
                  padding:"4px 10px",borderRadius:2,color:s.color,background:s.bg,border:`0.5px solid ${s.bdr}`,whiteSpace:"nowrap"}}>{o.status}</span>
              </div>
              <div style={{padding:"14px 18px"}}>
                <div style={{display:"flex",alignItems:"flex-start"}}>
                  {steps.map((st,idx)=>(
                    <div key={st} style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center"}}>
                      <div style={{display:"flex",alignItems:"center",width:"100%"}}>
                        {idx>0&&<div style={{flex:1,height:"0.5px",background:idx<o.step?C.gold:C.border}}/>}
                        <div style={{width:16,height:16,borderRadius:"50%",flexShrink:0,
                          background:idx<o.step?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,
                          border:`0.5px solid ${idx<o.step?C.gold:C.border}`,
                          display:"flex",alignItems:"center",justifyContent:"center"}}>
                          {idx<o.step&&<div style={{width:4,height:4,borderRadius:"50%",background:C.void}}/>}
                        </div>
                        {idx<3&&<div style={{flex:1,height:"0.5px",background:idx<o.step-1?C.gold:C.border}}/>}
                      </div>
                      <p style={{fontFamily:SANS,fontSize:7,letterSpacing:"0.07em",color:idx<o.step?C.goldDeep:C.textDim,marginTop:4,textAlign:"center"}}>{st}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Loyalty=({user})=>{
  const [showRedeem, setShowRedeem] = useState(false);
  const [redeemAmount, setRedeemAmount] = useState(100);
  const [redeemSuccess, setRedeemSuccess] = useState(false);
  
  const tiers=[
    {name:"Silver",range:"0 - 999",color:"#9CA3AF",current:user.tier==="Silver"},
    {name:"Gold",range:"1,000 - 3,999",color:C.gold,current:user.tier==="Gold"},
    {name:"Diamond",range:"4,000 - 7,999",color:C.blue,current:user.tier==="Diamond"},
    {name:"Elite",range:"8,000+",color:C.copper,current:user.tier==="Elite"},
  ];
  
  const handleRedeem = async () => {
    if (redeemAmount > user.points) return;
    try {
      // Call API to redeem points
      await apiReq("POST", "/api/loyalty/redeem", { points: redeemAmount });
      setRedeemSuccess(true);
      setTimeout(() => {
        setShowRedeem(false);
        setRedeemSuccess(false);
      }, 2000);
    } catch (e) {
      alert("Failed to redeem points. Please try again.");
    }
  };
  
  return(
    <div style={{padding:"0 24px 110px"}}>
      <div style={{paddingTop:26,paddingBottom:8}}>
        <SL>Rewards Programme</SL>
        <h1 style={{fontFamily:SERIF,fontSize:30,fontWeight:300,color:C.text,marginTop:5}}>Loyalty <GoldText size={30} weight={300}>Hub</GoldText></h1>
      </div>
      <Divider style={{margin:"14px 0 20px"}}/>
      <div style={{background:"linear-gradient(150deg,#1c1608,#251d09",border:`0.5px solid ${C.borderGold}`,
        borderRadius:20,padding:"28px 20px 24px",marginBottom:20,textAlign:"center",position:"relative",overflow:"hidden"}}>
        <div style={{position:"absolute",top:"50%",left:"50%",transform:"translate(-50%,-50%)",width:200,height:200,borderRadius:"50%",
          background:`radial-gradient(circle,${C.gold}0a,transparent 70%)`,animation:"glowPulse 3.5s ease-in-out infinite"}}/>
        <SL style={{marginBottom:8}}>Available Balance</SL>
        <GoldText size={50} weight={300}>{user.points.toLocaleString()}</GoldText>
        <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,marginTop:4}}>= {"CA$"}{(user.points*0.01).toFixed(2)} store credit</p>
        <Divider style={{margin:"16px 0"}}/>
        <button onClick={() => setShowRedeem(true)} className="lbtn" style={{background:`linear-gradient(135deg,${C.goldDeep},${C.goldBright})`,border:"none",borderRadius:4,
          padding:"14px 36px",fontFamily:SANS,fontSize:11,letterSpacing:"0.18em",textTransform:"uppercase",color:C.void,cursor:"pointer"}}>Redeem Points</button>
      </div>
      
      {/* Redeem Points Modal */}
      {showRedeem && (
        <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.85)",zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center",padding:20}}>
          <div style={{background:C.surface,border:`1px solid ${C.borderGold}`,borderRadius:16,padding:24,maxWidth:320,width:"100%",textAlign:"center"}}>
            {redeemSuccess ? (
              <>
                <div style={{width:50,height:50,borderRadius:"50%",background:`linear-gradient(135deg,${C.green},#22a55e)`,margin:"0 auto 16px",display:"flex",alignItems:"center",justifyContent:"center"}}>
                  <Icon n="check" size={24} color="white" sw={2.5}/>
                </div>
                <h3 style={{fontFamily:SERIF,fontSize:18,color:C.text,marginBottom:8}}>Points Redeemed!</h3>
                <p style={{fontFamily:SANS,fontSize:12,color:C.textDim}}>CA${(redeemAmount * 0.01).toFixed(2)} has been added to your account</p>
              </>
            ) : (
              <>
                <h3 style={{fontFamily:SERIF,fontSize:18,color:C.text,marginBottom:16}}>Redeem Points</h3>
                <p style={{fontFamily:SANS,fontSize:11,color:C.textDim,marginBottom:16}}>Convert your points to store credit</p>
                
                <div style={{display:"flex",gap:8,marginBottom:16,justifyContent:"center"}}>
                  {[100, 250, 500].map(amt => (
                    <button key={amt} onClick={() => setRedeemAmount(amt)} 
                      disabled={amt > user.points}
                      style={{
                        padding:"10px 16px",borderRadius:8,border:`1px solid ${redeemAmount===amt?C.gold:C.border}`,
                        background:redeemAmount===amt?`${C.gold}15`:"transparent",
                        color:amt > user.points ? C.textDim : (redeemAmount===amt?C.gold:C.text),
                        cursor:amt > user.points?"not-allowed":"pointer",fontFamily:SANS,fontSize:11,
                        opacity:amt > user.points?0.5:1
                      }}>
                      {amt} pts
                    </button>
                  ))}
                </div>
                
                <p style={{fontFamily:SANS,fontSize:13,color:C.gold,marginBottom:20}}>
                  = CA${(redeemAmount * 0.01).toFixed(2)} store credit
                </p>
                
                <div style={{display:"flex",gap:10}}>
                  <button onClick={() => setShowRedeem(false)} style={{
                    flex:1,padding:"12px",background:"transparent",border:`1px solid ${C.border}`,
                    borderRadius:6,color:C.textDim,fontFamily:SANS,fontSize:11,cursor:"pointer"
                  }}>Cancel</button>
                  <button onClick={handleRedeem} disabled={redeemAmount > user.points} style={{
                    flex:1,padding:"12px",background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
                    border:"none",borderRadius:6,color:C.void,fontFamily:SANS,fontSize:11,fontWeight:600,cursor:"pointer"
                  }}>Confirm</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
      
      <SL style={{marginBottom:11}}>Membership Tiers</SL>
      <div style={{display:"flex",flexDirection:"column",gap:9,marginBottom:20}}>
        {tiers.map((t,i)=>(
          <div key={t.name} className="chov" style={{background:t.current?`linear-gradient(135deg,${t.color}0a,transparent)`:C.card,
            border:`0.5px solid ${t.current?t.color+"44":C.border}`,borderRadius:10,padding:"13px 15px",
            display:"flex",justifyContent:"space-between",alignItems:"center",animation:`silkIn 0.4s ease ${i*0.07}s both`}}>
            <div style={{display:"flex",alignItems:"center",gap:11}}>
              <Icon n="loyalty" size={14} color={t.color}/>
              <div>
                <p style={{fontFamily:SERIF,fontSize:14,color:t.current?t.color:C.text}}>{t.name}</p>
                <p style={{fontFamily:SANS,fontSize:9,color:C.textDim,marginTop:1}}>{t.range} pts</p>
              </div>
            </div>
            {t.current&&<span style={{fontFamily:SANS,fontSize:7.5,letterSpacing:"0.16em",textTransform:"uppercase",
              color:t.color,border:`0.5px solid ${t.color}44`,padding:"3px 9px",borderRadius:2}}>Current</span>}
          </div>
        ))}
      </div>
    </div>
  );
};

const AIAdvisor=({user})=>{
  const [msgs,setMsgs]=useState([{role:"assistant",content:`Welcome, ${user.name.split(" ")[0]}. I'm your ReRoots AI Skin Advisor - an expert cosmetic chemist for the AURA-GEN Series. Ask me anything about your formulations, ingredients, or skin protocol.`}]);
  const [input,setInput]=useState("");
  const [loading,setLoading]=useState(false);
  const endRef=useRef(null);
  useEffect(()=>{endRef.current?.scrollIntoView({behavior:"smooth"});},[msgs]);
  const send=async()=>{
    if(!input.trim()||loading) return;
    const msg=input.trim();setInput("");
    setMsgs(m=>[...m,{role:"user",content:msg}]);setLoading(true);
    try{
      const res=await apiReq("POST","/api/ai/chat",{message:msg,context:{user:user.name,skinType:user.skinType,tier:user.tier}});
      setMsgs(m=>[...m,{role:"assistant",content:res.response||"Please retry."}]);
    }catch{
      setMsgs(m=>[...m,{role:"assistant",content:"Connection interrupted. Please retry."}]);
    }
    setLoading(false);
  };
  const quickQ=["Best morning protocol?","PDRN mechanism?","Layer with retinol?","Sensitive skin tips"];
  return(
    <div style={{display:"flex",flexDirection:"column",height:"100%",overflow:"hidden"}}>
      <div style={{padding:"20px 24px 12px",borderBottom:`0.5px solid ${C.border}`,flexShrink:0}}>
        <div style={{display:"flex",alignItems:"center",gap:11}}>
          <div style={{width:40,height:40,borderRadius:"50%",background:`radial-gradient(circle,${C.blue}22,${C.blue}08)`,
            border:`0.5px solid ${C.blue}33`,display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Icon n="ai" size={18} color={C.blue}/>
          </div>
          <div>
            <p style={{fontFamily:SERIF,fontSize:16,fontWeight:400,color:C.text}}>AI Skin Advisor</p>
            <p style={{fontFamily:SANS,fontSize:10,color:C.green,letterSpacing:"0.1em"}}>Live - Powered by AI</p>
          </div>
        </div>
      </div>
      <div style={{flex:1,overflowY:"auto",padding:"16px 22px",display:"flex",flexDirection:"column",gap:11}}>
        {msgs.map((m,i)=>(
          <div key={i} style={{display:"flex",justifyContent:m.role==="user"?"flex-end":"flex-start"}}>
            <div style={{maxWidth:"84%",padding:"12px 16px",
              borderRadius:m.role==="user"?"18px 18px 4px 18px":"18px 18px 18px 4px",
              background:m.role==="user"?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.card,
              border:m.role==="assistant"?`0.5px solid ${C.border}`:"none",
              color:m.role==="user"?C.void:C.text,fontFamily:SERIF,fontSize:14,lineHeight:1.7,fontWeight:300}}>{m.content}</div>
          </div>
        ))}
        {loading&&<div style={{display:"flex"}}><div style={{background:C.card,border:`0.5px solid ${C.border}`,
          borderRadius:"18px 18px 18px 4px",padding:"12px 18px",display:"flex",gap:5}}>
          {[0,1,2].map(i=><div key={i} style={{width:6,height:6,borderRadius:"50%",background:C.gold,animation:`dotBounce 1.2s ${i*0.2}s ease-in-out infinite`}}/>)}
        </div></div>}
        <div ref={endRef}/>
      </div>
      {msgs.length<=1&&<div style={{padding:"0 22px 10px",display:"flex",gap:7,overflowX:"auto",flexShrink:0}}>
        {quickQ.map(q=>(
          <button key={q} className="lbtn" onClick={()=>setInput(q)} style={{background:"transparent",
            border:`0.5px solid ${C.borderGold}`,borderRadius:2,padding:"6px 12px",whiteSpace:"nowrap",
            fontFamily:SANS,fontSize:9,color:C.textSub,cursor:"pointer",flexShrink:0}}>{q}</button>
        ))}
      </div>}
      <div style={{padding:"10px 20px 13px",borderTop:`0.5px solid ${C.border}`,display:"flex",gap:9,flexShrink:0}}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()}
          placeholder="Ask your skin advisor..."
          style={{flex:1,background:C.card,border:`0.5px solid ${C.border}`,borderRadius:4,
            padding:"12px 15px",color:C.text,fontFamily:SERIF,fontSize:13,fontWeight:300}}/>
        <button className="lbtn" onClick={send} disabled={loading||!input.trim()} style={{
          background:input.trim()?`linear-gradient(135deg,${C.goldDeep},${C.gold})`:C.surface,
          border:"none",borderRadius:4,width:44,height:44,cursor:"pointer",
          display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
          <Icon n="send" size={15} color={input.trim()?C.void:C.textDim}/>
        </button>
      </div>
    </div>
  );
};

const Profile=({user,onLogout})=>(
  <div style={{padding:"0 24px 110px"}}>
    <div style={{paddingTop:26,paddingBottom:8}}>
      <SL>Account</SL>
      <h1 style={{fontFamily:SERIF,fontSize:30,fontWeight:300,color:C.text,marginTop:5}}>My <GoldText size={30} weight={300}>Profile</GoldText></h1>
    </div>
    <Divider style={{margin:"14px 0 20px"}}/>
    <div style={{background:"linear-gradient(150deg,#1c1608,#211d0b)",border:`0.5px solid ${C.borderGold}`,
      borderRadius:20,padding:"24px 20px",marginBottom:16,textAlign:"center",animation:"silkIn 0.5s ease both"}}>
      <div style={{width:62,height:62,borderRadius:"50%",margin:"0 auto 10px",
        background:`linear-gradient(135deg,${C.goldDeep},${C.goldBright})`,
        display:"flex",alignItems:"center",justifyContent:"center",fontFamily:SERIF,fontSize:20,color:C.void}}>
        {user.name.split(" ").map(n=>n[0]).join("").slice(0,2)}
      </div>
      <p style={{fontFamily:SERIF,fontSize:20,fontWeight:300,color:C.text}}>{user.name}</p>
      <p style={{fontFamily:SANS,fontSize:10,color:C.textDim,marginTop:2,letterSpacing:"0.06em"}}>{user.email}</p>
      {user.skinType&&<p style={{fontFamily:SANS,fontSize:10,color:C.textSub,marginTop:3}}>{user.skinType} Skin Type</p>}
      <div style={{marginTop:10,display:"inline-flex",alignItems:"center",gap:7,
        border:`0.5px solid ${C.borderGold}`,borderRadius:2,padding:"4px 13px"}}>
        <Icon n="star" size={11} color={C.gold}/>
        <span style={{fontFamily:SANS,fontSize:8,color:C.gold,letterSpacing:"0.14em",textTransform:"uppercase"}}>{user.tier} Member</span>
      </div>
    </div>
    {/* Admin Panel Access - Only visible to admin users */}
    {user.role === "admin" && (
      <a href="/new-admin" style={{display:"block",textDecoration:"none",marginBottom:16}}>
        <div className="lbtn" style={{background:`linear-gradient(135deg,${C.goldDeep},${C.gold})`,
          border:"none",borderRadius:12,padding:"18px 20px",
          display:"flex",alignItems:"center",justifyContent:"space-between",cursor:"pointer"}}>
          <div style={{display:"flex",alignItems:"center",gap:12}}>
            <Icon n="settings" size={20} color={C.void}/>
            <div>
              <p style={{fontFamily:SANS,fontSize:11,letterSpacing:"0.1em",textTransform:"uppercase",color:C.void,fontWeight:500}}>Admin Panel</p>
              <p style={{fontFamily:SERIF,fontSize:12,color:"rgba(0,0,0,0.6)",marginTop:2}}>Manage store & orders</p>
            </div>
          </div>
          <Icon n="chevronRight" size={18} color={C.void}/>
        </div>
      </a>
    )}
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10,marginBottom:16}}>
      {[{label:"Points",value:user.points.toLocaleString()},{label:"Tier",value:user.tier},
        {label:"Skin Type",value:user.skinType||"-"},{label:"Offers",value:user.offers!==false?"Active":"Off"}].map((s,i)=>(
        <div key={s.label} className="chov" style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:12,padding:"14px",
          animation:`silkIn 0.4s ease ${i*0.07}s both`}}>
          <SL style={{marginBottom:6}}>{s.label}</SL>
          <p style={{fontFamily:SERIF,fontSize:20,fontWeight:300,color:C.text}}>{s.value}</p>
        </div>
      ))}
    </div>
    <div style={{background:C.card,border:`0.5px solid ${C.border}`,borderRadius:14,padding:"18px",marginBottom:14}}>
      <SL style={{marginBottom:14}}>Prescribed Routine</SL>
      {[{time:"A.M.",steps:"Cleanse -> TXA+PDRN Serum -> SPF 50+"},{time:"P.M.",steps:"Cleanse -> Recovery Complex -> Rich Cream"}].map((r,i)=>(
        <div key={r.time}>
          <div style={{display:"flex",gap:12,padding:"10px 0"}}>
            <span style={{fontFamily:SERIF,fontStyle:"italic",fontSize:13,color:C.gold,minWidth:32,paddingTop:1}}>{r.time}</span>
            <p style={{fontFamily:SANS,fontSize:11,color:C.textSub,lineHeight:1.8}}>{r.steps}</p>
          </div>
          {i===0&&<div style={{height:"0.5px",background:C.border}}/>}
        </div>
      ))}
    </div>
    <button className="lbtn" onClick={onLogout} style={{width:"100%",background:"transparent",
      border:`0.5px solid ${C.border}`,borderRadius:4,padding:"16px",
      fontFamily:SANS,fontSize:11,letterSpacing:"0.16em",textTransform:"uppercase",color:C.textDim,cursor:"pointer"}}>
      Sign Out
    </button>
  </div>
);

const TABS=[
  {id:"home",label:"Home",icon:"home"},{id:"shop",label:"Shop",icon:"shop"},
  {id:"orders",label:"Orders",icon:"orders"},{id:"loyalty",label:"Loyalty",icon:"loyalty"},
  {id:"ai",label:"Advisor",icon:"ai"},{id:"profile",label:"Profile",icon:"profile"},
];

/* ── ROOT ─────────────────────────────────────────────────────────────────── */
export default function CustomerApp(){
  const [authState,setAuthState]=useState("loading");
  const [user,setUser]=useState(null);
  const [tab,setTab]=useState("home");
  const [cart,setCart]=useState([]);
  const [resetToken,setResetToken]=useState(null);
  const [showSupport,setShowSupport]=useState(false);  // AI Chat support
  const [showScreenShare,setShowScreenShare]=useState(false);  // Screen share mode
  const [screenShareSession,setScreenShareSession]=useState(null);  // Session from admin request
  const [inviteCode,setInviteCode]=useState(null);  // Support invite code from URL
  const [inviteSession,setInviteSession]=useState(null);  // Session created from invite

  // Simple support click - opens AI chat first
  const handleSupportClick = () => {
    setShowSupport(!showSupport);
    setShowScreenShare(false);  // Close screen share if open
  };

  // Handle screen share request from admin (via SupportChat)
  const handleScreenShareRequest = (sessionId) => {
    setScreenShareSession({ session_id: sessionId });
    setShowScreenShare(true);
    setShowSupport(false);  // Close chat, open screen share
  };

  useEffect(()=>{
    // Check for password reset token in URL
    const urlParams=new URLSearchParams(window.location.search);
    const resetTokenParam=urlParams.get("reset_token");
    if(resetTokenParam){
      setResetToken(resetTokenParam);
      setAuthState("reset_password");
      window.history.replaceState({},document.title,window.location.pathname);
      return;
    }
    
    // Check for support invite code in URL
    const supportInvite=urlParams.get("support");
    if(supportInvite){
      setInviteCode(supportInvite.toUpperCase());
      // Clean URL but keep invite in state
      window.history.replaceState({},document.title,window.location.pathname);
    }
    
    const token=getToken();
    if(!token){setAuthState("welcome");return;}
    apiReq("GET","/api/auth/me")
      .then(data=>{setUser(normalizeUser(data));setAuthState("app");})
      .catch(()=>{clearToken();setAuthState("welcome");});
  },[]);

  // Auto-open support when there's an invite code and user is logged in
  useEffect(()=>{
    if(inviteCode && authState==="app" && user && !inviteSession){
      joinViaInvite();
    }
  },[inviteCode,authState,user]);

  // Join support session via invite link
  const joinViaInvite = async () => {
    if(!inviteCode) return;
    try {
      const res = await fetch(`${BASE_URL}/api/support/invite/${inviteCode}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.id || 'guest',
          user_name: user?.name || user?.email || 'Guest'
        })
      });
      if(res.ok){
        const data = await res.json();
        setInviteSession(data.session);
        setShowSupport(true);  // Auto-open support panel
      } else {
        console.log('[Support] Invite invalid or expired');
        setInviteCode(null);
      }
    } catch(e){
      console.error('[Support] Join invite error:', e);
      setInviteCode(null);
    }
  };

  const handleLogin=(u)=>{setUser(u);setAuthState("app");};
  const handleSignup=(u)=>{setUser(u);setAuthState("app");};
  const handleLogout=async()=>{
    try{await apiReq("POST","/api/auth/logout");}catch(_){}
    clearToken();
    setUser(null);setAuthState("welcome");setTab("home");setCart([]);
  };

  if(authState==="loading") return(
    <div className="rr-app" style={{height:"100vh",background:"#060608",display:"flex",alignItems:"center",justifyContent:"center"}}>
      <Styles/>
      <div style={{textAlign:"center"}}>
        <div style={{width:40,height:40,borderRadius:"50%",border:`1.5px solid rgba(201,168,110,0.3)`,
          borderTopColor:"#C9A86E",animation:"spin 0.9s linear infinite",margin:"0 auto"}}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
  if(authState==="welcome") return <div className="rr-app"><Styles/><WelcomeScreen onLogin={()=>setAuthState("login")} onSignup={()=>setAuthState("signup")}/></div>;
  if(authState==="login")   return <div className="rr-app"><Styles/><LoginScreen onBack={()=>setAuthState("welcome")} onSuccess={handleLogin} onForgotPassword={()=>setAuthState("forgot_password")}/></div>;
  if(authState==="signup")  return <div className="rr-app"><Styles/><SignupScreen onBack={()=>setAuthState("welcome")} onSuccess={handleSignup}/></div>;
  if(authState==="forgot_password") return <div className="rr-app"><Styles/><ForgotPasswordScreen onBack={()=>setAuthState("login")} onSuccess={()=>setAuthState("login")}/></div>;
  if(authState==="reset_password") return <div className="rr-app"><Styles/><ResetPasswordScreen token={resetToken} onBack={()=>setAuthState("login")} onSuccess={()=>setAuthState("login")}/></div>;

  const screens={
    home:<Home user={user} cart={cart} setTab={setTab}/>,
    shop:<Shop cart={cart} setCart={setCart}/>,
    orders:<OrdersScreen/>,
    loyalty:<Loyalty user={user}/>,
    ai:<AIAdvisor user={user}/>,
    profile:<Profile user={user} onLogout={handleLogout}/>,
  };

  return(
    <div className="rr-app" style={{background:C.void,minHeight:"100vh",maxWidth:480,margin:"0 auto",
      fontFamily:SERIF,position:"relative",display:"flex",flexDirection:"column",height:"100vh",overflow:"hidden"}}>
      <Styles/>
      <StatusBar />
      <div style={{flex:1,overflowY:tab==="ai"?"hidden":"auto",overflowX:"hidden"}}>
        {screens[tab]}
      </div>
      <div style={{background:`${C.noir}f0`,backdropFilter:"blur(24px) saturate(180%)",
        borderTop:`0.5px solid ${C.border}`,display:"flex",justifyContent:"space-around",
        padding:"8px 0 14px",flexShrink:0,zIndex:100}}>
        {TABS.map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)} style={{display:"flex",flexDirection:"column",alignItems:"center",gap:4,
            background:"none",border:"none",cursor:"pointer",padding:"3px 8px",flex:1}}>
            <div style={{position:"relative"}}>
              <Icon n={t.icon} size={20} color={tab===t.id?C.gold:C.textDim} sw={tab===t.id?1.2:1.1}/>
              {t.id==="shop"&&cart.length>0&&<div style={{position:"absolute",top:-4,right:-6,width:13,height:13,borderRadius:"50%",
                background:C.gold,display:"flex",alignItems:"center",justifyContent:"center"}}>
                <span style={{fontFamily:SANS,fontSize:7.5,color:C.void,fontWeight:700}}>{cart.length}</span>
              </div>}
            </div>
            <span style={{fontFamily:SANS,fontSize:7.5,letterSpacing:"0.1em",textTransform:"uppercase",
              color:tab===t.id?C.gold:C.textDim}}>{t.label}</span>
            {tab===t.id&&<div style={{width:14,height:"0.5px",background:C.gold,borderRadius:1}}/>}
          </button>
        ))}
      </div>
      
      {/* Floating Support Button */}
      {!showSupport && !showScreenShare && (
        <button
          onClick={handleSupportClick}
          data-testid="support-chat-btn"
          style={{
            position:"fixed", bottom:100, right:16,
            width:44, height:44, borderRadius:"50%",
            background:`linear-gradient(135deg, ${C.gold}, #b8956a)`,
            border:"none", cursor:"pointer",
            boxShadow:"0 4px 16px rgba(201,168,110,0.3)",
            display:"flex", alignItems:"center", justifyContent:"center",
            zIndex:9998
          }}
          title="Get Support"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C.void} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </button>
      )}
      
      {/* AI Support Chat */}
      {showSupport && (
        <SupportChat 
          user={user} 
          apiBase={BASE_URL} 
          onClose={()=>setShowSupport(false)}
          onRequestScreenShare={handleScreenShareRequest}
        />
      )}

      {/* Screen Share Mode (when admin requests) */}
      {showScreenShare && (
        <SupportMode 
          user={user} 
          apiBase={BASE_URL} 
          onClose={()=>{setShowScreenShare(false);setScreenShareSession(null);}}
          initialSession={screenShareSession}
        />
      )}
    </div>
  );
}
