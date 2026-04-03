import React, { useState } from "react";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";
import { useAdminBrand } from "./useAdminBrand";

// Dynamic color palette based on brand
const getThemeColors = (isLaVela) => isLaVela ? {
  bg: "#0D4D4D", surface: "#1A6B6B", surfaceAlt: "#1A6B6B40",
  border: "#D4A57440", pink: "#D4A574", pinkDim: "#E6BE8A",
  pinkFaint: "rgba(212,165,116,0.15)", dark: "#FDF8F5",
  textDim: "#D4A574", textMuted: "#E8C4B8",
  green: "#72B08A", greenFaint: "rgba(114,176,138,0.15)",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.15)",
  red: "#E07070", redFaint: "rgba(224,112,112,0.15)",
  blue: "#7AAEC8", blueFaint: "rgba(122,174,200,0.15)",
  purple: "#9B8EC4", purpleFaint: "rgba(155,142,196,0.15)",
} : {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceAlt: "#FEF6F7",
  border: "#F0E8E8", pink: "#F8A5B8", pinkDim: "#E8889A",
  pinkFaint: "rgba(248,165,184,0.08)", dark: "#2D2A2E",
  textDim: "#8A8490", textMuted: "#C4BAC0",
  green: "#72B08A", greenFaint: "rgba(114,176,138,0.08)",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.08)",
  red: "#E07070", redFaint: "rgba(224,112,112,0.08)",
  blue: "#7AAEC8", blueFaint: "rgba(122,174,200,0.08)",
  purple: "#9B8EC4", purpleFaint: "rgba(155,142,196,0.08)",
};

// Default colors for static references
const C = {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceAlt: "#FEF6F7",
  border: "#F0E8E8", pink: "#F8A5B8", pinkDim: "#E8889A",
  pinkFaint: "rgba(248,165,184,0.08)", dark: "#2D2A2E",
  textDim: "#8A8490", textMuted: "#C4BAC0",
  green: "#72B08A", greenFaint: "rgba(114,176,138,0.08)",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.08)",
  red: "#E07070", redFaint: "rgba(224,112,112,0.08)",
  blue: "#7AAEC8", blueFaint: "rgba(122,174,200,0.08)",
  purple: "#9B8EC4", purpleFaint: "rgba(155,142,196,0.08)",
};

const STATUS = {
  live:        { label: "Live",        color: C.green,  bg: C.greenFaint  },
  built:       { label: "Built",       color: C.blue,   bg: C.blueFaint   },
  connect:     { label: "Connect",     color: C.amber,  bg: C.amberFaint  },
  automate:    { label: "Automate",    color: C.purple, bg: C.purpleFaint },
  opportunity: { label: "Build",       color: C.pink,   bg: C.pinkFaint   },
  critical:    { label: "Action Now",  color: C.red,    bg: C.redFaint    },
};

const FULL_SIDEBAR = [
  {
    section: "Navigation", color: C.textDim,
    items: [
      { label: "Home",                status: "live",        action: "Add KPI widgets pulling from our 4 modules + live revenue" },
      { label: "Orders",              status: "connect",     action: "Connect to Module 03 Orders — same MongoDB collection, unified view" },
      { label: "Order Flow",          status: "live",        action: "Already working" },
      { label: "FlagShip Sync",       status: "critical",    action: "🔴 Owner adding webhook URL to FlagShip dashboard now" },
      { label: "Drafts",              status: "live",        action: "Already working" },
      { label: "Abandoned (12)",      status: "critical",    action: "🔴 3-step win-back active — immediate + 24hr (10% off) + 72hr final" },
    ]
  },
  {
    section: "Shop (5)", color: C.amber,
    items: [
      { label: "Products",            status: "live",        action: "Add HC compliance badge from Module 05 — show NPN status per product" },
      { label: "Combo Offers",        status: "automate",    action: "Pull active bundles dynamically into Day 28 repurchase emails" },
      { label: "Clinical Logic",      status: "automate",    action: "Drive personalised cross-sell recommendations in CRM automation emails" },
      { label: "Inventory",           status: "connect",     action: "Same data as Module 01 — connect to single MongoDB collection" },
      { label: "Collections",         status: "live",        action: "Already working" },
    ]
  },
  {
    section: "Data Hub", color: C.blue,
    items: [
      { label: "Customers",           status: "connect",     action: "Unify with Module 02 CRM — single customer profile, two views" },
      { label: "Partners",            status: "automate",    action: "Auto-create wholesale login + order portal when partner is added" },
      { label: "Waitlist",            status: "automate",    action: "Auto-add to CRM + fire launch email when product restocks" },
      { label: "Founders",            status: "automate",    action: "Auto-tag VIP in CRM + custom founder repurchase sequence" },
      { label: "Reviews",             status: "live",        action: "✅ Day 21 review request + 100 Roots reward — fully built" },
      { label: "Marketing",           status: "connect",     action: "Connect to CRM automation engine — unified campaign tracking" },
      { label: "Discounts",           status: "connect",     action: "Connect unique code generator (built) — auto-create codes per customer" },
      { label: "Programs",            status: "opportunity", action: "Build: PDRN loyalty program — 5th order free or 10% off at 3+ orders" },
      { label: "Biomarkers",          status: "opportunity", action: "Build: Skin biomarker inputs drive Clinical Logic personalised regimens" },
      { label: "AI Lab",              status: "connect",     action: "Connect to AI Intelligence module — share Claude API integration" },
      { label: "AI Intelligence",     status: "built",       action: "Executive Intelligence built — connect to live DB data from all modules" },
      { label: "Marketing Lab",       status: "connect",     action: "Connect to CRM segments for targeted campaign creation" },
      { label: "Blog",                status: "live",        action: "Consider auto-post on Day 21 (results milestone) for social proof" },
      { label: "Analytics",           status: "connect",     action: "Pull Module 03 + 04 data here for unified business analytics" },
    ]
  },
  {
    section: "Sales Channels", color: C.green,
    items: [
      { label: "Online Store",        status: "live",        action: "Live — ensure order webhooks fire to our automation system" },
      { label: "Inbox",               status: "automate",    action: "Claude auto-drafts replies to customer messages for owner review" },
      { label: "View Store",          status: "live",        action: "reroots.ca — live" },
    ]
  },
  {
    section: "Business System (Built)", color: C.blue,
    items: [
      { label: "Inventory & Batch",   status: "built",       action: "✅ Module 01 complete — wired to MongoDB" },
      { label: "CRM (28-day cycles)", status: "built",       action: "✅ Module 02 complete — automations active, wired to MongoDB" },
      { label: "Orders",              status: "built",       action: "✅ Module 03 complete — CA tax, wired to MongoDB" },
      { label: "Accounting",          status: "built",       action: "✅ Module 04 complete — GST/HST/CRA ready, wired to MongoDB" },
      { label: "HC Compliance",       status: "built",       action: "✅ Module 05 complete — NPN tracker + task manager, wired to MongoDB" },
    ]
  },
  {
    section: "Loyalty & Reviews (Live)", color: C.green,
    items: [
      { label: "Loyalty (Roots)",     status: "live",        action: "✅ 250/500 Roots per order — auto-award on purchase" },
      { label: "Roots Redemption",    status: "live",        action: "✅ 30% cap at checkout — wa.me notification" },
      { label: "Gift Roots",          status: "live",        action: "✅ Gift to any email — wa.me notifications both parties" },
      { label: "Reviews + Day 21",    status: "live",        action: "✅ 100 Roots on submit — Google review link shown" },
      { label: "Birthday Bonus",      status: "live",        action: "✅ 100 Roots — daily scheduler at 9 AM EST" },
      { label: "Referral Bonus",      status: "live",        action: "✅ 500 Roots — on referred customer's first purchase" },
    ]
  },
  {
    section: "WhatsApp (Live)", color: C.green,
    items: [
      { label: "WhatsApp AI",         status: "live",        action: "✅ Digital Twin + Brand Voice modes — WHAPI integrated" },
      { label: "WhatsApp CRM",        status: "live",        action: "✅ wa.me pending panel — manual send workflow" },
      { label: "WhatsApp Templates",  status: "live",        action: "✅ 7 loyalty notification types — instant wa.me links" },
      { label: "28-Day Messages",     status: "live",        action: "✅ Day 0/7/14/21/25/28/35 — daily scheduler at 10:30 AM EST" },
    ]
  },
  {
    section: "Apps", color: C.textDim,
    items: [
      { label: "Team",                status: "connect",     action: "RBAC built — map to owner, manager, staff, wholesale roles" },
    ]
  },
  {
    section: "Settings", color: C.textDim,
    items: [
      { label: "Store Settings",      status: "live",        action: "Already working" },
      { label: "Security",            status: "connect",     action: "Wire JWT auth + Google Sign-In we built to Security panel" },
    ]
  },
  {
    section: "System (Built)", color: C.blue,
    items: [
      { label: "Sales Intelligence",      status: "live",    action: "✅ Live pipeline view with actionable revenue items" },
      { label: "Automation Intelligence", status: "live",    action: "✅ 12-rule automation mapping — all schedulers visible" },
      { label: "Integration Map",         status: "live",    action: "✅ This page — full platform integration roadmap" },
      { label: "Platform Diagnosis",      status: "live",    action: "✅ Health checks and status monitoring" },
    ]
  },
];

const AUTOMATION_SEQUENCES = [
  {
    trigger: "Order Placed", icon: "🛒", color: C.green,
    flows: [
      { step:"1", action:"Create/update CRM customer record",         where:"Module 02", built:true },
      { step:"2", action:"Send order confirmation email",             where:"Email System", built:true },
      { step:"3", action:"Create revenue transaction in accounting",  where:"Module 04", built:true },
      { step:"4", action:"Auto-award 250/500 Roots",                  where:"Loyalty System", built:true },
      { step:"5", action:"Create wa.me notification for admin",       where:"WhatsApp CRM", built:true },
      { step:"6", action:"Check referral → award 500 Roots to referrer", where:"Loyalty System", built:true },
    ]
  },
  {
    trigger: "FlagShip Label Created", icon: "📦", color: C.blue,
    flows: [
      { step:"1", action:"Auto-update order to Shipped",              where:"Module 03", built:true },
      { step:"2", action:"Send shipping notification + tracking link",where:"Email System", built:true },
      { step:"3", action:"Start 28-day PDRN cycle clock in CRM",      where:"Module 02", built:true },
    ]
  },
  {
    trigger: "28-Day Repurchase Cycle", icon: "🔄", color: C.pink,
    flows: [
      { step:"D0",  action:"Welcome + wa.me link created",            where:"WhatsApp CRM", built:true },
      { step:"D1",  action:"Welcome + PDRN education email",          where:"CRM Automation", built:true },
      { step:"D7",  action:"Week 1 check-in + wa.me link",            where:"CRM Automation", built:true },
      { step:"D14", action:"Progress + Instagram share prompt",       where:"CRM Automation", built:true },
      { step:"D21", action:"Review request + 100 Roots incentive",    where:"Reviews", built:true },
      { step:"D25", action:"Running low nudge + wa.me link",          where:"CRM Automation", built:true },
      { step:"D28", action:"Cycle complete + dynamic bundle upsell",  where:"CRM Automation", built:true },
      { step:"D35", action:"Win-back with unique discount code",      where:"CRM Automation", built:true },
    ]
  },
  {
    trigger: "Abandoned Checkout", icon: "⚠️", color: C.red,
    flows: [
      { step:"1", action:"Immediate recovery email with cart items",   where:"Automation", built:true },
      { step:"2", action:"24hr follow-up with 10% off unique code",    where:"Automation", built:true },
      { step:"3", action:"72hr final email — PDRN routine waiting",    where:"Automation", built:true },
    ]
  },
  {
    trigger: "Roots Redemption at Checkout", icon: "🌿", color: C.green,
    flows: [
      { step:"1", action:"Validate Roots balance (30% cap)",           where:"Checkout", built:true },
      { step:"2", action:"Deduct Roots from customer balance",         where:"Loyalty System", built:true },
      { step:"3", action:"Create wa.me confirmation for admin",        where:"WhatsApp CRM", built:true },
    ]
  },
  {
    trigger: "Gift Roots Sent", icon: "🎁", color: C.purple,
    flows: [
      { step:"1", action:"Deduct from sender balance",                 where:"Loyalty System", built:true },
      { step:"2", action:"Credit to recipient (+ create if new)",      where:"Loyalty System", built:true },
      { step:"3", action:"Award 50 bonus if recipient is new",         where:"Loyalty System", built:true },
      { step:"4", action:"Create wa.me for sender + recipient",        where:"WhatsApp CRM", built:true },
    ]
  },
  {
    trigger: "Daily Scheduler — 9AM, 10AM, 10:30AM ET", icon: "⏰", color: C.amber,
    flows: [
      { step:"09:00", action:"Birthday bonus check → 100 Roots",       where:"Loyalty Scheduler", built:true },
      { step:"10:00", action:"Day 21 review request check",            where:"Reviews Scheduler", built:true },
      { step:"10:30", action:"28-day wa.me links generation",          where:"WhatsApp Scheduler", built:true },
    ]
  },
  {
    trigger: "1st of Month — 7AM ET", icon: "📊", color: C.purple,
    flows: [
      { step:"07:00", action:"Monthly P&L summary email to owner",     where:"Scheduler", built:true },
    ]
  },
];

const PRIORITY_GROUPS = [
  {
    title: "This Week — Immediate Revenue",
    color: C.red,
    items: [
      { task:"Abandoned checkout win-back (12 pending)",             detail:"12 × avg $180 = $2,160 recoverable. Webhook + 3-email sequence.", effort:"4 hrs", done: true },
      { task:"FlagShip → auto-fulfill + shipping notification",      detail:"🔴 Owner adding webhook URL to FlagShip dashboard now.", effort:"2 hrs", done: false },
      { task:"Wire all 5 modules to MongoDB",                        detail:"Modules built. Developer wires /api/admin/* routes to live DB.", effort:"1 day", done: true },
      { task:"SendGrid API key → .env",                              detail:"🔴 Owner adding key. Emails currently logged but not sent.", effort:"5 min", done: false },
    ]
  },
  {
    title: "Completed — Loyalty System (All 10 Tasks)", 
    color: C.green,
    items: [
      { task:"Loyalty (Roots) — 250/500 per order",                  detail:"✅ Auto-award on purchase, first order double bonus.",       effort:"Done", done: true },
      { task:"Roots Redemption — 30% cap at checkout",               detail:"✅ Customer applies Roots, wa.me notification created.",     effort:"Done", done: true },
      { task:"Gift Roots — sender/recipient notifications",          detail:"✅ +50 bonus if recipient is new, wa.me both parties.",      effort:"Done", done: true },
      { task:"Reviews — Day 21 + 100 Roots reward",                  detail:"✅ Auto-request review, Google review link on thank you.",   effort:"Done", done: true },
      { task:"28-Day WhatsApp Templates — wa.me links",              detail:"✅ Days 0/7/14/21/25/28/35 via daily scheduler.",            effort:"Done", done: true },
      { task:"Loyalty WhatsApp Notifications — 7 types",             detail:"✅ points_earned, redemption, gift, review, birthday, referral.", effort:"Done", done: true },
      { task:"Birthday Bonus — 100 Roots daily",                     detail:"✅ Scheduler at 9 AM EST, prevents duplicate awards.",       effort:"Done", done: true },
      { task:"Referral Bonus — 500 Roots on first purchase",         detail:"✅ Wired to order flow, auto-triggers for referrer.",        effort:"Done", done: true },
      { task:"Roots Balance in Email Footers",                       detail:"✅ All CRM emails show balance + progress to 30% off.",      effort:"Done", done: true },
      { task:"Points → Roots rename",                                detail:"✅ All customer-facing UI uses 'Roots' branding.",           effort:"Done", done: true },
    ]
  },
  {
    title: "This Month — Unify the Platform",
    color: C.amber,
    items: [
      { task:"Customers (Data Hub) ↔ Module 02 CRM",                 detail:"Single MongoDB collection. Both panels read same data.",       effort:"3 hrs", done: false },
      { task:"Inventory (Shop) ↔ Module 01 Inventory",               detail:"Same data source — eliminate duplicate entry.",               effort:"2 hrs", done: false },
      { task:"Discounts ↔ unique code generator",                    detail:"Codes we generate per customer appear in Discounts panel.",   effort:"2 hrs", done: false },
      { task:"Founders → VIP CRM tier",                              detail:"All Founders auto-tagged VIP + custom repurchase sequence.",  effort:"1 hr", done: false },
      { task:"Waitlist → CRM + restock email",                       detail:"On restock, auto-notify + add to CRM pipeline.",             effort:"2 hrs", done: false },
      { task:"Analytics ↔ Modules 03+04 data",                       detail:"Orders + Accounting feed Analytics panel.",                  effort:"3 hrs", done: false },
      { task:"AI Lab ↔ AI Intelligence module",                      detail:"Both use Claude API — share integration, don't duplicate.",  effort:"1 hr", done: false },
      { task:"Team (Apps) → RBAC roles",                             detail:"Owner/Manager/Staff/Wholesale roles map to Team panel.",     effort:"2 hrs", done: false },
      { task:"Security ↔ JWT auth system",                           detail:"Security panel shows active sessions + token management.",   effort:"2 hrs", done: false },
    ]
  },
  {
    title: "Next Quarter — Growth",
    color: C.purple,
    items: [
      { task:"Partners → wholesale login portal",                    detail:"Partners auto-get wholesale-role login + self-serve orders.", effort:"4 hrs", done: false },
      { task:"Inbox → Claude auto-draft replies",                    detail:"Claude reads message, drafts reply for owner to approve.",   effort:"3 hrs", done: false },
      { task:"Clinical Logic → personalised email recs",             detail:"Cross-sell in D25/28 emails based on purchase history.",    effort:"3 hrs", done: false },
      { task:"Combo Offers → dynamic bundle CTAs in email",          detail:"Day 28 email pulls live bundle from Combo Offers panel.",   effort:"2 hrs", done: false },
      { task:"Marketing Lab → CRM segment integration",              detail:"Segments from CRM tier/cycle data for targeted campaigns.", effort:"3 hrs", done: false },
      { task:"Programs → PDRN loyalty program",                      detail:"5th order free, or 10% off at 3+ orders — auto-calculated.",effort:"5 hrs", done: false },
      { task:"Biomarkers → Clinical Logic personalisation",          detail:"Skin inputs drive personalised regimen recommendations.",    effort:"6 hrs", done: false },
    ]
  },
];

function StatusBadge({ label, color, bg }) {
  return (
    <span 
      className="text-[10px] tracking-wider font-semibold px-2 py-0.5 rounded-full whitespace-nowrap"
      style={{ color, background: bg || `${color}15`, border: `1px solid ${color}30` }}
    >
      {label}
    </span>
  );
}

function SidebarTab() {
  const all = FULL_SIDEBAR.flatMap(s => s.items);
  const counts = {};
  Object.keys(STATUS).forEach(k => counts[k] = all.filter(i => i.status === k).length);

  return (
    <div className="space-y-6">
      {/* Status Summary */}
      <div className="grid grid-cols-6 gap-2">
        {Object.entries(STATUS).map(([key, val], i) => (
          <div 
            key={key} 
            className="bg-white border rounded-lg p-3 text-center"
            style={{ borderColor: `${val.color}30` }}
          >
            <div className="text-2xl font-light" style={{ color: val.color, fontFamily: "Georgia, serif" }}>
              {counts[key] || 0}
            </div>
            <div className="text-[10px] text-gray-500 mt-1">{val.label}</div>
          </div>
        ))}
      </div>

      {/* Full Sidebar Map */}
      <div className="border rounded-xl overflow-hidden" style={{ borderColor: C.border }}>
        <div className="grid grid-cols-[1.6fr_3fr_100px] px-4 py-2 bg-gray-50 border-b text-[10px] tracking-wider text-gray-400 uppercase font-medium">
          <div>Sidebar Item</div>
          <div>Action Required</div>
          <div>Status</div>
        </div>
        {FULL_SIDEBAR.map((section, si) => (
          <div key={section.section}>
            <div 
              className="px-4 py-2 border-b border-t text-[10px] tracking-wider uppercase font-semibold"
              style={{ background: `${section.color}08`, color: section.color, borderColor: C.border }}
            >
              {section.section}
            </div>
            {section.items.map((item, ii) => {
              const sm = STATUS[item.status] || STATUS.live;
              return (
                <div 
                  key={item.label}
                  className={cn(
                    "grid grid-cols-[1.6fr_3fr_100px] px-4 py-3 border-b items-center gap-4",
                    ii % 2 === 0 ? "bg-white" : "bg-gray-50/50"
                  )}
                  style={{ borderColor: C.border }}
                >
                  <div className={cn(
                    "text-sm flex items-center gap-2",
                    item.status === "critical" ? "text-red-600 font-medium" : "text-gray-800"
                  )}>
                    {item.status === "critical" && (
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    )}
                    {item.label}
                  </div>
                  <div className="text-xs text-gray-500 leading-relaxed">{item.action}</div>
                  <div><StatusBadge label={sm.label} color={sm.color} bg={sm.bg} /></div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function AutomationTab() {
  const [open, setOpen] = useState("28-Day Repurchase Cycle");
  const totalBuilt = AUTOMATION_SEQUENCES.flatMap(s => s.flows).filter(f => f.built).length;
  const totalAll = AUTOMATION_SEQUENCES.flatMap(s => s.flows).length;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          ["Steps Built", `${totalBuilt}/${totalAll}`, C.blue],
          ["Sequences Complete", `${AUTOMATION_SEQUENCES.filter(s => s.flows.every(f => f.built)).length}/${AUTOMATION_SEQUENCES.length}`, C.green],
          ["Still To Build", totalAll - totalBuilt, C.amber]
        ].map(([l, v, c]) => (
          <div key={l} className="bg-white border rounded-lg p-4" style={{ borderColor: C.border }}>
            <div className="text-[10px] tracking-wider text-gray-400 uppercase mb-1">{l}</div>
            <div className="text-2xl font-light" style={{ color: c, fontFamily: "Georgia, serif" }}>{v}</div>
          </div>
        ))}
      </div>

      {/* Automation Sequences */}
      <div className="space-y-3">
        {AUTOMATION_SEQUENCES.map((seq) => {
          const isOpen = open === seq.trigger;
          const builtCount = seq.flows.filter(f => f.built).length;
          const allBuilt = builtCount === seq.flows.length;
          const pct = Math.round(builtCount / seq.flows.length * 100);
          
          return (
            <div 
              key={seq.trigger}
              className="bg-white border rounded-xl overflow-hidden"
              style={{ borderColor: allBuilt ? `${seq.color}50` : C.border }}
            >
              <button
                onClick={() => setOpen(isOpen ? null : seq.trigger)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <span className="text-xl">{seq.icon}</span>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-800 mb-1">{seq.trigger}</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 bg-gray-100 rounded overflow-hidden">
                      <div 
                        className="h-full rounded transition-all"
                        style={{ width: `${pct}%`, background: allBuilt ? C.green : seq.color }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-gray-400">{builtCount}/{seq.flows.length}</span>
                  </div>
                </div>
                <StatusBadge 
                  label={allBuilt ? "Complete" : "In Progress"} 
                  color={allBuilt ? C.green : C.amber} 
                />
                <span className="text-gray-400 text-sm">{isOpen ? "▲" : "▼"}</span>
              </button>
              
              {isOpen && (
                <div className="border-t bg-gray-50" style={{ borderColor: C.border }}>
                  {seq.flows.map((flow, fi) => (
                    <div 
                      key={fi}
                      className="grid grid-cols-[44px_1fr_140px_80px] gap-3 px-4 py-2.5 border-b items-center"
                      style={{ borderColor: C.border }}
                    >
                      <div 
                        className={cn(
                          "w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-mono font-semibold",
                          flow.built ? "bg-green-50 border border-green-300 text-green-600" : "bg-red-50 border border-red-300 text-red-500"
                        )}
                      >
                        {flow.built ? "✓" : flow.step}
                      </div>
                      <div className="text-sm text-gray-700">{flow.action}</div>
                      <div className="text-[11px] font-mono text-gray-400">{flow.where}</div>
                      <StatusBadge 
                        label={flow.built ? "Built" : "To Build"} 
                        color={flow.built ? C.green : C.amber} 
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PriorityTab() {
  return (
    <div className="space-y-8">
      {PRIORITY_GROUPS.map((group) => (
        <div key={group.title}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-1 h-6 rounded" style={{ background: group.color }} />
            <h3 className="text-base font-medium text-gray-800" style={{ fontFamily: "Georgia, serif" }}>
              {group.title}
            </h3>
          </div>
          <div className="border rounded-xl overflow-hidden" style={{ borderColor: C.border }}>
            {group.items.map((item, ii) => (
              <div 
                key={ii}
                className={cn(
                  "grid grid-cols-[1fr_2fr_70px] gap-4 px-4 py-3 border-b items-start",
                  ii % 2 === 0 ? "bg-white" : "bg-gray-50/50",
                  item.done && "opacity-60"
                )}
                style={{ borderColor: C.border }}
              >
                <div className={cn(
                  "text-sm font-medium leading-snug",
                  item.done ? "line-through text-gray-400" : "text-gray-800"
                )}>
                  {item.done && <span className="text-green-500 mr-1">✓</span>}
                  {item.task}
                </div>
                <div className="text-xs text-gray-500 leading-relaxed">{item.detail}</div>
                <div 
                  className="text-[11px] font-mono font-medium px-2 py-1 rounded text-center"
                  style={{ 
                    color: group.color, 
                    background: `${group.color}10`,
                    border: `1px solid ${group.color}25`
                  }}
                >
                  {item.effort}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function IntegrationMap() {
  const { isLaVela, shortName } = useAdminBrand();
  const TC = getThemeColors(isLaVela);
  
  const [tab, setTab] = useState("sidebar");
  const tabs = [
    { id: "sidebar", label: "Complete Sidebar Map (34 items)" },
    { id: "automation", label: "Automation Flows" },
    { id: "priority", label: "Priority Roadmap" },
  ];
  
  const all = FULL_SIDEBAR.flatMap(s => s.items);

  return (
    <div className="min-h-screen" style={{ background: TC.bg }} data-testid="integration-map">
      {/* Header */}
      <div 
        className="bg-white border-b px-6 py-4 flex items-center justify-between"
        style={{ borderColor: C.border }}
      >
        <div className="flex items-center gap-4">
          <span 
            className="text-xl tracking-widest font-normal"
            style={{ fontFamily: "Georgia, serif", color: TC.dark }}
          >
            {shortName}
          </span>
          <span className="text-[10px] tracking-widest text-gray-400 uppercase">
            Full Platform Integration Map
          </span>
        </div>
        <div className="flex gap-4 text-[11px]">
          {Object.entries(STATUS).map(([k, v]) => (
            <div key={k} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ background: v.color }} />
              <span className="text-gray-500">{v.label}:</span>
              <span style={{ color: v.color }} className="font-semibold">
                {all.filter(i => i.status === k).length}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b flex px-6" style={{ borderColor: C.border }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "px-4 py-3 text-sm transition-colors border-b-2",
              tab === t.id 
                ? "border-pink-400 text-pink-500 font-medium" 
                : "border-transparent text-gray-500 hover:text-pink-400"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-6 max-w-[1100px] mx-auto">
        {tab === "sidebar" && <SidebarTab />}
        {tab === "automation" && <AutomationTab />}
        {tab === "priority" && <PriorityTab />}
      </div>

      {/* Footer Legend */}
      <div 
        className="border-t px-6 py-3 flex items-center gap-6 bg-white"
        style={{ borderColor: C.border }}
      >
        {Object.entries(STATUS).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5 text-[11px] text-gray-500">
            <div className="w-2 h-2 rounded-full" style={{ background: v.color }} />
            {v.label}
          </div>
        ))}
        <div className="ml-auto text-[11px] text-gray-400 font-mono">
          Reroots Aesthetics Inc. · 34 admin items mapped
        </div>
      </div>
    </div>
  );
}
