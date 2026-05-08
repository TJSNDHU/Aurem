import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Rocket, Users, Zap, BarChart3, LayoutDashboard, Chrome, Shield, Settings,
  TrendingUp, ArrowRight, Search, Bell, UserCircle, Phone, Wifi, MessageCircle,
  FileText, Activity, ChevronRight
} from 'lucide-react';

/* ═══ Gold Network Background (animated) ═══ */
function GoldNetworkBg() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext('2d'); let a;
    const ns = [];
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize(); window.addEventListener('resize', resize);
    for (let i = 0; i < 40; i++) ns.push({ x: Math.random()*c.width, y: Math.random()*c.height, vx: (Math.random()-0.5)*0.2, vy: (Math.random()-0.5)*0.2, pulse: Math.random()*Math.PI*2 });
    const draw = (t) => {
      ctx.clearRect(0, 0, c.width, c.height);
      for (let i = 0; i < ns.length; i++) for (let j = i+1; j < ns.length; j++) {
        const dx = ns[i].x-ns[j].x, dy = ns[i].y-ns[j].y, d = Math.sqrt(dx*dx+dy*dy);
        if (d < 180) { ctx.beginPath(); ctx.moveTo(ns[i].x, ns[i].y); ctx.lineTo(ns[j].x, ns[j].y); ctx.strokeStyle = `rgba(180,160,80,${0.07*(1-d/180)})`; ctx.lineWidth = 0.5; ctx.stroke(); }
      }
      ns.forEach(n => {
        const pulse = 0.8 + Math.sin(t * 0.001 + n.pulse) * 0.5;
        ctx.beginPath(); ctx.arc(n.x, n.y, 1.2 * pulse, 0, Math.PI*2);
        ctx.fillStyle = `rgba(180,160,80,${0.08 + pulse * 0.06})`; ctx.fill();
        n.x += n.vx; n.y += n.vy;
        if(n.x<0||n.x>c.width) n.vx*=-1; if(n.y<0||n.y>c.height) n.vy*=-1;
      });
      a = requestAnimationFrame(draw);
    };
    a = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(a); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={ref} className="absolute inset-0 w-full h-full pointer-events-none" />;
}

/* ═══ DNA Helix Logo (animated) ═══ */
function DnaLogo() {
  return (
    <div className="relative mx-auto w-[48px] h-[52px]" style={{ animation: 'dnaFloat 4s ease-in-out infinite' }}>
      <svg width="48" height="52" viewBox="0 0 44 50" fill="none">
        <path d="M10 5 C18 12,26 12,34 5 C26 18,18 18,10 25 C18 32,26 32,34 25 C26 38,18 38,10 45" stroke="#D4B977" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
        <path d="M34 5 C26 12,18 12,10 5 C18 18,26 18,34 25 C26 32,18 32,10 25 C18 38,26 38,34 45" stroke="#E8C55A" strokeWidth="1.8" fill="none" strokeLinecap="round" opacity="0.5"/>
        <circle cx="10" cy="15" r="2.2" fill="#D4B977"><animate attributeName="r" values="2;2.8;2" dur="2s" repeatCount="indefinite"/></circle>
        <circle cx="34" cy="15" r="2.2" fill="#D4B977"><animate attributeName="r" values="2.2;1.6;2.2" dur="2s" repeatCount="indefinite" begin="0.5s"/></circle>
        <circle cx="10" cy="35" r="2.2" fill="#D4B977"><animate attributeName="r" values="2;2.8;2" dur="2s" repeatCount="indefinite" begin="1s"/></circle>
        <circle cx="34" cy="35" r="2.2" fill="#D4B977"><animate attributeName="r" values="2.2;1.6;2.2" dur="2s" repeatCount="indefinite" begin="1.5s"/></circle>
      </svg>
      <div className="absolute -inset-2 rounded-full" style={{ background: 'radial-gradient(circle, rgba(212,175,55,0.08) 0%, transparent 70%)', animation: 'pulse 3s ease-in-out infinite' }} />
    </div>
  );
}

/* ═══ Pulse Rings ═══ */
function PulseRings() {
  return (
    <div className="relative w-16 h-16 mx-auto mb-2">
      {[0, 0.6, 1.2].map((d, i) => (
        <div key={i} className="absolute rounded-full border animate-ping" style={{ inset: `${i*5}px`, borderColor: 'rgba(74,222,128,0.2)', animationDuration: '2.5s', animationDelay: `${d}s` }} />
      ))}
      <div className="absolute inset-[20px] rounded-full flex items-center justify-center" style={{ background: 'rgba(74,222,128,0.12)' }}>
        <div className="w-2.5 h-2.5 rounded-full bg-[#4ade80]" style={{ boxShadow: '0 0 12px rgba(74,222,128,0.7)', animation: 'pulse 1.5s ease-in-out infinite' }} />
      </div>
    </div>
  );
}

/* ═══ 3D Tilt Card ═══ */
function Card3D({ children, className = '', delay = 0, glowColor = 'rgba(255,107,0,0.1)' }) {
  const ref = useRef(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [vis, setVis] = useState(false);
  const [hover, setHover] = useState(false);

  useEffect(() => { const t = setTimeout(() => setVis(true), delay); return () => clearTimeout(t); }, [delay]);

  const onMove = useCallback((e) => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    setTilt({ x: y * -8, y: x * 8 });
  }, []);

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setTilt({ x: 0, y: 0 }); setHover(false); }}
      className={`rounded-2xl ${vis ? 'opacity-100' : 'opacity-0 translate-y-5'} ${className}`}
      style={{
        transform: `perspective(800px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) ${hover ? 'translateZ(8px) scale(1.01)' : 'translateZ(0)'}`,
        transition: 'transform 0.12s ease-out, opacity 0.6s ease-out, translate 0.6s ease-out, box-shadow 0.3s ease',
        background: 'linear-gradient(145deg, rgba(255,255,255,0.93) 0%, rgba(245,242,230,0.88) 100%)',
        border: '2px solid rgba(45,122,74,0.3)',
        boxShadow: hover
          ? `0 20px 40px rgba(0,0,0,0.08), 0 0 30px ${glowColor}, inset 0 1px 0 rgba(255,255,255,0.6)`
          : '0 2px 16px rgba(0,0,0,0.03), inset 0 1px 0 rgba(255,255,255,0.5)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
      }}
    >
      {children}
      {/* Shine overlay on hover */}
      {hover && <div className="absolute inset-0 rounded-2xl pointer-events-none overflow-hidden">
        <div style={{
          position: 'absolute', top: '-50%', left: '-50%', width: '200%', height: '200%',
          background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.15) 45%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0.15) 55%, transparent 60%)',
          transform: `rotate(${tilt.y * 3}deg)`,
          transition: 'transform 0.15s ease',
        }} /></div>}
    </div>
  );
}

/* ═══ Sparkline (animated draw) ═══ */
function Sparkline({ data, color = '#FF6B00' }) {
  const pts = data || [20,35,28,45,33,52,42,58,48,62];
  const mx = Math.max(...pts), h = 36, w = 110;
  const path = pts.map((v,i) => `${i===0?'M':'L'}${(i/(pts.length-1))*w},${h-(v/mx)*h}`).join(' ');
  const pathLen = 300;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-9">
      <defs>
        <linearGradient id="spkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25"/><stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={`${path} L${w},${h} L0,${h} Z`} fill="url(#spkFill)" style={{ animation: 'fadeIn 1s ease 0.3s both' }}/>
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ strokeDasharray: pathLen, strokeDashoffset: pathLen, animation: `drawLine 1.5s ease 0.2s forwards` }}/>
    </svg>
  );
}

/* ═══ Counter ═══ */
function Ctr({ end, prefix='', suffix='', delay=0 }) {
  const [v, setV] = useState(0);
  useEffect(() => { const t = setTimeout(() => { let s=0; const step=end/80; const iv=setInterval(()=>{ s+=step; if(s>=end){setV(end);clearInterval(iv);} else setV(Math.floor(s));},16); return ()=>clearInterval(iv); },delay); return ()=>clearTimeout(t); }, [end,delay]);
  return <span>{prefix}{typeof end==='number'&&end%1!==0?v.toFixed(1):v}{suffix}</span>;
}

/* ═══ Sentiment Gauge (animated needle) ═══ */
function SentimentGauge() {
  const [angle, setAngle] = useState(-90);
  useEffect(() => { const t = setTimeout(() => setAngle(35), 600); return () => clearTimeout(t); }, []);
  return (
    <div className="flex items-center gap-4">
      <div className="relative w-28 h-16">
        <svg viewBox="0 0 120 70" className="w-full h-full">
          <path d="M15,60 A45,45 0 0,1 105,60" fill="none" stroke="#ef4444" strokeWidth="8" strokeLinecap="round" opacity="0.3"/>
          <path d="M15,60 A45,45 0 0,1 60,15" fill="none" stroke="#f59e0b" strokeWidth="8" strokeLinecap="round" opacity="0.3"/>
          <path d="M60,15 A45,45 0 0,1 105,60" fill="none" stroke="#FF6B00" strokeWidth="8" strokeLinecap="round" opacity="0.5"/>
          <g style={{ transformOrigin: '60px 58px', transform: `rotate(${angle}deg)`, transition: 'transform 1.2s cubic-bezier(0.34,1.56,0.64,1)' }}>
            <line x1="60" y1="58" x2="60" y2="18" stroke="#8B4513" strokeWidth="2.5" strokeLinecap="round"/>
          </g>
          <circle cx="60" cy="58" r="5" fill="#8B4513"/>
          <circle cx="60" cy="58" r="2.5" fill="#D4B977"/>
        </svg>
      </div>
      <div className="space-y-1.5 text-[11px]">
        <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-[#FF6B00] shadow-[0_0_6px_rgba(45,122,74,0.4)]"/>Positive <span className="font-bold text-[#1A1A2E]">75%</span></div>
        <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-[#f59e0b] shadow-[0_0_6px_rgba(245,158,11,0.4)]"/>Neutral <span className="font-bold text-[#1A1A2E]">20%</span></div>
        <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-[#ef4444] shadow-[0_0_6px_rgba(239,68,68,0.4)]"/>Negative <span className="font-bold text-[#1A1A2E]">5%</span></div>
      </div>
    </div>
  );
}

/* ═══ Funnel Bars (animated) ═══ */
function FunnelBars({ items }) {
  const max = Math.max(...items.map(i => i.value));
  return (
    <div className="space-y-2.5">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-3">
          <div className="flex-1 h-7 rounded-lg overflow-hidden relative" style={{ background: 'rgba(255,107,0,0.05)' }}>
            <div className="h-full rounded-lg flex items-center justify-center relative overflow-hidden"
              style={{
                width: `${(item.value / max) * 100}%`,
                background: `linear-gradient(90deg, #FF6B00, ${i===0?'#3D9B5E':i===1?'#4AAD6A':i===2?'#C88B3A':'#1B5E3A'})`,
                animation: `growWidth 1s cubic-bezier(0.25,0.46,0.45,0.94) ${0.5+i*0.2}s both`,
                boxShadow: '0 2px 8px rgba(255,107,0,0.12)',
              }}>
              <span className="text-[10px] font-bold text-white relative z-10">{item.value}</span>
              {/* Shimmer */}
              <div className="absolute inset-0" style={{
                background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)',
                animation: `shimmer 2s ease-in-out ${1.5+i*0.3}s infinite`,
              }}/>
            </div>
          </div>
          <span className="text-[10px] text-[#1A1A2E] font-medium w-20">{item.suffix}</span>
        </div>
      ))}
    </div>
  );
}

/* ═══ Typing Log ═══ */
function TypingLog({ logs, startDelay = 500 }) {
  const [visCount, setVisCount] = useState(0);
  useEffect(() => {
    let i = 0;
    const t = setTimeout(() => {
      const iv = setInterval(() => { i++; setVisCount(i); if (i >= logs.length) clearInterval(iv); }, 400);
      return () => clearInterval(iv);
    }, startDelay);
    return () => clearTimeout(t);
  }, [logs.length, startDelay]);

  return (
    <div className="space-y-1.5 font-mono text-[10px]">
      {logs.map((log, i) => (
        <div key={i} className={`text-[#1A1A2E] leading-relaxed transition-all duration-300 ${i < visCount ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-3'}`}>
          <span className="text-[#999]">{log.substring(0, 10)}</span>{log.substring(10)}
        </div>
      ))}
      {visCount < logs.length && (
        <div className="flex gap-1 mt-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#FF6B00] animate-bounce" style={{ animationDelay: '0s' }}/>
          <span className="w-1.5 h-1.5 rounded-full bg-[#FF6B00] animate-bounce" style={{ animationDelay: '0.15s' }}/>
          <span className="w-1.5 h-1.5 rounded-full bg-[#FF6B00] animate-bounce" style={{ animationDelay: '0.3s' }}/>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════
   MAIN
═══════════════════════════════════════ */
export default function FuturisticDemo() {
  const [activeNav, setActiveNav] = useState('acquisition');
  const [time, setTime] = useState(new Date());
  useEffect(() => { const iv = setInterval(()=>setTime(new Date()), 1000); return ()=>clearInterval(iv); }, []);

  const SIM_LOGS = [
    '[10:46:12] SMS RECV: +1-416-555-0123. ROUTING TO: Customer A Panel',
    '[10:46:22] SMS SEND: +1-416-555-013 (Ollama/Llama 3.2):',
    '[11:15:02] VOICE CALL RECV: +1-416-555-0987. ROUTING TO: Customer A Voice Agent.',
    '[11:15:10] AI AGENT (AUREM DIY Voice/ElevenLabs via Emergent Router): Analyzing intent...',
    '[11:15:15] AI AGENT TALK: "Hi, thanks for calling Reroots Aesthetics."',
  ];

  return (
    <div className="min-h-screen flex relative" data-testid="futuristic-demo" style={{ background: 'transparent' }}>

      {/* ══ GREEN SIDEBAR ══ */}
      <div className="w-[220px] min-h-screen flex flex-col py-5 relative overflow-hidden" style={{
        background: 'linear-gradient(180deg, #2D6B45 0%, #1B5E3A 40%, #164D30 100%)',
        boxShadow: '4px 0 30px rgba(0,0,0,0.15)',
        borderRadius: '0 24px 24px 0',
      }}>
        {/* Sidebar ambient glow */}
        <div className="absolute top-0 right-0 w-24 h-full pointer-events-none" style={{
          background: 'linear-gradient(90deg, transparent, rgba(212,175,55,0.03))',
        }}/>

        <div className="text-center mb-8 px-4 relative z-10">
          <DnaLogo />
          <div className="text-[14px] font-bold tracking-[3px] text-white mt-2">
            AUREM <span className="text-[#D4B977]" style={{ textShadow: '0 0 12px rgba(212,175,55,0.3)' }}>AI</span>
          </div>
        </div>

        <div className="flex-1 px-3 space-y-0.5 relative z-10">
          {[
            { id: 'acquisition', icon: Rocket, label: 'ACQUISITION ENGINE' },
            { id: 'campaigns', icon: Users, label: 'CRM CAMPAIGNS' },
            { id: 'insights', icon: BarChart3, label: 'AUDIENCE INSIGHTS' },
            { id: 'voice', icon: Activity, label: 'VOICE AGENTS' },
            { id: 'docs', icon: FileText, label: 'DOCUMENT FLOW' },
            { id: 'settings', icon: Settings, label: 'SETTINGS' },
          ].map((item, idx) => (
            <button key={item.id} onClick={() => setActiveNav(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[10px] font-semibold tracking-[1px] transition-all duration-400 relative ${
                activeNav === item.id ? 'text-[#1B5E3A]' : 'text-white/70 hover:text-white'
              }`}
              style={{
                ...(activeNav === item.id ? {
                  background: 'linear-gradient(135deg, #A8D5A2 0%, #7EC87A 100%)',
                  boxShadow: '0 4px 15px rgba(126,200,122,0.35), inset 0 1px 0 rgba(255,255,255,0.3)',
                  transform: 'translateX(4px)',
                } : {}),
                animation: `sidebarSlideIn 0.4s ease ${idx * 0.06}s both`,
              }}>
              <item.icon className="w-4 h-4" />{item.label}
              {activeNav === item.id && <ChevronRight className="w-3 h-3 ml-auto" />}
            </button>
          ))}
        </div>

        <div className="px-4 pt-3 relative z-10">
          <PulseRings />
          <div className="text-center text-[9px] font-bold tracking-[2px] text-[#4ade80]" style={{ textShadow: '0 0 8px rgba(74,222,128,0.3)' }}>
            ALL SYSTEMS<br/>ONLINE
          </div>
        </div>
      </div>

      {/* ══ CONTENT ══ */}
      <div className="flex-1 relative overflow-auto">
        <GoldNetworkBg />
        <div className="relative z-10 p-7">

          {/* Header */}
          <div className="flex items-center justify-between mb-7" style={{ animation: 'fadeSlideDown 0.6s ease both' }}>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="h-[2px] w-8 rounded-full" style={{ background: 'linear-gradient(90deg, #FF6B00, transparent)' }}/>
                <span className="text-[9px] tracking-[3px] font-semibold text-[#FF6B00] uppercase">Command Center</span>
              </div>
              <h1 className="text-[26px] font-bold text-[#1A1A2E] tracking-wide">Acquisition Engine</h1>
            </div>
            <div className="text-[11px] text-[#888] font-mono px-4 py-2 rounded-xl" style={{
              background: 'rgba(255,255,255,0.5)', border: '1px solid rgba(61,58,57,0.25)',
              backdropFilter: 'blur(8px)',
            }}>
              {time.toLocaleTimeString('en-US', { hour12: true })} EDT, {time.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
            </div>
          </div>

          {/* KPI Row */}
          <div className="grid grid-cols-4 gap-4 mb-5">
            {[
              { label: 'LEADS GENERATED', value: 312, pct: '+24%', pctLabel: 'today', data: [20,32,28,45,38,55,42,60,50,68] },
              { label: 'CONTACTED', value: 109, pct: '91%', pctLabel: 'contact', data: [15,22,18,30,25,38,30,42,35,48] },
              { label: 'CONVERSIONS', value: 18, pct: '16.5%', pctLabel: 'rate', data: [3,5,4,7,6,9,7,12,10,14] },
              { label: 'REVENUE', value: 21.6, prefix: '$', suffix: 'K', pct: 'YTD', pctLabel: '', data: [5,8,6,12,10,15,12,18,16,20] },
            ].map((kpi, i) => (
              <Card3D key={i} delay={i * 100} glowColor="rgba(61,58,57,0.3)">
                <div className="p-4 relative">
                  <div className="text-[9px] font-bold text-[#1A1A2E] tracking-[1.5px] mb-1.5">{kpi.label}</div>
                  <div className="flex items-end gap-2">
                    <span className="text-[34px] font-extrabold text-[#1A1A2E] leading-none font-mono">
                      <Ctr end={kpi.value} prefix={kpi.prefix||''} suffix={kpi.suffix||''} delay={i*100+300}/>
                    </span>
                    <div className="mb-1.5">
                      <span className="text-[11px] font-bold text-[#FF6B00]">{kpi.pct}</span>
                      {kpi.pctLabel && <span className="text-[9px] text-[#999] ml-1">{kpi.pctLabel}</span>}
                    </div>
                  </div>
                  <div className="mt-2"><Sparkline data={kpi.data}/></div>
                </div>
              </Card3D>
            ))}
          </div>

          {/* Middle Row */}
          <div className="grid grid-cols-2 gap-4 mb-5">
            <Card3D delay={450} glowColor="rgba(61,58,57,0.25)">
              <div className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="text-[13px] font-bold text-[#1A1A2E]">SIM NODE MONITOR <span className="font-normal text-[#777]">(Central Gateway)</span></h3>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-[10px] font-bold text-[#1A1A2E]">STATUS:</span>
                      <span className="text-[10px] font-bold text-[#FF6B00] flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#FF6B00] animate-pulse inline-block"/>
                        SIM NODE ONLINE (Mississauga)
                      </span>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{
                    background: 'rgba(61,58,57,0.15)', border: '1px solid rgba(255,107,0,0.1)',
                    animation: 'iconPulse 3s ease-in-out infinite',
                  }}>
                    <Wifi className="w-5 h-5 text-[#FF6B00]" />
                  </div>
                </div>
                <div className="mt-3">
                  <TypingLog logs={SIM_LOGS} startDelay={600} />
                </div>
              </div>
            </Card3D>

            <Card3D delay={500} glowColor="rgba(61,58,57,0.25)">
              <div className="p-4">
                <h3 className="text-[13px] font-bold text-[#1A1A2E] mb-3">REPLY & TRANSFER CENTER</h3>
                <div className="p-3 rounded-xl mb-3 relative overflow-hidden" style={{ background: 'rgba(45,122,74,0.05)', border: '1px solid rgba(61,58,57,0.3)' }}>
                  <p className="text-[11px] text-[#1A1A2E] leading-relaxed relative z-10">
                    [Inbound from Bob Smith for Customer B] → AI SUGGESTS: "Our fragrance-free line is generally safe for eczema. Can I text you the full ingredients list?"
                  </p>
                  <div className="absolute top-0 left-0 h-full w-1 rounded-r-full" style={{ background: 'linear-gradient(180deg, #FF6B00, #D4B977)' }}/>
                </div>
                <div className="flex gap-2">
                  {['SEND AUTOMATICALLY', 'EDIT DRAFT', 'INITIATE WARM TRANSFER'].map((btn, i) => (
                    <button key={i} className={`px-3 py-2 rounded-lg text-[9px] font-bold tracking-wider transition-all duration-300 hover:-translate-y-0.5 ${
                      i === 0 ? 'text-white hover:shadow-lg' : 'text-[#FF6B00] hover:bg-[#FF6B00]/5'
                    }`}
                      style={{
                        background: i === 0 ? 'linear-gradient(135deg, #FF6B00, #1B5E3A)' : 'transparent',
                        border: i === 0 ? 'none' : '1.5px solid rgba(45,122,74,0.25)',
                        boxShadow: i === 0 ? '0 4px 12px rgba(45,122,74,0.25)' : 'none',
                      }}>{btn}</button>
                  ))}
                </div>
              </div>
            </Card3D>
          </div>

          {/* Bottom Row */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            <Card3D delay={600}>
              <div className="p-4">
                <h3 className="text-[12px] font-bold text-[#1A1A2E] mb-3">AUDIENCE SENTIMENT <span className="font-normal text-[#777]">(Real-Time)</span></h3>
                <SentimentGauge />
              </div>
            </Card3D>

            <Card3D delay={650}>
              <div className="p-4">
                <h3 className="text-[12px] font-bold text-[#1A1A2E] mb-3">LEAD STATUS FUNNEL</h3>
                <FunnelBars items={[
                  { value: 312, suffix: 'New Leads' },
                  { value: 109, suffix: 'Contacted' },
                  { value: 45, suffix: 'Qualified' },
                  { value: 18, suffix: 'Converted' },
                ]} />
              </div>
            </Card3D>

            <Card3D delay={700}>
              <div className="p-4">
                <h3 className="text-[12px] font-bold text-[#1A1A2E] mb-3">RECENT ACTIVITY BY BRAND</h3>
                <div className="space-y-2.5">
                  {[
                    { brand: 'Customer A', pct: 90 },
                    { brand: 'Customer B', pct: 75 },
                    { brand: 'Customer C', pct: 55 },
                    { brand: 'Customer D', pct: 40 },
                  ].map((b, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-[10px] text-[#555] w-20 text-right">{b.brand}</span>
                      <div className="flex-1 h-5 rounded-md overflow-hidden relative" style={{ background: 'rgba(255,107,0,0.05)' }}>
                        <div className="h-full rounded-md relative overflow-hidden" style={{
                          width: `${b.pct}%`,
                          background: 'linear-gradient(90deg, #1B5E3A, #D4B977)',
                          animation: `growWidth 0.9s cubic-bezier(0.25,0.46,0.45,0.94) ${0.8+i*0.12}s both`,
                          boxShadow: '0 2px 8px rgba(255,107,0,0.1)',
                        }}>
                          <div className="absolute inset-0" style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.12) 50%, transparent)', animation: `shimmer 2.5s ease ${2+i*0.3}s infinite` }}/>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card3D>
          </div>

          {/* Doc + Messenger */}
          <div className="grid grid-cols-2 gap-4">
            <Card3D delay={800}>
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-[12px] font-bold text-[#1A1A2E]">DOCUMENT DISPATCH LOG</h3>
                  <div className="flex gap-1.5">
                    <div className="w-7 h-7 rounded-lg bg-[#ef4444]/8 flex items-center justify-center hover:scale-110 transition-transform cursor-pointer"><FileText className="w-3.5 h-3.5 text-[#ef4444]" /></div>
                    <div className="w-7 h-7 rounded-lg bg-[#FF6B00]/8 flex items-center justify-center hover:scale-110 transition-transform cursor-pointer"><MessageCircle className="w-3.5 h-3.5 text-[#FF6B00]" /></div>
                  </div>
                </div>
                <TypingLog logs={[
                  '[10:48:02] SENT: "Aura_Gen_Science_PDF" to Lead: Bob Smith (via WhatsApp).',
                  '[10:48:12] SENT: "Price_List_Q2" to Lead: Alice Chen',
                  '[10:48:12] SENT: "Price_List_Q2" to Lead: Alice Chen (sIMS Gateway).',
                ]} startDelay={900} />
              </div>
            </Card3D>

            <Card3D delay={850}>
              <div className="p-4">
                <h3 className="text-[12px] font-bold text-[#1A1A2E] mb-3">MESSENGER GATEWAY STATUS</h3>
                <div className="space-y-3">
                  <div className="flex items-center gap-3 group cursor-pointer">
                    <div className="w-8 h-8 rounded-lg bg-[#25D366]/10 flex items-center justify-center group-hover:scale-110 transition-transform" style={{ boxShadow: '0 0 12px rgba(37,211,102,0.1)' }}>
                      <MessageCircle className="w-4 h-4 text-[#25D366]" />
                    </div>
                    <div>
                      <div className="text-[11px] text-[#1A1A2E]">WhatsApp API status: <span className="font-bold text-[#FF6B00]">connected</span></div>
                      <div className="text-[10px] text-[#888]">1000/1000 free conversations remaining</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 group cursor-pointer">
                    <div className="w-8 h-8 rounded-lg bg-[#3b82f6]/10 flex items-center justify-center group-hover:scale-110 transition-transform" style={{ boxShadow: '0 0 12px rgba(59,130,246,0.1)' }}>
                      <Phone className="w-4 h-4 text-[#3b82f6]" />
                    </div>
                    <div className="text-[11px] text-[#1A1A2E]">Email-to-SMS gateway status: <span className="font-bold text-[#FF6B00]">active</span></div>
                  </div>
                </div>
              </div>
            </Card3D>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeSlideDown { from { opacity:0; transform:translateY(-12px); } to { opacity:1; transform:translateY(0); } }
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
        @keyframes growWidth { from { width:0; } }
        @keyframes drawLine { to { stroke-dashoffset: 0; } }
        @keyframes shimmer { 0% { transform:translateX(-100%); } 100% { transform:translateX(200%); } }
        @keyframes dnaFloat { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-4px); } }
        @keyframes sidebarSlideIn { from { opacity:0; transform:translateX(-16px); } to { opacity:1; transform:translateX(0); } }
        @keyframes iconPulse { 0%,100% { box-shadow:0 0 0 0 rgba(255,107,0,0.1); } 50% { box-shadow:0 0 16px 4px rgba(61,58,57,0.25); } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
      `}</style>
    </div>
  );
}
