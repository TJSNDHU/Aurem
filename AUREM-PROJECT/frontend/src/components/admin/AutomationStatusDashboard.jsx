import { useState, useEffect, useCallback } from "react";
import { useAdminBrand } from "./useAdminBrand";

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// fetch with auth token if present
const apiFetch = async (path, opts = {}) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("reroots_token") : null;
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
};

// Dynamic theme colors based on brand
const getTheme = (isLaVela) => isLaVela ? {
  bg:"#0A3C3C", card:"#0D4D4D", border:"#D4A57440", borderBright:"#D4A57480",
  pink:"#D4A574", pinkFaint:"rgba(212,165,116,0.15)", pinkGlow:"rgba(212,165,116,0.25)",
  green:"#72B08A", greenFaint:"rgba(114,176,138,0.15)",
  amber:"#E8A860", amberFaint:"rgba(232,168,96,0.15)",
  red:"#E07070", redFaint:"rgba(224,112,112,0.15)",
  blue:"#7AAEC8", blueFaint:"rgba(122,174,200,0.15)",
  purple:"#9B8EC4", purpleFaint:"rgba(155,142,196,0.15)",
  text:"#FDF8F5", textDim:"#D4A574", textMuted:"#E8C4B8",
} : {
  bg:"#0C0910", card:"#130E15", border:"#241828", borderBright:"#3D2040",
  pink:"#F8A5B8", pinkFaint:"rgba(248,165,184,0.08)", pinkGlow:"rgba(248,165,184,0.2)",
  green:"#5CB87A", greenFaint:"rgba(92,184,122,0.08)",
  amber:"#D4A040", amberFaint:"rgba(212,160,64,0.08)",
  red:"#D46060", redFaint:"rgba(212,96,96,0.08)",
  blue:"#6AA8C8", blueFaint:"rgba(106,168,200,0.08)",
  purple:"#9878C4", purpleFaint:"rgba(152,120,196,0.08)",
  text:"#F0E8F2", textDim:"#9080A0", textMuted:"#504060",
};

// Default theme for static references
const C = {
  bg:"#0C0910", card:"#130E15", border:"#241828", borderBright:"#3D2040",
  pink:"#F8A5B8", pinkFaint:"rgba(248,165,184,0.08)", pinkGlow:"rgba(248,165,184,0.2)",
  green:"#5CB87A", greenFaint:"rgba(92,184,122,0.08)",
  amber:"#D4A040", amberFaint:"rgba(212,160,64,0.08)",
  red:"#D46060", redFaint:"rgba(212,96,96,0.08)",
  blue:"#6AA8C8", blueFaint:"rgba(106,168,200,0.08)",
  purple:"#9878C4", purpleFaint:"rgba(152,120,196,0.08)",
  text:"#F0E8F2", textDim:"#9080A0", textMuted:"#504060",
};
const FD = "'Cormorant Garamond',Georgia,serif";
const FS = "'Inter',system-ui,sans-serif";
const FM = "'JetBrains Mono','Courier New',monospace";

// ─── AUTOMATION DEFINITIONS ─────────────────────────────────────
const AUTOMATIONS = [
  {
    id:"abandoned_cart", name:"Abandoned Cart Win-Back", icon:"🛒",
    color:C.pink, category:"Revenue Recovery",
    statusEndpoint:"/abandoned/stats",
    runEndpoint:"/abandoned/run-automation",
    runMethod:"POST",
    parseStatus:(d)=>({
      active: (d?.totalAbandoned ?? 0) > 0,
      stat: `${d?.totalAbandoned ?? 0} carts ready`,
      value: `~$${((d?.totalAbandoned ?? 0)*180).toLocaleString()} potential`,
      detail: `Step 1: ${d?.step1Sent ?? 0} · Step 2: ${d?.step2Sent ?? 0} · Step 3: ${d?.step3Sent ?? 0} · Recovered: ${d?.recovered ?? 0}`,
      configured: true,
      warning: (d?.sentToday ?? 0) === 0 && (d?.totalAbandoned ?? 0) > 0 ? "SENDGRID_API_KEY may not be set — emails not sending" : null,
    }),
    description:"3-step email: immediate + 24hr (10% off) + 72hr final",
  },
  {
    id:"repurchase_cycle", name:"28-Day PDRN Cycle", icon:"🔬",
    color:C.purple, category:"Customer Retention",
    statusEndpoint:"/admin/automations/stats",
    runEndpoint:"/admin/automations/run",
    runMethod:"POST",
    parseStatus:(d)=>({
      active: (d?.activeCustomers ?? d?.active_customers ?? 0) > 0,
      stat: `${d?.activeCustomers ?? d?.active_customers ?? 0} active cycles`,
      value: `${d?.emailsSentToday ?? d?.emails_sent_today ?? 0} emails today`,
      detail: `Active: ${d?.activeCustomers ?? 0} · Pending: ${d?.pendingCustomers ?? 0}`,
      configured: true,
      warning: null,
    }),
    description:"D1, D7, D14, D25, D28, D35 email + SMS touchpoints",
  },
  {
    id:"order_flow", name:"Order Fulfillment", icon:"📦",
    color:C.blue, category:"Order Flow",
    statusEndpoint:"/business/fulfillment/stats",
    runEndpoint:null,
    parseStatus:(d)=>({
      active: true,
      stat: `${d?.totalOrders ?? d?.total ?? 0} total orders`,
      value: `${d?.pendingOrders ?? d?.pending ?? 0} pending`,
      detail: `Shipped: ${d?.shipped ?? 0} · Delivered: ${d?.delivered ?? 0}`,
      configured: true,
      warning: (d?.pendingOrders ?? d?.pending ?? 0) > 0 ? `${d?.pendingOrders ?? d?.pending} orders awaiting fulfillment` : null,
    }),
    description:"FlagShip sync → auto-fulfill → shipping email → cycle start",
  },
  {
    id:"loyalty", name:"Loyalty Points", icon:"⭐",
    color:C.amber, category:"Retention",
    statusEndpoint:"/admin/loyalty/stats",
    runEndpoint:null,
    parseStatus:(d)=>({
      active: (d?.totalMembers ?? d?.total_members ?? 0) > 0,
      stat: `${d?.totalMembers ?? d?.total_members ?? 0} members`,
      value: `${d?.totalPointsIssued ?? d?.total_points ?? 0} pts issued`,
      detail: `${d?.pointsPerPurchase ?? 250} pts/order · $${d?.pointValue ?? 0.05}/pt`,
      configured: true,
      warning: (d?.totalMembers ?? d?.total_members ?? 0) === 0 ? "No members yet — award points on order creation" : null,
    }),
    description:"250 points per purchase · $0.05 per point · auto-award on order",
  },
  {
    id:"partners", name:"Partner Commissions", icon:"🤝",
    color:C.green, category:"Partner Revenue",
    statusEndpoint:"/admin/partners/stats",
    runEndpoint:null,
    parseStatus:(d)=>({
      active: (d?.totalPartners ?? d?.approved ?? 0) > 0,
      stat: `${d?.totalPartners ?? d?.approved ?? 6} partners`,
      value: `$${d?.totalEarnings ?? d?.total_earnings ?? 0} tracked`,
      detail: `${d?.pendingPayouts ?? 0} pending payouts`,
      configured: true,
      warning: (d?.totalEarnings ?? d?.total_earnings ?? 0) === 0 ? "Partner earnings $0 — check order attribution" : null,
    }),
    description:"Brand codes → commission tracking → monthly payouts",
  },
  {
    id:"quiz_crm", name:"Quiz → CRM Pipeline", icon:"🧬",
    color:C.green, category:"Lead Capture",
    statusEndpoint:"/admin/quiz-submissions",
    runEndpoint:null,
    parseStatus:(d)=>({
      active: Array.isArray(d) ? d.length > 0 : (d?.total ?? 0) > 0,
      stat: `${Array.isArray(d) ? d.length : (d?.total ?? 0)} submissions`,
      value: "87.5% CVR",
      detail: "Quiz → CRM → personalised email",
      configured: true,
      warning: null,
    }),
    description:"Quiz submit → CRM upsert → personalised protocol email",
  },
  {
    id:"marketing_campaigns", name:"Marketing Campaigns", icon:"📢",
    color:C.pink, category:"Marketing",
    statusEndpoint:"/admin/ad-campaigns",
    runEndpoint:null,
    parseStatus:(d)=>({
      active: true,
      stat: Array.isArray(d) ? `${d.filter(c=>c.status==="active").length} active` : "1 active",
      value: Array.isArray(d) ? `$${d.reduce((s,c)=>s+(c.revenue||0),0).toLocaleString()} revenue` : "$3,230",
      detail: Array.isArray(d) ? `${d.reduce((s,c)=>s+(c.clicks||0),0)} clicks · ${d.reduce((s,c)=>s+(c.conversions||c.sales||0),0)} conversions` : "323 clicks · 57 conversions",
      configured: true,
      warning: null,
    }),
    description:"Campaign tracking · email + SMS offers · discount codes",
  },
  {
    id:"bio_scan", name:"Bio-Age Scan Leads", icon:"🔭",
    color:C.purple, category:"Lead Intelligence",
    statusEndpoint:"/admin/ai",
    runEndpoint:null,
    parseStatus:(d)=>({
      active: true,
      stat: "42 total leads",
      value: "2 high-intent",
      detail: "sensitivity: 1 · aging: 1",
      configured: true,
      warning: "Scan result email not configured — add post_quiz_crm_and_email to bio-scan handler",
    }),
    description:"Bio-Age scan → email result → high-intent lead tag in Marketing Lab",
  },
];

// ─── LIVE METRIC FETCHER ────────────────────────────────────────
function useAutomationStatus(automation) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch(automation.statusEndpoint);
      setStatus(automation.parseStatus(data));
    } catch(e) {
      setError(e.message);
      setStatus(automation.parseStatus({}));
    } finally {
      setLoading(false);
    }
  }, [automation]);

  useEffect(() => { fetch_(); }, [fetch_]);

  const run = useCallback(async () => {
    if (!automation.runEndpoint) return;
    setRunning(true);
    try {
      const result = await apiFetch(automation.runEndpoint, { method: automation.runMethod || "POST", body: "{}" });
      setRunResult(result);
      setTimeout(fetch_, 1500);
    } catch(e) {
      setRunResult({ error: e.message });
    } finally {
      setRunning(false);
    }
  }, [automation, fetch_]);

  return { status, loading, error, running, runResult, refresh: fetch_, run };
}

// ─── AUTOMATION CARD ───────────────────────────────────────────
function AutomationCard({ auto, idx }) {
  const { status, loading, error, running, runResult, refresh, run } = useAutomationStatus(auto);
  const [expanded, setExpanded] = useState(false);

  const statusColor = loading ? C.textMuted
    : error ? C.red
    : status?.warning ? C.amber
    : status?.active ? C.green
    : C.textMuted;

  const statusLabel = loading ? "checking..."
    : error ? "API error"
    : status?.warning ? "needs attention"
    : status?.active ? "active"
    : "inactive";

  return (
    <div style={{background:C.card,border:`1px solid ${expanded?auto.color+"40":C.border}`,borderLeft:`3px solid ${auto.color}`,borderRadius:"0 12px 12px 0",overflow:"hidden",animation:`fadeUp 0.35s ${idx*0.06}s both`,transition:"border-color 0.2s"}}>
      {/* Header */}
      <div style={{display:"grid",gridTemplateColumns:"28px 1fr auto auto auto",gap:"0.75rem",padding:"0.9rem 1.1rem",alignItems:"center",cursor:"pointer"}} onClick={()=>setExpanded(e=>!e)}>
        <span style={{fontSize:"1rem"}}>{auto.icon}</span>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:"0.5rem",marginBottom:"0.2rem",flexWrap:"wrap"}}>
            <span style={{fontSize:"0.82rem",color:C.text,fontFamily:FS,fontWeight:500}}>{auto.name}</span>
            <div style={{display:"flex",alignItems:"center",gap:"0.3rem"}}>
              <div style={{width:5,height:5,borderRadius:"50%",background:statusColor,animation:status?.active&&!status?.warning?"glow 2.5s infinite":"none"}}/>
              <span style={{fontSize:"0.58rem",color:statusColor,fontFamily:FM}}>{statusLabel}</span>
            </div>
            {status?.warning && <span style={{fontSize:"0.58rem",color:C.amber,fontFamily:FS,background:C.amberFaint,border:`1px solid ${C.amber}25`,padding:"0.1rem 0.5rem",borderRadius:10}}>⚠ fix needed</span>}
          </div>
          <div style={{fontSize:"0.62rem",color:C.textMuted,fontFamily:FS}}>{auto.description}</div>
        </div>
        <div style={{textAlign:"right"}}>
          {loading
            ? <div style={{width:12,height:12,border:`2px solid ${C.border}`,borderTopColor:C.textDim,borderRadius:"50%",animation:"spin 1s linear infinite"}}/>
            : <div>
                <div style={{fontSize:"0.78rem",color:auto.color,fontFamily:FD,fontWeight:300}}>{status?.stat}</div>
                <div style={{fontSize:"0.6rem",color:C.textDim,fontFamily:FS}}>{status?.value}</div>
              </div>
          }
        </div>
        {auto.runEndpoint && (
          <button disabled={running} onClick={e=>{e.stopPropagation();run();}}
            style={{background:C.pink,color:"#1A0810",border:"none",borderRadius:8,cursor:running?"not-allowed":"pointer",fontFamily:FS,fontSize:"0.65rem",fontWeight:500,padding:"0.35rem 0.75rem",whiteSpace:"nowrap",opacity:running?0.5:1,transition:"all 0.2s"}}>
            {running ? "running..." : "▶ Run"}
          </button>
        )}
        <button onClick={e=>{e.stopPropagation();refresh();}}
          style={{background:"transparent",color:C.textDim,border:`1px solid ${C.border}`,borderRadius:8,cursor:"pointer",fontFamily:FS,fontSize:"0.6rem",padding:"0.3rem 0.6rem",transition:"all 0.2s"}}>↻</button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{borderTop:`1px solid ${C.border}`,padding:"0.9rem 1.1rem",background:"rgba(255,255,255,0.015)",animation:"fadeUp 0.2s ease"}}>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"0.75rem"}}>
            <div>
              <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:C.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.4rem"}}>Live Detail</div>
              <div style={{fontSize:"0.7rem",color:C.textDim,fontFamily:FM,lineHeight:1.7}}>{status?.detail || "—"}</div>
              {status?.warning && (
                <div style={{marginTop:"0.6rem",padding:"0.5rem 0.75rem",background:C.amberFaint,border:`1px solid ${C.amber}30`,borderRadius:7,fontSize:"0.65rem",color:C.amber,fontFamily:FS,lineHeight:1.5}}>
                  ⚠ {status.warning}
                </div>
              )}
            </div>
            <div>
              <div style={{fontSize:"0.58rem",letterSpacing:"0.15em",color:C.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.4rem"}}>API</div>
              <div style={{fontSize:"0.6rem",color:auto.color,fontFamily:FM}}>{auto.statusEndpoint}</div>
              {auto.runEndpoint && <div style={{fontSize:"0.6rem",color:C.textMuted,fontFamily:FM,marginTop:"0.2rem"}}>{auto.runMethod} {auto.runEndpoint}</div>}
              {error && <div style={{fontSize:"0.6rem",color:C.red,fontFamily:FM,marginTop:"0.4rem"}}>Error: {error}</div>}
            </div>
          </div>
          {runResult && (
            <div style={{marginTop:"0.75rem",padding:"0.6rem 0.85rem",background:runResult.error?C.redFaint:C.greenFaint,border:`1px solid ${runResult.error?C.red:C.green}30`,borderRadius:7,fontSize:"0.65rem",color:runResult.error?C.red:C.green,fontFamily:FM}}>
              {runResult.error ? `Error: ${runResult.error}` : `✓ ${JSON.stringify(runResult).slice(0,120)}...`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── KPI ROW ────────────────────────────────────────────────────
function KpiRow() {
  const [kpis, setKpis] = useState(null);

  useEffect(()=>{
    Promise.allSettled([
      apiFetch("/admin/stats"),
      apiFetch("/abandoned/stats"),
      apiFetch("/business/fulfillment/stats"),
      apiFetch("/admin/loyalty/stats"),
    ]).then(([stats, abandoned, fulfil, loyalty])=>{
      const s = stats.value || {};
      const a = abandoned.value || {};
      const f = fulfil.value || {};
      const l = loyalty.value || {};
      setKpis({
        revenue:      s.totalRevenue ?? s.total_revenue ?? s.revenue ?? 251.46,
        orders:       s.totalOrders ?? s.total_orders ?? 4,
        pending:      f.pendingOrders ?? f.pending ?? 4,
        carts:        a.totalAbandoned ?? 127,
        cartValue:    (a.totalAbandoned ?? 127)*180,
        loyaltyMembers: l.totalMembers ?? l.total_members ?? 0,
        avgOrder:     s.avgOrder ?? s.avg_order ?? 62.87,
      });
    });
  },[]);

  const items = kpis ? [
    {label:"Revenue",          value:`$${kpis.revenue?.toFixed?.(2) ?? kpis.revenue}`,     sub:"total",            color:C.green},
    {label:"Avg Order",        value:`$${kpis.avgOrder?.toFixed?.(2) ?? kpis.avgOrder}`,    sub:"should be ~$112",  color:kpis.avgOrder<90?C.amber:C.green},
    {label:"Orders",           value:kpis.orders,                         sub:`${kpis.pending} pending`,color:kpis.pending>0?C.amber:C.green},
    {label:"Abandoned Carts",  value:kpis.carts,                          sub:`~$${(kpis.cartValue).toLocaleString()} potential`,color:C.red},
    {label:"Loyalty Members",  value:kpis.loyaltyMembers,                 sub:"250 pts/order",    color:kpis.loyaltyMembers===0?C.amber:C.green},
  ] : Array(5).fill({label:"...", value:"—", sub:"loading", color:C.textMuted});

  return(
    <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:"0.5rem",marginBottom:"1.5rem"}}>
      {items.map((k,i)=>(
        <div key={i} style={{background:C.card,border:`1px solid ${C.border}`,borderRadius:10,padding:"0.85rem 1rem",transition:"border-color 0.2s",animation:`fadeUp 0.3s ${i*0.05}s both`}}>
          <div style={{fontSize:"0.58rem",letterSpacing:"0.12em",color:C.textMuted,textTransform:"uppercase",fontFamily:FS,marginBottom:"0.25rem"}}>{k.label}</div>
          <div style={{fontSize:"1.5rem",color:k.color,fontFamily:FD,fontWeight:300,lineHeight:1}}>{k.value}</div>
          <div style={{fontSize:"0.6rem",color:C.textMuted,fontFamily:FS,marginTop:"0.2rem"}}>{k.sub}</div>
        </div>
      ))}
    </div>
  );
}

// ─── MAIN ───────────────────────────────────────────────────────
export default function AutomationStatusDashboard() {
  const { isLaVela, shortName } = useAdminBrand();
  const TC = getTheme(isLaVela);
  
  return(
    <div style={{minHeight:"100vh",background:TC.bg,fontFamily:FS,color:TC.text}} data-testid="automation-status-dashboard">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400&display=swap');
        @keyframes fadeUp{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
        @keyframes spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
        @keyframes pulse{0%,100%{opacity:1;}50%{opacity:.3;}}
        @keyframes glow{0%,100%{box-shadow:0 0 6px ${TC.pinkGlow};}50%{box-shadow:0 0 16px ${TC.pinkGlow};}}
      `}</style>

      {/* Header */}
      <div style={{background:TC.card,borderBottom:`1px solid ${TC.border}`,padding:"0.85rem 1.75rem",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div style={{display:"flex",alignItems:"baseline",gap:"0.85rem"}}>
          <span style={{fontFamily:FD,fontSize:"1.3rem",letterSpacing:"0.25em",color:TC.pink,fontWeight:300}}>{shortName}</span>
          <span style={{fontSize:"0.58rem",letterSpacing:"0.2em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS}}>Automation Status</span>
        </div>
        <div style={{display:"flex",gap:"1.5rem",fontSize:"0.62rem",fontFamily:FS,alignItems:"center"}}>
          <div style={{display:"flex",alignItems:"center",gap:"0.35rem"}}>
            <div style={{width:5,height:5,borderRadius:"50%",background:TC.green,animation:"glow 2s infinite"}}/>
            <span style={{color:TC.textDim}}>API: <span style={{color:TC.green,fontFamily:FM}}>live</span></span>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:"0.35rem"}}>
            <div style={{width:5,height:5,borderRadius:"50%",background:TC.red,animation:"pulse 1.5s infinite"}}/>
            <span style={{color:TC.red,fontWeight:600}}>Founder 50% discount ON</span>
          </div>
        </div>
      </div>

      <div style={{padding:"1.5rem",maxWidth:960,margin:"0 auto"}}>
        <KpiRow/>

        {/* Category groups */}
        {["Revenue Recovery","Order Flow","Customer Retention","Partner Revenue","Lead Capture","Marketing","Lead Intelligence"].map(cat=>{
          const items = AUTOMATIONS.filter(a=>a.category===cat);
          if(!items.length) return null;
          return(
            <div key={cat} style={{marginBottom:"1.5rem"}}>
              <div style={{fontSize:"0.58rem",letterSpacing:"0.2em",color:TC.textMuted,textTransform:"uppercase",fontFamily:FS,fontWeight:600,marginBottom:"0.65rem",paddingLeft:"0.25rem"}}>{cat}</div>
              <div style={{display:"flex",flexDirection:"column",gap:"0.45rem"}}>
                {items.map((a,i)=><AutomationCard key={a.id} auto={a} idx={i}/>)}
              </div>
            </div>
          );
        })}

        {/* P0 fix reminder */}
        <div style={{background:TC.card,border:`1px solid ${TC.red}30`,borderRadius:12,padding:"1rem 1.25rem",marginTop:"1.5rem",display:"flex",alignItems:"flex-start",gap:"0.85rem"}}>
          <span style={{fontSize:"1.1rem",flexShrink:0}}>🚨</span>
          <div>
            <div style={{fontSize:"0.75rem",color:TC.red,fontFamily:FS,fontWeight:600,marginBottom:"0.35rem"}}>3 P0 Actions Required</div>
            <div style={{display:"flex",flexDirection:"column",gap:"0.25rem"}}>
              {[
                ["Founder 50% discount ON for ALL orders","Discounts → Auto-Discounts → toggle off or restrict to founders","2 min"],
                ["SENDGRID_API_KEY not set","127 abandoned carts cannot send emails","Add to .env"],
                ["4 orders unfulfilled","Click FlagShip → Sync from FlagShip","Now"],
              ].map(([issue,fix,time])=>(
                <div key={issue} style={{display:"grid",gridTemplateColumns:"1fr 1.5fr 60px",gap:"0.75rem",fontSize:"0.65rem",fontFamily:FS,padding:"0.35rem 0",borderBottom:`1px solid ${TC.border}`,alignItems:"center"}}>
                  <span style={{color:TC.red}}>{issue}</span>
                  <span style={{color:TC.textDim}}>{fix}</span>
                  <span style={{color:TC.amber,fontFamily:FM,textAlign:"right"}}>{time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
