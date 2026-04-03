import { useState, useEffect, useRef, useCallback } from "react";

/* ═══════════════════════════════════════════════════
   DESIGN TOKENS
═══════════════════════════════════════════════════ */
const C = {
  bg:'#EDEAE6', card:'#FFFFFF', gold:'#C9A227', goldL:'#F0D98A', goldD:'#8A6010',
  rose:'#C4788A', text:'#1A1A1A', sub:'#8A8A8A', border:'#E8E0D8', navBg:'#1A1A1A',
};

/* ═══════════════════════════════════════════════════
   MOCK DATA (fallback when API unavailable)
═══════════════════════════════════════════════════ */
const MOCK_PRODUCTS = [
  { id:1, name:'ACRC v4',   subtitle:'Rich Cream',         price:'$89 CAD',  category:'moisturizer', image_url:null },
  { id:2, name:'ARC v3',    subtitle:'Active Recovery Serum', price:'$89 CAD', category:'serum',       image_url:null },
  { id:3, name:'PM System', subtitle:'ACRC + ARC Combo',   price:'$149 CAD', category:'system',      image_url:null },
];
const MOCK_ORDERS = [
  { id:'RR-2026-001', date:'Mar 28, 2026', status:'Delivered', total:'$149.00', item:'AURA-GEN PM System' },
  { id:'RR-2026-002', date:'Feb 14, 2026', status:'Delivered', total:'$89.00',  item:'ARC v3 Serum' },
];

/* ═══════════════════════════════════════════════════
   LOGO SVG — 5-ring orbital wheel
═══════════════════════════════════════════════════ */
function RerootsLogo({ size=60, bg='#FFFFFF' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
      <defs>
        <linearGradient id={`rg${size}`} x1="10%" y1="0%" x2="90%" y2="100%">
          <stop offset="0%"   stopColor="#F0D98A"/>
          <stop offset="45%"  stopColor="#C9A227"/>
          <stop offset="100%" stopColor="#8A6010"/>
        </linearGradient>
      </defs>
      {[0,36,72,108,144].map(a =>
        <ellipse key={a} cx="50" cy="50" rx="33" ry="11"
          stroke={`url(#rg${size})`} strokeWidth="5.5" fill="none"
          transform={`rotate(${a} 50 50)`}/>
      )}
      <circle cx="50" cy="50" r="5.5" fill={bg}/>
    </svg>
  );
}

/* ═══════════════════════════════════════════════════
   ICONS
═══════════════════════════════════════════════════ */
function AIIcon({ size=52 }) {
  const g = C.gold;
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
      <rect x="50" y="11" width="54" height="54" rx="3" stroke={g} strokeWidth="2.2" fill="none" transform="rotate(45 50 50)"/>
      <rect x="50" y="22" width="40" height="40" rx="2"  stroke={g} strokeWidth="1.5" fill="none" transform="rotate(45 50 50)"/>
      <circle cx="50" cy="50" r="18" stroke={g} strokeWidth="1.5" fill="none"/>
      <circle cx="50" cy="50" r="12" stroke={g} strokeWidth="1.5" fill="none"/>
      <circle cx="50" cy="50" r="6"  stroke={g} strokeWidth="1.5" fill="none"/>
      <circle cx="50" cy="50" r="2.5" fill={g}/>
      {[0,45,90,135,180,225,270,315].map(a => {
        const r = (a*Math.PI)/180;
        return <line key={a} x1={50+7*Math.cos(r)} y1={50+7*Math.sin(r)} x2={50+17*Math.cos(r)} y2={50+17*Math.sin(r)} stroke={g} strokeWidth="1.3"/>;
      })}
      <circle cx="50" cy="21" r="3" fill={g}/>
      <circle cx="79" cy="50" r="3" fill={g}/>
      <circle cx="50" cy="79" r="3" fill={g}/>
      <circle cx="21" cy="50" r="3" fill={g}/>
    </svg>
  );
}

function VaultIcon({ size=52 }) {
  const g = C.gold;
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
      <path d="M50 7C50 7 26 36 26 52C26 67 37 77 50 77C63 77 74 67 74 52C74 36 50 7 50 7Z" stroke={g} strokeWidth="2.2" fill="none"/>
      <path d="M50 28C50 28 41 43 41 50C41 57 45 61 50 61C55 61 59 57 59 50C59 43 50 28 50 28Z" fill={g} opacity="0.55"/>
      {[25,34,43,50,57,66,75].map((x,i) => <circle key={`a${i}`} cx={x} cy="82" r="2.5" fill={g}/>)}
      {[34,43,50,57,66].map((x,i)       => <circle key={`b${i}`} cx={x} cy="91" r="2"   fill={g}/>)}
    </svg>
  );
}

/* ═══════════════════════════════════════════════════
   TIME / WEATHER HELPERS
═══════════════════════════════════════════════════ */
function getDayTheme(h) {
  if (h>=5  && h<12) return { phase:'morning', label:'MORNING RITUAL',   emoji:'🌅', greeting:'Good Morning',   accent:'#E8967A', bgGrad:'linear-gradient(135deg,#FFF5F0 0%,#FDF0E8 50%,#F5E4D8 100%)', dark:false };
  if (h>=12 && h<17) return { phase:'afternoon', label:'MIDDAY GLOW',    emoji:'✨', greeting:'Good Afternoon', accent:'#C9A227', bgGrad:'linear-gradient(135deg,#FEFBF2 0%,#F8F0DC 50%,#EDE0C0 100%)', dark:false };
  if (h>=17 && h<21) return { phase:'evening', label:'EVENING RESTORE',  emoji:'🌆', greeting:'Good Evening',   accent:'#C4788A', bgGrad:'linear-gradient(135deg,#F8F0F4 0%,#F0E4EC 50%,#E4D0DC 100%)', dark:false };
  return { phase:'night', label:'OVERNIGHT RECOVERY', emoji:'🌙', greeting:'Good Night', accent:'#C9A227', bgGrad:'linear-gradient(135deg,#1A1428 0%,#2A1F38 50%,#1E1730 100%)', dark:true };
}

function getWeatherInfo(code, temp, hum, h) {
  const isDay = h>=6 && h<20;
  let cond = 'Balanced', icon = '🌤️';
  if (code===0)               { cond='Sunny';   icon='☀️';  }
  else if (code<=3)           { cond='Cloudy';  icon='🌤️'; }
  else if (code<=48)          { cond='Foggy';   icon='🌫️'; }
  else if (code<=67)          { cond='Rainy';   icon='🌧️'; }
  else if (code<=77)          { cond='Snowy';   icon='❄️';  }
  else if (code<=82)          { cond='Showers'; icon='🌦️'; }
  else                        { cond='Stormy';  icon='⛈️';  }

  let tip = '"Balanced day — standard AURA-GEN PM ritual tonight."';
  if (code===0 && temp>22)   tip = '"High UV today — antioxidants first, SPF over ACRC."';
  else if (temp<3)           tip = '"Freezing air strips barrier — use 2 pumps of ACRC tonight."';
  else if (hum>78)           tip = '"High humidity — skip cream AM, ARC serum is enough."';
  else if (code>=51&&code<=82) tip = '"Rain means barrier stress — don\'t skip ACRC tonight."';
  else if (!isDay)           tip = '"Night is peak repair — apply ARC then ACRC before sleep."';

  const steps = ['1. Cleanse','2. Tone','3. ARC Serum','4. ACRC Cream'];
  return { cond, icon, tip, steps, temp:Math.round(temp) };
}

/* ═══════════════════════════════════════════════════
   ANIMATED PARTICLE BACKGROUND
═══════════════════════════════════════════════════ */
function AnimatedBg({ phase }) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    const palettes = {
      morning:   ['#F0D98A','#E8967A','#C4788A'],
      afternoon: ['#C9A227','#F0D98A','#E8E0D8'],
      evening:   ['#C4788A','#C9A227','#E4D0DC'],
      night:     ['#C9A227','#8A6010','#2D1A30'],
    };
    const cols = palettes[phase] || palettes.evening;

    const particles = Array.from({length:18}, (_,i) => ({
      x: Math.random()*canvas.width,
      y: Math.random()*canvas.height,
      r: Math.random()*3+1,
      dx: (Math.random()-0.5)*0.4,
      dy: (Math.random()-0.5)*0.4,
      color: cols[i%cols.length],
      opacity: Math.random()*0.3+0.05,
      pulse: Math.random()*Math.PI*2,
    }));

    const draw = () => {
      ctx.clearRect(0,0,canvas.width,canvas.height);
      particles.forEach(p => {
        p.pulse += 0.018;
        const alpha = p.opacity*(0.6+0.4*Math.sin(p.pulse));
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r*(0.8+0.4*Math.sin(p.pulse)), 0, Math.PI*2);
        ctx.fillStyle = p.color + Math.round(alpha*255).toString(16).padStart(2,'0');
        ctx.fill();
        p.x += p.dx; p.y += p.dy;
        if (p.x<0||p.x>canvas.width)  p.dx *= -1;
        if (p.y<0||p.y>canvas.height) p.dy *= -1;
      });
      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animRef.current);
  }, [phase]);

  return <canvas ref={canvasRef} style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none',opacity:0.6}}/>;
}

/* ═══════════════════════════════════════════════════
   STATUS BAR
═══════════════════════════════════════════════════ */
function StatusBar({ time }) {
  const [batt,setBatt] = useState(74);
  useEffect(() => {
    if (navigator.getBattery) navigator.getBattery().then(b => setBatt(Math.round(b.level*100)));
  },[]);
  const ts = time.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',hour12:true}).toLowerCase();
  return (
    <div style={{background:'#111',padding:'6px 14px',display:'flex',justifyContent:'space-between',alignItems:'center',flexShrink:0,zIndex:10}}>
      <span style={{fontSize:11,fontWeight:700,color:'#FFF'}}>{ts}</span>
      <span style={{fontSize:10,fontWeight:700,color:C.rose,letterSpacing:'0.22em'}}>REROOT'S</span>
      <div style={{display:'flex',gap:5,alignItems:'center'}}>
        <span style={{fontSize:8,color:'#AAA',fontWeight:600}}>4G</span>
        <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
          {[0,3,6,9].map((x,i) => <rect key={i} x={x} y={10-(i+1)*2.2} width="2" height={(i+1)*2.2} rx="0.5" fill={i<3?'#AAA':'#555'}/>)}
        </svg>
        <div style={{width:22,height:11,border:'1.5px solid #666',borderRadius:2,padding:'1.5px',display:'flex',alignItems:'center',position:'relative'}}>
          <div style={{position:'absolute',right:-3,top:'50%',transform:'translateY(-50%)',width:2,height:5,background:'#666',borderRadius:'0 1px 1px 0'}}/>
          <div style={{height:'100%',width:`${batt}%`,background:batt>30?'#C9A227':'#F44336',borderRadius:1}}/>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   SECONDARY NAV — WORKING with router
═══════════════════════════════════════════════════ */
function SecNav({ active, setActive, setTab }) {
  const items = [
    { label:'Home',        action:() => { setActive('Home'); setTab('home'); }},
    { label:'The System',  action:() => { setActive('The System'); setTab('shop'); }},
    { label:'The Science', action:() => { setActive('The Science'); setTab('science'); }},
    { label:'My Vault',    action:() => { setActive('My Vault'); setTab('profile'); }},
  ];
  return (
    <div style={{background:C.card,borderBottom:`1px solid ${C.border}`,padding:'8px 10px',display:'flex',gap:4,flexShrink:0,zIndex:10,overflowX:'auto',scrollbarWidth:'none'}}>
      {items.map(item => (
        <div key={item.label} onClick={item.action} style={{
          padding:'7px 13px', borderRadius:20, cursor:'pointer', whiteSpace:'nowrap', flexShrink:0,
          transition:'all 0.2s',
          background: active===item.label ? C.rose : 'transparent',
          color:       active===item.label ? '#FFF' : C.sub,
          fontSize:12, fontWeight: active===item.label ? 700 : 400,
          border:`1px solid ${active===item.label ? C.rose : 'transparent'}`,
        }}>
          {item.label}{item.label==='The System' ? ' ▾' : ''}
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   BOTTOM NAV — FULL WIDTH, ALL 6 TABS VISIBLE
═══════════════════════════════════════════════════ */
function BottomNav({ tab, setTab, setSecActive }) {
  const tabs = [
    { id:'home',    label:'HOME',    emoji:'🏠' },
    { id:'shop',    label:'SHOP',    emoji:'🛍️' },
    { id:'orders',  label:'ORDERS',  emoji:'📦' },
    { id:'loyalty', label:'LOYALTY', emoji:'⭐' },
    { id:'advisor', label:'ADVISOR', emoji:'💬' },
    { id:'profile', label:'PROFILE', emoji:'👤' },
  ];
  const navMap = { home:'Home', shop:'The System', science:'The Science', profile:'My Vault' };
  return (
    <div style={{background:C.navBg,flexShrink:0,zIndex:10}}>
      <div style={{fontSize:8,color:C.gold,textAlign:'center',padding:'3px 0 2px',letterSpacing:'0.12em',borderBottom:'1px solid #2A2A2A',fontWeight:600}}>
        ✦ Batch Tracking · Reserve Your Spot
      </div>
      {/* ALL 6 TABS — equal width using flex */}
      <div style={{display:'flex',width:'100%'}}>
        {tabs.map(t => (
          <div key={t.id} onClick={() => { setTab(t.id); if(navMap[t.id]) setSecActive(navMap[t.id]); }} style={{
            flex:'1 1 0', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
            gap:2, cursor:'pointer', padding:'7px 0 8px', minWidth:0,
          }}>
            <span style={{fontSize:16, lineHeight:1, filter: tab===t.id ? 'none' : 'grayscale(1) opacity(0.4)'}}>{t.emoji}</span>
            <span style={{fontSize:7.5, fontWeight:700, letterSpacing:'0.04em', color: tab===t.id ? C.rose : '#555', whiteSpace:'nowrap'}}>{t.label}</span>
            {tab===t.id && <div style={{width:12,height:2,background:C.rose,borderRadius:1,marginTop:1}}/>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   PRODUCT CARD — shows real image if available
═══════════════════════════════════════════════════ */
function ProductCard({ p, compact=false }) {
  const [imgErr, setImgErr] = useState(false);
  const h = compact ? 90 : 120;
  return (
    <div style={{background:C.card,borderRadius:14,overflow:'hidden',border:`1px solid rgba(196,120,138,0.2)`,boxShadow:'0 2px 10px rgba(0,0,0,0.06)',cursor:'pointer',flexShrink:compact?0:undefined,minWidth:compact?130:undefined}}>
      <div style={{height:h,background:'linear-gradient(145deg,#14182E,#1E2848)',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',position:'relative',overflow:'hidden'}}>
        {p.image_url && !imgErr ? (
          <img src={p.image_url.startsWith('http') ? p.image_url : `https://reroots.ca${p.image_url}`}
            alt={p.name} onError={()=>setImgErr(true)}
            style={{width:'100%',height:'100%',objectFit:'cover',position:'absolute',inset:0}}/>
        ) : (
          <>
            <div style={{fontSize:8,color:'rgba(201,162,39,0.9)',letterSpacing:'0.2em',fontWeight:700,zIndex:1}}>AURA-GEN</div>
            <div style={{width:2,height:compact?20:28,background:'linear-gradient(180deg,rgba(201,162,39,0.8),transparent)',margin:'4px 0',zIndex:1}}/>
            <div style={{fontSize:7,color:'rgba(255,255,255,0.45)',letterSpacing:'0.08em',zIndex:1,textAlign:'center',padding:'0 8px'}}>{p.subtitle}</div>
          </>
        )}
      </div>
      <div style={{padding:compact?'8px 10px':'12px'}}>
        <div style={{fontSize:compact?11:12,fontWeight:700,color:C.text,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{p.name}</div>
        {!compact && <div style={{fontSize:10,color:C.sub,marginTop:2}}>{p.subtitle}</div>}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:compact?4:8}}>
          <div style={{fontSize:compact?11:13,fontWeight:700,color:C.gold}}>{p.price}</div>
          <div style={{background:C.rose,color:'#FFF',fontSize:9,padding:'3px 8px',borderRadius:20,fontWeight:700}}>Add</div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   HOME SCREEN
═══════════════════════════════════════════════════ */
function HomeScreen({ time, weather, routine, setRoutine, products, setTab }) {
  const h     = time.getHours();
  const theme = getDayTheme(h);
  const winfo = weather ? getWeatherInfo(weather.weather_code, weather.temperature_2m, weather.relative_humidity_2m, h) : null;

  return (
    <div style={{padding:'12px',paddingBottom:16}}>

      {/* Branding Card */}
      <div style={{background:C.card,borderRadius:16,padding:'14px 18px',display:'flex',alignItems:'center',gap:14,boxShadow:'0 2px 16px rgba(0,0,0,0.07)',border:`1px solid ${C.border}`,marginBottom:12}}>
        <RerootsLogo size={54} bg={C.card}/>
        <div>
          <div style={{fontFamily:'"Georgia",serif',fontSize:21,fontWeight:700,letterSpacing:'0.18em',color:C.rose,lineHeight:1}}>REROOT'S</div>
          <div style={{fontSize:8.5,letterSpacing:'0.3em',color:C.gold,marginTop:5,fontWeight:700}}>BEAUTY ENHANCER</div>
        </div>
      </div>

      {/* Day/Night Banner */}
      <div style={{background:theme.bgGrad,borderRadius:16,padding:'16px 18px',marginBottom:12,border:`1px solid ${C.border}`,position:'relative',overflow:'hidden',minHeight:110}}>
        <AnimatedBg phase={theme.phase}/>
        <div style={{position:'relative',zIndex:1,display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
          <div>
            <div style={{fontSize:9,letterSpacing:'0.2em',color:theme.accent,fontWeight:700,marginBottom:4}}>
              {theme.emoji} {theme.label}
            </div>
            <div style={{fontSize:24,fontWeight:700,color:theme.dark?'#FFF':C.text,fontFamily:'"Georgia",serif',lineHeight:1.1}}>
              {theme.greeting}
            </div>
            <div style={{fontSize:11,color:theme.dark?'rgba(255,255,255,0.5)':C.sub,marginTop:4}}>
              Welcome to REROOT'S
            </div>
          </div>
          {/* Ghost logo in corner */}
          <div style={{opacity:0.08}}>
            <RerootsLogo size={70} bg={theme.dark?'#FFF':C.text}/>
          </div>
        </div>
      </div>

      {/* Weather · Skin Routine Card */}
      <div style={{background:C.card,borderRadius:16,padding:'14px 16px',marginBottom:12,border:`1px solid ${C.border}`,boxShadow:'0 2px 10px rgba(0,0,0,0.04)'}}>
        <div style={{fontSize:9,letterSpacing:'0.18em',color:C.sub,fontWeight:700,marginBottom:8}}>WEATHER · SKIN ROUTINE</div>
        {winfo ? (
          <>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
              <div>
                <div style={{fontSize:17,fontWeight:700,color:C.text}}>{winfo.icon} {winfo.cond} · {winfo.temp}°C</div>
                <div style={{fontSize:11,color:C.sub,marginTop:5,fontStyle:'italic',lineHeight:1.5}}>{winfo.tip}</div>
              </div>
              <div style={{width:44,height:44,background:'rgba(240,217,138,0.12)',borderRadius:12,display:'flex',alignItems:'center',justifyContent:'center',fontSize:26,flexShrink:0,border:`1px solid ${C.border}`}}>
                {winfo.icon}
              </div>
            </div>
            <div style={{display:'flex',gap:6,marginTop:12,flexWrap:'wrap'}}>
              {winfo.steps.map(s => (
                <div key={s} style={{padding:'5px 11px',borderRadius:20,border:`1px solid ${C.gold}`,fontSize:10,color:C.gold,fontWeight:600}}>{s}</div>
              ))}
            </div>
          </>
        ) : (
          <div style={{fontSize:11,color:C.sub,fontStyle:'italic'}}>📍 Allow location for live weather-based skin advice...</div>
        )}
      </div>

      {/* Feature Cards */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:12}}>
        {[
          { label:'AI Consultant', Icon:AIIcon, sub:'Personalized advice', t:'advisor' },
          { label:'Skin Vault',    Icon:VaultIcon, sub:'Your skin journal', t:'profile' },
        ].map(({ label, Icon, sub, t }) => (
          <div key={label} onClick={() => setTab(t)} style={{background:C.card,borderRadius:16,padding:'20px 10px',textAlign:'center',border:`1px solid ${C.border}`,borderBottom:`2px solid rgba(196,120,138,0.28)`,boxShadow:'0 2px 10px rgba(0,0,0,0.04)',cursor:'pointer',transition:'transform 0.15s'}}
            onMouseDown={e=>e.currentTarget.style.transform='scale(0.97)'}
            onMouseUp={e=>e.currentTarget.style.transform='scale(1)'}
          >
            <Icon size={52}/>
            <div style={{fontSize:13,fontWeight:700,color:C.text,marginTop:12}}>{label}</div>
            <div style={{fontSize:9.5,color:C.sub,marginTop:3}}>{sub}</div>
          </div>
        ))}
      </div>

      {/* Today's Routine */}
      <div style={{background:C.card,borderRadius:16,padding:'14px 16px',marginBottom:12,border:`1px solid ${C.border}`}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14}}>
          <div style={{fontSize:15,fontWeight:700,color:C.text}}>Today's Routine</div>
          <div style={{fontSize:11,fontWeight:700,color:C.gold}}>{routine.length}/4 done</div>
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
          {['Cleanse','Tone','Serum','Moisturize'].map(step => {
            const done = routine.includes(step);
            return (
              <div key={step} onClick={() => setRoutine(p => done ? p.filter(s=>s!==step) : [...p,step])}
                style={{display:'flex',alignItems:'center',gap:9,cursor:'pointer',padding:'4px 0'}}>
                <div style={{width:26,height:26,borderRadius:'50%',flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center',transition:'all 0.2s',background:done?C.rose:'transparent',border:`2px solid ${done?C.rose:'#CCC'}`}}>
                  {done && <span style={{color:'#FFF',fontSize:13,fontWeight:700,lineHeight:1}}>✓</span>}
                </div>
                <span style={{fontSize:13,color:done?C.text:C.sub,fontWeight:done?600:400}}>{step}</span>
              </div>
            );
          })}
        </div>
        <div style={{marginTop:14,height:4,background:'#F0EBE6',borderRadius:4,overflow:'hidden'}}>
          <div style={{height:'100%',width:`${(routine.length/4)*100}%`,background:`linear-gradient(90deg,${C.rose},${C.gold})`,borderRadius:4,transition:'width 0.4s ease'}}/>
        </div>
      </div>

      {/* Featured Products — from API */}
      <div>
        <div style={{fontSize:15,fontWeight:700,color:C.text,marginBottom:10}}>Featured Products</div>
        <div style={{display:'flex',gap:10,overflowX:'auto',paddingBottom:4,scrollbarWidth:'none'}}>
          {(products.length ? products : MOCK_PRODUCTS).map(p => (
            <ProductCard key={p.id} p={p} compact/>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   SHOP SCREEN (THE SYSTEM) — live products
═══════════════════════════════════════════════════ */
function ShopScreen({ products, setTab }) {
  const [filter, setFilter] = useState('all');
  const items = products.length ? products : MOCK_PRODUCTS;
  const cats  = ['all','serum','moisturizer','system'];
  const filtered = filter==='all' ? items : items.filter(p=>p.category===filter);

  return (
    <div style={{padding:'14px 12px',paddingBottom:16}}>
      <div style={{fontFamily:'"Georgia",serif',fontSize:18,fontWeight:700,color:C.text,marginBottom:2}}>The System</div>
      <div style={{fontSize:10,color:C.sub,marginBottom:14,letterSpacing:'0.05em'}}>AURA-GEN Collection · Live from reroots.ca</div>

      <div style={{display:'flex',gap:7,marginBottom:14,overflowX:'auto',scrollbarWidth:'none'}}>
        {cats.map(c => (
          <div key={c} onClick={()=>setFilter(c)} style={{padding:'5px 13px',borderRadius:20,cursor:'pointer',whiteSpace:'nowrap',flexShrink:0,fontSize:10,fontWeight:700,letterSpacing:'0.08em',textTransform:'uppercase',background:filter===c?C.rose:C.card,color:filter===c?'#FFF':C.sub,border:`1px solid ${filter===c?C.rose:C.border}`,transition:'all 0.2s'}}>{c}</div>
        ))}
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:14}}>
        {filtered.map(p => <ProductCard key={p.id} p={p}/>)}
      </div>

      {/* Combo Highlight */}
      <div style={{background:'linear-gradient(135deg,#14182E,#2A1F38)',borderRadius:16,padding:'18px',border:`1px solid rgba(201,162,39,0.3)`,position:'relative',overflow:'hidden'}}>
        <div style={{position:'absolute',right:-20,top:-20,opacity:0.06}}><RerootsLogo size={100} bg="#FFF"/></div>
        <div style={{fontSize:9,color:C.goldL,letterSpacing:'0.22em',fontWeight:700,marginBottom:4}}>BEST VALUE · COMPLETE SYSTEM</div>
        <div style={{fontFamily:'"Georgia",serif',fontSize:16,fontWeight:700,color:'#FFF',marginBottom:3}}>AURA-GEN PM System</div>
        <div style={{fontSize:10,color:'rgba(255,255,255,0.5)',marginBottom:14}}>ACRC Rich Cream 35mL + ARC Serum 30mL</div>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div>
            <div style={{fontSize:9,color:'rgba(255,255,255,0.3)',textDecoration:'line-through'}}>$178 CAD</div>
            <div style={{fontSize:22,fontWeight:700,color:C.gold}}>$149 CAD</div>
          </div>
          <div onClick={() => setTab && setTab('shop')} style={{background:`linear-gradient(135deg,${C.goldL},${C.gold})`,color:'#111',padding:'9px 18px',borderRadius:24,fontSize:11,fontWeight:700,cursor:'pointer'}}>Shop Now</div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   THE SCIENCE SCREEN
═══════════════════════════════════════════════════ */
function ScienceScreen() {
  const ingredients = [
    { name:'HPR (Hydroxypinacolone Retinoate)', pct:'2%', benefit:'Next-gen retinoid — cell turnover without irritation', product:'ACRC' },
    { name:'AHA Complex', pct:'8%', benefit:'Exfoliates + brightens, boosts penetration', product:'ACRC' },
    { name:'Peptide Blend', pct:'5%', benefit:'Collagen synthesis + firmness', product:'ACRC' },
    { name:'Niacinamide', pct:'5%', benefit:'Pore refinement + barrier strengthening', product:'ARC' },
    { name:'Hyaluronic Acid', pct:'2%', benefit:'Multi-weight hydration (3 molecular weights)', product:'ARC' },
    { name:'Vitamin C (Stable)', pct:'10%', benefit:'Brightening + antioxidant protection', product:'ARC' },
    { name:'PDRN', pct:'1%', benefit:'DNA repair + regeneration activator', product:'ARC' },
  ];

  return (
    <div style={{padding:'14px 12px',paddingBottom:16}}>
      <div style={{fontFamily:'"Georgia",serif',fontSize:18,fontWeight:700,color:C.text,marginBottom:2}}>The Science</div>
      <div style={{fontSize:10,color:C.sub,marginBottom:16,letterSpacing:'0.05em'}}>Clinical-grade formulation · Grade A rated</div>

      {/* Score card */}
      <div style={{background:'linear-gradient(135deg,#14182E,#2A1F38)',borderRadius:16,padding:'18px',marginBottom:14,border:`1px solid rgba(201,162,39,0.3)`}}>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
          {[{label:'Combo Score',val:'92/100',sub:'18 skin concerns'},{label:'Formula Grade',val:'A',sub:'Clinical review'},{label:'Active Ingredients',val:'11',sub:'Clinically dosed'},{label:'Skin Concerns',val:'18',sub:'Addressed by PM system'}].map(s=>(
            <div key={s.label} style={{textAlign:'center',padding:'12px',background:'rgba(255,255,255,0.06)',borderRadius:12}}>
              <div style={{fontSize:22,fontWeight:700,color:C.gold,fontFamily:'"Georgia",serif'}}>{s.val}</div>
              <div style={{fontSize:10,color:'rgba(255,255,255,0.7)',marginTop:3,fontWeight:600}}>{s.label}</div>
              <div style={{fontSize:9,color:'rgba(255,255,255,0.35)',marginTop:1}}>{s.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Ingredients */}
      <div style={{background:C.card,borderRadius:16,padding:'14px',border:`1px solid ${C.border}`}}>
        <div style={{fontSize:13,fontWeight:700,color:C.text,marginBottom:14}}>Key Active Ingredients</div>
        {ingredients.map((ing,i) => (
          <div key={ing.name} style={{padding:'10px 0',borderBottom:i<ingredients.length-1?`1px solid ${C.border}`:'none',display:'flex',gap:12,alignItems:'flex-start'}}>
            <div style={{background:`${ing.product==='ACRC'?C.rose:C.gold}18`,border:`1px solid ${ing.product==='ACRC'?C.rose:C.gold}`,borderRadius:8,padding:'3px 7px',flexShrink:0}}>
              <div style={{fontSize:9,fontWeight:700,color:ing.product==='ACRC'?C.rose:C.gold}}>{ing.product}</div>
            </div>
            <div style={{flex:1}}>
              <div style={{fontSize:11,fontWeight:700,color:C.text}}>{ing.name} <span style={{color:C.gold}}>{ing.pct}</span></div>
              <div style={{fontSize:10,color:C.sub,marginTop:2}}>{ing.benefit}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   ORDERS SCREEN
═══════════════════════════════════════════════════ */
function OrdersScreen() {
  const sc = { Delivered:'#2E7D32', Processing:'#C9A227', Shipped:'#1565C0' };
  return (
    <div style={{padding:'14px 12px',paddingBottom:16}}>
      <div style={{fontFamily:'"Georgia",serif',fontSize:18,fontWeight:700,color:C.text,marginBottom:2}}>My Orders</div>
      <div style={{fontSize:10,color:C.sub,marginBottom:18}}>Track your AURA-GEN deliveries · reroots.ca</div>
      {MOCK_ORDERS.map(o => (
        <div key={o.id} style={{background:C.card,borderRadius:16,padding:'14px',marginBottom:10,border:`1px solid ${C.border}`,boxShadow:'0 2px 8px rgba(0,0,0,0.04)'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
            <div>
              <div style={{fontSize:12,fontWeight:700,color:C.text}}>{o.id}</div>
              <div style={{fontSize:11,color:C.sub,marginTop:2}}>{o.item}</div>
              <div style={{fontSize:10,color:C.sub,marginTop:2}}>{o.date}</div>
            </div>
            <div style={{background:sc[o.status]+'20',color:sc[o.status],padding:'4px 10px',borderRadius:20,fontSize:9.5,fontWeight:700}}>{o.status}</div>
          </div>
          <div style={{borderTop:`1px solid ${C.border}`,marginTop:12,paddingTop:12,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <span style={{fontSize:11,color:C.sub}}>Order Total</span>
            <span style={{fontSize:14,fontWeight:700,color:C.gold}}>{o.total}</span>
          </div>
        </div>
      ))}
      <div style={{background:`linear-gradient(135deg,rgba(196,120,138,0.08),rgba(201,162,39,0.06))`,borderRadius:16,padding:'18px',border:`1px solid rgba(196,120,138,0.2)`,textAlign:'center',cursor:'pointer'}}>
        <div style={{fontSize:9.5,color:C.rose,fontWeight:700,letterSpacing:'0.14em'}}>✦ BATCH TRACKING</div>
        <div style={{fontSize:14,fontWeight:700,color:C.text,marginTop:5}}>Reserve Your Spot</div>
        <div style={{fontSize:11,color:C.sub,marginTop:3}}>Join the AURA-GEN launch waitlist</div>
        <div style={{background:C.rose,color:'#FFF',padding:'9px 22px',borderRadius:24,fontSize:11,fontWeight:700,display:'inline-block',marginTop:12}}>Reserve Now →</div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   LOYALTY SCREEN
═══════════════════════════════════════════════════ */
function LoyaltyScreen() {
  const pts   = 350;
  const tiers = [
    { name:'Bronze',   min:0,    color:'#CD7F32', icon:'🥉', perk:'Early access' },
    { name:'Silver',   min:250,  color:'#A8A9AD', icon:'🥈', perk:'5% off + early access' },
    { name:'Gold',     min:500,  color:'#C9A227', icon:'🥇', perk:'10% off + free shipping' },
    { name:'Platinum', min:1000, color:'#E5E4E2', icon:'💎', perk:'15% off + VIP concierge' },
  ];
  const cur  = [...tiers].reverse().find(t=>pts>=t.min) || tiers[0];
  const nxt  = tiers[tiers.indexOf(cur)+1];
  const pct  = nxt ? Math.min(100,((pts-cur.min)/(nxt.min-cur.min))*100) : 100;

  return (
    <div style={{padding:'14px 12px',paddingBottom:16}}>
      <div style={{fontFamily:'"Georgia",serif',fontSize:18,fontWeight:700,color:C.text,marginBottom:16}}>Loyalty Rewards</div>
      <div style={{background:'linear-gradient(135deg,#1A1428,#2D1A30)',borderRadius:20,padding:'22px 18px',marginBottom:14,border:`1px solid rgba(201,162,39,0.3)`,boxShadow:'0 8px 30px rgba(0,0,0,0.2)',position:'relative',overflow:'hidden'}}>
        <div style={{position:'absolute',right:-20,bottom:-20,opacity:0.06}}><RerootsLogo size={120} bg="#FFF"/></div>
        <div style={{fontSize:9,color:C.goldL,letterSpacing:'0.3em',marginBottom:6,fontWeight:700}}>ROOTS POINTS</div>
        <div style={{fontSize:56,fontWeight:700,color:'#FFF',lineHeight:1,fontFamily:'"Georgia",serif'}}>{pts}</div>
        <div style={{fontSize:10,color:'rgba(255,255,255,0.4)',marginTop:3}}>Available Points</div>
        <div style={{marginTop:18,padding:'14px',background:'rgba(255,255,255,0.05)',borderRadius:14}}>
          <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
            <div style={{fontSize:11,color:'rgba(255,255,255,0.7)',fontWeight:600}}>{cur.name} Member</div>
            {nxt&&<div style={{fontSize:10,color:C.goldL}}>{nxt.min-pts} pts to {nxt.name}</div>}
          </div>
          <div style={{height:5,background:'rgba(255,255,255,0.1)',borderRadius:3,overflow:'hidden'}}>
            <div style={{height:'100%',width:`${pct}%`,background:`linear-gradient(90deg,${cur.color},${C.goldL})`,borderRadius:3,transition:'width 0.6s'}}/>
          </div>
        </div>
      </div>
      <div style={{background:C.card,borderRadius:16,padding:'14px',border:`1px solid ${C.border}`}}>
        <div style={{fontSize:13,fontWeight:700,color:C.text,marginBottom:12}}>Tier Benefits</div>
        {tiers.map((t,i) => (
          <div key={t.name} style={{display:'flex',alignItems:'center',gap:12,padding:'10px 0',borderBottom:i<3?`1px solid ${C.border}`:'none',opacity:pts<t.min?0.4:1}}>
            <div style={{width:38,height:38,borderRadius:'50%',background:t.color+'18',border:`2px solid ${t.color}`,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,fontSize:18}}>{t.icon}</div>
            <div style={{flex:1}}>
              <div style={{fontSize:12,fontWeight:700,color:t.color}}>{t.name}</div>
              <div style={{fontSize:10,color:C.sub}}>{t.min}+ pts · {t.perk}</div>
            </div>
            {pts>=t.min&&<div style={{color:C.rose,fontSize:16,fontWeight:700}}>✓</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   AI ADVISOR SCREEN — Claude-powered, English only
═══════════════════════════════════════════════════ */
const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const SYSTEM_PROMPT = `You are the REROOT'S AI skincare advisor for reroots.ca. ABSOLUTE RULE: Respond in ENGLISH ONLY. No exceptions. If user writes in any other language, still reply in English only.

AURA-GEN PM System (sold only as combo, $149 CAD):
- ACRC Rich Cream 35mL airless pump: HPR 2%, AHA 8%, peptides 5%, glycerin, ceramides. Retinoid — requires sun-sensitivity warning.
- ARC Active Recovery Serum 30mL airless pump: Niacinamide 5%, HA 2%, Vitamin C 10%, PDRN 1%.
- Use 1 pump each, nightly only, after cleanse and tone.
- AHA in ACRC = advise SPF in AM.

Be warm, precise, 2-3 sentences max. Never recommend competitor products.`;

function AdvisorScreen() {
  const [msgs,    setMsgs]    = useState([{ role:'assistant', content:"Hi! I'm your REROOT'S AI skincare advisor. Ask me anything about your skin, the AURA-GEN system, or your PM routine." }]);
  const [input,   setInput]   = useState('');
  const [loading, setLoading] = useState(false);
  const [dotIdx,  setDotIdx]  = useState(0);
  const endRef = useRef(null);
  const SUGG   = ['Best routine for dry skin','How to layer ACRC + ARC','When will I see results?','Is it safe during pregnancy?'];

  useEffect(() => { if(loading) { const t=setInterval(()=>setDotIdx(d=>(d+1)%3),420); return ()=>clearInterval(t); } },[loading]);
  useEffect(() => { endRef.current?.scrollIntoView({behavior:'smooth'}); },[msgs,loading]);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const updated = [...msgs, { role:'user', content:text }];
    setMsgs(updated); setInput(''); setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/ai/chat`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ 
          message: text,
          system_prompt: SYSTEM_PROMPT,
          history: updated.slice(0, -1).map(m=>({role:m.role,content:m.content}))
        })
      });
      const data = await res.json();
      setMsgs(p => [...p, { role:'assistant', content: data.response || data.content?.[0]?.text || "I'm having a moment — please try again!" }]);
    } catch {
      setMsgs(p => [...p, { role:'assistant', content:"Connection issue. Please check your network and try again." }]);
    }
    setLoading(false);
  },[msgs,loading]);

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100%',minHeight:0}}>
      {/* Header */}
      <div style={{padding:'10px 14px',background:C.card,borderBottom:`1px solid ${C.border}`,display:'flex',alignItems:'center',gap:12,flexShrink:0}}>
        <div style={{width:40,height:40,borderRadius:'50%',background:'linear-gradient(135deg,#14182E,#1E2848)',display:'flex',alignItems:'center',justifyContent:'center',border:`2px solid rgba(201,162,39,0.4)`,flexShrink:0}}>
          <RerootsLogo size={26} bg="#14182E"/>
        </div>
        <div style={{flex:1}}>
          <div style={{fontSize:13,fontWeight:700,color:C.text}}>Reroots AI</div>
          <div style={{fontSize:9.5,color:C.sub}}>Skincare Advisor · English Only</div>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:4}}>
          <div style={{width:7,height:7,borderRadius:'50%',background:'#4CAF50'}}/>
          <span style={{fontSize:9.5,color:'#4CAF50',fontWeight:600}}>Online</span>
        </div>
      </div>
      {/* Messages */}
      <div style={{flex:1,overflowY:'auto',padding:'12px',display:'flex',flexDirection:'column',gap:10,scrollbarWidth:'none'}}>
        {msgs.map((m,i) => (
          <div key={i} style={{display:'flex',justifyContent:m.role==='user'?'flex-end':'flex-start'}}>
            <div style={{maxWidth:'84%',padding:'10px 14px',borderRadius:m.role==='user'?'18px 18px 4px 18px':'18px 18px 18px 4px',background:m.role==='user'?`linear-gradient(135deg,${C.rose},#B0607A)`:C.card,color:m.role==='user'?'#FFF':C.text,fontSize:12,lineHeight:1.6,border:m.role==='assistant'?`1px solid ${C.border}`:'none',boxShadow:'0 2px 8px rgba(0,0,0,0.06)'}}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{display:'flex'}}>
            <div style={{padding:'12px 16px',background:C.card,borderRadius:'18px 18px 18px 4px',border:`1px solid ${C.border}`,display:'flex',gap:5,alignItems:'center'}}>
              {[0,1,2].map(i => <div key={i} style={{width:7,height:7,borderRadius:'50%',background:C.gold,opacity:dotIdx===i?1:0.2,transition:'opacity 0.2s'}}/>)}
            </div>
          </div>
        )}
        <div ref={endRef}/>
      </div>
      {/* Suggestion chips */}
      {msgs.length <= 2 && (
        <div style={{padding:'0 12px 8px',display:'flex',gap:6,overflowX:'auto',flexShrink:0,scrollbarWidth:'none'}}>
          {SUGG.map(s => <div key={s} onClick={()=>send(s)} style={{padding:'6px 12px',background:C.card,border:`1px solid ${C.border}`,borderRadius:20,fontSize:10,color:C.text,cursor:'pointer',whiteSpace:'nowrap',flexShrink:0,fontWeight:500}}>{s}</div>)}
        </div>
      )}
      {/* Input */}
      <div style={{padding:'10px 12px',background:C.card,borderTop:`1px solid ${C.border}`,display:'flex',gap:8,alignItems:'center',flexShrink:0}}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send(input)}
          placeholder="Ask about your skin..."
          style={{flex:1,padding:'10px 14px',borderRadius:24,border:`1px solid ${C.border}`,background:C.bg,fontSize:12,color:C.text,outline:'none',fontFamily:'inherit'}}/>
        <div onClick={()=>send(input)} style={{width:40,height:40,borderRadius:'50%',background:loading?'#CCC':`linear-gradient(135deg,${C.rose},#B0607A)`,display:'flex',alignItems:'center',justifyContent:'center',cursor:loading?'default':'pointer',color:'#FFF',fontSize:18,flexShrink:0,boxShadow:loading?'none':`0 4px 14px rgba(196,120,138,0.45)`}}>↑</div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   PROFILE / BIOMETRIC SCREEN
═══════════════════════════════════════════════════ */
function ProfileScreen({ biometric, setBiometric }) {
  const [bioStatus, setBioStatus] = useState('idle');
  const [pinMode,   setPinMode]   = useState(false);
  const [pin,       setPin]       = useState('');
  const [pinSaved,  setPinSaved]  = useState(false);

  const enableBio = async () => {
    if (!window.PublicKeyCredential) { setBioStatus('unavailable'); return; }
    setBioStatus('requesting');
    try {
      const ch = new Uint8Array(32); window.crypto.getRandomValues(ch);
      const cred = await navigator.credentials.create({ publicKey: {
        challenge:ch, rp:{name:"REROOT'S",id:window.location.hostname},
        user:{id:new Uint8Array(16),name:'user@reroots.ca',displayName:"REROOT'S User"},
        pubKeyCredParams:[{alg:-7,type:'public-key'}],
        authenticatorSelection:{authenticatorAttachment:'platform',userVerification:'required'},
        timeout:30000,
      }});
      if (cred) { setBiometric(true); setBioStatus('success'); }
    } catch(e) { setBioStatus(e.name==='NotAllowedError'?'denied':'unavailable'); }
  };

  const settings = [
    { icon:'🔔', label:'Notifications',    sub:'Routine reminders & order alerts' },
    { icon:'🌍', label:'Language',         sub:'English (EN) — Always enforced' },
    { icon:'📦', label:'Shipping Address', sub:'Mississauga, ON L4T 3L6' },
    { icon:'💳', label:'Payment Methods',  sub:'Manage payment options' },
    { icon:'📋', label:'CNF Compliance',   sub:'Health Canada — 2 CNFs pending' },
    { icon:'🔒', label:'Privacy Policy',   sub:'AES-256 · Data never shared' },
  ];

  return (
    <div style={{padding:'14px 12px',paddingBottom:16}}>
      {/* Avatar */}
      <div style={{background:'linear-gradient(135deg,#1A1428,#2D1A30)',borderRadius:20,padding:'22px 18px',marginBottom:14,display:'flex',alignItems:'center',gap:16,border:`1px solid rgba(201,162,39,0.25)`,position:'relative',overflow:'hidden'}}>
        <div style={{position:'absolute',right:-20,bottom:-20,opacity:0.07}}><RerootsLogo size={110} bg="#FFF"/></div>
        <div style={{width:58,height:58,borderRadius:'50%',background:`linear-gradient(135deg,${C.rose},#B0607A)`,display:'flex',alignItems:'center',justifyContent:'center',border:`3px solid rgba(201,162,39,0.45)`,fontSize:26,flexShrink:0}}>👤</div>
        <div>
          <div style={{fontSize:16,fontWeight:700,color:'#FFF'}}>Welcome, Tj</div>
          <div style={{fontSize:10,color:'rgba(255,255,255,0.4)',marginTop:2}}>Reroots Aesthetics Inc.</div>
          <div style={{fontSize:10,color:C.gold,marginTop:6,fontWeight:600,letterSpacing:'0.1em'}}>✦ SILVER TIER · 350 POINTS</div>
        </div>
      </div>

      {/* Biometric Gate */}
      <div style={{background:C.card,borderRadius:16,padding:'14px',marginBottom:10,border:`1px solid ${C.border}`}}>
        <div style={{fontSize:13,fontWeight:700,color:C.text,marginBottom:3}}>🔐 Biometric Security</div>
        <div style={{fontSize:10.5,color:C.sub,marginBottom:14,lineHeight:1.5}}>Protect your skin data and payment info with Face ID or fingerprint. AES-256 encrypted, on-device only.</div>

        {biometric || pinSaved ? (
          <div style={{background:'rgba(46,125,50,0.08)',borderRadius:12,padding:'14px',border:'1px solid rgba(46,125,50,0.25)',display:'flex',alignItems:'center',gap:12}}>
            <span style={{fontSize:28}}>✅</span>
            <div>
              <div style={{fontSize:12,fontWeight:700,color:'#2E7D32'}}>{biometric?'Biometric Enabled':'PIN Enabled'}</div>
              <div style={{fontSize:10,color:C.sub}}>AES-256 Encrypted · On-Device Only · Never Shared</div>
            </div>
          </div>
        ) : (
          <>
            <div onClick={enableBio} style={{background:`linear-gradient(135deg,${C.gold},${C.goldD})`,color:'#FFF',padding:'16px',borderRadius:14,textAlign:'center',cursor:bioStatus==='requesting'?'default':'pointer',marginBottom:8,boxShadow:`0 4px 16px rgba(201,162,39,0.35)`}}>
              <div style={{fontSize:34,marginBottom:6}}>{bioStatus==='requesting'?'⏳':'🪪'}</div>
              <div style={{fontSize:13,fontWeight:700}}>{bioStatus==='requesting'?'Verifying...':'Enable Biometric'}</div>
              <div style={{fontSize:10,marginTop:3,opacity:0.8}}>Face ID · Touch ID · Fingerprint</div>
            </div>
            {(bioStatus==='denied'||bioStatus==='unavailable') && (
              <>
                <div style={{fontSize:10.5,color:bioStatus==='denied'?'#C62828':C.sub,textAlign:'center',marginBottom:8}}>
                  {bioStatus==='denied'?'Permission denied — enable in device settings':'Not available on this browser'}
                </div>
                {!pinMode
                  ? <div onClick={()=>setPinMode(true)} style={{border:`1px solid ${C.border}`,borderRadius:12,padding:'11px',textAlign:'center',fontSize:12,color:C.rose,cursor:'pointer',fontWeight:700}}>Use PIN Instead</div>
                  : <>
                      <div style={{fontSize:10,color:C.sub,textAlign:'center',marginBottom:8}}>Enter a 6-digit PIN</div>
                      <input type="password" inputMode="numeric" maxLength={6} value={pin}
                        onChange={e=>{setPin(e.target.value);if(e.target.value.length===6){setPinSaved(true);setPinMode(false);}}}
                        placeholder="● ● ● ● ● ●"
                        style={{width:'100%',padding:'14px',borderRadius:12,border:`1.5px solid ${C.gold}`,fontSize:20,textAlign:'center',letterSpacing:'0.4em',outline:'none',background:C.bg,boxSizing:'border-box',color:C.text}}/>
                    </>
                }
              </>
            )}
            <div style={{marginTop:8,fontSize:9.5,color:C.sub,textAlign:'center'}}>🔒 AES-256 · On-Device Only · Never Shared</div>
          </>
        )}
      </div>

      {/* Settings */}
      {settings.map(s => (
        <div key={s.label} style={{background:C.card,borderRadius:14,padding:'13px 14px',marginBottom:7,border:`1px solid ${C.border}`,display:'flex',alignItems:'center',gap:12,cursor:'pointer'}}>
          <span style={{fontSize:20}}>{s.icon}</span>
          <div style={{flex:1}}>
            <div style={{fontSize:12,fontWeight:600,color:C.text}}>{s.label}</div>
            <div style={{fontSize:10,color:C.sub,marginTop:1}}>{s.sub}</div>
          </div>
          <span style={{color:C.sub,fontSize:16}}>›</span>
        </div>
      ))}
      <div style={{textAlign:'center',padding:'12px',fontSize:9.5,color:C.sub}}>
        REROOT'S PWA v12.0 · Reroots Aesthetics Inc.<br/>
        <span style={{color:C.gold}}>reroots.ca</span> · Admin via website only
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   FAB
═══════════════════════════════════════════════════ */
function FAB({ setTab, setSecActive }) {
  return (
    <div onClick={()=>{setTab('advisor');setSecActive('');}}
      style={{position:'absolute',bottom:76,right:12,width:50,height:50,borderRadius:'50%',background:'#FFF',boxShadow:`0 4px 22px rgba(201,162,39,0.55)`,display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',border:`1.5px solid rgba(201,162,39,0.35)`,zIndex:20,transition:'transform 0.15s'}}
      onMouseDown={e=>e.currentTarget.style.transform='scale(0.92)'}
      onMouseUp={e=>e.currentTarget.style.transform='scale(1)'}
    >
      <RerootsLogo size={34} bg="#FFF"/>
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   ROOT APP
═══════════════════════════════════════════════════ */
export default function RerootsPWA() {
  const [tab,       setTab]       = useState('home');
  const [secActive, setSecActive] = useState('Home');
  const [time,      setTime]      = useState(new Date());
  const [weather,   setWeather]   = useState(null);
  const [routine,   setRoutine]   = useState(['Cleanse','Tone']);
  const [products,  setProducts]  = useState([]);
  const [biometric, setBiometric] = useState(false);

  // Live clock
  useEffect(() => { const t=setInterval(()=>setTime(new Date()),1000); return ()=>clearInterval(t); },[]);

  // Weather — user location first, Mississauga fallback
  useEffect(() => {
    const fw = async (lat,lon) => {
      try {
        const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code,relative_humidity_2m&timezone=auto`);
        const d = await r.json();
        setWeather(d.current);
      } catch {}
    };
    navigator.geolocation?.getCurrentPosition(
      ({ coords }) => fw(coords.latitude, coords.longitude),
      () => fw(43.59, -79.64)
    );
  },[]);

  // Products — live from reroots.ca with fallback
  useEffect(() => {
    fetch('https://reroots.ca/api/products?brand=reroots&featured=true&limit=6', { signal: AbortSignal.timeout(5000) })
      .then(r => { if(!r.ok) throw new Error(); return r.json(); })
      .then(setProducts)
      .catch(() => setProducts(MOCK_PRODUCTS));
  },[]);

  const screens = {
    home:    <HomeScreen    time={time} weather={weather} routine={routine} setRoutine={setRoutine} products={products} setTab={setTab}/>,
    shop:    <ShopScreen    products={products} setTab={setTab}/>,
    science: <ScienceScreen/>,
    orders:  <OrdersScreen/>,
    loyalty: <LoyaltyScreen/>,
    advisor: <AdvisorScreen/>,
    profile: <ProfileScreen biometric={biometric} setBiometric={setBiometric}/>,
  };

  return (
    /* Outer wrapper — fills 100% viewport, centers the phone frame */
    <div style={{width:'100vw',height:'100vh',background:'linear-gradient(135deg,#C0B8B0,#A8A098)',display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden',fontFamily:'"Helvetica Neue",Helvetica,Arial,sans-serif'}}>

      {/* Phone frame — responsive: fills screen on small viewports, fixed 390×844 on large */}
      <div style={{
        width: 'min(390px, 100vw)',
        height: 'min(844px, 100vh)',
        borderRadius: 'clamp(0px, 4vw, 52px)',
        overflow:'hidden',
        boxShadow:'0 40px 120px rgba(0,0,0,0.5), 0 0 0 clamp(0px,1vw,10px) #111, 0 0 0 clamp(0px,1.2vw,12px) #2A2A2A',
        display:'flex', flexDirection:'column',
        position:'relative',
        background:C.bg,
      }}>
        <StatusBar time={time}/>
        <SecNav active={secActive} setActive={setSecActive} setTab={setTab}/>

        {/* Scrollable content */}
        <div style={{flex:1, overflowY: tab==='advisor' ? 'hidden':'auto', display:'flex', flexDirection:'column', minHeight:0, scrollbarWidth:'none'}}>
          {screens[tab] || screens.home}
        </div>

        {/* FAB — hidden on advisor */}
        {tab !== 'advisor' && <FAB setTab={setTab} setSecActive={setSecActive}/>}

        <BottomNav tab={tab} setTab={setTab} setSecActive={setSecActive}/>
      </div>
    </div>
  );
}
